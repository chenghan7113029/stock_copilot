# tushare-historical-multiples Specification

## Purpose

Tushare `daily_basic` 按季末采样 5 年历史 PE/PB 序列，供相对估值方法使用。

## Requirements

### Requirement: Tushare 提供 5 年历史 PE/PB 季末序列
`TushareFetcher` SHALL 通过 `daily_basic` 接口拉取最近 5 年的 `pe_ttm`/`pb` 日频数据，按季末最后交易日采样，最多取 20 个季末点，写入 `FetchResult.data` 的 `historical_pe` 和 `historical_pb` 字段。过滤规则：PE ≤ 0 或 > 200 剔除；PB ≤ 0 或 > 50 剔除。至少 3 个有效点才写入；否则对应字段标注 missing。

#### Scenario: 正常采样 5 年历史 PE/PB
- **WHEN** `daily_basic` 返回 5 年日频数据，每季末均有有效交易日
- **THEN** `historical_pe` 和 `historical_pb` 各包含 ≥ 15 个有效值，均按降序排列（最近在前）

#### Scenario: 有效点不足 3 个时标注 missing
- **WHEN** 历史数据过短或极端值过滤后有效点 < 3
- **THEN** 对应字段不写入 data，加入 missing_fields，不报错

#### Scenario: Tushare 不可用时 Baostock fallback 生效
- **WHEN** Tushare 未启用或 token 无效
- **THEN** `historical_pe` 由 Baostock 提供（2 年），`historical_pb` 为 None（Baostock 无法提供）
