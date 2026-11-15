# review-checklist（评审机械清单）

> **用法**：T6 评审时打开本文件逐条走，把每行结论写进 `review.md` 的「CR 清单逐项结论」表
> （结构见 §E）——**发现/未发现都要写，不留白**。
> 这里放**判定细节**（要查什么、查到什么算什么）；`roles/reviewer.md` 只留用法、产出格式与
> 三条反直觉陷阱。
> **动本文件时**：§A 固定 6 行、§B 固定 9 行，正文任何提到数量的地方（含 `roles/reviewer.md`）
> 必须与实际行数一致；加一条就要同步改这些引用处，否则清单与结论表对不上号。

## A. 通用 6 条（`ponytail-review` 维度，按优先级）

| # | 维度 | 要判什么 |
| --- | --- | --- |
| A1 | correct | bug、崩溃、漏边界（空/零/末项/舍入/时区/停牌日）、调用方被破坏、共享函数没修、只在单个调用方打补丁 |
| A2 | safe | 注入、弱随机、密钥泄露（token 进日志/进报告）、缺输入校验、数据丢失（吞错误、写库顺序错、无事务） |
| A3 | load | check-then-write 竞态、每进程重复工作、只增不减的内存/列表、N+1、O(n²)、该共享的每进程状态 |
| A4 | tested | 风险新逻辑（分支/解析/金额/安全/写库/bug 修复）有没有「坏了会红」的测试；新增测试是不是从实现抄出来的 |
| A5 | fast | 大减速是问题；热循环里的小重复是建议（本仓库跑全量 pytest 是日常动作，别让它从秒级掉到分钟级） |
| A6 | lean | 死代码/未用选项/投机功能；该复用已有 helper（要指路径，如 `src/common/`）；stdlib/`pandas`/`numpy` 已做的别再加依赖；yagni；必须一起改的近重复该合并；职责混杂的函数该拆 |

## B. Agent 特有 9 项（核对 architect A–H 有没有被代码兑现）

| # | 维度 | 要判什么 |
| --- | --- | --- |
| B1 | LLM vs 确定性代码 | 取数/校验/比对/聚合用确定性代码（`src/data_provider/`、`src/service/`），没偷用 LLM；LLM 只做叙述/对抗，数值一律来自确定性模块（MRD §8.2 的「数值可追溯」） |
| B2 | 可信保证落地 | 防幻觉（数值不覆盖）、证据分桶、明暗账是真实现，不是只在 `design.md` 里声明 |
| B3 | 上下文管理 | 数据只放路径/索引，没把 DataFrame / 全量 K 线 / 全量报告塞进 prompt；长列表先聚合再进 prompt |
| B4 | 成本 | 无谓 LLM 调用 / token 浪费（同一标的重复 narrate、prompt 里塞无关上下文） |
| B5 | 确定性 | 需确定性的输出（`combined_signal`、checksum、报告里的数字与排序）真确定性；禁止用 LLM 生成阈值/排序/口径 |
| B6 | 注入面 | LLM 输出流入工具调用 / CLI 参数 / 文件路径的注入风险；外部文本（新闻、公告、用户输入）进 prompt 前不当指令用 |
| B7 | 可重入 / 可拒绝 | checkpoint / sha256 / 拒绝判定真接上了，不是摆设；同步与写库可重跑且幂等（不重复插入、不覆盖已确认数据） |
| B8 | 知识 / 能力抽象（去重） | ① 该进知识层的口径/阈值/规则有没有被硬编码重复——diff 新增字面量全仓 grep，命中 ≥2 处即记；② 该共享的能力（校验/比对/格式化）有没有被多方重复实现（对照 `src/common/` 现有 helper） |
| B9 | 知识 schema 一致性 | **先跑 `python scripts/check_knowledge_source.py`**（无来源知识=0；来源字段/形状 ↔ `config/knowledge/` 的 yaml ↔ loader 是否真读）。脚本报 error → `knowledge-abstraction`（值不一致 `high`，形状不一致 `medium`）；脚本的 warning 逐条判「真不一致 / 设计未收录」，判「真不一致」的同样记 finding。脚本之外还要看它看不到的：嵌套结构（`lifecycle`）与时间窗语义 |

## C. 分流：先定 type，再定 severity，最后查 verdict

**判定顺序固定，不许跳步**：

1. 先定 `type`——它回答「这条 finding 该谁修」，不是严重度。合法值只有三个：
   `bug`（代码质量问题）/ `knowledge-abstraction`（知识内容该抽象 → T7 知识需求）/
   `capability-abstraction`（能力该抽象 → T7 能力改进点）。
   `correct` / `safe` / `lean` / `dedup` 是**审查维度**不是 type，必须映射到上面三个之一。
2. 再定 `severity`（`blocker` / `high` / `medium` / `low`）。
3. 最后查下表拿 `verdict` 与去向，**不得凭印象改写「这个 severity 应该给什么 verdict」**。

| 情况 | type | severity | verdict | 去向 |
| --- | --- | --- | --- | --- |
| Must fix（bug / 安全 / 数据丢失 / 扛不住负载） | `bug` | `blocker` / `high` | `needs_revision` | 框架 repair → engineer 本波修 |
| Should fix（无测试的风险代码 / 真慢 / 重复 / 职责混杂 / 该死代码） | `bug` | `medium` | `pass` | T7 改进点（下波） |
| Nice to have（小提速 / 更短写法） | `bug` | `low` | `pass` | T7 改进点 |
| 同一知识硬编码多处、值一致 | `knowledge-abstraction` | `medium` | `pass` | T7 → PM 转知识需求 |
| 同一知识硬编码多处、**值不一致**（代码里两份实现冲突） | `knowledge-abstraction` | `blocker` | `needs_revision` | 本波 repair（requiredFix = 统一到知识层，两处引用同一条） |
| 同一知识**在知识 yaml 里**值冲突（或 yaml 与代码口径不一致） | `knowledge-abstraction` | `high` | **`pass`** | captain 立即建 K2 整改任务，**同波闭环** |
| 同一能力被多方重复实现 | `capability-abstraction` | `medium` | `pass` | T7 → PM 转「抽象共享能力」 |

两条容易判错的：

- **「重复异值」不是不够 DRY**，是两份口径已冲突、系统会产出不一致结果——数据正确性风险，必须本波拦。
- **知识 yaml 里值冲突为什么是 `pass` 而不是 `needs_revision`**：判 `needs_revision` 会让框架自动生成
  engineer 的**代码** repair，而问题在 `config/knowledge/` 的 yaml 里——修错对象，还占掉一次 repair 轮次。
  知识问题只能由 K2 改，故必须 `pass` + 同波建 K2 任务。

**收紧规则**：只有 `blocker` / `high` 触发 `needs_revision`；`medium` / `low` 一律 `pass`。
唯一例外：命中 proposal 的「成功标准/失败标准」明确要求（即「不达标 = 本波失败」）可升为 `high`。

## D. 越权 / 范围检查（3 条，结论也要写进 review.md）

| # | 检查 | 判据 |
| --- | --- | --- |
| D1 | `openspec/specs/` 没被手改 | `git diff --name-only main...feature/<change> -- openspec/specs/` 为空 |
| D2 | `test/` 与 `test/qa/` 分离 | engineer 不碰 `test/qa/`，QA 不碰 `test/`（逐 commit 看作者与路径：`git log --format='%h %an' main..feature/<change>` + `git show --name-only <sha>`） |
| D3 | 评审只读产物 | 自己没改被评审产物（`src/`、`test/`、`test/qa/`、`design.md`、`openspec/specs/`、`config/knowledge/`） |

## E. `review.md` 必含结构

```md
## CR 清单逐项结论（无留白）
### 通用 6 条（A1–A6）
| # | 维度 | 结论 |
（6 行，每行给「发现 X（finding id）」或「未发现 + 依据」）
### Agent 特有 9 项（B1–B9）
| # | 维度 | 结论 |
（9 行，同上）
## 越权 / 范围检查
（D1–D3 各一行，带命令与输出）
## verdict 的两项开放条件
（① tasks.md 是否全完成，未完成的逐条列；② 声称行为是否在生产路径可达）
## Findings
（逐条：id / type / severity / problem 具体 case / requiredFix / file:line）
```

「未发现」也要给依据（看了什么、为什么判定没有），只写「✅」不算结论——留白等同于没查。
收口闸门（`python scripts/agent_team_plan.py closeout`）按 A1–A6 / B1–B9 / D1–D3 共 18 个标记核对
`review.md`：表格行首必须带编号，缺标记等同于没写。
