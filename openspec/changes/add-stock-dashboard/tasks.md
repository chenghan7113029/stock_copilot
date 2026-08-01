## 1. DashboardView 数据结构

- [x] 1.1 新建 `src/service/report/__init__.py`
- [x] 1.2 新建 `src/service/report/models/__init__.py`
- [x] 1.3 新建 `src/service/report/models/dashboard_view.py`：`DashboardView` dataclass，字段 `code`/`value_section`/`tech_section`/`sentiment_section`/`checklist_section`/`combined_summary`/`warnings`
- [x] 1.4 单测 `test/service/report/test_dashboard_view.py`：验证 dataclass 默认值与字段类型

## 2. DashboardBuilder 聚合逻辑

- [x] 2.1 新建 `src/service/report/dashboard_builder.py`：`DashboardBuilder.__init__(value_analyzer, tech_analyzer, config=None)` + `from_config(config)`
- [x] 2.2 实现 `build(code: str) -> DashboardView`：内部调用 `DualTrackAnalyzer.analyze_offline()`，按决策 2 的降级规则拼装 `value_section`/`tech_section`
- [x] 2.3 实现红蓝证据摘要：调用 `EvidenceBucketer().bucket(report)`，将 `len(bull_evidence)`/`len(bear_evidence)` 写入 `combined_summary`
- [x] 2.4 实现情绪面/Checklist 占位：`sentiment_section`/`checklist_section` 固定输出「待建（见 PO-06/PO-04）」文案
- [x] 2.5 实现整体失败判定：`value_result is None and tech_result is None` 时抛出与 `report dual` 一致的错误
- [x] 2.6 单测 `test/service/report/test_dashboard_builder.py`：覆盖价值面+技术面均有数据、仅价值面缺失、仅技术面缺失、两者均缺失（抛错）四种场景

## 3. CLI `report dashboard`

- [x] 3.1 `src/apps/cli.py` 新增 `run_report_dashboard(code, as_json=False, output=None, config=None)`：装配 `ValueAnalyzer`/`TechAnalyzer`/`DashboardBuilder`，严格离线
- [x] 3.2 `build_parser()` 新增 `report dashboard` 子命令：`code` 位置参数、`--json`/`--output`/`--quiet`，与 `report dual` 对齐
- [x] 3.3 `main()` 分发逻辑新增 `report_type == "dashboard"` 分支
- [x] 3.4 `src/apps/formatters.py` 新增 `format_dashboard_report(view: DashboardView, as_json: bool) -> str`：text 模式含五分区标题，JSON 模式序列化全部字段
- [x] 3.5 单测 `test/apps/test_cli_report_dashboard.py`：覆盖成功输出、`--json`/`--output`、无本地数据报错三种场景

## 4. 端到端验证

- [x] 4.1 `sync 600519` 后运行 `report dashboard 600519`，人工检查五个分区均正确显示，且不发起网络请求
- [x] 4.2 对一个仅同步过价值面（未同步 K 线，或反之）的代码验证降级分区提示
- [x] 4.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 5. 文档更新

- [x] 5.1 更新 `docs/mrd/product-overview.md` §5.3：PO-01「多维立体看板」状态更新为「CLI 版已实现，Web 待建（依赖 REST API）」
- [x] 5.2 更新 `docs/mrd/product-overview.md` §7：PO-08 状态更新为「CLI 部分（report dashboard）已实现，Web 部分待建」
- [x] 5.3 更新 `docs/mrd/roadmap-todo.md`：新增变更记录，PO-01/PO-08 状态行更新，§1.4「尚未交付」表格勾选 CLI 看板

## 6. 归档

- [x] 6.1 确认 `tasks.md` 全部任务完成
- [ ] 6.2 运行 `/opsx-archive add-stock-dashboard` 归档，同步 specs 到 `openspec/specs/`
