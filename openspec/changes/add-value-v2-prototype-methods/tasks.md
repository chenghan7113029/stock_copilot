## 0. 前置

- [x] 0.1 确认 `add-v2-honesty-degrade` 已合入目标分支（或本分支可依赖其行为）
- [x] 0.2 Update `propose_list.md` / roadmap：本 change 为 V2 方法总立项，按 P1–P5 推进

## 1. Phase P1 — 比亚迪浅情景 DCF

- [x] 1.1 Design 定稿最小情景假设键；Create 配置/模型字段
- [x] 1.2 Create `growth_manufacturing` 原型路由（code `002594`）+ method_keys
- [x] 1.3 Implement 情景 DCF 运行与结果结构
- [x] 1.4 Modify Analyzer/Formatter：三档展示；情景可用则毕业诚实层
- [x] 1.5 Test + 目视 `report value 002594`

## 2. Phase P2 — Cyclical + 分众

- [x] 2.1 Create `CyclicalStock`（或 StockData 扩展）+ port 至少 1–2 个 cyclical 方法
- [x] 2.2 Create `cashflow_ad_cycle` 路由（code `002027`）
- [x] 2.3 Analyzer/Formatter 周期语义；毕业条件
- [x] 2.4 Test + 目视 `report value 002027`

## 3. Phase P3 — 军工订单

- [x] 3.1 Define 订单类输入字段与 CLI/配置入口
- [x] 3.2 Implement `defense_orders` 方法 + 路由（`600072`）
- [x] 3.3 无输入保持降级；有输入毕业
- [x] 3.4 Test 双向路径

## 4. Phase P4 — 保险 EV/NBV

- [x] 4.1 Define EV/NBV 输入字段与入口
- [x] 4.2 Implement `insurance` 方法 + 路由（`601318`）
- [x] 4.3 无输入保持降级；有输入毕业
- [x] 4.4 Test 双向路径

## 5. Phase P5 — 华测成长路由

- [ ] 5.1 Create `growth_tech` 原型与 method_keys（接线既有 peg/garp/rule_of_40 等）
- [ ] 5.2 路由 `300627`（及可选行业启发）
- [ ] 5.3 Test + 目视 `report value 300627`

## 6. 文档与归档

- [ ] 6.1 Update `docs/mrd/features/value-analysis.md` §2.2/路由表/T-4～T-12 状态（随 Phase 更新）
- [ ] 6.2 Update `docs/mrd/roadmap-todo.md` §4.3
- [ ] 6.3 全部 Phase 完成后 `/opsx-archive`（中途可先合 PR，归档可等收官或按子 change 归档）
