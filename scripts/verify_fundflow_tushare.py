"""一次性验证 Tushare margin_detail 与 moneyflow 接口在 2000 积分 Token 下可用。

仅用于 OpenSpec change add-stock-margin-fundflow 的 §1 数据源可行性验证，
不属于业务核心逻辑。运行：python scripts/verify_fundflow_tushare.py [ts_code]
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
            opened = cal.sort_values("cal_date")
            return str(opened.iloc[-1]["cal_date"])
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


def main() -> int:
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    config = load_app_config()
    token = resolve_tushare_token(config)
    if not token:
        print("[error] 未配置 Tushare token")
        return 1

    import tushare as ts

    # 直接用 pro_api(token)，避免 set_token 写 ~/tk.csv（sandbox 下 home 不可写）
    pro = ts.pro_api(token)
    ts_code = f"{code}.SH" if code[0] == "6" else f"{code}.SZ"

    end = date.today()
    trade_date = _latest_trade_date(pro, end)
    print(f"目标 ts_code={ts_code} 最近交易日={trade_date}")

    # margin_detail：个股两融明细（ts_code + trade_date）
    try:
        margin = pro.margin_detail(ts_code=ts_code, trade_date=trade_date)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] margin_detail 调用失败: {exc}")
        margin = None
    _describe("margin_detail", margin)

    # moneyflow：个股主力资金流（trade_date）
    try:
        mf = pro.moneyflow(ts_code=ts_code, trade_date=trade_date)
    except Exception as exc:  # noqa: BLE001
        print(f"[error] moneyflow(trade_date) 调用失败: {exc}")
        mf = None
    _describe("moneyflow(trade_date)", mf)

    if mf is None or getattr(mf, "empty", True):
        # 回退：用 start/end 拉取近 5 个交易日
        start = (end - timedelta(days=14)).strftime("%Y%m%d")
        try:
            mf2 = pro.moneyflow(ts_code=ts_code, start_date=start, end_date=end.strftime("%Y%m%d"))
        except Exception as exc:  # noqa: BLE001
            print(f"[error] moneyflow(start/end) 调用失败: {exc}")
            mf2 = None
        _describe("moneyflow(start/end)", mf2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
