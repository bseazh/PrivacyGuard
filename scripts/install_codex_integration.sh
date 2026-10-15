#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SKILL_TARGET="$CODEX_HOME_DIR/skills/privacyguard"

command -v codex >/dev/null || { echo "未找到 Codex CLI。" >&2; exit 1; }
[[ -x "$ROOT_DIR/.venv/bin/privacyguard-mcp" ]] || { echo "请先运行 scripts/bootstrap_privacyguard.sh" >&2; exit 1; }
if codex mcp get privacyguard >/dev/null 2>&1; then
  echo "Codex 已存在名为 privacyguard 的 MCP 配置，未覆盖。" >&2
  exit 1
fi
if [[ -e "$SKILL_TARGET" ]]; then
  echo "$SKILL_TARGET 已存在，未覆盖。" >&2
  exit 1
fi

echo "即将修改 $CODEX_HOME_DIR：注册 PrivacyGuard MCP 并安装 privacyguard Skill。"
read -r -p "输入 INSTALL 继续：" answer
[[ "$answer" == "INSTALL" ]] || { echo "已取消。"; exit 0; }

codex mcp add privacyguard \
  --env "PRIVACYGUARD_ALLOWED_ROOTS=$HOME/Documents:$HOME/Desktop:$HOME/Downloads" \
  --env "PRIVACYGUARD_DATA_DIR=$HOME/.privacyguard" \
  --env "PRIVACYGUARD_REFERENCE_TTL=900" \
  --env "PRIVACYGUARD_PRESIDIO_URL=http://127.0.0.1:5002" \
  --env "PRIVACYGUARD_REDACTION_BASE_URL=http://127.0.0.1:8000" \
  -- "$ROOT_DIR/.venv/bin/privacyguard-mcp"
mkdir -p "$CODEX_HOME_DIR/skills"
cp -R "$ROOT_DIR/skills/privacyguard" "$SKILL_TARGET"
echo "Codex 集成安装完成。请完全退出并重新打开 Codex。"
