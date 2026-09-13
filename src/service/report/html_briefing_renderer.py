"""将 BriefingView 渲染为自包含单文件 HTML（研报风 + 轻量可视化）。"""

from __future__ import annotations

import html
from typing import Any

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
        lines.append(f"<li value='{_esc(idx)}'><span class='tag'>{_esc(side)}</span> {_esc(text)}</li>")
    lines.append("</ol>")
    return "\n".join(lines)


_CSS = """
:root {
  --ink: #1a1a1a; --muted: #666; --line: #d8d4cc; --paper: #f7f4ef;
  --card: #fffdf9; --good: #1b6b3a; --bad: #8b1e1e; --warn: #8a5a00;
  --accent: #2c4a6e; --bull: #c8e6c9; --bear: #ffcdd2;
}
* { box-sizing: border-box; }
body {
  margin: 0; font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", Georgia, serif;
  color: var(--ink); background: var(--paper); line-height: 1.55;
}
.wrap { max-width: 920px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
header.hero {
  border-bottom: 2px solid var(--ink); padding-bottom: 1rem; margin-bottom: 1.5rem;
}
header.hero h1 { font-size: 1.85rem; margin: 0 0 0.35rem; letter-spacing: 0.02em; }
.meta { color: var(--muted); font-size: 0.92rem; }
.badge {
  display: inline-block; padding: 0.15rem 0.55rem; border-radius: 2px;
  font-size: 0.85rem; border: 1px solid var(--line); margin-right: 0.35rem;
}
.badge.good { background: #e8f5e9; color: var(--good); border-color: #a5d6a7; }
.badge.bad { background: #ffebee; color: var(--bad); border-color: #ef9a9a; }
.badge.neutral { background: #eee; color: #444; }
section {
  background: var(--card); border: 1px solid var(--line); padding: 1rem 1.1rem;
  margin: 1rem 0; border-radius: 2px;
}
section h2 {
  font-size: 1.15rem; margin: 0 0 0.75rem; border-left: 4px solid var(--accent);
  padding-left: 0.55rem;
}
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; }
@media (max-width: 720px) { .grid3 { grid-template-columns: 1fr; } }
.card mini, .mini {
  border: 1px solid var(--line); padding: 0.75rem; background: #fff;
}
.mini h3 { margin: 0 0 0.4rem; font-size: 0.95rem; }
.bar {
  position: relative; height: 1.1rem; background: #eceae4; border-radius: 2px; overflow: hidden;
  margin: 0.35rem 0;
}
.bar-fill { height: 100%; background: var(--accent); }
.bar.good .bar-fill { background: var(--good); }
.bar.warn .bar-fill { background: #c48a1a; }
.bar-label {
  position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
  font-size: 0.75rem; color: #111;
}
.range-viz { margin: 0.4rem 0; }
.range-track {
  position: relative; height: 10px; background: linear-gradient(90deg, #c8e6c9, #fff59d, #ffcdd2);
  border: 1px solid var(--line); border-radius: 2px;
}
.range-base, .range-price {
  position: absolute; top: -3px; width: 2px; height: 16px; background: #333;
}
.range-price { background: var(--accent); width: 3px; }
.range-labels { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--muted); }
.evidence-bars { display: flex; height: 1.4rem; margin: 0.5rem 0; border: 1px solid var(--line); }
.ebull { background: var(--bull); display: flex; align-items: center; justify-content: center; font-size: 0.8rem; }
.ebear { background: var(--bear); display: flex; align-items: center; justify-content: center; font-size: 0.8rem; }
ol.evidence { padding-left: 1.3rem; }
ol.evidence li { margin: 0.35rem 0; }
.tag { font-size: 0.7rem; color: var(--muted); margin-right: 0.25rem; }
.callout {
  border-left: 4px solid var(--line); background: #f3f1eb; padding: 0.65rem 0.8rem; margin: 0.6rem 0;
}
.callout.error { border-color: var(--bad); background: #fce8e8; }
.callout.warn { border-color: var(--warn); background: #fff6e0; }
.callout.info { border-color: var(--accent); background: #eef3f8; }
.callout p { margin: 0.25rem 0 0; }
details { margin: 0.5rem 0; }
summary { cursor: pointer; font-weight: 600; }
table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
th, td { border-bottom: 1px solid var(--line); padding: 0.35rem 0.4rem; text-align: left; }
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
    <h3>多方证据（{bull_n}）</h3>
    {_evidence_list(view.bull_evidence, "bull")}
    <h3>空方证据（{bear_n}）</h3>
    {_evidence_list(view.bear_evidence, "bear")}
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
            chunks.append(f"<h4>{_esc(labels.get(str(pid), str(pid)))} · {_esc(status)}</h4>")
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
        for r in view.value_method_rows:
            rows.append(
                "<tr>"
                f"<td>{_esc(r.get('key'))}</td>"
                f"<td>{_esc(_num(r.get('fair_value') if isinstance(r.get('fair_value'), (int, float)) else None))}</td>"
                f"<td>{_esc(r.get('label'))}</td>"
                f"<td>{_esc(r.get('applicable'))}</td>"
                "</tr>"
            )
        table = (
            "<table><thead><tr><th>方法</th><th>公允价</th><th>评估</th><th>适用</th></tr></thead>"
            f"<tbody>{''.join(rows) or '<tr><td colspan=4>无方法明细</td></tr>'}</tbody></table>"
        )
        warns = "".join(f"<li>{_esc(w)}</li>" for w in view.value_warnings) or "<li class='muted'>无</li>"
        return f"{table}<h4>警告</h4><ul>{warns}</ul>"

    def _tech_deep(self, view: BriefingView) -> str:
        reasons = "".join(f"<li>{_esc(x)}</li>" for x in view.tech_reasons) or "<li class='muted'>无</li>"
        risks = "".join(f"<li>{_esc(x)}</li>" for x in view.tech_risks) or "<li class='muted'>无</li>"
        boll = (
            f"<p>布林带：中轨 {_esc(_num(view.boll_mid))} · 上 {_esc(_num(view.boll_upper))} · "
            f"下 {_esc(_num(view.boll_lower))} · 带宽 {_esc(_pct((view.boll_bandwidth or 0) * 100 if view.boll_bandwidth is not None and view.boll_bandwidth < 2 else view.boll_bandwidth))} · "
            f"百分位 {_esc(_num(view.boll_percentile, 0))}% · {_esc(view.boll_status)}</p>"
        )
        pats = "".join(
            f"<li>{_esc(p.get('trade_date'))} {_esc(p.get('pattern'))}（{_esc(p.get('direction'))}）："
            f"{_esc(p.get('description'))}</li>"
            for p in view.candlestick_patterns
        ) or "<li class='muted'>无形态命中</li>"
        return (
            f"<h4>信号理由</h4><ul>{reasons}</ul>"
            f"<h4>风险</h4><ul>{risks}</ul>"
            f"{boll}"
            f"<h4>K 线形态</h4><ul>{pats}</ul>"
        )
