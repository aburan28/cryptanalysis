# F4 inner phase profile on certified point-decomposition queries

Round113 places 96.72–98.14% of native continuation time inside F4 on the
five fixed 12-variable point-decomposition queries. This experiment adds
observation-only clocks inside the unchanged F4 engine to distinguish input
normalization, S-pair creation, symbolic Macaulay construction, column
ranking and elimination, packed word elimination, candidate reduction,
final interreduction, and proof compaction.

`compute_ns` contains the exclusive initial, pair, matrix, candidate, and final
intervals, plus clock and loop overhead. `matrix_ns` contains `symbolic_ns`
and `column_ns`. `column_ns` contains `packed_ns`; the remainder covers column
ranking and conversion or the sparse fallback. `f4_ns` also includes the
seeded producer's existing logical decode charges and counter export. Every
completed worker checks these nesting relations. The clocks do not alter row
order, work charges, proof operations, or resource limits.
The parallel `*_work` counters partition the engine's deterministic logical
work charges across the same phases; a repeated panel requires these counts
to agree exactly across runs. They remain useful when host preemption distorts
wall-clock phase shares.

The opt-in library is built from the exact round108 generated engine SHA-256
and the frozen round110/113 native phase source. Both optimized and undefined
behavior sanitizer builds retain source, binary, compiler, and architecture
receipts. The panel compares each answer with the audited round112 result,
including proof bytes, work counters, original-equation replay, and curve
replay. Host timing is diagnostic until the isolated benchmark receipt passes.

```sh
python3 experiments/groebner-perf-20260924/round115/build.py \
  --reference-root /absolute/source-matched/reference
GROEBNER_F4_REFERENCE_ROOT=/absolute/source-matched/reference \
  python3 experiments/groebner-perf-20260924/round115/panel.py \
  --reference-report /absolute/audited/round112/panel/report.json \
  --output /absolute/new/inner-panel
python3 experiments/groebner-perf-20260924/round115/profile.py \
  --reference-root /absolute/source-matched/reference \
  --reference-report /absolute/audited/round112/panel/report.json \
  --output /absolute/new/inner-profile --reps 5
```
