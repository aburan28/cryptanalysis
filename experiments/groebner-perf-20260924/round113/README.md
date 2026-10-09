# Native continuation timing for verified F4 queries

This experiment adds observation-only clocks to the seeded continuation.
`preparation_ns` covers input scanning, row transfer, and engine construction;
`f4_ns` covers the unchanged F4 charges, compute, compaction, and counters;
`packing_ns` covers the continuation basis and proof copy;
`composition_ns` covers substitution of the matrix proof into the F4 proof;
`finalization_ns` covers output transfer, binding, and failure/status handling.
The five durations are exclusive and sum to `total_ns`. Every failed stage keeps
its attempted time. The original work, node, row, and checker budgets remain in
effect.

The instrumented library is generated from the frozen round110 source and
retains its `SeededStats` and proof ABI. The opt-in query uses the round112 early
matrix producer, original-equation certificate check, and curve replay. Each
measured result must match an independently audited uninstrumented result in
status, basis, work counters, proof bytes, and curve replay. This makes the
phase measurements useful for locating the next kernel change while avoiding
a second mathematical oracle in the timed interval.

The panel runs five 12-variable point-decomposition cases in optimized and
undefined-behavior-sanitized builds. Host timings are exploratory until the
repository's isolated-host receipt passes its preflight and noise gates.
For a local source-matched reference build, pass its repository path to
`build.py --reference-root` and set `GROEBNER_PHASE_REFERENCE_ROOT` to that
same path when running the panel. CI builds fresh references and leaves the
variable unset.

```sh
python3 experiments/groebner-perf-20260924/round113/build.py
python3 experiments/groebner-perf-20260924/round113/panel.py \
  --reference-report /absolute/validated/round112/panel/report.json \
  --output /absolute/new/phase-panel
```
