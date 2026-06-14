#!/usr/bin/env python
"""端到端数据采集脚本：fetch → upsert → 打印读回摘要。

用法：
    # 采集 config/value_data_validation_stocks.yaml 中全部样本
    python scripts/fetch_value_data.py

    # 只采集指定代码（可重复多次）
    python scripts/fetch_value_data.py --code 600519 --code 601398

    # 指定配置文件
    python scripts/fetch_value_data.py --config config/app.yaml

说明：
    - 首次运行若缺少 config/app.yaml，会自动从 app.example.yaml 复制。
    - 数据写入 config 中 db.url 指定的数据库（默认 data/stock_copilot.db）。
    - 打印每只股票各数据源的字段覆盖摘要（covered/missing）。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# 确保 src/ 在 PYTHONPATH（从仓库根运行时有效）
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("fetch_value_data")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="价值面数据端到端采集脚本")
    parser.add_argument(
        "--code", "-c",
        action="append",
        dest="codes",
        metavar="CODE",
        help="手动指定股票代码（可多次），优先于 validation_stocks.yaml",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="配置文件路径（默认 config/app.yaml）",
    )
    return parser.parse_args()


def _print_result_summary(code: str, name: str, stock) -> None:
    total_numeric = sum(
        1 for f in stock.__dataclass_fields__
        if f not in ("code", "name", "exchange", "field_sources",
                     "data_timestamp", "fundamental_report_date", "missing_fields")
    )
    covered_count = total_numeric - len(stock.missing_fields or [])
    print(f"\n  [{code}] {name}")
    print(f"    字段覆盖: {covered_count}/{total_numeric}")
    if stock.current_price:
        print(f"    当前价:  {stock.current_price:.2f}")
    if stock.eps:
        print(f"    EPS:     {stock.eps:.4f}")
    if stock.roe:
        print(f"    ROE:     {stock.roe:.2f}%")
    if stock.missing_fields:
        preview = stock.missing_fields[:10]
        more = len(stock.missing_fields) - 10
        print(f"    缺失字段: {preview}" + (f" ...等{more}个" if more > 0 else ""))


def main() -> None:
    args = _parse_args()

    from common.config_loader import load_app_config, load_validation_stocks
    from dao.engine import Base, create_db_engine, make_session_factory
    from dao.stock_snapshot_repo import StockSnapshotRepo
    from data_provider.provider import StockDataProvider

    # 加载配置
    config = load_app_config()

    # 决定要采集的股票列表
    if args.codes:
        stocks = [{"code": c, "name": c, "prototype": "unknown"} for c in args.codes]
        logger.info("手动模式：采集 %d 只股票", len(stocks))
    else:
        stocks = load_validation_stocks()
        logger.info("清单模式：采集 %d 只样本股票", len(stocks))

    # 初始化数据库
    engine = create_db_engine(config)
    Base.metadata.create_all(engine)
    session_factory = make_session_factory(engine)

    print("\n" + "=" * 60)
    print("  价值面数据采集任务开始")
    print("=" * 60)

    success_count = 0
    fail_count = 0

    for item in stocks:
        code: str = item["code"]
        name: str = item.get("name", code)

        try:
            session = session_factory()
            repo = StockSnapshotRepo(session)
            provider = StockDataProvider.from_config(config, repo=repo)

            stock = provider.get_stock_data(code)
            session.commit()
            session.close()

            _print_result_summary(code, name, stock)
            success_count += 1

        except Exception as exc:
            logger.error("采集失败 [%s] %s: %s", code, name, exc)
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"  完成：成功 {success_count} 只，失败 {fail_count} 只")
    print("=" * 60 + "\n")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
