#!/usr/bin/env bash
# Self-test of the Lean proof gate: every fixture under pass/ must pass and
# every fixture under fail/ must fail, and the gate's output must match the
# fixture's first line, `-- expect: <ERE>`. Checking the reason matters: a
# broken audit makes every fail/ fixture fail too, for the wrong reason. Runs in CI on every gate trigger, so the
# gate is exercised even in a repository with no Lean proofs yet.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
gate="$here/../proof-gate.sh"
cd "$root" || exit 3
rel=${here#"$root"/}
bad=0
for f in "$here"/pass/*.lean "$here"/fail/*.lean; do
  want=pass; case "$f" in */fail/*) want=fail ;; esac
  LEAN_GATE_TRUSTED="$here/trusted-native.txt" "$gate" "$rel/$want/$(basename "$f")" > /tmp/lean-selftest.$$ 2>&1
  rc=$?
  got=pass; [ $rc -eq 1 ] && got=fail; [ $rc -ne 0 ] && [ $rc -ne 1 ] && got="error($rc)"
  expect=$(sed -n '1s/^-- expect: //p' "$f")
  if [ -z "$expect" ]; then echo "WRONG no '-- expect:' line: $(basename "$f")"; bad=1; continue; fi
  if [ "$got" = "$want" ] && grep -qE -- "$expect" /tmp/lean-selftest.$$; then
    echo "ok    $want  $(head -1 /tmp/lean-selftest.$$)"
  else
    echo "WRONG expected $want matching /$expect/, got $got: $(basename "$f")"; cat /tmp/lean-selftest.$$; bad=1
  fi
done
rm -f /tmp/lean-selftest.$$
[ $bad -eq 0 ] && echo "gate self-test passed" || echo "gate self-test FAILED"
exit $bad
