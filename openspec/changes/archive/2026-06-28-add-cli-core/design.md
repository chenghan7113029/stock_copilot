## Context

`src/apps/` 目前仅有 `__init__.py`，三个 Facade（`TechAnalyzer`、`ValueAnalyzer`、`DualTrackAnalyzer`）全部实现完毕但无对外入口。`scripts/fetch_value_data.py` 是唯一的「用户可运行脚本」，功能局限于价值面数据采集。

**核心问题**：

1. `TechAnalyzer.analyze()` 默认每次调用都会联网拉取 K 线（会尝试补洞），无法强制离线
2. `ValueAnalyzer.analyze()` → `StockDataProvider.get_stock_data()` 始终联网，`StockSnapshotRepo.find_by_code()` 已有但没有「snapshot → StockData」重建路径
3. `KlineProvider` 当日 K 线不写缓存（设计 D-1），导致 `sync --realtime` 的结果在下次 `report` 时不可见

## Goals / Non-Goals

**Goals:**

- 三条 CLI 命令：`sync <code>`、`report tech <code>`、`report value <code>`
- `sync` 是唯一联网路径；`report` 默认纯离线，不触发网络
- `--realtime` 仅在 `sync` 上，`report` 不提供
- `sync --realtime` 叠加的当日 K 线持久化写入，供后续 `report tech` 读取
- 报告输出 text（默认）+ `--json`；落盘可选 `--output <path>`
- `scripts/fetch_value_data.py` 重构为薄包装，不重复逻辑

**Non-Goals:**

- 批量 sync（多 code）
- `report` 上的联网 / `--realtime` 参数
- Web 看板、FastAPI 接口
- LLM 综合报告
- `--format md` 格式（V1.1 待加）

## Decisions

### D-1：sync/report 严格分离（offline=True by default in report）
**决策**：`report` 命令不接受任何联网参数。要新数据必须先 `sync`。  
**理由**：report 可用 fixture/seed DB 做确定性测试；同时去除「不小心在 report 时触发 API 调用」的风险。  
**备选**：`report --force-fetch`（增加复杂度，首版不需要）。

### D-2：sync 路径持久化当日 K 线
**决策**：`sync` 时 `KlineProvider.get_kline()` 新增 `persist_today=True` 参数，将当日行（含 realtime overlay 结果）写入 `kline` 表。`report` 调用 `get_kline(offline=True)`，只读缓存。  
**理由**：不改 D-1（当日不写）语义的前提下，为 sync-then-report 工作流留出专用写路径。  
**备选**：另起 `kline_session` 表（语义更清晰但引入新模型，首版不必要）。

### D-3：离线价值面数据重建
**决策**：新增 `StockDataProvider.get_stock_data_offline(code)`——调用 `StockSnapshotRepo.find_by_code(code)` 取全部 source 快照，按与联网路径相同的字段优先级合并为 `StockData`，不做网络调用。  
**理由**：复用现有 repo 与 `_merge_result` 合并逻辑；最小改动路径。  
**备选**：给 `get_stock_data()` 加 `mode="offline"` 开关（等效，语义稍不清晰）。

### D-4：报告格式化层（Formatter）
**决策**：在 `src/apps/formatters.py` 实现两个纯函数：
- `format_tech_report(result: TechAnalysisResult, as_json: bool) -> str`
- `format_value_report(result: ValueAnalysisResult, as_json: bool) -> str`  

text 输出固定字段集（见 spec），json 输出直接 `dataclasses.asdict()`。  
**理由**：纯函数便于测试（输入 fixture 对象，比对输出字符串）；与 CLI 入口解耦，后续 Web/API 可复用。

### D-5：CLI 框架
**决策**：使用标准库 `argparse`，不引入 `typer` / `click`。  
**理由**：减少依赖；现有 `scripts/` 已有 argparse 用法；CLI V1 结构简单，三层子命令足够。

### D-6：数据时效水印
**决策**：`report` 输出头部始终展示「数据快照时间 + 离线提示」：
```
[离线模式] K线末行: 2026-06-28 | 价值快照: 2026-06-28 09:15
```
**理由**：用户需知道当前 report 基于哪天数据，避免误以为实时。

## Risks / Trade-offs

- **[价值快照合并精度]** `find_by_code` 返回多 source 快照，字段优先级需与联网 `_merge_result` 保持一致 → Mitigation：提取 `_merge_fields()` 共享方法，offline/online 路径共用。
- **[sync 写当日行与 D-1 冲突]** 原 `kline` 设计不写 today → Mitigation：以 `persist_today=True` 为显式 opt-in，调用方（sync 命令）负责传参；默认行为不变，存量测试不受影响。
- **[offline report 无数据]** 用户未先 `sync` 就跑 `report` → Mitigation：`report` 检测到缓存为空时打印清晰提示「请先运行 sync」而非报错崩溃。
- **[JSON 输出含 None]** `dataclasses.asdict()` 不自动序列化 `date`/`datetime`/`Enum` → Mitigation：自定义 `json_default` 序列化器处理这三类。
