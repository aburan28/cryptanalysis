# Fresh secp256k1 width-four recoding control

This is a **published-method control**, not a new algorithm. Reuse the
nine coefficient seeds and complete 54-class modulo-`τ⁴` digit table
from `experiments/prime-j0-cost-aware-chain/run.py`, which follows the
unit-invariant width-four construction in Xu, Yu, Han, and Lu, Section
4.2. Reduce each scalar to the same short `(a,b)` lattice pair for all
arms, then derive the width-four stream and verify exact expansion.

Evaluate three arms on eight fresh secp256k1 subgroup bases and sixteen
fresh scalars per base, fixed by the source SHA-256 input label:

1. Existing dense unit-digit recoding with its local carried-gauge
   paired-stride evaluator.
2. Width-four stream with one ordinary Jacobian `τ` step per position
   and generic mixed addition of a prepared affine seed point.
3. The same width-four stream with the existing local carried-gauge
   policy and legal paired strides. This tests whether the previously
   studied projective policy remains useful on a sparse stream; both
   unit-invariant preparation and tripling strides have prior art.

For each base, prepare the nine affine seed points `s_a P+s_b τP` with
Sage group operations **outside** the evaluator. This is a correctness
prototype; the seed-point preparation cost is retained as an excluded
stage and no full-scalar or one-target timing claim follows. A nonzero
digit selects one seed, a power of `ω`, and a sign. The evaluator must
agree with Sage's independent `kP` in all three arms.

Record both nominal multiplication and squaring counts for the
explicit generic formulas. One normal `τ` step is `4M+2S`; one
paired stride is `6M+4S` when its Z scale is a negation and `7M+4S`
otherwise; one mixed addition after initialization is `8M+3S`;
the first addition from infinity is free. Count nontrivial seed-point
rotations and final gauge correction as one `M` each. Also report
`M+S` under `S=M`. These counts exclude exceptional paths, setup,
recoding, normalization, inversion, memory traffic, and all runtime
overhead. Preserve per-case raw rows and source hashes. No CPU speedup
may be claimed without a full native run and host isolation receipt.

Freeze this file and `compare_width4.py` before deriving inputs. Save
the checked Sage runtime receipt, then run:

```sh
/Volumes/SSD990/cryptanalysis/sage --runtime-info > experiments/prime-j0-secp256k1-scalar/width4-runtime-info.json
/Volumes/SSD990/cryptanalysis/sage -python experiments/prime-j0-secp256k1-scalar/compare_width4.py
```
