#!/usr/bin/env bash
# Attach a locally built and smoke-tested Sage accelerator overlay to a release.
set -euo pipefail
cd "$(dirname "$0")/.."

TAG=${1:?usage: scripts/publish_sage_binary.sh cryptanalysis-vVERSION [SAGE_CHECKOUT]}
case "$TAG" in
    cryptanalysis-v*) VERSION=${TAG#cryptanalysis-v} ;;
    *) echo 'expected a cryptanalysis-vVERSION tag' >&2; exit 1 ;;
esac
SAGE=${2:-third_party/sage-binary}
OUT=dist/sage-binary
python3 scripts/sage_release.py verify-installed --sage "$SAGE"
python3 scripts/sage_release.py smoke --sage "$SAGE"
python3 scripts/sage_release.py pack-binary --sage "$SAGE" --version "$VERSION" --out "$OUT"
shopt -s nullglob
ARCHIVES=("$OUT/cryptanalysis-sage-$VERSION-macos-arm64-py"*.tar.gz)
if [ "${#ARCHIVES[@]}" -ne 1 ]; then
    echo "expected one compiled Sage archive for $VERSION under $OUT" >&2
    exit 1
fi
ARCHIVE=${ARCHIVES[0]}
(cd "$OUT" && shasum -a 256 -c "$(basename "$ARCHIVE").sha256")
python3 scripts/sage_release.py install-binary --sage "$SAGE" --archive "$ARCHIVE"
gh release view "$TAG" --repo aburan28/cryptanalysis >/dev/null
gh release upload "$TAG" "$ARCHIVE" "$ARCHIVE.sha256" --repo aburan28/cryptanalysis
