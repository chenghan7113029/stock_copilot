## 1. MOS 单位一致性（先修可信度）

- [x] 1.1 在 `src/service/report/explainers.py`（新建）实现 `format_mos_percent_points(mos: float | None) -> str`，并模块注释标明「百分数点」约定
- [x] 1.2 Modify `src/service/dual_track/analyzer.py`：`build_analysis_summary` 改用该格式化，移除对 `margin_of_safety` 的 `:.1%`
- [x] 1.3 Modify `src/service/report/dashboard_builder.py`：价值区安全边际改用同一格式化
- [x] 1.4 Modify `src/service/dual_track/config.py`：阈值改为百分数点（`20.0` / `-10.0`），注释说明单位
- [x] 1.5 Modify `test/service/dual_track/test_signal_fusion.py` 及所有误用比例 MOS 的 fixture（如 `0.25`→`25.0`）；补回归：`-0.8` 不得格式化为 `-80%`
- [x] 1.6 审计全库 `margin_of_safety` + `:.1%` / 阈值比较；修完后跑相关 pytest

## 2. 讲解核心模块

- [x] 2.1 Create `src/service/report/explainers.py`：技术指标词典（MA/MACD/RSI/KDJ/量能/Bias/筹码等）+ `render_tech_explanations(...)`
- [x] 2.2 实现估值方法元数据（中文名、含义、适用/不适用）+ `render_value_method_card(key, ValuationResult)`（公式/入参/来源映射/中文评估）
- [x] 2.3 实现 `render_value_trap_explainer(details)` 五维度中文拆解
- [x] 2.4 Create `test/service/report/test_explainers.py`：覆盖 MOS 格式、方法卡片要素、陷阱维度、缺失 details 不编造

## 3. 接入 formatters / CLI 报告

- [x] 3.1 Modify `format_tech_report`：默认嵌入技术指标注释
- [x] 3.2 Modify `format_value_report`：Applicable 完整卡片；Not Applicable 白话；价值陷阱详解；评估词中文化
- [x] 3.3 Modify `format_dual_report`：证据后附加 value/tech 同源讲解；摘要 MOS 已在 1.x 修复
- [x] 3.4 `--json`：保持 `bull_evidence`/`bear_evidence`；讲解仅文本默认（JSON 不附讲解正文）
- [x] 3.5 Modify/扩展 `test/apps/test_formatters.py` 与 dual/tech/value CLI 测试，断言讲解关键字与 MOS 量级

## 4. 入参来源补齐（按缺口）

- [x] 4.1 盘点高频方法（至少 ddm / two_stage_ddm / epv / owner_earnings / value_trap / graham_number）的 `details` 完整度
- [x] 4.2 对缺「来源」的字段补静态映射；必要时最小改动写入 `details`（不改公允价数值）
- [x] 4.3 单测：卡片在 details 齐全时展示来源标签

## 5. 文档

- [x] 5.1 Modify `docs/user-guide.md`：报告默认含讲解；安全边际单位说明与 dual/value 一致示例；术语与报告内嵌关系
- [x] 5.2 Create 或更新 `docs/design/report-inline-explainers.md`（可从本 design 精简）
- [x] 5.3 Modify `docs/mrd/roadmap-todo.md` / product-overview（如有可读性条目）：状态更新
- [x] 5.4 若新增 `service/report/explainers.py`：确认 engineering-conventions 目录描述仍准确，必要时补一行

## 6. 验收

- [x] 6.1 用 `002027`（或本地等价样例）对比：value / dual / dashboard 安全边际同量级
- [x] 6.2 目视：tech 含指标注释；value 每个 Applicable 有卡片；dual 证据后有讲解与陷阱说明
- [x] 6.3 `pytest test/ -q -m "not network"` 全量通过

## 7. 归档

- [x] 7.1 确认 `tasks.md` 全部完成
- [x] 7.2 运行 `/opsx-archive add-report-inline-explainers`，同步 specs 到 `openspec/specs/`，合并文档到 `docs/`
