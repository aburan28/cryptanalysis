//! The crate's error type.

use std::fmt;

use cudarc::driver::DriverError;
use cudarc::nvrtc::CompileError;

/// `Result` alias used throughout the crate.
pub type Result<T> = std::result::Result<T, Error>;

/// Everything that can go wrong while driving the GPU kernel.
#[derive(Debug)]
pub enum Error {
    /// The CUDA driver library (`libcuda.so` / `nvcuda.dll`) could not be
    /// loaded, so this machine has no usable NVIDIA driver.
    NoDriver,
    /// The driver is present but the requested device ordinal does not exist.
    NoDevice {
        /// The ordinal that was asked for.
        requested: usize,
        /// How many devices the driver reports.
        available: usize,
    },
    /// Neither build-time PTX nor NVRTC could provide the kernel.  The string
    /// explains which paths were tried.
    PtxUnavailable(String),
    /// NVRTC was available but rejected the kernel source.
    Nvrtc(Box<CompileError>),
    /// An error from the CUDA driver API (allocation, launch, copy, ...).
    Driver(DriverError),
    /// An error from the `cryptanalysis` C library (group arithmetic, ...).
    Library(cryptanalysis::Error),
    /// The request itself is not solvable as asked (e.g. unknown group order).
    Invalid(String),
    /// `Params::max_ops` was exceeded before a collision solved the logarithm.
    Limit {
        /// Group operations performed when the limit was hit.
        ops: u64,
    },
    /// The search finished without finding the logarithm (only possible for
    /// the tiny-group brute-force path, where the exponent range is finite).
    NotFound,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::NoDriver => write!(
                f,
                "no CUDA driver: could not load libcuda (install an NVIDIA driver)"
            ),
            Error::NoDevice {
                requested,
                available,
            } => write!(f, "no CUDA device {requested} ({available} available)"),
            Error::PtxUnavailable(why) => write!(f, "kernel PTX unavailable: {why}"),
            Error::Nvrtc(e) => write!(f, "NVRTC could not compile the kernel: {e}"),
            Error::Driver(e) => write!(f, "CUDA driver error: {e}"),
            Error::Library(e) => write!(f, "cryptanalysis: {e}"),
            Error::Invalid(m) => write!(f, "invalid request: {m}"),
            Error::Limit { ops } => write!(f, "work limit reached after {ops} group operations"),
            Error::NotFound => write!(f, "no logarithm found"),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Driver(e) => Some(e),
            Error::Library(e) => Some(e),
            Error::Nvrtc(e) => Some(e.as_ref()),
            _ => None,
        }
    }
}

impl From<DriverError> for Error {
    fn from(e: DriverError) -> Error {
        Error::Driver(e)
    }
}

impl From<cryptanalysis::Error> for Error {
    fn from(e: cryptanalysis::Error) -> Error {
        Error::Library(e)
    }
}

impl From<CompileError> for Error {
    fn from(e: CompileError) -> Error {
        Error::Nvrtc(Box::new(e))
    }
}
