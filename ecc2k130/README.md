# A GPU Pollard rho client for ECC2K-130

A CUDA walker for the Certicom ECC2K-130 challenge -- the Koblitz curve
`y² + xy = x³ + 1` over `F_{2¹³¹}` -- measured at **20.08 billion iterations
per second on one RTX PRO 6000 Blackwell**, with a host test that holds its
arithmetic to this repository's golden model and a re-walk that checks what
the device reports.

**What is verified and what is not.** The field arithmetic, the Frobenius
networks, the basis conversions, the table walk's selection and the walk
itself are checked bit for bit against `fpga/model/ecc2k130.c` (`make test`,
1,904 checks, gcc and clang in CI). Every report the device makes is a
64-byte record that `--verify N` re-walks from its seed on that model; the
measured run below re-walked 300 of 300. The rate is a measurement on one
card, in the geometry and with the compiler named below; CI compiles the
kernel with that compiler and reports registers and spills, but no runner
has the card, so only a card reproduces the number.

## Where the kernel comes from

The device code in `include/` is imported from
[aburan28/crypto](https://github.com/aburan28/crypto) `ecc2k130/` (branch
`ecc2k130-l1-geometry-and-tag-denominator`, `b8ed2f5`), where it was
developed and where its history, its many build-time knobs and the notes
that priced them live. What is imported is exactly the configuration that
measured 20.08 B/s; the other backends, the Modal integration, the
checkpointing and the resolver stay there. The generated headers
(`packedtransform131.h`, `packed*reduce131.h`, `packedgeneratedproduct131.h`,
`packedsigma131.h`) come from that repository's code generator and are not
edited here. Two small headers (`bitslice.h`, `kernel.h`) replace the source
tree's larger ones with just what the packed kernel uses, kept bit-for-bit
compatible so a report re-walks under either tree's reference.

This repository's part is the host: `src/ec2k_gpu.cu` drives the kernel,
`src/hostcheck.{h,cpp}` is the bridge to the golden model -- the
representation is the same permuted type-II normal basis, coefficient `i` of
`β_i` at bit `i−1`, so a value moves between the two by re-slicing its words
and every check is equality, not equivalence up to a basis change -- and
`src/hosttest.cpp` is the test CI runs.

## The walk

```
h(R)  = (HW(x) / 2) mod 8                            branch
k(R)  = (Σ_e L(e) x_e) · HW(x)⁻¹  mod 131            Frobenius phase
ε(R)  = bit p(R) of y,  p = argmax_{e ∈ supp x} (L(e) − k) mod 131
R'    = R + (−1)^ε · σ^{k}(T_h),   T_h = [a_h]P + [b_h]Q
```

an r-adding walk on the classes of `⟨σ, −1⟩` (262 points each): `k` shifts
by one under `σ` and `ε` flips under negation, so `f(σR) = σf(R)` and
`f(−R) = −f(R)` and the walk descends to classes with no canonical
representative in the loop. `L(e)` is the discrete log base 2 of the folded
coordinate index in `(Z/263)*/±1`; the table `σ^k(T_h)` (131 × 8 points,
48.7 KB) sits in shared memory. Fruitless 2- and 4-cycles are avoided by
advancing `h` against the last four step tags. A point is distinguished when
`HW(x) ≤ 34`. This is a different iteration function from the FPGA core's
`σ^j(R) + R`; the two share the field, the model and the 32-byte record
(`--dp-file32`, which `fpga/host/ec2k merge` reads) but not a corpus.

One step is one affine addition. Coordinates are stored in the polynomial
basis `F_2[c]/(m)`, `c = γ₁`, where a 131-bit product is three 64×64
carry-less multiplies -- six `clmad` -- plus a 78-instruction reduction; the
Bernstein–Lange conversions to and from the normal basis (where the weight,
the selection and the distinguished-point test live) are `O(K log K)`
shift-and-mask networks. Sixteen walks per thread share one inversion by
Montgomery's trick: a forward pass accumulates the denominators' prefix
products, one Itoh–Tsujii inversion (eight products), a reverse pass peels
the inverses off and completes the additions.

## Boundary and measurement

Unit: billions of complete iterations per second on one RTX PRO 6000
Blackwell Server Edition (188 SMs, 128 MB L2, 80 MiB persisting-L2 window,
2.32–2.42 GHz under load, well under its 600 W limit), CUDA 13.3.73, `sm_120`,
`bench --steps 1024 --launches 64` at the automatic thread count (96,256
threads × 16 slots = 1,540,096 walks).

**Floor:** the carry-less unit. Measured here, `CLMAD.LO`/`CLMAD.HI` issue at
1.62 lane-operations per SM-clock regardless of resident warps, spacing or
operand width, with a 60-cycle latency and one issue per ~63 cycles per warp;
ALU work co-issues at no cost. An iteration is 33.1 `clmad` (28.9 in its 4.81
products, 3.0 in the inversion's eight products, 1.25 in the inversion's
squarings), 20.4 SM-clocks, **22.3 B/s at 2.42 GHz with the unit never
idle.** No row below changes that count; each is engineering, its ratio to
the floor bounded above by 1.

| configuration | B/s | / floor | verified |
|---|---:|---:|---|
| the source tree's shipping walk (`σ^j(R) + R`, audited preset), rebuilt here | 14.00 | 0.63 | its receipts |
| its best table-walk configuration (256 threads × 2 blocks per SM), rebuilt here | 17.41 | 0.78 | its receipts |
| + one block of 512 threads per SM | 19.14 | 0.86 | 300/300 |
| + denominators rebuilt from the step tag (`TABLE_TAG_DENOM`) | 19.43 | 0.87 | 300/300 |
| + products inlined (`INLINE_POLY=3`, slot unroll 1) | 19.87 | 0.89 | |
| + forward pass software-pipelined, chain product first, reduced conversion | **20.08** (5 × 64 launches: 20.077–20.080) | **0.90** | **300/300** |
| the same, `walk --dp-weight 34` collection | 19.04 | | |
| this client, `bench` (same kernel, this host) | parity with the source binary within 0.2%, A/B under identical load | | 300/300, 470,921 records, 0 malformed in `ec2k merge` |

Three things account for the +15.3% over the source tree's best row, and the
tree's own static profile had priced all three as impossible because it put
the ALU pipe at 96–100%; the card's counters said 36–39%, carry-less unit
63–71%, and a `clock64()` phase profile built into the kernel located the
idle time:

- **Geometry.** `__launch_bounds__(512, 1)` in place of `(256, 2)`: same SASS,
  same 16 warps per SM, but one copy of the 48.7 KB walk table in shared
  memory leaves 64 KB of L1 instead of 28. +9.4%.
- **No denominator field.** The reverse pass needs `d = x + x_T` and was
  reloading the 17 bytes the forward pass stored; the low 16 bits of the
  history word it must read anyway are this step's tag, from which `x_T` is
  one shared-memory read. −34 bytes per iteration, and the state fits the
  persisting-L2 window. +1.5%.
- **Feeding the unit during the selection.** The twelve `clmad` of a slot sat
  behind a `__noinline__` call and the ~900 cycles of table lookups ran after
  it returned, with nothing queued on the unit. Inlining the products and
  issuing slot *k*'s products before slot *k+1*'s selection (chain product
  first, its partner's reduction deferred by a slot) recovered most of that.
  +3%.

The remaining tenth is the inversion: a chain of eight dependent products
with a basis conversion and a Frobenius network between each, 30,000 cycles
per warp per 16 slots for 68 `clmad`, which the other three warps on the
scheduler are in at about the same time. Splitting the batch costs a second
inversion (+13% on the binding unit); a polynomial-basis inversion needs
Frobenius tables that do not fit beside the walk table. The source tree's
`ONE-BLOCK-GEOMETRY.md` has the full table of what was tried, including what
did not pay.

## Running it

```sh
make                         # host test against the golden model (no CUDA)
make gpu                     # needs nvcc >= 13.3 for clmad; ARCH defaults to sm_120
make gpu NVCC=$(scripts/fetch_cuda.sh)/bin/nvcc     # CUDA 13.3 from NVIDIA's pip wheels
make bench                   # bench --steps 1024 --launches 64
make verify                  # walk at dp-weight 46, 300 reports re-walked on the model

build/ec2k-gpu walk --run-id 7 --dp-file dps.bin --dp-file32 dps32.bin --verify 100
build/ec2k-gpu check --rounds 256                    # the host test, from the client binary
```

`bench` counts iterations with no lane ever reporting. `walk` collects: at the
campaign's weight 34 a lane reports about once in 2²⁵ steps, so a 1024-step
launch of 1.5 M walks yields ~40 records; `--dp-weight` relaxes it for tests.
A lane that reports is revived from its incremented seed between launches
(`--run-id` is the high 16 bits of every seed; two runs with different ids
never share a trail). `--max-iters N` restarts lanes that have walked `N`
steps without reporting. The base and target points come from `--p-seed` and
`--q-seed` through `ec2k_point_from_seed`; the published challenge points
belong in a campaign definition and are passed in the same way.

`--threads` must be a multiple of 256 (the compact state layout's tile); the
default is one wave of resident blocks. The GPU is shared fairly between
processes, so a benchmark on a card that is also collecting measures half of
it -- the A/B row above was taken that way, against the source binary.

## What is not here

- **Coefficient tracking and the solve.** As in the FPGA core, a walk is
  identified by its seed and a collision is resolved by re-walking both trails
  with coefficients -- the source tree's resolver does that with its
  `TableWalk`; here the re-walk exists (`rewalk` in `hostcheck.h`) and the
  coefficient bookkeeping does not.
- **Checkpointing.** A stopped run loses its lanes' unreported prefixes (about
  a quarter of the work in flight); the source tree checkpoints, this client
  does not yet.
- **Multi-GPU.** One process, one device; run one per device with distinct
  run ids and merge the corpora.
- **A rate on any other card.** `clmad` exists from sm_80; the geometry
  (one 512-thread block, 64 KB L1, an 80 MiB persisting window) is tuned to
  this one, and the automatic thread count and `--threads` are where another
  part's tuning starts.
