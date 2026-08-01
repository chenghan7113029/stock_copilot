## ADDED Requirements

### Requirement: 已识别 V2 行业的方法论缺口说明

`describe_unimplemented_industry(industry: str | None) -> tuple[str, str] | None` SHALL 在 `industry` 命中 `_INDUSTRY_V2_UNIMPLEMENTED`（已识别但方法论未实现的行业清单，如"保险"、"军工"）时，返回 `(行业标签, 方法论缺口说明)` 二元组；缺口说明取自 `_INDUSTRY_METHODOLOGY_GAP` 字典，若该字典缺少对应标签的说明，SHALL 返回通用占位文案"专用估值方法论暂缺"，不抛异常。`industry` 为空字符串、`None`，或不命中 `_INDUSTRY_V2_UNIMPLEMENTED` 时，SHALL 返回 `None`。

#### Scenario: 保险行业返回精确缺口说明

- **WHEN** `describe_unimplemented_industry("保险")`
- **THEN** 返回 `("保险", "专用估值方法论（内含价值 EV/NBV 模型）暂缺")`

#### Scenario: 军工行业（子串变体）返回精确缺口说明

- **WHEN** `describe_unimplemented_industry("国防军工")`
- **THEN** 返回 `("军工", "专用估值方法论（在手订单驱动 + 资产重估模型）暂缺")`

#### Scenario: 行业信息缺失返回 None

- **WHEN** `describe_unimplemented_industry(None)` 或 `describe_unimplemented_industry("")`
- **THEN** 返回 `None`

#### Scenario: 行业未收录于 V2 清单返回 None

- **WHEN** `describe_unimplemented_industry("某未收录的行业名称")`
- **THEN** 返回 `None`

#### Scenario: 行业标签存在但缺口说明字典缺失对应项时返回通用占位

- **WHEN** `_INDUSTRY_V2_UNIMPLEMENTED` 命中某标签，但 `_INDUSTRY_METHODOLOGY_GAP` 未收录该标签（字典不同步的边界场景）
- **THEN** 返回 `(标签, "专用估值方法论暂缺")`，不抛异常
