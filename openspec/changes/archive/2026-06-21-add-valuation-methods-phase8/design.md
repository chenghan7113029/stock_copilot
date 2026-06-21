## Context

Phase 0–7 已建立完整的 21 种估值方法计算库（`src/service/value/valuation/`），通过 `BaseValuation` + `ValuationEngine` 统一注册/运行。Phase 8 补全两类"风险校验层"方法：

1. **ValueTrapDetector**：五维度量化 + 半定性评分，检测表面低估股的价值陷阱风险
2. **SBCAnalysis**：计算股权激励稀释影响，还原"真实" EPS

这两种方法属于 `output_type = "score"` 类别（同 AltmanZ、PiotroskiF、BeneishM），不参与估值区间聚合，而是进入 `warnings` 风险校验层。

`StockData` 已预留了 `sbc`（SBC 金额）、`prior_shares_outstanding`、`shares_issued`、`shares_repurchased` 字段（Phase 0 时预留），无需扩展数据模型。

## Goals / Non-Goals

**Goals:**
- Port `ValueTrapDetector` 五维度评分，dimension-level 风险等级（Low/Medium/High）+综合等级
- Port `SBCAnalysis` SBC 占比、调整 EPS、年稀释率、稀释性评级
- `default_engine()` 注册 `value_trap`、`sbc`，总计 23 个 method_key
- 单元测试覆盖各评级边界与缺失字段 graceful 降级

**Non-Goals:**
- Cyclical 4 种方法（依赖 V2 `CyclicalStock` 数据模型，延迟至独立 change）
- `revenue_growth` 字段的 data_provider 获取（缺失时该维度降级为 Limited，不阻断）
- LLM 解读层（不属于确定性计算库范围）

## Decisions

### D-1：ValueTrapDetector 五维度评分架构

维度 | 关键字段（`StockData`） | 缺失处理
---|---|---
财务健康 | `altman_z`（复用 `AltmanZScore` 结果）、`current_assets/liabilities`（流动比率）、`interest_expense/ebit`（利息覆盖率）、`total_liabilities/total_assets`（负债率） | 任一关键字段缺失 → 该维度 `Limited`
业务恶化 | `revenue`、`revenue_growth`（若有）、`operating_margin` | `revenue_growth` 缺失 → 维度 `Limited`；仅用现有字段评估
护城河侵蚀 | `roe`、`roic`（两者均无 → 该维度 `Limited`） | 有任一即可评估
AI/技术脆弱性 | 无定量字段，默认 `Medium`（需 LLM 层叠加，此层占位） | 固定输出 `Medium/unknown`，`warnings` 提示"需人工评估"
股息可持续性 | `dividend_payout_ratio`、`fcf`、`dividend_per_share` | 无分红数据 → `Not Applicable`

**优先复用** `AltmanZScore` 计算逻辑（不重复实现 Z-Score 公式）：`ValueTrapDetector` 内部调用 `AltmanZScore.calculate(stock)` 取 `details.z_score`，实现零重复。

### D-2：SBCAnalysis 实现架构

关键字段：`sbc`（主要输入）、`net_income`、`revenue`、`shares_outstanding`、`prior_shares_outstanding`

- `sbc = None` → `applicability = "Not Applicable"`（A 股 SBC 未披露的常见情形）
- `sbc = 0.0` → `output_type = "score"`，评级 `Negligible`，`adjusted_eps = eps`
- 年稀释率 = `(shares_outstanding - prior_shares_outstanding) / prior_shares_outstanding`；`prior_shares_outstanding = None` → 只评 SBC/净利润维度，稀释率维度标注 `Limited`
- `fair_value` 输出 = `current_price`（评分类，不参与聚合）

### D-3：稳定性与测试策略

ValueTrapDetector 因"AI 维度默认 Medium"会有固定输出，需明确断言：
- 输入完整股息 + 财务健康数据时，长江电力综合风险 = `Low`
- Altman-Z 复用时不抛异常（即使 AltmanZScore 内部失败，捕获并降级）

测试使用 fixture 注入（不需要 ref 同输入 ±0.1% 对标，因为 Value Trap 无严格公式参考值），验证维度评级逻辑的阈值边界。

## Risks / Trade-offs

- **[Risk] ValueTrap AI 维度空洞**：本期 AI 脆弱性维度只输出占位 `Medium`，综合等级可能被拉偏 → Mitigation：在 `details.ai_vulnerability_note` 中说明"需人工评估"，且该维度权重在综合评级中降低（权重 0.5x）
- **[Risk] revenue_growth 缺失率高**：`StockData` 无 `revenue_growth` 字段，业务恶化维度对多数股票为 `Limited` → Mitigation：接受降级，`warnings` 注明；后续 data_provider 获取历史收入时可补全
- **[Risk] SBC 数据在 A 股近乎全缺**：大多数 A 股 `sbc = None` → 输出 `Not Applicable`，不影响其他方法，是预期行为
