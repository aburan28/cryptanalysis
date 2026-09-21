# A GPU Pollard rho client for ECC2K-130

A CUDA walker for the Certicom ECC2K-130 challenge -- the Koblitz curve
`y² + xy = x³ + 1` over `F_{2¹³¹}` -- with a host test that holds its
arithmetic to this repository's golden model and a re-walk that checks what
the device reports. It builds two walks:

- **`make gpu`** (the default, `WALK=sigma`) walks what the live
  [ecc2k-130 campaign](https://aburan28.github.io/crypto/status/) walks:
  `R' = R + σ^j(R)` from Certicom's challenge points, distinguished at
  `HW(x) ≤ 32`. Its points are points of that campaign, record for record.
  [Collecting for the campaign](#collecting-for-the-ecc2k-130-campaign) is
  how to run it.
- **`make gpu WALK=table`** builds an r-adding table walk measured at
  **20.08 billion iterations per second on one RTX PRO 6000 Blackwell**. It
  is a different iteration function, so its points never collide with the
  campaign's: a throughput result, not collection.

**What is verified and what is not.** The field arithmetic, the Frobenius
networks, the basis conversions, each walk's selection and the walk itself
are checked bit for bit against `fpga/model/ecc2k130.c` (`make test`: 2,709
checks for the sigma walk, 1,904 for the table walk, gcc and clang in CI).
For the sigma walk, `make test` also replays 48 distinguished points that
the campaign's own client wrote (`tests/campaign-kat.hex`), and must get
every 32-byte record back from its seed. That is the check that this
client's points and the campaign's are the same points. Every report the
device makes can be re-walked from its seed on the model with `--verify N`.
The table walk's measured run below re-walked 300 of 300. The sigma build's
device run has not yet been measured or re-walked on a card in this tree.
CI compiles both kernels with the pinned compiler and reports registers and
spills. No runner has a card, so only a card can reproduce a rate or a
re-walk.

## Where the kernel comes from

The device code in `include/` is imported from
[aburan28/crypto](https://github.com/aburan28/crypto) `ecc2k130/` (branch
`ecc2k130-l1-geometry-and-tag-denominator`, `b8ed2f5`), where it was
developed and where its history, its many build-time knobs and the notes
that priced them live. What is imported is the configuration that measured
20.08 B/s, which still carries that tree's sigma-walk path; the default build
selects that path with the knobs of the campaign fleet's build (`aws/build.sh`
there). The other backends, the Modal integration and the resolver stay
there. The generated headers
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

## Collecting for the ecc2k-130 campaign

Each [release](https://github.com/aburan28/cryptanalysis/releases) tagged
`ec2k-gpu-v*` ships `ec2k-gpu` for Linux x86_64 and aarch64. Each binary is
built for sm_80, 86, 89, 90, 100 and 120, with the CUDA runtime linked in, and
needs only an NVIDIA driver recent enough for CUDA 13.3:

```sh
tar xzf ec2k-gpu-VERSION-linux-x86_64.tar.gz && cd ec2k-gpu-VERSION-linux-x86_64
./ec2k-gpu check --kat campaign-kat.hex   # the campaign's known answers, on this CPU
./ec2k-gpu walk --run-id R --dp-file dps.bin --checkpoint state.ck
```

`scripts/package.sh` builds that tarball, and
`.github/workflows/ec2k-gpu-release.yml` runs it on the tag. Before packing,
the binary it builds must pass `check --kat`. From source:

```sh
make test                  # the host test, including the campaign's known answers
make gpu                   # needs nvcc >= 13.3; ARCH defaults to sm_120
build/ec2k-gpu walk --run-id R --dp-file dps.bin --checkpoint state.ck
```

That walks until it is stopped. Every 600 s it syncs `dps.bin` and then
saves every lane to `state.ck`. On SIGINT or SIGTERM it finishes the launch
in flight, checkpoints and exits. Run the same command again and it resumes.
What makes the points the campaign's:

- **The walk and the points.** The sigma walk from Certicom's `P` and `Q`,
  start points `Q + Σ c_i σ^i(P)` from the seed's PRF, the same as the
  campaign client's.
- **The cutoff.** A walk ends at its first point with `HW(x) ≤ 32`, the
  campaign's weight. A run at another `--dp-weight` ends its trails at other
  points, which mostly cannot meet the campaign's. The client says so when
  it starts.
- **The record.** `dps.bin` is a flat file of 32-byte records: the seed, then
  the smallest `x` over the point's Frobenius orbit. This is `fpga/model`'s
  record, and byte for byte the campaign's `DpFileRecord`.
- **The run id.** Seeds are `(R << 48) | (lane << 16)`, and a lane that
  reports restarts from `seed + 1`. Two runs share a trail exactly when they
  share `R`, so every machine needs an `R` no one else is walking. The
  campaign's AWS fleet uses `R = slot + 1` from 1 upward, and its Modal runs
  use 8000–9999. A run under an id already walked finds nothing new.
- **The checkpoint header.** The first 40 bytes of `state.ck` are the
  campaign client's checkpoint header. From it, `iterBase × threads × batch`
  is the work done, which is what the campaign's ingest reads. The rest of
  the file is this client's own and loads only into this client, with the
  same geometry, run id, cutoff and points. Anything else is refused, and
  the file is left as it was.

After a crash, as opposed to a stop, lanes resume from the last checkpoint
and report again what they reported since. The second copy is byte-identical
to the first, so the campaign's store keeps it once: it is a re-report, not
a collision.

**Where the points go.** The campaign's store is written by its own fleet.
There is no public upload yet, so a contributor's `dps.bin` stays on their
machine until there is one.

At the campaign's weight a lane reports about once in `2^28.4` steps, so
`--verify` (a CPU re-walk) is for test weights. `make verify` collects at
weight 46 and re-walks 300 reports from the challenge points.

## The sigma walk

```
j(R) = 3 + ((HW(x) >> 1) & 7)
R'   = R + σ^j(R)
```

This is the iteration of Bailey et al., *Breaking ECC2K-130*. It is also the
one `fpga/model`'s `ec2k_step` implements and the FPGA core runs, which is
why the model can re-walk this client's reports with no walk code of its
own. `σ` is the Frobenius. On the normal basis it is a rotation of the
coordinates, so both `σ^j(x)` and `σ^j(y)` for the eight values of `j` come
out of one generated permutation network, whose masks sit in shared memory.
The weight, and so `j` and the distinguished-point test, is taken on the
normal-basis `x`, converted from the polynomial basis the state is kept in.
The rest of the step (the batched inversion, the addition) is shared with the
table walk below. Only `x` is reported: on a Koblitz curve
`−(x, y) = (x, x + y)`, and the Frobenius class is normalised by the orbit
minimum when the record is written.

## The table walk

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
`HW(x) ≤ 34` by default. This is a different iteration function from the
sigma walk and the FPGA core's. They share the field, the model and the
32-byte record (`--dp-file`, which `fpga/host/ec2k merge` reads), but not a
corpus.

One step of either walk is one affine addition. Coordinates are stored in the polynomial
basis `F_2[c]/(m)`, `c = γ₁`, where a 131-bit product is three 64×64
carry-less multiplies -- six `clmad` -- plus a 78-instruction reduction; the
Bernstein–Lange conversions to and from the normal basis (where the weight,
the selection and the distinguished-point test live) are `O(K log K)`
shift-and-mask networks. Sixteen walks per thread share one inversion by
Montgomery's trick: a forward pass accumulates the denominators' prefix
products, one Itoh–Tsujii inversion (eight products), a reverse pass peels
the inverses off and completes the additions.

## Boundary and measurement (the table walk)

These are measurements of `WALK=table`. The sigma build uses the campaign
fleet's geometry (two 256-thread blocks per SM). Its rate on this client has
not been measured; the first row is the source tree's number for the same
walk. Unit: billions of complete iterations per second on one RTX PRO 6000
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
make gpu WALK=table          # build/ec2k-gpu-table; every target takes WALK=

build/ec2k-gpu walk --run-id R --dp-file dps.bin --checkpoint state.ck
build/ec2k-gpu walk --run-id R --dp-weight 46 --dp-file64 full.bin --verify 100 --launches 4
build/ec2k-gpu check --rounds 256                    # the host test, from the client binary
```

`bench` counts iterations with no lane ever reporting, for 32 launches.
`walk` collects until it is stopped, or for `--launches L`. It needs a
`--run-id`, the high 16 bits of every seed, because two runs under one id walk
the same trails. A lane that reports is revived from its incremented seed
between launches. `--max-iters N` restarts lanes that have walked `N` steps
without reporting; the sigma default is the campaign's `2^30`. `--dp-file`
takes the 32-byte campaign record. `--dp-file64` takes the full 64-byte
report `(seed, iterations, x, y)`, which is what `--verify` re-walks. The base
and target points are Certicom's. `--p-seed` and `--q-seed` replace them with
test points from `ec2k_point_from_seed`, and the client then says that its
points are not the campaign's.

`--threads` must be a multiple of 256 (the compact state layout's tile); the
default is one wave of resident blocks. The GPU is shared fairly between
processes, so a benchmark on a card that is also collecting measures half of
it -- the A/B row above was taken that way, against the source binary.

## The table walk without the card: `ec2k-cpu` and `ec2k-metal`

Two clients run the table walk where there is no CUDA device. Like
`WALK=table`, their points are not the campaign's. They are built from the
same headers as `build/ec2k-gpu-table`, take their start points from the same
seeds and their addends from the same table, and write the same 64- and
32-byte records. So a report from any of the three re-walks on the model and
merges with the others'.
They exist to develop and test a campaign's pipeline -- reports, `--verify`,
`ec2k merge`, ingest -- on the machine in front of you; the throughput of the
campaign is the card's.

| client | engine | measured on an M4 Pro (10P + 4E cores, 20-core GPU) |
|---|---|---:|
| `ec2k-cpu` | worker threads, 64-bit limbs, products on PMULL | 139-159 M it/s, 14 workers |
| `ec2k-cpu`, one worker | | 18.6 M it/s (53.5 ns an iteration) |
| `ec2k-metal` | Metal compute, generated software product | 389-390 M it/s (3 x 4.3 G iterations) |
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
per thread measured best (16: 294, 32: 390, 64: 359 M it/s at comparable lane
counts); 65,536 threads gives 420 M it/s for twice the lanes in flight.
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
- **A way to hand in points.** `dps.bin` is the campaign's record, but the
  campaign's store takes points only from its own fleet today.
- **Multi-GPU.** One process, one device; run one per device with distinct
  run ids and merge the corpora.
- **A rate on any other card, or for the sigma build on any card.** `clmad`
  exists from sm_80. The table walk's geometry (one 512-thread block, 64 KB
  L1, an 80 MiB persisting window) is tuned to the RTX PRO 6000. The
  automatic thread count and `--threads` are where tuning another part
  starts.
