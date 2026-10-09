# Three-representative scalar selector: source and correctness result

The scalar `k` has many equivalent pairs `(a,b)` because
`a + b λτ ≡ k (mod n)`. The existing reduction inspects 25 nearby
endomorphism-lattice coset representatives and uses the smallest
Eisenstein norm. This experiment keeps the three smallest by the
predeclared norm/magnitude/coordinate ordering. It evaluates the
existing selective τ recoder on rank 0 and the zero-τ-priority recoder
on ranks 0, 1, and 2, then uses the lowest complete one-use source cost.
Ties favor selective rank 0, then zero-τ ranks 0, 1, and 2.

The design rule and Python scorer were committed at `5145d7de`; the
Sage replay's fixture/source binding was tightened at `0dc14749`.
Both preceded generation of the new 256-case fixture. Its input SHA-256
is `196ae2d9eca201d017edf5dce68595e3633b9a7de4a6226cfcd688c43a086844`.
No scalar appears in the seven earlier fixtures on this branch or in
the sibling exact-radix fixture. The checked Sage runtime status was
`verified` before generation.

| Panel | Cases | Existing shortest-selector `M+S` | Three-representative `M+S` | Saving | Improved cases | Nonshort choices |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Inspected design fixture | 64 | 86,405 | 85,921 | 484 (0.56%) | 24 | 24 |
| New held-out fixture | 256 | 345,924 | 344,252 | 1,672 (0.48%) | 88 | 88 |

The held-out choice histogram is 73 selective rank 0, 95 zero-τ rank
0, 58 zero-τ rank 1, and 30 zero-τ rank 2. Every held-out case tied
or improved in the source model because the prior two paths remain
available. Source `M+S` counts include chosen one-use seed preparation
and point operations. They do **not** price the 25-pair ranking or the
four recoders, so they are not CPU timing estimates.

Each of the eight held-out base-point groups of 32 scalars improved:
their source savings were 317, 152, 199, 259, 115, 214, 168, and 248
`M+S`, respectively. This is a complete description of the frozen
fixture, not a confidence interval for other scalar distributions.

Independent Sage group replay recovered all 320 expected points from
the selected streams. The native release build matched all four
cross-language action streams for all 320 cases (1,280 stream checks),
all selected source costs and choices, 2,929 prepared seed points, and
all 320 expected points. Native evaluation observed zero exceptional
cached additions. `native-coset-checks.json` retains the raw build,
regression, replay, and four paired case outputs. The new holdout
fixture SHA-256 is
`2d90d33ab939db8f57a831328efb194cf83ed21d6558db7e87a086312bb1177b`.

The isolated benchmark manifest compares `--benchmark-zero-tau-case`
with `--benchmark-coset-case` on the same 256 base/scalar pairs. It
starts the native clock before decoding the scalar and base and ends
after point recovery and independent expected-point comparison. The
candidate charges ranking all 25 representatives, all four recoders,
chosen seed preparation, evaluation, and final affine conversion.
Neither a physical-host isolation receipt nor paired timing exists, so
CPU speedup is **unknown**. Nearby lattice decompositions and
endomorphism recoding have prior art; academic novelty is also unknown.
