#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT_DIR/.venv"
STATE_DIR="${PRIVACYGUARD_DATA_DIR:-$HOME/.privacyguard}"
mkdir -p "$STATE_DIR/logs" "$STATE_DIR/run"

if [[ ! -x "$VENV/bin/privacyguard-presidio" ]]; then
  echo "缺少 PrivacyGuard 环境，请先运行 scripts/bootstrap_privacyguard.sh" >&2
  exit 1
fi

if curl -fsS http://127.0.0.1:5002/health >/dev/null 2>&1; then
  if [[ -f "$STATE_DIR/run/presidio.pid" ]] && ! kill -0 "$(tr -cd '0-9' < "$STATE_DIR/run/presidio.pid")" 2>/dev/null; then
    rm -f "$STATE_DIR/run/presidio.pid"
  fi
  echo "Presidio 已在运行。"
else
  nohup "$VENV/bin/privacyguard-presidio" >>"$STATE_DIR/logs/presidio.log" 2>&1 &
  echo $! >"$STATE_DIR/run/presidio.pid"
  for _ in {1..30}; do
    curl -fsS http://127.0.0.1:5002/health >/dev/null 2>&1 && break
    sleep 0.2
  done
  curl -fsS http://127.0.0.1:5002/health >/dev/null
fi
echo "PrivacyGuard MCP 可由 Codex 按配置自动启动；Presidio: http://127.0.0.1:5002"

if [[ -x "$ROOT_DIR/.venv-mlx/bin/python" && -d "$ROOT_DIR/models/qwen3/Qwen3-1.7B-bf16" ]]; then
  if ! curl --noproxy '*' -fsS http://127.0.0.1:8011/v1/models >/dev/null 2>&1; then
    nohup "$ROOT_DIR/.venv-mlx/bin/python" -m mlx_lm server \
      --model "$ROOT_DIR/models/qwen3/Qwen3-1.7B-bf16" \
      --host 127.0.0.1 --port 8011 \
      --chat-template-args '{"enable_thinking":false}' \
      --log-level WARNING >>"$STATE_DIR/logs/mlx-llm.log" 2>&1 &
    echo $! >"$STATE_DIR/run/mlx-llm.pid"
    for _ in {1..120}; do
      curl --noproxy '*' -fsS http://127.0.0.1:8011/v1/models >/dev/null 2>&1 && break
      sleep 0.5
    done
    curl --noproxy '*' -fsS http://127.0.0.1:8011/v1/models >/dev/null || {
      echo "MLX LiteLLM 上游启动失败；查看 $STATE_DIR/logs/mlx-llm.log" >&2
      exit 1
    }
  fi
  echo "本机 MLX LiteLLM 上游: http://127.0.0.1:8011/v1"
fi
