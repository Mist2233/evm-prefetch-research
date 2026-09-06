# Fig. 3 Pipeline — Drawio 绘图规范

> 离线管线图，展示增量模式生成与评估的完整流程（§4.3）。
> 与 Fig. 1 架构图区分定位：Fig. 1 展示**系统整体架构**（左右双路径），Fig. 3 展示**离线路径的具体流水线**（从左到右的五步骤流程）。

---

## 全局设置

- **画布尺寸**: ~850px 宽 × ~240px 高（水平布局，仅五步骤）
- **配色**（与 Fig. 1 统一的蓝灰色系）：
  - 容器底色: `#EAF0F6`（同 Fig. 1 左栏底色）
  - 框底色: 白色 `#FFFFFF`
  - 边框: `#6B8EB5`，1.5px
  - 步骤编号圆标: `#4A6B8C`，白字
  - 箭头: `#4A6B8C`，1.5px
  - 关键产出框（Augmented HT）: `#C8D6E5` 底色，2px 边框（同 Fig. 1）
  - 结果汇总框: `#C8D6E5` 底色，虚线边框

- **字号**（与 Fig. 1 统一）：
  - 容器标题: 13pt 加粗
  - 框内主文字: **11pt**
  - 框内副文字（节号、子描述）: **9pt** 斜体
  - 步骤编号: 10pt 加粗
  - 底部数据: 10pt

- **圆角**: 容器圆角 8px，内部框圆角 4px

---

## 整体布局

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Offline Pipeline: Incremental Pattern Generation & Evaluation (§4.3)     │
│                                                                           │
│  ① ──→ ② ──→ ③ ──→ ④ ──→ ⑤                                             │
│  ↓     ↓     ↓     ↓     ↓                                               │
│  ┌──┐  ┌──┐  ┌──┐  ┌──┐  ┌──┐                                           │
│  │  │  │  │  │  │  │  │  │  │                                           │
│  └──┘  └──┘  └──┘  └──┘  └──┘                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 五个步骤（水平排列，左→右）

---

### 步骤 ①: Data Preparation

| 属性 | 值 |
|------|-----|
| 框宽×高 | 140px × 90px |
| 主标题 | **Data Preparation** |
| 节号 | *§4.3.2* |
| 行 1 | Load transaction traces from Erigon full node |
| 行 2 | Chronological split (70/30) |
| 行 3 | → **Training Window** (699 blks, 65,706 txs) |
| 行 4 | → **Evaluation Window** (300 blks, 28,757 txs) |

**箭头**: ① → ②，标签 "Training data"

---

### 步骤 ②: Model Training

| 属性 | 值 |
|------|-----|
| 框宽×高 | 140px × 90px |
| 主标题 | **Classification Model Training** |
| 节号 | *§4.3.1* |
| 行 1 | Multi-label classifier |
| 行 2 | 8 input features |

**箭头**: ② → ③，标签 "Trained model"

**额外连接**: Training Window（①）也直接输入到步骤 ③，用于提供 ground-truth access sets。

---

### 步骤 ③: Pattern Generation

| 属性 | 值 |
|------|-----|
| 框宽×高 | 160px × 90px |
| 主标题 | **Pattern Generation (Algorithm 1)** |
| 节号 | *§4.3.3* |
| 行 1 | For each tx in Training Window: |
| 行 2 | Key in Online HT? → skip |
| 行 3 | Else: Model **predict ∩ GT** |
| 行 4 | → Accumulate counts per key/slot |

**说明**: Online HT 由 Pattern Key Union & Threshold Routing 构建（已在 Fig. 1 左栏展示）。本框只需标注 "Online HT from §4.2" 即可，不必重复绘制。

---

### 步骤 ④: Filter & Merge

| 属性 | 值 |
|------|-----|
| 框宽×高 | 140px × 90px |
| 主标题 | **Filter & Merge** |
| 节号 | *§4.3.4* |
| 行 1 | • Minimum support |
| 行 2 | • Per-key slot cap |
| 行 3 | → Validated slots merged into |
| 行 4 | → **Augmented Hash Table** |

**箭头**: ④ → ⑤，标签 "Augmented HT"

---

### 步骤 ⑤: Evaluation

| 属性 | 值 |
|------|-----|
| 框宽×高 | 140px × 90px |
| 主标题 | **Evaluation** |
| 节号 | *§4.3.5* |
| 行 1 | Simulator on Evaluation Window |
| 行 2 | **Baseline (Online HT)** vs |
| 行 3 | **Augmented (Offline-Enhanced)** |
| 行 4 | → Compare Recall, Precision, Cost |

---

## 箭头汇总

| 起点 | 终点 | 标签 | 线型 |
|------|------|------|------|
| Step ① (Training Window) | Step ② | Training data | 实线 |
| Step ① (Training Window) | Step ③ | Training data (for GT) | 实线 |
| Step ② | Step ③ | Trained model | 实线 |
| Step ③ | Step ④ | Accumulated counts | 实线 |
| Step ④ | Step ⑤ | Augmented HT | 实线 |
| Step ① (Evaluation Window) | Step ⑤ | Evaluation data | 实线（从底部绕过 ②③④） |

---

## 术语对照（与 CLAUDE.md 一致）

| 图中用 | 不用 |
|--------|------|
| Online Path / Offline Path | Fast path / Slow path |
| Online Hash Table | `fast_path_dict` |
| Classification Model | LightGBM |
| Pattern key | Rule |
| Incremental patterns | Delta rules |
| Training Window / Evaluation Window | Window A / Window B |
| Baseline (Online HT) / Augmented | rule_base / rule_delta |
| (to, selector) | `(to, selector)` |

---

## 与 Fig. 1 的区分和关联

| 维度 | Fig. 1 Architecture | Fig. 3 Pipeline |
|------|---------------------|-----------------|
| 视角 | 系统整体架构（双路径） | 离线路径的详细流水线 |
| 布局 | 左右两栏 | 水平五步骤 + 底部结果 |
| Online 部分 | 有单独右栏展示 | **不包含**（只聚焦 offline） |
| Augmented HT | 左栏底部的中间产物 | 步骤 ④→⑤ 的传递产物 |
| 评价结果 | 不包含 | 不包含（移到 Evaluation 展示） |
| 步骤粒度 | 粗粒度（合并了 3 个子步骤） | 细粒度（5 个明确步骤） |

**建议**: 保持 Fig. 3 的术语与 Fig. 1 完全一致，读者看了 Fig. 1 再看 Fig. 3 能自然对应。例如 Fig. 1 中的 "Pattern Gen · Filter · Merge" 对应 Fig. 3 的步骤 ③+④。

---

## 对比原文的修改记录

| 问题类型 | 原文 | 修改为 |
|----------|------|--------|
| 术语 | 快速路径 / 慢速路径 | Online Path / Offline Path |
| 术语 | `fast_path_dict`、LightGBM | Online Hash Table、Classification Model |
| 术语 | `rule_miss` | Hash table miss |
| 术语 | 增量规则 | Incremental patterns |
| 术语 | Window A / Window B | Training Window / Evaluation Window |
| 术语 | rule_base / rule_delta | Baseline (Online HT) / Augmented |
| 流程 | Step ① "从 pkl 加载模型" | 改为先加载数据、再训练模型（符合论文叙述顺序） |
| 流程 | 缺少 Pattern Key Union & Route 的标注 | 在 Step ③ 中添加脚注 "Online HT from §4.2" |
| 样式 | 无配色/字号规范 | 统一为蓝灰色系，与 Fig. 1 一致 |
| 定位 | 与 Fig. 1 功能区分不清 | 明确 Fig. 3 聚焦离线流水线、不包含 Online 部分 |
