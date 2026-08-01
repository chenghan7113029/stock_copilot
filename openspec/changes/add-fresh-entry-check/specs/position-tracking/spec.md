## ADDED Requirements

### Requirement: 最小化持仓记录数据模型
系统 SHALL 提供 `PositionRecord` 持久化模型，字段为 `code`（唯一）/`cost_price`/`shares`/`opened_at`/`updated_at`。系统 SHALL NOT 支持同一 `code` 存在多条持仓记录（覆盖式存储）。

#### Scenario: 首次录入持仓
- **WHEN** 调用 `PositionRepo.upsert(code, cost_price, shares)` 且该代码此前无持仓记录
- **THEN** SHALL 插入新记录，`opened_at` SHALL 设为当前时间

#### Scenario: 更新已有持仓
- **WHEN** 调用 `PositionRepo.upsert(code, cost_price, shares)` 且该代码已有持仓记录
- **THEN** SHALL 更新 `cost_price`/`shares`/`updated_at`，SHALL NOT 修改原 `opened_at`

### Requirement: CLI 持仓录入命令
系统 SHALL 提供 `python -m apps.cli position set <code> --cost <price> --shares <n>`，调用 `PositionRepo.upsert()` 完成录入/更新。

#### Scenario: 成功录入
- **WHEN** 运行 `position set 600519 --cost 1500 --shares 100`
- **THEN** SHALL 输出确认信息，且 `PositionRepo.get_by_code("600519")` SHALL 能读回 `cost_price=1500`/`shares=100`
