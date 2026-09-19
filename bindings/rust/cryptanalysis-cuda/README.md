# cryptanalysis-cuda

Rust host driver for libcryptanalysis' CUDA Pollard rho kernel.

The device code is **not** duplicated here.  It is the repository's
`cuda/ca_device.cuh` — the very translation unit the C library compiles for
the GPU (`cuda/rho_kernel.cu`) and, as plain C11, for its host emulator
(`src/gpu_emulate.c`).  This crate is the host half only: it builds the
multiplier table, picks the launch geometry and the distinguished-point
density, runs the launch loop, drains distinguished points, solves collisions
and re-seeds useless walks, exactly as `src/gpu_rho.c` does.  Group arithmetic
and the verification of every candidate exponent go through the safe
[`cryptanalysis`](../cryptanalysis) crate.

Unlike the C library, this crate talks to the GPU through the CUDA **driver**
API via [`cudarc`], with `dynamic-loading`: nothing links against `libcuda`,
so the crate builds and its tests run on machines with no NVIDIA driver at
all.

## Requirements

| To …                               | You need                                                   |
| ---------------------------------- | ---------------------------------------------------------- |
| build the crate                    | nothing beyond a C compiler (for `cryptanalysis-sys`)        |
| embed the PTX at build time        | `nvcc`, or `clang` with a CUDA toolkit (`--cuda-path`)       |
| run on a GPU with embedded PTX     | an NVIDIA driver (`libcuda.so`)                              |
| run on a GPU without embedded PTX  | an NVIDIA driver **and** NVRTC (`libnvrtc.so`)               |

## Where the PTX comes from

1. **Build time (preferred).**  `build.rs` tries, in order, `$NVCC`,
   `$CUDA_PATH/bin/nvcc`, `$CUDA_HOME/bin/nvcc`, `nvcc` on `PATH`, then
   `clang -x cuda --cuda-path=$CUDA_PATH` and finally plain `clang -x cuda`.
   Each candidate is *validated by actually compiling*, so a toolkit shim that
   only answers `--version` cannot shadow a working compiler.  On success the
   PTX lands in `$OUT_DIR` and is embedded with `include_str!`; the entry
   point is the C++-mangled `_Z18ca_rho_walk_kernel15ca_gpu_rho_args`.

   The clang invocation is equivalent to:

   ```sh
   clang -x cuda --cuda-device-only --cuda-path="$CUDA_PATH" \
         --cuda-gpu-arch=sm_70 -O3 -Iinclude -Icuda -Isrc \
         -Wno-unknown-cuda-version -S -o rho_kernel.ptx cuda/rho_kernel.cu
   ```

2. **Run time (fallback).**  With no embedded PTX, NVRTC compiles the kernel
   when a `CudaRho` is created.  NVRTC cannot include `<cuda_runtime.h>`, so
   instead of `cuda/rho_kernel.cu` the crate concatenates the embedded text of
   `cuda/ca_device.cuh` with the small `extern "C"` wrapper in
   `src/kernel_nvrtc.cu`, and prepends the fixed-width typedefs NVRTC has no
   `<stdint.h>` for.  The shared header on disk is never modified.  The entry
   point is then the unmangled `ca_rho_walk_kernel_c`.

`cryptanalysis_cuda::ptx_source()` reports which path a build took
(`Embedded`, `Nvrtc` or `Unavailable`), and never panics.

### Choosing the architecture

`CA_CUDA_ARCH` selects the build-time target; it defaults to `sm_70`
(Volta), which the driver will JIT forward to any newer device.

```sh
CUDA_PATH=/usr/local/cuda CA_CUDA_ARCH=sm_86 cargo build -p cryptanalysis-cuda
```

Set `CA_CUDA_NO_PTX=1` to skip the build-time compile and force the NVRTC
path.  `CA_CUDA_CLANG` overrides the clang executable.  If no compiler works
the build prints a `cargo:warning` and still succeeds.

## Usage

```rust,no_run
use cryptanalysis::Group;
use cryptanalysis_cuda::{device_count, CudaRho, Params};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    if device_count() == 0 {
        eprintln!("no CUDA device");
        return Ok(());
    }

    // A prime-order subgroup of Z_p^*.
    let g = Group::zp(2_000_000_579, 1_000_000_289)?;
    let base = g.find_generator(1)?;
    let target = g.mul(&base, 123_456_789)?;

    let params = Params {
        seed: 7,          // 0 => from the OS
        dp_bits: -1,      // -1 => auto
        ..Params::default()
    };

    // Keep the CudaRho alive to reuse the context and the loaded module.
    let rho = CudaRho::new(&params)?;
    let (x, stats) = rho.solve(&g, base, target, &params)?;

    assert_eq!(x, 123_456_789);
    println!(
        "{x} after {} group ops in {} launches ({} walks, {} DPs, {} restarts, {:.3}s)",
        stats.group_ops, stats.launches, stats.walks(), stats.dps, stats.restarts, stats.seconds
    );
    Ok(())
}
```

`Params` mirrors `ca_gpu_rho_params` from `include/cryptanalysis/ca_gpu.h`
(device ordinal, `threads_per_block`, `blocks`, `steps_per_launch`, `r`,
`dp_bits`, `negation_map`, `seed`, `max_ops`), with the same "0 / -1 means
auto" conventions.  Elliptic curves work the same way; the negation map only
applies there.

```sh
cargo run -p cryptanalysis-cuda --example gpu_rho        # Z_p^*
cargo run -p cryptanalysis-cuda --example gpu_rho -- ec  # elliptic curve
```

The example prints a message and exits successfully when no device is present.

## Tests

`cargo test -p cryptanalysis-cuda` passes without a GPU.  It covers the
Montgomery and RNG ports, the `ca_gpu_rho_args` field offsets, the parameter
auto-tuning (with the worked-out values for the fixtures in
`tests/test_gpu.c`), the collision solver including the negation-map sign case
and the `gcd` branch, and that `device_count()` / `solve` behave rather than
panic with no driver.  Tests that need real hardware skip themselves with an
`eprintln!` when `device_count() == 0`.

[`cudarc`]: https://docs.rs/cudarc
