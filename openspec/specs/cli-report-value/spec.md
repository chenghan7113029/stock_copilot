# cli-report-value Specification

## Purpose

CLI 离线价值面报告命令：读快照 → 估值计算 → 格式化输出。

## Requirements

### Requirement: report value 离线分析
`report value <code>` SHALL 从本地 `StockSnapshotRepo` 读取价值面快照，运行 `ValueAnalyzer.analyze()` 并输出格式化结果，不触发任何网络请求。

#### Scenario: 正常离线报告
- **WHEN** 用户执行 `python -m apps.cli report value 600519`（已先 sync）
- **THEN** 调用 `StockDataProvider.get_stock_data_offline('600519')`
- **THEN** 运行 `ValueAnalyzer.analyze()`
- **THEN** stdout 输出人类可读文本报告，包含估值区间与评分
- **THEN** 程序以退出码 0 结束

#### Scenario: 报告头部含数据时效水印
- **WHEN** 执行 `report value 600519`
- **THEN** 输出头部包含「[离线模式] 价值快照: YYYY-MM-DD HH:MM」

### Requirement: report value --json 输出
`report value --json` SHALL 将 `ValueAnalysisResult` 序列化为 JSON 字符串并输出到 stdout。

#### Scenario: JSON 输出
- **WHEN** 用户执行 `python -m apps.cli report value 600519 --json`
- **THEN** stdout 输出合法 JSON，包含所有 `ValueAnalysisResult` 字段
- **THEN** `Enum`、`date`、`None` 类型正确序列化

### Requirement: report value --output 落盘
`report value --output <path>` SHALL 将报告写入指定文件。

#### Scenario: 落盘到指定路径
- **WHEN** 用户执行 `python -m apps.cli report value 600519 --output reports/600519_value.txt`
- **THEN** 报告内容写入指定路径
- **THEN** stdout 输出「已保存至 reports/600519_value.txt」

### Requirement: report value 无缓存提示
缓存为空时 SHALL 打印友好提示，不崩溃。

#### Scenario: 未先 sync 就运行 report
- **WHEN** `StockSnapshotRepo` 中没有指定代码的数据
- **THEN** stderr 输出「[error] 未找到 600519 的价值快照，请先运行 sync」
- **THEN** 退出码为 1

### Requirement: DCF 与 EPV 方法行补充语义说明
价值面报告中，`dcf` 和 `epv` 方法的输出行 SHALL 分别追加括号内的语义提示，帮助用户理解两者差异，避免直接对比公允价数值时产生误判。

- `dcf` 行：追加 `(含增长假设)` 及 DCF 所用 `g₁` 与折现率简报
- `epv` 行：追加 `(零增长地板价)`

#### Scenario: 价值报告中 DCF/EPV 行有语义提示
- **WHEN** `format_value_report(result)` 且 result 包含 dcf 与 epv 方法结果
- **THEN** dcf 方法行包含 "(含增长假设)" 字样，epv 方法行包含 "(零增长地板价)" 字样

#### Scenario: 语义提示不影响 JSON 模式
- **WHEN** `format_value_report(result, as_json=True)`
- **THEN** JSON 输出中 `method_results.dcf.analysis` 字段包含增长假设说明，不影响结构

### Requirement: 默认嵌入估值方法讲解与价值陷阱说明
`report value` 的默认人类可读文本输出 SHALL 对每个 Applicable 估值方法嵌入完整讲解卡片（含义、适用、公式、本次入参与来源、结果），并对价值陷阱（若存在该方法结果）嵌入白话拆解。Not Applicable 方法 SHALL 以中文说明不适用原因。讲解 MUST 默认开启，本期无需用户传入额外 flag。

#### Scenario: 文本报告含方法卡片
- **WHEN** 用户执行 `report value <code>`（非 `--json`）且存在至少一个 Applicable 方法
- **THEN** stdout 文本 SHALL 包含该方法的讲解卡片关键要素（至少：含义或适用说明、公式或「公式未提供」、结果中文评估）

#### Scenario: 价值陷阱详解出现在 value 报告
- **WHEN** 方法结果含 `value_trap` 且可解析 overall_risk
- **THEN** 文本报告 SHALL 包含价值陷阱总体风险的中文解释与维度拆解

#### Scenario: 评估词中文化
- **WHEN** 方法评估原值为 `Undervalued` / `Overvalued` 等英文词
- **THEN** 默认文本报告的方法行或卡片结果区 SHALL 优先显示中文「低估」/「高估」等对应词
