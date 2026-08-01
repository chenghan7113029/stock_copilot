## Why

`docs/mrd/features/value-analysis.md` §3.2 定义的 **VA-CLS-2** 需求明确："用户可手动覆盖原型，覆盖结果与原因须可持久化、可追溯"；§10 场景 4 也要求"覆盖记录可持久化追溯"。当前 `PrototypeRouter` 只有硬编码覆盖表 `_CODE_OVERRIDE`（对齐 V1 六只样本股，非用户可写）与财务/行业启发式，没有任何用户可写、可持久化的覆盖机制（roadmap T-8：「人工覆盖持久化，VA-CLS-2，落 dao」，状态"未开始"）。缺少这层能力，当自动分类判断出错（例如某只股票的行业/财务特征恰好落在启发式误判区间）时，用户没有纠正手段，只能等代码修复。

## What Changes

- 新增 DAO 持久化表 `prototype_overrides`（ORM 模型 `PrototypeOverrideRecord`）：`code`（主键）、`prototype`、`reason`、`created_at`、`updated_at`；复用现有 `ensure_sqlite_schema()` 补丁建表模式（参照 `llm_narrate_cache` 的建表方式）
- 新增 `PrototypeOverrideRepo`（`src/dao/prototype_override_repo.py`）：`upsert(code, prototype, reason)`、`get_by_code(code) -> PrototypeOverrideRecord | None`
- `PrototypeRouter.route()` 新增可选参数 `override: str | None = None`：非 `None` 时直接短路返回该 prototype 对应的 method_keys，跳过 `_classify()` 全部内部判定（硬编码覆盖表、行业映射、财务启发式均不执行）——**人工覆盖优先级高于路由器内部的一切既有规则**
- `ValueAnalyzer` 新增可选依赖 `override_repo: PrototypeOverrideRepo | None`；`_analyze_stock()` 在调用 `router.route()` 前查询该 code 是否有覆盖记录，若有则传入 `override=record.prototype`，并在 `warnings` 中追加"原型已人工覆盖为 X（原因：...）"提示（可追溯性要求）
- 新增 CLI 命令 `python -m apps.cli value override <code> <prototype> --reason "<原因>"`：写入/更新覆盖记录（upsert 语义，同一 code 再次执行即为更新覆盖原因或调整原型），`prototype` 参数用 `argparse choices` 限定为已注册的 4 个原型值（Input Guard，零 LLM 校验）
- 明确路由优先级（本 change 的核心设计约束，design.md 详细展开）：**人工覆盖 > 行业映射（若已实施 `add-industry-prototype-router`）> 财务启发式 fallback**；本 change 不强制依赖 `add-industry-prototype-router` 先行实施——`route(stock, override=...)` 的短路检查发生在 `_classify()` 之外，无论 `_classify()` 内部有没有行业映射层，短路逻辑都不需要改动

## Capabilities

### New Capabilities
- `value-prototype-override`：人工覆盖的持久化存储（DAO 表 + Repo）、CLI 写入入口、覆盖记录的可追溯性（reason + 时间戳）

### Modified Capabilities
- `value-prototype-router`：`route()` 新增 `override` 参数，人工覆盖优先级最高
- `value-analyzer`：新增 `override_repo` 依赖注入；`analyze()`/`analyze_offline()` 在覆盖生效时于 `warnings` 追加可追溯提示

## Impact

- **新增文件**：
  - `src/dao/prototype_override_repo.py`
  - `src/dao/models.py` 新增 `PrototypeOverrideRecord` ORM 类（同文件追加，非新文件）
- **修改文件**：
  - `src/dao/engine.py`：`ensure_sqlite_schema()` 新增 `prototype_overrides` 建表补丁
  - `src/service/value/router.py`：`route()` 新增 `override` 参数
  - `src/service/value/analyzer.py`：`__init__`/`from_config()` 新增 `override_repo` 参数；`_analyze_stock()` 查询并应用覆盖
  - `src/apps/cli.py`：新增 `value override` 子命令与 `run_value_override()` 函数
- **不修改**：`_PROTOTYPE_METHODS` 字典（覆盖复用既有原型 → method_keys 映射，不新增取值）；若 `add-industry-prototype-router` 已实施，其 `_classify_by_industry()` 内部逻辑不需要任何改动（人工覆盖在其之前短路）
- **测试**：`test/dao/test_prototype_override_repo.py`（新建）、`test/service/value/test_router.py`、`test/service/value/test_analyzer.py`、`test/apps/test_cli_value_override.py`（新建；本 change 只产出方案文档，不实现代码）
- **文档**：`docs/mrd/features/value-analysis.md` §3.2（VA-CLS-2 状态）、§14.2-C、`docs/mrd/roadmap-todo.md` §4.1（T-8 行）
- **依赖关系**：与 `add-industry-prototype-router`（T-7）逻辑独立，实施顺序不受限制，交叉说明见 design.md「三层路由优先级」；与 `add-prototype-fallback-message`（T-15）无直接依赖
