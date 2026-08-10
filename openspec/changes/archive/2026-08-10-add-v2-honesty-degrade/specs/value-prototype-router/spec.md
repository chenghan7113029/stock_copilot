## ADDED Requirements

### Requirement: code 级 V2 诚实名单短路为 unknown

`PrototypeRouter._classify` SHALL 在硬编码 `_CODE_OVERRIDE`（银行/高股息/价值成长）之前，检查 `_CODE_V2_HONESTY`（或等价命名）code 白名单。命中时 SHALL 返回 `"unknown"`，且不执行行业映射与财务启发式。本期白名单至少包含：`002594`（成长+制造周期）、`002027`（现金流+广告周期）。

人工 `override` 参数仍为最高优先级（既有规则）：合法 override 时本名单不生效。

#### Scenario: 比亚迪 code 短路为 unknown

- **WHEN** `StockData(code="002594", industry="汽车整车", growth_rate=20, ...)` 且 `override=None`
- **THEN** prototype=`"unknown"`，`stock.proto="unknown"`，method_keys 为 unknown 通用集（不含以 dcf 为主的 value_growth 集）

#### Scenario: 分众 code 短路为 unknown

- **WHEN** `StockData(code="002027", ...)` 且 `override=None`
- **THEN** prototype=`"unknown"`

#### Scenario: 合法 override 仍可覆盖诚实名单

- **WHEN** `code="002594"` 且 `override="value_growth"`
- **THEN** prototype=`"value_growth"`（诚实名单被跳过）

### Requirement: 统一诚实缺口描述（code 优先于行业）

系统 SHALL 提供 `describe_honesty_gap(code: str, industry: str | None)`（或等价 API），返回结构化缺口信息或 `None`：

1. `code` 命中 `_CODE_V2_HONESTY` → 返回该 code 的标签与方法论/偏差说明
2. 否则 `industry` 命中 `_INDUSTRY_V2_UNIMPLEMENTED` → 返回保险/军工既有缺口说明，并须包含「通用方法得出的低估/高估不应用于买卖决策」语义
3. 否则 → `None`

`describe_unimplemented_industry(industry)` SHALL 保持可用：行为与转调「仅 industry 分支」一致，或作为兼容封装，不得在无行业命中时因 code 空参抛异常。

比亚迪缺口说明 SHALL 表达：成长+制造周期、单点 DCF/EPV 易把产销波动当稳定成长、专用情景估值暂缺、不能作为买卖依据。  
分众缺口说明 SHALL 表达：现金流+广告周期、景气期静态外推易偏高、缺周期位置、不能作为买卖依据。

#### Scenario: 比亚迪返回制造周期诚实缺口

- **WHEN** `describe_honesty_gap("002594", industry="汽车整车")`
- **THEN** 返回非空，标签含「成长+制造周期」或等价，文案含不能作为买卖依据的语义

#### Scenario: 保险行业返回升级后的决策禁止语义

- **WHEN** `describe_honesty_gap("601318", "保险")` 或仅行业命中
- **THEN** 返回非空，含 EV/NBV 暂缺，且含「不应用于买卖决策」语义

#### Scenario: 普通股票返回 None

- **WHEN** `describe_honesty_gap("600519", "白酒")`
- **THEN** 返回 `None`

## MODIFIED Requirements

### Requirement: 已识别 V2 行业的方法论缺口说明

`describe_unimplemented_industry(industry: str | None) -> tuple[str, str] | None` SHALL 在 `industry` 命中 `_INDUSTRY_V2_UNIMPLEMENTED`（已识别但方法论未实现的行业清单，如"保险"、"军工"）时，返回 `(行业标签, 方法论缺口说明)` 二元组；缺口说明取自 `_INDUSTRY_METHODOLOGY_GAP`（或由 `describe_honesty_gap` 组装），**须同时包含**专用方法暂缺说明与「通用方法得出的低估/高估不应用于买卖决策」语义。若字典缺少对应标签的说明，SHALL 返回通用占位文案"专用估值方法论暂缺"并仍附带决策禁止语义，不抛异常。`industry` 为空字符串、`None`，或不命中 `_INDUSTRY_V2_UNIMPLEMENTED` 时，SHALL 返回 `None`。

#### Scenario: 保险行业返回精确缺口说明与决策禁止

- **WHEN** `describe_unimplemented_industry("保险")`
- **THEN** 返回的说明同时提及"保险"相关 EV/NBV 暂缺语义，以及不应用于买卖决策的语义

#### Scenario: 军工行业（子串变体）返回精确缺口说明

- **WHEN** `describe_unimplemented_industry("国防军工")`
- **THEN** 返回标签为"军工"或等价，说明含订单驱动/资产重估暂缺语义，以及不应用于买卖决策的语义

#### Scenario: 行业信息缺失返回 None

- **WHEN** `describe_unimplemented_industry(None)` 或 `describe_unimplemented_industry("")`
- **THEN** 返回 `None`

#### Scenario: 行业未收录于 V2 清单返回 None

- **WHEN** `describe_unimplemented_industry("某未收录的行业名称")`
- **THEN** 返回 `None`
