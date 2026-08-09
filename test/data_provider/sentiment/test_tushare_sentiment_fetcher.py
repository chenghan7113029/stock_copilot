"""TushareSentimentFetcher 单元测试（mock pro）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from data_provider.sentiment.tushare_sentiment_fetcher import TushareSentimentFetcher


def test_fetch_market_breadth_from_daily_pct() -> None:
    pro = MagicMock()
    pro.trade_cal.return_value = pd.DataFrame({"cal_date": ["20260808"]})
    pro.daily.return_value = pd.DataFrame(
        {
            "pct_chg": [10.0, 9.6, -9.8, 1.0, -0.5, 0.0],
        }
    )
    fetcher = TushareSentimentFetcher(token="x", pro=pro)
    result = fetcher.fetch_market_breadth()
    assert result.ok
    assert result.data["limit_up_count"] == 2
    assert result.data["limit_down_count"] == 1
    assert result.data["up_count"] == 3
    assert result.data["down_count"] == 2
    assert result.data["_breadth_approximation"] is True


def test_fetch_margin_change() -> None:
    pro = MagicMock()
    pro.margin.return_value = pd.DataFrame(
        {
            "trade_date": ["20260807", "20260807", "20260808", "20260808"],
            "rzye": [100.0, 50.0, 110.0, 55.0],
        }
    )
    fetcher = TushareSentimentFetcher(token="x", pro=pro)
    result = fetcher.fetch_margin_change()
    assert result.ok
    # (165/150 - 1) * 100
    assert result.data["margin_balance_change_pct"] == pytest.approx(10.0)


def test_turnover_percentile_explicitly_missing() -> None:
    fetcher = TushareSentimentFetcher(token="x", pro=MagicMock())
    result = fetcher.fetch_turnover_percentile()
    assert not result.ok
    assert "turnover_percentile" in result.missing_fields
