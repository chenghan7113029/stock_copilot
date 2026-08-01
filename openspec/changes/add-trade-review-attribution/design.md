## Context

`docs/dao/models.py`（`src/dao/models.py`）当前只有 `StockSnapshot`（价值面原始数据）、`Kline`（K 线缓存）、`LLMNarrateCache`（LLM 叙事幂等缓存）三张表，均是"市场/公司客观数据"的缓存，没有任何一张表记录"用户做了什么决策"。`product-overview.md` §5.2「决策护航模块」定义的机制中：

- **红蓝对抗（PO-03）**：V1 Skill 版已实现，但"用户声明拒绝哪方及理由"的持久化被明确推迟（见 `add-red-blue-confrontation` design.md "本 change 不预先建表"）
- **结构化 Checklist（PO-04）**：尚未实现（P0，roadmap 标注"待建"）
- **假设今日首开仓（PO-05）**：尚未实现（P0，roadmap 标注"待建"）
- **复盘归因（PO-09，本 change）**：P2，依赖前两者的持久化数据才能完整工作

这意味着本 change 在整个决策护航链条中处于**下游末端**：它消费的"决策审计记录"（Checklist 是否通过）目前完全不存在。`agent-engineering-quality.md` 的"输入卫兵"原则要求"缺失必填参数时立即拒绝，不让下游猜"——本 change 应用同样的原则于 change 依赖层面：不假装"反正先把表建好，将来数据会有的"，而是清晰划定"有 Checklist 数据"和"没有 Checklist 数据"两种模式下系统分别能做什么，让降级路径本身就是设计的一部分而不是事后补丁。

`add-fresh-entry-check`（PO-05）目前也未实现，因此本 change 不能假设存在一个现成的 `PositionRecord`/持仓表可以复用；`add-portfolio-correlation`（PO-10，与本 change 同批提出）同样需要"当前持仓"信息。为避免三个 change（本 change、`add-fresh-entry-check`、`add-portfolio-correlation`）各自定义一套持仓/交易记录表，本 change 承担"第一个定义最小交易记录模型"的角色，其余 change 应交叉引用、复用本表。

## Goals / Non-Goals

**Goals:**
- 定义一个不依赖 `add-decision-checklist` 也能独立工作的最小 `TradeRecord` 模型（松耦合，`checklist_id` 为可空软引用，不做数据库级强制外键约束到一个尚不存在的表）
- 提供"有 Checklist 数据"与"无 Checklist 数据"两种模式下均可运行的复盘归因：前者产出完整胜率+Badcase 归因，后者产出胜率子集并显式声明降级
- V1 归因逻辑保持最简单的确定性统计（胜率、Badcase 计数、描述性字段统计），不引入任何机器学习或自适应权重调整
- 明确"规则反哺"在 V1 阶段的边界：仅提供人工可读的统计报告，不做任何自动化规则修改

**Non-Goals:**
- 不实现 `add-decision-checklist` 本身（不是本 change 的范围，只是消费方）
- 不实现自动化"规则反哺"（不做机器学习权重调整、不做自动生成新 Checklist 规则的能力）——`product-overview.md` §10 开放问题已明确"复盘归因自动化程度：Phase 4，先人工+模板"，本 change 严格遵循这一既定产品决策
- 不使用 LLM 做归因计算（胜率、Badcase 判定均为确定性数值比较，符合 `agent-engineering-quality.md` §3.1"能用代码做的不给 LLM"）；可选的人类可读总结文字生成（如"本季度共 12 笔交易，3 笔 badcase，主要集中在未设止损点的交易"这类自然语言总结）标记为**可选增强**，非 V1 必需，若要接入需复用已冻结的 `add-llm-narrative-core`（不在本 change 范围内实现，仅在 Open Questions 中留空间）
- 不实现"组合级"分析（如复盘归因是否与其他持仓存在关联）——那是 `add-portfolio-correlation` 的范围
- 不做实时/自动化交易记录导入（如对接券商 API），V1 交易记录完全靠用户通过 CLI 手动录入

## Decisions

### 决策 1：`TradeRecord` 与未来 `ChecklistRecord` 的关联方式——软引用整数 ID，不建数据库外键约束

**选择**：`TradeRecord.checklist_id: int | None`，存储的是"未来 `ChecklistRecord.id`"这个整数值，但**不**在数据库层面声明 `ForeignKey("checklist_records.id")`（该表当前不存在，SQLAlchemy 无法解析一个不存在的目标表）。归因逻辑读取 `checklist_id` 时，通过运行时查询判断该 ID 是否能在（未来存在的）`ChecklistRecord` 表中找到对应记录；找不到（无论是因为 ID 为空还是因为 `add-decision-checklist` 尚未实现导致该表不存在）都归入"无 Checklist 数据"降级路径处理。

**理由**：这是本 change 处理"强依赖尚未实现的另一个 change"这一现实约束的核心设计选择。数据库外键要求目标表在 schema 创建时就存在，若本 change 先于 `add-decision-checklist` 实现并合入主干，`create_all()` 会因为找不到目标表而失败。软引用（应用层持有 ID、不做 DB 级约束）让两个 change 可以独立按各自节奏交付，`add-decision-checklist` 落地后只需要保证其 `ChecklistRecord.id` 字段语义稳定，无需回过头修改 `TradeRecord` 的 schema。

**备选方案**：
- 等 `add-decision-checklist` 完全实现后再启动本 change，届时直接建正式外键——拒绝，本次任务要求为 4 个 roadmap 待办功能都产出设计方案，若因为依赖未就绪就完全不产出设计，无法让团队提前评估工作量与交叉依赖；软引用方案能让设计工作现在就完成，实现工作可以延后到依赖就绪，两者解耦。
- 在 `TradeRecord` 中冗余存储 Checklist 内容快照（JSON 字段），而不是引用 ID——拒绝作为主方案（但见决策 2，作为"无 Checklist 表可引用时"的临时降级手段是合理的，不适合作为长期主方案），因为一旦 `add-decision-checklist` 正式确立 schema，两份数据（`ChecklistRecord` 表 + `TradeRecord` 的快照 JSON）容易产生不一致，维护成本高于软引用。

### 决策 2：无 Checklist 数据时的归因降级——胜率统计仍可用，Badcase 归因显式不可用

**选择**：`TradeReviewAnalyzer.analyze()` 内部先检测"是否存在任何 `checklist_id` 非空且能解析到有效 `ChecklistRecord` 的交易记录"；若完全没有（`add-decision-checklist` 未实现的当前状态，或用户从未在录入交易时关联 Checklist），归因报告：
- **仍然计算并展示**：胜率（`win_rate`）、平均收益率（`avg_return`）、交易笔数等纯价格维度统计
- **不计算 Badcase 列表**，报告中显式输出："⚠ 当前无关联 Checklist 记录，无法判定 Badcase（当时是否合规决策），仅展示价格维度统计。启用 Badcase 归因需先完成 Checklist 记录关联（依赖 `add-decision-checklist`）"

**理由**：胜率统计本身只需要价格数据（`TradeRecord.price`/`quantity`/`trade_date`），与 Checklist 完全独立，没有理由因为 Checklist 依赖未就绪就让整个复盘归因功能不可用——这符合"缺失非必填输入时降级而非拒绝整体服务"的鲁棒性原则（区别于`agent-engineering-quality.md` §2.1 讲的"**必填**参数缺失时拒绝"，Checklist 关联在本 change 中被定义为**可选**输入，不是核心统计的必填项）。

**备选方案**：Checklist 未接入时整个 `report trade-review` 命令直接报错拒绝运行——拒绝，用户完全有可能想在 `add-decision-checklist` 落地之前就开始积累交易记录、查看基础胜率，等 Checklist 数据积累起来后归因质量自然提升，没必要人为设置一个"全有或全无"的门槛。

### 决策 3：胜率与 Badcase 的计算口径——FIFO 配对 + 可配置亏损阈值

**选择**：
- **胜率计算**：对同一 `code` 的 `BUY`/`SELL` 记录按时间排序，用 FIFO（先进先出）配对每笔卖出对应的买入批次，计算已实现收益率 `(sell_price - buy_price) / buy_price`；胜率 = 收益率 > 0 的配对数 / 总配对数（未平仓的 `BUY` 记录不计入分母）
- **Badcase 判定**：某笔已配对交易同时满足 (a) 该笔 `BUY` 记录关联的 `ChecklistRecord.passed == True`，(b) 已实现收益率 `< -badcase_threshold`（默认阈值可配置，V1 硬编码合理默认值如 `-8%`，不做用户级个性化配置，避免过度设计）

**理由**：FIFO 是最简单、无歧义的配对方法，个人投资者场景下不需要支持 LIFO/加权平均成本法等更复杂的会计准则（那是机构级需求）；Badcase 阈值需要一个默认值起步，写死一个合理数字比强制要求用户在 V1 就想清楚"我的止损容忍度是多少"更符合"先能用"的迭代节奏。

**备选方案**：支持多种配对方法（FIFO/LIFO/加权平均）——拒绝，个人投资者的实际交易频率与复杂度通常用不到多种会计准则的选择，V1 先用最直观的 FIFO，若未来有真实需求再扩展。

## Risks / Trade-offs

- **[风险] 软引用（无 DB 外键）意味着 `checklist_id` 的数据完整性完全靠应用层保证，可能出现"引用了一个已被删除的 Checklist 记录"的悬空 ID** → **缓解**：归因逻辑查询 `ChecklistRecord` 时用"查不到就当作无 Checklist 数据处理"的宽松容错策略（与决策 2 的降级路径复用同一套代码路径），不会因为悬空引用而抛异常；`add-decision-checklist` 落地时若决定不允许删除 Checklist 记录，可以在那个 change 里进一步加固。
- **[风险] 用户手动录入交易记录容易遗漏或录入延迟，导致胜率统计与真实交易历史不完全一致** → **接受**：V1 明确不对接券商 API 做自动化导入（Non-Goals），手动录入的准确性依赖用户自律，这是"个人使用工具"场景下的合理权衡；`trade record` 命令的 Input Guard（价格>0、数量>0、日期格式校验、action 枚举校验）只能保证"录入的数据本身格式正确"，无法保证"用户没有漏录"。
- **[风险] Badcase 判定的默认阈值（-8%）是主观拍定，不同用户的风险偏好差异很大** → **接受为 V1 已知局限**：不做个性化配置是为了避免"配置项爆炸"这一常见过度设计陷阱；若后续有强烈需求，可以在下一次迭代中把阈值做成 `config/app.yaml` 可配置项，本 change 不预先设计该配置项的结构。
- **[风险] "规则反哺 Checklist"完全依赖人工阅读统计报告后自行修改 Checklist——如果用户不主动看报告，闭环事实上不会发生** → **接受**：`product-overview.md` §10 已将"复盘归因自动化程度"列为 Phase 4 的开放问题，明确"先人工+模板"，本 change 不试图解决"如何让用户主动使用报告"这一产品运营问题。

## Migration Plan

- 新增 `TradeRecord` 表由 `Base.metadata.create_all()` 自动建表，纯新增无迁移
- 若未来 `add-decision-checklist` 落地后需要给 `TradeRecord.checklist_id` 补充真正的数据库外键约束，属于该 change（或一个专门的 schema 加固 change）的范围，不在本 change 内预先处理
- 回滚：删除 `src/service/trade_review/`、`TradeRecord` 模型、`trade_record_repo.py`、CLI 新增子命令即可，不影响任何既有功能（本 change 全程新增，零修改既有表结构）

## Open Questions

- "规则反哺 Checklist"是否需要在报告中给出**具体的修改建议文案**（如"建议在 Checklist 中新增『是否已确认止损点位』的必填校验"），而不仅是统计数字？—— V1 不做决定，倾向于先只输出统计数字（如"N 次 badcase 中 M 次缺少止损记录"），把"建议怎么改"完全留给人工判断；若未来发现纯数字不够直观，可以在描述性统计基础上叠加规则化的建议文案模板（仍非 LLM，非本 change 范围）。
- 是否需要支持"部分平仓"（一笔 `BUY` 被多笔 `SELL` 分批卖出）？—— V1 的 FIFO 配对天然支持部分平仓（按数量拆分配对），design 已考虑，但具体实现细节（如何拆分 `quantity`）留给 tasks 阶段的单测用例覆盖，不在 design.md 中给出算法伪代码。
- 可选的 LLM 人类可读总结（决策范围排除项）如果未来要做，应该消费 `TradeReviewResult` 的哪些字段作为 `narrate()` 的 evidence？—— 留给届时的独立 change 设计，本 change 不预先定义该 schema。
