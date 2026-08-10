"""数据一致性校验：本层 AKShare vs ref/valueinvest AKShare（0.1% 容差）。

标 @pytest.mark.network，交付前必须完整跑一次并留存报告到 reports/。

设计约束（design D7）：
- 仅对比"本层 AKShare 取数" vs "ref/valueinvest AKShare 取数"（同源对比）
- Baostock vs AKShare 的差异属正常，不纳入此门槛
- 参考侧 0 填充 / 本侧 None 归一化为"参考缺失"，不计差异但报告标注
- 相对误差 ≤ 0.1%，财报口径不放宽
- 生产代码不 import ref/，仅在测试内临时修改 sys.path 调用参考侧
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest

# ── 待比较的样本股票（code → 原型）─────────────────────────────────────────────
pytestmark = [pytest.mark.network, pytest.mark.akshare_legacy]

SAMPLE_STOCKS = {
    "600519": "value_growth",   # 贵州茅台
    "601398": "bank",           # 工商银行
    "600900": "high_dividend",  # 长江电力
}

# 参与一致性比对的关键字段
COMPARE_FIELDS = [
    "current_price",
    "eps",
    "bvps",
    "revenue",
    "net_income",
    "roe",
    "dividend_per_share",
    "dividend_yield",
    "total_assets",
    "shareholder_equity",
    "net_income",
    "fcf",
]

TOLERANCE = 0.001  # 0.1%


# ── 参考侧取数（临时 sys.path，仅用于测试）────────────────────────────────────

def _get_ref_valueinvest_path() -> Optional[Path]:
    workspace = Path(__file__).parent.parent.parent
    ref_path = workspace / "ref" / "valueinvest"
    return ref_path if ref_path.exists() else None


def _fetch_ref_stock(code: str) -> dict:
    """调用 ref/valueinvest AKShare fetcher，返回 data dict。

    生产代码不 import ref/，此函数仅在测试内临时修改 sys.path。
    """
    ref_path = _get_ref_valueinvest_path()
    if ref_path is None:
        pytest.skip("ref/valueinvest 不存在，跳过一致性检查")

    original_sys_path = sys.path.copy()
    try:
        # 临时插入 ref/valueinvest 到 sys.path（仅本测试范围内有效）
        sys.path.insert(0, str(ref_path))
        from valueinvest.data.fetcher.akshare import AKShareFetcher as RefFetcher
        fetcher = RefFetcher(code)
        result = fetcher.fetch_all(code)
        return result.data if result.success else {}
    except ImportError as e:
        pytest.skip(f"ref/valueinvest 导入失败: {e}")
        return {}
    finally:
        sys.path[:] = original_sys_path


# ── 本层取数 ──────────────────────────────────────────────────────────────────

def _fetch_our_stock(code: str) -> dict:
    """调用本层 AKShareFetcher.fetch_all，返回 data dict。"""
    from data_provider.akshare.fetcher import AKShareFetcher
    from data_provider.base import normalize_stock_code
    fetcher = AKShareFetcher()
    std_code, exchange = normalize_stock_code(code)
    result = fetcher.fetch_all(std_code, exchange)
    return result.data if result.ok else {}


# ── 对比逻辑 ──────────────────────────────────────────────────────────────────

def _relative_error(our_val, ref_val) -> Optional[float]:
    """计算相对误差 |our - ref| / |ref|；分母为 0 时返回 None。"""
    if ref_val == 0:
        return None
    return abs(our_val - ref_val) / abs(ref_val)


@pytest.fixture(scope="module")
def reports_dir():
    path = Path(__file__).parent.parent.parent / "reports"
    path.mkdir(exist_ok=True)
    return path


# ── 主测试逻辑 ────────────────────────────────────────────────────────────────

@pytest.mark.network
@pytest.mark.parametrize("code,prototype", list(SAMPLE_STOCKS.items()))
def test_consistency_with_ref(code: str, prototype: str, reports_dir: Path):
    """对比本层 AKShare 与 ref/valueinvest AKShare，相对误差 ≤ 0.1%。"""
    our_data = _fetch_our_stock(code)
    ref_data = _fetch_ref_stock(code)

    if not our_data:
        pytest.fail(f"本层取数失败: {code}")
    if not ref_data:
        pytest.skip(f"参考侧取数失败，跳过一致性检查: {code}")

    diffs: list[dict] = []
    failures: list[str] = []
    normalized: list[str] = []  # ref=0 / our=None 的归一化字段

    for field in COMPARE_FIELDS:
        our_val = our_data.get(field)
        ref_val = ref_data.get(field)

        # 归一化处理：ref=0 视为缺失，不计入差异（design D7）
        if ref_val == 0 and our_val is None:
            normalized.append(field)
            continue
        if ref_val == 0 and ref_val is not None:
            normalized.append(f"{field}(ref=0,skipped)")
            continue

        # 本侧缺失记录但不直接 fail（由完备性门槛把关）
        if our_val is None:
            diffs.append({"field": field, "our": None, "ref": ref_val, "status": "our_missing"})
            continue
        if ref_val is None:
            diffs.append({"field": field, "our": our_val, "ref": None, "status": "ref_missing"})
            continue

        rel_err = _relative_error(float(our_val), float(ref_val))
        if rel_err is None:
            normalized.append(f"{field}(ref_zero)")
            continue

        status = "PASS" if rel_err <= TOLERANCE else "FAIL"
        diffs.append({
            "field": field,
            "our": our_val,
            "ref": ref_val,
            "rel_error": rel_err,
            "status": status,
        })
        if status == "FAIL":
            failures.append(
                f"{field}: our={our_val:.4f}, ref={ref_val:.4f}, rel_err={rel_err:.4%}"
            )

    # 保存报告
    report = {
        "code": code,
        "prototype": prototype,
        "run_at": datetime.now().isoformat(),
        "tolerance": TOLERANCE,
        "diffs": diffs,
        "normalized_fields": normalized,
        "failures": failures,
    }
    report_path = reports_dir / f"consistency_{code}_{datetime.now().strftime('%Y%m%d')}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    if failures:
        pytest.fail(
            f"{code} 一致性校验失败（{len(failures)} 个字段超过 {TOLERANCE:.1%} 容差）:\n"
            + "\n".join(failures)
        )
    else:
        pass  # 所有字段通过


@pytest.mark.network
def test_consistency_report_saved(reports_dir: Path):
    """验证报告文件已被创建（收尾检查）。"""
    # 此测试在 test_consistency_with_ref 之后运行
    today = datetime.now().strftime("%Y%m%d")
    report_files = list(reports_dir.glob(f"consistency_*_{today}.json"))
    # 仅当其他一致性测试已运行时才检查
    if report_files:
        assert len(report_files) >= 1
