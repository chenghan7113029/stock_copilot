# cli-report-dual Specification

## Purpose
CLI `report dual`：严格离线输出红蓝对抗证据分桶（Level 0），供 Cursor Skill 消费。

## Requirements

### Requirement: CLI `report dual` 命令——严格离线输出证据分桶
系统 SHALL 提供 `python -m apps.cli report dual <code> [--json] [--output]`。命令 SHALL 严格离线（不发起任何网络请求），内部调用 `DualTrackAnalyzer.analyze_offline()` 与 `EvidenceBucketer`，输出证据分桶结果（含兜底内容）。命令 SHALL NOT 提供任何联网/LLM 相关 flag；互驳叙事的生成由 Cursor Skill（见 `cursor-skill-red-blue-confrontation` capability）在命令输出之外完成。命令内部 SHALL 复用 `run_report_tech`/`run_report_value` 已有的 analyzer 装配逻辑，不重新实现。

#### Scenario: 默认输出证据分桶
- **WHEN** 运行 `report dual 600519`（本地已有快照）
- **THEN** SHALL 输出 bull/bear 证据列表（含兜底条目，若触发），不发起任何网络请求

#### Scenario: 无本地快照时明确报错
- **WHEN** 运行 `report dual <code>` 但本地无该代码的价值快照与 K 线缓存
- **THEN** SHALL 输出 `[error] 未找到 <code> 的本地数据，请先运行 sync`，退出码非 0

#### Scenario: --json 与 --output 行为对齐既有 report 命令
- **WHEN** 运行 `report dual 600519 --json` 或 `--output <path>`
- **THEN** 行为 SHALL 与 `report tech`/`report value` 的对应 flag 语义一致（JSON 序列化 / 写入文件而非打印到 stdout）；`--json` 输出 SHALL 包含 `bull_evidence`/`bear_evidence` 字段，供 Cursor Skill 解析消费

### Requirement: dual 摘要安全边际与 value 一致
`report dual` 摘要中的安全边际展示 MUST 与同一分析结果下 `report value` 使用相同的百分数点语义与量级。

#### Scenario: 不再二次缩放
- **WHEN** `margin_of_safety` 约为 `-0.8` 且本地数据可生成 dual 与 value 报告
- **THEN** dual 摘要中的安全边际 SHALL 显示约 `-0.8%`，SHALL NOT 显示约 `-80%`

### Requirement: dual 默认带入 value/tech 讲解
`report dual` 的默认人类可读文本输出在证据分桶之后，SHALL 附加与 `report value` / `report tech` 同源的讲解内容（估值方法卡片与/或价值陷阱拆解、技术指标注释）。讲解 MUST 默认开启。证据列表（bull/bear）的 Level 0 结构 MUST 保留，供 Skill 继续消费。

#### Scenario: 文本 dual 含讲解分区
- **WHEN** 用户执行 `report dual <code>`（非 `--json`）且价值与技术结果均可用
- **THEN** 输出在多方/空方证据之后 SHALL 包含可识别的价值面讲解与技术面讲解内容（例如独立小节标题）

#### Scenario: JSON 向后兼容
- **WHEN** 用户执行 `report dual <code> --json`
- **THEN** 输出 SHALL 仍包含 `bull_evidence` 与 `bear_evidence` 字段；若增加讲解字段，MUST 为附加键且不得删除或重命名既有证据字段
