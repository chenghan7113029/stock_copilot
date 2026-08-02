## ADDED Requirements

### Requirement: report dual 默认 Markdown 文本与 .md 落盘约定
`report dual` 在非 `--json` 时的人类可读输出 SHALL 为 Markdown（见 `report-markdown-output`）：多方/空方证据与价值面/技术面讲解分区 SHALL 使用 Markdown 标题区分。批量 `-o` 目录默认文件名 SHALL 使用 `{code}_dual.md`。`--json` 输出 MUST 仍包含 `bull_evidence` / `bear_evidence`。

#### Scenario: 批量 dual 写 md
- **WHEN** 用户执行 `report dual --watchlist -o reports/out`（非 `--json`）
- **THEN** 输出文件扩展名 SHALL 为 `.md`，且文本中可用 Markdown 标题识别证据区或讲解区

#### Scenario: dual JSON 契约不变
- **WHEN** 用户执行 `report dual <code> --json`
- **THEN** 输出 SHALL 仍包含 `bull_evidence` 与 `bear_evidence` 字段
