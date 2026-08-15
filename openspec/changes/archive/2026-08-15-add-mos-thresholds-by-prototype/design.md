## Context

`_assessment_from_mos` 与 `DualTrackConfig` 使用全局常数。T-1 / VA-OUT-3 要求按原型差异化。诚实降级已用 `methodology_applicable` 切断错误方法的行动叙事；T-1 只服务**方法仍适用**的 V1 三原型（及未来已实现 V2 原型）。

## Goals / Non-Goals

**Goals:**

- 银行 / 高股息 / 价值成长使用可配置、可测的分档阈值
- 价值面 `assessment` 与双轨 `ValueRating` 使用同一套「按原型」低估/高估语义（避免一边低估一边评级 FAIR）
- YAML 可覆盖，缺省行为有文档化默认表

**Non-Goals:**

- 不改 MOS 公式 `((base - price) / base) * 100`
- 不在本 change 引入新原型或新估值方法
- 不为诚实降级标的发明「假低估阈值」

## Decisions

### D1：默认阈值表（可在 apply 前微调，须写入 specs/测试）

单位：百分数点（与现 MOS 一致）。

| prototype | 低估 > | 合理偏低 > | 合理 > | 合理偏高 > | 否则 |
|-----------|--------|------------|--------|------------|------|
| `bank` | 12 | 3 | -3 | -12 | 高估 |
| `high_dividend` | 12 | 3 | -3 | -12 | 高估 |
| `value_growth` | 20 | 5 | -5 | -20 | 高估（保持现状） |
| `unknown` / 其他 | 同 `value_growth`（保守） | | | | |

双轨二元阈值（与分档对齐）：

| prototype | UNDERVALUED if MOS > | OVERVALUED if MOS < |
|-----------|----------------------|---------------------|
| `bank` / `high_dividend` | 12 | -12 |
| `value_growth` / 默认 | 20 | -10（保持现 DualTrackConfig 默认高估侧，或与 -20 对齐——**实现时取：低估侧跟表，高估侧 bank/高股息 -12，value_growth 保持 -10 以免扩大行为差**） |

**理由**：银行/类债模型相对稳，略放宽「低估」门槛；成长维持严。  
**备选否决**：所有原型共用 YAML 全局一对阈值（无法满足 VA-OUT-3）。

### D2：阈值解析模块位置

新增小模块或挂在 `AssumptionProvider` / `value` 包内：`MosThresholds.for_prototype(proto) -> Thresholds`。Aggregator 与 SignalFusion 共用，禁止两处硬编码不一致。

### D3：与诚实降级的优先级

若 `methodology_applicable is False`：不走按原型低估标签（assessment 已是「方法暂不适用」；融合仍 UNKNOWN）。T-1 不覆盖该分支。

### D4：配置

```yaml
value:
  mos_thresholds_by_proto:
    bank: { undervalued: 12, mildly_undervalued: 3, fair_low: -3, mildly_overvalued: -12 }
    # ...
```

缺省用 D1 常量；非法/缺键回退 `value_growth` 表并 warning（可选）。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 银行「低估」变多，用户以为系统突然变乐观 | 报告可注明所用门槛；MRD 写清默认表 |
| Aggregator 与 DualTrack 阈值漂移 | 强制共用 `MosThresholds` |
| 历史报告对比基线漂移 | 迁移说明；baseline 若含 assessment 文案需更新 |

## Migration Plan

1. 实现共享阈值 + Aggregator + Fusion  
2. 单测锁定 D1 表  
3. 更新 MRD T-1 状态  
4. 回滚：删配置即回代码默认；或恢复统一 20/-10

## Open Questions

- 高估侧 `value_growth` 是否应从 -10（双轨）与 -20（五档）完全统一——本期建议**双轨高估侧保持 -10**，五档文案保持 -20，并在 design 注释「已知不对称，与现状一致」；若 Owner 要求对称，apply 前改 specs。
