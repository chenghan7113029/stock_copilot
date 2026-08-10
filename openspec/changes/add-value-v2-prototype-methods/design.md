## Context

V1 三原型已通；诚实层堵住比亚迪/分众/保险/军工的假买入叙事。Owner 持仓优先级决定实现顺序（≠ MRD 编号 T-4→T-6）。`ref/valueinvest` 有 Cyclical 与成长方法可 port；保险 EV/NBV、军工订单需新建且常缺免费 API 字段。

## Goals / Non-Goals

**Goals:**

- 按 P1→P5 为样本股提供**可理解的专用/半专用**估值输出
- 无可靠输入时保持诚实降级，毕业条件明确可测
- Router 可扩展新 `prototype` 而不破坏 V1
- 非金融背景：情景/周期用「落在哪档故事」表达，避免假中枢

**Non-Goals:**

- 一次 apply 做完所有 Phase（允许暂停）
- 自动爬取完整内含价值/在手订单（可用 YAML/CLI 手工输入）
- T-1 MOS 阈值、技术面 V2、飞书推送
- 深自动化周期定位（P2 可先手工/简单启发式 cycle_position）

## Decisions

### D1：阶段顺序锁死为应用优先

`P1 比亚迪情景 → P2 Cyclical+分众 → P3 军工 → P4 保险 → P5 华测成长路由`

**理由**：Owner 持仓/想买顺序。  
**否决**：严格按 T-4/T-5/T-6 编号。

### D2：P1 浅情景 DCF，不作深自动化

- 三档假设（悲观/基准/乐观）来自配置或股票级 override（增长率、利润率、产能利用率等有限键）
- 输出：三档公允区间或价格落位；主 `assessment` 可用「基准情景下…」或保持区间叙事；**禁止**把单点 DCF 中枢包装成唯一真理
- 情景不可用 → 维持诚实降级

### D3：新 prototype 键（建议名，实现可微调但须稳定进 specs）

| 键 | 含义 | Phase |
|----|------|-------|
| `growth_manufacturing` | 成长+制造周期 | P1 |
| `cashflow_ad_cycle` | 现金流+广告周期 | P2 |
| `defense_orders` | 军工订单 | P3 |
| `insurance` | 保险 | P4 |
| `growth_tech` | 成长科技 | P5 |
| （可选）`cyclical_asset` | 周期+资产 | P2 基础设施可复用 |

诚实名单 code 在对应 Phase 毕业后迁入上述键，而不再映射 `unknown`。

### D4：Cyclical 先子集

P2 先 port `cyclical_fcf` + `cyclical_pe`（或文档论证的最小集）+ `CyclicalStock`（含 cycle_position / 均值化盈利字段）；四方法全齐可后续增量。

### D5：P3/P4 数据墙策略

- 定义显式可选输入字段（如 `order_backlog`、`embedded_value`、`nbv`）
- 缺失 → `methodology_applicable=False` + 精确缺口（保持诚实）
- 有输入 → 跑专用方法并毕业

### D6：与诚实层 / override

- 毕业 = 路由到真实 V2 prototype 且专用方法产出可用结果
- 人工 override 到 V1 原型仍允许（知情选择）
- 未毕业前行为不得弱于当前诚实层

### D7：大 change 的工程节奏

每个 Phase 结束应：单测绿 + 样本 `report value` 目视 + 更新 tasks checkbox；可开 PR 合入后再继续下一 Phase。若需拆成子 change，子 change proposal 首段 MUST 链接本 change。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 情景假设变成另一种假精确 | 默认假设保守；报告强制展示三档与来源 |
| Cyclical 缺 cycle_position 乱估 | 无位置则降级，不瞎均值 |
| EV/订单数据长期缺失 | P3/P4 允许「永久半诚实」+ 手工输入通道 |
| 范围膨胀拖死 | Phase 门禁；P5 只做路由接线 |

## Migration Plan

1. 合入诚实层后从 P1 开始  
2. 每 Phase：router → methods → analyzer/report → 毕业名单 → 文档  
3. 回滚单 Phase：恢复 code 诚实名单即可降级

## Open Questions

- P1 情景键具体列表（收入增速 / 车型毛利 / 产能利用率…）apply 前用样本年报定一版最小集
- P4 是否允许「无 EV 时的弱专用」（剩余收益+低置信）——默认 **否**，与「不再误导」一致；若 Owner 改口再改 specs
