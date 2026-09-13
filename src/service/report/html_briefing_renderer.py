"""将 BriefingView 渲染为自包含单文件 HTML（冷静金融 + 轻量可视化）。"""

from __future__ import annotations

import html
from typing import Any

from service.report.explainers import method_tip, tech_tip, tech_tip_key_for_text
from service.report.models.briefing_view import BriefingView, SectionStatus


def _esc(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}%"


def _num(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{value:.{digits}f}"


def _status_callout(key: str, status: SectionStatus | None) -> str:
    if status is None or status.status == "ok":
        if status and status.hint:
            return (
                f'<div class="callout info"><strong>{_esc(key)}</strong>：'
                f"{_esc(status.hint)}</div>"
            )
        return ""
    kind = "error" if status.status == "failed" else "warn"
    label = "失败" if status.status == "failed" else "未生成"
    return (
        f'<div class="callout {kind}">'
        f"<strong>{_esc(key)} · {label}</strong>"
        f"<p>{_esc(status.hint or '该区块不可用')}</p>"
        f"</div>"
    )


def _signal_badge(signal: str) -> str:
    mapping = {
        "强烈买入": "good",
        "买入": "good",
        "持有": "neutral",
        "观望": "neutral",
        "卖出": "bad",
        "强烈卖出": "bad",
        "低估": "good",
        "合理": "neutral",
        "高估": "bad",
        "未知": "neutral",
    }
    cls = mapping.get(signal, "neutral")
    return f'<span class="badge {cls}">{_esc(signal or "—")}</span>'


def _progress_bar(score: float | None, max_v: float = 100.0, css: str = "") -> str:
    if score is None:
        return '<div class="bar empty"><span>N/A</span></div>'
    width = max(0.0, min(100.0, (float(score) / max_v) * 100.0))
    return (
        f'<div class="bar {css}"><div class="bar-fill" style="width:{width:.1f}%"></div>'
        f'<span class="bar-label">{_esc(f"{score:.0f}" if max_v == 100 else f"{score:.1f}")}'
        f"</span></div>"
    )


def _fair_range_viz(
    price: float | None,
    low: float | None,
    base: float | None,
    high: float | None,
    mos: float | None,
) -> str:
    if low is None or high is None or high <= low:
        return f"<p>公允区间不可用 · MOS {_esc(_pct(mos))}</p>"
    span = high - low

    def pos(v: float | None) -> float:
        if v is None:
            return 50.0
        return max(0.0, min(100.0, ((v - low) / span) * 100.0))

    mark = pos(price)
    base_pct = pos(base)
    return f"""
    <div class="range-viz" title="现价相对公允区间">
      <div class="range-track">
        <div class="range-base" style="left:{base_pct:.1f}%"></div>
        <div class="range-price" style="left:{mark:.1f}%"></div>
      </div>
      <div class="range-labels">
        <span>低 {_esc(_num(low))}</span>
        <span>中 {_esc(_num(base))}</span>
        <span>高 {_esc(_num(high))}</span>
      </div>
      <p class="muted">现价 {_esc(_num(price))} · 安全边际 {_esc(_pct(mos))}</p>
    </div>
    """


def _evidence_bars(bull_n: int, bear_n: int) -> str:
    total = max(bull_n + bear_n, 1)
    bull_w = (bull_n / total) * 100
    bear_w = (bear_n / total) * 100
    return f"""
    <div class="evidence-bars">
      <div class="ebull" style="width:{bull_w:.1f}%">多方 {bull_n}</div>
      <div class="ebear" style="width:{bear_w:.1f}%">空方 {bear_n}</div>
    </div>
    """


def _evidence_list(items: list[dict[str, Any]], side: str) -> str:
    if not items:
        return "<p class='muted'>（空）</p>"
    lines = ["<ol class='evidence'>"]
    for item in items:
        idx = item.get("index", "?")
        text = item.get("text", "")
        lines.append(
            f"<li value='{_esc(idx)}'><span class='tag'>{_esc(side)}</span> {_esc(text)}</li>"
        )
    lines.append("</ol>")
    return "\n".join(lines)


def _click_tip(label: str, body: str, tip_id: str) -> str:
    """无外部 JS：details/summary 实现点击展开。"""
    return (
        f'<details class="tip" id="{_esc(tip_id)}">'
        f'<summary class="tip-q" title="点击查看说明">?</summary>'
        f'<div class="tip-body"><strong>{_esc(label)}</strong>'
        f"<p>{_esc(body)}</p></div></details>"
    )


def _method_tip_html(key: str, tip_id: str) -> str:
    meta = method_tip(key)
    body = f"{meta.get('what', '')} {meta.get('when', '')}".strip()
    return _click_tip(meta.get("name") or key, body, tip_id)


def _price_svg(
    series: list[dict[str, Any]],
    *,
    fair_low: float | None,
    fair_base: float | None,
    fair_high: float | None,
    price_high: float | None,
    price_low: float | None,
) -> str:
    if not series:
        return ""
    closes = [float(p["close"]) for p in series]
    y_vals = list(closes)
    for v in (fair_low, fair_base, fair_high):
        if v is not None:
            y_vals.append(float(v))
    y_min = min(y_vals)
    y_max = max(y_vals)
    if y_max <= y_min:
        y_max = y_min + 1.0
    pad = (y_max - y_min) * 0.08
    y_min -= pad
    y_max += pad

    w, h = 1100, 220
    ml, mr, mt, mb = 48, 24, 24, 36
    pw, ph = w - ml - mr, h - mt - mb
    n = len(closes)

    def x_at(i: int) -> float:
        if n == 1:
            return ml + pw / 2
        return ml + (i / (n - 1)) * pw

    def y_at(v: float) -> float:
        return mt + (1.0 - (v - y_min) / (y_max - y_min)) * ph

    pts = " ".join(f"{x_at(i):.1f},{y_at(c):.1f}" for i, c in enumerate(closes))
    lines: list[str] = [
        f'<svg class="price-svg" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="近{n}个交易日收盘价">'
    ]
    for val, label, dash in (
        (fair_high, "公允高", "6 4"),
        (fair_base, "公允中", "4 4"),
        (fair_low, "公允低", "6 4"),
    ):
        if val is None:
            continue
        yy = y_at(float(val))
        lines.append(
            f'<line class="fair-line" x1="{ml}" y1="{yy:.1f}" x2="{ml + pw}" y2="{yy:.1f}" '
            f'stroke-dasharray="{dash}"/>'
            f'<text class="fair-label" x="{ml + 4}" y="{yy - 4:.1f}">{_esc(label)} {_esc(_num(val))}</text>'
        )
    lines.append(f'<polyline class="price-line" fill="none" points="{pts}"/>')

    hi = price_high if price_high is not None else max(closes)
    lo = price_low if price_low is not None else min(closes)
    hi_i = closes.index(hi) if hi in closes else closes.index(max(closes))
    lo_i = closes.index(lo) if lo in closes else closes.index(min(closes))
    for i, label, cls in (
        (hi_i, f"高 {_num(hi)}", "ext-high"),
        (lo_i, f"低 {_num(lo)}", "ext-low"),
    ):
        cx, cy = x_at(i), y_at(closes[i])
        lines.append(
            f'<circle class="{cls}" cx="{cx:.1f}" cy="{cy:.1f}" r="4"/>'
            f'<text class="{cls}-label" x="{cx:.1f}" y="{cy - 8:.1f}">{_esc(label)}</text>'
        )
    lines.append(
        f'<text class="axis" x="{ml}" y="{h - 8}">{_esc(series[0].get("date"))}</text>'
        f'<text class="axis end" x="{ml + pw}" y="{h - 8}">{_esc(series[-1].get("date"))}</text>'
    )
    lines.append("</svg>")
    return "\n".join(lines)


_CSS = """
:root {
  --ink: #1f2933; --muted: #6b7280; --line: #e5e7eb; --paper: #f3f4f6;
  --card: #ffffff; --good: #047857; --bad: #b91c1c; --warn: #b45309;
  --accent: #1d4ed8; --bull-bg: #ecfdf5; --bear-bg: #fef2f2;
  --bull: #a7f3d0; --bear: #fecaca;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Source Han Sans SC", "Noto Sans SC", "PingFang SC", "Microsoft YaHei",
    system-ui, sans-serif;
  color: var(--ink); background: var(--paper); line-height: 1.55;
}
.wrap { max-width: 1240px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
header.hero {
  padding: 1.1rem 1.25rem; margin-bottom: 1.25rem;
  background: var(--card); border-radius: 4px; border: 1px solid var(--line);
  border-left: 4px solid var(--accent);
}
header.hero h1 { font-size: 1.75rem; margin: 0 0 0.35rem; font-weight: 650; }
.meta { color: var(--muted); font-size: 0.9rem; }
.badge {
  display: inline-block; padding: 0.15rem 0.55rem; border-radius: 3px;
  font-size: 0.82rem; border: 1px solid var(--line); margin-right: 0.35rem;
}
.badge.good { background: #ecfdf5; color: var(--good); border-color: #a7f3d0; }
.badge.bad { background: #fef2f2; color: var(--bad); border-color: #fecaca; }
.badge.neutral { background: #f3f4f6; color: #374151; }
section {
  background: var(--card); border: 1px solid var(--line); padding: 1rem 1.2rem;
  margin: 1rem 0; border-radius: 4px;
}
section h2 {
  font-size: 1.12rem; margin: 0 0 0.75rem; color: var(--ink);
  border-left: 3px solid var(--accent); padding-left: 0.55rem; font-weight: 650;
}
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.85rem; }
@media (max-width: 900px) {
  .grid3 { grid-template-columns: 1fr; }
  .evidence-cols { grid-template-columns: 1fr !important; }
}
.mini { border: 1px solid var(--line); padding: 0.75rem; background: #fafafa; border-radius: 3px; }
.mini h3 { margin: 0 0 0.4rem; font-size: 0.95rem; }
.bar {
  position: relative; height: 1.1rem; background: #e5e7eb; border-radius: 2px; overflow: hidden;
  margin: 0.35rem 0;
}
.bar-fill { height: 100%; background: var(--accent); }
.bar.warn .bar-fill { background: #d97706; }
.bar-label {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; color: #111;
}
.range-viz { margin: 0.4rem 0; }
.range-track {
  position: relative; height: 10px;
  background: linear-gradient(90deg, #a7f3d0, #fde68a, #fecaca);
  border: 1px solid var(--line); border-radius: 2px;
}
.range-base, .range-price {
  position: absolute; top: -3px; width: 2px; height: 16px; background: #334155;
}
.range-price { background: var(--accent); width: 3px; }
.range-labels { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--muted); }
.price-context .price-meta { margin: 0.25rem 0 0.6rem; }
.price-svg { width: 100%; height: auto; background: #fafafa; border: 1px solid var(--line); border-radius: 3px; }
.price-line { stroke: var(--accent); stroke-width: 2.2; }
.fair-line { stroke: #94a3b8; stroke-width: 1.2; }
.fair-label { font-size: 10px; fill: #64748b; }
.ext-high { fill: var(--good); }
.ext-low { fill: var(--bad); }
.ext-high-label, .ext-low-label { font-size: 11px; text-anchor: middle; fill: var(--ink); }
.axis { font-size: 11px; fill: var(--muted); }
.axis.end { text-anchor: end; }
.evidence-bars { display: flex; height: 1.4rem; margin: 0.5rem 0; border: 1px solid var(--line); border-radius: 2px; overflow: hidden; }
.ebull { background: var(--bull); display: flex; align-items: center; justify-content: center; font-size: 0.8rem; }
.ebear { background: var(--bear); display: flex; align-items: center; justify-content: center; font-size: 0.8rem; }
.evidence-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.5rem; }
.col-bull { background: var(--bull-bg); border: 1px solid #a7f3d0; border-radius: 4px; padding: 0.75rem; }
.col-bear { background: var(--bear-bg); border: 1px solid #fecaca; border-radius: 4px; padding: 0.75rem; }
.col-bull h3, .col-bear h3 { margin: 0 0 0.5rem; font-size: 1rem; }
ol.evidence { padding-left: 1.3rem; margin: 0; }
ol.evidence li { margin: 0.35rem 0; }
.tag { font-size: 0.7rem; color: var(--muted); margin-right: 0.25rem; }
.callout {
  border-left: 4px solid var(--line); background: #f8fafc; padding: 0.65rem 0.8rem; margin: 0.6rem 0;
}
.callout.error { border-color: var(--bad); background: #fef2f2; }
.callout.warn { border-color: var(--warn); background: #fffbeb; }
.callout.info { border-color: var(--accent); background: #eff6ff; }
.callout p { margin: 0.25rem 0 0; }
details { margin: 0.5rem 0; }
summary { cursor: pointer; font-weight: 600; }
details.tip {
  display: inline-block; margin: 0 0 0 0.25rem; vertical-align: middle; position: relative;
}
details.tip > summary.tip-q {
  list-style: none; display: inline-flex; align-items: center; justify-content: center;
  width: 1.05rem; height: 1.05rem; border-radius: 50%; border: 1px solid var(--accent);
  color: var(--accent); font-size: 0.72rem; font-weight: 700; cursor: pointer;
  background: #eff6ff;
}
details.tip > summary.tip-q::-webkit-details-marker { display: none; }
details.tip[open] > .tip-body {
  display: block; position: absolute; z-index: 20; left: 0; top: 1.4rem;
  min-width: 220px; max-width: 320px; padding: 0.55rem 0.7rem;
  background: #fff; border: 1px solid var(--line); border-radius: 4px;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12); font-weight: 400; font-size: 0.82rem;
}
details.tip > .tip-body { display: none; }
details.tip .tip-body p { margin: 0.3rem 0 0; color: var(--muted); }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { border-bottom: 1px solid var(--line); padding: 0.4rem 0.45rem; text-align: left; }
.muted { color: var(--muted); font-size: 0.9rem; }
footer { margin-top: 2rem; color: var(--muted); font-size: 0.85rem; border-top: 1px solid var(--line); padding-top: 0.75rem; }
"""


class HtmlBriefingRenderer:
    """BriefingView → 自包含 HTML。"""

    def render(self, view: BriefingView) -> str:
        ss = view.section_statuses
        bull_n = len(view.bull_evidence)
        bear_n = len(view.bear_evidence)

        narrative_html = self._narrative_block(view)
        persona_html = self._persona_block(view)
        value_deep = self._value_deep(view)
        tech_deep = self._tech_deep(view)
        price_block = self._price_context(view)

        body = f"""
<div class="wrap">
  <header class="hero">
    <h1>{_esc(view.code)} {_esc(view.name)}</h1>
    <div class="meta">数据时点 {_esc(view.data_timestamp)}
      · confrontation_id={_esc(view.confrontation_id)}</div>
    <p>
      {_signal_badge(view.combined_signal)}
      {_signal_badge(view.value_rating)}
    </p>
    <p><strong>冲突摘要：</strong>{_esc(view.conflict_summary)}</p>
  </header>

  {price_block}

  <section id="scan">
    <h2>一、三维快扫</h2>
    <div class="grid3">
      <div class="mini">
        <h3>价值面</h3>
        {_status_callout("价值面", ss.get("value"))}
        <p>原型 {_esc(view.value_prototype)} · 置信度 {_esc(view.value_confidence)}</p>
        <p>{_esc(view.value_assessment)}</p>
        {_fair_range_viz(view.current_price, view.fair_low, view.fair_base, view.fair_high, view.margin_of_safety)}
      </div>
      <div class="mini">
        <h3>技术面</h3>
        {_status_callout("技术面", ss.get("tech"))}
        <p>{_esc(view.tech_trend)} · {_esc(view.tech_signal)}</p>
        <p>评分</p>
        {_progress_bar(float(view.tech_score) if view.tech_score is not None else None)}
      </div>
      <div class="mini">
        <h3>情绪面</h3>
        {_status_callout("情绪面", ss.get("sentiment"))}
        <p>{_esc(view.sentiment_status) or _esc(view.sentiment_note)}</p>
        <p>恐慌贪婪代理</p>
        {_progress_bar(view.sentiment_score, css="warn")}
      </div>
    </div>
  </section>

  <section id="conflict">
    <h2>二、冲突与立场</h2>
    {_status_callout("证据", ss.get("evidence"))}
    {_evidence_bars(bull_n, bear_n)}
    <div class="evidence-cols">
      <div class="col-bull">
        <h3>多方证据（{bull_n}）</h3>
        {_evidence_list(view.bull_evidence, "bull")}
      </div>
      <div class="col-bear">
        <h3>空方证据（{bear_n}）</h3>
        {_evidence_list(view.bear_evidence, "bear")}
      </div>
    </div>
    {narrative_html}
    {persona_html}
  </section>

  <section id="value-deep">
    <h2>三、价值面深潜</h2>
    <details>
      <summary>展开估值方法与警告</summary>
      {value_deep}
    </details>
  </section>

  <section id="tech-deep">
    <h2>四、技术面深潜</h2>
    <details>
      <summary>展开指标、布林带与 K 线形态</summary>
      {tech_deep}
    </details>
  </section>

  <section id="decision">
    <h2>五、决策痕迹</h2>
    {_status_callout("Checklist", ss.get("checklist"))}
    <p>{_esc(view.checklist_summary) or "（无 Checklist 摘要）"}</p>
    {_status_callout("Declare", ss.get("declare"))}
    <p>{_esc(view.declare_summary) or "（无 Declare 摘要）"}</p>
  </section>

  <footer>
    <p>{_esc(view.disclaimer)}</p>
    <p class="muted">stock_copilot · report briefing · 本地静态 HTML</p>
  </footer>
</div>
"""
        return (
            "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
            "<meta charset=\"utf-8\"/>\n"
            f"<title>深度复盘 {_esc(view.code)} {_esc(view.name)}</title>\n"
            f"<style>{_CSS}</style>\n"
            "</head>\n<body>\n"
            f"{body}\n"
            "</body>\n</html>\n"
        )

    def _price_context(self, view: BriefingView) -> str:
        callout = _status_callout("价格情境", view.section_statuses.get("price_context"))
        if not view.price_series:
            return (
                '<section id="price-context" class="price-context">'
                f"<h2>价格情境</h2>{callout}</section>"
            )
        first = float(view.price_series[0]["close"])
        last = float(view.price_series[-1]["close"])
        change = ""
        if first:
            pct = (last - first) / first * 100
            change = f" · 区间涨跌 {_esc(_pct(pct))}"
        svg = _price_svg(
            view.price_series,
            fair_low=view.fair_low,
            fair_base=view.fair_base,
            fair_high=view.fair_high,
            price_high=view.price_high,
            price_low=view.price_low,
        )
        return f"""
  <section id="price-context" class="price-context">
    <h2>价格情境</h2>
    {callout}
    <p class="price-meta">现价 <strong>{_esc(_num(view.current_price))}</strong>
      · 近 {len(view.price_series)} 交易日 高 {_esc(_num(view.price_high))} / 低 {_esc(_num(view.price_low))}{change}
      · 虚线为公允低/中/高</p>
    {svg}
  </section>
"""

    def _narrative_block(self, view: BriefingView) -> str:
        callout = _status_callout("互驳叙事", view.section_statuses.get("narrative"))
        if not view.narrative:
            return f"<div>{callout}</div>"
        n = view.narrative
        rebut_b = "".join(
            f"<li>针对空方 [{_esc(r.get('target_index'))}]：{_esc(r.get('text'))}</li>"
            for r in (n.get("bull_rebuttals") or [])
        ) or "<li class='muted'>（空）</li>"
        rebut_e = "".join(
            f"<li>针对多方 [{_esc(r.get('target_index'))}]：{_esc(r.get('text'))}</li>"
            for r in (n.get("bear_rebuttals") or [])
        ) or "<li class='muted'>（空）</li>"
        return f"""
        {callout}
        <details open>
          <summary>LLM 互驳叙事</summary>
          <h4>多方论述</h4><p>{_esc(n.get("bull_thesis"))}</p>
          <h4>空方论述</h4><p>{_esc(n.get("bear_thesis"))}</p>
          <h4>多方反驳</h4><ul>{rebut_b}</ul>
          <h4>空方反驳</h4><ul>{rebut_e}</ul>
          <p class="muted">{_esc(n.get("disclaimer"))}</p>
        </details>
        """

    def _persona_block(self, view: BriefingView) -> str:
        callout = _status_callout("Persona", view.section_statuses.get("persona"))
        payload = view.persona_stress or {}
        personas = payload.get("personas") or []
        if not personas:
            return f"<div>{callout}</div>"
        labels = {
            "value_quality": "价值质量",
            "trend_momentum": "趋势动量",
            "risk_governor": "风控官",
        }
        chunks = [callout, "<details><summary>Persona 三镜头</summary>"]
        for entry in personas:
            pid = entry.get("id", "?")
            status = entry.get("status", "?")
            out = entry.get("output") or {}
            chunks.append(
                f"<h4>{_esc(labels.get(str(pid), str(pid)))} · {_esc(status)}</h4>"
            )
            if status == "failed":
                chunks.append(
                    f"<div class='callout error'>失败：{_esc(entry.get('error') or '未知错误')}</div>"
                )
            elif status == "pending":
                chunks.append("<p class='muted'>待 narrate</p>")
            else:
                chunks.append(f"<p>{_esc(out.get('lens_summary'))}</p>")
        chunks.append(f"<p class='muted'>{_esc(payload.get('disclaimer'))}</p></details>")
        return "\n".join(chunks)

    def _value_deep(self, view: BriefingView) -> str:
        rows = []
        for i, r in enumerate(view.value_method_rows):
            key = str(r.get("key") or "")
            tip = _method_tip_html(key, f"vm-{i}") if key else ""
            rows.append(
                "<tr>"
                f"<td>{_esc(key)} {tip}</td>"
                f"<td>{_esc(_num(r.get('fair_value') if isinstance(r.get('fair_value'), (int, float)) else None))}</td>"
                f"<td>{_esc(r.get('label'))}</td>"
                f"<td>{_esc(r.get('applicable'))}</td>"
                "</tr>"
            )
        table = (
            "<table><thead><tr><th>方法</th><th>公允价</th><th>评估</th><th>适用</th></tr></thead>"
            f"<tbody>{''.join(rows) or '<tr><td colspan=4>无方法明细</td></tr>'}</tbody></table>"
        )
        warns = (
            "".join(f"<li>{_esc(w)}</li>" for w in view.value_warnings)
            or "<li class='muted'>无</li>"
        )
        return f"{table}<h4>警告</h4><ul>{warns}</ul>"

    def _tech_deep(self, view: BriefingView) -> str:
        reasons = []
        for i, x in enumerate(view.tech_reasons):
            key = tech_tip_key_for_text(x)
            note = tech_tip(key) if key else None
            if note:
                reasons.append(
                    f"<li>{_esc(x)} {_click_tip('术语说明', note, f'tr-{i}')}</li>"
                )
            else:
                reasons.append(f"<li>{_esc(x)}</li>")
        reasons_html = "".join(reasons) or "<li class='muted'>无</li>"

        risks = []
        for i, x in enumerate(view.tech_risks):
            key = tech_tip_key_for_text(x)
            note = tech_tip(key) if key else None
            if note:
                risks.append(
                    f"<li>{_esc(x)} {_click_tip('术语说明', note, f'risk-{i}')}</li>"
                )
            else:
                risks.append(f"<li>{_esc(x)}</li>")
        risks_html = "".join(risks) or "<li class='muted'>无</li>"

        boll_tip = _click_tip("布林带", tech_tip("boll") or "", "boll-tip")
        boll = (
            f"<p>布林带 {boll_tip}：中轨 {_esc(_num(view.boll_mid))} · 上 {_esc(_num(view.boll_upper))} · "
            f"下 {_esc(_num(view.boll_lower))} · 带宽 {_esc(_pct((view.boll_bandwidth or 0) * 100 if view.boll_bandwidth is not None and view.boll_bandwidth < 2 else view.boll_bandwidth))} · "
            f"百分位 {_esc(_num(view.boll_percentile, 0))}% · {_esc(view.boll_status)}</p>"
        )
        pat_tip = _click_tip("K 线形态", tech_tip("pattern") or "", "pat-tip")
        pats = "".join(
            f"<li>{_esc(p.get('trade_date'))} {_esc(p.get('pattern'))}（{_esc(p.get('direction'))}）："
            f"{_esc(p.get('description'))}</li>"
            for p in view.candlestick_patterns
        ) or "<li class='muted'>无形态命中</li>"
        return (
            f"<h4>信号理由</h4><ul>{reasons_html}</ul>"
            f"<h4>风险</h4><ul>{risks_html}</ul>"
            f"{boll}"
            f"<h4>K 线形态 {pat_tip}</h4><ul>{pats}</ul>"
        )
