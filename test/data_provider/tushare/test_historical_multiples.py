"""Tushare 历史 PE/PB 季末采样测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data_provider.tushare.fetcher import TushareFetcher, sample_quarter_end_multiples


def _make_quarterly_daily_basic() -> pd.DataFrame:
    rows = []
    # 5 年 × 4 季 = 20 个季末点
    for year in range(2021, 2026):
        for month, day in ((3, 31), (6, 30), (9, 30), (12, 31)):
            rows.append({
                "trade_date": f"{year}{month:02d}{day:02d}",
                "pe_ttm": 20.0 + (year - 2021) * 0.5,
                "pb": 5.0 + (year - 2021) * 0.1,
            })
            # 同季度较早交易日（应被季末覆盖）
            rows.append({
                "trade_date": f"{year}{month:02d}{day - 5:02d}",
                "pe_ttm": 99.0,
                "pb": 99.0,
            })
    return pd.DataFrame(rows)


def test_sample_quarter_end_multiples_picks_last_trading_day():
    df = _make_quarterly_daily_basic()
    pes, pbs = sample_quarter_end_multiples(df)
    assert len(pes) == 20
    assert len(pbs) == 20
    assert pes[0] == pytest.approx(22.0)  # 2025 年 PE
    assert pes[-1] == pytest.approx(20.0)  # 2021 年 PE
    assert 99.0 not in pes
    assert 99.0 not in pbs


def test_sample_quarter_end_multiples_filters_extremes():
    df = pd.DataFrame([
        {"trade_date": "20250331", "pe_ttm": -1.0, "pb": 8.0},
        {"trade_date": "20241231", "pe_ttm": 25.0, "pb": 0.0},
        {"trade_date": "20240930", "pe_ttm": 300.0, "pb": 60.0},
        {"trade_date": "20240630", "pe_ttm": 22.0, "pb": 7.0},
    ])
    pes, pbs = sample_quarter_end_multiples(df)
    assert pes == [25.0, 22.0]
    assert pbs == [8.0, 7.0]


def test_sample_quarter_end_multiples_empty_dataframe():
    pes, pbs = sample_quarter_end_multiples(pd.DataFrame())
    assert pes == []
    assert pbs == []


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_historical_multiples_writes_series(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.daily.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "trade_date": "20250630",
        "close": 1680.0,
    }])
    pro.daily_basic.side_effect = [
        pd.DataFrame([{
            "ts_code": "600519.SH",
            "trade_date": "20250630",
            "pe_ttm": 25.5,
            "pb": 8.2,
            "total_mv": 2100000.0,
            "total_share": 125619.0,
        }]),
        _make_quarterly_daily_basic(),
    ]
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_quote("600519", "SH")
    assert result.ok
    assert result.data["historical_pe"] is not None
    assert len(result.data["historical_pe"]) >= 15
    assert result.data["historical_pb"] is not None
    assert len(result.data["historical_pb"]) >= 15
    assert "historical_pe" not in result.missing_fields
    assert "historical_pb" not in result.missing_fields


@patch("tushare.set_token")
@patch("tushare.pro_api")
def test_fetch_historical_multiples_insufficient_points(mock_pro_api, mock_set_token):
    pro = MagicMock()
    pro.daily.return_value = pd.DataFrame([{
        "ts_code": "600519.SH",
        "trade_date": "20250630",
        "close": 1680.0,
    }])
    pro.daily_basic.side_effect = [
        pd.DataFrame([{
            "ts_code": "600519.SH",
            "trade_date": "20250630",
            "pe_ttm": 25.5,
            "pb": 8.2,
        }]),
        pd.DataFrame([
            {"trade_date": "20250331", "pe_ttm": 25.0, "pb": 8.0},
            {"trade_date": "20241231", "pe_ttm": 24.0, "pb": 7.5},
        ]),
    ]
    mock_pro_api.return_value = pro
    fetcher = TushareFetcher(token="fake-token")

    result = fetcher.fetch_quote("600519", "SH")
    assert result.ok
    assert "historical_pe" in result.missing_fields
    assert "historical_pb" in result.missing_fields
    assert result.data.get("historical_pe") is None
    assert result.data.get("historical_pb") is None
