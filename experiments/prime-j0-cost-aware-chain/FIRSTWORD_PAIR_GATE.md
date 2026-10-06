# Single-pass first-word gate for the periodic pair atlas

## Question and fixed policy

The exact periodic selector in [PR #329](https://github.com/aburan28/cryptanalysis/pull/329)
constructs both the canonical and periodic pair schedules for each scalar.
The [bounded 64-bit path](PERIODIC_PAIR_INT64.md) reduces the arithmetic
cost of those schedules, but still constructs both. This experiment tests a
selector that chooses **before** recoding, from the first periodic action
word alone, so it emits only one complete schedule.

Both arms use the same lattice reduction, modulus-27 periodic action atlas,
bounded-tail oracle, 726-point phase-complete exact table, and `10 ×
triples + 16 × additions` operation score. The first word is the exact
bounded-tail action when reachable, otherwise the action at the centered
modulus-27 residue. A 128-byte bitset keyed by that word determines whether
to run the periodic or canonical schedule. A selected periodic schedule is
used even when its realized score loses: this policy has no per-scalar
nonregression guarantee. A 128-word periodic fallback uses the canonical
schedule and is counted. Zero scalars and reduced coordinates outside the
proved 64-bit envelope keep their existing behavior. The bitset is fixed
before the new held-out fixture is generated.

## Retrospective training and separate validation

The [screen](screen_firstword_pair_gate.py) uses the published
`tail-pair-fused-inputs.json` point-0 scalar files on both curves for
training (4,096 scalars per curve). For each first periodic word, it sums
`canonical_score − periodic_score`; it selects a word iff it occurs at least
twice and that sum is positive. There is one shared bitset for both curves,
with 269 selected words of the 1,024 possible 10-bit codes. The
[generated header](../../src/generated/tau_pair_firstword_gate.h) SHA-256 is
`4c41264382d67a3b33e90712ac06ac3857d239106e44dd8b53422bb628dc7b0f`.

The same script evaluates the already-published point-1 scalar files
(4,096 per curve) **without fitting to them**. The
[summary](firstword-pair-gate-screen.json) pins all source and input hashes;
the [raw rows](firstword-pair-gate-raw.csv) retain every scalar and score.
The [read-only audit](audit_firstword_pair_screen.py) recomputes the
training rule, decoded bitset, input identities, and four score totals.
These are old data and constitute only a design screen, not a fresh
prospective success claim.

| Curve | Point | Canonical score | First-word score | Modeled saving | Selected scalars |
| --- | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32 | 0 (train) | 431,560 | 421,960 | 2.22% | 1,585 |
| glv-j0-32 | 1 (validate) | 431,210 | 421,664 | 2.21% | 1,486 |
| j0-56 | 0 (train) | 1,124,088 | 1,111,934 | 1.08% | 1,553 |
| j0-56 | 1 (validate) | 1,121,712 | 1,113,130 | 0.77% | 1,500 |

The direct ungated periodic policy raises the operation score on all four
cases. The first-word gate sacrifices part of the exact two-schedule
gate's operation gain to avoid its second complete recoding pass. Neither
CPU wall time nor academic novelty follows from these scores.

## Prospective native and held-out gate

Commit this protocol, screen, raw rows, and generated bitset before native
implementation. The native arm must match the Python selected word stream
on all 8,192 training scalars and 8,192 separate point-1 validation
scalars, including per-scalar selector decisions, aggregate operations,
fallbacks, and independent generic point replay. Test identity, subgroup
order, small-order points, every bounded-tail action, and all 729 atlas
entries. Commit the native implementation before generating new inputs.

Use the same SplitMix64 64-bit rejection law with seed
`0x4A71D5E2C3908B6F` to freeze 4,096 new public scalars for each of
`P`, `37P`, `101P`, and `103P` on each curve. Reject zero, out-of-subgroup
values, all scalars in the earlier `periodic-pair-int64-inputs.json`
fixture and its predecessor fixtures, and earlier accepted scalars on the
same curve. Commit the generator and prior-manifest hashes, scalar-file
hashes, and generic-reference output digests **before** running either
arm. The paired reference is the single-pass canonical arm; the candidate
is the single-pass first-word arm. Keep the same point table and resource
envelope. Alternate arm order, preserve every failure, and verify all
32,768 outputs, all prepared points, and the selected word streams outside
the online timer.

The online interval starts with the first target scalar reduction and ends
after the last affine output; it includes the candidate's first-word gate,
all recoding, group operations, conversion, and storage. Report preparation
and static-map bytes separately. The prospective modeled-operation gate
passes only if every arm verifies and the candidate score is strictly lower
in **all eight** paired cases. CPU wall-time effect requires at least five
AB/BA repetitions per case and a qualifying host-level isolation receipt
from `scripts/isolated_bench.py`. A repeated fixed-point panel cannot
substitute for a one-target rho or index-calculus comparison. Academic
novelty requires a separate prior-art assessment.

Reproduce the old-data screen and audit without Sage:

```sh
python3 experiments/prime-j0-cost-aware-chain/screen_firstword_pair_gate.py
python3 experiments/prime-j0-cost-aware-chain/audit_firstword_pair_screen.py
```

## Native old-data controls

The [native differential receipt](firstword-pair-native-design.json) retains
all 256 command statuses, stdout, raw word traces, input and source hashes,
and the exact design64 executable hash. Its
[read-only audit](audit_firstword_pair_native_design.py) confirmed all
**16,384** Python-selected word streams exactly, including 8,192 training
and 8,192 point-1 validation scalars. The four native group-operation
scores and selector counts match the table above; all generic scalar
replays and all 726 prepared-point checks passed. The candidate recorded
zero 128-word fallbacks. Its 68,157 static-map bytes are the prior 68,029
bytes plus the 128-byte gate. The direct curve test passed 2,293,682 checks,
including identity and small-order controls. Fourteen CTests passed together;
the coordinator loopback test passed separately with socket access.

`periodic_lookups` for this mode includes the gate's initial atlas read and
any atlas reads made while constructing a selected periodic schedule. The
native receipt records 9,885 and 9,469 such reads on the two `glv-j0-32`
old cases, and 25,041 and 24,296 on the two `j0-56` cases. These old-data
controls establish correctness of the native policy.

## Frozen held-out result

The [input generator](make_firstword_pair_inputs.py), its
[read-only audit](check_firstword_pair_inputs.py), and the
[paired runner](check_firstword_pair_panel.py) were committed before either
paired arm ran. The [fixture](firstword-pair-inputs.json) was committed as
`9823bf47` before the paired runner executed. It contains 32,768 new
scalars, with earlier fixtures excluded by the generator. The fixture
manifest SHA-256 is
`d144189c6b53317c9380515baecb3ea3aec41fc00d8b82b367dba808eb0eaaf5`.

The [raw paired receipt](firstword-pair-native-panel.json) preserves all 16
command statuses, stdout and stderr, hashes, arm order, operation counts,
selector counts, exploratory intervals, and correctness results. Its
[read-only audit](audit_firstword_pair_panel.py) independently checks all
eight pairings, output digests, 726 prepared points per arm, source and
executable hashes, operation scores, and the strict gate. Every arm exited
successfully and verified its 4,096 outputs; all eight candidate scores were
strictly lower than the paired canonical score.

| Curve | Point | Canonical score | First-word score | Modeled saving | Selected scalars | Candidate atlas reads |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32 | 0 | 433,754 | 424,628 | 2.10% | 1,510 | 9,614 |
| glv-j0-32 | 1 | 431,986 | 423,610 | 1.94% | 1,492 | 9,571 |
| glv-j0-32 | 2 | 431,476 | 422,286 | 2.13% | 1,567 | 9,779 |
| glv-j0-32 | 3 | 431,798 | 423,064 | 2.02% | 1,551 | 9,779 |
| j0-56 | 0 | 1,122,588 | 1,114,820 | 0.69% | 1,506 | 24,382 |
| j0-56 | 1 | 1,121,570 | 1,111,826 | 0.87% | 1,535 | 24,772 |
| j0-56 | 2 | 1,120,150 | 1,111,662 | 0.76% | 1,495 | 24,243 |
| j0-56 | 3 | 1,122,308 | 1,113,490 | 0.79% | 1,493 | 24,246 |

There were no 128-word fallbacks. The separate
[native word-stream receipt](firstword-pair-native-heldout-words.json) and
[audit](audit_firstword_pair_native_heldout_words.py) check every one of the
32,768 selected streams against the frozen Python policy in 512 raw 64-scalar
runs. Their aggregate scores, selections, and atlas reads match the paired
receipt. The operation gate therefore passes on the prospective fixture.

These scores are a fixed group-operation model, not CPU wall-time speedups.
The local macOS host has no qualifying isolation receipt, and this panel has
one arm execution per case rather than five AB/BA repetitions. The recorded
local intervals are exploratory; controlled CPU effect and academic novelty
remain unknown. The candidate uses 68,157 static-map bytes versus 68,029 for
the canonical arm, with the same 24,336-byte prepared state and 726 points.

Recheck the frozen evidence without running a new panel:

```sh
python3 experiments/prime-j0-cost-aware-chain/check_firstword_pair_inputs.py --bench build-cost-aware/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/audit_firstword_pair_panel.py --bench build-cost-aware/ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/audit_firstword_pair_native_heldout_words.py --bench build-cost-aware/ca_tau_chain_design64
```

## Controlled CPU run when a qualifying host is available

The [isolated manifest producer](make_firstword_pair_isolated_manifest.py)
binds these eight frozen cases and both exact arms to five paired repetitions
in the repository's [serial benchmark service](../../docs/ISOLATED_BENCHMARKS.md).
It verifies the fixture and scalar-file hashes before writing the manifest,
and includes the executable, build cache, runner, and relevant source files
as hashed artifacts. It does not perform a run or claim that a host passes
isolation. Select CPU and NUMA identifiers from that host's topology; the
numbers below are illustrative.

```sh
cmake -S . -B /workspace/build/firstword -DCMAKE_BUILD_TYPE=Release -DCA_CUPQC=OFF -DCA_WERROR=ON -DCA_BUILD_TAU_CHAIN_BENCH=ON
cmake --build /workspace/build/firstword --target ca_tau_chain_bench
python3 experiments/prime-j0-cost-aware-chain/make_firstword_pair_isolated_manifest.py \
  --repo-root /workspace/cryptanalysis \
  --bench /workspace/build/firstword/ca_tau_chain_bench \
  --cgroup /sys/fs/cgroup/benchmark-isolated \
  --cpus 4-5 --execution-cpu 4 --mem-nodes 0 \
  --output /workspace/isolated-bench/firstword-pair.json
python3 scripts/isolated_bench.py probe /workspace/isolated-bench/firstword-pair.json
python3 scripts/isolated_bench.py --queue-root /workspace/isolated-bench submit /workspace/isolated-bench/firstword-pair.json
```

`probe` must pass on a physical, host-controlled Linux machine before
submission. The service alternates arm order across repeats and cases,
serializes all work, retains every failure, and leaves aggregate speedup
unknown if any isolation, noise, answer, or completion gate fails.
