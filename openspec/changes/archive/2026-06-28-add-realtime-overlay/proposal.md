## Why

V1 的 `KlineProvider.get_kline()` 使用昨日收盘价作为 K 线末端，导致当日开盘后所有均线（MA5/10/20/60）、乖离率、支撑判断都滞后一天——盘中最新价与均线的相对位置无法实时感知。对于需要在盘中确认买点的场景，这会产生明显的信息差。

## What Changes

- 新增 `RealtimeQuoteFetcher`：通过 AKShare `stock_zh_a_spot_em` 接口拉取当日实时报价（最新价、涨跌幅、成交量），免 Token
- 新增 `RealtimeOverlayProvider`：将实时报价注入现有 K 线 DataFrame 末端，替换当日占位行（或追加今日未收盘行）
- `KlineProvider.get_kline()` 返回签名不变，但调用方可通过 `use_realtime=True` 参数启用实时叠加；默认 `False`（EOD 模式，向后兼容）
- `TechAnalyzer.analyze()` 新增 `use_realtime: bool = False` 参数，透传至 `KlineProvider`
- `TechAnalysisResult` 新增 `quote_mode: str`（`"eod"` / `"realtime"`）字段，标识当次分析使用的价格时效

## Capabilities

### New Capabilities

- `tech-realtime-overlay`：实时行情叠加能力 — `RealtimeQuoteFetcher` 拉取当日报价；`RealtimeOverlayProvider` 将实时价格注入 K 线末端；通过 `use_realtime` 标志按需启用，不影响 EOD 默认路径

### Modified Capabilities

- `tech-kline-provider`：`get_kline()` 新增 `use_realtime: bool = False` 参数；当日行的来源扩展为「API 历史」或「实时报价叠加」两路
- `tech-analyzer`：`analyze()` 新增 `use_realtime: bool = False` 参数；`TechAnalysisResult` 新增 `quote_mode` 字段

## Impact

- `src/data_provider/akshare/fetcher.py`：新增 `fetch_realtime_quote(code)` 方法
- `src/data_provider/realtime_overlay_provider.py`：新建，`RealtimeOverlayProvider`
- `src/data_provider/kline_provider.py`：`get_kline()` 接受 `use_realtime` 参数
- `src/service/tech/analyzer.py`：`analyze()` 接受 `use_realtime` 参数；组装 `quote_mode`
- `src/service/tech/models/tech_result.py`：`TechAnalysisResult` 新增 `quote_mode: str` 字段
- `test/data_provider/test_realtime_overlay_provider.py`：新建单测
- `test/service/tech/test_analyzer.py`：补充 `use_realtime=True` 路径测试
- `docs/mrd/features/tech-analysis.md`：F-16 状态更新
