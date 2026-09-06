# NAS 2026 Paper — Split-Path ML-Augmented Prefetching

> IEEE double-column, CCF-C, 8 pages (including references)
> Target: NAS conference (Network, Architecture, and Storage)
> Status: After final detail adjustments (2026-07-08) — 19 issues resolved

---

## Project Structure

```
paper/
  NAS2026.tex              — 主稿件（已大修版）
  NAS2026.bak.tex           — 大修前备份
  figures/                   — 图片文件
    fig1_english.png         — 架构总览图
    fig2_english.png         — 离线管道流程图
    fig3_english.png         — 离线增量效果对比柱状图
    fig4_english.png         — 缩放一致性曲线
    fig_cdf.png              — 规则键并集大小 CDF 分布
    fig_alpha.png            — Alpha 覆盖率分析
  section_1_intro.tex        — 各节独立文件(assembly intermediate)
  section_2_related_work.tex
  section_3_preliminary.tex
  section_4_system_design.tex
  sections_5_6_7.tex
  references/                — 参考文献 PDF
  TERMINOLOGY.md             — 术语规范 v2.0
  academic_writing_guide.md  — 写作准则
  advisor_discussion_cheatsheet.md
evm_analysis/               — 实验代码和数据
```

---

## Paper Structure (7 sections)

| # | Section | Notes |
|---|---------|-------|
| 1 | Introduction | 含 feasibility analysis (alpha sweep) |
| 2 | Related Work | A: EVM Optimization / B: Prefetching / C: Learned Index + Summary |
| 3 | Preliminary | EVM storage model + pattern keys + problem formulation (NEW) |
| 4 | System Design | Online path (hash table) + Offline path (classification model + merge) |
| 5 | Evaluation | Setup + Main Results + Scaling + Sensitivity |
| 6 | Limitation | 5 limitations (NEW) |
| 7 | Conclusion | Summary + results + brief future work + NAS citations |

**Abstract:** ~150 words. Background → problem → method (offline/offline separation) → key results (Recall +40.2%, Cost −11.3%). No em-dashes.

---

## Core Technical Concept

**Split-Path ML-Augmented Prefetching** — online/offline split-path architecture for EVM storage slot prefetching.

- **Online path**: O(1) hash table lookup keyed by `(to, selector)` pattern keys. Hit → return prefetched slots; Miss → return empty. Zero ML inference overhead (~0.23μs/tx).
- **Offline path**: Classification model runs in batch on historical data. Generates incremental patterns → filter by minimum support + per-key slot cap → merge into online hash table. Augmented table still O(1) lookup.

**Key insight**: ML is an OFFLINE COMPILER, not an online predictor. Its output is "compiled" into hash table entries in the same format as the original table.

**Why not online ML**: Alpha analysis proves online ML infeasible. Single inference ~28ms, benefit per prefetch ~3μs. Even at α=1.0 (perfect parallelism): 14.78s overhead vs 0.005s saved — ~3 orders of magnitude gap.

---

## Key Experimental Results

| Metric | Baseline | Augmented | Change |
|--------|----------|-----------|--------|
| Recall | 0.2223 | 0.3117 | **+40.2%** |
| Precision | 0.1888 | 0.1648 | −12.7% |
| Total Cost | 880,983 μs | 781,405 μs | **−11.3%** |
| Speedup | 1.0000× | 1.1274× | **+12.7%** |

**Scaling**: 2K: +26.8% → 10K: +35.7% → 94K: +40.2% (monotonic)
**Sensitivity**: E2 speedup ~1.28×, E3 speedup ~1.44×, stable within ±0.1%
**Delta**: +253 pattern keys, +2,641 slots (avg 10.4/key) from 201,770 candidates
**Dataset**: Ethereum mainnet blocks 20,000,000–20,001,000, 1,001 blocks, 94,463 valid txs. Split 70/30: training window (699 blks, 65,706 txs) / evaluation window (300 blks, 28,757 txs)
**Platform**: Intel Core Ultra 9 285K, 125GB DDR5, 3.6TB NVMe, Ubuntu 22.04, Erigon v2.59

---

## Terminology (MANDATORY)

| Deprecated | Use instead |
|-----------|------------|
| rule key | **pattern key** |
| fast path / slow path | **online path / offline path** |
| compiler | **merge** (not compile) |
| LightGBM / LSTM | **classification model** (in System Design) |
| `(to, selector)` as code | **(to, selector)** as normal text |
| Window A / Window B | **training window / evaluation window** (in Evaluation only) |
| rule_base / rule_plus_delta | **E2 (Hash Table) / E3 (Offline-Enhanced)** |
| rule_miss | **hash table miss** (descriptive) |
| storage slot list | **storage slot set** |
| `\texttt{min\_support}`, `max_new_slots_per_key` | Only in Evaluation, not System Design |

**Other writing rules:**
- NO em-dashes (`---`). Use commas or periods instead.
- NO long/compound sentences. Keep short and direct.
- NO excessive bullet lists — use paragraphs or algorithmic environment.
- First occurrence of any abbreviation: spell out fully (e.g., Cumulative Distribution Function (CDF)).
- Avoid AI-sounding phrases ("delves into", "leverages", "aforementioned").
- Positive results bold in tables, negative results mentioned in text only.
- **No invented terms.** Every term must be either a standard field term or explicitly defined at first use. If a concept can be described with existing terms, do not coin a new one.

---

## Figures

| Label | File | Section | Notes |
|-------|------|---------|-------|
| Fig. 1 | `figures/system_design_architecture.png` | Architecture Overview (§4.1) | 左右两栏布局，蓝灰色系 |
| Fig. 2 | `figures/fig_cdf.png` | CDF of union size (§4.2.2) | 重绘配色，三角/方形标记 |
| Fig. 3 | `figures/system_design_pipeline.png` | Pipeline flow (§4.3) | 水平五步骤流水线 |
| Fig. 4 | `figures/fig_alpha.png` | Alpha sweep (§1, Introduction) | 重绘配色 |
| Fig. 5 | — | — | 已删除：数据由主结果表(Table 2)替代 |
| Fig. 6 | — | — | 已删除：数据由缩放表(Table 3)替代 |
| Fig. 7 | `figures/evm_workflow.png` | EVM execution workflow (§1) | drawio 绘制 |

## Color System (Blue-Gray Palette)

Established 2026-07-05. Used for all figures.

| Hex | Usage |
|-----|-------|
| `#2C4A6E` | Primary curve, emphasis |
| `#4A6B8C` | Secondary, accent arrows |
| `#6B8EB5` | Borders, secondary curves |
| `#8DA3C4` | Tertiary, dashed arrows |
| `#B0C4DE` | Lightest, reference lines |
| `#C85A4A` | Warm accent (cost/overhead) |
| `#5A8C6E` | Green accent (gain/savings) |

Container backgrounds: `#EAF0F6` (offline panel), `#DFE6EE` (online panel), `#C8D6E5` (key box — Augmented HT).

**Figure design rules:**
- 字号统一：框内主文字 11pt，节号/副文字 9pt
- 曲线加标记（三角/方形），白填充，`markevery=0.05`
- 图中不含标题（LaTeX caption 替代）

---

## References (25)

Citation keys map: `storage_replica`, `evmtracer`, `eip7707`, `eip2930`, `eip7650`, `eip7863`, `reddio`, `ostm`, `needless_writes`, `evmshield`, `conflict_spec`, `voyager`, `efficient_neural`, `pythia`, `rlcopref`, `farsight`, `a2p`, `primer_prefetch`, `survey_prefetch`, `markov_prefetch`, `alex`, `pgm`, `radixspline`, `shifttable`, `nas_paper_1`, `nas_paper_2`

---

## Pending Tasks (第二轮修改 — 2026-07-11)

15. ~~**Fix Abstract: merge two paragraphs, remove "two-stage filtering", 1.1274x → 12.7%**~~ ✅ Done
16. ~~**Introduction: rewrite EVM/Erigon flow, add e.g., fix "core problem", fix "collection" footnote**~~ ✅ Done
17. ~~**Introduction: fix "Raw Predict Overhead" formula with symbols $t_{pred}$, $t_{exec}$**~~ ✅ Done
18. ~~**Introduction: fix footnote 28ms → inline, add sec:platform-configuration label**~~ ✅ Done
19. ~~**Introduction: explain (to, selector) at first occurrence**~~ ✅ Done
20. ~~**Related Work §2.3: restructure learned index section**~~ ✅ Done
21. ~~**Preliminary: fix pk → $\kappa$, add DeFi swap citation, add optimization formula**~~ ✅ Done
22. ~~**System Design §4.1: rewrite Overview, add ground-truth clarification, add generalization logic**~~ ✅ Done
23. ~~**System Design §4.3.1: fix hash table construction wording, add itemize for feature groups**~~ ✅ Done
24. ~~**System Design §4.3.1: add feature importance figure**~~ ✅ Done
25. ~~**System Design §4.3.3: fix ground-truth wording, unify/add $\mathcal{P}(tx)$ definition**~~ ✅ Done

**Remaining — to be completed:**

26. **§4.2.2 Threshold-based Routing** — 明确说明大 union key 不在 hash table 中 (vs 读者可能误解为"全存了")
27. **§4.3.3 Candidate Accumulation** — 改用更明确的 "stored/excluded" 替代 "hit/miss"
28. **§4.2.1 Union Construction** — 补充一句说明 hash table 的构建规则（只存小 union）
29. **零散润色** — 整理自 论文修改意见整理批注版.md 中剩余未处理的简单修改

1. ~~**Fill [DATA NEEDED] in Introduction**~~ ✅ Done
2. ~~**Add real citations**~~ ✅ Done (EIP-7707, Vitalik gas analysis)
3. ~~**Redraw Fig. 1 (architecture)**~~ ✅ Done (2026-07-05)
4. ~~**Redraw Fig. 2 (CDF)**~~ ✅ Done (2026-07-05)
5. ~~**Redraw Fig. 3 (pipeline)**~~ ✅ Done (2026-07-05)
6. ~~**Redraw Fig. 4 (alpha)**~~ ✅ Done (2026-07-05)
7. ~~**NAS paper citations** — replace `nas_paper_1`/`nas_paper_2` placeholders with real NAS papers~~ ✅ Done (2026-07-07) — DeepFetch + Cached Mapping Table Prefetching
8. ~~**Fix `sec:methodology` cross-ref** → `sec:evaluation`~~ ✅ Done
9. ~~**Check `Figure~\ref{fig:evm_workflow}`**~~ ✅ Done
10. ~~**Verify E2/E3 experiment labels**~~ ✅ Done (2026-07-07) — 编号改为 E0/E1/E2/E3，删旧 E3 (Online ML)，Augmented → E3
11. ~~**Verify all `fig:` labels match** — check after renumbering (currently 5 figs: evm_workflow, alpha, architecture, cdf, pipeline)~~ ✅ Done (2026-07-08)
12. ~~**Redraw Fig. 5/Fig. 6**~~ ✅ Cancelled — 数据已被表格替代，无需重绘
13. ~~**Restructure Related Work Sec.A/B/C**~~ ✅ Done (2026-07-05)
14. ~~**Update figure labels** — Fig. 1 (architecture) and Fig. 3 (pipeline) still use "pattern generation" in image labels; should update to "candidate accumulation" (drawio source + re-export PNG)~~ ✅ Done (2026-07-07)

## Session Log: 2026-07-07 — Evaluation 章节大修 + 实验代码命名统一

### 修改内容

**§5.1.1 Simulation Platform — 改写仿真理由**
- 删除了无力的 "our focus is on quantifying the theoretical upper bound" 理由
- 替换为实际理由：Erigon 是生产级客户端（50 万行 Go），修改工程复杂；验证核心想法不需要改 Erigon，trace-driven 仿真足够
- 删除了冗长的语义对应双栏表格，压缩为一句概括（cold/hot/block reset/prefetch injection）

**§5.1.4 Experiment Groups — 重构四组实验**
- 实验组从 5 组（E0/E1/E2/E3 + Augmented）改为 4 组（E0/E1/E2/E3）
- **删除了旧 E3 (Online ML)**：Introduction 的 α 分析已充分证明在线 ML 不可行
- **Augmented → E3 (Offline-Enhanced)**：编号统一
- 新增 "Dictionary" 列，突出 E2 和 E3 使用同一 Hash Table 查表机制，区别仅在字典内容
- 正文补充说明 "Both share the same O(1) hash table lookup mechanism"

**§5.2 Main Results — 更新主结果表**
- 表头从 "Online Hash Table / Augmented" 改为 "${E2}$ (Hash Table) / ${E3}$ (Offline-Enhanced)"

**§5.2 Ablation Study — 补充定量数据**
- 加入 ${E0}$/${E1}$/${E2}$/${E3}$ 在 Window B 上的实际代价数据
- ${E0}$: 1,128,660 µs → ${E1}$: 14,649 µs → ${E2}$: 880,983 µs (填补 22.2%) → ${E3}$: 781,405 µs (填补 31.2%)
- 删除旧 ${E3}$ (Online ML) 的无效论证

**§5.3 Scaling Consistency — 更新缩放数据**
- 2K 行更新为实测值 +26.8%/−7.7%（原为 +27.4%/−7.8%，偏差 ~0.6%）
- 10K 和 94K 数据完全匹配
- 补跑了 scale_2k 和 scale_10k 实验，CSV 保存至 `figures/data/scale_2k/` 和 `scale_10k/`

**§5.4 Sensitivity Analysis — 重跑数据**
- 旧数据：`none vs hybrid` 在 586 txs 上跑，speedup 1.3313x（与主表不匹配）
- 新数据：E2/E3 在 Window B (28,757 txs) 上用解析公式计算
- E2 speedup ~1.28x, E3 speedup ~1.44x, 变化 ±0.1%
- 新增 E2/E3 双列 + Variation 列，数据保存至 `figures/data/sensitivity_wb.csv`

**§5.1.3 Dataset — 术语统一**
- "training window (Window A)" → "training window"
- "evaluation window (Window B)" → "evaluation window"

### 代码命名统一（详见 docs/NAMING_CONVENTIONS.md）

| 旧名 | 新名 | 涉及文件 |
|------|------|---------|
| `fast_path_dict` | `pattern_table` | prefetch_api.py, offline_delta.py |
| `RuleBasePrefetcher` | `TablePrefetcher` | prefetch_api.py |
| `HybridPrefetcher` | `MLPrefetcher` | prefetch_api.py |
| `HybridGatedPrefetcher` | `MLGatedPrefetcher` | prefetch_api.py |
| `FAST_PATH_THRESHOLD` | `UNION_SIZE_THRESHOLD` | train_hybrid.py |
| `slow_batch_size` | `offline_batch_size` | run.py, offline_delta.py, prefetch_api.py |
| CLI: `rule` | `table` | run.py, prefetch_api.py |
| CLI: `hybrid` | `ml` | run.py, prefetch_api.py |
| CLI: `--hybrid-gate-rate` | `--ml-gate-rate` | run.py |
| CLI: `--slow-batch-size` | `--offline-batch-size` | run.py |
| `rule_base` / `rule_plus_delta` | `original_table` / `augmented_table` | offline_delta.py 内部变量 |
| `rule_miss` / `rule_miss_txs` | `table_miss` / `table_miss_txs` | offline_delta.py |
| Window A/B | training_window / eval_window | offline_delta.py 注释 |

### 实验数据跑的结果

- **Window B E0 (none)**: cost = 1,128,660 µs, would-be-miss = 375,088
- **Window B E1 (oracle)**: cost = 14,649 µs, recall = 1.0
- **Window B E2 (table)**: cost = 880,983 µs, recall = 0.2223
- **Window B E3 (augmented)**: cost = 781,405 µs, recall = 0.3117
- **Sensitivity**: E2/E3 speedup 稳定 ±0.1%，文件保存至 `figures/data/sensitivity_wb.csv`

### 已确认的事实

- Scaling 数据验证通过：2K (+26.8%), 10K (+35.7%), 94K (+40.2%) 单调递增
- Sensitivity 分析改用解析公式（因为 t_hit/t_miss 不影响 recall/precision）
- Window B JSONL 保存至 `/tmp/window_b.jsonl`
- 模型 pickle 文件 `evm_model_hybrid_v1.pkl` 中 key 仍为 `"fast_path_dict"`（保持向后兼容，未改）

## Session Log: 2026-07-08 — 最终细节调整（19项修正）

### 修改内容

**#5 α 参数定义修正（§1 Introduction）**
- 原定义 "fraction of cold accesses that the ML model can successfully predict" 与公式语义不一致
- 改为 "fraction of transaction execution time that can overlap with ML inference"
- 与实验代码 `effective_pred_overhead_us(alpha) = max(0, predict_overhead_us - alpha * tx_exec_us_total)` 统一

**#10/#13 CDF 数据修正（§3.2, §4.2.2, Fig.2 caption）**
- 原 "Over 80% of pattern keys have union sizes below ten" 是幻觉数据（实际仅 48.3%）
- 改为 "Over 80% of pattern keys have union sizes below 50"（实际 83.5%）
- §3.2 额外补充 "the majority of calling patterns access a compact and repeatable set of storage slots"

**#6 Raw Predict Overhead 明确定义（§1 Introduction）**
- 公式前新增定义："Let Raw Predict Overhead denote the total time spent on ML inference (number of inferences multiplied by per-inference latency)"
- "raw overhead" → "raw predict overhead" 统一术语
（这里采用了新的公式和符号，这一条可以忽略）


**#4 28ms 推理开销来源标注（§1 Introduction）**
- 新增脚注说明 28ms 是 LightGBM 模型在实验平台上的平均每笔交易推理时间
（这里现在已经在正文中说明了，所以无需脚注，这一条可以忽略）


**#7 区块数量 1001 vs 999 统一（§5.1.3 Dataset, §7 Conclusion）**
- Conclusion: "comprising" → "yielding"，消除"1001 个块包含 94K 交易"的歧义
- Dataset: 加了解释 "2 blocks contained only such transactions and were excluded"
- 补建了缺失的 `\label{sec:platform-configuration}`

**#16 "Pattern Generation" → "Candidate Accumulation" 统一（§4.3, Fig.3, Algorithm 1）**
- §4.3 标题: "Incremental Pattern Generation" → "Incremental Candidate Accumulation"
- Fig.3 caption: "incremental pattern generation" → "incremental candidate accumulation"
- 所有 label 更新：`sec:pattern-generation` → `sec:candidate-accumulation`，`alg:pattern-generation` → `alg:candidate-accumulation`
- §5.2.1 标题: "Offline Pattern Generation Effect" → "Offline Augmentation Effect"

**#17 $S_{\text{actual}}(t)$ vs $S_{\text{actual}}(tx)$ 符号统一（§4.3.3, Algorithm 1）**
- 全文统一为 $S_{\text{actual}}(tx)$，与 §3.2 Eq.(1) 一致
- 算法中 `$t$` → `$tx$`（用户修改后由我补改 2 处残留）

**#18 "(pattern key, slot)" → "(pattern key, storage slot)" 统一（§4.3.4）**
- L428 改为与 L380/L390 一致的完整表述

**#15 Algorithm 1 格式修复**
- 清理 preamble 冲突包：删除 `\usepackage{algorithmic}`（旧）和 `\usepackage{algorithmicx}`（由 `algpseudocode` 自动加载）
- `\EndFor` 与 `\Return` 之间加空行分隔

**#1 Introduction 硬件脚注去重**
- 删除脚注中的硬件规格（重复 §5.1.2），保留测量方法，增加跨引用

**#8 排比结构重写（§2.3 Summary）**
- 删除三个 "From a new... perspective" 的 AI 味排比
- 改为自然陈述，保留三个方向内容
- 添加中文注释说明三个方向

**#9 Pattern key 重复定义消除（§4.2.1）**
- 删除与 §3.2 完全重复的定义，改为引用 `Section~\ref{sec:pattern-keys}`

**#12 训练输出 → 输入特征的过渡补充（§4.3.1 Model Training）**
- 新增过渡句："To make predictions for unseen transactions, the model requires a set of features that are available before execution begins."

**#14 training window 命名确认**
- 维持 "training window"，不改为 "incremental window"
- 理由：`training window / evaluation window` 是 ML 标准配对

### 确认为无需修改的问题
- **#2**（冷热访问时间数据）：脚注已有详细测量方法，无需改动
- **#3**（76% 比例内涵）：76% = 375,088/488,295，是实际指令级冷访问率，脚注解释充分
- **#11**（`debug_traceTransaction` 下划线）：当前格式已正确

### 待办更新
- ~~#11 Verify all `fig:` labels match~~ ✅ 已由用户确认

## Session Log: 2026-07-07 — System Design 继续细化

### 修改内容

**§4.1（Abstract）"zero-overhead" 用词修正**
- "zero-overhead constant-time lookups" → "constant-time lookups with zero ML inference overhead"
- 精确限定："零 ML 推理开销" 而非笼统的 "零开销"

**§4.2.1 Union Size 定义统一**
- 删除 §4.2.1 中的重复定义，改为引用 §2.2 Preliminary 中的公式 `|U(k)|`
- 消除此前 `U(k)` 与 `\mathcal{U}(k)` 符号不一致的问题

**§4.2.2 Threshold-based Routing 理由补充**
- 从笼统的 "miss too many slots / waste space" 替换为具体解释：
  - hash table 存的是全集（all-or-nothing）
  - 小 union 存进去高效（几乎每个 slot 都会被访问）
  - 大 union 存进去全是误预取（浪费缓存带宽）
  - 所以需要路由到 ML 模型做更精细的选择

**§4.3.3 Candidate Accumulation 重命名**
- 原来叫 "Pattern Generation"——太笼统
- 改名为 "Candidate Accumulation"，强调算法的核心操作（累加模型预测正确的 slot 计数）
- 和 §4.3.4 "Filtering and Merging" 形成自然衔接

### 已确认的事实

- 论文当前无 "lookup cost" 术语残留，仅使用 "O(1)" / "constant-time" 等标准描述
- §4.2.3 Online Lookup 中 "zero machine learning inference cost" 表述正确，无需修改
- "Pattern Generation（离线增量）" 是 Evaluation 中的总体效果描述，不与 §4.3.3 冲突

### 2026-07-07 下午 — System Design 继续细化（续）

**§4.3.3 ∼ §4.3.4 Candidate Accumulation → Filtering → Merging 完整流程补充**
- 修正了 §4.3.3 中符号 $\mathcal{T}(t)$ 与 §2.2 $S_{\text{actual}}$ 不一致的问题，统一为 $S_{\text{actual}}$
- 删除了 body text 中模糊的 "Results are aggregated..." 表述，替换为 "count for each (pattern key, storage slot) pair"
- 补充了计分 → 置信度 → 过滤的衔接逻辑
- §4.3.4 Filtering and Merging 拆分为三个明确的子步骤并添加中文注释：
  - **Minimum support**：去除计数 < 阈值的噪声（实验中阈值为 2）
  - **Per-key slot limit**：按计数降序优先保留高分 slot
  - **Merge**：key 已存在则追加，不存在则新建条目

**符号统一检查**
- 确认 $\mathcal{T}$ 已全部替换为 $S_{\text{actual}}$（与 §2.2 一致）
- 确认 $\mathcal{U}(k)$ 已全部替换为 $U(k)$（与 §2.2 Eq.(1) 一致）
- 确认全文无 "rule_base"、"rule_plus_delta" 的未注释残留

**Simulation Platform / Hardware / lstlisting 检查**
- Simulation Platform 已在 Evaluation §5.1.1，无残留
- Platform Configuration 已在 Evaluation §5.1.2，规格完整
- `\lstlisting` 环境当前未使用，暂无需添加（留空）

### 待办（2026-07-07 确认）
- Fig. 1 和 Fig. 3 仍使用 "Pattern Generation" 标签 → 由用户自行更新 drawio 源文件后重绘（Pending Task #14）

## Advisor's Key Decisions (from 2026-07-03 meeting)

- New structure: Intro → Related Work → Preliminary → System Design → Evaluation → Limitation → Conclusion
- Related Work: A/B/C three subsections (not four), summary from three perspectives (new perspective / new architecture / new scene)
- Feasibility analysis moved from Evaluation to Introduction (it's motivation, not experiment)
- Simulation platform moved from System Design to Evaluation
- Rule key → pattern key; LightGBM → classification model (in System Design)
- No "compiler" language — use "merge"
- Future work: keep brief, don't write if not good, cite NAS papers as convention
- No em-dashes, no long sentences, no excessive lists
- E0 = no-prefetch baseline, E1 = oracle upper bound, E2 = hash table (original), E3 = offline-enhanced (our method, replaces old Augmented). Note: original E3 (online ML) was removed — proven infeasible by Introduction alpha analysis.

---

## Working Style

- Write in Chinese markdown first, then translate to English, then format to IEEE LaTeX
- User learns from the process — not just "AI writes everything"
- Always check numbers, citations, and terminology consistency
- Reference TERMINOLOGY.md for exact English terms
- Reference academic_writing_guide.md for sentence patterns
