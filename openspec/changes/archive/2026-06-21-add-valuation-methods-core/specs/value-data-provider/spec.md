## MODIFIED Requirements

### Requirement: 统一 A 股股票估值数据模型
系统 SHALL 提供一个统一的股票估值数据模型，覆盖 MRD §7 中 V1 三原型（银行 / 高股息·类债 / 高质量价值成长）所有估值方法所需的字段，包括：基础行情（当前价、总股本、市值）、每股指标（EPS、BVPS、每股分红）、盈利（营收、净利润、ROE/ROIC）、现金流（自由现金流、经营现金流、capex）、资产负债（总资产、总负债、净负债、股东权益）、分红（股息率、派息率、分红历史）、历史估值序列（历史 PE / PB）、质量与风险明细（Altman-Z / Piotroski-F / Beneish-M 所需输入）。

该模型为确定性数据结构，MUST NOT 由 LLM 生成或修改。

新增字段（向后兼容追加，默认 None）：
- `historical_pe: list[float] | None`：历史滚动 PE 序列（最近 N 期，降序），供相对估值方法使用
- `historical_pb: list[float] | None`：历史滚动 PB 序列（最近 N 期，降序），供相对估值方法使用

#### Scenario: 模型字段覆盖 V1 方法需求
- **WHEN** 价值面估值方法（PB、剩余收益、DDM、DCF、EPV、Owner Earnings、Graham、相对估值、Altman-Z、Piotroski-F、Beneish-M）声明其输入字段
- **THEN** 数据模型 SHALL 为每个字段提供对应属性，且类型明确（数值/序列/日期）

#### Scenario: 数据模型不可由 LLM 改写
- **WHEN** 数据模型实例被传入下游
- **THEN** 其数值字段 SHALL 仅来自 data_provider 的确定性取数，不经任何 LLM 环节

#### Scenario: historical_pe / historical_pb 字段缺失时相关估值方法返回 Not Applicable
- **WHEN** `StockData.historical_pe = None`（data_provider 尚未支持历史数据获取）
- **THEN** `PERelativeValuation.calculate()` 返回 `applicability = "Not Applicable"`，不抛异常，不阻断其他方法运行

#### Scenario: historical_pe / historical_pb 字段有值时相对估值方法正常运行
- **WHEN** `StockData.historical_pe = [18.5, 20.1, 15.3, 22.0, 16.8]`（5 期历史 PE）
- **THEN** `PERelativeValuation.calculate()` 正常输出公允价区间，`applicability = "Applicable"`
