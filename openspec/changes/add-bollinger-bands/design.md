## Context

`IndicatorCalculator`（`src/service/tech/calculator.py`）已实现 MA/MACD/RSI/KDJ 四类指标，统一范式：`_calculate_X(df, params)` 用 pandas 向量化操作在 `work` DataFrame 上新增列，`_analyze_X(df, result, params)` 从最新一行取值、判断状态枚举、生成文案。四类指标都遵循「先在 DataFrame 上批量计算 → 再从最新行读取并分类」的两段式结构，`TechIndicators` 是承载这些字段的统一输出契约，`TechAnalysisResult` 在 `TechAnalyzer.analyze()` 里逐字段搬运。

布林带（Bollinger Bands）定义明确：中轨 = N 日收盘价简单移动平均，上/下轨 = 中轨 ± K × N 日收盘价标准差（标准配置 N=20, K=2，与 MA20 共享同一窗口，工程上可复用 `df["MA20"]` 避免重复计算）。带宽（`(upper-lower)/mid`）是判断「波动率收缩/扩张」的标准量化指标，通常需要与近期一段带宽历史比较（取百分位）才能判断"当前是否处于收缩/扩张阶段"，而不是看带宽绝对值。

## Goals / Non-Goals

**Goals:**
- 布林带计算方法与既有 MACD/RSI/KDJ 完全同构（同文件、同函数命名模式、同样通过 `IndicatorParams` 配置化）
- 新增 `BollingerStatus` 枚举，命名风格对齐 `VolumeStatus`/`RSIStatus`（中文枚举值、覆盖"收缩/扩张/突破"关键状态）
- 带宽百分位判断在现有 `kline_days=90` 默认窗口下即可工作，不要求扩展 K 线抓取窗口
- 布林带单状态文案（如"布林带收窄，波动率处于近期低位"）追加进既有 `signal_reasons`/`risk_factors`，但不影响 `signal_score` 数值

**Non-Goals:**
- 不实现"收窄后放量突破上轨"等跨指标组合信号识别（需要同时关联 `boll_status` + `volume_status` + 价格位置，属于更复杂的规则组合，V1 不做，见 Open Questions）
- 不新增 `ScoringParams` 布林带权重，不重新分配现有 100 分权重体系
- 不做布林带参数（N=20, K=2）的自适应调优，V1 使用业界标准默认值，可通过 `IndicatorParams` 手动配置

## Decisions

### 决策 1：计算范式与既有 MACD/RSI/KDJ 完全同构

**选择**：`IndicatorCalculator` 新增：
```python
def _calculate_bollinger(self, df: pd.DataFrame, params: IndicatorParams) -> pd.DataFrame:
    mid = df["close"].rolling(window=params.boll_period).mean()
    std = df["close"].rolling(window=params.boll_period).std()
    df["BOLL_MID"] = mid
    df["BOLL_UPPER"] = mid + params.boll_std_mult * std
    df["BOLL_LOWER"] = mid - params.boll_std_mult * std
    df["BOLL_BANDWIDTH"] = (df["BOLL_UPPER"] - df["BOLL_LOWER"]) / df["BOLL_MID"]
    return df
```
`_analyze_bollinger(df, result, params)` 从最新行读取 `boll_mid/upper/lower/bandwidth`，并用 `df["BOLL_BANDWIDTH"].rolling(params.boll_bandwidth_lookback).rank(pct=True)` 得到 `boll_percentile`（当前带宽在近期窗口内的百分位排名），据此判断 `BollingerStatus`。`TechIndicators` 新增对应字段，与 `macd_dif`/`rsi_6` 等字段并列。

**理由**：与用户明确要求一致——"计算范式要对齐现有 MACD/RSI/KDJ 的实现方式"。复用同一个 `IndicatorCalculator.calculate()` 调用链（在 `_calculate_macd`/`_calculate_rsi`/`_calculate_kdj` 之后追加 `_calculate_bollinger`），不新增平行的计算入口，保持 `TechAnalyzer.analyze()` 编排逻辑不变（布林带只是 `calculate()` 内部多算了几列，不是新的编排步骤）。

**备选方案**：
- 新建独立的 `BollingerCalculator` 类——拒绝：布林带和 MACD/RSI/KDJ 一样都是"从同一份日线 DataFrame 派生的技术指标"，没有理由单独抽出一个类，增加不必要的模块数量
- 用第三方库（如 `ta`/`pandas-ta`）直接计算——拒绝：本项目现有全部指标（MA/MACD/RSI/KDJ）都是手写 pandas 向量化实现，不引入指标计算类第三方依赖是既定风格（`requirements.txt` 当前无此类依赖），引入新依赖只为算一个标准公式的指标不划算

### 决策 2：中轨复用 MA20，避免重复计算；带宽百分位窗口用现有 90 天数据即可，不扩展 `kline_days`

**选择**：布林带默认周期 `boll_period=20` 与既有 MA20 周期相同，`_calculate_bollinger` 直接复用 `df["MA20"]`（若已计算）作为中轨，只需额外计算 `rolling(20).std()`。带宽百分位回溯窗口 `boll_bandwidth_lookback` 默认设为 40（约为 `kline_days=90` 天窗口下扣除 MA20 预热期后可用的带宽序列长度上限），在默认窗口下即可产出有意义的百分位排名，**不要求**扩展 `kline_days`。

**理由**：`kline_days=90` 约对应 60 个交易日，MA20 预热需要 20 日，剩余约 40 个交易日可以产出有效带宽序列——对"是否处于近期相对收缩/扩张"这个相对性判断已经足够（不需要与"上市以来全部历史"比较，只需要与"近几十个交易日"比较，这正是布林带这类波动率指标的典型使用方式）。若强行扩展 `kline_days` 到几百天，会像 `add-chip-distribution` design.md 决策 1 讨论的那样不必要地拖慢 `sync`（MA60/MACD/RSI/KDJ 计算量同步增加），但布林带本身完全不需要这么长的窗口。

**备选方案**：
- 扩展 `kline_days` 到 250+ 天以获得"年度带宽百分位"——拒绝：布林带收缩/扩张判断关心的是"近期相对状态"，不是"历史全周期状态"；扩展窗口对布林带毫无必要收益，反而拖慢现有 sync 性能（与 `add-chip-distribution` 讨论的成本一致）
- 带宽百分位样本不足（如数据行数刚好在 20~40 之间）时直接报错——拒绝：应该优雅降级为"样本不足，用可用窗口计算百分位并在 `warnings` 注明"，参照现有 `MA60 数据不足，以 MA20 替代` 的降级模式，不中断整体分析流程

### 决策 3：`BollingerStatus` 枚举设计；V1 只做单指标状态判断，组合信号留 Open Question

**选择**：新增 5 级枚举（命名风格对齐 `VolumeStatus`/`RSIStatus` 的中文短语枚举值）：

```python
class BollingerStatus(Enum):
    SQUEEZE = "收窄"           # 带宽百分位 <= boll_squeeze_percentile（默认 20）
    EXPANSION = "扩张"         # 带宽百分位 >= boll_expansion_percentile（默认 80）
    UPPER_BREAKOUT = "上轨突破"  # 收盘价 > 上轨
    LOWER_BREAKOUT = "下轨突破"  # 收盘价 < 下轨
    NORMAL = "正常"            # 其余情况
```

`TechAnalyzer.analyze()` 在既有 `ScoringEngine.score()` 调用之后，直接依据 `boll_status` 追加单状态文案：`SQUEEZE`/`EXPANSION` → `signal_reasons` 追加"布林带收窄，波动率处于近期低位，关注方向选择"类描述；`UPPER_BREAKOUT`/`LOWER_BREAKOUT` → 分别追加至 `signal_reasons`/`risk_factors`。**此追加逻辑绕开 `ScoringEngine`**（与 `add-chip-distribution` 决策 2 的处理方式一致），`signal_score`/`buy_signal` 不受影响。**不实现**"布林带收窄后放量突破上轨"这类需要同时关联 `boll_status` + `volume_status` + 价格位置的组合信号——V1 范围明确收敛为"指标计算 + 单指标状态判断"，组合信号留 Open Question。

**理由**：枚举命名沿用 `VolumeStatus`（"放量上涨"/"缩量回调"等 2 字/4 字中文短语）与 `RSIStatus`（"超买"/"超卖"等）的风格，保持整个 `tech_result.py` 枚举值的一致性。不参与打分的理由与 `add-chip-distribution`/`add-pattern-recognition` 一致：新指标刚上线，权重体系的重新校准是独立的架构决策，不应该和"新增一个指标"这个 change 耦合在一起。组合信号推迟的理由：组合信号需要明确"收窄多久算收窄"、"放量倍数阈值"、"突破确认的持续天数"等一系列新参数，规则设计复杂度显著高于单指标状态判断，且目前没有历史回测数据验证这类组合规则的实际有效性，V1 先把基础设施（指标本身）铺好，观察使用反馈后再设计组合规则。

**备选方案**：
- V1 直接实现"收窄后放量突破"组合信号——拒绝：如上所述规则设计复杂度高、缺乏回测验证，且用户任务描述中已经建议"V1 只做指标计算+状态判断"
- `BollingerStatus` 只做 3 级（收窄/扩张/正常），突破另开新字段（如 `boll_breakout: str`）——拒绝：突破也是"当前布林带状态"的一种，与收窄/扩张同属"相对于布林带的价格状态"这一概念范畴，合并进同一个枚举更符合与 `RSIStatus`（超买/强势/中性/弱势/超卖 同属一个枚举）的既有设计模式

## Risks / Trade-offs

- **[风险] 带宽百分位窗口（`boll_bandwidth_lookback=40`）样本量偏小，百分位排名对少数极端值敏感**→ **缓解**：阈值与窗口长度均在 `IndicatorParams` 中可配置；单测覆盖"样本不足时优雅降级并 warnings 提示"场景；后续若发现样本量不够稳定，可评估是否需要专门为布林带扩展一个独立的、比 `kline_days` 更长的历史窗口（不影响其他指标），但 V1 先用现有窗口验证
- **[风险] `SQUEEZE`/`UPPER_BREAKOUT`/`LOWER_BREAKOUT` 可能同一时间出现看似矛盾的组合（如收窄的同时突破上轨，即"挤压后突破"）但 V1 只输出单一枚举值，无法同时表达两种状态**→ **接受**：`BollingerStatus` 判断顺序为先判断突破（`UPPER_BREAKOUT`/`LOWER_BREAKOUT` 优先级高于 `SQUEEZE`/`EXPANSION`），因为"价格已突破轨道"是更明确、更需要关注的状态；若使用者需要同时知道"是否收窄"和"是否突破"，可直接读取 `boll_percentile` 数值字段（结构化数值不受枚举单选限制）
- **[风险] 中轨复用 `MA20` 隐含假设 `boll_period` 始终等于 `IndicatorParams.ma_periods` 中的 20；若未来用户将 `boll_period` 配置为非 20 的值，复用优化失效**→ **缓解**：`_calculate_bollinger` 内部判断 `params.boll_period == 20` 时才复用 `MA20` 列，否则单独计算 `rolling(boll_period).mean()`，不假设两者恒等，通过单测覆盖 `boll_period != 20` 场景

## Migration Plan

- `TechIndicators`/`TechAnalysisResult` 新增布林带字段，均带默认值（数值默认 0.0，枚举默认 `BollingerStatus.NORMAL` 或按现有其他指标默认值风格，`boll_percentile` 默认 `None` 表示未计算），对现有消费方是纯新增字段，非 breaking
- `IndicatorParams` 新增布林带参数，均有默认值，不改变现有 MA/MACD/RSI/KDJ 参数的默认行为
- `IndicatorCalculator.calculate()` 内部新增一次方法调用（`_calculate_bollinger` + `_analyze_bollinger`），不改变函数签名，现有调用方（`TechAnalyzer.analyze()`、既有单测）无需修改调用代码
- 回滚：删除 `calculator.py`/`config.py`/`tech_result.py`/`analyzer.py`/`formatters.py` 中的增量代码即可，不影响 MA/MACD/RSI/KDJ 既有计算与既有打分体系（无交叉依赖）

## Open Questions

- "布林带收窄后放量突破"等跨指标组合信号规则如何设计（收窄持续天数阈值、突破确认窗口、与 `volume_status` 的组合条件）？V1 不预先设计，留给后续 change，视 V1 上线后的观察反馈与是否有回测数据支持再决定
- 是否需要将 `boll_status`（或组合信号）纳入 `ScoringParams` 打分权重？与 `add-chip-distribution`/`add-pattern-recognition` 面临的问题相同，本 change 不预先设计扩展点，待多个新指标上线后统一评估打分体系是否需要一次性重新校准
- `boll_bandwidth_lookback` 默认 40 是否需要随 `kline_days` 配置联动（如 `kline_days` 被用户调大时按比例调大）？V1 保持两者独立配置，不建立联动关系，避免隐式耦合
