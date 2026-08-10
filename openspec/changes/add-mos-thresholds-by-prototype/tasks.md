## 1. 共享阈值

- [ ] 1.1 Create `src/service/value/mos_thresholds.py`（或等价）：默认按原型表 + 可选从 config 覆盖；导出五档 assessment 与双轨二元阈值
- [ ] 1.2 Test 阈值解析：bank/high_dividend/value_growth 边界值；缺省回退；YAML 覆盖

## 2. Aggregator

- [ ] 2.1 Modify `ValuationAggregator.aggregate`：接收 `prototype`；用共享模块生成 assessment
- [ ] 2.2 Modify `ValueAnalyzer`：把 `prototype` 传入 aggregate
- [ ] 2.3 Test aggregator：同 MOS 不同原型 assessment 不同；value_growth 回归旧五档

## 3. Dual-track

- [ ] 3.1 Modify `signal_fusion.py`：按 prototype 阈值派生 ValueRating（诚实降级仍优先）
- [ ] 3.2 Test：bank MOS=15 → UNDERVALUED；value_growth MOS=15 → FAIR；honesty 仍 UNKNOWN

## 4. 配置与文档

- [ ] 4.1 Update `config/app.example.yaml`：示例 `value.mos_thresholds_by_proto`（注释说明即可）
- [ ] 4.2 Update `docs/mrd/features/value-analysis.md` VA-OUT-3 / T-1 状态与默认表
- [ ] 4.3 Update `docs/mrd/roadmap-todo.md` T-1；`propose_list.md`
- [ ] 4.4 归档前合并要点至 docs，再 `/opsx-archive`
