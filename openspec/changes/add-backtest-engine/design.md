# Design: add-backtest-engine（回测模块技术方案）

> change：`add-backtest-engine`　分支：`feature/add-backtest-engine`　角色：architect（T2）
> 依赖：T1（`proposal.md` + `specs/backtest-engine/spec.md`）、K1（`knowledge-delta.md` + `config/knowledge/_design.md`）
> 本文件只做**设计**，不写代码、不归档、不改 `openspec/specs/`、不改 K1 的层语义。
> 需求锚点：飞书《投资Agent》r482 §回测模块（`docs/agent-team/inputs/feishu-invest-agent.md`）。MRD v1 仍是骨架，全文 0 处 MRD 锚点（见 proposal `## 假设/开放问题`）。

---

## 1. Context（解决什么 + 环境事实）

一期 P0 需要一台**可复算、可审计、可机检**的历史验证台子，把「预注册假设 → 数据对齐 → A 股撮合（含成本摩擦）→ 指标与归因 → 实验台账 → 三级门禁」串成一条确定性计算链，使「某条规则是否改变交易结果」这类经验命题可被证伪，并允许结论是「无信号」。动机是飞书 r482 §一 的三个数字：-15% 止损净亏 5.2 万、-25% 止损净赚 2.9 万、MA60 触发 80/81 次净亏 29.7 万——阈值动一格结论就翻，没有回测就只能拍脑袋。

**环境事实（`docs/agent-team/ENV.md`，本机实测，不猜）**：

| 项 | 事实 |
| --- | --- |
| Python / pytest / ruff | 3.14.3（命令名 `python`，无 `python3`）/ 9.0.3 / 0.15.17 |
| openspec | 必须写 `openspec.cmd`（PowerShell 执行策略禁 `.ps1`） |
| 数据依赖 | pandas 3.0.2 / numpy 2.4.2 / sqlalchemy 2.0.50 / tushare 1.4.29 / baostock 0.9.20 / akshare 1.18.54 / pyyaml 6.0.3 / jsonschema 4.26.0 |
| 图表 | matplotlib **未安装** → 本 change 不做图表产出（结论只出结构化 JSON + 台账） |
| 测试 | `test/`（engineer）+ `test/qa/`（QA，盲测）两套；addopts `--import-mode=importlib -m "not akshare_legacy"` |

**本设计的三个锚点**：

1. **确定性边界**：回测全链路是确定性计算，**本波没有任何 LLM 调用点**（proposal 已声明「不新增 LLM 环节」；`docs/dev/engineering-conventions.md:310`「收益、回撤、t 值、滑点、K 一律确定性代码计算，禁止 LLM 生成或修改」）。LLM 叙事是未来、且在 `service/report`，不在本波。
2. **MVP = 事件研究**：第一版不做全策略回测，只做「条件成立 → 之后 20/60 日相对基准超额分布」+ 一道已知答案校准（跌破 MA60 跑全 A 应显著跑输买入持有）。全策略回测（组合级逐日撮合 + 调仓规则）明确不在 MVP。
3. **数据前置缺口「显式报错、不静默降级」**：后复权价 / 成交额 / 涨跌停 / 停牌 / 退市 ST / 历史成分 / 表级 `ann_date` 是本机数据缺口（见 proposal `## Impact`、knowledge-delta §13）。设计上为这些缺口定义**适配器契约**，取不到就 `BacktestDataGapError` 并停止，绝不按 0 或按前复权继续。

---

## 2. Goals / Non-Goals

### Goals（本设计要交付的决策）

- G1：把 T1 的 19 条 Requirement 逐条落到 `src/service/backtest/` + `src/data_provider/backtest/` + `src/apps/` 的具体模块与接口（R→模块映射见 §4.2）。
- G2：在**函数签名层面**杜绝未来函数（`signal.py` 输入只含 t 日及之前切片；`data.py` 只产出 `trade_date <= as_of` 的时点视图）。
- G3：画出**依赖方向**（`apps → service/backtest → data_provider/backtest + dao → common`），不违反 `apps → controller → service → data_provider/dao → common`。
- G4：定义**接口与数据结构**（dataclass + 函数签名 + 台账字段 + 门禁状态），使 T3（实现）与 T4（QA）拿到的是同一份契约。
- G5：明确**消费 K1 知识分层**的方式（canon/rules/hypotheses 分别落哪），不改层语义，不拍板任何「待确认」数值。

### Non-Goals（本波明确不做）

- NG1：不写 `src/`、`test/` 任何代码（本波只有 `design.md` + `tasks.md`）。
- NG2：不产出**策略研究结论**（「-15% 止损是否有效」「跌破 MA60 应该卖」是台子之上的实验，另立 change）。
- NG3：不修数据前置缺口（不修 fetcher / 不新增数据表 / 不改 `openspec/specs/`）；只登记并定义「缺什么、缺了怎么办」。
- NG4：不做全策略回测（组合级逐日撮合 + 调仓规则）；MVP 只做事件研究（R17）。
- NG5：不做全市场荐股排序、交易员自动下单、Web UI、宏观/债券、报告渲染（proposal `## out of scope`）。
- NG6：不改 K1 的 `config/knowledge/_design.md` 分层语义，不填 K1 标「待确认」的数值，不写 `config/knowledge/<layer>/*.yaml`。

---

## 3. Agent 架构决策（A–H 清单，逐项作答）

> 角色契约要求 A–H 逐项给「决策 + 理由」或显式「本波不涉及 + 原因」，不留白。

### A. LLM / 确定性代码边界

**决策：回测全链路（数据对齐 / 分组 / 信号 / 撮合 / 指标 / 台账 / 校准 / 门禁）100% 确定性代码，本波零 LLM 调用点。**

逐环节作答：

| 环节 | 实现位置 | LLM vs 确定性 | 输入/输出契约（摘要） |
| --- | --- | --- | --- |
| 数据对齐 | `service/backtest/data.py` | 确定性 | 入：codes + 区间 + `AdjustMode`；出：`PriceBar[]` / `FinancialRecord[]`（已按口径对齐） |
| 分组/成分 | `service/backtest/universe.py` | 确定性 | 入：`as_of` + 特征源；出：`list[str]` 成分 / `GroupAssignment[]` |
| 信号 | `service/backtest/signal.py` | 确定性**纯函数** | 入：`PointInTimeSnapshot`（t 日及之前）；出：`EventSignal` |
| 撮合 | `service/backtest/broker.py` | 确定性状态机 | 入：`Order[]` + `PriceBar[]` + `BacktestConfig`；出：`Fill[]`（含成本分项与顺延/跳过） |
| 指标/归因/统计 | `service/backtest/metrics.py` | 确定性 | 入：`Fill[]`/事件集 + 基准；出：`EventStudyResult` / `AttributionResult` / `StabilityResult` |
| 台账 | `service/backtest/registry.py` | 确定性 | 入：`ExperimentRecord`；出：append-only 一行，无 UPDATE/DELETE |
| 校准门禁 | `service/backtest/calibration.py` | 确定性 | 入：预注册的 MA60 校准题；出：`CalibrationResult`（未过则 `exit != 0`） |
| 三级门禁 | `service/backtest/gates.py` | 确定性状态机 | 入：规则 + 实验 ID；出：唯一 `GateStage`，跳级即拒 |

**理由**：proposal 已声明「不新增 LLM 环节」；`docs/dev/engineering-conventions.md` §9.2 把「收益/回撤/t 值/滑点/K」列为「禁止 LLM 生成或修改」的确定性字段。任何把数字比对、字段校验、成交判定交给 LLM 的做法都会破坏「可复算、可审计」，直接违反 R2/R5/R7/R18。

**可复现/可稽核**：每个实验的结果由「预注册 commit + 参数快照 + 数据版本 + 复权口径元数据」唯一确定；同输入重跑得到同输出（纯函数 + 确定性撮合），台账行含预注册 commit 供审计（R2）。

### B. 编排 / 能力边界（多智能体拓扑）

**决策：本波没有多 agent 拓扑。回测是一条**确定性批处理 pipeline（DAG）**，由单个 CLI 进程串行驱动；全局状态只有一处（台账 + 门禁状态），由 `registry.py` 单点持有。**

```
preregister ─▶ load(data/universe) ─▶ signal ─▶ broker ─▶ metrics ─▶ registry ─▶ [calibration/gate] ─▶ 结果 JSON + 台账行
```

- **编排者**：`src/apps/backtest_cli.py`（CLI 装配），不承载业务逻辑（业务逻辑全在 `service/backtest/`）。
- **全局状态**：实验台账（`data/backtest/registry.ndjson`，append-only）+ 门禁状态（同一台账内按 `rule_id` 的记录或独立 `gate` 段）。只有 `registry.py` 有写权。
- **防无限 fork / 回环**：无 agent 分叉，故无 fork 爆炸；pipeline 是 DAG（无环）。唯一可能「循环」的是撮合顺延，用**最大顺延交易日上限**（见 §4.1 broker 契约）封死。
- **交接契约 = 产物文件，不是会话记忆**：步骤间交接结构化对象（dataclass）→ 最终落 `data/backtest/` 的 JSON + 台账 NDJSON；任何一步失败即整条终止并留痕（不吞错）。

**理由**：回测是「取数→算→落盘」的计算任务，不是需要 agent 协作的开放任务；引入多 agent 只会制造状态同步与汇合问题（这正是 A–H 反模式「各自为政、无全局状态」）。选单进程 pipeline，最省、最可审计。

### C. 知识层实现（消费 `config/knowledge/_design.md`，不改层语义）

**决策：本波不写代码，只定义回测代码如何消费 K1 的五层知识。消费方式如下（严格遵守 `_design.md` §4 落点矩阵，语义一字不改）：**

| 层（K1 定义） | 回测侧的落点（本设计定的**实现**） | 例子 |
| --- | --- | --- |
| `canon`（口径/参数，可调） | `config/app.yaml` 新增 `backtest:` 段；`BacktestConfig.from_config()` 读取，**缺键即拒绝** | 佣金率/最低额、印花税率、滑点分档、流动性上限档、样本切分年份、门禁阈值、切点档数 |
| `canon`（口径，不可调不变量） | `src/service/backtest/` 内**常量/断言，禁止配置化** | T+1、封板不可成交须顺延、停牌跳过、信号不得读 t 之后数据、后复权/分段复权、K 不报不下结论 |
| `rules`（方法与流程） | 代码 + 单测；其**参数**落 `canon`/`hypotheses` | block bootstrap、部分池化、三级门禁状态机、预注册校验、样本外烧毁流程 |
| `hypotheses`（未确认） | **不落代码行为**；实现只能预埋「开关 + 缺失即拒绝」，**禁止预埋默认数值** | Q4 费率、Q6 切点基准、KQ-2 块长、KQ-3 收缩强度、KQ-7 牛熊判定 |
| `facts`（现状事实） | 不落代码；只在知识层/评审报告里出现（解释「为什么现在做不到」） | 「kline 表无成交额」「三源均为前复权」 |
| `cases`（裁决与结论） | 不落代码、不落配置；只在 `cases` 层 + 台账引用（`registry_refs`） | 「前复权冲突裁决：回测另走口径通道」「校准通过/失败」 |

**检索方式**：回测运行时**不检索**知识库做实时推理；`canon` 参数在 K2 落盘后由 `config/app.yaml` 的 `backtest:` 段以配置形式承载（K2/T3 同步，非运行时召回）。代码注释**可以**引用知识 id（`# 见 CAN-COST-001`），但注释不是知识真源。**退役的技术面**：`hypotheses` 答复到达 → 迁 `canon` → 填入 `app.yaml`；过期未复核的口径（`review_at` 过）→ 按 `_design.md` §3.4 强制降 `假设` → 回测侧按「配置缺值即拒绝」停止。

**不改层语义**：本设计只定「每一层落到代码/配置的哪个位置」，不改变 K1 对五层语义、准入标准、升降级/退役规则的任何定义。冲突裁决（后复权 vs 前复权）按 K1 冲突1 执行：回测**另走口径通道**，`openspec/specs/` 一字不改。

### D. 可信保证（trace / 明暗账 / 重入 / 拒绝）

**决策：**

- **trace（决策链路落盘字段）**：台账每行 = `experiment_id / hypothesis_id / params / segment / K / verdict / metrics / prereg_commit / timestamps / data_version / adjust_mode`（完整字段见 §4.1 `ExperimentRecord`）。逐笔成交另落 `Fill` 明细（订单状态、顺延天数、成本四分量），可从台账行回溯到每一笔钱。
- **明账/暗账分离**：明账 = 台账 + 结果 JSON（给人看，`data/backtest/results/<experiment_id>.json`）；暗账 = **拒绝记录 + K 累计 + 样本外烧毁标记**（稽核用，不进入「结论」输出，但写入同一台账的 `audit` 字段或独立拒绝行）。「改假设必须新开实验」「样本外二次请求被拒」这些拒绝动作本身必须留痕（R2/R4 的 Scenario）。
- **数字与上游核对**：所有数值由确定性代码算（A 项）；`metrics.py` 输出带 `data_version / adjust_mode / snapshot_time` 元数据，可与数据快照核对（R9/R13）。
- **可重入（checkpoint）**：一次实验 = 一次进程运行，输入快照（预注册 commit + 参数 + 数据版本）可复现；失败不落结果行（R1「缺失预注册不产生结果记录」）。
- **可拒绝**：三处硬拒绝——① 预注册缺失/未提交（R1）；② 配置缺键（R7）；③ 数据缺口（R9/R12）。都是确定性代码抛出、`exit != 0`，不静默降级。

### E. LLM 非功能需求

**决策：本波不涉及（零 LLM 调用点）。** 但为未来叙事层预先划两条红线（不进本波实现）：

1. 未来若在 `service/report` 增加「回测结论叙事」，LLM 只收 `metrics.py`/`registry.py` 产出的**结构化 JSON**（事件数、超额、CI、K、判定），prompt 显式写「不得修改任何数值字段」（`docs/dev/engineering-conventions.md` §9.4）。
2. 数据**只放路径索引/摘要，不整表灌上下文**；调用次数与成本上限走 `llm:` 配置（`config/app.yaml:51-55` 已存在），模型分级为「大模型只叙事、纯脚本算数」。

### F. 数据与工具层

**决策：数据源适配 = 复用既有 `DataFetcherRouter`（`enabled` + `priority` 选源，`src/data_provider/router.py`）+ 新增 `data_provider/backtest/` 子域（回测专用口径），本地 K 线/财务经 `dao` 读取。优先级：本地缓存（dao）→ 适配器拉取 → 缺口显式报错。**

- **复用边界**（proposal `## Capabilities` 关系表 + knowledge-delta 冲突裁决）：
  - `data-fetcher-router`：K 线/财务取数仍走 Router 选源；但**回测不直接复用其返回的前复权 K 线**（冲突1），必须显式取后复权或做分段复权。
  - `tech-analyzer` / `tech-indicator-calculator`：MA60 口径（`df.close.rolling(60).mean()`，不足 60 日用 MA20 替代，`src/service/tech/calculator.py:172-178`）作为「跌破 MA60」条件的确定性定义复用；但 `signal.py` **不调用 `TechAnalyzer.analyze()`**（那会取实时数据、破坏时点边界），只在时点切片上按同一 SMA 定义自算（纯函数）。
  - `value-analyzer`：规模/价值/质量分组特征的**语义骨架**可复用（`src/service/value/router.py` 原型分类），但切点以分位为准（K1 KD-6-09），不照搬其估值输出。
  - `dao`：本地 `Kline`（`src/dao/models.py:134`）与 `StockSnapshot`（`src/dao/models.py:31`）作历史数据缓存读取。
- **新增适配器契约**（缺口处「显式报错」的落地，见 §4.1）：
  - `data_provider/backtest/adjust_price.py`（后复权 + 除权因子）
  - `data_provider/backtest/market_rules.py`（成交额 / 涨跌停价 / 停牌）
  - `data_provider/backtest/universe.py`（退市 / ST / 历史成分）
  - `data_provider/backtest/financial_timing.py`（`ann_date` 对齐）
- **算子输入输出契约**（metrics 层，见 §4.1）：事件研究 CAR、block bootstrap、归因、部分池化，全部纯函数。
- **数据安全**：回测只读历史数据；`tushare token` 在 `config/app.yaml`（已 `.gitignore`）。本波无 LLM 带出数据的风险（无 LLM）。

### G. 评测与自进化

**决策：本波的质量指标是「台子资格」，不是「策略效果」：**

- **R18 已知答案校准**：校准题（跌破 MA60 跑全 A 显著跑输买入持有）通过 = 台子可信；不通过 = 拒绝输出任何研究结论（`exit != 0`）。这是本波唯一的「上线资格」指标。
- **T4 的 5 条成功标准**（proposal `## 成功标准`）：校准可复现 / 台账可审计 / 样本外只烧一次可机检 / 成本手算复算 / 无未来函数可证伪，逐条用命令输出判定。
- **回流成判例**：校准结果、冲突裁决、被否方案 → 经 K2 写入 `cases` 层（带 `registry_refs`）；本波不写知识条目。
- **无 LLM → 无幻觉率指标**；「完成率/成本」等 LLM 指标本波不适用（E 项已标 N/A）。

### H. Agent 特有反模式（明确规避）

| 反模式 | 本波如何规避 |
| --- | --- |
| 无限循环 | pipeline 是 DAG，无环；撮合顺延设**最大顺延交易日上限**（配置，缺省留空待定，但必须存在，否则拒绝执行），超限即订单失败留痕 |
| fork 爆炸 | 无 agent 分叉（B 项单进程 pipeline） |
| 上下文膨胀 | 无 LLM，N/A；未来叙事层只收结构化 JSON 摘要（E 项） |
| LLM 幻觉进入数据流 | 无 LLM 计算（A 项）；数值一律确定性代码，`docs/dev/engineering-conventions.md:310` 硬约束 |
| prompt 与代码职责不清 | 无 prompt（本波全部代码）；知识口径在 `config/knowledge/` 真源，代码注释只引用知识 id |

**研究层风险**（过拟合、多重比较、未来函数、成本低估）不进 A–H 的「agent 拓扑」范畴，而是 R1–R19 的行为约束，已由 T1 写成 spec，本设计在 §4 落成机制、在 §7 风险表给「触发/缓解/回滚」。

---

## 4. Decisions（模块划分、接口与数据结构）

### 4.0 模块落位与依赖方向

```
src/service/backtest/
├── models.py        # 契约：dataclass + 枚举（六件共享，无 IO，无业务编排）
├── config.py        # BacktestConfig：读 config/app.yaml backtest: 段，缺键即拒绝
├── data.py          # 数据对齐：后复权 + 公告日对齐，消费 data_provider/backtest + dao
├── universe.py      # 历史成分 / 退市 ST / 分组切点（季度重算，不回改历史）
├── signal.py        # 纯函数信号：入 t 日及之前切片 → 出事件/动作
├── broker.py        # 撮合：成本、涨跌停顺延、T+1、停牌、流动性上限
├── metrics.py       # 收益/回撤/换手、事件研究、block bootstrap、多重比较、归因、部分池化、稳定性
├── registry.py      # 实验台账（append-only）+ 样本外烧毁 + K 累计 + 门禁状态（委托 gates）
├── calibration.py   # R18 已知答案校准门禁
└── gates.py         # R19 三级门禁状态机（薄状态机，读写委托 registry）

src/data_provider/backtest/
├── __init__.py
├── adjust_price.py      # 后复权价 + 除权因子（Q4/Q5 未答复前：仅契约，缺失抛 BacktestDataGapError）
├── market_rules.py      # 成交额 / 涨跌停价 / 停牌（同上）
├── universe.py          # 退市 / ST / 历史成分（同上）
└── financial_timing.py  # ann_date（公告日）对齐（同上）

src/apps/backtest_cli.py # CLI 装配（preregister / run / calibrate / ledger / gate）
```

**依赖方向**（不违反 `apps → controller → service → data_provider/dao → common`）：

```text
apps/backtest_cli ──▶ service/backtest ──▶ data_provider/backtest + dao ──▶ common
```

- `service/backtest/*` 只依赖 `data_provider/backtest`、`dao`、`common`、以及 `service/tech`/`service/value` 的**纯计算口径**（不依赖其实时取数 Facade）。
- `data_provider/backtest/*` 只依赖 `common`（不依赖 service）。
- 禁止 `dao`/`data_provider` 反向依赖 `service`（`docs/dev/engineering-conventions.md` §4.2）。

> 与飞书 §八 六件的关系：六件（data/universe/signal/broker/metrics/registry）是**业务编排骨架**，一字不差保留；`models.py`/`config.py` 是六件共享的**契约与配置装载**，`calibration.py`/`gates.py` 是两条**门禁**从 `registry.py` 拆出，避免把「实验台账 + 门禁状态机」塞进单文件（单一职责）。§八 是结构参考，最终模块划分以本 design 为准（proposal `## What Changes` 已声明）。

### 4.1 契约：dataclass 与函数签名

> 约定：数值字段一律 `Optional` 且**无默认业务值**；来自 `config/app.yaml backtest:` 段，缺键即拒绝。任何「待确认」数值不在此写死（见 §8 Open Questions）。

**枚举（`models.py`）**

```python
class AdjustMode(str, Enum):
    HFQ = "hfq"                  # 后复权
    SEGMENTED_HFQ = "segmented_hfq"  # 分段复权（分红日调整）
    # QFQ（前复权）不在枚举内：请求前复权直接抛错（R9 Scenario「前复权请求被拒」）

class OrderSide(str, Enum):
    BUY = "buy"; SELL = "sell"

class OrderStatus(str, Enum):
    FILLED = "filled"
    FAILED_LIMIT_SEAL = "failed_limit_seal"   # 封板失败→顺延
    SKIPPED_SUSPENDED = "skipped_suspended"   # 停牌跳过→顺延
    REJECTED_T1 = "rejected_t1"               # T+1 拒绝（当日买当日卖）
    CAPPED_LIQUIDITY = "capped_liquidity"     # 流动性上限截断

class Segment(str, Enum):
    TRAIN = "train"                 # 2015–2020
    VALIDATION = "validation"       # 2021–2023
    OUT_OF_SAMPLE = "out_of_sample" # 2024–2026

class Verdict(str, Enum):
    VALID = "valid"; INVALID = "invalid"; INCONCLUSIVE = "inconclusive"

class GateStage(str, Enum):
    BACKTEST_PENDING = "backtest_pending"   # 回测未通过
    BACKTEST_PASSED = "backtest_passed"
    SHADOW_RUNNING = "shadow_running"
    LIVE_SMALL = "live_small"
    REJECTED = "rejected"
```

**数据结构（`models.py`，公开契约）**

```python
@dataclass(frozen=True)
class PriceBar:
    code: str
    trade_date: str                 # YYYY-MM-DD
    open: float; high: float; low: float; close: float   # 后复权（分段复权在分红日调整后）
    amount: float | None            # 成交额（元）；缺 → 流动性上限/滑点不可算，报缺口
    limit_up_price: float | None    # 涨停价；缺 → 封板判定不可做，报缺口
    limit_down_price: float | None  # 跌停价
    suspended: bool                 # 停牌标记
    delisted: bool                  # 退市日之后为 True（退市日当天仍计入，R12）
    st: bool                        # 当时 ST 状态（按时点，不回填）

@dataclass(frozen=True)
class FinancialRecord:
    code: str
    report_period: str              # 报告期（如 '20231231'）
    ann_date: str | None            # 实际公告日；缺 → 保守回退并标注（R11）
    end_date: str | None
    # 财务字段按需（净资产/营收/ROE…）；本波只定义「对齐」语义，字段集由事件研究条件决定
    visible_from: str               # = max(ann_date, conservative_cutoff)，t 时刻可见的判定日

@dataclass(frozen=True)
class GroupAssignment:
    code: str
    as_of: str                      # 分组生效时点（季度末）
    tiers: dict[str, int]           # {market_cap_tier, dividend_tier, volatility_tier}（分位档）
    effective_range: tuple[str, str]  # 生效区间，重算不得回改历史（R15）

@dataclass(frozen=True)
class PointInTimeSnapshot:
    """signal 的输入：构造时即被 data.py 裁到 trade_date <= as_of，函数签名杜绝未来。"""
    as_of: str
    price: tuple[PriceBar, ...]     # 仅 trade_date <= as_of
    financials: tuple[FinancialRecord, ...]  # 仅 visible_from <= as_of
    def __post_init__(self):        # 防御：任何 trade_date/visible_from > as_of 抛 FutureDataError（R10）
        ...

@dataclass(frozen=True)
class EventSignal:
    condition_id: str               # 预注册里固定的条件标识（如 "ma60_breakdown"）
    event_date: str                 # t（条件成立日）
    # MVP 事件研究只输出「事件是否成立」；全策略回测再扩展 action/target_weight（不在 MVP）

@dataclass(frozen=True)
class Order:
    code: str
    signal_date: str                # t
    side: OrderSide
    requested_amount: float         # 拟下单金额（元）
    requested_qty: int | None       # 拟下单股数（可为 None，由 broker 按 t+1 价格 + 100 股取整）

@dataclass(frozen=True)
class CostBreakdown:
    commission: float               # 佣金（含最低额判定）
    stamp_tax: float                # 卖出印花税（仅卖出方向）
    slippage: float                 # 滑点（按成交额分档）
    transfer_fee: float             # 过户费（是否计入待 Q4）
    total: float

@dataclass(frozen=True)
class Fill:
    order: Order
    status: OrderStatus
    fill_date: str | None           # 实际成交日（≥ t+1）
    fill_price: float | None
    filled_amount: float | None
    cost: CostBreakdown
    delay_days: int                 # 顺延天数（封板/停牌）
    notes: tuple[str, ...]          # 「触及流动性上限」「连续封板 N 日」「触发最低佣金」等

@dataclass(frozen=True)
class ExperimentRecord:
    """台账行（R2）：append-only，写后不可改。"""
    experiment_id: str
    hypothesis_id: str
    params: dict                     # 参数快照（含 K 相关）
    segment: Segment
    K: int                          # 累计尝试次数（R5）
    verdict: Verdict
    metrics: dict                   # 结果指标（结构化 JSON 可序列化）
    prereg_commit: str              # 预注册 commit（R1/R2）
    data_version: str               # 数据快照版本（R9/R13）
    adjust_mode: AdjustMode
    timestamps: dict                # created_at / finished_at
    parent_experiment_id: str | None  # 改假设须新开实验并引用父实验（R2）
    burnt: bool = False             # 样本外已烧毁标记（R4，不可撤销）
    audit: tuple[str, ...] = ()     # 拒绝/跳过留痕（R4/R8/R19 的拒绝动作）

@dataclass(frozen=True)
class CalibrationResult:
    passed: bool
    direction: str                  # 「显著跑输」/「未复现」
    ci: tuple[float, float] | None
    K: int
    params: dict
    notes: tuple[str, ...]

@dataclass(frozen=True)
class GateRecord:
    rule_id: str
    stage: GateStage
    stage_timestamps: dict[str, str]  # 每级通过时间
    evidence_experiment_ids: dict[str, str]  # 每级依据的实验 ID（R19）
    direction_agree: bool | None
```

**函数签名（公开接口，T3 实现时不得擅自偏离；偏离须回本 design 修订）**

```python
# data.py
def load_price_series(codes, start, end, adjust: AdjustMode, *, loader) -> dict[str, tuple[PriceBar, ...]]:
    """adjust 只能 HFQ/SEGMENTED_HFQ；请求前复权抛 BacktestDataGapError（R9）。"""

def load_financials_point_in_time(codes, as_of, *, loader) -> dict[str, tuple[FinancialRecord, ...]]:
    """按 visible_from <= as_of 对齐（R11）；缺 ann_date 走保守回退并标注。"""

def build_point_in_time(codes, as_of, *, loader) -> PointInTimeSnapshot:
    """把价格 + 财务裁到 as_of，构造 signal 输入。"""

# universe.py
def build_universe(as_of, universe_spec, *, provider) -> tuple[str, ...]:
    """含退市（退市日前计入）、当时 ST、历史成分（R12）；名单不可得→报缺口。"""

def assign_groups(codes, as_of, features, *, cfg) -> dict[str, GroupAssignment]:
    """分位切点分组，季度重算，生效区间不回改历史（R15/R16）。"""

# signal.py —— 纯函数，禁止 IO，禁止读 as_of 之后数据
def evaluate_condition(snapshot: PointInTimeSnapshot, condition: ConditionSpec) -> EventSignal | None:
    """入 t 日及之前切片；越界在 PointInTimeSnapshot 构造/校验层抛 FutureDataError（R10）。"""

# broker.py —— 确定性状态机
def execute_orders(orders, prices, *, cfg) -> tuple[Fill, ...]:
    """t+1 成交、封板顺延、T+1 拒绝、停牌跳过、流动性上限截断、成本四分量（R7/R8）。"""

def next_tradable_day(date, *, calendar, prices) -> str:
    """顺延目标日 = 下一个可成交交易日；停牌/封板递归顺延，设最大顺延上限。"""

# metrics.py —— 纯函数（入 Fill/事件 + 基准，出结构化结果）
def compute_event_study(events, benchmark, *, cfg) -> EventStudyResult:
    """20/60 日相对基准超额分布：n/mean/median/std/CI/分年度/分档（R17）。"""

def block_bootstrap(excess, *, block_length, n_bootstrap, seed) -> tuple[tuple[float,float], int]:
    """有效样本（时间块）重采样，返回 CI 与有效样本量（R6）。"""

def multiple_testing_correction(p_values, K, method, *, cfg) -> tuple[float, ...]:
    """Bonferroni / Deflated Sharpe 择一（预注册固定），输出校正后判定（R5）。"""

def attribution(returns, factors, benchmark) -> AttributionResult:
    """beta/规模/价值/动量 四项暴露与贡献（R13）。"""

def partial_pooling(estimates, group_mean, *, shrink) -> tuple[float, ...]:
    """个股估计向组均值收缩，输出组内分位（R16）。"""

def stability(result, *, cfg) -> StabilityResult:
    """分年度 / 分市场状态 / 分市值组；仅一段显著→标注（R14）。"""

# registry.py —— append-only
class ExperimentRegistry:
    def append(self, record: ExperimentRecord) -> None: ...
    def get(self, experiment_id) -> ExperimentRecord: ...
    def assert_not_burnt(self, hypothesis_id, segment) -> None: ...   # R4：二次请求样本外抛错
    def mark_burnt(self, hypothesis_id, experiment_id) -> None: ...   # 不可撤销
    def cumulative_K(self, study_scope) -> int: ...                   # R5：K 累计

# calibration.py
def run_calibration(*, cfg, loader) -> CalibrationResult: ...          # R18 校准题
def assert_calibrated(registry) -> None: ...                           # 未过 → exit != 0，封锁研究输出

# gates.py —— 三级门禁状态机（R19）
class GateStateMachine:
    def current(self, rule_id) -> GateRecord: ...
    def transition(self, rule_id, to: GateStage, evidence) -> GateRecord:
        """只允许 上一级→下一级 的合法边；跳级抛错并留痕。"""
```

**台账存储机制（R2 append-only 的机械保证）**

- 预注册文件（git 跟踪，R1「写入版本库并生成 commit」）：`config/backtest/preregistrations/<hypothesis_id>.yaml`。
- 运行台账（append-only，不入 git）：`data/backtest/registry.ndjson`。**每行** = `ExperimentRecord` 的 JSON + `record_sha256`（该行内容哈希）。写入只允许 `append`（追加一字节不覆盖），**不提供 UPDATE/DELETE 接口**；读取时逐行校验哈希，发现被篡改即报「台账已损坏」拒绝审计结论（R2 Scenario「修改已写入的台账行被拒绝」）。
- 结果 JSON：`data/backtest/results/<experiment_id>.json`（明账）。

**撮合顺延与未来函数的具体机制（R8/R10 的防作弊）**

1. **T+1**：`Order.signal_date = t`，`broker` 只允许 `fill_date >= 下一交易日`；当日买入当日卖出 → `OrderStatus.REJECTED_T1`（R8）。
2. **封板**：以「日终封板且无成交（一字板）」判定不可成交（口径 A3，Q5 待 Owner 确认）；`fill_date` 顺延到下一可成交日，`delay_days` 累计，明细标注「连续封板 N 日」（R8）。
3. **停牌**：`PriceBar.suspended == True` → 跳过并顺延（R8）。
4. **未来函数**：`PointInTimeSnapshot` 由 `data.py` 构造时硬裁到 `as_of`，`__post_init__` 断言「无 `trade_date > as_of`、无 `visible_from > as_of`」；越界抛 `FutureDataError`，不静默截断（R10）。`signal.py` 不接收任何日期参数、不 import 任何 IO 层。

### 4.2 R → 落地模块/接口 映射（19 条全覆盖）

| Requirement | 落地模块 / 接口 | 关键机制 |
| --- | --- | --- |
| R1 预注册先于跑数 | `registry.py::load_preregistration` + `apps/backtest_cli.py::preregister` | 预注册文件入 git 并校验 commit；缺失/未提交 → 拒绝、无结果行 |
| R2 台账 append-only + K 不可改 | `registry.py::ExperimentRegistry.append` + NDJSON 哈希 | 只 append、无 UPDATE/DELETE；改假设 → 新实验 + `parent_experiment_id` |
| R3 三段切分 | `config.py::BacktestConfig.segments` + `Segment` 枚举 | 每段独立可用状态；跨段报告显式列出各段（不合并单一数字） |
| R4 样本外一次性烧毁 | `registry.py::assert_not_burnt / mark_burnt` | 首次确认后写 `burnt=True`（不可撤销）；二次请求抛错留痕 |
| R5 多重比较 + K | `metrics.py::multiple_testing_correction` + `registry.py::cumulative_K` | K 缺 → `Verdict.INCONCLUSIVE`；校正方法预注册固定 |
| R6 block bootstrap | `metrics.py::block_bootstrap` | 报告名义样本 + 有效样本（时间块）；禁 iid t 检验下结论 |
| R7 成本摩擦 + 流动性上限 | `broker.py::execute_orders` + `config.py`（费率/档位） | 佣金/印花税/滑点/过户费四分量；缺配置 → 拒绝执行；超限截断标注 |
| R8 A 股撮合约束 | `broker.py` 状态机 + `data.py`（涨跌停/停牌字段） | T+1 / 封板顺延 / 停牌跳过，逐笔留痕 |
| R9 后复权 | `data.py::load_price_series(adjust=HFQ/SEGMENTED_HFQ)` | 前复权请求抛错；结果带 `adjust_mode + data_version + snapshot_time` |
| R10 信号纯函数 + t→t+1 | `signal.py::evaluate_condition` + `models.PointInTimeSnapshot` | 入参被硬裁到 t；越界抛 `FutureDataError`；成交在 t+1 及之后 |
| R11 公告日对齐 | `data.py::load_financials_point_in_time` | `visible_from = max(ann_date, conservative_cutoff)`；回退标注 |
| R12 生存偏差 | `universe.py::build_universe` + `data_provider/backtest/universe.py` | 含退市（退市日前计入）/当时 ST/历史成分；名单缺 → 报缺口 |
| R13 基准 + 归因 | `metrics.py::attribution` + 基准对比 | 双基准（买入持有 + 市场组合）+ beta/规模/价值/动量 |
| R14 稳定性分档 | `metrics.py::stability` | 分年度/牛熊震荡/市值组；仅一段显著 → 「仅在 X 段有效」 |
| R15 标签准入 + 切点纪律 | `universe.py::assign_groups` + 准入校验 | 三条件准入、软标签拒绝、结果标签禁用、季度重算不回改 |
| R16 部分池化 | `metrics.py::partial_pooling` | 组内分位 + 收缩强度；拒绝绝对收益预测 |
| R17 事件研究 MVP | `signal.py`（事件条件）+ `metrics.py::compute_event_study` + pipeline | 20/60 日超额分布 + 分年度/分档；允许「无信号」 |
| R18 校准门禁 | `calibration.py::run_calibration / assert_calibrated` | 校准题显著跑输 → 可信；否则封锁全部研究输出 |
| R19 三级门禁 | `gates.py::GateStateMachine` | 回测→影子→实盘；跳级拒绝留痕；唯一状态可查询 |

---

## 5. Rejected Alternatives（被否方案 + 理由）

### 否-1：复用既有前复权 K 线接口，就地做收益计算

- **方案**：不新增复权通道，直接复用 `data_provider` 三个 fetcher 返回的**前复权**序列跑回测。
- **理由**：① 违反 R9（前复权会随新分红改写历史价、制造假信号，飞书 r482 §三·复权口径）；② 违反 K1 冲突1 的裁决（「回测另走口径通道，`openspec/specs/` 一字不改」）；③ 三源实现明写前复权（`tushare/fetcher.py:295 adj="qfq"`、`akshare/fetcher.py:109`、`baostock/fetcher.py:363 adjustflag="2"`），复用即把「现状」当「口径」。
- **结论**：否决。回测必须经 `data_provider/backtest/adjust_price.py` 显式取后复权/分段复权；取不到 `BacktestDataGapError`，不静默降级。

### 否-2：把「费率/阈值/块长/收缩强度」写死成代码默认值

- **方案**：为赶进度，在 `broker.py`/`metrics.py` 里给佣金率、印花税率、滑点分档、block 块长、部分池化收缩强度、门禁阈值预埋「合理默认值」。
- **理由**：① 违反 R7 Scenario「费率配置缺失时拒绝执行」；② 违反 K1 `_design.md` §4.1「禁止预埋默认数值」硬规则；③ 这些参数 Owner 未答复（Q4/Q6/Q7、KQ-2/KQ-3/KQ-5），写过期值比没写更危险（`_design.md` §4.2）。
- **结论**：否决。这些参数只落 `config/app.yaml backtest:` 段（`hypotheses` 类），缺键即 `MissingBacktestConfigError`；代码里只能有「开关 + 缺失即拒绝」，不能有默认业务值。

### 否-3：把三级门禁状态机塞进 `registry.py` 单文件

- **方案**：为贴合飞书 §八 的六件，把 R19 门禁状态机也写进 `registry.py`。
- **理由**：① `registry.py` 的职责是「实验台账 append-only」，门禁是「规则生命周期状态机」，两者键不同（experiment_id vs rule_id）、写入语义不同（append-only vs 状态迁移）；混在一起会让「台账不可改」与「门禁可迁移」互相污染，评审无法判定某处是追加还是改状态；② 单文件承担两套不变量，T4 负向用例（「台账行改不了」vs「门禁可升级」）边界难写清。
- **结论**：否决。拆 `gates.py`（薄状态机，读写委托 `registry.py` 持久化），R19 仍完整落地。

### 否-4：让 signal 函数自行「只看 t 之前」而不做结构性约束

- **方案**：signal 函数内部约定「自己不看未来数据」，靠实现自觉。
- **理由**：① 无法在验证阶段**证伪**（R10 Scenario「越界访问抛错」需要结构性机制）；② 未来函数是回测头号杀手（飞书 §二·#5），靠自觉等于没有防线；③ 违反「函数签名层面杜绝未来函数」的架构硬约束。
- **结论**：否决。`PointInTimeSnapshot` 由 `data.py` 硬裁 + `__post_init__` 断言，`signal.py` 不接日期、不 import IO，越界在构造/校验层抛 `FutureDataError`。

---

## 6. 影响面（文件清单，禁止「相关模块」）

> 本波只写 `design.md` + `tasks.md`；下列为 **T3 实现波将要新增/修改**的文件，供影响评估与 T4 测试设计使用。

### 6.1 新增：`src/service/backtest/`（业务编排，10 文件）

- `src/service/backtest/models.py`
- `src/service/backtest/config.py`
- `src/service/backtest/data.py`
- `src/service/backtest/universe.py`
- `src/service/backtest/signal.py`
- `src/service/backtest/broker.py`
- `src/service/backtest/metrics.py`
- `src/service/backtest/registry.py`
- `src/service/backtest/calibration.py`
- `src/service/backtest/gates.py`

### 6.2 新增：`src/data_provider/backtest/`（外部数据适配，4 文件）

- `src/data_provider/backtest/__init__.py`
- `src/data_provider/backtest/adjust_price.py`
- `src/data_provider/backtest/market_rules.py`
- `src/data_provider/backtest/universe.py`
- `src/data_provider/backtest/financial_timing.py`

### 6.3 新增：CLI 入口

- `src/apps/backtest_cli.py`（子命令：`preregister` / `run` / `calibrate` / `ledger` / `gate`）
- `pyproject.toml`（`[project.scripts]` 注册 `backtest` 入口，或并入既有 CLI 子命令）

### 6.4 配置（T3 落，本波只登记不改）

- `config/app.yaml`：新增 `backtest:` 段（键形态见 K1 §12.1，**不填数值**）
- `config/backtest/preregistrations/<hypothesis_id>.yaml`（预注册文件，git 跟踪）

### 6.5 运行产物（gitignore，不提交）

- `data/backtest/registry.ndjson`（台账，append-only）
- `data/backtest/results/<experiment_id>.json`（明账结果）

### 6.6 测试：`test/`（engineer，TDD 单测）

- `test/service/backtest/test_data.py`
- `test/service/backtest/test_universe.py`
- `test/service/backtest/test_signal.py`
- `test/service/backtest/test_broker.py`
- `test/service/backtest/test_metrics.py`
- `test/service/backtest/test_registry.py`
- `test/service/backtest/test_calibration.py`
- `test/service/backtest/test_gates.py`
- `test/data_provider/backtest/test_adjust_price.py`
- `test/data_provider/backtest/test_financial_timing.py`
- `test/apps/test_backtest_cli.py`

### 6.7 测试：`test/qa/`（QA，盲测，负向/边界/对抗）

- `test/qa/backtest/test_no_future_function.py`（R10 负向：越界抛错）
- `test/qa/backtest/test_known_answer_calibration.py`（R18：校准门禁）
- `test/qa/backtest/test_out_of_sample_burn.py`（R4：二次请求拒绝 + 留痕）
- `test/qa/backtest/test_cost_hand_calc.py`（R7：成本四分量黄金样例手算复算）
- `test/qa/backtest/test_seal_rollover.py`（R8：一字涨停/跌停顺延、停牌跳过、T+1 拒绝）
- `test/qa/backtest/test_survivorship_bias.py`（R12：退市/ST/历史成分 + 缺口报错）
- `test/qa/backtest/test_multi_comparison.py`（R5：K 缺失不可判定、K 增大判定翻转）
- `test/qa/backtest/test_financial_timing.py`（R11：公告日 vs 报告期 + 回退标注）

### 6.8 文档（后续任务执行，本波不改）

- `docs/dev/engineering-conventions.md` §3.1/§3.2（新增 `service/backtest/`、`data_provider/backtest/` 子域，属架构变更，T7 或 T3 同步）
- `docs/design/references/README.md`（索引表补行，T7）

---

## 7. Risks / Trade-offs（风险表：Agent 风险优先）

| # | 风险 | 触发条件 | 缓解 | 回滚 |
| --- | --- | --- | --- | --- |
| 1 | **过拟合**（规则在训练段调参调到显著） | 训练段反复调参（R3 允许）却不报告 K | R5 强制 K 累计 + 校正；R4 样本外只烧一次；R14 稳定性分档「仅在 X 段有效」 | 关停该结论：K 缺失 → `INCONCLUSIVE`；仅一段显著 → 不标「有效」 |
| 2 | **多重比较灾难**（几百个组合里挑最好的三个） | 标签/切点在看结果后反复换 | R15 切点先定 + R5 校正 + KD-8-03「分组换档也计 K」 | 校正后不显著 → 如实标不显著，写入台账 |
| 3 | **未来函数**（信号/财务读到 t 之后） | 信号读 t+1 价；财务用报告期当公告日 | R10 `PointInTimeSnapshot` 硬裁 + 抛错；R11 公告日对齐 | 越界即抛 `FutureDataError` 并终止该次执行，台账记失败原因 |
| 4 | **成本低估**（漏算佣金/印花税/滑点） | 配置缺键按 0 继续；滑点未分档 | R7 缺配置拒绝执行；成本四分量黄金样例手算复算（T4） | 缺键 → `exit != 0`；手算不一致 → 台子判不可信 |
| 5 | **数据前置缺口静默降级**（前复权/无成交额/无退市名单） | 取不到数据却按近似继续 | R9/R12 显式报缺口并停止；`data_provider/backtest` 契约只抛 `BacktestDataGapError` | 缺口即拒绝执行，不产出结论 |
| 6 | **台账被篡改**（事后改 K / 改结果） | 有人改 NDJSON | append-only 无 UPDATE/DELETE + 逐行哈希校验 | 哈希不匹配 → 报「台账损坏」并拒绝审计结论 |
| 7 | **样本外烧毁语义被绕过**（换参数重跑） | 换参数/换实现/换数据版本请求样本外 | R4 `assert_not_burnt`；烧毁粒度 Q1 待 Owner 定 | 二次请求抛错留痕；例外须人工批准者字段（`_design.md` §4.2#5） |
| 8 | **校准题被「重跑到过」** | 结论不对就重跑校准 | R18 校准重跑触发条件（KQ-6 待定）+ 校准结果写台账 | 校准未过 → 封锁全部研究输出 |
| 9 | **MA60 口径污染校准题**（次新股用 MA20 替代） | 沿用 tech 口径「不足 60 日用 MA20 替代」 | KQ-1 待 Owner 定；未答复前该开关必须存在且不静默 | 按答复回填开关；未答复 → 校准题标注「口径未定」不判可信 |

**关键 trade-off**：为「可复算、可审计」牺牲便利——所有「待确认」参数一律缺省即拒绝，导致台子在 Owner 答复 Q4–Q8 前**无法跑出任何带成本的结论**。这是**有意为之**：宁可不跑，不可按拍脑袋的参数跑出假结论（`config/knowledge/_design.md` §4.1「禁止预埋默认数值」）。

---

## 8. Migration Plan（复用既有 kline/财务数据，无线上数据迁移）

本模块是**新增**能力，无线上数据、无存量迁移；但必须给出「复用既有 kline/财务数据」的落地路径：

1. **K 线**：`data.py` 优先经 `dao` 读本地 `Kline`（`src/dao/models.py:134`，OHLCV 五列）。该表**缺 `amount`、涨跌停价、停牌标记**，故只能作为价格序列的**前段**；后复权价与撮合所需字段经 `data_provider/backtest/adjust_price.py` / `market_rules.py` 补取，**补不齐即 `BacktestDataGapError`**（不把缺列当 0）。
2. **财务**：`data.py` 读 `StockSnapshot`（`src/dao/models.py:31`，键 `code,source,report_period`）。该表**无表级 `ann_date`**（公告日只在事件类表 `src/dao/models.py:251`），故财务对齐经 `data_provider/backtest/financial_timing.py` 补 `ann_date`；缺则走 R11 保守回退并标注（年报/一季报 4 月底、半年报 8 月底、三季报 10 月底）。
3. **交易日历**：复用 `src/common/trading_day.py::is_a_share_trading_day`，但其 V1 只有「工作日 + 可配置休市日」且 `config/app.yaml:47 holidays: []` 为空（KD-3-06）。设计上把休市表注入到 `broker.next_tradable_day`，空表时**明确降级为「周一至周五」并在结果元数据标注**（或按 Q5 答复补充权威休市源）；**不得**把空表当成「没有法定节假日」而静默忽略。
4. **无 Schema 迁移**：不新增数据库表、不改 `dao/models.py`（数据侧修复不属本 change）；缺口由适配器「拉取补列」承载，落盘仍只在 `data/backtest/`（JSON/NDJSON）。

---

## 9. Open Questions（消费 K1 待确认清单，不自行拍板数值）

> 本节**只消费** K1 `knowledge-delta.md` §12 与 T1 的 Q1–Q8，声明「未答复前设计如何不拍板」；**不填任何数值**。

### 9.1 T1 已提（Q1–Q8）→ 设计侧的「待开关」位置

| 问题 | 影响 R | 设计侧处理（不拍板） |
| --- | --- | --- |
| Q1 样本外烧毁粒度 | R4/R2/R19 | `assert_not_burnt` 的判定键（实验/假设/规则族）留空，`burn_scope` 为配置项；未答复前默认**按实验 ID** 独立额度（spec R4 Scenario「新实验拥有独立额度」），更高粒度合并须答复后加开关 |
| Q2 K 计数边界 | R5/R2 | `cumulative_K` 的 `k_components[]` 留空；未答复前只累计「规则/参数/切点/窗口」显式声明的分量，不擅自合并 |
| Q3 样本右边界/滚动 | R3/R4 | `BacktestConfig.segments` 的 `bounds[]` 边界（含首尾/自然日/交易日/roll_rule）留空；未答复前按 A2「右边界=数据截止日」执行并在结果元数据标注 |
| Q4 费率与滑点现值 | R7/R8 | `commission/stamp_tax/transfer_fee/slippage_tiers/liquidity_cap` 全部 `Optional`，缺键即 `MissingBacktestConfigError`（不按 0） |
| Q5 涨跌停判定与停牌源 | R8 | `limit_pct/seal_definition/suspend_source` 留空；未答复前按 A3「一字板（日终无成交）」判定，并在结果标注「判定口径未定」 |
| Q6 三硬标签切点基准 | R15/R14 | `cut_basis/tier_count/recompute_freq/min_group_size` 留空；未答复前分组不可运行（缺键拒绝），不默认全 A 截面 |
| Q7 三级门禁判据 | R19 | `backtest_pass/shadow/direction_agree/small_position` 留空；`GateStateMachine` 只校验「顺序不可跳级」，判据数值缺即不允许 transition |
| Q8 事件研究窗口 | R17/R5 | `windows[]` 默认仅 `[20, 60]`（spec R17 固定）；`custom_allowed` 留空，未答复前自定义窗口拒绝（防 K 漏记） |

### 9.2 K1 新增（KQ-1…KQ-7）→ 设计侧的「待开关」位置

| ID | 影响 R | 设计侧处理（不拍板） |
| --- | --- | --- |
| KQ-1 校准题次新股处理 | R18/R17 | `calibration.py` 预留「不足 60 日标的处置」开关（沿用 MA20 替代 / 整段剔除 / 单独标注），未答复前**不跑校准题下结论**（避免污染方向性结论） |
| KQ-2 块重采样口径 | R6/R5 | `block_bootstrap` 的 `block_length/n_bootstrap/聚类层级` 为参数，缺键即拒绝；只保留「必须块重采样、报告有效样本」这条已确定要求 |
| KQ-3 收缩强度 | R16 | `partial_pooling` 的 `shrink` 为参数，缺键即拒绝；不预埋固定/自动口径 |
| KQ-4 影子期计时 | R19 | `GateStateMachine` 的 `shadow.min_months/max_months/clock` 留空；未答复前不允许进入影子→实盘 transition |
| KQ-5 「显著」判据 | R18/R19 | 校准「显著跑输」与门禁「不劣于基准」共用同一判据参数（区间不含 0 / 单尾 / 校正后仍显著），未答复前缺键即拒绝，防止「校准过、门禁不过」自相矛盾 |
| KQ-6 校准重跑触发 | R18/R2 | `assert_calibrated` 的触发条件（首启/撮合变更/数据源变更/口径变更/定期）留空；未答复前只允许「首启」触发，其余触发需人工签署 |
| KQ-7 牛熊震荡判定 | R14 | `stability` 的「市场状态分档」参数留空；只保留「必须分三段报告」这条已确定要求，未答复前该维度输出「口径未定」不参与判定 |

**未答复时的统一纪律**：所有上述「待开关」= 缺键即 `MissingBacktestConfigError` / `exit != 0`，绝不填默认数值、绝不静默降级（`config/knowledge/_design.md` §4.1 + 本 design 否-2）。

---

## 10. 参考

调研索引唯一真源（T1 产出，进 git）：[`docs/design/references/backtest-engine-research.md`](../../../docs/design/references/backtest-engine-research.md)；change 内摘要见 [`references/research.md`](references/research.md)。关键决策处的引用：

- `REF-backtest-engine-01`（thesis-backtester）：时点硬过滤口径（`ann_date` / `trade_date <= cutoff`）→ 支撑 R10/R11 的 `visible_from` 设计（§4.1）。
- `REF-backtest-engine-02`（ai-hedge-fund）：事件研究骨架（AR→CAR→窗口统计）→ 支撑 R17 `compute_event_study`；其 iid bootstrap 不借鉴（改用 block bootstrap，R6）。
- `REF-backtest-engine-03`（TradingAgents-CN `scripts/`）：A 股规则**参数位**（T+1/涨跌停/100 股/佣金/最低额/印花税）→ 支撑 R7/R8 的字段形态；数值走 Q4/Q5 由 Owner 定。
- `REF-backtest-engine-04`（Vibe-Trading）：多重比较校正清单 → 支撑 R5 `multiple_testing_correction`。
