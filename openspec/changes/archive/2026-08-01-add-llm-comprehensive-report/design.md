## Context

`common.llm.narrate(evidence, schema, instruction) -> NarrateResult` 已实现并合入主干（`add-llm-narrative-core`），提供完整三层防御：Input Guard（空 evidence 拒绝 + 超长截断）、LLM 核（强制 JSON、`_SYSTEM_PROMPT` 已声明「不得编造 evidence 之外的事实」）、Output Guard（jsonschema 校验 + grounded 数值锚定校验 + 置信度分级 + 幂等缓存，缓存介质为已存在的 `llm_narrate_cache` 表）。但该 change 的 `tasks.md` 第 10 项归档任务标注「已冻结，暂缓执行」，因为落地时 `add-red-blue-confrontation` 改用 Cursor Skill 方案，narrate() 至今零消费方。

本 change 是 `narrate()` 的首个真实消费方，把它接到 PO-02「LLM 综合报告」这个具体业务场景上。落地后 `add-llm-narrative-core` 的冻结状态应解除（有真实消费方），但**本 change 只在此说明这一状态变化，不在 propose 阶段修改 `add-llm-narrative-core` 自己的文件**——那是本 change 进入 apply 阶段、真正调用 `narrate()` 时才需要同步更新 `add-llm-narrative-core/proposal.md` 顶部状态说明与 `tasks.md` 第 10.3 项的事。

`add-cli-core` 的既定原则 D-1「report 永不联网，要新数据必须先 sync」在 `add-red-blue-confrontation` 落地时被细化为「report 默认离线，联网需显式 flag」（该 change 的决策 3 明确拒绝了给 `report dual` 加 `--narrate`，理由是 Cursor 会话无法被 CLI 进程反向触发）。但那条拒绝理由是针对「触发 Cursor Skill」这个技术上不可行的路径，不适用于本 change——`narrate()` 是真实的 LLM API 调用，CLI 进程完全可以直接发起，因此给新命令加 `--narrate` flag 没有架构障碍。

## Goals / Non-Goals

**Goals:**
- 直接调用 `common.llm.narrate()`，不重新实现任何 LLM client / schema 校验 / grounded 校验逻辑
- 从 `DualTrackReport` 打包确定性 evidence（价值面 + 技术面关键字段），schema 定义综合报告结构（`summary`/`key_points[]`/`risks[]`）
- instruction 层显式重复「禁止引入 evidence 之外的新数字」的约束，作为 grounded 校验之外的第二道防线（纵深防御，即使 grounded 校验本身已能拦截多数数值幻觉）
- 新增 CLI 入口，默认离线（仅确定性摘要），显式 `--narrate` 才联网
- LLM 调用失败（未配置/超时/schema 校验失败/grounded 失败/低置信度）时优雅降级为确定性摘要 + 失败原因，不阻断命令整体输出

**Non-Goals:**
- 不扩展 `narrate()`/`LLMClient`/grounded 校验的既有能力（如需要，属于 `add-llm-narrative-core` 自身的后续 change）
- 不接入红蓝对抗完整证据或情绪面数据作为 evidence（V1 只消费价值面 + 技术面，未来可扩展，本 change 不预先设计扩展点）
- 不做 Web 端展示（属于未来 PO-08 Web 部分）
- 不修改 `report dual` 的既有契约与行为

## Decisions

### 决策 1：直接消费 `narrate()`，不新增中间抽象层

**选择**：`comprehensive_narrator.py` 直接 `from common.llm.narrator import narrate`，传入本地定义的 schema/instruction，不新增 `ReportNarratorBase` 之类的抽象基类。

**理由**：`narrate()` 本身已经是「evidence + schema + instruction → NarrateResult」的通用接口，业务方只需要提供三个参数，没有需要抽象的重复逻辑。过早抽象（如假设未来会有很多种 narrator 需要共享基类）违反 YAGNI；`add-llm-narrative-core` 的 design.md 已明确 `narrate()`「完全独立于具体业务语义」，本 change 的职责就是提供这三个业务参数。

**备选方案**：新增 `BaseReportNarrator` 抽象类，`comprehensive_narrator` 继承之——拒绝，当前只有一个消费场景，抽象基类没有第二个实现可验证其合理性。

### 决策 2：ContextPack 打包范围——只含确定性字段，不含原始 warnings 自由文本

**选择**：`build_dual_track_evidence(report)` 打包字段限定为：
- 价值面：`fair_value_range`（low/base/high）、`margin_of_safety`、`price_percentile`、`assessment`、`confidence`、`prototype`
- 技术面：`trend_status`、`signal_score`、`buy_signal`、`signal_reasons[]`、`risk_factors[]`
- 融合：`combined_signal`、`value_rating`
- 不包含 `warnings[]`（数据质量类警告，语义上不是「证据」，混入 evidence 会增加 grounded 校验的噪声面）

**理由**：`docs/agent-engineering-quality.md` 强调 evidence 应该是「干净、标准化的输入」；`warnings` 里可能包含与叙事无关的技术性提示（如「原型未识别」），纳入 evidence 只会增加 LLM 误用/复述的风险，不增加叙事价值。

**备选方案**：把 `DualTrackReport` 全量字段（含 `warnings`）都塞进 evidence——拒绝，`agent-engineering-quality.md` §2.3 明确「超长输入需要截断/摘要」，全量打包会更快触发 `narrate()` 的截断逻辑，且降低信号密度。

### 决策 3：CLI 入口——新增 `report summary`，不在 `report dual` 上加 `--narrate`

**选择**：新增独立命令 `report summary <code> [--narrate]`。不传 `--narrate` 时只输出确定性摘要（`build_analysis_summary()` 的既有输出 + 红蓝证据条数，不联网、不调用 `narrate()`）；传入 `--narrate` 时额外调用 `narrate_comprehensive_report()` 联网生成叙事段落并追加到输出。

**理由**：
- `report dual` 的既有 spec（`cli-report-dual`）明确「SHALL NOT 提供任何联网/LLM 相关 flag」，这是 `add-red-blue-confrontation` 的既定契约；修改它去支持 `--narrate` 属于对已交付 capability 的破坏性变更，且语义会变得混乱（`report dual` 的输出契约是「证据分桶」，不是「综合报告」）
- `report summary` 的 evidence 组成（价值面+技术面确定性字段）与 `report dual` 的证据分桶（bull/bear 列表）本质是两种不同的数据视图，拆分成两个命令职责更清晰
- 遵循既有「report 默认离线，联网需显式 flag」原则：不传 `--narrate` 时命令行为与其余 `report` 子命令一致（离线、可重复、可脚本化）

**备选方案**：
- 给 `report dual` 加 `--narrate`——拒绝，理由见上（破坏既有契约、语义混乱）
- 新增独立顶层命令 `python -m apps.cli narrate <code>`（不挂在 `report` 子命令下）——拒绝，`report` 家族已建立「离线报告生成」的用户心智，`report summary --narrate` 比独立顶层命令更符合既有 CLI 结构的一致性

### 决策 4：instruction 层重复"禁止编造数字"约束，作为纵深防御

**选择**：`comprehensive_narrator.py` 的 instruction 文本显式包含：「只能基于给定 evidence 中的数值与结论组织叙述，不得引入 evidence 之外的任何新数字、新百分比、新结论；若 evidence 不足以支撑某个论断，应明确说明信息不足，而非猜测」。这与 `narrate()` 内部 `_SYSTEM_PROMPT` 的约束（「你只能基于用户提供的 evidence 组织叙述，不得编造 evidence 中不存在的数字或事实」）在语义上重复。

**理由**：`agent-engineering-quality.md` §2.5/§8 反模式 #10 强调「不要指望 prompt 指令单独可靠」，但也不等于 prompt 指令完全无价值——它是纵深防御的一层（即使 grounded 校验已经是代码层硬约束）。本 change 的 instruction 补充业务语境（「综合报告」的具体结构要求），复用系统级约束的同时补充业务级约束，两者不冲突、职责不同（系统级管「不编造」，业务级管「这份报告应该讲什么」）。

**备选方案**：instruction 不重复强调，只依赖 `narrate()` 内置的系统级约束——可行但不采用，因为 instruction 是业务方唯一能传达「这次叙事的具体上下文与红线」的位置，省略后如果未来 `narrate()` 系统级 prompt 被调整（如变得更宽松），本业务场景会失去自己的显式声明。

## Risks / Trade-offs

- **[风险] LLM 综合报告可能因 grounded 校验失败反复重试后仍失败（如小模型不擅长严格遵循数值约束）** → **缓解**：`narrate()` 已有 `_SCHEMA_RETRIES=2` 上限，超限后返回 `ok=False`；本 change 的 CLI 层在 `ok=False` 时降级为「仅展示确定性摘要 + 附加提示『LLM 叙事生成失败：<原因>，以下为确定性摘要』」，不阻断命令输出，用户始终能拿到可用信息。
- **[风险] `--narrate` 引入网络依赖与延迟（LLM API 调用可能需要数秒到数十秒）** → **接受**：这是显式 opt-in flag，用户知情选择；不传 `--narrate` 的默认路径完全不受影响。
- **[风险] evidence 打包范围（决策 2）排除 `warnings`，未来若某个 warning 对综合报告很重要（如「价值面无本地快照」）却被排除，叙事可能显得脱离实际情况** → **缓解**：`build_dual_track_evidence` 只在 `value_result`/`tech_result` 非 `None` 时才纳入对应分区（缺失分区不纳入 evidence，而非纳入一条「缺失」warning），LLM 天然只会叙述 evidence 中存在的维度，不会凭空补全缺失维度的结论；若某维度整体缺失，CLI 层在确定性摘要部分已有既有的「无本地快照」提示，与 LLM 叙事互补而非依赖 LLM 提及。
- **[风险] `add-llm-narrative-core` 解冻后，若本 change 的具体使用暴露出 `narrate()` 本身的缺陷（如 grounded 校验漏报语义类幻觉），责任边界不清** → **缓解**：本 change 的 design 明确「不修改 `narrate()` 自身」；若发现 `narrate()` 缺陷，应在 `add-llm-narrative-core`（或其后续 fix change）中修复，本 change 只负责正确调用与合理降级。

## Migration Plan

- 无数据库变更：`llm_narrate_cache` 表已由 `add-llm-narrative-core` 建好，本 change 直接复用
- 新增命令与模块，不影响 `report tech`/`report value`/`report dual`/`report dashboard` 现有行为
- **`add-llm-narrative-core` 状态同步**（属本 change 实施阶段任务，非 propose 阶段）：apply 完成后，需回到 `openspec/changes/add-llm-narrative-core/proposal.md` 顶部状态说明与 `tasks.md` 10.3 项，去掉「已冻结/暂缓执行」标注，视情况执行 `/opsx-archive add-llm-narrative-core`
- 回滚：删除 `src/service/report/context_pack.py`、`comprehensive_narrator.py`、CLI 中 `report summary` 子命令即可，不影响 `narrate()` 本身或其余命令

## Open Questions

- 未来红蓝对抗证据 / 情绪面数据接入 evidence 后，schema 是否需要拆分为更细的分区（如 `bull_narrative`/`bear_narrative`）——本 change 不预先设计，等真实需求出现（对应 change 落地）时再扩展 schema，避免过度设计。
- `--narrate` 的调用结果是否需要写入 `reports/` 目录持久化——`docs/dev/engineering-conventions.md` §10 允许 `service/report/` 写 `reports/`，但本 change 的 `--output` flag 已提供落盘能力，是否需要额外的自动归档命名规则（如按日期分文件夹）留给未来使用量上升后再评估。
