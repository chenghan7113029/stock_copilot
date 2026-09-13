## 1. 数据模型与 Composer



- [x] 1.1 Create `src/service/report/models/briefing_view.py`：`SectionStatus`（ok/missing/failed + hint）、`BriefingView`（Hero、三维摘要、证据、narrative、persona、checklist/declare、section_statuses）

- [x] 1.2 Create `src/service/report/briefing_composer.py`：`BriefingComposer.build(code, *, narrate: bool, config=…)`，复用 DualTrack / EvidenceBucketer / Value / Tech / Sentiment，只组装不重算

- [x] 1.3 Modify composer：`narrate=True` 时调用 confront narrate + persona-stress（共享 confrontation_id）；失败写入 section_statuses，不抛崩整单

- [x] 1.4 Modify composer：只读 ChecklistRepo / ConfrontationRepo 填充决策痕迹；无记录 → missing + hint（含建议命令）

- [x] 1.5 Test `test/service/report/test_briefing_composer.py`：双轨齐全离线组装；双轨皆缺失败；narrate 失败降级；无 declare 仍成功且 hint 含失败/未生成语义



## 2. HTML 渲染器



- [x] 2.1 Create `src/service/report/html_briefing_renderer.py`（+ 可选 `templates/briefing.html.j2`）：`BriefingView` → 自包含 HTML；优先标准库模板，避免不必要新依赖

- [x] 2.2 Modify renderer：研报章节顺序（Hero → 三维快扫 → 冲突与立场 → 价值/技术深潜折叠 → 决策痕迹 → 免责）；内联 CSS

- [x] 2.3 Modify renderer：可视化 MOS/公允区间条、技术评分条、情绪指数条、多空证据条数对比

- [x] 2.4 Modify renderer：failed/missing 区块醒目 callout 展示 hint

- [x] 2.5 Test `test/service/report/test_html_briefing_renderer.py`：含 `<html`、关键章节、可视化标记类名/结构、失败提示文案可见



## 3. CLI



- [x] 3.1 Modify `src/apps/cli.py`：注册 `report briefing`，参数 `--no-narrate` / `--json` / `-o` / `--quiet`；**默认 narrate 启用**

- [x] 3.2 Modify CLI：`-o` 写 HTML；`--json` dump BriefingView；价值+技术皆缺 → 非 0；叙事失败仍 0 + stderr/HTML 提示

- [x] 3.3 Test `test/apps/test_cli_report_briefing.py`：默认 narrate 标志、`--no-narrate`、缺数据退出码、`-o` 写出文件冒烟（mock composer/renderer 可接受）



## 4. 文档



- [x] 4.1 Modify `docs/user-guide.md`：新增 `report briefing` 用法（周末复盘、默认 LLM、`--no-narrate`、仅本地 HTML）

- [x] 4.2 Modify `docs/mrd/roadmap-todo.md`：登记 briefing HTML 能力与变更记录

- [x] 4.3 Modify `docs/dev/engineering-conventions.md`：若新增 report 子文件/模板目录，更新目录表



## 5. 验证与归档



- [x] 5.1 Run `pytest test/service/report/test_briefing_composer.py test/service/report/test_html_briefing_renderer.py test/apps/test_cli_report_briefing.py -q` 并通过
- [x] 5.2 Run `pytest test/ -q -m "not network"` 全量离线门禁并通过（保留输出）
- [x] 5.3 手工：对已 sync 样本股 `report briefing <code> -o reports/<code>_briefing.html`，浏览器打开核对章节/可视化/降级提示
- [x] 5.4 Archive：`openspec archive add-html-briefing-report`（或 `/opsx-archive`），同步 specs；合并要点到 `docs/mrd/` / 必要时 `docs/design/`；确认验证门禁已通过

