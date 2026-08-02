## ADDED Requirements

### Requirement: report tech 默认 Markdown 文本与 .md 落盘约定
`report tech` 在非 `--json` 时的人类可读输出 SHALL 为 Markdown（见 `report-markdown-output`）。文档与批量 `-o` 目录默认文件名 SHALL 使用 `{code}_tech.md`。

#### Scenario: 批量 tech 写 md
- **WHEN** 用户执行 `report tech --watchlist -o reports/out`（非 `--json`）
- **THEN** 输出文件扩展名 SHALL 为 `.md`
