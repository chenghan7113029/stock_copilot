# Tasks: add-allocation-executor（T3 实现指引）

> 依据 `design.md`（T2）。本文件是 T3 工程师的可勾选拆解：每条能指到 design 决策、粒度一次可提交、带验证命令。
> 环境：`python`（**无 `python3`**）、`openspec.cmd`（**不是** `openspec`）、PyYAML 已装、不新增第三方依赖（见 `docs/agent-team/ENV.md`）。
> 顺序：模型/异常 → loader → executor 各纯函数 → compute_plan 编排 → CLI → 测试 → 收口。

## 0. 前置

- [ ] **T-0** 确认知识层已就绪：`config/knowledge/canon/allocation-executor.yaml` 含 `CAN-ALLOC-001…005`（K2 已落），代码注释可引用其 id，但**运行时只读 `config/ips.yaml`**，不读知识库（design C 节）。
  - 验证：`python scripts/check_knowledge_source.py` 退出码 0（本波 T3 不新增知识条目）。

## 1. 模型与异常

- [ ] **T-1** 新建 `src/service/allocation/__init__.py` 与 `src/service/allocation/models.py`：定义 `PlanInput` / `AllocationPlan` / `CategoryAllocation` / `RebalanceHint` / `CashHint` 等 dataclass，以及 `AllocationError` / `AllocationConfigError` / `AllocationStaleError`（继承 `common.exceptions.StockCopilotError`；语义见 design「异常模型」）。
  - 验证：`python -m compileall -q src/service/allocation` 退出码 0。

## 2. loader

- [ ] **T-2** 新建 `src/service/allocation/loader.py`：
  - `load_ips_policy()` 读 `config/ips.yaml`，缺 design「输入」表所列任一键/类型错 → `AllocationConfigError`；
  - `load_snapshot()` 读 `config/ips.local.yaml`，缺 `pool.total`/`allocation.current`/`holdings.total_market_value`/`holdings.as_of` → `AllocationConfigError`；**不返回** `deployment.gap_to_target`/`monthly_amount`（R1，结构隔离）。
  - 用 `yaml.safe_load`（禁 `yaml.load`）。
  - 验证：`python -m pytest -q test/service/allocation/test_executor.py -k loader`（先写 T-12 的 loader 用例，或同 commit 一起交）。

## 3. executor 各纯函数（`src/service/allocation/executor.py`）

- [ ] **T-3** `resolve_execution_month_day(as_of_calc) -> (execution_month, execution_day)`：实现「计算日当日或之后最近的当月最后一个周四」（design R2 决策；用 `calendar`/`date` 求「月最后一天向前回退到周四」）。不接行情、不做节假日顺延。
  - 验证：单测覆盖 `2026-11-15→(2026-11, 2026-11-26)`、`2026-12-01→(2026-12, 2026-12-31)`、计算日恰好是执行日当天。
- [ ] **T-4** `compute_gap(policy, snapshot) -> Decimal` 与 `compute_remaining_months(policy, execution_month) -> int`：`gap = Decimal(str(T_eq))×pool − Decimal(str(eq_mv))`；剩余月数 = `max(执行月, 首个定投月)` 到目标月含端点（design R3/金额公式）。缺 `holdings.total_market_value` → `AllocationConfigError`。
  - 验证：单测 `pool=1_000_000, eq_mv=250_000 → gap=100_000`；`2026-12 → remaining=24`（spec R3 Scenario）。
- [ ] **T-5** `round_yuan(x)` 与 `compute_monthly_amount(...)`：`round_yuan = quantize(Decimal("1"), ROUND_HALF_UP)`；按 design「判定顺序」状态机（期末/迁移月/顺延/负缺口/目标月补齐/常规均摊）。
  - 验证：单测 `round_yuan(100000/24)=4167`、`round_yuan(4158.5)=4159`（.5 向上）、目标月 `round_yuan(4159)=4159` 且剩余缺口 0、执行月晚于目标月 → 0、缺口负 → 0。
- [ ] **T-6** `decide_defer(policy, snapshot) -> DeferDecision`：`cur.equity > skip` → 顺延（0 + 理由）；`cur.equity > cap` 追加提示（不改判定、不产减仓金额）。严格比较 `>`。
  - 验证：单测 `0.36→顺延`、`0.42→顺延+超40%提示`、顺延后下一月 `remaining=23` 且无「待补额度」（spec R6 Scenario）。
- [ ] **T-7** `allocate_categories(...)`：迁移月 → 权益 0 + 固收迁移 `round_yuan(0.45×pool×0.30)`；定投月起 → 权益「宽基 ETF」、无代码；现金 0；迁移金额不依赖权益缺口（design R5 决策）。
  - 验证：单测 `2026-11, pool=1_000_000 → 固收迁移 135_000, 权益 0`；`2026-12 及之后无迁移`（spec R5 Scenario）。
- [ ] **T-8** `rebalance_hints(policy, snapshot)` 与 `cash_floor_hint(policy, snapshot)`：`|cur[b]−T_b|>0.05` → 提示；`cur.cash×pool < 0.20×pool` → 提示 + 补足 `round_yuan(0.20×pool − cash_mv)`，**不改当月权益买入额**（design R8/R9）。
  - 验证：单测 固收 `0.30 vs 0.45` → 偏离 −15pp 提示；带内无提示；`pool=1_000_000, cash_mv=150_000` → 补足 `50_000` 且权益买入额不变（spec R8/R9 Scenario）。
- [ ] **T-9** `assert_fresh(snapshot, as_of_calc)`：`(as_of_calc − holdings.as_of).days`；`> stale_days` → `AllocationStaleError`；`as_of` 缺失 → `AllocationConfigError`；`as_of` 晚于计算日 → `AllocationStaleError`；`== stale_days` 允许（design R7/金额公式）。
  - 验证：单测 过期 14 天 → 拒、恰好 7 天 → 允许、缺 `as_of` → 拒、未来快照 → 拒（spec R7 Scenario）。
- [ ] **T-10** `compute_plan(policy, snapshot, as_of_calc) -> AllocationPlan` 编排上述函数（按 design 判定顺序），以及 `render_plan(plan) -> str` / `render_plan_json(plan) -> dict`：输出含「执行月/执行日、缺口、剩余月数、当月金额、类别分配、顺延、再平衡提示、现金不足提示、时效、理由、回显（目标比例/期限/阈值/取整规则/`as_of`）」。理由由固定模板 + 回显值产生，零 LLM（design R10/A 节）。
  - 验证：单测 幂等（同输入两次逐字段一致）；`grep -rniE "openai|llm" src/service/allocation/` 无命中。

## 4. CLI（`src/apps/cli.py`）

- [ ] **T-11** 新增 `ips` 子命令 + `plan` 子子命令 + `--as-of`（字符串，`date.fromisoformat` 解析，坏格式 → stderr + exit 1）+ `--json`；`run_ips_plan(args) -> int` 映射退出码：`AllocationConfigError`→1、`AllocationStaleError`→2、其余 `StockCopilotError`/`ValueError`→1、成功→0（design CLI 契约）；`main()` 增加 `if args.command == "ips": return run_ips_plan(args)`。
  - 验证：`python -m pytest -q test/apps/test_cli_ips_plan.py`（先写 T-13 用例，或同 commit 交）。

## 5. 测试

- [ ] **T-12** 新建 `test/service/allocation/test_executor.py`：手算对照（design「手算对照示例」合成数）+ 幂等 + 边界（.5 进位/顺延/过期/恰好 7 天/现金不足/期末归零/缺键）。
  - 验证：`python -m pytest -q test/service/allocation/` 退出码 0。
- [ ] **T-13** 新建 `test/apps/test_cli_ips_plan.py`：退出码 0/1/2、stderr 文案（「数据过期」含 `as_of`/天数差/阈值）、`--json` 键齐全、`--as-of` 坏格式 → 1。
  - 验证：`python -m pytest -q test/apps/test_cli_ips_plan.py` 退出码 0。

## 6. 收口

- [ ] **T-14** 全量回归 + 静态检查 + openspec 校验，并勾选本文件全部 checkbox。
  - 验证（按序，均须退出码 0）：
    - `python -m pytest -q`
    - `python -m compileall -q src test`
    - `python -m ruff check .`（本 change 路径新增错误 = 0）
    - `openspec.cmd validate add-allocation-executor --strict`

> 失败红线（与 plan.yaml T3 失败定义一致）：把阈值当硬门禁 / 用 LLM 算数 / 留未实现假开关 / 改测试迁就实现 / 让 `deployment.gap_to_target`/`monthly_amount` 成为输入。
