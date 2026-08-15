## ADDED Requirements

### Requirement: CLI `feishu push` 入口
系统 SHALL 提供 `python -m apps.cli feishu push`，支持单票代码或 `--watchlist`，并支持 `--dry-run`、可选 `--sync`/`--no-sync`。该命令 SHALL 编排：可选 sync → 生成与 `report dual` 同源的本地 `{code}_dual.md` →（非 dry-run）经 `lark-cli` 新建飞书文档并立即发送一条消息。

#### Scenario: watchlist 推送
- **WHEN** 运行 `feishu push --watchlist` 且 `lark-cli` 可用且已登录、为交易日（或 `trading_days_only` 关闭）
- **THEN** 系统 SHALL 对常看列表中每只股票尝试生成 dual.md、新建文档，并在该票成功后立即推送一条消息

#### Scenario: dry-run 仅本地
- **WHEN** 运行 `feishu push --watchlist --dry-run`
- **THEN** 系统 SHALL 为列表中的股票生成本地 `{code}_dual.md`，SHALL NOT 调用 `lark-cli` 的创建文档或发送消息命令

#### Scenario: lark-cli 不可用
- **WHEN** 运行 `feishu push 600519`（非 dry-run）但未安装 `lark-cli` 或未登录
- **THEN** 系统 SHALL 以非 0 退出码失败并提示安装 / `lark-cli auth login`，SHALL NOT 假装发送成功

### Requirement: 交易日门闩
当配置 `trading_days_only` 为 true（默认建议 true）时，若当日判定为非 A 股交易日，命令 SHALL 跳过推送并以退出码 0 结束，并打印可识别的 skip 原因。

#### Scenario: 非交易日跳过
- **WHEN** `trading_days_only` 为 true 且当日为周末或配置的休市日
- **THEN** 命令 SHALL 不创建飞书文档、不发送成功推送消息，退出码 SHALL 为 0

### Requirement: 计划任务可调用
系统 SHALL 在用户文档中说明如何用 Windows 任务计划程序在 **09:00 / 13:00 / 17:00** 调用 `feishu push`（含 `py -m`、`--slot` 与 `lark-cli` 需已登录的说明）。命令本身 MUST NOT 要求常驻 daemon 进程。文档 MUST 说明 PC 休眠/未登录可能导致漏推，且本 change 不解决常开问题。

#### Scenario: 文档含三段时刻
- **WHEN** 用户阅读本 change 交付的用户指南相关章节
- **THEN** 文档 SHALL 写明 09:00 / 13:00 / 17:00 三个调度示例与 watchlist 推送命令
