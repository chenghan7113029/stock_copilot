"""ChipDistributionProvider 缓存与降级测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from common.exceptions import DataProviderError
from data_provider.chip_distribution_provider import ChipDistributionProvider


def _chip_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_date": "2026-07-31",
                "winner_ratio": 42.5,
                "avg_cost": 12.34,
                "concentration_90": 8.2,
                "concentration_70": 4.1,
                "cost_90_low": 10.0,
                "cost_90_high": 14.0,
                "cost_70_low": 11.0,
                "cost_70_high": 13.0,
            }
        ]
    )


def test_get_latest_offline_reads_only_cache() -> None:
    repo = MagicMock()
    repo.query_latest.return_value = {"code": "600519", "trade_date": "2026-07-31"}
    fetcher = MagicMock()

    result, warnings = ChipDistributionProvider(repo, fetcher).get_latest("600519", offline=True)

    assert result == repo.query_latest.return_value
    assert warnings == []
    fetcher.fetch_chip_distribution.assert_not_called()


def test_get_latest_fetches_and_persists_history_when_online() -> None:
    repo = MagicMock()
    repo.query_latest.return_value = {"code": "600519", "trade_date": "2026-07-31"}
    fetcher = MagicMock()
    fetcher.fetch_chip_distribution.return_value = _chip_df()

    result, warnings = ChipDistributionProvider(repo, fetcher).get_latest("600519")

    assert result == repo.query_latest.return_value
    assert warnings == []
    assert repo.upsert_batch.call_args.args[0][0]["code"] == "600519"


def test_get_latest_falls_back_to_cache_after_fetch_failure() -> None:
    cached = {"code": "600519", "trade_date": "2026-07-30"}
    repo = MagicMock()
    repo.query_latest.return_value = cached
    fetcher = MagicMock()
    fetcher.fetch_chip_distribution.side_effect = DataProviderError("network down")

    result, warnings = ChipDistributionProvider(repo, fetcher).get_latest("600519")

    assert result == cached
    assert any("network down" in warning for warning in warnings)


def test_get_latest_returns_warning_without_cache_after_fetch_failure() -> None:
    repo = MagicMock()
    repo.query_latest.return_value = None
    fetcher = MagicMock()
    fetcher.fetch_chip_distribution.side_effect = DataProviderError("network down")

    result, warnings = ChipDistributionProvider(repo, fetcher).get_latest("600519")

    assert result is None
    assert any("network down" in warning for warning in warnings)


def test_get_latest_skips_akshare_when_disabled() -> None:
    cached = {"code": "600519", "trade_date": "2026-07-30"}
    repo = MagicMock()
    repo.query_latest.return_value = cached
    fetcher = MagicMock()

    result, warnings = ChipDistributionProvider(
        repo, fetcher, use_akshare=False
    ).get_latest("600519")

    assert result == cached
    assert any("未在 data_sources.enabled 中启用" in w for w in warnings)
    fetcher.fetch_chip_distribution.assert_not_called()
