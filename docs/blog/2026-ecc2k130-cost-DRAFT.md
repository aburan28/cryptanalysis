# DRAFT — What does breaking ECC2K-130 cost in 2026?

*Status: draft for Isogeny Labs' blog. Not for publication until the checklist
at the end is done. Every number cites a file in this repository or a
published paper.*

In 1997 Certicom posted a ladder of elliptic-curve discrete-logarithm
challenges. The smallest one nobody has solved is **ECC2K-130**: a Koblitz
curve y² + xy = x³ + 1 over F_{2^131}, with a 130-bit prime-order subgroup.
In 2009 a 23-author team worked out exactly what solving it would take
(Bailey et al., ePrint 2009/541): about **2^60.9 iterations** of Pollard's rho
method, using the curve's Frobenius map to shrink the search by √262. They
built implementations for CPUs, PlayStation 3s, GPUs and FPGAs. The hardware
of the day put it at "less than 2,700 PlayStation 3s for one year" (Bos et al.,
ePrint 2010/077). On the GPU side, one GTX 295 did about 63 million iterations
per second (ePrint 2012/002).

It was never finished. Seventeen years later we asked what it costs now.

## The hardware changed in one specific way

Binary-field arithmetic is multiplication of polynomials over F_2: shifts and
XORs, with no carries. CPUs have had a carry-less multiply instruction for
over a decade (PCLMULQDQ); GPUs had none. The 2010 GPU implementation
therefore "bitsliced": it processed 32 independent walks one bit at a time
through logic operations.

In CUDA 13.3 (July 2026), NVIDIA exposed **`clmad`**, a 64×64-bit carry-less
multiply-add, on every GPU since Ampere. NVIDIA's announcement benchmarked
AES-GCM hashing and zero-knowledge sum-checks. We pointed it at ECC2K-130.

## What we measured

On one NVIDIA RTX PRO 6000 Blackwell, walking the exact iteration function
of Bailey et al. (so every distinguished point is compatible with theirs):

| | iterations / second | source |
|---|---:|---|
| 2009-style bitsliced kernel, same GPU | 0.85 B | `ecc2k130/runner/PACKED.md` |
| packed polynomial basis + `clmad` | 14.6 B | `paper/sec-ecc2k-gpu.tex` |
| + 640-thread blocks, 4-warp shared inversion, fused Frobenius | **17.6 B** | `ecc2k130/runner/research/FROBENIUS-FUSION.md` |
| GTX 295 (2010) | 0.063 B | ePrint 2012/002 |

Per card, that is about **280× the 2010 GPU**. Per SM clock cycle, one
iteration went from roughly 1,180 cycles to about 25 (188 SMs at about 2.36 GHz). On the same GPU, native
carry-less multiply beats 2009-style bitslicing by about 20×.

## So what does it cost?

At 2^60.9 ≈ 2.15 × 10^18 iterations:

- **one GPU at 17.6 B/s: about 3.9 GPU-years**, i.e. about 34,000 GPU-hours.
  The 2010 card would have needed about 1,080 GPU-years.
- **our 8-GPU fleet at 138.9 B/s: about 180 days** of expected work.
- **cloud cost: tens of thousands of dollars.** The repo's own estimate is
  about $56k at a $1.31/GPU-hour spot price (`aws/README.md`, computed at the
  older 14.1 B/s collecting rate). Rho's running time is random, so budget
  about 1.5× the mean for 83% confidence.

A 130-bit binary-field discrete log has moved from "a coordinated academic
consortium" to "a small company's cloud budget". None of this threatens
deployed cryptography: 130 bits is far below any standard curve, and binary
Koblitz curves at this size were never recommended. It is a concrete data
point for how fast "safe for a decade" erodes when the hardware gains one
instruction.

## What we are not claiming

- We have not solved ECC2K-130. About 2^55.3 of the expected 2^60.9
  iterations are done, and no collision has been found. That is the expected
  state.
- No new algorithm. The exponent is still √n; everything here is constant
  factors.
- A faster "table walk" on the same GPU reaches 22.1 B/s, but its
  fruitless-cycle behaviour is not yet validated. We do not use it in this
  post (`docs/papers/ecc2k130-blackwell/REVIEW-20260926.md`).

## Checklist before publishing

- [ ] Re-measure the 17.6 B/s figure on the current build and state the
      collecting-mode rate alongside the benchmark rate.
- [ ] Recompute the dollar cost at the current spot price, at the 17.6 B/s rate.
- [ ] Fix stale pages that contradict this post: `crypto/docs/performance-gains.html`
      and `crypto/hdl/ecc2k130/README.md` (the latter still says the GPU runs at 6.9 G/s).
- [ ] Decide what to say about the live campaign, e.g. a public progress page.
- [ ] Link the ePrint paper once it is posted.
