"""飞书 push 管道测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from common.config_loader import FeishuConfig
from service.feishu.pipeline import run_feishu_push
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


def _write_dual(code: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"# 红蓝对抗证据分桶 {code}\n", encoding="utf-8")


def test_pipeline_skips_weekend(tmp_path: Path):
    pub = FakePublisher()
    outcome = run_feishu_push(
        ["600519"],
        config={},
        write_dual=_write_dual,
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


def test_pipeline_dry_run_writes_dual_path(tmp_path: Path):
    pub = FakePublisher()
    outcome = run_feishu_push(
        ["600519", "002594"],
        config={},
        write_dual=_write_dual,
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
    for code in ("600519", "002594"):
        path = Path(outcome.local_paths[code])
        assert path.name == f"{code}_dual.md"
        assert "2026-08-14" in str(path)
        assert "0900" in str(path)
        assert "红蓝对抗" in path.read_text(encoding="utf-8")
    assert all(c["dry_run"] for c in pub.calls)


def test_pipeline_one_failure_continues(tmp_path: Path):
    def write(code: str, dest: Path) -> None:
        if code == "bad":
            raise RuntimeError("dual boom")
        _write_dual(code, dest)

    outcome = run_feishu_push(
        ["600519", "bad"],
        config={},
        write_dual=write,
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
            write_dual=_write_dual,
            reports_dir=tmp_path,
            slot="1700",
            dry_run=False,
            publisher=NoBin(),
            today=date(2026, 8, 14),
            feishu_cfg=_cfg(),
            do_sync=False,
        )
