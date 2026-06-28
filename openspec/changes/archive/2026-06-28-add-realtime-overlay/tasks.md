## 1. 实时报价数据层

- [x] 1.1 修改 `src/data_provider/akshare/fetcher.py`：新增 `fetch_realtime_quote(code: str) -> dict` 方法，调用 AKShare `stock_zh_a_spot_em`，返回 `{date, open, high, low, close, volume}`；获取失败时抛出 `DataProviderError`
- [x] 1.2 新建 `src/data_provider/realtime_overlay_provider.py`：实现 `RealtimeOverlayProvider` 类，`overlay(df, code) -> tuple[pd.DataFrame, str]`（第二个元素为 quote_mode）；实时价格无效（close=0 或 NaN）时降级为 eod_fallback
- [x] 1.3 验证：`fetch_realtime_quote` 的 `close > 0` 检查与 NaN 防护逻辑正确

## 2. KlineProvider 扩展

- [x] 2.1 修改 `src/data_provider/kline_provider.py`：`get_kline()` 新增 `use_realtime: bool = False` 参数；当 True 时在正常流程后调用 `RealtimeOverlayProvider.overlay()`；返回签名扩展为 `(DataFrame, list[str], str)`（第三元素 quote_mode）
- [x] 2.2 确保 `use_realtime=False`（默认）时行为与当前完全一致（向后兼容）

## 3. TechAnalysisResult 与 TechAnalyzer 扩展

- [x] 3.1 修改 `src/service/tech/models/tech_result.py`：`TechAnalysisResult` 新增 `quote_mode: str = "eod"` 字段
- [x] 3.2 修改 `src/service/tech/analyzer.py`：`analyze()` 新增 `use_realtime: bool = False` 参数，透传至 `get_kline()`，将返回的 quote_mode 赋值给 `result.quote_mode`
- [x] 3.3 修改 `src/service/tech/__init__.py`：确认公共导出包含变更（如有必要）

## 4. 单元测试

- [x] 4.1 新建 `test/data_provider/test_realtime_overlay_provider.py`：
  - mock `fetch_realtime_quote` 正常返回 → 验证末端行被替换，quote_mode = "realtime"
  - mock 今日无历史行 → 验证追加新行
  - mock 实时报价失败 → 验证降级为 eod_fallback，warnings 非空
  - mock close = 0 → 验证降级为 eod_fallback
- [x] 4.2 修改 `test/service/tech/test_analyzer.py`：
  - 新增 `use_realtime=True` 路径测试：mock RealtimeOverlayProvider 返回 "realtime" → 验证 result.quote_mode
  - 新增实时叠加失败路径：mock 返回 "eod_fallback" → 验证 result.quote_mode = "eod_fallback"
  - 验证默认 `use_realtime=False` 时 quote_mode = "eod"
- [x] 4.3 运行 `py -m pytest test/data_provider/ test/service/tech/ -v` 确认全部通过
- [x] 4.4 运行 `py -m ruff check src/data_provider/ src/service/tech/` 确认无 lint 错误

## 5. 文档更新

- [x] 5.1 更新 `docs/mrd/features/tech-analysis.md`：F-16 状态改为 ✅，变更记录新增 `add-realtime-overlay` 条目；§7.1 文件清单补充 `RealtimeOverlayProvider`；§4.2 `TechAnalysisResult` 补充 `quote_mode` 字段说明
