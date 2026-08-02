## ADDED Requirements

### Requirement: report summary 默认 Markdown 文本与 .md 落盘约定
`report summary` 在非 `--json` 时的人类可读输出（含可选 `--narrate` 追加段）SHALL 为 Markdown（见 `report-markdown-output`）。批量 `-o` 目录默认文件名 SHALL 使用 `{code}_summary.md`。

#### Scenario: 批量 summary 写 md
- **WHEN** 用户执行 `report summary --watchlist -o reports/out`（非 `--json`）
- **THEN** 输出文件扩展名 SHALL 为 `.md`
