# Per-scalar τ alphabet selection: fresh validation

The protocol and source were frozen in commit `f1bb8830` before the new
inputs were generated. The checked repository Sage launcher reported
`status: verified`; its runtime receipt is
`adaptive-mask-runtime-info.json` (SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`).
The fresh 64-pair input digest is
`00fff9ecf866caae832aabefce8fce0332b0c20a6a018eb16a880f6c3ce49e95`.
All mask costs, complete per-arm counts, prepared-point hashes, and verified
point outputs are in `adaptive-mask-result.json`.

Every selected and width-four arm constructed only its needed seed points,
normalized those used with one batch inversion, and independently matched
Sage's secp256k1 scalar product. The source-count model agreed with the
actual point construction and evaluation counts on all 64 cases.

| Fresh 64 one-use base/scalar pairs | Per-scalar selected mask | Width four |
| --- | ---: | ---: |
| `M+S` excluding inversions | 83,880 | 85,279 |
| Field inversions | 64 | 64 |
| Constructed nonbase seed points | 361 | 506 |
| Digit additions | 2,433 | 2,311 |
| Paired τ strides | 4,574 | 4,794 |

The modeled arithmetic saving is **1,399 `M+S`**, or **21.86 per scalar**
and 1.64% of the width-four count. Per-case savings were 0–55, positive in
62 of 64 cases, with median 20.5. A descriptive 10,000-resample paired
bootstrap with seed `0x20261007` gives a mean-saving 95% interval of
18.97–24.92 `M+S` over this input law. This is uncertainty about the
input distribution, not CPU timing uncertainty.

The selector evaluated all 64 masks and processed **655,394 recoded
positions**, compared with 10,168 positions in the width-four arm. Thus it
performs roughly 64.5 times as many recoder positions to save 21.86 field
operations per scalar. It also scores all 64 chains and tracks their seed
sets. None of those integer, branch, lookup, memory, or allocation costs is
charged in the table. This exhaustive selector is **not promoted** as a
faster scalar multiplier.

As a follow-up screen, we chose a small mask portfolio using only the
earlier fixed-hybrid holdout cases, greedily starting from mask 63. Reading
the already-generated fresh costs afterward gave the following *retrospective*
portfolio diagnostics; these are not a separately preregistered experiment:

| Masks searched | Frozen masks | Fresh saving per scalar, `M+S` |
| ---: | --- | ---: |
| 2 | 63, 30 | 6.05 |
| 3 | 63, 30, 3 | 8.64 |
| 4 | 63, 30, 3, 47 | 9.73 |
| 8 | 63, 30, 3, 47, 22, 7, 31, 13 | 15.58 |
| 64 | 0 through 63 | 21.86 |

This points toward a lower-cost selector, perhaps a shared-state recoding
graph or a tiny portfolio, but the additional scalar-processing cost still
needs to be charged. The 64 recodings visited 27,851 distinct
`(position, a, b)` states across the fresh panel, a 23.5-fold overlap in
states. A shared-state implementation could reuse transitions, while
selection and path-cost accumulation remain work to measure.

There is substantial published prior art for combining point tripling with
digit addition, including [Dimitrov, Imbert, and Mishra's double-base-chain
paper](https://eprint.iacr.org/2005/069). The [Explicit-Formulas
Database](https://www.hyperelliptic.org/EFD/g1p/index.html) catalogs the
relevant point arithmetic. The present adaptive alphabet rule is an
algorithmic diagnostic, **not an academic novelty claim**. Native complete
operation timings on an isolated host are required for a CPU speedup claim;
both `cpu_speedup_claim` and `academic_novelty_claim` remain `null`.
