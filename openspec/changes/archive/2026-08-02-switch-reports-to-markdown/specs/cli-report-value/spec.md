## ADDED Requirements

### Requirement: report value 默认 Markdown 文本与 .md 落盘约定
`report value` 在非 `--json` 时的人类可读输出 SHALL 为 Markdown（见 `report-markdown-output`），并保留默认嵌入的估值方法讲解与价值陷阱说明。批量 `-o` 目录默认文件名 SHALL 使用 `{code}_value.md`。

#### Scenario: 批量 value 写 md
- **WHEN** 用户执行 `report value --watchlist -o reports/out`（非 `--json`）
- **THEN** 输出文件扩展名 SHALL 为 `.md`，且文本中仍含方法讲解相关要素（若存在 Applicable 方法）
