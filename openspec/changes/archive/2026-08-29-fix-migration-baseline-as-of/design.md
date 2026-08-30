## Context

L3（`compare_migration_baseline.py`）用固定 seed DB 复跑离线 `report tech|value|dual`，期望与 `test/fixtures/migration_baseline/seed/` 零漂移。当前 `KlineProvider.get_kline` 用 `date.today()` 计算 `[today-days, today]`，seed 末交易日停在 2026-06/07：墙钟滑到 2026-08-29 后窗口内根数塌缩（601398 &lt;20 整票归零；600519 MACD 不足），产生约 86 条伪漂移。Owner 选择 **`as_of` 钉观察日**（相对「offline 锚定末根」），以便同一份生产/同步缓存也可在指定观察日下复现对比。

约束：依赖方向 apps/scripts → service → data_provider → dao；确定性与 LLM 分离；默认联网生产语义不变。

## Goals / Non-Goals

**Goals:**

- manifest 登记 `as_of`（ISO 日期）；capture / compare 共用，离线报告窗口与墙钟无关。
- `get_kline`（及串联的 TechAnalyzer 离线路径）支持显式观察日注入；未传时行为等同今日。
- 修确定性后 re-baseline，消化 numbered evidence 与 `methodology_applicable` 等预期 schema 演进。
- 单测证明：固定 `as_of` + 固定 seed，伪造不同 `date.today()` 仍 PASS。

**Non-Goals:**

- 不改变默认联网 CLI「以真实今天为 end」的产品语义。
- 不放宽 `float_rel_tol`；不做「按路径白名单忽略 diff」作为主修复。
- 不改为「永远取库内最后 N 根」为主策略（可作为后续增强，本 change 不做）。
- 不扩 seed 票种、不改估值算法。

## Decisions

### D1: `as_of` 落点 — provider 参数，而非仅脚本 monkeypatch

- **选择**：`KlineProvider.get_kline(..., as_of: date | str | None = None)`；`None` → `date.today()`。offline/online 共用同一窗口公式：`end=as_of`，`start=as_of - days`。
- **理由**：capture/compare、未来 CLI `--as-of`、单测均可注入；避免只在脚本里 patch `date.today`（易漏 TechAnalyzer 其它路径）。
- **备选**：仅在 compare 里 `unittest.mock.patch('datetime.date.today')` — 脆、易漏 import 路径。否决为主方案。

### D2: 向下传递方式

- **选择**：`TechAnalyzer.analyze(..., as_of=None)` → `get_kline(..., as_of=as_of)`；`capture.run_offline_json` / compare 从 config 或显式参数读取 `baseline_as_of` / `as_of`。
- **理由**：scripts 已直接构造 analyzer，改动面可控；CLI 本 change **可不暴露** flag（Non-Goal），仅 scripts + 内部 API。
- **备选**：thread-local / 全局 context — 隐式，违反可测性。否决。

### D3: manifest 契约

- **选择**：`manifest.json` 必含 `"as_of": "YYYY-MM-DD"`。compare 缺失则 **fail fast**（exit ≠ 0）并提示 re-capture。首次 apply 时 capture 用种子数据覆盖区间内的合理日（建议与历史采集接近的 `2026-08-10`，或 seed 内 max(trade_date)+缓冲策略文档化）；写入 manifest 后锁定。
- **理由**：门禁自描述；PR 可读。
- **备选**：缺省回退 today — 会复活 bug。否决。

### D4: re-baseline 时机

- **选择**：先实现 as_of + 单测 → 用旧 manifest 补上 `as_of=2026-08-10`（或验证能逼近旧 tech 数值）→ 再 `capture` 全量重录，登记变更原因：`as_of` 固化 + dual evidence `{index,text}` + `methodology_applicable`。
- **理由**：方案 B：先消时钟伪影，再承认产品 schema。

### D5: 文档

- 更新 `docs/mrd/features/data-source-migration.md` §12.3/12.4：as_of 定义、生产库复用注意事项（as_of 须落在缓存覆盖区间）。

## Risks / Trade-offs

- **[Risk] as_of 选在 seed 覆盖外 → 空窗伪绿/伪红** → Mitigation：capture 校验样本票在窗口内至少满足分析下限（如 ≥20 根或文档化警告）；manifest 旁注 seed 日期范围。
- **[Risk] online 路径误传 as_of 改变用户预期** → Mitigation：CLI 本 change 不暴露；仅 scripts/config 注入；单测锁定默认 `None` ≡ today。
- **[Risk] value 路径是否也吃 today** → Mitigation：分诊显示 value 主 diff 为新字段；若发现财务「截至日」依赖 today，同期注入同一 as_of 或记入 Open Questions 跟进。
- **[Trade-off] 钉 as_of vs 锚末根**：as_of 利于复用生产库做「某日切片」回放；锚末根更「永远用最新缓存」。Owner 已选 as_of。

## Migration Plan

1. 实现 `as_of` 传参与 manifest 读写。
2. 为现有 manifest 写入 `as_of`（与拟重录观察日一致）并跑 compare；记录残留 diff。
3. `capture_migration_baseline.py` re-baseline；更新 file_hashes / git_sha。
4. CI：既有 L3 命令不变，依赖新 manifest 字段。
5. 回滚：还原 provider 签名默认 `None` + 旧 fixtures；门禁行为回退到墙钟敏感（不推荐长期停留）。

## Open Questions

- value/dual 是否存在其它 `date.today()` 依赖需同一 as_of（apply 时用 grep 扫一遍，有则一并注入）。
- 是否在后续 change 给 CLI 加 `--as-of`（本 change 不做）。
