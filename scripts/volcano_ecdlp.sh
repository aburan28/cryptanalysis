#!/usr/bin/env bash
# volcano_ecdlp.sh - ECDLP across a curve's isogeny volcano, solved by `ca`.
#
#   scripts/volcano_ecdlp.sh --curve P,A,B [--order N] [options]
#
# Builds `ca` (build/ca) and hands it to `volcano-rho` from aburan28/crypto,
# which counts points (unless --order is given), draws a seeded random
# generator and secret k, walks the ell-isogeny volcano of
# y^2 = x^3 + Ax + B over F_P with verified Vélu maps, carries the same
# (P, kP) to every curve, and runs `ca solve --alg rho` --trials times on
# each. Prints min / mean / max per curve and per volcano level, and writes
# results.json, trials.csv, instances.jsonl (each curve's instance, ready
# for `ca solve`) and the standard volcano graphs to --out.
#
# The crypto checkout is $CRYPTO_DIR, else ../crypto next to this
# repository. Options are volcano-rho's (`--help` lists them): --ell 2|3,
# --seed S, --trials T, --per-level L, --controls C, --out DIR, and
# --ca-arg ARG to pass options to `ca solve` (e.g. --ca-arg --no-negation).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
crypto="${CRYPTO_DIR:-$root/../crypto}"
case "${1:-}" in
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
esac
if [[ ! -x "$crypto/scripts/volcano_ecdlp.sh" ]]; then
    echo "volcano_ecdlp.sh: no aburan28/crypto checkout at $crypto; set CRYPTO_DIR" >&2
    exit 2
fi

cmake -S "$root" -B "$root/build" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$root/build" --target ca -j >/dev/null
exec "$crypto/scripts/volcano_ecdlp.sh" --ca "$root/build/ca" "$@"
