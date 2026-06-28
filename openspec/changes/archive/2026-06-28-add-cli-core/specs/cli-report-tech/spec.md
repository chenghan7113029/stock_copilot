## ADDED Requirements

### Requirement: report tech 离线分析
`report tech <code>` SHALL 从本地缓存读取 K 线数据，运行 `TechAnalyzer.analyze()` 并输出格式化结果，不触发任何网络请求。

#### Scenario: 正常离线报告
- **WHEN** 用户执行 `python -m apps.cli report tech 600519`（已先 sync）
- **THEN** 从 `KlineRepo` 读取缓存 K 线
- **THEN** 运行技术面分析
- **THEN** stdout 输出人类可读文本报告
- **THEN** 程序以退出码 0 结束

#### Scenario: 报告头部含数据时效水印
- **WHEN** 执行 `report tech 600519`
- **THEN** 输出头部第一行为「[离线模式] K线末行: YYYY-MM-DD | quote_mode: eod」
- **THEN** 如上次 sync 时使用了 --realtime，quote_mode 显示 realtime

### Requirement: report tech --json 输出
`report tech --json` SHALL 将 `TechAnalysisResult` 序列化为 JSON 字符串并输出到 stdout。

#### Scenario: JSON 输出
- **WHEN** 用户执行 `python -m apps.cli report tech 600519 --json`
- **THEN** stdout 输出合法 JSON，包含所有 `TechAnalysisResult` 字段
- **THEN** `Enum` 值以字符串形式序列化，`date`/`None` 类型正确处理

### Requirement: report tech --output 落盘
`report tech --output <path>` SHALL 将报告写入指定文件，同时 stdout 输出「已保存至 <path>」。

#### Scenario: 落盘到指定路径
- **WHEN** 用户执行 `python -m apps.cli report tech 600519 --output reports/600519.txt`
- **THEN** 报告内容写入 `reports/600519.txt`
- **THEN** stdout 输出「已保存至 reports/600519.txt」

### Requirement: report tech 无缓存提示
缓存为空时 SHALL 打印友好提示，不崩溃。

#### Scenario: 未先 sync 就运行 report
- **WHEN** `KlineRepo` 中没有指定代码的数据
- **THEN** stderr 输出「[error] 未找到 600519 的 K线缓存，请先运行 sync」
- **THEN** 退出码为 1
