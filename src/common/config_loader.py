"""应用配置加载器。

职责：
- load_app_config()：从 config/app.yaml 加载运行时配置；
  若 app.yaml 不存在，从 app.example.yaml 自动复制并创建 data/ 目录。
- load_validation_stocks()：加载 config/value_data_validation_stocks.yaml，
  返回样本股票列表（E2E 测试 / fetch 脚本的单一真源）。
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 以仓库根为基准（本文件位于 src/common/，向上两层）
_REPO_ROOT = Path(__file__).parent.parent.parent
_CONFIG_DIR = _REPO_ROOT / "config"
_APP_YAML = _CONFIG_DIR / "app.yaml"
_APP_EXAMPLE_YAML = _CONFIG_DIR / "app.example.yaml"
_VALIDATION_STOCKS_YAML = _CONFIG_DIR / "value_data_validation_stocks.yaml"
_DATA_DIR = _REPO_ROOT / "data"


def _ensure_yaml_available():
    """若 app.yaml 不存在，从 example 复制；同时确保 data/ 目录存在。"""
    _DATA_DIR.mkdir(exist_ok=True)
    if not _APP_YAML.exists():
        if not _APP_EXAMPLE_YAML.exists():
            raise FileNotFoundError(
                f"找不到 {_APP_EXAMPLE_YAML}，无法初始化 config/app.yaml"
            )
        shutil.copy(_APP_EXAMPLE_YAML, _APP_YAML)
        logger.info("已从 app.example.yaml 创建 %s", _APP_YAML)


def load_app_config() -> dict[str, Any]:
    """加载并返回 config/app.yaml 的内容（dict）。

    缺少 app.yaml 时，自动从 example 复制（bootstrap）。
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        raise ImportError("缺少 pyyaml，请运行 pip install pyyaml")

    _ensure_yaml_available()
    with _APP_YAML.open(encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    logger.debug("已加载 config/app.yaml")
    return config


def load_validation_stocks() -> list[dict[str, str]]:
    """加载样本股票清单，返回列表，每项包含 code / name / prototype。

    示例返回：
        [{"code": "601398", "name": "工商银行", "prototype": "bank"}, ...]
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        raise ImportError("缺少 pyyaml，请运行 pip install pyyaml")

    if not _VALIDATION_STOCKS_YAML.exists():
        raise FileNotFoundError(f"找不到 {_VALIDATION_STOCKS_YAML}")
    with _VALIDATION_STOCKS_YAML.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    stocks: list[dict[str, str]] = data.get("stocks", [])
    logger.debug("加载了 %d 只样本股票", len(stocks))
    return stocks


@dataclass(frozen=True)
class LLMConfig:
    """LLM Client 配置（OpenAI 兼容协议）。"""

    base_url: str
    model: str
    api_key: str
    max_evidence_chars: int = 24_000


def resolve_llm_config(config: dict[str, Any] | None = None) -> LLMConfig | None:
    """解析 LLM 配置。

    优先级：config/app.yaml 的 llm.api_key > 环境变量 LLM_API_KEY。
    无 api_key 且无环境变量时返回 None（调用方应降级，不实例化 client）。
    """
    if config is None:
        config = load_app_config()
    llm_cfg = config.get("llm") or {}
    api_key = (llm_cfg.get("api_key") or "").strip()
    if not api_key:
        api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    base_url = (llm_cfg.get("base_url") or "https://api.openai.com/v1").strip()
    model = (llm_cfg.get("model") or "gpt-4o-mini").strip()
    max_chars = int(llm_cfg.get("max_evidence_chars") or 24_000)
    return LLMConfig(
        base_url=base_url,
        model=model,
        api_key=api_key,
        max_evidence_chars=max_chars,
    )


def is_data_source_enabled(config: dict[str, Any] | None, name: str) -> bool:
    """判断 data_sources.enabled 是否包含指定源（大小写不敏感）。

    未出现在 enabled 列表的源不应被实例化或联网调用（含 K 线备源、筹码、情绪等旁路）。
    """
    if not config:
        return False
    target = name.strip().lower()
    for src in config.get("data_sources", {}).get("enabled", []) or []:
        if str(src.get("name", "")).strip().lower() == target:
            return True
    return False


def resolve_tushare_token(config: dict[str, Any] | None = None) -> str | None:
    """解析 Tushare Pro Token。

    优先级：config/app.yaml 中 tushare 条目的 token > 环境变量 TUSHARE_TOKEN。
    Token 仅存在于本地配置或环境变量，切勿提交到 Git 或粘贴到公开渠道。
    """
    if config is None:
        config = load_app_config()
    for src in config.get("data_sources", {}).get("enabled", []):
        if src.get("name", "").lower() == "tushare":
            cfg_token = (src.get("token") or "").strip()
            if cfg_token:
                return cfg_token
    env_token = os.environ.get("TUSHARE_TOKEN", "").strip()
    return env_token or None


def has_tushare_token(config: dict[str, Any] | None = None) -> bool:
    """是否已配置可用的 Tushare Token（用于网络测试 skip 判断）。"""
    return resolve_tushare_token(config) is not None


def verify_tushare_access(config: dict[str, Any] | None = None) -> bool:
    """探测 Token 是否具备至少一个 Pro 接口权限（如 stock_basic）。

    新注册账号需完成 tushare.pro 实名/积分任务后才会返回 True。
    """
    token = resolve_tushare_token(config)
    if not token:
        return False
    try:
        import tushare as ts

        ts.set_token(token)
        pro = ts.pro_api()
        df = pro.stock_basic(ts_code="600519.SH", fields="ts_code,name")
        return df is not None and not df.empty
    except Exception as exc:
        logger.debug("Tushare 接口探测失败: %s", exc)
        return False
