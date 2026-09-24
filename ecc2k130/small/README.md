# Scaled-down ECC2K-130 on Metal

ECC2K-130 is the Koblitz curve `y² + xy = x³ + 1` over `F_2^131`. Its group
order is 4·ℓ with ℓ prime. Below 131 the prime degrees `m` that give the
same shape (a = 0, cofactor 4, prime subgroup) are 41, 83, 97, 103 and
107. `challenges/ecc/curves/f2-koblitz-a0-m{41,83,97,103,107,131}.json`
hold them. These curves have the same endomorphism as ECC2K-130 (Frobenius
σ with σ² + σ + 2 = 0), and rho on them is ECC2K-130's rho run to
completion.

| m | log₂ ℓ | expected iterations √(πℓ/4m) | M4 Pro rate | expected time |
|---|---|---|---|---|
| 41 | 39 | 2^16.6 | — | instant |
| 83 | 81 | 2^37.1 | 619 M it/s | 4 min |
| 97 | 95 | 2^44.0 | 354 M it/s | 14 h |
| 103 | 101 | 2^47.0 | 384 M it/s | 4.2 days |
| 107 | 105 | 2^49.0 | 371 M it/s | 17 days |
| 131 | 129 | 2^60.8 | — | — (kernel stops at m = 127) |

Rates are from `run.py bench` (8192 threads × 16 lanes, threadgroup 64,
GPU time). m ≥ 97 needs four 32-bit words per element, so it is slower
than m = 83.

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
prelude. Apple GPUs have no carry-less multiply, so each 32×32 carry-less product
is built from masked integer multiplies. Inversions are batched per thread (Montgomery's
trick, with Itoh–Tsujii for the one shared inversion).

Five switches select the arithmetic, all on by default. `--arch` sets them, and `bench` and
`microbench` compare them:

- `kara`: Karatsuba products, 6 32×32 products at m ≤ 96 and 9 at m ≤ 127,
  instead of 9 and 16.
- `tables`: normal-basis conversion by 4-bit tables held in threadgroup
  memory, instead of m row parities. With the tables, σʲ(x, y) is a
  rotation of the normal-basis vectors followed by one table conversion
  back. The inversion's long runs of repeated squaring (length ≥ `rotmin`)
  work the same way.
- `sqr32`: squaring spreads bits in 32-bit halves instead of emulated
  64-bit shifts.
- `frobtab`: σʲ goes through the tables (above) instead of 2j squarings.
- `clmul`: selects how a 32×32 product is built. `0` uses 16 64-bit
  products of 4-bit-spaced masks. `1` uses the same masks with explicit
  32-bit `mul`/`mulhi`. `2` (the default) is three 16×16 products
  (Karatsuba) of 3-bit-spaced masks, 27 32-bit multiplies in total. Each
  residue class of a 16-bit operand has at most six bits, so no digit sum
  carries.

`selftest` checks every switch combination against `field.py`.

## Use

Metal needs the real GPU, so run these outside a sandbox.

```sh
make -C ecc2k130/small                      # builds ecc2k130/build/ksmall
python3 ecc2k130/small/run.py selftest challenges/ecc/curves/f2-koblitz-a0-m83.json
python3 ecc2k130/small/run.py solve challenges/ecc/curves/f2-koblitz-a0-m83.json \
    --threads 8192 --batch 16
make -C ecc2k130/small test                 # selftest + solve the m=41 record
```

`selftest` compares products, squares, inverses, normal-basis weights, one
multi-squarings, normal-basis vectors, one walk step and start points from
the GPU against `field.py` (768 checks).
`solve` writes `result.json` in its work directory. It contains the plan
(expected iterations, DP cutoff, parallel overhead), the device's run
statistics and every collision's solution.

## Performance

`run.py microbench` times dependent chains of each operation on the whole
GPU. `run.py bench` times the full walk. Both accept `--arch` more than
once to compare variants. Measured on the M4 Pro at m = 83, in millions
per second:

| arithmetic | mul | sqr | inv | to normal basis | walk (M it/s) |
|---|---|---|---|---|---|
| baseline (all switches 0) | 2,939 | 14,032 | 144 | 1,844 | 247 |
| optimized (defaults) | 4,982 | 27,590 | 528 | 7,177 | 617 |

What each switch contributes:

- `sqr32` doubles squaring.
- `kara` multiplies product throughput by 1.47×, and `clmul=2` (16-bit
  halves with 3-bit masks, 27 integer multiplies per 32×32 product
  instead of 32) adds another 1.19×.
- The tables make normal-basis conversion 3.6× faster and inversion 3.3×
  faster.
- `frobtab` is slower than squaring in isolation at a fixed j. It wins in
  the walk (781 vs 612 M/s for the fused step's field work), because j
  varies across a SIMD group and the squaring loop runs to the group's
  largest j.

`clmul=1` (explicit `mulhi`) is slower than letting the compiler form the
64-bit products: 3,062 M/s vs 4,195.

Lane geometry at m = 83 (M it/s at threadgroup 32 / 64 / 128):

| threads × lanes | 32 | 64 | 128 |
|---|---|---|---|
| 8192 × 16 | 604 | 617 | 563 |
| 8192 × 32 | 604 | 612 | 554 |
| 16384 × 8 | 575 | 595 | 573 |
| 4096 × 32 | 492 | 490 | 489 |

The raw results are in `evidence/bench-*.json`. `evidence/m83-solve.json`
is the first m = 83 solve, on the baseline arithmetic (894 s).
`evidence/m83-solve-optimized.json` is an independent re-solve from other
seeds on the optimized arithmetic: same log, 114 s at 615 M it/s.
