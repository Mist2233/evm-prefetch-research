# 代码命名规范（与论文术语对齐）

> 依据：NAS2026.tex + CLAUDE.md + TERMINOLOGY.md
> 原则：代码变量名与论文术语一一对应

---

## 一、核心数据结构映射

| 论文术语 | 代码变量名 | 类型 | 说明 |
|---------|-----------|------|------|
| hash table (indexed by pattern key) | `pattern_table` | `dict[tuple, list[str]]` | `(to, selector)` → storage slot set 的映射 |
| union threshold | `union_threshold` | `int` | 控制哪些 pattern key 直接存入 hash table |
| pattern key | `pattern_key` | `tuple[str, str]` | `(to, selector)` |
| storage slot set | `slot_set` | `set[str]` 或 `list[str]` | 每个 pattern key 关联的槽位集合 |
| candidate set size | `top_k_slots` | `int` | 多标签分类的候选 slot 数 |

---

## 二、实验组命名

| 论文名 | CLI 名 | 类名 | 说明 |
|-------|--------|------|------|
| E0 (No Prefetch) | `none` | `NoPrefetcher` | 不变 |
| E1 (Oracle) | `oracle` | `OraclePrefetcher` | 不变 |
| E2 (Online Hash Table) | `table` (原 `rule`) | `TablePrefetcher` (原 `RuleBasePrefetcher`) | 纯 hash table 查表 |
| — (ML pattern generator) | `ml` (原 `hybrid`) | `MLPrefetcher` (原 `HybridPrefetcher`) | 离线增量生成引擎，论文不直接评估 |
| — (Gated ML) | `ml_gated` (原 `hybrid_gated`) | `MLGatedPrefetcher` (原 `HybridGatedPrefetcher`) | Risk-aware 变体，论文不需要 |

**关键变更：** `rule` → `table`。因为论文中 "rule" 在 Historical Context（static rule tables）中已被废弃，当前统一使用 "hash table" / "pattern key"。

---

## 三、离线增量管道命名

| 旧名 | 新名 | 出现位置 |
|------|------|---------|
| `fast_path_dict` | `pattern_table` | 全文 |
| `rule_base` | `original_table` | `offline_delta.py` 评估变量 |
| `rule_plus_delta` | `augmented_table` | `offline_delta.py` 评估变量 |
| `rule_miss` | `table_miss` | `offline_delta.py` 注释和变量 |
| `Window A` | `training_window` | `offline_delta.py` |
| `Window B` | `eval_window` | `offline_delta.py` |
| `FAST_PATH_THRESHOLD` | `UNION_SIZE_THRESHOLD` | `train_hybrid.py`, `slot_distribution_analysis.py` |

---

## 四、代码注释规范

| 废弃术语 | 替换为 |
|---------|-------|
| fast path | online path |
| slow path | offline path |
| rule (指 hash table 条目) | pattern 或 entry |
| rule key | pattern key |
| hybrid 推理/模型 | classification model 推理 |
| 编译(compile) | 合并(merge) |

---

## 五、其他变量名

| 旧名 | 新名 | 说明 |
|------|------|------|
| `slow_indices` | `offline_indices` | 需离线路径处理的交易索引 |
| `slow_batch_size` | `offline_batch_size` | 离线模型推理批大小 |
| `gate_rate` | `gate_rate` | 保留（仅 ml_gated 使用） |
| `hybrid_gate_rate` | `ml_gate_rate` | CLI 参数名 |

---

## 六、CLI 变更

| 旧参数名 | 新参数名 |
|---------|---------|
| `--prefetcher rule` | `--prefetcher table` |
| `--prefetcher hybrid` | `--prefetcher ml` |
| `--prefetcher hybrid_gated` | `--prefetcher ml_gated` |
| `--hybrid-gate-rate` | `--ml-gate-rate` |
| `--slow-batch-size` | `--offline-batch-size` |
| `--delta-min-support` | (`min_support` 保留，说明改为 `minimum support`) |
| `--delta-max-slots-per-key` | (`max_slots_per_key` 保留) |
