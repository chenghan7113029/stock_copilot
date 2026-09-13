## Context

`report briefing`（`add-html-briefing-report`）已交付自包含 HTML Briefing Pack。本变更只打磨桌面阅读 UX：价格情境、多空分栏、点击讲解、版心与冷静金融主题。继续遵守：Composer 只组装不重算；无 CDN；讲解文案复用 `explainers.py`。

## Goals / Non-Goals

**Goals:**

- Hero 后插入「价格情境」：现价 + 近 10 交易日收盘 SVG 折线 + 公允 low/base/high 虚线 + 高低点标注
- 冲突与立场：桌面左右分栏（多方左 / 空方右）；叙事与 Persona 全宽在下
- 价值方法 / 技术术语旁可点击「？」展开说明与适用场景
- 版心 ~1240px；冷静金融视觉（白底、冷灰、克制蓝强调、克制红绿）

**Non-Goals:**

- 新 CLI 子命令或改变默认 narrate / `--no-narrate` 语义
- CDN 图表库、Web 服务、暗色主题切换、打印优化专项
- 把 trade-review / portfolio / 多票汇总塞进 briefing
- 重写 explainers 词典体系（仅允许按需补 boll/形态等缺失词条）

## Decisions

### 决策 1：10 交易日序列来自本地 K 线

**选择：** Composer 经既有 K 线读取路径（如 `KlineRepo` / Tech 同源缓存）取最近 **10 条有收盘价的交易日**（按日期升序），写入 `BriefingView.price_series: list[{date, close}]`。点数不足时仍渲染可得点数并 `section_statuses["price_context"] = missing/ok` 带 hint。

**理由：** Owner 明确要交易日而非日历 14 天；只读本地，符合离线 briefing。

**备选：** 日历 14 天 — 拒绝（周末空洞）。

### 决策 2：价格图 = 内联 SVG，公允虚线 + 高低点

**选择：** Renderer 用纯 SVG polyline；Y 轴 span 覆盖收盘序列 **与** fair_low/base/high（若存在），避免现价远低于公允时虚线挤在图外。虚线三档：low / base / high；在序列 max/min 收盘处画标记与短标签。无公允区间时只画折线 + 高低点。

**理由：** 零依赖、双击可开；与既有「无 CDN」一致。

**备选：** Chart.js CDN — 拒绝。

### 决策 3：多空左右分栏，叙事全宽

**选择：** `#conflict` 内证据区 `display:grid; grid-template-columns: 1fr 1fr`（窄屏单列）；左侧 bull、右侧 bear；互驳 / Persona 在证据网格下方全宽。条数极不对称时允许自然不等高，不做强制等高滚动（V1）。

**理由：** 桌面醒目；叙事左右跳读成本高。

### 决策 4：点击展开 tip，文案复用 explainers

**选择：** 「？」为 `<button type="button">`，点击切换相邻 tip 面板显隐（纯 CSS `:checked` + checkbox 或极简内联 `<script>` 亦可；优先 **无 JS 的 details/summary 或 checkbox hack**，保证本地 file:// 可用）。文案：

- 估值方法：`_METHOD_META[key]` 的 name / what / when
- 技术术语：`_TECH_NOTES` + 按需补 `boll` / 常见形态；对 signal_reasons 中可识别关键词挂 tip

**理由：** Owner 要点击交互；复用已有讲解真源，避免双文案。

### 决策 5：冷静金融主题 + 1240 版心

**选择：** CSS 变量重置为白/近白纸面、冷灰正文、深蓝强调（非紫）、多空绿/红降低饱和；`max-width: 1240px`；无衬线中文优先栈（如 Source Han Sans / system-ui），弱化米黄宋体「旧研报」感。

**理由：** Owner 选定冷静金融 + 1240。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 现价远低于公允 → 折线贴底、虚线占满上半 | Y 域合并序列与公允；图例标明虚线含义 |
| K 线不足 10 根 | 降级渲染 + hint「K 线不足 10 日，请 sync」 |
| tip 文案与 MD 报告略有出入 | 同源 `explainers`；补词条时两边一起受益 |
| 无 JS 的 tip 在部分浏览器样式怪 | 优先 `<details>`；测试 Chromium/Edge file:// |

## Migration Plan

- 无数据迁移；旧 HTML 不兼容保证，重新跑 `report briefing` 即可
- 文档：user-guide §4.4c 补价格情境与「？」说明

## Open Questions

- （无阻塞）窄屏断点是否 900px 切单列 — 实现时取合理默认即可
