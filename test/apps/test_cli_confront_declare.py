"""CLI confront declare / show 测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.cli import main, run_confront_declare, run_confront_show
from dao.confrontation_repo import DECLARE_OK


def _record(*, declare_status=None, declaration=None):
    rec = MagicMock()
    rec.id = 12
    rec.code = "600519"
    rec.narrate_status = "skipped"
    rec.declare_status = declare_status
    rec.declared_at = None
    rec.created_at = None
    rec.evidence = {
        "bull_evidence": [{"index": 1, "text": "低估"}],
        "bear_evidence": [{"index": 1, "text": "风险"}, {"index": 2, "text": "风险2"}],
    }
    rec.declaration = declaration
    return rec


@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_confront_declare_json_file_ok(mock_cfg, mock_engine, mock_sf, mock_repo, tmp_path, capsys):
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_repo.return_value.get.return_value = _record()

    payload = {
        "stance": "adopt_bull",
        "adopted_side": "bull",
        "rejected_side": "bear",
        "adopted_evidence_refs": {"bull": [1], "bear": []},
        "rejected_evidence_refs": {"bull": [], "bear": [2]},
        "rejection_rationale": "拒绝空方[2]：证据偏弱",
        "confidence": 0.7,
    }
    path = tmp_path / "declare.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    run_confront_declare(12, json_file=str(path))

    mock_repo.return_value.update_declare.assert_called_once()
    assert "Declare 已保存" in capsys.readouterr().out


@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_confront_declare_rejects_out_of_range(mock_cfg, mock_engine, mock_sf, mock_repo, tmp_path, capsys):
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_repo.return_value.get.return_value = _record()

    payload = {
        "stance": "adopt_bull",
        "adopted_side": "bull",
        "rejected_side": "bear",
        "adopted_evidence_refs": {"bull": [1], "bear": []},
        "rejected_evidence_refs": {"bull": [], "bear": [99]},
        "rejection_rationale": "拒绝空方[99]",
        "confidence": 0.7,
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        run_confront_declare(12, json_file=str(path))
    assert exc.value.code == 1
    assert "Declare 校验失败" in capsys.readouterr().err


@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_confront_declare_rejects_duplicate(mock_cfg, mock_engine, mock_sf, mock_repo, tmp_path, capsys):
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_repo.return_value.get.return_value = _record(declare_status=DECLARE_OK)

    payload = {
        "stance": "adopt_bull",
        "adopted_side": "bull",
        "rejected_side": "bear",
        "adopted_evidence_refs": {"bull": [1], "bear": []},
        "rejected_evidence_refs": {"bull": [], "bear": [1]},
        "rejection_rationale": "拒绝空方[1]",
        "confidence": 0.5,
    }
    path = tmp_path / "dup.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(SystemExit):
        run_confront_declare(12, json_file=str(path))
    assert "不允许覆盖" in capsys.readouterr().err


@patch("apps.cli.ConfrontationRepo")
@patch("apps.cli.make_session_factory")
@patch("apps.cli.create_db_engine")
@patch("apps.cli.load_app_config", return_value={})
def test_confront_show_empty(mock_cfg, mock_engine, mock_sf, mock_repo, capsys):
    session = MagicMock()
    mock_sf.return_value = MagicMock(return_value=session)
    mock_repo.return_value.list_by_code.return_value = []
    run_confront_show("600519")
    assert "暂无 600519 的 confrontation 记录" in capsys.readouterr().out


@patch("apps.cli.run_confront_declare")
def test_confront_declare_routes(mock_run):
    main(["confront", "declare", "12", "--json-file", "x.json"])
    mock_run.assert_called_once()
