## Why

`product-overview.md` §5.3 将「多维立体看板」列为 P0 综合呈现能力（PO-01）：单票一页呈现价值 + 技术 + 情绪 + 综合摘要；§7 的 PO-08 则要求「Web/CLI：发起分析、看板、Checklist、红蓝对抗」的对外交互入口。当前 `DualTrackAnalyzer` 已能产出价值面 + 技术面的确定性结果与融合信号，但用户仍需分别运行 `report tech`/`report value`/`report dual` 三个命令并自行在脑中拼装，没有「一页看完」的单一入口；情绪面（PO-06）与 Checklist（PO-04）尚未实现，看板必须能在维度缺失时优雅降级而不整体报错。

`docs/mrd/roadmap-todo.md` §5 阶段 G 将「Web 看板」列为待立项项，但明确依赖「前述 API 与报告形态稳定」。当前产品仍是 CLI-first（Web/REST API 均未建），因此本 change 先交付 CLI 版单页看板，把 PO-01 与 PO-08 的 CLI 部分合并落地；PO-08 的 Web 部分显式推迟。

## What Changes

- 新增 `DashboardBuilder`（`src/service/report/`）：编排 `DualTrackAnalyzer.analyze_offline()` 的结果 + `EvidenceBucketer` 的证据要点计数，拼装为单票「一页汇总」的看板数据结构，内部不重新计算任何数值，只做展示态编排
- 新增维度可用性检测：情绪面（依赖未来 `add-sentiment-module`）与 Checklist（依赖未来 `add-decision-checklist`）未实现时，看板对应分区输出「待建」占位文案，不影响价值面/技术面分区正常展示
- 新增 CLI 入口 `python -m apps.cli report dashboard <code> [--json] [--output] [--quiet]`：严格离线（复用既有 `report` 命令族的离线原则），聚合展示价值 + 技术 + 情绪（占位）+ Checklist（占位）+ 综合摘要
- 新增 `src/apps/formatters.py::format_dashboard_report()`：文本/JSON 两种输出，与 `format_tech_report`/`format_value_report`/`format_dual_report` 风格一致

**不包含（明确推迟）：**
- 不包含 Web 看板（PO-08 的 Web 部分）：待 REST API 就绪后单独立项，本 change 只交付 CLI 文本增强报告
- 不包含情绪面数据接入（依赖未来 `add-sentiment-module`，本 change 只预留展示占位）
- 不包含 Checklist 交互（依赖未来 `add-decision-checklist`，本 change 只预留展示占位）
- 不新增或修改 `DualTrackAnalyzer`/`EvidenceBucketer` 的既有行为，只作为看板的只读数据来源被复用

## Capabilities

### New Capabilities
- `stock-dashboard`：看板聚合逻辑（`DashboardBuilder`），含维度缺失优雅降级规则、综合摘要拼装
- `cli-report-dashboard`：`report dashboard` 子命令（严格离线，text/JSON 双格式输出）

### Modified Capabilities
（无——不修改 `dual-track-analyzer`、`red-blue-confrontation`、`cli-report-dual` 等既有 capability 的既定需求，均以只读方式复用）

## Impact

- **新增文件**：
  - `src/service/report/__init__.py`
  - `src/service/report/dashboard_builder.py`（`DashboardBuilder.build(code) -> DashboardView`）
  - `src/service/report/models/dashboard_view.py`（`DashboardView` dataclass：value_section/tech_section/sentiment_section/checklist_section/combined_summary）
  - `src/apps/cli.py`：新增 `report dashboard` 子命令与 `run_report_dashboard()`
  - `src/apps/formatters.py`：新增 `format_dashboard_report()`
  - `test/service/report/test_dashboard_builder.py`
  - `test/apps/test_cli_report_dashboard.py`
- **修改文件**：无（`DualTrackAnalyzer`/`EvidenceBucketer` 保持只读消费，零改动）
- **依赖**：无新增第三方依赖；功能上依赖已实现的 `DualTrackAnalyzer.analyze_offline()`、`EvidenceBucketer`
- **文档**：`docs/mrd/product-overview.md` §5.3/§7（PO-01 状态更新为「CLI 版已实现，Web 待建」）、`docs/mrd/roadmap-todo.md`（PO-01/PO-08 状态更新 + 变更记录）
