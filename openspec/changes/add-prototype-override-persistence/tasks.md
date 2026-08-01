## 1. DAO：PrototypeOverrideRecord 表与 Repo

- [x] 1.1 `src/dao/models.py`：新增 `PrototypeOverrideRecord` ORM 类（`__tablename__ = "prototype_overrides"`）：`code: Mapped[str]`（`String(10)`，`primary_key=True`）、`prototype: Mapped[str]`（`String(20)`, `nullable=False`）、`reason: Mapped[str]`（`Text`, `nullable=False`）、`created_at: Mapped[datetime]`（`default=_utcnow`）、`updated_at: Mapped[datetime]`（`default=_utcnow`, `onupdate=_utcnow`）
- [x] 1.2 `src/dao/engine.py`：`ensure_sqlite_schema()` 新增补丁块——若 `prototype_overrides` 表不存在（沿用现有 `SELECT name FROM sqlite_master` 查询模式），执行 `CREATE TABLE` 语句（列定义与 1.1 一致）
- [x] 1.3 新建 `src/dao/prototype_override_repo.py`：`PrototypeOverrideRepo(session: Session)` 类，方法 `upsert(code: str, prototype: str, reason: str) -> None`（存在则更新 `prototype`/`reason`/`updated_at`，不存在则插入，参照 `StockSnapshotRepo._upsert_dict()` 的 `sqlite_insert(...).on_conflict_do_update()` 模式）、`get_by_code(code: str) -> PrototypeOverrideRecord | None`
- [x] 1.4 单测 `test/dao/test_prototype_override_repo.py`：覆盖首次插入、同 code 二次调用触发更新（`updated_at` 变化、`created_at` 不变）、`get_by_code` 查不到时返回 `None`

## 2. PrototypeRouter：override 参数

- [x] 2.1 `src/service/value/router.py`：`route()` 签名改为 `route(self, stock: StockData, override: str | None = None) -> tuple[str, list[str]]`；`override` 非 `None` 且是 `_PROTOTYPE_METHODS` 合法键时，直接短路：`stock.proto = override; return override, list(_PROTOTYPE_METHODS[override])`，不调用 `_classify()`
- [x] 2.2 `override` 非 `None` 但不是合法键时（防御性处理，理论上不应发生因为 CLI 层已用 `choices` 校验）：忽略该参数，回退到 `_classify()` 正常判定，并可选记录日志（不抛异常，遵循"确定性代码兜底不阻断"原则）
- [x] 2.3 单测 `test/service/value/test_router.py`：新增用例——`override="high_dividend"` 时，即使 `stock.code` 在 `_CODE_OVERRIDE`（如 `"601398"`）中且本应判定为 `bank`，最终返回 `"high_dividend"`（验证人工覆盖优先级最高，覆盖硬编码表）
- [x] 2.4 同文件新增用例——`override=None`（默认值）时，现有全部路由行为不变（回归验证）
- [x] 2.5 同文件新增用例——`override="invalid_prototype"`（非法值）时，回退到 `_classify()` 正常判定，不抛异常

## 3. ValueAnalyzer：查询并应用覆盖

- [x] 3.1 `src/service/value/analyzer.py`：`__init__` 新增可选参数 `override_repo: PrototypeOverrideRepo | None = None`
- [x] 3.2 `from_config(cls, config, repo=None, override_repo=None)`：新增 `override_repo` 形参并透传给构造函数
- [x] 3.3 `_analyze_stock()`：调用 `router.route()` 前，若 `self._override_repo is not None`，调用 `self._override_repo.get_by_code(stock.code)`；若返回非 `None` 记录，调用 `router.route(stock, override=record.prototype)`，并在 `warnings` 列表追加 `f"原型已人工覆盖为 {record.prototype}（原因：{record.reason}）"`；否则按现有方式调用 `router.route(stock)`
- [x] 3.4 单测 `test/service/value/test_analyzer.py`：新增用例——mock `override_repo.get_by_code()` 返回覆盖记录时，`ValueAnalysisResult.prototype` 等于覆盖值，`warnings` 包含可追溯提示文案；`override_repo=None` 或查无记录时行为与本 change 之前完全一致（回归验证）

## 4. CLI：`value override` 子命令

- [x] 4.1 `src/apps/cli.py`：`build_parser()` 新增顶层子命令 `value`（`sub.add_parser("value", ...)`），其下新增子命令 `override`（`code` 位置参数、`prototype` 位置参数用 `choices=list(_PROTOTYPE_METHODS.keys())` 或等价校验来源、`--reason` 必填字符串参数）
- [x] 4.2 新增 `run_value_override(code: str, prototype: str, reason: str, config: dict | None = None) -> None`：初始化数据库（复用 `create_db_engine`/`ensure_sqlite_schema` 既有模式），构造 `PrototypeOverrideRepo(session)`，调用 `upsert()`，提交事务，打印确认信息（如 `"已设置 {code} 原型覆盖为 {prototype}"`）
- [x] 4.3 `main()` 分发逻辑新增 `args.command == "value"` 分支，调用 `run_value_override(...)`
- [x] 4.4 单测 `test/apps/test_cli_value_override.py`：覆盖首次设置、二次调用更新原因、`prototype` 传入非法值时 argparse 报错退出（Input Guard 校验生效）

## 5. 端到端验证

- [x] 5.1 运行 `python -m apps.cli value override 600519 high_dividend --reason "测试：手动覆盖验证"`，确认命令成功且写入数据库
- [x] 5.2 运行 `python -m apps.cli report value 600519`，确认输出的"原型"字段为 `high_dividend`（而非硬编码表原本的 `value_growth`），且 `--- 警告 ---` 区块包含覆盖提示文案
- [x] 5.3 再次运行覆盖命令改为不同原因，确认 `updated_at` 更新（可通过日志或直接查库确认）
- [x] 5.4 运行 `pytest test/ -q -m "not network"`，确认全量测试通过，无回归

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/features/value-analysis.md` §3.2：VA-CLS-2 状态由"未开始"更新为已实现，简述持久化方案（表结构、CLI 入口）
- [x] 6.2 更新 `docs/mrd/features/value-analysis.md` §14.2-C：人工覆盖持久化状态更新
- [x] 6.3 更新 `docs/mrd/roadmap-todo.md` §4.1：T-8 行状态由 `[ ] 待建` 改为 `[x]`，并在变更记录追加一行

## 7. 归档

- [x] 7.1 确认 tasks.md 全部任务完成
- [ ] 7.2 运行归档流程（`openspec archive add-prototype-override-persistence` 或对应 Skill），同步 delta 内容回 `docs/mrd/features/value-analysis.md`
