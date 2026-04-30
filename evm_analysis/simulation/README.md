# simulation — EVM 存储预取仿真平台

**工程论证与边界说明**（Mode A 伪块 / Mode B 真块、结题叙事、路线图）：见 [docs/SIMULATION_PLATFORM_PLAN.md](../docs/SIMULATION_PLATFORM_PLAN.md)。**本 README 为命令行与复现的权威口径。**

## 背景

本模块实现了一个**数据驱动的离线重放仿真器**，用于在不修改 Erigon 源码的前提下，量化 slot 预取策略对存储访问代价的实际改善幅度。

**核心思路**：`erigon_tx_trace.jsonl` 中已包含真实执行的 `accessed_slots` 序列，无需重跑 EVM。仿真器直接回放这些访问序列，在 Python 中模拟 Erigon `intra_block_state` 的块内缓存语义，对比「有预取 vs 无预取」的总代价差异。

---

## 模块结构

```
simulation/
├── README.md
├── __init__.py
├── data_loader.py    # 支持 pseudo_block / real_block 两种分组
├── cache_sim.py      # 块内 first-touch 缓存仿真（核心逻辑）
├── prefetch_executor.py  # 异步预取执行器（并行/排队近似）
├── prefetch_api.py   # 四种预取策略接口
├── metric_log.py     # 指标收集与聚合
└── run.py            # CLI 主入口
```

---

## 仿真语义说明

当前支持两种块划分：

- **pseudo_block（默认）**：将连续 N 条记录视为同一个块（默认 N=293）。
- **real_block**：要求数据包含 `block_number` + `transaction_index`，按真块分组重放。

| Erigon 真实行为 | 仿真对应 |
|---|---|
| `intra_block_state` 块内积累 state objects | 块内缓存字典（`set[str]`）积累已访问 slots |
| 块内首次访问某 slot → 从 DB 加载（`t_miss`） | 该 slot 不在缓存字典中 → 计 `t_miss` |
| 块内重复访问同一 slot → 已在内存（`t_hit`） | 该 slot 已在缓存字典中 → 计 `t_hit` |
| 新块开始时 `intra_block_state` 被清空 | `reset_block()` 清空缓存字典 |
| 预取 = 提前将 slots 写入 `intra_block_state` | `process_tx()` 在访问前注入预测，并可模拟异步完成时间 |

并行预取支持两种时序模型：

- `--prefetch-timing ideal`：预测 slot 立即就绪（理论上界）。
- `--prefetch-timing timed`：按 `t_prefetch_us`、`prefetch_concurrency`、`queue_delay_us` 模拟并行预取完成时刻；仅当 `prefetch_finish_time <= first_access_time` 才算预取成功。

---

## 四组对照实验

| 实验组 | 预取器 | 用途 |
|---|---|---|
| **E0** | `none` | 无预取基线，所有 first-touch 均为 miss |
| **E1** | `oracle` | 理想上界，预测完全正确（用于自检仿真正确性） |
| **E2** | `rule` | 仅 `fast_path_dict` 查表，无 ML 模型 |
| **E3** | `hybrid` | 完整混合预取器（查表 + LightGBM 慢路径） |

**自检逻辑**（E0 vs E1）：
- E0 的「应有 miss 数」应等于「实际 miss 数」（偏差 < 0.01%）
- E1 的 Recall 应为 1.0000
- E1 总代价 ≤ E0 总代价

---

## 指标定义

```
recall    = 预取防止的 miss 数 / 无预取时应有的 miss 总数
precision = 预取防止的 miss 数 / 预测 slot 总数
speedup   = E0 总代价 / 当前方案总代价
```

这里的 recall 定义与 `train_hybrid.py` 中的集合口径不同：
- 训练脚本：`recall = 预测集合 ∩ 真实集合 / 真实集合`（per-transaction 集合交并）
- 仿真脚本：`recall = 块级 first-touch miss 被防止的比例`（更贴近工程意义）

---

## 最新结果快照（2026-04-27）

以下结果来自当前仓库数据与脚本，已切换到新数据文件（含 `block_number`、`transaction_index`），用于说明“优化是否已实现”。  
**注意**：这是阶段性结果（含 `max-txs` 限定），可用于周报/汇报，但不应当作最终全量结论。

### A. real_block 模式四组对比（`max-txs=200`）

命令：

```bash
python -m simulation.run --all \
  --data-mode real_block \
  --max-txs 200 \
  --model models/evm_model_hybrid_v1.pkl \
  --output-dir figures/data
```

结果（来自 `figures/data/simulation_results.csv`）：

| 方案 | total_cost_us | speedup_vs_baseline | recall | precision |
|---|---:|---:|---:|---:|
| none (E0) | 8997.00 | 1.0000x | 0.0000 | 0.0000 |
| rule (E2) | 7399.14 | 1.2160x | 0.1798 | 0.2191 |
| hybrid (E3) | 6683.37 | 1.3462x | 0.2603 | 0.2592 |
| oracle (E1) | 107.79 | 83.4679x | 1.0000 | 0.8330 |

可读结论：
- 在真实块顺序下，`hybrid` 相比无预取 `none` 已实现可观优化（约 **1.35x**，节省约 **25.7%** 代价）。
- `hybrid` 优于 `rule`，说明慢路径模型在工程口径下提供额外收益。
- `oracle` 与 `none` 形成上下界，验证了仿真器方向正确。

### B. 并行预取敏感性（timed prefetch）

命令：

```bash
python -m simulation.run --parallel-sensitivity \
  --prefetch-timing timed \
  --model models/evm_model_hybrid_v1.pkl \
  --output-dir figures/data
```

结果（`figures/data/parallel_prefetch_sensitivity.csv`）显示：
- 当 `t_prefetch_us` 增大、并发度不足时，`prefetch_timely_rate` 明显下降，speedup 随之下降；
- 增加 `prefetch_concurrency` 能部分恢复收益；
- 这证明“预取是否并行且来得及”是收益成立的必要条件，而不是可忽略细节。

### C. 参数鲁棒性（hit/miss 代价扰动）

结果（`figures/data/sensitivity_table.csv`）显示，在 `t_hit` / `t_miss` ±20% 扰动下，speedup 变化较小（约 1.33x 附近），结论方向稳定。

### 当前阶段结论（是否已实现优化）

可以回答“**已实现**”：  
- 在 `real_block` + 真实 trace 的工程口径下，`hybrid` 已稳定优于 `none` 与 `rule`；  
- 并行预取模型（timed）也显示在可接受延迟/并发下存在明确收益。  

同时需要保留边界声明：  
- 目前是离线 trace 重放，不含真实客户端端到端 I/O 与调度抖动；  
- 最终论文/结题应补更大规模 `max-txs` 或全量运行结果。

---

## 快速上手

在项目根目录（`evm_analysis/`）运行，需要 `erigon_tx_trace.jsonl` 和 `models/evm_model_hybrid_v1.pkl`。

### 快速验证（前 20 个伪块）

```bash
python -m simulation.run --all \
  --model models/evm_model_hybrid_v1.pkl \
  --max-blocks 20
```

### 全量四组对比

```bash
python -m simulation.run --all \
  --model models/evm_model_hybrid_v1.pkl \
  --output-dir figures/data
```

结果输出至 `figures/data/simulation_results.csv`。

### 单次运行（指定预取器）

```bash
# E0：无预取基线
python -m simulation.run --prefetcher none

# E3：混合预取器（全量）
python -m simulation.run --prefetcher hybrid \
  --model models/evm_model_hybrid_v1.pkl
```

### 敏感性分析

```bash
python -m simulation.run --sensitivity \
  --model models/evm_model_hybrid_v1.pkl \
  --output-dir figures/data
```

扫描五组 `t_hit`/`t_miss` 参数组合，结果输出至 `figures/data/sensitivity_table.csv`。

### 并行预取敏感性

```bash
python -m simulation.run --parallel-sensitivity \
  --model models/evm_model_hybrid_v1.pkl \
  --prefetch-timing timed \
  --output-dir figures/data
```

输出 `figures/data/parallel_prefetch_sensitivity.csv`，用于分析不同预取延迟和并发度下的 speedup 与及时命中率。

### 模式对比（pseudo vs real）

```bash
python -m simulation.run --compare-modes \
  --model models/evm_model_hybrid_v1.pkl \
  --block-number-field block_number \
  --tx-index-field transaction_index \
  --output-dir figures/data
```

输出 `figures/data/mode_compare.csv`。

### 完整参数列表

```
--data         JSONL 数据文件路径（默认：../erigon_tx_trace.jsonl）
--model        Hybrid 模型 pkl 路径（默认：models/evm_model_hybrid_v1.pkl）
--prefetcher   none / oracle / rule / hybrid（单次运行用）
--all          依次运行 E0/E1/E2/E3 并输出对比
--sensitivity  运行敏感性分析
--parallel-sensitivity 运行并行预取敏感性分析
--compare-modes 对比 pseudo_block 与 real_block 两种模式
--inspect-data  抽样检查数据字段可用性
--data-mode    pseudo_block / real_block（默认 pseudo_block）
--block-number-field real_block 模式块号字段名（默认 block_number）
--tx-index-field real_block 模式块内交易序字段名（默认 transaction_index）
--block-size   伪块大小，默认 293
--max-blocks   最多处理的伪块数（不填则全量）
--max-txs      最多处理的交易条数（用于快速抽样）
--t-hit-ns     命中代价，默认 30.0 ns
--t-miss-us    缺失代价，默认 3.0 µs
--prefetch-timing ideal / timed（默认 ideal）
--t-prefetch-us 单槽预取服务时间（µs）
--prefetch-concurrency 预取并发 worker 数
--queue-delay-us 预取入队固定延迟（µs）
--output-dir   CSV 输出目录，默认 figures/data
--quiet        减少进度输出
```

---

## 输出文件说明

### `simulation_results.csv`

每行对应一个实验组，字段包括：

| 字段 | 含义 |
|---|---|
| `prefetcher` | 预取器名称 |
| `n_blocks` | 处理的伪块数 |
| `n_tx` | 处理的交易数 |
| `n_would_be_miss` | E0 基准下的 first-touch miss 总数 |
| `n_miss_prevented` | 预取实际防止的 miss 数 |
| `recall` | 防止 miss 的覆盖率 |
| `precision` | 预测精度 |
| `total_cost_us` | 总仿真代价（µs） |
| `speedup_vs_baseline` | 相对 E0 的加速比 |
| `saved_cost_us` | 相对 E0 节省的代价（µs） |

### `sensitivity_table.csv`

每行对应一组 `t_hit`/`t_miss` 参数，固定使用 hybrid 预取器，记录加速比和节省百分比。

---

## 与现有脚本的关系

| 脚本 | 性质 | 在报告中的位置 |
|---|---|---|
| `analysis/estimate_prefetch_gain.py` | 解析公式模型 | 延迟分析理论推导（Fig 5a） |
| `simulation/run.py` | 数据驱动仿真 | 延迟分析实验验证，与 Fig 5a 并列引用 |
| `modeling/train_hybrid.py` | 离线训练 | 模型指标（Fig 4a Pareto 表） |

---

## 周三汇报逻辑（建议口径）

建议按 5 句主线汇报，避免被追问时口径分散：

1. **问题定义**：目标是降低块内 first-touch miss 代价，验证预取是否在执行路径上带来收益。  
2. **方法选择**：不改 Erigon 热路径，采用 trace-driven 仿真；先 `pseudo_block`，后 `real_block`（现已补齐 `block_number/transaction_index`）。  
3. **核心结果**：`real_block` 下 `hybrid` 对比 `none` 达到约 1.35x；且优于 `rule`，说明模型慢路径有增益。  
4. **关键机制验证**：并行预取敏感性显示收益依赖 `prefetch_finish_time <= first_access_time`；并发度不足时收益下滑。  
5. **边界与下一步**：当前为离线上界评估；下一步扩大样本规模并补客户端端到端测量，固化最终数字。  

一句话版本：

> 我们已经在真实块顺序 trace 上验证了优化成立，且并行预取是否及时是收益的决定因素；下一步是扩大样本并补端到端工程测量。
