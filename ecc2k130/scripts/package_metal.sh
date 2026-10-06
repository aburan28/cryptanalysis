#!/usr/bin/env bash
# Build the unified CLI with the ECC2K-130 Metal table-walk backend on macOS.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${1:?usage: scripts/package_metal.sh VERSION [OUTDIR]}
OUT=${2:-dist}
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
    echo 'the Metal release package requires macOS arm64' >&2
    exit 1
fi

BUILD=build/release-metal
rm -rf "$BUILD"
make test BUILD="$BUILD"
make metal-test metal BUILD="$BUILD"
BIN="$BUILD/ec2k-metal"
"$BIN" check --rounds 96

CLI_BUILD=../build/release-cli-metal
cmake -S .. -B "$CLI_BUILD" -DCMAKE_BUILD_TYPE=Release \
    -DCA_BUILD_SHARED=OFF -DCA_BUILD_TESTS=OFF -DCA_WERROR=ON
cmake --build "$CLI_BUILD" --target cryptanalysis_cli -j "${BUILD_JOBS:-2}"
CLI="$CLI_BUILD/cryptanalysis"
"$CLI" bsgs --group zp --p 1000003 --order 166667 --g 533154 --h 579795 | grep -q '"x":12345'
"$CLI" rho --group zp --p 1000003 --order 166667 --g 533154 --h 579795 --seed 1 | grep -q '"x":12345'

NAME="cryptanalysis-$VERSION-macos-arm64"
STAGE="$OUT/$NAME"
rm -rf "$STAGE"
mkdir -p "$STAGE/bin" "$STAGE/libexec/cryptanalysis" "$STAGE/share/cryptanalysis"
cp "$CLI" "$STAGE/bin/cryptanalysis"
cp "$BIN" "$STAGE/libexec/cryptanalysis/ecc2k130-rho-metal"
cp README.md "$STAGE/share/cryptanalysis/ECC2K130-README.md"
cp ../LICENSE "$STAGE/LICENSE"
cat >"$STAGE/VERSION" <<EOF
cryptanalysis $VERSION, macos-arm64
source: $(git rev-parse HEAD 2>/dev/null || echo unknown)
ECC2K-130 Metal walk: table (separate from the live sigma campaign)
kernel: Metal Shading Language, compiled by the client at start-up
EOF
"$STAGE/bin/cryptanalysis" rho --curve ecc2k130 --backend metal --check --rounds 96
tar -C "$OUT" -czf "$OUT/$NAME.tar.gz" "$NAME"
(cd "$OUT" && shasum -a 256 "$NAME.tar.gz" >"$NAME.tar.gz.sha256")
rm -rf "$STAGE"
echo "$OUT/$NAME.tar.gz"
