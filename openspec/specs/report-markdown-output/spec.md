# report-markdown-output Specification

## Purpose

报告默认落盘为 Markdown，人类可读 formatters 输出可渲染 Markdown 结构；JSON 契约不变。

## Requirements

### Requirement: 默认落盘扩展名为 Markdown
对 `report` / 同类离线报告在 `--watchlist` 且 `-o` 为目录时，系统 SHALL 将人类可读报告写入 `{code}_{kind}.md`（或组合报告约定的等价 `.md` 文件名）。当用户传入的 `-o` 路径已带有 `.md` / `.txt` / `.json` 后缀时，SHALL 按该路径写入，不得强行改写后缀。`--json` 模式下批量落盘 SHALL 继续使用 `.json`（若实现区分 kind 与 json）。

#### Scenario: watchlist 目录默认 md
- **WHEN** 用户执行 `report tech --watchlist -o reports/out`（非 `--json`）
- **THEN** 每只股票 SHALL 生成形如 `reports/out/{code}_tech.md` 的文件

#### Scenario: 显式 txt 路径仍可用
- **WHEN** 用户执行 `report tech 600519 -o reports/600519_tech.txt`
- **THEN** 内容 SHALL 写入该 `.txt` 路径（内容可为 Markdown 文本），不得改写为 `.md`

### Requirement: 人类可读输出为可渲染 Markdown
`format_*_report(..., as_json=False)`（及 checklist 文本模式等同类人类可读格式化）SHALL 返回以 Markdown 结构组织的字符串：至少使用一级标题表示报告名，使用二级（或更细）标题区分主要区块，列表项使用 Markdown 列表语法。输出 MUST 仍包含各报告既有的关键业务字段与讲解内容（若该报告类型已默认嵌入讲解）。`as_json=True` 时行为 MUST 保持既有 JSON 契约，不得因本能力改变字段名。

#### Scenario: 技术面 Markdown 标题
- **WHEN** 调用 `format_tech_report(result, as_json=False)`
- **THEN** 返回字符串 SHALL 包含以 `# ` 开头的报告标题行，且包含综合评分或信号等既有关键词

#### Scenario: JSON 模式不受影响
- **WHEN** 调用任一 `format_*_report(..., as_json=True)`
- **THEN** 返回值 SHALL 为可 `json.loads` 的字符串，且既有核心字段仍存在
