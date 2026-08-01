## Context

`src/service/value/router.py` 现有 `PrototypeRouter._classify()` 判定顺序：

1. `stock.code in _CODE_OVERRIDE`（硬编码样本表：工行/交行/建行/招行/长江电力/茅台）→ 直接返回
2. `stock.industry` 含"银行" → `"bank"`（**当前唯一的行业信号使用点**）
3. 关键字段（`total_assets`/`dividend_yield`/`growth_rate`）全为 `None` → `"unknown"`
4. `total_liabilities / total_assets > 0.85` → `"bank"`
5. `dividend_yield > 4.0` 且 `growth_rate < 10` → `"high_dividend"`
6. 兜底 → `"value_growth"`

第 4 步的杠杆率阈值判断存在已知误判风险：保险公司的准备金负债（未到期责任准备金、赔款准备金等）在会计科目上计入总负债，导致保险股的 `total_liabilities / total_assets` 同样长期处于 0.85+ 区间（与银行的高杠杆经营模式表现相似但业务模式完全不同）。当前代码在第 4 步之前，只有第 2 步窄范围的"银行"字符串检查会拦截，保险等其他行业没有任何行业层面的拦截机制，会直接落入第 4 步的杠杆率判断，可能被误判为 `bank` 原型。

数据源核查（Grep 结论）：
- `StockData.industry: str = ""`（`src/common/models/stock_data.py`）字段已存在
- `src/data_provider/provider.py::_STOCK_DATA_FIELDS` 包含 `"industry"`，`stock.industry == "" and data.get("industry")` 时写入（首次来源优先）
- `src/data_provider/tushare/field_mapping.py::STOCK_BASIC_FIELD_MAP = {"name": "name", "industry": "industry"}`，`src/data_provider/tushare/fetcher.py::_fetch_stock_basic()` 调用 Tushare `stock_basic(fields="ts_code,name,industry")`
- 该 `industry` 字段是 Tushare `stock_basic` 接口自带的**简化行业分类**（如"银行"、"保险"、"电力"等一级分类字符串），**不是**申万（SW）/中证（CS）官方多级行业代码体系；`src/data_provider/` 下没有任何模块调用 Tushare 的 `index_classify`/`index_member`（申万行业分类专用接口）或其他 SW/CS 代码接口
- AKShare/Baostock fetcher 均未见 industry 相关字段映射（Grep 未命中）

结论：MRD/roadmap 措辞中的"SW/CS 行业代码映射"在当前数据管道下**没有对应的官方分级代码可用**；现实可行的 V1 方案是复用已接入的 Tushare 简化行业名称字符串，做"行业名称 → 原型"的字典映射，而不是引入新的行业分级代码数据源（会显著扩大本 change 范围，涉及新 fetcher + 新字段 + 新持久化列）。

## Goals / Non-Goals

**Goals:**
- 用已有 `StockData.industry` 字符串字段实现"行业名称 → 原型"的优先判定层，修复保险等行业被杠杆率启发式误判为 `bank` 的具体缺陷
- 行业映射优先于财务启发式，命中已识别的 V2 行业（方法论未实现）时显式短路到 `"unknown"`，不让其继续走可能出错的启发式判断
- 行业字段缺失或行业名称不在映射表中时，完全回退到现有财务启发式（向后兼容）
- 为 `add-prototype-fallback-message`（T-15）预留可复用的"已识别 V2 行业名称"字典，不要求该 change 必须先实施

**Non-Goals:**
- 不引入申万（SW）/中证（CS）官方多级行业代码数据源（不新增 fetcher，不改 `StockSnapshot` 表结构）——这是一个量级更大的独立数据接入工作，超出"专项路由增强"范围，留作 Open Question
- 不新增新的 prototype 取值（如 `"insurance"`/`"military"`），不改变 `_PROTOTYPE_METHODS` 字典的键集合，不影响 `aggregator.py`/`evidence_bucketer.py` 对 prototype 字符串的既有消费逻辑
- 不实现人工覆盖持久化（属于 `add-prototype-override-persistence`，T-8，独立 change）
- 不实现精确的"保险方法论暂缺"降级文案（属于 `add-prototype-fallback-message`，T-15，本 change 只提供数据基础）

## Decisions

### 决策 1：复用现有 `industry` 字符串字段，不引入 SW/CS 官方行业代码

**选择**：V1 直接对已有的 `StockData.industry`（Tushare `stock_basic.industry` 简化分类字符串）做字典映射，不新增数据源。

**理由**：
1. Grep 核查确认当前数据管道（AKShare/Baostock/Tushare）均没有接入 SW/CS 官方行业代码接口；引入官方代码需要新 fetcher（Tushare `index_classify`/`index_member` 或 AKShare 对应接口）、新字段、可能的新持久化列，工程量远超"路由增强"范畴。
2. 现有 `industry` 字段已经在生产路径上（`route()` 第 2 步已经在用它判断"银行"），扩展为字典映射是对既有机制的自然延伸，不是新增能力。
3. Tushare 简化分类的粒度（银行/保险/电力/…一级行业名）对于"排除已知误判 + 命中已实现原型"这两个目标已经足够；SW/CS 多级代码的额外价值（如区分"银行-国有大型银行"vs"银行-城商行"）在 V1 三原型范围内没有实际收益。

**备选方案（拒绝）**：
- **方案 B：新增 Tushare `index_classify`（申万行业分类）接入**——拒绝（本 change 不做，留 Open Question）。理由：需要新增 fetcher 模块、`StockSnapshot` 表新列、离线合并逻辑，且 `index_member` 类接口的 Tushare 积分要求未知，可能重复 D-E（历史 PE/PB）当年"积分门槛需运营方承担"的决策链条；在当前"已识别行业名称"的字典方式已能解决具体误判 bug 的前提下，优先级不足以在本 change 内一并解决。
- **方案 C：不用字符串行业名，改用交易所行业代码前缀（如申万一级代码 `Bxx`）做映射**——拒绝，理由同 B，当前无该代码字段可用。

### 决策 2：行业映射的三分支输出——已实现原型 / 已识别待实现 / 未识别

**选择**：`_classify_by_industry(industry: str) -> str | None` 返回三种结果之一：
- 命中 `_INDUSTRY_PROTOTYPE_MAP`（如"银行"→`bank`，"电力"→`high_dividend`）→ 返回该 prototype 字符串
- 命中 `_INDUSTRY_V2_UNIMPLEMENTED`（如"保险"、"国防军工"）→ 返回 `"unknown"`（显式短路，不继续走启发式）
- 两者都未命中，或 `industry` 为空字符串 → 返回 `None`（调用方据此回退到现有财务启发式）

`_classify()` 主流程：`_CODE_OVERRIDE` 命中 → 直接返回；否则调用 `_classify_by_industry()`，非 `None` 则直接返回；否则继续现有第 3–6 步财务启发式（原样保留，不修改内部逻辑）。

**理由**：三分支设计让"行业已识别但方法论暂缺"和"行业信息完全缺失/未收录"在返回值层面是相同的（`"unknown"`），保持 `route()` 对外契约不变（仍是 4 个既有取值之一），但**判定路径不同**——前者是"主动识别后判定不适用现有方法"，后者是"缺乏信息判定不适用现有方法"，这个区分对下游（`add-prototype-fallback-message`）精确措辞很重要，因此设计上把区分点放在 `_classify_by_industry()` 内部（可被未来 change 复用/检视），而不是把两者合并成一次判断丢失区分信息。

**备选方案（拒绝）**：
- **方案 B：命中 V2 行业时也继续走启发式**（只是"参考"而非"短路"）——拒绝。理由：这恰恰是当前 bug 的根源（保险被杠杆率误判为 bank），如果不短路就无法修复本 change 的核心动机。
- **方案 C：为 V2 行业新增独立 prototype 值（如 `"insurance_unimplemented"`）**——拒绝，属于范围蔓延；`_PROTOTYPE_METHODS`、`aggregator.py`、`evidence_bucketer.py` 都需要联动处理这个新值，与"覆盖当前已支持的 prototype"的既定范围（见 proposal.md）冲突，留给未来若确定要实现保险/军工模型（T-4/T-5）时再引入真实新 prototype。

### 决策 3：映射表内容——V1 覆盖范围与匹配方式

**选择**：
- `_INDUSTRY_PROTOTYPE_MAP`（子串匹配，覆盖已实现的 3 个原型）：
  - `bank`：`"银行"`
  - `high_dividend`：`"电力"`、`"水务"`、`"燃气"`、`"高速公路"`、`"港口"`（对齐 MRD §2.2"高股息·类债"公用事业类描述）
  - `value_growth`：V1 不显式列举（继续依赖财务启发式兜底判定，行业映射只做"排除"与"银行/高股息类"的正向命中，避免对"价值成长"这种宽泛类别做过度归纳）
- `_INDUSTRY_V2_UNIMPLEMENTED`（子串匹配，对齐 MRD §2.2 V2 原型清单的行业名称）：`"保险"`、`"国防军工"`、`"军工"`
- 匹配方式沿用现有 `"银行" in stock.industry` 的子串匹配风格（而非精确相等），因为 Tushare `industry` 字段存在"银行"/"商业银行"等变体，子串匹配容错性更好，与现有测试 `test_bank_classification_by_industry`（`industry="商业银行"`）保持兼容

**理由**：字典风格与 `EvidenceBucketer._PROTOTYPE_VULNERABILITIES` 硬编码字典一致（proposal.md 已提及），符合仓库既有的"V1 硬编码 + 后续可扩展"惯例；范围刻意保守（不预测性地列举成长/周期类行业名称），因为这些行业本身就该继续走财务启发式兜底，风业映射的价值在于"排除已知误判"和"命中确定信号"，不是替代整个分类体系。

**备选方案（拒绝）**：
- **精确相等匹配**（`industry == "银行"`）——拒绝，Tushare 行业名称存在多个变体写法，精确匹配会漏判，且与现有测试用例（`"商业银行"`）冲突。

## Risks / Trade-offs

- **[风险] Tushare `industry` 字段的具体取值集合未被系统性枚举过**（本 change 基于对"银行"/"保险"等常见分类名称的合理推测，未逐一核对全部 A 股行业名称的真实字符串）→ **缓解**：tasks.md 包含端到端验证步骤，用真实样本股（如中国平安 601318）运行 `sync` + 路由，核对 `stock.industry` 的实际取值是否命中 `_INDUSTRY_V2_UNIMPLEMENTED`；若实际字符串与预期不同（如"保险业"而非"保险"），在实现阶段调整字典内容，不影响本 change 的架构设计。
- **[风险] `_INDUSTRY_PROTOTYPE_MAP` 的高股息行业列表（电力/水务/燃气/高速公路/港口）可能覆盖不全，导致部分高股息类股票仍走启发式路径**→ **接受**：这与现状（完全无行业映射）相比是纯增量改善，未覆盖的情况会精确回退到现状行为（financial heuristic），不会更差；字典可在后续 change 中增量扩充，不需要本 change 一次性穷尽。
- **[风险] 若 `add-prototype-override-persistence`（T-8）在本 change 之后实施，需要在 `_classify()` 最前插入人工覆盖检查**→ **缓解**：本 change 保持 `_classify()` 判定层级清晰（覆盖表 → 行业映射 → 启发式），新增人工覆盖只需在最前插入一个 `if` 分支，不需要重构现有判定链；已在本 design 的"三层路由优先级"约定中留好插入点（详见 `add-prototype-override-persistence` design.md 的交叉引用）。

## Migration Plan

- 无数据库变更（`industry` 字段已存在于 `StockSnapshot`/`StockData`，本 change 不新增列）
- `route()` 对外签名不变，现有调用方（`ValueAnalyzer._analyze_stock()`）无需修改
- 行为变化范围：仅影响 `industry` 字段命中 `_INDUSTRY_PROTOTYPE_MAP`/`_INDUSTRY_V2_UNIMPLEMENTED` 的股票；未命中的股票（包括当前所有测试 fixture 中未显式设置 industry 的用例）行为与改动前完全一致
- 回滚：将 `_classify()` 还原为直接调用财务启发式（删除行业映射分支）即可，不影响 `_CODE_OVERRIDE`/`_PROTOTYPE_METHODS`

## Open Questions

- 是否需要引入 SW/CS 官方多级行业代码（Tushare `index_classify`/`index_member` 或等价 AKShare 接口）？本 change 判断 V1 阶段收益不足以覆盖新增数据管道的工程成本，留待未来若产品需要更细粒度行业区分（如银行内部区分国有大型/城商/农商）时再单独立项（建议 change 名 `add-sw-industry-classification`）。
- `_INDUSTRY_PROTOTYPE_MAP`/`_INDUSTRY_V2_UNIMPLEMENTED` 的具体行业名称字符串需要在实现阶段用真实 Tushare 数据核实（见 Risks），本 change 的字典内容是基于 MRD 描述的合理起点，非最终穷尽列表。
- 与 `add-prototype-override-persistence`（T-8）的实施顺序：两个 change 相互独立，不强制先后依赖，但若 T-8 先实施，需在 `_classify()` 最前插入人工覆盖检查（本 design 已预留插入点）；若本 change（T-7）先实施，T-8 的人工覆盖检查同样插入在 `_CODE_OVERRIDE` 之前即可，两种实施顺序都不需要重新设计对方。
- 与 `add-prototype-fallback-message`（T-15）的关系：T-15 建议在本 change 之后实施，以复用 `_INDUSTRY_V2_UNIMPLEMENTED` 字典产出精确降级文案（如"检测到保险行业，专用方法论暂缺"）；若 T-15 先于本 change 实施，其降级文案精度会退化为通用"原型未识别"提示（价值有限），详见 `add-prototype-fallback-message` design.md 的依赖说明。
