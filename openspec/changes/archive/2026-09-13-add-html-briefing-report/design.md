## Context

周末深度复盘需要把分散的 Markdown 报告编成一份可读主文档。仓库已有 `DashboardBuilder`/`DashboardView`（短文本汇总）、`ConfrontationNarrator` / `PersonaStressNarrator`、以及完整的 tech/value/sentiment 确定性管线，但**没有 HTML 渲染路径**。本设计在 `service/report/` 增加 Composer + Renderer，CLI 增加 `report briefing`；遵守 apps → service 依赖方向与三层防御（数值只来自确定性模块）。

## Goals / Non-Goals

**Goals:**

- 组装 `BriefingView` 并渲染为**自包含单文件 HTML**（双击浏览器可开）
- 默认开启 LLM 叙事（confront + persona）；`--no-narrate` 仅离线
- 章节化研报风 + 关键数字可视化；深潜默认折叠
- Persona / declare / narrate 失败或缺失时**优雅降级并显式提示**

**Non-Goals:**

- trade-review、portfolio
- 飞书推送、Web 服务、PDF/Docx
- 新算估值/技术指标；LLM 不得改写数值
- 替换现有 `report tech/value/dashboard/...` Markdown 出口

## Decisions

### 决策 1：BriefingComposer 只组装，不重算

**选择：** `BriefingComposer.build(code, *, narrate: bool) -> BriefingView`，内部调用既有 `DualTrackAnalyzer` / `ValueAnalyzer` / `TechAnalyzer` / `SentimentAnalyzer`、`EvidenceBucketer`、`ConfrontationNarrator` / `PersonaStressNarrator`（或等价 CLI 路径逻辑）、`ChecklistRepo` / `ConfrontationRepo` 只读查询。数值字段直接拷贝自既有结果对象。

**理由：** 与 `DashboardBuilder` 同哲学；避免双源数字。

**备选：** 从已落盘 md 反解析 — 拒绝（脆弱、丢结构）。

### 决策 2：默认 narrate=True，失败不整单失败

**选择：** CLI 默认跑 confront narrate + persona-stress narrate（可复用同一次 confrontation_id）。任一步 LLM 失败 → `BriefingView.section_statuses` 记录 `failed`/`missing` + 人类可读 `hint`（含建议命令）；HTML 仍写出，确定性章节完整；命令退出码：**确定性核心成功则为 0**，叙事失败在 HTML/stderr 提示（与 `report summary --narrate` 降级一致）。价值+技术同时无本地数据时仍非 0 退出。

**理由：** Owner 要求默认 LLM；周末也可能只读证据层。

**备选：** 叙事失败 exit 1 — 拒绝（阻碍打开 HTML）。

### 决策 3：章节 IA（周末深度）

固定顺序：

0. Hero（代码/名称/综合信号/数据时点/冲突一句话）  
1. 三维快扫（价值/技术/情绪）— 默认展开 + 可视化  
2. 冲突与立场（编号证据、互驳、Persona）— 默认展开；叙事/Persona 可折叠  
3. 价值深潜 — 默认 `<details>`  
4. 技术深潜（含布林带、K 线形态）— 默认 `<details>`  
5. 决策痕迹（checklist / declare）— 有则展开，无则「未生成」提示块  
6. 附录/免责  

**圈出：** trade-review、portfolio。

### 决策 4：研报风 + 轻量可视化（无前端构建）

**选择：** 单文件 HTML + 内联 CSS；语义化章节标题；可视化用纯 CSS/SVG（无 Chart.js 强制依赖）：

| 数据 | 可视化 |
|------|--------|
| 安全边际 / 价格相对公允区间 | 区间条 + 现价标记 |
| 技术评分 0–100 | 水平进度条 |
| 情绪指数 0–100 | 进度条 + 档位色 |
| 多空证据条数 | 并排条形对比 |
| 综合信号 | 色标徽章 |

**理由：** Owner 要研报风但拒绝纯文字墙；零构建链适合本地导出。

**备选：** CDN 图表库 — 拒绝（离线双击打开不可靠）。

### 决策 5：模块落点与模板

**选择：**

- `src/service/report/models/briefing_view.py` — `BriefingView` / `SectionStatus`
- `src/service/report/briefing_composer.py`
- `src/service/report/html_briefing_renderer.py` + `src/service/report/templates/briefing.html.j2`（若引入 Jinja2）或同文件字符串模板
- `src/apps/cli.py` — `report briefing`

依赖：若 `pyproject.toml` 尚无 Jinja2，优先**标准库字符串替换/简单模板**，避免新依赖；若已有 Jinja2 则用之。

### 决策 6：与 dashboard / Markdown 并存

dashboard 继续做秒级速览；briefing 做半小时主阅读；各 `report *` Markdown 保留给 Agent/git。

## Risks / Trade-offs

- **[风险] 默认 narrate 使周末全量 watchlist 变慢且耗 token** → **缓解：** 文档标明；支持 `--no-narrate`；单票主路径
- **[风险] HTML 过大（方法卡片全文）** → **缓解：** 深潜折叠；方法表默认摘要行，详解进 `<details>`
- **[风险] 降级提示被忽略** → **缓解：** 失败区块用醒目 callout（边框/图标），文案含「失败」字样与建议 CLI
- **[风险] 与飞书/Web 预期混淆** → **缓解：** Non-Goal 写死；user-guide 写「仅本地静态 HTML」

## Migration Plan

- 纯新增命令与模块；无 DB schema 变更（只读既有表）
- 回滚：删除 briefing 模块与 CLI 子命令即可
- 归档后更新 user-guide / roadmap / engineering-conventions 目录表

## Open Questions

- `BriefingView` 是否同时支持 `--json` 导出结构化包（便于日后 Web）？**建议 V1 支持**，与其他 report 对齐。
- 冲突一句话：规则模板（确定性）还是 LLM 一句？**建议 V1 用确定性模板**（综合信号 + 多空条数 + 价值评级），避免又一层幻觉。
