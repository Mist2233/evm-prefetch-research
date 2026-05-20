# 图表指标定义（论文 / 幻灯片）

## Fig 1a
- 含义：在训练集划分上，针对 `(to, selector)` 规则的 union size ECDF。
- 说明：
  - **Unweighted**：每条规则权重相同。
  - **Weighted**：按交易加权的 CDF（每笔交易继承其对应规则的 union size）。
- 来源：`slot_distribution_analysis.py --export-csv`

## Fig 2*
- 含义：来自 `train_light_gbm` / `train` 的标签矩阵指标（`calculate_metrics`）：
  - Top-K Recall
  - Total Recall
  - Precision
  - Exact Match
- 注意：该组指标**不能**与 Hybrid 的基于集合（set-based）指标直接对比。

## Fig 3a
- 含义：Top-K 访问质量覆盖率（access-mass coverage）。
- 定义：所有 slot 访问中，slot 身份落在全局最频繁 K 个 slot 内的比例。
- 来源：`topk_slot_coverage.py --export-csv`

## Fig 4a
- 含义：Hybrid 的整体 Recall / Precision（使用 `train_hybrid.calc_metrics`，基于集合交集计算）。
- 说明：慢路径 LightGBM 模型固定为一次训练结果，仅变化 `FAST_PATH_THRESHOLD` 与 `fast_path_dict`。
- 来源：`sweep_hybrid_threshold.py`

## Fig 5a
- 含义：每笔交易 Python 推理时间中位数（离线 sklearn 口径）。
- 注意：该结果**不是** Erigon 生产环境口径。
- 来源：`benchmark_inference_latency.py`（始终导出 CSV）

## 训练 / 测试设置
- 在适用场景下：`random_state=42`，`test_size=0.2`。
