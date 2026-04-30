# evm_analysis 目录说明

本目录已按职责拆分为子目录，避免脚本与文档混放。

## 目录结构

```text
evm_analysis/
├── README.md
├── evm-decision-tree-data.xlsx
├── docs/
│   ├── SLOT_DEFINITION.md
│   └── SEMESTER_PROGRESS_REPORT.md   # 学期检查报告文稿（对齐仓库复现）
├── modeling/
│   ├── train.py
│   ├── train_light_gbm.py
│   ├── train_hybrid.py
│   ├── predict.py
│   ├── predict_light_gbm.py
│   ├── predict_hybrid.py
│   ├── export_go_model.py
│   └── load_paper_metrics.py
├── models/
│   └── evm_model*.pkl
├── analysis/
│   ├── slot_distribution_analysis.py
│   ├── topk_slot_coverage.py
│   ├── sweep_hybrid_threshold.py
│   ├── estimate_prefetch_gain.py
│   └── benchmark_inference_latency.py
├── viz/
│   └── plot_figures.py
└── figures/
    ├── *.png
    ├── README_CAPTIONS.txt
    ├── FIGURE_STORYLINE.md
    └── data/*.csv
```

说明：
- 训练产物 `*.pkl` 统一保存在 `evm_analysis/models/`。
- 图像输出在 `evm_analysis/figures/`，图表数据在 `evm_analysis/figures/data/`。

## 关键脚本入口

- 训练：
  - `evm_analysis/modeling/train.py`
  - `evm_analysis/modeling/train_light_gbm.py`
  - `evm_analysis/modeling/train_hybrid.py`
- 分析：
  - `evm_analysis/analysis/slot_distribution_analysis.py`
  - `evm_analysis/analysis/topk_slot_coverage.py`
  - `evm_analysis/analysis/sweep_hybrid_threshold.py`
- 绘图：
  - `evm_analysis/viz/plot_figures.py`

## 指标口径提示

- `train.py` / `train_light_gbm.py`：标签矩阵口径（Top-K Recall / Total Recall / Precision / EM）
- `train_hybrid.py`：集合口径（set-based recall/precision）

两者不可在同一坐标轴直接数值比较。

## 复现图表（新路径）

```bash
# 1) 合并图2数据（xlsx -> csv）
python evm_analysis/modeling/load_paper_metrics.py

# 2) 导出图1数据
python evm_analysis/analysis/slot_distribution_analysis.py --export-csv evm_analysis/figures/data/

# 3) 导出图3数据
python evm_analysis/analysis/topk_slot_coverage.py --export-csv evm_analysis/figures/data/

# 4) 导出图4数据（示例阈值）
python evm_analysis/analysis/sweep_hybrid_threshold.py --max-test-rows 4000 --thresholds 11 38 95 245 671

# 5) 生成图
python evm_analysis/viz/plot_figures.py --all
```

