## Context

对抗 **路径依赖 / 单框架思维**（见 `competitive-reference.md` §4.1）。与红蓝「多空对立」互补：同一 evidence，三种投资哲学 lens。

依赖 numbered evidence 与 `narrate()` 基础设施（`add-confrontation-narrate-api`）。

## Goals / Non-Goals

**Goals:**
- 3 固定 persona 并行 narrate
- 每 persona 输出：`lens_summary`、`emphasized_refs[]`、`blind_spots[]`、`questions_for_self[]`
- grounded 校验 + 分 persona 缓存
- CLI `report persona-stress`

**Non-Goals:**
- 可配置 persona 列表（V2）
- persona 参与 declare 枚举
- 自动修改 Checklist 规则

## Decisions

### D1：Persona 定义（V1 硬编码）

| id | 名称 | 意图 |
|----|------|------|
| value_quality | 价值质量 | 护城河、现金流、MOS；质疑趋势噪音 |
| trend_momentum | 趋势动量 | 趋势/信号；质疑「便宜但无动能」 |
| risk_governor | 风控官 | 价值陷阱、止损、最坏情形 |

Prompt 中注入：**仅**引用 `bull_evidence[n]` / `bear_evidence[n]`；禁止新数字。

### D2：存储

**选择**：`confrontation_records.persona_stress_json`（nullable），结构：

```json
{
  "personas": [
    {"id": "value_quality", "status": "ok", "output": {...}},
    ...
  ]
}
```

可选 CLI `--confrontation-id`：写入已有 record；否则新建 record（evidence-only + persona）。

### D3：与 confront narrate 关系

**选择**：独立命令；用户典型顺序 `report confront --narrate` → `report persona-stress --confrontation-id N`。

**理由**：persona 可选；不拖慢 confront 主路径。

## Risks

- 3× LLM 调用成本 → 必须缓存；`--persona value_quality` 可选单跑（V1 nice-to-have）

## Open Questions

- 是否在 persona 输出末尾固定提示「三种 lens 冲突时，应回到 declare 明确立场」（建议 yes）
