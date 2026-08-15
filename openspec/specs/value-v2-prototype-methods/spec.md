# value-v2-prototype-methods Specification

## Purpose

价值面 V2 专用原型与方法分阶段落地：按 Phase 引入成长制造情景、广告周期、军工订单、保险 EV/NBV、成长科技路由；输入不足时保持诚实层去行动化，专用方法可用时从诚实降级毕业。
## Requirements
### Requirement: V2 原型分阶段落地与诚实层毕业

系统 SHALL 按 Phase 引入 V2 专用原型与方法；在专用方法输入不足或未实现时，SHALL 保持与诚实层等价的去行动化行为（`methodology_applicable=False` 或同等）。当某样本的专用方法成功产出可用结果时，SHALL 将该样本从「仅诚实降级」毕业为对应 V2 prototype，并允许可引用的主评估（仍须展示关键假设/情景）。

Phase 与样本最低要求：

| Phase | prototype（建议键） | 样本 code | 最低能力 |
|-------|---------------------|-----------|----------|
| P1 | `growth_manufacturing` | `002594` | 至少三档情景估值输出 |
| P2 | `cashflow_ad_cycle`（+ Cyclical 基建） | `002027` | 至少一种周期调整估值可用或显式降级 |
| P3 | `defense_orders` | `600072` | 有订单类输入则专用结果；否则诚实降级 |
| P4 | `insurance` | `601318` | 有 EV/NBV 类输入则专用结果；否则诚实降级 |
| P5 | `growth_tech` | `300627` | 路由至成长方法集（含已有 PEG/Rule of 40 等） |

#### Scenario: P1 比亚迪在情景可用时毕业

- **WHEN** Phase P1 完成且比亚迪情景假设可用
- **THEN** prototype 为成长+制造周期键，报告含多情景，主结论非「方法暂不适用」

#### Scenario: P1 情景缺失时仍诚实降级

- **WHEN** 比亚迪情景假设缺失
- **THEN** 不得给出可执行的单一「低估→买入」价值叙事

#### Scenario: P5 华测路由到成长方法

- **WHEN** Phase P5 完成
- **THEN** `300627` 的 method_keys 含成长类方法（如 peg / rule_of_40 之一），且不以 value_growth 静默替代而不说明

### Requirement: 浅情景 DCF 输出契约（P1）

成长+制造周期原型 SHALL 支持悲观/基准/乐观至少三档假设下的估值结果，并在 `ValueAnalysisResult`（或明确子结构）中可被报告层读取。主展示 SHALL 让用户看到「现价落在哪档情景附近」，SHALL NOT 仅输出一个未标注情景的公允中枢冒充唯一真理。

#### Scenario: 三档情景均有结果

- **WHEN** 三档假设完整且 DCF 可算
- **THEN** 结果含三档估值（或等价区间），文本报告可区分悲观/基准/乐观

### Requirement: Cyclical 基建与广告周期样本（P2）

系统 SHALL 引入 `CyclicalStock`（或等价扩展字段：周期位置、均值化盈利/FCF 等）。分众样本在周期输入可用时 SHALL 使用周期调整方法子集；不可用时诚实降级。

#### Scenario: 分众在周期输入可用时使用周期方法

- **WHEN** `002027` 具备周期估值所需字段
- **THEN** method_keys 含至少一种 `cyclical_*` 方法且 methodology 可适用

### Requirement: 军工与保险的输入门禁（P3/P4）

军工订单模型与保险 EV/NBV 模型 SHALL 在关键输入缺失时拒绝假装适用：保持诚实降级文案（订单驱动 / EV·NBV 暂缺或输入不足）。输入存在时 SHALL 运行专用方法并毕业。

#### Scenario: 平安无 EV 输入则不毕业

- **WHEN** `601318` 缺少 EV/NBV 输入
- **THEN** `methodology_applicable` 为 False（或 assessment 为方法暂不适用语义）

#### Scenario: 中船无订单输入则不毕业

- **WHEN** `600072` 缺少订单类输入
- **THEN** 保持军工诚实降级语义
