## Context

`DualTrackAnalyzer.analyze_offline()` 已能产出价值面 + 技术面的确定性结果与融合信号（`combined_signal`/`value_rating`），`EvidenceBucketer` 能从中分桶多空证据要点。但用户当前只能通过 `report tech`/`report value`/`report dual` 三个独立命令查看，缺少「一页看完」的单一入口——这正是 `product-overview.md` §5.3 PO-01「多维立体看板」要解决的问题。

情绪面（PO-06）与决策护航 Checklist（PO-04）都在 roadmap 中标记「待建」，且未必按本 change 之后立即交付。看板作为「对外呈现层的汇总入口」，必须先于这两个模块存在，因此设计上必须能容忍维度缺失。

`docs/mrd/roadmap-todo.md` §5 阶段 G 明确 Web 看板依赖「前述 API 与报告形态稳定」，当前 REST API（`src/controller/`）尚未启动，因此本 change 范围收窄为 CLI 版。

## Goals / Non-Goals

**Goals:**
- 提供单一 CLI 命令 `report dashboard <code>`，一次性呈现价值 + 技术 + 情绪（占位）+ Checklist（占位）+ 综合摘要
- 维度缺失（情绪面/Checklist 未实现，或价值面/技术面本身无本地缓存）时优雅降级，看板仍可输出可用分区，不整体报错
- 看板内部只做展示态编排，不重新计算任何数值，所有数值均来自 `DualTrackAnalyzer`/`EvidenceBucketer` 的既有确定性输出
- `DashboardBuilder` 与 CLI 解耦，便于未来 Web 层直接复用同一编排逻辑

**Non-Goals:**
- 不做 Web 看板（等待 REST API 就绪后单独立项，属于 PO-08 的 Web 部分）
- 不接入情绪面数据源（等待 `add-sentiment-module`）
- 不实现 Checklist 交互（等待 `add-decision-checklist`）
- 不修改 `DualTrackAnalyzer`/`EvidenceBucketer`/`SignalFusion` 的既有计算逻辑
- 不做红蓝对抗 Level 1 互驳叙事的完整呈现（该叙事由 Cursor Skill 在对话中生成，看板只展示证据条数摘要，不重新生成叙事文本）

## Decisions

### 决策 1：呈现载体——CLI 文本单页汇总，Web 明确非本 change 目标

**选择**：V1 做 CLI 版单页汇总报告（`report dashboard`），复用 `report` 命令族的既有风格（数据时效水印、text/JSON 双格式、`--output` 落盘）。Web 版本明确列为非目标，后置到 PO-08 的 Web 部分，待 `src/controller/` REST API 就绪后再单独立项。

**理由**：当前产品完全是 CLI-first（`src/controller/` 目录尚无任何实现），`docs/mrd/roadmap-todo.md` 阶段 G 也明确 Web 看板依赖 API 先行。现在做 Web 版会导致同时引入 API 层脚手架 + 前端脚手架，范围失控，且看板呈现逻辑（`DashboardBuilder`）本身与呈现载体无关，可在 Web 版就绪时直接复用。

**备选方案**：直接做 Web 看板（跳过 CLI 版）——拒绝，当前无 REST API 基建，一次性引入 API + 前端 + 看板三层的范围超出单个 change 合理边界，且违反「先能用、再完整」的既定实施顺序（`roadmap-todo.md` §5）。

### 决策 2：维度缺失的优雅降级——每个分区独立 try/except，不因单一维度失败整体报错

**选择**：`DashboardBuilder.build(code)` 内部按分区（价值面/技术面/情绪面/Checklist）独立处理：
- 价值面/技术面：复用 `DualTrackAnalyzer.analyze_offline()` 已有的“单侧分析失败仅追加 warning、不中断整体流程”模式（见 `analyzer.py` 现有 `try/except` 结构），看板只是在此基础上再做一层展示态判断（`value_result is None` → 该分区显示「无本地快照，请先运行 sync」）
- 情绪面/Checklist：直接判断对应能力尚未接入（V1 阶段硬编码为「待建」，不做运行时探测未来模块是否存在的插件机制，避免过度设计），分区固定输出「情绪面待建（见 PO-06）」/「Checklist 待建（见 PO-04）」
- 只有当价值面与技术面**同时**失败（`value_result is None and tech_result is None`，与 `report dual` 现有报错条件一致）时才判定整体失败，输出 `[error] 未找到 <code> 的本地数据，请先运行 sync`

**理由**：与 `report dual` 现有的“无本地数据才整体报错”策略保持一致，避免用户在只有价值面数据、缺技术面数据时也拿不到任何看板输出。情绪面/Checklist 用硬编码占位而非运行时探测，是因为 V1 阶段这两个模块确定不存在，插件式探测在没有第二个实现之前是过度设计（YAGNI）。

**备选方案**：任一维度缺失就报错拒绝生成看板——拒绝，与 PO-01「单票一页」的核心价值相悖，且情绪面/Checklist 长期未就绪会导致看板功能长期不可用。

### 决策 3：与 `report dual` 的关系——看板是更高层汇总入口，内部复用但不强制包含红蓝对抗完整叙事

**选择**：`DashboardBuilder` 内部调用 `DualTrackAnalyzer.analyze_offline()` 获取 `value_result`/`tech_result`/`combined_signal`，并调用 `EvidenceBucketer().bucket()` 取 `bull_evidence`/`bear_evidence` 的**条数**（而非完整证据列表）纳入综合摘要分区（如「红蓝证据：多方 5 条 / 空方 3 条，详见 report dual 或红蓝对抗 Skill」）。看板**不**复刻 `report dual` 的完整证据列表输出，也不触发红蓝对抗 Cursor Skill。

**理由**：`report dual`（`EvidenceBucketer` 的完整消费方）与看板服务的用户意图不同——`report dual` 是「我要看红蓝对抗的完整证据」，看板是「我要一页看全局，需要的话再深入」。看板展示证据条数摘要 + 引导用户运行 `report dual`/触发 Skill，避免看板文本过长、避免看板与 `report dual` 输出重复导致维护两份几乎相同的格式化逻辑。

**备选方案**：
- 看板直接内嵌完整红蓝对抗证据列表——拒绝，会让看板文本冗长，且与 `report dual` 输出高度重复，维护两份格式化逻辑增加成本
- 看板完全不涉及红蓝对抗信息——拒绝，PO-01 要求「综合摘要」，红蓝证据条数是低成本、高价值的摘要信息，完全不提及会削弱看板的信息完整度

### 决策 4：`DashboardView` 作为独立于 CLI 的编排产物

**选择**：新增 `DashboardView` dataclass（`src/service/report/models/dashboard_view.py`）承载看板的展示态数据（各分区字符串/结构化字段），`DashboardBuilder.build(code) -> DashboardView` 是纯 service 层方法，不感知 CLI 参数（`--json`/`--output`）。CLI 层的 `run_report_dashboard()` 与 `format_dashboard_report()` 只做 `DashboardView → text/JSON` 的转换，遵循既有 `apps/formatters.py` 纯函数模式。

**理由**：符合 `docs/dev/engineering-conventions.md` §3.2 `service/report/` 子域职责（「报告 Context 打包」），且为未来 Web 层直接消费 `DashboardView`（而非重新解析 CLI 文本）预留了清晰边界。

**备选方案**：把看板聚合逻辑直接写在 `run_report_dashboard()` 内——拒绝，会导致未来 Web 层无法复用聚合逻辑，且违反既有 CLI 命令「薄封装、逻辑下沉到 service」的既定模式（`run_report_tech`/`run_report_value` 均如此）。

## Risks / Trade-offs

- **[风险] 情绪面/Checklist 占位文案硬编码，未来两个 change 落地后需要回来修改 `DashboardBuilder`** → **接受**：这是维度缺失场景下的必然代价；`DashboardView` 分区字段设计为独立字段（非拼接字符串），未来接入时只需替换对应分区的取值逻辑，不影响其余分区。
- **[风险] 看板复用 `EvidenceBucketer` 的证据条数摘要，若 `EvidenceBucketer` 分类逻辑未来调整，看板摘要数字会跟随变化** → **接受**：这是有意为之的复用（决策 3），保证数字来源单一；若分类逻辑变化导致数字异常，应在 `EvidenceBucketer` 自身单测中捕获，不需要看板重复校验。
- **[风险] `report dashboard` 与 `report dual`/`report tech`/`report value` 存在信息重叠，用户可能困惑该用哪个命令** → **缓解**：看板文本头部固定提示「本命令为汇总视图，单维度深入分析请使用 report tech/value/dual」，明确各命令定位差异。

## Migration Plan

- 无数据库变更（`DashboardBuilder` 不新增持久化，纯只读编排）
- 新增命令/模块，不影响 `report tech`/`report value`/`report dual` 现有行为
- 回滚：删除 `src/service/report/`、CLI 中 `report dashboard` 子命令与 `format_dashboard_report()` 即可，不影响其余命令

## Open Questions

- 未来情绪面/Checklist 落地后，`DashboardBuilder` 是否需要一个通用的“能力可用性探测”机制（而非硬编码占位）——本 change 不预先设计，等第二个「缺失维度补齐」场景出现时再评估是否值得抽象（YAGNI）。
- 看板是否需要支持批量代码（如一次看多只自选股）——`product-overview.md` 未明确提及批量场景，本 change 不预先设计，仅支持单代码入参。
