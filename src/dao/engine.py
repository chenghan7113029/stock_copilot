"""SQLAlchemy engine / session 工厂。

- db.url 来自 config，默认 SQLite
- SQLite 启用 WAL + busy_timeout（参考 daily_stock_analysis storage.py）
- 全程只用 SQLAlchemy 通用能力，避免 SQLite 专有 SQL（预留 MySQL）
"""

from __future__ import annotations

import logging
from typing import Any, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)

_DEFAULT_URL = "sqlite:///data/stock_copilot.db"


def create_db_engine(config: dict[str, Any]) -> Engine:
    """根据 config['db'] 创建并返回 SQLAlchemy Engine。"""
    db_cfg: dict = config.get("db", {})
    url: str = db_cfg.get("url", _DEFAULT_URL)
    echo: bool = db_cfg.get("echo", False)

    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        connect_args["timeout"] = 30  # busy_timeout 30s

    engine = create_engine(url, echo=echo, connect_args=connect_args)

    # SQLite 启用 WAL 模式（写入并发更好）
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def set_sqlite_wal(dbapi_conn, _conn_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    logger.info("数据库 engine 创建完成: %s", url.split("?")[0])
    return engine


def ensure_sqlite_schema(engine: Engine) -> None:
    """SQLite 轻量 schema 补丁（create_all 不修改已有表结构）。"""
    if not str(engine.url).startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(stock_snapshots)")).fetchall()
        col_names = {row[1] for row in rows}
        if "historical_pe_json" not in col_names:
            conn.execute(text("ALTER TABLE stock_snapshots ADD COLUMN historical_pe_json TEXT"))
            logger.info("已添加列 stock_snapshots.historical_pe_json")
        if "historical_pb_json" not in col_names:
            conn.execute(text("ALTER TABLE stock_snapshots ADD COLUMN historical_pb_json TEXT"))
            logger.info("已添加列 stock_snapshots.historical_pb_json")
        for col in (
            "prior_roa",
            "prior_debt_ratio",
            "prior_current_ratio",
            "prior_shares_outstanding",
            "prior_gross_margin",
            "prior_asset_turnover",
        ):
            if col not in col_names:
                conn.execute(text(f"ALTER TABLE stock_snapshots ADD COLUMN {col} REAL"))
                logger.info("已添加列 stock_snapshots.%s", col)
        if "industry" not in col_names:
            conn.execute(text("ALTER TABLE stock_snapshots ADD COLUMN industry VARCHAR(50)"))
            logger.info("已添加列 stock_snapshots.industry")
        for col in ("net_interest_margin", "npl_ratio", "provision_coverage"):
            if col not in col_names:
                conn.execute(text(f"ALTER TABLE stock_snapshots ADD COLUMN {col} REAL"))
                logger.info("已添加列 stock_snapshots.%s", col)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def make_session_factory(engine: Engine):
    """返回一个 sessionmaker 工厂（不传入 class=Session，兼容 SA 2.x）。"""
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session(session_factory) -> Generator[Session, None, None]:
    """Context manager / generator：获取一个 session，自动 commit/rollback。"""
    session: Session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
