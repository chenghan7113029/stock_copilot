## ADDED Requirements

### Requirement: 价格分位定性分档映射
系统 SHALL 提供 `percentile_band(price_percentile: float) -> str`，将 0–100 的数值映射为 5 档定性描述（低位/中低位/中性/中高位/高位），不修改 `price_percentile` 本身的计算逻辑。

#### Scenario: 低位分档
- **WHEN** `price_percentile = 15`
- **THEN** SHALL 返回"历史估值区间低位"

#### Scenario: 中性分档边界值
- **WHEN** `price_percentile = 40`
- **THEN** SHALL 返回"历史估值区间中性"（边界值归入较高一档，需在实现中固定该边界归属并单测覆盖）

#### Scenario: 高位分档
- **WHEN** `price_percentile = 95`
- **THEN** SHALL 返回"历史估值区间高位"

### Requirement: 历史最高价计算与默认隐藏
系统 SHALL 提供 `historical_high(code: str) -> tuple[float, int] | None`（返回历史最高价与所依据的数据窗口天数），纯离线从本地 `Kline` 缓存计算，不发起网络请求。该计算结果 MUST NOT 出现在任何报告的默认输出中，仅当调用方显式请求（如 CLI `--show-anchor-price` flag）时才展示，且展示时 MUST 附带数据窗口说明与"仅供参考，不建议作为决策心理锚点"的固定警示文案。

#### Scenario: 本地有 K 线缓存时计算历史最高价
- **WHEN** 本地 `Kline` 表中 `600519` 有 250 条记录
- **THEN** `historical_high("600519")` SHALL 返回 `(该 250 条记录中的最大 close/high 值, 250)`

#### Scenario: 本地无 K 线缓存时返回 None
- **WHEN** 本地 `Kline` 表中无该 `code` 记录
- **THEN** SHALL 返回 `None`，不抛异常

#### Scenario: 默认报告输出不包含历史最高价
- **WHEN** 执行 `report value <code>`（不带 `--show-anchor-price`）
- **THEN** 输出 MUST NOT 包含历史最高价数值或字段

#### Scenario: 显式 opt-in 后展示且携带警示与窗口说明
- **WHEN** 执行 `report value <code> --show-anchor-price`
- **THEN** 输出 SHALL 包含历史最高价数值、所依据的数据窗口天数说明、以及"仅供参考，不建议作为决策心理锚点"的固定警示文案
