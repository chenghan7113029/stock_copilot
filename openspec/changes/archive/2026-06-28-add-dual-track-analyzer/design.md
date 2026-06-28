## Context

价值面 `ValueAnalyzer.analyze(code) → ValueAnalysisResult`（含公允价区间、安全边际、原型）与技术面 `TechAnalyzer.analyze(code) → TechAnalysisResult`（含趋势、评分、买入信号）均已完整实现并测试。两者当前是独立模块，`service/value/` 与 `service/tech/` 无交叉依赖。

上层应用（CLI、LLM 报告生成）需要一次调用得到双轨结果和一个综合操作建议，而不是分别调用两个 Analyzer 后手工合并。

## Goals / Non-Goals

**Goals:**
- `DualTrackAnalyzer.analyze(code) → DualTrackReport` 单一调用入口
- 确定性规则融合 `combined_signal`（不调用 LLM）
- 任一子 Analyzer 失败时降级输出（不阻断另一路）
- `analysis_summary` 纯字符串拼装，供上层 LLM prompt 消费
- `from_config(config_dict)` 工厂方法统一初始化

**Non-Goals:**
- LLM 调用（融合逻辑纯规则，LLM 在上层消费 summary）
- 修改 `ValueAnalyzer` 或 `TechAnalyzer` 接口
- 历史双轨结果存储
- 批量分析（V1 仅单股）

## Decisions

### D-1：模块位置
**决策**：新建 `src/service/dual_track/`，不放入 `service/value/` 或 `service/tech/` 下。  
**理由**：`dual_track` 是编排层，依赖 value 和 tech，单独目录符合依赖方向约定；避免循环依赖。

### D-2：并发策略
**决策**：V1 使用同步顺序调用（先 ValueAnalyzer，后 TechAnalyzer）。  
**备选**：`asyncio.gather` 或 `ThreadPoolExecutor` 并发。  
**理由**：两个 Analyzer 内部均有 IO（数据拉取），并发可减少延迟；但 V1 中数据源多为本地 SQLite + 同步 HTTP 库，异步改造成本高且引入复杂性。在 CLI/单次调用场景下顺序调用延迟可接受（约 2~5s）。保留 `_execute_concurrent` 接口预留位，V2 可替换。

### D-3：combined_signal 融合矩阵
**决策**：基于 `ValueRating`（价值面评级：UNDERVALUED/FAIR/OVERVALUED）× `BuySignal`（技术面 6 级）的 18 组合矩阵，输出 `CombinedSignal`（与 `BuySignal` 同 6 级枚举）：

| 价值面 \ 技术面 | STRONG_BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
|---|---|---|---|---|---|---|
| UNDERVALUED | STRONG_BUY | BUY | BUY | WAIT | WAIT | SELL |
| FAIR | BUY | BUY | HOLD | WAIT | SELL | STRONG_SELL |
| OVERVALUED | HOLD | WAIT | SELL | SELL | STRONG_SELL | STRONG_SELL |

**理由**：「价值低估 + 技术买入」是最强共振；「价值高估 + 技术空头」是最强做空信号；技术面空头且价值低估时保守 WAIT（等技术面企稳）。

### D-4：ValueRating 派生
**决策**：从 `ValueAnalysisResult.margin_of_safety` 派生：MOS > 20% → UNDERVALUED；MOS ∈ [-10%, 20%] → FAIR；MOS < -10% → OVERVALUED。阈值写入 `DualTrackConfig`，可配置。  
**理由**：MOS 是 `ValueAnalysisResult` 已有字段，无需新增计算；阈值基于 Graham 安全边际理论（20% 为经典低估门槛）。

### D-5：降级语义
**决策**：若 ValueAnalyzer 失败，`DualTrackReport.value_result = None`，`combined_signal` 直接等于 `tech_result.buy_signal`；反之亦然；两者均失败则 `combined_signal = WAIT`，`warnings` 含错误摘要。  
**理由**：用户至少可以得到单轨结果，不因一路失败而完全无输出。

## Risks / Trade-offs

- **[融合矩阵过度简化]** 18 组合矩阵无法覆盖所有市场情境（如价值低估但技术极端超买）→ Mitigation：矩阵可配置（`DualTrackConfig.fusion_matrix`）；`risk_factors` 中传递子分析的风险提示
- **[两路 IO 串行延迟]** 顺序调用约 2~5s，CLI 场景可接受 → Mitigation：V2 异步化，预留接口
- **[MOS 阈值主观性]** 20%/-10% 是经验值，不同行业适用性不同 → Mitigation：配置化，用户可覆盖
- **[ValueRating 依赖 fair_value_range]** 若 `fair_value_range` 为 None（所有方法不适用），MOS 无法计算 → Mitigation：此时 `ValueRating = UNKNOWN`，融合矩阵退化为技术面单轨

## Open Questions

- Q1：`analysis_summary` 的文本格式是否需要对齐后续 LLM prompt 模板？建议在 CLI/LLM 集成 change 中确定，本 change 仅输出结构化字段摘要。
