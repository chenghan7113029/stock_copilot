## Why

Phase 0–7 已完成 21 种确定性估值方法的实现（`default_engine()` 全量注册），但价值陷阱检测（ValueTrap）与股权激励稀释分析（SBC）两项"风险校验类"方法尚缺失。这两项方法是价值面输出 `warnings` 层的重要信号源——ValueTrap 防止"便宜但越跌越便宜"，SBC 揭示科技股被隐藏的稀释成本——MRD §8 将其列为 V1.x 待补项。本次 change 补全这两个方法，使估值库的质量/风险评分层完整。Cyclical 4 种方法因依赖 V2 `CyclicalStock` 数据模型，延迟至后续独立 change。

## What Changes

- 新增 `src/service/value/valuation/value_trap.py`：`ValueTrapDetector`，五维度综合评估（财务健康、业务恶化、护城河侵蚀、AI 脆弱性、股息可持续性），产出风险等级（Low/Medium/High）及维度明细
- 新增 `src/service/value/valuation/sbc.py`：`SBCAnalysis`，计算 SBC/净利润、SBC/营收、年稀释率、调整后 EPS，给出稀释性评级（Negligible/Light/Moderate/Severe/Extreme）
- 更新 `src/service/value/valuation/engine.py`：`default_engine()` 新增注册 `value_trap`、`sbc` 两个 method_key
- 更新 `src/service/value/valuation/__init__.py`：导出新增类
- 新增 `test/service/value/test_value_trap.py` 与 `test/service/value/test_sbc.py`：覆盖各维度评级逻辑与缺失字段 graceful 降级
- 更新 `docs/mrd/features/value-analysis.md` §13.2：标注 Phase 8 完成状态

## Capabilities

### New Capabilities

- `valuation-value-trap`：`ValueTrapDetector` 五维度陷阱检测；`details.output_type = "score"`，`details` 含各维度评分；`fair_value = current_price`（不参与区间聚合）
- `valuation-sbc`：`SBCAnalysis` 股权激励稀释分析；`details.output_type = "score"`，`details` 含调整后 EPS 及稀释等级

### Modified Capabilities

- `valuation-infrastructure`：`default_engine()` 新增 `value_trap`、`sbc` 两个 method_key；共 23 个 method_key

## Impact

- `src/service/value/valuation/`：新增 `value_trap.py`、`sbc.py`；修改 `engine.py`、`__init__.py`
- `test/service/value/`：新增 `test_value_trap.py`、`test_sbc.py`
- `docs/mrd/features/value-analysis.md` §13.2：Phase 8 状态更新
- 无破坏性变更；`default_engine()` 纯新增注册，已有 method_key 行为不变
- `StockData` 可能需要新增 `stock_based_compensation`（SBC 金额）字段；若字段缺失，SBC 方法返回 `applicability="Limited"`
