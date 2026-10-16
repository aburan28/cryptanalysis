#!/usr/bin/env bash
# Self-test of the Lean proof gate: every fixture under pass/ must pass and
# every fixture under fail/ must fail. Runs in CI on every gate trigger, so the
# gate is exercised even in a repository with no Lean proofs yet.
set -uo pipefail
here=$(cd "$(dirname "$0")" && pwd)
root=$(git -C "$here" rev-parse --show-toplevel)
gate="$root/tools/lean/proof-gate.sh"
rel=${here#"$root"/}
bad=0
for f in "$here"/pass/*.lean "$here"/fail/*.lean; do
  want=pass; case "$f" in */fail/*) want=fail ;; esac
  LEAN_GATE_TRUSTED="$here/trusted-native.txt" "$gate" "$rel/$want/$(basename "$f")" > /tmp/lean-selftest.$$ 2>&1
  rc=$?
  got=pass; [ $rc -eq 1 ] && got=fail; [ $rc -ne 0 ] && [ $rc -ne 1 ] && got="error($rc)"
  if [ "$got" = "$want" ]; then echo "ok    $want  $(head -1 /tmp/lean-selftest.$$)"
  else echo "WRONG expected $want, got $got: $(basename "$f")"; cat /tmp/lean-selftest.$$; bad=1; fi
done
rm -f /tmp/lean-selftest.$$
[ $bad -eq 0 ] && echo "gate self-test passed" || echo "gate self-test FAILED"
exit $bad
