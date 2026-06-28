## Context

当前 `KlineProvider.get_kline()` 在 API 成功时，用 API 返回的「最后一行」（通常为昨日收盘行）补充到 DataFrame 末端，收盘后即为最终值。盘中调用时，昨日收盘价是最新可用值，导致日线 MA/乖离率/评分均基于 T-1 数据计算，无法反映盘中最新价格位置。

现有架构：`KlineProvider` → `KlineRepo`（SQLite）+ `BaostockFetcher`/`AKShareFetcher`。引入实时行情需要新增一个数据源层组件，以最小侵入方式叠加到现有流程。

## Goals / Non-Goals

**Goals:**
- 提供「盘中实时价格叠加」能力，由调用方按需启用（`use_realtime=True`）
- 默认 EOD 模式行为完全不变（向后兼容）
- 实时行情获取失败时，安全降级至 EOD 模式，不抛异常
- `TechAnalysisResult.quote_mode` 明确标识当次分析的价格时效

**Non-Goals:**
- 分钟级 K 线或 tick 数据（V2 范围）
- 实时推送 / WebSocket 订阅
- 实时价格写入 SQLite 缓存（实时行情不应持久化）
- 历史 K 线的实时修正（仅替换末端当日行）

## Decisions

### D-1：实时报价接口选择
**决策**：使用 AKShare `stock_zh_a_spot_em`（东方财富实时行情），字段含最新价、今开、最高、最低、成交量。  
**备选**：Baostock 无实时行情接口；Tushare 实时行情需 Token + 积分。  
**理由**：AKShare 免 Token，与现有技术栈一致；返回格式稳定。

### D-2：叠加方式
**决策**：`RealtimeOverlayProvider` 将 K 线 DataFrame 末端的「当日行」替换为实时报价构造的行（date=今日, open/high/low/close/volume 来自实时接口）。若今日无历史行，则追加一行。  
**备选**：在 `KlineProvider` 内部直接写实时逻辑。  
**理由**：保持 `KlineProvider` 职责单一；`RealtimeOverlayProvider` 可独立测试和替换。

### D-3：参数传递
**决策**：`use_realtime: bool = False` 从 `TechAnalyzer.analyze()` 透传至 `KlineProvider.get_kline()`，再到 `RealtimeOverlayProvider`。接口签名向后兼容。  
**理由**：避免全局配置污染；调用方按需显式启用，语义清晰。

### D-4：失败降级
**决策**：实时报价获取失败（网络/格式）时，`RealtimeOverlayProvider` 记录 warning 并返回原始 K 线 DataFrame（即退化为 EOD 模式），`quote_mode` 置为 `"eod_fallback"`。  
**理由**：实时行情可靠性低于历史数据，不能阻断分析主流程。

## Risks / Trade-offs

- **[盘前/盘后调用]** 非交易时段实时接口返回的价格可能为 0 或昨日收盘价 → Mitigation：检查 `latest_price > 0` 且为当日日期，否则 fallback
- **[AKShare 格式变化]** `stock_zh_a_spot_em` 字段名可能随版本变动 → Mitigation：在 fetcher 内做字段映射 + 单测 mock 隔离
- **[MA 计算影响]** 实时价格与均线的比较在盘中波动较大，可能产生频繁信号翻转 → Mitigation：`quote_mode` 字段让上层展示时标注「盘中实时」，用户自行判断
