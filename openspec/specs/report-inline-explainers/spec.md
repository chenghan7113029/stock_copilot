# report-inline-explainers Specification

## Purpose

报告内嵌讲解：技术指标注释、估值方法卡片、价值陷阱拆解、安全边际百分数点格式化；供 tech/value/dual 文本报告与看板价值区同源复用。

## Requirements

### Requirement: 共享讲解渲染器
系统 SHALL 提供可复用的报告内讲解渲染能力（技术指标注释、估值方法卡片、价值陷阱拆解、安全边际百分数点格式化），供 tech/value/dual 文本报告及看板价值区调用。讲解内容 MUST 仅基于确定性结果中已有字段与静态词典/映射，MUST NOT 调用 LLM 或编造未提供的入参数值。

#### Scenario: 同源复用
- **WHEN** value 报告与 dual 报告均需渲染同一 Applicable 估值方法讲解
- **THEN** 两者 SHALL 调用同一渲染实现，避免两套互不一致的文案

### Requirement: 安全边际百分数点格式化与阈值单位
系统 SHALL 将 `margin_of_safety` 视为百分数点（例如 `7.14` 表示 `7.14%`）。人类可读展示 MUST 使用百分数点格式（例如显示 `7.1%`），MUST NOT 对该字段使用会再次 ×100 的比例格式化（如 Python `:.1%` 作用于百分数点值）。用于价值评级的低估/高估阈值 MUST 使用同一百分数点单位（产品语义保持约 +20% / -10%）。

#### Scenario: 展示与 value 一致
- **WHEN** 同一分析结果的 `margin_of_safety` 约为 `-0.8`
- **THEN** value 报告、dual 摘要与 dashboard 价值区展示的安全边际 SHALL 同为约 `-0.8%` 量级，SHALL NOT 显示为约 `-80%`

#### Scenario: 评级阈值按百分数点
- **WHEN** `margin_of_safety` 为 `25.0`（表示 25%）且配置阈值为百分数点 +20 / -10
- **THEN** 价值评级 SHALL 为低估（UNDERVALUED），SHALL NOT 要求传入 `0.25` 才能触发低估

### Requirement: 估值方法完整卡片
对 applicability 为 Applicable（或等价「适用」）的估值方法，文本讲解 SHALL 包含：方法含义、适用场景、计算公式、本次入参（名称、数值、来源说明）、本次结果（公允价与中文评估）。当 `details` 缺少某入参时，SHALL 标明缺失，MUST NOT 捏造数值。

#### Scenario: Applicable 方法出卡
- **WHEN** 价值结果包含 Applicable 的 `ddm`（或同类）方法且 details 含公式与入参
- **THEN** 讲解输出 SHALL 包含公式与至少一项带来源说明的入参行，以及中文结果评估

### Requirement: 价值陷阱白话拆解
当价值陷阱方法结果存在时，讲解 SHALL 用中文说明总体风险含义，并列出各风险维度等级与说明（含占位维度的人工评估提示）。

#### Scenario: Medium 陷阱可读
- **WHEN** `value_trap` 总体风险为 Medium 且 details 含维度字段
- **THEN** 讲解 SHALL 出现「价值陷阱」中文说明与至少两个维度的中文名称及风险等级
