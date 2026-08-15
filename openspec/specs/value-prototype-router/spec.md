# value-prototype-router Specification

## Purpose
TBD - created by archiving change add-value-analyzer-core. Update Purpose after archive.
## Requirements
### Requirement: 路由返回原型与 method_keys

`PrototypeRouter.route(stock: StockData, override: str | None = None) -> tuple[str, list[str]]` SHALL 返回 `(prototype, method_keys)`，其中 prototype 为 `"bank"` / `"high_dividend"` / `"value_growth"` / `"unknown"` 之一。**route() 执行后 SHALL 将 prototype 写入 stock.proto 字段。**

**新增前置规则（最高优先级）**：若 `override` 参数非 `None` 且是 `_PROTOTYPE_METHODS` 的合法键，SHALL 直接返回 `(override, list(_PROTOTYPE_METHODS[override]))`，`stock.proto = override`，且**不执行**内部 `_classify()` 判定（硬编码覆盖表、行业映射、财务启发式均被跳过）。若 `override` 非法（不在 `_PROTOTYPE_METHODS` 键集合中），SHALL 忽略该参数并回退到正常 `_classify()` 判定流程，不抛异常。

#### Scenario: 工行路由为银行原型（无覆盖）

- **WHEN** stock.code="601398"（硬编码覆盖表中的工行），`override=None`
- **THEN** prototype="bank"，method_keys 包含 "pb"、"residual_income"、"altman_z"，不包含 "dcf"，且 stock.proto="bank"

#### Scenario: 长江电力路由为高股息原型（无覆盖）

- **WHEN** stock.code="600900"（硬编码覆盖表），`override=None`
- **THEN** prototype="high_dividend"，method_keys 包含 "ddm"、"two_stage_ddm"，且 stock.proto="high_dividend"

#### Scenario: 茅台路由为价值成长原型（无覆盖）

- **WHEN** stock.code="600519"（硬编码覆盖表），`override=None`
- **THEN** prototype="value_growth"，method_keys 包含 "dcf"、"epv"、"owner_earnings"，且 stock.proto="value_growth"

#### Scenario: 数据不足降级为 unknown（无覆盖）

- **WHEN** stock.code 不在覆盖表，且 industry 不含「银行」，且 total_assets=None、dividend_yield=None、growth_rate=None，`override=None`
- **THEN** prototype="unknown"，method_keys 为通用集合（含 "graham_number"、"altman_z"、"value_trap"），且 stock.proto="unknown"

#### Scenario: 人工覆盖优先于硬编码覆盖表

- **WHEN** stock.code="601398"（硬编码覆盖表判定为 "bank"），但 `override="high_dividend"`
- **THEN** 返回 prototype="high_dividend"（覆盖生效，忽略硬编码表判定），`stock.proto="high_dividend"`，`_classify()` 内部逻辑不被执行

#### Scenario: 非法覆盖值被忽略，回退正常判定

- **WHEN** stock.code="601398"，`override="not_a_real_prototype"`（不在 `_PROTOTYPE_METHODS` 键集合中）
- **THEN** 忽略 `override`，按 `_classify()` 正常判定返回 prototype="bank"（硬编码覆盖表命中），不抛异常

### Requirement: 银行原型分类对商业银行股票生效

`PrototypeRouter._classify(stock)` SHALL 将 `StockData.industry` 命中 `_INDUSTRY_PROTOTYPE_MAP["bank"]` 子串（包括"银行"、"商业银行"等变体）的股票归类为 `bank` 原型。行业映射判断 SHALL 优先于财务特征启发式（杠杆率等）与"关键字段全 None → unknown"的降级规则。

#### Scenario: 601398（工商银行）分类为 bank

- **WHEN** `StockData(code="601398", industry="银行")` 传入 `route()`
- **THEN** 返回的 prototype = `"bank"`，`stock.proto = "bank"`

#### Scenario: 601288 仅含行业字段时分类为 bank

- **WHEN** `StockData(code="601288", industry="商业银行")` 且无 total_assets/dividend_yield/growth_rate
- **THEN** prototype = `"bank"`

#### Scenario: 行业字段为空时不误分类为 bank

- **WHEN** `StockData.industry` 为空且 code 不在银行覆盖表
- **THEN** prototype 由其他规则（杠杆/股息率等）决定，不默认为 bank

### Requirement: 财务特征启发式路由

在硬编码覆盖表与行业映射均未命中时，SHALL 按以下顺序判断：
1. `total_liabilities / total_assets > 0.85` → `"bank"`
2. `dividend_yield > 4.0` 且 `growth_rate is not None` 且 `growth_rate < 10` → `"high_dividend"`
3. 有效财务数据 → `"value_growth"`（兜底）
4. 关键字段全为 None 且行业映射未命中 → `"unknown"`

**前置条件变更**：本需求仅在 `_classify_by_industry(stock.industry)` 返回 `None`（即行业字段为空，或行业名称既不在 `_INDUSTRY_PROTOTYPE_MAP` 也不在 `_INDUSTRY_V2_UNIMPLEMENTED` 中）时才被触发；若行业映射已给出判定结果（无论是已实现原型还是显式 `unknown`），本需求描述的启发式判断 SHALL 被跳过。

#### Scenario: 高杠杆特征路由为银行（行业字段为空）

- **WHEN** stock.code 不在覆盖表，`industry=""`，total_liabilities=9e12，total_assets=10e12（杠杆率 0.9）
- **THEN** prototype="bank"

#### Scenario: 高股息低成长路由为高股息（行业字段为空）

- **WHEN** stock.code 不在覆盖表，`industry=""`，dividend_yield=5.5，growth_rate=3.0
- **THEN** prototype="high_dividend"

#### Scenario: 普通股票兜底为价值成长

- **WHEN** stock.code 不在覆盖表，`industry=""`，杠杆率正常（<0.85），dividend_yield=1.5，growth_rate=18.0
- **THEN** prototype="value_growth"

#### Scenario: 高杠杆但行业为保险时不再触发银行启发式

- **WHEN** stock.code 不在覆盖表，`industry="保险"`，total_liabilities=9e12，total_assets=10e12（杠杆率 0.9，若无行业拦截会被判定为 bank）
- **THEN** 行业映射先命中 `_INDUSTRY_V2_UNIMPLEMENTED`，返回 `"unknown"`，财务启发式 SHALL 不被执行，prototype = `"unknown"`（而不是 `"bank"`）

### Requirement: 各原型 method_keys 满足最小集合约束
每个原型 SHALL 覆盖以下最小集合：

| 原型 | 最小 method_keys |
|------|-----------------|
| bank | pb, residual_income, altman_z, value_trap |
| high_dividend | ddm, two_stage_ddm, altman_z, value_trap |
| value_growth | dcf, epv, owner_earnings, piotroski_f, beneish_m, value_trap |
| unknown | graham_number, graham_formula, epv, altman_z, value_trap |

明确排除的方法不应出现在对应原型的 method_keys 中：
- bank：不含 "dcf"、"reverse_dcf"、"peg"、"garp"、"rule_of_40"
- value_growth：不含 "ncav"

#### Scenario: 银行方法集排除 DCF
- **WHEN** prototype="bank"
- **THEN** "dcf" 不在 method_keys 中，"pb" 和 "residual_income" 在 method_keys 中

#### Scenario: 价值成长方法集排除 NCAV
- **WHEN** prototype="value_growth"
- **THEN** "ncav" 不在 method_keys 中，"dcf" 和 "piotroski_f" 在 method_keys 中

### Requirement: 行业映射优先于财务启发式（新增判定层）

`PrototypeRouter._classify_by_industry(industry: str) -> str | None` SHALL 实现以下三分支判定，作为 `_classify()` 中「硬编码覆盖表」之后、「财务特征启发式」之前的判定层：

1. `industry` 为空字符串 → 返回 `None`
2. `industry` 命中 `_INDUSTRY_PROTOTYPE_MAP`（子串匹配）→ 返回对应已实现 prototype（`"bank"` 或 `"high_dividend"`）
3. `industry` 命中 `_INDUSTRY_V2_UNIMPLEMENTED`（子串匹配，如"保险"、"国防军工"、"军工"）→ 返回 `"unknown"`
4. 均未命中 → 返回 `None`

`_classify()` SHALL 在 `_classify_by_industry()` 返回非 `None` 时直接采用该结果，不再执行后续财务启发式步骤。

#### Scenario: 高股息行业直接命中，不依赖启发式阈值

- **WHEN** `StockData(code="600900", industry="电力")`，且股息率/成长率数据缺失（`dividend_yield=None`, `growth_rate=None`）
- **THEN** `_classify_by_industry("电力")` 返回 `"high_dividend"`，最终 prototype = `"high_dividend"`（即使按原有启发式因字段缺失会走向别的分支）

#### Scenario: 已识别 V2 行业短路到 unknown，不进入启发式

- **WHEN** `StockData(code="601318", industry="保险", total_liabilities=9e12, total_assets=10e12)`
- **THEN** `_classify_by_industry("保险")` 返回 `"unknown"`，最终 prototype = `"unknown"`，且高杠杆特征启发式（第 4 步）SHALL 不被执行

#### Scenario: 行业名称未收录时返回 None，交由启发式处理

- **WHEN** `industry="某未收录的新兴行业名称"`
- **THEN** `_classify_by_industry()` 返回 `None`，`_classify()` 继续执行原有财务启发式步骤，行为与本 change 之前一致

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

#### Scenario: 行业标签存在但缺口说明字典缺失对应项时返回通用占位

- **WHEN** `_INDUSTRY_V2_UNIMPLEMENTED` 命中某标签，但 `_INDUSTRY_METHODOLOGY_GAP` 未收录该标签（字典不同步的边界场景）
- **THEN** 返回的说明含"专用估值方法论暂缺"与不应用于买卖决策语义，不抛异常

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

### Requirement: Router 支持 V2 原型键增量注册

`PrototypeRouter` SHALL 允许注册并路由下列 V2 prototype 键（随 Phase 增量启用，未启用前不得把样本静默当成已实现）：`growth_manufacturing`、`cashflow_ad_cycle`、`defense_orders`、`insurance`、`growth_tech`（名称以实现为准，但 MUST 稳定写入 `_PROTOTYPE_METHODS`）。

每个已启用键 SHALL 有非空 `method_keys` 最小集；code 白名单或行业映射 SHALL 优先于错误的 V1 启发（例如比亚迪不得在 P1 启用后仍静默 `value_growth`）。

#### Scenario: P1 启用后比亚迪不再 value_growth

- **WHEN** `growth_manufacturing` 已启用且 code=`002594`
- **THEN** route 结果 prototype 为该键（除非人工 override）

#### Scenario: 未启用的 V2 键不出现在 route 成功路径

- **WHEN** 某 V2 键尚未在本 Phase 启用
- **THEN** 对应样本保持诚实 unknown/降级路径，不返回该键

