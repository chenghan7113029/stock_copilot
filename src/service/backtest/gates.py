"""R19 三级门禁状态机（design §4.1，T2-fix-4）。

- 每规则**唯一**状态：`backtest_pending → backtest_passed → shadow_running → live_small`
  （`rejected` 为终态）；
- 判据来自 `cfg.gate_criteria`（`config/app.yaml backtest.gates`，Q7）：缺失/None →
  `MissingBacktestConfigError`（**不允许 transition**）；
- 只允许相邻迁移；跳级/前置条件未满足 → `GateSkipError`（子类 `BacktestError`）并留痕；
- 时间戳与持久化经 `ExperimentRegistry`：状态落同目录 `gates.ndjson`，拒绝动作额外追加
  执行行 `RunRecord(status=REJECTED)` 到实验台账（R19「拒绝记录写入台账」）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from common.exceptions import (
    BacktestError,
    GateSkipError,
    MissingBacktestConfigError,
)
from service.backtest.models import (
    BacktestConfig,
    GateRecord,
    GateStage,
    RunRecord,
    RunStatus,
)

STAGE_ORDER: tuple[GateStage, ...] = (
    GateStage.BACKTEST_PENDING,
    GateStage.BACKTEST_PASSED,
    GateStage.SHADOW_RUNNING,
    GateStage.LIVE_SMALL,
)
GATE_STORE_NAME = "gates.ndjson"
# GateRecord.evidence_experiment_ids / stage_timestamps 的级名（R19 Scenario3「每级依据」）
GATE_LEVEL_KEYS: dict[GateStage, str] = {
    GateStage.BACKTEST_PASSED: "backtest",
    GateStage.SHADOW_RUNNING: "shadow",
    GateStage.LIVE_SMALL: "live",
}


@dataclass(frozen=True)
class _Transition:
    rule_id: str
    stage: GateStage
    at: str
    accepted: bool
    experiment_id: str | None
    direction_agree: bool | None
    reason: str | None


class GateStateMachine:
    def __init__(self, registry: Any, *, cfg: BacktestConfig | None = None) -> None:
        """`registry` 提供台账路径与 clock（design 写明时间戳经 registry 注入）。"""
        self.registry = registry
        self.store_path = Path(registry.store_path).parent / GATE_STORE_NAME
        self.cfg = cfg

    # ---- 查询 ----
    def current(self, rule_id: str) -> GateRecord:
        transitions = [item for item in self._read() if item.rule_id == rule_id]
        accepted = [item for item in transitions if item.accepted]
        stage = accepted[-1].stage if accepted else GateStage.BACKTEST_PENDING
        timestamps: dict[str, str] = {}
        evidence: dict[str, str] = {}
        direction_agree: bool | None = None
        for item in accepted:
            key = GATE_LEVEL_KEYS.get(item.stage, item.stage.value)
            timestamps[key] = item.at
            if item.experiment_id:
                evidence[key] = item.experiment_id
            direction_agree = item.direction_agree
        return GateRecord(
            rule_id=rule_id,
            stage=stage,
            stage_timestamps=timestamps,
            evidence_experiment_ids=evidence,
            direction_agree=direction_agree,
        )

    # ---- 迁移（T2-fix-6 优先序：① 边 → ② 判据可用性 → ③ 达成性）----
    def transition(
        self, rule_id: str, to: GateStage, evidence: Mapping[str, Any] | None = None
    ) -> GateRecord:
        target = to if isinstance(to, GateStage) else GateStage(str(to))
        current = self.current(rule_id)
        payload = dict(evidence or {})
        experiment_id = payload.get("experiment_id")
        if experiment_id is not None:
            experiment_id = str(experiment_id)

        # ① 边合法性：跳级/回退/同态 → GateSkipError + 业务拒绝留痕
        try:
            self._validate_edge(current, target)
        except GateSkipError as exc:
            self._record_rejection(rule_id, current, target, experiment_id, payload, exc)
            raise

        # ② 判据可用性：gate_criteria 缺 → 配置错误（不落业务拒绝行）
        self._ensure_criteria(target)

        # ③ 达成性：evidence 不满足 → GateSkipError + 业务拒绝留痕
        try:
            self._validate_attainment(current, target, payload)
        except GateSkipError as exc:
            self._record_rejection(rule_id, current, target, experiment_id, payload, exc)
            raise

        self._append(
            _Transition(
                rule_id=rule_id,
                stage=target,
                at=self.registry.clock(),
                accepted=True,
                experiment_id=experiment_id,
                direction_agree=payload.get("direction_agree"),
                reason=payload.get("reason"),
            )
        )
        return self.current(rule_id)

    def _record_rejection(
        self,
        rule_id: str,
        current: GateRecord,
        target: GateStage,
        experiment_id: str | None,
        payload: Mapping[str, Any],
        exc: GateSkipError,
    ) -> None:
        at = self.registry.clock()
        self._append(
            _Transition(
                rule_id=rule_id,
                stage=target,
                at=at,
                accepted=False,
                experiment_id=experiment_id,
                direction_agree=payload.get("direction_agree"),
                reason=str(exc),
            )
        )
        self.registry.append_run(
            RunRecord(
                run_id=self.registry.next_experiment_id(f"gate-{rule_id}"),
                status=RunStatus.REJECTED,
                at=at,
                hypothesis_id=f"gate:{rule_id}",
                reason=f"门禁拒绝（{current.stage.value} → {target.value}）：{exc}",
            )
        )

    def _validate_edge(self, current: GateRecord, target: GateStage) -> None:
        if target is GateStage.REJECTED:
            if current.stage is GateStage.REJECTED:
                raise GateSkipError(f"规则 {current.rule_id} 门禁已拒绝，不得重复拒绝（R19）")
            return
        if target not in STAGE_ORDER:
            raise GateSkipError(f"未知门禁阶段: {target!r}（R19）")
        if target is GateStage.BACKTEST_PENDING:
            raise GateSkipError("门禁不可回退到「回测未通过」（R19）")
        if current.stage is GateStage.REJECTED:
            raise GateSkipError(f"规则 {current.rule_id} 门禁已拒绝，不得继续迁移（R19）")
        current_index = STAGE_ORDER.index(current.stage)
        target_index = STAGE_ORDER.index(target)
        if target_index != current_index + 1:
            raise GateSkipError(
                f"跳级请求被拒：{current.stage.value} → {target.value}（R19 只允许逐级）"
            )

    def _ensure_criteria(self, target: GateStage) -> None:
        if target is GateStage.BACKTEST_PASSED:
            self._criterion("backtest_pass")
        elif target is GateStage.SHADOW_RUNNING:
            self._criterion("shadow")
        elif target is GateStage.LIVE_SMALL:
            shadow = self._criterion("shadow")
            self._criterion("direction_agree")
            if shadow.get("min_months") is None:
                raise MissingBacktestConfigError(
                    "回测配置缺值: gate_criteria.shadow.min_months（Q7/KQ-4）"
                )

    def _validate_attainment(
        self, current: GateRecord, target: GateStage, evidence: Mapping[str, Any]
    ) -> None:
        if target is GateStage.REJECTED:
            return
        if target is GateStage.BACKTEST_PASSED:
            if not evidence.get("experiment_id"):
                raise GateSkipError("进入「回测通过」需给出依据实验 ID（R19 Scenario 3）")
        elif target is GateStage.SHADOW_RUNNING:
            if not evidence.get("experiment_id"):
                raise GateSkipError("进入影子运行需给出依据实验 ID（R19）")
        elif target is GateStage.LIVE_SMALL:
            if evidence.get("direction_agree") is not True:
                raise GateSkipError("方向一致判据未满足：不得进入实盘小仓位（R19）")
            started = current.stage_timestamps.get(GATE_LEVEL_KEYS[GateStage.SHADOW_RUNNING])
            if not started:
                raise GateSkipError("影子运行起始时间缺失，无法核对最短期限（KQ-4）")
            shadow = self._criterion("shadow")
            min_months = int(shadow["min_months"])
            elapsed = _months_between(started, self.registry.clock())
            if elapsed < min_months:
                raise GateSkipError(
                    f"影子期未满：已 {elapsed} 个月 < 最短 {min_months} 个月（R19 Scenario 2）"
                )

    def _criteria(self) -> Any:
        if self.cfg is None or self.cfg.gate_criteria is None:
            raise MissingBacktestConfigError(
                "回测配置缺值: gate_criteria（backtest.gates，Q7）；判据未配置不允许 transition"
            )
        return self.cfg.gate_criteria

    def _criterion(self, name: str) -> Mapping[str, Any]:
        criteria = self._criteria()
        value = getattr(criteria, name, None)
        if not value:
            raise MissingBacktestConfigError(
                f"回测配置缺值: gate_criteria.{name}（Q7）；判据未配置不允许 transition"
            )
        return value

    # ---- 持久化 ----
    def _append(self, transition: _Transition) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "rule_id": transition.rule_id,
            "stage": transition.stage.value,
            "at": transition.at,
            "accepted": transition.accepted,
            "experiment_id": transition.experiment_id,
            "direction_agree": transition.direction_agree,
            "reason": transition.reason,
        }
        with self.store_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def _read(self) -> list[_Transition]:
        if not self.store_path.exists():
            return []
        items: list[_Transition] = []
        with self.store_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                items.append(
                    _Transition(
                        rule_id=str(payload["rule_id"]),
                        stage=GateStage(str(payload["stage"])),
                        at=str(payload["at"]),
                        accepted=bool(payload["accepted"]),
                        experiment_id=payload.get("experiment_id"),
                        direction_agree=payload.get("direction_agree"),
                        reason=payload.get("reason"),
                    )
                )
        return items


def _months_between(start: str, end: str) -> int:
    try:
        start_date = datetime.fromisoformat(str(start))
        end_date = datetime.fromisoformat(str(end))
    except ValueError as exc:
        raise BacktestError(f"时间戳非法: {start!r} / {end!r}") from exc
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return max(0, months)
