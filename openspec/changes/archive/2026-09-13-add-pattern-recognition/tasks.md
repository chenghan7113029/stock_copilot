## 1. 配置与数据模型

- [x] 1.1 `src/service/tech/config.py` 新增 `PatternParams` dataclass：`doji_body_ratio_max: float = 0.1`、`hammer_shadow_ratio_min: float = 2.0`、`hammer_upper_shadow_ratio_max: float = 1.0`（上影线相对实体的倍数上限）
- [x] 1.2 `TechAnalysisConfig` 新增字段 `pattern_params: PatternParams = field(default_factory=PatternParams)`
- [x] 1.3 `src/service/tech/models/tech_result.py` 新增 `CandlestickPattern` 枚举：`DOJI = "十字星"`、`HAMMER = "锤头线"`、`HANGING_MAN = "吊颈线"`、`BULLISH_ENGULFING = "看涨吞没"`、`BEARISH_ENGULFING = "看跌吞没"`
- [x] 1.4 `tech_result.py` 新增 `PatternSignal` dataclass：`pattern: CandlestickPattern`、`direction: str`、`trade_date: str`、`description: str`
- [x] 1.5 `TechAnalysisResult` 新增字段 `candlestick_patterns: list[PatternSignal] = field(default_factory=list)`

## 2. PatternRecognizer 核心实现

- [x] 2.1 新建 `src/service/tech/pattern_recognizer.py`：`PatternRecognizer.recognize(df: pd.DataFrame, trend_status: TrendStatus, params: PatternParams) -> list[PatternSignal]`
- [x] 2.2 实现 `_detect_doji(latest_row, params) -> PatternSignal | None`：`abs(close-open) / (high-low) <= doji_body_ratio_max`（振幅为 0 时视为满足）
- [x] 2.3 实现 `_detect_hammer_or_hanging_man(latest_row, trend_status, params) -> PatternSignal | None`：计算实体、上影线、下影线长度；下影线 ≥ 实体 × `hammer_shadow_ratio_min`，上影线 ≤ 实体 × `hammer_upper_shadow_ratio_max`；命中几何特征后按 `trend_status` 分支：空头相关 → `HAMMER`（方向"看多"），多头相关 → `HANGING_MAN`（方向"看空"），`CONSOLIDATION` → 不标注
- [x] 2.4 实现 `_detect_engulfing(latest_two_rows, params) -> PatternSignal | None`：当日阳线且实体覆盖前日阴线实体 → `BULLISH_ENGULFING`；当日阴线且实体覆盖前日阳线实体 → `BEARISH_ENGULFING`
- [x] 2.5 `recognize()` 汇总以上三个检测函数结果（過濾 None），数据行数 < 2 时直接返回空列表（不抛异常）
- [x] 2.6 单测 `test/service/tech/test_pattern_recognizer.py`：覆盖 spec 中十字星/锤头/吊颈线/看涨吞没/看跌吞没的命中与未命中场景，含边界值（振幅为 0、趋势为 CONSOLIDATION 时不标注锤头/吊颈线）

## 3. TechAnalyzer 编排集成（不参与打分）

- [x] 3.1 `src/service/tech/analyzer.py` 的 `analyze()` 在周线分析步骤之后新增：调用 `PatternRecognizer.recognize(work_df, indicators.trend_status, self._config.pattern_params)`，结果直接赋值给 `result.candlestick_patterns`
- [x] 3.2 确认该调用**不**传入 `ScoringEngine`、**不**修改 `signal_reasons`/`risk_factors`/`signal_score`/`buy_signal` 的既有赋值逻辑（代码审查要点，非新增逻辑）
- [x] 3.3 单测 `test/service/tech/test_analyzer.py` 新增场景：
  - 命中形态时 `candlestick_patterns` 非空，且与「mock 掉 PatternRecognizer 返回空列表」相比，`signal_score`/`buy_signal`/`signal_reasons`/`risk_factors` 完全一致（回归对比断言）
  - 数据不足/无形态命中时 `candlestick_patterns == []`

## 4. CLI 展示

- [x] 4.1 `src/apps/formatters.py` 的 `format_tech_report()` 新增「--- K 线形态 ---」展示区块，逐条展示 `{trade_date} {pattern.value}（{direction}）：{description}`；`candlestick_patterns` 为空时跳过该区块
- [x] 4.2 确认 `--json` 模式下 `candlestick_patterns` 可被 `json.loads` 正常解析（枚举需转字符串，参照现有 `_dump_json` 对其余枚举字段的处理方式）
- [x] 4.3 单测覆盖：有形态命中/无形态命中两种场景下 `format_tech_report()` 输出断言

## 5. 端到端验证

- [x] 5.1 构造历史上已知发生过看涨吞没/十字星的真实 K 线区间（或人工构造 fixture），运行 `report tech <code>` 确认「K 线形态」区块正确标注
- [x] 5.2 对同一股票分别在"启用形态识别"与"临时 mock 形态识别返回空列表"两种路径下运行分析，人工核对 `signal_score`/`buy_signal` 输出完全一致
- [x] 5.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/features/tech-analysis.md` §2.2：F-18 状态由「待建」更新为「✅」，说明 V1 范围（4 类形态、不参与打分）；§4.2 输出契约补充 `candlestick_patterns` 字段
- [x] 6.2 更新 `docs/mrd/roadmap-todo.md` §3：F-18 状态勾选为已实现，追加变更记录条目

## 7. 归档

- [x] 7.1 确认 `tasks.md` 全部任务完成，`openspec validate add-pattern-recognition --strict` 通过
- [x] 7.2 运行归档流程（`/opsx-archive add-pattern-recognition` 或等效命令），同步 delta specs 到 `openspec/specs/`
