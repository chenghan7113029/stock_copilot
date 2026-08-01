"""CLI Checklist 提交与查询测试。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from apps.cli import main, run_checklist_show, run_checklist_submit
from apps.formatters import format_checklist_records


def _input_values(*values: str):
    return iter(values)


@patch("apps.cli.ChecklistRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_checklist_submit_passes_and_persists(mock_cfg, mock_engine, mock_session_factory, mock_repo, capsys):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)
    responses = _input_values(
        "PE 处于历史低分位，安全边际充足，当前价格低于合理估值区间。",
        "现金流稳健，ROE 持续高于行业均值，基本面仍有韧性。",
        "",
        "价格回到 MA20 上方，成交量温和放大。",
        "市场情绪偏谨慎，尚未出现极端贪婪。",
        "1400",
        "1800",
    )

    with patch("builtins.input", side_effect=lambda _: next(responses)):
        run_checklist_submit("600519", action="buy")

    assert "Checklist 提交成功（合规）" in capsys.readouterr().out
    mock_repo.return_value.save.assert_called_once()
    session.commit.assert_called_once()


@patch("apps.cli.ChecklistRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_checklist_submit_rejection_is_persisted(mock_cfg, mock_engine, mock_session_factory, mock_repo, capsys):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)
    responses = _input_values(
        "PE 很低，值得买入。",
        "",
        "价格回到 MA20 上方。",
        "市场情绪偏谨慎。",
        "1400",
        "1800",
    )

    with patch("builtins.input", side_effect=lambda _: next(responses)):
        run_checklist_submit("600519", action="buy")

    assert "本次提交不构成合规 Checklist" in capsys.readouterr().out
    mock_repo.return_value.save.assert_called_once()
    session.commit.assert_called_once()


@patch("apps.cli.ChecklistRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_checklist_show_with_and_without_records(
    mock_cfg, mock_engine, mock_session_factory, mock_repo, capsys
):
    session = MagicMock()
    mock_session_factory.return_value = MagicMock(return_value=session)
    mock_repo.return_value.list_by_code.return_value = []

    run_checklist_show("600519")

    assert "暂无 600519 的 Checklist 记录" in capsys.readouterr().out
    mock_repo.return_value.list_by_code.return_value = [
        MagicMock(
            code="600519",
            action="buy",
            passed=True,
            created_at=datetime(2026, 8, 1, 10, 0),
            value_reasons=["PE 低估"],
            tech_alignment="站上 MA20",
            sentiment_position="偏谨慎",
            stop_loss_price=1400.0,
            take_profit_price=1800.0,
            rejection_reasons=[],
        )
    ]

    run_checklist_show("600519", as_json=True)

    assert '"code": "600519"' in capsys.readouterr().out


@patch("apps.cli.run_checklist_show")
@patch("apps.cli.run_checklist_submit")
def test_checklist_commands_are_routed(mock_submit, mock_show):
    main(["checklist", "submit", "600519", "--action", "buy"])
    mock_submit.assert_called_once_with("600519", action="buy", config=None)

    main(["checklist", "show", "600519", "--json"])
    mock_show.assert_called_once_with("600519", as_json=True, config=None)


def test_format_checklist_records_text():
    record = MagicMock(
        code="600519",
        action="buy",
        passed=False,
        created_at=datetime(2026, 8, 1, 10, 0),
        value_reasons=["昨晚看新闻说要涨"],
        tech_alignment="站上 MA20",
        sentiment_position="偏热",
        stop_loss_price=1400.0,
        take_profit_price=1800.0,
        rejection_reasons=["价值理由不足 2 条"],
    )

    text = format_checklist_records("600519", [record])

    assert "不合规" in text
    assert "价值理由不足 2 条" in text
