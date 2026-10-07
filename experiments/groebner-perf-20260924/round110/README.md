# Native seeded completion

This experiment ports round109's seed transfer and proof substitution into C++.
It borrows the matrix's binary proof view and the original packed coefficients,
constructs F4 input rows directly, and returns an owned original-input proof.
The existing independent checker still decides whether the candidate is valid.

The F4 engine and its compaction remain byte-identical to the reference. The
native bridge preserves round109's abstract materialization, packing, F4 decode
and composition charges even when physical Python operations disappear. An
additional nonnegative `scan_work` counter charges raw packed-input decoding and
canonicalization, including zero coefficients. All charges share the same total
budget. This conservative accounting prevents a native success from coming from
a looser limit. These counters are declared work units, not processor instructions.

Debug capture retains the continuation proof for exact comparison. Normal calls
move the final basis storage and release the intermediate graph. All returned
data are handle-owned; borrowed input and seed views only need to survive the
call. No target answers or target-dependent proof values are cached.

Source and workload must be frozen before numerical runs. Use `build.py` for a
fresh source-bound reference/native build, then run `python -m unittest discover
-s experiments/groebner-perf-20260924/round110 -v`. Local numerical jobs must take
the repository's shared heavy lock. Qualified timing ratios remain null without
an auditable CPU isolation receipt. No new GPU or asymptotic F6 claim is made.
