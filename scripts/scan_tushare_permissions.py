"""扫描 Tushare Token 对各接口的实际访问权限。

用法：
    py scripts/scan_tushare_permissions.py

Token 来源：环境变量 TUSHARE_TOKEN 或 config/app.yaml。
仅输出接口名与 OK/FAIL，不打印 token。
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))


def _load_token() -> str:
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if token:
        return token
    import yaml

    cfg_path = ROOT / "config" / "app.yaml"
    if not cfg_path.exists():
        return ""
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    for src in cfg.get("data_sources", {}).get("enabled", []):
        if str(src.get("name", "")).lower() == "tushare":
            return (src.get("token") or "").strip()
    return ""


def _probe(label: str, fn) -> tuple[str, str]:
    try:
        result = fn()
        if result is None:
            return label, "FAIL(empty)"
        if hasattr(result, "empty") and result.empty:
            return label, "FAIL(no rows)"
        return label, "OK"
    except Exception as exc:
        msg = str(exc).replace("\n", " ")[:120]
        return label, f"FAIL({msg})"


def main() -> int:
    token = _load_token()
    if not token:
        print("ERROR: 未找到 Tushare token（config/app.yaml 或 TUSHARE_TOKEN）")
        return 1

    import tushare as ts

    ts.set_token(token)
    pro = ts.pro_api()

    ts_code = "600519.SH"
    end = date.today().strftime("%Y%m%d")
    start = (date.today() - timedelta(days=30)).strftime("%Y%m%d")
    cal_start = (date.today() - timedelta(days=10)).strftime("%Y%m%d")

    probes: list[tuple[str, str]] = []

    # ── 项目已使用 ──
    used = [
        ("stock_basic [已用: 行业/校验]", lambda: pro.stock_basic(ts_code=ts_code, fields="ts_code,name,industry")),
        ("daily [已用: 行情/情绪广度]", lambda: pro.daily(ts_code=ts_code, start_date=start, end_date=end)),
        ("daily_basic [已用: 指标/历史PE]", lambda: pro.daily_basic(ts_code=ts_code, start_date=start, end_date=end)),
        ("pro_bar [已用: 前复权K线]", lambda: ts.pro_bar(ts_code=ts_code, start_date=start, end_date=end, adj="qfq", asset="E", freq="D", api=pro)),
        ("rt_k [已用: 实时; 单独月费]", lambda: pro.rt_k(ts_code=ts_code)),
        ("income [已用: 利润表]", lambda: pro.income(ts_code=ts_code, limit=1)),
        ("balancesheet [已用: 资产负债表]", lambda: pro.balancesheet(ts_code=ts_code, limit=1)),
        ("cashflow [已用: 现金流]", lambda: pro.cashflow(ts_code=ts_code, limit=1)),
        ("fina_indicator [已用: 财务指标/银行]", lambda: pro.fina_indicator(ts_code=ts_code, limit=1)),
        ("dividend [已用: 分红]", lambda: pro.dividend(ts_code=ts_code, limit=1)),
        ("margin [已用: 两融汇总/情绪]", lambda: pro.margin(start_date=cal_start, end_date=end)),
        ("trade_cal [已用: 交易日历/情绪]", lambda: pro.trade_cal(exchange="SSE", start_date=cal_start, end_date=end, is_open="1")),
    ]

    # ── 2000 分可用但项目未用（高价值） ──
    unused_2000 = [
        ("top_list [未用: 龙虎榜]", lambda: pro.top_list(trade_date=end)),
        ("top_inst [未用: 龙虎榜机构]", lambda: pro.top_inst(trade_date=end)),
        ("margin_detail [未用: 两融明细]", lambda: pro.margin_detail(trade_date=end)),
        ("moneyflow [未用: 个股资金流]", lambda: pro.moneyflow(ts_code=ts_code, start_date=start, end_date=end)),
        ("stk_holdertrade [未用: 股东增减持]", lambda: pro.stk_holdertrade(ts_code=ts_code, start_date=start, end_date=end)),
        ("stk_holdernumber [未用: 股东人数]", lambda: pro.stk_holdernumber(ts_code=ts_code, start_date=start, end_date=end)),
        ("block_trade [未用: 大宗交易]", lambda: pro.block_trade(ts_code=ts_code, start_date=start, end_date=end)),
        ("pledge_detail [未用: 股权质押]", lambda: pro.pledge_detail(ts_code=ts_code, start_date=start, end_date=end)),
        ("repurchase [未用: 回购]", lambda: pro.repurchase(ann_date=end)),
        ("hk_hold [未用: 北向持股]", lambda: pro.hk_hold(ts_code=ts_code, start_date=start, end_date=end)),
        ("stk_limit [未用: 涨跌停价]", lambda: pro.stk_limit(ts_code=ts_code, start_date=start, end_date=end)),
        ("forecast [未用: 业绩预告]", lambda: pro.forecast(ts_code=ts_code, limit=1)),
        ("express [未用: 业绩快报]", lambda: pro.express(ts_code=ts_code, limit=1)),
        ("fina_mainbz [未用: 主营构成]", lambda: pro.fina_mainbz(ts_code=ts_code, limit=1)),
        ("index_daily [未用: 指数日线]", lambda: pro.index_daily(ts_code="000300.SH", start_date=start, end_date=end)),
        ("index_classify [未用: 申万行业]", lambda: pro.index_classify(level="L1", src="SW2021")),
        ("weekly [未用: 周线]", lambda: pro.weekly(ts_code=ts_code, start_date=start, end_date=end)),
        ("monthly [未用: 月线]", lambda: pro.monthly(ts_code=ts_code, start_date=start, end_date=end)),
    ]

    # ── 高于 2000 分（预期 FAIL） ──
    above_2000 = [
        ("share_float [需3000: 解禁]", lambda: pro.share_float(ts_code=ts_code, start_date=start, end_date=end)),
        ("cyq_perf [需5000: 筹码]", lambda: pro.cyq_perf(ts_code=ts_code, start_date=start, end_date=end)),
        ("index_dailybasic [需4000: 指数指标]", lambda: pro.index_dailybasic(ts_code="000300.SH", start_date=start, end_date=end)),
        ("fund_portfolio [需5000: 基金持仓]", lambda: pro.fund_portfolio(ts_code=ts_code, limit=1)),
    ]

    sections = [
        ("=== 项目已调用接口 ===", used),
        ("=== 2000 分档可用·项目未用 ===", unused_2000),
        ("=== 高于 2000 分（对照） ===", above_2000),
    ]

    ok_used = 0
    ok_unused = 0
    for title, items in sections:
        print(title)
        for label, call in items:
            name, status = _probe(label, call)
            print(f"  {name}: {status}")
            if status == "OK":
                if title.startswith("=== 项目"):
                    ok_used += 1
                elif "2000 分档" in title:
                    ok_unused += 1
        print()

    print(f"已用接口可用: {ok_used}/{len(used)}")
    print(f"未用但 2000 分接口可用: {ok_unused}/{len(unused_2000)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
