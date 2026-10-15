#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ASSETS_DIR="$ROOT_DIR/../000-Assets"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

command -v "$PYTHON_BIN" >/dev/null || { echo "需要 Python 3.11" >&2; exit 1; }
"$PYTHON_BIN" -m venv "$ROOT_DIR/.venv"
if [[ -d "$ASSETS_DIR/presidio-main/presidio-analyzer" && -d "$ASSETS_DIR/presidio-main/presidio-anonymizer" ]]; then
  "$ROOT_DIR/.venv/bin/pip" install -e "$ASSETS_DIR/presidio-main/presidio-analyzer" -e "$ASSETS_DIR/presidio-main/presidio-anonymizer"
fi
"$ROOT_DIR/.venv/bin/pip" install -e "$ROOT_DIR[test,secure-llm]"
echo "安装完成。运行：./scripts/start_privacyguard.sh"
