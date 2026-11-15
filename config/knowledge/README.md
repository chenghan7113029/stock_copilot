# 知识层（config/knowledge）

> 本目录是「系统现在知道什么」的唯一权威源（口径 / 规则 / 判例 / 映射）。
> 生命周期与代码不同：**代码随 change 归档，知识跨波存活**（持续升降级 / 退役）。

## 谁写什么

| 文件 | 谁写 | 写什么 |
| --- | --- | --- |
| `_design.md` | `knowledge-architect`（K1） | 分层方案 + 每层语义 + 准入标准 + 元数据 schema + 升降级 / 退役规则 + ≥1 被否方案 |
| `<layer>/*.yaml` | `knowledge-engineer`（K2） | 知识条目；每条带 来源 / 置信度 / owner / 强度 / 频次 / 生命周期 |
| `known_unknowns.yaml` | `knowledge-engineer`（K2） | 采不到 / 无权威来源 / 待谁确认的「已知未知」（知识负债，不是失败） |
| 其余角色 | — | **只读**。reviewer 通过 `scripts/check_knowledge_source.py` 判 B9，不许改条目 |

`<layer>` 的具体分层由 `_design.md` 定义（本仓库初始不预设层名）。K1 尚未产出 `_design.md` 时，本目录只有本文件与 `known_unknowns.yaml`。

## 采集纪律（本项目硬约束）

- **入口只有两个**：① 人工答复（经 captain 转交）② 仓库内一手材料（`docs/mrd/`、`docs/design/`、`config/*.yaml`、`openspec/specs/`、现有代码与 `test/` 断言）。
- **禁止**：飞书机器人、飞书号、`lark-cli`、任何自动抓取 / 自动蒸馏。当前客户端找不到可蒸馏的飞书机器人或飞书号。
- **知识不可发明**：无来源不入库；把「假设 / 未知」标成「确定」是死罪。
- 置信度判定：人工明确答复（含答复人 + 日期 + 原话）= `确定`；一手材料原文（文件:行 + 引文）= `确定`；推断 / `ref/` 快照 / 外部资料 = `假设`；无来源 = 不入库。
- **代码现状 ≠ 正确口径**：代码怎么算只说明「现在是什么」，要标 `确定` 必须另有 1/2 类信源。
- 1 小时无答复 → 该条标「未解决」，缺口记入 `docs/improvements/IMPROVEMENTS.md` 下波补。

## 机检

```bash
python scripts/check_knowledge_source.py          # 无来源知识 = 0（K2 自查 / reviewer B9 / T8 收口共用）
python scripts/check_knowledge_source.py --json
```

条目判定的形态（三种之一）：顶层 list、顶层 dict 的 `entries:` list、或顶层 dict 自带 `confidence` 字段。
`known_unknowns.yaml` 用 `known_unknowns:` 键，不会被当成知识条目扫描。

## 与 OpenSpec 的关系

知识不是规格：`openspec/specs/` 写「系统必须做什么」（可被 `validate` 校验），本目录写「系统知道什么」（靠来源 + 置信度 + case 回归约束）。**不要把口径写死进 spec 正文**，也不要把行为需求写进知识条目。
