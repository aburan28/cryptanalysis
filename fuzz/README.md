# Fuzzing libcryptanalysis

Six libFuzzer harnesses, one per layer of the library.  The interesting
inputs here are not byte buffers - the API takes 64-bit integers, group
elements and options structs - so every harness starts with a small
struct-style decoder that maps the fuzzer's bytes onto those parameters,
and then asserts the invariants that must hold for whatever the API
*accepts*.  Anything the headers document as a rejection is checked as a
returned `ca_status`, never reported as a bug.

| harness | covers | asserts |
| --- | --- | --- |
| `fuzz_group.c` | `ca_group.h`, `src/group_zp.c`, `src/group_ec.c` | accepted element is valid; encode/decode round-trips; `op(a, inv(a)) == id`; `dbl(a) == op(a,a)`; `mul` is a homomorphism; `batch_op` == one-at-a-time (including the aliased `r == a` form the solvers use); equal elements hash equal; `canonicalize` is idempotent and identifies `a` with `-a`; `elem_order` divides the group order; Hasse bound on `ca_ec_count_points` |
| `fuzz_modarith.c` | `ca_modarith.h` | `gcd` divides both operands; `isqrt(n)^2 <= n < (isqrt(n)+1)^2`; same for `iroot`; `invmod(a)*a == 1`; `powmod(a,b+1) == powmod(a,b)*a`; CRT result is correct mod both moduli; factorisation multiplies back to `n`, is sorted and every factor is prime; `mult_order` divides `p-1`; `primitive_root` has order `p-1`; Montgomery agrees with the plain path on to/from/mul/sqr/pow/inv; sieve output is prime and increasing |
| `fuzz_dlog.c` | BSGS (+ amortised table), kangaroo, grumpy giants, rho, `ca_dlog_prime_order`, `ca_pohlig_hellman`, `ca_dlog` | soundness: `CA_OK` => `x*base == target`; completeness: BSGS over an interval containing the planted `x0` never answers `CA_ERR_NOT_FOUND`, and neither does the brute-force solver; documented rejections (empty interval, unknown order) really are rejections |
| `fuzz_gpu.c` | `ca_gpu_rho_solve` on `CA_GPU_BACKEND_EMULATE`, i.e. the kernel body in `cuda/ca_device.cuh` | soundness of the returned logarithm; internal consistency of `ca_stats`; `dp_bits` is fuzzed over the whole `int32` range because `ca_gpu.h` documents that it is clamped to 63; asking for CUDA without CUDA fails cleanly |
| `fuzz_indexcalc.c` | `ca_ic_precompute` / `ca_ic_log` / `ca_ic_solve` and the accessors | `CA_OK` => `g^x == h (mod p)`; every "known" factor-base log verifies as `zeta^log == prime`; `h = g^e` is never answered with `NOT_FOUND`; out-of-range accessor index is safe; non-prime modulus is rejected |
| `fuzz_ffi.c` | the flat ABI in `ca_ffi.h` (what the Rust/Go/Python bindings call) | the `*_size()` functions match `sizeof`; `ca_ctx_validate` agrees with what every element entry point accepts; the group laws hold in the public word representation; every solver's `CA_OK` verifies; a Cheon instance solves back to the same `g^alpha`; the number-theory helpers agree with the structured API |

## Building

The wiring in `CMakeLists.txt` builds one binary per `fuzz/*.c`, named after
the file, when `CA_FUZZ=ON` and the compiler is clang:

```sh
CC=clang cmake -S . -B build-fuzz -DCA_FUZZ=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build-fuzz -j4
```

That works, but it only puts `-fsanitize=fuzzer,address,undefined` on the
harness translation unit, so the fuzzer gets **no coverage feedback from the
library** and UBSan does not see library code at all.  For real fuzzing pass
the flags through `CFLAGS`, which reaches every target:

```sh
CC=clang CFLAGS="-fsanitize=fuzzer-no-link,address,undefined -fno-omit-frame-pointer" \
  cmake -S . -B build-fuzz -DCA_FUZZ=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCA_BUILD_TESTS=OFF -DCA_BUILD_TOOLS=OFF -DCA_BUILD_SHARED=OFF
cmake --build build-fuzz -j4
```

Measured on a 4-core runner, that raises `fuzz_dlog` from 88 covered edges
(harness only) to 2492 (harness + library).  `.github/workflows/fuzz.yml`
uses this form.  Sanitizer runtimes come from `libclang-rt-<major>-dev` on
Debian/Ubuntu; without them the link fails with "cannot find
libclang_rt.asan-x86_64.a".

## Running

```sh
# replay the committed corpus (fast, use this as a regression check)
./build-fuzz/fuzz_group fuzz/corpus/fuzz_group/*

# fuzz, growing the committed corpus in place
./build-fuzz/fuzz_group fuzz/corpus/fuzz_group \
    -dict=fuzz/cryptanalysis.dict -max_total_time=60 -rss_limit_mb=2048

# make UBSan findings fatal instead of a printed warning
UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 ./build-fuzz/fuzz_dlog ...
```

Invariant violations abort with `__builtin_trap()`, so they surface as an
ordinary libFuzzer crash.  Leak detection is on (ASan default): every
harness frees every context and handle on every path, including the early
`return 0` ones.

## Corpus

`fuzz/corpus/<harness>/seedNN` holds 8 hand-built seeds per harness, written
against each decoder's field layout so they land on the interesting paths
rather than bailing out: both group kinds, degenerate moduli, curves with
point counting on and off, subgroup vs. whole-group orders, each solver
selection, explicit `dp_bits` at 0 / 63 / above 63, both index-calculus
methods, and the documented rejection paths.  `fuzz/cryptanalysis.dict`
holds the little-endian encodings of the scalars that matter.

## Keeping one input cheap

Everything is sized so the fuzzer runs thousands of executions per second
rather than grinding on one input:

* moduli are masked to at most 24 bits (`fuzz_group`), 20 bits (`fuzz_dlog`,
  `fuzz_ffi`, `fuzz_indexcalc`) or 12-20 bits (`fuzz_gpu`, which needs
  `n >= 4096` to get past the driver's brute-force shortcut);
* every solver gets a `max_ops` budget, and the two solvers that ignore it
  (brute force, and `ca_bsgs_solve` with `max_ops = 0`) only ever see a
  short interval or a tiny group;
* `ca_ec_count_points` is O(p^1/4) and only runs where a real curve order is
  needed, with p at most 2^20;
* GPU `blocks`, `threads_per_block` and `steps_per_launch` are capped, since
  the emulator executes every walk step on one core and they size its
  buffers;
* the index-calculus factor-base bound is floored at 128 - individual
  logarithms retry up to 50 million times before giving up, and a factor
  base too small to ever hit would turn one input into a multi-second run;
* solver threads are pinned to 1 (2 for one index-calculus path) so that
  replaying an input is deterministic.

## Deliberately unreachable inputs

Three parameter ranges are clamped in the harnesses because the library
misbehaves on them in a way that is already recorded; leaving them reachable
would just rediscover the same crash forever and make CI permanently red.
Each is written up with a reproducer in `fuzz/crashes/`:

* `dp_bits >= 64` for `ca_rho_solve` / `ca_kangaroo_solve` - undefined shift
  (`rho_kangaroo_dp_bits_shift.txt`);
* `herd_size >= 2^31` for `ca_kangaroo_solve` - infinite loop
  (`kangaroo_herd_size_hang.txt`);
* the "x lies in [lo, hi]" half of the interval contract for kangaroo and
  grumpy giants - they can return a verifying logarithm outside the interval
  (`grumpy_kangaroo_out_of_interval.txt`).

Build with `-DCA_FUZZ_WILD_PARAMS` to lift the first two clamps, and restore
the `CHK(x >= eff_lo && x <= eff_hi)` lines in `fuzz_dlog.c` for the third,
once the library is fixed.

A few further preconditions are enforced rather than reported, because the
headers state them: a zero modulus for `ca_powmod` / `ca_legendre` /
`ca_mult_order` (they divide by it), a non-prime `p` for the prime-only
helpers, and non-finite `ca_grumpy_params.alpha` (the library casts
`alpha * sqrt(width)` to `uint64_t`, which is undefined for inf/NaN).

## CI

`.github/workflows/fuzz.yml`:

* on pull requests and pushes - build, replay the committed corpus, then
  fuzz each harness for 60s (`-rss_limit_mb=2048 -timeout=25`); any crash
  fails the job and the artifacts are uploaded.  Whole job budget ~8 min.
* nightly (`cron: 17 3 * * *`) - one matrix job per harness, 10 minutes
  each, crash artifacts and the grown corpus uploaded.

## Adding a harness

Drop a new `fuzz/<name>.c` with an `LLVMFuzzerTestOneInput`; CMake globs the
directory, so no build-system change is needed, and the workflow iterates
over `fuzz/*.c`.  Add seeds under `fuzz/corpus/<name>/` and, for the nightly
matrix, one line in `.github/workflows/fuzz.yml`.
