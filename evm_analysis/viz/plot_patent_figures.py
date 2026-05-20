"""
Generate patent application figures.

Output to figures/patent/:
  patent_fig1_architecture.png    — Fig 1: Hybrid prefetch architecture
  patent_fig2_pipeline.png        — Fig 2: Offline delta pipeline flowchart
  patent_fig3_comparison.png      — Fig 3: Full prefetcher comparison
  patent_fig4_scale.png           — Fig 4: Scale consistency curve
  patent_abstract_figure.png      — Abstract figure

Usage:
  python viz/plot_patent_figures.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "AR PL UMing CN", "SimHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

EVM_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = EVM_DIR / "figures" / "data"
OUT_DIR = EVM_DIR / "figures" / "patent"

# Globally larger, bolder fonts
plt.rcParams.update({
    "font.size": 13,
    "axes.titlesize": 15,
    "axes.labelsize": 13,
    "font.weight": "normal",
})

DARK = "#000000"
MID = "#1a1a1a"


def _ensure_out():
    OUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 1: Architecture diagram
# ═══════════════════════════════════════════════════════════════════════════════

def plot_patent_fig1_architecture():
    _ensure_out()
    fig, ax = plt.subplots(1, 1, figsize=(22, 12))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 12)
    ax.axis("off")

    FW = "bold"

    def box(x, y, w, h, text, color="#E3F2FD", fontsize=20, edgecolor="#1565C0", fontweight=FW):
        rect = mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                                        facecolor=color, edgecolor=edgecolor, linewidth=3.0)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=fontsize, weight=fontweight, color="#000000")

    def arrow(x1, y1, x2, y2, style="->", color="#555555", lw=3.0):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle=style, color=color, lw=lw))

    # ── Title ──
    ax.text(11, 11.5, "图1：在线/离线职责分离的EVM存储访问混合预取架构",
            ha="center", fontsize=26, weight=FW, color="#000000")

    # ═══ Online path ═══
    O_BG_Y, O_BG_H = 7.5, 3.2
    O_ROW_Y, O_ROW_H = 7.8, 2.2
    O_Y_MID = O_ROW_Y + O_ROW_H / 2  # 8.9

    box(0.5, O_BG_Y, 21, O_BG_H, "", color="#E8F5E9", edgecolor="#2E7D32", fontsize=1)
    ax.text(11, 10.45, "在线路径（交易执行关键路径）",
            ha="center", fontsize=22, weight=FW, color="#1B5E20")

    # 三列等间距: 左 x=1.5 w=4.5 | gap=2.25 | 中 x=8.25 w=6.5 | gap=2.25 | 右 x=17.0 w=4.5
    box(1.5,  O_ROW_Y, 4.5, O_ROW_H, "待处理交易\n(to, selector, ...)",
        color="#C8E6C9", fontsize=20, edgecolor="#388E3C")
    box(8.25, O_ROW_Y, 6.5, O_ROW_H, "快路径哈希表\n(rule, slot_list): O(1) 查表",
        color="#A5D6A7", fontsize=22, edgecolor="#2E7D32")
    box(17.0, O_ROW_Y, 4.5, O_ROW_H, "预测 slot 集合\n→ 注入块内缓存",
        color="#C8E6C9", fontsize=20, edgecolor="#388E3C")

    arrow(6.0, O_Y_MID, 8.25, O_Y_MID)
    arrow(14.75, O_Y_MID, 17.0, O_Y_MID)

    # ── Divider ──
    ax.plot([0.3, 21.7], [7.0, 7.0], "k--", linewidth=2.5, alpha=0.5)
    ax.text(11, 6.5, "▼  离线（非关键路径）  ▼",
            ha="center", fontsize=16, color="#333333", weight=FW)

    # ═══ Offline path ═══
    F_BG_Y, F_BG_H = 1.2, 5.0
    F_R1_Y, F_R1_H = 3.8, 2.0
    F_R1_MID = F_R1_Y + F_R1_H / 2  # 4.8
    F_R2_Y, F_R2_H = 1.5, 1.8

    box(0.5, F_BG_Y, 21, F_BG_H, "", color="#FFF3E0", edgecolor="#E65100", fontsize=1)
    ax.text(11, 6.00, "离线路径（定期批量执行）",
            ha="center", fontsize=22, weight=FW, color="#BF360C")

    # Row 1: 左 x=1.5 w=4.5 | gap=2.25 | 中 x=8.25 w=5.5 | gap=2.25 | 右 x=16.0 w=5.5
    box(1.5,  F_R1_Y, 4.5, F_R1_H, "Window A 数据\n(历史区块)",
        color="#FFE0B2", fontsize=20, edgecolor="#EF6C00")
    box(8.25, F_R1_Y, 5.5, F_R1_H, "慢路径 LightGBM\n多标签分类预测",
        color="#FFCC80", fontsize=20, edgecolor="#E65100")
    box(16.0, F_R1_Y, 5.5, F_R1_H, "候选增量生成\nmin_support 过滤",
        color="#FFE0B2", fontsize=20, edgecolor="#EF6C00")

    arrow(6.0, F_R1_MID, 8.25, F_R1_MID)
    arrow(13.75, F_R1_MID, 16.0, F_R1_MID)

    # Row 2: 左对齐 R1 第一列 (x=1.5) + 中对齐 R1 第二列 (x=8.25)
    box(1.5,  F_R2_Y, 4.5, F_R2_H, "Window B 评估\n基线 vs 增强对比",
        color="#FFE0B2", fontsize=20, edgecolor="#EF6C00")
    box(8.25, F_R2_Y, 5.5, F_R2_H, "合并增量到\n快路径哈希表",
        color="#FFAB40", fontsize=22, edgecolor="#BF360C")

    # 候选增量 → 合并 的斜箭头
    ax.annotate("", xy=(11.0, F_R2_Y + F_R2_H), xytext=(18.75, F_R1_Y),
                arrowprops=dict(arrowstyle="->", color="#BF360C", lw=3.0))

    # Feedback arrow (left arc): offline → online
    ax.annotate("", xy=(5, 7.8), xytext=(4, 2.8),
                arrowprops=dict(arrowstyle="->", color="#0D47A1", lw=4.5,
                               connectionstyle="arc3,rad=-0.55"))
    ax.text(0.5, 5.3, "增量\n规则\n补充",
            fontsize=18, color="#0D47A1", ha="center", weight=FW)

    plt.tight_layout()
    out = OUT_DIR / "patent_fig1_architecture.png"
    fig.savefig(out, dpi=250, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out}")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 2: Pipeline flowchart
# ═══════════════════════════════════════════════════════════════════════════════

def plot_patent_fig2_pipeline():
    _ensure_out()
    fig, ax = plt.subplots(1, 1, figsize=(22, 7.5))
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 7.5)
    ax.axis("off")

    ax.text(11, 7.0, "图2：离线增量管道五步流程",
            ha="center", fontsize=22, fontweight="bold", color="#000000")

    steps = [
        ("①", "加载模型与数据\n(Hybrid模型 + JSONL Trace)", "#E3F2FD", "#1565C0"),
        ("②", "切分时间窗口\nWindow A / B", "#E8F5E9", "#2E7D32"),
        ("③", "生成候选增量\nslow-path预测 × 正确交集", "#FFF3E0", "#E65100"),
        ("④", "过滤与合并\nmin_support + max_slots", "#FCE4EC", "#C62828"),
        ("⑤", "Window B 评估\nrule_base vs rule_delta", "#F3E5F5", "#6A1B9A"),
    ]

    descriptions = [
        "读取 pkl 中的\nfast_path_dict\n和 LightGBM 模型",
        "按 block_number\n分组并排序\n前70%→A 后30%→B",
        "对 rule_miss 交易\n调用模型预测\n取predicted∩true",
        "正确次数≥min_support\n且每键≤max_slots\n合并到 fast_path",
        "同一仿真器\n同一 Window B\n对比 Recall/Cost",
    ]

    for i, (num, title, color, edge) in enumerate(steps):
        x = 0.5 + i * 4.3
        box_w, box_h = 3.6, 2.6

        rect = mpatches.FancyBboxPatch((x, 2.8), box_w, box_h, boxstyle="round,pad=0.15",
                                        facecolor=color, edgecolor=edge, linewidth=2.5)
        ax.add_patch(rect)
        ax.text(x + box_w/2, 4.95, num, ha="center", fontsize=32, fontweight="bold", color=edge)
        ax.text(x + box_w/2, 4.00, title, ha="center", fontsize=15, fontweight="bold", color="#000000")
        ax.text(x + box_w/2, 2.35, descriptions[i], ha="center", fontsize=13, color="#1a1a1a",
                va="top", fontweight="bold")

        if i < 4:
            # xy = 箭头终点(下一box左侧), xytext = 箭头起点(当前box右侧)
            ax.annotate("", xy=(x + 4.3 - 0.08, 4.1), xytext=(x + box_w + 0.08, 4.1),
                        arrowprops=dict(arrowstyle="->", color="#333333", lw=3))

    ax.text(11, 1.0, "Window A: 699块/65,706笔  →  Window B: 300块/28,757笔  →  新增253键/2,641槽  →  Recall +40.2%  Cost -11.3%",
            ha="center", fontsize=14, color="#333333", fontweight="bold")

    plt.tight_layout()
    out = OUT_DIR / "patent_fig2_pipeline.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out}")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 3: Prefetcher comparison
# ═══════════════════════════════════════════════════════════════════════════════

def plot_patent_fig3_comparison():
    delta_path = DATA_DIR / "rule_delta_eval.csv"
    if not delta_path.is_file():
        print(f"Skip Fig3: missing {delta_path}")
        return None

    df = pd.read_csv(delta_path)
    base = df[df["prefetcher"] == "rule_base"].iloc[0]
    delta = df[df["prefetcher"] == "rule_plus_delta"].iloc[0]

    speedup = base["total_cost_us"] / delta["total_cost_us"]

    _ensure_out()
    fig, axes = plt.subplots(1, 4, figsize=(18, 5))

    metrics = [
        ("recall", "Recall", base["recall"], delta["recall"],
         f'{base["recall"]:.4f}', f'{delta["recall"]:.4f}',
         (delta["recall"] - base["recall"]) / base["recall"] * 100, True),
        ("precision", "Precision", base["precision"], delta["precision"],
         f'{base["precision"]:.4f}', f'{delta["precision"]:.4f}',
         (delta["precision"] - base["precision"]) / base["precision"] * 100, False),
        ("total_cost_us", "Total Cost (µs)", base["total_cost_us"], delta["total_cost_us"],
         f'{base["total_cost_us"]:,.0f}', f'{delta["total_cost_us"]:,.0f}',
         (base["total_cost_us"] - delta["total_cost_us"]) / base["total_cost_us"] * 100, True),
        ("speedup", "Speedup vs rule_base", 1.0, speedup,
         "1.0000x", f"{speedup:.4f}x",
         (speedup - 1.0) * 100, True),
    ]

    colors = ["#1f77b4", "#2ca02c"]
    bar_labels = ["rule_base", "rule+Δ"]

    for ax, (key, title, bv, dv, btxt, dtxt, pct, up_is_good) in zip(axes, metrics):
        x = np.arange(2)
        vals = [bv, dv]
        bars = ax.bar(x, vals, color=colors, width=0.4, edgecolor="white", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(bar_labels, fontsize=12, fontweight="bold")
        ax.set_title(title, fontweight="bold", fontsize=14, color=DARK)

        for bar, txt in zip(bars, [btxt, dtxt]):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                    txt, ha="center", va="bottom", fontsize=11, fontweight="bold", color=DARK)

        pct_color = "#1B5E20" if (up_is_good and pct > 0) or (not up_is_good and pct < 0) else "#B71C1C"
        pct_sign = "+" if pct > 0 else ""
        # total_cost_us 数值大，百分比标注用更大的偏移避免与柱顶数值重叠
        y_mul = 1.15 if key != "total_cost_us" else 1.25
        y_pos = max(bv, dv) * y_mul
        ax.text(0.5, y_pos, f"{pct_sign}{pct:.1f}%",
                ha="center", fontsize=13, color=pct_color, fontweight="bold")
        # 扩展 y 轴上限确保标注不被截断
        ax.set_ylim(0, y_pos * 1.08)
        ax.grid(axis="y", alpha=0.3)
        ax.tick_params(labelsize=11)

    fig.suptitle("图3：离线增量效果对比 — rule_base vs rule+Δ（同一Window B：300区块/28,757笔交易）",
                 fontsize=16, fontweight="bold", color=DARK, y=1.03)
    plt.tight_layout()

    out = OUT_DIR / "patent_fig3_comparison.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out}")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Fig 4: Scale consistency
# ═══════════════════════════════════════════════════════════════════════════════

def plot_patent_fig4_scale():
    _ensure_out()
    fig, ax1 = plt.subplots(1, 1, figsize=(10, 6))

    scales = ["2K", "10K", "94K (full)"]
    x = np.arange(len(scales))
    recall_improvements = [27.4, 35.7, 40.2]
    cost_reductions = [7.8, 10.9, 11.3]

    color_recall = "#1B5E20"
    color_cost = "#0D47A1"

    ax1.plot(x, recall_improvements, "o-", color=color_recall, linewidth=3,
             markersize=12, label="Recall improvement (%)")
    for i, val in enumerate(recall_improvements):
        ax1.annotate(f"{val}%", (x[i], val), textcoords="offset points",
                    xytext=(0, 12), ha="center", fontsize=14, fontweight="bold",
                    color=color_recall)

    ax2 = ax1.twinx()
    ax2.plot(x, cost_reductions, "s--", color=color_cost, linewidth=3,
             markersize=12, label="Cost reduction (%)")
    # 每个点的 cost 标注偏移量不同，避免与 blocks 标注重叠
    cost_offsets = [-18, -22, -30]
    for i, val in enumerate(cost_reductions):
        ax2.annotate(f"{val}%", (x[i], val), textcoords="offset points",
                    xytext=(0, cost_offsets[i]), ha="center", fontsize=14, fontweight="bold",
                    color=color_cost)

    ax1.set_xticks(x)
    ax1.set_xticklabels(scales, fontsize=14, fontweight="bold")
    ax1.set_ylabel("Recall improvement (%)", color=color_recall, fontsize=13, fontweight="bold")
    ax2.set_ylabel("Cost reduction (%)", color=color_cost, fontsize=13, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=color_recall, labelsize=12)
    ax2.tick_params(axis="y", labelcolor=color_cost, labelsize=12)

    # blocks/txs 标注贴近 recall 数据点，放在数据点与 x 轴之间
    annotations = ["23 blocks\n1,320 txs", "115 blocks\n7,027 txs", "999 blocks\n65,706 txs"]
    ann_offsets = [-8, -10, -12]
    for i, ann in enumerate(annotations):
        ax1.text(x[i], recall_improvements[i] + ann_offsets[i], ann, ha="center", fontsize=11,
                color=MID, va="top", fontweight="bold")

    ax1.grid(True, alpha=0.3)
    ax1.set_ylim(15, 52)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    legend = ax1.legend(lines1 + lines2, labels1 + labels2, loc="lower right",
                        fontsize=12, framealpha=0.9)
    for text in legend.get_texts():
        text.set_fontweight("bold")

    ax1.set_title("图4：缩放一致性 — Recall 提升与 Cost 降幅均单调递增",
                  fontsize=16, fontweight="bold", color=DARK, pad=15)

    plt.tight_layout()
    out = OUT_DIR / "patent_fig4_scale.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out}")
    return out


# ═══════════════════════════════════════════════════════════════════════════════
# Abstract figure
# ═══════════════════════════════════════════════════════════════════════════════

def plot_patent_abstract_figure():
    _ensure_out()
    fig, ax = plt.subplots(1, 1, figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    def box(x, y, w, h, text, color="#E3F2FD", fontsize=13, fontweight="bold", edgecolor="#1565C0"):
        rect = mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                                        facecolor=color, edgecolor=edgecolor, linewidth=2.2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=fontsize, fontweight=fontweight, color="#000000")

    def arrow(x1, y1, x2, y2, color="#333333", lw=2.5):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=lw))

    # Title
    ax.text(8, 8.5, "在线/离线职责分离的EVM存储访问混合预取方法",
            ha="center", fontsize=22, fontweight="bold", color="#000000")

    # ── Left: Architecture ──
    ax.text(4, 7.8, "[架构]", ha="center", fontsize=16, fontweight="bold", color="#0D47A1")

    # Online
    box(0.5, 5.6, 7, 1.8, "", color="#E8F5E9", edgecolor="#2E7D32")
    ax.text(4, 7.20, "在线路径", ha="center", fontsize=17, fontweight="bold", color="#1B5E20")
    box(0.8, 5.8, 3, 1.2, "交易 → 快路径哈希表\nO(1) 查表",
        color="#C8E6C9", fontsize=13, edgecolor="#388E3C")
    box(4.3, 5.8, 3, 1.2, "预测 slot 集合\n注入块内缓存",
        color="#C8E6C9", fontsize=13, edgecolor="#388E3C")
    arrow(3.8, 6.4, 4.3, 6.4, color="#1B5E20")

    # Offline
    box(0.5, 2.8, 7, 2.5, "", color="#FFF3E0", edgecolor="#E65100")
    ax.text(4, 5.15, "离线路径（定期执行）", ha="center", fontsize=17, fontweight="bold", color="#BF360C")
    box(0.8, 3.0, 3, 1.7, "Window A 历史数据\nLightGBM 预测\n正确slot计数",
        color="#FFE0B2", fontsize=13, edgecolor="#EF6C00")
    box(4.3, 3.0, 3, 1.7, "min_support过滤\n合并增量规则\n→增强哈希表",
        color="#FFCC80", fontsize=13, edgecolor="#E65100")
    arrow(3.8, 3.85, 4.3, 3.85, color="#BF360C")

    # Feedback arrow
    ax.annotate("", xy=(2.5, 5.6), xytext=(2.5, 5.45),
                arrowprops=dict(arrowstyle="->", color="#0D47A1", lw=3.5))
    ax.text(0.3, 5.5, "增量补充", fontsize=14, color="#0D47A1", rotation=90, va="center", fontweight="bold")

    ax.plot([0.5, 7.5], [5.35, 5.35], "k--", linewidth=1.5, alpha=0.5)

    # ── Right: Results ──
    ax.text(12, 7.8, "[全量实验结果]", ha="center", fontsize=16, fontweight="bold", color="#B71C1C")

    data_cards = [
        (9, 6.0, "+40.2%", "Recall 提升", "#1B5E20"),
        (12.5, 6.0, "-11.3%", "Cost 降低", "#0D47A1"),
        (9, 4.2, "253键\n2,641槽", "新增规则", "#E65100"),
        (12.5, 4.2, "94,463笔\n999区块", "全量规模", "#555555"),
    ]
    for x, y, big, label, color in data_cards:
        rect = mpatches.FancyBboxPatch((x, y), 2.8, 1.5, boxstyle="round,pad=0.1",
                                        facecolor="white", edgecolor=color, linewidth=2.5)
        ax.add_patch(rect)
        ax.text(x + 1.4, y + 1.0, big, ha="center", fontsize=20, fontweight="bold", color=color)
        ax.text(x + 1.4, y + 0.3, label, ha="center", fontsize=13, color="#1a1a1a", fontweight="bold")

    # Scale consistency
    ax.text(12, 3.6, "缩放一致性：Recall提升 +27%→+36%→+40%（单调递增）",
            ha="center", fontsize=13, color="#1a1a1a", fontweight="bold")

    # Bottom: comparison table (rendered with proper font, no monospace)
    ax.text(12, 3.0, "Window B (300块/28,757笔) 对比：",
            ha="center", fontsize=13, color="#000000", fontweight="bold")

    table_lines = [
        ("  recall    precision    total_cost  ", True),
        ("  rule_base:    0.2223 / 0.1888 / 880,983 µs  ", False),
        ("  rule_+Δ:     0.3117 / 0.1648 / 781,405 µs  ", False),
    ]
    for j, (line, is_header) in enumerate(table_lines):
        kw = {}
        if is_header:
            kw["bbox"] = dict(boxstyle="round,pad=0.3", facecolor="#EEEEEE", edgecolor="#BBBBBB")
        ax.text(12, 2.5 - j * 0.45, line, ha="center", fontsize=12,
                color="#000000" if is_header else "#1a1a1a",
                fontweight="bold", **kw)

    ax.text(12, 1.1, "← 本方法",
            ha="center", fontsize=12, color="#1B5E20", fontweight="bold")

    # Bottom tagline
    ax.text(8, 0.3, "技术效果：在线零推理开销 (O(1) 查表) + 离线 ML 增量规则补充 → 持续提升预测覆盖率",
            ha="center", fontsize=14, color="#1a1a1a", fontweight="bold")

    plt.tight_layout()
    out = OUT_DIR / "patent_abstract_figure.png"
    fig.savefig(out, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out}")
    return out


# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("Generating patent figures ...\n")
    plot_patent_fig1_architecture()
    plot_patent_fig2_pipeline()
    plot_patent_fig3_comparison()
    plot_patent_fig4_scale()
    plot_patent_abstract_figure()
    print("\nAll figures saved to figures/patent/")


if __name__ == "__main__":
    main()
