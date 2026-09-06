"""
Feature importance bar chart for LightGBM multi-label classification model.

数据来源：evm_model_lgbm_k1000_to_sel_params_codehash_from_value.pkl
提取方法：MultiOutputClassifier（1000 个 LGBMClassifier 子模型），
遍历每个子模型的 .feature_importances_（gain-based），
按特征求平均后归一化。

数据：
  calldata[0]  17.8%
  sender       16.2%
  selector     13.4%
  calldata[2]  12.9%
  to           11.3%
  value        10.0%
  code_hash     9.7%
  calldata[1]   8.8%

输出：evm_analysis/figures/fig_feature_importance.png
"""

from __future__ import annotations
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

EVM_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = EVM_DIR / "figures" / "data"
OUT_DIR = EVM_DIR / "figures"

# ── 数据 ──
features = ["calldata[0]", "sender", "selector", "calldata[2]",
            "to", "value", "code_hash", "calldata[1]"]
importance = [17.8, 16.2, 13.4, 12.9, 11.3, 10.0, 9.7, 8.8]

# CLAUDE.md 蓝灰色系
COLORS = {
    "primary":   "#2C4A6E",
    "secondary": "#4A6B8C",
    "tertiary":  "#8DA3C4",
    "light":     "#B0C4DE",
    "warm":      "#C85A4A",
    "green":     "#5A8C6E",
}

# 特征分组着色
GROUP_MAP = {
    "to":         "Contract Identity",
    "selector":   "Contract Identity",
    "code_hash":  "Contract Identity",
    "calldata[0]": "Transaction Payload",
    "calldata[1]": "Transaction Payload",
    "calldata[2]": "Transaction Payload",
    "sender":     "Execution Context",
    "value":      "Execution Context",
}
COLOR_MAP = {
    "Contract Identity":      COLORS["primary"],
    "Transaction Payload":    COLORS["tertiary"],
    "Execution Context":      COLORS["warm"],
}


def plot_feature_importance(out_path: Path | None = None) -> Path:
    """绘制 LightGBM 特征重要性柱状图"""
    out_path = out_path or OUT_DIR / "fig_feature_importance.png"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bar_colors = [COLOR_MAP[GROUP_MAP[f]] for f in features]

    # 每组一个填充纹理，确保黑白打印可区分
    HATCH_MAP = {
        "Contract Identity":   "///",
        "Transaction Payload": "\\\\\\",
        "Execution Context":   "xx",
    }
    bar_hatches = [HATCH_MAP[GROUP_MAP[f]] for f in features]

    plt.rcParams.update({"font.size": 12, "axes.titlesize": 13})
    fig, ax = plt.subplots(figsize=(8.5, 4.5))

    x = np.arange(len(features))
    bars = ax.bar(x, importance, color=bar_colors, width=0.5,
                  edgecolor="white", linewidth=0.5, hatch=bar_hatches)

    # 柱顶数值标注
    for bar, val in zip(bars, importance):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f"{val:.1f}%", ha="center", va="bottom", fontsize=10,
                color=COLORS["primary"], fontweight="bold")

    # x 轴标签（黑色）
    ax.set_xticks(x)
    ax.set_xticklabels(features, fontsize=11, color="black")

    # y 轴
    ax.set_ylabel("Normalized Importance (%)", fontsize=12, color="black")
    ax.set_ylim(0, 22.5)
    ax.tick_params(axis="y", colors="black", labelsize=11)

    # 边框
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("black")
    ax.spines["bottom"].set_color("black")

    # 图例（带纹理，便于黑白打印区分）
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=COLORS["primary"],  hatch="///", label="Contract Identity"),
        Patch(facecolor=COLORS["tertiary"], hatch="\\\\\\", label="Transaction Payload"),
        Patch(facecolor=COLORS["warm"],     hatch="xx",   label="Execution Context"),
    ]
    ax.legend(handles=legend_elements, fontsize=10, loc="upper right",
              framealpha=0.9, edgecolor="#CCCCCC")

    plt.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved to {out_path}")
    return out_path


if __name__ == "__main__":
    plot_feature_importance()
