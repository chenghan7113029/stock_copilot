## MODIFIED Requirements

### Requirement: CLI `report briefing` 入口

系统 SHALL 提供 `python -m apps.cli report briefing <code> [--no-narrate] [--json] [--output|-o] [--quiet]`。命令 SHALL 调用 `BriefingComposer` 组装 `BriefingView`，默认将 HTML 渲染结果写到标准输出或 `-o` 指定路径。默认 `narrate` SHALL 为启用（尝试 LLM 互驳与 Persona）；`--no-narrate` SHALL 仅离线组装确定性章节。`--json` SHALL 输出 `BriefingView` 的结构化 JSON（枚举等可序列化），而非 HTML。默认 HTML 输出 SHALL 符合 `html-briefing-report` 的价格情境、多空左右分栏、可点击讲解与冷静金融版式要求（命令参数面不变）。

#### Scenario: 默认生成 HTML 文件

- **WHEN** 运行 `report briefing 600519 -o reports/600519_briefing.html` 且本地数据充足、可选 LLM 可用或不可用
- **THEN** SHALL 写出 HTML 文件（或在 LLM 失败时仍写出含降级提示的 HTML）
- **THEN** 若价值与技术数据充足，进程退出码 SHALL 为 0
- **THEN** HTML SHALL 含价格情境相关结构（有 K 线时）及加宽版心样式

#### Scenario: --no-narrate 不调用 LLM 叙事

- **WHEN** 运行 `report briefing 600519 --no-narrate -o …`
- **THEN** 命令 MUST NOT 依赖成功的 LLM 调用即可完成确定性章节
- **THEN** 输出 HTML SHALL 仍含证据等离线章节与价格情境（若有 K 线）

#### Scenario: 无本地双轨数据时非零退出

- **WHEN** 运行 `report briefing <code>` 但本地无价值快照且无可用 K 线
- **THEN** SHALL 向 stderr 打印请先 sync 类错误，退出码非 0，且 MUST NOT 写出伪装完整的成功 HTML
