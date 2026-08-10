#!/usr/bin/env python3
"""探测当前 Token 是否具备 Tushare rt_k 权限。

用法（仓库根目录，已配置 TUSHARE_TOKEN）：
  python scripts/verify_rt_k_access.py [code]

无权限或失败时以非零退出码结束，便于 CI / 人工确认 OQ-1。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    code = (args[0] if args else "600519").strip()
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        print("SKIP: 未设置 TUSHARE_TOKEN", file=sys.stderr)
        return 0

    from common.exceptions import DataProviderError
    from data_provider.tushare.fetcher import TushareFetcher

    try:
        quote = TushareFetcher(token=token).fetch_realtime_quote(code)
    except DataProviderError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: 未预期错误: {exc}", file=sys.stderr)
        return 1

    print(f"OK: rt_k {code} close={quote.get('close')} date={quote.get('date')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
