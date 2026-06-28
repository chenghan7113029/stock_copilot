## Why

价值面（`ValueAnalyzer`）与技术面（`TechAnalyzer`）已各自完整交付，但两者目前独立运行，没有统一的双轨入口。上层应用（CLI/API/LLM 报告）需要一次调用同时拿到「价值面公允价 + 技术面信号」，并获得一个综合操作建议（`combined_signal`），以支撑 product-overview §5.3「多维立体看板」与 LLM 报告生成。

## What Changes

- 新建 `DualTrackReport` 数据类：封装 `ValueAnalysisResult`、`TechAnalysisResult` 及派生字段 `combined_signal`（6 级枚举）、`analysis_summary`（结构化摘要文本）
- 新建 `DualTrackAnalyzer` Facade：`analyze(code) → DualTrackReport`，内部并发调用两个 Analyzer（`asyncio.gather` 或线程池），任一失败时降级输出，不阻断另一路结果
- `combined_signal` 融合逻辑（确定性规则，不调用 LLM）：
  - 价值面「高估」且技术面「空头」→ STRONG_SELL
  - 价值面「低估」且技术面「买入或强烈买入」→ STRONG_BUY
  - 价值面「低估」但技术面「卖出/观望」→ WAIT（价值确认，技术未就绪）
  - 价值面「合理」且技术面「买入」→ BUY
  - 其余组合 → HOLD 或 WAIT（具体矩阵见 design.md）
- `analysis_summary` 生成：纯确定性字符串拼装（不调 LLM），输出结构化摘要供上层 LLM 使用
- 新增 `DualTrackAnalyzer.from_config(config_dict)` 工厂方法，统一初始化两个子 Analyzer

## Capabilities

### New Capabilities

- `dual-track-analyzer`：双轨分析 Facade — `DualTrackAnalyzer.analyze(code) → DualTrackReport`；内部串联 ValueAnalyzer + TechAnalyzer；确定性规则融合 combined_signal；结构化摘要供 LLM 消费

### Modified Capabilities

无（ValueAnalyzer 与 TechAnalyzer 接口不变，仅新增上层编排）

## Impact

- `src/service/dual_track/analyzer.py`：新建 `DualTrackAnalyzer`
- `src/service/dual_track/models/report.py`：新建 `DualTrackReport` + `CombinedSignal` 枚举
- `src/service/dual_track/signal_fusion.py`：新建 `SignalFusion`（确定性融合规则矩阵）
- `src/service/dual_track/__init__.py`：公共导出
- `test/service/dual_track/test_analyzer.py`：完整流程 mock 测试
- `test/service/dual_track/test_signal_fusion.py`：覆盖所有融合矩阵组合
- `docs/mrd/features/tech-analysis.md`：§10.3 双轨集成点状态更新
