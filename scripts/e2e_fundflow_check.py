"""个股资金面 E2E 验证：联网拉取 + 落库 + 离线分析 + 格式化。

用于 OpenSpec change add-stock-margin-fundflow §7 端到端验收（人工核对数值）。
运行：python scripts/e2e_fundflow_check.py [code]
"""

from __future__ import annotations

import sys

from apps.formatters import format_fund_flow_report
from common.config_loader import load_app_config
from common.win_console import setup_utf8_console
from dao.engine import Base, create_db_engine, make_session_factory
from dao.fund_flow_repo import StockMarginDetailRepo, StockMoneyFlowRepo
from data_provider.fundflow.provider import FundFlowProvider, FundFlowRepos
from service.fundflow.analyzer import FundFlowAnalyzer


def main() -> int:
    setup_utf8_console()
    code = sys.argv[1] if len(sys.argv) > 1 else "600519"
    cfg = load_app_config()
    engine = create_db_engine(cfg)
    Base.metadata.create_all(engine)
    session = make_session_factory(engine)()
    try:
        repos = FundFlowRepos(
            margin=StockMarginDetailRepo(session),
            moneyflow=StockMoneyFlowRepo(session),
        )
        analyzer = FundFlowAnalyzer(FundFlowProvider.from_config(cfg, repos))

        print(f"===== 联网拉取并分析 {code} =====")
        online = analyzer.analyze(code)
        session.commit()
        print(format_fund_flow_report(online))

        print(f"\n===== 严格离线分析（读缓存）{code} =====")
        offline = analyzer.analyze_offline(code)
        if offline is None:
            print("[error] 离线无资金面缓存")
            return 1
        print(format_fund_flow_report(offline))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
