//! # `gf3m` — characteristic-three finite fields and elliptic curves.
//!
//! Arithmetic in the finite field `F_{3^m}` and on short-Weierstrass
//! elliptic curves defined over it, added so the index-calculus engine can
//! cover characteristic-three curves. The implementation favours clarity and
//! correctness over speed: elements are dense coefficient vectors over `F_3`
//! and reduction is ordinary polynomial long division. `m` up to ~163 is
//! supported (only the cost of the schoolbook `O(m^2)` multiply grows).
//!
//! ## Field representation
//!
//! `F_{3^m}` is realised as `F_3[z] / (f)` for a monic irreducible reduction
//! polynomial `f` of degree `m`. An element is a [`Gf3Elem`], holding exactly
//! `m` coefficients in `{0, 1, 2}`, little-endian: index `i` is the
//! coefficient of `z^i`. Every element produced by this module is canonical
//! (length `m`, each entry reduced mod 3), so `Gf3Elem`'s derived `PartialEq`
//! is the field equality.
//!
//! `F_3` itself is tiny and has two facts worth stating because the code
//! relies on them:
//!
//! * `2` is invertible and every nonzero element is its own inverse:
//!   `1 * 1 = 1` and `2 * 2 = 4 = 1`, so `1/2 = 2`.
//! * Negation is `x -> (3 - x) mod 3`: `-0 = 0`, `-1 = 2`, `-2 = 1`.
//!
//! ## Characteristic-three curve subtlety
//!
//! For `y^2 = x^3 + a4*x + a6` the general point-doubling slope is
//! `lambda = (3*x^2 + a4) / (2*y)`. In characteristic three `3 = 0`, so the
//! `3*x^2` term vanishes and the slope collapses to
//!
//! ```text
//!     lambda = a4 / (2*y)          (doubling, characteristic 3)
//! ```
//!
//! The addition slope for two points with distinct `x` is the usual
//! `(y2 - y1) / (x2 - x1)`, and the `x3`/`y3` formulas are the ordinary
//! Weierstrass ones; only the doubling slope changes. This is implemented in
//! [`Char3Curve::point_double`] and flagged there again. Note also that in
//! characteristic three a short-Weierstrass curve is nonsingular iff
//! `a4 != 0` (the discriminant reduces to `2*a4^3`), so [`Char3Curve::new`]
//! rejects `a4 = 0`.

use num_bigint::BigUint;

// ---------------------------------------------------------------------------
// Free polynomial helpers over F_3 (trimmed, little-endian, empty == zero).
//
// These operate on arbitrary polynomials in F_3[z] (NOT reduced modulo the
// field's irreducible) and back the irreducibility test in `Gf3::new`. A
// polynomial is a `Vec<u8>` of coefficients in {0,1,2}, low degree first,
// kept trimmed so the last entry is nonzero; the empty vector is the zero
// polynomial and has degree -1.
// ---------------------------------------------------------------------------

/// Drop trailing zero coefficients so the representation is canonical.
fn f3_trim(mut p: Vec<u8>) -> Vec<u8> {
    while matches!(p.last(), Some(&0)) {
        p.pop();
    }
    p
}

/// Schoolbook product `a * b` in `F_3[z]` (no modular reduction).
fn f3_poly_mul(a: &[u8], b: &[u8]) -> Vec<u8> {
    if a.is_empty() || b.is_empty() {
        return Vec::new();
    }
    let mut r = vec![0u8; a.len() + b.len() - 1];
    for (i, &ai) in a.iter().enumerate() {
        if ai == 0 {
            continue;
        }
        for (j, &bj) in b.iter().enumerate() {
            r[i + j] = (r[i + j] + ai * bj) % 3;
        }
    }
    f3_trim(r)
}

/// Difference `a - b` in `F_3[z]`.
fn f3_poly_sub(a: &[u8], b: &[u8]) -> Vec<u8> {
    let n = a.len().max(b.len());
    let mut r = vec![0u8; n];
    for (i, slot) in r.iter_mut().enumerate() {
        let av = a.get(i).copied().unwrap_or(0);
        let bv = b.get(i).copied().unwrap_or(0);
        *slot = (av + 3 - bv) % 3;
    }
    f3_trim(r)
}

/// Remainder of `a` modulo the nonzero polynomial `b`, by long division.
///
/// `b` must be trimmed and nonzero. Uses that every nonzero element of `F_3`
/// is its own multiplicative inverse to normalise the leading term.
fn f3_poly_rem(a: &[u8], b: &[u8]) -> Vec<u8> {
    debug_assert!(!b.is_empty(), "division by the zero polynomial");
    let db = b.len() - 1;
    let blead = b[db]; // in {1,2}; inv(blead) == blead in F_3
    let mut r = f3_trim(a.to_vec());
    while r.len() > db {
        let rlead = r[r.len() - 1];
        // factor c so that c * blead == rlead  (i.e. c = rlead * inv(blead))
        let c = (rlead * blead) % 3;
        let shift = r.len() - 1 - db;
        for j in 0..=db {
            let sub = (c * b[j]) % 3;
            let idx = shift + j;
            r[idx] = (r[idx] + 3 - sub) % 3;
        }
        r = f3_trim(r);
    }
    r
}

/// Monic-agnostic gcd of `a` and `b` in `F_3[z]` (result not normalised).
fn f3_poly_gcd(a: &[u8], b: &[u8]) -> Vec<u8> {
    let mut a = f3_trim(a.to_vec());
    let mut b = f3_trim(b.to_vec());
    while !b.is_empty() {
        let r = f3_poly_rem(&a, &b);
        a = b;
        b = r;
    }
    a
}

/// Distinct-degree irreducibility test for a monic `f` of degree `m >= 1`.
///
/// `f` (degree `m`) is irreducible over `F_3` iff it has no irreducible
/// factor of degree `<= m/2`. The product of all monic irreducibles whose
/// degree divides `k` is `z^(3^k) - z`, so `f` has such a small factor iff
/// `gcd(z^(3^k) - z, f) != 1` for some `k in 1..=m/2`. We compute
/// `z^(3^k) mod f` by starting from `z` and cubing `k` times (the
/// characteristic-3 Frobenius is `x -> x^3`).
fn is_irreducible_f3(f: &[u8]) -> bool {
    let f = f3_trim(f.to_vec());
    if f.len() < 2 {
        return false; // degree < 1 is never irreducible
    }
    let m = f.len() - 1;
    let z = vec![0u8, 1u8];
    // beta = z^(3^k) mod f, starting at k = 0 (beta = z mod f).
    let mut beta = f3_poly_rem(&z, &f);
    for _ in 1..=(m / 2) {
        // beta <- beta^3 mod f
        let sq = f3_poly_mul(&beta, &beta);
        let cube = f3_poly_mul(&sq, &beta);
        beta = f3_poly_rem(&cube, &f);
        let h = f3_poly_sub(&beta, &z); // z^(3^k) - z, reduced mod f
        let g = f3_poly_gcd(&f, &h);
        if g.len() >= 2 {
            return false; // common factor of degree >= 1
        }
    }
    true
}

// ---------------------------------------------------------------------------
// Field element and field.
// ---------------------------------------------------------------------------

/// An element of `F_{3^m}`: `m` coefficients in `{0,1,2}`, little-endian
/// (index `i` is the `z^i` coefficient). Always canonical when produced by
/// this module, so the derived equality is field equality.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Gf3Elem {
    coeffs: Vec<u8>,
}

impl Gf3Elem {
    /// The coefficient vector, little-endian, length `m`, entries in `{0,1,2}`.
    pub fn coeffs(&self) -> &[u8] {
        &self.coeffs
    }
}

/// The finite field `F_{3^m} = F_3[z] / (f)` for a monic irreducible `f`.
#[derive(Clone, Debug)]
pub struct Gf3 {
    m: u32,
    /// Reduction polynomial, length `m+1`, monic (`irr[m] == 1`).
    irr: Vec<u8>,
}

impl Gf3 {
    /// Build `F_{3^m}` from a monic reduction polynomial.
    ///
    /// `irr` holds the reduction polynomial's coefficients, little-endian,
    /// length `m + 1`, every entry in `{0,1,2}`, with the leading
    /// coefficient `irr[m] == 1`. The constructor verifies that `irr` is
    /// **irreducible** over `F_3` (a full distinct-degree test, not merely a
    /// root check) and returns `Err` if `irr` is malformed or reducible.
    pub fn new(m: u32, irr: &[u8]) -> Result<Self, String> {
        if m == 0 {
            return Err("m must be >= 1".to_string());
        }
        let want = m as usize + 1;
        if irr.len() != want {
            return Err(format!(
                "reduction polynomial must have length m+1 = {}, got {}",
                want,
                irr.len()
            ));
        }
        if irr.iter().any(|&c| c >= 3) {
            return Err("reduction polynomial coefficients must be in {0,1,2}".to_string());
        }
        if irr[m as usize] != 1 {
            return Err("reduction polynomial must be monic (leading coefficient 1)".to_string());
        }
        if !is_irreducible_f3(irr) {
            return Err("reduction polynomial is reducible over F_3".to_string());
        }
        Ok(Gf3 {
            m,
            irr: irr.to_vec(),
        })
    }

    /// The extension degree `m`.
    pub fn degree(&self) -> u32 {
        self.m
    }

    /// The reduction polynomial (length `m+1`, monic).
    pub fn modulus(&self) -> &[u8] {
        &self.irr
    }

    /// Reduce an arbitrary-length coefficient vector to a canonical element
    /// of length `m` by polynomial long division modulo `irr` (mod 3).
    fn reduce(&self, poly: &[u8]) -> Vec<u8> {
        let m = self.m as usize;
        let mut p: Vec<u8> = poly.iter().map(|&c| c % 3).collect();
        if p.len() > m {
            // Eliminate every term of degree >= m, high degree first. Because
            // `irr` is monic, subtracting `p[i] * z^(i-m) * irr` zeroes p[i]
            // and only touches lower indices, so a single downward sweep
            // performs the whole division.
            for i in (m..p.len()).rev() {
                let c = p[i];
                if c != 0 {
                    for j in 0..=m {
                        let sub = (c * self.irr[j]) % 3;
                        let idx = i - m + j;
                        p[idx] = (p[idx] + 3 - sub) % 3;
                    }
                }
            }
        }
        let mut out = vec![0u8; m];
        let take = p.len().min(m);
        out[..take].copy_from_slice(&p[..take]);
        out
    }

    /// Construct an element from raw coefficients (little-endian). Entries are
    /// reduced mod 3 and the polynomial is reduced modulo `irr`, so any length
    /// is accepted. Returns `Err` only if an entry is not a valid base-3 digit
    /// once you consider it may already exceed 2 — here we accept anything and
    /// reduce, so this never fails; kept as `Result` for a stable signature.
    pub fn element(&self, coeffs: &[u8]) -> Result<Gf3Elem, String> {
        Ok(Gf3Elem {
            coeffs: self.reduce(coeffs),
        })
    }

    /// The additive identity `0`.
    pub fn zero(&self) -> Gf3Elem {
        Gf3Elem {
            coeffs: vec![0u8; self.m as usize],
        }
    }

    /// The multiplicative identity `1`.
    pub fn one(&self) -> Gf3Elem {
        let mut c = vec![0u8; self.m as usize];
        c[0] = 1;
        Gf3Elem { coeffs: c }
    }

    /// Embed an integer by writing it in base 3 and reducing modulo `irr`.
    // `from_int` needs the field context (degree and modulus) to build an
    // element, so it takes `&self`; the `from_*`-should-be-a-constructor
    // convention does not fit a per-field embedding.
    pub fn from_int(&self, mut n: u64) -> Gf3Elem {
        let mut digits = Vec::new();
        if n == 0 {
            digits.push(0u8);
        }
        while n > 0 {
            digits.push((n % 3) as u8);
            n /= 3;
        }
        Gf3Elem {
            coeffs: self.reduce(&digits),
        }
    }

    /// `a + b`.
    pub fn add(&self, a: &Gf3Elem, b: &Gf3Elem) -> Gf3Elem {
        let m = self.m as usize;
        let mut c = vec![0u8; m];
        for i in 0..m {
            c[i] = (a.coeffs[i] + b.coeffs[i]) % 3;
        }
        Gf3Elem { coeffs: c }
    }

    /// `a - b`.
    pub fn sub(&self, a: &Gf3Elem, b: &Gf3Elem) -> Gf3Elem {
        let m = self.m as usize;
        let mut c = vec![0u8; m];
        for i in 0..m {
            c[i] = (a.coeffs[i] + 3 - b.coeffs[i]) % 3;
        }
        Gf3Elem { coeffs: c }
    }

    /// `-a`.
    pub fn neg(&self, a: &Gf3Elem) -> Gf3Elem {
        let m = self.m as usize;
        let mut c = vec![0u8; m];
        for i in 0..m {
            c[i] = (3 - a.coeffs[i]) % 3;
        }
        Gf3Elem { coeffs: c }
    }

    /// `a * b` (schoolbook multiply, then reduce modulo `irr`).
    pub fn mul(&self, a: &Gf3Elem, b: &Gf3Elem) -> Gf3Elem {
        let m = self.m as usize;
        let mut prod = vec![0u8; 2 * m - 1];
        for i in 0..m {
            if a.coeffs[i] == 0 {
                continue;
            }
            for j in 0..m {
                prod[i + j] = (prod[i + j] + a.coeffs[i] * b.coeffs[j]) % 3;
            }
        }
        Gf3Elem {
            coeffs: self.reduce(&prod),
        }
    }

    /// `a^2`.
    pub fn sqr(&self, a: &Gf3Elem) -> Gf3Elem {
        self.mul(a, a)
    }

    /// `a^3`. In characteristic three this is the Frobenius endomorphism, so
    /// `(a + b)^3 == a^3 + b^3` ("freshman's dream").
    pub fn cube(&self, a: &Gf3Elem) -> Gf3Elem {
        self.mul(&self.sqr(a), a)
    }

    /// The Frobenius endomorphism `a -> a^3` (alias for [`Gf3::cube`]).
    pub fn frobenius(&self, a: &Gf3Elem) -> Gf3Elem {
        self.cube(a)
    }

    /// `a^exp` by square-and-multiply over the big-integer exponent.
    pub fn pow(&self, a: &Gf3Elem, exp: &BigUint) -> Gf3Elem {
        let mut result = self.one();
        let mut base = a.clone();
        let bits = exp.bits();
        for i in 0..bits {
            if exp.bit(i) {
                result = self.mul(&result, &base);
            }
            base = self.sqr(&base);
        }
        result
    }

    /// Multiplicative inverse via Fermat: `a^(3^m - 2) == a^{-1}` for
    /// `a != 0`, since the multiplicative group has order `3^m - 1`.
    ///
    /// # Panics
    /// Panics if `a` is zero, which has no inverse.
    pub fn inv(&self, a: &Gf3Elem) -> Gf3Elem {
        assert!(!self.is_zero(a), "Gf3::inv: zero has no inverse");
        let exp = BigUint::from(3u32).pow(self.m) - BigUint::from(2u32);
        self.pow(a, &exp)
    }

    /// Whether `a` is the zero element.
    pub fn is_zero(&self, a: &Gf3Elem) -> bool {
        a.coeffs.iter().all(|&c| c == 0)
    }

    /// Field equality of `a` and `b`.
    pub fn eq(&self, a: &Gf3Elem, b: &Gf3Elem) -> bool {
        a.coeffs == b.coeffs
    }
}

// ---------------------------------------------------------------------------
// Elliptic curve in short Weierstrass form over F_{3^m}.
// ---------------------------------------------------------------------------

/// A point on a [`Char3Curve`]: the point at infinity or an affine point.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Char3Point {
    /// The identity element (point at infinity).
    Infinity,
    /// An affine point `(x, y)`.
    Affine { x: Gf3Elem, y: Gf3Elem },
}

/// A short-Weierstrass curve `y^2 = x^3 + a4*x + a6` over `F_{3^m}`.
#[derive(Clone, Debug)]
pub struct Char3Curve {
    field: Gf3,
    a4: Gf3Elem,
    a6: Gf3Elem,
}

impl Char3Curve {
    /// Build `y^2 = x^3 + a4*x + a6` over `field`.
    ///
    /// Returns `Err` if `a4`/`a6` do not belong to `field` (wrong length) or
    /// if the curve is singular. In characteristic three the discriminant of
    /// a short-Weierstrass curve reduces to `2*a4^3`, so the curve is
    /// nonsingular iff `a4 != 0`.
    pub fn new(field: Gf3, a4: Gf3Elem, a6: Gf3Elem) -> Result<Self, String> {
        let m = field.m as usize;
        if a4.coeffs.len() != m || a6.coeffs.len() != m {
            return Err("a4/a6 do not have the field's coefficient length".to_string());
        }
        if field.is_zero(&a4) {
            return Err("curve is singular in characteristic 3 when a4 = 0".to_string());
        }
        Ok(Char3Curve { field, a4, a6 })
    }

    /// The base field.
    pub fn field(&self) -> &Gf3 {
        &self.field
    }

    /// The `a4` coefficient.
    pub fn a4(&self) -> &Gf3Elem {
        &self.a4
    }

    /// The `a6` coefficient.
    pub fn a6(&self) -> &Gf3Elem {
        &self.a6
    }

    /// Whether `p` satisfies the curve equation (infinity always does).
    pub fn is_on_curve(&self, p: &Char3Point) -> bool {
        match p {
            Char3Point::Infinity => true,
            Char3Point::Affine { x, y } => {
                let f = &self.field;
                let lhs = f.sqr(y);
                let rhs = f.add(&f.add(&f.cube(x), &f.mul(&self.a4, x)), &self.a6);
                f.eq(&lhs, &rhs)
            }
        }
    }

    /// `-p`. The negative of `(x, y)` is `(x, -y)`.
    pub fn point_neg(&self, p: &Char3Point) -> Char3Point {
        match p {
            Char3Point::Infinity => Char3Point::Infinity,
            Char3Point::Affine { x, y } => Char3Point::Affine {
                x: x.clone(),
                y: self.field.neg(y),
            },
        }
    }

    /// `2*p`.
    ///
    /// Characteristic-three subtlety: the general doubling slope
    /// `(3*x^2 + a4) / (2*y)` loses its `3*x^2` term because `3 = 0` here, so
    /// the slope is `lambda = a4 / (2*y)`. (`2` is invertible in `F_3`.) The
    /// `x3 = lambda^2 - 2*x`, `y3 = lambda*(x - x3) - y` formulas are the
    /// ordinary Weierstrass ones.
    pub fn point_double(&self, p: &Char3Point) -> Char3Point {
        match p {
            Char3Point::Infinity => Char3Point::Infinity,
            Char3Point::Affine { x, y } => {
                let f = &self.field;
                if f.is_zero(y) {
                    // A point of order 2 doubles to the identity.
                    return Char3Point::Infinity;
                }
                // lambda = a4 / (2y)  -- the char-3 doubling slope.
                let two_y = f.add(y, y);
                let lambda = f.mul(&self.a4, &f.inv(&two_y));
                let x3 = f.sub(&f.sub(&f.sqr(&lambda), x), x); // lambda^2 - 2x
                let y3 = f.sub(&f.mul(&lambda, &f.sub(x, &x3)), y); // lambda(x - x3) - y
                Char3Point::Affine { x: x3, y: y3 }
            }
        }
    }

    /// `p + q`.
    pub fn point_add(&self, p: &Char3Point, q: &Char3Point) -> Char3Point {
        let f = &self.field;
        match (p, q) {
            (Char3Point::Infinity, _) => q.clone(),
            (_, Char3Point::Infinity) => p.clone(),
            (Char3Point::Affine { x: x1, y: y1 }, Char3Point::Affine { x: x2, y: y2 }) => {
                if f.eq(x1, x2) {
                    if f.eq(y1, y2) {
                        return self.point_double(p);
                    }
                    // Equal x, unequal y => y2 = -y1 => P + (-P) = O.
                    return Char3Point::Infinity;
                }
                // Distinct x: lambda = (y2 - y1) / (x2 - x1).
                let dx = f.sub(x2, x1);
                let dy = f.sub(y2, y1);
                let lambda = f.mul(&dy, &f.inv(&dx));
                let x3 = f.sub(&f.sub(&f.sqr(&lambda), x1), x2); // lambda^2 - x1 - x2
                let y3 = f.sub(&f.mul(&lambda, &f.sub(x1, &x3)), y1); // lambda(x1 - x3) - y1
                Char3Point::Affine { x: x3, y: y3 }
            }
        }
    }

    /// `[k]*p` via double-and-add.
    pub fn scalar_mul(&self, p: &Char3Point, k: &BigUint) -> Char3Point {
        let mut result = Char3Point::Infinity;
        let mut addend = p.clone();
        let bits = k.bits();
        for i in 0..bits {
            if k.bit(i) {
                result = self.point_add(&result, &addend);
            }
            addend = self.point_double(&addend);
        }
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;

    // Known monic irreducibles over F_3 (little-endian coefficients).
    const IRR_M2: [u8; 3] = [1, 0, 1]; // z^2 + 1
    const IRR_M3: [u8; 4] = [1, 2, 0, 1]; // z^3 + 2z + 1  (= z^3 - z + 1)
    const IRR_M5: [u8; 6] = [1, 2, 0, 0, 0, 1]; // z^5 + 2z + 1  (= z^5 - z + 1)

    /// Independent reference multiply: reduce via a `z^k mod irr` substitution
    /// table (a different reduction structure than the module's long division)
    /// so the cross-check does not merely re-run the same algorithm.
    fn zpow_table(m: usize, irr: &[u8]) -> Vec<Vec<u8>> {
        let mut table: Vec<Vec<u8>> = Vec::with_capacity(2 * m - 1);
        for k in 0..m {
            let mut e = vec![0u8; m];
            e[k] = 1;
            table.push(e);
        }
        // z^m = -(irr[0] + irr[1] z + ... + irr[m-1] z^{m-1}) since irr monic.
        let zm: Vec<u8> = (0..m).map(|j| (3 - irr[j]) % 3).collect();
        for k in m..(2 * m - 1) {
            let prev = table[k - 1].clone();
            let mut cur = vec![0u8; m];
            cur[1..m].copy_from_slice(&prev[..m - 1]);
            let top = prev[m - 1]; // coefficient of z^m after shifting up by z
            for j in 0..m {
                cur[j] = (cur[j] + top * zm[j]) % 3;
            }
            table.push(cur);
        }
        table
    }

    fn ref_mul(m: usize, table: &[Vec<u8>], a: &[u8], b: &[u8]) -> Vec<u8> {
        let mut acc = vec![0u8; m];
        for i in 0..m {
            if a[i] == 0 {
                continue;
            }
            for j in 0..m {
                if b[j] == 0 {
                    continue;
                }
                let c = (a[i] * b[j]) % 3;
                let t = &table[i + j];
                for k in 0..m {
                    acc[k] = (acc[k] + c * t[k]) % 3;
                }
            }
        }
        acc
    }

    fn field_axioms(m: u32, irr: &[u8]) {
        let f = Gf3::new(m, irr).unwrap();
        let q = 3u64.pow(m);
        let table = zpow_table(m as usize, irr);
        let zero = f.zero();
        let one = f.one();

        assert!(f.is_zero(&zero));
        assert!(!f.is_zero(&one));
        assert!(f.eq(&f.from_int(0), &zero));
        assert!(f.eq(&f.from_int(1), &one));

        // Choose a sampling stride so large fields stay fast but small ones
        // are exhaustive.
        let stride = if q <= 27 { 1 } else { 5 };

        let mut a_i = 0u64;
        while a_i < q {
            let a = f.from_int(a_i);
            // additive identity, negation, subtraction
            assert!(f.eq(&f.add(&a, &zero), &a));
            assert!(f.eq(&f.sub(&a, &a), &zero));
            assert!(f.eq(&f.add(&a, &f.neg(&a)), &zero));
            // multiplicative identity
            assert!(f.eq(&f.mul(&a, &one), &a));
            // inverse (Fermat) and Fermat's little theorem
            if !f.is_zero(&a) {
                assert!(f.eq(&f.mul(&a, &f.inv(&a)), &one));
                let flt = f.pow(&a, &(BigUint::from(q) - 1u32));
                assert!(f.eq(&flt, &one));
            }
            // sqr / cube consistency and pow vs repeated multiply
            assert!(f.eq(&f.sqr(&a), &f.mul(&a, &a)));
            assert!(f.eq(&f.cube(&a), &f.mul(&f.mul(&a, &a), &a)));
            assert!(f.eq(&f.frobenius(&a), &f.cube(&a)));
            let mut acc = one.clone();
            for e in 0u32..6 {
                assert!(f.eq(&f.pow(&a, &BigUint::from(e)), &acc));
                acc = f.mul(&acc, &a);
            }

            let mut b_i = 0u64;
            while b_i < q {
                let b = f.from_int(b_i);
                // commutativity
                assert!(f.eq(&f.add(&a, &b), &f.add(&b, &a)));
                assert!(f.eq(&f.mul(&a, &b), &f.mul(&b, &a)));
                // multiply matches the independent reference
                let got = f.mul(&a, &b);
                let want = ref_mul(m as usize, &table, a.coeffs(), b.coeffs());
                assert_eq!(got.coeffs(), want.as_slice());
                // freshman's dream: (a+b)^3 == a^3 + b^3
                let lhs = f.cube(&f.add(&a, &b));
                let rhs = f.add(&f.cube(&a), &f.cube(&b));
                assert!(f.eq(&lhs, &rhs));

                // distributivity a*(b+c) == a*b + a*c for a few c
                let mut c_i = 0u64;
                while c_i < q {
                    let c = f.from_int(c_i);
                    let l = f.mul(&a, &f.add(&b, &c));
                    let r = f.add(&f.mul(&a, &b), &f.mul(&a, &c));
                    assert!(f.eq(&l, &r));
                    c_i += if q <= 9 { 1 } else { q / 3 + 1 };
                }
                b_i += stride;
            }
            a_i += stride;
        }
    }

    #[test]
    fn field_axioms_m2_m3_m5() {
        field_axioms(2, &IRR_M2);
        field_axioms(3, &IRR_M3);
        field_axioms(5, &IRR_M5);
    }

    #[test]
    fn irreducibility_accepts_known_irreducibles() {
        assert!(Gf3::new(2, &IRR_M2).is_ok());
        assert!(Gf3::new(3, &IRR_M3).is_ok());
        assert!(Gf3::new(5, &IRR_M5).is_ok());
        // z (degree 1) is trivially irreducible.
        assert!(Gf3::new(1, &[0, 1]).is_ok());
        // z^3 + 2z^2 + 1 is another irreducible cubic (no roots, cubic).
        assert!(Gf3::new(3, &[1, 0, 2, 1]).is_ok());
    }

    #[test]
    fn irreducibility_rejects_reducibles_and_malformed() {
        // z^2 + 2 == z^2 - 1 == (z-1)(z+1): reducible.
        assert!(Gf3::new(2, &[2, 0, 1]).is_err());
        // z^2 == z * z: reducible.
        assert!(Gf3::new(2, &[0, 0, 1]).is_err());
        // z^2 + z == z(z+1): reducible.
        assert!(Gf3::new(2, &[0, 1, 1]).is_err());
        // A quartic that is a product of two irreducible quadratics is caught
        // even though it has no roots: (z^2+1)^2 = z^4 + 2z^2 + 1.
        assert!(Gf3::new(4, &[1, 0, 2, 0, 1]).is_err());
        // Malformed: wrong length.
        assert!(Gf3::new(2, &[1, 0]).is_err());
        // Malformed: non-monic (leading coefficient 2).
        assert!(Gf3::new(2, &[1, 0, 2]).is_err());
        // Malformed: coefficient out of range.
        assert!(Gf3::new(2, &[1, 3, 1]).is_err());
    }

    #[test]
    fn element_round_trip() {
        let f = Gf3::new(3, &IRR_M3).unwrap();
        // Over-long, unreduced input gets reduced mod irr and mod 3.
        let e = f.element(&[5, 4, 3, 1]).unwrap(); // == [2,1,0,0] then + z^3 reduction
                                                   // z^3 == -(2z + 1) == z + 2 (since -1=2,-2=1)
                                                   // input poly: 5 + 4z + 3z^2 + z^3
                                                   //  = 2 + z + 0 + (z+2) = (2+2) + (1+1)z = 1 + 2z
        assert_eq!(e.coeffs(), &[1, 2, 0]);
    }

    // ---- curve tests -----------------------------------------------------

    fn all_points(curve: &Char3Curve) -> Vec<Char3Point> {
        let f = curve.field();
        let q = 3u64.pow(f.degree());
        let mut pts = vec![Char3Point::Infinity];
        for xi in 0..q {
            let x = f.from_int(xi);
            for yi in 0..q {
                let p = Char3Point::Affine {
                    x: x.clone(),
                    y: f.from_int(yi),
                };
                if curve.is_on_curve(&p) {
                    pts.push(p);
                }
            }
        }
        pts
    }

    fn point_order(curve: &Char3Curve, p: &Char3Point) -> u64 {
        if *p == Char3Point::Infinity {
            return 1;
        }
        let mut acc = p.clone();
        let mut ord = 1u64;
        while acc != Char3Point::Infinity {
            acc = curve.point_add(&acc, p);
            ord += 1;
        }
        ord
    }

    /// Exercise the full group law on the supersingular curve
    /// `y^2 = x^3 - x + 1` (a4 = -1 = 2, a6 = 1) over `F_{3^m}`.
    fn curve_law(m: u32, irr: &[u8]) {
        let field = Gf3::new(m, irr).unwrap();
        let a4 = field.from_int(2); // -1
        let a6 = field.one(); // 1
        let curve = Char3Curve::new(field.clone(), a4, a6).unwrap();

        let pts = all_points(&curve);
        let n = pts.len() as u64; // #E, brute-forced
        let big_n = BigUint::from(n);

        // Every enumerated point is on the curve, and there exist off-curve
        // points that is_on_curve rejects.
        for p in &pts {
            assert!(curve.is_on_curve(p));
        }
        let q = 3u64.pow(m);
        let mut found_off = false;
        'outer: for xi in 0..q {
            for yi in 0..q {
                let p = Char3Point::Affine {
                    x: field.from_int(xi),
                    y: field.from_int(yi),
                };
                if !curve.is_on_curve(&p) {
                    found_off = true;
                    break 'outer;
                }
            }
        }
        assert!(found_off, "expected some off-curve point to exist");

        // Identity behaviour, negation, and the group order annihilating
        // every point (Lagrange).
        for p in &pts {
            assert_eq!(curve.point_add(p, &Char3Point::Infinity), p.clone());
            assert_eq!(curve.point_add(&Char3Point::Infinity, p), p.clone());
            assert_eq!(
                curve.point_add(p, &curve.point_neg(p)),
                Char3Point::Infinity
            );
            assert_eq!(curve.scalar_mul(p, &big_n), Char3Point::Infinity);
        }

        // Doubling agrees across all three code paths, plus a naive check.
        for p in &pts {
            let d_double = curve.point_double(p);
            let d_add = curve.point_add(p, p);
            let d_scalar = curve.scalar_mul(p, &BigUint::from(2u32));
            assert_eq!(d_double, d_add);
            assert_eq!(d_double, d_scalar);
        }

        // Associativity over all triples (small groups only).
        for a in &pts {
            for b in &pts {
                let ab = curve.point_add(a, b);
                for c in &pts {
                    let left = curve.point_add(&ab, c);
                    let right = curve.point_add(a, &curve.point_add(b, c));
                    assert_eq!(left, right);
                }
            }
        }

        // scalar_mul (double-and-add) matches naive repeated addition, and a
        // point's order divides #E with [ord]G = O.
        for p in &pts {
            let mut naive = Char3Point::Infinity;
            for k in 0..(n + 2) {
                assert_eq!(curve.scalar_mul(p, &BigUint::from(k)), naive);
                naive = curve.point_add(&naive, p);
            }
            let ord = point_order(&curve, p);
            assert_eq!(n % ord, 0, "point order must divide #E");
            assert_eq!(
                curve.scalar_mul(p, &BigUint::from(ord)),
                Char3Point::Infinity
            );
        }

        // A generator (maximal order) exists; check it explicitly.
        let g = pts
            .iter()
            .max_by_key(|p| point_order(&curve, p))
            .unwrap()
            .clone();
        let gord = point_order(&curve, &g);
        assert_eq!(n % gord, 0);
        assert_eq!(
            curve.scalar_mul(&g, &BigUint::from(gord)),
            Char3Point::Infinity
        );
    }

    #[test]
    fn curve_law_small_fields() {
        // #E is 7 (m=2) and 28 (m=3) for this curve; brute-forced, not
        // assumed. The trace-0 supersingular formula 3^m+1 is NOT asserted
        // because it does not hold here for m=2 (it would give 10, not 7).
        curve_law(2, &IRR_M2);
        curve_law(3, &IRR_M3);
    }

    #[test]
    fn curve_rejects_singular_a4_zero() {
        let field = Gf3::new(2, &IRR_M2).unwrap();
        let a4 = field.zero();
        let a6 = field.one();
        assert!(Char3Curve::new(field, a4, a6).is_err());
    }
}
