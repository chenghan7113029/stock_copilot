"""可选 sync → confront / persona-stress.md → lark-cli 新建文档并立即发消息。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from common.config_loader import FeishuConfig, resolve_feishu_config
from common.trading_day import is_a_share_trading_day
from common.watchlist import load_watchlist
from service.feishu.publisher import FeishuPublisherError, LarkCliPublisher

SyncFn = Callable[[str], None]
ReportWriter = Callable[[str, Path, str, date], list["FeishuPushDocument"]]


@dataclass(frozen=True)
class FeishuPushDocument:
    kind: str
    path: Path
    title_tag: str


@dataclass
class PushRunResult:
    skipped: bool = False
    skip_reason: str = ""
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    local_paths: dict[str, list[str]] = field(default_factory=dict)
    doc_succeeded: int = 0
    doc_total: int = 0


def reports_root(config: dict[str, Any], repo_root: Path) -> Path:
    raw = (config.get("reports") or {}).get("dir") or "reports"
    path = Path(raw)
    return path if path.is_absolute() else repo_root / path


def run_feishu_push(
    codes: list[str],
    *,
    config: dict[str, Any],
    write_reports: ReportWriter,
    reports_dir: Path,
    slot: str,
    dry_run: bool,
    do_sync: bool | None = None,
    sync_fn: SyncFn | None = None,
    publisher: LarkCliPublisher | None = None,
    today: date | None = None,
    feishu_cfg: FeishuConfig | None = None,
) -> PushRunResult:
    today = today or date.today()
    feishu_cfg = feishu_cfg or resolve_feishu_config(config)
    result = PushRunResult()

    if feishu_cfg.trading_days_only and not is_a_share_trading_day(today, feishu_cfg.holidays):
        result.skipped = True
        result.skip_reason = f"非交易日，跳过飞书推送（{today.isoformat()}）"
        return result

    pub = publisher or LarkCliPublisher(feishu_cfg)
    if not dry_run:
        pub.resolve_binary()

    want_sync = feishu_cfg.sync_before_push if do_sync is None else do_sync
    if want_sync:
        if sync_fn is None:
            raise FeishuPublisherError("已启用 sync_before_push 但未提供 sync 回调")
        for code in codes:
            sync_fn(code)

    names = {item["code"]: item.get("name", "") for item in load_watchlist()}
    day_iso = today.isoformat()

    for code in codes:
        stock_paths: list[str] = []
        stock_failed = False
        try:
            docs = write_reports(code, reports_dir, slot, today)
            if not docs:
                raise FeishuPublisherError(f"{code} 未生成任何推送文档")
            result.doc_total += len(docs)
            for doc in docs:
                if not doc.path.exists():
                    raise FeishuPublisherError(f"未写出 markdown：{doc.path}")
                stock_paths.append(str(doc.path))
                published = pub.publish(
                    code=code,
                    name=names.get(code) or code,
                    md_path=doc.path,
                    slot=slot,
                    day_iso=day_iso,
                    dry_run=dry_run,
                    title_tag=doc.title_tag,
                )
                if published.error:
                    result.failed.append((f"{code}/{doc.kind}", published.error))
                    stock_failed = True
                else:
                    result.doc_succeeded += 1
            if not stock_failed:
                result.succeeded.append(code)
            if stock_paths:
                result.local_paths[code] = stock_paths
        except Exception as exc:  # noqa: BLE001
            result.failed.append((code, str(exc)))
    return result
