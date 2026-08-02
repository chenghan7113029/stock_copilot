## Why

业余用户阅读 CLI 报告时，技术面英文缩写（RSI/KDJ/MACD）与价值面方法名（ddm/epv/value_trap）缺少「是什么、怎么用」；用户指南 §5 词典存在但与报告割裂，通勤扫报告时等于没有。同时发现 `margin_of_safety` 在聚合层以**百分数点**存储（已 ×100），但 `report dual` 摘要与 `report dashboard` 价值区用 `:.1%` 再次缩放，把约 `-0.8%` 显示成约 `-80%`；`DualTrackConfig` 的 MOS 阈值（`0.20`/`-0.10`）亦按比例语义编写，与百分数点真源不一致，会扭曲价值评级与综合信号。

explore 已定案：详解**默认开启**；所有 Applicable 估值方法出完整卡片；dual **带入** value/tech 讲解；MOS 口径一并摸清并修复。

## What Changes

- 新增共享「报告内讲解」渲染能力：技术指标短注释、估值方法完整卡片（定义 / 适用场景 / 公式 / 本次入参与来源 / 结果）、价值陷阱五维度白话拆解
- **默认**在 `report tech` / `report value` / `report dual` 文本输出中嵌入上述讲解（本期不强制做关闭开关；若后续需要可再加 `--concise`）
- `report dual` 在证据分桶之外，带入与 value/tech 同源的讲解块（共用渲染器，禁止复制粘贴两套文案）
- **修 MOS 单位一致性（含行为修正）**：统一约定 `ValueAnalysisResult.margin_of_safety` 为百分数点（例：`7.14` 表示 `7.14%`）；所有人类可读展示用 `:.1f%`（或等价「数值 + %」）；将 `DualTrackConfig` 低估/高估阈值改为百分数点（如 `20.0` / `-10.0`）并修正相关测试与文档
- 价值面/双轨输出中的 `Undervalued`/`Overvalued`/`Not Applicable` 等评估词优先中文化（讲解与方法行）
- 更新 `docs/user-guide.md`：说明报告自带讲解；澄清安全边际单位；术语可与报告内嵌互补而非唯一入口

**不包含：**
- 不改估值公式本身的计算结果（除 MOS **展示/阈值单位**对齐外）
- 不做 LLM 叙事增强（仍属 `report summary --narrate`）
- 不强制重做证据分桶「Altman 进空方」等语义争议（可在 design Open Questions 记录，本期可选修）
- 不实现 `--concise`（明确后置）

## Capabilities

### New Capabilities
- `report-inline-explainers`：共享讲解词典与渲染器（tech 指标注、value 方法卡、价值陷阱拆解）；供 formatters / dual 复用

### Modified Capabilities
- `cli-report-tech`：默认文本报告嵌入指标含义与用途注释
- `cli-report-value`：默认文本报告对 Applicable 方法输出完整讲解卡片；Not Applicable 白话原因；价值陷阱详细解释
- `cli-report-dual`：摘要安全边际展示与 value 一致；默认带入 value/tech 讲解；价值陷阱详细解释

（看板 `dashboard_builder` 的 MOS 展示一并修复，纳入 `report-inline-explainers` 需求与 tasks；主库尚无独立 `stock-dashboard` capability 时不另开 modified capability。）

## Impact

- **主要改动**：`src/apps/formatters.py`；新建 `src/service/report/explainers.py`（或同类）；`src/service/dual_track/analyzer.py`（`build_analysis_summary`）；`src/service/dual_track/config.py` + `signal_fusion` 测试；`src/service/report/dashboard_builder.py`
- **可能补强**：各估值方法 `details` 缺「来源」时增加静态字段→来源映射表（不重算）
- **测试**：formatters / dual summary / signal_fusion / dashboard 相关单测
- **文档**：`docs/user-guide.md`；可选 `docs/design/report-inline-explainers.md`；MRD/roadmap 可读性条目；归档时视目录变更更新 engineering-conventions
