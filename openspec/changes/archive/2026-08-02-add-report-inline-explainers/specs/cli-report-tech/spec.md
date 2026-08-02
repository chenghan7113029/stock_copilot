## ADDED Requirements

### Requirement: 默认嵌入技术指标注释
`report tech` 的默认人类可读文本输出 SHALL 为报告中出现的主要技术指标（至少包括均线 MA、MACD、RSI、KDJ、量能/量比、Bias/乖离；若输出筹码分布则含筹码相关术语）提供中文含义与用途说明。注释 MUST 默认开启，本期无需额外 flag。

#### Scenario: RSI 带注释
- **WHEN** 用户执行 `report tech <code>`（非 `--json`）且报告含 RSI 数值行
- **THEN** 同一份文本输出中 SHALL 包含说明 RSI 含义或用途的中文注释（例如超买超卖解读）

#### Scenario: 缩写可理解
- **WHEN** 报告出现 MACD 或 KDJ
- **THEN** 文本中 SHALL 有对应中文释义或用途提示，使读者无需离开报告查阅外部文档即可理解其角色
