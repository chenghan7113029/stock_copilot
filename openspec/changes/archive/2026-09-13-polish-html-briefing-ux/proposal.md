## Why

`report briefing` 已能产出自包含 HTML，但桌面深读体验仍偏弱：缺少近端价格情境、多空证据上下堆叠不醒目、估值/技术术语无可点讲解、版心过窄（~920px）、米黄研报配色观感不佳。Owner 已确认用「冷静金融」桌面风格做一轮 UX 打磨，提升周末复盘可读性。

## What Changes

- 在 Hero 之后、三维快扫之前新增 **价格情境** 区块：现价 + **最近 10 个交易日**收盘折线；叠加公允区间（low/base/high）**虚线**；标注区间内 **最高/最低** 点
- **冲突与立场**：桌面左右分栏（多方左 / 空方右）；互驳叙事与 Persona 仍全宽置于证据下方
- 价值深潜估值方法行、技术深潜术语旁增加 **可点击「？」**，展开方法/术语的说明与适用场景（复用 `explainers` 词典，不新造文案源）
- 版心加宽至约 **1240px**；视觉改为 **冷静金融**（白底、冷灰字、克制蓝强调、克制红绿多空）
- **非 BREAKING**：CLI 参数与默认 narrate 行为不变；无 CDN、仍自包含单文件 HTML

## Capabilities

### New Capabilities

- （无）本变更在既有 Briefing Pack 上增强 UX，不引入新能力域

### Modified Capabilities

- `html-briefing-report`：增加价格情境（10 交易日 + 公允虚线 + 高低点）、多空左右分栏、点击式讲解 tip、版心与冷静金融视觉要求
- `cli-report-briefing`：输出 HTML 须符合上述 UX 要求（命令面不变；若需文档示例可顺带更新 user-guide 截图式描述）

## Impact

- **代码**：`BriefingView` / `BriefingComposer`（注入近 10 日 K 线收盘序列）；`HtmlBriefingRenderer`（SVG sparkline、双栏、tooltip、主题 CSS）；复用 `service/report/explainers.py` 的 `_METHOD_META` / `_TECH_NOTES`（可小幅补 boll/形态词条）
- **数据**：只读 `KlineRepo` 本地缓存，不联网、不重算估值
- **文档**：`docs/user-guide.md` §4.4c 补充价格情境与交互说明；`docs/mrd/roadmap-todo.md` 变更记录；工程约定一般无需改目录（无新顶层模块）
- **测试**：renderer/composer 单测覆盖新区块结构与 tip 文案；全量 `pytest -q -m "not network"`
