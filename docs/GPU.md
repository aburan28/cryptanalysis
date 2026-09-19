# The GPU (CUDA) backend

The parallel part of Pollard rho is a near-perfect fit for a GPU: tens of
thousands of independent walks, each a handful of 64-bit modular
multiplications per step, with communication only when a walk reaches a
distinguished point.  This component implements that as a CUDA kernel
written in CUDA C, driven either from the C library, from the `ca` CLI, or
from Rust.

## What is where

| file | role |
|------|------|
| `cuda/ca_device.cuh` | the device code: Montgomery arithmetic, curve and `Z_p^*` group operations, the negation map, cycle escapes, and the per-thread walk loop `ca_dev_rho_thread` |
| `cuda/rho_kernel.cu` | the `__global__` entry point and a launch shim (device code only, so it compiles with `--cuda-device-only`) |
| `cuda/gpu_cuda.c` | host side of the CUDA backend: device allocation, uploads, launches, downloading distinguished points |
| `src/gpu_emulate.c` | runs the identical kernel body on the CPU, one thread at a time |
| `src/gpu_cuda_stub.c` | the same backend interface when CUDA is off, so `src/*.c` always builds without CUDA headers |
| `src/gpu_rho.c` | the backend-independent driver: multipliers, parameter choice, the launch loop, collision solving, walk restarts |
| `include/cryptanalysis/ca_gpu.h` | the public API (`ca_gpu_rho_solve`) |
| `bindings/rust/cryptanalysis-cuda` | a Rust driver that launches the same kernel through the CUDA driver API |

`ca_device.cuh` is **simultaneously valid CUDA C++ and valid C11**: one
macro makes every function either `__device__ __forceinline__` or
`static inline`, and the 64x64→128 multiply is either `__umul64hi` or
`unsigned __int128`.  That single source is why the emulator is worth
having: it is not a reimplementation that can drift, it is the same code.

## Why one thread owns eight walks

Affine curve addition needs a modular inverse.  There is no cheap extended
Euclid on a GPU (it branches on data), so the kernel inverts by Fermat:
`a^(p-2)` over a 64-bit exponent, which is 64 squarings plus about 32
multiplications, roughly 96 in total.  The addition itself is only 3
multiplications, so a private inversion makes the inverse 97 % of the cost
of a step.

Montgomery's simultaneous-inversion trick shares one inversion between
`CA_GPU_W` walks for about 3 extra multiplications each.  At eight walks per
thread a step costs roughly `96/8 + 3 + 3 = 18` multiplications instead of
`96 + 3 = 99`: a 5.5x saving, and the reason a thread owns several walks
rather than one.  `CA_GPU_W` is a compile-time constant (default 8) so that
the walk array is a fixed-size local allocation rather than a dynamic one.

The same trick on the CPU is worth 10.6x (232 ns down to 21.8 ns per
addition, see BENCHMARKS.md); the GPU figure is smaller because the CPU
inverts with extended Euclid, which is cheaper than Fermat to begin with.

Measured cost of the kernel, from `scripts/build_cuda_kernel.sh`:

| arch | registers | local memory per thread | spills |
|------|----------:|------------------------:|-------:|
| sm_70 | 72 | 736 B | 0 |
| sm_80 | 64 | 736 B | 0 |
| sm_89 | 64 | 736 B | 0 |
| sm_90 | 64 | 736 B | 0 |

The 736 bytes are the eight walk states (92 bytes each); `ptxas` keeps them
in local memory, which is per-thread interleaved and L1-backed, rather than
in registers.  Forcing full unrolling with `#pragma unroll` moves nothing
into registers and more than doubles register use (72 → 168 on sm_70),
which would only cost occupancy, so the loops are left rolled.  With
`--walks 4` the figure halves to 368 bytes, and nothing spills at any
setting tried (4, 8 or 16 walks; sm_70 through sm_90).

## The distinguished-point protocol

The host never reads walk state.  Each walk keeps `(Y, a, b)` with
`Y = aG + bH` on the device; when `hash(Y)` has `dp_bits` trailing zero
bits, the thread reserves a slot with `atomicAdd` and writes
`(hash, a, b, walk id)`.  After each launch the host drains that buffer
into a hash table:

* a second arrival at the same point with a different `(a, b)` gives
  `(b - b') x = a' - a (mod n)`, which the host solves (including the
  negation-map sign ambiguity and a gcd branch for composite `n`) and
  **verifies with a scalar multiplication** before returning it;
* the same `(a, b)` means the walk rediscovered its own trail, so the host
  sets a per-walk restart flag that the next launch picks up.

Only the flags travel to the device, so a launch costs one small upload,
one kernel, and one download proportional to the number of distinguished
points found.

The buffer holds one launch's worth of points.  Overflowing it is safe by
construction rather than by luck: the kernel only writes slots below the
capacity and the host clamps the count, so an overflow drops points and
costs a little work but can never produce a wrong answer.

A walk that runs `24 << dp_bits` steps without reaching a distinguished
point is re-seeded: it is in a cycle, and in a small group that cycle may
well contain no distinguished point at all at the chosen density.  This is
the same rule the CPU solver uses, and it is the reason the
distinguished-point density is derived from the group size rather than
fixed.

Reported `group_ops` is walk steps summed over all walks. A retried step
(the negation-map look-ahead) performs a real group operation and is
counted; the rare cycle-escape walk happens device-side and is not, so the
figure is a very slight undercount when escapes occur.

Parameters chosen automatically by `ca_gpu_rho_solve` (all overridable):
the number of multipliers `r` (up to 1024 with the negation map, since a
larger table makes fruitless cycles rarer and the table is built on the
host), the thread count (bounded so that walk start-up, about `3 log2 n`
operations per walk, stays under `sqrt(n)/8`), `dp_bits` (about 32
distinguished points per walk over the expected run, capped so the table
stays under `2^24` entries), and the steps per launch (about 1/16 of the
expected work).

## Using it

From C:

```c
#include <cryptanalysis/cryptanalysis.h>

ca_gpu_rho_params p;
ca_gpu_rho_params_default(&p);       /* backend AUTO: CUDA if present */
p.threads_per_block = 256;
uint64_t x;
ca_stats st = {0};
ca_status rc = ca_gpu_rho_solve(&g, &gen, &h, &p, &x, &st);
/* st.threads = threads used, st.reserved = kernel launches */
```

From the CLI:

```sh
$ ca gpu-info
{"cuda_compiled":false,"devices":0,"walks_per_thread":8,"names":[]}

$ ca solve --alg gpu-rho --group zp --p 2000000579 --order 1000000289 \
      --g 1422302461 --h 1216411080 --backend emulate --seed 3
{"status":"ok","alg":"gpu-rho","x":123456789,"launches":5,"ops":18307,...}

$ ca_bench gpu --bits 24,28,32          # GPU kernel vs the CPU solver
```

`--backend cuda` fails with a clear error when the library was built
without CUDA or no device is present; `--backend emulate` always works.

## Building the CUDA backend

```sh
cmake -S . -B build-cuda -DCMAKE_BUILD_TYPE=Release -DCA_CUDA=ON
cmake --build build-cuda -j
ctest --test-dir build-cuda -R gpu
```

`-DCA_CUDA=ON` needs a real CUDA toolkit: `nvcc`, or clang with a complete
toolkit (CMake's CUDA language support requires `nvcc` and `fatbinary` to be
present for toolkit detection even when clang does the compiling).
`-DCA_CUDA_ARCHITECTURES="70;80;89;90"` selects the targets.  Without
`CA_CUDA` the library still exposes the full GPU API, backed by the
emulator, and `ca_gpu_cuda_compiled()` returns 0.

To check the kernel itself without installing CUDA and without a GPU:

```sh
scripts/build_cuda_kernel.sh --fetch            # all four architectures
scripts/build_cuda_kernel.sh --fetch --walks 4  # a different walk count
```

`--fetch` assembles the headers, `libdevice` and `ptxas` from NVIDIA's pip
wheels into a scratch directory, compiles with `nvcc` if it finds one and
otherwise with clang, and prints the register and local-memory table above.
This is what CI runs.

One wrinkle when clang does the compiling: clang force-includes its own CUDA
wrapper header, which pulls in libstdc++'s `<cmath>` and so `<limits>`, and
from GCC 14 on that declares `numeric_limits<__float128>` — a type the NVPTX
target does not have.  The compile then fails with a dozen errors that have
nothing to do with the kernel.  The script detects this and retries against
each installed GCC's headers, oldest first, reporting which one it used;
`--host-gcc DIR` picks one explicitly.  `nvcc` is unaffected.

## How this is tested

* `tests/test_gpu.c` checks the device arithmetic against the host library
  over five moduli up to `2^64 - 59` (Montgomery multiply, add, subtract,
  inverse), then checks device group operations, scalar multiplication and
  the element hashes against `ca_group_*` on a curve and in `Z_p^*`,
  including the doubling, infinity and inverse-pair cases. 77,000 assertions.
* The same test runs the **whole solver** through the emulator on four
  groups (`Z_p^*` prime and composite order, curves with and without the
  negation map, 17 to 31 bits), plus an explicit tiny configuration
  (1 block of 4 threads, 2 distinguished-point bits) and the `max_ops`
  limit. Because the emulator executes the kernel body itself, this covers
  the walk function, the negation map, cycle escapes, the atomic DP
  protocol, collision solving and restarts.
* When a device is present the same tests additionally run with
  `CA_GPU_BACKEND_CUDA`; when it is not, they assert the clean
  `CA_ERR_UNSUPPORTED`.
* `scripts/build_cuda_kernel.sh` proves the kernel compiles to a real cubin
  for sm_70/80/89/90 with no spills.

**Not verified in this container:** an end-to-end run on real hardware.
There is no GPU and no complete CUDA toolkit here, so `-DCA_CUDA=ON` has
not been configured through CMake, and no kernel has executed on a device.
What is verified is that the kernel compiles to a valid cubin, that the
host backend compiles cleanly as C against the CUDA runtime headers, and
that the algorithm the kernel implements is correct (via the emulator).
The first run on a real GPU should be `ctest -R gpu` plus
`ca_bench gpu --bits 32,36,40`.

## Expected speed-up, and where the limit is

The kernel does no synchronisation and no shared-memory traffic, so its
throughput is set by 64-bit integer multiply capacity.  A single CPU core
here does 169 M Montgomery multiplies/s in `Z_p^*` and 4.3 M affine curve
additions/s (45.9 M batched); a mid-range GPU has thousands of ALUs, so the
useful comparison at a given size is operations, which is what `ca_bench
gpu` prints, times the per-operation cost on each device.

Two limits are worth knowing. First, rho is `O(sqrt(n))` regardless of how
many walks run, so a GPU buys a constant factor, not an asymptotic
improvement: the parallel speed-up from `M` walkers is linear in `M`
(van Oorschot-Wiener), and nothing here changes the exponent. Second,
64-bit moduli mean one walk step is only a few instructions, so the
kernel is latency- rather than throughput-bound on small groups; the
thread-count heuristic deliberately keeps walk start-up below
`sqrt(n)/8`, which for small `n` leaves the device underused. Groups above
about 2^48 are where a GPU is the right tool.
