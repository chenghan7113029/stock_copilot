## ADDED Requirements

### Requirement: 本地产物为 report dual 同源 Markdown
系统 SHALL 为指定股票代码生成（或定位）一份本地 Markdown，其内容 MUST 与 `report dual` 同源。系统 MUST NOT 再拼装综合叙事、多维看板、价值面或技术面章节作为飞书推送正文。

#### Scenario: 仅 dual
- **WHEN** 本地已有该代码的价值快照与 K 线，且 dual 报告生成成功
- **THEN** 输出文件 SHALL 为 `{code}_dual.md`（或文档化的等价命名），内容 SHALL 为红蓝证据分桶报告，SHALL NOT 要求包含 summary/dashboard/value/tech 四个额外一级章节

#### Scenario: 单票失败不丢批次
- **WHEN** 某一股票的 dual 报告生成失败
- **THEN** 系统 SHALL 记录该票失败并继续处理同批次其余股票，SHALL NOT 因单票失败删除其他已成功写入的 dual.md

### Requirement: 本地路径按日期与时段隔离
系统 SHALL 将 dual.md 写入 `reports/feishu/{YYYY-MM-DD}/{slot}/{code}_dual.md`（或等价、文档化的路径）。不同日期或不同 slot MUST NOT 静默覆盖彼此的本地产物。

#### Scenario: 日期与 slot 路径
- **WHEN** 在 `2026-08-18` 的 `1700` 槽为 `600519` 生成 dual 供飞书推送
- **THEN** 本地文件路径 SHALL 包含 `2026-08-18`、`1700` 与 `600519`，且文件名 SHALL 标识 dual（如 `600519_dual.md`）
