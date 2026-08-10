## ADDED Requirements

### Requirement: 诚实降级时价值评级强制 UNKNOWN

当 `value_result` 非空且 `value_result.methodology_applicable is False` 时，`SignalFusion`（及 `derive_value_rating` 的调用路径）SHALL **忽略** `margin_of_safety`，将 `value_rating` 设为 `ValueRating.UNKNOWN`。

融合后果与既有 UNKNOWN 语义一致：

- 仅有价值面：`combined_signal = WAIT`
- 价值面 + 技术面：`combined_signal` 跟随技术面 `buy_signal`（转换为 CombinedSignal），**不得**因 MOS 显示低估而升级为 BUY/STRONG_BUY

#### Scenario: 比亚迪双轨不因假低估买入

- **WHEN** `value_result` 为比亚迪诚实降级结果（`methodology_applicable=False`，即使 `margin_of_safety > 20`），且 `tech_result.buy_signal = BUY`
- **THEN** `value_rating = UNKNOWN`，`combined_signal` 等于技术面转换结果（BUY），而非矩阵中 UNDERVALUED×BUY 的加成路径以外的「价值驱动买入」；具体地 SHALL NOT 把价值面解释为 UNDERVALUED

#### Scenario: 诚实降级且无技术面 → 观望

- **WHEN** `methodology_applicable=False` 且 `tech_result is None`
- **THEN** `value_rating = UNKNOWN`，`combined_signal = WAIT`

#### Scenario: 正常价值成长仍按 MOS 评级

- **WHEN** `methodology_applicable=True` 且 MOS > 低估阈值
- **THEN** `value_rating = UNDERVALUED`（行为与本 change 之前一致）

## MODIFIED Requirements

### Requirement: SignalFusion 确定性规则融合

`SignalFusion.fuse(value_result, tech_result) → CombinedSignal` SHALL 基于 `ValueRating` × `tech_result.buy_signal` 的矩阵输出 `CombinedSignal`。

`ValueRating` 派生规则：

1. 若 `value_result is None` → 无价值评级（见下方仅技术面）
2. 若 `value_result.methodology_applicable is False` → **强制** `ValueRating.UNKNOWN`（忽略 MOS）
3. 否则由 `value_result.margin_of_safety` 按既有阈值派生 UNDERVALUED / FAIR / OVERVALUED / UNKNOWN(mos 为空)

矩阵（当 rating 为 UNDERVALUED/FAIR/OVERVALUED 且技术面非空）：

| ValueRating \ BuySignal | STRONG_BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
|---|---|---|---|---|---|---|
| UNDERVALUED | STRONG_BUY | BUY | BUY | WAIT | WAIT | SELL |
| FAIR | BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
| OVERVALUED | HOLD | WAIT | SELL | SELL | STRONG_SELL | STRONG_SELL |

当 `value_result = None` 时，SHALL 直接返回 `tech_result.buy_signal`（转换为 `CombinedSignal`）。当 `tech_result = None` 时，SHALL 基于 `ValueRating` 单独输出（UNDERVALUED→BUY，FAIR→HOLD，OVERVALUED→WAIT，**UNKNOWN→WAIT**）。两者均 None 时返回 WAIT。当 `value_rating == UNKNOWN` 且技术面非空时，SHALL 返回技术面转换结果（不查 UNDERVALUED/FAIR/OVERVALUED 矩阵）。

#### Scenario: 低估 + 强烈买入 → 强烈买入

- **WHEN** `methodology_applicable=True`，MOS > 20% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = STRONG_BUY`

#### Scenario: 高估 + 强烈买入 → 持有（抑制技术追高）

- **WHEN** `methodology_applicable=True`，MOS < -10% 且 `tech_result.buy_signal = STRONG_BUY`
- **THEN** `combined_signal = HOLD`

#### Scenario: 低估 + 技术空头 → 观望（等技术面企稳）

- **WHEN** `methodology_applicable=True`，MOS > 20% 且 `tech_result.buy_signal = STRONG_SELL`
- **THEN** `combined_signal = SELL`

#### Scenario: 仅技术面可用

- **WHEN** `value_result = None`，`tech_result.buy_signal = BUY`
- **THEN** `combined_signal = BUY`

#### Scenario: 诚实降级忽略 MOS 低估

- **WHEN** `methodology_applicable=False`，MOS > 20%，`tech_result.buy_signal = STRONG_BUY`
- **THEN** `value_rating = UNKNOWN`，`combined_signal` 为技术面 STRONG_BUY 的转换结果（不得先按 UNDERVALUED 矩阵再融合出「价值确认」语义——实现上即 UNKNOWN 分支）
