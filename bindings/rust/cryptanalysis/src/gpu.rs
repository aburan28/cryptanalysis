//! The GPU (CUDA) Pollard rho solver, through the C library.
//!
//! This drives the CUDA kernel in `cuda/rho_kernel.cu` when the C library
//! was built with `-DCA_CUDA=ON` and a device is present, and otherwise the
//! host emulator, which executes the identical kernel body on the CPU one
//! thread at a time. Either way the algorithm being run is the same code.
//!
//! To launch the kernel from Rust directly, through the CUDA driver API and
//! without going through the C library, use the `cryptanalysis-cuda` crate.

use core::mem::MaybeUninit;

use crate::error::{check, Result};
use crate::group::{Elem, Group};
use crate::options::Stats;
use cryptanalysis_sys as sys;

/// Which backend to run the walk kernel on.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum GpuBackend {
    /// CUDA when the library has it and a device exists, else the emulator.
    #[default]
    Auto,
    /// Require CUDA; [`Error::Unsupported`](crate::Error::Unsupported) when
    /// the library was built without it or no device is present.
    Cuda,
    /// Always the host emulator.
    Emulate,
}

impl GpuBackend {
    fn to_raw(self) -> i32 {
        match self {
            GpuBackend::Auto => sys::CA_GPU_BACKEND_AUTO,
            GpuBackend::Cuda => sys::CA_GPU_BACKEND_CUDA,
            GpuBackend::Emulate => sys::CA_GPU_BACKEND_EMULATE,
        }
    }

    fn from_raw(v: i32) -> GpuBackend {
        match v {
            sys::CA_GPU_BACKEND_CUDA => GpuBackend::Cuda,
            sys::CA_GPU_BACKEND_EMULATE => GpuBackend::Emulate,
            _ => GpuBackend::Auto,
        }
    }
}

/// Options for [`Group::gpu_rho`]. `Default` takes the library's own
/// defaults, in which every numeric field means "choose automatically".
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct GpuOptions {
    /// Which backend to use.
    pub backend: GpuBackend,
    /// CUDA device ordinal.
    pub device: i32,
    /// Threads per block (0 => 128).
    pub threads_per_block: u32,
    /// Blocks per launch (0 => from the group size).
    pub blocks: u32,
    /// Walk steps per launch (0 => auto).
    pub steps_per_launch: u32,
    /// Adding-walk multipliers (0 => auto).
    pub r: u32,
    /// Distinguished-point bits (`None` => auto).
    pub dp_bits: Option<u32>,
    /// Use the negation map on curves.
    pub negation_map: bool,
    /// RNG seed (0 => random).
    pub seed: u64,
    /// Work limit in group operations (0 => unlimited).
    pub max_ops: u64,
}

impl Default for GpuOptions {
    fn default() -> Self {
        let mut raw = MaybeUninit::<sys::CaFfiGpuOptions>::uninit();
        // SAFETY: ca_ffi_gpu_options_default fully initialises the struct.
        let raw = unsafe {
            sys::ca_ffi_gpu_options_default(raw.as_mut_ptr());
            raw.assume_init()
        };
        GpuOptions {
            backend: GpuBackend::from_raw(raw.backend),
            device: raw.device,
            threads_per_block: raw.threads_per_block,
            blocks: raw.blocks,
            steps_per_launch: raw.steps_per_launch,
            r: raw.r,
            dp_bits: if raw.dp_bits < 0 {
                None
            } else {
                Some(raw.dp_bits as u32)
            },
            negation_map: raw.negation_map != 0,
            seed: raw.seed,
            max_ops: raw.max_ops,
        }
    }
}

impl GpuOptions {
    pub(crate) fn to_raw(self) -> sys::CaFfiGpuOptions {
        sys::CaFfiGpuOptions {
            backend: self.backend.to_raw(),
            device: self.device,
            threads_per_block: self.threads_per_block,
            blocks: self.blocks,
            steps_per_launch: self.steps_per_launch,
            r: self.r,
            dp_bits: self.dp_bits.map_or(-1, |b| b as i32),
            negation_map: i32::from(self.negation_map),
            seed: self.seed,
            max_ops: self.max_ops,
        }
    }
}

impl Group {
    /// Pollard rho on the GPU (or its host emulator): solve
    /// `x * base == target` over the whole group.
    ///
    /// Requires a known group [`order`](Group::order). The returned
    /// [`Stats::threads`] is the number of device threads, each of which
    /// owns several walks.
    ///
    /// ```
    /// use cryptanalysis::{Group, GpuBackend, GpuOptions};
    /// let g = Group::zp(2_000_000_579, 1_000_000_289).unwrap();
    /// let gen = g.find_generator(1).unwrap();
    /// let h = g.mul(&gen, 123_456_789).unwrap();
    /// // The emulator always works, with or without a GPU.
    /// let opts = GpuOptions { backend: GpuBackend::Emulate, seed: 7, ..Default::default() };
    /// let (x, _stats) = g.gpu_rho(&gen, &h, &opts).unwrap();
    /// assert_eq!(x, 123_456_789);
    /// ```
    pub fn gpu_rho(&self, base: &Elem, target: &Elem, opts: &GpuOptions) -> Result<(u64, Stats)> {
        let raw = opts.to_raw();
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_gpu_rho(
                self.raw(),
                base.as_ptr(),
                target.as_ptr(),
                &raw,
                &mut x,
                &mut st,
            )
        })?;
        Ok((x, Stats::from_raw(&st)))
    }
}

/// Whether the C library was built with the CUDA backend (`-DCA_CUDA=ON`).
pub fn cuda_compiled() -> bool {
    // SAFETY: no arguments, no state.
    unsafe { sys::ca_ffi_gpu_cuda_compiled() != 0 }
}

/// Number of usable CUDA devices; 0 when CUDA is not compiled in or no
/// driver is present.
pub fn device_count() -> i32 {
    // SAFETY: no arguments, no state.
    unsafe { sys::ca_ffi_gpu_device_count() }
}

/// A description of a CUDA device, or `None` if it cannot be queried.
pub fn device_name(device: i32) -> Option<String> {
    let mut buf = [0i8; 256];
    // SAFETY: buf is a valid writable buffer of the length we pass.
    let rc = unsafe { sys::ca_ffi_gpu_device_name(device, buf.as_mut_ptr(), buf.len()) };
    if rc != 0 {
        return None;
    }
    let bytes: Vec<u8> = buf
        .iter()
        .take_while(|&&c| c != 0)
        .map(|&c| c as u8)
        .collect();
    String::from_utf8(bytes).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn emulator_solves_zp() {
        let g = Group::zp(2_000_000_579, 1_000_000_289).unwrap();
        let gen = g.find_generator(1).unwrap();
        let h = g.mul(&gen, 4242).unwrap();
        let opts = GpuOptions {
            backend: GpuBackend::Emulate,
            seed: 3,
            ..Default::default()
        };
        let (x, stats) = g.gpu_rho(&gen, &h, &opts).unwrap();
        assert_eq!(x, 4242);
        assert!(stats.group_ops > 0);
        assert!(stats.threads > 0);
    }

    #[test]
    fn emulator_solves_curve() {
        let n = Group::ec_count_points(1_000_003, 1, 7).unwrap();
        let mut g = Group::ec(1_000_003, 1, 7, n).unwrap();
        let p = g.random_element(3).unwrap();
        let ord = g.elem_order(&p).unwrap();
        g.set_order(ord, n / ord);
        let q = g.mul(&p, 1234 % ord).unwrap();
        let opts = GpuOptions {
            backend: GpuBackend::Emulate,
            seed: 5,
            ..Default::default()
        };
        let (x, _) = g.gpu_rho(&p, &q, &opts).unwrap();
        assert_eq!(x, 1234 % ord);
    }

    #[test]
    fn options_round_trip_and_defaults() {
        let d = GpuOptions::default();
        assert_eq!(d.backend, GpuBackend::Auto);
        assert_eq!(d.dp_bits, None);
        assert!(d.negation_map);
        let o = GpuOptions {
            dp_bits: Some(4),
            backend: GpuBackend::Cuda,
            ..Default::default()
        };
        let raw = o.to_raw();
        assert_eq!(raw.dp_bits, 4);
        assert_eq!(raw.backend, sys::CA_GPU_BACKEND_CUDA);
    }

    #[test]
    fn cuda_backend_reports_cleanly() {
        let g = Group::zp(2_000_000_579, 1_000_000_289).unwrap();
        let gen = g.find_generator(1).unwrap();
        let h = g.mul(&gen, 99).unwrap();
        let opts = GpuOptions {
            backend: GpuBackend::Cuda,
            ..Default::default()
        };
        let got = g.gpu_rho(&gen, &h, &opts);
        if cuda_compiled() && device_count() > 0 {
            assert_eq!(got.unwrap().0, 99);
        } else {
            // No CUDA: an error, never a panic and never a silent CPU answer.
            assert!(got.is_err());
        }
        assert!(device_count() >= 0);
    }

    #[test]
    fn max_ops_is_enforced() {
        let g = Group::zp(2_000_000_579, 1_000_000_289).unwrap();
        let gen = g.find_generator(1).unwrap();
        let h = g.mul(&gen, 123_456_789).unwrap();
        let opts = GpuOptions {
            backend: GpuBackend::Emulate,
            max_ops: 500,
            seed: 11,
            ..Default::default()
        };
        assert!(g.gpu_rho(&gen, &h, &opts).is_err());
    }
}
