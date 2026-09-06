# 阶段 B：Slow-path 离线补充 Fast-path

## 目标

Phase A 已证实 online hybrid slow-path 预测开销（百秒级）与执行时间（十秒级）之间存在 ~18x 量级差距，即使 100% 覆盖也无法转正。Phase B 切换到**在线/离线职责分离**路线：在线只用 `rule`（哈希查表，O(1)），hybrid slow-path 转为离线任务，为 rule_miss 的 `(to, selector)` 键生成增量规则，补充到 fast_path_dict 中。

核心思路：hybrid 推理虽慢，但可以在离线窗口（Window A）上完成，产出的增量规则写入 fast_path_dict 后，在线路径（Window B）直接用查表服务，无需承担推理开销。

## 完成事项

### 新增文件：`simulation/offline_delta.py`

管线 5 步：

```
[1] 加载模型 → [2] 按 block_number 切分 Window A/B
       → [3] Window A: hybrid 预测 rule_miss 交易，累积正确 slot 计数
       → [4] 按 min_support + max_new_slots_per_key 过滤，合并到 fast_path_dict
       → [5] Window B: rule_base vs rule_plus_delta 仿真对比
```

核心函数：

| 函数 | 职责 |
|---|---|
| `split_by_block(path, ratio, max_txs)` | 按 block_number 分组，前 ratio 块归 A，其余归 B |
| `generate_candidates(txs, hybrid, fast_path_dict)` | 对 rule_miss 交易取 `predicted ∩ accessed_slots`，按键累加计数 |
| `filter_candidates(candidates, min_support, max_new)` | slot 正确次数 ≥ min_support，每键 ≤ max_new 个 |
| `merge_delta(original, delta)` | 合并到新 dict，已有键追加去重，新键新建 |
| `run_offline_delta_pipeline(...)` | 主流程，输出两个 CSV |

### CLI 新增（`simulation/run.py`）

- `--offline-delta` — 启动离线增量管道
- `--delta-split-ratio` — Window A/B 切分比例（默认 0.7）
- `--delta-min-support` — 候选 slot 最小支持次数（默认 2）
- `--delta-max-slots-per-key` — 每键最多新增 slot 数（默认不限制）

运行示例：
```bash
python -m simulation.run --offline-delta \
  --data-mode real_block \
  --model models/evm_model_hybrid_v1.pkl \
  --delta-split-ratio 0.7 --delta-min-support 2 \
  --delta-max-slots-per-key 20 \
  --output-dir figures/data
```

### 输出文件

| 文件 | 内容 |
|---|---|
| `figures/data/offline_delta_stats.csv` | 窗口统计、新增键/槽数、平均增量 |
| `figures/data/rule_delta_eval.csv` | Window B 上 rule_base vs rule_plus_delta 对比 |

## 实测数据

### 抽样验证（`--max-txs 10000`）

| 指标 | rule_base | rule_plus_delta | 变化 |
|---|---:|---:|---:|
| Recall | 0.2376 | 0.3225 | **+0.0848 (+35.7%)** |
| Precision | 0.1887 | 0.1637 | −0.0250 |
| Total Cost (µs) | 79,023 | 70,380 | **−8,643 (−10.9%)** |
| Miss Prevented | 8,151 | 11,061 | +2,910 (+35.7%) |

### 全量实验（不设 `--max-txs`，耗时 ~16 分钟）

**数据规模**：999 个区块，共 94,463 笔有效交易（过滤空 slot 后）。

#### 窗口切分

| | 块数 | 交易数 |
|---|---|---|
| Window A | 699 | 65,706 |
| Window B | 300 | 28,757 |

Window A 中 rule_miss 占比 66.4%（43,660/65,706）。

#### 增量生成

| 指标 | 数值 |
|---|---|
| 候选键数 | 285 |
| 候选 slot 实例 | 201,770 |
| 过滤后保留键数 | 253 |
| 过滤后保留 slot 数 | 2,641 |
| 过滤丢弃 slot 数 | 5,819（`max_new_slots_per_key=20` 截断） |
| 平均每键新增 slot | 10.4 |
| fast_path_dict 变化 | 8,233 → 8,486 键 |

#### Window B 评估对比

| 指标 | rule_base | rule_plus_delta | 变化 |
|---|---:|---:|---:|
| Recall | 0.2223 | 0.3117 | **+0.0894 (+40.2%)** |
| Precision | 0.1888 | 0.1648 | −0.0240 (−12.7%) |
| Total Cost (µs) | 880,983 | 781,405 | **−99,578 (−11.3%)** |
| Miss Prevented | 83,393 | 116,921 | +33,528 (+40.2%) |

#### 缩放一致性

| 规模 | 区块数 | Recall 提升 | Cost 降幅 |
|---|---|---|---|
| 2K txs | 23 | +27.4% | −7.8% |
| 10K txs | 115 | +35.7% | −10.9% |
| **全量 94K** | **999** | **+40.2%** | **−11.3%** |

随着规模扩大，Recall 提升和 Cost 降幅均**单调递增**，说明 delta 规则在更大未见区块集上泛化良好，不存在规模稀释效应。

#### 结论

- 全量下 Recall 提升 **+40.2%**、总代价降低 **−11.3%**，效果随规模扩大而增强
- 新增 253 个 `(to, selector)` 键、2,641 个 slot，`max_new_slots_per_key=20` 有效约束增量规模，Precision 仅下降 12.7%
- 离线增量管道在全量数据上验证成立：hybrid 的预测能力可有效"编译"进 fast_path_dict，在线路径零推理开销享受模型收益
- **验收通过**：核心指标显著提升，缩放一致性良好，无指标断崖式恶化

## 涉及文件

- `simulation/offline_delta.py` — 新增，完整离线增量管线
- `simulation/run.py` — CLI 参数 + dispatch
- 复用（无需修改）：`prefetch_api.py`（RuleBasePrefetcher / HybridPrefetcher）、`cache_sim.py`、`metric_log.py`
