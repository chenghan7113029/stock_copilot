## Context

`src/service/value/valuation/` 已有 Phase 0–3 实现（含 EPV、WACC）。本 change 在同一目录扩展 Phase 4–7，算法 port 自 `ref/valueinvest/valueinvest/valuation/`，保持 None 语义与 ±0.1% 验收标准。

## Goals / Non-Goals

**Goals:**
- Port 12 种新方法，注册到 `default_engine()`
- 评分类方法（Altman/Piotroski/Beneish）正确区分「分数输出」与「公允价输出」
- 相对估值（PE/PB Relative）在 `historical_pe/pb=None` 时返回 Not Applicable
- 32+ 新单元测试，非网络全量回归通过

**Non-Goals:**
- Phase 8（ValueTrap、SBC、Cyclical）
- 原型路由层、区间聚合 orchestrator
- data_provider 历史 PE/PB 自动填充
- Controller/API 暴露

## Decisions

### D1：文件布局

```
src/service/value/valuation/
├── quality.py          # OwnerEarnings + AltmanZScore + PiotroskiFScore
├── dcf.py              # DCF + ReverseDCF
├── growth.py           # PEG + GARP + RuleOf40 + EVEBITDA
├── magic_formula.py    # MagicFormula
├── relative.py         # PERelativeValuation + PBRelativeValuation
├── mscore.py           # BeneishMScore（独立文件，公式较长）
└── engine.py           # default_engine() 扩展
```

### D2：评分类方法的 ValuationResult 约定

Altman / Piotroski / Beneish 仍返回 `ValuationResult`，但：
- `fair_value` 可为 0（不作为定价输入）
- 核心产出写入 `details`（如 `z_score`、`f_score`、`m_score`）
- `applicability` 始终 Applicable/Limited（非 Not Applicable，除非 critical 字段全缺）
- 下游聚合层 SHALL 按 method_key 前缀或 `details` 中 `output_type="score"` 排除

OwnerEarnings / DCF / 成长类方法正常输出 `fair_value`。

### D3：DCF 参数来源

| 参数 | 来源 |
|------|------|
| WACC | `calculate_wacc(stock, assumptions)`（已实现） |
| growth_rate_1_5 | `AssumptionProvider` 默认 5%，或 `StockData.growth_rate` |
| growth_rate_6_10 | 默认 3% |
| terminal_growth | 默认 2% |
| FCF 基数 | `StockData.fcf`，缺失时从 OCF − capex 推导，再缺失则 error |

### D4：相对估值 historical 序列

- `PERelativeValuation`：`StockData.historical_pe` 为空或长度 < 3 → Not Applicable
- `PBRelativeValuation`：同上，`historical_pb`
- 测试用 fixture 注入 5 期序列，与 ref ±0.1%

### D5：default_engine method_key 一览（Phase 4–7 新增）

| method_key | 类 |
|------------|-----|
| `owner_earnings` | OwnerEarnings |
| `dcf` | DCF |
| `reverse_dcf` | ReverseDCF |
| `altman_z` | AltmanZScore |
| `piotroski_f` | PiotroskiFScore |
| `beneish_m` | BeneishMScore |
| `peg` | PEG |
| `garp` | GARP |
| `rule_of_40` | RuleOf40 |
| `ev_ebitda` | EVEBITDA |
| `magic_formula` | MagicFormula |
| `pe_relative` | PERelativeValuation |
| `pb_relative` | PBRelativeValuation |

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| Beneish M-Score 需 prior 期财务数据，A 股字段常缺 | 缺 prior 字段时返回 Limited + warnings，不抛异常 |
| Piotroski 需 6 个 prior_* 对比字段 | 同上；测试 fixture 提供完整 prior 数据 |
| DCF 对 FCF 质量敏感 | 缺失时明确 missing_fields，不静默用 0 |
| Magic Formula 需行业排名上下文 | 单股计算仅输出 EY/ROC 及 implied fair value，不做全市场排名 |

## Migration Plan

1. 纯增量：新文件 + engine 注册扩展，不破坏已有 8 种方法测试
2. `AssumptionProvider` 追加 DCF 增长率字段，向后兼容
3. 无配置/DB 迁移

## Open Questions

- 无阻塞项；Phase 8 独立 change 后续处理
