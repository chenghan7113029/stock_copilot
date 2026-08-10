## ADDED Requirements

### Requirement: `report value` 文本输出的价格分位呈现方式
`format_value_report()` 文本模式输出 SHALL 以定性分档描述（`percentile_band()` 结果）作为价格分位信息的呈现主体，原始数值 SHALL 以弱化形式（如括号内标注）伴随展示，不得以精确数值作为该信息行的句首/主语。`--json` 模式 SHALL 保持 `price_percentile` 原始数值字段不变，供程序化消费方使用。

#### Scenario: 文本模式呈现定性分档优先于数值
- **WHEN** `result.price_percentile = 72.3`，执行 `report value <code>`（文本模式，默认不带 `--show-anchor-price`）
- **THEN** 输出 SHALL 包含类似"当前价格处于历史估值区间中高位（分位 72%）"的表达，不得输出旧格式"价格分位: 72.3%"作为独立呈现

#### Scenario: --json 模式数值字段不变
- **WHEN** 执行 `report value <code> --json`
- **THEN** JSON 输出中 `price_percentile` SHALL 为原始数值（如 `72.3`），不受文本呈现规则调整影响

#### Scenario: price_percentile 为 None 时不展示分档
- **WHEN** `result.price_percentile is None`
- **THEN** 文本输出 SHALL 不包含分位相关行（沿用既有"字段为 None 时不展示该行"约定）
