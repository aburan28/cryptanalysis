//! Drives libcryptanalysis' CUDA Pollard rho kernel from Rust through the
//! CUDA **driver** API.
//!
//! The device code is not written here: it is the repository's
//! `cuda/ca_device.cuh`, the same translation unit the C library compiles for
//! the GPU (`cuda/rho_kernel.cu`) and, as plain C11, for its host emulator.
//! This crate is only the host half - multipliers, launch geometry, the
//! distinguished-point protocol, collision solving and walk restarts - ported
//! from `src/gpu_rho.c` onto [`cudarc`].  Group arithmetic and the final
//! verification of every candidate exponent go through the safe
//! [`cryptanalysis`] crate, so a returned logarithm has always been checked
//! with a scalar multiplication.
//!
//! # Two ways to get the PTX
//!
//! 1. **Build time (preferred).**  `build.rs` looks for `nvcc` (under
//!    `$CUDA_PATH`, `$CUDA_HOME` or on `PATH`) and then for `clang -x cuda
//!    --cuda-path=$CUDA_PATH`, and compiles `cuda/rho_kernel.cu` to PTX for
//!    `$CA_CUDA_ARCH` (default `sm_70`).  The result is embedded with
//!    `include_str!` and the entry point is the C++-mangled
//!    `_Z18ca_rho_walk_kernel15ca_gpu_rho_args`.  Each candidate compiler is
//!    validated by actually producing PTX, so a toolkit stub cannot shadow a
//!    working one.  If none works the build still succeeds, with a
//!    `cargo:warning`.
//! 2. **Run time (fallback).**  With no embedded PTX the kernel is compiled by
//!    NVRTC when a [`CudaRho`] is created.  NVRTC cannot use
//!    `<cuda_runtime.h>`, so instead of `cuda/rho_kernel.cu` the crate
//!    concatenates the embedded text of `cuda/ca_device.cuh` with the small
//!    `extern "C"` wrapper in `src/kernel_nvrtc.cu` and supplies the
//!    fixed-width typedefs NVRTC has no `<stdint.h>` for.  The shared header
//!    is never modified; only this in-memory copy is adjusted.
//!
//! [`ptx_source()`] reports which path a given build will take.
//!
//! # No GPU, no problem
//!
//! `cudarc` is used with `dynamic-loading`, so nothing links against
//! `libcuda` and the crate builds and tests fine on a machine with no NVIDIA
//! driver.  cudarc's loader *panics* when the library is missing, so every
//! entry point here `dlopen`s it first: [`device_count()`] returns 0 and
//! [`CudaRho::new`] returns [`Error::NoDriver`] rather than aborting.
//!
//! # Example
//!
//! ```no_run
//! use cryptanalysis::Group;
//! use cryptanalysis_cuda::{device_count, CudaRho, Params};
//!
//! if device_count() == 0 {
//!     eprintln!("no CUDA device");
//!     return Ok(());
//! }
//! let g = Group::zp(2_000_000_579, 1_000_000_289)?;
//! let base = g.find_generator(1)?;
//! let target = g.mul(&base, 123_456_789)?;
//!
//! let params = Params { seed: 7, ..Params::default() };
//! let (x, stats) = CudaRho::new(&params)?.solve(&g, base, target, &params)?;
//! assert_eq!(x, 123_456_789);
//! println!("{} ops in {} launches", stats.group_ops, stats.launches);
//! # Ok::<(), cryptanalysis_cuda::Error>(())
//! ```

#![deny(missing_docs)]
#![warn(rust_2018_idioms)]

mod args;
mod arith;
mod error;
mod kernel;
mod plan;
mod probe;
mod solver;

pub use error::{Error, Result};
pub use kernel::{embedded_ptx, ptx_source, PtxSource};
pub use plan::Params;
pub use solver::{device_count, device_name, solve, CudaRho};

// Kernel geometry constants read out of `cuda/ca_device.cuh` at build time,
// so that the host can never disagree with the compiled kernel
// (`WALKS_PER_THREAD` = CA_GPU_W, `AUX_WORDS` = CA_GPU_AUX).
include!(concat!(env!("OUT_DIR"), "/kernel_consts.rs"));

/// Work statistics for one [`CudaRho::solve`] call.
///
/// The counters line up with the `ca_stats` fields `ca_gpu_rho_solve` fills
/// in: `group_ops` counts walk steps summed over all walks (plus the host-side
/// multiplier setup), `dps` is `iterations`, `restarts` is `collisions`,
/// `launches` is `reserved` and `threads` is the number of device threads
/// (each running [`WALKS_PER_THREAD`] walks).
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub struct Stats {
    /// Group operations performed, walk steps included.
    pub group_ops: u64,
    /// Kernel launches issued.
    pub launches: u64,
    /// Distinguished points drained from the device.
    pub dps: u64,
    /// Walks re-seeded after a useless collision.
    pub restarts: u64,
    /// Wall-clock seconds spent in `solve`.
    pub seconds: f64,
    /// Device threads used (`nthreads`).
    pub threads: u32,
}

impl Stats {
    /// Zeroed statistics carrying only the elapsed time.
    pub(crate) fn elapsed(started: std::time::Instant) -> Stats {
        Stats {
            seconds: started.elapsed().as_secs_f64(),
            ..Stats::default()
        }
    }

    /// Walks run on the device, i.e. `threads * WALKS_PER_THREAD`.
    pub fn walks(&self) -> u64 {
        u64::from(self.threads) * u64::from(WALKS_PER_THREAD)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kernel_constants_match_the_shared_header() {
        // `cuda/ca_device.cuh` defaults; build.rs re-reads them every build.
        assert_eq!(WALKS_PER_THREAD, 8);
        assert_eq!(AUX_WORDS, 8);
    }

    #[test]
    fn stats_walks() {
        let st = Stats {
            threads: 5,
            ..Stats::default()
        };
        assert_eq!(st.walks(), 40);
    }
}
