"""飞书 push 管道测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from common.config_loader import FeishuConfig
from service.feishu.pipeline import FeishuPushDocument, run_feishu_push
from service.feishu.publisher import FeishuPublisherError, PublishResult


class FakePublisher:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def resolve_binary(self) -> str:
        return "lark-cli"

    def publish(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("dry_run"):
            return PublishResult(code=kwargs["code"], doc_url="", title="t", dry_run=True)
        return PublishResult(
            code=kwargs["code"],
            doc_url="https://feishu.cn/docx/x",
            title="t",
            dry_run=False,
        )


def _cfg(**kwargs) -> FeishuConfig:
    data = dict(lark_cli="lark-cli", chat_id="oc", trading_days_only=True, sync_before_push=False)
    data.update(kwargs)
    return FeishuConfig(**data)


def _write_reports(code: str, reports_dir: Path, slot: str, today: date) -> list[FeishuPushDocument]:
    confront = reports_dir / "feishu" / today.isoformat() / slot / f"{code}_confront.md"
    persona = reports_dir / "feishu" / today.isoformat() / slot / f"{code}_persona-stress.md"
    confront.parent.mkdir(parents=True, exist_ok=True)
    confront.write_text(f"# 红蓝对抗报告 {code}\n**confrontation_id:** 1\n", encoding="utf-8")
    persona.write_text(f"# Persona 压力测试 {code}\n", encoding="utf-8")
    return [
        FeishuPushDocument(kind="confront", path=confront, title_tag="红蓝对抗"),
        FeishuPushDocument(kind="persona-stress", path=persona, title_tag="Persona压力"),
    ]


def test_pipeline_skips_weekend(tmp_path: Path):
    pub = FakePublisher()
    outcome = run_feishu_push(
        ["600519"],
        config={},
        write_reports=_write_reports,
        reports_dir=tmp_path,
        slot="1700",
        dry_run=False,
        publisher=pub,
        today=date(2026, 8, 15),
        feishu_cfg=_cfg(),
        do_sync=False,
    )
    assert outcome.skipped is True
    assert pub.calls == []


def test_pipeline_dry_run_writes_two_docs_per_code(tmp_path: Path):
    pub = FakePublisher()
    outcome = run_feishu_push(
        ["600519", "002594"],
        config={},
        write_reports=_write_reports,
        reports_dir=tmp_path,
        slot="0900",
        dry_run=True,
        publisher=pub,
        today=date(2026, 8, 14),
        feishu_cfg=_cfg(),
        do_sync=False,
    )
    assert outcome.failed == []
    assert outcome.succeeded == ["600519", "002594"]
    assert outcome.doc_succeeded == 4
    assert outcome.doc_total == 4
    for code in ("600519", "002594"):
        paths = outcome.local_paths[code]
        assert len(paths) == 2
        assert any(p.endswith(f"{code}_confront.md") for p in paths)
        assert any(p.endswith(f"{code}_persona-stress.md") for p in paths)
    assert all(c["dry_run"] for c in pub.calls)
    assert len(pub.calls) == 4


def test_pipeline_one_failure_continues(tmp_path: Path):
    def write(code: str, reports_dir: Path, slot: str, today: date) -> list[FeishuPushDocument]:
        if code == "bad":
            raise RuntimeError("report boom")
        return _write_reports(code, reports_dir, slot, today)

    outcome = run_feishu_push(
        ["600519", "bad"],
        config={},
        write_reports=write,
        reports_dir=tmp_path,
        slot="1300",
        dry_run=True,
        publisher=FakePublisher(),
        today=date(2026, 8, 14),
        feishu_cfg=_cfg(),
        do_sync=False,
    )
    assert outcome.succeeded == ["600519"]
    assert outcome.failed[0][0] == "bad"


def test_pipeline_missing_cli_before_write(tmp_path: Path):
    class NoBin(FakePublisher):
        def resolve_binary(self) -> str:
            raise FeishuPublisherError("未找到 lark-cli")

    with pytest.raises(FeishuPublisherError, match="lark-cli"):
        run_feishu_push(
            ["600519"],
            config={},
            write_reports=_write_reports,
            reports_dir=tmp_path,
            slot="1700",
            dry_run=False,
            publisher=NoBin(),
            today=date(2026, 8, 14),
            feishu_cfg=_cfg(),
            do_sync=False,
        )
