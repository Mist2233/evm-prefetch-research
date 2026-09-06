"""
Phase A & B 仿真图表生成。

输入：figures/data/ 下的 CSV 文件
输出：figures/ 下的 PNG 文件

用法：
  python viz/plot_sim_figures.py --all          # 生成全部图表
  python viz/plot_sim_figures.py --only s1 s2   # 只生成指定图表
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

EVM_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = EVM_DIR / "figures" / "data"
OUT_DIR = EVM_DIR / "figures"

# 全局样式
plt.rcParams.update({"font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11})


def _ensure_out():
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _savefig(fig, stem: str):
    """Save figure as both PNG (for quick preview) and PDF (for LaTeX)."""
    for ext in ["png", "pdf"]:
        path = OUT_DIR / f"{stem}.{ext}"
        fig.savefig(path, dpi=150 if ext == "png" else 300, bbox_inches="tight")
        print(f"  Saved: {path}")


# ═══════════════════════════════════════════════════════════════════════════════
# Fig S1: Alpha 覆盖敏感性
# ═══════════════════════════════════════════════════════════════════════════════

def plot_s1_alpha_sweep(csv_path: Path | None = None) -> Path | None:
    path = csv_path or DATA_DIR / "alpha_sweep_overlap.csv"
    if not path.is_file():
        print(f"Skip S1: missing {path}")
        return None
    df = pd.read_csv(path)

    alphas = df["alpha"].values
    net_gain_s = df["net_gain_us"].values / 1e6  # 转秒
    eff_overhead_s = df["effective_pred_overhead_us"].values / 1e6
    raw_overhead = df["raw_pred_overhead_us"].values[0] / 1e6
    storage_gain = df["storage_gain_us"].values[0] / 1e6

    _ensure_out()
    fig, ax1 = plt.subplots(figsize=(8, 3.5))

    color_net = "#2C4A6E"
    color_eff = "#C85A4A"
    color_raw = "#8DA3C4"
    color_stor = "#5A8C6E"

    ax1.plot(alphas, net_gain_s, "o-", color=color_net, linewidth=2, markersize=6, markerfacecolor="white",
             label="Net gain with overlap (s)")
    ax1.set_xlabel("Alpha (overlap ratio)", fontsize=13)
    ax1.set_ylabel("Net gain (s)", color=color_net, fontsize=13)
    ax1.tick_params(axis="y", labelcolor=color_net, labelsize=12)
    ax1.tick_params(axis="x", labelsize=12)
    ax1.set_ylim(net_gain_s[-1] * 1.15, storage_gain * 1.5)

    ax2 = ax1.twinx()
    ax2.plot(alphas, eff_overhead_s, "s--", color=color_eff, linewidth=2, markersize=6, markerfacecolor="white",
             label="Effective pred overhead (s)")
    ax2.set_ylabel("Effective pred overhead (s)", color=color_eff, fontsize=13)
    ax2.tick_params(axis="y", labelcolor=color_eff, labelsize=12)

    # 合并图例
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right", fontsize=11)

    ax1.grid(True, alpha=0.3)

    _savefig(fig, "fig_alpha")
    plt.close(fig)
    return OUT_DIR / "fig_alpha.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# Fig S2: Rule Delta 评估对比
# ═══════════════════════════════════════════════════════════════════════════════

def plot_s2_rule_delta(csv_path: Path | None = None) -> Path | None:
    path = csv_path or DATA_DIR / "rule_delta_eval.csv"
    if not path.is_file():
        print(f"Skip S2: missing {path}")
        return None
    df = pd.read_csv(path)
    base = df[df["prefetcher"] == "rule_base"].iloc[0]
    delta = df[df["prefetcher"] == "rule_plus_delta"].iloc[0]

    metrics = ["recall", "precision", "miss_prevented", "total_cost_us"]
    labels = ["Recall", "Precision", "Miss Prevented", "Total Cost (µs)"]
    base_vals = [base["recall"], base["precision"], base["n_miss_prevented"], base["total_cost_us"]]
    delta_vals = [delta["recall"], delta["precision"], delta["n_miss_prevented"], delta["total_cost_us"]]

    _ensure_out()
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.5))

    colors = ["#1f77b4", "#ff7f0e"]
    for ax, metric, label, bv, dv in zip(axes, metrics, labels, base_vals, delta_vals):
        x = np.arange(2)
        vals = [bv, dv]
        bars = ax.bar(x, vals, color=colors, width=0.5, edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(["rule_base", "rule_+delta"], fontsize=9)
        ax.set_title(label, fontweight="bold")

        # 标注数值
        for bar, val in zip(bars, vals):
            if metric == "total_cost_us":
                text = f"{val:,.0f}"
            elif metric == "miss_prevented":
                text = f"{val:,}"
            else:
                text = f"{val:.4f}"
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    text, ha="center", va="bottom", fontsize=9)

        # 标注变化百分比
        if bv != 0:
            pct = (dv - bv) / abs(bv) * 100
            color = "#2ca02c" if (
                (metric in ("recall", "miss_prevented") and pct > 0) or
                (metric == "total_cost_us" and pct < 0)
            ) else "#d62728"
            ax.text(0.5, max(bv, dv) * 1.08 if metric != "total_cost_us" else max(bv, dv) * 1.02,
                    f"{pct:+.1f}%", ha="center", fontsize=10, color=color, fontweight="bold")

        ax.grid(axis="y", alpha=0.3)

    n_tx = int(base["n_tx"])
    fig.suptitle(f"Fig S2: Rule base vs Rule+delta on Window B ({n_tx} txs, 35 blocks)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()

    _savefig(fig, "fig_s2_rule_delta")
    plt.close(fig)
    return OUT_DIR / "fig_s2_rule_delta.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# Fig S3: 全量预取器对比（含 rule_plus_delta）
# ═══════════════════════════════════════════════════════════════════════════════

def plot_s3_full_comparison(
    sim_csv: Path | None = None,
    delta_csv: Path | None = None,
) -> Path | None:
    sim_path = sim_csv or DATA_DIR / "simulation_results.csv"
    delta_path = delta_csv or DATA_DIR / "rule_delta_eval.csv"
    if not sim_path.is_file():
        print(f"Skip S3: missing {sim_path}")
        return None
    if not delta_path.is_file():
        print(f"Skip S3: missing {delta_path}")
        return None

    sim = pd.read_csv(sim_path)
    delta = pd.read_csv(delta_path)
    delta_row = delta[delta["prefetcher"] == "rule_plus_delta"].iloc[0]

    # 从 sim 取 prefetcher, recall, speedup_vs_baseline, net_gain_us
    prefetchers = list(sim["prefetcher"].values) + ["rule_+delta"]
    recalls = list(sim["recall"].values) + [delta_row["recall"]]
    speedups = list(sim["speedup_vs_baseline"].values) + [
        sim[sim["prefetcher"] == "none"]["total_cost_us"].values[0] / delta_row["total_cost_us"]
    ]

    # 过滤掉 oracle（太大了不好看）
    mask = [p != "oracle" for p in prefetchers]
    prefetchers = [p for p, m in zip(prefetchers, mask) if m]
    recalls = [r for r, m in zip(recalls, mask) if m]
    speedups = [s for s, m in zip(speedups, mask) if m]

    _ensure_out()
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    colors = ["#1f77b4"] * (len(prefetchers) - 1) + ["#ff7f0e"]
    x = np.arange(len(prefetchers))

    # Recall
    ax = axes[0]
    bars = ax.bar(x, recalls, color=colors, width=0.5, edgecolor="white")
    for bar, val in zip(bars, recalls):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.005,
                f"{val:.4f}", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(prefetchers, fontsize=9)
    ax.set_ylabel("Recall")
    ax.set_title("Recall by prefetcher")
    ax.grid(axis="y", alpha=0.3)
    ax.set_ylim(0, max(recalls) * 1.2)

    # Speedup
    ax = axes[1]
    bars = ax.bar(x, speedups, color=colors, width=0.5, edgecolor="white")
    for bar, val in zip(bars, speedups):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"{val:.4f}x", ha="center", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(prefetchers, fontsize=9)
    ax.set_ylabel("Speedup vs baseline")
    ax.set_title("Speedup by prefetcher")
    ax.grid(axis="y", alpha=0.3)
    ax.axhline(y=1.0, color="gray", linestyle="--", linewidth=0.8)
    ax.set_ylim(0, max(speedups) * 1.2)

    fig.suptitle("Fig S3: Full prefetcher comparison (real_block, max_txs=10k Window B)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()

    _savefig(fig, "fig_s3_full_comparison")
    plt.close(fig)
    return OUT_DIR / "fig_s3_full_comparison.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# Fig S4: Delta 增量统计总览
# ═══════════════════════════════════════════════════════════════════════════════

def plot_s4_delta_overview(csv_path: Path | None = None) -> Path | None:
    path = csv_path or DATA_DIR / "offline_delta_stats.csv"
    if not path.is_file():
        print(f"Skip S4: missing {path}")
        return None
    df = pd.read_csv(path)
    row = df.iloc[0]

    _ensure_out()
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))

    # Panel 1: Window split
    ax = axes[0]
    sizes = [int(row["window_a_txs"]), int(row["window_b_txs"])]
    labels = [f"Window A\n({int(row['window_a_blocks'])} blocks)", f"Window B\n({int(row['window_b_blocks'])} blocks)"]
    colors = ["#1f77b4", "#ff7f0e"]
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%",
                                       startangle=90, textprops={"fontsize": 10})
    ax.set_title(f"Data split (total {int(row['total_txs']):,} txs)", fontweight="bold")

    # Panel 2: Dict growth
    ax = axes[1]
    before = int(row["original_keys"])
    after = int(row["augmented_keys"])
    bars = ax.bar(["Original", "Augmented"], [before, after], color=["#7f7f7f", "#2ca02c"],
                  width=0.4, edgecolor="white")
    for bar, val in zip(bars, [before, after]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                f"{val:,}", ha="center", fontsize=11, fontweight="bold")
    ax.set_ylabel("Keys in fast_path_dict")
    ax.set_title(f"Dict growth (+{after - before:,} keys)", fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    # Panel 3: Delta slots
    ax = axes[2]
    new_slots = int(row["delta_slots_total"])
    new_keys = int(row["delta_keys_new"])
    avg = float(row["avg_slots_per_new_key"])
    metrics = ["New Keys", "New Slots", "Avg Slots/Key"]
    values = [new_keys, new_slots, avg]
    colors_bar = ["#1f77b4", "#ff7f0e", "#2ca02c"]
    bars = ax.bar(metrics, values, color=colors_bar, width=0.4, edgecolor="white")
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.02,
                f"{val:,.1f}" if val == avg else f"{val:,}", ha="center", fontsize=11)
    ax.set_title("Delta supplement detail", fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Fig S4: Offline delta pipeline overview (max_txs=10k, split=0.7, min_support=2)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()

    _savefig(fig, "fig_s4_delta_overview")
    plt.close(fig)
    return OUT_DIR / "fig_s4_delta_overview.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# Fig Main: Main Results 柱状图 — E2 vs E3
# ═══════════════════════════════════════════════════════════════════════════════

def plot_main_results() -> Path:
    _ensure_out()
    metrics = ["Recall", "Precision", "Total Cost (μs)", "Speedup"]
    e2_vals = [0.2223, 0.1888, 880_983, 1.0000]
    e3_vals = [0.3117, 0.1648, 781_405, 1.1274]
    changes = ["+40.2%", "−12.7%", "−11.3%", "+12.7%"]

    # 正收益 = recall 提升 / cost 下降 / speedup 提升 → 绿色
    # 负收益 = precision 下降 → 暖色
    is_good = [True, False, True, True]

    color_e2 = "#2C4A6E"
    color_e3 = "#6B8EB5"
    color_pos = "#5A8C6E"
    color_neg = "#C85A4A"

    fig, axes = plt.subplots(2, 2, figsize=(8, 5.5))

    for idx, (ax, m, e2, e3, chg, good) in enumerate(
        zip(axes.flat, metrics, e2_vals, e3_vals, changes, is_good)
    ):
        bars = ax.bar(["E2", "E3"], [e2, e3], color=[color_e2, color_e3],
                      width=0.6, edgecolor="white", linewidth=0.5,
                      hatch=["///", "\\\\\\"])

        # 标注数值
        for bar, val in zip(bars, [e2, e3]):
            if m == "Total Cost (μs)":
                text = f"{val:,.0f}"
            elif m == "Speedup":
                text = f"{val:.4f}×"
            else:
                text = f"{val:.4f}"
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(),
                    text, ha="center", va="bottom", fontsize=10)

        # 标注变化率（字符串已自带 +/- 符号）
        chg_color = color_pos if good else color_neg
        y_max = max(e2, e3)
        ax.text(0.5, y_max * 1.15, chg, ha="center",
                fontsize=11, fontweight="bold", color=chg_color)

        # 柔化边框：隐藏上/右，左/下变浅
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        for spine in ["left", "bottom"]:
            ax.spines[spine].set_color("black")
            ax.spines[spine].set_linewidth(0.5)

        ax.set_ylabel(m, fontsize=10)
        ax.tick_params(axis="both", labelsize=9)
        ax.set_ylim(0, y_max * 1.35)
        ax.grid(False)
        # y 轴刻度用逗号分隔
        if m == "Total Cost (μs)":
            ax.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
            )

    fig.tight_layout()
    _savefig(fig, "fig_main_results")
    plt.close(fig)
    return OUT_DIR / "fig_main_results.pdf"


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

PLOTS = {
    "s1": ("Alpha overlap sensitivity", plot_s1_alpha_sweep),
    "s2": ("Rule base vs rule+delta comparison", plot_s2_rule_delta),
    "s3": ("Full prefetcher comparison with delta", plot_s3_full_comparison),
    "s4": ("Delta pipeline overview", plot_s4_delta_overview),
    "main": ("Main results E2 vs E3 bar chart", plot_main_results),
}


def main():
    p = argparse.ArgumentParser(description="Generate Phase A/B simulation figures")
    p.add_argument("--all", action="store_true", help="Generate all figures")
    p.add_argument("--only", nargs="*", choices=list(PLOTS), help="Generate specific figures")
    args = p.parse_args()

    if not args.all and not args.only:
        p.print_help()
        print("\nAvailable figures:", ", ".join(PLOTS))
        return

    targets = list(PLOTS) if args.all else args.only
    for key in targets:
        name, func = PLOTS[key]
        print(f"\n[{key}] {name} ...")
        try:
            func()
        except Exception as e:
            print(f"  Error: {e}", file=sys.stderr)

    print("\nDone.")


if __name__ == "__main__":
    main()
