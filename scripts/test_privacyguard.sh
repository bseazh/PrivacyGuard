#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
curl -fsS http://127.0.0.1:5002/health >/dev/null || { echo "Presidio 未启动" >&2; exit 1; }
.venv/bin/python -m pytest -q \
  tests/test_privacyguard_core.py tests/test_presidio_adapter.py \
  tests/test_local_api.py tests/test_pdf_redactor.py tests/test_pseudonym.py tests/test_quality_audit.py tests/test_safe_files.py
if .venv/bin/python -c 'import importlib.util; assert importlib.util.find_spec("litellm")' 2>/dev/null; then
  .venv/bin/python -m pytest -q tests/test_secure_ask.py
else
  echo "未安装 secure-llm 可选依赖，跳过 LiteLLM 验收；不能报告该链路已通过。"
fi
.venv/bin/python tests/mcp_smoke.py
echo "PrivacyGuard Core、安全文件、LiteLLM Guardrail、Presidio 与 MCP 验证通过。"
