## Why

`docs/mrd/features/tech-analysis.md` §2.2 F-18（V2）与 `docs/mrd/roadmap-todo.md` §3 均列出「K 线形态识别」为技术面待办：当前 `IndicatorCalculator` 只从统计意义上的均线/MACD/RSI/KDJ 判断趋势与动量，完全忽略单根/双根 K 线本身的开高低收几何关系（如十字星代表多空分歧加剧、锤头线/吞没形态代表趋势末端反转信号）。这类形态的识别规则是明确的数学判断（开高低收数值比较），属于`docs/agent-engineering-quality.md` 强调的「确定性计算核」范畴——**能用确定性代码完成的判断，不应该交给 LLM 或图像识别模型**，用规则代码即可实现且零幻觉风险。

## What Changes

- 新增 `src/service/tech/pattern_recognizer.py`：`PatternRecognizer`（纯 pandas/numpy，无 IO，输入 K 线 DataFrame，输出结构化形态列表），架构范式对齐现有 `IndicatorCalculator`
- **V1 范围收敛到 4 类规则明确的经典形态**（十字星、锤头线/吊颈线、看涨/看跌吞没），其余形态（晨星、暮星、三兵、穿头破脚等）需要更复杂的多 K 线组合规则，留 Open Questions（design.md 决策 2）
- 新增 `CandlestickPattern` 枚举与 `PatternSignal` 结构化结果（`src/service/tech/models/tech_result.py`），`TechAnalysisResult` 新增独立字段 `candlestick_patterns: list[PatternSignal]`
- 新增 `PatternParams` 配置（`src/service/tech/config.py`，纳入 `TechAnalysisConfig`），可配置形态判定阈值（如十字星实体占比上限、锤头下影线倍数下限等）
- **关键决策：形态识别结果不参与 `signal_score`/`buy_signal` 打分**，仅作为独立的「形态提示」结构化列表附加展示（详见 design.md 决策 3），避免规则粒度更细、尚未经生产验证的新信号污染现有已验证的 6 维度评分体系
- `TechAnalyzer.analyze()` 编排新增一步：调用 `PatternRecognizer.recognize(df)`，结果直接赋值给 `result.candlestick_patterns`，**不经过** `ScoringEngine`

**不包含**：
- 不实现晨星/暮星/三兵/穿头破脚等更复杂的多 K 线组合形态（V1 范围收敛，见 Open Questions）
- 不使用任何图像识别模型或 LLM 判断形态——纯规则代码
- 不将形态识别结果计入 `signal_score`，也不写入 `signal_reasons`/`risk_factors`（保持既有打分体系零改动）

## Capabilities

### New Capabilities
- `tech-pattern-recognition`：K 线形态规则识别（十字星/锤头/吊颈/吞没），纯规则代码，独立展示不参与打分

### Modified Capabilities
- `tech-analyzer`：`TechAnalysisResult` 新增 `candlestick_patterns` 字段；`TechAnalyzer.analyze()` 编排新增形态识别步骤（不影响既有 `signal_score`/`buy_signal` 计算路径）

## Impact

- **新增文件**：
  - `src/service/tech/pattern_recognizer.py`
  - `test/service/tech/test_pattern_recognizer.py`
- **修改文件**：
  - `src/service/tech/models/tech_result.py`：新增 `CandlestickPattern` 枚举、`PatternSignal` dataclass、`TechAnalysisResult.candlestick_patterns` 字段
  - `src/service/tech/config.py`：新增 `PatternParams`，纳入 `TechAnalysisConfig`
  - `src/service/tech/analyzer.py`：`analyze()` 新增形态识别步骤
  - `src/apps/formatters.py`：`format_tech_report()` 新增「K 线形态」展示区块
  - `test/service/tech/test_analyzer.py`：新增形态识别集成场景
- **依赖**：无新增第三方依赖（纯 pandas/numpy 规则判断，复用已有 K 线 DataFrame，无需新数据源）
- **文档**：`docs/mrd/features/tech-analysis.md` §2.2（F-18 状态更新 + §4.2 输出契约补充字段）、`docs/mrd/roadmap-todo.md` §3（F-18 状态更新 + 变更记录）
