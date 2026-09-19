# The C ABI and the language bindings

The library has two layers of API:

* the **structured C API** (`ca_group.h`, `ca_bsgs.h`, `ca_rho.h`, ...) used
  by C/C++ programs and by the tools.  It exposes structs such as
  `ca_group` and the per-solver parameter structs; their layout may change
  between minor versions;
* the **flat ABI** in [`ca_ffi.h`](../include/cryptanalysis/ca_ffi.h),
  which the Rust, Go and Python bindings are written against.  It uses only
  opaque handles, plain integers, `uint64_t[4]` element words and a small
  number of POD structs whose sizes can be checked at runtime.

## Conventions

* Every fallible function returns an `int` that is a `ca_status`
  (`0 = CA_OK`, see `ca_types.h`).  The message for the most recent failure
  on the calling thread is available from `ca_last_error()`.
* A group is an opaque `ca_ctx*` created by `ca_ctx_new_zp(p, order)` or
  `ca_ctx_new_ec(p, a, b, order)` and released with `ca_ctx_free`.  A
  `ca_ctx` is immutable after construction (except `ca_ctx_set_order`) and
  may be shared between threads.
* Elements are `uint64_t[4]` in public form (never Montgomery):
  `Z_p^*`: `{residue, 0, 0, 0}`; curves: `{x, y, is_infinity, 0}`.  Every
  element passed in is validated (residue in range, point on the curve).
* Solver options live in `ca_ffi_options` (`ca_ffi_options_default` fills
  the defaults); statistics come back in `ca_stats`.  Index calculus uses
  `ca_ic_params` / `ca_ic_stats` from `ca_indexcalc.h`, which are already
  POD.  `ca_ffi_options_size()`, `ca_stats_size()`, `ca_ic_params_size()`
  and `ca_ic_stats_size()` return the sizes the library was compiled with;
  the bindings assert equality at start-up so a layout mismatch fails
  loudly instead of corrupting memory.
* Interval solvers take `lo, hi` (inclusive); `lo == hi == 0` means the
  whole group `[0, order-1]`.

## Struct layouts

```c
typedef struct ca_stats {          /* 56 bytes */
    uint64_t group_ops, iterations, table_entries, collisions, bytes_peak;
    double   seconds;
    uint32_t threads, reserved;
} ca_stats;

typedef struct ca_ffi_options {    /* 96 bytes */
    uint32_t threads;  uint32_t reserved0;
    uint64_t seed;     uint64_t max_ops;
    uint64_t bsgs_table_size;
    uint32_t rho_r;    int32_t rho_dp_bits;
    uint32_t rho_walks_per_thread;  int32_t rho_negation_map;
    uint64_t rho_max_table_entries;
    uint32_t kangaroo_herd_size;  int32_t kangaroo_dp_bits;
    uint32_t kangaroo_jumps;      uint32_t reserved1;
    uint64_t grumpy_m;  double grumpy_alpha;
    int32_t  solver;    int32_t reserved2;
    uint64_t bsgs_max_prime;
} ca_ffi_options;
```

`ca_ic_params` and `ca_ic_stats` are documented in `ca_indexcalc.h`.

## Building the library for a binding

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
# build/libcryptanalysis.so (and .a), headers in include/
```

Alternatively `cmake --install build` installs headers, libraries and a
`cryptanalysis.pc` pkg-config file.

## Rust (`bindings/rust`)

Two crates: `cryptanalysis-sys` compiles the C sources with the `cc` crate
(no separate CMake step) and exposes the raw `extern "C"` declarations;
`cryptanalysis` is the safe wrapper (`Group`, `Elem`, `Options`, `Stats`,
solver methods returning `Result`).  `cargo test` in `bindings/rust` runs
the tests.

## Go (`bindings/go`)

Module `github.com/aburan28/cryptanalysis/bindings/go`, package
`cryptanalysis`.  It is cgo based and compiles the C sources itself (one
wrapper `.c` per source file), so `go build` needs only a C compiler.
`go test ./...` runs the tests.

## Python (`bindings/python`)

Pure-Python `ctypes` package `cryptanalysis`.  The loader looks for the
shared library in `CRYPTANALYSIS_LIB`, inside the package, in the
developer checkout's `build/` directory, and finally on the system path.
`python3 -m unittest discover -s tests` runs the tests; `pip install .`
compiles the shared library into the package.

## Adding a binding for another language

1. Load `libcryptanalysis` and call `ca_ffi_options_size()` /
   `ca_stats_size()` to check the struct layouts.
2. Wrap `ca_ctx_new_*` / `ca_ctx_free` in whatever resource-management
   idiom the language has.
3. Represent elements as four 64-bit words; validate with
   `ca_ctx_validate` when they come from user input.
4. Map non-zero statuses to exceptions/errors carrying `ca_last_error()`.

Everything in `ca_ffi.h` is safe to call from multiple threads as long as
each `ca_ctx` is not mutated concurrently; the rho solver itself is
multi-threaded internally (`threads` option).
