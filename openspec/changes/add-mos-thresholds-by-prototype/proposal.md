## Why

价值面与双轨融合目前用**统一 MOS 阈值**判定「低估 / 高估」与价值评级（Aggregator：>20% 低估等；DualTrack：默认 >20% / <-10%）。银行、高股息与成长股对「多大折扣才算有安全垫」的风险特征不同，统一尺子会让稳健原型偏严、或让假设脆弱的原型偏松（VA-OUT-3 / T-1）。V1 已实现统一阈值并标注后置；诚实层落地后，对**方法适用**的原型更需要按原型校准行动门槛。

## What Changes

- 引入**按原型可配置的 MOS 评估阈值表**（低估 / 合理偏低 / 合理 / 合理偏高 / 高估分界），默认覆盖 `bank`、`high_dividend`、`value_growth`；`unknown` 与诚实降级标的仍不依赖「低估」行动语义（与 `methodology_applicable=False` 共存）
- `ValuationAggregator`（或 Analyzer 后处理）按 `stock.proto` / 结果 `prototype` 选用阈值生成 `assessment`
- `SignalFusion.derive_value_rating`（或等价路径）按原型选用低估/高估阈值，与价值面标签对齐
- 阈值来源：代码默认常量 + 可选 `config/app.yaml` 覆盖（`value.mos_thresholds_by_proto`）
- **不做**：改变 MOS 计算公式本身；不实现 V2 新原型方法；不放宽诚实降级标的的买入叙事

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `value-aggregator`：`assessment` 由「统一 MOS 阈值」改为「按原型阈值」
- `dual-track-analyzer`：价值评级派生阈值按原型差异化，并与 Aggregator 语义一致

## Impact

- **代码**：`src/service/value/aggregator.py`（及必要时 `analyzer.py`）；`src/service/dual_track/signal_fusion.py`、`config.py`；可选 `config/app.example.yaml`
- **测试**：aggregator / signal_fusion 按原型阈值单测；回归既有统一行为作为 `value_growth` 默认
- **文档**：`docs/mrd/features/value-analysis.md` VA-OUT-3 / T-1；`docs/mrd/roadmap-todo.md` T-1
- **依赖**：不依赖 V2 专用方法；与 `add-v2-honesty-degrade` 兼容（`methodology_applicable=False` 时仍强制 UNKNOWN / 方法暂不适用）
