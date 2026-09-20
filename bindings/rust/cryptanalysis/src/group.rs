//! Group contexts, elements and the discrete-logarithm solvers.

use std::fmt;
use std::ptr::NonNull;

use cryptanalysis_sys as sys;

use crate::error::{check, last_error_message, Error, Result};
use crate::options::{Options, PrecompOptions, Stats};

/// The kind of group a [`Group`] represents.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum Kind {
    /// The multiplicative group `Z_p^*` (or a subgroup of it).
    Zp,
    /// The points of an elliptic curve `y^2 = x^3 + a x + b` over `F_p`.
    Ec,
}

/// A group element in the library's public word form.
///
/// * `Z_p^*`: `words[0]` = residue in `[1, p)`, the rest zero.
/// * `E(F_p)`: `words[0] = x`, `words[1] = y`, `words[2] = 1` for the point at
///   infinity.
///
/// `PartialEq`/`Eq` compare the raw words; that is the right notion of
/// equality for elements produced by this library (the public form is
/// canonical), but you may also use [`Group::equal`].
#[derive(Clone, Copy, PartialEq, Eq, Hash, Default)]
#[repr(transparent)]
pub struct Elem(pub [u64; 4]);

impl Elem {
    /// A `Z_p^*` element from its residue.
    pub const fn zp(residue: u64) -> Elem {
        Elem([residue, 0, 0, 0])
    }

    /// An affine curve point `(x, y)`.
    pub const fn ec(x: u64, y: u64) -> Elem {
        Elem([x, y, 0, 0])
    }

    /// The point at infinity of a curve.
    pub const fn ec_infinity() -> Elem {
        Elem([0, 0, 1, 0])
    }

    /// The raw words.
    pub const fn words(&self) -> &[u64; 4] {
        &self.0
    }

    /// For `Z_p^*`: the residue.  (Same as `x()`.)
    pub const fn residue(&self) -> u64 {
        self.0[0]
    }

    /// For `E(F_p)`: the x coordinate (meaningless at infinity).
    pub const fn x(&self) -> u64 {
        self.0[0]
    }

    /// For `E(F_p)`: the y coordinate (meaningless at infinity).
    pub const fn y(&self) -> u64 {
        self.0[1]
    }

    /// For `E(F_p)`: whether this is the point at infinity.
    pub const fn is_infinity(&self) -> bool {
        self.0[2] != 0
    }

    #[inline]
    pub(crate) fn as_ptr(&self) -> *const u64 {
        self.0.as_ptr()
    }
}

impl From<[u64; 4]> for Elem {
    fn from(w: [u64; 4]) -> Elem {
        Elem(w)
    }
}

impl From<Elem> for [u64; 4] {
    fn from(e: Elem) -> [u64; 4] {
        e.0
    }
}

impl fmt::Debug for Elem {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        if self.0[2] != 0 {
            write!(f, "Elem(infinity)")
        } else if self.0[1] == 0 && self.0[3] == 0 {
            write!(f, "Elem({})", self.0[0])
        } else {
            write!(f, "Elem({}, {})", self.0[0], self.0[1])
        }
    }
}

/// A group in which discrete logarithms are computed: either `Z_p^*` or an
/// elliptic curve over `F_p`, together with the order of the (sub)group of
/// interest.
///
/// Wraps an opaque `ca_ctx`.  All element and solver operations take `&self`
/// and may be called from several threads at once.
///
/// # Thread safety
///
/// The C context is a plain struct of integers (prime, curve coefficients,
/// order, cofactor, Montgomery constants) that is fully initialised by the
/// constructor and never written to afterwards by any `const ca_ctx *`
/// function; the solvers keep all of their mutable state in their own stack or
/// heap allocations.  The only mutator, `ca_ctx_set_order`, is exposed as
/// [`Group::set_order`] taking `&mut self`, so Rust's borrow rules already
/// exclude concurrent access.  Hence `Send + Sync` are sound.
pub struct Group {
    ptr: NonNull<sys::CaCtx>,
}

// SAFETY: see the "Thread safety" section of the type documentation.
unsafe impl Send for Group {}
// SAFETY: see the "Thread safety" section of the type documentation.
unsafe impl Sync for Group {}

impl Drop for Group {
    fn drop(&mut self) {
        // SAFETY: the pointer came from ca_ctx_new_* and is freed exactly once.
        unsafe { sys::ca_ctx_free(self.ptr.as_ptr()) }
    }
}

impl fmt::Debug for Group {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let mut d = f.debug_struct("Group");
        d.field("kind", &self.kind()).field("p", &self.p());
        if self.kind() == Kind::Ec {
            d.field("a", &self.curve_a()).field("b", &self.curve_b());
        }
        d.field("order", &self.order())
            .field("cofactor", &self.cofactor())
            .finish()
    }
}

/// Error for a null return from a constructor (the C ABI does not give a
/// status code there).
fn construction_error(what: &str) -> Error {
    let msg = last_error_message();
    let msg = if msg.is_empty() {
        format!("invalid {what} parameters")
    } else {
        format!("invalid {what} parameters ({msg})")
    };
    Error::with_message(sys::CA_ERR_INVALID, msg)
}

impl Group {
    /// The multiplicative group `Z_p^*` for the prime `p`.
    ///
    /// `order` is the order of the subgroup of interest (it must divide
    /// `p - 1`); pass 0 to use the full group order `p - 1`.  Solvers that
    /// search the whole group (rho, dlog) rely on this order.
    ///
    /// ```
    /// use cryptanalysis::Group;
    /// let g = Group::zp(2_000_000_579, 1_000_000_289).unwrap();
    /// assert_eq!(g.order(), 1_000_000_289);
    /// assert!(Group::zp(1000, 0).is_err()); // not prime
    /// ```
    pub fn zp(p: u64, order: u64) -> Result<Group> {
        // SAFETY: plain integer arguments; a null return is handled.
        let ptr = unsafe { sys::ca_ctx_new_zp(p, order) };
        NonNull::new(ptr)
            .map(|ptr| Group { ptr })
            .ok_or_else(|| construction_error("Z_p^*"))
    }

    /// The elliptic curve `y^2 = x^3 + a x + b` over `F_p`.
    ///
    /// `order` is the order of the (sub)group of interest; use
    /// [`Group::ec_count_points`] to obtain the full curve order when it is not
    /// known.  Singular curves are rejected.
    pub fn ec(p: u64, a: u64, b: u64, order: u64) -> Result<Group> {
        // SAFETY: plain integer arguments; a null return is handled.
        let ptr = unsafe { sys::ca_ctx_new_ec(p, a, b, order) };
        NonNull::new(ptr)
            .map(|ptr| Group { ptr })
            .ok_or_else(|| construction_error("elliptic curve"))
    }

    /// Count the points of `y^2 = x^3 + a x + b` over `F_p` (including infinity).
    ///
    /// ```
    /// let n = cryptanalysis::Group::ec_count_points(1_000_003, 1, 7).unwrap();
    /// assert!((n as i64 - 1_000_004).abs() <= 2 * 1001); // Hasse bound
    /// ```
    pub fn ec_count_points(p: u64, a: u64, b: u64) -> Result<u64> {
        let mut n = 0u64;
        // SAFETY: `n` is a valid out pointer.
        check(unsafe { sys::ca_ec_order(p, a, b, &mut n) })?;
        Ok(n)
    }

    #[inline]
    pub(crate) fn raw(&self) -> *const sys::CaCtx {
        self.ptr.as_ptr()
    }

    /// The raw `ca_ctx` pointer, for interoperating with `cryptanalysis-sys`.
    ///
    /// The pointer is valid for as long as `self` lives; do not free it.
    pub fn as_raw(&self) -> *const sys::CaCtx {
        self.raw()
    }

    // ---- accessors ---------------------------------------------------------

    /// Whether this is `Z_p^*` or a curve.
    pub fn kind(&self) -> Kind {
        // SAFETY: valid context.
        match unsafe { sys::ca_ctx_kind(self.raw()) } {
            sys::CA_GROUP_EC => Kind::Ec,
            _ => Kind::Zp,
        }
    }

    /// The field prime.
    pub fn p(&self) -> u64 {
        // SAFETY: valid context.
        unsafe { sys::ca_ctx_p(self.raw()) }
    }

    /// The order of the (sub)group of interest.
    pub fn order(&self) -> u64 {
        // SAFETY: valid context.
        unsafe { sys::ca_ctx_order(self.raw()) }
    }

    /// The cofactor (full group order / subgroup order).
    pub fn cofactor(&self) -> u64 {
        // SAFETY: valid context.
        unsafe { sys::ca_ctx_cofactor(self.raw()) }
    }

    /// Curve coefficient `a` (0 for `Z_p^*`).
    pub fn curve_a(&self) -> u64 {
        // SAFETY: valid context.
        unsafe { sys::ca_ctx_curve_a(self.raw()) }
    }

    /// Curve coefficient `b` (0 for `Z_p^*`).
    pub fn curve_b(&self) -> u64 {
        // SAFETY: valid context.
        unsafe { sys::ca_ctx_curve_b(self.raw()) }
    }

    /// Change the subgroup order and cofactor, e.g. after computing the order
    /// of a particular base point with [`Group::elem_order`].
    ///
    /// This is the only operation that mutates the context, hence `&mut self`.
    pub fn set_order(&mut self, order: u64, cofactor: u64) {
        // SAFETY: valid context, exclusively borrowed.
        unsafe { sys::ca_ctx_set_order(self.ptr.as_ptr(), order, cofactor) }
    }

    // ---- elements ----------------------------------------------------------

    /// Whether `e` is a valid element (residue in range / point on the curve).
    pub fn validate(&self, e: &Elem) -> bool {
        // SAFETY: valid context and 4-word element.
        unsafe { sys::ca_ctx_validate(self.raw(), e.as_ptr()) != 0 }
    }

    /// The identity element (1, or the point at infinity).
    pub fn identity(&self) -> Elem {
        let mut out = Elem::default();
        // SAFETY: valid context; ca_ctx_identity cannot fail.
        unsafe { sys::ca_ctx_identity(self.raw(), out.0.as_mut_ptr()) };
        out
    }

    /// Whether `e` is the identity (false for invalid elements).
    pub fn is_identity(&self, e: &Elem) -> bool {
        // SAFETY: valid context and 4-word element.
        unsafe { sys::ca_ctx_is_identity(self.raw(), e.as_ptr()) != 0 }
    }

    /// The group operation `a * b` (point addition on curves).
    pub fn op(&self, a: &Elem, b: &Elem) -> Result<Elem> {
        let mut out = Elem::default();
        // SAFETY: valid context and 4-word elements.
        check(unsafe { sys::ca_ctx_op(self.raw(), out.0.as_mut_ptr(), a.as_ptr(), b.as_ptr()) })?;
        Ok(out)
    }

    /// The inverse `a^-1` (point negation on curves).
    pub fn inv(&self, a: &Elem) -> Result<Elem> {
        let mut out = Elem::default();
        // SAFETY: valid context and 4-word element.
        check(unsafe { sys::ca_ctx_inv(self.raw(), out.0.as_mut_ptr(), a.as_ptr()) })?;
        Ok(out)
    }

    /// Scalar multiplication `a^k` (`k * A` on curves).
    pub fn mul(&self, a: &Elem, k: u64) -> Result<Elem> {
        let mut out = Elem::default();
        // SAFETY: valid context and 4-word element.
        check(unsafe { sys::ca_ctx_mul(self.raw(), out.0.as_mut_ptr(), a.as_ptr(), k) })?;
        Ok(out)
    }

    /// Group equality (false if either element is invalid).
    pub fn equal(&self, a: &Elem, b: &Elem) -> bool {
        // SAFETY: valid context and 4-word elements.
        unsafe { sys::ca_ctx_equal(self.raw(), a.as_ptr(), b.as_ptr()) != 0 }
    }

    /// The order of the element `a`.
    pub fn elem_order(&self, a: &Elem) -> Result<u64> {
        let mut ord = 0u64;
        // SAFETY: valid context, 4-word element and out pointer.
        check(unsafe { sys::ca_ctx_elem_order(self.raw(), a.as_ptr(), &mut ord) })?;
        Ok(ord)
    }

    /// A generator of the subgroup of order [`Group::order`].
    ///
    /// `seed` selects the random search (0 => random from the OS).
    pub fn find_generator(&self, seed: u64) -> Result<Elem> {
        let mut out = Elem::default();
        // SAFETY: valid context and out buffer.
        check(unsafe { sys::ca_ctx_find_generator(self.raw(), out.0.as_mut_ptr(), seed) })?;
        Ok(out)
    }

    /// A pseudo-random element of the subgroup (a random element of the full
    /// group multiplied by the cofactor).  `seed` 0 => random from the OS.
    pub fn random_element(&self, seed: u64) -> Result<Elem> {
        let mut out = Elem::default();
        // SAFETY: valid context and out buffer.
        check(unsafe { sys::ca_ctx_random_element(self.raw(), out.0.as_mut_ptr(), seed) })?;
        Ok(out)
    }

    /// Curves only: a point with the given x coordinate.
    ///
    /// Returns [`Error::NotFound`] if `x^3 + a x + b` is not a square and
    /// [`Error::Unsupported`] for `Z_p^*`.
    pub fn lift_x(&self, x: u64) -> Result<Elem> {
        let mut out = Elem::default();
        // SAFETY: valid context and out buffer.
        check(unsafe { sys::ca_ctx_lift_x(self.raw(), out.0.as_mut_ptr(), x) })?;
        Ok(out)
    }

    // ---- solvers -----------------------------------------------------------

    /// Baby-step giant-step: find `x` in `[lo, hi]` with `base^x == target`.
    ///
    /// `lo == hi == 0` searches the whole group.  Returns `x` and the work
    /// statistics.
    pub fn bsgs(
        &self,
        base: &Elem,
        target: &Elem,
        lo: u64,
        hi: u64,
        opts: &Options,
    ) -> Result<(u64, Stats)> {
        let raw = opts.to_raw();
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_bsgs(
                self.raw(),
                base.as_ptr(),
                target.as_ptr(),
                lo,
                hi,
                &raw,
                &mut x,
                &mut st,
            )
        })?;
        Ok((x, Stats::from_raw(&st)))
    }

    /// Pollard's kangaroo (lambda) method on the interval `[lo, hi]`
    /// (`lo == hi == 0` => the whole group).
    pub fn kangaroo(
        &self,
        base: &Elem,
        target: &Elem,
        lo: u64,
        hi: u64,
        opts: &Options,
    ) -> Result<(u64, Stats)> {
        let raw = opts.to_raw();
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_kangaroo(
                self.raw(),
                base.as_ptr(),
                target.as_ptr(),
                lo,
                hi,
                &raw,
                &mut x,
                &mut st,
            )
        })?;
        Ok((x, Stats::from_raw(&st)))
    }

    /// Grumpy giants on the interval `[lo, hi]` (`lo == hi == 0` => the whole group).
    pub fn grumpy(
        &self,
        base: &Elem,
        target: &Elem,
        lo: u64,
        hi: u64,
        opts: &Options,
    ) -> Result<(u64, Stats)> {
        let raw = opts.to_raw();
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_grumpy(
                self.raw(),
                base.as_ptr(),
                target.as_ptr(),
                lo,
                hi,
                &raw,
                &mut x,
                &mut st,
            )
        })?;
        Ok((x, Stats::from_raw(&st)))
    }

    /// Pollard rho over the whole group of order [`Group::order`].
    ///
    /// Uses `opts.threads` worker threads.
    pub fn rho(&self, base: &Elem, target: &Elem, opts: &Options) -> Result<(u64, Stats)> {
        let raw = opts.to_raw();
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_rho(
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

    /// The general driver: Pohlig-Hellman over the factorisation of
    /// [`Group::order`], using `opts.solver` in each prime-power subgroup.
    ///
    /// The result is reduced modulo the order of `base`.
    ///
    /// ```
    /// use cryptanalysis::{Group, Options};
    /// let g = Group::zp(2_000_000_579, 1_000_000_289).unwrap();
    /// let gen = g.find_generator(1).unwrap();
    /// let h = g.mul(&gen, 123_456_789).unwrap();
    /// let (x, _stats) = g.dlog(&gen, &h, &Options::default()).unwrap();
    /// assert_eq!(x, 123_456_789);
    /// ```
    pub fn dlog(&self, base: &Elem, target: &Elem, opts: &Options) -> Result<(u64, Stats)> {
        let raw = opts.to_raw();
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_dlog(
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

    /// Discrete logarithm with precomputation (Bernstein-Lange free
    /// precomputation): a one-time table for `base` (built with
    /// `opts.threads` workers), then this `target` solved online.
    ///
    /// One-shot — it builds the table, solves once and frees it — so the
    /// returned [`Stats`] cover the whole `n^{2/3}` build plus the `n^{1/3}`
    /// online phase; the reusable-table API is C-only.  `base` must generate
    /// the group of order [`Group::order`].
    pub fn precomp(
        &self,
        base: &Elem,
        target: &Elem,
        opts: &PrecompOptions,
    ) -> Result<(u64, Stats)> {
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_precomp(
                self.raw(),
                base.as_ptr(),
                target.as_ptr(),
                opts.dp_bits,
                opts.table_size,
                opts.coverage,
                opts.threads,
                opts.seed,
                &mut x,
                &mut st,
            )
        })?;
        Ok((x, Stats::from_raw(&st)))
    }

    /// Solve `base^x == target` folding the Pollard rho walk by the curve's
    /// GLV endomorphism when it has one, else the negation-map rho.
    ///
    /// Returns `x`, the [`CurveInfo`](crate::curve::CurveInfo) reporting which
    /// path ran (its `beta` is left 0 -- use [`curve::detect`](crate::curve::detect)
    /// for the field constant), and the work statistics.  Elliptic-curve
    /// groups only (`CA_ERR_UNSUPPORTED` for `Z_p^*`).
    pub fn curve_solve(
        &self,
        base: &Elem,
        target: &Elem,
        seed: u64,
    ) -> Result<(u64, crate::curve::CurveInfo, Stats)> {
        let mut x = 0u64;
        let mut st = sys::CaStats::default();
        let mut endo = 0i32;
        let mut aut_order = 0u32;
        let mut lambda = 0u64;
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_curve_solve(
                self.raw(),
                base.as_ptr(),
                target.as_ptr(),
                seed,
                &mut x,
                &mut endo,
                &mut aut_order,
                &mut lambda,
                &mut st,
            )
        })?;
        let info = crate::curve::CurveInfo {
            endo: crate::curve::Endo::from_raw(endo),
            aut_order,
            beta: 0,
            lambda,
            rho_speedup: f64::from(aut_order).sqrt(),
        };
        Ok((x, info, Stats::from_raw(&st)))
    }

    // ---- Cheon -------------------------------------------------------------

    /// Cheon's attack on the strong Diffie-Hellman problem.
    ///
    /// Given `gen`, `g_alpha = gen^alpha` and `g_alpha_d = gen^(alpha^d)` with
    /// `d | order - 1` (the group order must be prime), recover `alpha`.
    /// `max_exps` bounds the number of exponentiations (0 => unlimited;
    /// exceeding it yields [`Error::Limit`]).  Choose `d` with
    /// [`cheon_best_divisor`].
    pub fn cheon(
        &self,
        gen: &Elem,
        g_alpha: &Elem,
        g_alpha_d: &Elem,
        d: u64,
        max_exps: u64,
    ) -> Result<(u64, Stats)> {
        let mut alpha = 0u64;
        let mut st = sys::CaStats::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_cheon(
                self.raw(),
                gen.as_ptr(),
                g_alpha.as_ptr(),
                g_alpha_d.as_ptr(),
                d,
                max_exps,
                &mut alpha,
                &mut st,
            )
        })?;
        Ok((alpha, Stats::from_raw(&st)))
    }

    /// Build a Cheon instance `(gen^alpha, gen^(alpha^d))` for experiments.
    pub fn cheon_instance(&self, gen: &Elem, alpha: u64, d: u64) -> Result<(Elem, Elem)> {
        let mut ga = Elem::default();
        let mut gad = Elem::default();
        // SAFETY: all pointers are valid for the duration of the call.
        check(unsafe {
            sys::ca_ffi_cheon_instance(
                self.raw(),
                gen.as_ptr(),
                alpha,
                d,
                ga.0.as_mut_ptr(),
                gad.0.as_mut_ptr(),
            )
        })?;
        Ok((ga, gad))
    }
}

/// The best divisor `d` of `p - 1` for Cheon's attack on a group of prime
/// order `p` (minimises `sqrt((p-1)/d) + sqrt(d)`), together with the
/// estimated cost in exponentiations.
///
/// ```
/// let (d, cost) = cryptanalysis::cheon_best_divisor(1_000_000_289);
/// assert!(d > 1 && (1_000_000_288 % d) == 0 && cost > 0.0);
/// ```
pub fn cheon_best_divisor(p: u64) -> (u64, f64) {
    let mut cost = 0f64;
    // SAFETY: `cost` is a valid out pointer.
    let d = unsafe { sys::ca_ffi_cheon_best_divisor(p, &mut cost) };
    (d, cost)
}
