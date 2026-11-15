# docs/cases — 现实锚点（case 台账）

> **作用**：这里是整条流水线的**现实锚点**——业务里真实发生过的分析实例，用来挡住"agent 自嗨"：
> 没有 case（没有 ground-truth）的波次不许起波。
>
> **起波硬前置（机检 A1）**：`python scripts/agent_team_plan.py check` 的 A1 项会查
> `docs/cases/<case>/annotations.md` 是否存在、是否带 `采纳 / 存疑 / 不采纳` 的 ground-truth 标注。
> 缺了就不许起波，不许用"先开工后补 case"绕过去。

## 目录结构

```text
docs/cases/
├── README.md                 # 本文件：约定与所有权
├── _template-traces.yaml     # traces.yaml 模板（复制到 <case-id>/traces.yaml）
└── <case-id>/                # 一个真实 case 一个目录，kebab-case，与 change 名区分
    ├── annotations.md        # 标注区：PM 主笔（K1 只填「用到的知识」列与「知识差距」段）
    └── traces.yaml           # 溯源区：QA 唯一写者，append-only
```

## 两个文件的分工（不许混写）

| 文件 | 谁写 | 写什么 | 禁止 |
| --- | --- | --- | --- |
| `annotations.md` | `product-manager` 主笔；`knowledge-architect` 只填「用到的知识」列与「知识差距」段 | 原始业务问题 / 背景 / 逐环事实（提问 / 取数 / 计算 / 结论 / 呈现）/ 结论编号（`C1`、`C2`…）/ ground-truth / 功能差距 / 改进点 / 「距端到端复现还差什么」 | 抄 trace 数字、verdict；手写「复现进度」表；替业务方写 ground-truth |
| `traces.yaml` | `qa`（K3 与 T5）唯一写者，**只 append** | 一条记录 = 一次"验了哪条结论的哪一层、结论是什么"：`id / date / kind / conclusion / layer / verdict / run_id / evidence / note`（**9 字段**，口径见 `_template-traces.yaml`） | 改历史条目、删条目、写散文；凭记忆重写数字/verdict；`run_id` 指向不存在的文件 |

**ground-truth 只能由业务方标注**（采纳 / 存疑 / 不采纳）：PM 负责把事实问全、把问题问清，
**不替判对错**；标不出来就写 `partial` 并说明缺什么。

**没有 case 不许起波**：`<case>` 必须是 `docs/cases/` 下的真实目录，且 `annotations.md` 里
有 ground-truth 标注。无 ground-truth 的案例只能当"方法参考"，不能当 case 回归的验证标准。

## annotations.md 的必含段

1. 原始业务问题（原始话术，不改写）+ 来源（谁、何时、什么业务）
2. 分析链逐环事实（环定义随 MRD 演进改；模板见 `docs/agent-team/templates/case-teardown.md`）
3. 结论 + 结论编号（`C1`…；与 `traces.yaml` 的 `conclusion` 对齐）
4. **ground-truth**（采纳 / 存疑 / 不采纳，业务方标注）
5. 功能差距（指回某一环）
6. 改进点（有证据、能切成独立 change 才进 `docs/improvements/IMPROVEMENTS.md`）
7. 「距端到端复现还差什么」（缺功能 / 缺知识 / 缺数据源，三选一标注）

## traces.yaml 的字段与纪律

字段定义（含取值域）的**唯一真源**是 `_template-traces.yaml` 的注释；本文件只列字段名与纪律，不重写定义。
一条记录固定 **9 个字段**，顺序固定：`id / date / kind / conclusion / layer / verdict / run_id / evidence / note`。

核心纪律三条：

1. **append-only**：只追加，不改不删；结论变了就追加一条新记录，不覆盖旧的。
2. **能引用的一律不转述**：`evidence` 写「命令 + 退出码 + 关键输出」或「`文件:行` / 测试节点 id」，
   数字与 verdict 从实际输出复制，不凭记忆重写、不从旧记录复制。`note` 只做一句话导读，不替代 `evidence`。
3. **`run_id` 与 `evidence` 分工**（两者不可互相替代）：
   - `run_id` = **取证唯一标识**，指向仓库内**真实存在**的证据文件（如
     `openspec/changes/<change>/verification.md`、`.../knowledge-verification.md`、`.../review.md`），
     回答「去哪份文件复现」；不得指向不存在的文件，不得为凑命名新建空目录。
   - `evidence` = **可重放的证明**（命令 + 退出码 + 关键输出，或 `文件:行` / 测试节点 id），
     回答「凭什么这么判」；只写 `run_id` 不写 `evidence` 无法复核，只写 `evidence` 不写 `run_id`
     找不到取证报告。

> 本波（`add-allocation-executor`）起 `traces.yaml` 由 8 字段升为 **9 字段**（新增 `run_id`）：此前
> 字段口径与实例记录不一致（QA 按任务契约增列 `run_id`，模板未同步），现以本模板为唯一真源统一。
> 历史文件的记录**不改不删**；若某文件头部注释仍写旧字段数，以本模板/README 为准，记录内容不受影响。
>
> 「复现进度」表**不手写**：它是 `traces.yaml` 按 `conclusion × layer` 取最新 `verdict` 的派生视图。
> 手写一份就多一个真源，迟早对不上。
