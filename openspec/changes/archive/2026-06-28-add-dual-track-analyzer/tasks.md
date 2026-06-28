## 1. 数据模型

- [x] 1.1 新建 `src/service/dual_track/models/__init__.py`（空）
- [x] 1.2 新建 `src/service/dual_track/models/report.py`：
  - 定义 `CombinedSignal` 枚举（STRONG_BUY / BUY / HOLD / WAIT / SELL / STRONG_SELL）
  - 定义 `ValueRating` 枚举（UNDERVALUED / FAIR / OVERVALUED / UNKNOWN）
  - 定义 `DualTrackReport` dataclass（`code`, `value_result`, `tech_result`, `combined_signal`, `value_rating`, `analysis_summary`, `warnings`, `data_timestamp`）

## 2. 信号融合逻辑

- [x] 2.1 新建 `src/service/dual_track/signal_fusion.py`：
  - 实现 `ValueRating` 派生函数 `derive_value_rating(mos: float | None, config) -> ValueRating`：MOS > 20% → UNDERVALUED；[-10%, 20%] → FAIR；< -10% → OVERVALUED；None → UNKNOWN
  - 实现 `SignalFusion.fuse(value_result, tech_result, config) -> CombinedSignal`：按 3×6 矩阵（见 design.md D-3）输出；处理 value_result=None / tech_result=None / 两者均 None 的降级路径

## 3. DualTrackAnalyzer Facade

- [x] 3.1 新建 `src/service/dual_track/__init__.py`：导出 `DualTrackAnalyzer`, `DualTrackReport`, `CombinedSignal`
- [x] 3.2 新建 `src/service/dual_track/analyzer.py`：
  - 实现 `DualTrackAnalyzer.__init__(value_analyzer, tech_analyzer, config)`
  - 实现 `from_config(config_dict) -> DualTrackAnalyzer`：内部调用 `ValueAnalyzer.from_config()` 和 `TechAnalyzer.from_config()`
  - 实现 `analyze(code) -> DualTrackReport`：顺序调用两个 Analyzer，捕获各自异常，调用 `SignalFusion.fuse()`，生成 `analysis_summary`，组装 `DualTrackReport`
- [x] 3.3 实现 `analysis_summary` 生成：纯字符串拼装，包含「股票代码 | 价值面：公允价区间 | 安全边际 | 技术面：趋势 | 评分 | 综合信号」格式

## 4. DualTrackConfig

- [x] 4.1 新建 `src/service/dual_track/config.py`：定义 `DualTrackConfig` dataclass，含 `undervalued_mos_threshold: float = 0.20`、`overvalued_mos_threshold: float = -0.10`，供 `SignalFusion` 使用

## 5. 单元测试

- [x] 5.1 新建 `test/service/dual_track/test_signal_fusion.py`：
  - 覆盖融合矩阵全部 18 组合（UNDERVALUED/FAIR/OVERVALUED × 6 级 BuySignal）
  - 测试 value_result=None → combined_signal = tech buy_signal
  - 测试 tech_result=None → 单价值面降级
  - 测试两者均 None → WAIT
  - 测试 MOS=None → ValueRating.UNKNOWN
- [x] 5.2 新建 `test/service/dual_track/test_analyzer.py`：
  - mock 两个子 Analyzer 正常 → 验证 DualTrackReport 所有字段非 None，combined_signal 正确
  - mock ValueAnalyzer 抛出异常 → value_result=None，combined_signal=tech buy_signal
  - mock TechAnalyzer 抛出异常 → tech_result=None，combined_signal 基于价值面
  - mock 两者均失败 → combined_signal=WAIT，warnings 含两路原因
  - 验证 analysis_summary 包含代码、公允价（若有）、趋势、综合信号
  - 验证 from_config 工厂方法可正常构造（mock 子 Analyzer from_config）
- [x] 5.3 运行 `py -m pytest test/service/dual_track/ -v` 确认全部通过
- [x] 5.4 运行 `py -m ruff check src/service/dual_track/` 确认无 lint 错误

## 6. 文档更新

- [x] 6.1 更新 `docs/mrd/features/tech-analysis.md`：§10.3 双轨集成点状态更新，DualTrackAnalyzer 标为 ✅；变更记录新增 `add-dual-track-analyzer` 条目
- [x] 6.2 更新 `docs/mrd/product-overview.md`（如有必要）：§5.3 双轨看板集成说明中标注 DualTrackAnalyzer 已交付
