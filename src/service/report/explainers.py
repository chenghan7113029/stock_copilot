"""报告内嵌讲解：技术指标注释、估值方法卡片、价值陷阱拆解。

安全边际（margin_of_safety）约定为**百分数点**：
例如 7.14 表示 7.14%，展示时用 format_mos_percent_points，禁止对该字段使用 :.1%。
"""

from __future__ import annotations

from typing import Any

from service.tech.models.tech_result import TechAnalysisResult
from service.value.models.analysis_result import ValueAnalysisResult
from service.value.valuation.base import ValuationResult

# ── MOS ──────────────────────────────────────────────────────────────────────


def format_mos_percent_points(mos: float | None) -> str:
    """将百分数点 MOS 格式化为带 % 的字符串；None → N/A。"""
    if mos is None:
        return "N/A"
    return f"{mos:.1f}%"


# ── 评估词中文化 ─────────────────────────────────────────────────────────────

_ASSESSMENT_ZH: dict[str, str] = {
    "undervalued": "低估",
    "overvalued": "高估",
    "fair": "合理",
    "fairly valued": "合理",
    "not applicable": "不适用",
    "applicable": "适用",
    "limited": "有限适用",
    "low value trap risk": "价值陷阱风险低",
    "medium value trap risk": "价值陷阱风险中等",
    "high value trap risk": "价值陷阱风险高",
    "low bankruptcy risk": "破产风险低",
    "high bankruptcy risk": "破产风险高",
    "insufficient data for full assessment": "数据不足，无法完整评估",
}


def assessment_to_zh(text: str | None) -> str:
    if not text:
        return "N/A"
    key = text.strip().lower()
    if key in _ASSESSMENT_ZH:
        return _ASSESSMENT_ZH[key]
    for en, zh in sorted(_ASSESSMENT_ZH.items(), key=lambda x: -len(x[0])):
        if en in key:
            idx = key.find(en)
            return text[:idx] + zh + text[idx + len(en) :]
    return text


def applicability_to_zh(text: str | None) -> str:
    if not text:
        return "N/A"
    return _ASSESSMENT_ZH.get(text.strip().lower(), text)


# ── 技术指标词典 ─────────────────────────────────────────────────────────────

_TECH_NOTES: dict[str, str] = {
    "ma": (
        "均线（MA）：一段时间收盘价的平均值，用来看趋势方向。"
        "短期均线在长期均线上方且发散，常称多头排列；反之为空头排列。"
    ),
    "macd": (
        "MACD：用快慢指数均线差值看动量。"
        "多头/金叉偏向上涨动能，空头/死叉偏向下跌动能；适合辅助趋势，不宜单独下单。"
    ),
    "rsi": (
        "RSI（相对强弱）：衡量近端涨跌速度，常见区间 0–100。"
        "通常 >70 偏超买（短线回调风险↑），<30 偏超卖；本报告同时给出 6/12/24 日。"
    ),
    "kdj": (
        "KDJ：另一套超买超卖指标。K/D 很高或 J>100 常表示短线过热；"
        "J 超界并不等于立刻必须卖出，需结合趋势与量能。"
    ),
    "volume": (
        "量能/量比：成交量相对近期是否放大。"
        "放量配合突破更有说服力；缩量上涨或放量下跌需提高警惕。"
    ),
    "bias": (
        "乖离率（Bias）：现价相对均线偏离多少。"
        "偏离过大时短线回归均线的概率上升，常用于控制追高/杀跌节奏。"
    ),
    "chip": (
        "筹码分布：按持仓成本估算的结构（非逐账户明细）。"
        "获利比例高可能意味抛压；套牢比例高可能意味反弹卖压。V1 不计入综合评分。"
    ),
    "support": (
        "支撑/压力：近期价格曾获得买盘/卖盘集中的价位区域，仅供参考，可被放量突破。"
    ),
    "boll": (
        "布林带：中轨为均线，上下轨为均线 ± N×标准差。"
        "带宽收窄常表示波动率低位、后续可能放大；触及上/下轨需结合趋势，不宜单独当作买卖信号。"
    ),
    "pattern": (
        "K 线形态：用单根或多根蜡烛的实体与影线结构识别短线转折/延续线索。"
        "命中仅作提示，不参与综合评分，需结合量能与趋势确认。"
    ),
    "trend": (
        "趋势/多空排列：均线多头排列偏顺势做多语境，空头排列偏顺势做空或观望。"
        "排列描述趋势结构，不等于即时下单点。"
    ),
}


def render_tech_explanations(result: TechAnalysisResult) -> list[str]:
    """按报告中实际出现的区块输出指标说明。"""
    keys: list[str] = ["ma", "macd", "rsi", "kdj", "volume", "bias"]
    if result.support_levels or result.resistance_levels:
        keys.append("support")
    if result.winner_ratio is not None:
        keys.append("chip")

    lines = ["", "## 指标说明（本次报告）", ""]
    for key in keys:
        note = _TECH_NOTES.get(key)
        if note:
            lines.append(f"- {note}")
    return lines


# ── 估值方法元数据与入参来源 ─────────────────────────────────────────────────

_METHOD_META: dict[str, dict[str, str]] = {
    "ddm": {
        "name": "股息贴现 DDM（Gordon）",
        "what": "把预期股息按要求回报率贴现，得到今天的合理股价。",
        "when": "适用：分红稳定、可预测的公司（高股息原型常用）。不适用：长期不分红或增长极不稳定。",
    },
    "two_stage_ddm": {
        "name": "两阶段股息贴现",
        "what": "先按较高增长阶段估算股息，再进入永续增长阶段并贴现。",
        "when": "适用：股息将经历一段较快增长后再放缓。不适用：无分红或无法估计分段增长。",
    },
    "epv": {
        "name": "盈利力价值 EPV（零增长）",
        "what": "假设利润不再增长，仅把维持性盈利资本化，得到偏保守的「地板价」。",
        "when": "适用：成熟稳定生意的下限锚定。不适用：高成长或盈利剧烈波动期。",
    },
    "owner_earnings": {
        "name": "所有者收益法",
        "what": "用自由现金流/所有者收益资本化，估算股东可拿走的长期价值。",
        "when": "适用：现金流质量较好的公司。不适用：长期负自由现金流且无改善路径。",
    },
    "dcf": {
        "name": "现金流贴现 DCF",
        "what": "预测未来自由现金流并贴现到今天，含明确增长假设。",
        "when": "适用：可合理预测增长的公司。对增长与折现率敏感，需看置信度与警告。",
    },
    "graham_number": {
        "name": "格雷厄姆数字",
        "what": "防御型投资者用的粗算上限：√(22.5 × EPS × BVPS)。",
        "when": "适用：盈利与账面价值都扎实。BVPS 过低或亏损时通常不适用。",
    },
    "graham_formula": {
        "name": "格雷厄姆公式",
        "what": "按盈利、增长与债券收益率估算内在价值的经典公式变体。",
        "when": "适用：有稳定盈利的企业；对增长假设敏感。",
    },
    "altman_z": {
        "name": "Altman Z 破产风险评分",
        "what": "用多项财务比率合成评分，筛查财务困境风险（评分类，不直接给目标价）。",
        "when": "适用：风险筛查。低风险不等于值得买；高风险需优先核实负债与流动性。",
    },
    "value_trap": {
        "name": "价值陷阱检测",
        "what": "从财务健康、业务、护城河、技术脆弱性、股息等维度评估「便宜是否有坑」。",
        "when": "适用：估值偏低时的尽职调查。评分类，不参与公允价区间聚合。",
    },
    "relative_pe": {
        "name": "相对 PE 估值",
        "what": "用盈利与合理/历史市盈率估算价格带。",
        "when": "适用：盈利稳定、可比性强。亏损或盈利失真时慎用。",
    },
    "relative_pb": {
        "name": "相对 PB 估值",
        "what": "用净资产与合理市净率估算价格带。",
        "when": "适用：资产较重或银行等账面有意义的行业。",
    },
    "pb_relative": {
        "name": "PB 相对估值（历史分位）",
        "what": "对照自身历史市净率分位判断贵贱。",
        "when": "适用：银行等账面有意义的公司。分位低不自动等于买点，需结合资产质量。",
    },
    "residual_income": {
        "name": "剩余收益模型",
        "what": "在账面价值之上，把超额（剩余）收益贴现，得到股权价值。",
        "when": "适用：银行等净资产与 ROE 较有信息量的行业。对 ROE 与折现假设敏感。",
    },
    "pb_valuation": {
        "name": "P/B 估值",
        "what": "按合理或目标市净率对净资产定价。",
        "when": "适用：资产驱动型生意（如银行）。账面失真或一次性损益时慎用。",
    },
}


def method_tip(key: str) -> dict[str, str]:
    """供 HTML tip 使用的估值方法说明（name / what / when）。"""
    return dict(
        _METHOD_META.get(
            key,
            {
                "name": key,
                "what": "本工具内置的估值或评分方法。",
                "when": "详见方法 applicability 与警告；请结合原型与置信度理解。",
            },
        )
    )


_TECH_KEYWORD_MAP: list[tuple[str, str]] = [
    ("布林", "boll"),
    ("boll", "boll"),
    ("多头排列", "trend"),
    ("空头排列", "trend"),
    ("缩量", "volume"),
    ("放量", "volume"),
    ("MACD", "macd"),
    ("RSI", "rsi"),
    ("KDJ", "kdj"),
    ("均线", "ma"),
    ("MA", "ma"),
    ("乖离", "bias"),
    ("筹码", "chip"),
    ("支撑", "support"),
    ("压力", "support"),
    ("锤头", "pattern"),
    ("吞没", "pattern"),
    ("十字星", "pattern"),
    ("吊颈", "pattern"),
    ("形态", "pattern"),
    ("量能", "volume"),
    ("量比", "volume"),
]


def tech_tip_key_for_text(text: str) -> str | None:
    """从信号/风险文案中识别可讲解术语键。"""
    for needle, key in _TECH_KEYWORD_MAP:
        if needle.lower() in text.lower() or needle in text:
            return key
    return None


def tech_tip(key: str) -> str | None:
    """返回技术术语讲解文案。"""
    return _TECH_NOTES.get(key)

# details 字段 → (展示名, 来源说明)
_DETAIL_SOURCES: dict[str, tuple[str, str]] = {
    "formula": ("公式", "方法内置"),
    "dividend": ("股息 D", "价值快照/财报分红字段"),
    "next_dividend": ("下一期股息", "由当前股息与增长率推算"),
    "growth_rate": ("增长率 g", "假设/快照推算（AssumptionProvider 或财报）"),
    "required_return": ("要求回报率 r", "AssumptionProvider / 配置折现假设"),
    "current_yield": ("当前股息率", "现价与股息推算"),
    "fair_yield": ("公允股息率", "模型推算"),
    "growth_1_5": ("前5年增长率", "AssumptionProvider / 配置"),
    "growth_6_10": ("6–10年增长率", "AssumptionProvider / 配置"),
    "terminal_growth": ("永续增长率", "AssumptionProvider / 配置"),
    "discount_rate": ("折现率", "AssumptionProvider / WACC 假设"),
    "cost_of_capital": ("资本成本", "AssumptionProvider / 配置"),
    "normalized_earnings": ("正常化盈利", "财报盈利调整"),
    "owner_earnings": ("所有者收益", "财报现金流相关字段推算"),
    "eps": ("每股收益 EPS", "价值快照/财报"),
    "bvps": ("每股净资产 BVPS", "价值快照/财报"),
    "revenue": ("营业收入", "价值快照/财报"),
    "operating_margin": ("营业利润率", "价值快照/财报或 EBIT/收入推算"),
    "tax_rate": ("税率", "财报或默认假设"),
    "shares_outstanding": ("股本", "价值快照"),
    "maintenance_capex_pct": ("维持性资本开支比例", "方法默认或配置"),
    "z_score": ("Z 分数", "财报比率合成"),
    "overall_risk": ("总体风险", "五维度合成"),
    "stage1_growth": ("第一阶段增长", "假设/配置"),
    "stage2_growth": ("第二阶段增长", "假设/配置"),
    "high_growth_years": ("高增长年数", "方法/配置"),
}

_SKIP_DETAIL_KEYS = frozenset(
    {
        "output_type",
        "financial_health",
        "financial_health_note",
        "business_deterioration",
        "business_deterioration_note",
        "moat_erosion",
        "moat_erosion_note",
        "ai_vulnerability",
        "ai_vulnerability_note",
        "dividend_sustainability",
        "dividend_sustainability_note",
    }
)


def _fmt_detail_value(value: Any) -> str:
    if value is None:
        return "未在 details 中提供"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def render_value_method_card(key: str, mr: ValuationResult) -> list[str]:
    """单个估值方法的完整讲解卡片。"""
    meta = _METHOD_META.get(
        key,
        {
            "name": key,
            "what": "本工具内置的估值或评分方法。",
            "when": "详见方法 applicability 与警告；请结合原型与置信度理解。",
        },
    )
    details = mr.details or {}
    formula = details.get("formula")
    app_zh = applicability_to_zh(mr.applicability)
    assess_zh = assessment_to_zh(mr.assessment)

    lines = [
        "",
        f"### {meta['name']}（键名: `{key}`）",
        "",
        f"- **是什么：** {meta['what']}",
        f"- **适用场景：** {meta['when']}",
        f"- **公式：** {formula if formula else '未在 details 中提供'}",
        "- **本次入参：**",
    ]

    input_keys = [
        k
        for k in details
        if k not in _SKIP_DETAIL_KEYS and k != "formula" and not k.endswith("_note")
    ]
    if not input_keys:
        lines.append("  - （details 中无额外入参字段）")
    else:
        for dk in input_keys:
            label, source = _DETAIL_SOURCES.get(dk, (dk, "见 details；来源未单独标注"))
            lines.append(
                f"  - {label} = {_fmt_detail_value(details.get(dk))}  ← {source}"
            )

    fv = f"{mr.fair_value:.2f}" if mr.fair_value is not None else "N/A"
    lines.append(f"- **结果：** 公允价={fv} | 评估={assess_zh} | 适用性={app_zh}")

    if mr.applicability and mr.applicability.lower() in ("not applicable", "limited"):
        err = mr.error or (mr.analysis[0] if mr.analysis else "")
        if err:
            lines.append(f"- **说明：** {err}")

    return lines


def render_all_value_method_cards(result: ValueAnalysisResult) -> list[str]:
    if not result.method_results:
        return []
    lines = ["", "## 估值方法详解（默认开启）", ""]
    for key, mr in result.method_results.items():
        lines.extend(render_value_method_card(key, mr))
    return lines


# ── 价值陷阱 ─────────────────────────────────────────────────────────────────

_TRAP_DIMS: list[tuple[str, str, str]] = [
    ("financial_health", "financial_health_note", "财务健康"),
    ("business_deterioration", "business_deterioration_note", "业务恶化"),
    ("moat_erosion", "moat_erosion_note", "护城河侵蚀"),
    ("ai_vulnerability", "ai_vulnerability_note", "AI/技术脆弱性"),
    ("dividend_sustainability", "dividend_sustainability_note", "股息可持续性"),
]

_RISK_ZH = {
    "Low": "低",
    "Medium": "中等",
    "High": "高",
    "Limited": "数据有限",
    "Not Applicable": "不适用",
}


def render_value_trap_explainer(details: dict[str, Any] | None) -> list[str]:
    if not details:
        return []
    overall = details.get("overall_risk", "N/A")
    overall_zh = _RISK_ZH.get(str(overall), str(overall))
    lines = [
        "",
        "## 价值陷阱说明",
        "",
        "含义：价格可能看起来「不贵」，但基本面有坑时，便宜也可能长期无法兑现为回报。",
        f"本次总体风险：**{overall_zh}**（{overall}）",
        "怎么读：低=未发现明显陷阱信号；中等=需核对财报与竞争；高=便宜也不能闭眼买。",
        "",
        "**各维度：**",
        "",
    ]
    for risk_key, note_key, label in _TRAP_DIMS:
        risk = details.get(risk_key)
        note = details.get(note_key) or ""
        if risk is None:
            continue
        risk_zh = _RISK_ZH.get(str(risk), str(risk))
        lines.append(f"- {label}：{risk_zh} — {note}")
    return lines


def render_value_explanations(result: ValueAnalysisResult) -> list[str]:
    lines = render_all_value_method_cards(result)
    trap = result.method_results.get("value_trap")
    if trap is not None:
        lines.extend(render_value_trap_explainer(trap.details))
    return lines
