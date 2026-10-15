#!/usr/bin/env bash
set -euo pipefail

STATE_DIR="${PRIVACYGUARD_DATA_DIR:-$HOME/.privacyguard}"
PID_FILE="$STATE_DIR/run/presidio.pid"
[[ -f "$PID_FILE" ]] || { echo "PrivacyGuard Presidio 未由本脚本启动。"; exit 0; }
PID="$(tr -cd '0-9' < "$PID_FILE")"
if [[ -z "$PID" ]] || ! kill -0 "$PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "记录中的进程已不存在，已清理过期 PID。"
  exit 0
elif ps -p "$PID" -o command= 2>/dev/null | grep -q 'privacyguard-presidio'; then
  kill "$PID"
  echo "Presidio 已停止。"
else
  echo "PID 身份不匹配，未结束任何进程。" >&2
  exit 1
fi
rm -f "$PID_FILE"

MLX_PID_FILE="$STATE_DIR/run/mlx-llm.pid"
if command -v launchctl >/dev/null 2>&1 && launchctl list com.privacyguard.mlx-llm >/dev/null 2>&1; then
  launchctl remove com.privacyguard.mlx-llm
  rm -f "$MLX_PID_FILE"
  echo "本机 MLX LiteLLM 上游已停止。"
  exit 0
fi
if [[ -f "$MLX_PID_FILE" ]]; then
  MLX_PID="$(tr -cd '0-9' < "$MLX_PID_FILE")"
  if [[ -n "$MLX_PID" ]] && kill -0 "$MLX_PID" 2>/dev/null; then
    if ps -p "$MLX_PID" -o command= 2>/dev/null | grep -Eq 'mlx_lm(\.server)? .*127\.0\.0\.1.*8011'; then
      kill "$MLX_PID"
      echo "本机 MLX LiteLLM 上游已停止。"
      rm -f "$MLX_PID_FILE"
    else
      echo "MLX PID 身份不匹配，未结束任何进程。" >&2
      exit 1
    fi
  else
    rm -f "$MLX_PID_FILE"
  fi
fi
