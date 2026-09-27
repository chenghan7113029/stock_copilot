## ADDED Requirements

### Requirement: sync 单票追加个股两融与主力资金流同步
`sync <code>` SHALL 在完成价值面快照与 K 线拉取（及筹码分布拉取）之后，追加拉取个股两融（`margin_detail`）与主力资金流（`moneyflow`）并落库。资金面拉取失败 SHALL 降级（保留本地缓存或记缺失），MUST NOT 回滚已提交的价值面/K 线，MUST NOT 因资金面接口不可用导致整次 `sync` 失败退出。

#### Scenario: 正常 sync 追加资金面
- **WHEN** 执行 `sync 600519` 且 Tushare `margin_detail`/`moneyflow` 可用
- **THEN** 价值快照、K 线、筹码、两融、资金流均落库，stdout 输出含「资金面 OK」类状态

#### Scenario: 资金面接口失败不阻断 sync
- **WHEN** 执行 `sync 600519` 且 `moneyflow` 接口异常，但价值面与 K 线成功
- **THEN** 价值快照与 K 线正常落库并 commit，stdout 输出资金面降级警告，退出码仍为 0
