## ADDED Requirements

### Requirement: 人工覆盖记录可持久化存储

系统 SHALL 提供 `PrototypeOverrideRecord`（表 `prototype_overrides`）持久化用户对某股票原型的人工覆盖，字段包含 `code`（主键）、`prototype`、`reason`、`created_at`、`updated_at`。`PrototypeOverrideRepo.upsert(code, prototype, reason)` SHALL 按 `code` upsert：不存在则插入并设置 `created_at`/`updated_at`；已存在则更新 `prototype`/`reason`/`updated_at`，保持 `created_at` 不变。

#### Scenario: 首次设置覆盖

- **WHEN** 调用 `PrototypeOverrideRepo.upsert("600519", "high_dividend", "管理层变更，转向稳定分红策略")`，且此前无该 code 的记录
- **THEN** `get_by_code("600519")` 返回的记录 `prototype == "high_dividend"`，`reason` 与传入一致，`created_at == updated_at`

#### Scenario: 二次覆盖更新而非新增

- **WHEN** 对已存在覆盖记录的 `"600519"` 再次调用 `upsert("600519", "value_growth", "策略反转，重新评估为成长股")`
- **THEN** `get_by_code("600519")` 返回单条记录（不产生第二条），`prototype == "value_growth"`，`reason` 已更新，`updated_at` 晚于 `created_at`，`created_at` 保持首次插入时的值不变

#### Scenario: 查无记录返回 None

- **WHEN** 调用 `get_by_code("999999")` 且该 code 从未被覆盖
- **THEN** 返回 `None`

### Requirement: CLI 提供人工覆盖写入入口

`python -m apps.cli value override <code> <prototype> --reason "<原因>"` SHALL 调用 `PrototypeOverrideRepo.upsert()` 写入覆盖记录；`prototype` 参数 SHALL 被限定为路由器已注册的原型取值集合（`bank`/`high_dividend`/`value_growth`/`unknown`），非法值 SHALL 被 argparse 在执行业务逻辑前拦截并以非零退出码结束；`--reason` SHALL 为必填参数，缺失时命令报错退出。

#### Scenario: 合法覆盖命令成功执行

- **WHEN** 用户执行 `python -m apps.cli value override 600519 high_dividend --reason "管理层变更"`
- **THEN** 命令以退出码 0 结束，stdout 输出确认信息，数据库中出现对应覆盖记录

#### Scenario: 非法原型值被拦截

- **WHEN** 用户执行 `python -m apps.cli value override 600519 insurance --reason "测试"`（`insurance` 不在已注册原型集合中）
- **THEN** 命令在写入数据库前即报错退出（argparse `choices` 校验失败），不产生任何数据库写入

#### Scenario: 缺失原因参数被拦截

- **WHEN** 用户执行 `python -m apps.cli value override 600519 high_dividend`（缺少 `--reason`）
- **THEN** 命令报错退出，不产生数据库写入
