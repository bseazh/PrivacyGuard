#!/bin/zsh
set -u

TARGET_DIR="${1:-$HOME/Documents/PrivacyGuard/v0.1.4}"
SPEED_MBPS="${2:-0}"
FAILURES=0
WARNINGS=0
DOWNLOAD_GIB="1.65"
WHEEL_COUNT="166"
INSTALLATION_GATE="${PRIVACYGUARD_INSTALL_GATE:-0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_DIR="${PRIVACYGUARD_PACKAGE_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

ok() { print "[OK] $1"; }
warn() { WARNINGS=$((WARNINGS + 1)); print "[WARN] $1"; }
fail() { FAILURES=$((FAILURES + 1)); print "[FAIL] $1"; }
has_command() { command -v "$1" >/dev/null 2>&1; }

print "PrivacyGuard standard offline preflight (macOS)"
print "Target: $TARGET_DIR"
print "------------------------------------------------"

[[ "$(uname -s)" == "Darwin" ]] || fail "This package requires macOS."
[[ "$(uname -m)" == "arm64" ]] && ok "Architecture: Apple Silicon arm64" || fail "The v0.1.4 macOS package does not support Intel Macs."

MAC_VERSION="$(sw_vers -productVersion 2>/dev/null || print 0)"
MAC_MAJOR="${MAC_VERSION%%.*}"
if [[ "$MAC_MAJOR" == <-> ]] && (( MAC_MAJOR >= 14 )); then
  ok "macOS: $MAC_VERSION"
else
  fail "macOS 14 or newer is required by the bundled arm64 wheels; found $MAC_VERSION."
fi

RAM_BYTES="$(sysctl -n hw.memsize 2>/dev/null || print 0)"
RAM_GB=$((RAM_BYTES / 1024 / 1024 / 1024))
if (( RAM_GB >= 16 )); then ok "Memory: ${RAM_GB} GB"; elif (( RAM_GB >= 8 )); then warn "Memory: ${RAM_GB} GB; 16 GB is recommended and OCR may be slow."; else fail "Memory: ${RAM_GB} GB; at least 8 GB is required."; fi

DISK_PROBE="$TARGET_DIR"
while [[ ! -e "$DISK_PROBE" && "$DISK_PROBE" != "/" ]]; do
  DISK_PROBE="$(dirname "$DISK_PROBE")"
done
FREE_KB="$(df -Pk "$DISK_PROBE" | awk 'END {print $4}')"
FREE_GB=$((FREE_KB / 1024 / 1024))
if (( FREE_GB >= 15 )); then ok "Free disk for $TARGET_DIR: ${FREE_GB} GB"; elif (( FREE_GB >= 10 )); then warn "Free disk for $TARGET_DIR: ${FREE_GB} GB; 15 GB is recommended."; else fail "Free disk for $TARGET_DIR: ${FREE_GB} GB; at least 10 GB is required."; fi

for cmd in curl tar shasum; do
  has_command "$cmd" && ok "$cmd is available" || fail "$cmd is missing from the system."
done

if has_command python3.11; then
  ok "Python 3.11 is already installed; the bundled installer is not needed."
else
  warn "Python 3.11 is not installed; use app/prerequisites/python-3.11.9-macos11.pkg after extracting the runtime package."
fi

for port in 8000 8080 8082; do
  owner="$(lsof -nP -iTCP:$port -sTCP:LISTEN 2>/dev/null | awk 'NR==2 {print $1" (PID "$2")"}')"
  [[ -n "$owner" ]] && warn "Port $port is already in use by $owner." || ok "Port $port is available"
done

if [[ "$INSTALLATION_GATE" == "1" ]]; then
  print "------------------------------------------------"
  print "Installation gate: package integrity and write access"
  VERSION_FILE="$SCRIPT_DIR/OFFLINE_VERSION"
  if [[ ! -f "$VERSION_FILE" ]]; then
    fail "Missing OFFLINE_VERSION in $SCRIPT_DIR"
  else
    VERSION="$(<"$VERSION_FILE")"
    MANIFEST="$PACKAGE_DIR/SHA256SUMS"
    if [[ ! -f "$MANIFEST" ]]; then
      fail "Missing SHA256SUMS in $PACKAGE_DIR"
    else
      for name in \
        "PrivacyGuard-standard-macos-arm64-runtime-$VERSION.tar.gz" \
        "PrivacyGuard-standard-model-has-$VERSION.tar.gz" \
        "PrivacyGuard-standard-model-paddleocr-$VERSION.tar.gz"
      do
        file="$PACKAGE_DIR/$name"
        if [[ ! -f "$file" ]]; then fail "Missing package: $name"; continue; fi
        expected="$(awk -v name="$name" '$2 == name {print $1}' "$MANIFEST")"
        if [[ -z "$expected" ]]; then fail "SHA256SUMS has no entry for $name"; continue; fi
        actual="$(shasum -a 256 "$file" | awk '{print $1}')"
        [[ "$actual" == "$expected" ]] && ok "SHA-256: $name" || fail "SHA-256 mismatch: $name"
      done
    fi
  fi
  mkdir -p "$TARGET_DIR" 2>/dev/null || true
  probe="$TARGET_DIR/.privacyguard-write-test-$$.tmp"
  if print ok > "$probe" 2>/dev/null; then
    /bin/rm -f "$probe"
    ok "Installation directory is writable: $TARGET_DIR"
  else
    fail "Installation directory is not writable: $TARGET_DIR"
  fi
fi

print "------------------------------------------------"
print "Installation plan"
print "Files to download: 4 (macOS runtime, HaS model, PaddleOCR model, SHA256SUMS)"
print "Download size: about ${DOWNLOAD_GIB} GiB; bundled Python wheels: $WHEEL_COUNT"
if [[ "$SPEED_MBPS" == <-> || "$SPEED_MBPS" == <->.<-> ]] && (( ${SPEED_MBPS%.*} > 0 )); then
  DOWNLOAD_MINUTES="$(awk -v gib="$DOWNLOAD_GIB" -v mbps="$SPEED_MBPS" 'BEGIN {print int((gib*8192/mbps/60*1.2)+0.999)}')"
  print "Estimated download at $SPEED_MBPS Mbps: about $DOWNLOAD_MINUTES minutes (includes 20% overhead)"
else
  print "Estimated download: 10 Mbps 27-35 min; 50 Mbps 6-10 min; 100 Mbps 3-6 min"
  print "Pass the measured Mbps as argument 2 for a machine-specific estimate."
fi
if (( RAM_GB >= 16 )); then
  print "Estimated install + first startup: 10-25 minutes"
else
  print "Estimated install + first startup: 20-45 minutes; avoid other memory-heavy apps"
fi
print "Expected disk after extraction: about 8-10 GB; keep 15 GB free for logs and documents."

print "------------------------------------------------"
print "Bundled: frontend, Python wheels, Python 3.11 installer, llama.cpp, HaS and PaddleOCR model packages."
print "Not required: Node.js, npm, Git, Homebrew, WSL, Docker, CUDA."
print "Result: $FAILURES failure(s), $WARNINGS warning(s)"
(( FAILURES == 0 )) || exit 2
