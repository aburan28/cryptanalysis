# Full-digit mixed-radix tail on prime-field j=0 curves

## Design question

The [bounded mixed-radix tail](MIXED_RADIX_TAIL.md) uses one of 727 already
prepared pair digits after a τ² step, but only zero or six units after a
single τ or binary doubling. Can every radix use the complete prepared digit
set without another point table? This variant changes only the offline action
map. It retains the same lattice representative, high canonical recoder,
entry rule, 726-point table, projective evaluator, and cost model. Its online
actions still fit in one 12-bit `(kind, word)` code per bounded state.

The graph contains every state `|a|,|b|≤64`. For a successor `s` and
predecessor `q`, each legal action has one of the exact forms

```text
s = τ² q + d       τ²(a,b) = (−3a−9b, 3a+6b)
s = τ  q + d       τ (a,b) = (−3b, a+3b)
s = 2  q + d       2 (a,b) = (2a, 2b),
```

where `d` is **any** of the 727 existing words, including zero, for each
radix. Reverse Dijkstra uses the frozen weights `10` per τ², `6` per τ,
`8` per double, and `16` per nonzero digit; the first nonzero digit has no
radix charge. Equal-cost ties choose τ², then τ, then doubling, then the
lower word code. All 16,641 states have exact paths. The action map uses
33,282 raw bytes, the same size as the unit-restricted mixed map. The
[read-only auditor](audit_mixed_full_digits.py) reconstructs every path,
checks its cost and every legal-edge Bellman inequality, and replays every
old scalar row.

This is a concrete digit-set extension of the existing mixed-radix scheme.
It is **not** an academic-novelty claim: double-base and τ-adic methods, and
Eisenstein digit sets on prime-field `j=0` curves, have prior art. The
implementation must still show a real end-to-end benefit.

## Retrospective design result

The [screen](screen_mixed_full_digits.py) used all 4,096 older scalars in
each point-0 and point-1 file on both curves, with the high recoding held
fixed. Its [raw rows](mixed-full-digits-raw.csv) and
[summary](mixed-full-digits-screen.json) pin inputs, source hashes, map
hash, scores, and operation counts. The new graph examines 7,145,038 legal
edges and improves the modeled optimum on 7,946 bounded states. The
full-digit score is never worse for an old scalar because the old graph is
a subgraph.

| Curve | Point | Unit-restricted mixed | Full-digit mixed | Saving |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32 | 0 | 403,540 | 401,334 | 0.55% |
| glv-j0-32 | 1 | 402,474 | 400,168 | 0.57% |
| j0-56 | 0 | 1,095,048 | 1,092,624 | 0.22% |
| j0-56 | 1 | 1,093,962 | 1,091,530 | 0.22% |

These are modeled group-operation scores, not CPU timings. The 727 digits
already have prepared points, so this variant adds no point entries or table
preparation. Native recoding, map reads, group operations, conversion, and
memory traffic must all be timed on an isolated host before a CPU claim.

## Prospective gates

Freeze the generator, generated map, old-data rows, auditor, and this
protocol before implementing the native variant. Commit the native evaluator
and exact old-data differential controls before generating a new fixture.
Compare every C action stream on the 16,384 old scalars with the frozen map,
check generic point multiplication, and reconstruct all 16,641 map states.
Cover zero, subgroup-order multiples, small-order inputs, and the rational
τ kernel. Preserve the unit-restricted mixed mode as the comparator.

Generate eight new 4,096-scalar cases for `P`, `37P`, `101P`, and `103P` on
both curves with SplitMix64 64-bit rejection seed `0x56B02D89A7C31E4F`.
Exclude zero, out-of-subgroup values, all prior fixture scalars including
`mixed-radix-inputs.json`, and earlier accepted scalars on the same curve.
Freeze the scalar files, their hashes, generic-reference output digests,
and a two-arm rotating runner in a commit before either arm executes. The
prospective operation gate requires verified outputs and a strictly lower
full-digit score than the unit-restricted mixed score in all eight cases.
Retain every raw failure, timeout, and output digest.

The online interval begins with the first scalar reduction after input
loading and the 726-point preparation, and ends after the last affine
output. It includes recoding, map reads, group operations, conversion, and
storage. Report preparation, prepared bytes, and selected static-map bytes
separately. A controlled CPU claim requires at least five paired AB/BA
repetitions on a host passing the repository's isolation preflight. The
ordinary Mac panel is algorithmic evidence only. This fixed-point repeated
panel cannot establish a one-target rho speedup.

Reproduce the design screen and audit without Sage:

```sh
python3 experiments/prime-j0-cost-aware-chain/screen_mixed_full_digits.py --samples 4096
python3 experiments/prime-j0-cost-aware-chain/audit_mixed_full_digits.py
```
