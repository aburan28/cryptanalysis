# High-order exact-pair recoding: design screen

## Question and scope

The [phase-complete pair table](PHASE_COMPLETE_PAIR.md) evaluates any of 727
two-position contributions with one exact affine lookup and one mixed addition.
Its current recoder optimizes a bounded tail and uses a fixed rule at higher
positions. This screen asks whether choosing among high-order contributions
can remove enough triplings or additions to justify the scalar-side search.
All results below are retrospective design-data operation counts for public
scalars. There is no native candidate, CPU speedup, rho result, or academic
novelty claim.

## Recoding identity

Write a scalar representative as `z=a+bτ`, where `τ²=3τ−3` and the reduction
in `run.py` verifies `a+bλ_τ ≡ k (mod r)`. At each pair position choose a
contribution `d=(d_a,d_b)` with `d_a≡a (mod 3)` and `d_b≡b (mod 3)`. Then

`z=d+τ²q`, with `q=(2(a−d_a)/3+(b−d_b), −(a−d_a+b−d_b)/3)`.

The 727 catalog words cover all nine residue classes. For a bounded tail
`|a|,|b|≤64`, reverse Dijkstra over the square and all exact-pair words
stores the least modeled cost among paths that stay in that square. Every
reachable state's stored path is reconstructed and its score checked. The
high-order comparator uses the existing canonical pair step until this
bounded oracle is reachable. This gives both searches the same stronger tail
policy, rather than comparing against the older native word stream.

The phase-complete point table makes the evaluation score
`10 × (pair length−1) + 16 × nonzero pairs`. The highest nonzero pair initializes
the accumulator and every lower pair position costs one tripling; the score uses
the project's established operation weights. It omits scalar recoding,
point-table preparation, memory traffic, affine output, and CPU timing.

Two high-order selectors are screened:

- **Norm greedy:** among the first `K` words of the right residue class,
  sorted by Eisenstein norm, choose the word minimizing the quotient's norm.
- **Beam:** expand the same `K` words, score each with a valid canonical
  completion, retain the best `W` frontier states, and keep the best complete
  recoding seen. The completion score is a heuristic for search order, not a
  proof of global optimality. The result is exact as a scalar representation.

Both selectors fall back to the canonical comparator unless their complete
score is strictly lower. `K=all` uses up to 112 words in a residue class;
`K=32` means at most 32, since three residue classes have fewer words. The
search stops after at most 32 high-order expansions and finishes canonically.

## Design inputs and checks

The first 64 scalar values in the `point0` file for each curve in the older
`tail-pair-fused-inputs.json` fixture are design data. The screen checks the
file hashes from that fixture, every catalog word against its decoded lattice
point, each reduced representative against the scalar modulo the subgroup
order, every reachable bounded-tail path and score, and both complete output
streams against the same lattice representative. The JSON summary records
input and source SHA-256 hashes and the SHA-256 of the row-level CSV. That CSV
preserves all per-scalar outcomes for all 25 selector configurations. The
25 configurations reconstruct 6,400 complete
streams, including baseline and candidate for every scalar. No held-out input
was used for this screen.

## Result and decision

The bounded oracle reaches 15,043 of 16,641 states. The table below uses the
same 64 scalars per curve for every row. `Trials/scalar` counts candidate
digit expansions; `fallback states/scalar` counts distinct canonical
completion states evaluated by the Python screen. Both are scalar-side work
that the evaluation score omits. The [summary](global-pair-search-screen.json)
retains all 25 configurations; the [raw rows](global-pair-search-raw.csv)
retain every scalar, including zero-saving cases.

| Selector | glv-j0-32 modeled saving | glv trials / fallback states | j0-56 modeled saving | j0-56 trials / fallback states |
| --- | ---: | ---: | ---: | ---: |
| Norm greedy, K=32 | 0.45% | 100 / 6 | 0.00% | 369 / 15 |
| Beam, K=16, W=1 | 5.58% | 36 / 46 | 1.98% | 127 / 163 |
| Beam, K=32, W=1 | 7.93% | 63 / 77 | 3.39% | 195 / 248 |
| Beam, K=all, W=1 | 12.38% | 162 / 192 | 5.41% | 485 / 583 |
| Beam, K=all, W=8 | 13.30% | 1,209 / 459 | 7.08% | 4,676 / 1,796 |

The greedy norm rule loses almost all potential gain, and the unrestricted
beam does much more scalar-side work. `K=32, W=1` is the selected *design
candidate* for a native recoder investigation because it retains modeled
operation savings on both curves with fewer trial digits than the full beam.
This is a choice for the next experiment, not a claim that it is faster.
Recoding may outweigh every saved group operation on these small curves.

Before a held-out native comparison, freeze the exact selector and its
implementation, disjoint scalar fixture, paired arm order, operation and
memory accounting, and correctness checks in a separate prospective protocol.
Charge online recoding, point lookup, group operations, and output conversion
inside the same timed interval for both arms. Preserve point-table preparation
separately. Use host-level isolation receipts for any CPU speedup claim.

This search composes established ideas in a new configuration for this codebase;
digit-set optimization and dynamic recoding have prior art, including
[Heuberger and Krenn](https://arxiv.org/abs/1110.0966) and
[Heuberger and Mazzoli](https://eprint.iacr.org/2013/705.pdf).

## Reproduce

```sh
python3 experiments/prime-j0-cost-aware-chain/screen_global_pair_search.py --samples 64
```

The script uses only the Python standard library and the repository's pure
Python recoding modules. It does not launch a Sage job.
