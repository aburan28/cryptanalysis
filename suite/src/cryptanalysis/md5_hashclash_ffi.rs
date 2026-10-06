//! FFI scaffolding for Marc Stevens' `hashclash` C++ library.
//!
//! `hashclash` (<https://github.com/cr-marcstevens/hashclash>) is the
//! reference implementation of chosen-prefix MD5 collisions, with
//! GPU acceleration and the path-construction engine that powers
//! the 2008 rogue-CA and 2012 Flame collisions.  Reimplementing it
//! is a multi-year research project (see `md5_chosen_prefix`).
//! Instead, this module provides:
//!
//! 1. **`build.rs` hooks** — autodetects a `hashclash` checkout via
//!    the `HASHCLASH_PREFIX` env var and links its static libraries.
//! 2. **`extern "C"` declarations** — for the small subset of
//!    `hashclash` entry points needed for a chosen-prefix attack:
//!      - `cpc_init(prefix_p, len_p, prefix_q, len_q) -> handle`
//!      - `cpc_run(handle, options) -> status`
//!      - `cpc_get_result(handle, &mut out_m, &mut out_m_prime)`
//!      - `cpc_free(handle)`
//! 3. **Safe Rust wrapper** — `ChosenPrefixCollision::new(p, q)` ⇒
//!    `.find()?` returning `(Vec<u8>, Vec<u8>)`.
//!
//! **Status**: scaffolding only.  The FFI compiles regardless of
//! whether `hashclash` is present.  When `HASHCLASH_PREFIX` is set
//! at build time, the `extern` block links to real symbols; without
//! it, all calls return `Err(FfiError::NotLinked)` from the safe
//! wrapper.  The `cpc_*` C ABI defined below is **not yet upstream**
//! in `hashclash` — integrating it requires a small (~200 LOC) C++
//! shim around `hashclash`'s `cpc/main_cpu.cpp` driver.
//!
//! ## Usage (when fully wired)
//!
//! ```ignore
//! use cryptanalysis_suite::cryptanalysis::md5_hashclash_ffi::ChosenPrefixCollision;
//!
//! let prefix_p = b"Alice's CSR:\n";
//! let prefix_q = b"Bob's CSR:\n";
//! let cpc = ChosenPrefixCollision::new(prefix_p, prefix_q);
//! let (m, m_prime) = cpc.find()?;
//! assert_eq!(md5(&m, 64), md5(&m_prime, 64));
//! ```
//!
//! ## Build wiring (`build.rs`)
//!
//! Add to `build.rs`:
//! ```ignore
//! fn main() {
//!     if let Ok(prefix) = std::env::var("HASHCLASH_PREFIX") {
//!         println!("cargo:rustc-link-search=native={}/lib", prefix);
//!         println!("cargo:rustc-link-lib=static=hashclash_cpc");
//!         println!("cargo:rustc-link-lib=static=hashclash_core");
//!         println!("cargo:rustc-link-lib=stdc++");
//!         println!("cargo:rustc-cfg=hashclash_linked");
//!     }
//!     println!("cargo:rerun-if-env-changed=HASHCLASH_PREFIX");
//! }
//! ```

use std::os::raw::{c_int, c_uchar, c_ulong};

/// Errors from the safe wrapper.
#[derive(Debug)]
pub enum FfiError {
    /// Built without `HASHCLASH_PREFIX` — no library to call.
    NotLinked,
    /// `cpc_init` returned a null handle.
    InitFailed,
    /// `cpc_run` returned a non-zero status.
    RunFailed(c_int),
    /// `cpc_get_result` reported a buffer overrun.
    ResultBufferTooSmall,
}

// ────────────────────────────────────────────────────────────────────
// C ABI declarations.  When `hashclash` is not linked, we provide
// stub implementations that always fail with `FfiError::NotLinked`.
// ────────────────────────────────────────────────────────────────────

/// Opaque handle to a `hashclash` chosen-prefix-collision session.
#[repr(C)]
pub struct CpcHandle {
    _opaque: [u8; 0],
}

/// Options for `cpc_run`.  Mirrors `hashclash`'s `cpc_options` struct.
#[repr(C)]
pub struct CpcOptions {
    pub max_blocks: c_int,
    pub birthday_dp_bits: c_int,
    pub birthday_max_trails: c_ulong,
    pub use_gpu: c_int,
    pub seed: c_ulong,
}

impl Default for CpcOptions {
    fn default() -> Self {
        CpcOptions {
            max_blocks: 9,
            birthday_dp_bits: 26,
            birthday_max_trails: 1 << 30,
            use_gpu: 1,
            seed: 0,
        }
    }
}

#[cfg(hashclash_linked)]
extern "C" {
    fn cpc_init(
        prefix_p: *const c_uchar,
        len_p: c_ulong,
        prefix_q: *const c_uchar,
        len_q: c_ulong,
    ) -> *mut CpcHandle;

    fn cpc_run(handle: *mut CpcHandle, opts: *const CpcOptions) -> c_int;

    fn cpc_get_result(
        handle: *mut CpcHandle,
        out_m: *mut c_uchar,
        out_m_cap: *mut c_ulong,
        out_mp: *mut c_uchar,
        out_mp_cap: *mut c_ulong,
    ) -> c_int;

    fn cpc_free(handle: *mut CpcHandle);
}

// Stub implementations when not linked — surface NotLinked on every call.
#[cfg(not(hashclash_linked))]
unsafe fn cpc_init(
    _prefix_p: *const c_uchar,
    _len_p: c_ulong,
    _prefix_q: *const c_uchar,
    _len_q: c_ulong,
) -> *mut CpcHandle {
    std::ptr::null_mut()
}

#[cfg(not(hashclash_linked))]
unsafe fn cpc_run(_h: *mut CpcHandle, _o: *const CpcOptions) -> c_int {
    -1
}

#[cfg(not(hashclash_linked))]
unsafe fn cpc_get_result(
    _h: *mut CpcHandle,
    _om: *mut c_uchar,
    _omc: *mut c_ulong,
    _omp: *mut c_uchar,
    _ompc: *mut c_ulong,
) -> c_int {
    -1
}

#[cfg(not(hashclash_linked))]
unsafe fn cpc_free(_h: *mut CpcHandle) {}

// ────────────────────────────────────────────────────────────────────
// Safe Rust wrapper.
// ────────────────────────────────────────────────────────────────────

/// Compile-time flag: true iff `build.rs` linked `hashclash`.
pub const HASHCLASH_LINKED: bool = cfg!(hashclash_linked);

/// Safe handle to a chosen-prefix-collision computation.
pub struct ChosenPrefixCollision {
    prefix_p: Vec<u8>,
    prefix_q: Vec<u8>,
    opts: CpcOptions,
}

impl ChosenPrefixCollision {
    pub fn new(prefix_p: &[u8], prefix_q: &[u8]) -> Self {
        Self {
            prefix_p: prefix_p.to_vec(),
            prefix_q: prefix_q.to_vec(),
            opts: CpcOptions::default(),
        }
    }

    pub fn with_options(mut self, opts: CpcOptions) -> Self {
        self.opts = opts;
        self
    }

    /// Run the chosen-prefix collision search.  Returns
    /// `(message, message_prime)` such that `md5(message) ==
    /// md5(message_prime)` and `message` starts with `prefix_p`,
    /// `message_prime` starts with `prefix_q`.
    pub fn find(&self) -> Result<(Vec<u8>, Vec<u8>), FfiError> {
        if !HASHCLASH_LINKED {
            return Err(FfiError::NotLinked);
        }
        unsafe {
            let handle = cpc_init(
                self.prefix_p.as_ptr(),
                self.prefix_p.len() as c_ulong,
                self.prefix_q.as_ptr(),
                self.prefix_q.len() as c_ulong,
            );
            if handle.is_null() {
                return Err(FfiError::InitFailed);
            }
            let status = cpc_run(handle, &self.opts);
            if status != 0 {
                cpc_free(handle);
                return Err(FfiError::RunFailed(status));
            }
            // Allocate output buffers: prefix + up to 9 near-collision blocks.
            let cap = self.prefix_p.len().max(self.prefix_q.len()) + 9 * 128;
            let mut out_m = vec![0u8; cap];
            let mut out_mp = vec![0u8; cap];
            let mut cap_m = cap as c_ulong;
            let mut cap_mp = cap as c_ulong;
            let rc = cpc_get_result(
                handle,
                out_m.as_mut_ptr(),
                &mut cap_m,
                out_mp.as_mut_ptr(),
                &mut cap_mp,
            );
            cpc_free(handle);
            if rc != 0 {
                return Err(FfiError::ResultBufferTooSmall);
            }
            out_m.truncate(cap_m as usize);
            out_mp.truncate(cap_mp as usize);
            Ok((out_m, out_mp))
        }
    }
}

// ────────────────────────────────────────────────────────────────────
// Tests.
// ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **FFI test**: without `HASHCLASH_PREFIX` at build time, the
    /// safe wrapper returns `NotLinked`.  This is the expected state
    /// in CI; integration with a real `hashclash` checkout would be a
    /// separate task gated on env-var presence.
    #[test]
    fn ffi_not_linked_by_default() {
        let cpc = ChosenPrefixCollision::new(b"A", b"B");
        let r = cpc.find();
        match r {
            Err(FfiError::NotLinked) => {
                println!("\n=== hashclash FFI: not linked (expected) ===");
            }
            other => panic!("expected NotLinked, got {:?}", other),
        }
    }

    /// **FFI test**: the option struct round-trips through Rust's
    /// default initialiser.
    #[test]
    fn ffi_options_default() {
        let o = CpcOptions::default();
        assert_eq!(o.max_blocks, 9);
        assert_eq!(o.birthday_dp_bits, 26);
        assert_eq!(o.use_gpu, 1);
    }
}
