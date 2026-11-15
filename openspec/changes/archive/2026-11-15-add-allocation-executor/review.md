# Review: add-allocation-executor（T6 白盒评审 + 准出）

> 角色：reviewer　change：`add-allocation-executor`　分支：`feature/add-allocation-executor`
> 被评审对象：T3 实现（commit `83449c0`，8 文件）+ T4 QA 用例（`9800070`）+ T5 验证报告（`d0e4a77`）。
> 评审方法：白盒通读 `src/service/allocation/{models,loader,executor}.py`、`src/apps/cli.py` 的 `ips plan` 分支与两套单测；逐条走 `docs/agent-team/templates/review-checklist.md` 的 A1–A6 / B1–B9 / D1–D3；去重 grep + `check_knowledge_source.py`。
> 环境证据：`git rev-parse HEAD = e0fca3546f743489238ab2b4c8e1cded284e9eac`（工作树干净，src 自 `83449c0` 后无改动）。

## verdict

**pass**

无 blocker / high；实现正确、安全、幂等、零 LLM、测试手算对照充分。仅 2 条 medium/low 回显/透明度缺口（F1/F2），按清单 §C 分流规则（medium/low 一律 pass）转 T7 改进，不阻塞归档。

## CR 清单逐项结论（无留白）

### 通用 6 条（A1–A6）

| # | 维度 | 结论 |
| --- | --- | --- |
| A1 | correct | 未发现算术/边界/状态机 bug。通读 executor/loader/models/cli 全文 + 46 例单测全绿。取整 `.5` 向上（`round_yuan` ROUND_HALF_UP，executor.py:149-151）、期末/负缺口归零、严格 `>` 比较（defer `0.35→不延` executor.py:157、rebalance `<=band` 带内 executor.py:280、stale `>7` 才拒 executor.py:340）。design 状态机未覆盖的「迁移月之前」由 `STATE_NOT_STARTED` 补齐（executor.py:194-202），方向正确（spec R5「首个定投月前 MUST NOT 出权益买入」）。调用方未被破坏：`main()` 新增独立 `ips` 分支（cli.py:2465-2466），与既有命令无交集。 |
| A2 | safe | 未发现。注入面：`yaml.safe_load`（loader.py:42，禁 `yaml.load`）；`--as-of` 经 `date.fromisoformat` 严格解析、坏日期 stderr+exit 1（cli.py:2055-2058）；无 eval/shell/网络/subprocess（`grep -rniE "openai\|llm\|requests\|http\|urllib\|socket\|subprocess" src/service/allocation/` 退出码 1）。密钥：工单含个人金额只打印 stdout，不落文件、不外发（design F 节）。数据丢失：纯只读，不写库、无事务/吞错。 |
| A3 | load | 未发现。单进程纯函数，无共享可变状态、无 check-then-write（只读不写）、无每进程重复工作、无内存累积。预期负载 = 单机个人脚本每次一条指令，O(1)。 |
| A4 | tested | 未发现。风险逻辑（金额/取整/顺延/过期/提示/缺键/幂等）均有「坏了会红」单测：test_executor.py 36 例 + test_cli_ips_plan.py 10 例；断言值均为手算数（4167/135000/50000/4159/4348），`make_policy`/`make_snapshot` 显式写数值、非从实现抄出；幂等有专门测试（test_plan_is_idempotent）。变异实验（T4 把 ROUND_HALF_UP→DOWN 仅 TC-R4-05 变红）证明断言非空转。 |
| A5 | fast | 未发现。纯算术 O(1)，rebalance 循环仅 3 桶，无 N+1 / O(n²) / 热循环重复。全量 pytest 1177 例秒级。 |
| A6 | lean | 未发现死代码/未用选项/投机功能。三异常均被 CLI 捕获使用（cli.py:2062-2070）；`PlanEcho` 字段均在 render/JSON 使用；`__init__.py` 单行包标记。复用 stdlib（decimal/calendar/argparse）+ PyYAML（已装），未新增依赖。F1/F2 属回显完整性（见 B2/Findings），非死代码。 |

### Agent 特有 9 项（B1–B9）

| # | 维度 | 结论 |
| --- | --- | --- |
| B1 | LLM vs 确定性代码 | 未发现。`src/service/allocation/` 全链路纯函数 + 固定模板文本，零 LLM 调用点；grep openai/llm/requests/http/urllib/socket/subprocess 退出码 1。数值全部由确定性代码产出（design A 决策兑现）。 |
| B2 | 可信保证落地 | 发现 **F1、F2**（均 medium/low）。可复算=回显+纯函数+单测已兑现：权益金额公式 `0.35 × 1,000,000 − 250,000 = 100,000` 已在「缺口:」行回显（executor.py:418-419，实测输出确认），剩余月数行含 `2026-12 → 2028-11`（:420-422）；可拒绝=缺键 exit 1 / 过期·未来 exit 2 已兑现。缺口：迁移金额（135,000）的 `trial_ratio` 未回显（F1），迁移基数/次数假设（Q2）未标「待确认」（F2）。 |
| B3 | 上下文管理 | 未发现（N/A：零 LLM，无 prompt/DataFrame/全量数据注入）。 |
| B4 | 成本 | 未发现（零 LLM 调用，token 成本 0）。 |
| B5 | 确定性 | 未发现。`compute_plan` 纯函数：不读时钟（`--as-of` 缺省 `date.today()` 在 CLI 层显式取值后作入参，cli.py:2055）、不读随机、不写状态；幂等单测逐字段一致（test_plan_is_idempotent）。 |
| B6 | 注入面 | 未发现。`yaml.safe_load` 禁任意对象；`date.fromisoformat` 严格解析；零 LLM 故无「外部文本进 prompt 当指令」；无工具调用/文件路径注入面。 |
| B7 | 可重入 / 可拒绝 | 未发现。幂等（纯函数）真实落地；拒绝判定真接上：`assert_fresh` 是 `compute_plan` 第一步（executor.py:356），缺键在 loader `_require` 拒绝（loader.py:54-61）；只读无写库，无重复插入/覆盖已确认数据问题。 |
| B8 | 知识 / 能力抽象（去重） | 未发现。diff 新增政策字面量全仓 grep：`0.35/0.45/0.20/0.30/0.05/0.40/24/7/2028` 在 `src/service/allocation/*.py` 源码 0 命中（唯一 `% 7` 是 weekday 算术 executor.py:102；`last_thursday` 单一常量 loader.py:36）。全部政策值从 `config/ips.yaml` 读，无硬编码多处。未与 `src/common/` 现有 helper 重复实现（loader/executor 为新域，无同源重复）。 |
| B9 | 知识 schema 一致性 | 未发现。`python scripts/check_knowledge_source.py` → 扫描 11 文件 / 31 条 / **0 error / 1 warning**（warning = `known_unknowns.yaml` 非条目容器，判「设计未收录」非真不一致），exit 0。运行时零读库（design C：canon 是治理索引非第二配置源），故无 yaml↔loader 读值不一致；canon CAN-ALLOC-005 已按 K3 F1 requiredFix 改写（statement 只留「比例=30%」、基数/次数指向 KU），代码按 `ips.yaml` 的 `trial_ratio` 取值，与 canon 一致。 |

## 越权 / 范围检查

| # | 检查 | 结论 |
| --- | --- | --- |
| D1 | `openspec/specs/` 没被手改 | 通过。`git diff --name-only main...feature/add-allocation-executor -- openspec/specs/` → 空输出。 |
| D2 | `test/` 与 `test/qa/` 分离 | 通过。全 branch 18 提交作者均为 `chenghan7113029`（单身份）。T3 `83449c0` 只碰 `src/`+`test/service/`+`test/apps/`（`git show --name-only` 核实，未碰 `test/qa/`）；T4 `9800070` 只碰 `test/qa/`。engineer 未碰 `test/qa/`，QA 未碰 `test/`。 |
| D3 | 评审只读产物 | 通过。本评审只新增 `review.md`；未改 `src/`、`test/`、`test/qa/`、`design.md`、`openspec/specs/`、`config/knowledge/`（`git status --porcelain` 评审前为空）。 |

## verdict 的两项开放条件

1. **tasks.md 是否全完成**：是。`openspec/changes/add-allocation-executor/tasks.md` 的 T-0…T-14 全部 `[x]`（15/15），无未勾选项。
2. **声称行为是否在生产路径可达**：是。`python -m apps.cli ips plan --as-of <date>` → `main()` `if args.command == "ips": return run_ips_plan(args)`（src/apps/cli.py:2465-2466）+ `if __name__ == "__main__": raise SystemExit(main())`（:2657-2658）；`build_parser()` 注册 `ips`→`plan`→`--as-of/--json`（:2319-2323）。

## Findings

### F1（medium · bug · 转 T7）

- **problem（具体 case）**：迁移月输出「固收迁移: 135,000 元」，但回显段（文本与 `--json` echo）不含 `trial_ratio`（试水比例 0.30），故 `135,000 = 0.45 × 1,000,000 × 0.30` 无法仅凭工单手算复核（缺 `0.30` 输入）。对照：权益金额的 `0.35 / 1,000,000 / 250,000 / 24` 全部已回显。实测：`ips plan --as-of 2026-11-15`（迁移月，合成 pool=1,000,000 / 固收目标 0.45 / trial 0.30）→ 输出「固收迁移: 135,000 元」，回显段只有「固收 45%」「池总额 1,000,000」，无「试水比例 30%」。
- **requiredFix（最小修复）**：在 `PlanEcho` 增加 `trial_ratio` 字段，并在 `render_plan` 回显段与 `render_plan_json` 的 `echo` 输出「试水比例 30%」（值取 `policy.trial_ratio`，不硬编码）。
- **file:line**：src/service/allocation/executor.py:255-264（迁移计算）、:380-404（PlanEcho 构造缺 trial_ratio）、:438-457（render_plan 回显段）、:501-531（render_plan_json echo）；src/service/allocation/models.py:133-157（PlanEcho 缺字段）。

### F2（low · bug · 转 T7）

- **problem（具体 case）**：design §C / Open Questions 承诺「未答复口径在输出显式标待确认」，实现只对取整（Q1）标了「Q1 待 Owner 确认」（executor.py:32 `ROUNDING_RULE`），迁移金额的「基数=目标固收额度、次数=一次性」（Q2/A3，KU-2026-11-alloc-migration-base-01）未在理由或回显中标记。实测迁移月理由为「迁移月（2026-11），只做固收迁移；定投自 2026-12 起」，无「待确认」字样；与取整行「…ROUND_HALF_UP；Q1 待 Owner 确认」不对称。
- **requiredFix（最小修复）**：在迁移理由（`STATE_MIGRATION` 文案）追加「迁移基数与次数按 A3 假设、待 Owner 确认（KU-2026-11-alloc-migration-base-01）」。
- **file:line**：src/service/allocation/executor.py:207-210。

## T5 findings 处置核对（不重复计 findings）

| T5 编号 | 处置 | 依据 |
| --- | --- | --- |
| F1（medium，R3-S1 公式回显缺失） | **已解决，不复现** | 实现已在「缺口:」行回显 `0.35 × 1,000,000 − 250,000 = 100,000`（executor.py:418-419），剩余月数行含 `2026-12 → 2028-11`（:420-422）；实测输出与单测 `test_regular_month_buys_gap_over_remaining_months` 均确认。 |
| F2（low，design 未冻结 `--json` 键名） | 仍成立，转 T7 | 属 design 文档完整性（非代码缺陷）；代码 `render_plan_json` 已有具体 schema，T4 test-design §1.2 已冻结机检契约。 |
| F3（low，traces 功能层未补录） | 已解决 | `e0fca35`（T5b）已 append C1–C5 功能层 traces。 |

## 验证命令（辅助，不替代读代码）

```text
$ openspec.cmd validate add-allocation-executor --strict
Change 'add-allocation-executor' is valid
[exit code: 0]

$ python scripts/check_knowledge_source.py
扫描 11 个文件，识别 31 个知识条目
结论: 0 error，1 warning —— 通过（无来源知识=0）。
[exit code: 0]

$ python -m pytest test/service/allocation/ test/apps/test_cli_ips_plan.py -q
46 passed in 0.95s
[exit code: 0]
```

评审中额外实测：合成 policy/snapshot 跑 `compute_plan` + `render_plan`（PYTHONPATH=src、PYTHONIOENCODING=utf-8），确认常规月输出含「缺口: 0.35 × 1,000,000 − 250,000 = 100,000」「当月权益买入额: 4,167 元」，迁移月输出含「固收迁移: 135,000 元」但回显缺「试水比例 30%」——构成 F1 的 case 依据。
