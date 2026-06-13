#!/usr/bin/env bash
# 开发环境初始化：创建 venv 并安装项目（含 dev 依赖）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"

echo "Done. Activate: source .venv/bin/activate"
