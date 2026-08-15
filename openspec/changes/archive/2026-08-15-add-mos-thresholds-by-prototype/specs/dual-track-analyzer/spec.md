## ADDED Requirements

### Requirement: 双轨价值评级阈值按原型差异化

当 `value_result.methodology_applicable is True` 时，`derive_value_rating` / `SignalFusion.fuse` SHALL 按 `value_result.prototype` 选用低估/高估阈值（与 Aggregator 共享解析源）：

| prototype | UNDERVALUED if MOS > | OVERVALUED if MOS < |
|-----------|----------------------|---------------------|
| `bank` | 12 | -12 |
| `high_dividend` | 12 | -12 |
| `value_growth` 及其他 | 20 | -10 |

`methodology_applicable is False` 时仍强制 `UNKNOWN`（既有诚实降级规则优先）。

#### Scenario: 银行 MOS=15 双轨为低估

- **WHEN** prototype=`bank`，MOS=15，`methodology_applicable=True`
- **THEN** `value_rating=UNDERVALUED`

#### Scenario: 价值成长 MOS=15 双轨为合理

- **WHEN** prototype=`value_growth`，MOS=15，`methodology_applicable=True`
- **THEN** `value_rating=FAIR`

#### Scenario: 诚实降级仍优先

- **WHEN** `methodology_applicable=False`，即使 prototype=`bank` 且 MOS=15
- **THEN** `value_rating=UNKNOWN`

## MODIFIED Requirements

### Requirement: SignalFusion 确定性规则融合

`SignalFusion.fuse(value_result, tech_result) → CombinedSignal` SHALL 基于 `ValueRating` × `tech_result.buy_signal` 的矩阵输出 `CombinedSignal`。

`ValueRating` 派生规则：

1. 若 `value_result is None` → 无价值评级（见下方仅技术面）
2. 若 `value_result.methodology_applicable is False` → **强制** `ValueRating.UNKNOWN`（忽略 MOS）
3. 否则按 `value_result.prototype` 的按原型阈值与 `margin_of_safety` 派生 UNDERVALUED / FAIR / OVERVALUED / UNKNOWN(mos 为空)

矩阵（当 rating 为 UNDERVALUED/FAIR/OVERVALUED 且技术面非空）保持既有 3×6 表不变。

当 `value_result = None` 时，SHALL 直接返回 `tech_result.buy_signal`（转换为 `CombinedSignal`）。当 `tech_result = None` 时，SHALL 基于 `ValueRating` 单独输出（UNDERVALUED→BUY，FAIR→HOLD，OVERVALUED→WAIT，**UNKNOWN→WAIT**）。两者均 None 时返回 WAIT。当 `value_rating == UNKNOWN` 且技术面非空时，SHALL 返回技术面转换结果。

#### Scenario: 低估 + 强烈买入 → 强烈买入

- **WHEN** `methodology_applicable=True`，prototype=`value_growth`，MOS > 20% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = STRONG_BUY`

#### Scenario: 银行较低门槛即可低估融合

- **WHEN** `methodology_applicable=True`，prototype=`bank`，MOS=15，`tech_result.buy_signal = BUY`
- **THEN** `value_rating = UNDERVALUED`，`combined_signal = BUY`

#### Scenario: 高估 + 强烈买入 → 持有（抑制技术追高）

- **WHEN** `methodology_applicable=True`，prototype=`value_growth`，MOS < -10% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = HOLD`

#### Scenario: 仅技术面可用

- **WHEN** `value_result = None`，`tech_result.buy_signal = BUY`
- **THEN** `combined_signal = BUY`

#### Scenario: 诚实降级忽略 MOS 低估

- **WHEN** `methodology_applicable=False`，MOS > 20%，`tech_result.buy_signal = STRONG_BUY`
- **THEN** `value_rating = UNKNOWN`，`combined_signal` 为技术面 STRONG_BUY 的转换结果
