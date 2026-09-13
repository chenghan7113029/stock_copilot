## ADDED Requirements

### Requirement: 价格情境区块（10 交易日）

系统 SHALL 在 Briefing HTML 的 Hero 之后、三维快扫之前渲染 **价格情境** 区块。`BriefingView` SHALL 携带现价与最近至多 **10 个交易日**的收盘序列（来自本地 K 线缓存，按交易日升序）。渲染 SHALL 使用自包含 SVG（或等价内联矢量），MUST NOT 依赖外部 CDN。当公允区间（fair_low / fair_base / fair_high）可用时，图上 SHALL 以虚线标出这三档价位；对序列内最高与最低收盘价 SHALL 有可见标注。K 线不足或缺失时，SHALL 降级展示（可得点数或明确 missing hint），MUST NOT 因此使整个 briefing 失败（若价值/技术核心仍可用）。

#### Scenario: 有 10 日 K 线与公允区间时画出折线与虚线

- **WHEN** 本地至少有 10 个交易日收盘且 fair_low/base/high 可用
- **THEN** HTML 价格情境区 SHALL 含近 10 点折线、三条公允虚线，以及最高/最低点标注
- **THEN** 该区块位于 Hero 之后、三维快扫之前

#### Scenario: K 线不足时降级

- **WHEN** 本地可交易日收盘少于 10 但不少于 1
- **THEN** SHALL 仍渲染可得序列的折线（可附 hint 说明不足 10 日）
- **THEN** briefing 整体 MUST 仍可成功输出（核心数据可用时）

### Requirement: 冲突与立场左右分栏

在桌面宽度下，冲突与立场中的多方/空方证据列表 SHALL 左右并排展示（多方在左、空方在右）。互驳叙事与 Persona 区块 SHALL 置于证据分栏下方且全宽。窄视口下允许堆叠为单列，但 MUST NOT 改变证据编号语义。

#### Scenario: 桌面双栏证据

- **WHEN** 在足够宽的视口打开 briefing HTML
- **THEN** 多方与空方证据区域 SHALL 呈左右两栏布局
- **THEN** 互驳叙事（若存在）SHALL 出现在证据区域下方

### Requirement: 可点击术语/方法讲解

价值深潜中各估值方法标识旁、以及技术深潜中出现的关键术语旁，系统 SHALL 提供可点击的「？」控件；点击后 SHALL 展示该方法/术语的说明与适用场景文案。讲解内容 MUST 来自 `service/report/explainers` 既有词典（或对其的补充词条），MUST NOT 由 LLM 现场生成。打开 HTML 时 MUST NOT 依赖外部脚本 CDN。

#### Scenario: 点击估值方法问号可见说明

- **WHEN** 用户点击某估值方法旁的「？」
- **THEN** SHALL 可见包含该方法含义与适用场景的说明文本

#### Scenario: 点击技术术语问号可见说明

- **WHEN** 技术深潜中某术语旁存在「？」且用户点击
- **THEN** SHALL 可见该术语的说明与应用场景文本

### Requirement: 冷静金融视觉与版心宽度

Briefing HTML 的主内容容器最大宽度 SHALL 约为 **1240px**（允许实现取 1200–1280 合理值，默认目标 1240）。视觉风格 SHALL 为冷静金融桌面风：浅色纸面、冷灰正文、克制蓝强调色、克制红/绿区分多空；MUST NOT 以米黄宋体旧研报皮肤作为默认主题。仍 MUST 为自包含单文件（内联 CSS）。

#### Scenario: 版心加宽

- **WHEN** 打开 briefing HTML
- **THEN** 主内容区 CSS max-width SHALL 不小于 1200px 且目标为约 1240px

#### Scenario: 仍无外部图表 CDN

- **WHEN** 打开 briefing HTML 源码
- **THEN** MUST NOT 依赖 chart.js 等外部 CDN 才能显示价格折线与样式
