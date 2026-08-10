## Why

`docs/mrd/features/value-analysis.md` §14.2-C 与 roadmap T-7 指出：`PrototypeRouter`（`src/service/value/router.py`）当前仅用硬编码样本覆盖表 + 纯财务特征启发式（杠杆率、股息率、成长率）做原型判定，行业代码映射待实现。现有财务启发式存在**具体误判风险**：`_classify()` 的银行判定规则是 `total_liabilities / total_assets > 0.85` → `"bank"`，而保险公司（如中国平安）的准备金负债结构同样会导致总负债/总资产比例长期处于 85%~90%+ 区间——在无行业信息拦截的情况下，保险股会被启发式**误判为银行原型**，进而套用 PB/剩余收益法（银行专用方法），产出的估值结论完全不适用（MRD §3.1 明确"保险"与"银行"是不同原型，PB/PE 直接套用是保险原型的"不适用方法"之一）。军工等订单驱动型企业也可能因为资本结构特征意外撞入某个既有原型的启发式阈值。行业代码映射作为路由的高优先级信号，可以在启发式介入之前拦截这类误判。

## What Changes

- `PrototypeRouter._classify()` 新增「行业映射」判定层，插入在硬编码覆盖表 (`_CODE_OVERRIDE`) 之后、财务启发式之前：
  - 命中**已实现原型**的行业名称（如"银行"/"商业银行"→ `bank`；"电力"/"水务"/"燃气"/"高速公路"等公用事业类 → `high_dividend`）→ 直接返回对应 prototype，跳过财务启发式
  - 命中**已识别但方法论未实现**的行业名称（如"保险"/"国防军工"/"军工"，对齐 MRD §2.2 V2 原型清单）→ 显式返回 `"unknown"`，**同样跳过财务启发式**（防止误判为已实现原型），而不是让这些行业继续走向可能出错的杠杆率/股息率判断
  - 未命中（行业字段为空，或行业名称不在映射表中）→ 完全回退到现有财务启发式路径（**向后兼容，不是 breaking change**）
- 新增硬编码字典 `_INDUSTRY_PROTOTYPE_MAP`（行业名称 → 已实现 prototype）与 `_INDUSTRY_V2_UNIMPLEMENTED`（行业名称 → 已识别但方法论暂缺，用于短路启发式误判；同时为 `add-prototype-fallback-message` change 提供可复用的"已识别行业名称"数据源）
- `route()` 对外签名 `tuple[str, list[str]]` **不变**，不引入新的 prototype 取值，`_PROTOTYPE_METHODS` 字典键集合不变（`bank`/`high_dividend`/`value_growth`/`unknown`）
- 数据源沿用现有 `StockData.industry` 字符串字段（已由 `data_provider/provider.py` 从 Tushare `stock_basic.industry` 填充，非新增数据管道；本 change 不引入 SW/CS 官方行业代码/层级分类接口，见 design.md 决策 1 与 Open Questions）

## Capabilities

### New Capabilities
（无）

### Modified Capabilities
- `value-prototype-router`：新增「行业映射优先于财务启发式」判定层需求；修改「财务特征启发式路由」需求的触发前提（新增"行业映射未命中"前置条件）

## Impact

- **修改文件**：
  - `src/service/value/router.py`：`_classify()` 拆分出行业映射判定层；新增两个硬编码字典
- **不修改**：`data_provider/`（`StockData.industry` 字段填充逻辑不变）、`_PROTOTYPE_METHODS`（原型 → method_keys 映射不变）、`aggregator.py`/`evidence_bucketer.py`（均不感知 prototype 取值集合的扩展，本 change 未扩展该集合）
- **测试**：`test/service/value/test_router.py`（新增行业映射优先级、保险行业不再误判为 bank 等用例；本 change 只产出方案文档，不实现代码）
- **文档**：`docs/mrd/features/value-analysis.md` §14.2-C（T-7 状态）、`docs/mrd/roadmap-todo.md` §4.1（T-7 行）
- **下游关系**：本 change 的 `_INDUSTRY_V2_UNIMPLEMENTED` 字典是 `add-prototype-fallback-message`（T-15）的建议数据源（详见该 change 的 design.md 依赖说明）；本 change 与 `add-prototype-override-persistence`（T-8）在路由优先级上有交叉，交叉说明见双方 design.md「三层路由优先级」章节
