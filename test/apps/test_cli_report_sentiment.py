import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_report_sentiment
from apps.formatters import format_sentiment_report
from service.sentiment.models.sentiment_result import SentimentAnalysisResult, SentimentStatus


def _result() -> SentimentAnalysisResult:
    return SentimentAnalysisResult(
        code="600519",
        market_sentiment_status=SentimentStatus.GREED,
        market_sentiment_score=70.0,
        limit_updown_ratio=0.75,
        data_timestamp=datetime(2026, 8, 1),
    )


def test_format_sentiment_report_includes_required_disclaimer() -> None:
    text = format_sentiment_report(_result())

    assert "情绪面结论不得单独作为买卖依据" in text
    assert "report dual 600519" in text


def test_format_sentiment_report_json_contains_disclaimer() -> None:
    payload = json.loads(format_sentiment_report(_result(), as_json=True))

    assert "disclaimer" in payload


@patch("apps.cli.SentimentAnalyzer")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_sentiment_success(mock_cfg, mock_sf, mock_engine, mock_repo, mock_analyzer, capsys) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = _result()

    run_report_sentiment("600519")

    assert "情绪面分析报告" in capsys.readouterr().out


@patch("apps.cli.SentimentAnalyzer")
@patch("apps.cli.MarketSentimentRepo")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.load_app_config")
def test_report_sentiment_without_cache_exits(
    mock_cfg, mock_sf, mock_engine, mock_repo, mock_analyzer, capsys
) -> None:
    mock_cfg.return_value = {}
    mock_sf.return_value = MagicMock(return_value=MagicMock())
    mock_analyzer.return_value.analyze_offline.return_value = None

    with pytest.raises(SystemExit) as exc:
        run_report_sentiment("600519")

    assert exc.value.code == 1
    assert "未找到市场情绪数据，请先运行 sync market" in capsys.readouterr().err


@patch("apps.cli.run_report_sentiment")
def test_cli_report_sentiment_invocation(mock_run) -> None:
    main(["report", "sentiment", "600519", "--json"])

    mock_run.assert_called_once_with("600519", as_json=True, output=None, config=None)
