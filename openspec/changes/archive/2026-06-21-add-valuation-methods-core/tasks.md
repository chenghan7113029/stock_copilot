## 1. Phase 0 — 基础设施骨架

- [x] 1.1 创建目录 `src/service/value/valuation/` 及 `__init__.py`，`src/service/value/__init__.py`
- [x] 1.2 创建 `src/service/value/valuation/base.py`：Port `ValuationResult`、`ValuationRange`、`FieldRequirement`、`BaseValuation`，改造 None 语义（`validate_data` 检测 None 而非 0）
- [x] 1.3 创建 `src/service/value/valuation/assumptions.py`：`AssumptionProvider` 类，含 A 股默认参数（china_10y_yield=1.80、ERP=6.0、aaa_yield=5.30、discount_rate=10.0、tax_rate=25.0、dividend_growth_rate=3.0）及 4 级优先级推导逻辑
- [x] 1.4 创建 `src/service/value/valuation/adapter.py`：`StockDataAdapter` 类，将 `StockData` 包装为 duck-type 接口，`None` 字段透传 `None`，`0.0` 透传 `0.0`
- [x] 1.5 创建 `src/service/value/valuation/wacc.py`：Port `calculate_wacc(stock, **overrides) -> WACCResult`，实现 CAPM + 简化两路径，debt_weight=0 兜底
- [x] 1.6 创建 `src/service/value/valuation/engine.py`：`ValuationEngine`，支持 `register`、`run_single`、`run_all`（异常不中断）
- [x] 1.7 扩展 `src/common/models.py`（`StockData`）：追加 `historical_pe: list[float] | None = None`、`historical_pb: list[float] | None = None` 两个可空字段
- [x] 1.8 创建 `test/service/value/__init__.py` 及 `test/service/value/test_base.py`：验证 None 语义、adapter 转换、engine run_all 异常不中断、WACC 计算与 ref/valueinvest 偏差 ≤ ±0.1%

## 2. Phase 1 — Graham 体系

- [x] 2.1 创建 `src/service/value/valuation/graham.py`：Port `GrahamNumber`，改 None 语义，保留 `BVPS_THRESHOLD=10.0` 检查
- [x] 2.2 在 `graham.py` 中 Port `GrahamFormula`，`growth_rate=None` 时默认 0%（warnings），增长率截断逻辑不变
- [x] 2.3 在 `graham.py` 中 Port `NCAV`，`preferred_stock` 可配置，`safety_margin` 可配置（默认 0.67）
- [x] 2.4 创建 `test/service/value/test_graham.py`：
  - GrahamNumber：`eps=5, bvps=30` → `fair_value≈58.09`，±0.1%
  - GrahamNumber：`bvps=2` → `applicability=Not Applicable`
  - GrahamFormula：`eps=4, g=10, aaa=5.3` → `fair_value≈94.34`，±0.1%
  - GrahamFormula：`g=None` → warnings 含 "0%"，不出错
  - GrahamFormula：`g=25` → 截断为 20，warnings 说明
  - NCAV：正常 + 负 NCAV 场景（不抛异常）

## 3. Phase 2 — 银行专用模型

- [x] 3.1 创建 `src/service/value/valuation/bank.py`：Port `PBValuation`，`ROE≤COE` 时 `applicability=Not Applicable`；`payout_ratio` 可配置（默认 0.4）
- [x] 3.2 在 `bank.py` 中 Port `ResidualIncome`，`years=10`、`terminal_roe=8.0`、`payout_ratio=0.6`、`cost_of_equity=10.0` 均可通过 `__init__` 覆盖
- [x] 3.3 创建 `test/service/value/test_bank.py`：
  - PBValuation：`roe=12, bvps=8, payout=0.4, coe=10` → `fair_value≈13.71`，±0.1%
  - PBValuation：`roe=8, coe=10` → `applicability=Not Applicable`
  - ResidualIncome：`bvps=10, roe=15, coe=10` → `fair_value>10`（有溢价），±0.1%
  - ResidualIncome：`bvps=10, roe=6, coe=10` → `fair_value<10`（折价）

## 4. Phase 3 — 股息模型

- [x] 4.1 创建 `src/service/value/valuation/ddm.py`：Port `DDM`（Gordon Growth），`g≥r` 时返回错误，`dividend_per_share=None` → `missing_fields`
- [x] 4.2 在 `ddm.py` 中 Port `TwoStageDDM`，`growth_stage1/stage1_years/growth_stage2/required_return` 均可配置
- [x] 4.3 创建 `test/service/value/test_ddm.py`：
  - DDM：`d=1.2, r=10, g=4` → `fair_value=20.8`，±0.1%
  - DDM：`g=12, r=10` → `error` 非空
  - DDM：`dividend_per_share=None` → `missing_fields=["dividend_per_share"]`
  - TwoStageDDM：`d=0.8, r=9, g1=6, n=5, g2=3` → `fair_value>0`，±0.1%
  - TwoStageDDM：`g2=10, r=9` → `error` 非空

## 5. Phase 3b — EPV

- [x] 5.1 创建 `src/service/value/valuation/epv.py`：Port `EPV`，`operating_margin=None` 时从 `ebit/revenue` 推导；`maintenance_capex_pct` 可配置（默认 3%）；EPV 为负时 `applicability=Limited`
- [x] 5.2 创建 `test/service/value/test_epv.py`：
  - EPV：`rev=100e9, margin=35, tax=25, net_debt=0, shares=1.26e9` → `fair_value≈184.52`，±0.1%
  - EPV：`operating_margin=None, ebit=35e9, revenue=100e9` → 推导正常，warnings 含说明
  - EPV：`net_debt > EPV_公司` → `applicability=Limited`，`fair_value<0`，不抛异常

## 6. 注册 & 导出

- [x] 6.1 在 `src/service/value/valuation/__init__.py` 中 import 并导出所有方法类和 `ValuationEngine`
- [x] 6.2 在 `src/service/value/valuation/engine.py` 中创建默认注册表函数 `default_engine() -> ValuationEngine`，预注册本期 8 种方法（method_key：graham_number、graham_formula、ncav、pb、residual_income、ddm、two_stage_ddm、epv）
- [x] 6.3 运行 `pytest test/service/value/ -v` 验证全部测试通过，无 ruff 报错

## 7. 文档 & 归档准备

- [x] 7.1 确认 `docs/design/valuation-methods-reference.md` 中 Phase 0–3 对应方法章节存在且准确（无需新建，已存在）
- [x] 7.2 检查 `docs/mrd/features/value-analysis.md` §13 设计决策与 Phase 0–3 任务描述与实现一致（无需新建，已存在）
- [x] 7.3 在 `docs/dev/engineering-conventions.md` 中更新目录结构，补充 `src/service/value/valuation/` 新增模块说明
