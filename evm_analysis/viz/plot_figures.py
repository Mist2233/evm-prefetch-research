"""
Generate paper figures from CSVs in evm_analysis/figures/data/ (see plan).

Metrics:
  - Figure 2: LightGBM/DT label-matrix recall/precision (train_light_gbm.calculate_metrics).
  - Figure 4: Hybrid set-based recall/precision (train_hybrid.calc_metrics).

Run data export scripts first, or use --regenerate-data where implemented.

Example:
  python plot_figures.py --all
  python plot_figures.py --only 1 2 4
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EVM_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = EVM_DIR / 'figures' / 'data'
OUT_DIR = EVM_DIR / 'figures'


def _ensure_out():
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _savefig(fig, stem: str):
    """Save figure as both PNG (quick preview) and PDF (LaTeX)."""
    for ext in ["png", "pdf"]:
        path = OUT_DIR / f"{stem}.{ext}"
        fig.savefig(path, dpi=150 if ext == "png" else 300, bbox_inches="tight")
        print(f"Wrote {path}")


def plot_figure1a_union_cdf(csv_path: Path | None = None) -> Path | None:
    """Training-only union size ECDF: unweighted (each pattern key) vs weighted (by training tx count)."""
    path = csv_path or DATA_DIR / 'figure1_train_union_keys.csv'
    if not path.is_file():
        print(f"Skip fig1a: missing {path}")
        return None
    df = pd.read_csv(path)
    sizes = df['union_size'].values.astype(float)

    order = np.argsort(sizes)
    x = sizes[order]

    x_u = np.sort(sizes)
    y_u = np.arange(1, len(x_u) + 1, dtype=float) / len(x_u)

    _ensure_out()
    fig, ax = plt.subplots(figsize=(7.5, 3.5))
    ax.plot(x_u, y_u, label='Union size per pattern key', color='#2C4A6E', linewidth=1.5, marker='^', markevery=0.05, markersize=5, markerfacecolor='white')
    ax.set_xlabel('Union size per pattern key (to, selector)', fontsize=13)
    ax.set_ylabel('CDF', fontsize=13)
    ax.tick_params(axis='both', labelsize=12)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_xscale('symlog', linthresh=10)
    fig.tight_layout()
    _savefig(fig, 'fig_cdf')
    plt.close(fig)
    return OUT_DIR / 'fig_cdf.pdf'


def plot_figure2_merged(merged_csv: Path | None = None) -> list[Path]:
    """Bar/line plots from metrics_figure2_merged.csv."""
    path = merged_csv or DATA_DIR / 'metrics_figure2_merged.csv'
    if not path.is_file():
        print(f"Skip fig2: missing {path} (run load_paper_metrics.export_merged_csv)")
        return []

    df = pd.read_csv(path)
    df['strategy_norm'] = df['strategy'].astype(str).str.lower()
    df['n_num'] = pd.to_numeric(df['n'], errors='coerce')
    is_max = df['strategy_norm'].str.contains('max', na=False)
    full_feat = 'to+sel+params+codehash+from+value'

    out_paths = []
    _ensure_out()

    # 2a: same k,n, strategy; compare features (DT vs LightGBM)
    sub0 = df[
        (df['k'] == 1000)
        & (df['n'].astype(str) == '-')
        & (df['strategy_norm'] == 'default')
        & (df['sheet'].isin(['Sheet1', 'Sheet2', 'Sheet3']))
    ].copy()
    if len(sub0) > 0:
        fig, ax = plt.subplots(figsize=(9, 4.8))
        # Keep top feature names concise on x-axis
        sub0['feature_short'] = sub0['features'].str.replace('to+selector', 'to+sel', regex=False)
        cats = sorted(sub0['feature_short'].unique())
        x = np.arange(len(cats))
        w = 0.18
        # four bars: DT recall/prec + LGBM recall/prec (where available)
        for i, (model, metric, color, ls) in enumerate(
            [
                ('DT', 'recall_topk', '#1f77b4', 'rec'),
                ('DT', 'precision', '#6baed6', 'prec'),
                ('LightGBM', 'recall_topk', '#ff7f0e', 'rec'),
                ('LightGBM', 'precision', '#fdae6b', 'prec'),
            ]
        ):
            vals = []
            for c in cats:
                g = sub0[(sub0['feature_short'] == c) & (sub0['model'] == model)]
                vals.append(float(g.iloc[0][metric]) if len(g) else np.nan)
            ax.bar(x + (i - 1.5) * w, vals, width=w, label=f'{model} {ls}', color=color)
        ax.set_xticks(x)
        ax.set_xticklabels(cats, rotation=20, ha='right')
        ax.set_ylabel('Metric (label matrix)')
        ax.set_title('Fig 2a: Feature comparison (k=1000, strategy=default)')
        ax.legend(fontsize=8, ncol=2)
        ax.grid(True, axis='y', alpha=0.3)
        fig.tight_layout()
        _savefig(fig, 'fig2a_feature_compare')
        plt.close(fig)
        out_paths.append(OUT_DIR / 'fig2a_feature_compare.pdf')

    # 2b: same features + k; n sweep
    sub1 = df[
        (df['k'] == 1000)
        & is_max
        & (df['features'] == full_feat)
        & (df['sheet'].isin(['Sheet2', 'Sheet3']))
    ].copy()
    if len(sub1) > 0:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for (model, sheet), g in sub1.groupby(['model', 'sheet']):
            g = g.sort_values('n_num')
            lab = f'{model} ({sheet})'
            ax.plot(g['n_num'], g['recall_topk'], marker='o', label=f'{lab} recall')
            ax.plot(g['n_num'], g['precision'], marker='s', linestyle='--', label=f'{lab} prec')
        ax.set_xlabel('N (predicted slots per tx)')
        ax.set_ylabel('Metric')
        ax.set_title('Fig 2b: n sweep (k=1000, full features, max strategy)')
        ax.legend(fontsize=7, loc='best')
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        _savefig(fig, 'fig2b_n_sweep')
        plt.close(fig)
        out_paths.append(OUT_DIR / 'fig2b_n_sweep.pdf')

    # 2d: DT (Sheet2) vs LightGBM (Sheet3), k=1000, n=10, max strategy, full features
    sub = df[
        (df['k'] == 1000)
        & (df['n_num'] == 10)
        & is_max
        & (df['features'] == full_feat)
        & (df['sheet'].isin(['Sheet2', 'Sheet3']))
    ].drop_duplicates(subset=['sheet'], keep='last')
    if len(sub) >= 2:
        sub = sub.sort_values('sheet')
        fig, ax = plt.subplots(figsize=(6, 4))
        labs = [f"{r['model']}\n({r['sheet']})" for _, r in sub.iterrows()]
        x = np.arange(len(sub))
        w = 0.25
        ax.bar(x - w, sub['recall_topk'], width=w, label='Top-K Recall')
        ax.bar(x, sub['recall_total'], width=w, label='Total Recall')
        ax.bar(x + w, sub['precision'], width=w, label='Precision')
        ax.set_xticks(x)
        ax.set_xticklabels(labs, rotation=12)
        ax.set_ylabel('Metric (label matrix)')
        ax.set_title('Fig 2d: DT vs LightGBM (k=1000, n=10, max strategy, full features)')
        ax.legend()
        ax.grid(True, axis='y', alpha=0.3)
        fig.tight_layout()
        _savefig(fig, 'fig2d_model_compare_bar')
        plt.close(fig)
        out_paths.append(OUT_DIR / 'fig2d_model_compare_bar.pdf')

    # 2c: K sweep using DEFAULT strategy (precision trend is clearer/monotonic in this view)
    sub2 = df[
        (df['n'].astype(str) == '-')
        & (df['strategy_norm'] == 'default')
        & (df['features'] == full_feat)
        & (df['sheet'].isin(['Sheet2', 'Sheet3']))
    ].copy()
    if len(sub2) > 0:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for (model, sheet), g in sub2.groupby(['model', 'sheet']):
            g = g.sort_values('k')
            lab = f'{model} ({sheet})'
            ax.plot(g['k'], g['recall_topk'], marker='o', label=f'{lab} top-k recall')
            ax.plot(g['k'], g['precision'], marker='s', linestyle='--', label=f'{lab} precision')
        ax.set_xlabel('K (Top-K slots)')
        ax.set_ylabel('Metric')
        ax.set_title('Fig 2c: k sweep (label matrix, default strategy)')
        ax.legend(fontsize=7, loc='best')
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        _savefig(fig, 'fig2c_k_sweep')
        plt.close(fig)
        out_paths.append(OUT_DIR / 'fig2c_k_sweep.pdf')

    return out_paths


def plot_figure3_topk(csv_path: Path | None = None) -> Path | None:
    path = csv_path or DATA_DIR / 'figure3_topk_coverage.csv'
    if not path.is_file():
        print(f"Skip fig3: missing {path}")
        return None
    df = pd.read_csv(path)
    sub = df[df['split'] == 'full'] if 'split' in df.columns else df
    if sub.empty:
        sub = df
    _ensure_out()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(sub['k_effective'], sub['access_mass_coverage'] * 100.0, marker='o')
    ax.set_xlabel('K (Top-K frequent slots)')
    ax.set_ylabel('Access-mass coverage (%)')
    ax.set_title('Fig 3a: Top-K vs share of slot accesses (full data)')
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    _savefig(fig, 'fig3a_topk_access_mass')
    plt.close(fig)
    return OUT_DIR / 'fig3a_topk_access_mass.pdf'


def plot_figure4_hybrid(csv_path: Path | None = None) -> Path | None:
    path = csv_path or DATA_DIR / 'hybrid_pareto.csv'
    if not path.is_file():
        print(f"Skip fig4: missing {path} (run sweep_hybrid_threshold.py)")
        return None
    df = pd.read_csv(path)
    _ensure_out()
    fig, ax1 = plt.subplots(figsize=(7.5, 4.8))
    # Use categorical x positions so close thresholds (150 vs 152) are visually separable.
    x = np.arange(len(df))
    xlabels = [str(int(v)) for v in df['fast_path_threshold']]
    ax1.plot(x, df['recall_overall'], 'o-', label='Recall (set-based)')
    ax1.plot(x, df['precision_overall'], 's-', label='Precision (set-based)')
    ax1.set_xlabel('FAST_PATH_THRESHOLD')
    ax1.set_ylabel('Recall / Precision')
    ax1.set_title('Fig 4a: Hybrid Pareto (slow model fixed from single train)')
    ax1.set_xticks(x)
    ax1.set_xticklabels(xlabels)
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2 = ax1.twinx()
    ax2.plot(x, df['fast_path_tx_fraction'] * 100.0, '^--', color='gray', alpha=0.7, label='Fast-path tx %')
    ax2.set_ylabel('Fast-path tx %', color='gray')

    fig.tight_layout()
    _savefig(fig, 'fig4a_hybrid_pareto')
    plt.close(fig)
    return OUT_DIR / 'fig4a_hybrid_pareto.pdf'


def plot_figure5_latency(csv_path: Path | None = None) -> Path | None:
    """
    Fig5 (revised): estimated access latency from recall, not sklearn inference time.
    Uses:
      - DT/LGBM recall_total from figure2 merged csv (k=1000, n=10, max strategy, full features)
      - Hybrid recall_overall from hybrid_pareto (threshold closest to 79 by default)
    """
    fig2 = DATA_DIR / 'metrics_figure2_merged.csv'
    fig4 = DATA_DIR / 'hybrid_pareto.csv'
    if (not fig2.is_file()) or (not fig4.is_file()):
        print(f"Skip fig5: missing {fig2} or {fig4}")
        return None

    df2 = pd.read_csv(fig2)
    df4 = pd.read_csv(fig4)

    df2['strategy_norm'] = df2['strategy'].astype(str).str.lower()
    df2['n_num'] = pd.to_numeric(df2['n'], errors='coerce')
    full_feat = 'to+sel+params+codehash+from+value'
    is_max = df2['strategy_norm'].str.contains('max', na=False)

    # Comparable DT/LGBM points from xlsx grid
    dt_row = df2[
        (df2['model'] == 'DT')
        & (df2['features'] == full_feat)
        & (df2['k'] == 1000)
        & (df2['n_num'] == 10)
        & is_max
    ]
    lgbm_row = df2[
        (df2['model'] == 'LightGBM')
        & (df2['features'] == full_feat)
        & (df2['k'] == 1000)
        & (df2['n_num'] == 10)
        & is_max
    ]

    # Hybrid point: threshold closest to 79 (paper default pivot)
    if len(df4) == 0:
        print("Skip fig5: empty hybrid_pareto.csv")
        return None
    df4 = df4.copy()
    df4['dist79'] = (df4['fast_path_threshold'] - 79).abs()
    hyb_row = df4.sort_values('dist79').iloc[0]

    if len(dt_row) == 0 or len(lgbm_row) == 0:
        print("Skip fig5: missing DT/LGBM recall rows for (k=1000,n=10,max,full features)")
        return None

    r_dt = float(dt_row.iloc[0]['recall_total'])
    r_lgbm = float(lgbm_row.iloc[0]['recall_total'])
    r_hyb = float(hyb_row['recall_overall'])

    # First-order expected access latency from recall
    t_hit_us = 0.03
    t_miss_us = 3.0
    def e_latency(r: float) -> float:
        return r * t_hit_us + (1.0 - r) * t_miss_us

    labels = ['Hybrid', 'LightGBM', 'DecisionTree', 'No Prefetch (Baseline)']
    recalls = [r_hyb, r_lgbm, r_dt, 0.0]
    lat_us = [e_latency(r_hyb), e_latency(r_lgbm), e_latency(r_dt), e_latency(0.0)]

    _ensure_out()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(labels, lat_us, color=['#1f77b4', '#ff7f0e', '#2ca02c', '#7f7f7f'])
    ax.set_ylabel('Estimated latency per needed access (µs)')
    ax.set_title('Fig 5a: Estimated access latency from recall')
    # annotate recall values
    for i, (r, y) in enumerate(zip(recalls, lat_us)):
        ax.text(i, y, f"recall={r:.2%}", ha='center', va='bottom', fontsize=8)
    ax.text(
        0.99,
        0.02,
        'E[T]=r*t_hit+(1-r)*t_miss, t_hit=0.03us, t_miss=3.0us',
        transform=ax.transAxes,
        ha='right',
        va='bottom',
        fontsize=8,
    )
    ax.grid(True, axis='y', alpha=0.3)
    p = OUT_DIR / 'fig5a_inference_latency.png'
    fig.tight_layout()
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"Wrote {p}")
    return p


def try_export_figure2_xlsx():
    try:
        from modeling.load_paper_metrics import export_merged_csv

        return export_merged_csv()
    except Exception as e:
        print(f"Could not export figure2 xlsx: {e}")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', type=int, nargs='*', default=[], help='Figure numbers 1-5')
    ap.add_argument('--all', action='store_true', help='Generate all figures')
    ap.add_argument('--regenerate-figure2-csv', action='store_true', help='Merge xlsx to metrics_figure2_merged.csv')
    ap.add_argument('--data-dir', type=str, default=str(DATA_DIR))
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    if args.regenerate_figure2_csv:
        try_export_figure2_xlsx()

    which = set(range(1, 6)) if args.all else set(args.only or [])
    if not which:
        ap.print_help()
        print('Use --all or --only 1 2 3 4 5')
        return 1

    if 1 in which:
        plot_figure1a_union_cdf(data_dir / 'figure1_train_union_keys.csv')
    if 2 in which:
        plot_figure2_merged(data_dir / 'metrics_figure2_merged.csv')
    if 3 in which:
        plot_figure3_topk(data_dir / 'figure3_topk_coverage.csv')
    if 4 in which:
        plot_figure4_hybrid(data_dir / 'hybrid_pareto.csv')
    if 5 in which:
        plot_figure5_latency(data_dir / 'figure5_inference_latency.csv')

    print("\nCaption reminder: Fig 2 uses label-matrix metrics; Fig 4 uses hybrid set-based metrics.")
    return 0


if __name__ == '__main__':
    sys.path.insert(0, str(EVM_DIR))
    raise SystemExit(main())
