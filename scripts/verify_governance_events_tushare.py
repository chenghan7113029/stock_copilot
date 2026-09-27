"""一次性验证 Tushare 治理事件接口在 2000 积分 Token 下可用。

仅用于 OpenSpec change add-governance-flow-events 的 §1 数据源可行性验证。
接口：stk_holdertrade / repurchase / share_float / pledge_stat / block_trade / moneyflow_hsgt
运行：python scripts/verify_governance_events_tushare.py [ts_code]
"""

from __future__ import annotations

import sys
from datetime import date, timedelta

from common.config_loader import load_app_config, resolve_tushare_token


def _latest_trade_date(pro, end: date) -> str | None:
    start = end - timedelta(days=14)
    try:
        cal = pro.trade_cal(
            exchange="SSE",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            is_open="1",
        )
        if cal is not None and not cal.empty and "cal_date" in cal.columns:
            return str(cal.sort_values("cal_date").iloc[-1]["cal_date"])
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] trade_cal 失败: {exc}")
    value = end
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value.strftime("%Y%m%d")


def _describe(name: str, df) -> None:
    print(f"\n===== {name} =====")
    if df is None:
        print("  返回 None")
        return
    if getattr(df, "empty", True):
        print("  返回空 DataFrame")
        return
    print(f"  shape={df.shape}")
    print(f"  columns={list(df.columns)}")
    print(f"  dtypes=\n{df.dtypes.to_string()}")
    print("  首行:")
    print(df.iloc[0].to_string())


def _try_call(name: str, fn) -> None:
    try:
        _describe(name, fn())
    except Exception as exc:  # noqa: BLE001
        print(f"\n===== {name} =====\n  [error] 调用失败: {exc}")


def main() -> int:
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    config = load_app_config()
    token = resolve_tushare_token(config)
    if not token:
        print("[error] 未配置 Tushare token")
        return 1

    import tushare as ts

    pro = ts.pro_api(token)  # 直接用 pro_api(token)，避免 set_token 写 ~/tk.csv
    ts_code = f"{code}.SH" if code[0] == "6" else f"{code}.SZ"

    end = date.today()
    start_90d = (end - timedelta(days=90)).strftime("%Y%m%d")
    end_s = end.strftime("%Y%m%d")
    trade_date = _latest_trade_date(pro, end)
    print(f"ts_code={ts_code} 窗口 {start_90d}~{end_s} 最近交易日={trade_date}")

    _try_call("stk_holdertrade", lambda: pro.stk_holdertrade(ts_code=ts_code, start_date=start_90d, end_date=end_s))
    _try_call("repurchase", lambda: pro.repurchase(ts_code=ts_code, start_date=start_90d, end_date=end_s))
    _try_call("share_float", lambda: pro.share_float(ts_code=ts_code, start_date=start_90d, end_date=end_s))
    _try_call("pledge_stat", lambda: pro.pledge_stat(ts_code=ts_code))
    _try_call("block_trade", lambda: pro.block_trade(ts_code=ts_code, start_date=start_90d, end_date=end_s))
    _try_call("moneyflow_hsgt", lambda: pro.moneyflow_hsgt(trade_date=trade_date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
