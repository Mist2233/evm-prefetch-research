"""
Sweep FAST_PATH_THRESHOLD: rebuild fast_path_dict from train only, reuse saved Slow-path
LightGBM from evm_model_hybrid_v1.pkl (approximate Pareto; slow model fixed).

Exports CSV for figure 4a (hybrid Pareto).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
_modeling = _here.parent / 'modeling'
if str(_modeling) not in sys.path:
    sys.path.insert(0, str(_modeling))

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split

from train_hybrid import DATA_PATH, MODEL_DIR, RANDOM_STATE, calc_metrics, load_data  # noqa: E402

TEST_SIZE = 0.2

HYBRID_PKL = os.path.join(MODEL_DIR, 'evm_model_hybrid_v1.pkl')
DEFAULT_THRESHOLDS = [10, 32, 50, 79, 100, 150, 152, 200]


def encode_df_like_predict(df: pd.DataFrame, encoders: dict, feature_cols: list) -> pd.DataFrame:
    df = df.copy()
    for col in encoders.keys():
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)
        le = encoders[col]
        # Fast path: vectorized transform (same dataset domain as training, so usually no OOV).
        try:
            df[f'f_{col}'] = le.transform(df[col])
        except ValueError:
            # Safe fallback for potential OOV when a different dataset is provided.
            class_to_idx = {c: i for i, c in enumerate(le.classes_)}
            fallback_idx = 0
            df[f'f_{col}'] = df[col].map(lambda x: class_to_idx.get(x, fallback_idx)).astype(int)
    return df


def build_train_unions(df_train) -> dict:
    to_sel_slots = defaultdict(set)
    for _, row in df_train.iterrows():
        to_sel_slots[(row['to'], row['selector'])].update(row['accessed_slots'])
    return to_sel_slots


def fast_dict_for_threshold(to_sel_slots: dict, threshold: int) -> dict:
    return {k: list(v) for k, v in to_sel_slots.items() if len(v) <= threshold}


def precompute_slow_pred_per_row(df_test: pd.DataFrame, model, mlb, feature_cols: list) -> dict:
    """One batched predict for entire test set; then per-row slow preds (for routing reuse)."""
    X = df_test[feature_cols]
    ml_preds_sparse = model.predict(X)
    inv = mlb.inverse_transform(ml_preds_sparse)
    return {idx: list(inv[i]) for i, idx in enumerate(df_test.index)}


def evaluate_threshold(
    df_test: pd.DataFrame,
    fast_path_dict: dict,
    slow_pred_cache: dict,
) -> tuple[float, float, float, float]:
    y_true_all = []
    preds_all = []
    n_fast = 0
    for idx, row in df_test.iterrows():
        key = (row['to'], row['selector'])
        y_true_all.append(row['accessed_slots'])
        if key in fast_path_dict:
            preds_all.append(fast_path_dict[key])
            n_fast += 1
        else:
            preds_all.append(slow_pred_cache[idx])
    rec_all, prec_all, em_all = calc_metrics(y_true_all, preds_all)
    fast_pct = n_fast / len(df_test) if len(df_test) else 0.0
    return rec_all, prec_all, em_all, fast_pct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=DATA_PATH)
    ap.add_argument('--hybrid-pkl', default=HYBRID_PKL)
    ap.add_argument(
        '--thresholds',
        type=int,
        nargs='*',
        default=DEFAULT_THRESHOLDS,
    )
    ap.add_argument(
        '--export-csv',
        default='',
        help='Path to write hybrid_pareto.csv (default: evm_analysis/figures/data/hybrid_pareto.csv)',
    )
    ap.add_argument(
        '--max-test-rows',
        type=int,
        default=0,
        help='Subsample test set for faster sweep (0 = full test set)',
    )
    args = ap.parse_args()

    if not os.path.isfile(args.hybrid_pkl):
        print(f"Missing {args.hybrid_pkl}; run train_hybrid.py first.")
        return 1

    save = joblib.load(args.hybrid_pkl)
    model = save['model']
    mlb = save['mlb']
    encoders = save['encoders']
    feature_cols = save['feature_cols']

    df = load_data(args.data)
    for col in ['to', 'code_hash', 'selector', 'input_param_1', 'input_param_2', 'input_param_3', 'from', 'value']:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)
    df = df[df['selector'] != '0x'].copy()
    df['accessed_slots'] = df['accessed_slots'].apply(lambda x: x if isinstance(x, list) else [])

    df = encode_df_like_predict(df, encoders, feature_cols)
    df_train, df_test = train_test_split(df, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    if args.max_test_rows > 0 and len(df_test) > args.max_test_rows:
        df_test = df_test.sample(n=args.max_test_rows, random_state=RANDOM_STATE)
        print(f"Subsampled test to n={args.max_test_rows} for sweep")
    to_sel_slots = build_train_unions(df_train)

    print("Precomputing slow-path predictions for all test rows (one batch)...")
    slow_pred_cache = precompute_slow_pred_per_row(df_test, model, mlb, feature_cols)

    rows = []
    for t in sorted(set(args.thresholds)):
        fast_path_dict = fast_dict_for_threshold(to_sel_slots, t)
        rec, prec, em, fpct = evaluate_threshold(df_test, fast_path_dict, slow_pred_cache)
        rows.append(
            {
                'fast_path_threshold': t,
                'recall_overall': rec,
                'precision_overall': prec,
                'exact_match_overall': em,
                'fast_path_tx_fraction': fpct,
            }
        )
        print(f"threshold={t} recall={rec:.4f} precision={prec:.4f} fast%={fpct:.4f}")

    out = pd.DataFrame(rows)
    csv_path = args.export_csv or os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'figures', 'data', 'hybrid_pareto.csv'
    )
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    out.to_csv(csv_path, index=False)
    print(f"Wrote {csv_path}")
    print("Note: set-based recall/precision (train_hybrid.calc_metrics); slow model fixed from pkl.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
