#!/usr/bin/env bash
set -euo pipefail

source_dir=/opt/sage-binary
stage=${1:?expected Sage build stage}
if [ "$stage" = prepare ]; then
  mkdir -p "$source_dir"
  echo 'Extracting Sage source archive'
  tar -xzf /opt/modal/sage-source.tar.gz -C "$source_dir"
  echo 'Sage source extracted'
  cd "$source_dir"
  test -x ./configure
  test -x build/bin/sage-venv
  test -f src/sage/schemes/elliptic_curves/binary_batch_ntl.pyx
  ./configure --enable-build-as-root --disable-editable --with-python=/usr/bin/python3
  exit 0
fi

cd "$source_dir"
test -f build/make/Makefile
case "$stage" in
  flint|gf2x|highs) target=$stage ;;
  local) target=build-local ;;
  venv) target=build-venv ;;
  verify)
    test -x venv/bin/python3
    ./sage -python - <<'PY'
from sage.all import GF, EllipticCurve
from sage.schemes.elliptic_curves import binary_batch
from sage.schemes.elliptic_curves import binary_batch_ntl
F = GF(2**31, 'z', impl='ntl')
E = EllipticCurve(F, [1, 1, 0, 0, 1])
P = next(E.lift_x(F.from_integer(i), all=True)[0]
         for i in range(2, 100) if E.lift_x(F.from_integer(i), all=True))
assert binary_batch.add_pairs(E, [(P, P)])[0] == 2*P
assert binary_batch_ntl is not None
PY
    exit 0 ;;
  *) echo "unknown Sage build stage: $stage" >&2; exit 2 ;;
esac
# Cache each bounded build step as a separate Modal image layer. A preempted
# builder then loses only the current step, not the full Sage installation.
make -j"${SAGE_BUILD_JOBS:-4}" "$target"
