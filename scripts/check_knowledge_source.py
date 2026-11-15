#!/usr/bin/env python3
"""知识条目「无来源知识=0」机检：每个条目都必须有 confidence，且 confidence=确定 时必须有非空 source。

用途:
  递归扫 <root>（默认 config/knowledge）下的 *.yaml / *.yml，按下面的规则判定「知识条目」：
    - 文件顶层是 list → 每个元素是一个知识条目；
    - 文件顶层是 dict 且有 `entries:` list → `entries` 的每个元素是一个知识条目；
    - 文件顶层是 dict 且自身带 `confidence` 字段 → 该 dict 本身是一个知识条目。
  对每个条目检查：
    - 必填：source、confidence、owner、strength、frequency、lifecycle；
    - confidence ∈ {确定, 假设, 未知}；
    - confidence=确定 时 source 必须非空（其余 confidence 允许空 source）。
  缺字段 / 枚举越界 / 确定无来源 → error（带 文件:路径 定位）；空库不是错误。

为什么需要它:
  「无来源知识=0」是知识库的准出门槛，必须能机械判定；靠人读 YAML 核对会漏，
  而永远不报错的检查比没有检查更糟（假绿）。

用法:
  python scripts/check_knowledge_source.py
  python scripts/check_knowledge_source.py --root config/knowledge
  python scripts/check_knowledge_source.py --json

退出码:
  0 = 无 error（warning 不影响退出码；目录不存在/无条目也算 0）
  1 = 至少一个 error（缺字段、confidence 非法、确定无来源、YAML 解析失败）
"""
import argparse
import json
import sys
from pathlib import Path

import yaml

# 统一 UTF-8 输出。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

DEFAULT_ROOT = "config/knowledge"
REQUIRED_FIELDS = ("source", "confidence", "owner", "strength", "frequency", "lifecycle")
NON_EMPTY_FIELDS = ("confidence", "owner", "strength", "frequency", "lifecycle")
CONFIDENCE_VALUES = ("确定", "假设", "未知")
CONFIDENCE_CERTAIN = "确定"


def is_nonempty(value):
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) > 0
    return True


def extract_entries(doc):
    """返回 [(条目路径, 值)]；路径形如 'entries[2]' / '[2]' / ''（顶层 dict 自身即条目）。"""
    if isinstance(doc, list):
        return [(f"[{i}]", v) for i, v in enumerate(doc)]
    if isinstance(doc, dict):
        entries = doc.get("entries")
        if isinstance(entries, list):
            return [(f"entries[{i}]", v) for i, v in enumerate(entries)]
        if "confidence" in doc:
            return [("", doc)]
    return []


def join(entry_path, field):
    return f"{entry_path}.{field}" if entry_path else field


def check_entry(entry_path, entry):
    """返回 errors，每条是 (定位后缀, 说明)。"""
    errors = []
    if not isinstance(entry, dict):
        errors.append((entry_path or "<root>", f"条目不是 mapping（实际 {type(entry).__name__}），无法检查字段"))
        return errors

    confidence = entry.get("confidence")
    confidence_ok = isinstance(confidence, str) and confidence in CONFIDENCE_VALUES

    for field in REQUIRED_FIELDS:
        if field not in entry:
            errors.append((join(entry_path, field), "缺少必填字段"))
            continue
        value = entry[field]
        if field in NON_EMPTY_FIELDS and not is_nonempty(value):
            errors.append((join(entry_path, field), "必填字段为空"))
        elif field == "confidence" and not confidence_ok:
            if isinstance(value, str):
                errors.append(
                    (join(entry_path, field), f"confidence='{value}' 不在 {list(CONFIDENCE_VALUES)} 内")
                )
            else:
                errors.append((join(entry_path, field), f"confidence 类型应为 str（实际 {type(value).__name__}）"))

    if confidence_ok and confidence == CONFIDENCE_CERTAIN:
        if "source" in entry and not is_nonempty(entry.get("source")):
            # source 缺失已由上面的「缺少必填字段」覆盖，这里只报「有字段但为空」
            errors.append(
                (join(entry_path, "source"), "confidence=确定 但没有来源（无来源知识=0，必须补 source）")
            )

    return errors


def scan_file(path):
    """返回 (条目数, errors, warnings)，errors/warnings 为 dict。"""
    errors, warnings, n_entries = [], [], 0
    rel = path.as_posix()
    try:
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        errors.append({"file": rel, "path": "<file>", "message": f"YAML 读取/解析失败: {exc}"})
        return 0, errors, warnings

    entries = extract_entries(doc)
    if not entries:
        warnings.append(
            {
                "file": rel,
                "path": "<file>",
                "message": "不是知识条目容器（顶层 list / entries: / 带 confidence 的 dict），已跳过",
            }
        )
        return 0, errors, warnings

    for entry_path, entry in entries:
        n_entries += 1
        for suffix, message in check_entry(entry_path, entry):
            errors.append({"file": rel, "path": suffix, "message": message})
    return n_entries, errors, warnings


def main():
    ap = argparse.ArgumentParser(description="知识条目来源机检（无来源知识=0）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help=f"知识库根目录（默认 {DEFAULT_ROOT}）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    args = ap.parse_args()

    root = Path(args.root)
    files = []
    if root.is_dir():
        files = sorted({p for pattern in ("*.yaml", "*.yml") for p in root.rglob(pattern) if p.is_file()})

    errors, warnings, n_entries = [], [], 0
    for path in files:
        n, errs, warns = scan_file(path)
        n_entries += n
        errors.extend(errs)
        warnings.extend(warns)

    display_root = args.root.rstrip("/\\") + "/"
    empty = not files or n_entries == 0

    if args.json:
        print(
            json.dumps(
                {
                    "root": args.root,
                    "files": len(files),
                    "entries": n_entries,
                    "errors": errors,
                    "warnings": warnings,
                    "ok": not errors,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if errors else 0

    if empty:
        print(f"未发现知识条目（{display_root} 为空或不存在）")
        if files:
            skipped = ", ".join(sorted({w["file"] for w in warnings})) or "（无）"
            print(f"  实际扫描 {len(files)} 个 yaml，均非知识条目容器：{skipped}")
        for warn in warnings:
            print(f"  [warn] {warn['file']}: {warn['message']}")
        print("结论: 空库不是错误，退出码 0。")
        return 0

    print(f"知识来源机检（root: {args.root}）")
    print("=" * 64)
    print(f"扫描 {len(files)} 个文件，识别 {n_entries} 个知识条目")
    for err in errors:
        print(f"  ✘ {err['file']}:{err['path']}  {err['message']}")
    for warn in warnings:
        print(f"  ⚠ {warn['file']}:{warn['path']}  {warn['message']}")
    print("-" * 64)
    print(
        f"结论: {len(errors)} error，{len(warnings)} warning —— "
        + ("通过（无来源知识=0）。" if not errors else "不通过，逐条修掉上面标 ✘ 的。")
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
