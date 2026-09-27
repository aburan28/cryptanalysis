# First usable relation for one independently verified target

Round21 compares the merged round20 packed path with early target completion.
Both arms use the same native producer, packed coefficient boundary, independent
exact basis certificate, direct original-equation evaluator and signed curve
replay. Reusable relation collection still examines all certified roots and
requires full column rank. Only target witness selection changes.

`all-roots` preserves the round20 policy: examine every certified assignment,
deduplicate and sort projected rows, then recover from the first row.
`first-usable` visits certified assignments in ascending order and stops after
the first independently checked witness with valid factor-base membership.
Rejected lifts and unusable witnesses do not stop the search. Empty/unsuccessful
systems exhaust their roots. The complete basis certificate and full root set
remain in the receipt, separately from the prefix actually examined. Final
Python scalar replay remains charged inside the online interval.

The mathematical setup remains `EC1N13Ckb1h0f132ba0b5e2`, field degree 13 and
subgroup order 2003 (**11 bits**). Prefix dimensions 3 and 6 have 8/60 actual
usable points, 4/29 folded columns and 9/18 Boolean variables. The producer is
evaluation/Buchberger–Möller (`PDP3eval`), not F4/F5. Each arm gets a new canonical
candidate/source identity with its target policy. Frozen workload identities,
public points, seeds, limits, preparation and same-point rho reference match
round20. Report each one-target workload separately; no batch amortization.

`first_audit.py` retains the round20 independent equation, complete-basis,
curve/projection, dense-rank, column-log, final-scalar and phase-ledger audits.
It additionally checks the exact ascending root prefix, rejected-root reasons,
the selected witness, and termination at the first accepted root. An independent
Python enumeration of signed lifts rejects false claims that an earlier root
could not lift. Collection is required to retain its all-root policy.

The tests compare every nonzero point of the 2003-order subgroup with an
independent point-sum oracle at 9 variables, plus 64 frozen ordinary 18-variable
points. Both policies have identical full basis certificates, decomposition
presence, ordinary collection rows/ranks, target-attempt streams and recovered
scalars. Additional controls reject corrupted basis/root traces and exercise
membership rejection followed by success, exhausted roots, producer budgets,
invalid certificates, consumed contexts and forbidden dictionary conversion.

## Recoverable receipt writing

Round20 repeatedly serialized and compressed its accumulated report. Round21
writes immutable metadata once and appends hash-chained checkpoints containing
only the active group, newly encountered candidate manifests and small mutable
state. Each append is flushed and synced. It materializes the full aggregate
once on normal completion or a caught interruption, and retains the compressed
raw journal beside it. Evidence writing is outside all algorithm intervals.

`journal.recover(path)` also reads an interrupted uncompressed journal. It
retains prior complete records and marks a truncated trailing write interrupted
and ineligible. Checksum, ordering, chain and candidate-mutation failures are
rejected. After an ambiguous write/sync error the writer closes; it never
appends a duplicate sequence. An interrupted journal is not a completed
benchmark. A completed report must exactly equal its recovered journal before
its mathematical audit can pass.

The checkpoint byte-count test is synthetic bookkeeping evidence: doubling
groups from 16 to 32 approximately doubles journal bytes, while rewriting the
accumulated report grows by about four times. It is not an IC speedup or new
mathematical trial. No result or historical failure is discarded to save space.

## Reproduce and qualify

Use Python 3.12/3.13, NumPy 2.4.0 and the same native compilers as round20:

```sh
python experiments/groebner-perf-20260924/round20/build.py
python -m unittest discover -s experiments/groebner-perf-20260924/round21 -p 'test_*.py' -v
python experiments/groebner-perf-20260924/round21/first_measure.py --repetitions 31 --output /tmp/first-relation.json.gz
python experiments/groebner-perf-20260924/round21/first_audit.py /tmp/first-relation.json.gz
```

The default six workloads are independent one-target experiments, each freshly
prepared per arm and repetition. One warmup is retained and excluded from timing
summaries. Order is randomized. All target-dependent attempts, even unsuccessful
ones, and independent scalar replay are charged. Operation counts remain null
under the existing `verified_online_wall` contract. The primary ratio is paired
rho/IC; the secondary engineering ratio is all-roots/first-usable. No IC-over-rho
win, global ranking, GPU crossover or asymptotic improvement is presumed.

Admission requires one-minute load at most the logical CPU count, with the
initial, every paired-group start/end and final sample all passing. This is
necessary but does not establish an exclusive host. `--correctness-only` uses
separate frozen seeds and is permanently ineligible for performance claims.
Existing report/admission/journal files are not overwritten. A CI timeout leaves
the raw journal for recovery; a partial run cannot support a speedup claim.

The Linux/macOS workflow runs the new controls, round20 regressions, exact
audits and a 31-pair measurement per point when admitted. Evidence is retained
on every outcome. Local correctness logs and the source-bound final trace are
listed in `results/inventory.json`; `verify_evidence.py` also checks that each
artifact is tracked by Git.
