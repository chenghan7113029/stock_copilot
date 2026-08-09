## Why

`docs/mrd/features/tech-analysis.md` §2.2 F-19（V2）与 `docs/mrd/roadmap-todo.md` §3 均列出「布林带」为技术面待办：现有 `IndicatorCalculator` 已有均线（MA5/10/20/60）、MACD、RSI、KDJ，但缺一个直接刻画「价格通道 + 波动率状态」的指标——布林带（均值 ± N×标准差）能同时提供动态支撑/压力参考（上下轨）与波动率收缩/扩张的量化判断（带宽），补齐现有指标体系在"波动率维度"上的空白。

## What Changes

- `src/service/tech/calculator.py` 的 `IndicatorCalculator` 新增布林带计算方法 `_calculate_bollinger()`，架构范式与现有 `_calculate_mas()`/`_calculate_macd()`/`_calculate_rsi()`/`_calculate_kdj()` 完全一致（纯 pandas 向量化，`rolling(window).mean()` + `rolling(window).std()`）
- `TechIndicators`（`src/service/tech/calculator.py`）与 `TechAnalysisResult`（`src/service/tech/models/tech_result.py`）新增布林带字段：`boll_mid`/`boll_upper`/`boll_lower`（中轨/上轨/下轨）、`boll_bandwidth`（带宽 = `(upper-lower)/mid`）、`boll_percentile`（带宽在近期窗口内的百分位）、`boll_status`（新增 `BollingerStatus` 5 级枚举，中文枚举值风格对齐 `VolumeStatus`/`RSIStatus`）、`boll_signal`（文案）
- `IndicatorParams` 新增布林带参数：`boll_period`（默认 20）、`boll_std_mult`（默认 2.0）、`boll_bandwidth_lookback`（带宽百分位回溯窗口）、`boll_squeeze_percentile`/`boll_expansion_percentile`（收缩/扩张判定阈值）
- **V1 范围（关键决策）**：只做指标计算 + 单指标状态判断（收缩/扩张/上轨突破/下轨突破/正常），`boll_signal` 单状态文案由 `TechAnalyzer.analyze()` 直接追加进既有 `signal_reasons`/`risk_factors`（不经过 `ScoringEngine` 打分路径，`BullTrendScorer` 权重体系零改动）；**不实现**跨维度组合信号（如"收窄后放量突破上轨"），留 Open Questions（design.md 决策 3）

**不包含**：
- 不新增 `ScoringParams` 布林带权重，不改变现有 6 维度 100 分打分体系
- 不实现"布林带收窄 + 放量 + 突破"等跨指标组合信号识别（V2 Open Question）
- 不扩展 `kline_days` 窗口（默认 90 天窗口下带宽百分位样本量足够，见 design.md）

## Capabilities

### New Capabilities
- `tech-bollinger-bands`：布林带（中轨/上轨/下轨/带宽/百分位）计算，`BollingerStatus` 状态判断

### Modified Capabilities
- `tech-indicator-calculator`：`IndicatorCalculator`/`TechIndicators` 新增布林带计算方法与字段
- `tech-analyzer`：`TechAnalysisResult` 新增布林带字段；`analyze()` 新增布林带单状态文案追加进 `signal_reasons`/`risk_factors`（不参与 `signal_score` 打分）

## Impact

- **修改文件**：
  - `src/service/tech/calculator.py`：新增 `_calculate_bollinger()`/`_analyze_bollinger()`，`TechIndicators` 新增布林带字段
  - `src/service/tech/config.py`：`IndicatorParams` 新增布林带参数
  - `src/service/tech/models/tech_result.py`：新增 `BollingerStatus` 枚举，`TechAnalysisResult` 新增布林带字段
  - `src/service/tech/analyzer.py`：`analyze()` 新增布林带字段合并 + 单状态文案追加逻辑
  - `src/apps/formatters.py`：`format_tech_report()` 新增布林带展示区块
  - `test/service/tech/test_calculator.py`：新增布林带计算单测
  - `test/service/tech/test_analyzer.py`：新增布林带集成场景
- **依赖**：无新增第三方依赖（纯 pandas 向量化，复用现有 K 线 DataFrame）
- **文档**：`docs/mrd/features/tech-analysis.md` §2.2（F-19 状态更新 + §4.2 输出契约 + §5 配置模型补充字段）、`docs/mrd/roadmap-todo.md` §3（F-19 状态更新 + 变更记录）
