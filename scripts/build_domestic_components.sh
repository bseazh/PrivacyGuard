#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${1:-v0.1.5}"
REDACTION_SOURCE="${REDACTION_SOURCE:-$ROOT_DIR/../000-Assets/DataInfra-RedactionEverything-main}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/dist/domestic/$VERSION}"
QWEN_DIR="$ROOT_DIR/models/qwen3/Qwen3-1.7B-bf16"
HAS_ARCHIVE="$REDACTION_SOURCE/dist/offline/v0.1.1/PrivacyGuard-standard-model-has-v0.1.1.tar.gz"
OCR_ARCHIVE="$REDACTION_SOURCE/dist/offline/v0.1.1/PrivacyGuard-standard-model-paddleocr-v0.1.1.tar.gz"

[[ -d "$REDACTION_SOURCE/backend/app" ]] || { echo "缺少 RedactionEverything 源码。" >&2; exit 1; }
[[ -d "$QWEN_DIR" ]] || { echo "缺少 Qwen3 模型。" >&2; exit 1; }
[[ -f "$HAS_ARCHIVE" && -f "$OCR_ARCHIVE" ]] || { echo "缺少 HaS 或 PaddleOCR 组件。" >&2; exit 1; }
mkdir -p "$OUTPUT_DIR"
work="$(mktemp -d "${TMPDIR:-/tmp}/privacyguard-components.XXXXXX")"
trap 'rm -rf "$work"' EXIT

git -C "$ROOT_DIR" archive --format=tar --prefix="PrivacyGuard-$VERSION/" HEAD | tar -xf - -C "$work"
for directory in privacyguard service tests skills scripts config; do
  rsync -a --exclude '__pycache__' "$ROOT_DIR/$directory/" "$work/PrivacyGuard-$VERSION/$directory/"
done
cp "$ROOT_DIR/install.sh" "$work/PrivacyGuard-$VERSION/install.sh"
cp "$ROOT_DIR/README.md" "$ROOT_DIR/INSTALL.md" "$ROOT_DIR/AGENT_INSTALL.md" "$ROOT_DIR/FAQ.md" "$work/PrivacyGuard-$VERSION/"
tar -C "$work" -czf "$OUTPUT_DIR/PrivacyGuard-$VERSION-source.tar.gz" "PrivacyGuard-$VERSION"

mkdir -p "$work/redaction-everything/backend"
rsync -a --exclude '.venv*' --exclude models --exclude data --exclude uploads --exclude outputs \
  --exclude tests --exclude '__pycache__' "$REDACTION_SOURCE/backend/" "$work/redaction-everything/backend/"
mkdir -p "$work/redaction-everything/offline/requirements"
cp "$REDACTION_SOURCE/offline/requirements/macos-app.txt" "$work/redaction-everything/offline/requirements/"
cp "$REDACTION_SOURCE/offline/requirements/macos-ocr.txt" "$work/redaction-everything/offline/requirements/"
cp "$REDACTION_SOURCE/LICENSE" "$work/redaction-everything/"
tar -C "$work" -czf "$OUTPUT_DIR/RedactionEverything-$VERSION-source.tar.gz" redaction-everything

tar -C "$ROOT_DIR/models/qwen3" -czf "$OUTPUT_DIR/Qwen3-1.7B-bf16-$VERSION.tar.gz" Qwen3-1.7B-bf16
cp "$HAS_ARCHIVE" "$OUTPUT_DIR/RedactionEverything-HaS-0.6B-$VERSION.tar.gz"
cp "$OCR_ARCHIVE" "$OUTPUT_DIR/RedactionEverything-PaddleOCR-$VERSION.tar.gz"

(cd "$OUTPUT_DIR" && shasum -a 256 \
  "PrivacyGuard-$VERSION-source.tar.gz" \
  "RedactionEverything-$VERSION-source.tar.gz" \
  "Qwen3-1.7B-bf16-$VERSION.tar.gz" \
  "RedactionEverything-HaS-0.6B-$VERSION.tar.gz" \
  "RedactionEverything-PaddleOCR-$VERSION.tar.gz" > SHA256SUMS)
echo "组件已生成：$OUTPUT_DIR"
