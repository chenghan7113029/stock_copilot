## Why

方法论库（Phase 0–8，23 种估值方法）已完成，但 `service/value/` 层缺少将数据获取、原型路由、方法运行、区间聚合串联起来的编排层——调用方无法用一次函数调用获取价值面分析结果。本次 change 建立这个编排层，使价值面分析从"计算器库"升级为"可调用分析服务"，为后续 API/CLI/LLM 集成提供统一入口。

## What Changes

- 新增 `src/service/value/analyzer.py`：`ValueAnalyzer` Facade，单一入口 `analyze(code) -> ValueAnalysisResult`；内部编排数据获取 → 原型路由 → 方法运行 → 区间聚合
- 新增 `src/service/value/aggregator.py`：`ValuationAggregator`，将多方法 `ValuationResult` 聚合为 `fair_value_range` + `margin_of_safety` + `price_percentile`；评分类方法（`output_type = "score"`）不参与聚合，进入 `warnings`
- 新增 `src/service/value/router.py`：`PrototypeRouter`，V1 实现"行业代码 + 财务特征启发"路由（银行/高股息/价值成长），返回对应 method_keys 列表；支持硬编码覆盖以确保三原型样本正确路由
- 新增 `src/service/value/models/analysis_result.py`：`ValueAnalysisResult` 数据类，输出契约（MRD §6.1 全部字段）
- 新增 `test/service/value/test_analyzer.py`、`test_aggregator.py`、`test_router.py`：离线单测，mock `StockDataProvider`
- 更新 `src/service/value/__init__.py`：导出 `ValueAnalyzer`、`ValueAnalysisResult`
- 更新 `docs/mrd/features/value-analysis.md` §14：标注编排层完成状态

## Capabilities

### New Capabilities

- `value-analyzer`：`ValueAnalyzer` Facade，编排数据获取 → 路由 → 运行 → 聚合，输出 `ValueAnalysisResult`
- `value-aggregator`：`ValuationAggregator`，多方法公允价 → 区间聚合，含异常值过滤、MOS、分位计算
- `value-prototype-router`：`PrototypeRouter`，股票原型分类（银行/高股息/价值成长/未知）+ method_keys 路由

### Modified Capabilities

（无现有 spec 的行为变更）

## Impact

- `src/service/value/`：新增 `analyzer.py`、`aggregator.py`、`router.py`、`models/analysis_result.py`
- `test/service/value/`：新增对应单测文件
- `src/service/value/__init__.py`：补充导出
- `docs/mrd/features/value-analysis.md`：§14 状态更新
- 依赖：`src/service/value/valuation/`（已有）、`src/data_provider/provider.py`（已有）、`src/common/config_loader.py`（已有）
- 无 breaking change；现有 `valuation/` 方法库不受影响
