"""Tushare K 线 E2E：tushare-only 配置经 KlineProvider 写入缓存。

需本地 config/app.yaml 或环境变量 TUSHARE_TOKEN；无 Token 时自动 skip。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from common.config_loader import has_tushare_token, load_app_config, verify_tushare_access
from dao.engine import Base, make_session_factory
from dao.kline_repo import KlineRepo
from data_provider.kline_provider import KlineProvider

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _tushare_only_config(config: dict) -> dict:
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
def test_tushare_kline_pipeline_writes_cache():
    """tushare-only 下 get_kline 成功，且历史行写入 KlineRepo。"""
    config = _tushare_only_config(load_app_config())
    assert has_tushare_token(config)

    test_db_path = _REPO_ROOT / "data" / "e2e_tushare_kline_test.db"
    test_db_path.parent.mkdir(exist_ok=True)
    if test_db_path.exists():
        test_db_path.unlink()

    engine = create_engine(
        f"sqlite:///{test_db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)
    session = session_factory()

    try:
        repo = KlineRepo(session)
        provider = KlineProvider.from_config(config, repo)
        assert any(name == "tushare" for _, name in provider._kline_sources)
        assert all(name != "akshare" for _, name in provider._kline_sources)

        df, warnings, quote_mode = provider.get_kline("600519", days=90, use_realtime=False)
        session.commit()

        assert not df.empty, f"K 线为空 warnings={warnings}"
        assert "close" in df.columns
        assert float(df["close"].iloc[-1]) > 0
        assert quote_mode == "eod"

        cached = repo.list_by_code("600519")
        assert cached, "KlineRepo 未写入历史 K 线"
        assert cached[0]["close"] is not None
        logger.info(
            "tushare kline OK: rows=%d cached=%d last_close=%s",
            len(df),
            len(cached),
            df["close"].iloc[-1],
        )
    finally:
        session.close()
