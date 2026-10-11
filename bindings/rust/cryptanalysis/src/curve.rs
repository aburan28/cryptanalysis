//! Curve-aware dispatch: detect a curve's GLV endomorphism and solve with the
//! accelerated Pollard rho.
//!
//! Some curves over `F_p` carry an efficiently computable endomorphism beyond
//! negation ([`Endo::J0`] for `y^2 = x^3 + b` with `p = 1 mod 3`, an order-6
//! automorphism group; [`Endo::J1728`] for `y^2 = x^3 + a x` with
//! `p = 1 mod 4`, order 4).  [`Group::curve_solve`](crate::Group::curve_solve)
//! folds the rho walk by it, for `sqrt(m)` fewer operations.

use std::ffi::{CStr, CString};

use cryptanalysis_sys as sys;

use crate::error::{check, Error, Result};

/// The efficiently computable endomorphism a curve carries, if any.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Endo {
    /// Only the order-2 negation map (a generic curve).
    None,
    /// j-invariant 0 (`y^2 = x^3 + b`): an order-6 automorphism group.
    J0,
    /// j-invariant 1728 (`y^2 = x^3 + a x`): an order-4 automorphism group.
    J1728,
}

impl Endo {
    pub(crate) fn from_raw(v: i32) -> Endo {
        match v {
            1 => Endo::J0,
            2 => Endo::J1728,
            _ => Endo::None,
        }
    }
}

/// A curve's endomorphism structure and the resulting rho speed-up.
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CurveInfo {
    /// Which endomorphism the curve carries.
    pub endo: Endo,
    /// The automorphism group the rho walk folds by (2, 4 or 6).
    pub aut_order: u32,
    /// Field constant: cube root of unity (j0) or sqrt(-1) (j1728) mod p, or 0.
    pub beta: u64,
    /// The eigenvalue `lambda` with `psi(P) = lambda P` (mod order), or 0.
    pub lambda: u64,
    /// `sqrt(aut_order)`: the rho operation-count factor vs a plain `sqrt(n)`.
    pub rho_speedup: f64,
}

/// Detect the endomorphism structure of `y^2 = x^3 + a x + b` over `F_p` for
/// the subgroup of order `order` (0 => geometric structure only, leaving
/// `lambda` unresolved).
pub fn detect(p: u64, a: u64, b: u64, order: u64) -> Result<CurveInfo> {
    let mut endo = 0i32;
    let mut aut_order = 0u32;
    let mut beta = 0u64;
    let mut lambda = 0u64;
    let mut rho_speedup = 0f64;
    // SAFETY: all out pointers are valid for the duration of the call.
    check(unsafe {
        sys::ca_ffi_curve_detect(
            p,
            a,
            b,
            order,
            &mut endo,
            &mut aut_order,
            &mut beta,
            &mut lambda,
            &mut rho_speedup,
        )
    })?;
    Ok(CurveInfo {
        endo: Endo::from_raw(endo),
        aut_order,
        beta,
        lambda,
        rho_speedup,
    })
}

/// Look up a named registry curve, returning `(p, a, b, order)`.
pub fn by_name(name: &str) -> Result<(u64, u64, u64, u64)> {
    let c = CString::new(name).map_err(|_| {
        Error::with_message(sys::CA_ERR_INVALID, "curve name contains a NUL".into())
    })?;
    let (mut p, mut a, mut b, mut order) = (0u64, 0u64, 0u64, 0u64);
    // SAFETY: `c` is a valid NUL-terminated string; the outputs are valid.
    check(unsafe { sys::ca_ffi_curve_by_name(c.as_ptr(), &mut p, &mut a, &mut b, &mut order) })?;
    Ok((p, a, b, order))
}

/// The names of the curves in the registry.
pub fn names() -> Vec<String> {
    let mut out = Vec::new();
    let mut i = 0usize;
    loop {
        // SAFETY: ca_ffi_curve_name returns a static string or null past the end.
        let ptr = unsafe { sys::ca_ffi_curve_name(i) };
        if ptr.is_null() {
            break;
        }
        out.push(
            unsafe { CStr::from_ptr(ptr) }
                .to_string_lossy()
                .into_owned(),
        );
        i += 1;
    }
    out
}
