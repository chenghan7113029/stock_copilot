# cli-report-sentiment Specification

## Purpose
TBD - created by archiving change add-sentiment-module. Update Purpose after archive.
## Requirements
### Requirement: `report sentiment` 严格离线且强制携带联合解读提示
CLI SHALL 新增 `python -m apps.cli report sentiment <code> [--json] [--output]` 子命令，严格离线（不发起网络请求），调用 `SentimentAnalyzer.analyze_offline(code)`。文本输出 MUST 包含不可关闭的固定提示："情绪面结论不得单独作为买卖依据，请结合 `report dual <code>` 查看价值+技术+情绪联合解读"。

#### Scenario: 成功输出情绪面报告并携带提示
- **WHEN** 本地已有市场情绪快照，执行 `python -m apps.cli report sentiment 600519`
- **THEN** 输出 SHALL 包含情绪等级、指数、涨跌停家数比，且 SHALL 包含固定的联合解读提示文案

#### Scenario: --json 输出同样包含提示字段
- **WHEN** 执行 `python -m apps.cli report sentiment 600519 --json`
- **THEN** JSON 输出 SHALL 包含一个固定字段（如 `disclaimer`）承载上述提示文案，供程序化消费方（如未来 Web 前端）识别并展示

#### Scenario: 本地无市场快照时的错误提示
- **WHEN** 本地无任何市场情绪快照
- **THEN** SHALL 输出"[error] 未找到市场情绪数据，请先运行 sync market"，与既有 `report tech`/`report value` 无缓存报错风格一致

