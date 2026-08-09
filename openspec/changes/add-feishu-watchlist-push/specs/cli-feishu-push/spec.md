## ADDED Requirements

### Requirement: CLI `feishu push` 入口
系统 SHALL 提供 `python -m apps.cli feishu push`，支持单票代码或 `--watchlist`，并支持 `--dry-run`、可选 `--narrate`、可选 `--sync`/`--no-sync`（或等价配置覆盖）。该命令 SHALL 编排：可选 sync → composer 写本地 Markdown →（非 dry-run）publisher 新建文档并发送一票一消息。

#### Scenario: watchlist 推送
- **WHEN** 运行 `feishu push --watchlist` 且飞书已配置、为交易日（或 `trading_days_only` 关闭）
- **THEN** 系统 SHALL 对常看列表中每只股票尝试生成文档并推送消息

#### Scenario: dry-run 仅本地
- **WHEN** 运行 `feishu push --watchlist --dry-run`
- **THEN** 系统 SHALL 为列表中的股票生成本地 Markdown，SHALL NOT 调用飞书写接口

#### Scenario: 未配置飞书
- **WHEN** 运行 `feishu push 600519`（非 dry-run）但缺少飞书凭证
- **THEN** 系统 SHALL 以非 0 退出码失败并提示配置 `feishu:` / 环境变量

### Requirement: 交易日门闩
当配置 `trading_days_only` 为 true（默认建议 true）时，若当日判定为非 A 股交易日，命令 SHALL 跳过推送并以退出码 0 结束，并打印可识别的 skip 原因。

#### Scenario: 非交易日跳过
- **WHEN** `trading_days_only` 为 true 且当日为周末或配置的休市日
- **THEN** 命令 SHALL 不创建飞书文档、不发送成功推送消息，退出码 SHALL 为 0

### Requirement: 计划任务可调用
系统 SHALL 在用户文档中说明如何用 Windows 任务计划程序在交易日 09:00、13:00、17:00 调用 `feishu push`（含 PYTHONPATH/`py -m` 示例）。命令本身 MUST NOT 要求常驻 daemon 进程。

#### Scenario: 文档含三段时刻
- **WHEN** 用户阅读本 change 交付的用户指南相关章节
- **THEN** 文档 SHALL 写明 09:00 / 13:00 / 17:00 三个调度示例与 watchlist 推送命令
