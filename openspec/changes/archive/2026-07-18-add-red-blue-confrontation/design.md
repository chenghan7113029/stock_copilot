## Context

`DualTrackAnalyzer.analyze()` 已产出 `DualTrackReport`，内含丰富的、天然带立场的确定性证据（详见 proposal）。本 change 落地 `product-overview.md` §6 的红蓝军对抗机制的 V1：**确定性证据分桶（代码）+ 互驳叙事（Cursor Skill）**。

**为何不用 `add-llm-narrative-core`**：该 change 已实现并合入主干（`narrate()` + grounded 校验 + 幂等缓存），技术上可直接调用。但当前主要使用场景是"本人在 Cursor 会话中做决策分析"，引入独立 LLM API 需要：额外 API Key/计费、`config/app.yaml` 配置、网络调用失败降级路径——这些工程量在"个人使用 Cursor"场景下收益低于成本。Cursor Skill 方案直接复用当前会话的模型能力，零额外配置、零额外调用成本，且 V1 阶段"互驳叙事"本身不需要跨会话复用或高并发（这两点才是 `narrate()` 幂等缓存/结构化 API 的核心价值）。因此 `add-llm-narrative-core` 保持已合入但**冻结**（不被任何 change 依赖），留给未来 Web 产品化阶段（届时需要跨用户复用、无 Cursor 会话上下文）。

既有 CLI 设计原则（`add-cli-core` D-1）：「report 永不联网，要新数据必须先 sync」。本 change 的 `report dual` 完全遵循此原则——不联网、不调用任何 LLM API，只输出确定性证据分桶。互驳叙事的生成完全发生在 Skill/Cursor 会话侧，不属于 `report dual` 命令的职责范围，因此不存在既有 CLI 原则与联网叙事的张力（相比之前基于 `narrate()` 的方案，这个张力被架构性地消除了）。

另发现一个既有缺口：`DualTrackAnalyzer.analyze()` 内部调用的是联网版 `ValueAnalyzer.analyze()`，不是 `analyze_offline()`。若 `report dual` 要严格离线，必须先补齐 `DualTrackAnalyzer.analyze_offline()`。

## Goals / Non-Goals

**Goals:**
- 从 `DualTrackReport` 确定性地（零 LLM）分桶出多空证据
- 某一方证据不足时有兜底规则（列出对方假设脆弱性），保证对抗内容不空
- 新增 `report dual` CLI 入口，严格离线，输出证据分桶（文本 + `--json`）
- 提供 Cursor Skill，读取证据分桶生成 Level 1 互驳叙事，在当前会话内交付价值
- Skill 的输入/输出契约需文档化，作为独立 capability 可被检视/演进

**Non-Goals:**
- 不实现真正多轮对话式攻防（Level 2）
- 不实现用户声明/复盘归因的持久化与交互界面（推迟到 Web + LLM API 阶段一并设计，那时才有真实的跨会话消费方）
- 不修改 `SignalFusion` 或 `combined_signal` 的既有融合逻辑
- 不改变 `DualTrackAnalyzer.analyze()`（联网版）的既有行为，只新增 `analyze_offline()`
- 不在代码层实现 grounded 数值锚定校验（Skill 输出不经过 `narrate()` 管道，见风险与缓解）

## Decisions

### 决策 1：证据分桶规则——直接复用既有确定性字段，不新增判断逻辑

**选择**：`EvidenceBucketer` 按以下规则分类，均为读取已有字段，不重新计算：

| 证据来源 | 分桶规则 |
|---|---|
| `value_result.method_results[k].assessment` 含"低估"/正向关键词 | → bull |
| `value_result.method_results[k].assessment` 含"高估"/负向关键词，或 `value_trap` overall_risk ∈ {Medium, High} | → bear |
| `value_result.warnings` | 含"风险"/"不可信"/"Limited" → bear；其余不采信（避免噪音） |
| `tech_result.signal_reasons` | → bull（该字段本身就是"支持买入"的理由） |
| `tech_result.risk_factors` | → bear（该字段本身就是"风险提示"） |

**理由**：`agent-engineering-quality.md` 强调"能用代码做的不要给 LLM"；这些字段的正负极性在产出时已经确定（如 `risk_factors` 命名本身就是负面），用规则分类零幻觉风险、可单测。这一决策不受"Skill 替代 LLM API"路线调整影响，原样保留。

**备选方案**：让 LLM/Skill 直接读原始 `DualTrackReport` 自行判断哪些是利好哪些是利空 —— 拒绝，判断本身会影响后续叙事的事实基础，一旦分类错误整个对抗内容的立场都会错，风险不可控，且这是"代码能做的事"不应交给模型。

### 决策 2：兜底规则的触发阈值与内容来源

**选择**：任一方证据数 `< 2` 时，触发兜底，追加以下内容（仍是规则生成，零 LLM）：
- 价值面：读取 `prototype` 对应方法论的已知局限（如 `value_growth` 原型的 DCF 依赖 growth_rate 假设、bank 原型排除 DCF 的原因）
- 技术面：若 `trend_status` 单边强势，追加"该状态可能钝化/趋势反转历史概率"的通用提示（非个股数据，是方法论层面的通用免责提示）

**理由**：保证对抗双方"有话可说"而不是留空，同时不编造具体数值。

**备选方案**：证据不足时不生成对抗内容，直接提示"证据不足无法对抗" —— 拒绝，会导致强多头/强空头个股永远拿不到红蓝对抗报告。

### 决策 3：`report dual` 始终离线，互驳叙事完全移出 CLI 命令边界

**选择**：
- `report dual <code>`：内部调用 `DualTrackAnalyzer.analyze_offline()` + `EvidenceBucketer` + 兜底规则，全程不触网，输出证据分桶列表（文本或 `--json`）
- **不提供** `--narrate` 或任何联网 flag——互驳叙事的生成责任完全交给 Cursor Skill（在 Cursor 会话中，由用户显式触发 Skill，Skill 内部再决定如何调用当前会话模型）
- CLI 命令本身与"是否使用 LLM"完全解耦，命令output 是叙事生成的输入，不是最终产品

**理由**：相比原方案（CLI 内置 `--narrate` 联网），彻底移除了"report 命令联网"与既有 CLI 原则的张力；也让 `report dual` 命令本身可以独立于 Skill 演进和测试（纯确定性输出，无需 mock LLM）。

**备选方案**：
- 保留 `--narrate` 但改为调用 Skill 而非 `narrate()` —— 技术上不可行，CLI 进程无法反向触发 Cursor Agent 会话；拒绝
- 方案：CLI 输出后由用户手动复制粘贴给 Cursor —— 可行但体验差，Skill 方案可以自动执行 `report dual --json` 并解析，用户只需触发 Skill，拒绝手动复制方案

### 决策 4：Skill 的输入/输出契约

**选择**：Skill（`.cursor/skills/red-blue-confrontation/SKILL.md`）遵循以下契约：
- **输入**：Skill 自行执行 `python -m apps.cli report dual <code> --json`（或用户提供的现成 JSON 文件路径），解析出 `bull_evidence[]` / `bear_evidence[]`（含兜底条目，各含 `text` 与来源标记）
- **生成约束**（写入 SKILL.md 的 instruction，靠 prompt 而非代码强制）：
  - 多方论述基于 `bull_evidence`，空方论述基于 `bear_evidence`，禁止引入证据列表之外的具体数值/事实
  - 互驳部分需引用对方证据的具体条目（可要求带序号），不得泛泛而谈
  - 输出末尾固定包含免责声明："叙事由 AI 生成，仅供参考，请对照上方原始证据列表核实"
- **输出**：直接在对话中呈现 `{多方论述, 空方论述, 多方反驳空方[], 空方反驳多方[]}` 结构；MAY 另存为 `reports/<code>_confrontation.md`（若目录不存在则创建），不写入数据库

**理由**：Skill 是 prompt 层而非代码层的约束，无法做到 `narrate()` 那样的代码级 grounded 校验，但通过要求"引用具体条目 + 保留原始证据可核对"将风险控制在可接受范围，且实现成本几乎为零。

## Risks / Trade-offs

- **[风险] 证据分桶的关键词匹配（"低估"/"高估"等）脆弱，未来估值方法输出文案变化会导致分类失效** → **缓解**：优先用已有结构化字段（如 `value_trap.overall_risk` 枚举值、`ValueRating` 枚举）而非自由文本关键词匹配；仅在缺乏结构化字段时才 fallback 到关键词匹配，且单测覆盖具体文案。
- **[风险] `DualTrackAnalyzer.analyze_offline()` 是新增方法，需要与联网版保持字段行为一致** → **缓解**：复用 `ValueAnalyzer.analyze_offline()` 与 `TechAnalyzer.analyze(offline=True)` 已验证的既有离线路径，`DualTrackAnalyzer` 层只做编排，不重新实现离线逻辑。
- **[风险] Skill 模式没有代码级 grounded 校验，模型可能编造证据外的数字或选择性引用最弱的反驳** → **缓解**：V1 接受此局限；SKILL.md 强制要求输出末尾附免责声明且鼓励引用具体证据序号；CLI 输出的原始证据列表始终与叙事一并可见，供人工核对；若未来发现质量不可接受，可在 Web+API 阶段用 `narrate()` 的 grounded 校验重新实现（`add-llm-narrative-core` 已就位，随时可启用）。
- **[风险] Skill 依赖用户在 Cursor 中手动触发，无法像 CLI 一样被脚本化/自动化批量运行** → **接受**：这是 Skill 方案与 LLM API 方案的核心差异，本 change 明确选择"个人分析场景，牺牲自动化换取零成本"，若未来需要批量/无人值守生成，是启用 `add-llm-narrative-core` 的明确信号。

## Migration Plan

- 无数据库变更（本 change 不新增表）
- `DualTrackAnalyzer.analyze_offline()` 为新增方法，不影响现有 `analyze()` 调用方（`analyze()` 本身零改动）
- 回滚：删除新增文件（`evidence_bucketer.py`、`report dual` 子命令、Skill 目录）即可，不影响双轨分析、CLI 现有命令

## Open Questions

- 兜底规则的"方法论局限性通用提示"文案库，V1 先硬编码在 `EvidenceBucketer` 内（按 prototype 分支），未来若需要更细粒度（如按具体估值方法）可再拆分，本 change 不预先设计扩展点。
- 若未来确定要将 Skill 产出的叙事持久化（例如用户想留存历史对抗记录），届时再评估是否需要 `ConfrontationRecord` 表，本 change 不预先建表。
