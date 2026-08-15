"""可选 sync → dual.md → lark-cli 新建文档并立即发消息。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

from common.config_loader import FeishuConfig, resolve_feishu_config
from common.trading_day import is_a_share_trading_day
from common.watchlist import load_watchlist
from service.feishu.paths import dual_md_path
from service.feishu.publisher import FeishuPublisherError, LarkCliPublisher

SyncFn = Callable[[str], None]
DualWriter = Callable[[str, Path], None]


@dataclass
class PushRunResult:
    skipped: bool = False
    skip_reason: str = ""
    succeeded: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    local_paths: dict[str, str] = field(default_factory=dict)


def reports_root(config: dict[str, Any], repo_root: Path) -> Path:
    raw = (config.get("reports") or {}).get("dir") or "reports"
    path = Path(raw)
    return path if path.is_absolute() else repo_root / path


def run_feishu_push(
    codes: list[str],
    *,
    config: dict[str, Any],
    write_dual: DualWriter,
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
        dest = dual_md_path(reports_dir, day=today, slot=slot, code=code)
        try:
            write_dual(code, dest)
            if not dest.exists():
                raise FeishuPublisherError(f"未写出 dual.md：{dest}")
            result.local_paths[code] = str(dest)
            published = pub.publish(
                code=code,
                name=names.get(code) or code,
                md_path=dest,
                slot=slot,
                day_iso=day_iso,
                dry_run=dry_run,
            )
            if published.error:
                result.failed.append((code, published.error))
            else:
                result.succeeded.append(code)
        except Exception as exc:  # noqa: BLE001
            result.failed.append((code, str(exc)))
    return result
