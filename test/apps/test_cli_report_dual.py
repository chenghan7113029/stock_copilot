"""CLI report dual 命令测试。"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_dual
from apps.formatters import format_dual_report
from service.dual_track.models.report import CombinedSignal, DualTrackReport, ValueRating
from service.sentiment.models.sentiment_result import SentimentAnalysisResult, SentimentStatus
from service.tech.models.tech_result import BuySignal, TechAnalysisResult, TrendStatus
from service.value.models.analysis_result import ValueAnalysisResult


def _dual_report(*, with_value: bool = True, with_tech: bool = True) -> DualTrackReport:
    value = None
    if with_value:
        value = ValueAnalysisResult(
            code="600519",
            name="贵州茅台",
            current_price=1500.0,
            prototype="value_growth",
            method_keys_used=[],
            fair_value_range=None,
            margin_of_safety=25.0,
            price_percentile=None,
            assessment="低估",
            confidence="High",
            data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
        )
    tech = None
    if with_tech:
        tech = TechAnalysisResult(
            code="600519",
            trend_status=TrendStatus.STRONG_BULL,
            signal_score=80,
            buy_signal=BuySignal.STRONG_BUY,
            signal_reasons=["MA5 上穿 MA20"],
            risk_factors=[],
            data_timestamp=datetime(2026, 6, 21, tzinfo=timezone.utc),
        )
    return DualTrackReport(
        code="600519",
        value_result=value,
        tech_result=tech,
        combined_signal=CombinedSignal.STRONG_BUY,
        value_rating=ValueRating.UNDERVALUED if with_value else None,
        analysis_summary="股票代码: 600519 | 综合信号: 强烈买入",
    )


@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dual_success(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["[价值评级] 低估", "[技术信号] MA5 上穿 MA20"]
    buckets.bear_evidence = ["[假设脆弱性] DCF 依赖增长率假设"]
    mock_bucketer_cls.return_value.bucket.return_value = buckets

    run_report_dual("600519")
    captured = capsys.readouterr()
    assert "红蓝对抗证据分桶" in captured.out
    assert "低估" in captured.out
    mock_dual_cls.return_value.analyze_offline.assert_called_once_with("600519")


@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dual_json(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["bull-1"]
    buckets.bear_evidence = ["bear-1"]
    mock_bucketer_cls.return_value.bucket.return_value = buckets

    run_report_dual("600519", as_json=True)
    captured = capsys.readouterr()
    assert '"bull_evidence"' in captured.out
    assert '"bear_evidence"' in captured.out
    assert "bull-1" in captured.out


@patch("apps.cli.EvidenceBucketer")
@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dual_output_file(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    mock_bucketer_cls,
    tmp_path: Path,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_dual_cls.return_value.analyze_offline.return_value = _dual_report()
    buckets = MagicMock()
    buckets.bull_evidence = ["bull-1"]
    buckets.bear_evidence = ["bear-1"]
    mock_bucketer_cls.return_value.bucket.return_value = buckets

    out = tmp_path / "dual.json"
    run_report_dual("600519", as_json=True, output=str(out))
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "bull_evidence" in text


@patch("apps.cli.DualTrackAnalyzer")
@patch("apps.cli.TechAnalyzer")
@patch("apps.cli.ValueAnalyzer")
@patch("apps.cli.StockSnapshotRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_dual_no_cache(
    mock_cfg,
    mock_sf,
    mock_engine,
    mock_repo_cls,
    mock_value_cls,
    mock_tech_cls,
    mock_dual_cls,
    capsys,
):
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    tech = TechAnalysisResult(
        code="600519",
        warnings=["无K线缓存"],
        risk_factors=["无K线缓存，请先运行 sync"],
    )
    mock_dual_cls.return_value.analyze_offline.return_value = DualTrackReport(
        code="600519",
        value_result=None,
        tech_result=tech,
        warnings=["价值面无本地快照，请先运行 sync"],
    )

    with pytest.raises(SystemExit) as exc:
        run_report_dual("600519")
    assert exc.value.code == 1
    captured = capsys.readouterr()
    assert "未找到 600519 的本地数据" in captured.err


@patch("apps.cli.run_report_dual")
def test_cli_report_dual_invocation(mock_run):
    main(["report", "dual", "600519", "--json"])
    mock_run.assert_called_once_with("600519", as_json=True, output=None, config=None)


def test_format_dual_report_text_and_json():
    text = format_dual_report("600519", ["b1"], ["e1"], analysis_summary="摘要")
    assert "多方证据" in text
    assert "[1] b1" in text
    js = format_dual_report("600519", ["b1"], ["e1"], as_json=True)
    assert '"code": "600519"' in js
    assert '"bull_evidence"' in js


def test_format_dual_report_displays_sentiment_summary():
    sentiment = SentimentAnalysisResult(
        code="600519",
        market_sentiment_status=SentimentStatus.GREED,
        market_sentiment_score=70.0,
        limit_updown_ratio=0.75,
    )

    text = format_dual_report("600519", [], [], sentiment_result=sentiment)

    assert "市场情绪: 贪婪" in text
