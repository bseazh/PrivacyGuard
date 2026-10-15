#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
curl --noproxy '*' -fsS http://127.0.0.1:5002/health >/dev/null || { echo "Presidio 未启动" >&2; exit 1; }
curl --noproxy '*' -fsS http://127.0.0.1:8000/health >/dev/null || { echo "RedactionEverything 未启动" >&2; exit 1; }
.venv/bin/python -m pytest -q \
  tests/test_privacyguard_core.py tests/test_presidio_adapter.py tests/test_redaction_adapter.py \
  tests/test_local_api.py tests/test_pdf_redactor.py tests/test_pseudonym.py tests/test_quality_audit.py tests/test_safe_files.py
if .venv/bin/python -c 'import importlib.util; assert importlib.util.find_spec("litellm")' 2>/dev/null; then
  .venv/bin/python -m pytest -q tests/test_secure_ask.py
else
  echo "未安装 secure-llm 可选依赖，跳过 LiteLLM 验收；不能报告该链路已通过。"
fi
.venv/bin/python tests/mcp_smoke.py
if [[ -x "$ROOT_DIR/.venv-mlx/bin/python" && -f "$ROOT_DIR/models/qwen3/Qwen3-1.7B-bf16/model.safetensors" ]]; then
  curl --noproxy '*' -fsS http://127.0.0.1:8011/v1/models >/dev/null || { echo "MLX 模型服务未启动" >&2; exit 1; }
  export PRIVACYGUARD_MLX_PYTHON="$ROOT_DIR/.venv-mlx/bin/python"
  export PRIVACYGUARD_LLM_MODEL="openai/$ROOT_DIR/models/qwen3/Qwen3-1.7B-bf16"
  export PRIVACYGUARD_LLM_BASE_URL="http://127.0.0.1:8011/v1"
  export PRIVACYGUARD_LLM_API_KEY="local-only"
  .venv/bin/python tests/secure_ask_live.py
else
  echo "未找到 MLX 环境或 Qwen3 权重，不能报告 LiteLLM 真实链路通过。" >&2
  exit 1
fi
echo "PrivacyGuard Core、安全文件、Presidio、RedactionEverything、MCP 与 LiteLLM→MLX 真实链路全部通过。"
