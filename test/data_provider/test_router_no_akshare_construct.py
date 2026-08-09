"""筹码/情绪：仅 baostock 启用时不实例化 AKShare。"""

from __future__ import annotations

from unittest.mock import MagicMock

from data_provider.chip_distribution_provider import ChipDistributionProvider
from data_provider.sentiment.provider import MarketSentimentProvider


def test_chip_from_config_baostock_only_no_akshare(monkeypatch):
    created: list[str] = []

    class _BS:
        source_name = "baostock"
        priority = 1

    def fake_build(name, priority_override, src=None, config=None):
        created.append(name)
        if name == "baostock":
            return _BS()
        raise AssertionError(name)

    monkeypatch.setattr(
        "data_provider.router.DataFetcherRouter.build_fetcher",
        staticmethod(fake_build),
    )
    # prevent accidental AKShare import path
    monkeypatch.setattr(
        "data_provider.akshare.fetcher.AKShareFetcher",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("AKShareFetcher")),
    )
    provider = ChipDistributionProvider.from_config(
        {"data_sources": {"enabled": [{"name": "baostock", "priority": 1}]}},
        MagicMock(),
    )
    assert created == ["baostock"]
    assert provider._fetchers == []


def test_sentiment_from_config_baostock_only_no_akshare(monkeypatch):
    class _BS:
        source_name = "baostock"
        priority = 1

    monkeypatch.setattr(
        "data_provider.router.DataFetcherRouter.build_fetcher",
        staticmethod(lambda name, priority_override, src=None, config=None: _BS()),
    )

    def boom(*a, **k):
        raise AssertionError("AkshareSentimentFetcher should not construct")

    monkeypatch.setattr(
        "data_provider.sentiment.provider.AkshareSentimentFetcher",
        boom,
    )
    provider = MarketSentimentProvider.from_config(
        {"data_sources": {"enabled": [{"name": "baostock", "priority": 1}]}},
        MagicMock(),
    )
    assert provider._fetcher is None
    assert provider._use_akshare is False


def test_sentiment_from_config_tushare_only(monkeypatch):
    class _TS:
        source_name = "tushare"
        priority = 1

    monkeypatch.setattr(
        "data_provider.router.DataFetcherRouter.build_fetcher",
        staticmethod(lambda name, priority_override, src=None, config=None: _TS()),
    )
    monkeypatch.setattr(
        "data_provider.sentiment.provider.resolve_tushare_token",
        lambda config: "tok",
    )
    created: list[str] = []

    class _FakeTS:
        source_name = "tushare"

        def __init__(self, token: str):
            created.append(token)

    monkeypatch.setattr(
        "data_provider.sentiment.provider.TushareSentimentFetcher",
        _FakeTS,
    )
    provider = MarketSentimentProvider.from_config(
        {"data_sources": {"enabled": [{"name": "tushare", "priority": 1}]}},
        MagicMock(),
    )
    assert created == ["tok"]
    assert provider._use_akshare is False
    assert isinstance(provider._fetcher, _FakeTS)
