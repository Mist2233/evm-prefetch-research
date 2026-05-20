# Hybrid 近期问题与下一步详细计划

## 1. 当前状态（结论先行）

- `hybrid` 在“存储代价口径”上优于 `rule`，但在“端到端净收益口径”下仍为负。
- GPU 和批处理已显著降本，但尚不足以使在线 slow-path 变成主路径。
- 更可行路线：**在线以 rule 为主，slow-path 转离线后台补充 fast-path**。

---

## 2. 已确认问题与根因

### 2.1 结果落盘认知偏差
- **问题**：日志显示已处理大量区块，但汇总 CSV 未更新。
- **根因**：`--all` 在全部组别结束后才统一写 `simulation_results.csv`。
- **影响**：中途退出会造成“日志有进度、结果没更新”的错觉。

### 2.2 HYBRID 阶段运行极慢
- **问题**：HYBRID 阶段耗时远超其他组。
- **根因**：slow-path 模型推理 + Python 数据管线开销（编码、构造、解码）。
- **影响**：在线模式端到端收益被推理开销吞噬。

### 2.3 指标口径不完整
- **问题**：只看 `cost` 会误判优化有效。
- **根因**：`cost` 仅反映 slot hit/miss 代价，不含预测器真实开销。
- **影响**：需要用 `predict_overhead_us`、`net_gain_us`、`e2e_elapsed_s` 联合判断。

### 2.4 GPU 不是单点解法
- **问题**：GPU 可加速但没有数量级逆转。
- **根因**：瓶颈不仅是模型算力，还包括数据准备与 Python 调度。
- **影响**：必须结合架构策略（在线/离线职责分离）。

---

## 3. 已完成改造（可复现）

### 3.1 指标升级
- 已新增并落盘：
  - `predict_overhead_us`
  - `e2e_elapsed_s`
  - `e2e_cost_proxy_us`
  - `speedup_net_vs_baseline`
  - `storage_gain_us`
  - `net_gain_us`

### 3.2 运行策略
- 已支持：
  - `hybrid_gated`
  - `--hybrid-gate-rate`
  - `--use-gpu`
  - `--gpu-device-id`
  - `--slow-batch-size`

### 3.3 性能改造
- slow-path 分片批处理已接入，逐条模式到批处理有显著改善。

---

## 4. 今日收尾后的主执行计划

> 目标：解决“在线 slow-path 净收益为负”并给出可论证的新路径。

## 阶段 A：执行时间覆盖模型（Overlap）

### A1. 要解决的问题
- 当前评估默认预测开销全额计入，没有考虑“交易执行期间可并行预取”的覆盖效应。

### A2. 方案
- 增加 `alpha` 参数表示可覆盖比例：`alpha ∈ [0,1]`。
- 增加执行时间代理：`tx_exec_us_total`（先常数代理，后续替换实测）。
- 计算：
  - `effective_pred_overhead_us = max(0, predict_overhead_us - alpha * tx_exec_us_total)`
  - `net_gain_with_overlap_us = storage_gain_us - effective_pred_overhead_us`

### A3. 产出
- 新 CSV 字段：
  - `tx_exec_us_total`
  - `effective_pred_overhead_us`
  - `net_gain_with_overlap_us`
  - `speedup_overlap_vs_baseline`
- 新扫描结果：`alpha_sweep_overlap.csv`

### A4. 验收标准
- 能回答“在什么 `alpha` 区间内 online hybrid 才可能转正”。

---

## 阶段 B：slow-path 离线补充 fast-path

### B1. 要解决的问题
- 在线 slow-path 代价高，难以直接使用。

### B2. 方案（职责分离）
- 在线：仅 `rule` 服务。
- 离线：`hybrid` 对 `rule_miss` 样本生成候选增量。
- 更新策略（最小可行）：
  - `min_support`（最小出现次数）
  - `max_new_slots_per_key`
  - 可选 `ttl` / 回滚版本

### B3. 实验设计（避免泄漏）
- 时间窗口切分：
  - Window A：生成增量规则
  - Window B：评估更新后 rule
- 对比：
  - `rule_base`
  - `rule_plus_delta`

### B4. 产出
- `offline_delta_stats.csv`（新增键/槽统计）
- `rule_delta_eval.csv`（补充前后效果）

### B5. 验收标准
- 至少一项核心指标有稳定提升（如 `recall` 或 `total_cost_us`），且不显著恶化其他指标。

---

## 阶段 C：汇报与专利叙事固化

### C1. 统一表述
- 在线路径：低延迟 rule。
- 离线路径：hybrid 增量学习与规则编译。
- 可控参数：`alpha`、`gate_rate`、`min_support`、`max_new_slots_per_key`。

### C2. 必交付材料
- 一页“问题-证据-行动-结果”摘要。
- 两张图：
  - `alpha` 覆盖敏感性图
  - 离线补充前后对比图

---

## 5. 风险与对策

- **风险 1**：执行时间代理偏差大。  
  **对策**：先做区间扫描，不做单点结论；后续替换为实测代理。

- **风险 2**：离线补充引入噪声，precision 下滑。  
  **对策**：提高 `min_support`，限制每键新增槽位上限，保留回滚。

- **风险 3**：结论被质疑“只调参不创新”。  
  **对策**：强调架构创新在“在线/离线职责分离 + 开销感知评估 + 动态规则补充闭环”。

---

## 6. 执行顺序与里程碑

1. **先做阶段 A**：完成 `alpha` 口径与扫描，明确在线可行边界。  
2. **再做阶段 B**：实现离线补充闭环并验证有效性。  
3. **最后做阶段 C**：收敛成可汇报、可答辩、可写专利的统一叙事。  

---

## 7. 本计划的最终判断标准

- 若 `alpha` 覆盖后 online hybrid 仍难转正：以“在线 rule + 离线 hybrid 增量”作为主路线。  
- 若在合理 `alpha` 下可转正：保留在线 gated hybrid 作为可选增强模式。  
- 无论哪条路线，都以“净收益口径”作为唯一判定标准。  

