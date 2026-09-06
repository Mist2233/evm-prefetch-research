# Fig. 1 Architecture — Drawio 绘图规范（第二版：左右布局）

> 上一版三块区域太长，框内文字太多字号太小。  
> 这一版改为**左右两栏布局**，大幅简化文字，增大字号。

---

## 全局设置（更新）

- **画布尺寸**: ~750px 宽 × ~500px 高（比上一版更扁更宽）
- **配色**（蓝灰系，两个区域用同色系不同深浅）：
  - 左栏 Offline Path 底色: `#EAF0F6`
  - 右栏 Online Path 底色: `#DFE6EE`
  - 框底色: 白色 `#FFFFFF`
  - 边框: 统一 `#6B8EB5`，1.5px
  - 关键框（Augmented HT）: `#C8D6E5` 底色，边框 2px
  - 箭头: `#4A6B8C`，1.5px
  - 分叉虚线: `#8CA3C0`，虚线 `---`

- **字号（整体加大）**：
  - 区域标题: 13pt 加粗
  - **框内主文字: 11pt**（上一版 10pt）
  - **框内副文字（节号）: 9pt 斜体**（上一版 8pt）
  - 箭头标签: 10pt

- **圆角**: 区域容器圆角 8px，内部框圆角 4px

---

## 整体布局（左右两栏）

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│  ┌──────────── 左栏: Offline Path ───────────┐  ┌─ 右栏: Online ─┐
│  │  背景 #EAF0F6                               │  │   #DFE6EE     │
│  │                                            │  │               │
│  │   框1                                      │  │  框A          │
│  │     │                                      │  │    │          │
│  │   框2                                      │  │  框B          │
│  │   / \                                      │  │   / \         │
│  │ 框3 框4                                     │  │ 框C 框D        │
│  │  │   │                                      │  │   \ /         │
│  │  └─┬─┘                                      │  │  框E          │
│  │    │                                        │  │               │
│  │  框5 (Augmented HT) ────────→ (跨栏箭头) ───────→               │
│  └──────────────────────────────────────────────┘               │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 左栏: Offline Path — Incremental Pattern Generation

**区域属性**: 背景 `#EAF0F6`，标题 "Offline Path: Incremental Pattern Generation (§4.3)"

```
┌─────────────────────────────────────────────────────────┐
│ Offline Path: Incremental Pattern Generation (§4.3)      │
│                                                          │
│  ┌───────────────────────────────────────────┐            │
│  │     Training Window                        │            │
│  │     699 blocks · 65,706 transactions       │            │
│  └─────────────────────┬─────────────────────┘            │
│                        │                                  │
│         ┌──────────────┼──────────────┐                   │
│         │              │              │                   │
│         ▼              │              ▼                   │
│  ┌──────────────────┐ │ ┌────────────────────────────┐   │
│  │ Pattern Key      │ │ │ Classification Model        │   │
│  │ Union & Route    │ │ │ Training (§4.3.1)           │   │
│  │ (§4.2.1-4.2.2)   │ │ │                            │   │
│  │                  │ │ │ Multi-label classifier      │   │
│  │ |U(k)| ≤ θ → Online│ │ 8 input features           │   │
│  │ |U(k)| > θ → Model│ │ └──────────┬─────────────────┘   │
│  └──────┬───────────┘ │             │                    │
│         │             │             │                    │
│         ▼             │             ▼                    │
│  ┌──────────────────┐ │ ┌────────────────────────────┐   │
│  │ Online Hash      │ │ │ Pattern Gen · Filter ·     │   │
│  │ Table (§4.2.3)   │ │ │ Merge (§4.3.3-4.3.4)      │   │
│  │ O(1) lookup      │ │ │                            │   │
│  └────────┬─────────┘ │ │ Predict ∩ Ground Truth     │   │
│           │           │ │ → Min support + Per-key cap│   │
│           └─────┬─────┘ │ → Merge into Hash Table    │   │
│                 │       └──────────────┬──────────────┘   │
│                 └──────────┬───────────┘                  │
│                            ▼                              │
│  ┌──────────────────────────────────────────┐             │
│  │       Augmented Hash Table                │             │
│  │  Same key-value format · O(1) preserved   │             │
│  └────────────────────┬─────────────────────┘             │
│                       │                                    │
└───────────────────────┼────────────────────────────────────┘
                        │ ★ 粗箭头跨栏
                        ▼
                  (指向右栏 Hash Table Lookup)
```

**合并后的框数**: 上一版 7 个框 → 这一版 **5 个框**

| 框 | 文字 | 合并了什么 |
|----|------|-----------|
| Training Window | **Training Window**<br>699 blks · 65,706 txs | 简化为只含关键数字 |
| Pattern Key Union & Route | **Pattern Key Union & Route (§4.2.1-4.2.2)**<br>\|U(k)\| ≤ θ → Online HT<br>\|U(k)\| > θ → Model | 合并了 Union Construction + Threshold Routing |
| Classification Model Training | **Classification Model Training (§4.3.1)**<br>Multi-label, 8 features | 去掉详细特征列表 |
| Online Hash Table | **Online Hash Table (§4.2.3)**<br>O(1) lookup | 简化为标题 + 属性 |
| Pattern Gen · Filter · Merge | **Pattern Gen · Filter · Merge (§4.3.3-4.3.4)**<br>Predict ∩ GT → Min support + cap → Merge | **合并了三个子步骤**，这是最大的简化 |
| **Augmented Hash Table** | **Augmented Hash Table**<br>Same key-value · O(1) | 加深底色强调 |

---

## 右栏: Online Path — Hash Table Lookup

**区域属性**: 背景 `#DFE6EE`，标题 "Online Path: Hash Table Lookup (§4.2)"

```
┌─────────────────────────────────────────────────────────┐
│ Online Path: Hash Table Lookup (§4.2)                    │
│                                                          │
│                   ↑← 接收左栏的 Augmented HT              │
│                   │                                      │
│  ┌────────────────────────────────────┐                  │
│  │      Incoming Transaction           │                  │
│  └────────────────┬───────────────────┘                  │
│                   │                                      │
│  ┌────────────────▼───────────────────┐                  │
│  │      Extract Pattern Key (to, selector)               │
│  └────────────────┬───────────────────┘                  │
│                   │                                      │
│  ┌────────────────▼───────────────────┐                  │
│  │      Hash Table Lookup (§4.2.3)    │                  │
│  │      O(1) · Augmented Hash Table   │                  │
│  └────────────────┬─────────┬─────────┘                  │
│                Hit│         │Miss                        │
│  ┌────────────────▼──┐ ┌───▼────────────┐                │
│  │  Storage Slot Set  │ │  Empty Set     │                │
│  └────────────────┬───┘ └───┬───────────┘                │
│                   │         │                            │
│                   ▼         ▼                            │
│  ┌────────────────────────────────────┐                  │
│  │      EVM Execution                  │                  │
│  │  Zero ML inference cost at runtime  │                  │
│  └────────────────────────────────────┘                  │
│                                                          │
│  ┌────────────────────────────────────┐                  │
│  │  Key Properties                    │                  │
│  │  • O(1) unchanged after merge      │                  │
│  │  • Continuous periodic updates     │                  │
│  └────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────┘
```

**框数**: 6 个（比上一版 8 个少，且每框文字大幅减少）

| 框 | 文字 |
|----|------|
| Incoming Transaction | **Incoming Transaction** |
| Extract Pattern Key | **Extract Pattern Key (to, selector)** |
| Hash Table Lookup | **Hash Table Lookup (§4.2.3)**<br>O(1) · Augmented Hash Table |
| Storage Slot Set | **Storage Slot Set** |
| Empty Set | **Empty Set** |
| EVM Execution | **EVM Execution**<br>Zero ML inference cost |
| Key Properties | **Key Properties**<br>• O(1) unchanged after merge<br>• Continuous periodic updates |

---

## 箭头标签汇总

| 起点 | 终点 | 标签 | 线型 |
|------|------|------|------|
| Training Window | Pattern Key Union & Route | — | 实线 |
| Training Window | Model Training | — | 实线 |
| Pattern Key Union → | Online HT | \|U(k)\| ≤ θ | 实线 |
| Pattern Key Union → | (虚线到 Pattern Gen) | \|U(k)\| > θ → Model | **虚线** |
| Model Training | Pattern Gen · Filter · Merge | Trained model | 实线 |
| Online HT | Augmented HT | baseline | 实线 |
| Pattern Gen · Filter · Merge | Augmented HT | incremental | 实线 |
| **Augmented HT** | **HT Lookup (右栏)** | **★ Deploy / Merge** | **粗实线跨栏** |
| Incoming Tx → | Extract Key | — | 实线 |
| Extract Key → | HT Lookup | — | 实线 |
| HT Lookup → | Slot Set | Hit | 实线 |
| HT Lookup → | Empty Set | Miss | 实线 |

---

## 相比第一版的主要修改

| 问题 | 上一版 | 这一版 |
|------|--------|--------|
| 布局 | 上中下三块≈880px 高 | 左右两栏≈500px 高 |
| 框数总数 | ~16 个 | ~11 个 |
| 框内文字 | 大段描述 + 子细节 | 只剩标题 + 节号 + 一行属性 |
| 字号 | 10pt + 8pt 子描述 | **11pt + 9pt 节号** |
| Historical Data | 独立框，含区块数字 | 去掉（移到 Evaluation） |
| Evaluation Window | 容器内有框 | 去掉（不在 System Design 范围内）|
| Design Properties | 逐条列出 | 简化为两行要点 |
| Pattern Gen + Filter + Merge | 三个独立框 | 合并为一个框 |
