#!/usr/bin/env bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
source_dir="$repo/third_party/sage-binary"
out=${1:-"$repo/scripts/modal/.build/sage-source.tar.gz"}
test -f "$source_dir/VERSION.txt" || { echo 'Sage fork source is missing' >&2; exit 1; }
test -x "$source_dir/build/bin/sage-venv" || { echo 'Sage build helpers are missing' >&2; exit 1; }
mkdir -p "$(dirname "$out")"
tmp="$out.tmp"
trap 'rm -f "$tmp"' EXIT
# Ship source, including the currently uncommitted fork changes, but never the
# macOS build, credentials, Git history, or prior experiment output.
COPYFILE_DISABLE=1 tar -C "$source_dir" -czf "$tmp" --no-xattrs --no-acls \
  --exclude='./.git' --exclude='./build/sage-distro' --exclude='./build-deps' \
  --exclude='./build/platform/meson/sage-configure-native-file.ini' \
  --exclude='./local' --exclude='./venv' --exclude='./logs' \
  --exclude='./upstream' --exclude='./.sage' --exclude='./__pycache__' \
  --exclude='./config.status' --exclude='./config.log' \
  --exclude='./config.cache' --exclude='./autom4te.cache' .
mv "$tmp" "$out"
if command -v sha256sum >/dev/null 2>&1; then sha256sum "$out"; else shasum -a 256 "$out"; fi
