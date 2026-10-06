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
