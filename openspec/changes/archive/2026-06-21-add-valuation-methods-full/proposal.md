## Why

Phase 0–3（`add-valuation-methods-core`）已交付基础设施与 8 种基础估值方法，但 V1 三原型冒烟清单（MRD §13.3）仍缺少 DCF、Owner Earnings、质量评分与成长/相对估值等关键方法。本 change 补齐 Phase 4–7，使 `ValuationEngine.default_engine()` 覆盖 MRD 定义的 V1 方法论全集（不含 Phase 8 后置项）。

## What Changes

- **新增** `OwnerEarnings`（巴菲特所有者收益，Phase 4 剩余项；EPV 已在 core 交付）
- **新增** `DCF`、`ReverseDCF`（三阶段 FCF 折现 + 反推隐含增长率，Phase 5；WACC 已在 core 交付）
- **新增** 质量/风险评分三方法（Phase 6）：
  - `AltmanZScore`、`PiotroskiFScore`、`BeneishMScore`
  - 产出分数/等级，写入 `details`/`analysis`；`fair_value` 可为 0，不参与区间聚合
- **新增** 成长/相对估值七方法（Phase 7）：
  - `PEG`、`GARP`、`RuleOf40`、`EVEBITDA`、`MagicFormula`
  - `PERelativeValuation`、`PBRelativeValuation`（依赖 `StockData.historical_pe/pb`，空则 Not Applicable）
- **扩展** `default_engine()` 注册上述 12 种新方法（method_key 见 design.md）
- **扩展** `AssumptionProvider`：DCF 三阶段增长率默认值（g1=5%、g2=3%、terminal=2%）
- **新增** 对应单元测试，验收标准沿用 ±0.1%（评分方法用阈值断言）

## Capabilities

### New Capabilities

- `valuation-owner-earnings`: Owner Earnings 估值（维护性 capex、NWC 变化估算，零增长+增长均值公允价）
- `valuation-dcf`: DCF 三阶段折现与 Reverse DCF 反推隐含增长率
- `valuation-quality-scores`: Altman Z-Score、Piotroski F-Score、Beneish M-Score 质量/风险评分
- `valuation-growth`: PEG、GARP、Rule of 40、EV/EBITDA 成长与倍数估值
- `valuation-relative`: Magic Formula 排名指标、PE/PB 历史分位相对估值

### Modified Capabilities

- `valuation-infrastructure`: 扩展 `default_engine()` 注册 Phase 4–7 全部 method_key；文档化评分类方法的 `applicability` 与聚合排除规则

## Impact

- **新增模块**：`valuation/quality.py`、`valuation/dcf.py`、`valuation/growth.py`、`valuation/magic_formula.py`、`valuation/mrelative.py`（或 `relative.py`）
- **修改模块**：`valuation/engine.py`、`valuation/assumptions.py`、`valuation/__init__.py`
- **新增测试**：`test/service/value/test_owner_earnings.py`、`test_dcf.py`、`test_quality.py`、`test_growth.py`、`test_relative.py`
- **无 API/DB 变更**；历史 PE/PB 仍由 fixture 注入，data_provider 获取为独立 change
- **文档**：`docs/design/valuation-methods-reference.md` 已覆盖全部方法，实现后核对即可
