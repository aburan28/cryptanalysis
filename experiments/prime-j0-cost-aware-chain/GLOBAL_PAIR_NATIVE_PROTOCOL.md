# Prospective native exact-pair recoder comparison

## Freeze boundary

This protocol is committed and published before its held-out scalar files are
created or inspected. The prior design screen is
[`GLOBAL_PAIR_SEARCH.md`](GLOBAL_PAIR_SEARCH.md); its Python policy source has
SHA-256 `e4aedc63a3478e8afa7771b2b08088201d49b13dbdec1b4bcbd6b84ab0fd7afb`.
The design data selected one experimental policy: at most 32 high-order
options per residue and a beam width of one. Any change to that selection,
the cost model, or the gate below requires a new protocol and new disjoint
inputs. Implementation corrections that preserve the policy must be recorded
with a source digest before the held-out panel executes.

This is a public-scalar, repeated-fixed-point evaluation on the existing
`glv-j0-32` and `j0-56` curves. The result is an operation and correctness
experiment first. CPU timing from a contended host remains exploratory.

## Frozen mathematics and policy

Use the existing lattice reduction and phase-complete 726-point affine table.
Words are exactly the 727 contributions in `make_tau_pair_fused.catalog()`:
726 nonzero signed/unit points and zero. Pair division is

`q=(2(a−d_a)/3+(b−d_b), −(a−d_a+b−d_b)/3)`

for a word `d` matching both coordinates modulo 3. The online evaluation
score is `10 × (pair length−1) + 16 × nonzero words` in the existing project
model. All word positions, including zeros below the highest nonzero word,
are charged for tripling.

Generate one exact bounded-tail action table for `|a|,|b|≤64` by reverse
Dijkstra over all 727 words. Edge cost is `16` for a nonzero word and `10`
when its quotient is nonzero. On equal cost choose the smaller word. An
unreachable bounded state falls through to canonical recoding. The reference
arm applies the existing canonical high-order pair step and then this common
bounded table. The candidate arm uses that same reference completion to
search high-order digits:

1. Sort each residue class by `(a²+3ab+3b², word)` and examine its first
   32 words, or all words if fewer than 32 exist.
2. At each state, form every valid quotient, append the word, and score the
   resulting path plus the reference completion. Retain the best complete
   path only on a strictly lower score. If equal, preserve the earlier path.
3. Exclude bounded and zero quotients from the next frontier. With beam
   width one, select the next state by `(completion score, quotient norm,
   quotient a, quotient b, nonzero count, word path)`.
4. Stop on an empty frontier or after 32 high-order iterations. Select the
   best complete path only when it scores below the reference path; otherwise
   emit the reference path. Preserve its low-to-high word order.

The native implementation must match this selector and exact word stream on
the 128 old design scalars before it sees held-out inputs. It must generate
all policy arrays deterministically from the frozen algorithm, verify every
reachable bounded path and the 727 word mappings, and record the generated
header hash. The online candidate includes every trial and reference
completion in its clock and counters. Neither arm may cache recodings across
scalars or look up held-out scalar answers.

## Held-out inputs

After this protocol and the native implementation are committed, generate
4,096 public scalars for each of four fixed points (`P`, `37P`, `101P`,
`103P`) on each curve, giving eight cases. Use SplitMix64 with the same
64-bit rejection law as the earlier panels, seed `0x7645F13B2AC09D8E`,
and per-case state `seed XOR (curve_index << 32) XOR point_index`.
Reject zero, out-of-range values, every scalar from all manifests already
excluded by `make_phase_complete_pair_inputs.py`, every scalar from
`phase-complete-pair-inputs.json`, and earlier accepted values on the same
curve. Freeze all eight scalar-file SHA-256 values, generic-reference output
digests, generator source hash, and prior-manifest hashes in a committed
fixture manifest before running either native arm on those inputs. Do not
change or replace a failed case.

## Paired execution and acceptance

Run the native reference and candidate on identical inputs and the same
prepared point table. Alternate process arm order across cases. The online
interval begins at the first scalar reduction and ends after the last affine
output. It includes all recoding, policy lookups, group operations, output
conversion, and storage. Record each arm's raw command, status, stdout,
stderr, and online interval; report point-table preparation separately.
For every case retain triple and mixed-add counts, weighted score, trial
digits, canonical completion states, oracle fallbacks, static/table/scratch
bytes, setup operations and inversions, and output digest.

Outside the online interval, replay all 32,768 outputs with generic scalar
multiplication, verify each exact prepared point, reconstruct every emitted
word stream to the reduced lattice representative, and compare native words
against an independent Python implementation of this frozen policy. Include
zero, identity-point, subgroup-order, and small-order controls in the direct
curve test. Preserve every failure, timeout, and zero-gain case as a row.

The operation gate passes only if all eight cases pass every correctness
check and the candidate's weighted evaluation score is strictly lower than
the reference arm in each case. Report absolute score and percentage per
case. A CPU speedup remains **unknown** without at least five paired AB/BA
repetitions on a host with an auditable isolation receipt meeting
`docs/ISOLATED_BENCHMARKS.md`. This protocol does not treat the 32,768-output
batch as a one-target rho or index-calculus result.
