## Why

单票分析已拆成多份 Markdown（tech / value / dual / confront / persona / dashboard 等），周末深度复盘时阅读成本高：内容分散、纯文本堆叠、难一眼抓住冲突与关键数字。需要一份**本地静态 HTML Briefing Pack**：重组既有确定性结果（及可选 LLM 叙事）为研报风、可跳读、可可视化的深度复盘主阅读物——不替代 CLI Markdown，也不做 Web/飞书推送。

## What Changes

- 新增 CLI：`report briefing <code> [-o file.html] [--no-narrate] [--json]`（**默认启用 LLM 叙事**：confront + persona-stress；`--no-narrate` 仅离线组装）
- 新增 `BriefingComposer`：组装 `BriefingView`（只编排、不重算数值），来源含价值/技术/情绪摘要、编号红蓝证据、互驳叙事、Persona、Checklist/declare 摘要
- 新增 `HtmlBriefingRenderer`：输出**自包含单文件 HTML**（内联 CSS；研报章节风 + 关键数字可视化：进度条/区间条/多空对比等；深潜区默认 `<details>` 折叠）
- Persona / declare / narrate **缺失或失败时优雅降级**：对应区块仍输出，并显式提示「此处失败/未生成」及建议命令；不中断整份 briefing
- **不包含**：trade-review、portfolio、飞书推送、Web/API 服务端；数值不以 LLM 为准

## Capabilities

### New Capabilities

- `html-briefing-report`：BriefingView 组装契约、章节信息架构、HTML 渲染与降级提示语义
- `cli-report-briefing`：CLI `report briefing` 入口、默认 narrate、输出路径与退出码行为

### Modified Capabilities

- （无）既有 `cli-report-*` / dashboard / confront 的对外 Markdown 契约不变；briefing 为新增出口

## Impact

- **新增模块（建议）**：`src/service/report/briefing_composer.py`、`src/service/report/models/briefing_view.py`、`src/service/report/html_briefing_renderer.py`（或 `templates/briefing.html.j2`）
- **修改**：`src/apps/cli.py`（子命令）、可选 `src/apps/formatters.py`（若 JSON dump 复用）
- **依赖**：优先标准库 + 既有 Jinja2（若项目已有）或纯字符串模板；**不新增**前端构建链；LLM 复用既有 `llm:` / narrate 管线
- **文档**：归档后更新 `docs/mrd/roadmap-todo.md`、`docs/user-guide.md`、`docs/mrd/product-overview.md`（综合呈现）；若新增 `service/report` 子模块说明则更新 `docs/dev/engineering-conventions.md` 目录表
- **测试**：composer 组装/降级单测、renderer 冒烟（含关键区块与失败提示文案）、CLI 参数默认值；门禁 `pytest -q -m "not network"`
