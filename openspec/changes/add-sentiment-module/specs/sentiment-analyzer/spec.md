## ADDED Requirements

### Requirement: SentimentAnalyzer 输出确定性情绪面分析结果
系统 SHALL 提供 `SentimentAnalyzer`，暴露 `analyze(code) -> SentimentAnalysisResult` 与 `analyze_offline(code) -> SentimentAnalysisResult | None` 两个方法，字段命名对齐 `ValueAnalysisResult`/`TechAnalysisResult` 习惯（`code`、`market_sentiment_status` 枚举、`market_sentiment_score`、`reasons: list[str]`、`warnings: list[str]`）。所有数值与等级判定 MUST 由代码规则计算，MUST NOT 由 LLM 生成或修改。

#### Scenario: 离线分析返回情绪面结果
- **WHEN** 本地已有最新市场情绪快照（`sync market` 已执行过），调用 `analyze_offline("600519")`
- **THEN** SHALL 返回 `SentimentAnalysisResult`，`market_sentiment_score` 为 0–100 区间数值，`market_sentiment_status` 为预定义枚举值之一

#### Scenario: 无本地市场快照时返回 None 并记录原因
- **WHEN** 本地无任何 `market_sentiment_snapshot` 记录
- **THEN** `analyze_offline` SHALL 返回 `None`，调用方（`DualTrackAnalyzer`）负责记录"情绪面无本地快照，请先运行 sync market"警告，不抛异常

### Requirement: 涨跌停家数比计算
系统 SHALL 计算涨跌停家数比 `limit_up_count / (limit_up_count + limit_down_count)`，当分母为 0 时结果 SHALL 为 `None` 并记录 warning，不得抛出除零异常。

#### Scenario: 正常计算涨跌停家数比
- **WHEN** 当日市场快照 `limit_up_count=50, limit_down_count=10`
- **THEN** 涨跌停家数比 SHALL 计算为 `50/60 ≈ 0.833`

#### Scenario: 涨跌停家数均为 0 时安全降级
- **WHEN** 当日市场快照 `limit_up_count=0, limit_down_count=0`
- **THEN** 涨跌停家数比 SHALL 为 `None`，`warnings` SHALL 包含说明，不抛异常

### Requirement: 恐慌贪婪代理指数复合计算与分量缺失降级
系统 SHALL 计算恐慌贪婪代理指数（0–100），由涨跌停家数比、两融余额环比变化率、全市场换手率分位三个分量加权计算。任一分量缺失时，SHALL 从权重中剔除该分量并对剩余分量重新归一化，不得因单一分量缺失导致整体指数为 `None`（除非全部三个分量均缺失）。

#### Scenario: 全部分量可用时正常加权
- **WHEN** 三个分量均有值
- **THEN** SHALL 按预定义权重加权求和得出 0–100 的复合指数

#### Scenario: 两融余额分量缺失时降级重新加权
- **WHEN** 两融余额环比变化率分量为 `None`，其余两个分量可用
- **THEN** SHALL 仅用剩余两个分量重新归一化权重计算复合指数，`warnings` SHALL 说明"两融余额分量缺失，指数基于部分分量计算"

#### Scenario: 全部分量缺失时返回 None
- **WHEN** 三个分量全部为 `None`
- **THEN** `market_sentiment_score` 与 `market_sentiment_status` SHALL 均为 `None`，`warnings` SHALL 说明数据不足
