# html-briefing-report Specification

## Purpose

周末深度复盘 Briefing Pack：组装 `BriefingView` 并渲染为自包含 HTML（只编排不重算；默认 LLM 叙事可优雅降级；冷静金融桌面版式）。

## Requirements

### Requirement: BriefingView 组装契约（只编排不重算）

系统 SHALL 提供 `BriefingComposer.build(code: str, *, narrate: bool) -> BriefingView`。`BriefingView` SHALL 包含至少：Hero 元数据（code、名称、综合信号、数据时点、冲突摘要）、价值/技术/情绪摘要字段、编号多方/空方证据、可选互驳叙事、可选 Persona 结果、Checklist/declare 摘要、以及 `section_statuses`（各可选区块的 `ok` / `missing` / `failed` 与 `hint`）。所有价格、评分、MOS、证据原文等数值/证据文本 MUST 来自既有确定性分析或已落库 confrontation evidence；Composer MUST NOT 重新计算估值或技术指标，MUST NOT 用 LLM 改写数值。

#### Scenario: 本地价值与技术数据均可用时产出完整确定性章节

- **WHEN** 调用 `build(code, narrate=False)` 且本地已有价值快照与 K 线缓存
- **THEN** 返回的 `BriefingView` SHALL 含非空 Hero、价值摘要、技术摘要，以及非空的多方或空方证据列表之一（或二者）
- **THEN** `section_statuses` 中价值/技术核心章节 SHALL 为 `ok`

#### Scenario: 价值与技术同时缺失时失败

- **WHEN** 调用 `build(code, …)` 且本地既无价值快照又无可用 K 线
- **THEN** SHALL 抛出或返回与 `report dual` 一致的「请先 sync」类错误，且 MUST NOT 写出假装完整的 briefing

### Requirement: 默认 LLM 叙事与优雅降级提示

当 `narrate=True` 时，系统 SHALL 尝试生成 confront 互驳叙事与 persona-stress 三镜头，并写入 `BriefingView`。若 LLM 未配置、调用失败、或 grounded 校验失败，系统 SHALL 仍返回可用的确定性章节，并将对应 `section_statuses` 标为 `failed` 或 `missing`，`hint` MUST 含明确失败/未生成说明与建议补救命令（例如配置 `llm:` 或 `report confront --narrate`）。Persona 或 declare 记录不存在时，系统 SHALL 同样降级并提示，MUST NOT 因可选区块缺失而使整个 `build` 失败。

#### Scenario: narrate 失败时确定性内容仍可用

- **WHEN** `build(code, narrate=True)` 且 LLM 叙事失败
- **THEN** `BriefingView` SHALL 仍含编号证据等确定性字段
- **THEN** 互驳叙事对应 status SHALL 为 `failed`，且 `hint` 含「失败」或等价字样

#### Scenario: 无 declare 记录时显式提示

- **WHEN** `build(code, …)` 且该票无成功 `confront declare` 记录可展示
- **THEN** 决策痕迹中 declare 区块 status SHALL 为 `missing`
- **THEN** `hint` SHALL 提示可通过 `confront declare` 补齐，且整体 build MUST 成功

### Requirement: 章节范围（周末深度复盘）

`BriefingView` / 渲染输出的章节 SHALL 覆盖：Hero、价格情境、三维快扫、冲突与立场（证据 + 可选叙事 + 可选 Persona）、价值深潜、技术深潜（含布林带与 K 线形态字段若存在）、决策痕迹（Checklist/declare）、免责声明。系统 MUST NOT 在 V1 将 `trade-review` 或 `portfolio` 纳入 briefing 必选章节。

#### Scenario: 圈出组合与交易复盘

- **WHEN** 生成 briefing
- **THEN** 输出 MUST NOT 要求存在交易复盘或组合集中度数据才能成功
- **THEN** 主章节标题集合 MUST NOT 以交易复盘/组合报告为必选章

### Requirement: 自包含 HTML 渲染与可视化

系统 SHALL 提供将 `BriefingView` 渲染为**单一自包含 HTML 文档**的能力（样式内联或嵌入；打开时 MUST NOT 依赖外部构建步骤）。视觉风格 SHALL 为研究报告章节结构；对安全边际/公允区间相对位置、技术评分、情绪指数、多空证据条数等关键标量，渲染器 SHALL 提供非纯文本的可视化（例如区间条、进度条或并排条形），不得仅用大段无结构的纯文字堆叠呈现这些字段。价值/技术深潜默认 SHALL 可折叠。`section_statuses` 为 `failed`/`missing` 的区块 SHALL 在 HTML 中以醒目提示块展示 `hint`。

#### Scenario: 输出可本地打开的单文件 HTML

- **WHEN** 对有效 `BriefingView` 调用 HTML 渲染
- **THEN** 结果 SHALL 为完整 HTML 文档字符串或文件内容，含 `<html` 与内联/嵌入样式
- **THEN** 文档 SHALL 含 Hero 与三维快扫区域

#### Scenario: 失败区块可见

- **WHEN** `BriefingView` 中某可选章节 status 为 `failed`
- **THEN** HTML 中对应区域 SHALL 可见显示该章节的失败提示文案（含 hint）

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
