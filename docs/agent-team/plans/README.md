# 波次计划（plan.yaml）

> 一句话：**任务的字段写在这里，不写在脑子里。**
> `python scripts/agent_team_plan.py check` 退出码 0 才允许起波；建任务时用
> `render <ID> --json` 取参数粘贴进 `create_task`，不要手抄。

## 为什么有这个文件

起波要做两件「文本 → 动作」的人工翻译：读检查表、把 11 个任务的契约逐字抄进工具调用。
两步都不报错——漏一条只是少做一点，抄错一个字段只是让成员做的事和 finding 无关。

`plan.yaml` 把契约变成仓库里的文件，于是这些判断第一次变成可执行断言：能被脚本读、能被 diff
审、能随 change 一起归档。**契约进文件是可机检的前提**——inScope 只存在于运行时工具调用时，
仓库里没有任何东西承载它，事后无法复核。

## 用法

```bash
python scripts/agent_team_plan.py init --change add-foo --case case-20261114-foo
# 填 TODO（每处占位符都是必填项，check 会逼它被填掉）
python scripts/agent_team_plan.py check          # 退出码 1 = 不许起波
python scripts/agent_team_plan.py render T3 --json   # 建任务时取参数
python scripts/agent_team_plan.py checks         # 全部断言清单
```

`check` 不替你判断内容好坏——它只管**结构与形态**：编制定没定、DAG 通不通、字段够不够、
路径是不是文件、verify 有没有被放宽、数字有没有写死。语义正确性（判据有没有能力变红、
inScope 归属对不对）留给 `templates/wave-tasks.md` 检查表里「需要人判断」的部分。

## 字段

```yaml
wave:
  change: add-foo                 # kebab-case，与 feature 分支同名
  branch: feature/add-foo
  case: case-20261114-foo         # 目录名；check 验 docs/cases/<case>/annotations.md 有 ground-truth 标注
  mrd: docs/mrd/mrd-v1.md
  baseline_commit: 47a6a42        # 起队凭据：按哪一版配置起的队（须是 HEAD 祖先）
  engineer_test_root: test/       # 双轨分离用：engineer 不得进 test/qa/，QA 不得进 test/
  qa_test_root: test/qa/
  allow_custom_dag: false         # 偏离 11 任务编制时设 true，并在 note 写理由
  note: ""
members:                          # 只有名字：模型与 effort 唯一真值源是 models.yaml
  - name: product-manager
tasks:
  - id: T3
    kind: implementation          # quality kind 才有 acceptance/verify 承载
    assignee: engineer
    subject: "..."
    description: "..."            # work kind 必含「完成定义」「失败定义」两段
    dependencies: [T2]            # 只能依赖上游（D4）
    inScope: [src/service/foo.py] # 逐文件；必须有扩展名、不得是目录
    outOfScope: [openspec/specs/] # 允许目录（禁止面写粗不吃亏）
    acceptance: ["不低于起跑时实测值"]        # 禁写死「832 passed」
    verify: ["python -m pytest -q"]          # 禁 --deselect / -k not / || true / python3
    reviewed_task: T3             # 仅 review kind
```

`init` 生成的骨架自带占位符（`TODO:`），`check` 会全部报错——**骨架看起来像完成，是本项目
最贵的一种错觉**，所以宁可让它一生成就红。

## 29 条断言 ↔ 它接管了检查表的哪一条 ↔ 历史依据

改脚本前先看这张表：每条都对应一次真实事故，删检查等于让事故重演。

| 断言 | 管什么 | 依据 |
| --- | --- | --- |
| M1 | 成员集合 == `models.yaml` 的 roles | 模型裸名解析失败、编制漂移 |
| M2 | 11 任务 / 8 成员；偏离须 `allow_custom_dag` + 理由 | 起队前必须现读对账 |
| M3 | 成员 name 在 `models.yaml` 能解析、effort 非空 | 成员模型传裸名 → `UNKNOWN_MODEL` |
| C0 | kind 与负责人 == PLAYBOOK §4 编制 | 悄悄改编制等于绕过闸门 |
| C1 | 质量 kind 必须有 acceptance | 没有判据的闸门无法判定通过 |
| C2 | 质量 kind 必须有 verify | 无命令的验收 = 没有验收 |
| C3 | `reviewed_task` 指向 implementation / repair | review 挂错对象 → 框架生成打偏的 repair |
| C4 | work kind 的 description 含完成 / 失败定义 | work 无 acceptance 承载、启动后不可编辑、`amend_task` 不管用 |
| C5 | 无占位符残留 | 骨架 / 半成品被当成完成 |
| D1 | DAG 无环 | `edit_plan` 造环后全线卡死 |
| D2 | 依赖指向存在的任务 | 依赖不存在的 id = 永不 ready |
| D3 | 关键边在位（T2←T1,K1 / K3←K2,T1 / T6←T3,T5,K3 / T8←T7,K3 …） | 漏一条边 = 闸门形同虚设 |
| D4 | 依赖只从下游加 | 给上游加依赖会误报 inScope 重叠甚至造环 |
| S1 | inScope 逐条是文件且带扩展名（或标「待新建」），不得是目录 | 目录化笼住他人文件；裸名致 repair 死锁 |
| S2 | 质量 kind 的 inScope 非空 | 改了什么都无法界定 |
| S3 | engineer 不碰 `test/qa/`、QA 不碰 `test/` 与 `src/` | 双轨分离（QA 盲测的前提） |
| V1 | verify 未被放宽（`--deselect` / `-k not` / `\|\| true` / `--ignore=`） | 假绿比删测试更隐蔽 |
| V2 | acceptance 未写死测试数字 | 写死必然过期，repair 只能改测试凑数或死锁 |
| V3 | verify 里没有 `python3`、`openspec` 必须写成 `openspec.cmd` | 本机没有 `python3`；裸 `openspec` 撞 PowerShell 执行策略 |
| K1 | 知识线（K1/K2/K3）kind == work | 质量闸门面向代码，套在知识上会路由出错误修复 |
| K2 | K3 写明「盲验」 | 不写死就退化成本人自验（利益冲突） |
| P1 | `_shared.md` ≤3200B、角色 ≤8000B | 每步重发；规则多了会被挑着执行且不报错 |
| P2 | 每个成员都有 `roles/<name>.md` | 成员没有 SOP = 全凭即兴 |
| A1 | case 存在且带 ground-truth 标注 | 没有现实锚点的波次会产出自嗨产物（本项目立项的第一性约束） |
| A2 | MRD 文件存在 | 同理 |
| G1 | 当前分支 == plan.branch | 在 main 上起波 |
| G2 | 工作树干净（warning） | 并行 session 的改动被卷进本波 |
| G3 | `baseline_commit` 是 HEAD 祖先 | 起队凭据缺失 = 无法回答「按哪版配置起的队」 |
| G4 | `git user.email` == `chenghan7113029@users.noreply.github.com` | 提交身份靠邮箱判定，姓名不可信 |

## 不在这张表里的东西（必须人判）

语义正确性、判据有没有能力变红、运行时动作（reassign、amend、看门狗）、以及
「inScope 归属是否与 `design.md` 的文件所有权一致」。最后一类见
[`../templates/wave-tasks.md`](../templates/wave-tasks.md) 检查表的「需要人判断」段。

## 纪律

- 闸门红了，先查本表再改计划或改契约；**不许改脚本放宽检查**。
- 新增一条断言 = 多一条历史事故的护栏，必须在本表登记依据。
- 波次结束（T8）时 `plan.yaml` 随分支合回 main，成为「这一波按什么编制、按什么契约起的」的唯一记录。

## 收口时（`closeout` 子命令）· R0–R5

`check` 守的是「起跑前」；这一组守「收口那一刻」，跑在 T8 之前，红了不许归档。

```bash
python scripts/agent_team_plan.py closeout --plan docs/agent-team/plans/<change>.yaml
# 已归档的波可以补跑：--change <name> --base <合并前的 commit>
```

| 断言 | 管什么 | 依据 |
| --- | --- | --- |
| R0 | 规格目录存在（live `openspec/changes/<change>/` 或 `archive/YYYY-MM-DD-<change>/`） | 归档后目录改名，脚本两边都认 |
| R1 | 每个改动文件都落在某任务 inScope 内（`openspec/changes/`、`docs/cases/`、`docs/improvements/`、`docs/agent-team/plans/` 之下豁免） | 「没人认领的改动」是波次里最常见的静默越权 |
| R2 | implementation / repair 任务至少落地一个自家 inScope 文件 | 有任务、有 inScope、没落地 ≠ 半成品，是没做 |
| R3 | `verification.md` 存在（<80 字节给 warning） | T5 的产物缺失等于验收没发生 |
| R4 | `review.md` 存在，A1–A6 / B1–B9 / D1–D3 共 18 行齐全 | 清单存在但没人打开 = 没有清单 |
| R5 | `stage: pre` 时不许改 `openspec/specs/` | 合并主规格是 `openspec archive` 的动作，不属于任何成员 |

## 另一组闸门：知识来源

```bash
python scripts/check_knowledge_source.py     # 无来源知识 = 0；K2 自查 + reviewer B9 + T8 收口共用
```

| 断言 | 管什么 | 依据 |
| --- | --- | --- |
| 来源 | `confidence: 确定` 的条目必须有非空 `source` | 知识不可发明；无来源的「确定」是把假设洗成事实 |
| 必填 | `source` / `confidence` / `owner` / `strength` / `frequency` / `lifecycle` 齐全 | schema 缺字段时 loader 会静默取默认值，口径失效而产物正常 |

**未安装的脚本**（`verify_traces.py`、`check_knowledge_schema.py`、`scan_prohibitions.py`）：它们依赖本仓库不存在的产物（`artifacts/` run 目录、idata `query_id`、知识 loader）。**不许把它们写进闸门或 verify**；将来真有了对应产物再装，装了才加门槛。

两条纪律与上面相同：**红了先查依据，不许改脚本放宽**。它们的共同失效形态是**假绿**（在跑、永远不报错），所以每一条都必须经得起一次变异注入。
