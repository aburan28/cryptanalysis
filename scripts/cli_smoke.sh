#!/usr/bin/env bash
#
# Exercise every `ca` subcommand and check the answers that are known in
# closed form.
#
# The point is coverage, not speed: if a public header gains a function that no
# command reaches, this script is where that shows up. Every command in
# `ca`'s usage text must appear here, and the assertions are chosen so a wrong
# answer fails rather than merely a crash.
#
# Usage: scripts/cli_smoke.sh [path-to-ca]   (default: build/ca)
set -euo pipefail

CA=${1:-build/ca}
if [ ! -x "$CA" ]; then
  echo "no ca binary at $CA — build it first (cmake --build build --target ca)" >&2
  exit 2
fi

fail=0
checks=0

# Assert that running `ca $*` succeeds and its output contains a string. The
# expected string is the first argument.
want() {
  local expect=$1
  shift
  checks=$((checks + 1))
  local out
  if ! out=$("$CA" "$@" 2>&1); then
    printf 'FAIL (exit) %s\n  %s\n' "$*" "$out" >&2
    fail=$((fail + 1))
    return
  fi
  case $out in
  *"$expect"*) : ;;
  *)
    printf 'FAIL %s\n  wanted: %s\n  got:    %s\n' "$*" "$expect" "$out" >&2
    fail=$((fail + 1))
    ;;
  esac
}

# Assert that `ca $*` reports "no such object" — exit status 1 with the given
# string in its output. The CLI distinguishes three outcomes: 0 for an answer,
# 1 for a well-posed question whose answer is "there is none" (not invertible,
# not a square, not on the curve), and 2 for a malformed invocation.
want_no() {
  local expect=$1
  shift
  checks=$((checks + 1))
  local out rc=0
  out=$("$CA" "$@" 2>&1) || rc=$?
  if [ "$rc" -ne 1 ]; then
    printf 'FAIL (wanted exit 1, got %d) %s\n  %s\n' "$rc" "$*" "$out" >&2
    fail=$((fail + 1))
    return
  fi
  case $out in
  *"$expect"*) : ;;
  *)
    printf 'FAIL %s\n  wanted: %s\n  got:    %s\n' "$*" "$expect" "$out" >&2
    fail=$((fail + 1))
    ;;
  esac
}

# Assert that `ca $*` exits non-zero. Used for the refusals that matter.
want_fail() {
  checks=$((checks + 1))
  if "$CA" "$@" >/dev/null 2>&1; then
    printf 'FAIL (expected non-zero exit) %s\n' "$*" >&2
    fail=$((fail + 1))
  fi
}

# ── information ─────────────────────────────────────────────────────────────
want '"version"' version
want '"cuda_compiled"' gpu-info

# ── number theory (ca_modarith.h) ───────────────────────────────────────────
# 3^100 mod 1000003, cross-checked against Python: 189751.
want '"result":"189751"' num powmod --base 3 --exp 100 --mod 1000003
# 2 is invertible mod 1000003 and 2 * 500002 = 1000004 = 1 (mod 1000003).
want '"result":"500002"' num invmod --a 2 --mod 1000003
# 6 is not invertible mod 9: gcd is 3.
want_no '"invertible":false' num invmod --a 6 --mod 9
want '"result":"6"' num gcd --a 24 --b 42
want '"result":"1000","exact":true' num isqrt --n 1000000
want '"exact":false' num isqrt --n 1000001
want '"result":"100"' num iroot --n 1000000 --k 3
# 4 is a square mod 1000003; its roots are +/-2, and -2 = 1000001.
want '"square":true' num sqrtmod --a 4 --p 1000003
want '"result":-1' num legendre --a 5 --p 1000003
want '"result":1' num legendre --a 4 --p 1000003
# x = 2 mod 3, x = 3 mod 5  =>  x = 8 mod 15.
want '"result":"8","modulus":"15"' num crt --r1 2 --m1 3 --r2 3 --m2 5
want_fail num crt --r1 1 --m1 4 --r2 1 --m2 6   # moduli not coprime
want '"result":"1000003"' num next-prime --n 1000000
# 1000003 is prime, so a primitive root has order p-1.
want '"order":"1000002"' num primitive-root --p 1000003
# pi(1000) = 168, first prime 2, last 997.
want '"count":168' num sieve --bound 1000
want '"last":997' num sieve --bound 1000
# The Montgomery domain must agree with schoolbook arithmetic on every op.
want '"agree":true' num mont --p 1000003 --a 12345 --b 67890
want '"agree":true' num mont --p 2147483647 --a 123456789 --b 987654321
want_fail num mont --p 1000004                   # even modulus
want_fail num mont --p 1                          # below the Montgomery floor
want_fail num mont --p 0                          # would divide by zero
want_fail num powmod --base 3 --exp 4 --mod 1     # degenerate modulus
# m1 * m2 must not wrap: the result is reduced against it, so a wrapped modulus
# would be printed alongside an answer not taken modulo it.
want_fail num crt --r1 1 --m1 18446744073709551557 --r2 1 --m2 3
want_fail num sieve --bound 99999999999           # would be an absurd allocation
want_fail num nonsense

# ── factorisation and primality ─────────────────────────────────────────────
want '"is_prime":true' prime 1000003
want '"is_prime":false' prime 1000001
# 2^32 - 1 = 3 * 5 * 17 * 257 * 65537.
want '65537' factor 4294967295

# ── groups (ca_group.h) ─────────────────────────────────────────────────────
ZP=(--group zp --p 1000003 --order 1000002)
want '"order":"1000002"' group generator "${ZP[@]}"
# 2^100 mod 1000003 = 253109, so the group's scalar multiple must agree with
# `num powmod` — the same computation through two different abstractions.
want '"result":"253109"' group exp "${ZP[@]}" --elem 2 --k 100
want '"result":"253109"' num powmod --base 2 --exp 100 --mod 1000003
want '"result":"2"' group div "${ZP[@]}" --a 6 --b 3
want '"divides_group_order":true' group order "${ZP[@]}" --elem 2
want '"exponent"' group random "${ZP[@]}" --seed 7

EC=(--group ec --p 1000003 --a 2 --b 3)
want '"order":999708' ec-order --p 1000003 --a 2 --b 3
# x = 5 is not the x of a point of this curve; some x is, and the command must
# distinguish the two cases rather than guessing.
want_no '"on_curve":false' group lift-x "${EC[@]}" --x 5
lifted=0
for x in $(seq 1 40); do
  if "$CA" group lift-x "${EC[@]}" --x "$x" >/dev/null 2>&1; then
    want '"on_curve":true' group lift-x "${EC[@]}" --x "$x"
    lifted=1
    break
  fi
done
checks=$((checks + 1))
if [ "$lifted" -ne 1 ]; then
  echo 'FAIL no x in 1..40 lifted to a curve point' >&2
  fail=$((fail + 1))
fi
want_fail group lift-x "${ZP[@]}" --x 5           # lift-x is EC-only
want_fail group nonsense "${ZP[@]}"

# ── key generation and the solvers ──────────────────────────────────────────
want '"h"' gen "${ZP[@]}" --x 123456 --seed 1
for alg in bsgs rho kangaroo grumpy dlog; do
  # x = 123456 is planted; every algorithm must find exactly it.
  want '"x":123456' solve --alg "$alg" "${ZP[@]}" --g 858101 \
    --h "$("$CA" group exp "${ZP[@]}" --elem 858101 --k 123456 | sed 's/.*"\([0-9]*\)".*/\1/')" \
    --lo 0 --hi 1000002 --seed 1
done
want '"x":123456' solve --alg gpu-rho "${ZP[@]}" --g 858101 \
  --h "$("$CA" group exp "${ZP[@]}" --elem 858101 --k 123456 | sed 's/.*"\([0-9]*\)".*/\1/')" \
  --seed 1
want_fail solve --alg dlog --group zp --p 12x34    # malformed number

# Bernstein-Lange precomputation (ca_precomp.h).  The method needs a base that
# generates the whole group, so work in the prime-order subgroup (order 166667,
# where 1000002 = 2 * 3 * 166667): g^6 is such a base.  Plant x = 12345 and
# solve it online against the precomputed table.
PSUB=(--group zp --p 1000003 --order 166667)
PBASE=$("$CA" group exp "${ZP[@]}" --elem 858101 --k 6 | sed 's/.*"\([0-9]*\)".*/\1/')
PH=$("$CA" group exp "${PSUB[@]}" --elem "$PBASE" --k 12345 | sed 's/.*"\([0-9]*\)".*/\1/')
want '"precomp_ops"' solve --alg precomp "${PSUB[@]}" --g "$PBASE" --h "$PH" --seed 1
want '"x":12345' solve --alg precomp "${PSUB[@]}" --g "$PBASE" --h "$PH" --seed 1

# ── index calculus ──────────────────────────────────────────────────────────
want '"status":"ok"' ic --p 1099511627791 --g 3 --h 123456789 --threads 2

# ── Cheon's attack ──────────────────────────────────────────────────────────
# Cheon needs a *prime* group order, so work in the prime-order subgroup:
# 1000002 = 2 * 3 * 166667, and g^6 generates the subgroup of order 166667.
# Then d = 2 divides q - 1 = 166666 = 2 * 83333.
SUBG=$("$CA" group exp "${ZP[@]}" --elem 858101 --k 6 | sed 's/.*"\([0-9]*\)".*/\1/')
want '"status":"ok"' cheon --group zp --p 1000003 --order 166667 --g "$SUBG" --d 2 --alpha 4242

# ── the distributed protocol ────────────────────────────────────────────────
DIST=("${ZP[@]}" --g 858101 --campaign-seed 42)
H=$("$CA" group exp "${ZP[@]}" --elem 858101 --k 123456 | sed 's/.*"\([0-9]*\)".*/\1/')
want '"campaign_id"' dist-info "${DIST[@]}" --h "$H"
want_fail dist-info "${ZP[@]}" --g 858101 --h "$H"   # campaign seed is required

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for unit in 1 2 3 4; do
  "$CA" dist-walk "${DIST[@]}" --h "$H" --unit "$unit" --steps 400000 \
    --out "$tmp/u$unit.bin" >/dev/null
done
want '"x":123456' dist-merge "${DIST[@]}" --h "$H" "$tmp"/u*.bin

# ── usage and unknown commands ──────────────────────────────────────────────
want_fail
want_fail not-a-command

printf '%d checks, %d failures\n' "$checks" "$fail"
[ "$fail" -eq 0 ]
