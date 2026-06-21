## ADDED Requirements

### Requirement: ValueTrapDetector 五维度价值陷阱检测
系统 SHALL 实现 `ValueTrapDetector` 方法，从五个维度量化评估价值陷阱风险：
财务健康、业务恶化、护城河侵蚀、AI/技术脆弱性（占位）、股息可持续性。
每个维度独立输出风险等级（Low/Medium/High/Limited）；综合等级由维度加权多数决定。
`details.output_type = "score"`，`fair_value = current_price`（不参与估值区间聚合）。
AI/技术脆弱性维度在纯数据驱动模式下固定输出 `Medium`，并在 `details.ai_vulnerability_note` 标注"需人工评估"。

**五维度定义：**

| 维度 | 关键指标 | 评级逻辑（参考阈值） |
|------|---------|---------------------|
| 财务健康 | Altman Z-Score、流动比率、利息覆盖率、负债率 | Z > 2.99 且流动比率 > 1.5 且利息覆盖率 > 3 → Low；Z < 1.81 或利息覆盖率 < 1.5 → High |
| 业务恶化 | 营业利润率趋势（现有数据）、revenue_growth | operating_margin > 15% → Low；operating_margin < 5% 且下滑 → High；revenue_growth 缺失 → Limited |
| 护城河侵蚀 | ROE 水平、ROIC 水平 | ROE > 15% 且 ROIC > 12% → Low；ROE < 8% 或 ROIC < 6% → High；均缺失 → Limited |
| AI/技术脆弱性 | （纯数据层占位） | 固定 Medium，标注需人工评估 |
| 股息可持续性 | 派息率、FCF 覆盖 | dividend_per_share = None → Not Applicable；派息率 < 60% 且 fcf > 0 → Low；派息率 > 100% 或 fcf < 0 → High |

**综合风险等级：** High 维度 ≥ 2 → High；High = 1 或 Medium ≥ 2 → Medium；否则 → Low。`Limited` 维度不纳入多数决，但 `warnings` 注明。

#### Scenario: 低风险股票（高股息公用事业类）
- **WHEN** `roe = 20.0`, `roic = 15.0`, `operating_margin = 35.0`, `dividend_payout_ratio = 65.0`, `fcf = 1e10`，Altman-Z > 3.0
- **THEN** `details.overall_risk = "Low"`，财务健康维度 = Low，护城河维度 = Low，股息维度 = Low

#### Scenario: 高风险股票（低利润率高负债）
- **WHEN** `operating_margin = 2.0`, `roe = 5.0`, `roic = 4.0`, `dividend_payout_ratio = 110.0`, `fcf = -5e9`，Altman Z-Score < 1.5
- **THEN** `details.overall_risk = "High"`，至少 3 个维度为 High

#### Scenario: revenue_growth 缺失时业务恶化维度降级
- **WHEN** `revenue` 有值但无 `revenue_growth` 字段数据（revenue_growth=None）
- **THEN** 业务恶化维度 = `Limited`，`warnings` 含"revenue_growth unavailable"，整体计算不抛异常

#### Scenario: 无分红数据时股息维度不适用
- **WHEN** `StockData.dividend_per_share = None`
- **THEN** 股息可持续性维度 = `Not Applicable`，`details` 含 `dividend_sustainability = "Not Applicable"`

#### Scenario: AI 维度固定占位
- **WHEN** 任意输入
- **THEN** `details.ai_vulnerability = "Medium"`，`details.ai_vulnerability_note` 含"需人工评估"

#### Scenario: critical 字段缺失时方法不抛异常
- **WHEN** `total_assets = None`（财务健康无法计算）
- **THEN** 财务健康维度 = `Limited`，整体 `applicability` 可为 `Limited`，不抛异常
