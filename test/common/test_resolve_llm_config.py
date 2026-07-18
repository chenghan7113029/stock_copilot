"""resolve_llm_config 单元测试。"""

from __future__ import annotations

import os
from unittest.mock import patch

from common.config_loader import resolve_llm_config


def test_resolve_llm_config_from_yaml():
    cfg = resolve_llm_config(
        {
            "llm": {
                "base_url": "https://api.deepseek.com/v1",
                "model": "deepseek-chat",
                "api_key": "sk-test",
            }
        }
    )
    assert cfg is not None
    assert cfg.api_key == "sk-test"
    assert cfg.model == "deepseek-chat"


def test_resolve_llm_config_env_fallback():
    with patch.dict(os.environ, {"LLM_API_KEY": "env-key"}, clear=False):
        cfg = resolve_llm_config({"llm": {"model": "m"}})
    assert cfg is not None
    assert cfg.api_key == "env-key"


def test_resolve_llm_config_none_when_missing():
    with patch.dict(os.environ, {}, clear=True):
        # clear=True 会清掉全部 env，可能影响其他东西；只清 LLM_API_KEY
        pass
    env = {k: v for k, v in os.environ.items() if k != "LLM_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        cfg = resolve_llm_config({"llm": {}})
        assert cfg is None
        cfg2 = resolve_llm_config({})
        assert cfg2 is None
