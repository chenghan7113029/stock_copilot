# 情绪面 V1 数据源实现说明

更新：2026-08-01

## 已选接口与归一化字段

| 分量 | AKShare 接口 | 原始字段/计算 | 落库字段 |
|---|---|---|---|
| 市场广度 | `stock_market_activity_legu()`；回退 `stock_zt_pool_em()` / `stock_zt_pool_dtgc_em()` | `涨停家数`、`跌停家数`、`上涨家数`、`下跌家数`；回退时统计涨跌停池行数 | `limit_up_count`、`limit_down_count`、`up_count`、`down_count` |
| 两融环比 | `macro_china_market_margin_sh()` + `macro_china_market_margin_sz()` | 两市最近两个交易日的 `融资余额` 合计环比 | `margin_balance_change_pct` |
| 换手率分量 | `stock_zh_a_spot_em()` | 当日全 A 股 `换手率` 中，均值所在横截面分位 | `turnover_percentile` |

本地安装的 AKShare 1.18.54 已确认上述函数名存在；`stock_market_activity_legu` 的实现返回 `item` / `value` 两列。2026-08-01 实测该 AKShare 包因上游页面结构变化抛出 `AttributeError`，因此实现以东方财富涨跌停池作为回退；实测 2026-07-31 返回涨停池 99 条、跌停池 0 条。回退时无法获得上涨/下跌总家数，字段按 `NULL` 保存而不伪造为 0。

## 调用频率与降级

- `sync market` 是唯一联网入口，设计为每个交易日一次；同日重复执行只 upsert 当日快照。
- AKShare 未公开承诺稳定的频率配额，客户端不做高频轮询；遇到限流或接口异常由 `retry_with_backoff` 最多重试 3 次。
- 市场广度是 V1 最小必要分量：其接口失败时整个同步失败，避免用全空数据覆盖有效快照。
- 两融或换手率接口失败时对应字段写 `NULL`，恐慌贪婪代理指数对剩余分量重新归一化。

## 联网验收限制

已完成市场广度回退与两融余额环比的实时调用抽样。`stock_zh_a_spot_em()` 在本次环境中对东方财富请求超时，因此换手率分量将按可选分量降级；运行 `py -m apps.cli sync market` 后，应按 OpenSpec 端到端任务核对当天数值与市场概况，并在数据源调整时更新本说明。
