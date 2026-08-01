## ADDED Requirements

### Requirement: 单票多维看板聚合
系统 SHALL 提供 `DashboardBuilder.build(code: str) -> DashboardView`，内部调用 `DualTrackAnalyzer.analyze_offline()` 与 `EvidenceBucketer` 聚合价值面、技术面、红蓝证据摘要、综合信号为单一 `DashboardView`，且 SHALL NOT 重新计算任何数值（所有数值字段均直接取自既有确定性输出）。

#### Scenario: 价值面与技术面均有本地数据
- **WHEN** 调用 `build(code)` 且本地已有该代码的价值快照与 K 线缓存
- **THEN** 返回的 `DashboardView` SHALL 含非空的 `value_section`、`tech_section`、`combined_summary`

#### Scenario: 综合摘要含红蓝证据条数
- **WHEN** `DashboardView` 构建完成
- **THEN** `combined_summary` SHALL 包含 `bull_evidence`/`bear_evidence` 的条数摘要（非完整证据列表）

### Requirement: 维度缺失优雅降级
系统 SHALL 在情绪面、Checklist 尚未实现时输出固定「待建」占位，SHALL NOT 因单一维度缺失导致整体构建失败；仅当价值面与技术面**同时**无法产出结果时才判定整体失败。

#### Scenario: 情绪面与 Checklist 未实现
- **WHEN** 调用 `build(code)`（当前版本情绪面/Checklist 均未接入）
- **THEN** `sentiment_section` SHALL 为固定占位文案（含「待建」字样与对应 roadmap ID）
- **THEN** `checklist_section` SHALL 为固定占位文案（含「待建」字样与对应 roadmap ID）

#### Scenario: 仅价值面本地无快照
- **WHEN** 调用 `build(code)` 但本地无该代码的价值快照，技术面 K 线缓存存在
- **THEN** `value_section` SHALL 提示「无本地快照，请先运行 sync」，`tech_section` SHALL 正常输出，整体不抛异常

#### Scenario: 价值面与技术面均无本地数据
- **WHEN** 调用 `build(code)` 且本地无该代码的价值快照与 K 线缓存
- **THEN** SHALL 抛出与 `report dual` 一致的「未找到本地数据，请先运行 sync」错误
