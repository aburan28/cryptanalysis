# Carry-aware orbit recoding reduces norm-seven branch activation

A width-two carry-aware recoder reuses the fixed radix-1024, 67,338-seed
cover and chooses among its exact seed/map/unit representations. On a frozen,
disjoint panel of 4,096 secp256k1 scalars, the recoder used a nonzero
`rho=1+tau` digit for **2,846** scalars versus **3,062** with the fixed
priority assignment. It used 4,679 versus 5,345 rho-mapped full-window
digits. Every selected digit sequence reconstructed its scalar, met the
terminal bound, and passed the independent certificate verifier.

## Scheme and correctness

For an Eisenstein representative `A+B*tau`, a radix-1024 digit `d` is valid
when both coordinates of `d` match the current pair modulo 1024. Different
valid digits in one residue class produce different exact integer quotients
`(A-d.a)/1024, (B-d.b)/1024`. The recoder carries two candidate quotient
states through twelve windows and ranks them by (any rho map, rho-term count,
nonzero-term count, quotient norm). It chooses the better admissible complete
path against the fixed priority path, which remains a fallback.

The selected path satisfies the exact identity

`(A,B) = sum_{i=0}^{11} 1024^i * d_i + 1024^12 * (A_12,B_12)`.

Thus evaluating the precomputed point for each selected digit and the exact
terminal point yields `[A+B*lambda_tau]G`. The holdout verifier independently
checked every digit against its encoded seed, map, and unit; the congruence
against each supplied scalar modulo the secp256k1 subgroup order; the
terminal norm `<149^2`; and the endomorphism eigenvalue on the generator.
The fixed-path fallback preserves the original cover's totality.

## Paired panels and search work

| Frozen panel | Policy | Scalars with rho | Rho digits | Nonzero full-window digits | Offers examined |
| --- | --- | ---: | ---: | ---: | ---: |
| Observed design, 4,096 scalars | Fixed priority | 3,044 | 5,324 | 49,152 | 49,152 fixed lookups |
| Observed design | Carry-aware width 2 | 2,829 | 4,695 | 49,152 | 113,811 |
| Disjoint holdout, 4,096 scalars | Fixed priority | 3,062 | 5,345 | 49,152 | 49,152 fixed lookups |
| Disjoint holdout | Carry-aware width 2 | **2,846** | **4,679** | 49,152 | **113,623** |

The holdout has 216 paired rho-activation improvements and zero regressions
under the frozen lexicographic selector, a 5.27-percentage-point reduction in
this panel. If the deterministic pseudorandom fixture is modeled as
independent uniform draws, the Wilson 95% interval for the improvement
fraction is 4.63% to 6.00%. The rho-digit
count fell by 666 (12.46%). No selected terminal exceeded the bound, and
the maximum terminal norm was 21,744. The search examined 27.74 offers per
scalar, compared with 12 fixed lookups; native recoding cost therefore needs
to be charged before drawing a runtime conclusion.

The earlier tau-only carry-choice screen (commit `2ba49f8`)
found alternate paths and fewer gauge rotations but no change in mixed
addition count. This construction searches the four-map priority cover and
targets activation of the norm-seven branch; its full-window nonzero-term
count also remains 49,152. The observed change is in map selection and its
bucket combination.

Including the exact terminal codes, phase occupancy predicts 20,517 gauge
rotations for fixed priority and 20,941 for width two on the holdout: **424
additional fixed-constant products**. The same accounting reproduces the
prior native priority count of 20,579 rotations exactly on its own frozen
panel. The direct-XYZZ-rho source-call model assigns 9 general
multiplications, 5 squarings, and 2 fixed-constant products to one
nonidentity rho call; a gauge rotation uses one fixed-constant product.
Across the 216 removed rho activations and 424 additional rotations, that
isolated subpath has a nominal delta of `-1,944M -1,080S -8C`. This excludes
the online offer search and other point-evaluator effects.

On the design panel, beam widths 1, 2, 4, 8, and 16 had active-rho counts
2,939; 2,829; 2,828; 2,828; and 2,828, respectively. Width 2 captured
215 of the 216 improvements available in that bounded width screen while
using 113,811 offers versus 167,402 at width 4. The width-two choice and
source SHA-256 `1c413c4d4b3b014e8e0530f689a0a37f1ee937788fba1f36930f937d04f8274c`
were fixed in the holdout input receipt before its replay.

The selected seed set has 246,429 seed/map offers across 174,764 classes.
Some boundary residues admit multiple valid unit images of one offer; the
index retains all **246,451** seed/map/unit records. It uses four-byte class
offsets and eight-byte records: **2,670,684 bytes** including its header.
Its SHA-256 is `caa0218ae73daa40645701963e198515c76e288caf1ae05e5b74e8ebadea3b8b`.
The independent index verifier checked all 174,764 canonical classes and
1,048,576 exact residues, including every inverse unit transform. Adding
this asset to the existing 54,339,936-byte native table projects
57,010,620 retained bytes, within the 64 MiB budget. The native evaluator
loads this index and checks its retained byte count.

The native beam compares quotient norms exactly without a multiprecision
square for each offer. Each full-window digit has Eisenstein norm at most
`R^2`, where `R=1024`, so its coordinates obey `|a|<=2R` and
`|b|<=2R/sqrt(3)`. Two valid paths starting from the same representative
therefore differ after any positive window by integer carries `da`, `db`
with `|da|<=4` and `|db|<=2`: sum the bounded digit differences as a
geometric series in `1/R`. For `Q(a,b)=a^2+3ab+3b^2`, the exact difference
between `Q(a+da,b+db)` and `Q(a,b)` is

`a(2da+3db) + b(3da+6db) + da^2+3da*db+3db^2`.

Three signed 192-bit limbs suffice for the exact comparison on these
representatives. The native implementation asserts the carry bounds and
overflow bounds at runtime.

## Reproduction and next implementation step

- [PROTOCOL.md](PROTOCOL.md) defines the screen and promotion gates.
- [holdout-inputs.json](holdout-inputs.json) contains the source-panel
  digests and deterministic disjoint scalar stream.
- [holdout-screen-width2.json](holdout-screen-width2.json) records the
  fixed/selected counts, offer work, and source/cover/input hashes.
- [holdout-paths-width2.jsonl](holdout-paths-width2.jsonl) records every
  selected path; [holdout-verify.json](holdout-verify.json) binds its digest
  and independent verifier outcome.
- [offer-index-check.json](offer-index-check.json) records the exhaustive
  class and residue verification of the compressed offer asset.
- [phase-cost.json](phase-cost.json) records the paired gauge-phase and
  bucket-activation counts with the exact terminal atlas.

The next experiment is a paired end-to-end benchmark on a host that passes
the repository's isolation gate. The algebraic and operation-count result
is verified; online wall-time speedup remains unknown.
