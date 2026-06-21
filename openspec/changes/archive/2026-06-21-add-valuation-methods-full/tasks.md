## 1. Phase 4 — Owner Earnings

- [x] 1.1 创建 `src/service/value/valuation/quality.py`：Port `OwnerEarnings`（维护性 capex、NWC 估算、零增长+增长均值公允价）
- [x] 1.2 创建 `test/service/value/test_owner_earnings.py`：正常场景 ±0.1%、OE≤0 错误、net_income=None missing_fields

## 2. Phase 5 — DCF 族

- [x] 2.1 扩展 `assumptions.py`：新增 `growth_rate_1_5`、`growth_rate_6_10`、`terminal_growth`、`ev_ebitda_multiple` 及 getter
- [x] 2.2 创建 `src/service/value/valuation/dcf.py`：Port `DCF`（三阶段 FCF + WACC 折现 + 终值）
- [x] 2.3 在 `dcf.py` 中 Port `ReverseDCF`（二分法反推 implied_growth_rate）
- [x] 2.4 创建 `test/service/value/test_dcf.py`：DCF fixture 茅台 ±0.1%、fcf=None missing、ReverseDCF 正常/无解

## 3. Phase 6 — 质量/风险评分

- [x] 3.1 在 `quality.py` 中 Port `AltmanZScore`（details.z_score、output_type=score）
- [x] 3.2 在 `quality.py` 中 Port `PiotroskiFScore`（details.f_score、prior 缺失 → Limited）
- [x] 3.3 创建 `src/service/value/valuation/mscore.py`：Port `BeneishMScore`（8 组件、details.m_score）
- [x] 3.4 创建 `test/service/value/test_quality.py`：Z>2.99 安全、F-Score 整数、M-Score 阈值、missing 不抛异常

## 4. Phase 7 — 成长/相对估值

- [x] 4.1 创建 `src/service/value/valuation/growth.py`：Port `PEG`、`GARP`、`RuleOf40`、`EVEBITDA`
- [x] 4.2 创建 `src/service/value/valuation/magic_formula.py`：Port `MagicFormula`
- [x] 4.3 创建 `src/service/value/valuation/relative.py`：Port `PERelativeValuation`、`PBRelativeValuation`（historical 空 → Not Applicable）
- [x] 4.4 创建 `test/service/value/test_growth.py`：PEG/GARP/EV/EBITDA ±0.1%、growth≤0 错误
- [x] 4.5 创建 `test/service/value/test_relative.py`：Magic Formula ±0.1%、PE/PB relative fixture 序列、historical=None Not Applicable

## 5. 注册 & 导出

- [x] 5.1 扩展 `engine.default_engine()` 注册 Phase 4–7 全部 13 个 method_key
- [x] 5.2 更新 `valuation/__init__.py` 导出新增类
- [x] 5.3 运行 `pytest test/service/value/ -v` 与 `pytest test/ -m "not network" --ignore=test/e2e` 全量通过
- [x] 5.4 运行 `ruff check src/service/value/ test/service/value/`

## 6. 文档

- [x] 6.1 核对 `docs/design/valuation-methods-reference.md` Phase 4–7 章节与实现一致（参数默认值、公式）
- [x] 6.2 更新 `docs/mrd/features/value-analysis.md` §13.2：标注 Phase 0–3/4–7 完成状态（归档 task）
