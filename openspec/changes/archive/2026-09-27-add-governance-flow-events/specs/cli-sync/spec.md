## ADDED Requirements

### Requirement: sync 单票追加治理事件同步
`sync <code>` SHALL 在完成价值面快照与 K 线（及筹码/资金面）拉取之后，追加拉取该股治理事件（`stk_holdertrade`/`repurchase`/`share_float`/`pledge_stat`/`block_trade`）并落库。任一治理接口失败 SHALL 降级（保留缓存或记缺失），MUST NOT 回滚已提交的价值面/K 线，MUST NOT 因治理接口不可用导致整次 `sync` 失败退出。

#### Scenario: 正常 sync 追加治理事件
- **WHEN** 执行 `sync 600519` 且治理接口可用
- **THEN** 价值快照、K 线、治理事件均落库，stdout 输出含「治理事件 OK」类状态

#### Scenario: 治理接口失败不阻断 sync
- **WHEN** 执行 `sync 600519` 且 `pledge_stat` 接口异常，但价值面与 K 线成功
- **THEN** 价值快照与 K 线正常落库并 commit，stdout 输出治理事件降级警告，退出码仍为 0
