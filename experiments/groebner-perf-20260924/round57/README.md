# Complete-query timing for sparse F4 pair and pivot selection

This experiment compares the four non-deferred round56 variants with the existing
packed evaluation/interpolation solver. The purpose is to determine whether the
charged-work reductions improve a complete, independently verified query. No
producer, checker or application dispatch is changed here.

`measurement_plan.json` freezes all 23 original fixtures, the primary/comparator
arms, limits, ordering, repetition counts, load admission and acceptance rule
before timing. The five planted six-variable PDP controls are primary. Every
primary case gets three trials with one retained warmup and seven measured pairs.
The remaining eight algebra and ten harder PDP controls are secondary, with one
trial of one warmup and three measured pairs. All attempts are individual queries;
there is no batch-throughput metric or numeric-answer reuse.

The primary F4 variant is `chain_filter`; comparisons with `prior`, `chain` and
`filter` separate the old baseline and both constituent optimizations. Evaluation
is retained as a diagnostic comparator on every PDP case. It cannot be omitted
because it outperforms an F4 variant. Failed and budget-limited queries cannot
provide speedup denominators.

## Timing interval and correctness

PDP timing starts with fresh descent from the frozen target coordinate and ends
after independent native certification, root extraction, original-equation checks
and curve replay. Library loading, fixture construction and ring-only layouts are
separate. F4 uses its certified basis for bounded extraction; evaluation uses the
roots its independent checker already provides. Both use the same untouched
reference equations and curve code. Four exclusive outer phases sum exactly to
the query wall time; nested native timers remain diagnostics.

The wider algebra controls time frozen coefficient packing through independently
certified basis materialization. Their measurements are separately labeled; they
are not complete point-decomposition queries. The F4 checker does not enumerate,
but the supplementary extraction here is restricted to at most 4,096 assignments.
Planted fixtures are correctness controls, not a natural relation-yield study.
There is no full IC solve or paired rho measurement in this panel: `candidate_id`
and `online_speedup` stay null.

Before measurement, `preflight.py` independently verifies fresh optimized and
UBSan queries, matches F4 proofs/counters to the frozen round56 screen, checks
evaluation with a separate Python truth/staircase oracle, and requires identical
canonical bases across successful arms. All 214 case/arm/sanitizer rows remain in
the preflight. Trap-mode UBSan avoids loading a dynamic sanitizer runtime into
Python; optimized evaluation flags and mathematical source are unchanged.

## Admission and analysis

The one-minute load must not exceed one per logical CPU at admission and before
and after each arm. Two rejected admissions stop an attempt, recording every
remaining trial as unrun. A load spike makes a trial unqualified; its rows are
retained. Arm order uses seeded shuffled cyclic rotations. Every timed result
must match its independently verified preflight identity and integer counters.
Source, generated-code and rebuilt-binary bindings must remain unchanged.

The acceptance rule requires all three qualified trials on all five primary
cases, with the lower paired-bootstrap 95% median-ratio bound above one against
each confirmatory comparator. Whether those same bounds exceed two is reported
separately as an engineering target. Per-case intervals are descriptive; they
provide no familywise guarantee or general workload-population claim. A partial
panel cannot promote routing or establish the primary claim.

```sh
python3 experiments/groebner-perf-20260924/round57/build.py
python3 -m unittest discover -s experiments/groebner-perf-20260924/round57 -p 'test_*.py' -v
python3 experiments/groebner-perf-20260924/round57/preflight.py --output preflight.json.gz
python3 experiments/groebner-perf-20260924/round57/measure.py --preflight preflight.json.gz --output timing-panel
python3 experiments/groebner-perf-20260924/round57/analyze.py --input timing-panel --output timing-analysis.json
```

Use new output paths for every attempt. Keep compilation and other local heavy
work out of the measurement interval. Retain the build receipt, preflight,
`attempts.jsonl`, panel report and analysis together. A CI correctness pass can
coexist with no admitted timing rows or a failed performance hypothesis.
