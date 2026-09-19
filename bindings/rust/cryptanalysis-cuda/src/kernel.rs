//! Getting the kernel onto the device: embedded PTX or NVRTC.

use cudarc::nvrtc::{CompileOptions, Ptx};

use crate::error::{Error, Result};
use crate::probe;

/// How the kernel PTX was (or would be) obtained.
///
/// See the [crate documentation](crate) for the two paths.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum PtxSource {
    /// `build.rs` found a CUDA compiler and the PTX is baked into the binary.
    Embedded,
    /// No PTX was embedded, but NVRTC is present and will compile the kernel
    /// when a [`CudaRho`](crate::CudaRho) is created.
    Nvrtc,
    /// Neither path is available; [`CudaRho::new`](crate::CudaRho::new) will
    /// fail with [`Error::PtxUnavailable`].
    Unavailable,
}

impl std::fmt::Display for PtxSource {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let s = match self {
            PtxSource::Embedded => "embedded (compiled by build.rs)",
            PtxSource::Nvrtc => "NVRTC (compiled at run time)",
            PtxSource::Unavailable => "unavailable",
        };
        f.write_str(s)
    }
}

/// The C++-mangled name of `ca_rho_walk_kernel(ca_gpu_rho_args)` as emitted
/// from `cuda/rho_kernel.cu`.
const EMBEDDED_ENTRY: &str = "_Z18ca_rho_walk_kernel15ca_gpu_rho_args";
/// The `extern "C"` entry point of the NVRTC wrapper.
const NVRTC_ENTRY: &str = "ca_rho_walk_kernel_c";

/// The device kernel body, shared verbatim with the C library and the host
/// emulator.  Embedded as text so that NVRTC can compile it without the
/// repository being present at run time.
const DEVICE_HEADER: &str = include_str!("../../../../cuda/ca_device.cuh");
/// The `__global__` wrapper for the NVRTC path (see `src/kernel_nvrtc.cu`).
const NVRTC_WRAPPER: &str = include_str!("kernel_nvrtc.cu");

/// NVRTC has no `<stdint.h>`, so supply the fixed-width types the shared
/// header needs.  These are the CUDA device types, so the struct layout is
/// identical to the one `cc` computes on the host.
const NVRTC_PRELUDE: &str = "\
typedef unsigned char uint8_t;\n\
typedef signed char int8_t;\n\
typedef unsigned short uint16_t;\n\
typedef short int16_t;\n\
typedef unsigned int uint32_t;\n\
typedef int int32_t;\n\
typedef unsigned long long uint64_t;\n\
typedef long long int64_t;\n";

/// The PTX compiled by `build.rs`, if a CUDA compiler was found.
///
/// The text is the output of `nvcc --ptx` / `clang -x cuda
/// --cuda-device-only -S` on `cuda/rho_kernel.cu`, so it contains the same
/// `ca_rho_walk_kernel` the C library launches.
#[cfg(ca_embedded_ptx)]
pub fn embedded_ptx() -> Option<&'static str> {
    Some(include_str!(env!("CA_CUDA_PTX")))
}

/// The PTX compiled by `build.rs`, if a CUDA compiler was found.
#[cfg(not(ca_embedded_ptx))]
pub fn embedded_ptx() -> Option<&'static str> {
    None
}

/// Which of the two PTX paths this build will use.
///
/// ```
/// // On a machine with neither a CUDA compiler nor NVRTC this is `Unavailable`,
/// // and it never panics.
/// let _ = cryptanalysis_cuda::ptx_source();
/// ```
pub fn ptx_source() -> PtxSource {
    if embedded_ptx().is_some() {
        PtxSource::Embedded
    } else if probe::nvrtc_available() {
        PtxSource::Nvrtc
    } else {
        PtxSource::Unavailable
    }
}

/// How to satisfy `<stdint.h>` in the source handed to NVRTC.
///
/// `cuda/ca_device.cuh` is never modified on disk; only the in-memory copy is
/// adjusted, and only on its single `#include` line.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum StdintMode {
    /// Drop the include and supply the fixed-width typedefs ourselves.  This
    /// is what today's NVRTC needs.
    Shim,
    /// Drop the include and rely on NVRTC already declaring the types.
    Builtin,
    /// Leave the header exactly as it is (an NVRTC that ships `<stdint.h>`).
    Keep,
}

/// The exact source text handed to NVRTC: the shared device header followed by
/// the `__global__` wrapper from `src/kernel_nvrtc.cu`.
pub(crate) fn nvrtc_source(mode: StdintMode) -> String {
    const INCLUDE: &str = "#include <stdint.h>";
    const REPLACEMENT: &str = "/* <stdint.h> supplied by the host (NVRTC has none) */";
    let mut out = String::with_capacity(DEVICE_HEADER.len() + NVRTC_WRAPPER.len() + 512);
    match mode {
        StdintMode::Shim => {
            out.push_str(NVRTC_PRELUDE);
            out.push_str(&DEVICE_HEADER.replace(INCLUDE, REPLACEMENT));
        }
        StdintMode::Builtin => out.push_str(&DEVICE_HEADER.replace(INCLUDE, REPLACEMENT)),
        StdintMode::Keep => out.push_str(DEVICE_HEADER),
    }
    out.push('\n');
    out.push_str(NVRTC_WRAPPER);
    out.push('\n');
    out
}

/// A loaded kernel: the PTX plus the name to look up in the module.
pub(crate) struct Kernel {
    pub ptx: Ptx,
    pub entry: &'static str,
    pub source: PtxSource,
}

/// Obtain the kernel, preferring the build-time PTX.
pub(crate) fn load(arch: Option<&'static str>) -> Result<Kernel> {
    if let Some(ptx) = embedded_ptx() {
        return Ok(Kernel {
            ptx: Ptx::from_src(ptx),
            entry: EMBEDDED_ENTRY,
            source: PtxSource::Embedded,
        });
    }
    if !probe::nvrtc_available() {
        return Err(Error::PtxUnavailable(
            "build.rs found no CUDA compiler (set CUDA_PATH so nvcc or clang -x cuda can be \
             used) and libnvrtc is not installed for the run-time fallback"
                .into(),
        ));
    }
    let opts = CompileOptions {
        arch,
        name: Some("ca_rho_walk_kernel.cu".into()),
        ..Default::default()
    };
    // Today's NVRTC needs the typedef shim, but try the other two shapes too
    // rather than fail outright if a future release declares the fixed-width
    // types itself or starts shipping <stdint.h>.  The first error is the one
    // worth reporting.
    let mut first_err = None;
    let mut compiled = None;
    for mode in [StdintMode::Shim, StdintMode::Builtin, StdintMode::Keep] {
        match cudarc::nvrtc::compile_ptx_with_opts(nvrtc_source(mode), opts.clone()) {
            Ok(ptx) => {
                compiled = Some(ptx);
                break;
            }
            Err(e) => first_err.get_or_insert(e),
        };
    }
    let ptx = match compiled {
        Some(ptx) => ptx,
        None => return Err(Error::from(first_err.expect("a failure was recorded"))),
    };
    Ok(Kernel {
        ptx,
        entry: NVRTC_ENTRY,
        source: PtxSource::Nvrtc,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nvrtc_source_is_self_contained() {
        let src = nvrtc_source(StdintMode::Shim);
        // NVRTC resolves no includes at all, so none may be left.
        assert!(!src.contains("#include"), "no unresolvable includes");
        assert!(src.contains("typedef unsigned long long uint64_t;"));
        // the shared kernel body and the wrapper both made it in
        assert!(src.contains("ca_dev_rho_thread"));
        assert!(src.contains("struct ca_gpu_rho_args"));
        assert!(src.contains("__global__ void ca_rho_walk_kernel_c"));
        // the header itself is untouched apart from the include line.
        // Matched token by token: clang-format aligns consecutive macros, so
        // the run of spaces before the value is not stable.
        assert!(
            src.lines().any(|l| {
                let mut t = l.split_whitespace();
                t.next() == Some("#define")
                    && t.next() == Some("CA_GPU_AUX")
                    && t.next() == Some("8")
            }),
            "CA_GPU_AUX is defined as 8 in the assembled source"
        );
        assert!(src.contains("__umul64hi"));
    }

    #[test]
    fn the_other_stdint_modes_are_well_formed() {
        let builtin = nvrtc_source(StdintMode::Builtin);
        assert!(!builtin.contains("#include"));
        assert!(!builtin.contains("typedef unsigned long long uint64_t;"));
        assert!(builtin.contains("ca_rho_walk_kernel_c"));
        let keep = nvrtc_source(StdintMode::Keep);
        assert!(keep.contains("#include <stdint.h>"));
        assert!(keep.contains("ca_rho_walk_kernel_c"));
    }

    #[test]
    fn ptx_source_does_not_panic_without_cuda() {
        let s = ptx_source();
        assert!(matches!(
            s,
            PtxSource::Embedded | PtxSource::Nvrtc | PtxSource::Unavailable
        ));
        assert!(!s.to_string().is_empty());
    }

    #[cfg(ca_embedded_ptx)]
    #[test]
    fn embedded_ptx_is_real_ptx() {
        let ptx = embedded_ptx().expect("cfg(ca_embedded_ptx) implies Some");
        assert!(!ptx.is_empty());
        assert!(ptx.contains(".target sm_"), "missing .target directive");
        assert!(ptx.contains("ca_rho_walk_kernel"));
        assert!(ptx.contains(EMBEDDED_ENTRY), "mangled entry point present");
        assert_eq!(ptx_source(), PtxSource::Embedded);
    }
}
