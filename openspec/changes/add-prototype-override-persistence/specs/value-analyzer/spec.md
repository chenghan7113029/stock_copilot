## MODIFIED Requirements

### Requirement: ValueAnalyzer 支持依赖注入构造

`ValueAnalyzer.__init__` SHALL 接受 `provider`、`engine`（可选）、`router`（可选）、`aggregator`（可选）、`override_repo`（可选，`PrototypeOverrideRepo | None`）参数；`from_config(config: dict, repo=None, override_repo=None) -> ValueAnalyzer` SHALL 从配置字典构造完整实例，`override_repo` 透传给构造函数。

分析流程中（`analyze()`/`analyze_offline()` 内部的 `_analyze_stock()`）：若 `override_repo` 非 `None`，SHALL 在调用 `router.route(stock)` 前先查询 `override_repo.get_by_code(stock.code)`；查询到记录时，SHALL 以 `router.route(stock, override=record.prototype)` 调用路由，并在返回的 `ValueAnalysisResult.warnings` 中追加一条包含 `record.prototype` 与 `record.reason` 的可追溯提示；未查询到记录，或 `override_repo` 为 `None`，SHALL 按 `router.route(stock)`（不传 override）的既有方式执行，行为与本 change 之前完全一致。

#### Scenario: 默认引擎使用 default_engine

- **WHEN** `engine=None` 时构造 ValueAnalyzer
- **THEN** 内部自动使用 `default_engine()`，包含 23 个注册方法

#### Scenario: 注入 mock provider 用于单测

- **WHEN** 在测试中注入返回固定 StockData 的 mock provider
- **THEN** `analyze()` 正常执行且不发起真实网络请求

#### Scenario: 存在人工覆盖记录时应用覆盖并追加可追溯提示

- **WHEN** `override_repo.get_by_code("600519")` 返回 `PrototypeOverrideRecord(prototype="high_dividend", reason="管理层变更")`
- **THEN** `ValueAnalysisResult.prototype == "high_dividend"`（而非硬编码表/启发式原本会判定的值）
- **THEN** `ValueAnalysisResult.warnings` 中包含一条同时提及 `"high_dividend"` 与 `"管理层变更"` 的提示文案

#### Scenario: 无覆盖记录或未注入 override_repo 时行为不变

- **WHEN** `override_repo=None`，或 `override_repo.get_by_code(code)` 返回 `None`
- **THEN** `router.route(stock)` 按原有方式调用（不传 `override`），`ValueAnalysisResult` 的 `prototype`/`warnings` 与本 change 之前完全一致
