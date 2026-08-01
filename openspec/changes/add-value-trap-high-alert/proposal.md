## Why

`docs/mrd/features/value-analysis.md` §8.1 与 §14.1 指出：`ValueTrapDetector`（`value_trap`）五维度检测已实现，评分摘要已通过 `ValuationAggregator._score_summary()` 进入 `ValueAnalysisResult.warnings`，但 `overall_risk = "High"` 时的**专项**提示逻辑（roadmap T-2）尚未实现——目前 High 风险的价值陷阱信号与其他 warnings（如 IQR 异常值剔除说明、数据缺失提示）混在同一个列表里，权重与视觉区分度相同，用户在 CLI 报告中容易忽略"这只股票可能是价值陷阱"这一关键信号，尤其是在 DCF/EPV 显示"低估"、诱导用户忽视五维度风险检测结果的场景下最危险。本 change 补齐这一专项提示增量。

## What Changes

- `ValuationAggregator.aggregate()` 新增 value_trap High 专项检测：当 `method_results["value_trap"].details.overall_risk == "High"` 时，产出独立的醒目提示文案，写入 `AggregateResult` 新字段 `value_trap_alert: str | None`（不放入 `warnings` 列表，避免被其他条目稀释）
- 同一场景下对 `confidence` 做**一级降级**（`High→Medium`、`Medium→Low`、`Low`/`不可信` 保持不变），叠加在现有置信度计算逻辑之上，不替换既有规则
- `ValueAnalysisResult` 新增字段 `value_trap_alert: str | None = None`（向后兼容默认值），由 `ValueAnalyzer._analyze_stock()` 透传
- CLI `report value` 文本渲染器（`format_value_report()`）在报告头部（名称/原型之后，评估/置信度之前）插入醒目警示区块，仅当 `value_trap_alert` 非空时渲染；`--json` 输出自动包含该字段（dataclass 序列化，无需额外代码）
- **明确不变更**：`ValueAnalysisResult.assessment`（低估/合理偏低/合理/合理偏高/高估）的既有 MOS 语义与取值集合保持不变，不引入复合状态；`EvidenceBucketer`（红蓝对抗证据分桶）当前已通过结构化字段 `value_trap.details.overall_risk` 分桶（非 `assessment` 文本），故不受本 change 影响，设计细节与验证方式见 design.md 决策 1

## Capabilities

### New Capabilities
（无——本 change 是对既有能力的增量增强，不引入新的独立能力域）

### Modified Capabilities
- `value-aggregator`：新增「value_trap High 专项警示 + confidence 一级降级」需求
- `value-analyzer`：`ValueAnalysisResult` 新增 `value_trap_alert` 字段
- `cli-report-value`：`report value` 文本报告新增醒目警示区块渲染规则

## Impact

- **修改文件**：
  - `src/service/value/aggregator.py`：`AggregateResult` 新增字段；`aggregate()` 新增 High 专项检测与 confidence 降级逻辑
  - `src/service/value/models/analysis_result.py`：`ValueAnalysisResult` 新增 `value_trap_alert` 字段
  - `src/service/value/analyzer.py`：`_analyze_stock()` 透传新字段
  - `src/apps/formatters.py`：`format_value_report()` 新增警示区块渲染
- **不修改**：`src/service/value/valuation/value_trap.py`（`ValueTrapDetector` 五维度计算逻辑不变）、`src/service/dual_track/evidence_bucketer.py`（已通过结构化字段消费，无需联动修改，design.md 会记录验证结论）
- **测试**：`test/service/value/test_aggregator.py`、`test/service/value/test_analyzer.py`、`test/apps/test_cli_report_value.py`（新增/扩展用例，具体见 tasks.md；本 change 只产出方案文档，不实现代码）
- **文档**：`docs/mrd/features/value-analysis.md` §8.1/§14.1（T-2 状态）、`docs/mrd/roadmap-todo.md` §4.1（T-2 行）
