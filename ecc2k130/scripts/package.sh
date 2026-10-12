#!/usr/bin/env bash
# package.sh - build the unified CLI and its ECC2K-130 CUDA rho backend.
#
#   scripts/package.sh VERSION [OUTDIR]        (from ecc2k130/, OUTDIR default dist)
#
# Produces cryptanalysis-VERSION-linux-ARCH.tar.gz and, temporarily, the
# legacy ec2k-gpu-VERSION-linux-ARCH.tar.gz. Both have .sha256 files. The
# private backend holds the campaign build (WALK=sigma) compiled for every GPU
# generation with a carry-less multiplier, plus PTX for later ones; the
# known-answer file its `check --kat` replays; the README and the licence.
#
# Before packing, the binary it built checks itself: `ec2k-gpu check --kat`
# needs no GPU, so a release never ships a binary whose host arithmetic or
# campaign known answers fail.  It also refuses a binary that would load a
# shared CUDA runtime, which a downloader's machine need not have.
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=${1:?usage: scripts/package.sh VERSION [OUTDIR]}
OUT=${2:-dist}
case "$(uname -m)" in
    x86_64) MACHINE=x86_64 ;;
    aarch64 | arm64) MACHINE=aarch64 ;;
    *) echo "unsupported machine $(uname -m)" >&2; exit 1 ;;
esac

# Ampere, Ada, Hopper, Blackwell datacentre and Blackwell workstation/consumer
# as machine code, and compute_120 as PTX so that a newer part's driver can
# compile it.  clmad exists from sm_80, so nothing older can run the kernel.
ARCH="-gencode arch=compute_80,code=sm_80 -gencode arch=compute_86,code=sm_86 \
-gencode arch=compute_89,code=sm_89 -gencode arch=compute_90,code=sm_90 \
-gencode arch=compute_100,code=sm_100 -gencode arch=compute_120,code=sm_120 \
-gencode arch=compute_120,code=compute_120"

if [ -z "${NVCC:-}" ]; then
    NVCC="$(scripts/fetch_cuda.sh)/bin/nvcc"
fi
BUILD=build/release
rm -rf "$BUILD"
make test BUILD="$BUILD"
make gpu WALK=sigma BUILD="$BUILD" NVCC="$NVCC" ARCH="$ARCH"
BIN="$BUILD/ec2k-gpu"

"$BIN" check --kat tests/campaign-kat.hex
if ldd "$BIN" | grep -q libcudart; then
    echo "$BIN links a shared CUDA runtime; the release needs it static" >&2
    exit 1
fi

# The public command uses the generic C solvers and dispatches this curve's
# rho walk to the private, curve-specific CUDA backend in the same archive.
CLI_BUILD=../build/release-cli
cmake -S .. -B "$CLI_BUILD" -DCMAKE_BUILD_TYPE=Release \
    -DCA_BUILD_SHARED=OFF -DCA_BUILD_TESTS=OFF -DCA_WERROR=ON
cmake --build "$CLI_BUILD" --target cryptanalysis_cli -j "${BUILD_JOBS:-2}"
CLI="$CLI_BUILD/cryptanalysis"
"$CLI" bsgs --group zp --p 1000003 --order 166667 --g 533154 --h 579795 | grep -q '"x":12345'
"$CLI" rho --group zp --p 1000003 --order 166667 --g 533154 --h 579795 --seed 1 | grep -q '"x":12345'

CANONICAL="cryptanalysis-$VERSION-linux-$MACHINE"
CANONICAL_STAGE="$OUT/$CANONICAL"
rm -rf "$CANONICAL_STAGE"
mkdir -p "$CANONICAL_STAGE/bin" "$CANONICAL_STAGE/libexec/cryptanalysis" \
    "$CANONICAL_STAGE/share/cryptanalysis"
cp "$CLI" "$CANONICAL_STAGE/bin/cryptanalysis"
cp "$BIN" "$CANONICAL_STAGE/libexec/cryptanalysis/ecc2k130-rho-cuda"
cp tests/campaign-kat.hex "$CANONICAL_STAGE/share/cryptanalysis/"
cp README.md "$CANONICAL_STAGE/share/cryptanalysis/ECC2K130-README.md"
cp ../LICENSE "$CANONICAL_STAGE/LICENSE"
cat >"$CANONICAL_STAGE/VERSION" <<EOF
cryptanalysis $VERSION, linux-$MACHINE
source: $(git rev-parse HEAD 2>/dev/null || echo unknown)
ECC2K-130 walk: sigma
nvcc: $("$NVCC" --version | tail -1)
arch: sm_80 sm_86 sm_89 sm_90 sm_100 sm_120, compute_120 PTX
EOF
"$CANONICAL_STAGE/bin/cryptanalysis" rho --curve ecc2k130 --check \
    --kat "$CANONICAL_STAGE/share/cryptanalysis/campaign-kat.hex"
tar -C "$OUT" -czf "$OUT/$CANONICAL.tar.gz" "$CANONICAL"
(cd "$OUT" && sha256sum "$CANONICAL.tar.gz" >"$CANONICAL.tar.gz.sha256")
rm -rf "$CANONICAL_STAGE"

NAME="ec2k-gpu-$VERSION-linux-$MACHINE"
STAGE="$OUT/$NAME"
rm -rf "$STAGE"
mkdir -p "$STAGE"
cp "$BIN" tests/campaign-kat.hex README.md "$STAGE/"
cp ../LICENSE "$STAGE/"
cat >"$STAGE/VERSION" <<EOF
ec2k-gpu $VERSION, linux-$MACHINE, walk sigma (the ecc2k-130 campaign's)
source: $(git rev-parse HEAD 2>/dev/null || echo unknown)
nvcc: $("$NVCC" --version | tail -1)
arch: sm_80 sm_86 sm_89 sm_90 sm_100 sm_120, compute_120 PTX
EOF
tar -C "$OUT" -czf "$OUT/$NAME.tar.gz" "$NAME"
(cd "$OUT" && sha256sum "$NAME.tar.gz" >"$NAME.tar.gz.sha256")
rm -rf "$STAGE"
echo "$OUT/$NAME.tar.gz"
echo "$OUT/$CANONICAL.tar.gz"
