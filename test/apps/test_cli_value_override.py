"""CLI value override 单元测试。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.cli import build_parser, run_value_override
from dao.engine import Base, ensure_sqlite_schema
from dao.prototype_override_repo import PrototypeOverrideRepo


def test_run_value_override_persists_and_updates_reason(tmp_path, capsys):
    db_path = tmp_path / "stock_copilot.db"
    config = {"db": {"url": f"sqlite:///{db_path.as_posix()}"}}

    run_value_override("600519", "high_dividend", "初始原因", config=config)
    run_value_override("600519", "high_dividend", "更新后的原因", config=config)

    engine = create_engine(config["db"]["url"])
    Base.metadata.create_all(engine)
    ensure_sqlite_schema(engine)
    session = sessionmaker(bind=engine)()
    record = PrototypeOverrideRepo(session).get_by_code("600519")
    assert record is not None
    assert record.prototype == "high_dividend"
    assert record.reason == "更新后的原因"
    assert "已设置 600519 原型覆盖为 high_dividend" in capsys.readouterr().out
    session.close()


def test_value_override_rejects_invalid_prototype_before_execution():
    parser = build_parser()

    # insurance 等已是合法 V2 原型；此处须用不在 _PROTOTYPE_METHODS 中的名字
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["value", "override", "600519", "bogus_proto", "--reason", "测试"])

    assert exc_info.value.code == 2
