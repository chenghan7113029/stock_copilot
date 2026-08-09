## 1. 配置与数据模型

- [ ] 1.1 `src/service/tech/config.py` 的 `IndicatorParams` 新增：`boll_period: int = 20`、`boll_std_mult: float = 2.0`、`boll_bandwidth_lookback: int = 40`、`boll_squeeze_percentile: float = 20.0`、`boll_expansion_percentile: float = 80.0`
- [ ] 1.2 `src/service/tech/models/tech_result.py` 新增 `BollingerStatus` 枚举：`SQUEEZE = "收窄"`、`EXPANSION = "扩张"`、`UPPER_BREAKOUT = "上轨突破"`、`LOWER_BREAKOUT = "下轨突破"`、`NORMAL = "正常"`
- [ ] 1.3 `src/service/tech/calculator.py` 的 `TechIndicators` dataclass 新增字段：`boll_mid: float = 0.0`、`boll_upper: float = 0.0`、`boll_lower: float = 0.0`、`boll_bandwidth: float = 0.0`、`boll_percentile: float | None = None`、`boll_status: BollingerStatus = BollingerStatus.NORMAL`、`boll_signal: str = ""`
- [ ] 1.4 `src/service/tech/models/tech_result.py` 的 `TechAnalysisResult` 新增对应字段（同名，默认值风格与 `TechIndicators` 一致）

## 2. IndicatorCalculator 布林带计算

- [ ] 2.1 `src/service/tech/calculator.py` 新增 `_calculate_bollinger(self, df: pd.DataFrame, params: IndicatorParams) -> pd.DataFrame`：`boll_period == 20` 时复用 `df["MA20"]` 作为中轨，否则独立计算 `rolling(boll_period).mean()`；新增列 `BOLL_MID`/`BOLL_UPPER`/`BOLL_LOWER`/`BOLL_BANDWIDTH`
- [ ] 2.2 在 `calculate()` 方法内、`_calculate_kdj()` 调用之后新增 `work = self._calculate_bollinger(work, params)` 调用
- [ ] 2.3 新增 `_analyze_bollinger(self, df: pd.DataFrame, result: TechIndicators, params: IndicatorParams) -> None`：
  - 数据行数 < `boll_period` 时设置 `boll_signal = "数据不足"`，`warnings` 追加「布林带数据不足」，直接返回
  - 读取最新行 `boll_mid/upper/lower/bandwidth`
  - 计算 `boll_percentile`：取近 `min(boll_bandwidth_lookback, 可用样本数)` 个交易日的 `BOLL_BANDWIDTH` 序列做百分位排名（`pandas.Series.rank(pct=True)` 或等价实现）；样本数 < `boll_bandwidth_lookback` 时 `warnings` 追加样本不足说明
  - 按优先级判断 `boll_status`：收盘价 > 上轨 → `UPPER_BREAKOUT`；收盘价 < 下轨 → `LOWER_BREAKOUT`；否则百分位 <= `boll_squeeze_percentile` → `SQUEEZE`；百分位 >= `boll_expansion_percentile` → `EXPANSION`；否则 `NORMAL`
  - 设置对应 `boll_signal` 文案（如"布林带收窄（带宽百分位 {p:.0f}%），波动率处于近期低位"/"收盘价突破布林带上轨"）
- [ ] 2.4 在 `calculate()` 方法内调用 `self._analyze_bollinger(work, result, params)`
- [ ] 2.5 单测 `test/service/tech/test_calculator.py` 新增：
  - 标准参数下 `boll_mid == MA20`，上下轨与 pandas `rolling(20).std()` 参考值偏差 < 1e-6
  - `boll_period=10` 时 `boll_mid != MA20`（独立计算校验）
  - 数据不足 `boll_period` 日时降级场景（`boll_signal == "数据不足"`，`warnings` 含相应提示）
  - 带宽历史样本不足 `boll_bandwidth_lookback` 时的降级百分位计算与 `warnings`
  - `BollingerStatus` 四种状态（收窄/扩张/上轨突破/下轨突破）+ 正常状态的固定 fixture 验证，含"突破优先级高于收缩判断"的边界场景

## 3. TechAnalyzer 集成（不参与打分）

- [ ] 3.1 `src/service/tech/analyzer.py` 的 `analyze()` 在既有指标字段搬运处新增布林带字段搬运（`result.boll_mid = indicators.boll_mid` 等，共 7 个字段）
- [ ] 3.2 `analyze()` 在 `ScoringEngine.score()` 调用完成之后（评分结果已赋值给 `result.signal_score`/`buy_signal`/`signal_reasons`/`risk_factors`），新增布林带单状态文案追加逻辑：`SQUEEZE`/`EXPANSION` → `result.signal_reasons.append(...)`；`UPPER_BREAKOUT` → `result.signal_reasons.append(...)`；`LOWER_BREAKOUT` → `result.risk_factors.append(...)`
- [ ] 3.3 确认该追加逻辑**不**修改 `self._scorer.score()` 的调用参数或 `ScoringEngine` 接口签名（代码审查要点）
- [ ] 3.4 单测 `test/service/tech/test_analyzer.py` 新增场景：
  - 四种 `BollingerStatus` 分别验证对应文案出现在 `signal_reasons`/`risk_factors` 中
  - 回归对比：mock `IndicatorCalculator` 使 `boll_status` 分别为 `SQUEEZE`/`NORMAL` 两种情况，断言 `signal_score`/`buy_signal` 完全一致（证明布林带文案追加不影响打分）

## 4. CLI 展示

- [ ] 4.1 `src/apps/formatters.py` 的 `format_tech_report()` 新增「--- 布林带 ---」展示区块：`中轨={boll_mid} 上轨={boll_upper} 下轨={boll_lower} | 带宽={boll_bandwidth:.2%} (百分位 {boll_percentile:.0f}%) | {boll_status.value}`
- [ ] 4.2 确认 `--json` 模式下布林带字段（含枚举）可被 `json.loads` 正常解析
- [ ] 4.3 单测覆盖：标准场景与「数据不足降级」场景下 `format_tech_report()` 输出断言

## 5. 端到端验证

- [ ] 5.1 `sync 600519` 后运行 `report tech 600519`，人工核对「布林带」区块数值与 TradingView/同花顺等第三方图表的布林带（20, 2）参考值量级一致（允许合理误差，作为 sanity check，非精确对齐验收）
- [ ] 5.2 人工验证收窄/扩张/突破至少各一个历史区间样本（可用不同股票或不同日期区间），确认 `boll_status` 判断符合预期
- [ ] 5.3 运行 `pytest test/ -q -m "not network"` 确认全量测试通过，无回归

## 6. 文档更新

- [ ] 6.1 更新 `docs/mrd/features/tech-analysis.md` §2.2：F-19 状态由「待建」更新为「✅」；§4.2 输出契约补充布林带字段分组；§5.1 `IndicatorParams` 补充布林带参数说明
- [ ] 6.2 更新 `docs/mrd/roadmap-todo.md` §3：F-19 状态勾选为已实现，追加变更记录条目

## 7. 归档

- [ ] 7.1 确认 `tasks.md` 全部任务完成，`openspec validate add-bollinger-bands --strict` 通过
- [ ] 7.2 运行归档流程（`/opsx-archive add-bollinger-bands` 或等效命令），同步 delta specs 到 `openspec/specs/`
