## 1. ValueTrapDetector 实现

- [x] 1.1 创建 `src/service/value/valuation/value_trap.py`：实现 `ValueTrapDetector`，复用 `AltmanZScore.calculate(stock)` 取 z_score，五维度独立评级，综合风险等级加权多数决
- [x] 1.2 创建 `test/service/value/test_value_trap.py`：低风险长江电力 fixture 综合 Low、高风险场景综合 High、revenue_growth=None 业务维度降级 Limited、无分红数据股息维度 Not Applicable、critical 字段缺失不抛异常

## 2. SBCAnalysis 实现

- [x] 2.1 创建 `src/service/value/valuation/sbc.py`：实现 `SBCAnalysis`，计算 sbc/净利润、sbc/营收、年稀释率、调整后 EPS，输出稀释性评级（Negligible/Light/Moderate/Severe/Extreme）
- [x] 2.2 创建 `test/service/value/test_sbc.py`：sbc=None Not Applicable、sbc=0 Negligible、sbc/净利润=50% Severe、prior_shares=None 省略稀释率、net_income=None missing_fields

## 3. 引擎与导出更新

- [x] 3.1 更新 `src/service/value/valuation/engine.py`：`default_engine()` 新增注册 `value_trap` → `ValueTrapDetector()`、`sbc` → `SBCAnalysis()`；共 23 个 method_key
- [x] 3.2 更新 `src/service/value/valuation/__init__.py`：导出 `ValueTrapDetector`、`SBCAnalysis`

## 4. 验证与回归

- [x] 4.1 运行 `pytest test/service/value/ -v`，全部通过
- [x] 4.2 运行 `pytest test/ -m "not network" --ignore=test/e2e`，全量回归通过
- [x] 4.3 运行 `ruff check src/service/value/valuation/ test/service/value/`，无 lint 错误

## 5. 文档归档

- [x] 5.1 更新 `docs/mrd/features/value-analysis.md` §13.2：标注 Phase 8 完成状态，补充 `value_trap`、`sbc` 到 method_key 总表
