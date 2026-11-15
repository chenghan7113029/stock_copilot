#!/usr/bin/env python3
"""Agent Teams 起队前本机环境预检（运行时 / CLI / 仓库）。

用途:
  起队建成员前，把「本机能不能跑起来」实测一遍，避免成员一开工就撞环境：
    1. 运行时：python ≥ 3.11、`python -m pytest` 可用、`python -m ruff` 可用、
       PyYAML 可 import；
    2. CLI：`openspec.cmd --version` 可用（记录版本）；若只能通过 .cmd shim 才可用，
       明确提示「须用 openspec.cmd」；
    3. 仓库：git 工作树成立、`git config user.email` 是约定身份、当前分支名、
       `git status --short` 是否干净（脏只 warning，不失败）。
  只做本地探测，不连网络、不读任何 token/凭据文件内容。

用法:
  python scripts/agent_team_preflight.py
  python scripts/agent_team_preflight.py --json

退出码:
  0 = 全部就绪（允许有 warning，如工作区有未提交改动）
  1 = 有需修项（openspec 不可用、git user.email/user.name 不符、pytest/ruff/PyYAML 缺失）
  2 = 有不可用项（python < 3.11、当前目录不是 git 工作树 —— 得先换环境）
"""
import argparse
import json
import os
import subprocess
import sys
import unicodedata
from pathlib import Path

# 统一 UTF-8 输出，避免已收窄为 GBK 的管道在 ✔/✘ 上抛 UnicodeEncodeError。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(__file__).resolve().parents[1]  # 仓库根（scripts/ 的上一级）

EXPECTED_GIT_EMAIL = "chenghan7113029@users.noreply.github.com"
EXPECTED_GIT_NAME = "chenghan7113029"
MIN_PYTHON = (3, 11)
CMD_TIMEOUT = 120

STATUS_OK = "ok"
STATUS_FIX = "fix"
STATUS_UNAVAILABLE = "unavailable"

MARK = {STATUS_OK: "✔", STATUS_FIX: "✘", STATUS_UNAVAILABLE: "✘"}


def run(cmd, *, cwd=None, timeout=CMD_TIMEOUT):
    """跑命令，返回 (rc, 合并后的输出文本)；命令不存在返回 (None, 错误说明)。"""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(cwd) if cwd else None,
            timeout=timeout,
        )
    except FileNotFoundError:
        return None, f"命令未找到: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return None, f"命令超时（>{timeout}s）: {' '.join(cmd)}"
    except OSError as exc:
        return None, f"命令无法执行: {' '.join(cmd)}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def item(name, status, detail, hint=None):
    return {"name": name, "status": status, "detail": detail, "hint": hint}


def first_line(text, fallback="?"):
    for line in (text or "").splitlines():
        line = line.strip()
        if line:
            return line
    return fallback


def pad(text, width):
    """按显示宽度补空格（CJK 算 2 列），让中文条目名也能对齐。"""
    cells = sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)
    return text + " " * max(0, width - cells)


def check_python():
    version = ".".join(str(x) for x in sys.version_info[:3])
    if sys.version_info[:2] < MIN_PYTHON:
        return item(
            "python",
            STATUS_UNAVAILABLE,
            f"{version}（需 ≥ {'.'.join(map(str, MIN_PYTHON))}）",
            "升级 Python 或换用符合条件的解释器启动本脚本",
        )
    return item("python", STATUS_OK, f"{version}（≥ {'.'.join(map(str, MIN_PYTHON))}；{sys.executable}）")


def check_module_cli(label, module, arg="--version"):
    rc, text = run([sys.executable, "-m", module, arg])
    if rc is None:
        return item(label, STATUS_UNAVAILABLE, text, f"确认 {module} 已装进当前解释器")
    if rc != 0:
        return item(
            label,
            STATUS_FIX,
            f"`python -m {module} {arg}` 退出码 {rc}: {first_line(text)}",
            f"pip install {module}",
        )
    return item(label, STATUS_OK, first_line(text))


def check_pyyaml():
    try:
        import yaml  # noqa: PLC0415 —— 就为了探测能否 import
    except ImportError as exc:
        return item("PyYAML", STATUS_FIX, f"import yaml 失败: {exc}", "pip install pyyaml")
    return item("PyYAML", STATUS_OK, f"{getattr(yaml, '__version__', '?')}（import yaml 正常）")


def openspec_exe_candidates():
    if os.name == "nt":
        # Windows 上 npm 包的可执行入口是 .cmd shim；裸 `openspec` 直接 subprocess 会
        # FileNotFoundError（CreateProcess 不能直接跑 .cmd）。
        return ["openspec.cmd", "openspec"]
    return ["openspec"]


def check_openspec():
    tried, version = [], None
    working = None
    for exe in openspec_exe_candidates():
        rc, text = run([exe, "--version"])
        if rc is None:
            tried.append(f"{exe}: {text}")
            continue
        tried.append(f"{exe}: 退出码 {rc}")
        if rc == 0 and text:
            working, version = exe, first_line(text)
            break

    if working is None:
        return item(
            "openspec",
            STATUS_FIX,
            "openspec.cmd --version 不可用（" + "；".join(tried) + "）",
            "npm i -g openspec 后用 openspec.cmd 调用",
        )

    # 诊断 shim：.cmd 能用但裸命令不能用 → 必须写明「须用 openspec.cmd」
    bare_ok = True
    if os.name == "nt" and working != "openspec":
        rc, text = run(["openspec", "--version"])
        bare_ok = rc == 0
        if not bare_ok:
            tried.append(f"openspec: {text if rc is None else f'退出码 {rc}'}")

    if bare_ok:
        return item("openspec", STATUS_OK, f"{version}（{working}）")
    return item(
        "openspec",
        STATUS_OK,
        f"{version}（{working}；裸 `openspec` 不可直接调用 → 须用 openspec.cmd）",
        "脚本/agent 里一律写 openspec.cmd --version，不要写裸 openspec",
    )


def check_repo():
    results = []

    rc, text = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT)
    if rc != 0 or text.strip().lower() != "true":
        results.append(
            item(
                "git 工作树",
                STATUS_UNAVAILABLE,
                f"{ROOT} 不是 git 工作树" + (f"（{first_line(text)}）" if text else ""),
                "在仓库内运行本脚本",
            )
        )
        return results
    results.append(item("git 工作树", STATUS_OK, f"成立（{ROOT}）"))

    rc, text = run(["git", "config", "user.email"], cwd=ROOT)
    email = first_line(text) if rc == 0 else ""
    if rc != 0 or email != EXPECTED_GIT_EMAIL:
        results.append(
            item(
                "git user.email",
                STATUS_FIX,
                f"当前 {email or '(未设置)'}，应为 {EXPECTED_GIT_EMAIL}",
                f"git config user.email {EXPECTED_GIT_EMAIL}",
            )
        )
    else:
        results.append(item("git user.email", STATUS_OK, email))

    rc, text = run(["git", "config", "user.name"], cwd=ROOT)
    name = first_line(text) if rc == 0 else ""
    if rc != 0 or name != EXPECTED_GIT_NAME:
        results.append(
            item(
                "git user.name",
                STATUS_FIX,
                f"当前 {name or '(未设置)'}，应为 {EXPECTED_GIT_NAME}",
                f"git config user.name {EXPECTED_GIT_NAME}",
            )
        )
    else:
        results.append(item("git user.name", STATUS_OK, name))

    rc, text = run(["git", "branch", "--show-current"], cwd=ROOT)
    branch = text.strip() if rc == 0 else ""
    if rc != 0:
        results.append(item("当前分支", STATUS_FIX, f"读取失败: {first_line(text)}", "git branch --show-current"))
    elif not branch:
        results.append(item("当前分支", STATUS_FIX, "detached HEAD（无分支名）", "git switch <branch>"))
    else:
        expected_shape = "main 或 feature/<change>"
        results.append(item("当前分支", STATUS_OK, f"{branch}（约定形态：{expected_shape}）"))

    rc, text = run(["git", "status", "--short"], cwd=ROOT)
    if rc != 0:
        results.append(item("工作区", STATUS_FIX, f"git status 失败: {first_line(text)}", None))
    else:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            results.append(item("工作区", STATUS_OK, "干净"))
        else:
            preview = "；".join(lines[:5])
            more = f" 等 {len(lines)} 项" if len(lines) > 5 else ""
            results.append(
                item(
                    "工作区",
                    STATUS_OK,
                    f"有 {len(lines)} 项未提交改动（warning，不阻塞）：{preview}{more}",
                )
            )
    return results


def collect():
    return [
        (
            "运行时",
            [check_python(), check_module_cli("pytest", "pytest"), check_module_cli("ruff", "ruff"), check_pyyaml()],
        ),
        ("CLI", [check_openspec()]),
        ("仓库", check_repo()),
    ]


def main():
    ap = argparse.ArgumentParser(description="Agent Teams 起队前本机环境预检（运行时/CLI/仓库）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    groups = collect()

    n_fix = sum(1 for _, items in groups for it in items if it["status"] == STATUS_FIX)
    n_unavail = sum(1 for _, items in groups for it in items if it["status"] == STATUS_UNAVAILABLE)
    n_ok = sum(1 for _, items in groups for it in items if it["status"] == STATUS_OK)
    dirty_notes = [
        it["detail"]
        for _, items in groups
        for it in items
        if it["name"] == "工作区" and it["status"] == STATUS_OK and "未提交改动" in it["detail"]
    ]

    if args.json:
        print(
            json.dumps(
                {
                    "root": str(ROOT),
                    "groups": [
                        {
                            "group": gname,
                            "items": [
                                {
                                    "name": it["name"],
                                    "status": it["status"],
                                    "detail": it["detail"],
                                    "hint": it["hint"],
                                }
                                for it in items
                            ],
                        }
                        for gname, items in groups
                    ],
                    "summary": {"ok": n_ok, "fix": n_fix, "unavailable": n_unavail},
                    "ready": n_fix == 0 and n_unavail == 0,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Agent Teams 起队前预检（仓库: {ROOT}）")
        print("=" * 64)
        for gname, items in groups:
            print(f"\n[{gname}]")
            for it in items:
                print(f"  {MARK[it['status']]} {pad(it['name'], 16)} {it['detail']}")
                if it["status"] != STATUS_OK and it["hint"]:
                    print(f"      → {it['hint']}")
        print("\n" + "-" * 64)
        if dirty_notes:
            print(f"warning: {dirty_notes[0]}；建议起队前先提交，便于成员以干净基线开工。")
        if n_unavail:
            print(f"结论: {n_unavail} 项不可用、{n_fix} 项需修 —— 先修环境再起队。")
        elif n_fix:
            print(f"结论: {n_fix} 项需修 —— 修完再起队。")
        else:
            print("结论: 全部就绪，可以起队。")

    if n_unavail:
        sys.exit(2)
    if n_fix:
        sys.exit(1)


if __name__ == "__main__":
    main()
