# Slide Deck Outline: 入库成本核算系统

**Source**: Direct input
**Style**: corporate
**Audience**: executives
**Language**: zh
**Slide Count**: 8 slides
**Generated**: 2026-03-03 17:30

---

<STYLE_INSTRUCTIONS>
Design Aesthetic: Professional, clean, structured business presentation
Background Color: Clean white (#FFFFFF) with navy blue header bars
Primary Font: Inter (headlines)
Secondary Font: Source Sans Pro (body)
Color Palette:
  Primary Text Color: #1E3A5F (deep navy)
  Primary Accent Color: #C9A227 (gold)
Visual Elements: Clean charts, structured grids, professional icons, gold divider lines, subtle shadows
</STYLE_INSTRUCTIONS>

---

## Slide 1: 入库成本核算系统

**Position**: Cover
**Filename**: 01-cover.png

// NARRATIVE GOAL
Establish the system's purpose as an intelligent, data-driven cost management platform for warehouse inbound operations.

// KEY CONTENT
Headline: 入库成本核算系统
Sub-headline: 智能化 · 多维度 · 全流程成本管控
Body:
- 实时同步飞书排班与运单数据
- 三类成本自动归集与分流向分摊
- 看板可视化驱动管理决策

// VISUAL
Large navy background with bold white headline. Gold accent line below headline. Abstract warehouse/logistics icons in background (boxes, arrows, dollar signs). Professional and commanding.

// LAYOUT
Full-bleed navy cover, headline centered top-third, gold divider, sub-headline below, body bullets bottom-third left-aligned with gold dots.

---

## Slide 2: 系统功能总览

**Position**: Content
**Filename**: 02-overview.png

// NARRATIVE GOAL
Give executives a quick map of the 3 modules before diving into details.

// KEY CONTENT
Headline: 三大功能模块，覆盖核算全生命周期
Body:
- 📊 成本看板：历史趋势折线图、成本构成饼图，一屏掌握全局
- 🔢 数据采集与核算：同步飞书数据 → 预览计算 → 保存归档
- 📋 核算报表明细：按流向查询历史核算记录，支持导出 CSV

// VISUAL
Three-column card layout, each card with an icon, navy header, and bullet points. Gold divider lines between cards.

// LAYOUT
Three equal-width cards in a row, white background with navy card headers, gold accent border-left on each card.

---

## Slide 3: 数据来源（三类）

**Position**: Content
**Filename**: 03-data-sources.png

// NARRATIVE GOAL
Show where the raw data comes from — all automated from external systems.

// KEY CONTENT
Headline: 数据全部来自外部系统，自动同步
Body:
- 飞书排班表：每人每天工时 → 计时工资（正班 + 1.5倍加班）
- 飞书运单表：各目的地装车票数 → 运输费率关联计算
- Gofo 计件系统：操作件数 × 配置单价 → 计件工资

// VISUAL
Flow diagram: three data source boxes (Feishu Schedule, Feishu Waybill, Gofo) with arrows pointing into a central "Cost Accounting Engine" box. Each source box has an icon.

// LAYOUT
Horizontal flow left-to-right, source boxes in a row with connecting arrows, central engine box highlighted in navy.

---

## Slide 4: 人工费用计算

**Position**: Content
**Filename**: 04-labor-cost.png

// NARRATIVE GOAL
Explain the two-type labor cost calculation — timed and piece-rate.

// KEY CONTENT
Headline: 人工费用 = 计时工资 + 计件工资
Body:
- 计时：每人实际工时，超出 8 小时部分按 1.5 倍时薪结算
  - 外包商时薪如 AAS $19/hr，GF $19/hr 等，分公司汇总
- 计件：操作件数 × 配置费率
  - AAS Sorter 6（人工分拣）$0.12/件
  - 其他分拣机操作员 $0.095/件

// VISUAL
Split panel: left shows a clock/hours chart with regular vs OT bars, right shows piece-rate formula with icons for workers and boxes.

// LAYOUT
Two-column layout, dividing line in gold, formulas in highlighted boxes, example values in navy.

---

## Slide 5: 运输与耗材成本

**Position**: Content
**Filename**: 05-transport-consumable.png

// NARRATIVE GOAL
Explain how transport fees and consumable costs are calculated and attributed.

// KEY CONTENT
Headline: 运输成本直接归因流向，耗材按票数比例分摊
Body:
- 运输成本：费率表 × 各流向票数（直接归因，无需分摊）
  - 各目的地单独费率，如 LAX、DFW、ORD 等
- 耗材成本：出库记录数量 × 采购单价
  - 按各流向票数占比进行比例分摊
  - 支持均摊或权重配置两种模式

// VISUAL
Left: bar chart showing transport cost by direction. Right: pie chart showing consumable allocation across directions.

// LAYOUT
Two-column layout. Left transport section with dark navy bar chart. Right consumables with gold-accented pie. Gold divider line between.

---

## Slide 6: 核算汇总逻辑（流向分摊）

**Position**: Content
**Filename**: 06-allocation.png

// NARRATIVE GOAL
Show the final allocation formula that produces unit cost per direction.

// KEY CONTENT
Headline: 单票成本 = 总成本 ÷ 该流向票数
Body:
- 各流向总成本 = 运输成本 + 分摊人工 + 分摊耗材
- 人工/耗材分摊系数 = 该流向票数 / 全部流向总票数
- 单票成本用于流向间横向比较与定价参考

// VISUAL
Formula breakdown diagram: boxes showing "运输" + "人工×比例" + "耗材×比例" summing into "该流向总成本" → divided by "票数" → "单票成本 $/件". Clean flowchart style.

// LAYOUT
Center-aligned formula flow with gold arrows, each cost component in a colored box, final result highlighted in navy with large font.

---

## Slide 7: 可视化看板

**Position**: Content
**Filename**: 07-dashboard.png

// NARRATIVE GOAL
Demonstrate the management value of the dashboard — insight at a glance.

// KEY CONTENT
Headline: 成本看板：数据一目了然
Body:
- 折线图：各流向单票成本历史趋势，支持缩放与数据悬停
- 饼图：最近核算周期成本构成（运输 / 人工 / 耗材）
- 柱图：各流向总核算成本对比
- 暗色系主题，专业商务风格

// VISUAL
Mock dashboard screenshot with three charts: a line chart top-full-width, bottom-left pie, bottom-right bar chart. Dark navy background with glowing lines.

// LAYOUT
Dashboard card layout, full width top chart, two smaller cards bottom row, gold axis labels, white chart lines on dark bg.

---

## Slide 8: 系统价值与展望

**Position**: Back Cover
**Filename**: 08-back-cover.png

// NARRATIVE GOAL
Close with the measurable impact and a forward-looking statement.

// KEY CONTENT
Headline: 从手工表格到自动化核算，成本透明是优化的起点
Body:
- 数据自动同步，核算周期从数天压缩至分钟级
- 历史数据永久保留，支持跨期趋势分析
- 可在无飞书账号的环境中基于本地主数据运行

// VISUAL
Full navy background like cover. Abstract upward trend line in gold, small data visualization graphics in background. Bold closing statement centered.

// LAYOUT
Full-bleed navy, headline centered large white text, gold trend line graphic, body bullets bottom with gold bullet markers.
