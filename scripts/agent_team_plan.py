#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""波次计划（plan.yaml）的机检与契约渲染。

用途
    把「起队前对账」与「收口核对」从人肉检查变成可执行断言：
        init     按规范编制生成 docs/agent-team/plans/<change>.yaml 骨架（一生成就该是红的）
        check    对 plan.yaml 跑全部起跑断言（M / C / D / S / V / K / P / A / G 九组）
        render   把某个任务渲染成 create_task 参数字典（消除手抄）
        checks   列出全部断言（编号 + 管什么 + 历史依据）与条数
        closeout 收口闸门 R0–R5（改动范围 / 任务落地 / 产物存在 / 评审留痕 / 主规格未被手改）

真值源分工（本脚本不复制第二份）
    成员与模型   docs/agent-team/models.yaml（只读）
    角色 SOP     docs/agent-team/roles/<name>.md（只读：存在性与体量预算）
    规范编制     本文件的 CANON 表（与 docs/agent-team/PLAYBOOK.md 的编制表对齐，改动须同步）
    case 锚点    docs/cases/<case>/annotations.md（只读）
    规格真源     openspec/changes/<change>/（收口时读 verification.md / review.md）

本仓库常量（写死在下面，换项目要一起改）
    python       python（本机不存在 python3 命令）
    代码根       src/
    单测         test/（engineer 拥有）
    QA 用例      test/qa/（qa 拥有；与 engineer 的 test/ 双轨分离）
    知识库根     config/knowledge/
    命令         python -m pytest -q
                 python -m pytest -q test/qa
                 python -m ruff check .
                 python -m compileall -q src test
                 openspec.cmd validate <change> --strict
    git          主干 main；提交身份 chenghan7113029 <chenghan7113029@users.noreply.github.com>

退出码
    0  全部通过（warning 只打印，不判失败）
    1  存在 error（check = 不许起跑；closeout = 不许收口）
    2  用法 / 环境错误（plan 不存在、YAML 解析失败、PyYAML 缺失等）

用法（Windows；命令是 python 不是 python3；不联网、不用 bash）
    python scripts/agent_team_plan.py init --change add-foo --case case-xxx
    python scripts/agent_team_plan.py check --plan docs/agent-team/plans/add-foo.yaml
    python scripts/agent_team_plan.py render T3 --json
    python scripts/agent_team_plan.py checks
    python scripts/agent_team_plan.py closeout --plan docs/agent-team/plans/add-foo.yaml

    # 临时目录自测：--root / --cases-root / --mrd-root / --roles-root / --models-file 均可覆盖，
    # 相对路径按 --root（默认脚本所在仓库）解析，不污染仓库也能跑全套断言。
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

try:
    import yaml
except ImportError:  # pragma: no cover - 环境缺 PyYAML 时给一句人话
    sys.exit("需要 PyYAML：python -m pip install pyyaml")


def _utf8_streams() -> None:
    """Windows 控制台默认 cp936，直接打印中文会 UnicodeEncodeError；统一成 UTF-8。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, OSError, ValueError):  # pragma: no cover - 老解释器/重定向
            pass


_utf8_streams()

REPO = Path(__file__).resolve().parent.parent

PLANS_REL = "docs/agent-team/plans"
CASES_REL = "docs/cases"
MRD_REL = "docs/mrd"
ROLES_REL = "docs/agent-team/roles"
MODELS_REL = "docs/agent-team/models.yaml"

# ── 本仓库常量（写死；换项目改这里，不要在断言里散落字面量）──────────────
PYTHON = "python"
CODE_ROOT = "src/"
TEST_ENGINEER = "test/"
TEST_QA = "test/qa/"
KNOWLEDGE_ROOT = "config/knowledge/"
MAIN_BRANCH = "main"
COMMIT_EMAIL = "chenghan7113029@users.noreply.github.com"

REPO_COMMANDS = (
    f"{PYTHON} -m pytest -q",
    f"{PYTHON} -m pytest -q test/qa",
    f"{PYTHON} -m ruff check .",
    f"{PYTHON} -m compileall -q src test",
    "openspec.cmd validate <change> --strict",
)

# 规范编制：ID → kind / 负责成员 / 依赖。与 PLAYBOOK 的编制表一一对应，改 DAG 时两处都要动。
CANON: dict[str, dict] = {
    "T1": {"kind": "requirements", "assignee": "product-manager", "deps": []},
    "K1": {"kind": "work", "assignee": "knowledge-architect", "deps": ["T1"]},
    "T2": {"kind": "work", "assignee": "architect", "deps": ["T1", "K1"]},
    "K2": {"kind": "work", "assignee": "knowledge-engineer", "deps": ["K1"]},
    "T3": {"kind": "implementation", "assignee": "engineer", "deps": ["T2"]},
    "T4": {"kind": "work", "assignee": "qa", "deps": ["T2"]},
    "K3": {"kind": "work", "assignee": "qa", "deps": ["K2", "T1"]},
    "T5": {"kind": "verification", "assignee": "qa", "deps": ["T3", "T4"]},
    "T6": {"kind": "review", "assignee": "reviewer", "deps": ["T3", "T5", "K3"]},
    "T7": {"kind": "work", "assignee": "product-manager", "deps": ["T5", "T6", "K3"]},
    "T8": {"kind": "integration", "assignee": "integrator", "deps": ["T5", "T6", "T7", "K3"]},
}
TASK_IDS = tuple(CANON)

QUALITY_KINDS = frozenset(
    {"requirements", "implementation", "verification", "review", "repair", "integration"}
)
KNOWLEDGE_IDS = frozenset({"K1", "K2", "K3"})
WORK_WORDS = ("完成定义", "失败定义")
BLIND_CHECK_WORD = "盲验"

PLACEHOLDER = "TODO:"
WIDE_GREEN = ("--deselect", "|| true", "--ignore=", "-k not")
HARD_NUMBER = re.compile(r"\b\d+\s*(?:passed|failed|tests?)\b", re.IGNORECASE)
COVERAGE_NUMBER = re.compile(r"覆盖率\s*\d+\s*%")
BARE_OPENSPEC = re.compile(r"(?<![\w.\-])openspec\b(?!\.cmd|[\\/])")

DEFAULT_MEMBERS = (
    "product-manager",
    "knowledge-architect",
    "architect",
    "knowledge-engineer",
    "engineer",
    "qa",
    "reviewer",
    "integrator",
)

# 规范序（由 CANON 的依赖推导出的层次）：D4「依赖只从下游加」的方向依据。
CANON_LEVEL: dict[str, int] = {}


def _canon_level(tid: str, memo: dict[str, int]) -> int:
    if tid in memo:
        return memo[tid]
    deps = CANON[tid]["deps"]
    memo[tid] = 0 if not deps else 1 + max(_canon_level(d, memo) for d in deps)
    return memo[tid]


for _tid in CANON:
    _canon_level(_tid, CANON_LEVEL)
del _tid


# ── 断言清单（编号 / 管什么 / 历史依据）────────────────────────────────
CHECK_INVENTORY: list[tuple[str, str, str]] = [
    ("M1", "成员集合 == models.yaml 的 roles", "模型裸名解析失败、编制漂移（波 10 两次）"),
    ("M2", "任务数 11 且任务 ID 集合 == 规范（偏离须 allow_custom_dag + wave.note）", "起队前必须现读对账"),
    ("M3", "每个成员的 name 在 models.yaml 里能解析、effort 非空", "模型字段缺 effort 会让成员静默降级"),
    ("C0", "每个任务的 kind 与 assignee == 规范编制表", "悄悄改编制等于绕过闸门"),
    ("C1", "质量 kind 必须有非空 acceptance", "没有判据的闸门无法判定通过"),
    ("C2", "质量 kind 必须有非空 verify", "无命令的验收 = 没有验收（FLOW-harden-verdict）"),
    ("C3", "T6 的 reviewed_task 指向存在且 kind ∈ {implementation, repair} 的任务", "评审对象错位 → repair 修错对象"),
    ("C4", "work kind 的 description 同时含「完成定义」与「失败定义」", "work 无 acceptance 承载、启动后不可编辑"),
    ("C5", "全文无 TODO: 占位符残留", "骨架/半成品被当成完成"),
    ("D1", "DAG 无环", "edit_plan 造环后全线卡死"),
    ("D2", "dependencies 只指向存在的任务", "依赖不存在的 id = 永不 ready"),
    ("D3", "关键边逐条在位（规范 11 行的依赖）", "漏一条边 = 闸门形同虚设"),
    ("D4", "依赖只从下游加（不得依赖规范上的下游任务）", "给上游加依赖会误报 inScope 重叠甚至造环"),
    ("S1", "inScope 逐条是文件路径（有扩展名、不得是裸目录；允许 <path> (待新建)）", "目录化笼住他人文件，复发 2 次"),
    ("S2", "质量 kind 的 inScope 非空", "改了什么都无法界定"),
    ("S3", "engineer 不碰 test/qa/；qa 不碰 src/ 与 test/（test/qa/ 除外）", "双轨分离是 QA 盲测的前提"),
    ("V1", "verify 未被放宽（--deselect / -k not / || true / --ignore=）", "假绿比删测试更隐蔽"),
    ("V2", "acceptance 未写死测试数字（须写「起跑时实测值」）", "写死必然过期，repair 只能改测试凑数"),
    ("V3", "verify 里的命令本机可跑（无 python3、无裸 openspec）", "不存在的命令 = 验收永不执行"),
    ("K1", "知识线任务（K1/K2/K3）kind 必须是 work", "质量闸门面向代码，套在知识上会路由出错误修复"),
    ("K2", "K3 的 description 必须含「盲验」", "不写死就退化成本人自验（利益冲突）"),
    ("P1", "roles/_shared.md ≤ 3200 字节；每个 roles/<name>.md ≤ 8000 字节", "每步重发，超预算会被挑着执行"),
    ("P2", "每个成员都有 docs/agent-team/roles/<name>.md", "成员没有 SOP = 全凭即兴"),
    (
        "A1",
        "docs/cases/<case>/annotations.md 存在且含 ground-truth 标注（不全是 TBD/待补）",
        "没有现实锚点的波次会产出自嗨产物",
    ),
    ("A2", "docs/mrd/<...>.md（wave.mrd）存在", "需求基线缺失则无从对齐"),
    ("G1", "当前分支 == wave.branch", "在 main（或别人的分支）上起波"),
    ("G2", "工作树干净（脏 → warning，不失败）", "并行 session 的改动被卷进本波"),
    ("G3", "wave.baseline_commit 是 HEAD 祖先", "起队凭据缺失 = 无法回答「按哪版配置起的队」"),
    ("G4", "git config user.email == chenghan7113029@users.noreply.github.com", "提交身份靠邮箱判定，姓名不可信"),
]

REQUIRED_REVIEW_ROWS = (
    [f"A{i}" for i in range(1, 7)] + [f"B{i}" for i in range(1, 10)] + ["D1", "D2", "D3"]
)

CLOSEOUT_INVENTORY: list[tuple[str, str, str]] = [
    ("R0", "规格目录存在（openspec/changes/<change>/ 或 archive/*-<change>/）", "归档后目录改名，两边都要认"),
    ("R1", "每个改动文件都落在某个任务的 inScope 内（四个豁免目录之外）", "没人认领的改动是波次里最常见的静默越权"),
    ("R2", "implementation / repair 任务至少落地一个自家 inScope 文件", "有任务、有 inScope、没落地不是半成品，是没做"),
    ("R3", "verification.md 存在（<80 字节给 warning）", "T5 的产物缺失等于验收没发生"),
    (
        "R4",
        f"review.md 存在且含 A1–A6 / B1–B9 / D1–D3 共 {len(REQUIRED_REVIEW_ROWS)} 个标记",
        "清单存在但没人打开 = 没有清单",
    ),
    ("R5", "stage: pre 时 openspec/specs/ 无改动", "合并主规格是 openspec archive 的动作，不属于任何成员"),
]

CLOSEOUT_EXEMPT = (
    "openspec/changes/",
    "docs/cases/",
    "docs/improvements/",
    "docs/agent-team/plans/",
)

REVIEW_ROW = re.compile(r"^\s*\|?\s*([ABCD]\d{1,2})\b")
GT_MARKER = re.compile(r"ground[\s_-]?truth", re.IGNORECASE)
GT_PLACEHOLDERS = frozenset(
    {"", "-", "—", "–", "?", "tbd", "tba", "todo", "待补", "待填", "n/a", "na", "none", "无"}
)
_NEW_FILE_MARK = re.compile(r"\s*[（(]\s*(?:待新建|新建)\s*[)）]\s*$")
_MD_NOISE = re.compile(r"[|`*_>#:：\-–—()（）\[\]{}，,。.;；/\\\s]+")
_TABLE_SEP = re.compile(r"^:?-{2,}:?$")

_LEVEL_LABEL = {"error": "FAIL", "warn": "WARN", "pass": "PASS"}


# ── 小工具（Windows 路径 / 编码 / 子进程）──────────────────────────────
def _posix(value: object) -> str:
    """统一成正斜杠比较；Windows 下反斜杠与正斜杠混用会让断言假红/假绿。"""
    return str(value).strip().replace("\\", "/")


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    return [str(value)]


def _die(msg: str):
    print(msg, file=sys.stderr)
    sys.exit(2)


def _run(cmd: list[str], root: Path) -> tuple[int, str]:
    """跑一条子进程命令，永不抛：git 不可用时返回 (127, "")，由检查项自己报。"""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
        )
    except (OSError, ValueError):  # pragma: no cover - 环境缺 git
        return 127, ""
    return proc.returncode, ((proc.stdout or "") + (proc.stderr or "")).strip()


def _read_text(path: Path) -> str:
    """读 UTF-8（容忍 BOM）；坏字节替换而不是抛异常，避免一个坏文件毁掉整轮检查。"""
    try:
        return path.read_bytes().decode("utf-8-sig", errors="replace")
    except OSError:
        return ""


def _load_yaml(path: Path):
    """返回 dict/list；空文件返回 {}；解析失败返回 None（调用方决定如何报）。"""
    text = _read_text(path)
    if not text.strip():
        return {}
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # pragma: no cover - 输入错误
        print(f"YAML 解析失败：{path}：{exc}", file=sys.stderr)
        return None
    return {} if data is None else data


def _load_models(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    data = _load_yaml(path)
    if not isinstance(data, dict):
        return []
    return [r for r in (data.get("roles") or []) if isinstance(r, dict)]


def _size_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:  # pragma: no cover
        return 0


def _rel(path: Path, root: Path) -> str:
    try:
        return _posix(path.resolve().relative_to(root.resolve()))
    except (ValueError, OSError):
        return _posix(path)


def _arg_dir(value: str | None, root: Path, default_rel: str) -> Path:
    """显式传入的目录：绝对路径直接用；相对路径按 --root 解析（默认仓库根）。"""
    if value:
        p = Path(value)
        return p.resolve() if p.is_absolute() else (root / p).resolve()
    return (root / default_rel).resolve()


def _scope_path(entry: object) -> str:
    """inScope 条目 → 纯路径：去掉「(待新建)」标记与反斜杠。"""
    raw = _NEW_FILE_MARK.sub("", str(entry).strip()).strip()
    return _posix(raw.split()[0]) if raw else ""


def is_file_path(entry: object) -> bool:
    """inScope 的每条必须是文件路径：有扩展名，且不是以 / 结尾的目录形态。"""
    raw = str(entry).strip()
    if not raw:
        return False
    path = _scope_path(raw)
    if not path or path.endswith("/") or path.endswith("."):
        return False
    return bool(PurePosixPath(path).suffix)


# ── git 事实──────────────────────────────────────────────────────────
def git_facts(plan: dict, root: Path) -> dict:
    """采集 git 侧事实，失败不抛异常——检查项自己报，别让脚本先死。"""
    facts: dict = {}
    code, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    facts["branch"] = out if code == 0 else ""
    code, out = _run(["git", "status", "--porcelain", "--untracked-files=no"], root)
    facts["dirty"] = bool(out.strip()) if code == 0 else False
    base = str((plan.get("wave") or {}).get("baseline_commit") or "").strip()
    if not base:
        facts["baseline_ok"] = None
    else:
        code, _ = _run(["git", "merge-base", "--is-ancestor", base, "HEAD"], root)
        facts["baseline_ok"] = code == 0
    code, out = _run(["git", "config", "user.email"], root)
    facts["email"] = out if code == 0 else ""
    return facts


def _git_head(root: Path) -> str | None:
    code, out = _run(["git", "rev-parse", "--short", "HEAD"], root)
    return out if code == 0 and out else None


def git_changed(base: str, root: Path, head: str = "HEAD") -> list[str] | None:
    """三点 diff（与 base 的 merge-base 比），避免 base 落后时把别人的提交算进来。"""
    code, out = _run(["git", "diff", "--name-only", f"{base}...{head}"], root)
    if code != 0:
        code, out = _run(["git", "diff", "--name-only", base, head], root)
    if code != 0:
        return None
    return [_posix(line) for line in out.splitlines() if line.strip()]


# ── 起跑断言─────────────────────────────────────────────────────────
def _iter_strings(node: object, prefix: str = ""):
    """递归遍历 plan 里的所有字符串（C5 全文占位符检测用），产出 (位置, 文本)。"""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_strings(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            yield from _iter_strings(value, f"{prefix}[{index}]")
    elif isinstance(node, str):
        yield prefix, node


def check_plan(
    plan: dict,
    root: Path = REPO,
    facts: dict | None = None,
    *,
    cases_root: Path | None = None,
    mrd_root: Path | None = None,
    roles_root: Path | None = None,
    models_file: Path | None = None,
) -> list[dict]:
    """纯函数：plan 字典 + 仓库根 + git 事实 → findings。自测可直接喂假事实。"""
    out: list[dict] = []

    def add(code: str, level: str, msg: str) -> None:
        out.append({"code": code, "level": level, "msg": msg})

    wave = plan.get("wave") or {}
    if not isinstance(wave, dict):
        wave = {}
    tasks = [t for t in (plan.get("tasks") or []) if isinstance(t, dict)]
    by_id = {str(t.get("id")): t for t in tasks}
    members = [
        str(m.get("name")) if isinstance(m, dict) else str(m)
        for m in (plan.get("members") or [])
    ]
    members = [m.strip() for m in members if m.strip()]

    cases_dir = cases_root or (root / CASES_REL)
    mrd_dir = mrd_root or (root / MRD_REL)
    roles_dir = roles_root or (root / ROLES_REL)
    models_path = models_file or (root / MODELS_REL)

    # ── M1 / M3：成员与 models.yaml 对账 ────────────────────────
    models = _load_models(models_path)
    roster = [str(r.get("name") or "").strip() for r in models]
    roster = [n for n in roster if n]
    if not models_path.is_file():
        add("M1", "error", f"缺 {_rel(models_path, root)}：成员模型没有真值源")
    elif sorted(members) != sorted(roster):
        add(
            "M1",
            "error",
            f"成员与 models.yaml 不一致（plan={sorted(members)} / 真值源={sorted(roster)}）",
        )
    if models_path.is_file():
        for name in members:
            if name not in roster:
                add("M3", "error", f"成员 {name} 在 models.yaml 的 roles 里解析不到（模型裸名必失败）")
        for entry in models:
            name = str(entry.get("name") or "").strip()
            if not name:
                add("M3", "error", "models.yaml 有 role 缺 name")
            elif not str(entry.get("effort") or "").strip():
                add("M3", "error", f"models.yaml 里 {name} 的 effort 为空（建成员时会静默降级）")

    # ── M2：任务数与 ID 集合（偏离须 allow_custom_dag + note）──
    allow_custom = bool(wave.get("allow_custom_dag"))
    note = str(wave.get("note") or "").strip()
    custom_ok = allow_custom and bool(note)
    if allow_custom and not note:
        add("M2", "error", "allow_custom_dag: true 但 wave.note 没写偏离理由")
    m2_level = "warn" if custom_ok else "error"
    if len(tasks) != len(CANON):
        hint = "（allow_custom_dag 已放行）" if custom_ok else "（偏离须 allow_custom_dag: true 并写 wave.note）"
        add("M2", m2_level, f"任务数 {len(tasks)} ≠ 规范 {len(CANON)}{hint}")
    if set(by_id) != set(CANON):
        add(
            "M2",
            m2_level,
            "任务 ID 集合 ≠ 规范："
            f"多 {sorted(set(by_id) - set(CANON))} 缺 {sorted(set(CANON) - set(by_id))}",
        )

    # ── C0：kind / assignee 必须等于规范编制 ────────────────────
    for tid, spec in CANON.items():
        task = by_id.get(tid)
        if not task:
            continue
        if task.get("kind") != spec["kind"]:
            add("C0", "error", f"{tid} kind={task.get('kind')} ≠ 规范 {spec['kind']}（改编制请改 CANON 与 PLAYBOOK）")
        if task.get("assignee") != spec["assignee"]:
            add("C0", "error", f"{tid} assignee={task.get('assignee')} ≠ 规范 {spec['assignee']}")
        owner = str(task.get("assignee") or "")
        if owner and owner not in members:
            add("C0", "error", f"{tid} 的 assignee {owner} 不在 members 里")

    # ── DAG：D2 存在性 / D1 无环 / D3 规范边 / D4 方向 ──────────
    graph = {tid: [_posix(d) for d in _as_list(task.get("dependencies"))] for tid, task in by_id.items()}
    for tid, deps in graph.items():
        for dep in deps:
            if dep not in by_id:
                add("D2", "error", f"{tid} 依赖了不存在的任务 {dep}（永不 ready）")

    WHITE, GREY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in graph}

    def dfs(node: str, stack: list[str]) -> None:
        color[node] = GREY
        for dep in graph.get(node, []):
            if dep not in color:
                continue
            if color[dep] == GREY:
                add("D1", "error", "DAG 成环：" + "→".join(stack + [node, dep]))
            elif color[dep] == WHITE:
                dfs(dep, stack + [node])
        color[node] = BLACK

    for tid in list(graph):
        if color[tid] == WHITE:
            dfs(tid, [])

    for tid, spec in CANON.items():
        if tid not in by_id:
            continue
        actual = graph.get(tid, [])
        for dep in spec["deps"]:
            if dep not in actual:
                add("D3", "error", f"{tid} 缺规范依赖 {dep}（关键边缺失 = 闸门形同虚设）")

    for tid, deps in graph.items():
        if tid not in CANON_LEVEL:
            continue
        for dep in deps:
            if dep in CANON_LEVEL and CANON_LEVEL[dep] > CANON_LEVEL[tid]:
                add("D4", "error", f"{tid} 依赖了规范上的下游 {dep}（规范序 {dep} > {tid}）——依赖只从下游加")

    # ── C1–C5 / S1–S3 / V1–V3 / K1–K2：逐任务契约 ───────────────
    for task in tasks:
        tid = str(task.get("id"))
        kind = str(task.get("kind") or "")
        desc = str(task.get("description") or "")
        acc = _as_list(task.get("acceptance"))
        ver = _as_list(task.get("verify"))
        ins = _as_list(task.get("inScope"))
        owner = str(task.get("assignee") or "")

        if kind in QUALITY_KINDS:
            if not any(a.strip() for a in acc):
                add("C1", "error", f"{tid}（{kind}）缺 acceptance——质量闸门没有判据就无法判定通过")
            if not any(v.strip() for v in ver):
                add("C2", "error", f"{tid}（{kind}）缺 verify——接受一个没有命令的验收等于没有验收")
        if kind == "work":
            for word in WORK_WORDS:
                if word not in desc:
                    add(
                        "C4",
                        "error",
                        f"{tid} 是 work kind，description 缺「{word}」（启动后不可编辑，写进 description 才生效）",
                    )
        if kind == "review":
            reviewed = str(task.get("reviewed_task") or task.get("reviewedTaskId") or "").strip()
            if not reviewed:
                add("C3", "error", f"{tid} 是 review 但没写 reviewed_task")
            elif reviewed not in by_id:
                add("C3", "error", f"{tid}.reviewed_task={reviewed} 指向不存在的任务")
            elif str(by_id[reviewed].get("kind")) not in ("implementation", "repair"):
                add(
                    "C3",
                    "error",
                    f"{tid}.reviewed_task={reviewed} 的 kind={by_id[reviewed].get('kind')}，不是 implementation/repair",
                )

        for entry in ins:
            if not is_file_path(entry):
                add("S1", "error", f"{tid} 的 inScope 不是文件路径：{entry}（目录/裸名会笼住他人文件）")
        if kind in QUALITY_KINDS and not [p for p in ins if p.strip()]:
            add("S2", "error", f"{tid}（{kind}）inScope 为空——改了什么都无法界定")

        for entry in ins:
            path = _scope_path(entry)
            if not path:
                continue
            if owner == "engineer" and path.startswith(TEST_QA):
                add("S3", "error", f"{tid}（engineer）inScope 含 {TEST_QA}——双轨分离，engineer 不碰 QA 用例")
            if owner == "qa":
                if path.startswith(CODE_ROOT):
                    add("S3", "error", f"{tid}（qa）inScope 含 {CODE_ROOT}——双轨分离，QA 不碰源码")
                elif path.startswith(TEST_ENGINEER) and not path.startswith(TEST_QA):
                    add(
                        "S3",
                        "error",
                        f"{tid}（qa）inScope 含 {TEST_ENGINEER}（只允许 {TEST_QA}）——QA 不碰单测",
                    )

        for command in ver:
            flat = command.replace('"', "").replace("'", "")
            if any(word in flat for word in WIDE_GREEN) or re.search(r"-k\s+not\b", flat):
                add("V1", "error", f"{tid} verify 被放宽：{command[:70]}（假绿比删测试更隐蔽）")
            if "python3" in command:
                add("V3", "error", f"{tid} verify 写了 python3（本机不存在该命令，验收必定执行失败）：{command[:60]}")
            if BARE_OPENSPEC.search(command):
                add("V3", "error", f"{tid} verify 用了裸 openspec（本仓库须写 openspec.cmd）：{command[:60]}")
        for criterion in acc:
            if HARD_NUMBER.search(criterion) or COVERAGE_NUMBER.search(criterion):
                add(
                    "V2",
                    "error",
                    f"{tid} acceptance 写死了测试数字：{criterion[:60]}（应写「起跑时实测值」）",
                )

        if tid in KNOWLEDGE_IDS and kind != "work":
            add("K1", "error", f"{tid} 是知识线，kind 必须 work（质量闸门面向代码）；当前 {kind}")
        if tid == "K3" and BLIND_CHECK_WORD not in desc:
            add("K2", "error", "K3 description 缺「盲验」——不写死就会退化成本人自验（利益冲突）")

    # ── C5：全文无 TODO: 占位符残留 ─────────────────────────────
    for where, blob in _iter_strings(plan):
        if PLACEHOLDER in blob:
            add("C5", "error", f"{where} 仍是占位符：{blob[:60]}")

    # ── P1 / P2：角色 SOP 的存在性与体量预算 ────────────────────
    for name in members:
        path = roles_dir / f"{name}.md"
        if not path.is_file():
            add("P2", "error", f"缺角色文件 {_rel(path, root)}（成员没有 SOP）")
            continue
        size = _size_bytes(path)
        if size > 8000:
            add("P1", "error", f"{path.name} {size}B > 8000B（每步重发，超预算会挑着执行）")
    shared = roles_dir / "_shared.md"
    if not shared.is_file():
        add("P1", "error", f"缺 {_rel(shared, root)}（共享纪律没有真值源）")
    elif _size_bytes(shared) > 3200:
        add("P1", "error", f"_shared.md {_size_bytes(shared)}B > 3200B（规则多了会被挑着执行且不报错）")

    # ── A1：现实锚点 ────────────────────────────────────────────
    case = str(wave.get("case") or "").strip()
    if not case:
        add("A1", "error", "wave.case 未填——没有现实锚点的波次不许开")
    else:
        annotations = cases_dir / case / "annotations.md"
        if not annotations.is_file():
            add("A1", "error", f"case 缺 annotations.md：{_rel(annotations, root)}")
        elif not _has_ground_truth(_read_text(annotations)):
            add(
                "A1",
                "error",
                f"{_rel(annotations, root)} 里没有可用的 ground-truth 标注（须含「ground-truth」且不全是 TBD/待补）",
            )

    # ── A2：MRD 存在 ────────────────────────────────────────────
    mrd_raw = str(wave.get("mrd") or "").strip()
    if not mrd_raw:
        add("A2", "error", "wave.mrd 未填（需求基线缺失则无从对齐）")
    else:
        candidates = [Path(mrd_raw) if Path(mrd_raw).is_absolute() else root / mrd_raw]
        candidates.append(mrd_dir / Path(mrd_raw).name)
        if not any(p.is_file() for p in candidates):
            add("A2", "error", f"MRD 不存在：{mrd_raw}（在 {_rel(mrd_dir, root)}/ 下也没找到同名文件）")

    # ── G1–G4：git 侧事实 ───────────────────────────────────────
    if facts is None:
        for code, desc in (("G1", "分支"), ("G2", "工作树"), ("G3", "baseline"), ("G4", "提交身份")):
            add(code, "pass", "跳过（--no-git）")
    else:
        branch = str(facts.get("branch") or "")
        expected = str(wave.get("branch") or "")
        if not expected:
            add("G1", "error", f"wave.branch 未填（主干是 {MAIN_BRANCH}；波次分支应为 feature/<change>）")
        elif branch and branch != expected:
            add("G1", "error", f"当前分支 {branch} ≠ plan.branch {expected}（不要在别人的分支上起波）")
        if facts.get("dirty"):
            add("G2", "warn", "工作树有未提交改动（并行 session？）——起波前确认这些不属于本波")
        baseline_ok = facts.get("baseline_ok")
        if baseline_ok is None:
            add("G3", "error", "wave.baseline_commit 未填（起队凭据：按哪一版配置起的队）")
        elif baseline_ok is False:
            add("G3", "error", f"baseline_commit {wave.get('baseline_commit')} 不在 HEAD 祖先链上")
        email = str(facts.get("email") or "")
        if email != COMMIT_EMAIL:
            add("G4", "error", f"git user.email={email or '（未配置）'} ≠ {COMMIT_EMAIL}（提交身份靠邮箱判定）")

    return out


def _table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all((not cell) or _TABLE_SEP.match(cell) for cell in cells)


def _has_ground_truth(text: str) -> bool:
    """annotations.md 是否带可用的 ground-truth 标注：含标记，且标记后的内容不全是 TBD/待补。

    跨空行看后续 12 行（标题与内容之间常有空行），遇到下一个 # 标题为止；
    markdown 表只认「分隔行之后的数据行」的值列，避免把表头当成结论。
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not GT_MARKER.search(line):
            continue
        context = [line]
        for nxt in lines[index + 1 : index + 13]:
            if nxt.strip().startswith("#"):
                break
            context.append(nxt)
        rows = [_table_cells(item) for item in context]
        header_index = -1
        for pos in range(len(context) - 1):
            nxt_cells = rows[pos + 1]
            if rows[pos] is not None and nxt_cells and _is_separator_row(nxt_cells):
                header_index = pos
        for pos, raw in enumerate(context):
            cells = rows[pos]
            if cells is None:
                blob = raw
            else:
                if pos == header_index or _is_separator_row(cells):
                    continue
                blob = " ".join(cells[1:] if len(cells) > 1 else cells)
            rest = _MD_NOISE.sub(" ", GT_MARKER.sub(" ", blob))
            for token in rest.split():
                if token.lower() not in GT_PLACEHOLDERS:
                    return True
    return False


# ── 输出 ────────────────────────────────────────────────────────────
def _rows(findings: list[dict], inventory: list[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    buckets: dict[str, list[dict]] = {}
    for finding in findings:
        buckets.setdefault(finding["code"], []).append(finding)
    rows: list[tuple[str, str, str, str]] = []
    for code, desc, _basis in inventory:
        items = buckets.pop(code, [])
        if not items:
            rows.append(("PASS", code, desc, ""))
            continue
        for finding in items:
            label = _LEVEL_LABEL.get(finding["level"], str(finding["level"]).upper())
            rows.append((label, code, desc, finding.get("msg", "")))
    for code, items in buckets.items():  # 未登记的编号也照实打印，不吞
        for finding in items:
            label = _LEVEL_LABEL.get(finding["level"], str(finding["level"]).upper())
            rows.append((label, code, str(finding.get("msg", "")), ""))
    return rows


def _print_rows(rows: list[tuple[str, str, str, str]]) -> None:
    for label, code, desc, msg in rows:
        line = f"{label} {code} {desc}"
        if msg:
            line += f" —— {msg}"
        print(line)


def _tally(findings: list[dict]) -> tuple[int, int]:
    errors = sum(1 for f in findings if f["level"] == "error")
    warnings = sum(1 for f in findings if f["level"] == "warn")
    return errors, warnings


# ── init：骨架───────────────────────────────────────────────────────
def skeleton(change: str, case: str, branch: str, mrd: str, baseline: str, members: list[str]) -> dict:
    """把「位置」摆好，把「内容」留成显式 TODO 占位符。

    只填结构不填内容——填不了的东西写 TODO:，check 会逼它被填掉。
    骨架一生成就该是红的：宁可红，也不要「看起来像完成」。
    """
    tasks = []
    for tid, spec in CANON.items():
        if tid == "T3":
            scope = f"{CODE_ROOT}TODO-{tid}.py"
        elif tid in ("T4", "T5"):
            scope = f"{TEST_QA}TODO-{tid}.py"
        elif tid in ("K1", "K2"):
            scope = f"{KNOWLEDGE_ROOT}TODO-{tid}.yaml"
        else:
            scope = f"openspec/changes/{change}/TODO-{tid}.md"
        task = {
            "id": tid,
            "kind": spec["kind"],
            "assignee": spec["assignee"],
            "subject": f"TODO: {tid} 主题（见 docs/agent-team/templates/wave-tasks.md）",
            "description": "TODO: 任务范围与判据（work kind 必含「完成定义」「失败定义」两段）",
            "dependencies": list(spec["deps"]),
            "inScope": [scope],
            "outOfScope": ["openspec/specs/"],
        }
        if spec["kind"] in QUALITY_KINDS:
            task["acceptance"] = ["TODO: 可观测的完成判据（数字写「起跑时实测值」）"]
            task["verify"] = ["TODO: 能变红的命令"]
        if spec["kind"] == "review":
            task["reviewed_task"] = "T3"
        tasks.append(task)
    return {
        "wave": {
            "change": change,
            "branch": branch,
            "case": case,
            "mrd": mrd,
            "baseline_commit": baseline,
            "engineer_test_root": TEST_ENGINEER,
            "qa_test_root": TEST_QA,
            "allow_custom_dag": False,
            "note": "",
        },
        "members": [{"name": name} for name in members],
        "tasks": tasks,
    }


PLAN_HEADER = (
    "# 波次计划（plan.yaml）：机检真值源。字段含义与断言清单见 scripts/agent_team_plan.py。\n"
    "# 填完跑 `python scripts/agent_team_plan.py check --plan <本文件>`，退出码 0 才起波；\n"
    "# 建任务用 `render <ID> --json` 取参数，不要手抄。\n"
)


def _root_of(args: argparse.Namespace) -> Path:
    value = getattr(args, "root", None)
    if value:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
    return REPO


def _plans_dir(args: argparse.Namespace, root: Path) -> Path:
    return _arg_dir(getattr(args, "plans_dir", None), root, PLANS_REL)


def _models_path(args: argparse.Namespace, root: Path) -> Path:
    value = getattr(args, "models_file", None)
    if value:
        path = Path(value)
        return path.resolve() if path.is_absolute() else (root / path).resolve()
    return (root / MODELS_REL).resolve()


def find_plan(explicit: str | None, plans_dir: Path) -> Path:
    if explicit:
        path = Path(explicit)
        path = path if path.is_absolute() else (Path.cwd() / path)
        path = path.resolve()
        if not path.is_file():
            _die(f"plan 不存在：{path}")
        return path
    plans = sorted(plans_dir.glob("*.yaml"))
    if len(plans) == 1:
        return plans[0]
    if not plans:
        _die(f"{_posix(plans_dir)} 下没有 plan.yaml，先跑 init")
    _die("有多个 plan，请用 --plan 指定：" + ", ".join(p.name for p in plans))


def cmd_init(args: argparse.Namespace) -> int:
    root = _root_of(args)
    plans_dir = _plans_dir(args, root)
    dest = plans_dir / f"{args.change}.yaml"
    if dest.exists() and not args.force:
        _die(f"{_rel(dest, root)} 已存在（--force 覆盖）")
    head = _git_head(root) or "TODO: git rev-parse --short HEAD"
    if head.startswith("TODO"):
        print("警告：拿不到 git HEAD，baseline_commit 留成占位符", file=sys.stderr)
    members = [
        str(entry.get("name")).strip()
        for entry in _load_models(_models_path(args, root))
        if str(entry.get("name") or "").strip()
    ] or list(DEFAULT_MEMBERS)
    plan = skeleton(
        change=args.change,
        case=args.case,
        branch=args.branch or f"feature/{args.change}",
        mrd=args.mrd,
        baseline=head,
        members=members,
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    text = PLAN_HEADER + yaml.safe_dump(plan, allow_unicode=True, sort_keys=False, width=100)
    dest.write_bytes(text.encode("utf-8"))  # 写字节：绕开 Windows 文本模式的 CRLF 转换
    print(f"已生成 {_rel(dest, root)}")
    print("下一步：把每个 TODO: 占位符填掉 → 跑 check；建任务用 `render <ID> --json` 取参数。")
    return 0


# ── check ───────────────────────────────────────────────────────────
def cmd_check(args: argparse.Namespace) -> int:
    root = _root_of(args)
    path = find_plan(args.plan, _plans_dir(args, root))
    plan = _load_yaml(path)
    if plan is None:
        print(f"plan 解析失败，先修 YAML：{path}", file=sys.stderr)
        return 2
    if not isinstance(plan, dict):
        print(f"plan 顶层必须是映射（{type(plan).__name__}）：{path}", file=sys.stderr)
        return 2
    cases_root = _arg_dir(args.cases_root, root, CASES_REL)
    mrd_root = _arg_dir(args.mrd_root, root, MRD_REL)
    roles_root = _arg_dir(args.roles_root, root, ROLES_REL)
    models_file = _arg_dir(args.models_file, root, MODELS_REL)
    facts = None if args.no_git else git_facts(plan, root)
    findings = check_plan(
        plan,
        root,
        facts,
        cases_root=cases_root,
        mrd_root=mrd_root,
        roles_root=roles_root,
        models_file=models_file,
    )
    errors, warnings = _tally(findings)
    if args.json:
        print(
            json.dumps(
                {"plan": _rel(path, root), "errors": errors, "warnings": warnings, "findings": findings},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"plan: {_rel(path, root)}")
        _print_rows(_rows(findings, CHECK_INVENTORY))
        if errors:
            print("—— 存在 error：不许起波（先查断言依据，再改计划；不许改脚本放宽）")
        print(f"ERRORS={errors} WARNINGS={warnings}")
    return 1 if errors else 0


# ── render：契约 → create_task 参数 ────────────────────────────────
def build_kernel(task: dict) -> dict:
    """单个任务 → create_task 的参数字典（依赖原样输出，由调用方替换真实 id）。"""
    kind = str(task.get("kind") or "")
    subject = str(task.get("subject") or "")
    kernel: dict = {
        "subject": subject,
        "description": task.get("description"),
        "kind": kind,
        "assignee": task.get("assignee"),
        "dependencies": _as_list(task.get("dependencies")),
    }
    objective = str(task.get("objective") or "").strip()
    if not objective and kind in QUALITY_KINDS:
        objective = subject
    if objective:
        kernel["objective"] = objective
    for key in ("acceptance", "inScope", "outOfScope", "verify"):
        value = task.get(key)
        if value:
            kernel[key] = _as_list(value)
    reviewed = str(task.get("reviewed_task") or task.get("reviewedTaskId") or "").strip()
    if reviewed:
        kernel["reviewedTaskId"] = f"<{reviewed} 的真实 id>"
    return kernel


def cmd_render(args: argparse.Namespace) -> int:
    root = _root_of(args)
    path = find_plan(args.plan, _plans_dir(args, root))
    plan = _load_yaml(path)
    if not isinstance(plan, dict):
        print(f"plan 解析失败或顶层不是映射：{path}", file=sys.stderr)
        return 2
    tasks = {str(t.get("id")): t for t in (plan.get("tasks") or []) if isinstance(t, dict)}
    ids = list(args.task_ids or [])
    if not ids:
        _die("render 需要一个任务 ID（如 T3）；用 checks 看断言、用 --plan 指定文件")
    missing = [tid for tid in ids if tid not in tasks]
    if missing:
        _die(f"plan 里没有这些任务：{missing}（现有：{sorted(tasks)}）")
    kernels = [(tid, build_kernel(tasks[tid])) for tid in ids]
    if args.json:
        payload = kernels[0][1] if len(kernels) == 1 else [kernel for _, kernel in kernels]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for local_id, kernel in kernels:
            print(
                f"# {local_id}：dependencies 里的 T*/K* 原样输出，create_task 时替换成真实 id；"
                "reviewedTaskId 里的 <...> 同样要替换"
            )
            print(json.dumps(kernel, ensure_ascii=False, indent=2))
            print()
    return 0


# ── checks：清单────────────────────────────────────────────────────
def cmd_checks(_: argparse.Namespace) -> int:
    check_count = len(CHECK_INVENTORY)
    closeout_count = len(CLOSEOUT_INVENTORY)
    print(f"起跑前（check 子命令，{check_count} 条）：")
    for code, desc, basis in CHECK_INVENTORY:
        print(f"  {code:<3} {desc}")
        print(f"      依据：{basis}")
    print(f"\n收口时（closeout 子命令，{closeout_count} 条）：")
    for code, desc, basis in CLOSEOUT_INVENTORY:
        print(f"  {code:<3} {desc}")
        print(f"      依据：{basis}")
    print(f"\n共 {check_count} 条起跑断言 + {closeout_count} 条收口断言 = {check_count + closeout_count} 条。")
    print("本仓库命令常量（verify / acceptance 只能写这些形态）：")
    for command in REPO_COMMANDS:
        print(f"  {command}")
    print("改了断言先看依据；红了改计划，不许改脚本放宽。")
    return 0


# ── closeout：R0–R5 ────────────────────────────────────────────────
def _resolve_change_dir(root: Path, change: str) -> Path | None:
    """归档会把目录改名成 YYYY-MM-DD-<change>；收口常在归档之后才跑，两边都认。"""
    live = root / "openspec" / "changes" / change
    if live.is_dir():
        return live
    archive = root / "openspec" / "changes" / "archive"
    if archive.is_dir():
        archived = sorted(archive.glob(f"*-{change}"))
        if archived:
            return archived[0]
    return None


def _scope_contains(entries: list[str], path: str) -> bool:
    target = _posix(path)
    for entry in entries:
        clean = _posix(entry).rstrip("/")
        if not clean:
            continue
        if target == clean or target.startswith(clean) or fnmatch(target, clean):
            return True
    return False


def parse_review_markers(text: str) -> set[str]:
    """review.md 的结论标记：行首（可带一个 |）的 A1–A6 / B1–B9 / D1–D3。"""
    found: set[str] = set()
    for line in text.splitlines():
        match = REVIEW_ROW.match(line)
        if match:
            found.add(match.group(1))
    return found


def check_closeout(
    plan: dict,
    *,
    change: str,
    root: Path = REPO,
    base: str | None = None,
    changed: list[str] | None = None,
    stage: str = "pre",
) -> list[dict]:
    """纯函数：plan + 变更名 + 改动文件列表 → findings（自测可直接喂 changed）。"""
    out: list[dict] = []

    def add(code: str, level: str, msg: str) -> None:
        out.append({"code": code, "level": level, "msg": msg})

    change = str(change or "").strip()
    if not change:
        add("R0", "error", "plan 没有 wave.change，收口无法定位本波规格目录")
        return out
    spec_dir = _resolve_change_dir(root, change)
    if spec_dir is None:
        add("R0", "error", f"规格目录不存在：openspec/changes/{change}（连 archive/*-{change} 也没有）")
        spec_dir = root / "openspec" / "changes" / change

    tasks = [t for t in (plan.get("tasks") or []) if isinstance(t, dict)]
    scope: list[str] = []
    for task in tasks:
        for entry in _as_list(task.get("inScope")):
            path = _scope_path(entry)
            if path:
                scope.append(path)

    if changed is None:
        if not base:
            add("R1", "error", "没有比对基线（--base 或 wave.baseline_commit），改动范围无从判定")
        else:
            changed = git_changed(str(base), root)
            if changed is None:
                add("R1", "error", f"git diff --name-only {base}...HEAD 失败，改动范围无从判定")

    if changed is None:
        add("R2", "pass", "跳过：拿不到改动列表，无法判定落地")
        add("R5", "pass", "跳过：拿不到改动列表")
    else:
        escaped = [
            path
            for path in changed
            if not any(path.startswith(prefix) for prefix in CLOSEOUT_EXEMPT)
            and not _scope_contains(scope, path)
        ]
        if escaped:
            suffix = " …" if len(escaped) > 8 else ""
            add(
                "R1",
                "error",
                f"{len(escaped)} 个改动越出全部 inScope（改的是没人认领的文件）：{escaped[:8]}{suffix}",
            )
        for task in tasks:
            if str(task.get("kind") or "") not in ("implementation", "repair"):
                continue
            own = [_scope_path(e) for e in _as_list(task.get("inScope"))]
            own = [p for p in own if p]
            if not any(_scope_contains(own, path) for path in changed):
                add(
                    "R2",
                    "error",
                    f"{task.get('id')}（{task.get('kind')}）在自己的 inScope 里一个文件都没落地",
                )
        if stage != "pre":
            add("R5", "pass", f"stage={stage}，不检查主规格")
        else:
            touched = [path for path in changed if path.startswith("openspec/specs/")]
            if touched:
                add("R5", "error", f"归档前手改了主规格（应由 openspec archive 合并）：{touched[:5]}")

    verification = spec_dir / "verification.md"
    if not verification.is_file():
        add("R3", "error", f"缺 openspec/changes/{change}/verification.md（T5 的产物，收口必看）")
    elif len(verification.read_bytes().strip()) < 80:
        add("R3", "warn", "verification.md 几乎是空的（<80 字节）")

    review = spec_dir / "review.md"
    if not review.is_file():
        add("R4", "error", f"缺 openspec/changes/{change}/review.md（T6 的产物，收口必看）")
    else:
        found = parse_review_markers(_read_text(review))
        missing = [row for row in REQUIRED_REVIEW_ROWS if row not in found]
        if missing:
            add(
                "R4",
                "error",
                f"review.md 缺结论标记 {missing}（共需 {len(REQUIRED_REVIEW_ROWS)} 个：A1–A6 / B1–B9 / D1–D3）",
            )
    return out


def cmd_closeout(args: argparse.Namespace) -> int:
    root = _root_of(args)
    path = find_plan(args.plan, _plans_dir(args, root))
    plan = _load_yaml(path)
    if not isinstance(plan, dict):
        print(f"plan 解析失败或顶层不是映射：{path}", file=sys.stderr)
        return 2
    wave = plan.get("wave") or {}
    change = str(args.change or (wave.get("change") if isinstance(wave, dict) else "") or "").strip()
    base = args.base or (str(wave.get("baseline_commit") or "").strip() if isinstance(wave, dict) else "")
    findings = check_closeout(plan, change=change, root=root, base=base, stage=args.stage)
    errors, warnings = _tally(findings)
    if args.json:
        print(
            json.dumps(
                {
                    "plan": _rel(path, root),
                    "change": change,
                    "errors": errors,
                    "warnings": warnings,
                    "findings": findings,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"plan: {_rel(path, root)}（change={change or '?'} / stage={args.stage}）")
        _print_rows(_rows(findings, CLOSEOUT_INVENTORY))
        if errors:
            print("—— 存在 error：不许收口／归档（先查断言依据，再补产物）")
        print(f"ERRORS={errors} WARNINGS={warnings}")
    return 1 if errors else 0


# ── CLI ────────────────────────────────────────────────────────────
def _add_repo_opts(parser: argparse.ArgumentParser, *, with_plan: bool = True, with_json: bool = True) -> None:
    if with_plan:
        parser.add_argument("--plan", help="plan.yaml 路径（默认在 plans 目录里找唯一的 *.yaml）")
    parser.add_argument("--plans-dir", help=f"计划目录（默认 {PLANS_REL}，可用临时目录自测）")
    parser.add_argument("--root", help="仓库根（默认脚本所在仓库；相对路径按 --root 解析）")
    if with_json:
        parser.add_argument("--json", action="store_true", help="输出 JSON（findings 原样）")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="agent_team_plan.py",
        description="Agent Teams 波次计划的机检与契约渲染（起跑断言 + 收口闸门）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "退出码：0 通过 / 1 有 error（不许起波、不许收口）/ 2 用法或环境错误。\n"
            "断言清单与历史依据：python scripts/agent_team_plan.py checks\n"
            "字段与断言的对应关系见 docs/agent-team/plans/README.md。"
        ),
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="按规范编制生成 plan.yaml 骨架（字段是 TODO: 占位符，check 必红）")
    p.add_argument("--change", required=True, help="change 名（kebab-case，与 feature 分支同名）")
    p.add_argument("--case", required=True, help="case 目录名（docs/cases/<case>/）")
    p.add_argument("--mrd", default="docs/mrd/mrd-v1.md", help="MRD 相对路径（默认 docs/mrd/mrd-v1.md）")
    p.add_argument("--branch", help="波次分支（默认 feature/<change>）")
    p.add_argument("--models-file", help=f"成员真值源（默认 {MODELS_REL}）")
    p.add_argument("--force", action="store_true", help="覆盖已存在的 plan 文件")
    _add_repo_opts(p, with_plan=False, with_json=False)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("check", help="对 plan.yaml 跑全部起跑断言；exit 1 = 不许起波")
    p.add_argument("--cases-root", help=f"case 根（默认 {CASES_REL}）")
    p.add_argument("--mrd-root", help=f"MRD 根（默认 {MRD_REL}）")
    p.add_argument("--roles-root", help=f"角色 SOP 目录（默认 {ROLES_REL}）")
    p.add_argument("--models-file", help=f"成员真值源（默认 {MODELS_REL}）")
    p.add_argument("--no-git", action="store_true", help="跳过 G1–G4（临时目录自测用）")
    _add_repo_opts(p)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("render", help="输出某任务的 create_task 参数（依赖里的 T*/K* 原样输出）")
    p.add_argument("task_ids", nargs="*", help="任务 ID，如 T3（可给多个）")
    _add_repo_opts(p)
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("closeout", help="收口闸门 R0–R5；exit 1 = 不许收口／归档")
    p.add_argument("--change", help="change 名（默认取 plan.wave.change）")
    p.add_argument("--base", help="比对基线 commit（默认取 plan.wave.baseline_commit）")
    p.add_argument(
        "--stage",
        choices=("pre", "post"),
        default="pre",
        help="pre=归档前（查 openspec/specs/ 未被手改）；post=归档后",
    )
    _add_repo_opts(p)
    p.set_defaults(func=cmd_closeout)

    p = sub.add_parser("checks", help="列出全部断言（编号 + 管什么 + 依据）与条数")
    p.set_defaults(func=cmd_checks)

    return ap


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
