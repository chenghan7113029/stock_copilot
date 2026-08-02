# 报告内嵌讲解（report-inline-explainers）

> 对应 OpenSpec：`add-report-inline-explainers`

## 目的

让 `report tech` / `value` / `dual` 文本报告默认自带说明书：技术指标注释、估值方法卡片、价值陷阱拆解；并统一安全边际为百分数点展示。

## 模块

- `src/service/report/explainers.py`：词典与渲染（`format_mos_percent_points`、`render_tech_explanations`、`render_value_method_card`、`render_value_trap_explainer`）
- `src/apps/formatters.py`：编排调用；dual JSON 不附讲解正文以保持 Skill 契约轻量

## MOS 约定

`ValueAnalysisResult.margin_of_safety` 为百分数点（`7.14` → `7.14%`）。  
`DualTrackConfig` 低估/高估阈值为 `20.0` / `-10.0`（同一单位）。禁止对 MOS 使用 `:.1%`。

## 默认开启

本期不提供 `--concise`；需要精简时后置。
