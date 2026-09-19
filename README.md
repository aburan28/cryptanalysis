# cryptanalysis

A fast, self-contained C11 library of discrete-logarithm algorithms with
Rust, Go and Python bindings.

| algorithm | header | problem | cost |
|-----------|--------|---------|------|
| Baby-step giant-step (Shanks), amortised tables | `ca_bsgs.h` | interval / whole group | `1.5 sqrt(N)` ops, `O(sqrt N)` memory |
| Pollard rho: r-adding walks, distinguished points, multi-threaded, negation map with fruitless-cycle handling | `ca_rho.h` | whole group | `~1.25 sqrt(n)` ops (`/sqrt 2` on curves), tiny memory |
| Pollard kangaroo / lambda (van Oorschot-Wiener herds) | `ca_kangaroo.h` | interval | `~2 sqrt(N)` ops, tiny memory |
| Two grumpy giants and a baby (Bernstein-Lange) | `ca_grumpy.h` | interval / whole group | `1.18 sqrt(n)` whole group, `1.78 sqrt(N)` interval |
| Pohlig-Hellman + solver dispatch (`ca_dlog`) | `ca_pohlig.h` | composite order | sum over prime factors |
| Cheon's attack on the strong Diffie-Hellman problem (`d \| p-1`) | `ca_cheon.h` | recover `alpha` from `g, g^alpha, g^(alpha^d)` | `2 sqrt((p-1)/d) + 2 sqrt(d)` exponentiations |
| Index calculus in `(Z/pZ)^*`: linear sieve, Pohlig-Hellman for small factors, structured elimination + Lanczos, Hensel lifting, verified logs | `ca_indexcalc.h` | `Z_p^*`, `p < 2^63` | `L_p[1/2, 1]`; 56-bit `p` in 1.3 s |
| **GPU Pollard rho**: a CUDA kernel (CUDA C) with 8 walks per thread sharing one modular inversion, atomic distinguished-point output, plus a host emulator that runs the same code | `ca_gpu.h` | whole group | same `sqrt(n)` with tens of thousands of concurrent walks |

Everything is written against one generic cyclic-group interface
(`ca_group.h`) with two concrete groups: subgroups of `(Z/pZ)^*` and of
`E(F_p)` for short Weierstrass curves, both over 64-bit primes using
Montgomery arithmetic.  Curve walks use batched affine addition (one
inversion per 256 additions, 21.8 ns per addition on one core).  Every
solver reports its work in a `ca_stats` struct so that results can be
compared in the unit `S = operations / sqrt(N)`; see
[docs/BENCHMARKS.md](docs/BENCHMARKS.md) for the measured tables and
[docs/ALGORITHMS.md](docs/ALGORITHMS.md) for the mathematics, design
decisions and references.

The 64-bit limit is deliberate.  The library exists to measure algorithm
constants, to serve as the reference implementation that research code is
compared against, and to give higher-level languages a fast native core;
it is not an attack tool for cryptographic sizes.

## Build

Requirements: CMake >= 3.16 and a C11 compiler with `__int128` (gcc or
clang; pthreads).

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
ctest --test-dir build            # 11 test programs, ~1 minute
sudo cmake --install build        # headers, libcryptanalysis.{a,so}, ca, pkg-config
```

Useful options: `-DCA_NATIVE=ON` (`-march=native`), `-DCA_SANITIZE=ON`
(ASan + UBSan), `-DCA_WERROR=ON`, `-DCA_BUILD_SHARED/STATIC/TOOLS/TESTS`,
and `-DCA_CUDA=ON` for the GPU backend (see [docs/GPU.md](docs/GPU.md)).
`make test`, `make bench`, `make asan`, `make cuda`, `make cuda-kernel`,
`make bindings` wrap the common invocations.

The GPU kernel can be compiled and measured without a GPU or a CUDA
install: `scripts/build_cuda_kernel.sh --fetch` builds it for sm_70 through
sm_90 and reports registers, local memory and spills.

## Command line

`ca` prints one JSON object per invocation.

```sh
$ ./build/ca gen --group zp --p 2000000579 --order 1000000289 --x 123456789 --seed 1
{"status":"ok","group":"zp","p":2000000579,"order":1000000289,"cofactor":2,"g":"1422302461","h":"1216411080","x":123456789}

$ ./build/ca solve --alg rho --group zp --p 2000000579 --order 1000000289 \
      --g 1422302461 --h 1216411080 --threads 4
{"status":"ok","alg":"rho","x":123456789,"ops":63915,"iterations":1808,...,"threads":4}

$ ./build/ca ec-order --p 1000003 --a 1 --b 7
{"status":"ok","p":1000003,"order":999720,"factors":[[2,3],[3,2],[5,1],[2777,1]],...}

$ ./build/ca solve --alg dlog --group ec --p 1000003 --a 1 --b 7 --order 2777 \
      --g 965127,959535 --h 484062,675069
{"status":"ok","alg":"dlog","x":2130,"ops":2134,...}

$ ./build/ca cheon --group zp --p 2000000579 --order 1000000289 --g 1422302461 --alpha 987654321
{"status":"ok","alpha":987654321,"d":30512,"exponentiations":552,"ops":22606,...}

$ ./build/ca gpu-info
{"cuda_compiled":false,"devices":0,"walks_per_thread":8,"names":[]}

$ ./build/ca solve --alg gpu-rho --group zp --p 2000000579 --order 1000000289 \
      --g 1422302461 --h 1216411080 --backend emulate --seed 3
{"status":"ok","alg":"gpu-rho","x":123456789,"launches":5,"ops":18307,...}

$ ./build/ca ic --p 1099511627791 --g 3 --h 123456789 --threads 4
{"status":"ok","x":240852468320,"check":123456789,"factor_base":143,"unknowns":1094,
 "relations":1505,"verified_logs":143,"sieve_seconds":0.001,"linalg_seconds":0.049,...}
```

Other commands: `ca factor N`, `ca prime N`, `ca solve --alg bsgs|kangaroo|grumpy
... --lo L --hi U` for interval problems, `ca_bench generic|interval|ic|cheon|gpu|ops`
for the benchmark tables.

## C API in one screen

```c
#include <cryptanalysis/cryptanalysis.h>

ca_group g;
ca_group_zp_init(&g, 2000000579ULL, 1000000289ULL);   /* order-q subgroup */
ca_elem gen, h;
ca_group_find_generator(&g, &gen, /*seed*/ 1);
ca_group_mul(&g, &h, &gen, 123456789, NULL);          /* h = 123456789 * gen */

uint64_t x;
ca_stats st = {0};
ca_status rc = ca_dlog(&g, &gen, &h, &x, &st);        /* Pohlig-Hellman + auto solver */
/* or: ca_rho_solve, ca_bsgs_solve, ca_kangaroo_solve, ca_grumpy_solve, ca_cheon_solve */

uint64_t y;
ca_ic_solve(1099511627791ULL, 3, 123456789, NULL, &y, NULL);   /* index calculus */
```

Elliptic curves: `ca_group_ec_init(&g, p, a, b, order)`, `ca_ec_count_points`
(Mestre BSGS point counting), `ca_ec_random_point`, `ca_ec_lift_x`.  All
solvers take a parameter struct (`ca_rho_params` etc., filled by a
`*_params_default` function) and optional `ca_stats`.

## Language bindings

All three bindings sit on the flat ABI in `ca_ffi.h` (opaque handles,
`uint64_t[4]` elements, POD option/stat structs whose sizes are checked at
load time).  See [docs/FFI.md](docs/FFI.md).

**Rust** (`bindings/rust`, crates `cryptanalysis-sys` and `cryptanalysis`;
the sys crate compiles the C sources with `cc`, no CMake needed):

```rust
use cryptanalysis::{Group, Options};
let g = Group::zp(2_000_000_579, 1_000_000_289)?;
let gen = g.find_generator(1)?;
let h = g.mul(&gen, 123_456_789)?;
let (x, stats) = g.dlog(&gen, &h, &Options::default())?;
assert_eq!(x, 123_456_789);
let (y, _) = cryptanalysis::index_calculus::solve(1_099_511_627_791, 3, 123_456_789, &Default::default())?;
```

**Go** (`bindings/go`, module `github.com/aburan28/cryptanalysis/bindings/go`,
cgo; compiles the C sources itself):

```go
g, _ := cryptanalysis.NewZp(2000000579, 1000000289)
defer g.Close()
gen, _ := g.FindGenerator(1)
h, _ := g.Mul(gen, 123456789)
x, stats, err := g.Dlog(gen, h, nil)
y, _, _ := cryptanalysis.ICSolve(1099511627791, 3, 123456789, nil)
```

**Rust, on the GPU.** Two routes, both running the same kernel source.
Through the C library:

```rust
use cryptanalysis::{Group, GpuBackend, GpuOptions};
let (x, stats) = g.gpu_rho(&gen, &h, &GpuOptions::default())?;   // CUDA if present
let (x, _) = g.gpu_rho(&gen, &h, &GpuOptions { backend: GpuBackend::Emulate, ..Default::default() })?;
```

Or driving the device from Rust directly with `cryptanalysis-cuda`, which
compiles `cuda/rho_kernel.cu` to PTX at build time (or with NVRTC at run
time) and launches it through the CUDA driver API, so the kernel is shared
with the C library rather than reimplemented.

**Python** (`bindings/python`, ctypes, no compile step beyond building the
shared library):

```python
import cryptanalysis as ca
g = ca.Group.zp(2000000579, 1000000289)
gen = g.find_generator(seed=1)
h = g.mul(gen, 123456789)
x, stats = g.dlog(gen, h)
y, ic_stats = ca.ic_solve(1099511627791, 3, 123456789)
```

Run the binding tests with `make rust`, `make go`, `make python` (or see
each binding's README).

## Layout

```
include/cryptanalysis/   public headers (cryptanalysis.h is the umbrella)
src/                     library sources (+ internal linalg.h, ca_internal.h)
cuda/                    the CUDA kernel (ca_device.cuh is shared C11/CUDA code)
tests/                   C test programs (ctest)
tools/                   ca (CLI) and ca_bench
scripts/                 build_cuda_kernel.sh (compile the kernel, no GPU needed)
bindings/{rust,go,python} plus bindings/rust/cryptanalysis-cuda (Rust GPU driver)
docs/                    ALGORITHMS.md, BENCHMARKS.md, FFI.md, GPU.md
.github/workflows/ci.yml gcc/clang/macOS builds, sanitizers, CUDA kernel, bindings
```

## Status and roadmap

Implemented and tested: everything in the table above, for groups of order
below `2^64`.  Every solver verifies its answer before returning it.

The GPU backend ships the kernel, the host driver, the CLI and benchmark
integration, and a Rust driver. It is verified by compiling to a real cubin
for sm_70 through sm_90 and by running the identical kernel body through the
host emulator; **it has not yet been run on a physical GPU**, because this
development container has neither a device nor a complete CUDA toolkit. See
the end of [docs/GPU.md](docs/GPU.md) for exactly what that means.

Not implemented (documented in `docs/ALGORITHMS.md`): the number field
sieve (the state of the art for `F_p` above ~100 bits), index calculus on
curves over extension fields (Semaev/Gaudry/Diem summation polynomials,
which need Groebner-basis machinery and do not beat rho at any
cryptographic size), the `d | p+1` case of Cheon's attack, and
multi-precision moduli.  The group interface is the extension point for
all of these.

## License

MIT, see [LICENSE](LICENSE).
