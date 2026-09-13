## 1. Composer / View：价格序列

- [x] 1.1 Modify `BriefingView`：增加 `price_series`（date/close 列表）、可选 `price_high`/`price_low` 摘要字段；`section_statuses["price_context"]`
- [x] 1.2 Modify `BriefingComposer`：从本地 K 线读取最近至多 10 个交易日收盘（升序）；不足时降级 + hint；不联网
- [x] 1.3 Test composer：有 ≥10 根 K 线时 series 长度为 10；不足时仍成功且 status/hint 合理

## 2. Renderer：布局与可视化

- [x] 2.1 Modify `HtmlBriefingRenderer`：Hero 后插入价格情境 SVG（折线 + 公允虚线 low/base/high + 高低点标注）；无 CDN
- [x] 2.2 Modify renderer：冲突与立场证据左右分栏（多方左/空方右）；叙事与 Persona 全宽在下；窄屏单列
- [x] 2.3 Modify renderer：价值方法行 / 技术术语旁可点击「？」；文案来自 `explainers`（按需补 boll/形态词条）；优先无外部 JS
- [x] 2.4 Modify renderer CSS：版心约 1240px；冷静金融主题（白底、冷灰、克制蓝/红绿）
- [x] 2.5 Test renderer：含价格情境结构类名、双栏标记、问号/ tip 文案、max-width≥1200、无 chart CDN

## 3. 文档

- [x] 3.1 Modify `docs/user-guide.md` §4.4c：价格情境、左右证据、点击「？」、版式说明
- [x] 3.2 Modify `docs/mrd/roadmap-todo.md`：登记本 UX 打磨变更记录

## 4. 验证与归档

- [x] 4.1 Run 相关单测（composer/renderer/cli briefing）`-q` 并通过
- [x] 4.2 Run `pytest -q -m "not network"` 并通过（保留输出）
- [x] 4.3 手工：`report briefing 600036 --no-narrate -o reports/…` 浏览器核对曲线/分栏/问号/配色宽度
- [x] 4.4 Archive：`/opsx-archive`（验证门禁通过后）
