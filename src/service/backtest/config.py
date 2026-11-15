"""`config/app.yaml` 的 `backtest:` 段装载（design §4.1 / QA-F11）。

解析顺序（design §6.3，唯一真源）：
`--config <path>`（相对路径按 **cwd**）> `config/app.yaml`（**cwd**/config/app.yaml）
> 缺失 / 段缺键 → `MissingBacktestConfigError`（CLI 退出码 1）。

纪律：本模块只负责「把段读出来」，不填任何业务数值；缺键由
`BacktestConfig.require()` / 各消费方在用到时拒绝。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml

from common.exceptions import MissingBacktestConfigError
from service.backtest.models import BacktestConfig

DEFAULT_CONFIG_FILE = Path("config") / "app.yaml"
BACKTEST_SECTION = "backtest"


def load_yaml_config(path: Path) -> Mapping[str, Any]:
    if not path.exists():
        raise MissingBacktestConfigError(f"配置文件不存在: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - 语法错误直接上报
        raise MissingBacktestConfigError(f"配置文件无法解析: {path}: {exc}") from exc
    if not isinstance(data, Mapping):
        raise MissingBacktestConfigError(f"配置文件顶层不是映射: {path}")
    return data


def backtest_section(config: Mapping[str, Any], *, source: str = "<mapping>") -> Mapping[str, Any]:
    section = config.get(BACKTEST_SECTION)
    if not isinstance(section, Mapping):
        raise MissingBacktestConfigError(f"{source} 缺少 `{BACKTEST_SECTION}:` 段")
    return section


def resolve_backtest_config(
    config_path: str | Path | None = None,
    *,
    cwd: Path | None = None,
    require_pipeline: bool = True,
) -> BacktestConfig:
    """按 design §6.3 的顺序解析配置；相对 `--config` 与默认路径都按 cwd 解析。"""
    base = Path(cwd) if cwd is not None else Path.cwd()
    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = base / path
    else:
        path = base / DEFAULT_CONFIG_FILE
    config = load_yaml_config(path)
    section = backtest_section(config, source=str(path))
    cfg = BacktestConfig.from_config(section, base_dir=base, require_pipeline=require_pipeline)
    return BacktestConfig(
        results_dir=cfg.results_dir,
        registry_store_path=cfg.registry_store_path,
        prereg_dir=cfg.prereg_dir,
        params=cfg.params,
        source_path=path,
    )
