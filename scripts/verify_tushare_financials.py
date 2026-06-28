"""验证 Tushare 财报接口权限（income / cashflow / balancesheet / fina_indicator）。

用法：
    py scripts/verify_tushare_financials.py [code]

退出码：0 = 全部可用；1 = 至少一个接口无权限或失败。
Token 来源：config/app.yaml 或环境变量 TUSHARE_TOKEN。
"""

from __future__ import annotations

import os
import sys
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
        if src.get("name") == "tushare":
            return (src.get("token") or "").strip()
    return ""


def main() -> int:
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    exchange = "SH" if code.startswith("6") else "SZ"
    ts_code = f"{code}.{exchange}"

    token = _load_token()
    if not token:
        print("ERROR: 未找到 Tushare token（config/app.yaml 或 TUSHARE_TOKEN）")
        return 1

    import tushare as ts

    ts.set_token(token)
    pro = ts.pro_api()

    apis = ("income", "cashflow", "balancesheet", "fina_indicator")
    ok_count = 0
    for api in apis:
        try:
            fn = getattr(pro, api)
            df = fn(ts_code=ts_code, limit=2)
            if df is None or df.empty:
                print(f"{api}: FAIL 无数据")
                continue
            end_date = df.iloc[0].get("end_date", "?")
            print(f"{api}: OK rows={len(df)} latest_end_date={end_date}")
            ok_count += 1
        except Exception as exc:
            print(f"{api}: FAIL {exc}")

    if ok_count == len(apis):
        print(f"\n全部 {ok_count} 个财报接口可用。")
        return 0
    print(f"\n仅 {ok_count}/{len(apis)} 个接口可用。请升级 Tushare 积分至 ≥120。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
