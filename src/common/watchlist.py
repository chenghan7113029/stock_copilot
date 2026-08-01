"""个人常看股票列表（config/watchlist.yaml）。

与 value_data_validation_stocks.yaml（E2E 验证样本）分离；本文件入库以便多设备同步。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).parent.parent.parent
_WATCHLIST_YAML = _REPO_ROOT / "config" / "watchlist.yaml"

_HEADER = """# 个人常看股票列表（入库，便于多设备 git 同步）
#
# 与 value_data_validation_stocks.yaml（E2E 验证样本）职责分离。
# 维护方式：
#   python -m apps.cli watchlist list|add|remove
# 批量：
#   python -m apps.cli sync --watchlist
#   python -m apps.cli report value --watchlist

"""


def watchlist_path() -> Path:
    return _WATCHLIST_YAML


def _require_yaml():
    try:
        import yaml  # type: ignore[import]
    except ImportError as exc:
        raise ImportError("缺少 pyyaml，请运行 pip install pyyaml") from exc
    return yaml


def load_watchlist(*, path: Path | None = None) -> list[dict[str, str]]:
    """加载常看列表。文件不存在时返回空列表。每项至少含 code，可选 name。"""
    yaml = _require_yaml()
    target = path or _WATCHLIST_YAML
    if not target.exists():
        return []
    with target.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    stocks: list[dict[str, Any]] = data.get("stocks") or []
    result: list[dict[str, str]] = []
    for item in stocks:
        if not isinstance(item, dict):
            continue
        code = str(item.get("code", "")).strip()
        if not code:
            continue
        entry: dict[str, str] = {"code": code}
        name = item.get("name")
        if name is not None and str(name).strip():
            entry["name"] = str(name).strip()
        result.append(entry)
    return result


def save_watchlist(stocks: list[dict[str, str]], *, path: Path | None = None) -> Path:
    """写回常看列表（覆盖写入，保留文件头注释）。"""
    yaml = _require_yaml()
    target = path or _WATCHLIST_YAML
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {"stocks": stocks}
    body = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False)
    target.write_text(_HEADER + body, encoding="utf-8")
    return target


def normalize_code(code: str) -> str:
    return str(code).strip()


def add_to_watchlist(
    code: str,
    *,
    name: str | None = None,
    path: Path | None = None,
) -> tuple[list[dict[str, str]], bool]:
    """加入常看列表。返回 (新列表, 是否新添加)。已存在时仅更新 name（若提供）。"""
    code = normalize_code(code)
    if not code:
        raise ValueError("股票代码不能为空")
    stocks = load_watchlist(path=path)
    for item in stocks:
        if item["code"] == code:
            if name is not None and str(name).strip():
                item["name"] = str(name).strip()
                save_watchlist(stocks, path=path)
            return stocks, False
    entry: dict[str, str] = {"code": code}
    if name is not None and str(name).strip():
        entry["name"] = str(name).strip()
    stocks.append(entry)
    save_watchlist(stocks, path=path)
    return stocks, True


def remove_from_watchlist(code: str, *, path: Path | None = None) -> tuple[list[dict[str, str]], bool]:
    """从常看列表移除。返回 (新列表, 是否确实删除)。"""
    code = normalize_code(code)
    stocks = load_watchlist(path=path)
    new_stocks = [s for s in stocks if s["code"] != code]
    removed = len(new_stocks) < len(stocks)
    if removed:
        save_watchlist(new_stocks, path=path)
    return new_stocks, removed


def watchlist_codes(*, path: Path | None = None) -> list[str]:
    return [s["code"] for s in load_watchlist(path=path)]
