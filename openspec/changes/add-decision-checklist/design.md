## Context

`product-overview.md` §5.2 给出「Checklist 最低字段」清单：

- 长期价值理由（≥2 条，须引用价值面输出）
- 短期技术面配合情况
- 当前情绪所处位置及解读
- 明确止损点与止盈点
- 非「可得性单一原因」（系统校验）

§8.1 验收准则「缺字段或仅可得性原因时系统拒绝提交」明确要求这是**系统校验**而非仅靠用户自觉，且 §7 非目标未排除这类护栏。`product-overview.md` §10 的开放问题「Checklist 拦截 vs 仅警告」写明「默认 P0 为硬拦截」——本 change 直接采用该默认值，不重新讨论。

当前仓库没有「用户决策留痕」的任何数据模型，`docs/dev/engineering-conventions.md` §3.2 已预留 `service/guard/`（「决策护航：Checklist 等」）子域，本 change 是该子域的首次实现。

## Goals / Non-Goals

**Goals:**
- 提供 `ChecklistRecord` 数据模型，覆盖 MRD 最低字段清单
- 提供纯规则（零 LLM）校验逻辑，包含字段完整性、价值理由条数（≥2）、「非可得性单一原因」启发式判定
- 提供 CLI 交互式提交命令，校验失败时硬拦截（不视为合规提交），但仍留痕（写入 `passed=False` 的记录）供未来复盘
- 校验逻辑与数据模型独立于交互层，为未来 Web 表单直接复用

**Non-Goals:**
- 不依赖情绪面模块（`add-sentiment-module`），情绪位置字段 V1 为用户手动文本输入
- 不做「价值理由引用价值面输出」的程序化事实核对（只做关键词层面的启发式判断，见决策 2）
- 不做 Web 表单（等待 REST API 就绪）
- 不做复盘归因统计（PO-09，属于 Phase 4）
- 不修改任何既有 `service/value`、`service/tech`、`service/dual_track` 模块

## Decisions

### 决策 1：数据模型——`ChecklistRecord` 字段设计

**选择**：新增 `ChecklistRecord` ORM（`src/dao/models.py`），字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | Integer PK | 自增 |
| `code` | String(10) | 股票代码 |
| `action` | String(10) | `buy`/`sell` |
| `value_reasons_json` | Text | JSON 数组，价值理由列表（每条为字符串） |
| `tech_alignment` | Text | 短期技术面配合情况（自由文本） |
| `sentiment_position` | Text | 当前情绪位置及解读（自由文本，手动填写） |
| `stop_loss_price` | Float | 止损点 |
| `take_profit_price` | Float | 止盈点 |
| `passed` | Boolean | 系统校验是否通过 |
| `rejection_reasons_json` | Text | JSON 数组，校验失败时的具体原因（`passed=True` 时为空数组） |
| `created_at` | DateTime | 提交时间 |

**理由**：直接对应 MRD §5.2 最低字段清单，`value_reasons_json`/`rejection_reasons_json` 用 JSON 数组存储（复用现有 `historical_pe_json` 的 Text+JSON 序列化模式，不新增专门的多值字段表，保持 V1 简洁）。`passed`/`rejection_reasons_json` 是系统校验的产出，不是用户输入，用于满足「留痕」需求（决策 4）。

**备选方案**：为 `value_reasons` 单独建一张子表（一对多关系，每条理由一行）——拒绝，V1 理由条数少（通常 2-4 条），关系型子表增加查询复杂度但收益有限，JSON 数组已足够，且与仓库现有 `historical_pe_json` 的既定模式一致。

### 决策 2：「非可得性单一原因」的校验规则——启发式而非语义理解

**选择**：`ChecklistValidator` 对每条 `value_reasons` 条目做以下判定（纯代码，零 LLM）：

1. **条数门槛**：`len(value_reasons) < 2` → 直接拒绝，原因「价值理由不足 2 条」
2. **单条有效性判定**（逐条检查，判定该条是否为「有效价值理由」）：
   - 去除首尾空白后长度 `< 15` 字符 → 判定为「过短，疑似非实质性理由」
   - 命中 `_AVAILABILITY_KEYWORDS`（如「新闻」「消息」「听说」「传闻」「网上说」「群里」「大 V」「涨停」「抱团」）且**未命中** `_GROUNDED_KEYWORDS`（如「估值」「PE」「PB」「安全边际」「低估」「护城河」「现金流」「ROE」「基本面」「财报」「DCF」「分位」）→ 判定为「疑似可得性单一来源」
3. **整体判定**：统计「有效价值理由」条数（未被判定为过短或可得性单一来源的条目），若 `< 2` → 拒绝，原因「价值理由中有效条目不足 2 条（存在过短或疑似新闻/传闻式单一来源理由）」

**理由**：`agent-engineering-quality.md` 反复强调「能用代码判断的不给 LLM」；语义级别的「这条理由是不是认真的价值分析」判断本可以交给 LLM，但会引入不确定性与额外成本，且校验结果直接决定是否拦截用户提交，稳定性要求高于语义精细度。字数阈值 + 关键词表是最低成本、可单测、可预测的实现。

**已知局限（V1 明确接受）**：
- 字数阈值无法区分「言简意赅的专业理由」与「凑字数的空洞文本」（如「基本面很好估值合理」14 字会被判过短，但「我觉得这个便宜」9 字也会被判过短——两者都会被拦截，前者是误判）
- 关键词表是硬编码列表，用户用同义词/新造词表达可得性偏差时可能漏判（如「刷到一个视频说」未命中任何关键词）
- 不做「理由内容是否真的对应该股票价值面输出」的事实核对（如用户写「PE 很低」但实际 PE 并不低，规则不会发现）

**备选方案**：
- 调用 LLM 判断每条理由是否「实质性」——拒绝，校验结果直接影响是否拦截提交这个高风险决策点，`agent-engineering-quality.md` 明确「用 LLM 做参数校验」是反模式 #1，且 LLM 判断本身不稳定，两次相同输入可能给出不同拦截结果，与「审计」的确定性要求冲突
- 完全不做内容质量判断，只做条数校验（`len >= 2` 即通过）——拒绝，MRD 明确要求「非可得性单一原因」的系统校验，纯条数校验无法拦截「随便写两条水字数」的场景，等于变相放弃了这条验收准则

### 决策 3：交互形式——CLI 交互式命令，不做纯 API

**选择**：V1 提供 `python -m apps.cli checklist submit <code> [--action buy|sell]`，通过一系列 `input()` prompt 依次收集字段（价值理由多条输入直到用户输入空行结束、技术面配合、情绪位置、止损点、止盈点），采集完毕后本地跑校验并输出结果。

**理由**：当前产品完全是 CLI-first，`src/controller/` 尚无任何 REST API 实现；先做纯数据结构+API 而不提供任何可用交互入口，会导致本 change 交付后用户依然无法真正使用 Checklist（除非自己写脚本调用），与「先能用」的既定实施原则相悖。CLI 交互式命令是当前产品形态下成本最低的可用交互。

**备选方案**：
- 只提供数据结构 + `ChecklistValidator`，不做 CLI 命令，等 Web 表单——拒绝，会导致本 change 交付后功能不可用，验收准则「买入/卖出意图触发 Checklist」无法被用户实际触发
- 非交互式命令（一次性通过大量 flag 传入所有字段，如 `checklist submit 600519 --reason "..." --reason "..." --stop-loss 10.5`）——可行但拒绝作为 V1 首选，理由字段是自由文本且可能较长，命令行 flag 传多行/多条文本体验差于交互式 prompt；不排除未来补充非交互模式供脚本化场景使用（记录为 Open Question）

### 决策 4：硬拦截 + 留痕，而非硬拦截 + 不落库

**选择**：校验失败（`passed=False`）时：
- 不视为「合规提交」，CLI 输出明确的拒绝原因列表，且不会有任何后续动作把它当作已完成的 Checklist
- 但**仍然写入** `ChecklistRecord`（`passed=False`），不做静默丢弃

**理由**：`product-overview.md` §8.2「关键决策（Checklist 填写、用户拒绝红蓝哪方）可持久化备查」与 §5.2 表格中「假设首开仓」条目的复盘精神一致——用户「明知不合规仍强行提交」这件事本身是有价值的审计信号（未来 PO-09 复盘归因可以统计「用户提交被拒绝后是否仍然交易」）。硬拦截的「拦截」体现在**不认可其为合规状态**，不体现在「不留痕」。

**备选方案**：校验失败直接拒绝写库（`raise` 或直接 `return`，不调用 `ChecklistRepo.save()`）——拒绝，会丢失「用户尝试绕过 Checklist」这个对未来复盘（PO-09）有价值的信号，且与产品「审计镜」定位（§1 执行摘要）不符——审计镜的价值恰恰在于记录所有尝试，不只记录「乖乖听话」的记录。

### 决策 5：与情绪面模块解耦

**选择**：`sentiment_position` 字段为用户手动输入的自由文本（如「短期换手率偏高，个人感觉偏热但未到极端」），V1 不校验其内容是否与任何情绪指标一致，也不依赖 `add-sentiment-module` 是否存在。

**理由**：`add-sentiment-module`（对应 PO-06）状态为「待建」且优先级 P1，低于本 change（PO-04，P0）；若强制依赖会阻塞本 change 交付。MRD §5.2 表格本身也只要求「当前情绪所处位置及解读」，未强制要求必须来自量化情绪指标。

**备选方案**：等待情绪面模块实现后再做本 change，让 `sentiment_position` 自动预填量化情绪等级——拒绝，会造成 P0 能力被 P1 能力阻塞，违反优先级排序；待情绪面模块实现后，可在该 change 中反过来给 Checklist 提供一个可选的「预填」能力（不在本 change 预先设计扩展点）。

## Risks / Trade-offs

- **[风险] 决策 2 的关键词表覆盖不全，用户可以用规则未覆盖的表达方式绕过「可得性单一原因」拦截**（如完全不提及新闻类关键词，直接编两条空洞但字数达标的文本）→ **接受**：V1 明确此局限，规则不追求 100% 拦截所有伪装，只拦截最典型的表达模式；`ChecklistRecord` 的留痕（决策 4）为未来观察真实滥用模式、迭代关键词表提供数据基础。
- **[风险] CLI 交互式 prompt 的多行输入体验（如价值理由需要输入多条直到空行结束）对新手不够直观** → **缓解**：每个 prompt 前打印清晰的操作说明（如「请输入第 N 条价值理由，直接回车结束输入」），且 `checklist show` 命令可随时回顾历史提交格式作为参照。
- **[风险] `value_reasons_json`/`rejection_reasons_json` 用 Text+JSON 存储，无法用 SQL 直接查询理由内容** → **接受**：V1 查询需求（`checklist show <code>`）只需按 code 取出后在应用层解析 JSON，不需要 SQL 层面的全文检索；若未来需要跨股票的理由内容分析（如 PO-09 复盘归因），可在那时评估是否需要额外索引或迁移到关系表。
- **[风险] 硬拦截可能被用户视为「烦人」而放弃使用本工具** → **接受**：这是产品哲学的既定选择（`product-overview.md` §10「Checklist 拦截 vs 仅警告」已定 P0 默认硬拦截），本 change 不重新讨论，若未来数据显示需要调整，应在专门的 fix change 中讨论。

## Migration Plan

- 数据库变更：新增 `checklist_records` 表（`ChecklistRecord`），通过 `Base.metadata.create_all()` 自动建表；`ensure_sqlite_schema()` 补充兜底建表逻辑（参考 `llm_narrate_cache` 的兜底模式），确保已存在的库也能补建
- 纯新增，不影响任何既有表或既有命令行为
- 回滚：删除 `src/service/guard/`、`src/dao/checklist_repo.py`、`ChecklistRecord` ORM 定义、CLI 中 `checklist` 子命令即可；若表已建且有数据，回滚时保留表结构（不做破坏性 `DROP TABLE`），只停用功能入口

## Open Questions

- 是否需要非交互式的 `checklist submit` flag 模式（供脚本化/批量场景）——本 change 不预先设计，等真实脚本化需求出现时再补充（YAGNI）。
- `ChecklistRecord` 是否需要支持「修改/撤销」已提交的记录——MRD 未提及，V1 假设 Checklist 是一次性提交行为（类似「声明」），不支持编辑；若未来需要，应作为独立的小 change 补充。
- 关键词表（`_AVAILABILITY_KEYWORDS`/`_GROUNDED_KEYWORDS`）是否应做成可配置项（`config/app.yaml`）而非硬编码——V1 先硬编码在 `checklist_validator.py` 内，理由与 `EvidenceBucketer` 的兜底文案硬编码一致（现阶段只有一个使用场景，配置化收益不明确），留待未来有调整需求时再评估。
