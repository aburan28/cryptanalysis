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
make                         # host tests against the golden model (no CUDA): kernel and CPU walker
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

## The same walk without the card: `ec2k-cpu` and `ec2k-metal`

Two clients run this walk where there is no CUDA device.  They are built from
the same headers, take their start points from the same seeds and their
addends from the same table, and write the same 64- and 32-byte records, so a
report from any client re-walks on the model and merges with any other's.
They exist to develop and test a campaign's pipeline -- reports, `--verify`,
`ec2k merge`, ingest -- on the machine in front of you; the throughput of the
campaign is the card's.

| client | engine | measured on an M4 Pro (10P + 4E cores, 20-core GPU) |
|---|---|---:|
| `ec2k-cpu` | worker threads, 64-bit limbs, products on PMULL | 139-159 M it/s, 14 workers |
| `ec2k-cpu`, one worker | | 18.6 M it/s (53.5 ns an iteration) |
| `ec2k-metal` | Metal compute, generated software product | 432-435 M it/s (8.6 G iterations), was 357 before the profile below |
| for scale: `ec2k-gpu` on an RTX PRO 6000 | | 20,080 M it/s |

**`ec2k-cpu`.** `include/hostclmul.h` gives `packed131.h`'s host paths the
host's carry-less multiplier -- `vmull_p64` (PMULL) on AArch64, PCLMULQDQ on
x86-64, selected by what the compiler is targeting, the software product
otherwise -- at the three places the device uses `clmad`: `clmul64`,
`clmadLo64`, `spread32p`.  `src/cpuknobs.h` is the kernel's knob set for a
host: with a multiplier the 3-bit top-word correction and the polynomial
squaring go to it too.  On those routines one worker on an M4 Pro core ran an
iteration in 127 ns (163 ns with the device's knobs over the same PMULL,
261 ns on the software product), bound by instruction count: five 32-bit
words per element is the device's layout, and the compiler emits about 100
instructions for a product, 95 for its reduction and 290 for the selection.

`src/f131.h` is the step on three 64-bit limbs instead -- the same Karatsuba
product (vector-resident on PMULL: eight multiplies, the partial sums folded
before anything crosses to the integer registers), the same direct reduction
with its shifts written across limbs, the same conversion network and the
same byte-table selection -- and `src/cpuwalk.h` is the engine around it:
**53.5 ns an iteration** on the same core, 153 ns on the software product.
Where the time went, in order of what it bought:

| | ns an iteration, one worker |
|---|---:|
| the packed routines over PMULL | 127 |
| + 64-bit limbs for product, reduction, squaring, conversion, selection, addend | 76.5 |
| + the step as loops over the batch, the selection in its three dependent stages | 62 |
| + the four inversion chains' accumulators in locals, not an array indexed `i % 4` | 53.5 |

The last two are the same observation: a lane's selection (phase, then mask,
then pivot, then sign: some 90 cycles for 240 instructions) and its link in
the prefix-product chain are dependency chains far longer than their
instruction counts, and a core only stays full when neighbouring lanes'
chains overlap.  A product is now 6 ns, of which the reduction is 3.2 and the
multiplies 1.4; the reduction is the next thing to look at.  The engine keeps
512 lanes per batched inversion, as four interleaved chains, because a core
has L1 where the device has registers; a lane that reports restarts in the
same step; work is handed out in 64-step slices of one batch so efficiency
cores do not gate a launch.  All 14 cores give 139-159 M it/s, which is the
package's limit rather than the scheduler's (ten workers give 136).

The reports of a run do not depend on the batch size or the worker count,
which `src/cputest.cpp` checks along with: the multiplier against a
bit-serial product; every `f131.h` routine against its packed counterpart on
4,000 random operands and 1,500 curve points with histories that fire the
cycle rule, the reduction also on limbs no product produces; start points
against the model's; and every lane and every report of a run with restarts
re-walked on the model (28,641 checks, and again with the software product).

**`ec2k-metal`.** Metal Shading Language is C++14 with address spaces, so the
kernel is not a port: `scripts/mslgen.py` inlines the headers and applies four
mechanical rewrites (operands by value, `thread`/`device` on the remaining
pointers, `ulong`, `constant` on namespace-scope constants), `metal/walk.metal`
adds the two-pass loop of `packedkernels.cuh`, and the client compiles the
result with `newLibraryWithSource` when it starts -- the Command Line Tools are
enough, no offline Metal toolchain.  An Apple GPU has no carry-less multiply,
so this is the kernel's `ECC_PACKED_CLMAD=0` configuration
(`generatedProduct131`, the masked-multiply product the source tree keeps for
Turing).  Memory is unified: the state buffers are shared, the host seeds and
revives lanes directly with the CPU client's `startPoint`, and there is no
init kernel.  A launch is cut into dispatches of about a quarter second,
sized from the measured step time, to stay under the GPU watchdog.  32 lanes
per thread measured best; the default is 65,536 threads, two million lanes.

`build/metalprof` times a shader file's walk (or any kernel, `--per-thread`)
on the GPU clock, with variants behind `-D` macros; a dispatch under ~200 ms
reads low because the GPU has not reached its clock.  Its profile of the walk
on an M4 Pro: the five polynomial products are 0.38 ns each chip-wide and
~76% of a step -- each is half widening 32x32->64 multiplies (~5 logic-op
slots apiece) and half logic -- the inversion ~17%, selection ~6%.  Four
changes came of it, 2.70 -> ~2.3 ns an iteration on the GPU clock: inv131's
long Frobenius powers through the permutation networks (`PERM_SIGMA=3`,
13.4 -> 5.0 ns an inversion, 130 squarings having been 10.8 ns of it);
slot-major state in word planes, so a SIMD group's loads are consecutive;
the 14 KB of selection tables in threadgroup memory (`ADDEND_GLOBAL=1`); and
65,536 threads.  Metal's `reverse_bits` for `reverse32` adds a few percent.
What is left is the product.
`src/metaltest.mm` runs every routine the kernel calls on the GPU against the
host, word for word -- normal-basis multiply, square and inverse, both
conversions, the polynomial product, pair and squaring, the selection with
histories that fire the cycle rule, the addend -- and then the engine with
reports, `--max-iters` restarts and revived lanes, every report and every
lane re-walked on the model (1,066 checks).  `make metal-verify` at the default
geometry re-walked 300 of 300.  Without a Metal device the test says so and
passes; a sandbox that hides the GPU looks like that.

```sh
make cpu   && build/ec2k-cpu bench            # make cpu-bench, make cpu-verify
make metal && build/ec2k-metal bench          # make metal-test, metal-bench, metal-verify
build/ec2k-metal walk --run-id 9 --dp-file dps.bin --dp-file32 dps32.bin --verify 100
EC2K_METAL_SOURCE=build/walk_metal.metal build/ec2k-metal bench   # shader development
```

Neither client checkpoints, and at the campaign's weight a lane reports about
once in 2^25 steps: a million lanes at 390 M it/s are a day from their first
reports, so a short session at weight 34 yields nothing.  That is what
`--dp-weight` is for on these clients.

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
