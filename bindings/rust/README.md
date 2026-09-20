# Rust bindings for libcryptanalysis

Two crates in a Cargo workspace:

| crate | what it is |
|---|---|
| `cryptanalysis-sys` | raw `extern "C"` declarations for the flat ABI in `include/cryptanalysis/ca_ffi.h` (+ `ca_types.h`, `ca_indexcalc.h`); `build.rs` compiles the C sources with the [`cc`](https://crates.io/crates/cc) crate |
| `cryptanalysis`     | safe, idiomatic wrapper: `Group`, `Elem`, `Options`, `Stats`, `Error`, the solvers, Cheon's attack, the `curve` GLV dispatch, `index_calculus`, number-theory helpers |

## Build requirements

* A Rust toolchain (edition 2021; tested with 1.94).
* A C compiler that understands `-std=gnu11` (gcc or clang).  The C library is
  compiled from `../../src/*.c` straight into the Rust build with
  `-O3 -std=gnu11 -D_GNU_SOURCE -DCA_BUILDING`; no CMake step or installed
  shared library is needed.  `pthread` and `m` are linked.
* The crates must stay at `bindings/rust/` inside the repository so that
  `build.rs` can find `include/` and `src/`.

```sh
cd bindings/rust
cargo build
cargo test
```

## Example

```rust
use cryptanalysis::{Group, Options, Solver};

fn main() -> Result<(), cryptanalysis::Error> {
    // Prime-order subgroup of Z_p^* (p = 2000000579, q = 1000000289).
    let g = Group::zp(2_000_000_579, 1_000_000_289)?;
    let gen = g.find_generator(1)?;
    let h = g.mul(&gen, 123_456_789)?;

    // Pohlig-Hellman + automatically chosen solver.
    let (x, stats) = g.dlog(&gen, &h, &Options::default())?;
    assert_eq!(x, 123_456_789);
    println!("x = {x} after {} group ops in {:.3}s", stats.group_ops, stats.seconds);

    // Interval solvers, or an explicit algorithm and seed.
    let opts = Options { seed: 7, threads: 4, solver: Solver::Rho, ..Options::default() };
    let (x, _) = g.kangaroo(&gen, &h, 123_000_000, 124_000_000, &opts)?;
    assert_eq!(x, 123_456_789);

    // Elliptic curve y^2 = x^3 + x + 7 over F_1000003.
    let n = Group::ec_count_points(1_000_003, 1, 7)?;
    let mut e = Group::ec(1_000_003, 1, 7, n)?;
    let p = e.random_element(3)?;
    let ord = e.elem_order(&p)?;
    e.set_order(ord, n / ord);
    let q = e.mul(&p, 4242)?;
    let (k, _) = e.dlog(&p, &q, &Options::default())?;
    assert_eq!(k, 4242 % ord);

    // Index calculus in (Z/pZ)^*.
    use cryptanalysis::index_calculus::{self, IcParams};
    let (x, _) = index_calculus::solve(1_000_003, 2, 424_242, &IcParams::default())?;
    assert_eq!(cryptanalysis::powmod(2, x, 1_000_003), 424_242);
    Ok(())
}
```

## Notes

* `Group` is `Send + Sync`: the C context is immutable after construction
  (the one mutator, `ca_ctx_set_order`, is exposed as `set_order(&mut self)`),
  and the solvers keep all mutable state on their own stack/heap.
* `index_calculus::IcContext` is `Send` but not `Sync`, because `ca_ic_log`
  caches the logarithm of the base inside the context on first use.
* Errors carry the library's thread-local `ca_last_error()` text.  The C
  library never clears that buffer, so on the few failure paths that do not set
  a message the text may describe an earlier error; the `Error` variant (status
  code) is always accurate.
* `cryptanalysis-sys` has a unit test that checks `size_of::<CaFfiOptions>()`
  etc. against `ca_ffi_options_size()` and friends, guarding the hand-written
  struct layouts.
