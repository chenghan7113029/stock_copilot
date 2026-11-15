#!/usr/bin/env python3
"""Agent Teams 成员模型解析器：角色 → 模型 name → 本机真实 model id。

用途:
  读 docs/agent-team/models.yaml（角色 → 模型 name → effort 的唯一真源），把每个角色
  的 `model`（模型 name，如 "DeepSeek-V4-Pro"）解析成本机可传给
  agent_teams_add_member 的真实 model id（如 "deepseek-v4-pro"），并校验 effort
  落在该模型允许的集合内。

为什么不用 list_subagent_models:
  那是 subagent 委托工具，只列 coding_plan 子集（本机实测只有 deepseek-flash），
  不是 AgentTeams 成员模型的权威来源。name 稳定、id 随环境变，所以 models.yaml
  只写 name，本脚本负责按 name 找 id。

解析顺序（逐层尝试，命中即用，并记录来源）:
  1. $DSH_HOME/settings.yaml.imported 的 llm-pi-ai.providers.<provider>.models[]
     （元素含 name/id 对；按 name 大小写不敏感匹配，优先 provider 与 models.yaml 一致者）
  2. $DSH_PROFILE_DIR/cordis.patch.yml 的 agent-default-model 条目
     （只有 provider/model，没有 name→id 映射；用作一致性交叉校验，不是解析层）
  3. 内置映射兜底 BUILTIN_MODEL_IDS（本机 app catalog 实测，见该常量上方注释）

用法:
  python scripts/agent_team_models.py
  python scripts/agent_team_models.py --json
  python scripts/agent_team_models.py --models-file docs/agent-team/models.yaml
  python scripts/agent_team_models.py --settings <registry> --profile-dir <dsh profile 目录>

退出码:
  0 = 所有角色解析成功
  1 = 有角色解析失败（name 在任何来源都找不到）、models.yaml 缺失/结构错、
      effort 越界（对该模型已知允许集合），或读入的 yaml 解析失败
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

# 输出统一走 UTF-8；控制台本来就是 UTF-8，重定向时也不会因 GBK 编不出来而崩。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # 非 TextIO，忽略
        pass

ROOT = Path(__file__).resolve().parents[1]  # 仓库根（scripts/ 的上一级）
DEFAULT_MODELS_FILE = ROOT / "docs" / "agent-team" / "models.yaml"

# 本机 app catalog 实测（2026-11-14，Windows，dsh desktop）。
# 实测内容：内置 catalog 的 DEFAULT_MODELS 数组里有两条 name/id 对
#   { id: "deepseek-flash",    name: "DeepSeek-V4.1-Flash" }
#   { id: "deepseek-v4-pro",   name: "DeepSeek-V4-Pro" }
# 发现方式（换机器/升级后照此更新本表）：
#   1) 在 dsh 安装目录的 resources/ 下，
#        grep -a "DEFAULT_MODELS" app.asar | head
#      asar 内是打包 JS，可用 grep -a 直接读；
#   2) 或在 GUI 的模型选择器里看模型显示名（name）与调用时实际用的 id。
# 注意：catalog 可被 deployment 覆盖，所以它只是兜底，registry 有 name/id 对时以 registry 为准。
BUILTIN_MODEL_IDS = {
    "DeepSeek-V4.1-Flash": "deepseek-flash",
    "DeepSeek-V4-Pro": "deepseek-v4-pro",
}
_BUILTIN_BY_LOWER = {k.lower(): v for k, v in BUILTIN_MODEL_IDS.items()}

# 本机实测的 effort 允许集合：deepseek-flash 的 reasoningEfforts 为
# off / low / high / max（无 medium）。
# deepseek-v4-pro 属同族，但本机拿不到它的 reasoningEfforts 键集合，故不内置
# （遇到它只发 warning、跳过校验，不阻塞）。
EFFORT_ALLOWED = {"deepseek-flash": ("off", "low", "high", "max")}


def eprint(msg):
    print(msg, file=sys.stderr)


def die(msg):
    eprint(f"[ERROR] {msg}")
    sys.exit(1)


def dsh_home():
    env = os.environ.get("DSH_HOME")
    return Path(env).expanduser() if env else Path.home() / ".dsh"


def dsh_profile_dir():
    env = os.environ.get("DSH_PROFILE_DIR")
    return Path(env).expanduser() if env else dsh_home() / "profiles" / "desktop"


def load_yaml_file(path, *, required, label):
    """读 yaml；required=True 时缺失/解析失败直接退出。"""
    p = Path(path).expanduser()
    if not p.is_file():
        if required:
            die(f"{label} 不存在: {p}")
        return None
    try:
        with p.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        if required:
            die(f"{label} 读取/解析失败: {p}: {exc}")
        eprint(f"[WARN] {label} 读取/解析失败，跳过该层: {p}: {exc}")
        return None


def load_roles(path):
    data = load_yaml_file(path, required=True, label="models.yaml")
    roles = (data or {}).get("roles") if isinstance(data, dict) else None
    if not isinstance(roles, list) or not roles:
        die(f"{path} 缺少非空 roles 列表")
    bad = [i for i, r in enumerate(roles) if not isinstance(r, dict)]
    if bad:
        die(f"{path} 的 roles 第 {bad} 项不是 mapping")
    return roles


def collect_providers(node, path=""):
    """递归找 settings 里所有含 models 列表的 providers 段。"""
    found = []
    if isinstance(node, dict):
        providers = node.get("providers")
        if isinstance(providers, dict):
            for pname, pdata in providers.items():
                if isinstance(pdata, dict) and isinstance(pdata.get("models"), list):
                    dot = f"{path}.providers.{pname}" if path else f"providers.{pname}"
                    found.append((dot, str(pname), pdata))
        for key, val in node.items():
            found.extend(collect_providers(val, f"{path}.{key}" if path else str(key)))
    elif isinstance(node, list):
        for i, val in enumerate(node):
            found.extend(collect_providers(val, f"{path}[{i}]"))
    return found


def _efforts_of(model):
    raw = model.get("reasoningEfforts")
    if isinstance(raw, dict):
        return tuple(str(k) for k in raw)
    if isinstance(raw, list):
        return tuple(str(x) for x in raw if isinstance(x, (str, int, float)))
    return ()


def registry_index(settings_path):
    """{name_lower: [ {id, efforts, provider, source} ]}；文件缺失或无该段时为空（走兜底）。"""
    settings = load_yaml_file(settings_path, required=False, label="settings.yaml.imported")
    index = {}
    if not isinstance(settings, dict):
        return index
    for dot_path, provider, pdata in collect_providers(settings):
        for model in pdata["models"]:
            if not isinstance(model, dict):
                continue
            name, mid = model.get("name"), model.get("id")
            if not name or not mid:
                continue
            index.setdefault(str(name).strip().lower(), []).append(
                {
                    "id": str(mid),
                    "efforts": _efforts_of(model),
                    "provider": provider,
                    "source": f"{settings_path}:{dot_path}",
                }
            )
    return index


DEFAULT_MODEL_ID = "agent-default-model"


def patch_default_model(patch_path):
    """从 cordis.patch.yml 取 (provider, model, effort)。

    patch 文件是顶层 loader entry 数组。正常用 safe_load；若文件里有 `!!js` 之类
    自定义 tag 导致 safe_load 失败，退回正则只抽 agent-default-model 块，避免整层失效。
    取不到返回 None。
    """
    p = Path(patch_path).expanduser()
    if not p.is_file():
        return None
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        eprint(f"[WARN] cordis.patch.yml 读取失败，跳过一致性校验: {exc}")
        return None

    def pick(block):
        if not isinstance(block, dict):
            return None
        provider = block.get("provider")
        model = block.get("model")
        if not provider or not model:
            return None
        return {
            "provider": str(provider),
            "model": str(model),
            "effort": str(block.get("reasoningEffort") or ""),
        }

    try:
        entries = yaml.safe_load(text)
    except yaml.YAMLError:
        entries = None
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and entry.get("id") == DEFAULT_MODEL_ID:
                hit = pick(entry.get("config"))
                if hit:
                    return hit
        return None

    # safe_load 失败（自定义 tag）→ 只抓 agent-default-model 块
    m = re.search(
        rf"id:\s*[\"']?{re.escape(DEFAULT_MODEL_ID)}[\"']?(.*?)(?=^\s*-\s+id:|\Z)",
        text,
        re.S | re.M,
    )
    if not m:
        return None
    block = {}
    for key in ("provider", "model", "reasoningEffort"):
        mm = re.search(rf"\b{key}:\s*[\"']?([^\s\"'#]+)", m.group(1))
        if mm:
            block[key] = mm.group(1)
    return pick(block)


def candidates(index):
    """解析失败时给用户看的候选 name 列表（内置表 + registry 里能看到的 name）。

    不含 cordis.patch.yml 的 model：那里是 id 不是 name，列出来会误导。
    """
    names = dict(BUILTIN_MODEL_IDS)  # display name -> id
    for lower in index:
        for rec in index[lower]:
            names.setdefault(lower, rec["id"])
    return sorted(names.items())


def patch_note(provider, resolved_id, patch):
    """一致性说明；只在能取到 patch 默认模型时返回非空。"""
    if not patch:
        return ""
    if patch["provider"] != provider:
        return f"；注意 patch 默认 provider={patch['provider']}，与本角色 provider={provider} 不同"
    if resolved_id == patch["model"]:
        return "；与 cordis.patch.yml 默认模型一致"
    return f"；非 patch 默认模型（默认 {patch['model']}）"


def resolve(roles, index, patch):
    resolved, errors, warnings = [], [], []

    for role in roles:
        name = str(role.get("name") or "?").strip()
        role_disp = str(role.get("role") or name).strip()
        provider = str(role.get("provider") or "").strip()
        model_name = str(role.get("model") or "").strip()
        effort = str(role.get("effort") or "high").strip()

        if not model_name:
            errors.append(f"{name}: models.yaml 缺 model 字段")
            continue

        recs = index.get(model_name.lower(), [])
        chosen = next((r for r in recs if provider and r["provider"] == provider), None)
        if chosen is None and recs:
            chosen = recs[0]
            if provider and chosen["provider"] != provider:
                warnings.append(
                    f"{name}: registry 里 '{model_name}' 只出现在 provider={chosen['provider']}，"
                    f"与 models.yaml 的 provider={provider} 不一致"
                )

        if chosen:
            resolved_id, source, efforts = chosen["id"], chosen["source"], chosen["efforts"]
        else:
            resolved_id = _BUILTIN_BY_LOWER.get(model_name.lower())
            source = "builtin-catalog（本机 app DEFAULT_MODELS 实测）" if resolved_id else ""
            efforts = None

        if not resolved_id:
            pairs = ", ".join(f"{n}→{i}" for n, i in candidates(index))
            errors.append(
                f"{name}: 模型 name '{model_name}' 在 registry / patch / 内置表里都解析不出 id"
                f"（可用 name：{pairs}）"
            )
            continue

        allowed = efforts or EFFORT_ALLOWED.get(resolved_id)
        if allowed is None:
            warnings.append(
                f"{name}: 模型 {resolved_id} 的 effort 允许集合本机未实测，跳过校验（effort={effort}）"
            )
        elif effort not in allowed:
            errors.append(
                f"{name}: effort '{effort}' 不被 {resolved_id} 支持（允许: {'/'.join(allowed)}）"
            )
            continue

        note = patch_note(provider, resolved_id, patch) if provider else ""
        if provider and patch and patch["provider"] != provider:
            warnings.append(
                f"{name}: 角色 provider={provider} 与 patch 默认 provider={patch['provider']} 不同"
                "（成员显式传 provider 即可，不算错误）"
            )

        resolved.append(
            {
                "name": name,
                "role": role_disp,
                "provider": provider,
                "model": model_name,
                "effort": effort,
                "resolved_id": resolved_id,
                "source": source + note,
            }
        )

    return resolved, errors, warnings


def main():
    ap = argparse.ArgumentParser(description="解析 Agent Teams 成员模型（role → name → id）")
    ap.add_argument("--json", action="store_true", help="输出 JSON 数组（逐条含 resolved_id/source）")
    ap.add_argument("--models-file", default=str(DEFAULT_MODELS_FILE), help="models.yaml 路径")
    ap.add_argument(
        "--settings",
        default=str(dsh_home() / "settings.yaml.imported"),
        help="registry（settings.yaml.imported）路径；缺省取 $DSH_HOME",
    )
    ap.add_argument(
        "--profile-dir",
        default=str(dsh_profile_dir()),
        help="dsh profile 目录（内含 cordis.patch.yml）；缺省取 $DSH_PROFILE_DIR",
    )
    args = ap.parse_args()

    roles = load_roles(args.models_file)
    index = registry_index(args.settings)
    patch = patch_default_model(Path(args.profile_dir) / "cordis.patch.yml")

    resolved, errors, warnings = resolve(roles, index, patch)

    for msg in warnings:
        eprint(f"[WARN] {msg}")
    for msg in errors:
        eprint(f"[ERROR] {msg}")

    if args.json:
        print(json.dumps(resolved, ensure_ascii=False, indent=2))
    else:
        header = (
            f"{'name':20s} {'role':20s} {'model(name)':22s} "
            f"{'effort':7s} {'resolved_id':16s} 来源"
        )
        print(header)
        print("-" * len(header))
        for r in resolved:
            print(
                f"{r['name']:20s} {r['role']:20s} {r['model']:22s} "
                f"{r['effort']:7s} {r['resolved_id']:16s} {r['source']}"
            )
        print()
        print(f"models.yaml : {Path(args.models_file)}")
        print(f"registry    : {Path(args.settings)}（解析到 {len(index)} 个 name）")
        print(f"patch       : {Path(args.profile_dir) / 'cordis.patch.yml'}（默认模型 "
              f"{patch['provider']}/{patch['model']}）" if patch
              else f"patch       : {Path(args.profile_dir) / 'cordis.patch.yml'}（无 agent-default-model）")

    if errors:
        sys.exit(1)
    if not args.json:
        print(f"\n结论: {len(resolved)}/{len(roles)} 个角色解析成功，可起队。")


if __name__ == "__main__":
    main()
