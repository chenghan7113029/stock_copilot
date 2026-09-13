# html-briefing-report Specification

## Purpose

周末深度复盘 Briefing Pack：组装 `BriefingView` 并渲染为自包含 HTML（只编排不重算；默认 LLM 叙事可优雅降级）。

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

`BriefingView` / 渲染输出的章节 SHALL 覆盖：Hero、三维快扫、冲突与立场（证据 + 可选叙事 + 可选 Persona）、价值深潜、技术深潜（含布林带与 K 线形态字段若存在）、决策痕迹（Checklist/declare）、免责声明。系统 MUST NOT 在 V1 将 `trade-review` 或 `portfolio` 纳入 briefing 必选章节。

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
