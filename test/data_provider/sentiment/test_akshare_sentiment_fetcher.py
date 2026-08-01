from unittest.mock import MagicMock

import pandas as pd

from data_provider.sentiment.akshare_sentiment_fetcher import AkshareSentimentFetcher


def _activity_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "item": ["涨停家数", "跌停家数", "上涨家数", "下跌家数"],
            "value": ["50", "10", "3000", "1000"],
        }
    )


def test_fetch_market_breadth_parses_market_activity() -> None:
    akshare = MagicMock()
    akshare.stock_market_activity_legu.return_value = _activity_df()

    result = AkshareSentimentFetcher(akshare).fetch_market_breadth()

    assert result.ok
    assert result.data == {
        "limit_up_count": 50,
        "limit_down_count": 10,
        "up_count": 3000,
        "down_count": 1000,
    }


def test_optional_component_failure_returns_fetch_error() -> None:
    akshare = MagicMock()
    akshare.macro_china_market_margin_sh.side_effect = RuntimeError("down")

    result = AkshareSentimentFetcher(akshare).fetch_margin_change()

    assert not result.ok
    assert "down" in result.error


def test_fetch_market_breadth_falls_back_to_limit_pools_when_legu_breaks() -> None:
    akshare = MagicMock()
    akshare.stock_market_activity_legu.side_effect = RuntimeError("page changed")
    akshare.stock_zt_pool_em.return_value = pd.DataFrame({"代码": ["a", "b"]})
    akshare.stock_zt_pool_dtgc_em.return_value = pd.DataFrame()

    result = AkshareSentimentFetcher(akshare).fetch_market_breadth()

    assert result.ok
    assert result.data["limit_up_count"] == 2
    assert result.data["limit_down_count"] == 0


def test_all_components_fail_independently() -> None:
    akshare = MagicMock()
    akshare.stock_market_activity_legu.side_effect = RuntimeError("breadth down")
    akshare.stock_zt_pool_em.side_effect = RuntimeError("limit pool down")
    akshare.macro_china_market_margin_sh.side_effect = RuntimeError("margin down")
    akshare.stock_zh_a_spot_em.side_effect = RuntimeError("turnover down")
    fetcher = AkshareSentimentFetcher(akshare)

    assert not fetcher.fetch_market_breadth().ok
    assert not fetcher.fetch_margin_change().ok
    assert not fetcher.fetch_turnover_percentile().ok
