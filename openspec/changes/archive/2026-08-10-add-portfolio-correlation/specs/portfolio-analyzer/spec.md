## ADDED Requirements

### Requirement: 持仓集中度计算
系统 SHALL 提供 `PortfolioAnalyzer`，基于 `trade_record_repo.find_open_positions()`（`add-trade-review-attribution` 提供）与最新持仓价格计算：单票市值占比、前 N 大持仓占比。计算 MUST 为确定性代码逻辑，MUST NOT 使用 LLM。系统 MUST NOT 新建独立的持仓/组合数据表，MUST 复用 `TradeRecord` 派生当前持仓。

#### Scenario: 单票占比计算
- **WHEN** 组合总市值 100 万元，`600519` 持仓市值 20 万元
- **THEN** `single_stock_weight("600519")` SHALL 返回 `20%`

#### Scenario: 前 3 大持仓占比计算
- **WHEN** 组合含 5 只持仓，市值分别为 30/25/20/15/10 万元（总计 100 万元）
- **THEN** `top_n_concentration(3)` SHALL 返回 `(30+25+20)/100 = 75%`

#### Scenario: 空组合时的安全返回
- **WHEN** 当前无任何未平仓持仓
- **THEN** SHALL 返回集中度为 `None`/空结构并在 `warnings` 中说明"当前无持仓"，不抛异常

### Requirement: 行业暴露度粗估
系统 SHALL 基于已有 `StockSnapshot.industry` 自由文本字段，对当前持仓按行业分组，计算目标股票所属行业在组合中的现有市值占比。结果 MUST 携带已知局限提示（行业分类为原始文本粗匹配，非标准化分类）。

#### Scenario: 目标股票所属行业已有持仓暴露
- **WHEN** 目标股票 `industry="银行"`，当前持仓中 `industry="银行"` 的标的合计占组合 30%
- **THEN** `industry_exposure("目标股票代码")` SHALL 返回 `30%`，且结果 SHALL 附带粗匹配局限提示

#### Scenario: 目标股票行业信息缺失
- **WHEN** 目标股票的 `industry` 字段为空或本地无该股票快照
- **THEN** SHALL 返回 `None` 并在 `warnings` 中说明"无法获取行业信息，无法估算行业暴露度"

### Requirement: 加仓边际影响模拟
系统 SHALL 支持给定"若买入/加仓 N 股"的假设参数，重新计算加仓后的单票占比与行业暴露度，用于对比加仓前后的集中度变化。模拟计算 MUST NOT 产生任何真实交易记录写入。

#### Scenario: 模拟加仓后集中度上升
- **WHEN** 当前 `600519` 占比 20%，模拟加仓使其市值增加 10 万元（组合总市值同步增加）
- **THEN** SHALL 返回加仓后的新占比（高于 20%），且不写入任何 `TradeRecord`

### Requirement: 持仓价格时效标注
系统 SHALL 为每个持仓标的携带价格数据的时间戳（`price_as_of`），价格数据过期时 SHALL 在 `warnings` 中提示，不阻断计算。

#### Scenario: 价格数据过期时的提示
- **WHEN** 某持仓标的的最新价值快照时间戳早于当前 7 天以上（阈值可配置）
- **THEN** SHALL 正常完成计算，`warnings` SHALL 包含"该持仓价格数据已过期，建议先 sync"提示
