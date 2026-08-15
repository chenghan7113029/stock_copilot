## ADDED Requirements

### Requirement: 按原型差异化的 MOS 评估阈值

系统 SHALL 提供共享的按原型 MOS 阈值解析（供 Aggregator 与双轨共用）。对五档 `assessment`，默认阈值（百分数点）SHALL 为：

| prototype | 低估 if MOS > | 合理偏低 if MOS > | 合理 if MOS > | 合理偏高 if MOS > | 否则 |
|-----------|---------------|-------------------|---------------|-------------------|------|
| `bank` | 12 | 3 | -3 | -12 | 高估 |
| `high_dividend` | 12 | 3 | -3 | -12 | 高估 |
| `value_growth` | 20 | 5 | -5 | -20 | 高估 |
| 其他 / 未识别 | 同 `value_growth` | | | | |

配置 `value.mos_thresholds_by_proto`（若存在）SHALL 可覆盖上述默认；缺键回退默认表。

#### Scenario: 银行 MOS=15 为低估

- **WHEN** prototype=`bank` 且 MOS=15
- **THEN** assessment=`低估`

#### Scenario: 价值成长 MOS=15 仅为合理偏低

- **WHEN** prototype=`value_growth` 且 MOS=15
- **THEN** assessment=`合理偏低`（未达 20）

#### Scenario: 高股息与银行共用较宽低估门槛

- **WHEN** prototype=`high_dividend` 且 MOS=13
- **THEN** assessment=`低估`

## MODIFIED Requirements

### Requirement: 聚合输出区间与 MOS

聚合后 SHALL 计算：
- `base = median(filtered_values)`
- `low = percentile(filtered_values, 25)`
- `high = percentile(filtered_values, 75)`
- `margin_of_safety = (base - current_price) / base * 100`（%）
- `price_percentile`：current_price 在 [low, high] 中的线性百分位，low 时为 0，high 时为 100，超出范围 clamp 到 [0, 100]
- `assessment`：SHALL 根据调用方传入的 `prototype`（或等价参数）选用按原型 MOS 阈值表生成；未传 prototype 时按 `value_growth` 表（保持历史默认严口径）

#### Scenario: 正常聚合计算（价值成长口径）

- **WHEN** filtered_values=[600, 700, 800]，current_price=650，prototype=`value_growth`
- **THEN** base=700，MOS≈7.14%，assessment 为"合理偏低"

#### Scenario: 当前价高于 base（高估，价值成长口径）

- **WHEN** filtered_values=[600, 700, 800]，current_price=900，prototype=`value_growth`
- **THEN** MOS≈-28.6%，assessment 为"高估"

#### Scenario: 同等 MOS 银行与价值成长评估不同

- **WHEN** 同一 MOS≈15%，分别以 prototype=`bank` 与 `value_growth` 聚合
- **THEN** bank 的 assessment 为「低估」，value_growth 的 assessment 为「合理偏低」
