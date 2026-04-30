# 专利材料口径包（中国发明专利）

## 1. 技术主题与申请边界

- **主题**：一种面向以太坊执行路径的存储预取方法与系统。
- **核心问题**：降低区块内首次存储访问（first-touch miss）导致的高代价访问。
- **核心方案**：规则快路径 + 模型慢路径的混合预取，并以预取完成时间约束判定预取是否真正生效。
- **申请边界**：当前证据来自 trace-driven 仿真平台，结论用于证明方法有效性，不等同于主网端到端性能承诺。

## 2. 术语统一表

| 术语 | 统一定义 | 对应实现/数据 |
|---|---|---|
| first-touch miss | 同一块内某 slot 首次访问，需按 miss 计费 | `simulation/cache_sim.py` |
| cache hit | 同一块内重复访问已就绪 slot，按 hit 计费 | `simulation/cache_sim.py` |
| hybrid prefetch | `(to, selector)` 快路径查表 + 慢路径模型推理 | `simulation/prefetch_api.py` |
| rule prefetch | 仅使用 `fast_path_dict` 查表 | `simulation/prefetch_api.py` |
| oracle prefetch | 直接使用真实访问集合（理论上界） | `simulation/prefetch_api.py` |
| timed prefetch | 显式模拟预取完成时刻；仅在 `finish <= first_access` 时生效 | `simulation/cache_sim.py`, `simulation/prefetch_executor.py` |
| pseudo_block | 按固定窗口切块重放 | `simulation/data_loader.py` |
| real_block | 按 `block_number` 分组，按 `transaction_index` 排序 | `simulation/data_loader.py` |

## 3. 现有证据来源（用于实施例与效果）

- 平台与机制说明：`evm_analysis/simulation/README.md`
- 工程边界与方法论：`evm_analysis/docs/SIMULATION_PLATFORM_PLAN.md`
- 四组对比数据：`evm_analysis/figures/data/simulation_results.csv`
- 并行敏感性数据：`evm_analysis/figures/data/parallel_prefetch_sensitivity.csv`
- 参数鲁棒性数据：`evm_analysis/figures/data/sensitivity_table.csv`

## 4. 阶段性关键数字（可写入“有益效果”草稿）

基于 `simulation_results.csv`（`real_block`, `max-txs=200`）：

- `none` 代价：8997.00 µs
- `rule` 代价：7399.14 µs，`speedup=1.2160x`
- `hybrid` 代价：6683.37 µs，`speedup=1.3462x`
- `oracle` 代价：107.79 µs（理论上界）

基于 `parallel_prefetch_sensitivity.csv`：

- 当 `t_prefetch_us` 增大且并发不足时，`prefetch_timely_rate` 与 `speedup`同步下降；
- 并发度提升可以恢复部分收益，说明“预取是否及时完成”是收益成立的关键条件。

基于 `sensitivity_table.csv`：

- 在 `t_hit`/`t_miss` ±20% 扰动下，`speedup` 稳定在约 `1.33x` 附近，结论方向稳定。

## 5. 专利文本中的边界声明（必须保留）

以下表述建议在交底书“有益效果/实施例说明”中出现：

1. 该效果基于离线 trace 重放仿真，不包含真实客户端端到端 I/O 与线程调度抖动。
2. 仿真用于验证方法机制与改进方向，不直接替代生产环境绝对性能承诺。
3. 并行预取效果依赖于预取完成时间与首次访问时间窗口关系，应通过参数或系统资源配置保障及时性。

## 6. 发明点草案（一句话版本）

一种面向区块链状态访问的混合预取方法：基于交易调用键进行规则快路径与模型慢路径联合预测，并通过预取完成时间不晚于首次访问时间的约束判定有效命中，以降低区块内首次存储访问代价。
