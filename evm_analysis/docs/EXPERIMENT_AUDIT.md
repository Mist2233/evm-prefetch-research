# `evm_analysis/` 实验代码审计报告

> 撰写日期：2026-07-07
> 目的：梳理代码现状与论文需求的对应关系，识别过时命名、缺失实验和冗余代码

---

## 一、整体目录概览

```
evm_analysis/
├── simulation/    ← 仿真平台，论文 Evaluation 核心
├── modeling/      ← 模型训练（早期 + hybrid 混合）
├── analysis/      ← 数据分析脚本（部分过时）
├── viz/           ← 可视化（论文图 + 仿真图 + 专利图）
├── docs/          ← 开发文档（含阶段 A/B 实验记录）
├── figures/       ← 输出图片 + 实验数据
│   ├── data/          ← CSV 实验结果
│   ├── mid-figures/   ← 早期论文 Fig1-5（不再使用）
│   ├── sim-figures/   ← 仿真辅助图（S1-S4）
│   └── patent/        ← 专利申请图
├── models/        ← 训练好的模型文件
└── evm-decision-tree-data.xlsx  ← 早期指标记录
```

---

## 二、各模块详细审计

### 2.1 `simulation/` — 仿真平台 ← 论文核心用

| 文件 | 功能 | 论文需要？ | 状态 |
|------|------|-----------|------|
| `run.py` | CLI 入口，E0-E5 实验 + sensitivity + alpha sweep + offline delta | ✅ 核心 | **命名过时** |
| `prefetch_api.py` | 5 种预取器实现 | ✅ 核心 | **命名过时** |
| `offline_delta.py` | 离线增量管道（论文 Augmented 实验的关键） | ✅ 核心 | 基本 OK |
| `cache_sim.py` | 缓存仿真引擎 | ✅ 核心 | OK |
| `metric_log.py` | 指标收集与聚合 | ✅ 核心 | OK |
| `prefetch_executor.py` | 异步预取时序模拟 | ⚠️ 备用 | OK（Limitation 章节提到） |
| `data_loader.py` | 数据加载（pseudo/real block） | ✅ 使用 | OK |
| `README.md` | 实验说明 | — | **内容过时** |

#### 命名问题（严重）

| 代码中现用名 | 论文标准名 | 出现位置 |
|-------------|-----------|---------|
| `fast_path_dict` | `online hash table` / `pattern key dictionary` | prefetch_api.py（line 62, 98, 191, 215, 263, 315）、offline_delta.py（line 88, 104, 186, 297, 328） |
| `rule` (prefetcher name) | `Online Hash Table` / `E2` | prefetch_api.py（line 58）、run.py（line 553, 812） |
| `hybrid` (prefetcher name) | N/A（论文中不直接评估） | prefetch_api.py（line 72）、run.py（line 553, 813） |
| `rule_base` | `Online Hash Table` | offline_delta.py（line 360, 370, 410）、PHASE_B_OFFLINE_DELTA.md |
| `rule_plus_delta` | `Augmented (Offline-Enhanced)` | offline_delta.py（line 365, 381, 410）、PHASE_B_OFFLINE_DELTA.md |
| `Window A / Window B` | `training window / evaluation window` | offline_delta.py（line 62-80）、PHASE_B_OFFLINE_DELTA.md |
| `rule_miss` | `hash table miss` | offline_delta.py（line 101, 104） |
| `slow_path` | `offline path` | prefetch_api.py（line 195, 213） |
| `hybrid_gated` | 论文中不存在 | prefetch_api.py（line 204） |

#### 设计问题

**`HybridPrefetcher` 的角色混淆。** 当前 `hybrid` 预取器的行为是：
- fast path 命中 → 直接返回
- fast path 未命中 → 跑 LightGBM 推理

在论文中，这个预取器被用于两个不同目的：
1. 作为 E3 "Online ML" 实验（证明在线 ML 不可行）— **但 E3 实验数据只有 200 txs，太小**
2. 作为 offline delta pipeline 的"候选生成引擎"（对 Window A 的 rule_miss 交易预测）— **这是真正用途**

论文的 Main Results 比较的是 `rule` 与 `rule_plus_delta`（两者都是 RuleBasePrefetcher，区别在字典内容）。所以 `hybrid` 不是被评估的对象，而是生成增量的工具。

---

### 2.2 `modeling/` — 模型训练

| 文件 | 功能 | 论文需要？ | 状态 |
|------|------|-----------|------|
| `train_hybrid.py` | 训练 hybrid 模型（fast_path_dict + LightGBM） | ✅ **核心模型** | **命名过时** |
| `train_light_gbm.py` | 纯 LightGBM 多标签分类（不同 K 值） | ⚠️ 早期探索 | 可清理 |
| `train.py` | 纯 DecisionTree 多标签分类（不同 K 值） | ⚠️ 早期探索 | 可清理 |
| `load_paper_metrics.py` | 从 xlsx 加载指标 | ❌ 不再需要 | 可清理 |
| `export_go_model.py` | 导出 Go 代码 | ❌ 专利相关 | 保留但非论文用 |

**`train_hybrid.py` 的命名问题：**
- `FAST_PATH_THRESHOLD` → `UNION_SIZE_THRESHOLD`
- `fast_path` / `slow_path` → `online_path` / `offline_path`
- `calc_metrics` 中的 recall/precision 是**集合交并口径**，与仿真侧**块级 first-touch 口径**不同——论文当前用的是仿真口径

---

### 2.3 `analysis/` — 分析脚本

| 文件 | 功能 | 论文需要？ | 状态 |
|------|------|-----------|------|
| `slot_distribution_analysis.py` | union size 分布分析 | ⚠️ 图 CDF 数据源 | 命名 OK |
| `topk_slot_coverage.py` | Top-K 覆盖率 | ❌ 早期探索，论文不再用 | 可清理 |
| `sweep_hybrid_threshold.py` | 阈值扫描生成 Pareto | ❌ 早期探索，论文不再用 | 可清理 |
| `estimate_prefetch_gain.py` | 延迟估计解析模型 | ❌ 早期探索 | 可清理 |
| `benchmark_inference_latency.py` | 推理延迟微基准 | ⚠️ 备用（Introduction 的 α 分析可能用到） | 保留 |

**注意**：这些脚本大多使用 `sklearn.model_selection.train_test_split`（随机切分），而不是论文当前使用的时间序列切分（chronological split by block number）。指标口径也不同。

---

### 2.4 `viz/` — 可视化

| 文件 | 功能 | 论文需要？ | 状态 |
|------|------|-----------|------|
| `plot_figures.py` | 生成 Fig1-5（早期论文图） | ❌ 不再需要 | 可清理 |
| `plot_sim_figures.py` | 生成仿真图（S1: alpha, S2: delta对比） | ⚠️ 论文 Fig alpha + Fig 5/delta | 保留 |
| `plot_patent_figures.py` | 生成专利申请图 | ❌ 专利用 | 保留但非论文 |

---

### 2.5 模型文件（`models/`）

| 文件 | 用途 | 论文使用？ |
|------|------|-----------|
| `evm_model_hybrid_v1.pkl` | K=1000, fast_path_dict + LightGBM | ✅ **主模型** |
| `evm_model_k1000.pkl` 等 | K 值变体 | ⚠️ 备用 |
| `evm_model_lgbm_*.pkl` | 纯 LightGBM（无 fast_path_dict） | ❌ 不需要 |
| `evm_model_k*_to_selector*.pkl` | 不同特征组合 | ⚠️ 消融实验备用 |

---

## 三、论文需要但缺少的实验数据

### 3.1 ❌ Scaling 数据（2K/10K/94K）无 CSV

论文 Table scaling 声称的数据：
| 规模 | Recall 提升 | Cost 降幅 |
|------|-----------|----------|
| 2K txs | +27.4% | −7.8% |
| 10K txs | +35.7% | −10.9% |
| 94K txs | +40.2% | −11.3% |

这些数据**只在 `docs/PHASE_B_OFFLINE_DELTA.md` 中出现过**，没有任何 CSV 文件记录。需要找到当时的运行记录或重跑。

### 3.2 ⚠️ Sensitivity 分析跑错了数据和预取器

当前的 `sensitivity_table.csv`：
- 比较的是 `none` vs `hybrid`（不是 `rule_base` vs `rule_plus_delta`）
- 只跑了 586 笔交易（2 个块）
- speedup 1.3313x 与主结果 1.1274x 不匹配

**论文需要**：在 Window B (28,757 txs) 上比较 `rule_base` vs `rule_plus_delta` 的 sensitivity。

### 3.3 ⚠️ E0-E3 全量对比不存在

`simulation_results.csv` 只有 200 txs。论文 Ablation Study 提到 E0/E1/E2/E3 但没有给出全量数据。如果用全量数据跑 E0/E1/E2/rule_plus_delta，效果会更有说服力。

---

## 四、论文当前 Evaluation 实验表格建议

根据代码实际，建议 Evaluation 的实验设计改为：

| 实验 | 预取器实现 | 字典 | 用途 |
|------|-----------|------|------|
| E0 | `NoPrefetcher` | — | 无预取基线 |
| E1 | `OraclePrefetcher` | — | 理论上界 |
| E2 | `RuleBasePrefetcher` | `fast_path_dict`（原始） | 纯 hash table |
| Augmented | `RuleBasePrefetcher` | 原始 + 离线增量 | **本文方法** |

**删除 E3**：α 分析（Introduction）已证明在线 ML 不可行。

**Augmented 和 E2 使用相同的 `RuleBasePrefetcher`，差异仅在字典是否经过离线增强。** 这需要在论文中明确说明，表格中可以用"字典来源"列来体现。

---

## 五、需要命名重构的清单

### 代码内（影响功能）

| 当前名 | 建议名 | 涉及文件 |
|-------|--------|---------|
| `fast_path_dict` | `pattern_key_dict` 或 `online_table` | `prefetch_api.py`, `offline_delta.py`, `train_hybrid.py` |
| `FAST_PATH_THRESHOLD` | `UNION_SIZE_THRESHOLD` | `train_hybrid.py`, `slot_distribution_analysis.py` |
| `RuleBasePrefetcher.name = "rule"` | `"online_hash_table"` 或保留 `"rule"` 但文档说明 | `prefetch_api.py` |
| `rule_base` (offline_delta.py) | `online_hash_table` | `offline_delta.py` |
| `rule_plus_delta` (offline_delta.py) | `augmented` | `offline_delta.py` |
| `HybridPrefetcher` 注释中的 "E3" | 改为描述性注释 | `prefetch_api.py` |
| 代码注释中的 `Window A/B` | `training_window / eval_window` | `offline_delta.py` 注释 |

### 文档内（不影响功能）

| 当前名 | 建议名 | 涉及文件 |
|-------|--------|---------|
| `Window A/B` | `training/evaluation window` | 所有 `.md` 文档 |
| `rule_base / rule_plus_delta` | 论文对应名 | `PHASE_B_OFFLINE_DELTA.md` |
| `fast_path / slow_path` | `online path / offline path` | `SIMULATION_PLATFORM_PLAN.md` |
| `Phase A / Phase B` 阶段名称 | 改为论文术语 | `docs/*.md` |

---

## 六、数据口径不一致问题

### 6.1 仿真 recall vs 训练 recall

| 口径 | 定义 | 来源 |
|------|------|------|
| **仿真 recall**（论文使用） | `miss_prevented / would_be_miss` 块级 first-touch | `metric_log.py` |
| **训练 recall**（早期脚本） | `|predicted ∩ actual| / |actual|` per-tx 集合交并 | `train_hybrid.py` 的 `calc_metrics` |

两者数值不可直接比较。论文当前使用的是仿真口径，与 `rule_delta_eval.csv` 一致。

### 6.2 Random split vs Chronological split

- 早期 `analysis/` 和 `modeling/` 脚本使用 `train_test_split(random_state=42)`
- 论文当前使用按 block_number 的时间序列切分（70/30）
- 前者会泄露未来信息，后者才是正确的评估方式

---

## 七、建议的重构优先级

### P0 — 论文必须（不改会影响审稿）

1. **重构实验表格**：删除 E3、明确 Augmented 和 E2 使用同一预取器
2. **补 Scaling 数据**：找到或重跑 2K/10K 截断实验，导出 CSV
3. **重跑 Sensitivity**：在 Window B 上比较 `rule_base` vs `rule_plus_delta`

### P1 — 命名统一（消除审稿人困惑）

4. **代码内 `fast_path_dict` 改名** → `pattern_key_dict` 或 `online_table`
5. **`rule_base` / `rule_plus_delta` 改名** → `online_hash_table` / `augmented`
6. **CLI 参数 `--prefetcher rule` 说明更新**
7. **`Window A/B` → `training/evaluation window`**

### P2 — 清理（减少维护负担）

8. 删除 `analysis/topk_slot_coverage.py`、`sweep_hybrid_threshold.py`、`estimate_prefetch_gain.py`（如需保留请在文档说明用途）
9. 清理 `models/` 下多余的 22 个 pkl 文件（只用 hybrid_v1 即可）
10. 清理 `figures/mid-figures/`（论文不再使用）

### P3 — 文档更新

11. 更新 `simulation/README.md` 中的术语
12. 更新 `SIMULATION_PLATFORM_PLAN.md` 中的术语
13. 删除或归档 `RECENT_ISSUES_SUMMARY.md`（历史记录）

---

## 八、各个 CSV 文件与论文的对应关系

| CSV 文件 | 论文中使用？ | 数据集大小 | 备注 |
|---------|-----------|-----------|------|
| `rule_delta_eval.csv` | ✅ Table 2（Main Results） | Window B, 28,757 txs | **可靠** |
| `offline_delta_stats.csv` | ✅ 文中提及 delta 统计 | 全量 94,463 txs | **可靠** |
| `sensitivity_table.csv` | ⚠️ 当前 Paper Table sensitivity | 586 txs ⛔ | **需重跑** |
| `simulation_results.csv` | ⚠️ Ablation Study 引用 | 200 txs ⛔ | **太小，不能当结论** |
| `alpha_sweep_overlap.csv` | ✅ Introduction Fig alpha | 500 txs | OK 作为趋势 |
| `sim_none.csv` | ❌ | 586 txs | 废弃 |
| `sim_hybrid.csv` | ❌ | 87 txs | 废弃 |
| `sim_rule.csv` | ❌ | 1 tx | 废弃 |
| `hybrid_pareto.csv` | ❌ 早期探索 | — | 可清理 |
| `mode_compare.csv` | ❌ | — | 可清理 |
| `hybrid_gated_break_even*.csv` | ❌ | — | 可清理 |
| `figure1_train_union_keys.csv` | ⚠️ CDF 图数据源 | training set | 保留 |
| `figure3_topk_coverage.csv` | ❌ 早期 | — | 可清理 |
| `figure5_inference_latency.csv` | ❌ 早期 | — | 可清理 |
| `metrics_figure2_merged.csv` | ❌ 早期 | — | 可清理 |
| `parallel_prefetch_sensitivity.csv` | ❌ 论文未使用 | — | 可清理 |
