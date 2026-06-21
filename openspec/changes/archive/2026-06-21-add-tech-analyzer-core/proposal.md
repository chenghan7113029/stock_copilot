## Why

价值面分析已完整实现（23 种估值方法 + 编排层），但双轨分析报告缺少技术面这一轨——没有趋势判断，用户无法在价值面「便宜」时判断是否已止跌，容易在下跌通道中「接飞刀」。本 Change 建立技术面分析核心模块，补全 stock_copilot 的第二条分析轨道。

## What Changes

- **新增 K 线数据获取能力**：在 `BaostockFetcher` 和 `AKShareFetcher` 中分别新增 `fetch_kline()` 方法（日线 OHLCV，前复权），Baostock 为主，AKShare 为备；
- **新增 K 线本地缓存**：新建 `dao/kline_repo.py`（SQLite `kline` 表）；`KlineProvider` 实现「空洞检测 + 自动回填」——程序多日未运行时，自动识别并补拉缺失的历史交易日数据，当日数据始终实时拉取不写缓存；
- **新增技术指标计算层**：纯 pandas 实现 MA5/10/20/60、乖离率、MACD（12/26/9）、RSI（6/12/24，Wilder's EMA）、KDJ（9/3/3，J 值保留原始值不裁剪）、量能分析（5日量比）、支撑/压力位；
- **新增综合评分引擎**：`BullTrendScorer` 实现 6 维度 100 分制评分（趋势 30 + 乖离率 20 + 量能 15 + 支撑 10 + MACD 15 + 动量 10），权重全部可配置；极强趋势低评分时输出人工复核提示；
- **新增 `TechAnalyzer` Facade**：`analyze(code) → TechAnalysisResult`，依赖注入 `KlineProvider`，支持 `from_config` 工厂方法；
- **新增配置模型**：`TechAnalysisConfig`（`IndicatorParams` + `ScoringParams`），所有参数有默认值，支持外部覆盖；
- **新增 `service/tech/` 模块**，镜像 `service/value/` 的分层结构；
- **更新 MRD**：`docs/mrd/features/tech-analysis.md` 同步标注实现状态。

## Capabilities

### New Capabilities

- `tech-kline-provider`：K 线数据获取与本地缓存，含空洞检测与自动回填逻辑
- `tech-indicator-calculator`：日线技术指标纯计算层（MA / 乖离率 / MACD / RSI / KDJ / 量能 / 支撑位）
- `tech-analyzer`：技术面分析 Facade，`analyze(code) → TechAnalysisResult`，含可配置评分引擎

### Modified Capabilities

（无已有 spec 涉及技术面，无需修改现有 spec）

## Impact

**新增文件**：
- `src/dao/kline_repo.py` — KlineRepo（SQLite kline 表 CRUD）
- `src/data_provider/kline_provider.py` — KlineProvider（主备切换 + 缓存）
- `src/data_provider/baostock/fetcher.py` — 新增 `fetch_kline()` 方法
- `src/data_provider/akshare/fetcher.py` — 新增 `fetch_kline()` 方法
- `src/service/tech/__init__.py`
- `src/service/tech/config.py` — TechAnalysisConfig / IndicatorParams / ScoringParams
- `src/service/tech/calculator.py` — IndicatorCalculator
- `src/service/tech/scorer.py` — ScoringEngine Protocol + BullTrendScorer
- `src/service/tech/analyzer.py` — TechAnalyzer
- `src/service/tech/models/__init__.py`
- `src/service/tech/models/tech_result.py` — TechAnalysisResult + 所有状态枚举
- `test/service/tech/test_calculator.py`
- `test/service/tech/test_kline_provider.py`
- `test/service/tech/test_analyzer.py`

**修改文件**：
- `docs/mrd/features/tech-analysis.md` — 更新实现状态

**依赖**：`baostock >= 0.9.2`（已有）、`akshare >= 1.18.54`（已有）、`pandas`（已有）、`numpy`（已有）；无新增外部依赖。
