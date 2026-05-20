# Patent Figure Beautification Prompts

Use these prompts with ChatGPT (GPT-4o image generation/editing) or similar tools.
Upload each PNG alongside its prompt. All images should retain original Chinese text labels.

---

## Fig 1 — Architecture Diagram

**File**: `patent_fig1_architecture.png`

```
Please enhance this architecture diagram while keeping its layout and
structure intact. The image describes a "Hybrid EVM Storage Prefetch
Architecture with Online/Offline Duty Separation".

What to PRESERVE:
- The two-section layout: "在线路径（交易执行关键路径）" (top green area)
  and "离线路径（定期批量执行）" (bottom orange area), separated by a
  dashed divider line
- The exact flow:
  Online: [待处理交易] → [快路径哈希表] → [预测 slot 集合]
  Offline: [Window A 数据] → [慢路径 LightGBM] → [候选增量生成] →
           [Window B 评估] / [合并增量到快路径哈希表]
- The left-side blue feedback arc arrow labeled "增量规则补充" looping
  from Offline back to Online
- The same color palette: green tones (#E8F5E9 series) for Online,
  orange/amber tones (#FFF3E0 series) for Offline, dark blue (#0D47A1)
  for the feedback arrow
- The original Chinese text labels — do NOT translate them

What to FIX:
1. ALL text inside the rounded boxes is TOO SMALL and TOO FAINT.
   Increase font size significantly (at least 2-3x larger) and make it
   bold and deep black (#000000) so it is clearly readable at a glance.
   This is the most critical fix.
2. Make box border strokes crisper and slightly thicker (3-4px)
3. Add subtle drop shadows behind boxes for a polished, modern look
4. Make section header labels ("在线路径..." and "离线路径...")
   larger and bolder than box text
5. Ensure arrow heads are clearly visible and proportional to the line
   weight
6. Add slightly more padding inside boxes so text doesn't feel cramped

Style goal: Clean, modern, professional — suitable for a patent
application or top-tier academic paper figure. Minimalist aesthetic but
every text element must be crisp, bold, and instantly legible.
```

---

## Fig 2 — Pipeline Flowchart

**File**: `patent_fig2_pipeline.png`

```
Please enhance this five-step pipeline flowchart while preserving its
structure. The image shows an "Offline Delta Pipeline" for supplementing
a blockchain storage prefetch hash table.

What to PRESERVE:
- The left-to-right five-step flow: ① → ② → ③ → ④ → ⑤
- The exact step labels:
  ① 加载模型与数据 (Hybrid模型 + JSONL Trace)
  ② 切分时间窗口 Window A / B
  ③ 生成候选增量 slow-path预测 × 正确交集
  ④ 过滤与合并 min_support + max_slots
  ⑤ Window B 评估 rule_base vs rule_delta
- The description text below each step number
- The color coding per step: blue #E3F2FD, green #E8F5E9, orange
  #FFF3E0, pink #FCE4EC, purple #F3E5F5
- The statistics footer line at the bottom
- The original Chinese text — do NOT translate

CRITICAL — Arrow direction MUST be preserved:
The pipeline flows LEFT TO RIGHT: ① → ② → ③ → ④ → ⑤. Arrows MUST
point from left to right (from the right edge of one box to the left
edge of the next box). If any arrow points right-to-left, that is a
bug and must be corrected.

What to FIX:
1. ALL text inside the step boxes is TOO SMALL. Increase font size
   significantly (2-3x). Step titles should be bold and prominent.
   Descriptions should be clearly readable.
2. Make the circled numbers (①②③④⑤) much larger and bolder
3. Make the connecting arrows thicker and more visible (3-4px).
   Double-check every arrow points LEFT→RIGHT.
4. Add subtle shadows or depth to each step box for visual polish
5. Ensure consistent padding inside all five boxes
6. Make the footer statistics text larger and bolder

Style goal: Clean infographic style — each step visually distinct,
text instantly readable, suitable for a patent figure or conference
poster.
```

---

## Fig 3 — Comparison Bar Chart

**File**: `patent_fig3_comparison.png`

```
Please enhance this four-panel grouped bar chart comparing "rule_base"
vs "rule+Δ" (offline delta enhanced) on blockchain storage prefetch
metrics. The four panels show: Recall, Precision, Total Cost, and
Speedup vs rule_base.

What to PRESERVE:
- The 4-panel layout (Recall, Precision, Total Cost, Speedup)
- The blue (#1f77b4) and green (#2ca02c) color scheme for rule_base
  and rule+Δ bars respectively
- The exact data values shown above each bar
- The percentage change annotations (e.g., +40.2%, -12.7%, -11.3%,
  +12.7%) with their red/green coloring
- The chart title and axis labels
- The original text — do NOT translate

What to FIX:
1. Make ALL axis labels, tick labels, and bar value annotations larger
   and bolder — currently they are too small
2. Make the percentage change callouts more prominent (larger font,
   heavier weight)
3. Add subtle grid lines for easier value reading
4. Enhance bar colors to be more vibrant and publication-quality
5. Make the chart title larger and more prominent
6. Add a subtle background or bounding box to unify the four panels
7. Ensure consistent font sizes across all four subplots

Style goal: Publication-quality academic bar chart — clean, precise,
with data immediately readable at a glance.
```

---

## Fig 4 — Scale Consistency Curve

**File**: `patent_fig4_scale.png`

```
Please enhance this dual-axis line chart showing scale consistency of
the offline delta pipeline. Left y-axis (green): Recall improvement %,
Right y-axis (blue): Cost reduction %. X-axis: data scale (2K, 10K,
94K transactions).

What to PRESERVE:
- The dual y-axis layout (green left, blue right)
- The three x-axis points: "2K", "10K", "94K (full)"
- The data values: Recall +27.4%→+35.7%→+40.2%, Cost -7.8%→-10.9%→
  -11.3%
- The monotonic upward trend that demonstrates scale consistency
- The annotation labels below each data point (block/tx counts)
- The chart title and axis labels
- The original text — do NOT translate

What to FIX:
1. Make ALL text elements larger and bolder — axis labels, tick labels,
   data point annotations, and the legend
2. Make the two curves thicker (3-4px) and more visually distinct
3. Make data point markers larger and more prominent
4. The annotation text below each point (block/tx info) is particularly
   small — increase it significantly
5. Enhance the legend to be more visible with a subtle background box
6. Make the chart title larger and bolder
7. Add a light grid for easier trend reading

Style goal: Clean, modern line chart suitable for a journal paper or
patent application — the key message ("monotonic improvement with
scale") should be visually obvious.
```

---

## Abstract Figure

**File**: `patent_abstract_figure.png`

```
Please enhance this summary figure for a patent abstract. It combines
a simplified architecture diagram (left) with key experimental results
(right). The invention is a "Hybrid EVM Storage Prefetch Method with
Online/Offline Duty Separation".

What to PRESERVE:
- The two-column layout: Architecture diagram (left) + Results data
  cards and comparison table (right)
- Left side: "在线路径" (green) and "离线路径（定期执行）" (orange)
  sub-sections with the blue "增量补充" feedback loop
- Right side data cards: +40.2% Recall, -11.3% Cost, 253 keys/2,641
  slots, 94,463 txs/999 blocks
- The comparison table showing rule_base vs rule_+Δ results
- The "缩放一致性" annotation and the bottom tagline
- The original Chinese text — do NOT translate

What to FIX:
1. ALL text is TOO SMALL. Increase font size throughout by 2-3x.
   This applies to box labels, data cards, table text, annotations,
   and the bottom tagline.
2. Make the architecture boxes on the left more prominent — thicker
   borders, subtle shadows, larger internal text
3. The data cards on the right should be visually striking — larger
   numbers, bolder colors, more padding
4. The comparison table text is nearly unreadable — make it much larger
   and use a clean tabular layout with proper spacing
5. Make the "增量补充" feedback arrow thicker and more visible
6. Add subtle section dividers or background tints to separate the
   architecture and results areas

Style goal: Patent-quality abstract figure — the core idea
(online/offline separation) and key results (+40% recall, -11% cost)
should be graspable in 5 seconds.
```
