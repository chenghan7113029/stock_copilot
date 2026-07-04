## ADDED Requirements

### Requirement: growth_rate 使用 2 年净利 CAGR
`BaostockFetcher` SHALL 将 `growth_rate` 计算改为「最近两个完整年度（Q4）净利润的 CAGR」，不再直接使用单季 `YOYNI`。

公式：`growth_rate = (TTM_now / TTM_2y_ago)^(1/2) - 1`，结果以百分比表示（乘以 100）。

#### Scenario: 两个 Q4 年度数据均可获取
- **WHEN** 当前年度 `epsTTM` 和 2 年前年度 `epsTTM` 均有效（> 0）
- **THEN** `growth_rate = ((eps_ttm_now / eps_ttm_2y_ago)^0.5 - 1) × 100`，写入 `FetchResult.data["growth_rate"]`

#### Scenario: 2 年前数据不可获取
- **WHEN** 查询 `(year-2, quarter)` 的 profit_data 失败或 epsTTM 为 None
- **THEN** 退化使用 `YOYNI`（原单季同比），写入警告日志

#### Scenario: CAGR 超出合理范围
- **WHEN** 计算得 CAGR < -50% 或 > 100%
- **THEN** 将 `growth_rate` clamp 到 [-50, 100] 范围，并写入 warning：`"growth_rate clamped from {raw}% to {clamped}%, may reflect exceptional period"`

#### Scenario: 历史净利润为负（亏损期）
- **WHEN** `epsTTM` 在任一年份 ≤ 0
- **THEN** CAGR 不可计算，退化使用 `YOYNI`，写入 warning
