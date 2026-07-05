## ADDED Requirements

### Requirement: TTM EPS 推导覆写季报单季 EPS
在所有数据源 merge 完成后，`StockDataProvider` SHALL 检查 `stock.net_income` 与 `stock.shares_outstanding` 是否均为有效正值；若是，SHALL 用 `net_income / shares_outstanding` 计算 TTM EPS 并覆写 `stock.eps`，来源标注为 `"derived:ttm"`。原始 `fina_indicator.eps`（季报单季值）不再直接作为估值输入。

#### Scenario: 年报净利润与总股本均可用时推导 TTM EPS
- **WHEN** merge 完成后 stock.net_income=82320000000（823.2亿），stock.shares_outstanding=1250000000（12.5亿股）
- **THEN** stock.eps SHALL 被覆写为 65.86，stock.field_sources["eps"] = "derived:ttm"

#### Scenario: net_income 缺失时保留原始 EPS
- **WHEN** merge 完成后 stock.net_income=None，stock.eps=21.76（fina_indicator季报值）
- **THEN** stock.eps 保持 21.76 不变，不进行 TTM 推导

#### Scenario: TTM EPS 推导对离线模式同样生效
- **WHEN** 调用 get_stock_data_offline() 且快照中有 net_income 与 shares_outstanding
- **THEN** TTM EPS 推导逻辑 SHALL 同样执行，结果与在线模式一致
