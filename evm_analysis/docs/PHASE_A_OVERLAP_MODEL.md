# 阶段 A：执行时间覆盖模型（alpha overlap）

## 目标

解决"在线 slow-path 预测开销被全额计入关键路径"的评估偏差。真实系统中，交易执行可与预测计算并行，本次模拟的仿真执行时间可视为交易在 Evm 中的近似真实执行时间。增加 `alpha` 参数量化覆盖比例，回答：**在多大覆盖比例下 online hybrid 才能转正**。

## 完成事项

### 新增字段与参数

| 位置 | 新增内容 |
|---|---|
| `TxResult` | `tx_exec_us` — 单笔交易执行时间代理（µs） |
| `CacheSim` | `--tx-exec-us-per-slot` / `--tx-exec-us-base` — 控制代理计算 |
| `RunSummary` | `tx_exec_us_total` — 全量执行时间代理累加 |

每笔交易执行时间代理计算：`tx_exec_us = len(accessed_slots) * tx_exec_us_per_slot + tx_exec_us_base`，默认均为 0，向后兼容。

### 覆盖感知指标（RunSummary 新增方法）

```
effective_pred_overhead_us(alpha) = max(0, predict_overhead_us - alpha * tx_exec_us_total)
net_gain_with_overlap_us(baseline, alpha) = storage_gain_us - effective_pred_overhead_us(alpha)
speedup_overlap_vs(baseline, alpha) = baseline.e2e / (total_cost_us + effective_overhead)
```

### CLI 新增

- `--alpha-sweep` — 启动 alpha 覆盖敏感性分析
- `--alphas` — 覆盖比例列表，默认 `[0.0, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0]`
- `--tx-exec-us-per-slot` / `--tx-exec-us-base` — 执行时间代理参数

运行示例：
```bash
python -m simulation.run --alpha-sweep \
  --data-mode real_block --max-txs 500 \
  --model models/evm_model_hybrid_v1.pkl \
  --tx-exec-us-per-slot 100 \
  --output-dir figures/data
```

输出 `figures/data/alpha_sweep_overlap.csv`，字段包括 `alpha`、`tx_exec_us_total`、`raw_pred_overhead_us`、`effective_pred_overhead_us`、`storage_gain_us`、`net_gain_us`、`speedup_overlap_vs_baseline`、`net_positive`。

### 实测数据（`--max-txs 500`, `--tx-exec-us-per-slot 100`）

采样 500 笔交易，`tx_exec_us_total = 748,600 µs (0.75s)`，`storage_gain_us = 5,366.79 µs (0.005s)`：

| alpha | effective_overhead (s) | net_gain (s) | speedup |
|------:|------:|------:|------:|
| 0.0 | 15.53 | −15.52 | 0.0012x |
| 0.2 | 15.38 | −15.37 | 0.0012x |
| 0.4 | 15.23 | −15.22 | 0.0012x |
| 0.6 | 15.08 | −15.07 | 0.0012x |
| 0.8 | 14.93 | −14.92 | 0.0012x |
| 0.95 | 14.81 | −14.81 | 0.0012x |
| 1.0 | 14.78 | −14.77 | 0.0012x |

即便 alpha=1.0，覆盖掉的预测开销仅 0.75s，而总预测开销为 15.53s，净收益仍为 −14.77s。

### 全量推算（`--max-txs 200`, 17,777 笔交易，`--tx-exec-us-per-slot 100`）

全量下 `predict_overhead_us = 504.38s`，`storage_gain_us = 0.21s`，`n_true_accesses = 279,187`，推算 `tx_exec_us_total ≈ 27.9s`：

| alpha | effective_overhead (s) | net_gain (s) |
|------:|------:|------:|
| 0.0 | 504.38 | −504.17 |
| 0.5 | 490.43 | −490.22 |
| 1.0 | 476.48 | −476.27 |

即使 alpha=1.0，执行时间覆盖最多抵消 27.9s，远不足以消化 504s 的预测开销。

### 初步结论

HYBRID 的 slow-path 预测开销（百秒级）与执行时间代理（十秒级）之间存在约 **18 倍** 量级差距。**仅靠执行时间覆盖不足以让 online slow-path 转正**，需推进阶段 B（slow-path 离线补充 fast-path）。

## 涉及文件

- `simulation/cache_sim.py` — TxResult / CacheSim 扩展
- `simulation/metric_log.py` — RunSummary 累加与覆盖感知方法
- `simulation/run.py` — CLI 参数、`run_alpha_sweep()` 函数、dispatch
