# 仿真平台工程计划书

> **文档用途**：解决「不修改 Erigon 源码、如何验证预取收益」的工程层难点，给出仿真环境的设计说明、语义边界与结题叙事。  
> **适用阶段**：大创项目仿真平台搭建与结题收口。  
> **数据与模型说明**：`erigon_tx_trace.jsonl` 及训练产物 `*.pkl` 可在服务器或本地路径；凡涉及「读取数据/加载模型」的路径按实际环境填写。

**与代码的关系**：**命令行参数、默认路径与复现步骤以 [simulation/README.md](../simulation/README.md) 为唯一执行口径**；本计划书负责工程动机、Mode A/B 边界、模块语义、数据口径、路线图与结题表述，避免与实现漂移。

---

## 一、核心工程难点与解题思路

### 1.1 为什么不直接改 Erigon

Erigon 是 Go 语言实现的完整以太坊客户端，代码量约 50 万行，内部状态管理（`intra_block_state`、`state.Reader`、Trie 缓存等）深度耦合。若要在其中埋入「预取注入点」并测量前后延迟，需要：

- 理解多层读路径（MDBX → StateReader → intra_block_state）；
- 修改 block execution 热路径，引入 instrumentation；
- 保持与共识层的语义等价性，不破坏状态根校验；
- 在 Go 环境中对接 Python 模型。

上述每一项单独拿出来都是独立的工程课题。对于大创项目而言，侵入式修改的风险远超收益。

### 1.2 解题思路：数据驱动的离线重放仿真

关键洞察：**我们已经拥有真实执行的访问序列**。`erigon_tx_trace.jsonl` 的每条记录包含一笔交易真实访问过的存储槽位列表（`accessed_slots`），这是 Erigon 线上执行的直接产物。

因此，「验证预取收益」不需要再次运行 Erigon，只需：

```
离线重放 JSONL 数据  ──→  仿真缓存状态  ──→  统计命中/缺失代价
                              ↑
                      注入预取预测结果（ML 模型输出）
```

仿真无需真正执行 EVM 字节码，也无需接触 Erigon 源码；**它只是在已知的访问序列上模拟块内 first-touch 计费逻辑**，实现成本低，结论对「预取减少了多少 first-touch miss」具有直接可解释性。

---

## 二、执行模式：Mode A（默认，已实现）与 Mode B（可选升级）

### 2.1 Mode A：伪块（pseudo-block）— 当前仓库实现

**背景**：当前数据集可能**不含**链上真实字段 `block_number`。无法在 JSONL 内恢复主网块边界时，采用**固定窗口**：连续 `block_size` 条记录视为一个「伪块」，块边界处执行 `reset_block()`，模拟「块内缓存清零」这一行为。

**默认参数**：`block_size = 293`（来自全量记录数与区块数的比例取整，见 `simulation/data_loader.py` 中 `DEFAULT_BLOCK_SIZE`）。可通过 CLI `--block-size` 调整；`--max-blocks` 用于快速试跑。

**与 Erigon 的对应关系（须写进结题边界声明）**：

- **一致之处**：块（或伪块）内 first-touch 语义、跨边界缓存重置、先预取再按 `accessed_slots` 顺序计费，与 `intra_block_state` 的**块内首次/重复访问**类比一致。
- **不一致之处**：伪块边界**不等于**以太坊真实块边界；跨真实块但落在同一伪块内的两条交易，在仿真中会共享块内缓存。因此 Mode A 给出的是**在固定窗口重放假设下的**延迟与加速比，**不声称**与「按真实块重放」数值逐点相同。

### 2.2 Mode B：真块（on-chain block）— ✅ 已实现

**前提**：JSONL 每行至少包含 **`block_number`** 与块内排序字段（建议统一为 **`transaction_index`**，与常见 RPC 命名一致）。

**行为**：`DataLoader.iter_blocks()` 按 `block_number` 分组，组内按 `transaction_index` 排序后依次重放；其余仿真逻辑（`CacheSim`、`PrefetchAPI`、`MetricLog`）与 Mode A 相同。

**当前状态**：Mode B（`--data-mode real_block`）已在 `data_loader.py` 中完全实现，支持 `--block-number-field` 和 `--tx-index-field` 参数配置字段名。全量实验（999 个真实区块，94,463 笔交易）及离线增量管道均运行在 real_block 模式下。

### 2.3 数据口径：`skip_empty_slots`

当前 [simulation/data_loader.py](../simulation/data_loader.py) 默认 **`skip_empty_slots=True`**：跳过 `accessed_slots` 为空或缺失的记录。

**结题中须声明**：仿真统计的是「**至少发生一次非空存储访问**」的交易子集上的代价与加速比；若需纳入无存储访问的交易（代价恒为 0），需显式关闭该选项并重新评估全量曲线含义。

---

## 三、有效性论证

### 3.1 语义对应关系（块内 first-touch）

下表在 **Mode A 或 Mode B** 下均成立：二者仅「块边界如何划分」不同，块内计费语义相同。

| Erigon 真实行为 | 仿真中的对应 |
|---|---|
| `intra_block_state` 在块内积累已加载的 state / storage 视图 | 块内缓存 `set[str]` 积累已「就绪」的 slot |
| 同块内第二次访问同一 slot → 已在内存 | 同块内第二次出现同一 slot → `t_hit` |
| 新块开始时块内缓存语义重置 | 每个（真/伪）块开始前 `reset_block()` 清空集合 |
| 预取 = 在交易执行前将 key 标为已就绪 | `process_tx` 内在遍历 `accessed_slots` 前合并预测 slot 入缓存 |
| 代价量级 | 参数 `t_hit_ns`、`t_miss_us`（默认 30 ns / 3 µs，可调） |

解析层面的 first-touch 讨论见 [analysis/estimate_prefetch_gain.py](../analysis/estimate_prefetch_gain.py)（`block-first-touch` 等模型）；本仿真是其**带真实 trace 序列的具体化**：用 JSONL 中的访问顺序驱动计数，而非仅用聚合统计量。

### 3.2 假设与局限（须在报告中声明）

1. **预取完全及时**：预取在交易「执行」前完成，且命中预取的 slot 在首次真实访问前已在块内缓存中。实际系统若预取落后于执行，收益低于仿真。→ 仿真给出**理论收益上界**之一。
2. **忽略预取侧额外 I/O 代价**：低 Precision 时真实系统会浪费带宽；可作扩展敏感性项（例如对 `|predicted|` 加惩罚项），当前实现未默认计入。
3. **单机串行重放**：不模拟多 worker 并发与锁竞争；关注「有/无预取」的相对趋势时通常可接受。
4. **`t_hit` / `t_miss` 为经验参数**：注明来源，并用 `--sensitivity` 扫描五组参数（见第七节）声明鲁棒性边界。

---

## 四、整体架构

```
┌─────────────────────────────────────────────────────────────┐
│           仿真主流程：simulation/run.py :: run_simulation      │
│           （块循环 + 交易循环；若代码膨胀可再拆 block_replayer） │
│                                                             │
│   ┌──────────────┐      ┌─────────────┐      ┌───────────┐   │
│   │  DataLoader  │─────▶│  CacheSim   │◀────▶│ MetricLog│   │
│   │  按块迭代     │      │ process_tx  │      │ record   │   │
│   └──────────────┘      └──────▲──────┘      └─────┬─────┘   │
│          │                     │ predict()          │         │
│          │              ┌───────┴───────┐            │         │
│          │              │ PrefetchAPI │            │         │
│          │              │ (各 Prefetcher)         │         │
│          │              └─────────────┘            │         │
└──────────┼──────────────────────────────────────────┼─────────┘
           │                                          │
           └──────────────────┬───────────────────────┘
                              ▼
              figures/data/simulation_results.csv
              figures/data/sensitivity_table.csv
              （可选）viz 扩展 fig_sim_*.png
```

| 模块 | 文件 | 职责 |
|---|---|---|
| 重放与 CLI | [simulation/run.py](../simulation/run.py) | `run_simulation()`：按块调用 `reset_block`、逐笔 `predict` + `process_tx`、`MetricLog`；`main()` 解析参数、`sanity_check`、写 CSV |
| `DataLoader` | [simulation/data_loader.py](../simulation/data_loader.py) | Mode A：按 `block_size` 窗口分组；支持 `max_blocks`、`skip_empty_slots` |
| `CacheSim` | [simulation/cache_sim.py](../simulation/cache_sim.py) | `process_tx(tx, predicted_slots)`：先算无预取时的 first-touch miss 集合，再注入预测，再按序列计 hit/miss 与代价 |
| `PrefetchAPI` | [simulation/prefetch_api.py](../simulation/prefetch_api.py) | `make_prefetcher`：`none` / `oracle` / `rule` / `hybrid` |
| `MetricLog` | [simulation/metric_log.py](../simulation/metric_log.py) | 聚合 `RunSummary`；recall/precision 为**防止的块级 first-touch miss** 口径（见 simulation README） |

---

## 五、核心模块说明（与实现对齐）

### 5.1 DataLoader（Mode A）

- `iter_blocks()`：顺序读取 JSONL，累积至 `block_size` 条有效行后 `yield` 一批交易字典；文件末尾不足一批则 yield 尾块。
- `get_stats()` / `count_rows()`：估算总行数、伪块数，用于报告规模说明。

Mode B 实现时：增加按 `block_number` 分组与 `transaction_index` 排序的迭代器，或同一类内通过构造函数 flag 切换策略。

### 5.2 CacheSim

实现以仓库为准：**`process_tx(tx, predicted_slots) -> TxResult`**，内部顺序为：

1. 在注入预测前，用当前块缓存计算「若无预取，本笔交易 unique slots 中哪些会是 first-touch miss」；
2. 将 `predicted_slots` 并入缓存；
3. 按 `accessed_slots` **列表顺序**（含重复访问）计费并更新缓存。

（早期设计稿中的 `prefetch` + `access_tx` 拆分仅为说明性伪代码，与当前合并 API 等价。）

### 5.3 PrefetchAPI

- **E0** `NoPrefetcher`：恒返回 `[]`。
- **E1** `OraclePrefetcher`：返回真实 `accessed_slots` 的去重集合（顺序无关）。
- **E2** `RuleBasePrefetcher`：仅查 `fast_path_dict[(to, selector)]`。
- **E3** `HybridPrefetcher`：快路径字典命中则返回；否则用 `joblib` 加载的模型 + `MultiLabelBinarizer` 与训练时一致的特征编码（见 `prefetch_api.py`，与 `predict_hybrid.py` 对齐）。

### 5.4 MetricLog 与聚合指标

单笔结果见 `TxResult`；全量聚合见 `RunSummary`。与训练脚本中「集合 recall」不同，仿真侧 recall/precision 定义为（见 README）：

- **recall** = 预取防止的 first-touch miss 数 / 无预取时应有的 first-touch miss 总数  
- **precision** = 预取防止的 miss 数 / 预测 slot 总数（去重后逐笔求和）  
- **speedup** = E0 `total_cost_us` / 当前方案 `total_cost_us`

---

## 六、对照实验设计（E0–E3）

仿真的价值在于**控制变量**。四组实验须使用**同一份 JSONL、同一 `block_size`（或同一 Mode B 块划分）、同一 `t_hit_ns` / `t_miss_us`**。

| 实验组 | 预取器（CLI / 代码） | 用途 |
|---|---|---|
| E0 | `none` | 无预取基线，作分母 |
| E1 | `oracle` | 理想上界，用于自检仿真实现 |
| E2 | `rule` | 仅 fast_path，量化查表贡献 |
| E3 | `hybrid` | 完整混合策略，核心结论文案 |

**完整性检验（与代码一致）**：运行 `python -m simulation.run --all ...` 时，[run.py](../simulation/run.py) 中 **`sanity_check(baseline, oracle)`** 执行：

1. **E0**：`n_would_be_miss` 与 `cache_misses_total` 相对偏差应极小（打印为「E0 miss 一致性」；实现中阈值 0.01%）。
2. **E1**：`recall` 应接近 1.0（Oracle 防止全部应有 miss）。
3. **E1 总代价 ≤ E0 总代价**。

不要求 E1 与某条手写闭式「全局加速比」自动对比误差 &lt;1%；若需在附录做解析对照，可采用**单伪块、少笔交易**手算验证 `process_tx` 顺序与计费。

---

## 七、敏感性分析

仓库已实现五组参数扫描（[run.py](../simulation/run.py) 中 `SENSITIVITY_PARAMS`），与下表一致：

| 标签 | t_hit (ns) | t_miss (µs) |
|---|---|---|
| 基准 | 30 | 3.0 |
| t_miss −20% | 30 | 2.4 |
| t_miss +20% | 30 | 3.6 |
| t_hit −20% | 24 | 3.0 |
| t_hit +20% | 36 | 3.0 |

**命令**（在 `evm_analysis/` 目录下）：

```bash
python -m simulation.run --sensitivity --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --output-dir figures/data
```

输出：`figures/data/sensitivity_table.csv`。若各组 hybrid 相对 E0 的加速比变化在合理范围内，可在结题中写「参数小幅扰动下结论方向稳定」（具体 ±15% 等阈值由你根据表格填写）。

---

## 八、数据依赖与接口约定

### 8.1 Mode A（伪块）— JSONL 字段

| 字段 | Mode A 仿真 | Hybrid 慢路径 | 备注 |
|---|---|---|---|
| `accessed_slots` | 必须（非空行才会被默认 loader 保留） | — | 地面真值 |
| `to`, `selector` | 预取键 | 特征 / 快路径键 | |
| `code_hash` | — | 建议有 | 编码用 |
| `input_param_1`, `input_param_2`, `input_param_3` | — | 建议有 | 缺失时慢路径用空串 fallback |
| `from`, `value` | — | 建议有 | 同上 |
| `block_number` | 不使用 | 可选 | Mode B 必须 |
| `transaction_index` | 不使用 | 可选 | Mode B 块内排序必须 |

### 8.2 Mode B — 额外字段

| 字段 | 要求 |
|---|---|
| `block_number` | 必须；用于分组 |
| `transaction_index` | 必须；组内升序重放 |

**字段探测脚本**（在准备 Mode B 或审计数据时使用；Mode A 可不依赖块号）：

```bash
python3 - <<'EOF'
import json
path = "erigon_tx_trace.jsonl"  # 按实际路径修改
with open(path) as f:
    row = json.loads(f.readline())
keys = set(row.keys())
for name in ("block_number", "transaction_index", "accessed_slots", "to", "selector"):
    print(name, "OK" if name in keys else "MISSING")
print("all keys:", sorted(keys))
EOF
```

### 8.3 模型路径

与训练脚本一致，默认相对 `evm_analysis/`：

`models/evm_model_hybrid_v1.pkl`

`HybridPrefetcher` / `make_prefetcher("rule")` 均从该文件读取 `fast_path_dict` 等；推理逻辑以 [prefetch_api.py](../simulation/prefetch_api.py) 为准，并与 [modeling/predict_hybrid.py](../modeling/predict_hybrid.py) 保持一致。

---

## 九、实现路线图（可执行验收）

以下步骤假设工作目录为 **`evm_analysis/`**，且已安装项目依赖（含 `joblib`、`pandas`、`lightgbm` 等）。

### 阶段 0：文档与口径（本文件 + README）

- **验收**：计划书与 README 无互相矛盾的命令或模块名。

### 阶段 1：快速跑通四组实验

```bash
python -m simulation.run --all --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --max-blocks 20 --output-dir figures/data
```

- **验收**：终端打印 `sanity_check` 三项通过；生成 `figures/data/simulation_results.csv` 共 **4 行**（E0–E3）；E1 recall 接近 1；E3 speedup 在 1～E1 之间（视数据而定）。

### 阶段 2：全量四组 + 敏感性

```bash
python -m simulation.run --all --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --output-dir figures/data

python -m simulation.run --sensitivity --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --output-dir figures/data
```

- **验收**：`simulation_results.csv` 与 `sensitivity_table.csv` 落盘；数值可用于结题表格。

### 阶段 3：与解析模型对照（叙事级，非逐点强制相等）

- 运行 [analysis/estimate_prefetch_gain.py](../analysis/estimate_prefetch_gain.py) 得到理论趋势与参数解释（Fig5a 等）。
- **验收**：结题中写清——解析模型给出**参数化上界/趋势**；仿真给出 **trace 驱动的总量与分布**；二者互补，**不要求**某个 recall 点上仿真加速比与公式数值完全一致。

### 阶段 4：可视化（可选）

- 扩展 `viz/plot_figures.py` 读取上述 CSV 生成 `fig_sim_*.png`。
- **验收**：图注中注明 Mode A 伪块与 `skip_empty_slots` 口径。

### 阶段 5：Mode B（✅ 已完成）

- `DataLoader` 已实现 real_block 模式，支持按 `block_number` 分组 + `transaction_index` 排序。
- 全量实验（999 区块）及离线增量管道均在 real_block 下运行。
- **验收**：Mode A（pseudo_block）与 Mode B（real_block）可通过 `--compare-modes` 对比。

---

## 十、目录结构（与仓库一致）

```
evm_analysis/
├── simulation/
│   ├── README.md
│   ├── run.py
│   ├── data_loader.py
│   ├── cache_sim.py
│   ├── prefetch_api.py
│   └── metric_log.py
├── docs/
│   └── SIMULATION_PLATFORM_PLAN.md   ← 本文件
├── figures/
│   └── data/
│       ├── simulation_results.csv
│       └── sensitivity_table.csv
├── analysis/
│   └── estimate_prefetch_gain.py
└── modeling/
    └── ...
```

可选工程卫生：在 `simulation/` 下增加空 `__init__.py` 便于部分工具识别为包（Python 3 下无该文件时从 `evm_analysis/` 运行 `python -m simulation.run` 仍可工作）。

### 典型运行命令（从 `evm_analysis/` 执行）

```bash
# 快速四组对比（前 20 个伪块）
python -m simulation.run --all --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --max-blocks 20 --output-dir figures/data

# 全量四组
python -m simulation.run --all --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --output-dir figures/data

# 单次 E3
python -m simulation.run --prefetcher hybrid --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --output-dir figures/data

# 敏感性（五组参数，固定 hybrid）
python -m simulation.run --sensitivity --model models/evm_model_hybrid_v1.pkl \
  --data erigon_tx_trace.jsonl --output-dir figures/data
```

单次运行会额外写入 `figures/data/sim_{prefetcher}.csv`（以自身为 baseline 时加速比为 1）；**主对比表以 `--all` 产出的 `simulation_results.csv` 为准**。

---

## 十一、与结题报告的对接方式

| 工具 | 性质 | 用途 |
|---|---|---|
| [estimate_prefetch_gain.py](../analysis/estimate_prefetch_gain.py) | 解析 / 参数化模型 | 理论趋势、Fig5a 类叙述、`t_hit`/`t_miss` 含义 |
| [simulation/run.py](../simulation/run.py) | Trace 驱动仿真 | 真实访问序列上的总代价、E0–E3、敏感性 |

结题「延迟分析」建议顺序：

1. first-touch 与 `E[T]` 一阶模型（引用解析脚本与 Fig5a）；  
2. 说明 Mode A 伪块与假设局限（第二节、第三节）；  
3. 给出 E0 vs E3 的 `simulation_results.csv` 摘要 + `sensitivity_table.csv`；  
4. 声明仿真为**上界取向**、未计预取 I/O 与并行。

---

## 附录：快速自检清单

- [ ] 已阅读 [simulation/README.md](../simulation/README.md) 并能成功执行 `--all --max-blocks 20`
- [ ] 结题中写明 **Mode A 伪块**与 **`skip_empty_slots` 子集口径**
- [ ] `evm_model_hybrid_v1.pkl` 路径正确且可被 `joblib.load`
- [ ] `--all` 输出后 `sanity_check` 三项为 ✓
- [ ] 报告中注明：仿真**不**包含预取异步延迟与预取错误带来的额外 I/O；结论为 trace 意义下的 first-touch 收益评估

---

*计划书版本：v2.0（2026-04-22）*  
*v2.0：与 `simulation/` 实现及 README 对齐；引入 Mode A/B、`skip_empty_slots` 口径、`run_simulation` 架构、自检与 CLI 修订。*
