"""
Slot / rule statistics aligned with evm_analysis/train_hybrid.py routing.

Uses the same DATA_PATH, train/test split, and Fast Path definition:
  - Union of accessed_slots per (to, selector) computed on **training rows only**
  - Fast path iff len(union) <= FAST_PATH_THRESHOLD
  - Test routing: fast iff key in fast_path_dict; otherwise slow (either train-union too
    large, or key never seen in train — "cold").

Run with the same FAST_PATH_THRESHOLD as train_hybrid.py for numbers that match evaluation
(e.g. Test Set Routed to Fast Path %%).
"""

import argparse
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# --- Keep in sync with train_hybrid.py ---
DATA_PATH = '/home/tianyumao/workspace/transaction-replay/erigon_tx_trace.jsonl'
RANDOM_STATE = 42
TEST_SIZE = 0.2
FAST_PATH_THRESHOLD_DEFAULT = 152

PERCENTILES = [50, 75, 90, 95, 99]
# Train-only union CDF: 10%–90% step 10 (finer than PERCENTILES; no 95/99 tail)
PERCENTILES_TRAIN_UNION = list(range(10, 91, 10))


def load_data(path):
    data = []
    with open(path, 'r') as f:
        for line in f:
            if not line.strip():
                continue
            data.append(json.loads(line))
    return pd.DataFrame(data)


def calc_weighted_percentiles(values, weights, percentiles):
    sorted_indices = np.argsort(values)
    sorted_values = np.array(values)[sorted_indices]
    sorted_weights = np.array(weights)[sorted_indices]
    cum_weights = np.cumsum(sorted_weights)
    total_weight = cum_weights[-1]
    results = []
    for p in percentiles:
        target = total_weight * (p / 100.0)
        idx = np.searchsorted(cum_weights, target)
        results.append(sorted_values[idx])
    return results


def build_fast_path_from_train(df_train, fast_path_threshold):
    """Same logic as train_hybrid.py §3."""
    to_sel_slots = defaultdict(set)
    for _, row in df_train.iterrows():
        to_sel_slots[(row['to'], row['selector'])].update(row['accessed_slots'])

    fast_path_dict = {}
    slow_path_keys = set()
    for k, v in to_sel_slots.items():
        if len(v) <= fast_path_threshold:
            fast_path_dict[k] = list(v)
        else:
            slow_path_keys.add(k)
    return to_sel_slots, fast_path_dict, slow_path_keys


def analyze_test_routing(df_test, fast_path_dict, to_sel_slots_train):
    """
    Match train_hybrid evaluation: is_fast = (to, selector) in fast_path_dict.
    Slow breakdown: key not in train vs in train but union too large.
    """
    n = len(df_test)
    n_fast = 0
    n_slow_cold = 0  # (to, selector) never appeared in train
    n_slow_heavy = 0  # appeared in train but not in fast_path_dict

    for _, row in df_test.iterrows():
        key = (row['to'], row['selector'])
        if key in fast_path_dict:
            n_fast += 1
        elif key not in to_sel_slots_train:
            n_slow_cold += 1
        else:
            n_slow_heavy += 1

    assert n_fast + n_slow_cold + n_slow_heavy == n
    return {
        'n_test': n,
        'n_fast': n_fast,
        'n_slow_cold': n_slow_cold,
        'n_slow_heavy': n_slow_heavy,
        'pct_fast': n_fast / n if n else 0.0,
    }


def train_rule_tx_counts(df_train):
    """Per (to, selector), number of training rows (for weighted percentiles on train)."""
    c = defaultdict(int)
    for _, row in df_train.iterrows():
        c[(row['to'], row['selector'])] += 1
    return c


def export_train_union_cdf_csv(to_sel_slots, tx_counts, csv_path: str, label: str = 'to_selector'):
    """One row per train key: union_size, weight_tx_count (for weighted ECDF in plot_figures)."""
    keys = list(to_sel_slots.keys())
    rows = []
    for k in keys:
        rows.append(
            {
                'rule_key': str(k),
                'union_size': len(to_sel_slots[k]),
                'train_tx_count': tx_counts[k],
                'label': label,
            }
        )
    parent = os.path.dirname(os.path.abspath(csv_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    pd.DataFrame(rows).to_csv(csv_path, index=False)


def print_train_union_distribution(to_sel_slots, tx_counts, label):
    """CDF of train-only union sizes — same population hybrid uses to choose fast/slow rules."""
    keys = list(to_sel_slots.keys())
    union_sizes = [len(to_sel_slots[k]) for k in keys]
    weights = [tx_counts[k] for k in keys]

    print(f"\n  --- Train-only union size per {label} (same as hybrid profiling) ---")
    print(f"  Unique keys in train: {len(keys)}")
    print("  Unweighted (each key one vote), percentiles 10%–90%:")
    for p, val in zip(PERCENTILES_TRAIN_UNION, np.percentile(union_sizes, PERCENTILES_TRAIN_UNION)):
        print(f"    {p}% of train keys have union size <= {int(val)}")
    print("  Weighted by train transaction count per key, percentiles 10%–90%:")
    for p, val in zip(
        PERCENTILES_TRAIN_UNION,
        calc_weighted_percentiles(union_sizes, weights, PERCENTILES_TRAIN_UNION),
    ):
        print(f"    {p}% of train transactions belong to keys with union size <= {int(val)}")


def print_hybrid_aligned_report(df, fast_path_threshold, export_union_csv: str | None = None):
    df_train, df_test = train_test_split(
        df, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )
    print(f"\n{'=' * 60}")
    print("Hybrid-aligned (matches train_hybrid.py)")
    print(f"{'=' * 60}")
    print(f"  random_state={RANDOM_STATE}, test_size={TEST_SIZE}, FAST_PATH_THRESHOLD={fast_path_threshold}")
    print(f"  Train rows: {len(df_train)}, Test rows: {len(df_test)}")

    to_sel_slots, fast_path_dict, slow_path_keys = build_fast_path_from_train(
        df_train, fast_path_threshold
    )
    tx_counts = train_rule_tx_counts(df_train)

    print(f"\n  Fast Path rules (train union <= {fast_path_threshold}): {len(fast_path_dict)}")
    print(f"  Slow Path rules (train union > {fast_path_threshold}): {len(slow_path_keys)}")
    print(f"  Unique (to, selector) keys in train: {len(to_sel_slots)}")

    route = analyze_test_routing(df_test, fast_path_dict, to_sel_slots)
    print(f"\n  --- Test set routing (same definition as train_hybrid evaluation) ---")
    print(f"  Routed to Fast Path: {route['n_fast']} / {route['n_test']} = {route['pct_fast']:.2%}")
    print(f"  Routed to Slow Path (train key, union too large): {route['n_slow_heavy']} ({route['n_slow_heavy']/route['n_test']:.2%})")
    print(f"  Routed to Slow Path (key not in train — cold): {route['n_slow_cold']} ({route['n_slow_cold']/route['n_test']:.2%})")

    print_train_union_distribution(to_sel_slots, tx_counts, '(to, selector)')
    if export_union_csv:
        export_train_union_cdf_csv(to_sel_slots, tx_counts, export_union_csv, label='to_selector')
        print(f"\n  Wrote train union key table: {export_union_csv}")
    return df_train, df_test, to_sel_slots, tx_counts


# --- Optional: full-dataset exploratory stats (not comparable to hybrid routing) ---

def collect_per_rule_stats(df, key_cols):
    union_slots = defaultdict(set)
    per_tx_lens = defaultdict(list)
    for _, row in df.iterrows():
        key = tuple(row[c] for c in key_cols)
        slots = row.get('accessed_slots', [])
        if isinstance(slots, list):
            union_slots[key].update(slots)
            per_tx_lens[key].append(len(slots))
        else:
            per_tx_lens[key].append(0)
    keys = list(per_tx_lens.keys())
    weights = [len(per_tx_lens[k]) for k in keys]
    union_sizes = [len(union_slots[k]) for k in keys]
    mean_per_tx = [float(np.mean(per_tx_lens[k])) for k in keys]
    median_per_tx = [float(np.median(per_tx_lens[k])) for k in keys]
    return {
        'keys': keys,
        'weights': weights,
        'union_sizes': union_sizes,
        'mean_per_tx': mean_per_tx,
        'median_per_tx': median_per_tx,
    }


def print_per_tx_rule_metrics(title, stats):
    n_rules = len(stats['keys'])
    total_txs = sum(stats['weights'])
    print(f"\n  --- {title} (per-transaction slot counts, summarized per rule) ---")
    print(f"  Rules: {n_rules}, transactions: {total_txs}")
    for label, arr in [('mean len(accessed_slots) per tx', stats['mean_per_tx']),
                       ('median len(accessed_slots) per tx', stats['median_per_tx'])]:
        uw = np.percentile(arr, PERCENTILES)
        w = calc_weighted_percentiles(arr, stats['weights'], PERCENTILES)
        print(f"\n  Statistic: {label}")
        print("    [Unweighted over rules]:")
        for p, val in zip(PERCENTILES, uw):
            print(f"      {p}% of rules have {label} <= {val:.2f}")
        print("    [Weighted by transaction volume]:")
        for p, val in zip(PERCENTILES, w):
            print(f"      {p}% of transactions belong to rules with {label} <= {val:.2f}")


def print_historical_union_reference(title, stats):
    arr = stats['union_sizes']
    weights = stats['weights']
    print(f"\n  --- {title} (full-data historical union per rule) ---")
    uw = np.percentile(arr, PERCENTILES)
    w = calc_weighted_percentiles(arr, weights, PERCENTILES)
    print("    [Unweighted over rules]:")
    for p, val in zip(PERCENTILES, uw):
        print(f"      {p}% of rules have historical union size <= {int(val)}")
    print("    [Weighted by transaction volume]:")
    for p, val in zip(PERCENTILES, w):
        print(f"      {p}% of transactions belong to rules whose historical union size <= {int(val)}")


def print_global_per_tx_cdf(df):
    lens = []
    for _, row in df.iterrows():
        slots = row.get('accessed_slots', [])
        lens.append(len(slots) if isinstance(slots, list) else 0)
    lens = np.array(lens, dtype=float)
    print("\n--- Full data: single-transaction len(accessed_slots) ---")
    print(f"Transactions: {len(lens)}")
    for p in PERCENTILES:
        print(f"  {p}% of transactions access <= {np.percentile(lens, p):.2f} slots (this tx only)")


def analyze_full_dataset_exploratory(df):
    print("\n" + "#" * 60)
    print("# Full-dataset exploratory (NOT the same population as hybrid train-only union)")
    print("#" * 60)
    print_global_per_tx_cdf(df)
    print("\n" + "=" * 60)
    print("Group: (to, selector), full data")
    print("=" * 60)
    s1 = collect_per_rule_stats(df, ['to', 'selector'])
    print_per_tx_rule_metrics("(to, selector)", s1)
    print_historical_union_reference("(to, selector)", s1)
    print("\n" + "=" * 60)
    print("Group: (code_hash, selector), full data")
    print("=" * 60)
    s2 = collect_per_rule_stats(df, ['code_hash', 'selector'])
    print_per_tx_rule_metrics("(code_hash, selector)", s2)
    print_historical_union_reference("(code_hash, selector)", s2)


def main():
    parser = argparse.ArgumentParser(description='Slot stats; hybrid-aligned by default.')
    parser.add_argument(
        '--threshold', type=int, default=FAST_PATH_THRESHOLD_DEFAULT,
        help='FAST_PATH_THRESHOLD; must match train_hybrid.py for comparable routing %% (default: %(default)s)',
    )
    parser.add_argument(
        '--full-dataset',
        action='store_true',
        help='Also print full-data exploratory CDFs (per-tx / full-data union); not aligned with hybrid.',
    )
    parser.add_argument(
        '--data', type=str, default=DATA_PATH,
        help='Path to erigon_tx_trace.jsonl',
    )
    parser.add_argument(
        '--export-csv',
        type=str,
        default='',
        help='Directory or path: write figure1_train_union_keys.csv for plotting (default: evm_analysis/figures/data/)',
    )
    args = parser.parse_args()

    print("Loading data...")
    df = load_data(args.data)

    for col in ['to', 'code_hash', 'selector']:
        if col not in df.columns:
            df[col] = ''
        df[col] = df[col].fillna('').astype(str)

    df = df[df['selector'] != '0x'].copy()
    df['accessed_slots'] = df['accessed_slots'].apply(
        lambda x: x if isinstance(x, list) else []
    )
    print(f"Data size after filtering '0x' selector: {len(df)}")

    export_path = None
    if args.export_csv:
        base = args.export_csv if args.export_csv.endswith('.csv') else os.path.join(
            args.export_csv, 'figure1_train_union_keys.csv'
        )
        export_path = base

    print_hybrid_aligned_report(df, args.threshold, export_union_csv=export_path)

    if args.full_dataset:
        analyze_full_dataset_exploratory(df)


if __name__ == '__main__':
    main()
