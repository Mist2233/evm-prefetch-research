# 论文术语规范 v3.0 (2026-07-14 更新)

> 基于论文正文实际使用情况构建。所有修改必须遵循此表。

---

## 全局写作规则
- **禁止双破折号**（-- 或 ---），逗号替代即可
- **禁止长难句**，简单句直接写，不用分号连接从句
- **禁止列表过多**，能用段落描述就不用 itemize/enumerate
- 明显的 first-second-third 列举必须用 itemize/enumerate
- **第一次出现的缩写**必须全拼，且前面单词首字母大写（如 Machine Learning (ML)）
- **避免 AI 味措辞**，不用 overly polished 的句式
- **括号尽量少用**，能写入正文的都写入正文
- **零散小段整合成大段**，注意段间逻辑衔接
- **不要删内容**，保留原意

---

## 术语对照（强制）

### 核心术语（全文统一）

| 标准术语 | 类型 | 首次出现位置 | 说明 |
|----------|------|-------------|------|
| pattern key | 名词 | §3.2 | (to, selector) 二元组，用于分组交易的键 |
| online path | 名词 | §1, §4 | 在线路径，O(1)哈希表查询 |
| offline path | 名词 | §1, §4 | 离线路径，批量运行分类模型 |
| classification model | 名词 | §4.3.1 (System Design) | System Design 中只能用此称呼 |
| LightGBM | 名词 | §1 (Introduction), §5 (Evaluation) | **仅限 Introduction 和 Evaluation 出现** |
| multi-label classification | 名词 | §4.3.1 | 多标签分类，模型预测任务 |
| hash table | 名词 | 全文 | 哈希表，在线查询结构 |
| base hash table / augmented hash table | 名词 | §4 | 基础表/增强表 |
| storage slot | 名词 | 全文 | 存储槽，EVM 状态基本单位 |
| storage slot set | 名词 | 全文 | 存储槽集合（非 list） |
| cold access / hot access | 名词 | §1, §3 | 冷/热访问 |
| intra-block cache | 名词 | §1, §3 | 块内缓存 |
| union size $U(k)$ | 名词 | §3.2, §4.2 | 模式键的历史并集大小 |
| coverage parameter $\alpha$ | 符号 | §1 | 执行时间重叠比例 |
| training window / evaluation window | 名词 | §5 (Evaluation) | **仅限 Evaluation 章节** |
| SPML-PF | 缩写 | §1 (Introduction) | Split-Path ML-Augmented Prefetching |
| E0 / E1 / E2 / E3 | 缩写 | §5 (Evaluation) | 实验组编号，**仅限 Evaluation** |
| recall / precision / speedup | 指标 | §3.3, §5 | 评估指标 |

### 禁用/替换对照

| 废弃术语 | 替换为 | 说明 |
|----------|--------|------|
| rule key | pattern key | 全文替换 |
| fast path | online path | 全文替换 |
| slow path | offline path | 全文替换 |
| compiler / compile | merge / generation | 如 "compile patterns" → "generate patterns" |
| rule_base / rule_plus_delta | original table / augmented table | 变量名不在正文出现 |
| rule_miss | hash table miss | 描述性文字 |
| Window A / Window B | training window / evaluation window | 仅限 Evaluation |
| Learned Indexes | Learned Indexes | 作为 Related Work 标准术语保留 |
| Single Inference / Inference overhead | ML inference | 统一为 ML inference |
| storage slot list | storage slot set | 统一 |
| `\texttt{min\_support}` / `\texttt{max\_new\_slots\_per\_key}` | — | 仅在 Evaluation 出现 |

### 需注意的短语和用法

| 用法 | 正确形式 | 说明 |
|------|---------|------|
| "(to, selector)" | (to, selector) | 正常文字，不用代码字体或斜体强调 |
| "O(1)" | $O(1)$ | 数学模式 |
| "zero ML inference overhead" | 固定短语 | 不要写成 "zero-overhead" |
| "machine learning" vs "Machine Learning (ML)" | 首次 Machine Learning (ML)，之后 ML | 注意首字母大写 |
| "offline batch processing" | 固定短语 | 描述离线路径运行方式 |
| "ground truth" | ground-truth（做定语时连字符） | 如 ground-truth access sets |
| "storage access cost" | 固定短语 | 存储访问总代价 |

## 各章节内容边界

| 内容 | 所属章节 | 禁止出现位置 |
|------|---------|------------|
| 具体实验数据（Window 大小、命中率、min_support 值） | Evaluation | System Design |
| 具体模型名（LightGBM 等） | Introduction, Evaluation | System Design (4.3.1) |
| Feasibility Analysis（alpha 模型） | Introduction | Evaluation |
| Simulation Platform | Evaluation | System Design |
| Parallel EVM 相关工作 | Related Work §2.A | Introduction |
| training window / evaluation window 命名 | 全文可用（System Design、Evaluation） | 核心设计概念，可在 System Design 中使用 |
| E0-E3 实验组定义 | Evaluation | System Design |
