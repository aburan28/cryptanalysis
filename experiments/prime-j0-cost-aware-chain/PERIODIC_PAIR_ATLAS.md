# Periodic 3-adic exact-pair action atlas: design screen

## Question

The [high-order beam](GLOBAL_PAIR_SEARCH.md) saves modeled group operations
but evaluates many candidate completions online. Its
[native design check](https://github.com/aburan28/cryptanalysis/pull/324)
confirms the word streams and exposes that large scalar-side workload. Can a
small periodic action table capture some of the savings with one lookup at
each high-order pair position?

This is a retrospective operation screen using previously published design
scalars. It is not a native wall-time result, isolated CPU speedup, one-target
rho comparison, or academic novelty claim.

## Algebra and online policy

In the `1,τ` coordinate basis, multiplication by `τ²` is

`(a,b) ↦ (−3a−9b, 3a+6b) = 3 U(a,b)`, where
`U = [[−1,−3],[1,2]]` has determinant `1`.

Consequently, `τ^(2h) Z[τ] = 3^h Z²` in these coordinates: coordinate
residues modulo `3^h` are exactly quotient classes modulo `τ^(2h)`. For modulus
`M=3^h`, replace a high-order state `(a,b)` by its centered coordinate
residues `(ā,b̄)` modulo `M`, look up the shortest-path bounded-tail action
for `(ā,b̄)`, and apply that word to the *actual* `(a,b)`. The word is valid
because actual and centered states agree modulo `3`. The exact quotient
identity in [GLOBAL_PAIR_SEARCH.md](GLOBAL_PAIR_SEARCH.md) proves scalar
reconstruction; it does not make the periodic action globally optimal.

Within `|a|,|b|≤64`, use the exact bounded-tail action directly. If a
centered table entry is unavailable, use the established canonical pair
step. Try `M∈{3,9,27,81}`. The `M=27` table has 729 reachable entries,
representing three pair positions, and its raw `uint16` action array would
occupy 1,458 bytes. The screen also applies a per-scalar gate: construct the
canonical-plus-exact-tail schedule and the periodic schedule, then evaluate
the one with the lower frozen `10 × triples + 16 × additions` score. A tie
keeps the canonical schedule. This gate performs two linear-time recodes; it
does not evaluate beam alternatives or cache a scalar's answer.

## Design inputs and verification

Use the first 512 scalar values of each curve's `point0` file from
`tail-pair-fused-inputs.json`, the same older design fixture used for the
earlier pair experiments. The [screen](screen_periodic_pair_atlas.py)
verifies both scalar-file hashes, each reduced representative modulo the
subgroup order, the exact bounded-tail oracle, and complete lattice
reconstruction for every emitted schedule. All 4,096 candidate/scalar
configurations terminated and reconstructed exactly. The
[summary](periodic-pair-atlas-screen.json) records source and raw-file
SHA-256 hashes; the [CSV](periodic-pair-atlas-raw.csv) retains each scalar,
including regressions and zero gains.

## Result and decision

All entries below are modeled group-operation counts, not CPU times.
`Direct` uses the periodic schedule without the per-scalar gate. `Gated`
chooses the lower-cost complete schedule. The comparison holds the curve,
scalar, exact point table, and bounded-tail oracle fixed.

| Curve | Modulus | Direct saving | Scalars worse direct | Gated saving | High-order lookups / scalar |
| --- | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32 | 9 | −0.66% | 101 / 512 | 2.48% | 3.65 |
| glv-j0-32 | 27 | −0.69% | 160 / 512 | **4.40%** | 3.65 |
| glv-j0-32 | 81 | −11.92% | 348 / 512 | 2.55% | 3.63 |
| j0-56 | 9 | −2.15% | 244 / 512 | 0.93% | 13.50 |
| j0-56 | 27 | −0.75% | 209 / 512 | **2.72%** | 13.48 |
| j0-56 | 81 | −11.82% | 414 / 512 | 0.71% | 13.48 |

`M=3` is a negative control: direct costs worsen 20.37% and 33.43%,
respectively. `M=27` is the selected design candidate because its gated
schedule improves the operation score on both curves with only one atlas
lookup per high-order position. The ungated form is a regression and must
not be presented as a speedup. This design result does not include the
online cost of constructing two schedules and comparing their scores; a
native implementation and host-isolated comparison are required to learn
whether complete scalar multiplication is faster.

Digit-set and dynamic recoding methods have prior art, including
[Heuberger and Krenn](https://arxiv.org/abs/1110.0966) and
[Heuberger and Mazzoli](https://eprint.iacr.org/2013/705.pdf). The specific
periodic atlas and gate here are an experimental combination in this codebase;
academic novelty has not been established.

## Reproduce

```sh
python3 experiments/prime-j0-cost-aware-chain/screen_periodic_pair_atlas.py --samples 512
```

The script uses pure Python and does not launch Sage. The
[prospective native protocol](PERIODIC_PAIR_NATIVE_PROTOCOL.md) freezes the
exact `M=27` selector, gate, fixture, pairing, correctness checks, and
memory/setup accounting before any disjoint inputs are generated.
