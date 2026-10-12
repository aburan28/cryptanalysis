# Endomorphism-assisted width-four seed preparation

The protocol and source were frozen in commit `78e5f97b` before deriving
64 new one-use secp256k1 base/scalar pairs. The checked repository Sage
launcher reported `status: verified`; the receipt is
`endo-seed-runtime-info.json` (SHA-256
`073ca37250b100a7f961de3475da8a4d489f3f2140c15f4c72457816893f3f01`).
The fresh input digest is
`45397165abf83b8bfd9161f512d860a569aacaa4f87cd227ec61234c461dc2fe`.
All case inputs, prepared-point digests, evaluator counts, and output points
are in `endo-seed-result.json`.

For every base, both chains produced **the same nine affine seed points**.
Each seed was independently checked as its declared `aP+bτP` point, and
both complete scalar evaluations matched Sage. Their width-four digits,
unit orbits, paired strides, and online operation counts were identical
on all 64 cases.

| Generic source count, 64 one-use scalars | Existing chain | Endomorphism-assisted chain |
| --- | ---: | ---: |
| Preparation multiplications | 6,528 | 6,144 |
| Preparation squarings | 2,752 | 2,560 |
| Preparation inversions | 64 | 64 |
| Online multiplications | 49,124 | 49,124 |
| Online squarings | 27,100 | 27,100 |
| Complete `M+S`, inversion separate | **85,504** | **84,928** |

The replacement saves **6M+3S per one-use scalar**, or 576 `M+S`
across the 64 cases (0.674% of the old complete count), with the same
inversion. The fixed per-case saving needs no rate extrapolation; it is a
source-level arithmetic identity for this chain. It excludes recoding,
allocation, exceptional paths, and wall time. The candidate does not
claim a native or host-isolated CPU speedup.

The key identities are `(1+τ)P=2P−ω(P)` and
`(1−2τ)P=ω(2P)−P`. They replace the old `τP+P` and a generic
Jacobian/Jacobian add with two mixed additions and two charged field
rotations. They are straightforward algebraic rewrites of published
`τ=1−ω` arithmetic, **not a demonstrated academically novel method**.
The [Xu et al. width-four algorithm](https://eprint.iacr.org/2024/1906)
remains the control. A native complete-operation comparison, with the
field inversion cost and selection/recoding included and an isolated
host receipt, is required before any speed claim.
