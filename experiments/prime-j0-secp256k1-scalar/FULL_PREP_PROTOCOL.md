# Single-use variable-base width-four preparation control

This run closes the main arithmetic-accounting gap in the previous
width-four panels. Each of 32 fresh secp256k1 bases is used for
exactly one fresh full-width scalar. No seed or orbit table is shared
between cases. The SHA-256 input label is frozen in `full_prep.py`.

For each base, construct the nine published coefficient points in
the order `(1,0), (2,0), (4,0), (1,1), (2,2), (1,2), (2,4),
(2,1), (1,-2)` in the `(1,τ)` basis. Use explicit Jacobian doubling,
ordinary τ, mixed addition, and one general Jacobian addition:

1. `2P`, `4P`, and `(1+τ)P = τP+P`;
2. `(2+2τ)P = 2(1+τ)P`, `(2+τ)P = (1+τ)P+P`,
   `(1+2τ)P = (2+2τ)P−P`;
3. `(2+4τ)P = 2(1+2τ)P`,
   `(1−2τ)P = 2P−(1+2τ)P`.

Batch-normalize the eight constructed Jacobian points with one field
inversion. Compare every resulting point with an independent Sage
group expression before using it. Prepare the three `ω` images of
each affine point, recode the scalar using the checked width-four
table, evaluate the prepared-orbit paired-τ path, and compare the
output with Sage's `kP`.

The declared generic-path arithmetic boundary is:

| Stage | Field multiplications `M` | Field squarings `S` | Inversions `I` |
| --- | ---: | ---: | ---: |
| Nine-point Jacobian chain | 48 | 35 | 0 |
| Batch normalize eight points | 45 | 8 | 1 |
| Prepare nine unit orbits | 9 | 0 | 0 |
| **Single-use preparation** | **102** | **43** | **1** |

The chain count uses `4M+2S` for ordinary τ, `2M+5S` for each
of four doublings, `8M+3S` for each of three mixed additions, and
`12M+4S` for one general Jacobian addition. Batch inversion uses
seven prefix, seven reverse-output, and seven reverse-update
multiplications, followed by `3M+1S` to normalize each of eight
points. This count is tied to the actual source expressions, including
field multiplication by coordinate one. It is not the paper's
optimized shared `2P`/`ρP` precomputation formula. One inversion
remains a separate unit; do not silently set it to zero or equate it
to one multiplication.

For each row, report the evaluator `M`, `S`, and generic `M+S`
alongside the preparation `M`, `S`, and `I`. A full conversion to
wall time requires a native field backend, inversion calibration,
recoding and table costs, exceptional-path accounting, and a
host-isolated receipt. This is an arithmetic and correctness
prototype, not a CPU speedup or academic novelty claim.

Freeze this protocol and `full_prep.py` before deriving inputs. Save
the checked Sage runtime receipt, then run:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-scalar/full-prep-runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-scalar/full_prep.py
```
