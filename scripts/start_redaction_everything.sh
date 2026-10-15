#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REDACTION_ROOT="${PRIVACYGUARD_REDACTION_ROOT:-$ROOT_DIR/redaction-everything}"
BACKEND="$REDACTION_ROOT/backend"
STATE_DIR="${PRIVACYGUARD_DATA_DIR:-$HOME/.privacyguard}"
RUN_DIR="$STATE_DIR/run"
LOG_DIR="$STATE_DIR/logs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

[[ -x "$BACKEND/.venv-mac/bin/python" ]] || { echo "缺少 RedactionEverything 应用环境。" >&2; exit 1; }
[[ -x "$BACKEND/.venv-ocr-mac/bin/python" ]] || { echo "缺少 PaddleOCR 环境。" >&2; exit 1; }
[[ -f "$BACKEND/models/has/has_4.0_0.6B.gguf" ]] || { echo "缺少 HaS 模型。" >&2; exit 1; }
[[ -d "$BACKEND/models/paddlex-cache/official_models" ]] || { echo "缺少 PaddleOCR 模型。" >&2; exit 1; }

started=()
cleanup_failure() {
  local pid
  for pid in "${started[@]:-}"; do
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  done
}
trap cleanup_failure ERR

wait_url() {
  local name="$1" url="$2" attempts="$3"
  for ((i=0; i<attempts; i++)); do
    curl --noproxy '*' -fsS "$url" >/dev/null 2>&1 && return 0
    sleep 1
  done
  echo "$name 启动失败，请查看 $LOG_DIR。" >&2
  return 1
}

if ! curl --noproxy '*' -fsS http://127.0.0.1:8080/v1/models >/dev/null 2>&1; then
  nohup env HAS_MODEL_PATH="$BACKEND/models/has/has_4.0_0.6B.gguf" \
    HAS_TEXT_HOST=127.0.0.1 HAS_TEXT_PORT=8080 HAS_TEXT_N_CTX=4096 HAS_TEXT_N_GPU_LAYERS=-1 \
    "$BACKEND/.venv-mac/bin/python" "$BACKEND/scripts/start_has_python.py" \
    >>"$LOG_DIR/redaction-has.log" 2>&1 &
  started+=("$!"); echo "$!" >"$RUN_DIR/redaction-has.pid"
  wait_url "HaS" http://127.0.0.1:8080/v1/models 180
fi

if ! curl --noproxy '*' -fsS http://127.0.0.1:8082/health >/dev/null 2>&1; then
  nohup env OCR_DEVICE=cpu OCR_VL_ENABLED=0 OCR_STRUCTURE_ENABLED=1 OCR_STRUCTURE_WARMUP=0 \
    PADDLE_PDX_CACHE_HOME="$BACKEND/models/paddlex-cache" \
    PADDLE_PDX_MODEL_SOURCE=modelscope PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True OCR_PORT=8082 \
    "$BACKEND/.venv-ocr-mac/bin/python" "$BACKEND/scripts/ocr_server.py" \
    >>"$LOG_DIR/redaction-ocr.log" 2>&1 &
  started+=("$!"); echo "$!" >"$RUN_DIR/redaction-ocr.pid"
  wait_url "PaddleOCR" http://127.0.0.1:8082/health 240
fi

if ! curl --noproxy '*' -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  mkdir -p "$BACKEND/data" "$BACKEND/uploads" "$BACKEND/outputs"
  nohup env AUTH_ENABLED=false DEBUG=false \
    DATA_DIR="$BACKEND/data" UPLOAD_DIR="$BACKEND/uploads" OUTPUT_DIR="$BACKEND/outputs" \
    HAS_TEXT_RUNTIME=llamacpp HAS_LLAMACPP_BASE_URL=http://127.0.0.1:8080/v1 \
    HAS_NER_CONTEXT_TOKENS=4096 HAS_NER_MAX_TOKENS=1024 \
    OCR_BASE_URL=http://127.0.0.1:8082 OCR_REQUIRE_GPU=false \
    VISUAL_FEATURES_BASE_URL=http://127.0.0.1:8090 LOCATE_ANYTHING_DEVICE=cpu \
    "$BACKEND/.venv-mac/bin/python" -m uvicorn app.main:app \
    --app-dir "$BACKEND" --host 127.0.0.1 --port 8000 \
    >>"$LOG_DIR/redaction-api.log" 2>&1 &
  started+=("$!"); echo "$!" >"$RUN_DIR/redaction-api.pid"
  wait_url "RedactionEverything" http://127.0.0.1:8000/health 90
fi

trap - ERR
echo "RedactionEverything: http://127.0.0.1:8000"
