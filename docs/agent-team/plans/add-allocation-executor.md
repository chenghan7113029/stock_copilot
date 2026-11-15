# add-allocation-executor 收波记录（2026-11-15）

> 计划真值源：[add-allocation-executor.yaml](add-allocation-executor.yaml)（29 条起跑断言 + 11 任务 + 派生 T9）。
> 本文件只记「交付结果 / 遗留 / 流程教训」，不复述契约。

## 交付结果

| 项 | 值 |
| --- | --- |
| 能力 | `allocation-executor`（一期 P0 第二项）：`ips plan --as-of <date>` 纯算术月度指令 |
| 主规格 | `openspec/specs/allocation-executor/spec.md`：10 Requirement / 28 Scenario；Purpose 331 字符、无 TBD |
| 归档 | `openspec/changes/archive/2026-11-15-add-allocation-executor/`（11 文件，含 verification / review / knowledge-verification） |
| 合并 | feature `c977312` → main **`2f49f2f`**（`merge --no-ff`，无冲突）；feature 分支保留 |
| 门禁 | 全量 **1177 passed / 32 deselected**；QA `test/qa` 99 passed（其中 allocation 37）；本 change ruff 新增 0；`validate --specs` **25 passed / 76 failed**（归档前 24/76，零新增失败）；`validate --archived` 41/15（零新增失败）；`closeout --stage post` ERRORS=0；`check_knowledge_source.py` 0 error |
| 知识 | 新增 5 条 canon（`CAN-ALLOC-001…005`）+ 6 条 KU；canon 准入③ 由「≥2 Requirement」细化为「可回解消费点 + 分档」并完成 7 条回填 |

## 行为边界（本波明确不做/不作为门禁）

- 硬门禁**只有一条**：快照 `as_of` 超 `rules.R8_stale_days`（7 天）或未来日期 → 拒绝（exit 2）。
- 权益 40% / 单票 5% / 行业 25% / 止损 -15% / MA60 / 现金 20% / 再平衡 5pp **全部只提示**，不改金额、不产调仓指令（文档 v2 已把未验证阈值移出验收标准）。
- 零 LLM、零网络、零政策值硬编码（全部读 `config/ips.yaml`）；私人数值不进 canon。

## 未决口径（下波首项，`IMP-add-allocation-executor-04`）

| # | 问题 | 本波临时口径 |
| --- | --- | --- |
| A | 现金 <20% 是压缩买入额还是只提示 | 只提示、不改金额 |
| B | 执行日遇休市/节假日 | 仍按日历周四给指令（不做交易日顺延） |
| C | 再平衡 5pp 是只提示还是季度真调回目标带 | 只提示（草案 `portfolio-plan-v0.1.md:110` 写「季度调整回目标带」，存疑） |

## 遗留与流程教训

1. **可审计性缺口**（IMP-01，P1）：迁移金额 135,000 未回显 `trial_ratio`，工单不能独立复算。
2. **规格漂移**：`CAN-GATE-002`（影子期 3 个月，Owner 2026-11-15）vs 主规格 `R19`（6–12 个月）——知识库已登记冲突，需另立 change 修 spec，不得静默消解。
3. **canon 观察名单**（6 条）：有 Requirement 无 Scenario 断言，2 波无新增消费点降 `hypotheses`。
4. **`plan.yaml` inScope 格式**：写「…（待新建）」会让运行时 completion 按字面比对、无法登记 changedPaths；**下波 inScope 只写纯路径**，「待新建」只用于文档说明。
5. **`check` S1 误判**：根目录点文件 `.gitattributes`（无扩展名）被判为裸名；`closeout` R1 已正常认领。属校验器 false positive，待修脚本（不得改脚本放宽）。
6. **归档前未提交产物**：T6 的 `review.md` 曾被漏 `git add`，由 integrator 补提交（`5622781`）——评审类产物提交应在任务完成定义里显式要求 `git status` 干净。
7. **closeout 阶段参数**：归档后必须用 `--stage post`，否则 R5（主规格未改）会假红。
