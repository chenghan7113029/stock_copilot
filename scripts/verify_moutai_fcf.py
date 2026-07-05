"""核验茅台 FCF：对比 Tushare 各期现金流与本地快照。"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dao.engine import Base, create_db_engine, ensure_sqlite_schema, make_session_factory
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.tushare.fetcher import TushareFetcher


def main() -> None:
    cfg = yaml.safe_load((ROOT / "config" / "app.yaml").read_text(encoding="utf-8"))
    token = None
    for src in cfg.get("data_sources", {}).get("enabled", []):
        if src.get("name") == "tushare":
            token = src.get("token")
    if not token:
        print("无 Tushare token")
        return

    fetcher = TushareFetcher(token=token)
    pro = fetcher._pro  # noqa: SLF001
    ts_code = "600519.SH"

    print("=== Tushare cashflow 原始记录（limit=8）===")
    df = pro.cashflow(ts_code=ts_code, limit=8)
    if df is None or df.empty:
        print("无数据")
    else:
        df = df.sort_values("end_date", ascending=False)
        cols = ["end_date", "ann_date", "n_cashflow_act", "c_pay_acq_const_fiolta"]
        cols = [c for c in cols if c in df.columns]
        for _, row in df[cols].iterrows():
            ocf = row.get("n_cashflow_act")
            capex = row.get("c_pay_acq_const_fiolta")
            fcf = None
            if ocf is not None and capex is not None:
                fcf = float(ocf) - abs(float(capex))
            ocf_yi = float(ocf) / 1e8 if ocf else None
            capex_yi = float(capex) / 1e8 if capex else None
            fcf_yi = fcf / 1e8 if fcf else None
            print(
                f"  end_date={row['end_date']}  OCF={ocf_yi:.2f}亿  "
                f"capex={capex_yi:.2f}亿  FCF={fcf_yi:.2f}亿"
                if fcf_yi
                else f"  end_date={row['end_date']}  raw OCF={ocf} capex={capex}"
            )

    print("\n=== fetcher._fetch_latest('cashflow') 选中行 ===")
    row = fetcher._fetch_latest("cashflow", ts_code)
    if row is not None:
        ocf = row.get("n_cashflow_act")
        capex = row.get("c_pay_acq_const_fiolta")
        print(f"  end_date={row.get('end_date')}")
        print(f"  OCF={float(ocf)/1e8:.2f}亿  capex={float(capex)/1e8:.2f}亿")
        print(f"  FCF={(float(ocf)-abs(float(capex)))/1e8:.2f}亿")

    print("\n=== 本地 DB 全部 tushare 快照 ===")
    eng = create_db_engine(cfg)
    ensure_sqlite_schema(eng)
    Base.metadata.create_all(eng)
    session = make_session_factory(eng)()
    repo = StockSnapshotRepo(session)
    for snap in sorted(repo.find_by_code("600519"), key=lambda s: s.fetched_at, reverse=True):
        if snap.source != "tushare":
            continue
        fcf = getattr(snap, "fcf", None)
        print(
            f"  report_period={snap.report_period}  fetched_at={snap.fetched_at}  "
            f"fcf={fcf/1e8:.2f}亿" if fcf else f"  report_period={snap.report_period}"
        )
    session.close()


if __name__ == "__main__":
    main()
