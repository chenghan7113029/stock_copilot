## Why

股票估值是 stock_copilot 价值面分析的核心能力，目前项目只有数据管道（`data_provider`）
而没有计算层。需要将 `ref/valueinvest` 中已验证的估值算法移植进 `src/service/value/`，
建立可测试、可配置、可扩展的方法论计算库，作为后续原型路由与 LLM 综合决策的基础。

Phase 0–3 聚焦"先跑通最小闭环"：基础设施骨架 + Graham 体系 + 银行专用模型 + 股息模型，
覆盖 A 股三大典型原型中的银行（工行）和高股息（长江电力）两类，可独立交付并验收。

## What Changes

- **新增** `src/service/value/valuation/` 目录，建立方法论计算层骨架（`BaseValuation`、
  `AssumptionProvider`、`StockDataAdapter`、`ValuationEngine`）
- **新增** 3 组共 8 种估值方法实现：
  - Graham 体系：`GrahamNumber`、`GrahamFormula`、`NCAV`
  - 银行专用：`PBValuation`、`ResidualIncome`
  - 股息模型：`DDM`（Gordon Growth）、`TwoStageDDM`
  - 盈利力价值：`EPV`（Earnings Power Value）
- **新增** WACC 计算模块（`wacc.py`），从 `StockData` 字段推导，可配置覆盖
- **新增** 对应单元测试（`test/service/value/`），验收标准：与 `ref/valueinvest` 同输入 ±0.1%
- **修改** `src/common/models.py`（或 `StockData`）：扩展 `historical_pe`、`historical_pb`
  可空列表字段，为后续相对估值准备
- **新增** `docs/design/valuation-methods-reference.md`（已存在，Phase 0–3 对应方法论文档）

## Capabilities

### New Capabilities

- `valuation-infrastructure`: 估值方法论层基础设施（`BaseValuation`、`AssumptionProvider`、
  `StockDataAdapter`、`ValuationEngine` 注册表），含 None/0 语义适配和配置化参数体系
- `valuation-graham`: Graham 体系三方法（GrahamNumber、GrahamFormula、NCAV），
  适用防御型 A 股价值投资筛选
- `valuation-bank`: 银行/金融类专用两方法（PBValuation、ResidualIncome），
  适用招行/工行等 PB 主导定价的标的
- `valuation-ddm`: 股息折现模型两方法（DDM、TwoStageDDM），
  适用长江电力/国家电网等高分红公共事业类标的
- `valuation-epv`: 盈利力价值法（EPV），零增长假设下的保守基准估值，
  适用稳定盈利的成熟企业

### Modified Capabilities

- `value-data-provider`: 扩展 `StockData` 模型，新增 `historical_pe: list[float] | None`
  和 `historical_pb: list[float] | None` 可空字段（向后兼容，仅追加）

## Impact

- **新增模块**：`src/service/value/valuation/`（6 个文件 + `__init__.py`）
- **新增测试**：`test/service/value/`（5 个测试文件）
- **微改**：`src/common/models.py` 或 `StockData` 数据类（追加两个可空字段，不破坏现有序列化）
- **无 API 变更**：本期无 controller 层暴露，估值引擎仅作为 service 内部库
- **依赖**：无新第三方包（pure Python，仅依赖已有 `dataclasses`、`math`、`typing`）
- **文档**：`docs/design/valuation-methods-reference.md` 已就绪，`docs/mrd/features/value-analysis.md` Phase 0–3 章节已就绪
