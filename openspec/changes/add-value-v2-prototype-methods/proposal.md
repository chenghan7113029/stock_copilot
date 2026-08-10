## Why

诚实层（`add-v2-honesty-degrade`）已对比亚迪、分众、保险、军工做到「不再误导」；但持仓与想买标的仍**缺专用估值方法**，对照数字无法升级为可引用结论。MRD §2.2 / roadmap §4.3 列出的 V2 原型（保险 EV/NBV、军工订单、成长 PEG、制造情景 DCF、Cyclical 等）需按**应用场景优先**（Owner：比亚迪 > 中船+分众 > 平安 > 华测）分阶段落地，而不是按历史任务编号顺序。

## What Changes

本 change 是价值面 **V2 专用方法总立项**（多阶段）。成功标准延续探索结论：**可引用结论优先于假精确**；无可靠输入时保持诚实降级，不静默套用 V1。

分阶段交付（apply 可按 Phase 暂停）：

| Phase | 内容 | 样本 | 毕业诚实层 |
|-------|------|------|------------|
| **P1** | 成长+制造周期：浅情景 DCF（悲观/基准/乐观）+ 报告叙事；主结论以情景落位表达，非单一公允中枢当真理 | 比亚迪 `002594` | 可从 code 诚实名单移除（或仅在情景可用时 applicable） |
| **P2** | `CyclicalStock` + 周期方法子集（至少 FCF/PE）+ 分众路由 | 分众 `002027`（北大荒可同基础设施、非必须同发） | 分众可毕业 |
| **P3** | 军工·订单驱动（订单/合同负债等输入；缺数据则保持降级） | 中船 `600072` | 有输入才毕业 |
| **P4** | 保险 EV/NBV（或经论证的弱专用+低置信；优先有可信输入） | 平安 `601318` | 有输入才毕业 |
| **P5** | 成长（科技）原型正式路由：接线已有 PEG/GARP/Rule of 40 等 | 华测 `300627` | 新原型，非诚实名单 |

横切：

- Router：新 prototype 键与 method_keys；code/行业映射；与 override、诚实层共存
- Aggregator / 报告：情景或多区间展示契约；毕业后 `methodology_applicable=True`
- **不做（本总立项明确排除）**：T-1 MOS 阈值（独立 change `add-mos-thresholds-by-prototype`）；飞书/形态/布林带；假装自动填满 EV/订单字段

## Capabilities

### New Capabilities

- `value-v2-prototype-methods`：V2 原型定义、路由、专用方法、情景/周期输出与诚实层毕业规则（分 Phase 验收）

### Modified Capabilities

- `value-prototype-router`：注册 V2 prototype 键与映射（随 Phase 增量）
- `value-analyzer`：V2 方法编排；情景/周期结果进入 `ValueAnalysisResult`；毕业诚实压制
- `cli-report-value`：情景区间 / 周期位置等展示（非金融可读）

## Impact

- **代码**：`src/service/value/router.py`、`analyzer.py`、`models/`、`valuation/`（情景 DCF、cyclical、insurance、order-driven 等新模块）；`apps/formatters.py`
- **数据**：部分 Phase 需手动/配置输入（订单、EV/NBV、情景假设）；无输入则保持降级
- **依赖**：强烈建议先合入 `add-v2-honesty-degrade`；T-1 可并行、不阻塞 P1
- **文档**：`docs/mrd/features/value-analysis.md` §2.2/§3/§4/T-4～T-12；roadmap §4.3
- **风险**：单体 change 跨度大——**以 Phase 为 apply 边界**；若执行中需拆 PR，保持本 proposal 为真源、子切片可另开 change 但须回链
