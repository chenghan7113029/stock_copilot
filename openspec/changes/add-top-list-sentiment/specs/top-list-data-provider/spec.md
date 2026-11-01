## ADDED Requirements

### Requirement: TopListProvider 按交易日采集全市场龙虎榜并持久化
系统 SHALL 提供 `TopListProvider`（`src/data_provider/toplist/provider.py`），具备 `from_config(config, repos)` 工厂方法：仅当配置启用 `tushare` 且存在 token 时实例化 `TushareTopListFetcher`，否则以空 fetcher 列表构造并返回「无可用数据源」警告。`sync_trade_date(trade_date)` SHALL 调用 `top_list(trade_date=...)` 拉取**该交易日全市场**上榜明细并落库（不按单票过滤），随后尝试 `top_inst(trade_date=...)` 落库机构席位明细。两张表 SHALL 按交易日**整日替换**写入（重复同步幂等）；`top_inst` MUST 使用代理主键保存原始席位行（席位名不可作唯一键）。整次调用 MUST NOT 因单接口失败抛出未捕获异常。

#### Scenario: 正常拉取一个交易日
- **WHEN** 调用 `sync_trade_date("2026-10-30")` 且 `top_list` 返回非空 DataFrame
- **THEN** `stock_top_list` SHALL 写入该日所有上榜股票记录，`net_amount`/`l_buy`/`l_sell`/`reason` 等字段与源一致，并返回空 warnings

#### Scenario: 重复同步幂等
- **WHEN** 对同一 `trade_date` 连续调用两次 `sync_trade_date`
- **THEN** `stock_top_list` 与 `stock_top_inst` 的行数 SHALL 与单次调用一致（整日替换，不累加）

#### Scenario: 该交易日无榜单数据
- **WHEN** `top_list` 返回空 DataFrame（休市日或数据未发布）
- **THEN** SHALL NOT 写入任何 `stock_top_list` 记录、SHALL NOT 写入覆盖水位标记，并返回含「无榜单数据」的 warning

#### Scenario: 未配置可用数据源
- **WHEN** 配置未启用 `tushare` 或 token 为空
- **THEN** `sync_trade_date` SHALL 返回「龙虎榜无可用数据源」warning 且不抛异常，本地缓存读取路径仍可用

### Requirement: 交易日覆盖水位区分「未上榜」与「未拉取」
系统 SHALL 维护 `top_list_sync_marker` 表（主键 `trade_date`），仅在 `top_list` 成功返回非空数据后写入该交易日标记。系统 SHALL 提供查询接口返回已覆盖交易日集合（或最近覆盖区间），供分析层判断统计窗口是否被完整覆盖。MUST NOT 以榜单数据的 `MAX(trade_date)` 代替水位判定。

#### Scenario: 成功后写入水位
- **WHEN** `sync_trade_date("2026-10-30")` 成功
- **THEN** `top_list_sync_marker` SHALL 存在 `trade_date="2026-10-30"` 的记录，重复调用不产生重复行

#### Scenario: 覆盖不足可被查询
- **WHEN** 本地仅覆盖 3 个交易日
- **THEN** 查询接口 SHALL 返回这 3 个交易日（升序），分析层据此在 `warnings` 说明覆盖不足

### Requirement: 机构席位接口不可用时降级而非中断
`top_inst` 官方标注更高积分门槛，本项目仅在 2000 积分档实测可用，故系统 MUST 假定其可能失败。当 `top_inst` 调用失败（权限/网络/无数据）时，SHALL 保留 `top_list` 已落库数据，返回含接口名与原因的 warning，MUST NOT 回滚 `top_list` 写入、MUST NOT 使整次同步失败。

#### Scenario: top_inst 权限不足
- **WHEN** `top_list` 成功但 `top_inst` 抛权限错误
- **THEN** `stock_top_list` 数据 SHALL 保留，warnings SHALL 含「机构席位接口不可用」类说明，`stock_top_inst` 保持原状

### Requirement: 严格离线读取
系统 SHALL 提供 `get_offline(code, window_days)`，只读本地库返回该股在窗口内的上榜记录与机构席位记录，并发起零网络请求。窗口内既无榜单记录**也无覆盖水位**时 SHALL 返回 `None`（由调用方决定措辞）；若水位存在但该股未上榜，SHALL 返回空记录 + 覆盖日期的数据对象（供分析层输出「未上榜」而非「无缓存」）。MUST NOT 用空列表伪装成「已确认未上榜」。

#### Scenario: 离线读到已缓存记录
- **WHEN** 本地存在该股 2 条上榜记录，调用 `get_offline("600519", 90)`
- **THEN** SHALL 返回这些记录（按 `trade_date` 升序）与覆盖水位信息，且不发起网络请求

#### Scenario: 无记录返回 None
- **WHEN** 本地无该股任何上榜记录
- **THEN** SHALL 返回 `None`，调用方据此输出「无龙虎榜缓存，请先运行 sync」
