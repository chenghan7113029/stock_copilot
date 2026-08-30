"""resolve_feishu_config 测试。"""

from __future__ import annotations

from common.config_loader import resolve_feishu_config


def test_resolve_feishu_config_defaults():
    cfg = resolve_feishu_config({})
    assert cfg.lark_cli == "lark-cli"
    assert cfg.user_id == ""
    assert cfg.chat_id == ""
    assert cfg.sync_before_push is True
    assert cfg.trading_days_only is True


def test_resolve_feishu_config_from_yaml():
    cfg = resolve_feishu_config(
        {
            "feishu": {
                "lark_cli": "C:/tools/lark-cli.exe",
                "user_id": "ou_me",
                "chat_id": "oc_x",
                "folder_token": "fld",
                "sync_before_push": False,
                "holidays": ["2026-10-01"],
            }
        }
    )
    assert cfg.lark_cli.endswith("lark-cli.exe")
    assert cfg.user_id == "ou_me"
    assert cfg.chat_id == "oc_x"
    assert cfg.folder_token == "fld"
    assert cfg.sync_before_push is False
    assert cfg.holidays == ("2026-10-01",)
