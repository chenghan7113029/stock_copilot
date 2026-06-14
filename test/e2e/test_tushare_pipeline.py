"""Tushare 数据源 E2E 验收：fetch → upsert → readback。

需本地 config/app.yaml 或环境变量 TUSHARE_TOKEN；无 Token 时自动 skip。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from common.config_loader import (
    has_tushare_token,
    load_app_config,
    load_validation_stocks,
    verify_tushare_access,
)
from dao.engine import Base, make_session_factory
from dao.stock_snapshot_repo import StockSnapshotRepo
from data_provider.provider import StockDataProvider

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _tushare_only_config(config: dict) -> dict:
    """E2E 仅测 Tushare 路径，避免其他源网络延迟干扰。"""
    enabled = config.get("data_sources", {}).get("enabled", [])
    tushare_entries = [s for s in enabled if s.get("name", "").lower() == "tushare"]
    assert tushare_entries, "config 中未启用 tushare"
    return {
        **config,
        "data_sources": {"enabled": tushare_entries},
    }


@pytest.mark.network
@pytest.mark.skipif(not has_tushare_token(), reason="未配置 Tushare Token")
@pytest.mark.skipif(
    has_tushare_token() and not verify_tushare_access(),
    reason="Tushare Token 无接口权限（请在 tushare.pro 完成实名认证并获取积分）",
)
def test_tushare_pipeline_e2e():
    """6 只样本股均应有 source=tushare 快照，且至少 current_price 或 eps 非空。"""
    config = _tushare_only_config(load_app_config())
    assert has_tushare_token(config), "Tushare 未在 enabled 中启用或 token 为空"

    stocks_list = load_validation_stocks()
    assert stocks_list, "样本股票清单不能为空"

    test_db_path = _REPO_ROOT / "data" / "e2e_tushare_test.db"
    test_db_path.parent.mkdir(exist_ok=True)

    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)

    for item in stocks_list:
        code: str = item["code"]
        name: str = item.get("name", code)

        session = session_factory()
        repo = StockSnapshotRepo(session)
        provider = StockDataProvider.from_config(config, repo=repo)

        try:
            provider.get_stock_data(code)
            session.commit()
        except Exception as exc:
            session.rollback()
            pytest.fail(f"[{code}] {name} 采集失败: {exc}")
        finally:
            session.close()

        read_session = session_factory()
        read_repo = StockSnapshotRepo(read_session)
        snapshots = read_repo.find_by_code(code)
        read_session.close()

        tushare_snaps = [s for s in snapshots if s.source == "tushare"]
        assert tushare_snaps, f"[{code}] {name} 未写入 source=tushare 快照"

        snap = tushare_snaps[0]
        has_price = snap.current_price is not None
        has_eps = snap.eps is not None
        assert has_price or has_eps, (
            f"[{code}] {name} tushare 快照缺少 current_price 与 eps"
        )
        logger.info(
            "[%s] %s tushare OK: price=%s eps=%s",
            code, name, snap.current_price, snap.eps,
        )
