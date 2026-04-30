"""
Top-K slot vocabulary coverage (aligned with train_light_gbm / train.py).

Definitions (same as training scripts):
  - Globally rank slots by how often they appear in `accessed_slots` across all rows
    (each list element counts one "access").
  - Top-K = the K most frequent slot identities.

Metrics:
  1) Access-mass coverage: (sum of frequencies of Top-K slots) / (total slot accesses).
     If this is low, recall capped by Top-K label space is structurally limited.
  2) Per-transaction: for each tx, hits = # of accesses whose slot is in Top-K,
     ratio = hits / len(accessed_slots). Summarize mean/median/percentiles — this is
     the per-tx recall upper bound when the model only predicts within Top-K.

Optional: --train-only-topk builds Top-K from train split only, then measures coverage
on train and test (closer to generalization story).
"""

import argparse
import json
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

DATA_PATH = '/home/tianyumao/workspace/transaction-replay/erigon_tx_trace.jsonl'
RANDOM_STATE = 42
TEST_SIZE = 0.2
K_LIST = [1000, 5000, 10000]


def load_data(path):
    data = []
    with open(path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            data.append(json.loads(line))
    return pd.DataFrame(data)


def prepare_df(path):
    df = load_data(path)
    for col in ['to', 'code_hash', 'selector']:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)
    df = df[df['selector'] != '0x'].copy()
    df['accessed_slots'] = df['accessed_slots'].apply(
        lambda x: x if isinstance(x, list) else []
    )
    return df


def slot_counter_from_df(df):
    """Flatten: one count per slot occurrence in each tx's list."""
    all_slots = [s for slots in df['accessed_slots'] for s in slots]
    return Counter(all_slots), len(all_slots)


def topk_set_from_counter(slot_counts, k):
    k = min(k, len(slot_counts))
    return set(s for s, _ in slot_counts.most_common(k))


def access_mass_coverage(slot_counts, total_accesses, k):
    top_sum = sum(c for _, c in slot_counts.most_common(k))
    return top_sum / total_accesses if total_accesses else 0.0


def per_tx_hit_ratios(df, topk_set):
    """One ratio per row: accesses landing in topk / len(accessed_slots)."""
    ratios = []
    hits_list = []
    lens = []
    for slots in df['accessed_slots']:
        n = len(slots)
        if n == 0:
            continue
        hits = sum(1 for s in slots if s in topk_set)
        ratios.append(hits / n)
        hits_list.append(hits)
        lens.append(n)
    return np.array(ratios), np.array(hits_list), np.array(lens)


def collect_coverage_rows(df, slot_counts, total_accesses, k_list, split_label: str):
    """Rows for CSV export (figure 3)."""
    n_unique = len(slot_counts)
    rows = []
    for k in k_list:
        k_eff = min(k, n_unique)
        mass = access_mass_coverage(slot_counts, total_accesses, k_eff)
        topk_set = topk_set_from_counter(slot_counts, k_eff)
        ratios, _, _ = per_tx_hit_ratios(df, topk_set)
        mean_ratio = float(ratios.mean()) if len(ratios) else float('nan')
        rows.append(
            {
                'split': split_label,
                'k_requested': k,
                'k_effective': k_eff,
                'access_mass_coverage': mass,
                'mean_per_tx_hit_ratio': mean_ratio,
                'total_accesses': total_accesses,
                'unique_slots': n_unique,
            }
        )
    return rows


def print_report(title, df, slot_counts, total_accesses, k_list):
    n_unique = len(slot_counts)
    print(f"\n{'=' * 60}")
    print(title)
    print(f"{'=' * 60}")
    print(f"  Transactions: {len(df)}")
    print(f"  Total slot accesses (sum of len(accessed_slots)): {total_accesses}")
    print(f"  Unique slot identities: {n_unique}")

    qs = [5, 10, 25, 50, 75, 90, 95]

    for k in k_list:
        if k > n_unique:
            print(f"\n  --- K={k} (clamped: only {n_unique} unique slots exist) ---")
            k_eff = n_unique
        else:
            k_eff = k
            print(f"\n  --- K={k} ---")

        mass = access_mass_coverage(slot_counts, total_accesses, k_eff)
        print(f"  Access-mass coverage: {100.0 * mass:.4f}% of all accesses hit a Top-{k_eff} slot")

        topk_set = topk_set_from_counter(slot_counts, k_eff)
        ratios, hits_arr, lens_arr = per_tx_hit_ratios(df, topk_set)
        if len(ratios) == 0:
            print("  No non-empty accessed_slots rows.")
            continue

        print(f"  Per-tx hit ratio (hits/len(slots) for each tx), over txs with len>0:")
        print(f"    mean={ratios.mean():.4f}, median={np.median(ratios):.4f}")
        for q in qs:
            print(f"    p{q}: {np.percentile(ratios, q):.4f}")

        print(f"  Per-tx absolute hits (how many accesses covered by Top-K), txs with len>0:")
        print(f"    mean hits={hits_arr.mean():.2f}, mean |slots|={lens_arr.mean():.2f}")
        for q in qs:
            print(f"    p{q} hits: {np.percentile(hits_arr, q):.2f}")

        all_in_topk = np.mean(ratios >= 1.0 - 1e-15)
        print(f"  Share of txs with 100% of accesses in Top-K: {all_in_topk:.2%}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default=DATA_PATH)
    ap.add_argument(
        '--train-only-topk',
        action='store_true',
        help='Build Top-K from train split only; report coverage on train and test separately.',
    )
    ap.add_argument(
        '--k',
        type=int,
        nargs='*',
        default=K_LIST,
        help='K values (default: 1000 5000 10000)',
    )
    ap.add_argument(
        '--export-csv',
        default='',
        help='Write figure3_topk_coverage.csv (default: evm_analysis/figures/data/)',
    )
    args = ap.parse_args()

    df = prepare_df(args.data)
    k_list = sorted(set(args.k))
    export_rows = []

    if not args.train_only_topk:
        slot_counts, total_accesses = slot_counter_from_df(df)
        print_report('Full dataset (Top-K from all txs — same as train_light_gbm default)', df, slot_counts, total_accesses, k_list)
        export_rows.extend(collect_coverage_rows(df, slot_counts, total_accesses, k_list, 'full'))
        _write_topk_csv(args.export_csv or None, export_rows)
        return

    df_train, df_test = train_test_split(df, test_size=TEST_SIZE, random_state=RANDOM_STATE)
    print(f"\nTrain/test split: random_state={RANDOM_STATE}, test_size={TEST_SIZE}")
    print(f"Train rows: {len(df_train)}, Test rows: {len(df_test)}")

    slot_counts_tr, tot_tr = slot_counter_from_df(df_train)
    print_report('Train: Top-K from TRAIN only; coverage on TRAIN rows', df_train, slot_counts_tr, tot_tr, k_list)
    export_rows.extend(collect_coverage_rows(df_train, slot_counts_tr, tot_tr, k_list, 'train'))

    # Test rows: frequencies for access-mass on test only, but Top-K set from train
    _, tot_te = slot_counter_from_df(df_test)
    print(f"\n  (Test total accesses: {tot_te}, for per-tx stats below)")
    for k in k_list:
        k_eff = min(k, len(slot_counts_tr))
        topk_set = topk_set_from_counter(slot_counts_tr, k_eff)
        # access mass on test: how many test accesses hit train-defined Top-K
        test_slots_flat = [s for slots in df_test['accessed_slots'] for s in slots]
        test_hits = sum(1 for s in test_slots_flat if s in topk_set)
        mass_te = test_hits / len(test_slots_flat) if test_slots_flat else 0.0
        ratios, hits_arr, lens_arr = per_tx_hit_ratios(df_test, topk_set)
        export_rows.append(
            {
                'split': 'test_train_topk',
                'k_requested': k,
                'k_effective': k_eff,
                'access_mass_coverage': mass_te,
                'mean_per_tx_hit_ratio': float(ratios.mean()) if len(ratios) else float('nan'),
                'total_accesses': tot_te,
                'unique_slots': len(slot_counts_tr),
            }
        )
        print(f"\n  --- TEST rows, Top-{k_eff} from TRAIN only ---")
        print(f"  Access-mass coverage on test: {100.0 * mass_te:.4f}% of test accesses hit train Top-{k_eff}")
        if len(ratios):
            print(f"  Per-tx hit ratio on test: mean={ratios.mean():.4f}, median={np.median(ratios):.4f}")
    _write_topk_csv(args.export_csv or None, export_rows)


def _write_topk_csv(export_arg: str | None, rows: list) -> None:
    if not rows:
        return
    import os

    path = export_arg
    if not path:
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'figures', 'data', 'figure3_topk_coverage.csv')
    elif not str(path).endswith('.csv'):
        path = os.path.join(path, 'figure3_topk_coverage.csv')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    print(f"\nWrote {path}")


if __name__ == '__main__':
    main()
