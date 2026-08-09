## ADDED Requirements

### Requirement: 固定章节组装本地 Markdown
系统 SHALL 为指定股票代码生成一份本地 Markdown 报告，章节顺序 MUST 为：(1) 综合叙事；(2) 红蓝证据分桶；(3) 多维看板；(4) 价值面报告；(5) 技术面报告。综合叙事章节 MUST 使用 `report summary` 同源输出（可选 LLM narrate），MUST NOT 将内容标注为红蓝互驳 Level 1；该节文首 MUST 包含免责声明，标明本节为综合叙事而非红蓝互驳。

#### Scenario: 五节齐全
- **WHEN** 本地已有该代码的价值快照与 K 线，且各报告生成成功
- **THEN** 输出的 Markdown SHALL 按上述顺序包含五个一级章节

#### Scenario: 综合叙事免责声明
- **WHEN** 生成综合叙事章节
- **THEN** 该节文首 SHALL 含有表明「非红蓝互驳 Level 1」的免责文字

#### Scenario: 单节失败降级
- **WHEN** 某一章节对应报告生成失败
- **THEN** 该节 SHALL 写入可读错误说明，其余成功章节 SHALL 仍写入同一 Markdown，SHALL NOT 丢弃整份文件

### Requirement: 本地路径按运行槽隔离
系统 SHALL 将 Markdown 写入 `reports/feishu/{YYYY-MM-DD}/{slot}/{code}.md`（或等价、文档化的路径约定），其中 `slot` 标识本次推送时段（如 `0900`）。每次推送运行 MUST 使用独立目录或文件，MUST NOT 静默覆盖另一时段的本地产物。

#### Scenario: 同时段路径
- **WHEN** 在交易日 09:00 槽为 `600519` 生成报告
- **THEN** 本地文件路径 SHALL 包含当日日期与 `0900`（或配置的同等 slot 标识）以及代码 `600519`
