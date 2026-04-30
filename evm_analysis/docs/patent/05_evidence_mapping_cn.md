# 实施例证据映射清单（CSV -> 专利段落）

> 用途：避免“有方案无证据”，把现有实验产物直接映射到交底书实施例段落。

---

## 一、主证据文件与用途

| 文件 | 用途 | 建议写入章节 |
|---|---|---|
| `figures/data/simulation_results.csv` | E0/E1/E2/E3 主对比，证明方案有效性 | 实施例四（效果验证） |
| `figures/data/parallel_prefetch_sensitivity.csv` | 并行及时性与收益关系，证明关键机制 | 实施例二（并行时序） |
| `figures/data/sensitivity_table.csv` | 参数扰动鲁棒性 | 实施例四（鲁棒性） |

---

## 二、字段到段落的映射模板

### 2.1 `simulation_results.csv`

| CSV字段 | 含义 | 建议对应段落 | 示例写法 |
|---|---|---|---|
| `prefetcher` | 方案标识（none/rule/hybrid/oracle） | 实施例四-对照组定义 | “设置 none 作为基线，rule 与 hybrid 为对照方案，oracle 为理论上界。” |
| `data_mode` | 重放模式（real_block/pseudo_block） | 实施例三-重放模式 | “本实施例在 real_block 模式下执行，以真实块顺序进行重放。” |
| `n_would_be_miss` | 无预取应有 miss 总数 | 实施例四-基线说明 | “无预取条件下应有 first-touch miss 为……次。” |
| `n_miss_prevented` | 被预取防止的 miss 数 | 实施例四-效果指标 | “hybrid 防止 miss 数显著高于 rule。” |
| `recall` | miss 覆盖率 | 实施例四-效果指标 | “hybrid 的覆盖率高于 rule，说明慢路径补全有效。” |
| `precision` | 预测精度 | 实施例四-效果指标 | “precision 与 recall 结合反映预取冗余水平。” |
| `total_cost_us` | 总代价 | 实施例四-核心结果 | “在相同数据条件下，hybrid 总代价低于 none。” |
| `speedup_vs_baseline` | 相对基线加速比 | 实施例四-核心结论 | “hybrid 相对 none 达到约 1.346x。” |

### 2.2 `parallel_prefetch_sensitivity.csv`

| CSV字段 | 含义 | 建议对应段落 | 示例写法 |
|---|---|---|---|
| `t_prefetch_us` | 单槽预取服务时延 | 实施例二-参数设置 | “设置预取服务时延为……µs。” |
| `prefetch_concurrency` | 并发 worker 数 | 实施例二-调度策略 | “并发度提升可改善及时命中率。” |
| `prefetch_timely_rate` | 及时命中率 | 实施例二-机制验证 | “当时延增加时及时率下降，说明时序约束有效。” |
| `speedup_vs_baseline` | 与基线速度比 | 实施例二-效果关联 | “及时率下降时 speedup 同步下降。” |
| `prefetch_queue_wait_us_total` | 累计排队等待 | 实施例二-队列影响 | “排队等待增大时收益减弱，体现并发瓶颈。” |

### 2.3 `sensitivity_table.csv`

| CSV字段 | 含义 | 建议对应段落 | 示例写法 |
|---|---|---|---|
| `param_label` | 参数组合标签 | 实施例四-鲁棒性设置 | “设置基准、t_miss±20%、t_hit±20%。” |
| `baseline_cost_us` | 基线代价 | 实施例四-对照值 | “基线代价随参数变动呈预期变化。” |
| `hybrid_cost_us` | hybrid 代价 | 实施例四-结果值 | “hybrid 在各参数组下均低于 baseline。” |
| `speedup` | 加速比 | 实施例四-鲁棒性结论 | “speedup 在约 1.33x 附近波动，方向稳定。” |
| `saved_pct` | 节省比例 | 实施例四-鲁棒性结论 | “节省比例约 24.8%~24.96%。” |

---

## 三、当前可直接引用的数字（阶段性）

### 3.1 real_block 主对比（`max-txs=200`）

- none：`total_cost_us=8997.00`
- rule：`total_cost_us=7399.14`，`speedup=1.2160x`
- hybrid：`total_cost_us=6683.37`，`speedup=1.3462x`
- oracle：`total_cost_us=107.79`，`speedup=83.4679x`

### 3.2 并行敏感性示例（节选）

- `t_prefetch_us=0.5, concurrency=16`：`prefetch_timely_rate=0.8734`, `speedup=1.2780x`
- `t_prefetch_us=4.0, concurrency=1`：`prefetch_timely_rate=0.0349`, `speedup=1.0092x`

### 3.3 参数鲁棒性（±20%）

- `speedup` 区间约：`1.3297x ~ 1.3326x`
- `saved_pct` 区间约：`24.80% ~ 24.96%`

---

## 四、实施例写作边界（必须保留）

1. 标注“阶段性样本规模（例如 max-txs）”；
2. 说明这是 trace-driven 仿真，不直接等价主网端到端；
3. 结果用于证明技术方案可行与趋势稳定，不写绝对性能承诺。
