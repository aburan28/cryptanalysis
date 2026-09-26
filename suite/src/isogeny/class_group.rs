//! # Class group of an imaginary quadratic order.
//!
//! Computations in `Cl(O)` for the order `O = Z + f·O_K` inside the
//! imaginary quadratic field `K = Q(√D₀)`, where `D₀` is the
//! fundamental discriminant and `f` the conductor.  The
//! discriminant of the order is `D = f² · D₀`.
//!
//! We represent ideal classes by **primitive positive-definite
//! integral binary quadratic forms** `(a, b, c)` of discriminant
//! `D = b² − 4ac`, with `gcd(a, b, c) = 1` (primitivity) and `a > 0`
//! (positive-definite).  This is the classical Gauss correspondence
//!
//! ```text
//! Cl(O)   ↔   {primitive pos-def forms of disc D} / SL₂(Z)-equivalence.
//! ```
//!
//! Two forms are **equivalent** iff related by an `SL₂(Z)` change of
//! variable, and each equivalence class contains a unique **reduced
//! representative** characterised by
//!
//! ```text
//! |b| ≤ a ≤ c          (and  b ≥ 0  if  |b| = a  or  a = c).
//! ```
//!
//! Reduction is Lagrange's algorithm (Cohen §5.4): alternately
//! translate `b → b mod 2a` (into `(-a, a]`) and swap-then-rename
//! when `a > c`.  Composition is Gauss / Shanks NUCOMP-lite: solve
//! a small linear Diophantine to merge two forms and reduce the
//! result.
//!
//! ## Cross-reference
//!
//! The crate already ships a Hilbert-class-polynomial module
//! ([`crate::cryptanalysis::hilbert_class_poly`]) that documents
//! the scaling barrier of `H_D(X)` for large `|D|`.  This file
//! handles the *structural* side: enumerating Cl(O) as an abelian
//! group of forms, which is feasible up to `|D| ≈ 10⁶` on a
//! workstation.

use num_bigint::BigInt;
use num_integer::Integer;
use num_traits::{One, Signed, Zero};
use std::collections::HashMap;
use std::fmt;

/// A primitive positive-definite integral binary quadratic form
/// `f(x, y) = a·x² + b·x·y + c·y²` of negative discriminant
/// `b² − 4ac = D < 0`.
#[derive(Clone, Debug)]
pub struct BinaryQuadraticForm {
    pub a: BigInt,
    pub b: BigInt,
    pub c: BigInt,
}

impl BinaryQuadraticForm {
    /// Construct `(a, b, c)` and check that the discriminant
    /// `b² − 4ac` matches the supplied `disc`.  Returns `None` on
    /// mismatch, on `a ≤ 0`, or on non-primitive forms.
    pub fn new(a: BigInt, b: BigInt, c: BigInt, disc: &BigInt) -> Option<Self> {
        if a <= BigInt::zero() {
            return None;
        }
        let computed = &b * &b - 4 * &a * &c;
        if &computed != disc {
            return None;
        }
        let g = a.gcd(&b).gcd(&c);
        if !g.is_one() {
            return None;
        }
        Some(Self { a, b, c })
    }

    /// Discriminant `b² − 4ac`.  Always negative for the forms
    /// considered here.
    pub fn discriminant(&self) -> BigInt {
        &self.b * &self.b - 4 * &self.a * &self.c
    }

    /// The **principal form** of discriminant `D`.  Represents the
    /// identity of `Cl(O)`.
    ///
    /// - If `D ≡ 0 (mod 4)`:  `(1, 0, -D/4)`.
    /// - If `D ≡ 1 (mod 4)`:  `(1, 1, (1-D)/4)`.
    ///
    /// Any other parity is invalid for a fundamental or order
    /// discriminant.
    pub fn principal(disc: &BigInt) -> Option<Self> {
        let four = BigInt::from(4);
        let r = disc.mod_floor(&four);
        if r == BigInt::zero() {
            let c = -disc / &four;
            Some(Self {
                a: BigInt::one(),
                b: BigInt::zero(),
                c,
            })
        } else if r == BigInt::one() {
            let c = (BigInt::one() - disc) / &four;
            Some(Self {
                a: BigInt::one(),
                b: BigInt::one(),
                c,
            })
        } else {
            None
        }
    }

    /// Lagrange reduction.  Returns the unique reduced form
    /// equivalent to `self` under SL₂(Z).
    pub fn reduce(&self) -> Self {
        let (mut a, mut b, mut c) = (self.a.clone(), self.b.clone(), self.c.clone());

        loop {
            // Step 1: bring `b` into the half-open interval `(-a, a]`.
            let two_a = &a * 2;
            // q ≈ b / (2a), rounded to nearest with ties broken upward
            // so b lands in (-a, a].
            let r = b.mod_floor(&two_a);
            // Translate r into the canonical interval.
            let r = if r > a { r - &two_a } else { r };
            let q = (&b - &r) / &two_a;
            // After x → x + q·y the new form is (a, r, c′).
            c = &c + &q * &q * &a - &q * &b;
            // The relation b = r + 2a·q gives c′ = a q² − b q + c.
            // We've just computed c′.
            b = r;

            // Step 2: if a > c, swap (and negate b).
            if a > c {
                std::mem::swap(&mut a, &mut c);
                b = -b;
                continue;
            }
            // Step 3: handle the boundary canonical cases.
            if a == c && b.is_negative() {
                b = -b;
            } else if a == -&b {
                // |b| == a with b < 0: flip sign to make b ≥ 0.
                b = -b;
            }
            break;
        }
        Self { a, b, c }
    }

    /// Test whether a form is already reduced.
    pub fn is_reduced(&self) -> bool {
        let abs_b = self.b.abs();
        if abs_b > self.a || self.a > self.c {
            return false;
        }
        if (abs_b == self.a || self.a == self.c) && self.b.is_negative() {
            return false;
        }
        true
    }

    /// The **inverse** of `[a, b, c]` is `[a, -b, c]`, then reduced.
    /// (Geometrically: conjugation in the imaginary quadratic field.)
    pub fn inverse(&self) -> Self {
        let inv = Self {
            a: self.a.clone(),
            b: -self.b.clone(),
            c: self.c.clone(),
        };
        inv.reduce()
    }

    /// Gauss / Shanks composition of two forms of the same
    /// discriminant.  Returns the (reduced) product class.
    ///
    /// Reference: Cohen, *A course in computational algebraic
    /// number theory*, Algorithm 5.4.7 (Composition of forms).
    /// The nested extended-GCD pattern handles the case `gcd(a₁, a₂) ∤ s`
    /// without falling back to ad-hoc CRT.
    pub fn compose(&self, other: &Self) -> Self {
        let d_disc = self.discriminant();
        assert_eq!(d_disc, other.discriminant());

        // Cohen's algorithm prefers a₁ ≤ a₂; swap if needed.
        let (a1, b1, _c1, a2, b2, c2) = if self.a <= other.a {
            (
                self.a.clone(),
                self.b.clone(),
                self.c.clone(),
                other.a.clone(),
                other.b.clone(),
                other.c.clone(),
            )
        } else {
            (
                other.a.clone(),
                other.b.clone(),
                other.c.clone(),
                self.a.clone(),
                self.b.clone(),
                self.c.clone(),
            )
        };

        let two = BigInt::from(2);
        let s = (&b1 + &b2) / &two;
        let n = (&b2 - &b1) / &two;

        // Step 1: ext_gcd(a₂, a₁) → (d1, _, y1) with y0·a₂ + y1·a₁ = d1.
        let (d1, _y0, y1) = ext_gcd(&a2, &a1);

        // Step 2: depending on whether d1 | s, take one of two
        // branches for (d, x2, y2).
        let (d, x2, y2) = if s.mod_floor(&d1).is_zero() {
            (d1.clone(), BigInt::zero(), -y1.clone())
        } else {
            // ext_gcd(s, d1) → (d, x2, y3) with x2·s + y3·d1 = d.
            let (d, x2, y3) = ext_gcd(&s, &d1);
            (d, x2, -(&y3 * &y1))
        };

        let v1 = &a1 / &d;
        let v2 = &a2 / &d;

        // r = (y2·n·v2 − x2·c2) mod v1, in [0, v1).
        let r_raw = &y2 * &n * &v2 - &x2 * &c2;
        let r = r_raw.mod_floor(&v1);

        let b3 = &b2 + &two * &v2 * &r;
        let a3 = &v1 * &v2;
        let c3 = (&b3 * &b3 - &d_disc) / (&a3 * BigInt::from(4));

        BinaryQuadraticForm {
            a: a3,
            b: b3,
            c: c3,
        }
        .reduce()
    }

    /// Square the class: `[f]² = compose(f, f)`.
    pub fn square(&self) -> Self {
        self.compose(self)
    }

    /// Repeated composition / class-group exponentiation.
    pub fn pow(&self, k: u64) -> Self {
        if k == 0 {
            let disc = self.discriminant();
            return Self::principal(&disc).expect("principal form exists");
        }
        let mut base = self.reduce();
        let mut acc: Option<Self> = None;
        let mut e = k;
        while e > 0 {
            if e & 1 == 1 {
                acc = Some(match acc {
                    None => base.clone(),
                    Some(a) => a.compose(&base),
                });
            }
            e >>= 1;
            if e > 0 {
                base = base.square();
            }
        }
        acc.unwrap()
    }
}

impl PartialEq for BinaryQuadraticForm {
    fn eq(&self, other: &Self) -> bool {
        // Equality is on the *reduced* form so that composition output
        // matches a canonical representative.
        let r1 = self.reduce();
        let r2 = other.reduce();
        r1.a == r2.a && r1.b == r2.b && r1.c == r2.c
    }
}
impl Eq for BinaryQuadraticForm {}

impl std::hash::Hash for BinaryQuadraticForm {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        let r = self.reduce();
        r.a.hash(state);
        r.b.hash(state);
        r.c.hash(state);
    }
}

impl fmt::Display for BinaryQuadraticForm {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "[{}, {}, {}]", self.a, self.b, self.c)
    }
}

// ── Extended Euclid and small CRT helpers ─────────────────────────────────────

/// Extended GCD over `BigInt`.  Returns `(g, u, v)` with `g = u·a + v·b`,
/// `g > 0`.
fn ext_gcd(a: &BigInt, b: &BigInt) -> (BigInt, BigInt, BigInt) {
    if b.is_zero() {
        let sign = if a.is_negative() {
            BigInt::from(-1)
        } else {
            BigInt::one()
        };
        return (a.abs(), sign, BigInt::zero());
    }
    let (g, u1, v1) = ext_gcd(b, &a.mod_floor(b));
    let u = v1.clone();
    let v = u1 - (a.div_floor(b)) * v1;
    (g, u, v)
}

// (CRT helper removed: Cohen 5.4.7 in `compose` no longer needs it.)

// ── Class-number / class-group enumeration ────────────────────────────────────

/// Enumerate every reduced primitive form of negative discriminant
/// `disc`.  This is the standard enumeration: for each
/// `a` with `1 ≤ a ≤ √(|D|/3)`, and for each `b` with `−a < b ≤ a`
/// of the correct parity (`b ≡ D (mod 2)`), check that
/// `c = (b² − D) / (4a)` is integral, `c ≥ a`, and the form is
/// primitive; add `(a, b, c)` and (when `0 < b < a < c`) its
/// "negative twin" `(a, −b, c)`.
///
/// Complexity: `O(|D|^{1/2 + ε})` arithmetic operations.
pub fn enumerate_reduced_forms(disc: &BigInt) -> Vec<BinaryQuadraticForm> {
    assert!(disc.is_negative(), "discriminant must be negative");
    let abs_d = disc.abs();
    // bound on a: a ≤ √(|D|/3)
    let bound_sq = &abs_d / 3;
    let a_max = isqrt_bigint(&bound_sq);
    let mut forms = Vec::new();
    let parity = disc.mod_floor(&BigInt::from(2));

    let mut a = BigInt::one();
    while a <= a_max {
        // b ≡ D (mod 2)
        let mut b = parity.clone();
        while b <= a {
            // b² − D divisible by 4a?
            let num = &b * &b - disc;
            let denom = &a * 4;
            if num.mod_floor(&denom).is_zero() {
                let c = &num / &denom;
                if c >= a {
                    // primitivity
                    let g = a.gcd(&b).gcd(&c);
                    if g.is_one() {
                        let f = BinaryQuadraticForm {
                            a: a.clone(),
                            b: b.clone(),
                            c: c.clone(),
                        };
                        if f.is_reduced() {
                            forms.push(f.clone());
                            // negative twin, unless |b| ∈ {0, a} or
                            // a == c (those collide with their negative).
                            if !b.is_zero() && b != a && a != c {
                                let mb = -b.clone();
                                let f_neg = BinaryQuadraticForm {
                                    a: a.clone(),
                                    b: mb,
                                    c: c.clone(),
                                };
                                if f_neg.is_reduced() {
                                    forms.push(f_neg);
                                }
                            }
                        }
                    }
                }
            }
            b += BigInt::from(2);
        }
        a += BigInt::one();
    }
    forms
}

/// Class number `h(D)`: the size of the form class group.
pub fn class_number(disc: &BigInt) -> u64 {
    enumerate_reduced_forms(disc).len() as u64
}

/// Integer square root via Newton iteration on `BigInt`.
fn isqrt_bigint(n: &BigInt) -> BigInt {
    if n.is_negative() {
        panic!("isqrt of negative");
    }
    if n.is_zero() {
        return BigInt::zero();
    }
    let bits = n.bits() as usize;
    let mut x = BigInt::from(1) << ((bits / 2) + 1);
    loop {
        let y = (&x + n / &x) >> 1;
        if y >= x {
            return x;
        }
        x = y;
    }
}

// ── The class group as an abelian group ──────────────────────────────────────

/// The class group `Cl(O)` realised as the set of reduced primitive
/// forms of discriminant `D`, together with the composition law.
///
/// We do **not** compute the abelian invariants (i.e. the
/// decomposition `Z/d₁ × Z/d₂ × …`) — that would require a full
/// Smith-normal form pass on the relation matrix, which is
/// out of scope.  Callers can:
///
/// - Compute `h = elements.len()` (the class number).
/// - Enumerate every class.
/// - Look up the inverse / product of any pair via the table.
#[derive(Clone, Debug)]
pub struct ClassGroup {
    pub discriminant: BigInt,
    pub elements: Vec<BinaryQuadraticForm>,
    /// Lookup table from reduced-form representation to index.
    pub index_of: HashMap<BinaryQuadraticForm, usize>,
    /// Composition multiplication table (small only).  None when
    /// `h > MAX_TABULATED_H`.
    pub mul_table: Option<Vec<Vec<usize>>>,
}

const MAX_TABULATED_H: usize = 64;

impl ClassGroup {
    /// Build `Cl(O)` for the given discriminant.  Builds the full
    /// multiplication table when `h ≤ MAX_TABULATED_H`.
    pub fn new(disc: &BigInt) -> Self {
        let elements = enumerate_reduced_forms(disc);
        let mut index_of = HashMap::new();
        for (i, e) in elements.iter().enumerate() {
            index_of.insert(e.clone(), i);
        }
        let mul_table = if elements.len() <= MAX_TABULATED_H {
            let mut t = vec![vec![0usize; elements.len()]; elements.len()];
            for i in 0..elements.len() {
                for j in 0..elements.len() {
                    let p = elements[i].compose(&elements[j]);
                    let k = *index_of
                        .get(&p)
                        .expect("composition stayed inside the class group");
                    t[i][j] = k;
                }
            }
            Some(t)
        } else {
            None
        };
        Self {
            discriminant: disc.clone(),
            elements,
            index_of,
            mul_table,
        }
    }

    pub fn class_number(&self) -> usize {
        self.elements.len()
    }

    pub fn identity(&self) -> &BinaryQuadraticForm {
        // Principal form has a == 1 and is therefore unique and first.
        self.elements
            .iter()
            .find(|f| f.a == BigInt::one())
            .expect("principal form is always reduced")
    }

    /// Compose two classes by index.  Falls back to direct
    /// composition when the multiplication table is absent.
    pub fn compose(&self, i: usize, j: usize) -> usize {
        if let Some(t) = &self.mul_table {
            return t[i][j];
        }
        let p = self.elements[i].compose(&self.elements[j]);
        *self.index_of.get(&p).expect("closure of Cl(O)")
    }
}

// ── Action on j-invariants (stub / interface) ────────────────────────────────
//
// The class group acts on the set of j-invariants of CM curves with
// the given endomorphism ring: `[a] · j(E) = j(E')` where `E' = E /
// E[a]` (the quotient by the `a`-torsion subgroup defined by the
// ideal `a`).  A faithful implementation requires:
//
//   1. Reading off prime ideals from each form (via `a · x² + b x y
//      + c y² = ℓ` for split primes `ℓ`).
//   2. For each split prime, applying the corresponding `ℓ`-isogeny
//      via Vélu's formulas on `E`.
//
// We provide the *interface* here and call into the volcano /
// Vélu modules for the actual isogeny work.  See
// [`crate::isogeny::volcano::horizontal_step`].

/// Given a small split prime `ℓ` and a discriminant `D`, return the
/// reduced form `(ℓ, b, c)` (if any) representing the unique class
/// `[l]` above `ℓ`.  Used to look up which volcano edge is being
/// traversed.
pub fn class_above_prime(disc: &BigInt, ell: u64) -> Option<BinaryQuadraticForm> {
    // Split iff D is a QR mod 4ℓ and ℓ ∤ D.  We do an exhaustive
    // search for b ∈ [0, 2ℓ) with b² ≡ D (mod 4ℓ).
    let four_ell = BigInt::from(4 * ell);
    let target = disc.mod_floor(&four_ell);
    let target = (target + &four_ell).mod_floor(&four_ell);

    for b_small in 0..(2 * ell) {
        let b = BigInt::from(b_small as i64);
        let b2 = (&b * &b).mod_floor(&four_ell);
        if b2 == target {
            // c = (b² − D) / (4ℓ)
            let num = &b * &b - disc;
            let denom = BigInt::from(4 * ell);
            if num.mod_floor(&denom).is_zero() {
                let c = &num / &denom;
                let f = BinaryQuadraticForm {
                    a: BigInt::from(ell),
                    b,
                    c,
                };
                let r = f.reduce();
                // primitivity
                let g = r.a.gcd(&r.b).gcd(&r.c);
                if g.is_one() {
                    return Some(r);
                }
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    fn d(v: i64) -> BigInt {
        BigInt::from(v)
    }

    #[test]
    fn class_number_3_mod4() {
        // h(-3) = 1 (only class is the principal one).
        assert_eq!(class_number(&d(-3)), 1);
    }

    #[test]
    fn class_number_4() {
        // h(-4) = 1 (CM by Z[i]).
        assert_eq!(class_number(&d(-4)), 1);
    }

    #[test]
    fn class_number_class_one_discriminants() {
        // The famous nine fundamental class-number-1 discriminants
        // for ℂ-CM curves with End_Q(E) maximal.
        for d_val in [-3, -4, -7, -8, -11, -19, -43, -67, -163] {
            assert_eq!(class_number(&d(d_val)), 1, "expected h({}) = 1", d_val);
        }
    }

    #[test]
    fn class_number_negative_23() {
        // h(-23) = 3 — the smallest non-cyclic-trivial example.
        // The three reduced forms are (1,1,6), (2,1,3), (2,-1,3).
        let forms = enumerate_reduced_forms(&d(-23));
        assert_eq!(forms.len(), 3);
        let mut printed: Vec<String> = forms.iter().map(|f| f.to_string()).collect();
        printed.sort();
        assert_eq!(
            printed,
            vec![
                "[1, 1, 6]".to_string(),
                "[2, -1, 3]".to_string(),
                "[2, 1, 3]".to_string()
            ],
        );
    }

    #[test]
    fn class_number_negative_47() {
        // h(-47) = 5.
        assert_eq!(class_number(&d(-47)), 5);
    }

    #[test]
    fn principal_form_is_identity() {
        let cg = ClassGroup::new(&d(-23));
        let principal = cg.identity().clone();
        // principal · anything == anything.
        for f in &cg.elements {
            assert_eq!(principal.compose(f), f.reduce());
        }
    }

    #[test]
    fn inverse_is_two_sided() {
        let cg = ClassGroup::new(&d(-23));
        let principal = cg.identity().clone();
        for f in &cg.elements {
            let inv = f.inverse();
            let prod = f.compose(&inv);
            assert_eq!(prod, principal);
        }
    }

    #[test]
    fn class_group_is_cyclic_order_3_for_d23() {
        // Cl(-23) ≅ Z/3.  Pick the non-identity (2,1,3) — its cube
        // must be the identity.
        let f213 = BinaryQuadraticForm {
            a: BigInt::from(2),
            b: BigInt::from(1),
            c: BigInt::from(3),
        };
        assert!(f213.is_reduced());
        let cube = f213.pow(3);
        assert_eq!(cube.a, BigInt::one());
    }

    #[test]
    fn lagrange_reduction_idempotent() {
        let f = BinaryQuadraticForm {
            a: BigInt::from(13),
            b: BigInt::from(11),
            c: BigInt::from(3),
        };
        let r = f.reduce();
        let r2 = r.reduce();
        assert_eq!(r, r2);
        assert!(r.is_reduced());
    }
}
