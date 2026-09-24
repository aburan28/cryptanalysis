# Scaled-down ECC2K-130 on Metal

ECC2K-130 is the Koblitz curve `y² + xy = x³ + 1` over `F_2^131`. Its group
order is 4·ℓ with ℓ prime. Below 131 the prime degrees `m` that give the
same shape (a = 0, cofactor 4, prime subgroup) are 41, 83, 97, 103 and
107. `challenges/ecc/curves/f2-koblitz-a0-m{41,83,97,103,107,131}.json`
hold them. These curves have the same endomorphism as ECC2K-130 (Frobenius
σ with σ² + σ + 2 = 0), and rho on them is ECC2K-130's rho run to
completion.

| m | log₂ ℓ | expected iterations √(πℓ/4m) | M4 Pro at 262 M it/s |
|---|---|---|---|
| 41 | 39 | 2^16.6 | instant |
| 83 | 81 | 2^37.1 | ~10 min |
| 97 | 95 | 2^44.0 | ~19 h |
| 103 | 101 | 2^47.0 | ~6 days |
| 107 | 105 | 2^49.0 | ~25 days |
| 131 | 129 | 2^60.8 | ~600 years |

## The walk

It is the ECC2K-130 walk: `R ← R + σ^j(R)`, with `j = 3 + (HW(x)/2 mod 8)`.
`HW` is the Hamming weight of `x` in a normal basis. `HW` is unchanged by
Frobenius and negation, so the walk acts on the 2m-element classes
`{±σ^i R}` and saves the factor √(2m). A point is distinguished when
`HW(x)` falls at or below a cutoff. Each class is keyed by the smallest
rotation of its normal-basis `x`.

The kernel does not track scalars. Each lane counts how many times it took
each `j`. A reported point is `∏(1+λ^j)^count_j · (u·P + Q)`, where λ is σ's
eigenvalue mod ℓ and `u` comes from the start point
`Q + Σ σ^{e_k}(P_k)`, with twelve bases `P_k = r_k·P`. With six bases
there are only 83⁶ ≈ 2³⁸ start points at m = 83. A full run uses about 2²¹
of them, so a few repeat, and the first m = 83 run stopped on two seeds
that walked the same trail. The host now drops a match whose two records
have the same point, length and j counts (`sameStartTrails`). `run.py`
checks this identity for both points of every
collision before it solves
`c_a(u_a + k) = ±λ^s c_b(u_b + k)` for `k`. It then verifies `k·G = target`
in the challenge file's own field with `challenges/ecc/generate.py`'s
scalar multiplication, which is independent of this directory.

## Field

The kernel works in F_2[z]/(f) with f a sparse polynomial whose middle terms
are ≤ m − 33, so reduction is a word-at-a-time fold (m = 83 uses
`z^83 + z^7 + z^4 + z^2 + 1`). The challenge files use other polynomials.
`field.py` finds a root of the file's polynomial (Cantor–Zassenhaus) and
maps the points across. The kernel supports any m ≤ 127 via a generated
prelude. Apple GPUs have no carry-less multiply, so 32×32 products use
masked integer multiplies. Inversions are batched per thread (Montgomery's
trick, Itoh–Tsujii for the one inversion).

## Use

Metal needs the real GPU, so run these outside a sandbox.

```sh
make -C ecc2k130/small                      # builds ecc2k130/build/ksmall
python3 ecc2k130/small/run.py selftest challenges/ecc/curves/f2-koblitz-a0-m83.json
python3 ecc2k130/small/run.py solve challenges/ecc/curves/f2-koblitz-a0-m83.json \
    --threads 16384 --batch 8
make -C ecc2k130/small test                 # selftest + solve the m=41 record
```

`selftest` compares products, squares, inverses, normal-basis weights, one
walk step and start points from the GPU against `field.py` (640 checks).
`solve` writes `result.json` in its work directory. It contains the plan
(expected iterations, DP cutoff, parallel overhead), the device's run
statistics and every collision's solution.

Throughput at m = 83 on the M4 Pro: 16384×8 lanes 262 M it/s, 8192×16
260, 8192×8 225, 32768×4 222, 4096×32 200.
