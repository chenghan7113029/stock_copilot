## Context

`docs/mrd/features/value-analysis.md` §3.2 原文：

> **VA-CLS-2**：用户可手动覆盖原型，覆盖结果与原因须可持久化、可追溯

§10 场景 4（Given/When/Then）：

> **Given** 自动分类将某股判为原型 A；**When** 用户手动覆盖为原型 B 并填写原因；**Then** 系统按原型 B 重新路由方法论并重算，覆盖记录可持久化追溯

`src/service/value/router.py::PrototypeRouter` 当前是无状态类（`__init__` 未定义，直接 `PrototypeRouter()` 构造），`_classify()` 内部依次判定：硬编码覆盖表 `_CODE_OVERRIDE`（V1 六只样本股，代码内常量，非用户可写）→（若 `add-industry-prototype-router` 已实施）行业映射 → 财务启发式。这三层都是"系统判定"，没有"用户判定"层。

`src/dao/` 现有持久化模式（`stock_snapshots`、`kline`、`llm_narrate_cache` 三表）均遵循：ORM 模型定义在 `dao/models.py`，`ensure_sqlite_schema()` 里做"若表不存在则 CREATE TABLE"的补丁式建表（`create_all()` 不会修改已存在的表结构，新表需要在 `ensure_sqlite_schema()` 里显式判断补建，`llm_narrate_cache` 是最近的参照案例）。Repo 类（如 `StockSnapshotRepo`）持有 `Session`，提供面向业务的读写方法，不暴露原始 SQL。

## Goals / Non-Goals

**Goals:**
- 实现 VA-CLS-2：人工覆盖原型可持久化（DAO 表）、可追溯（reason + 时间戳字段）
- 人工覆盖是路由判定的最高优先级，高于路由器内部任何既有/未来规则（硬编码表、行业映射、财务启发式）
- 提供最小可用的 CLI 写入入口（V1 不做 Web 表单，见 proposal.md）
- 与 `add-industry-prototype-router`（T-7）解耦：无论该 change 是否已实施，本 change 都能独立完整交付

**Non-Goals:**
- 不实现覆盖记录的 Web 表单/API 端点（属于未来 `add-value-api-cli` 或 Web 阶段）
- 不实现覆盖记录的批量导入/导出
- 不实现覆盖记录的"清除/回退到自动判定"命令（V1 只支持 upsert 设置覆盖；如需清除，重新覆盖为自动判定会得出的原型是一种手动 workaround，正式的清除命令留作 Open Question）
- 不修改 `_PROTOTYPE_METHODS` 字典或新增 prototype 取值——用户只能覆盖为**已注册**的 4 个原型之一（`bank`/`high_dividend`/`value_growth`/`unknown`），CLI 层用 `argparse choices` 做输入校验（Input Guard，零 LLM，符合 `agent-engineering-quality.md` 三层防御规范）
- 不重新设计 `PrototypeRouter._classify()` 内部的硬编码表/行业映射/启发式判定顺序（人工覆盖是外层短路，不侵入内部判定链）

## Decisions

### 决策 1：三层路由优先级——人工覆盖 > 行业映射 > 财务启发式 fallback

**选择**：最终优先级顺序为：

1. **人工覆盖**（本 change，`route(stock, override=...)` 的 `override` 参数非 `None` 时最先短路返回，跳过 `_classify()` 全部内部逻辑，包括硬编码覆盖表 `_CODE_OVERRIDE`）
2. **硬编码覆盖表 `_CODE_OVERRIDE`**（既有实现细节，V1 六只样本股，不属于本 change 议题，保持不变）
3. **行业映射**（`add-industry-prototype-router`，T-7，若已实施）
4. **财务启发式 fallback**（既有实现，保持不变）

实现方式：`route()` 签名扩展为 `route(self, stock: StockData, override: str | None = None) -> tuple[str, list[str]]`。当 `override is not None`（且是 `_PROTOTYPE_METHODS` 的合法键）时，直接 `stock.proto = override; return override, list(_PROTOTYPE_METHODS[override])`，**不调用** `_classify()`。`override` 参数由调用方（`ValueAnalyzer`）从 `PrototypeOverrideRepo` 查询后传入，`PrototypeRouter` 本身不感知 DAO，保持纯函数式判定逻辑（与现状一致，不引入新依赖方向）。

**理由**：
1. 人工覆盖代表用户的显式判断，语义上必须高于系统的任何自动推断（包括"精心维护的硬编码样本表"），否则用户覆盖会被更"权威"的硬编码表悄悄忽略，违反 VA-CLS-2 的字面要求。
2. 短路点选在 `route()` 方法入口而非 `_classify()` 内部，让 `PrototypeRouter` 保持无状态、无 DAO 依赖（符合 `docs/dev/engineering-conventions.md` §4.2 "禁止跨层跳级"——路由器作为纯业务逻辑，不应该反过来依赖 `dao/`；查询覆盖记录的职责放在 `ValueAnalyzer`，它已经持有 `provider`/`repo` 等基础设施依赖，是合适的编排层）。
3. 这个优先级设计**不要求** `add-industry-prototype-router` 先行实施：`override` 短路发生在 `_classify()` 调用之前，`_classify()` 内部有没有行业映射层，对短路逻辑的正确性没有影响——两个 change 在代码层面几乎零耦合，只在"概念优先级"上有先后关系（这也是为什么本 change 的 Impact 声明"不修改 `_classify_by_industry()`"）。

**备选方案（拒绝）**：
- **方案 B：`PrototypeRouter` 持有 `PrototypeOverrideRepo` 依赖，`_classify()` 内部第一步查询覆盖记录**——拒绝。理由：`PrototypeRouter` 目前是无参数构造的纯逻辑类（`router or PrototypeRouter()`），让它反过来持有一个数据库 Session-bound 的 Repo，会把"每次路由都要建立数据库连接"的隐式假设带入一个原本可以完全离线单测的模块，测试成本上升（当前 `test_router.py` 全部是纯内存 `StockData` fixture，无需 mock DB）；把查询职责放在 `ValueAnalyzer`（编排层，已经持有 session-bound repo）更符合分层。
- **方案 C：人工覆盖优先级低于硬编码覆盖表**（即硬编码表命中时忽略用户覆盖）——拒绝，明显违反"用户可手动覆盖"的产品意图，V1 六只样本股也应该可以被用户覆盖（例如用户认为某只银行股其实该按高股息处理）。

### 决策 2：数据模型——`code` 为主键的单一活跃覆盖记录（非历史多版本表）

**选择**：`PrototypeOverrideRecord` 以 `code`（`String(10)`）为主键，`upsert()` 语义：同一 code 再次调用覆盖命令即更新 `prototype`/`reason`/`updated_at`，不保留历史版本。字段：`code`（PK）、`prototype`（`String(20)`）、`reason`（`Text`）、`created_at`（首次创建时间，`DateTime`）、`updated_at`（`DateTime`，`onupdate`）。

**理由**：VA-CLS-2 要求"可追溯"，但"可追溯"在 V1 语境下指"能看到当前覆盖是谁设置的、为什么"（`reason` + 时间戳字段），不是"历史版本审计日志"（如覆盖了 3 次，能看到 3 次变更记录）。对齐"避免过度设计"的指导原则（proposal.md、design.md 多次强调），V1 用单表单记录满足最小可用的可追溯性需求；若未来产品明确需要覆盖历史审计，可扩展为独立的 `prototype_override_history` 表，不影响本 change 的表结构（`code` 主键表可以继续作为"当前生效记录"的快照视图）。

**备选方案（拒绝）**：
- **方案 B：`(code, created_at)` 复合键，每次覆盖新增一行（历史多版本）**——拒绝，V1 无明确"查看覆盖历史"的产品需求，复合键设计会让"查询当前生效覆盖"变成"按 created_at 取最新一行"，比单表主键 upsert 复杂，且当前 `StockSnapshotRepo` 的 `(code, source, report_period)` 复合键模式是为"多数据源独立存储"设计的，语义不匹配"单一用户覆盖状态"场景。

### 决策 3：CLI 交互——最小命令集，`argparse choices` 做输入校验

**选择**：`python -m apps.cli value override <code> <prototype> --reason "<原因>"`；`prototype` 用 `argparse` 的 `choices=["bank", "high_dividend", "value_growth", "unknown"]` 限定（复用 `_PROTOTYPE_METHODS.keys()` 而非硬编码列表，避免未来新增原型时 CLI 与 router 字典不同步）；`--reason` 为必填参数（`required=True`），空原因不允许提交（呼应 VA-CLS-2"覆盖结果与原因须可持久化"——原因是必需信息，不是可选备注）。

**理由**：与 `docs/dev/engineering-conventions.md` §9.3 Input Guard 原则一致——参数校验用纯代码（`argparse choices`），不依赖运行时才发现"无效原型"错误；`--reason` 必填直接在 CLI 层强制满足 VA-CLS-2 的语义要求，而不是在 DAO 层允许空值再指望上层调用方自律。

**备选方案（拒绝）**：
- **交互式命令行输入（无参数，程序运行后再提示输入）**——拒绝，与现有 `sync`/`report` 命令的"一次性参数化调用"风格不一致，不便于脚本化调用。

## Risks / Trade-offs

- **[风险] 用户覆盖为一个与股票实际行业/财务特征严重不符的原型**（如把银行股覆盖为 `value_growth`，套用 DCF）→ **接受**：这是人工覆盖机制的固有风险（用户主动决策的代价由用户承担），VA-CLS-2 本身就是为了给用户"纠正系统误判"的权力，CLI 层只做"原型是否在已注册集合中"的格式校验，不做"原型是否合理"的语义校验（语义合理性判断超出确定性代码能力范围，属于用户责任）。
- **[风险] `ValueAnalyzer.from_config()` 新增 `override_repo` 可选参数，若调用方忘记传入，覆盖功能静默不生效**→ **缓解**：`override_repo=None` 时的行为是"完全跳过覆盖查询，等同于本 change 之前的行为"，是安全的默认值（不会报错，只是功能不生效）；CLI 的 `run_report_value`/`run_report_dual` 等既有命令需要在 tasks.md 中显式加入"传入 override_repo"的任务项，避免遗漏。
- **[风险] 与 `add-industry-prototype-router` 并行开发时的合并冲突**（两者都修改 `router.py::route()`/`_classify()`）→ **缓解**：本 change 的改动点（`route()` 方法签名新增参数 + 最前置短路 `if`）与 T-7 的改动点（`_classify()` 内部新增行业映射分支）在代码位置上基本不重叠（前者在方法入口，后者在 `_classify()` 内部），实施时后合并的一方只需正常 rebase，无需重新设计。

## Migration Plan

- 新增表 `prototype_overrides`：`ensure_sqlite_schema()` 补丁式建表（参照 `llm_narrate_cache` 案例），首次运行任意 CLI 命令（会调用 `Base.metadata.create_all(engine)` + `ensure_sqlite_schema(engine)`）时自动建表，无需手动迁移脚本
- `route()` 新增可选参数 `override`，默认 `None`，现有调用方（`ValueAnalyzer._analyze_stock()` 改造前的调用点）不传该参数时行为完全不变
- `ValueAnalyzer.__init__`/`from_config()` 新增可选参数 `override_repo`，默认 `None`，不传时行为完全不变（向后兼容，不是 breaking change）
- 回滚：删除 `prototype_overrides` 表相关代码（DAO 模型、Repo、`ensure_sqlite_schema` 补丁块）、还原 `route()` 签名、移除 CLI 子命令即可；已写入的覆盖记录表本身可以保留在数据库中不清理（不影响回滚后的路由行为，因为回滚后代码不再查询该表）

## Open Questions

- 是否需要"清除覆盖，恢复自动判定"的命令（如 `value override <code> --clear`）？V1 未包含，因为当前需求（roadmap T-8 原文）只提到"覆盖持久化"，没有提到"撤销"；若后续需要，是一个很小的独立增量（新增一个 CLI flag + Repo 的 `delete_by_code()` 方法），不需要现在预先设计。
- 是否需要覆盖历史审计（多版本）？见决策 2，V1 明确不做，留待未来产品需求明确后再评估。
- 与 `add-industry-prototype-router`（T-7）的实施顺序：两者相互独立，可任意顺序实施或并行实施（决策 1 已说明零代码耦合），本 Open Question 仅记录"若团队协作开发，建议提前沟通避免同时修改 `router.py` 造成不必要的 merge 冲突"，非技术阻塞项。
