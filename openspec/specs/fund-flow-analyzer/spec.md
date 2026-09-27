# fund-flow-analyzer Specification

## Purpose
TBD - created by archiving change add-stock-margin-fundflow. Update Purpose after archive.
## Requirements
### Requirement: FundFlowAnalyzer 输出确定性资金面分析结果
系统 SHALL 提供 `FundFlowAnalyzer`，暴露 `analyze(code) -> FundFlowResult` 与 `analyze_offline(code) -> FundFlowResult | None` 两个方法。`FundFlowResult` SHALL 包含 `code`、`margin_balance_change_pct`（两融余额近 5 日变化率，可空）、`short_balance_change_pct`（融券余额近 5 日变化率，可空）、`main_net_inflow_5d`（主力资金近 5 日净流入累计，可空）、`leverage_direction`（加杠杆/去杠杆/平稳枚举，可空）、`reasons: list[str]`、`warnings: list[str]`、`data_timestamp`。所有数值与方向判定 MUST 由代码规则计算，MUST NOT 由 LLM 生成或修改。

#### Scenario: 离线分析返回资金面结果
- **WHEN** 本地已有该股两融与资金流缓存，调用 `analyze_offline("600519")`
- **THEN** SHALL 返回 `FundFlowResult`，`margin_balance_change_pct` 等为确定性数值，`reasons` 含事实陈述文本

#### Scenario: 无本地缓存时返回 None
- **WHEN** 本地无该股两融/资金流记录
- **THEN** `analyze_offline` SHALL 返回 `None`，调用方负责记录「资金面数据缺失，请先运行 sync」警告，不抛异常

### Requirement: 两融余额与融券余额近 5 日变化计算
系统 SHALL 取该股最近两个可用交易日的 `rzrqye`/`rqye`（间隔尽量为 5 个交易日，数据不足则取可用最近两日）计算变化率；当上一交易日余额为 0 或数据不足两日时，结果 SHALL 为 `None` 并记录 warning，MUST NOT 抛出除零异常。

#### Scenario: 正常计算两融变化率
- **WHEN** 最近交易日 `rzrqye=1.1e8`，5 个交易日前的交易日 `rzrqye=1.0e8`
- **THEN** `margin_balance_change_pct` SHALL ≈ `10.0`

#### Scenario: 数据不足两日时安全降级
- **WHEN** 仅有一日两融记录
- **THEN** `margin_balance_change_pct` SHALL 为 `None`，`warnings` 说明数据不足

### Requirement: 主力资金近 5 日净流入累计与融券突增信号
系统 SHALL 累加最近 5 个交易日 `net_mf_amount` 得到 `main_net_inflow_5d`；当 `short_balance_change_pct` 超过模块内可调阈值（默认 +50%）时，SHALL 在 `reasons` 追加「融券余额显著增加」事实陈述（不直接断言「看空」，仅陈述变化幅度）。MUST NOT 让资金面结果参与 `signal_score`/`combined_signal` 数值融合。

#### Scenario: 主力资金 5 日累计
- **WHEN** 最近 5 个交易日 `net_mf_amount` 分别为 `+1000, -200, +300, +500, -100`（万元）
- **THEN** `main_net_inflow_5d` SHALL 为 `+1500`（万元）

#### Scenario: 融券突增只陈述事实
- **WHEN** `short_balance_change_pct = 80.0`
- **THEN** `reasons` SHALL 包含「融券余额较 5 个交易日前增加 80%」的事实陈述，MUST NOT 输出「强烈看空」类结论性断言

