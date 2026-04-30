"""
Microbenchmark: pure Python inference latency (not Erigon production).

Measures:
  - Fast path: dict lookup + list fetch for (to, selector) -> slots
  - Slow path: MultiOutputClassifier.predict + MultiLabelBinarizer.inverse_transform (1 row)
  - Hybrid expected latency: p_fast * t_fast + p_slow * t_slow

Optional:
  - Pure LightGBM: every row uses slow path (same model as hybrid slow)
  - Pure DecisionTree: load evm_model_v1.pkl if present, predict all rows

Requires trained joblib artifacts (run train_hybrid.py / train_light_gbm.py / train.py first).

Example:
  python benchmark_inference_latency.py --sample 2000 --repeat 5 --warmup 50
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from pathlib import Path

import joblib
import pandas as pd

DEFAULT_DATA = '/home/tianyumao/workspace/transaction-replay/erigon_tx_trace.jsonl'
HYBRID_PATH = '/home/tianyumao/workspace/transaction-replay/evm_analysis/models/evm_model_hybrid_v1.pkl'
LGBM_PATH = '/home/tianyumao/workspace/transaction-replay/evm_analysis/models/evm_model_lgbm_v1.pkl'
DT_PATH = '/home/tianyumao/workspace/transaction-replay/evm_analysis/models/evm_model_v1.pkl'


def load_jsonl_rows(path: str, limit: int) -> pd.DataFrame:
    rows = []
    with open(path, 'r') as f:
        for i, line in enumerate(f):
            if not line.strip():
                continue
            rows.append(json.loads(line))
            if i + 1 >= limit:
                break
    return pd.DataFrame(rows)


def prepare_hybrid_df(df: pd.DataFrame, encoders: dict, feature_cols: list) -> pd.DataFrame:
    for col in encoders.keys():
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)
        le = encoders[col]
        known = set(le.classes_)
        fallback = le.classes_[0] if len(le.classes_) > 0 else 0
        df[f'f_{col}'] = df[col].apply(
            lambda x, le=le, k=known, fb=fallback: le.transform([x])[0] if x in k else le.transform([fb])[0]
        )
    return df


def safe_encode_series(series, encoder):
    if encoder is None:
        return series.apply(lambda _: 0)
    known = set(encoder.classes_)
    fb = encoder.classes_[0] if len(encoder.classes_) else 0
    return series.apply(lambda x: encoder.transform([x])[0] if x in known else encoder.transform([fb])[0])


def prepare_lgbm_df(df: pd.DataFrame, save_data: dict) -> pd.DataFrame:
    for col in ['to', 'code_hash', 'selector', 'input_param_1', 'input_param_2', 'input_param_3', 'from', 'value']:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)
    sd = save_data
    df['f_to'] = safe_encode_series(df['to'], sd['le_to'])
    df['f_code_hash'] = safe_encode_series(df['code_hash'], sd.get('le_code_hash'))
    df['f_sel'] = safe_encode_series(df['selector'], sd['le_sel'])
    df['f_param'] = safe_encode_series(df['input_param_1'], sd['le_param'])
    df['f_param2'] = safe_encode_series(df['input_param_2'], sd.get('le_param2'))
    df['f_param3'] = safe_encode_series(df['input_param_3'], sd.get('le_param3'))
    df['f_from'] = safe_encode_series(df['from'], sd.get('le_from'))
    df['f_value'] = safe_encode_series(df['value'], sd.get('le_value'))
    feats = sd.get('features_used', ['f_to', 'f_code_hash', 'f_sel', 'f_param', 'f_param2', 'f_param3', 'f_from', 'f_value'])
    return df[feats]


def prepare_dt_df(df: pd.DataFrame, save_data: dict) -> pd.DataFrame:
    return prepare_lgbm_df(df, save_data)


def bench_fast_only(rows_df: pd.DataFrame, fast_path_dict: dict) -> list[float]:
    times = []
    for _, row in rows_df.iterrows():
        key = (row['to'], row['selector'])
        t0 = time.perf_counter()
        _ = fast_path_dict[key]
        times.append(time.perf_counter() - t0)
    return times


def bench_slow_only(rows_df: pd.DataFrame, model, mlb, feature_matrix: pd.DataFrame) -> list[float]:
    times = []
    for i in range(len(feature_matrix)):
        X = feature_matrix.iloc[i : i + 1]
        t0 = time.perf_counter()
        sp = model.predict(X)
        _ = list(mlb.inverse_transform(sp)[0])
        times.append(time.perf_counter() - t0)
    return times


def median_ms(seconds: list[float]) -> float:
    return statistics.median(seconds) * 1000.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=DEFAULT_DATA)
    ap.add_argument('--sample', type=int, default=2000, help='Number of txs to benchmark')
    ap.add_argument('--repeat', type=int, default=5, help='Repeat full pass for stability')
    ap.add_argument('--warmup', type=int, default=30, help='Warmup iterations per path')
    ap.add_argument('--hybrid', default=HYBRID_PATH)
    ap.add_argument('--lgbm', default=LGBM_PATH)
    ap.add_argument('--dt', default=DT_PATH)
    ap.add_argument('--skip-lgbm', action='store_true', help='Skip pure LightGBM baseline timing')
    ap.add_argument('--skip-dt', action='store_true', help='Skip pure DecisionTree baseline timing')
    ap.add_argument(
        '--batch-mode',
        action='store_true',
        help='Use batched timing (faster): one predict() over all rows per repeat.',
    )
    ap.add_argument(
        '--export-csv',
        default='',
        help='Write figure5_inference_latency.csv (median ms per mode)',
    )
    args = ap.parse_args()

    if not os.path.isfile(args.hybrid):
        print(f"Hybrid model not found: {args.hybrid}")
        print("Train with: python train_hybrid.py")
        return 1

    print(f"Loading data ({args.sample} rows)...")
    df = load_jsonl_rows(args.data, args.sample)
    df = df[df['selector'].fillna('').astype(str) != '0x'].copy()
    print(f"Rows after filter: {len(df)}")

    save = joblib.load(args.hybrid)
    fast_path_dict = save['fast_path_dict']
    model = save['model']
    mlb = save['mlb']
    encoders = save['encoders']
    feature_cols = save['feature_cols']

    df_h = prepare_hybrid_df(df.copy(), encoders, feature_cols)
    X_h = df_h[feature_cols]

    is_fast = df_h.apply(lambda r: (r['to'], r['selector']) in fast_path_dict, axis=1)
    df_fast = df_h[is_fast]
    df_slow = df_h[~is_fast]
    p_fast = len(df_fast) / len(df_h) if len(df_h) else 0.0
    p_slow = 1.0 - p_fast

    print(f"Routing on sample: fast={p_fast:.2%}, slow={p_slow:.2%}")

    # Warmup
    for _ in range(args.warmup):
        if len(df_fast):
            _ = fast_path_dict[(df_fast.iloc[0]['to'], df_fast.iloc[0]['selector'])]
        if len(df_slow):
            _ = model.predict(X_h.iloc[0:1])
            _ = mlb.inverse_transform(_)

    def run_pass():
        t_fast = bench_fast_only(df_fast, fast_path_dict) if len(df_fast) else []
        t_slow = bench_slow_only(df_slow, model, mlb, X_h.loc[df_slow.index]) if len(df_slow) else []
        return t_fast, t_slow

    all_fast, all_slow = [], []
    for _ in range(args.repeat):
        tf, ts = run_pass()
        all_fast.extend(tf)
        all_slow.extend(ts)

    med_f = median_ms(all_fast) if all_fast else 0.0
    med_s = median_ms(all_slow) if all_slow else 0.0
    hybrid_est = p_fast * med_f + p_slow * med_s

    print('\n=== Hybrid components (median per tx, ms) ===')
    print(f'  Fast path (dict lookup), n={len(all_fast)//max(1,args.repeat)} per pass: {med_f:.4f} ms')
    print(f'  Slow path (LGBM+inverse), n={len(all_slow)//max(1,args.repeat)} per pass: {med_s:.4f} ms')
    print(f'  Weighted hybrid (p_fast*t_fast + p_slow*t_slow): {hybrid_est:.4f} ms/tx')

    # Pure LGBM on same rows (all slow-style)
    if (not args.skip_lgbm) and os.path.isfile(args.lgbm):
        lgbm_save = joblib.load(args.lgbm)
        lgbm_model = lgbm_save['model']
        lgbm_mlb = lgbm_save['mlb']
        X_lgbm = prepare_lgbm_df(df.copy(), lgbm_save)
        for _ in range(args.warmup):
            _ = lgbm_model.predict(X_lgbm.iloc[0:1])
            _ = lgbm_mlb.inverse_transform(_)
        t_lgbm = []
        for _ in range(args.repeat):
            if args.batch_mode:
                t0 = time.perf_counter()
                y_pred = lgbm_model.predict(X_lgbm)
                _ = lgbm_mlb.inverse_transform(y_pred)
                elapsed = time.perf_counter() - t0
                per_tx = elapsed / max(len(X_lgbm), 1)
                t_lgbm.extend([per_tx] * len(X_lgbm))
            else:
                t_lgbm.extend(bench_slow_only(df, lgbm_model, lgbm_mlb, X_lgbm))
        med_lgbm = median_ms(t_lgbm)
        print('\n=== Pure LightGBM (all txs use full model) ===')
        print(f'  Median: {med_lgbm:.4f} ms/tx')
        print(f'  vs hybrid weighted: {hybrid_est:.4f} ms (ratio hybrid/lgbm = {hybrid_est/med_lgbm if med_lgbm else 0:.3f})')

    if (not args.skip_dt) and os.path.isfile(args.dt):
        dt_save = joblib.load(args.dt)
        dt_model = dt_save['model']
        dt_mlb = dt_save['mlb']
        X_dt = prepare_dt_df(df.copy(), dt_save)
        feats_dt = dt_save.get('features_used', list(X_dt.columns))
        X_dt = X_dt[feats_dt]
        for _ in range(args.warmup):
            _ = dt_model.predict(X_dt.iloc[0:1])
            _ = dt_mlb.inverse_transform(_)
        t_dt = []
        for _ in range(args.repeat):
            if args.batch_mode:
                t0 = time.perf_counter()
                y_pred = dt_model.predict(X_dt)
                _ = dt_mlb.inverse_transform(y_pred)
                elapsed = time.perf_counter() - t0
                per_tx = elapsed / max(len(X_dt), 1)
                t_dt.extend([per_tx] * len(X_dt))
            else:
                t_dt.extend(bench_slow_only(df, dt_model, dt_mlb, X_dt))
        med_dt = median_ms(t_dt)
        print('\n=== Pure DecisionTree (all txs) ===')
        print(f'  Median: {med_dt:.4f} ms/tx')

    print('\nNotes:')
    print('  - Single-threaded sklearn; production may differ.')
    print('  - Hybrid uses same LGBM as slow path; fast path dominates when p_fast is large.')
    print('  - For bar charts, use median ms with [optional] error bars from repeat passes.')

    rows = [{'mode': 'hybrid_weighted', 'median_ms_per_tx': hybrid_est}]
    if (not args.skip_lgbm) and os.path.isfile(args.lgbm):
        rows.append({'mode': 'pure_lightgbm', 'median_ms_per_tx': med_lgbm})
    if (not args.skip_dt) and os.path.isfile(args.dt):
        rows.append({'mode': 'pure_decision_tree', 'median_ms_per_tx': med_dt})

    out = args.export_csv
    if not out:
        out = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'figures', 'data', 'figure5_inference_latency.csv')
    elif not out.endswith('.csv'):
        out = os.path.join(out, 'figure5_inference_latency.csv')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nWrote {out}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
