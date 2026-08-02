## MODIFIED Requirements

### Requirement: 技术面文本格式化
`format_tech_report(result: TechAnalysisResult, as_json: bool = False) -> str` SHALL 将技术面分析结果转换为可读字符串。

非 JSON（人类可读）模式固定输出字段集，并以 Markdown 组织：
- 一级标题含代码的报告名
- 数据时效水印（K 线末日 + quote_mode）
- 综合评分与信号（score / buy_signal）
- 趋势状态（trend_status）
- 周线趋势（weekly_trend_status）
- 各指标分项（MA、MACD、RSI、KDJ、Volume、Bias）
- 支撑/压力区间
- 风险提示（risks）

#### Scenario: text 格式输出
- **WHEN** 传入合法 `TechAnalysisResult` 且 `as_json=False`
- **THEN** 返回多行 Markdown 字符串，首行（或首个标题行）为以 `# ` 开头且含技术面报告语义与 `<code>` 的标题
- **THEN** 包含「综合评分」「信号」「周线」等固定关键词

#### Scenario: JSON 格式输出
- **WHEN** 传入合法 `TechAnalysisResult` 且 `as_json=True`
- **THEN** 返回合法 JSON 字符串（`json.loads()` 不抛异常）
- **THEN** `Enum` 值序列化为 `.value` 字符串，`date` 序列化为 `"YYYY-MM-DD"`，`None` 序列化为 `null`

### Requirement: 价值面文本格式化
`format_value_report(result: ValueAnalysisResult, as_json: bool = False) -> str` SHALL 将价值面分析结果转换为可读字符串。

非 JSON 模式固定输出字段集，并以 Markdown 组织：
- 一级标题含代码的报告名
- 数据时效水印（快照时间）
- 公司名称 / 行业 / 市值
- 综合评分与投资建议
- 各估值方法结果汇总（intrinsic_value / margin_of_safety）
- 质量评分与成长评分
- 风险提示

#### Scenario: text 格式输出
- **WHEN** 传入合法 `ValueAnalysisResult` 且 `as_json=False`
- **THEN** 返回多行 Markdown 字符串，首行（或首个标题行）为以 `# ` 开头且含价值面报告语义与 `<code>` 的标题
- **THEN** 包含「估值」「安全边际」「评分」等固定关键词

#### Scenario: JSON 格式输出
- **WHEN** 传入合法 `ValueAnalysisResult` 且 `as_json=True`
- **THEN** 返回合法 JSON 字符串，字段类型同技术面规范
