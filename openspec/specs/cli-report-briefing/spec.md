# cli-report-briefing Specification

## Purpose

CLI 入口暴露周末深度复盘 Briefing Pack（默认 HTML；默认启用 LLM 叙事）。

## Requirements

### Requirement: CLI `report briefing` 入口

系统 SHALL 提供 `python -m apps.cli report briefing <code> [--no-narrate] [--json] [--output|-o] [--quiet]`。命令 SHALL 调用 `BriefingComposer` 组装 `BriefingView`，默认将 HTML 渲染结果写到标准输出或 `-o` 指定路径。默认 `narrate` SHALL 为启用（尝试 LLM 互驳与 Persona）；`--no-narrate` SHALL 仅离线组装确定性章节。`--json` SHALL 输出 `BriefingView` 的结构化 JSON（枚举等可序列化），而非 HTML。

#### Scenario: 默认生成 HTML 文件

- **WHEN** 运行 `report briefing 600519 -o reports/600519_briefing.html` 且本地数据充足、可选 LLM 可用或不可用
- **THEN** SHALL 写出 HTML 文件（或在 LLM 失败时仍写出含降级提示的 HTML）
- **THEN** 若价值与技术数据充足，进程退出码 SHALL 为 0

#### Scenario: --no-narrate 不调用 LLM 叙事

- **WHEN** 运行 `report briefing 600519 --no-narrate -o …`
- **THEN** 命令 MUST NOT 依赖成功的 LLM 调用即可完成确定性章节
- **THEN** 输出 HTML SHALL 仍含证据等离线章节

#### Scenario: 无本地双轨数据时非零退出

- **WHEN** 运行 `report briefing <code>` 但本地无价值快照且无可用 K 线
- **THEN** SHALL 向 stderr 打印请先 sync 类错误，退出码非 0，且 MUST NOT 写出伪装完整的成功 HTML

### Requirement: briefing 与现有 Markdown 报告并存

引入 `report briefing` MUST NOT 移除或改变既有 `report tech` / `report value` / `report dashboard` / `report confront` 等命令的默认 Markdown/JSON 行为。

#### Scenario: 既有 report tech 行为不变

- **WHEN** 运行 `report tech 600519`（在 briefing 功能落地后）
- **THEN** 输出 SHALL 仍为技术面 Markdown（或既有 `--json` 行为），MUST NOT 强制改为 HTML
