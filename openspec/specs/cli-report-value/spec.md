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

### Requirement: report value 默认 Markdown 文本与 .md 落盘约定
`report value` 在非 `--json` 时的人类可读输出 SHALL 为 Markdown（见 `report-markdown-output`），并保留默认嵌入的估值方法讲解与价值陷阱说明。批量 `-o` 目录默认文件名 SHALL 使用 `{code}_value.md`。

#### Scenario: 批量 value 写 md
- **WHEN** 用户执行 `report value --watchlist -o reports/out`（非 `--json`）
- **THEN** 输出文件扩展名 SHALL 为 `.md`，且文本中仍含方法讲解相关要素（若存在 Applicable 方法）

### Requirement: report value 报告头部渲染价值陷阱高危警示

`format_value_report()` 文本渲染路径 SHALL 在 `result.value_trap_alert` 非空时，于报告头部（名称/原型之后、评估/置信度之前）插入独立于文末 `--- 警告 ---` 区块的醒目警示区块，展示 `value_trap_alert` 的完整文案。`result.value_trap_alert` 为空时 SHALL 不渲染该区块，输出与现状一致。

`--json` 输出路径 SHALL 自动包含 `value_trap_alert` 字段（沿用既有 dataclass 序列化逻辑，无需额外分支）。

#### Scenario: High 风险时渲染醒目区块

- **WHEN** `result.value_trap_alert = "🚨 疑似价值陷阱（High Risk）：..."`
- **THEN** `format_value_report(result)` 返回的文本在"评估:"行之前包含该警示文案
- **THEN** 文末仍照常输出 `--- 警告 ---` 区块（包含 value_trap 的既有摘要行），两者不冲突不去重

#### Scenario: 非 High 风险时不渲染

- **WHEN** `result.value_trap_alert is None`
- **THEN** `format_value_report(result)` 输出中不出现警示区块，其余内容与本 change 之前完全一致

#### Scenario: JSON 输出包含新字段

- **WHEN** `format_value_report(result, as_json=True)` 且 `result.value_trap_alert` 非空
- **THEN** 输出 JSON 顶层包含键 `"value_trap_alert"`，值为对应文案

### Requirement: 诚实降级标的在价值报告中去行动化展示

当 `ValueAnalysisResult.methodology_applicable is False` 时，`format_value_report`（非 `--json`）SHALL：

1. 在报告靠前位置展示诚实警告（来自 `warnings` 中的缺口文案，或等价置顶块）
2. 主评估行展示 `assessment` 原文「方法暂不适用」（不得改写成「低估」「高估」）
3. 若展示安全边际或公允区间，SHALL 附带「对照用」或等价中文标注，表明不可作为买卖依据

`--json` 模式 SHALL 原样序列化 `methodology_applicable` 与 `assessment` 字段，不做改写。

#### Scenario: 比亚迪文本报告主评估非低估

- **WHEN** `format_value_report(result)` 且 `result.code=="002594"`，`methodology_applicable=False`，`assessment=="方法暂不适用"`
- **THEN** 文本含「方法暂不适用」，含诚实警告关键语义，若出现安全边际数字则同时出现「对照用」或等价标注

#### Scenario: JSON 含 methodology_applicable

- **WHEN** `format_value_report(result, as_json=True)` 且 result 含 `methodology_applicable=False`
- **THEN** JSON 中该字段为 `false`，`assessment` 为「方法暂不适用」

#### Scenario: 正常标的展示不变

- **WHEN** `methodology_applicable=True` 且 assessment 为「低估」
- **THEN** 文本可正常显示「低估」，不强制追加「对照用」标注

### Requirement: `report value` 文本输出的价格分位呈现方式
`format_value_report()` 文本模式输出 SHALL 以定性分档描述（`percentile_band()` 结果）作为价格分位信息的呈现主体，原始数值 SHALL 以弱化形式（如括号内标注）伴随展示，不得以精确数值作为该信息行的句首/主语。`--json` 模式 SHALL 保持 `price_percentile` 原始数值字段不变，供程序化消费方使用。

#### Scenario: 文本模式呈现定性分档优先于数值
- **WHEN** `result.price_percentile = 72.3`，执行 `report value <code>`（文本模式，默认不带 `--show-anchor-price`）
- **THEN** 输出 SHALL 包含类似"当前价格处于历史估值区间中高位（分位 72%）"的表达，不得输出旧格式"价格分位: 72.3%"作为独立呈现

#### Scenario: --json 模式数值字段不变
- **WHEN** 执行 `report value <code> --json`
- **THEN** JSON 输出中 `price_percentile` SHALL 为原始数值（如 `72.3`），不受文本呈现规则调整影响

#### Scenario: price_percentile 为 None 时不展示分档
- **WHEN** `result.price_percentile is None`
- **THEN** 文本输出 SHALL 不包含分位相关行（沿用既有"字段为 None 时不展示该行"约定）

### Requirement: 价值报告展示 V2 情景与周期语义

当结果含情景估值或周期调整语义时，`format_value_report`（非 JSON）SHALL 以非金融可读方式展示：多档情景标签、现价相对落位说明、或周期位置说明；SHALL NOT 仅显示一个未解释的公允中枢。JSON 模式 SHALL 序列化新增字段。

#### Scenario: 比亚迪报告含三档情景标签

- **WHEN** 结果含 P1 情景结构
- **THEN** 文本出现悲观/基准/乐观（或等价中文）分档

#### Scenario: 诚实未毕业报告仍去行动化

- **WHEN** `methodology_applicable=False`
- **THEN** 主评估为方法暂不适用语义，并保留对照用标注（与诚实层一致）

