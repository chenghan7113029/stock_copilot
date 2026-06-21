## 1. 数据模型 — ValueAnalysisResult

- [x] 1.1 创建 `src/service/value/models/__init__.py`（空，包标记）
- [x] 1.2 创建 `src/service/value/models/analysis_result.py`：定义 `ValuationRange` 和 `ValueAnalysisResult` dataclass，包含 spec `value-analyzer` 所有规定字段

## 2. 原型路由 — PrototypeRouter

- [x] 2.1 创建 `src/service/value/router.py`：实现 `PrototypeRouter` 类
- [x] 2.2 实现硬编码样本覆盖表（工行/交行/建行/招行→bank；长江电力→high_dividend；贵州茅台→value_growth）
- [x] 2.3 实现财务特征启发式路由（杠杆率 > 0.85→bank；dividend_yield > 4.0 && growth_rate < 10→high_dividend；其余→value_growth；关键字段全 None→unknown）
- [x] 2.4 实现各原型 method_keys 映射表，满足 spec 中最小集合约束与排除规则
- [x] 2.5 创建 `test/service/value/test_router.py`：覆盖 spec `value-prototype-router` 全部 scenario（硬编码覆盖、特征路由、unknown 降级、方法集排除验证）

## 3. 区间聚合 — ValuationAggregator

- [x] 3.1 创建 `src/service/value/aggregator.py`：实现 `ValuationAggregator` 类
- [x] 3.2 实现过滤逻辑：过滤 error / Not Applicable / score 类方法（altman_z、piotroski_f、beneish_m、value_trap、sbc），评分类摘要追加 warnings
- [x] 3.3 实现 IQR 异常值过滤（len >= 4 时启用，过滤后 len < 2 则回退）
- [x] 3.4 实现聚合计算：base=median，low=p25，high=p75，MOS，price_percentile（clamp 0–100）
- [x] 3.5 实现 confidence 评估（High/Medium/Low 三级规则）
- [x] 3.6 实现 assessment 文本（低估/合理偏低/合理/合理偏高/高估 五级，基于 MOS 阈值）
- [x] 3.7 创建 `test/service/value/test_aggregator.py`：覆盖 spec `value-aggregator` 全部 scenario（评分类过滤、全不可用、单一有效值、IQR 过滤、聚合计算、confidence 评估）

## 4. 编排 Facade — ValueAnalyzer

- [x] 4.1 创建 `src/service/value/analyzer.py`：实现 `ValueAnalyzer` 类
- [x] 4.2 实现 `__init__(provider, engine=None, router=None, aggregator=None)` 依赖注入构造；engine=None 时自动使用 `default_engine()`
- [x] 4.3 实现 `from_config(config: dict) -> ValueAnalyzer` 类方法，从 app.yaml config 构造 `StockDataProvider` + `ValueAnalyzer`
- [x] 4.4 实现 `analyze(code: str) -> ValueAnalysisResult`：编排 provider → router → engine.run_selected → aggregator.aggregate → 构建 `ValueAnalysisResult`
- [x] 4.5 将评分类方法的 warnings 和原型降级 warnings 汇总到结果的 `warnings` 字段
- [x] 4.6 创建 `test/service/value/test_analyzer.py`：用 mock provider（返回固定 StockData）覆盖 spec `value-analyzer` 全部 scenario（价值成长分析、银行路由、非 A 股拒绝、数据不足降级、输出类型校验）

## 5. 导出与文档

- [x] 5.1 更新 `src/service/value/__init__.py`：导出 `ValueAnalyzer`、`ValueAnalysisResult`、`ValuationRange`、`PrototypeRouter`、`ValuationAggregator`
- [x] 5.2 运行 `pytest test/service/value/` 确认全部测试通过，`ruff check src/service/value/` 无报错
- [x] 5.3 更新 `docs/mrd/features/value-analysis.md` §14.2 分层缺口地图：将 A/B/C 三项标为已完成（✅）
