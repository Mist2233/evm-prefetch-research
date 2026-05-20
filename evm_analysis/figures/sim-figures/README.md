4 张图表全部生成，大小正常。概括每张图的内容：

| 图                                  | 内容                                                                                                | 核心信息                                                                 |
| ----------------------------------- | --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **S1** `fig_s1_alpha_sweep.png`     | Alpha 覆盖敏感性，双 Y 轴：net_gain（红） + effective_overhead（蓝） vs alpha                       | alpha=1.0 时净收益仍为负，覆盖不足以消化 overhead                        |
| **S2** `fig_s2_rule_delta.png`      | 四面板柱状图：rule_base vs rule_+delta 在 Recall / Precision / Miss Prevented / Total Cost 上的对比 | Recall +35.7%，Cost −10.9%，Precision 轻微下降                           |
| **S3** `fig_s3_full_comparison.png` | 全量预取器 Recall & Speedup 对比（none/rule/hybrid/hybrid_gated/rule_+delta）                       | rule_+delta 在 Recall 和 Speedup 上均优于 rule，接近 hybrid 但零推理开销 |
| **S4** `fig_s4_delta_overview.png`  | 三面板：数据切分饼图 + dict 增长 + delta 增量明细（新键/新 slot/均值）                              | 直观展示管线规模和增量效果                                               |

生成脚本在 `viz/plot_sim_figures.py`，用法：`python viz/plot_sim_figures.py --all`。