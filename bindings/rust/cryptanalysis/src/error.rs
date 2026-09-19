//! Error type mapping the library's `ca_status` codes.

use std::ffi::CStr;
use std::fmt;

use cryptanalysis_sys as sys;

/// An error raised by the C library.
///
/// Each variant corresponds to one non-zero `ca_status` code and carries the
/// thread-local message from `ca_last_error()` at the time the error was
/// observed.  Note that the C library never clears that buffer, so for a few
/// failure paths that do not set a message (e.g. an interval solver that
/// simply exhausted its range) the text may describe an *earlier* error on
/// the same thread; the variant itself is always accurate.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Error {
    /// `CA_ERR_INVALID`: invalid argument (bad modulus, point not on curve, ...).
    Invalid(String),
    /// `CA_ERR_NOT_FOUND`: the search space was exhausted without a solution.
    NotFound(String),
    /// `CA_ERR_NOMEM`: allocation failure.
    NoMem(String),
    /// `CA_ERR_LIMIT`: an explicit work/memory/time limit was reached.
    Limit(String),
    /// `CA_ERR_UNSUPPORTED`: the operation is not supported for this group/params.
    Unsupported(String),
    /// `CA_ERR_INTERNAL`: internal consistency failure (should not happen).
    Internal(String),
    /// `CA_ERR_SINGULAR`: linear system had no usable solution.
    Singular(String),
    /// A status code this crate does not know about (newer library?).
    Unknown(i32, String),
}

/// `Result` alias used throughout the crate.
pub type Result<T> = std::result::Result<T, Error>;

impl Error {
    /// Build an error for a non-zero status, capturing the thread-local message.
    ///
    /// Callers must only pass non-zero codes (this is not checked in release
    /// builds).
    pub(crate) fn from_status(code: i32) -> Error {
        debug_assert_ne!(code, sys::CA_OK);
        Error::with_message(code, last_error_message())
    }

    /// Build an error for a status code with an explicit message.
    pub(crate) fn with_message(code: i32, msg: String) -> Error {
        match code {
            sys::CA_ERR_INVALID => Error::Invalid(msg),
            sys::CA_ERR_NOT_FOUND => Error::NotFound(msg),
            sys::CA_ERR_NOMEM => Error::NoMem(msg),
            sys::CA_ERR_LIMIT => Error::Limit(msg),
            sys::CA_ERR_UNSUPPORTED => Error::Unsupported(msg),
            sys::CA_ERR_INTERNAL => Error::Internal(msg),
            sys::CA_ERR_SINGULAR => Error::Singular(msg),
            other => Error::Unknown(other, msg),
        }
    }

    /// The raw `ca_status` code.
    pub fn status(&self) -> i32 {
        match self {
            Error::Invalid(_) => sys::CA_ERR_INVALID,
            Error::NotFound(_) => sys::CA_ERR_NOT_FOUND,
            Error::NoMem(_) => sys::CA_ERR_NOMEM,
            Error::Limit(_) => sys::CA_ERR_LIMIT,
            Error::Unsupported(_) => sys::CA_ERR_UNSUPPORTED,
            Error::Internal(_) => sys::CA_ERR_INTERNAL,
            Error::Singular(_) => sys::CA_ERR_SINGULAR,
            Error::Unknown(c, _) => *c,
        }
    }

    /// The library's static description of the status code (`ca_status_string`).
    pub fn status_string(&self) -> &'static str {
        // SAFETY: ca_status_string returns a pointer to a static C string for
        // every input (unknown codes map to a fixed "unknown" string).
        unsafe {
            let p = sys::ca_status_string(self.status());
            if p.is_null() {
                "unknown status"
            } else {
                CStr::from_ptr(p).to_str().unwrap_or("unknown status")
            }
        }
    }

    /// The detail message captured from `ca_last_error()` (may be empty).
    pub fn message(&self) -> &str {
        match self {
            Error::Invalid(m)
            | Error::NotFound(m)
            | Error::NoMem(m)
            | Error::Limit(m)
            | Error::Unsupported(m)
            | Error::Internal(m)
            | Error::Singular(m)
            | Error::Unknown(_, m) => m,
        }
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let msg = self.message();
        if msg.is_empty() {
            write!(f, "{}", self.status_string())
        } else {
            write!(f, "{}: {}", self.status_string(), msg)
        }
    }
}

impl std::error::Error for Error {}

/// Read the thread-local last-error buffer.
pub(crate) fn last_error_message() -> String {
    // SAFETY: ca_last_error returns a pointer to a NUL-terminated thread-local
    // buffer that is never null.
    unsafe {
        let p = sys::ca_last_error();
        if p.is_null() {
            String::new()
        } else {
            CStr::from_ptr(p).to_string_lossy().into_owned()
        }
    }
}

/// Convert a raw status code into a `Result`.
#[inline]
pub(crate) fn check(code: i32) -> Result<()> {
    if code == sys::CA_OK {
        Ok(())
    } else {
        Err(Error::from_status(code))
    }
}
