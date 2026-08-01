"""锚定防御呈现规则测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dao.engine import Base
from dao.kline_repo import KlineRepo
from dao.models import Kline
from service.value.anchor import historical_high, percentile_band


@pytest.mark.parametrize(
    ("percentile", "expected"),
    [
        (0.0, "历史估值区间低位"),
        (19.9, "历史估值区间低位"),
        (20.0, "历史估值区间中低位"),
        (39.9, "历史估值区间中低位"),
        (40.0, "历史估值区间中性"),
        (59.9, "历史估值区间中性"),
        (60.0, "历史估值区间中高位"),
        (79.9, "历史估值区间中高位"),
        (80.0, "历史估值区间高位"),
        (100.0, "历史估值区间高位"),
    ],
)
def test_percentile_band_maps_representative_and_boundary_values(percentile: float, expected: str):
    assert percentile_band(percentile) == expected


def test_historical_high_reads_only_local_kline_cache():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        session.add_all(
            [
                Kline(code="600519", trade_date="2026-01-02", high=1500.0, close=1490.0),
                Kline(code="600519", trade_date="2026-01-03", high=1520.0, close=1530.0),
                Kline(code="600519", trade_date="2026-01-04", high=None, close=1510.0),
            ]
        )
        session.commit()

        assert historical_high("600519", KlineRepo(session)) == (1530.0, 3)
    finally:
        session.close()
        engine.dispose()


def test_historical_high_returns_none_without_local_kline_cache():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        assert historical_high("600519", KlineRepo(session)) is None
    finally:
        session.close()
        engine.dispose()
