#!/usr/bin/env bash
set -euo pipefail

VERSION="v0.1.5"
BASE_URL="${PRIVACYGUARD_DOWNLOAD_BASE:-https://privacyguard.snorlaxden.fun}/$VERSION"
TARGET_DIR="${PRIVACYGUARD_INSTALL_DIR:-$HOME/Documents/PrivacyGuard}"
CACHE_DIR="${PRIVACYGUARD_CACHE_DIR:-$HOME/Library/Caches/PrivacyGuardInstaller/$VERSION}"

fail() { echo "[失败] $*" >&2; exit 1; }
step() { echo; echo "==> $*"; }

[[ "$(uname -s)" == "Darwin" ]] || fail "当前一键安装仅支持 macOS Apple Silicon。"
[[ "$(uname -m)" == "arm64" ]] || fail "当前完整模式需要 M1/M2/M3/M4 系列 Apple Silicon Mac。"
command -v curl >/dev/null || fail "系统缺少 curl。"
command -v tar >/dev/null || fail "系统缺少 tar。"
command -v shasum >/dev/null || fail "系统缺少 shasum。"

memory_bytes="$(sysctl -n hw.memsize)"
(( memory_bytes >= 12 * 1024 * 1024 * 1024 )) || fail "内存低于 12GB，无法可靠运行完整本地模型链路。"
mkdir -p "$(dirname "$TARGET_DIR")" "$CACHE_DIR"
free_kb="$(df -Pk "$(dirname "$TARGET_DIR")" | awk 'NR==2 {print $4}')"
(( free_kb >= 12 * 1024 * 1024 )) || fail "安装分区至少需要 12GB 可用空间。"
if [[ -e "$TARGET_DIR" && -n "$(ls -A "$TARGET_DIR" 2>/dev/null)" ]]; then
  if [[ ! -f "$TARGET_DIR/.privacyguard-install-version" ]] || [[ "$(cat "$TARGET_DIR/.privacyguard-install-version")" != "$VERSION" ]]; then
    fail "目标目录已存在且不是本安装器创建的同版本目录：$TARGET_DIR。为避免覆盖，请先改名或设置 PRIVACYGUARD_INSTALL_DIR。"
  fi
  echo "检测到未完成的 $VERSION 安装，将复用目录和下载缓存继续。"
fi

PYTHON_BIN=""
for candidate in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 "$(command -v python3.11 2>/dev/null || true)"; do
  if [[ -n "$candidate" && -x "$candidate" ]]; then PYTHON_BIN="$candidate"; break; fi
done
if [[ -z "$PYTHON_BIN" ]]; then
  command -v brew >/dev/null || fail "缺少 Python 3.11 和 Homebrew。请先从 https://brew.sh 安装 Homebrew，再重新运行本命令。"
  step "安装 Python 3.11"
  brew install python@3.11
  PYTHON_BIN="$(brew --prefix python@3.11)/bin/python3.11"
fi

files=(
  "PrivacyGuard-$VERSION-source.tar.gz"
  "RedactionEverything-$VERSION-source.tar.gz"
  "Qwen3-1.7B-bf16-$VERSION.tar.gz"
  "RedactionEverything-HaS-0.6B-$VERSION.tar.gz"
  "RedactionEverything-PaddleOCR-$VERSION.tar.gz"
)

step "下载清单和组件（约 4GB，支持断点续传）"
curl -fL --retry 5 --retry-delay 2 "$BASE_URL/SHA256SUMS" -o "$CACHE_DIR/SHA256SUMS"
for name in "${files[@]}"; do
  curl -fL --retry 5 --retry-delay 2 -C - "$BASE_URL/$name" -o "$CACHE_DIR/$name"
done

step "强制校验 SHA-256"
(
  cd "$CACHE_DIR"
  for name in "${files[@]}"; do
    expected="$(awk -v file="$name" '$2 == file {print $1}' SHA256SUMS)"
    [[ -n "$expected" ]] || fail "SHA256SUMS 缺少 $name"
    actual="$(shasum -a 256 "$name" | awk '{print $1}')"
    [[ "$actual" == "$expected" ]] || fail "$name 校验失败；保留缓存供续传。"
    echo "[通过] $name"
  done
)

step "安装源码和独立模型组件"
stage="$(mktemp -d "${TMPDIR:-/tmp}/privacyguard-install.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
if [[ ! -f "$TARGET_DIR/.privacyguard-install-version" ]]; then
  tar -xzf "$CACHE_DIR/PrivacyGuard-$VERSION-source.tar.gz" -C "$stage"
  mv "$stage/PrivacyGuard-$VERSION" "$TARGET_DIR"
  printf '%s\n' "$VERSION" >"$TARGET_DIR/.privacyguard-install-version"
fi
[[ -d "$TARGET_DIR/redaction-everything/backend/app" ]] || tar -xzf "$CACHE_DIR/RedactionEverything-$VERSION-source.tar.gz" -C "$TARGET_DIR"
mkdir -p "$TARGET_DIR/models/qwen3"
[[ -f "$TARGET_DIR/models/qwen3/Qwen3-1.7B-bf16/model.safetensors" ]] || tar -xzf "$CACHE_DIR/Qwen3-1.7B-bf16-$VERSION.tar.gz" -C "$TARGET_DIR/models/qwen3"
[[ -f "$TARGET_DIR/redaction-everything/backend/models/has/has_4.0_0.6B.gguf" ]] || tar -xzf "$CACHE_DIR/RedactionEverything-HaS-0.6B-$VERSION.tar.gz" -C "$TARGET_DIR/redaction-everything"
[[ -d "$TARGET_DIR/redaction-everything/backend/models/paddlex-cache/official_models" ]] || tar -xzf "$CACHE_DIR/RedactionEverything-PaddleOCR-$VERSION.tar.gz" -C "$TARGET_DIR/redaction-everything"
chmod +x "$TARGET_DIR"/scripts/*.sh "$TARGET_DIR/install.sh"

pip_install() {
  local python="$1"; shift
  if ! "$python" -m pip install --disable-pip-version-check -i https://pypi.tuna.tsinghua.edu.cn/simple "$@"; then
    echo "国内 Python 镜像失败，切换官方 PyPI。"
    "$python" -m pip install --disable-pip-version-check -i https://pypi.org/simple "$@"
  fi
}

step "安装 PrivacyGuard、Presidio 和 LiteLLM"
"$PYTHON_BIN" -m venv "$TARGET_DIR/.venv"
pip_install "$TARGET_DIR/.venv/bin/python" --upgrade pip
pip_install "$TARGET_DIR/.venv/bin/python" -e "$TARGET_DIR[test,secure-llm]"

step "安装 MLX 本地模型服务"
"$PYTHON_BIN" -m venv "$TARGET_DIR/.venv-mlx"
pip_install "$TARGET_DIR/.venv-mlx/bin/python" --upgrade pip
pip_install "$TARGET_DIR/.venv-mlx/bin/python" "mlx-lm==0.32.0"

step "安装 RedactionEverything 与 PaddleOCR"
backend="$TARGET_DIR/redaction-everything/backend"
"$PYTHON_BIN" -m venv "$backend/.venv-mac"
"$PYTHON_BIN" -m venv "$backend/.venv-ocr-mac"
export CMAKE_ARGS="-DGGML_METAL=on"
pip_install "$backend/.venv-mac/bin/python" -r "$TARGET_DIR/redaction-everything/offline/requirements/macos-app.txt"
pip_install "$backend/.venv-ocr-mac/bin/python" -r "$TARGET_DIR/redaction-everything/offline/requirements/macos-ocr.txt"

step "启动本地服务"
"$TARGET_DIR/scripts/start_privacyguard.sh"

export PRIVACYGUARD_MLX_PYTHON="$TARGET_DIR/.venv-mlx/bin/python"
export PRIVACYGUARD_LLM_MODEL="openai/$TARGET_DIR/models/qwen3/Qwen3-1.7B-bf16"
export PRIVACYGUARD_LLM_BASE_URL="http://127.0.0.1:8011/v1"
export PRIVACYGUARD_LLM_API_KEY="local-only"

step "运行 MCP 与真实 LiteLLM 端到端验收"
cd "$TARGET_DIR"
"$TARGET_DIR/.venv/bin/python" tests/mcp_smoke.py
"$TARGET_DIR/.venv/bin/python" tests/secure_ask_live.py

if command -v codex >/dev/null 2>&1; then
  step "注册 Codex MCP 并安装 privacyguard Skill"
  if "$TARGET_DIR/scripts/install_codex_integration.sh" --yes; then
    echo "请完全退出并重新打开 Codex。"
  else
    echo "Codex 已有同名 MCP/Skill 或注册失败，未覆盖；核心链路验收仍已通过。" >&2
  fi
else
  echo "未检测到 Codex CLI；核心链路已安装，暂未注册 MCP/Skill。"
fi

echo
echo "安装和验收完成：$TARGET_DIR"
echo "以后启动：$TARGET_DIR/scripts/start_privacyguard.sh"
