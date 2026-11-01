## ADDED Requirements

### Requirement: sync 单票追加近期龙虎榜同步
`sync <code>` SHALL 在完成价值面快照、K 线、筹码分布、资金面与治理事件之后，追加同步「最近交易日」的龙虎榜数据。由于 `top_list` 是市场级日接口（`trade_date` 必选），同步 SHALL 拉取该交易日**全市场**上榜数据并落库（不按单票过滤），使该票及其他票同时受益。若该交易日已存在于覆盖水位表，SHALL 跳过网络调用。失败 SHALL 仅降级为 warning，MUST NOT 回滚已提交的价值面/K线/筹码/资金面/事件数据，MUST NOT 使整次 `sync` 以非 0 退出码结束。

#### Scenario: 首次 sync 拉取当日榜单
- **WHEN** 执行 `sync 600519`，覆盖水位不包含最近交易日
- **THEN** SHALL 调用 `top_list` 一次（及尽力而为的 `top_inst`），落库该日全部上榜股票，并在进度输出中显示「龙虎榜」状态

#### Scenario: 已覆盖的交易日跳过
- **WHEN** 执行 `sync 600519` 且最近交易日已在水位表中
- **THEN** SHALL NOT 发起 `top_list` 网络调用，进度输出说明已跳过，退出码 0

#### Scenario: 龙虎榜接口失败不阻断 sync
- **WHEN** 执行 `sync 600519`，价值面与 K 线成功而 `top_list` 抛异常
- **THEN** 既有数据 SHALL 正常提交，stdout/stderr 输出龙虎榜降级警告，退出码仍为 0

#### Scenario: 非交易日或盘中运行
- **WHEN** 最近交易日解析失败（`trade_cal` 与退化探测均无可用交易日）
- **THEN** SHALL 跳过龙虎榜同步并输出警告，不写覆盖水位，其余步骤照常
