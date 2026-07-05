## Context

Baostock `historical_pe` 实现（`fix-baostock-data-quality`）已验证可行，但窗口仅 2 年；`historical_pb` 则完全未实现。Tushare `daily_basic` 提供完整的 `pe_ttm`/`pb` 日频历史，按季末采样即可获得稳定的 5 年序列。

当前 DCF vs EPV 分歧（1950 vs 989）在报告中缺乏说明，用户容易误判。

## Goals / Non-Goals

**Goals:**
- Tushare fetcher 中新增 historical_pe/pb（5年，季末采样）
- Baostock 保留为 fallback（Tushare 不可用时）
- formatters.py 中 DCF/EPV 补充语义行

**Non-Goals:**
- 不改 Baostock historical_pe 的现有逻辑
- 不引入日级别 PE/PB 序列存储（只存最新采样序列到快照）
- 不改动估值方法本身计算逻辑

## Decisions

### 决策 1：Tushare daily_basic 按季末采样

从 `daily_basic` 拉 5 年 `pe_ttm`/`pb` 日频序列，按以下规则取季末值：
- Q1: 3 月最后一个交易日
- Q2: 6 月最后一个交易日
- Q3: 9 月最后一个交易日
- Q4: 12 月最后一个交易日

最多取最近 20 个季末点（5 年），过滤异常值（PE ≤ 0 或 > 200；PB ≤ 0 或 > 50）。

**备选（Baostock 推导 PB = 价格/bvps）**：Baostock 无历史 bvps 序列，无法推导，放弃。

### 决策 2：Baostock 作为 historical_pe fallback

`StockDataProvider._merge_fields()` 已有「Tushare 优先」逻辑，不需额外改动。Tushare 写入后，Baostock 的 historical_pe 通过 `set_field` 不覆盖（historical_pe 用 set_field 非 override）。

### 决策 3：DCF/EPV 语义注释位置

在 `formatters.py` 的 `format_value_report` 中，方法行渲染时若 key 为 `dcf` 或 `epv`，在描述后追加括号内的语义提示：
- dcf：`(含增长假设：g₁=X% 5年)`
- epv：`(零增长地板价)`

这是纯格式层变化，不影响任何计算结果。

## Risks / Trade-offs

- **[风险] Tushare daily_basic 需要一定积分**：2000 积分已满足，与财报接口同级。
- **[权衡] 历史数据不持久化**：每次 sync 重新采样。V1 够用；V2 可考虑单独存储 PE/PB 序列表。
- **[风险] 季末日期非交易日**：按月倒推最近交易日，Tushare 日频数据会有实际收盘日期可回溯。

## Migration Plan

1. sync 后即可享受新的 historical_pb 和 5 年 historical_pe，无需重建数据库
2. 现有快照仍然有效（historical_pb=None → 下次 sync 自动填充）
