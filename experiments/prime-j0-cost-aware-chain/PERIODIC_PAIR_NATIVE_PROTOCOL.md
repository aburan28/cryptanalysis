# Prospective native modulus-27 pair-atlas comparison

## Freeze boundary and question

This protocol is published before its held-out inputs are created. The
[design screen](PERIODIC_PAIR_ATLAS.md) selected the gated modulus-27
periodic atlas. Its implementation source has SHA-256
`1f0fb33ffbd7d0273d54afd82b04da892feb3814cb9c80e1de4dc0a9c295c3ac`.
The experiment asks whether replacing high-order beam search with one
residue action lookup per pair leaves an end-to-end scalar multiplier that
is faster after charging both recoders and their gate. A change to modulus,
digit policy, gate, score, fixture law, or success criterion requires a new
protocol and new disjoint inputs. Implementation corrections preserving the
policy must be committed with source hashes before held-out execution.

## Frozen policy and comparison

Both arms use the same lattice reduction, 726-point phase-complete exact
table, and shortest-path bounded-tail oracle over `|a|,|b|≤64`. The oracle
uses all 727 pair words, cost `16` per nonzero contribution plus `10` when
the quotient is nonzero, with smaller word breaking equal-cost ties. The
reference emits canonical high-order pair steps until the oracle can finish.

The candidate constructs that exact reference schedule, then constructs a
periodic schedule. At every nonzero state with a reachable bounded-oracle
action, use the bounded action. Otherwise center each coordinate modulo
`27` into `[-13,13]`, look up the bounded-oracle action for the centered
pair, and apply its word to the actual state. All 729 centered actions are
reachable. Divide exactly by `τ²` after subtracting the word and repeat.
If a periodic schedule exceeds 128 words, emit the reference schedule and
record that fallback. Compare full schedules by

`10 × (word count−1) + 16 × nonzero word count`.

Emit the periodic schedule only when its score is strictly lower; on a tie
emit the reference. Preserve low-to-high word order and the exact-table
index rule from `PHASE_COMPLETE_PAIR.md`. Include construction and scoring
of **both** schedules in the candidate's online interval. No scalar answer
or recoding may be cached across calls. Generated action arrays must be
deterministic and independently verified against the frozen Python oracle.

## Controls before held-out inputs

The native implementation must match the reference and selected Python
word streams, triple/add counts, and gate decisions on all 1,024 old design
scalars used by `screen_periodic_pair_atlas.py`, with per-scalar evidence or
collision-resistant digests. Verify all 729 periodic actions, every
reachable bounded-tail path, zero and subgroup-order scalars, identity and
small-order points, and independent generic scalar replay. Build and pass
the direct curve test and the applicable repository CI gates. Commit the
native implementation and generated table before creating the fixture.

## Disjoint held-out workload

After the protocol and implementation are committed, generate 4,096 public
scalars for each of `P`, `37P`, `101P`, and `103P` on each of the two curves:
eight cases and 32,768 scalar-point outputs. Use SplitMix64 and the prior
64-bit rejection law with seed `0xB6DE9430F15A27C8` and per-case state
`seed XOR (curve_index << 32) XOR point_index`. Reject zero, values outside
the subgroup range, all scalars in the manifests excluded by
`make_phase_complete_pair_inputs.py`, all scalars in
`phase-complete-pair-inputs.json`, and earlier accepted values on the same
curve. Freeze generator and prior-manifest hashes, eight scalar-file hashes,
and generic-reference output digests in a committed fixture manifest
*before* executing either candidate arm. Preserve a failed case and its
status; do not silently replace the fixture.

## Paired run and claims

Pair the canonical and gated periodic arms on the same prepared point,
scalar file, code snapshot, and resource envelope. Alternate arm order
across cases. The online interval starts at the first scalar reduction and
ends after the last affine output; it includes recoding, the per-scalar
gate, policy lookup, group operations, conversion, and storage. Report
point-table preparation separately, including setup operations, inversions,
static action bytes, exact-point bytes, full prepared bytes, and scratch.
Retain raw command, stdout, stderr, status, online interval, triples,
additions, lookup and gate counts, fallback counts, output digest, and code
and binary hashes for every arm/case.

Outside the timed interval, reconstruct every emitted word stream, replay
all 32,768 outputs with generic scalar multiplication, and verify all 726
exact prepared points per case. Keep every failure, timeout, and zero-gain
case. The modeled-operation gate passes only if all eight paired cases are
fully verified and the gated periodic score is strictly lower than the
canonical score in every case. An isolated CPU wall-time speedup requires
at least five paired AB/BA repetitions and an auditable host-level receipt
under `docs/ISOLATED_BENCHMARKS.md`; local timing and operation scores alone
cannot establish it. This repeated-fixed-point workload does not answer
a one-target rho or index-calculus speed question. Academic novelty is a
separate prior-art question and is not claimed by this gate.

## Native implementation and old-design controls

The generated bounded-tail and modulus-27 header reproduced SHA-256
`232a09169126b103f3cca1c2efb3aef0d8a6c8f3aca5565630286e99d911f399`
on two runs. The [exact cross-language control](periodic-pair-native-design.json)
compared all 2,048 native word streams, one for each arm on each of the
1,024 old design scalars, directly against the frozen Python schedules.
It also matched per-run triple/add counts, atlas lookup counts, gate
acceptances, and zero fallbacks. The [raw word rows](periodic-pair-native-design-words.csv)
and full native stdout/stderr/status remain available. The direct curve test
passed 2,293,207 checks. The 14 tests that do not need a loopback socket
passed together; the coordinator socket test passed separately with loopback
access. These controls precede held-out input generation.

An additional [paired old-data diagnostic](periodic-pair-native-old-panel.json)
ran 4,096 scalars from the prior orbit-pair `point0` fixture on each curve.
Both arms independently replayed every output and verified the 726 prepared
points. Its raw commands, statuses, stdout/stderr, exploratory local intervals,
source hashes, and binary hash are retained. The deterministic counters are:

| Curve | Canonical score | Gated periodic score | Modeled saving | Atlas lookups | Periodic schedules accepted | Fallbacks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32 | 431,560 | 412,918 | 4.32% | 15,010 | 1,200 | 0 |
| j0-56 | 1,124,088 | 1,093,796 | 2.69% | 55,254 | 1,572 | 0 |

This old-data result verifies the intended operation saving with low search
work and justifies proceeding to the frozen disjoint panel. It does not
establish an isolated CPU speedup. The protocol above remains unchanged.

## Frozen disjoint panel result

The protocol was committed as `e4178e1e`, the native implementation as
`5024a385`, the fixture generator as `760270cf`, the fixture as `f29b3106`,
and the sequential runner as `675a2722`, in that order. Each was pushed
before the dependent held-out step. The [fixture manifest](periodic-pair-native-inputs.json)
has SHA-256 `70e2dbf16f8efd40e6e179a02f0aced1c6a99eab75a3ff9584fc7b0bf1de5a14`.
The [fixture check](check_periodic_pair_inputs.py) reproduced all 32,768
scalars, verified disjointness from 90,101 and 90,112 prior scalar values
on the two curves, and matched the generic-reference output digest of all
eight cases.

The [raw paired panel](periodic-pair-native-panel.json) and its
[read-only audit](audit_periodic_pair_panel.py) record 16 successful arms,
eight verified pairs, and a strict modeled-operation gain in every pair.
The score is `10 × triples + 16 × additions`; it excludes table setup and
recoding work, both of which remain recorded separately. Each arm verified
its 4,096 scalar-point outputs by generic replay and all 726 prepared points.

| Frozen case | Canonical score | Gated periodic score | Saved score | Modeled saving |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32-point0 | 435,424 | 415,932 | 19,492 | 4.48% |
| glv-j0-32-point1 | 432,470 | 414,064 | 18,406 | 4.26% |
| glv-j0-32-point2 | 431,264 | 413,288 | 17,976 | 4.17% |
| glv-j0-32-point3 | 429,412 | 410,690 | 18,722 | 4.36% |
| j0-56-point0 | 1,123,616 | 1,094,226 | 29,390 | 2.62% |
| j0-56-point1 | 1,120,898 | 1,091,348 | 29,550 | 2.64% |
| j0-56-point2 | 1,122,782 | 1,092,562 | 30,220 | 2.69% |
| j0-56-point3 | 1,124,212 | 1,093,804 | 30,408 | 2.70% |

Over four cases per curve, the score falls from 1,728,570 to 1,653,974
(4.32%) on `glv-j0-32` and from 4,491,508 to 4,371,940 (2.66%) on
`j0-56`. The candidate made 59,871 and 220,887 atlas lookups, accepted
4,751 and 6,199 periodic schedules, and had zero 128-word fallbacks.
Both arms used 726 exact points (23,232 bytes), 24,336 prepared bytes,
68,029 static map bytes, and 1,024 online scratch bytes per case. Table
preparation recorded 103 additions, 390 rotations, and two inversions.

The candidate's raw local online interval was longer in seven of eight
pairs. The macOS host has no host-level isolation receipt, and these
single-pass timings are exploratory. The controlled CPU wall-time effect
is **unknown**. The operation gate passes; an end-to-end CPU speedup,
one-target rho benefit, and academic novelty are not established.

The committed panel can be audited from a fresh checkout without rebuilding
the host-specific executable:

```sh
python3 experiments/prime-j0-cost-aware-chain/audit_periodic_pair_panel.py
```

When the exact original executable and CMake cache are available, add
`--bench PATH` and `--build-cache PATH` to check their bytes against the
recorded hashes. The fixture's generic-reference replay additionally needs
the exact reference binary, as described by `check_periodic_pair_inputs.py
--help`.
