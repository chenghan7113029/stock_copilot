"""实验台账：append-only + 执行行/结果行 + 逐行哈希（design §4.1 / 「台账存储机制」）。

机械保证（R2，QA-F2）：
- 每行是 `RunRecord`（执行行）或 `ExperimentRecord`（结果行），带 `row_type` 判别符与
  `record_sha256`（该行内容哈希）；读取时逐行校验，不匹配即 `RegistryCorruptedError`；
- 只提供 append，**没有** update/delete 接口；
- 拒绝/失败只落执行行（`RunRecord`），结果行仅由 PASSED 执行追加（R1/R2 一致）。

注入点（QA-F6/QA-F10）：`store_path` / `clock` / `data_version` / `results_dir`，
测试全部用 `tmp_path`，不得写真实 `data/backtest/`。
"""

from __future__ import annotations

import hashlib
import json
import os
import warnings
from dataclasses import asdict, is_dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import yaml

from common.exceptions import (
    BacktestError,
    MissingBacktestConfigError,
    RegistryCorruptedError,
    RegistryImmutableError,
)
from service.backtest.models import (
    DEFAULT_PREREG_DIR,
    AdjustMode,
    ExperimentRecord,
    LedgerExportRow,
    PreregistrationSpec,
    RunRecord,
    RunStatus,
    Segment,
    Verdict,
)

ROW_TYPE_RUN = "run"
# R4/T2-fix-4：烧毁标记 = 追加执行行 reason 固定值；导出 burnt 由此派生
BURNT_REASON = "样本外已烧毁"
ROW_TYPE_RESULT = "result"
# design §4.1 台账存储机制：预注册文件在 git 跟踪目录内（可覆盖，CLI 传 cfg.prereg_dir）
DEFAULT_PREREG_PATH = Path(DEFAULT_PREREG_DIR)


# --------------------------------------------------------------------------
# 序列化 / 哈希
# --------------------------------------------------------------------------


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _record_payload(record: RunRecord | ExperimentRecord) -> dict[str, Any]:
    payload = _jsonable(record)
    payload.pop("record_sha256", None)
    return payload


def _record_hash(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _encode_line(record: RunRecord | ExperimentRecord) -> str:
    payload = _record_payload(record)
    payload["record_sha256"] = _record_hash(payload)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _decode_line(line: str, *, lineno: int) -> RunRecord | ExperimentRecord:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise RegistryCorruptedError(f"台账第 {lineno} 行不是合法 JSON，台账损坏") from exc
    if not isinstance(payload, dict):
        raise RegistryCorruptedError(f"台账第 {lineno} 行不是对象，台账损坏")
    stored = payload.pop("record_sha256", None)
    if stored is None or stored != _record_hash(payload):
        raise RegistryCorruptedError(
            f"台账第 {lineno} 行哈希校验失败（被篡改），拒绝审计结论（R2）"
        )
    row_type = payload.get("row_type")
    try:
        if row_type == ROW_TYPE_RUN:
            return RunRecord(
                run_id=str(payload["run_id"]),
                status=RunStatus(str(payload["status"])),
                at=str(payload["at"]),
                experiment_id=payload.get("experiment_id"),
                hypothesis_id=payload.get("hypothesis_id"),
                reason=payload.get("reason"),
                prereg_commit=payload.get("prereg_commit"),
                data_version=payload.get("data_version"),
                row_type=ROW_TYPE_RUN,
            )
        if row_type == ROW_TYPE_RESULT:
            return ExperimentRecord(
                experiment_id=str(payload["experiment_id"]),
                hypothesis_id=str(payload["hypothesis_id"]),
                params=dict(payload.get("params") or {}),
                segment=Segment(str(payload["segment"])),
                K=None if payload.get("K") is None else int(payload["K"]),
                verdict=Verdict(str(payload["verdict"])),
                metrics=dict(payload.get("metrics") or {}),
                prereg_commit=str(payload.get("prereg_commit") or ""),
                data_version=str(payload.get("data_version") or ""),
                adjust_mode=AdjustMode(str(payload.get("adjust_mode"))),
                timestamps=dict(payload.get("timestamps") or {}),
                parent_experiment_id=payload.get("parent_experiment_id"),
                burnt=bool(payload.get("burnt", False)),
                row_type=ROW_TYPE_RESULT,
            )
    except (KeyError, ValueError, TypeError) as exc:
        raise RegistryCorruptedError(f"台账第 {lineno} 行结构非法：{exc}") from exc
    raise RegistryCorruptedError(f"台账第 {lineno} 行 row_type 非法: {row_type!r}")


# --------------------------------------------------------------------------
# 台账
# --------------------------------------------------------------------------


class ExperimentRegistry:
    def __init__(
        self,
        store_path: Path,
        *,
        clock: Callable[[], str],
        data_version: str,
        results_dir: Path | None = None,
    ) -> None:
        self.store_path = Path(store_path)
        self.clock = clock
        self.data_version = data_version
        self.results_dir = (
            Path(results_dir) if results_dir is not None else self.store_path.parent / "results"
        )

    # ---- 读取 ----
    def _read_rows(self) -> list[RunRecord | ExperimentRecord]:
        if not self.store_path.exists():
            return []
        rows: list[RunRecord | ExperimentRecord] = []
        with self.store_path.open("r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                rows.append(_decode_line(stripped, lineno=lineno))
        return rows

    def rows(self) -> Sequence[RunRecord | ExperimentRecord]:
        return self._read_rows()

    # ---- 写入 ----
    def _append_raw(self, record: RunRecord | ExperimentRecord) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with self.store_path.open("a", encoding="utf-8") as handle:
            handle.write(_encode_line(record) + "\n")

    def append_run(self, record: RunRecord) -> None:
        """执行行：每次执行尝试一行（含拒绝/失败留痕，QA-F2）。"""
        if not record.data_version:
            record = replace(record, data_version=self.data_version)
        self._append_raw(record)

    def append(self, record: ExperimentRecord) -> None:
        """结果行：仅 PASSED 执行追加；同 ID 重写、改假设未新开实验一律拒绝（R2）。"""
        rows = self._read_rows()
        existing_ids = {
            row.experiment_id for row in rows if isinstance(row, ExperimentRecord)
        }
        if record.experiment_id in existing_ids:
            raise RegistryImmutableError(
                f"实验 {record.experiment_id} 已写入：台账 append-only，改假设必须新开实验（R2）"
            )
        if record.parent_experiment_id and record.parent_experiment_id not in existing_ids:
            raise BacktestError(f"父实验不存在: {record.parent_experiment_id}（R2）")
        previous = [
            row
            for row in rows
            if isinstance(row, ExperimentRecord) and row.hypothesis_id == record.hypothesis_id
        ]
        if previous:
            latest = previous[-1]
            if dict(latest.params) != dict(record.params) and not record.parent_experiment_id:
                raise RegistryImmutableError(
                    "改假设/参数/评价指标必须新开实验并写入 parent_experiment_id（R2）"
                )
        if record.burnt and self._burnt_markers(record.hypothesis_id):
            raise RegistryImmutableError(
                f"假设 {record.hypothesis_id} 的样本外已烧毁，标记不可撤销（R4）"
            )
        payload = record if record.data_version else replace(record, data_version=self.data_version)
        self._append_raw(payload)

    # ---- 查询 ----
    def get(self, experiment_id: str) -> ExperimentRecord:
        """返回该实验**最新**一条结果行（烧毁标记是 append 的标记行，不改旧行）。"""
        found: ExperimentRecord | None = None
        for row in self._read_rows():
            if isinstance(row, ExperimentRecord) and row.experiment_id == experiment_id:
                found = row
        if found is None:
            raise BacktestError(f"实验 {experiment_id} 不存在（台账无结果行）")
        return found

    def result_rows(self, hypothesis_id: str | None = None) -> tuple[ExperimentRecord, ...]:
        return tuple(
            row
            for row in self._read_rows()
            if isinstance(row, ExperimentRecord)
            and (hypothesis_id is None or row.hypothesis_id == hypothesis_id)
        )

    def _next_seq(self, hypothesis_id: str) -> int:
        prefix = f"{hypothesis_id}-"
        max_seq = 0
        for row in self._read_rows():
            identifiers = [getattr(row, "experiment_id", None), getattr(row, "run_id", None)]
            for identifier in identifiers:
                if not identifier or not str(identifier).startswith(prefix):
                    continue
                suffix = str(identifier)[len(prefix):].split("-")[0]
                if suffix.isdigit():
                    max_seq = max(max_seq, int(suffix))
        return max_seq + 1

    def next_experiment_id(self, hypothesis_id: str) -> str:
        """`f"{hypothesis_id}-{seq:04d}"`，seq 单调递增（QA-F8）。"""
        return f"{hypothesis_id}-{self._next_seq(hypothesis_id):04d}"

    # ---- 预注册（R1） ----
    def validate_preregistration(self, spec: PreregistrationSpec) -> None:
        missing: list[str] = []
        for name in PreregistrationSpec.REQUIRED_FIELDS:
            value = getattr(spec, name)
            if value is None or (isinstance(value, (str, Mapping, Sequence)) and len(value) == 0):
                missing.append(name)
        if missing:
            raise BacktestError("预注册缺字段: " + ", ".join(missing) + "（R1）")
        method = str(spec.correction_method).strip().lower()
        if method not in ("bonferroni", "deflated_sharpe"):
            raise BacktestError(
                f"预注册 correction_method 非法: {spec.correction_method!r}（R5 要求预注册固定）"
            )
        if not str(spec.k_definition).strip():
            raise BacktestError("预注册缺 k_definition：K 计算口径必须预注册固定（R5）")

    def load_preregistration(
        self, hypothesis_id: str, *, prereg_dir: Path | None = None
    ) -> PreregistrationSpec | None:
        directory = Path(prereg_dir) if prereg_dir is not None else DEFAULT_PREREG_PATH
        return load_preregistration_file(directory / f"{hypothesis_id}.yaml")

    # ---- 样本外烧毁（R4） ----
    def _burnt_markers(self, hypothesis_id: str | None = None) -> list[RunRecord]:
        return [
            row
            for row in self._read_rows()
            if isinstance(row, RunRecord)
            and row.reason == BURNT_REASON
            and (hypothesis_id is None or row.hypothesis_id == hypothesis_id)
        ]

    def assert_not_burnt(self, hypothesis_id: str, segment: Segment) -> None:
        if segment is not Segment.OUT_OF_SAMPLE:
            return
        markers = self._burnt_markers(hypothesis_id)
        if not markers:
            return
        reason = f"样本外已烧毁：{hypothesis_id} 的样本外额度已用尽（R4）"
        self.append_run(
            RunRecord(
                run_id=self.next_experiment_id(hypothesis_id),
                status=RunStatus.REJECTED,
                at=self.clock(),
                experiment_id=markers[0].experiment_id,
                hypothesis_id=hypothesis_id,
                reason=reason,
            )
        )
        raise RegistryImmutableError(reason)

    def mark_burnt(self, hypothesis_id: str, experiment_id: str) -> None:
        """写入「已烧毁」标记（R4/T2-fix-4）：追加执行行 `RunRecord(reason="样本外已烧毁")`。

        append-only、不可撤销；导出 `burnt` 由该执行行派生。同一假设重复标记同一实验幂等，
        标记不同实验 → `RegistryImmutableError`。
        """
        markers = self._burnt_markers(hypothesis_id)
        if markers:
            if markers[0].experiment_id == experiment_id:
                return
            raise RegistryImmutableError(
                f"假设 {hypothesis_id} 已有烧毁标记（{markers[0].experiment_id}），不可撤销（R4）"
            )
        target = self.get(experiment_id)
        if target.hypothesis_id != hypothesis_id:
            raise BacktestError(f"实验 {experiment_id} 不属于假设 {hypothesis_id}（R4）")
        self.append_run(
            RunRecord(
                run_id=self.next_experiment_id(hypothesis_id),
                status=RunStatus.RUNNING,
                at=self.clock(),
                experiment_id=experiment_id,
                hypothesis_id=hypothesis_id,
                reason=BURNT_REASON,
            )
        )

    # ---- K 累计（R5） ----
    def cumulative_K(self, study_scope: str | Mapping[str, Any]) -> int:
        """按显式声明的 `k_components[]` 累计；字符串 scope 则累加该假设结果行的 K（R5）。"""
        if isinstance(study_scope, Mapping):
            components = study_scope.get("k_components")
            if components is None:
                raise MissingBacktestConfigError(
                    "cumulative_K 缺 k_components：K 计数边界未确认（Q2），不得擅自合并"
                )
            return sum(int(value) for value in components)
        scope = str(study_scope)
        total = 0
        for row in self.result_rows(scope):
            if row.K is None:
                continue
            total += int(row.K)
        return total

    # ---- 结果落盘（QA-F10） ----
    def write_result(self, experiment_id: str, payload: Mapping[str, Any]) -> Path:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        destination = self.results_dir / f"{experiment_id}.json"
        text = json.dumps(_jsonable(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(text + "\n", encoding="utf-8")
        os.replace(temporary, destination)
        return destination

    # ---- 台账导出（QA-F10 + R1-03 join 规则） ----
    def export_ledger(
        self,
        *,
        experiment_id: str | None = None,
        hypothesis_id: str | None = None,
        prereg_dir: Path | None = None,
    ) -> list[LedgerExportRow]:
        """导出结果行（+ 无结果行的执行行摘要）。

        join 规则（QA-F10 / R1-03）：结果行与执行行按 `hypothesis_id + experiment_id` 关联；
        `REJECTED/FAILED` 无结果行时，导出行的 `segments/params` 取预注册（执行所依据的参数），
        `run_status` 取执行行状态，`verdict` 留 None（拒绝/失败没有结论）。
        `statement` 缺失预注册时用显式占位 `[prereg-missing]` 并 WARN（R1-01）。
        """
        rows = self._read_rows()
        latest_result: dict[str, ExperimentRecord] = {}
        for row in rows:
            if isinstance(row, ExperimentRecord):
                latest_result[row.experiment_id] = row  # 烧毁标记行覆盖旧行（append-only）
        results = list(latest_result.values())
        runs = [row for row in rows if isinstance(row, RunRecord)]
        latest_run: dict[str, RunStatus] = {}
        burnt_experiments: set[str] = set()
        for run in runs:
            if run.experiment_id:
                latest_run[str(run.experiment_id)] = run.status
                if run.reason == BURNT_REASON:
                    burnt_experiments.add(str(run.experiment_id))
        cache: dict[str, PreregistrationSpec | None] = {}

        def prereg(hid: str) -> PreregistrationSpec | None:
            if hid not in cache:
                cache[hid] = self.load_preregistration(hid, prereg_dir=prereg_dir)
            return cache[hid]

        def statement_of(hid: str) -> str:
            spec = prereg(hid) if hid else None
            if spec is None:
                warnings.warn(
                    f"预注册缺失：{hid or '<unknown>'}，导出 statement 用占位符（R1-01）",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return "[prereg-missing]"
            return spec.statement

        def segments_of(hid: str, fallback: Segment) -> tuple[str, ...]:
            spec = prereg(hid) if hid else None
            if spec is not None and spec.segments:
                return tuple(segment.value for segment in spec.segments)
            return (fallback.value,)

        exported: list[LedgerExportRow] = []
        for row in results:
            if experiment_id and row.experiment_id != experiment_id:
                continue
            if hypothesis_id and row.hypothesis_id != hypothesis_id:
                continue
            run_status = latest_run.get(row.experiment_id)
            exported.append(
                LedgerExportRow(
                    experiment_id=row.experiment_id,
                    hypothesis_id=row.hypothesis_id,
                    statement=statement_of(row.hypothesis_id),
                    params=dict(row.params),
                    segments=segments_of(row.hypothesis_id, row.segment),
                    K=row.K,
                    metrics=dict(row.metrics),
                    verdict=row.verdict.value,
                    burnt=bool(row.burnt) or row.experiment_id in burnt_experiments,
                    prereg_commit=row.prereg_commit,
                    run_status=None if run_status is None else run_status.value,
                    data_version=row.data_version,
                    adjust_mode=row.adjust_mode.value,
                )
            )
        result_ids = {row.experiment_id for row in results}
        if experiment_id or hypothesis_id:
            for run in runs:
                identifier = run.experiment_id
                if not identifier or identifier in result_ids:
                    continue
                if experiment_id and identifier != experiment_id:
                    continue
                if hypothesis_id and run.hypothesis_id != hypothesis_id:
                    continue
                spec = prereg(run.hypothesis_id) if run.hypothesis_id else None
                exported.append(
                    LedgerExportRow(
                        experiment_id=identifier,
                        hypothesis_id=run.hypothesis_id or "",
                        statement=(
                            spec.statement if spec is not None else statement_of(run.hypothesis_id or "")
                        ),
                        params=dict(spec.params) if spec is not None else {},
                        segments=(
                            tuple(segment.value for segment in spec.segments)
                            if spec is not None
                            else ()
                        ),
                        K=None,
                        metrics={},
                        verdict=None,
                        burnt=False,
                        prereg_commit=run.prereg_commit,
                        run_status=run.status.value,
                        data_version=run.data_version,
                        adjust_mode=None,
                    )
                )
        return exported


# --------------------------------------------------------------------------
# 预注册文件（git 跟踪，R1）
# --------------------------------------------------------------------------


def load_preregistration_file(path: Path) -> PreregistrationSpec | None:
    if not path.exists():
        return None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        raise BacktestError(f"预注册文件顶层不是映射: {path}")
    return preregistration_from_mapping(data)


def preregistration_from_mapping(data: Mapping[str, Any]) -> PreregistrationSpec:
    missing = [name for name in PreregistrationSpec.REQUIRED_FIELDS if name not in data]
    if missing:
        raise BacktestError("预注册缺字段: " + ", ".join(missing) + "（R1）")
    segments: list[Segment] = []
    for value in data["segments"]:
        try:
            segments.append(value if isinstance(value, Segment) else Segment(str(value)))
        except ValueError as exc:
            raise BacktestError(f"预注册 segments 含未知区段: {value!r}") from exc
    return PreregistrationSpec(
        hypothesis_id=str(data["hypothesis_id"]).strip(),
        statement=str(data["statement"]).strip(),
        params=dict(data["params"] or {}),
        metrics=tuple(str(item) for item in data["metrics"] or ()),
        segments=tuple(segments),
        benchmarks=tuple(str(item) for item in data["benchmarks"] or ()),
        correction_method=str(data["correction_method"]).strip(),
        k_definition=str(data["k_definition"]).strip(),
        created_at=str(data["created_at"]).strip(),
    )


def write_preregistration_file(spec: PreregistrationSpec, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "hypothesis_id": spec.hypothesis_id,
        "statement": spec.statement,
        "params": dict(spec.params),
        "metrics": list(spec.metrics),
        "segments": [segment.value for segment in spec.segments],
        "benchmarks": list(spec.benchmarks),
        "correction_method": spec.correction_method,
        "k_definition": spec.k_definition,
        "created_at": spec.created_at,
    }
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    return path
