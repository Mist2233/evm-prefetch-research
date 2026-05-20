# evm_analysis 目录说明

本目录为本项目的核心成果区，按职责拆分为子目录，覆盖数据采集、建模训练、分布分析、仿真验证、可视化与文档。

## 目录结构

```text
evm_analysis/
├── README.md
├── evm-decision-tree-data.xlsx
├── docs/
│   ├── SLOT_DEFINITION.md
│   ├── SEMESTER_PROGRESS_REPORT.md
│   ├── MODIFY_NOTE.md
│   ├── SIMULATION_PLATFORM_PLAN.md
│   ├── RECENT_ISSUES_SUMMARY.md
│   ├── PHASE_A_OVERLAP_MODEL.md
│   ├── PHASE_B_OFFLINE_DELTA.md
│   └── patent/
│       ├── patent_specification.md
│       ├── patent_claims.md
│       ├── patent_abstract.md
│       └── PATENT_WRITING_GUIDE.md
├── modeling/
│   ├── train.py
│   ├── train_light_gbm.py
│   ├── train_hybrid.py
│   ├── export_go_model.py
│   └── load_paper_metrics.py
├── simulation/
│   ├── run.py
│   ├── data_loader.py
│   ├── cache_sim.py
│   ├── prefetch_api.py
│   ├── prefetch_executor.py
│   ├── metric_log.py
│   └── offline_delta.py
├── analysis/
│   ├── slot_distribution_analysis.py
│   ├── topk_slot_coverage.py
│   ├── sweep_hybrid_threshold.py
│   ├── estimate_prefetch_gain.py
│   └── benchmark_inference_latency.py
├── viz/
│   ├── plot_figures.py
│   ├── plot_sim_figures.py
│   └── plot_patent_figures.py
├── models/            # 训练产物 *.pkl（~10GB）
├── figures/
│   ├── data/          # 图表源 CSV
│   ├── patent/        # 专利附图
│   ├── mid-figures/   # 中期图表归档
│   └── sim-figures/   # 仿真结果图表
└── logs/              # 仿真运行日志
```

说明：
- 训练产物 `*.pkl` 统一保存在 `evm_analysis/models/`。
- 图表输出在 `evm_analysis/figures/`，源数据 CSV 在 `evm_analysis/figures/data/`。

## 关键脚本入口

### 训练
- `evm_analysis/modeling/train.py` — 决策树多标签训练（基线）
- `evm_analysis/modeling/train_light_gbm.py` — LightGBM 多标签训练
- `evm_analysis/modeling/train_hybrid.py` — 混合模型训练（快路径 + 慢路径）

### 分析
- `evm_analysis/analysis/slot_distribution_analysis.py` — 规则并集分布分析（Fig 1a）
- `evm_analysis/analysis/topk_slot_coverage.py` — Top-K 访问覆盖率（Fig 3a）
- `evm_analysis/analysis/sweep_hybrid_threshold.py` — 混合阈值 Pareto 扫描（Fig 4a）

### 仿真
- `evm_analysis/simulation/run.py` — CLI 主入口，支持 `--all`（E0–E3）、`--sensitivity`、`--alpha-sweep`、`--offline-delta`、`--parallel-sensitivity` 等模式
- `evm_analysis/simulation/offline_delta.py` — 离线增量管道（Phase B）

### 绘图
- `evm_analysis/viz/plot_figures.py` — 论文图表（Fig 1–5）
- `evm_analysis/viz/plot_sim_figures.py` — 仿真图表（Phase A/B）
- `evm_analysis/viz/plot_patent_figures.py` — 专利附图

## 指标口径提示

- `train.py` / `train_light_gbm.py`：标签矩阵口径（Top-K Recall / Total Recall / Precision / EM）
- `train_hybrid.py`：集合口径（set-based recall/precision）
- 两种口径**不可在同一坐标轴直接数值比较**，报告和论文中应显式区分。

## 复现图表

```bash
# 1) 合并 Fig2 数据（xlsx → csv）
python evm_analysis/modeling/load_paper_metrics.py

# 2) 导出 Fig1 数据
python evm_analysis/analysis/slot_distribution_analysis.py --export-csv evm_analysis/figures/data/

# 3) 导出 Fig3 数据
python evm_analysis/analysis/topk_slot_coverage.py --export-csv evm_analysis/figures/data/

# 4) 导出 Fig4 数据（示例阈值）
python evm_analysis/analysis/sweep_hybrid_threshold.py --max-test-rows 4000 --thresholds 11 38 95 245 671

# 5) 生成论文图表
python evm_analysis/viz/plot_figures.py --all
```

## 仿真复现

```bash
# 四组对照实验（抽样）
python -m simulation.run --all --data-mode real_block --max-txs 200 \
  --model models/evm_model_hybrid_v1.pkl

# Alpha 覆盖敏感性
python -m simulation.run --alpha-sweep --data-mode real_block --max-txs 500 \
  --model models/evm_model_hybrid_v1.pkl --tx-exec-us-per-slot 100

# 离线增量管道（全量，约 15 分钟）
python -m simulation.run --offline-delta --data-mode real_block \
  --model models/evm_model_hybrid_v1.pkl \
  --delta-split-ratio 0.7 --delta-min-support 2 --delta-max-slots-per-key 20

# 敏感性分析
python -m simulation.run --sensitivity --model models/evm_model_hybrid_v1.pkl
python -m simulation.run --parallel-sensitivity --prefetch-timing timed \
  --model models/evm_model_hybrid_v1.pkl

# 生成仿真图表
python viz/plot_sim_figures.py --all

# 生成专利附图
python viz/plot_patent_figures.py
```

结果输出至 `figures/data/`（CSV）和各 `figures/` 子目录（PNG）。

## 全量实验结果

| 指标 | rule_base | rule_plus_delta | 变化 |
|---|---|---|---|
| Recall | 0.2223 | 0.3117 | **+40.2%** |
| Total Cost | 880,983 µs | 781,405 µs | **−11.3%** |

详见 `docs/PHASE_B_OFFLINE_DELTA.md`。
