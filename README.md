# EVM 存储访问预测与混合预取研究

基于以太坊主网真实 Trace 数据，研究 EVM 交易级存储槽（slot）访问预测，提出在线/离线职责分离的混合预取架构。在线路径仅执行 O(1) 哈希查表（微秒级），机器学习推理完全剥离为离线增量规则生成任务，在零在线推理开销的前提下持续提升预测覆盖率。

## 项目结构

```
transaction-replay/
├── README.md                        # 本文件
├── replay.py                        # 主网交易回放与 trace 采集
├── run_offline_erigon.sh            # 魔改 Erigon 离线启动脚本
├── requirements.txt                 # Python 依赖
├── erigon_tx_trace.jsonl            # 采集产物（~238MB，另获取）
│
└── evm_analysis/                    # ★ 核心分析/建模/仿真（主要成果）
    ├── README.md                    # 详细说明、复现命令、指标口径
    ├── evm-decision-tree-data.xlsx  # 论文指标源数据
    │
    ├── modeling/                    # 模型训练与推理
    │   ├── train.py                 # 决策树多标签训练（基线）
    │   ├── train_light_gbm.py       # LightGBM 多标签训练
    │   ├── train_hybrid.py          # 混合模型训练（快路径+慢路径）
    │   ├── export_go_model.py       # 模型导出为 Go 代码
    │   └── load_paper_metrics.py    # xlsx → csv 指标转换
    │
    ├── simulation/                  # ★ 仿真平台（核心工程验证）
    │   ├── run.py                   # CLI 入口（E0–E3 四组实验、敏感性分析等）
    │   ├── cache_sim.py             # 块内 first-touch 缓存仿真
    │   ├── data_loader.py           # 数据加载（pseudo / real block）
    │   ├── prefetch_api.py          # 预取策略接口
    │   ├── prefetch_executor.py     # 异步预取执行器
    │   ├── metric_log.py            # 指标收集与聚合
    │   └── offline_delta.py         # 离线增量管道（Phase B）
    │
    ├── analysis/                    # 数据分析与阈值扫描
    │   ├── slot_distribution_analysis.py   # 规则并集分布（Fig 1a）
    │   ├── topk_slot_coverage.py           # Top-K 访问覆盖率（Fig 3a）
    │   └── sweep_hybrid_threshold.py       # 混合阈值扫描（Fig 4a）
    │
    ├── viz/                         # 图表生成
    │   ├── plot_figures.py          # 论文图表（Fig 1–5）
    │   ├── plot_sim_figures.py      # 仿真图表（Phase A/B）
    │   └── plot_patent_figures.py   # 专利附图
    │
    ├── docs/                        # 文档
    │   ├── SLOT_DEFINITION.md       # Slot 术语定义
    │   ├── SEMESTER_PROGRESS_REPORT.md    # 学期进展报告
    │   ├── MODIFY_NOTE.md           # 项目变更申请
    │   ├── SIMULATION_PLATFORM_PLAN.md   # 仿真平台工程计划
    │   ├── PHASE_A_OVERLAP_MODEL.md      # Phase A：执行时间覆盖
    │   ├── PHASE_B_OFFLINE_DELTA.md      # Phase B：离线增量管道
    │   └── patent/                  # 专利申请文件（已提交）
    │
    ├── models/                      # 训练产物（*.pkl, ~10GB）
    ├── figures/                     # 图表输出（PNG + 源数据 CSV）
    └── logs/                        # 仿真运行日志
```

## 核心成果

### 方法
**混合预取架构**：快路径 `(to, selector)` 哈希查表（O(1)）+ 慢路径 LightGBM 多标签预测。
**在线/离线职责分离**：在线仅查表，ML 推理转为离线增量规则生成任务，零在线推理开销。

### 全量实验（999 区块 / 94,463 笔交易）

| 指标 | rule_base | rule_plus_delta | 变化 |
|---|---|---|---|
| Recall | 0.2223 | 0.3117 | **+40.2%** |
| Total Cost | 880,983 µs | 781,405 µs | **−11.3%** |
| 新增规则 | — | 253 键 / 2,641 slot | — |

缩放一致性：Recall 提升 +27.4% → +35.7% → +40.2%（随数据规模单调递增）。

### 知识产权
已提交中国发明专利申请：**"基于在线免推理与离线增量生成的以太坊虚拟机存储访问混合预取方法及系统"**（见 `evm_analysis/docs/patent/`）。

## 数据采集（需魔改版 Erigon）

Trace 数据通过 `replay.py` 配合**魔改版 Erigon** 采集。魔改版在 `TraceTx` 函数中埋入 Hook，在执行 `debug_traceTransaction` RPC 时同步输出 `erigon_tx_trace.jsonl`，每条记录包含目标合约地址、函数选择器、代码哈希、调用参数及实际访问的存储槽列表。

```bash
# 1. 启动魔改版 Erigon（离线模式）
./run_offline_erigon.sh

# 2. 回放区块，采集 trace
python3 replay.py 20000000 20001000
```

魔改版 Erigon 仓库需另行获取（与本仓库同级目录 `erigon-upstream/`），改动了 `core/state/intra_block_state.go` 和 `eth/tracers/api.go` 两处，在交易执行路径上插入数据收集逻辑。

采集完成后，产物 `erigon_tx_trace.jsonl` 作为 `evm_analysis/` 的输入数据。

## 快速上手

```bash
# 环境
cd evm_analysis
python3 -m venv .venv && source .venv/bin/activate
pip install -r ../requirements.txt

# 仿真：四组对照实验（抽样，200 笔）
python -m simulation.run --all --data-mode real_block --max-txs 200 \
  --model models/evm_model_hybrid_v1.pkl

# 离线增量管道（全量，约 15 分钟）
python -m simulation.run --offline-delta --data-mode real_block \
  --model models/evm_model_hybrid_v1.pkl \
  --delta-split-ratio 0.7 --delta-min-support 2 --delta-max-slots-per-key 20

# 生成论文图表
python viz/plot_figures.py --all
```

详细命令及参数说明见 [`evm_analysis/README.md`](evm_analysis/README.md)。
