## MODIFIED Requirements

### Requirement: PBRelativeValuation 历史 PB 分位估值
系统 SHALL 实现 `PBRelativeValuation`，逻辑同 PE Relative，使用 `historical_pb` 与 bvps。**当 `historical_pb` 由 Tushare 5 年数据提供后，该方法 SHALL 从 Not Applicable 变为 Applicable，参与聚合中位计算。**

#### Scenario: historical_pb 有值时正常计算
- **WHEN** `historical_pb` 长度 ≥ 3，bvps、current_price 齐全
- **THEN** `fair_value > 0`，`applicability = "Applicable"`

#### Scenario: historical_pb 为空时 Not Applicable
- **WHEN** `StockData.historical_pb = None` 或 `[]`
- **THEN** `applicability = "Not Applicable"`，不抛异常

### Requirement: PERelativeValuation 数据窗口扩展至 5 年
`PERelativeValuation` 所使用的 `historical_pe` SHALL 来自 Tushare 5 年季末采样（约 20 点）；Baostock 2 年（约 8 点）作为 fallback。更长的窗口使均值更稳定，减少近期市场情绪偏差。

#### Scenario: 5 年 PE 均值比 2 年更稳定
- **WHEN** `historical_pe` 包含 ≥ 15 个点
- **THEN** pe_relative 公允价基于更长期均值，不受近 2 年极端行情影响
