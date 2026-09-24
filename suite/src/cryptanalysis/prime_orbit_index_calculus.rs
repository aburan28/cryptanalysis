//! # Automorphism-orbit index calculus on prime-field curves.
//!
//! The binary Koblitz pipeline ([`super::koblitz_index_calculus`]) gets its
//! speed-up from a factor base closed under Frobenius: the unknowns
//! collapse to one per signed Frobenius orbit, because
//! `log π^k(P) = λ^k log P`.  A prime field has no Frobenius acting on the
//! points, but some prime-field curves have **automorphisms** that play
//! exactly that role, and the curve type decides which:
//!
//! | type | curve | `Aut(E)` on `⟨G⟩` | action on `(x, y)` | eigenvalue |
//! |---|---|---|---|---|
//! | generic | P-192 … P-521, Brainpool, SM2, GOST | `{±1}`, `w = 2` | `(x, ±y)` | `±1` |
//! | `j = 0`, `p ≡ 1 (3)` | secp160k1 … secp256k1 | `μ₆`, `w = 6` | `(ζᵏx, ±y)` | `±λᵏ`, `λ² + λ + 1 ≡ 0` |
//! | `j = 1728`, `p ≡ 1 (4)` | `y² = x³ + ax` | `μ₄`, `w = 4` | `ιᵏ`, `ι(x, y) = (−x, iy)` | `μᵏ`, `μ² ≡ −1` |
//!
//! Take a factor base that is a union of `m` full `Aut`-orbits.  It has
//! `w·m` points but only `m` unknowns, since every orbit member's
//! logarithm is `e(α)·log(rep)` for a known eigenvalue `e(α)`.  A
//! decomposition `R = α(P_o) + β(P_o')` through *any* orbit members is a
//! relation `e(α) x_o + e(β) x_o' ≡ log R` in those `m` unknowns.  Against
//! a base that uses only negation, the same number of unknowns covers
//! `(w/2)²` times as many pair sums: 9× on a `j = 0` curve.  That is the
//! prime-field analogue of the Galbraith–Granger–Merz–Petit Frobenius
//! collapse, and it is what [`super::ec_index_calculus_j0`] does not do —
//! its relation finder accepts only decompositions through the stored
//! orbit representatives, so the `ζ`-images never serve as summands and
//! the order-6 automorphism adds no coverage there.
//!
//! # The pipeline
//!
//! 1. **Curve.**  [`generate_instance`] builds a curve of a requested
//!    [`ScaledShape`] — keeping `a = −3` for a NIST-shaped curve, `b = 7`
//!    for a secp256k1-shaped one — and *certifies* its group order: a
//!    baby-step giant-step over the Hasse interval finds `N` with
//!    `[N]P = O`, and `N = h·r` with `r` prime, wider than the interval,
//!    and `[h]P ≠ O` proves `#E = N` (see [`OrderCertificate`]).
//! 2. **Automorphisms.**  [`OrbitCurve::from_params`] derives the table
//!    above and checks every eigenvalue on the generator: `α(G) = [e(α)]G`.
//! 3. **Factor base.**  [`OrbitFactorBase::select`] draws abscissae
//!    pseudo-randomly, lifts them, multiplies by the cofactor (so every
//!    base point lies in `⟨G⟩`) and keeps one representative per orbit.
//!    No logarithm is used.
//! 4. **Decomposition.**  The oracle sweeps `α⁻¹(R) − P_o` over every
//!    automorphism `α` and every representative, one batched inversion per
//!    block, and looks the difference up by abscissa.  A hit is re-added
//!    in the group before it becomes a relation.
//! 5. **Logarithms.**  Relations `R = [a]G` have at most two unknowns, so
//!    the system is a gain graph and [`solve_two_term_system`] solves it
//!    exactly, component by component: a spanning tree expresses every
//!    logarithm affinely in the root's, and a cycle whose gain is not `1`,
//!    or a one-term relation, pins the root.  Every solved column is
//!    certified by `[x_o]G == P_o`; an uncertified one is never used.
//! 6. **Descent.**  A target `Q` is recovered from one decomposition of
//!    `R = [a]G + [b]Q` over the certified orbits, and checked as
//!    `[d]G == Q`.
//! 7. **Baseline.**  [`rho_baseline`] is a distinguished-point Pollard rho
//!    in the same arithmetic, walks sized to the instance sharing one
//!    inversion per step, over a jump table of multiples of `G` that every
//!    target shares, as they share the logarithm database.  It does not
//!    fold by `Aut`; the report carries the `√w` folded expectation
//!    beside it.
//!
//! # Costs, and what they mean
//!
//! A random point decomposes with `≈ (wm)²/(2r)` expected witnesses, and
//! the sweep stops at the first one, so a relation costs `≈ r/(wm)`
//! subtractions.  Collecting the `≈ c·m` relations the logarithms need is
//! therefore `≈ c·r/w` whatever `m` is — linear in `r`, far above rho's
//! `√r` — while one *descent* costs `≈ r/(wm)`, which a wide base pushes
//! below rho.  That is the same split the binary `vs_rho` block reports:
//! a charged (per-target, database paid) comparison that index calculus
//! can win, and a whole-process one it loses unless the precomputation is
//! amortised over `Ω(√r)` targets.  Counts are reported in group
//! operations (affine additions, each sharing a batched inversion on both
//! sides), so they compare across implementations; wall time is reported
//! beside them.
//!
//! None of this threatens a deployed curve: at 256 bits the precomputation
//! alone is `≈ 2^{256}/w` operations.

use crate::cryptanalysis::bsgs_fast::{FastCurve, FastField, FastPoint};
use crate::cryptanalysis::ec_index_calculus_curves::{classify, CurveKind, ScaledInstance};
use crate::cryptanalysis::fx_hash::FxMap;
use crate::ecc::curve::CurveParams;
use crate::ecc::point::Point;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::time::Instant;

/// Largest field a curve is built over: coordinates and the subgroup order
/// must fit the single-word Montgomery arithmetic of [`FastField`].
pub const MAX_FIELD_BITS: u32 = 62;
/// Smallest field [`generate_instance`] builds over.  Below this the
/// certificate's `r > 4√p` has too little room.
pub const MIN_FIELD_BITS: u32 = 8;
/// Representatives per batched inversion in the decomposition sweep.  The
/// sweep stops at the first hit, so a block bounds the wasted work.
const SWEEP_BLOCK: usize = 256;

// ── Arithmetic modulo the subgroup order ───────────────────────────────

#[inline]
fn mul_r(a: u64, b: u64, r: u64) -> u64 {
    ((a as u128 * b as u128) % r as u128) as u64
}
#[inline]
fn add_r(a: u64, b: u64, r: u64) -> u64 {
    let s = a as u128 + b as u128;
    (s % r as u128) as u64
}
#[inline]
fn sub_r(a: u64, b: u64, r: u64) -> u64 {
    add_r(a, r - b % r, r)
}
fn pow_r(mut base: u64, mut e: u64, r: u64) -> u64 {
    let mut acc = 1 % r;
    base %= r;
    while e > 0 {
        if e & 1 == 1 {
            acc = mul_r(acc, base, r);
        }
        base = mul_r(base, base, r);
        e >>= 1;
    }
    acc
}
/// `a⁻¹ mod r` by extended Euclid; `None` when `gcd(a, r) ≠ 1`.
fn inv_r(a: u64, r: u64) -> Option<u64> {
    let (mut old_r, mut rr) = (a as i128 % r as i128, r as i128);
    let (mut old_s, mut s) = (1i128, 0i128);
    while rr != 0 {
        let q = old_r / rr;
        (old_r, rr) = (rr, old_r - q * rr);
        (old_s, s) = (s, old_s - q * s);
    }
    (old_r == 1).then(|| old_s.rem_euclid(r as i128) as u64)
}
/// A square root of `a` modulo the odd prime `r` (Tonelli–Shanks), if any.
fn sqrt_r(a: u64, r: u64) -> Option<u64> {
    let a = a % r;
    if a == 0 {
        return Some(0);
    }
    if pow_r(a, (r - 1) / 2, r) != 1 {
        return None;
    }
    let (mut q, mut s) = (r - 1, 0u32);
    while q & 1 == 0 {
        q >>= 1;
        s += 1;
    }
    let z = (2..r).find(|&z| pow_r(z, (r - 1) / 2, r) == r - 1)?;
    let (mut m, mut c, mut t, mut x) = (
        s,
        pow_r(z, q, r),
        pow_r(a, q, r),
        pow_r(a, q.div_ceil(2), r),
    );
    while t != 1 {
        let mut i = 0u32;
        let mut t2 = t;
        while t2 != 1 {
            t2 = mul_r(t2, t2, r);
            i += 1;
            if i == m {
                return None;
            }
        }
        let b = pow_r(c, 1u64 << (m - i - 1), r);
        m = i;
        c = mul_r(b, b, r);
        t = mul_r(t, c, r);
        x = mul_r(x, b, r);
    }
    Some(x)
}

/// Deterministic Miller–Rabin for `n < 2^64`: the first twelve primes as
/// bases prove primality below `3.3 · 10^24`.
pub fn is_prime_u64(n: u64) -> bool {
    const BASES: [u64; 12] = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37];
    if n < 2 {
        return false;
    }
    for p in BASES {
        if n == p {
            return true;
        }
        if n.is_multiple_of(p) {
            return false;
        }
    }
    let (mut d, mut s) = (n - 1, 0u32);
    while d & 1 == 0 {
        d >>= 1;
        s += 1;
    }
    'witness: for a in BASES {
        let mut x = pow_r(a, d, n);
        if x == 1 || x == n - 1 {
            continue;
        }
        for _ in 1..s {
            x = mul_r(x, x, n);
            if x == n - 1 {
                continue 'witness;
            }
        }
        return false;
    }
    true
}

fn isqrt(v: u64) -> u64 {
    let mut s = (v as f64).sqrt() as u64;
    while s > 0 && s.saturating_mul(s) > v {
        s -= 1;
    }
    while (s + 1).saturating_mul(s + 1) <= v {
        s += 1;
    }
    s
}

// ── The curve with its automorphism group ──────────────────────────────

/// One automorphism `α(x, y) = (cx·x, cy·y)` of the curve and the scalar
/// it acts as on `⟨G⟩`: `α(P) = [eig]P`.  `cx`, `cy` are in Montgomery
/// form; `eig` is an integer modulo `r`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Automorphism {
    pub cx: u64,
    pub cy: u64,
    pub eig: u64,
}

/// A prime-field curve in single-word Montgomery arithmetic, its
/// prime-order subgroup `⟨G⟩` of order `r` and cofactor `h`, and its
/// automorphism group with every eigenvalue verified on `G`.
#[derive(Clone, Debug)]
pub struct OrbitCurve {
    pub kind: CurveKind,
    /// Field, point arithmetic, the subgroup order `r = fast.n` and `G`.
    pub fast: FastCurve,
    /// `a` and `b` in Montgomery form.
    a: u64,
    b: u64,
    pub r: u64,
    pub h: u64,
    /// `Aut(E)` acting on `⟨G⟩`; `aut[0]` is the identity.
    pub aut: Vec<Automorphism>,
    /// `aut_inv[i]` indexes the inverse of `aut[i]`.
    aut_inv: Vec<usize>,
    /// The distinct abscissa multipliers `cx`, one per `x`-image of an orbit.
    xmul: Vec<u64>,
    /// Tonelli–Shanks data for square roots in `F_p`.
    sqrt_nonresidue: u64,
    two_adicity: u32,
    odd_part: u64,
}

impl OrbitCurve {
    /// Adopt a curve whose prime, subgroup order and generator fit a word,
    /// deriving its automorphism group from its type.
    ///
    /// `j = 0` with `p ≡ 1 (3)` gets `μ₆`, `j = 1728` with `p ≡ 1 (4)` gets
    /// `μ₄`, everything else `{±1}` (a `j = 0` curve with `p ≡ 2 (3)` is
    /// supersingular and has only negation over `F_p`).  Every eigenvalue
    /// is checked on `G`; a curve where one does not hold is refused.
    pub fn from_params(c: &CurveParams) -> Result<Self, String> {
        if c.p.bits() > u64::from(MAX_FIELD_BITS) || c.n.bits() > u64::from(MAX_FIELD_BITS) {
            return Err(format!(
                "the orbit engine needs p and r below 2^{MAX_FIELD_BITS}; this curve has a {}-bit field",
                c.p.bits()
            ));
        }
        let fast = FastCurve::from_params(c).ok_or("generator is not on the curve")?;
        let f = fast.f;
        let p = f.modulus();
        let r = fast.n;
        if !is_prime_u64(r) {
            return Err(format!("subgroup order {r} is not prime"));
        }
        let (mut odd_part, mut two_adicity) = (p - 1, 0u32);
        while odd_part & 1 == 0 {
            odd_part >>= 1;
            two_adicity += 1;
        }
        let euler = |v: u64| f.pow(f.to_mont(v), (p - 1) / 2);
        let sqrt_nonresidue = (2..p)
            .find(|&z| euler(z) == f.neg(f.one()))
            .map(|z| f.to_mont(z))
            .ok_or("no quadratic non-residue")?;
        let mut curve = Self {
            kind: classify(c),
            fast,
            a: f.to_mont(c.a.to_u64().unwrap_or(0)),
            b: f.to_mont(c.b.to_u64().unwrap_or(0)),
            r,
            h: u64::from(c.h),
            aut: Vec::new(),
            aut_inv: Vec::new(),
            xmul: Vec::new(),
            sqrt_nonresidue,
            two_adicity,
            odd_part,
        };
        let one = f.one();
        let minus_one = f.neg(one);
        let negation = [
            Automorphism {
                cx: one,
                cy: one,
                eig: 1,
            },
            Automorphism {
                cx: one,
                cy: minus_one,
                eig: r - 1,
            },
        ];
        curve.aut = match curve.kind {
            CurveKind::J0 if p % 3 == 1 => curve.order_six_table()?,
            CurveKind::J1728 if p % 4 == 1 => curve.order_four_table()?,
            _ => negation.to_vec(),
        };
        curve.finish_table()?;
        Ok(curve)
    }

    /// `μ₆ = {±ψᵏ}` with `ψ(x, y) = (ζx, y)`, `ψ(G) = [λ]G`.
    fn order_six_table(&self) -> Result<Vec<Automorphism>, String> {
        let f = self.fast.f;
        let (p, r) = (f.modulus(), self.r);
        // An element of order 3 in F_p^*.
        let zeta = (2..p)
            .map(|g| f.pow(f.to_mont(g), (p - 1) / 3))
            .find(|&z| z != f.one())
            .ok_or("no cube root of unity")?;
        // λ² + λ + 1 ≡ 0 (mod r): λ = (−1 ± √−3)/2.
        let s =
            sqrt_r(r - 3, r).ok_or("−3 is not a square mod r; the GLV eigenvalue is undefined")?;
        let half = inv_r(2, r).ok_or("r = 2")?;
        let psi_g = FastPoint {
            x: f.mul(zeta, self.fast.g.x),
            y: self.fast.g.y,
            infinity: false,
        };
        let lambda = [s, r - s]
            .into_iter()
            .map(|s| mul_r(sub_r(s, 1, r), half, r))
            .find(|&l| self.fast.scalar_mul(self.fast.g, l) == psi_g)
            .ok_or("neither root of λ² + λ + 1 is the eigenvalue of ψ on G")?;
        let mut table = Vec::with_capacity(6);
        for sign in [1u64, r - 1] {
            let cy = if sign == 1 { f.one() } else { f.neg(f.one()) };
            let (mut cx, mut eig) = (f.one(), sign);
            for _ in 0..3 {
                table.push(Automorphism { cx, cy, eig });
                cx = f.mul(cx, zeta);
                eig = mul_r(eig, lambda, r);
            }
        }
        Ok(table)
    }

    /// `μ₄ = {ιᵏ}` with `ι(x, y) = (−x, iy)`, `i² = −1`, `ι(G) = [μ]G`.
    fn order_four_table(&self) -> Result<Vec<Automorphism>, String> {
        let f = self.fast.f;
        let (p, r) = (f.modulus(), self.r);
        let i = (2..p)
            .map(|g| f.pow(f.to_mont(g), (p - 1) / 4))
            .find(|&z| f.sqr(z) == f.neg(f.one()))
            .ok_or("no fourth root of unity")?;
        let s =
            sqrt_r(r - 1, r).ok_or("−1 is not a square mod r; the eigenvalue of ι is undefined")?;
        let iota_g = FastPoint {
            x: f.neg(self.fast.g.x),
            y: f.mul(i, self.fast.g.y),
            infinity: false,
        };
        let mu = [s, r - s]
            .into_iter()
            .find(|&m| self.fast.scalar_mul(self.fast.g, m) == iota_g)
            .ok_or("neither square root of −1 is the eigenvalue of ι on G")?;
        let mut table = Vec::with_capacity(4);
        let (mut cx, mut cy, mut eig) = (f.one(), f.one(), 1u64);
        for _ in 0..4 {
            table.push(Automorphism { cx, cy, eig });
            cx = f.neg(cx);
            cy = f.mul(cy, i);
            eig = mul_r(eig, mu, r);
        }
        Ok(table)
    }

    /// Inverses, distinct abscissa multipliers, and the eigenvalue check.
    fn finish_table(&mut self) -> Result<(), String> {
        let f = self.fast.f;
        for al in &self.aut {
            if self.fast.scalar_mul(self.fast.g, al.eig) != self.apply(al, self.fast.g) {
                return Err("an automorphism does not act on G as its eigenvalue".into());
            }
        }
        self.aut_inv = self
            .aut
            .iter()
            .map(|al| {
                self.aut
                    .iter()
                    .position(|be| f.mul(al.cx, be.cx) == f.one() && f.mul(al.cy, be.cy) == f.one())
                    .ok_or("automorphism table is not closed under inversion")
            })
            .collect::<Result<_, _>>()?;
        let mut xmul: Vec<u64> = self.aut.iter().map(|al| al.cx).collect();
        xmul.sort_unstable();
        xmul.dedup();
        self.xmul = xmul;
        Ok(())
    }

    /// `|Aut(E)|` acting on `⟨G⟩`.
    pub fn automorphism_order(&self) -> usize {
        self.aut.len()
    }

    /// `α(P)`.
    #[inline]
    pub fn apply(&self, al: &Automorphism, p: FastPoint) -> FastPoint {
        if p.infinity {
            return p;
        }
        let f = &self.fast.f;
        FastPoint {
            x: f.mul(al.cx, p.x),
            y: f.mul(al.cy, p.y),
            infinity: false,
        }
    }

    /// `x³ + a x + b`, Montgomery form in and out.
    fn rhs(&self, x: u64) -> u64 {
        let f = &self.fast.f;
        f.add(f.add(f.mul(f.sqr(x), x), f.mul(self.a, x)), self.b)
    }

    /// A square root in `F_p` (Tonelli–Shanks, Montgomery form), if any.
    fn sqrt(&self, v: u64) -> Option<u64> {
        let f = &self.fast.f;
        if v == 0 {
            return Some(0);
        }
        let p = f.modulus();
        if f.pow(v, (p - 1) / 2) != f.one() {
            return None;
        }
        let (mut m, mut c) = (self.two_adicity, f.pow(self.sqrt_nonresidue, self.odd_part));
        let mut t = f.pow(v, self.odd_part);
        let mut x = f.pow(v, self.odd_part.div_ceil(2));
        while t != f.one() {
            let (mut i, mut t2) = (0u32, t);
            while t2 != f.one() {
                t2 = f.sqr(t2);
                i += 1;
                if i == m {
                    return None;
                }
            }
            let mut b = c;
            for _ in 0..(m - i - 1) {
                b = f.sqr(b);
            }
            m = i;
            c = f.sqr(b);
            t = f.mul(t, c);
            x = f.mul(x, b);
        }
        Some(x)
    }

    /// `[k]G`.
    pub fn mul_g(&self, k: u64) -> FastPoint {
        self.fast.scalar_mul(self.fast.g, k % self.r)
    }

    /// The generator in the general representation.
    pub fn generator(&self) -> Point {
        self.fast.lower(self.fast.g)
    }

    /// The curve in the general representation, with `n` the subgroup order.
    pub fn params(&self, name: &'static str) -> CurveParams {
        let f = &self.fast.f;
        let g = self.fast.g;
        CurveParams {
            name,
            p: BigUint::from(f.modulus()),
            a: BigUint::from(f.from_mont(self.a)),
            b: BigUint::from(f.from_mont(self.b)),
            gx: BigUint::from(f.from_mont(g.x)),
            gy: BigUint::from(f.from_mont(g.y)),
            n: BigUint::from(self.r),
            h: self.h as u32,
        }
    }

    /// The same curve with its automorphism group cut down to `{±1}`: the
    /// control that isolates what the extra automorphisms buy.
    pub fn negation_only(&self) -> Self {
        let mut c = self.clone();
        let f = c.fast.f;
        c.aut = vec![
            Automorphism {
                cx: f.one(),
                cy: f.one(),
                eig: 1,
            },
            Automorphism {
                cx: f.one(),
                cy: f.neg(f.one()),
                eig: c.r - 1,
            },
        ];
        c.aut_inv = vec![0, 1];
        c.xmul = vec![f.one()];
        c
    }
}

// ── Curve generation with a certified group order ──────────────────────

/// A curve coefficient in a [`ScaledShape`]: drawn at random, or fixed to
/// a small signed integer reduced mod `p` (`−3` for the NIST curves, `7`
/// for secp256k1, `0` for the `j`-special families).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Coefficient {
    Random,
    Fixed(i64),
}

impl Coefficient {
    fn value(self, p: u64, rng: &mut StdRng) -> u64 {
        match self {
            Coefficient::Random => rng.gen_range(1..p),
            Coefficient::Fixed(v) => v.rem_euclid(p as i64) as u64,
        }
    }
}

/// What a scaled-down curve keeps of the curve it stands for: which
/// coefficients are fixed, and the largest cofactor allowed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct ScaledShape {
    pub kind: CurveKind,
    pub a: Coefficient,
    pub b: Coefficient,
    pub max_cofactor: u64,
}

impl ScaledShape {
    /// The default shape of a type: random coefficients where the type
    /// allows, prime order, except `j = 1728` whose order is always even
    /// (the rational 2-torsion point `(0, 0)`), which gets cofactor ≤ 4.
    pub fn of_kind(kind: CurveKind) -> Self {
        match kind {
            CurveKind::Generic => Self {
                kind,
                a: Coefficient::Random,
                b: Coefficient::Random,
                max_cofactor: 1,
            },
            CurveKind::J0 => Self {
                kind,
                a: Coefficient::Fixed(0),
                b: Coefficient::Random,
                max_cofactor: 1,
            },
            CurveKind::J1728 => Self {
                kind,
                a: Coefficient::Random,
                b: Coefficient::Fixed(0),
                max_cofactor: 4,
            },
        }
    }

    /// The shape of a deployed curve: a coefficient that is small, or is
    /// `p − small` (the NIST `a = −3`), is kept; a random-looking one is
    /// redrawn.  The cofactor bound is the curve's own (at least what the
    /// type forces).
    pub fn of_curve(c: &CurveParams) -> Self {
        let kind = classify(c);
        let keep = |v: &BigUint| -> Coefficient {
            const SMALL: u64 = 1 << 16;
            if let Some(v) = v.to_u64().filter(|&v| v < SMALL) {
                return Coefficient::Fixed(v as i64);
            }
            if v < &c.p {
                if let Some(d) = (&c.p - v).to_u64().filter(|&d| d < SMALL) {
                    return Coefficient::Fixed(-(d as i64));
                }
            }
            Coefficient::Random
        };
        let base = Self::of_kind(kind);
        Self {
            kind,
            a: keep(&c.a),
            b: keep(&c.b),
            max_cofactor: base.max_cofactor.max(u64::from(c.h)),
        }
    }

    fn residue_ok(&self, p: u64) -> bool {
        match self.kind {
            CurveKind::Generic => true,
            CurveKind::J0 => p % 3 == 1,
            CurveKind::J1728 => p % 4 == 1,
        }
    }
}

/// The proof that `#E(F_p) = N`.
///
/// `[N]P = O` for a point `P`, `N` lies in the (padded) Hasse interval
/// `[lo, hi]`, `N = h·r` with `r` prime and `r > hi − lo`, and `[h]P ≠ O`.
/// Then `r | ord(P)`, so `ord(P) > hi − lo`, so `N` is the only multiple
/// of `ord(P)` in the interval — and `#E` is one.  The generator is
/// `G = [h]P`, of order `r`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct OrderCertificate {
    pub group_order: u64,
    pub cofactor: u64,
    pub subgroup_order: u64,
    pub hasse_lo: u64,
    pub hasse_hi: u64,
    /// Group operations the baby-step giant-step order search took.
    pub bsgs_steps: u64,
}

/// Find `N ∈ [lo, hi]` with `[N]P = O` by baby-step giant-step with the
/// negation map, then try to certify it.  `None` when no certificate with
/// cofactor at most `max_cofactor` exists for this point.
fn certify_order(fc: &FastCurve, pt: FastPoint, max_cofactor: u64) -> Option<OrderCertificate> {
    let p = fc.f.modulus();
    let s = isqrt(p);
    let lo = (p + 1).saturating_sub(2 * s + 2).max(1);
    let hi = p + 1 + 2 * s + 2;
    let width = hi - lo;
    let m = isqrt(width / 2).max(1) + 1;
    let mut steps = 0u64;
    // Baby steps: x([j]P) → j, for 1 ≤ j ≤ m.
    let mut baby: FxMap<u64, u64> = FxMap::default();
    let mut cur = pt;
    for j in 1..=m {
        if cur.infinity {
            return None; // ord(P) ≤ m: far too small to certify
        }
        baby.entry(cur.x).or_insert(j);
        cur = fc.add(cur, pt);
        steps += 1;
    }
    // Giant steps: T_i = [lo + i·(2m+1)]P against ±[j]P.
    let stride = 2 * m + 1;
    let giant = fc.scalar_mul(pt, stride);
    let mut t = fc.scalar_mul(pt, lo);
    let mut base = lo;
    while base <= hi + m {
        let mut candidates = [None, None];
        if t.infinity {
            candidates[0] = Some(base);
        } else if let Some(&j) = baby.get(&t.x) {
            let pj = fc.scalar_mul(pt, j);
            if t == fc.neg(pj) {
                candidates[0] = Some(base + j);
            } else if t == pj {
                candidates[0] = base.checked_sub(j);
            }
        }
        for n in candidates.into_iter().flatten() {
            if !(lo..=hi).contains(&n) || !fc.scalar_mul(pt, n).infinity {
                continue;
            }
            // Smallest cofactor first, so r is as large as it can be.
            for h in 1..=max_cofactor {
                if !n.is_multiple_of(h) {
                    continue;
                }
                let r = n / h;
                if r > width && is_prime_u64(r) && !fc.scalar_mul(pt, h).infinity {
                    return Some(OrderCertificate {
                        group_order: n,
                        cofactor: h,
                        subgroup_order: r,
                        hasse_lo: lo,
                        hasse_hi: hi,
                        bsgs_steps: steps,
                    });
                }
            }
            return None;
        }
        t = fc.add(t, giant);
        base += stride;
        steps += 1;
    }
    None
}

/// A generated curve with a certified order and a planted logarithm.
#[derive(Clone, Debug)]
pub struct GeneratedInstance {
    pub curve: OrbitCurve,
    pub certificate: OrderCertificate,
    /// The planted logarithm; `target = [known_log]G`.
    pub known_log: u64,
    pub target: FastPoint,
    /// Curves tried before this one certified.
    pub curves_tried: u64,
}

impl GeneratedInstance {
    /// Field size in bits.
    pub fn field_bits(&self) -> u32 {
        64 - self.curve.fast.f.modulus().leading_zeros()
    }

    /// `count` known-answer targets `(k, [k]G)`: the planted logarithm
    /// first, then logarithms drawn reproducibly from `seed`.
    pub fn targets(&self, count: usize, seed: u64) -> Vec<(u64, FastPoint)> {
        let mut rng = StdRng::seed_from_u64(seed ^ 0x7461_7267_6574_7300);
        let mut out = vec![(self.known_log, self.target)];
        while out.len() < count {
            let k = rng.gen_range(1..self.curve.r);
            out.push((k, self.curve.mul_g(k)));
        }
        out
    }

    /// The instance in the general `num-bigint` representation, for the
    /// Semaev reference solvers.
    pub fn scaled(&self) -> ScaledInstance {
        let name = match self.curve.kind {
            CurveKind::Generic => "scaled-generic",
            CurveKind::J0 => "scaled-j0",
            CurveKind::J1728 => "scaled-j1728",
        };
        ScaledInstance {
            kind: self.curve.kind,
            curve: self.curve.params(name),
            known_log: BigUint::from(self.known_log),
            generator: self.curve.generator(),
            target: self.curve.fast.lower(self.target),
        }
    }
}

/// Build a curve of `shape` over a `bits`-bit prime with a certified group
/// order, deterministically from `seed`, and plant a logarithm in it.
///
/// The prime is drawn from `[2^{bits−1}, 2^bits)` in the congruence class
/// the type's automorphisms need (`p ≡ 1 (3)` for `j = 0`, `p ≡ 1 (4)`
/// for `j = 1728`), and coefficients are drawn per the shape until one
/// curve certifies with cofactor at most `shape.max_cofactor`.  Anomalous
/// curves (`#E = p`, polynomial-time by Smart's attack) are skipped.
/// `known_log` plants a specific logarithm; `None` draws one from `seed`.
pub fn generate_instance(
    shape: ScaledShape,
    bits: u32,
    known_log: Option<u64>,
    seed: u64,
) -> Result<GeneratedInstance, String> {
    if !(MIN_FIELD_BITS..=MAX_FIELD_BITS).contains(&bits) {
        return Err(format!(
            "field size must be {MIN_FIELD_BITS}..={MAX_FIELD_BITS} bits"
        ));
    }
    if shape.kind == CurveKind::J1728 && shape.max_cofactor < 2 {
        return Err(
            "y² = x³ + ax always has the rational 2-torsion point (0, 0): a j1728 curve needs cofactor ≥ 2"
                .into(),
        );
    }
    let mut rng = StdRng::seed_from_u64(seed ^ 0x6f72_6269_745f_6963);
    let lo = 1u64 << (bits - 1);
    let hi = if bits == 64 { u64::MAX } else { 1u64 << bits };
    let fixed_curve =
        !matches!(shape.a, Coefficient::Random) && !matches!(shape.b, Coefficient::Random);
    // A fixed (a, b) is one curve per prime, so walk primes; otherwise try
    // several coefficient draws per prime.
    let per_prime = if fixed_curve { 1 } else { 48 };
    let mut tried = 0u64;
    for _ in 0..4096 {
        let mut p = rng.gen_range(lo..hi) | 1;
        let p = loop {
            if p >= hi {
                break None;
            }
            if shape.residue_ok(p) && is_prime_u64(p) {
                break Some(p);
            }
            p += 2;
        };
        let Some(p) = p else { continue };
        let Some(f) = FastField::new(p) else {
            continue;
        };
        for _ in 0..per_prime {
            let (a, b) = (shape.a.value(p, &mut rng), shape.b.value(p, &mut rng));
            let (am, bm) = (f.to_mont(a), f.to_mont(b));
            // 4a³ + 27b² ≠ 0.
            let disc = f.add(
                f.mul(f.to_mont(4), f.mul(f.sqr(am), am)),
                f.mul(f.to_mont(27), f.sqr(bm)),
            );
            if disc == 0 {
                continue;
            }
            tried += 1;
            // The smallest abscissa ≥ 1 with a point lifts P.
            let Some((x, y)) = (1..p.min(1 << 20)).find_map(|x| {
                let xm = f.to_mont(x);
                let v = f.add(f.add(f.mul(f.sqr(xm), xm), f.mul(am, xm)), bm);
                sqrt_mont(&f, v).map(|y| (x, f.from_mont(y)))
            }) else {
                continue;
            };
            let probe = CurveParams {
                name: "certify",
                p: BigUint::from(p),
                a: BigUint::from(a),
                b: BigUint::from(b),
                gx: BigUint::from(x),
                gy: BigUint::from(y),
                n: BigUint::from(u64::MAX >> 2),
                h: 1,
            };
            let Some(fc) = FastCurve::from_params(&probe) else {
                continue;
            };
            let Some(cert) = certify_order(&fc, fc.g, shape.max_cofactor) else {
                continue;
            };
            if cert.group_order == p {
                continue; // anomalous
            }
            let g = fc.lower(fc.scalar_mul(fc.g, cert.cofactor));
            let Point::Affine { x: gx, y: gy } = g else {
                continue;
            };
            let params = CurveParams {
                name: "generated",
                p: BigUint::from(p),
                a: BigUint::from(a),
                b: BigUint::from(b),
                gx: gx.value,
                gy: gy.value,
                n: BigUint::from(cert.subgroup_order),
                h: cert.cofactor as u32,
            };
            let curve = match OrbitCurve::from_params(&params) {
                Ok(c) => c,
                Err(_) => continue,
            };
            let r = curve.r;
            let k = match known_log {
                Some(k) if k == 0 || k >= r => {
                    return Err(format!(
                        "known logarithm must be nonzero and below the subgroup order {r}"
                    ))
                }
                Some(k) => k,
                None => rng.gen_range(1..r),
            };
            let target = curve.mul_g(k);
            return Ok(GeneratedInstance {
                curve,
                certificate: cert,
                known_log: k,
                target,
                curves_tried: tried,
            });
        }
    }
    Err(format!(
        "no {} curve with cofactor ≤ {} certified at {bits} bits within the search budget",
        shape.kind.as_str(),
        shape.max_cofactor
    ))
}

/// A square root in Montgomery form over a bare field, for lifting before
/// an [`OrbitCurve`] exists.  `p ≡ 3 (4)` takes the one-exponentiation
/// shortcut; otherwise Tonelli–Shanks.
fn sqrt_mont(f: &FastField, v: u64) -> Option<u64> {
    if v == 0 {
        return Some(0);
    }
    let p = f.modulus();
    if f.pow(v, (p - 1) / 2) != f.one() {
        return None;
    }
    if p % 4 == 3 {
        return Some(f.pow(v, (p + 1) / 4));
    }
    let (mut q, mut s) = (p - 1, 0u32);
    while q & 1 == 0 {
        q >>= 1;
        s += 1;
    }
    let minus_one = f.neg(f.one());
    let z = (2..p)
        .map(|z| f.to_mont(z))
        .find(|&z| f.pow(z, (p - 1) / 2) == minus_one)?;
    let (mut m, mut c, mut t, mut x) = (s, f.pow(z, q), f.pow(v, q), f.pow(v, q.div_ceil(2)));
    while t != f.one() {
        let (mut i, mut t2) = (0u32, t);
        while t2 != f.one() {
            t2 = f.sqr(t2);
            i += 1;
            if i == m {
                return None;
            }
        }
        let mut b = c;
        for _ in 0..(m - i - 1) {
            b = f.sqr(b);
        }
        m = i;
        c = f.sqr(b);
        t = f.mul(t, c);
        x = f.mul(x, b);
    }
    Some(x)
}

// ── Factor base of automorphism orbits ─────────────────────────────────

/// A factor base that is a union of full `Aut`-orbits of points in `⟨G⟩`,
/// one representative per orbit.  Its `w·m` points carry `m` unknowns.
#[derive(Clone, Debug)]
pub struct OrbitFactorBase {
    pub reps: Vec<FastPoint>,
    /// Every abscissa of every orbit → the orbit's index.
    index: FxMap<u64, u32>,
    /// Abscissae drawn to fill the base (each costs a lift and a cofactor
    /// multiplication).
    pub draws: u64,
}

impl OrbitFactorBase {
    /// Draw `orbits` orbits: a pseudo-random abscissa is lifted to a point,
    /// multiplied by the cofactor into `⟨G⟩`, and its orbit is kept unless
    /// it is already present.  Points with `x = 0` are skipped (on a
    /// `j = 0` curve `ψ` fixes them, so their orbit is not free).  No
    /// discrete logarithm is used.
    pub fn select(c: &OrbitCurve, orbits: usize, seed: u64) -> Self {
        let f = c.fast.f;
        let p = f.modulus();
        let mut rng = StdRng::seed_from_u64(seed ^ 0x6662_6173_655f_6f72);
        let mut reps = Vec::with_capacity(orbits);
        let mut index: FxMap<u64, u32> = FxMap::default();
        index.reserve(orbits * c.xmul.len());
        let mut draws = 0u64;
        let cap = (orbits as u64) * 64 + 4096;
        while reps.len() < orbits && draws < cap {
            draws += 1;
            let x = f.to_mont(rng.gen_range(1..p));
            let Some(y) = c.sqrt(c.rhs(x)) else { continue };
            let mut pt = FastPoint {
                x,
                y,
                infinity: false,
            };
            if c.h != 1 {
                pt = c.fast.scalar_mul(pt, c.h);
            }
            if pt.infinity || pt.x == 0 {
                continue;
            }
            let rep = c
                .aut
                .iter()
                .map(|al| c.apply(al, pt))
                .min_by_key(|q| (q.x, q.y))
                .expect("the identity is in the table");
            if index.contains_key(&rep.x) {
                continue;
            }
            let o = reps.len() as u32;
            for &cx in &c.xmul {
                index.insert(f.mul(cx, rep.x), o);
            }
            reps.push(rep);
        }
        Self { reps, index, draws }
    }

    /// Orbits (unknowns).
    pub fn len(&self) -> usize {
        self.reps.len()
    }
    /// Is the base empty?
    pub fn is_empty(&self) -> bool {
        self.reps.is_empty()
    }

    /// The sub-base of the orbits in `keep`, renumbered in order.
    fn restrict(&self, c: &OrbitCurve, keep: &[usize]) -> Self {
        let f = c.fast.f;
        let reps: Vec<FastPoint> = keep.iter().map(|&o| self.reps[o]).collect();
        let mut index: FxMap<u64, u32> = FxMap::default();
        for (o, rep) in reps.iter().enumerate() {
            for &cx in &c.xmul {
                index.insert(f.mul(cx, rep.x), o as u32);
            }
        }
        Self {
            reps,
            index,
            draws: self.draws,
        }
    }
}

// ── The decomposition oracle ───────────────────────────────────────────

/// `R = Σ coeff·log(rep)`: one or two `(orbit, eigenvalue)` terms.
pub type Terms = Vec<(u32, u64)>;

/// Reused buffers for the sweep.
#[derive(Default)]
struct Sweep {
    den: Vec<u64>,
    scratch: Vec<u64>,
}

/// Decompose `target` as `α(P_o)` or `α(P_o) + β(P_o')` over the orbit
/// base, or `None`.  `ops` is charged one per difference evaluated.
///
/// For each automorphism `α` the sweep forms `α⁻¹(R) − P_o` for every
/// representative, sharing one inversion per [`SWEEP_BLOCK`], and looks
/// the difference up by abscissa; `α⁻¹(R) = P_o + β(P_o')` is
/// `R = α(P_o) + αβ(P_o')`, eigenvalues `e(α)` and `e(α)e(β)`.  The first
/// hit is returned, so a decomposable target costs about `r/(wm)`
/// differences.
///
/// The sweep starts at an automorphism and a representative chosen from
/// the target's coordinates.  That leaves the expected cost alone, but a
/// fixed start would make a wide base's first hit almost always a
/// low-index orbit, piling the relations onto a few columns and leaving
/// others uncovered.
fn decompose(
    c: &OrbitCurve,
    fb: &OrbitFactorBase,
    target: FastPoint,
    sweep: &mut Sweep,
    ops: &mut u64,
) -> Option<Terms> {
    if target.infinity || fb.is_empty() {
        return None;
    }
    let f = &c.fast.f;
    let r = c.r;
    let m = fb.reps.len();
    let w = c.aut.len();
    let find_image = |o: usize, d: FastPoint| -> Option<u64> {
        c.aut
            .iter()
            .find(|be| c.apply(be, fb.reps[o]) == d)
            .map(|be| be.eig)
    };
    let (aut_off, rep_off) = (
        (target.y % w as u64) as usize,
        (target.x % m as u64) as usize,
    );
    for step in 0..w {
        let ai = (aut_off + step) % w;
        let al = &c.aut[ai];
        let ra = c.apply(&c.aut[c.aut_inv[ai]], target);
        // One summand: α⁻¹(R) is itself a representative.
        if let Some(&o) = fb.index.get(&ra.x) {
            if fb.reps[o as usize] == ra {
                return Some(vec![(o, al.eig)]);
            }
        }
        for start in (0..m).step_by(SWEEP_BLOCK) {
            let len = SWEEP_BLOCK.min(m - start);
            let rep_at = |i: usize| (rep_off + start + i) % m;
            sweep.den.clear();
            sweep.den.extend((0..len).map(|i| {
                let d = f.sub(ra.x, fb.reps[rep_at(i)].x);
                // x(R_α) = x(P_o): P_o = ±R_α, handled by the one-summand
                // check or a doubling; 1 keeps the batch invertible.
                if d == 0 {
                    f.one()
                } else {
                    d
                }
            }));
            sweep.scratch.resize(len, 0);
            f.batch_inv(&mut sweep.den, &mut sweep.scratch);
            for i in 0..len {
                let q = &fb.reps[rep_at(i)];
                if q.x == ra.x {
                    continue;
                }
                *ops += 1;
                // D = R_α − P_o = R_α + (−P_o): λ = (y_R + y_o)/(x_R − x_o).
                let lam = f.mul(f.add(ra.y, q.y), sweep.den[i]);
                let xd = f.sub(f.sub(f.sqr(lam), ra.x), q.x);
                let Some(&o2) = fb.index.get(&xd) else {
                    continue;
                };
                let yd = f.sub(f.mul(lam, f.sub(ra.x, xd)), ra.y);
                let d = FastPoint {
                    x: xd,
                    y: yd,
                    infinity: false,
                };
                if let Some(e_beta) = find_image(o2 as usize, d) {
                    let o = rep_at(i) as u32;
                    return Some(vec![(o, al.eig), (o2, mul_r(al.eig, e_beta, r))]);
                }
            }
        }
    }
    None
}

/// Re-add a decomposition in the group: does `Σ terms` equal `target`?
/// Each term's point is recovered as the orbit member with that
/// eigenvalue.
fn verify_terms(c: &OrbitCurve, fb: &OrbitFactorBase, target: FastPoint, terms: &Terms) -> bool {
    let mut sum = FastPoint::INFINITY;
    for &(o, e) in terms {
        let Some(al) = c.aut.iter().find(|al| al.eig == e) else {
            return false;
        };
        sum = c.fast.add(sum, c.apply(al, fb.reps[o as usize]));
    }
    sum == target
}

// ── The two-term relation system ───────────────────────────────────────

/// One relation `Σ coeff·x_orbit ≡ rhs (mod r)` with one or two terms.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Relation {
    pub terms: Terms,
    pub rhs: u64,
}

/// What [`solve_two_term_system`] found, by connected component of the
/// relation graph (orbits are vertices, two-term relations edges).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct TwoTermStats {
    pub components: usize,
    /// Components pinned by a cycle of gain `≠ 1` or a one-term relation.
    pub determined_components: usize,
    /// Components with a contradiction; nonzero means a wrong relation.
    pub inconsistent_components: usize,
    pub solved_columns: usize,
}

/// Solve a system of one- and two-term relations exactly, component by
/// component, returning the logarithm of every column the relations pin.
///
/// A spanning tree of each component expresses every column affinely in
/// its root, `x_u = α_u t + β_u`; every non-tree relation, and every
/// one-term relation, is then an equation `A t = B`.  `A = 0` means a
/// cycle of gain one, which says nothing; otherwise `t` is pinned, and
/// two pins that disagree mark the component inconsistent.  `O(rows + m)`
/// operations and one modular inverse per tree edge.
pub fn solve_two_term_system(
    columns: usize,
    rows: &[Relation],
    r: u64,
) -> (Vec<Option<u64>>, TwoTermStats) {
    let mut adj: Vec<Vec<u32>> = vec![Vec::new(); columns];
    for (i, row) in rows.iter().enumerate() {
        let mut seen = [u32::MAX; 2];
        for (k, &(o, _)) in row.terms.iter().enumerate() {
            if !seen.contains(&o) {
                adj[o as usize].push(i as u32);
            }
            seen[k.min(1)] = o;
        }
    }
    let mut solution = vec![None; columns];
    let mut visited = vec![false; columns];
    let mut alpha = vec![0u64; columns];
    let mut beta = vec![0u64; columns];
    let mut stats = TwoTermStats::default();
    let mut queue: Vec<usize> = Vec::new();
    for root in 0..columns {
        if visited[root] || adj[root].is_empty() {
            continue;
        }
        stats.components += 1;
        visited[root] = true;
        alpha[root] = 1;
        beta[root] = 0;
        queue.clear();
        queue.push(root);
        let mut comp = Vec::new();
        let mut pinned: Option<u64> = None;
        let mut inconsistent = false;
        // `a t = b`: pin the root, or note a contradiction.
        fn pin(a: u64, b: u64, r: u64, pinned: &mut Option<u64>, inconsistent: &mut bool) {
            if a == 0 {
                if b != 0 {
                    *inconsistent = true;
                }
                return;
            }
            let t = mul_r(b, inv_r(a, r).expect("r is prime"), r);
            match pinned {
                None => *pinned = Some(t),
                Some(prev) if *prev != t => *inconsistent = true,
                _ => {}
            }
        }
        let mut head = 0;
        while head < queue.len() {
            let u = queue[head];
            head += 1;
            comp.push(u);
            for &ri in &adj[u] {
                let row = &rows[ri as usize];
                // Merge the terms into (column, coefficient) pairs.
                let mut merged: Vec<(usize, u64)> = Vec::with_capacity(2);
                for &(o, e) in &row.terms {
                    match merged.iter_mut().find(|(c, _)| *c == o as usize) {
                        Some((_, v)) => *v = add_r(*v, e, r),
                        None => merged.push((o as usize, e % r)),
                    }
                }
                merged.retain(|&(_, v)| v != 0);
                match merged.as_slice() {
                    [] => {
                        if !row.rhs.is_multiple_of(r) {
                            inconsistent = true;
                        }
                    }
                    [(o, cu)] => {
                        // cu (α t + β) = rhs.
                        let (a, b) = (
                            mul_r(*cu, alpha[*o], r),
                            sub_r(row.rhs, mul_r(*cu, beta[*o], r), r),
                        );
                        pin(a, b, r, &mut pinned, &mut inconsistent);
                    }
                    [(o1, c1), (o2, c2)] => {
                        let (known, cu, other, cw) = if *o1 == u {
                            (*o1, *c1, *o2, *c2)
                        } else {
                            (*o2, *c2, *o1, *c1)
                        };
                        if !visited[other] {
                            // x_w = (rhs − cu x_u) / cw.
                            let inv = inv_r(cw, r).expect("r is prime");
                            visited[other] = true;
                            alpha[other] = mul_r(r - mul_r(cu, alpha[known], r) % r, inv, r);
                            beta[other] =
                                mul_r(sub_r(row.rhs, mul_r(cu, beta[known], r), r), inv, r);
                            queue.push(other);
                        } else {
                            let a =
                                add_r(mul_r(cu, alpha[known], r), mul_r(cw, alpha[other], r), r);
                            let b = sub_r(
                                row.rhs,
                                add_r(mul_r(cu, beta[known], r), mul_r(cw, beta[other], r), r),
                                r,
                            );
                            pin(a, b, r, &mut pinned, &mut inconsistent);
                        }
                    }
                    _ => unreachable!("relations have at most two terms"),
                }
            }
        }
        if inconsistent {
            stats.inconsistent_components += 1;
            continue;
        }
        if let Some(t) = pinned {
            stats.determined_components += 1;
            for &u in &comp {
                solution[u] = Some(add_r(mul_r(alpha[u], t, r), beta[u], r));
                stats.solved_columns += 1;
            }
        }
    }
    (solution, stats)
}

// ── Logarithms, descent, and the rho baseline ──────────────────────────

/// Knobs for [`run_known_answer`].  Zeros size themselves.
#[derive(Clone, Copy, Debug)]
pub struct OrbitIcOptions {
    /// Orbits in the factor base; 0 → `⌈c·√r / w⌉` with `c = width`.
    pub orbits: usize,
    /// Base width in units of `√r / w` when `orbits` is 0.  At width `c`
    /// a descent costs about `√r / c` differences.
    pub width: f64,
    /// Relations collected per orbit before the logarithms are solved.
    pub relations_per_orbit: f64,
    /// Oracle-operation bound for the logarithm precomputation.  A probe
    /// costs up to `w·m` operations, so this, not a probe count, is what
    /// bounds the running time.
    pub max_ops: u64,
    /// Oracle-operation bound for one descent.
    pub max_descent_ops: u64,
    /// Rho walk-step bound; 0 → `64·√r`.
    pub rho_max_steps: u64,
    /// Skip the rho baseline.
    pub skip_rho: bool,
    pub seed: u64,
}

impl Default for OrbitIcOptions {
    fn default() -> Self {
        Self {
            orbits: 0,
            width: 2.0,
            relations_per_orbit: 1.5,
            max_ops: 1 << 32,
            max_descent_ops: 1 << 30,
            rho_max_steps: 0,
            skip_rho: false,
            seed: 1,
        }
    }
}

/// The logarithm precomputation.
#[derive(Clone, Debug, Default)]
pub struct LogsReport {
    pub orbits: usize,
    pub points: usize,
    pub factor_base_draws: u64,
    pub trials: u64,
    pub relations: usize,
    /// Relations whose re-addition in the group failed; must be zero.
    pub rejected_relations: u64,
    /// Differences the oracle evaluated.
    pub oracle_ops: u64,
    /// Group additions spent advancing probes.
    pub probe_ops: u64,
    pub system: TwoTermStats,
    /// Columns whose solved logarithm satisfied `[x]G == P`.
    pub certified_columns: usize,
    /// Solved columns that failed that check; must be zero.
    pub uncertified_columns: usize,
    pub seconds: f64,
}

/// One target's descent.
#[derive(Clone, Debug, Default)]
pub struct DescentReport {
    pub trials: u64,
    pub oracle_ops: u64,
    pub probe_ops: u64,
    pub recovered: Option<u64>,
    pub verified: bool,
    pub seconds: f64,
}

/// The rho baseline.
#[derive(Clone, Debug, Default)]
pub struct RhoReport {
    pub walks: usize,
    pub dp_bits: u32,
    /// Walk steps (group additions).
    pub steps: u64,
    /// Group operations seeding the walks (and reseeding one after a
    /// degenerate collision), charged by [`scalar_mul_ops`].  The shared
    /// jump table is charged once, in
    /// [`OrbitIcReport::rho_precompute_ops`].
    pub setup_ops: u64,
    pub distinguished_points: u64,
    pub recovered: Option<u64>,
    pub verified: bool,
    /// `√(π r / 2)`, the expected steps of this (unfolded) walk.
    pub expected_steps: f64,
    /// `√(π r / 2) / √w`, the expectation for a walk folded by `Aut`.
    pub expected_steps_folded: f64,
    pub seconds: f64,
}

/// Index calculus against rho on a batch of known-answer targets sharing
/// one logarithm database.
#[derive(Clone, Debug, Default)]
pub struct OrbitIcReport {
    pub automorphism_order: usize,
    pub logs: LogsReport,
    /// One per target, in order.
    pub descents: Vec<DescentReport>,
    /// One per target, in order; empty when rho was skipped.
    pub rhos: Vec<RhoReport>,
    /// Group operations building rho's shared jump table, the rho side's
    /// target-independent precomputation.
    pub rho_precompute_ops: u64,
}

impl OrbitIcReport {
    /// Group operations the logarithm database cost.
    pub fn precompute_ops(&self) -> u64 {
        self.logs.oracle_ops + self.logs.probe_ops
    }
    /// Group operations one descent cost.
    pub fn descent_ops(d: &DescentReport) -> u64 {
        d.oracle_ops + d.probe_ops
    }
    pub fn descent_ops_total(&self) -> u64 {
        self.descents.iter().map(Self::descent_ops).sum()
    }
    /// Rho group operations over every target, walk steps plus seeding;
    /// the shared jump table is [`Self::rho_precompute_ops`].
    pub fn rho_ops_total(&self) -> u64 {
        self.rhos.iter().map(|r| r.steps + r.setup_ops).sum()
    }
    pub fn descents_verified(&self) -> usize {
        self.descents.iter().filter(|d| d.verified).count()
    }
    pub fn rhos_verified(&self) -> usize {
        self.rhos.iter().filter(|r| r.verified).count()
    }
    /// Mean group operations per descent: the charged, per-target cost.
    pub fn mean_descent_ops(&self) -> f64 {
        self.descent_ops_total() as f64 / self.descents.len().max(1) as f64
    }
    /// Mean rho group operations per target, walk steps plus seeding.
    pub fn mean_rho_ops(&self) -> f64 {
        self.rho_ops_total() as f64 / self.rhos.len().max(1) as f64
    }
}

/// What one scalar multiplication is charged, in group operations: the
/// `⌈1.5 · bits(r)⌉` doublings and additions of double-and-add.  Setup
/// multiplications are charged at this rate on both sides of the
/// comparison; the `[d]G == Q` and `[x]G == P` certification checks are
/// charged to neither.
pub fn scalar_mul_ops(r: u64) -> u64 {
    let bits = u64::from(64 - r.leading_zeros());
    (3 * bits).div_ceil(2)
}

/// Probe walk `R_t = [a_t]G + [b]Q` with `a_{t+1} = a_t + s`: one group
/// addition a probe.
struct ProbeWalk {
    point: FastPoint,
    a: u64,
    step: FastPoint,
    s: u64,
}

impl ProbeWalk {
    fn new(c: &OrbitCurve, rng: &mut StdRng, offset: FastPoint) -> Self {
        let a = rng.gen_range(1..c.r);
        let s = rng.gen_range(1..c.r);
        Self {
            point: c.fast.add(c.mul_g(a), offset),
            a,
            step: c.mul_g(s),
            s,
        }
    }
    fn advance(&mut self, c: &OrbitCurve) {
        self.point = c.fast.add(self.point, self.step);
        self.a = add_r(self.a, self.s, c.r);
    }
}

/// The factor-base logarithm database: relations `R = [a]G`, solved by
/// [`solve_two_term_system`], every column certified.  Returns the base
/// restricted to the certified orbits and their logarithms.
pub fn solve_logs(
    c: &OrbitCurve,
    fb: &OrbitFactorBase,
    opts: &OrbitIcOptions,
) -> (OrbitFactorBase, Vec<u64>, LogsReport) {
    let begin = Instant::now();
    let mut rep = LogsReport {
        orbits: fb.len(),
        points: fb.len() * c.automorphism_order(),
        factor_base_draws: fb.draws,
        ..LogsReport::default()
    };
    let want = ((fb.len() as f64) * opts.relations_per_orbit).ceil() as usize;
    let mut rng = StdRng::seed_from_u64(opts.seed ^ 0x6c6f_6773_5f70_7262);
    let mut walk = ProbeWalk::new(c, &mut rng, FastPoint::INFINITY);
    rep.probe_ops += 2 * scalar_mul_ops(c.r) + 1;
    let mut rows: Vec<Relation> = Vec::with_capacity(want);
    let mut sweep = Sweep::default();
    while rows.len() < want && rep.oracle_ops < opts.max_ops {
        rep.trials += 1;
        if let Some(terms) = decompose(c, fb, walk.point, &mut sweep, &mut rep.oracle_ops) {
            if verify_terms(c, fb, walk.point, &terms) {
                rows.push(Relation { terms, rhs: walk.a });
            } else {
                rep.rejected_relations += 1;
            }
        }
        walk.advance(c);
        rep.probe_ops += 1;
    }
    rep.relations = rows.len();
    let (solution, stats) = solve_two_term_system(fb.len(), &rows, c.r);
    rep.system = stats;
    let mut keep = Vec::new();
    let mut logs = Vec::new();
    for (o, x) in solution.iter().enumerate() {
        if let Some(x) = *x {
            if c.mul_g(x) == fb.reps[o] {
                keep.push(o);
                logs.push(x);
            } else {
                rep.uncertified_columns += 1;
            }
        }
    }
    rep.certified_columns = keep.len();
    rep.seconds = begin.elapsed().as_secs_f64();
    (fb.restrict(c, &keep), logs, rep)
}

/// Recover `log_G Q` from one decomposition of `R = [a]G + [b]Q` over the
/// certified base, and check it as `[d]G == Q`.
pub fn descend(
    c: &OrbitCurve,
    fb: &OrbitFactorBase,
    logs: &[u64],
    q: FastPoint,
    opts: &OrbitIcOptions,
) -> DescentReport {
    let begin = Instant::now();
    let r = c.r;
    let mut rep = DescentReport::default();
    let mut rng = StdRng::seed_from_u64(opts.seed ^ 0x6465_7363_656e_7400);
    let b = rng.gen_range(1..r);
    let b_inv = inv_r(b, r).expect("r is prime");
    let mut walk = ProbeWalk::new(c, &mut rng, c.fast.scalar_mul(q, b));
    rep.probe_ops += 3 * scalar_mul_ops(r) + 1;
    let mut sweep = Sweep::default();
    while rep.oracle_ops < opts.max_descent_ops && !fb.is_empty() {
        rep.trials += 1;
        if let Some(terms) = decompose(c, fb, walk.point, &mut sweep, &mut rep.oracle_ops) {
            if verify_terms(c, fb, walk.point, &terms) {
                // a + b·d ≡ Σ e·x  ⇒  d = (Σ e·x − a) / b.
                let sum = terms.iter().fold(0u64, |acc, &(o, e)| {
                    add_r(acc, mul_r(e, logs[o as usize], r), r)
                });
                let d = mul_r(sub_r(sum, walk.a, r), b_inv, r);
                rep.recovered = Some(d);
                rep.verified = c.mul_g(d) == q;
                break;
            }
        }
        walk.advance(c);
        rep.probe_ops += 1;
    }
    rep.seconds = begin.elapsed().as_secs_f64();
    rep
}

/// A 32-way r-adding walk's partition index for an abscissa.
#[inline]
fn partition(x: u64) -> usize {
    (x.wrapping_mul(0x9E37_79B9_7F4A_7C15) >> 59) as usize
}
#[inline]
fn distinguished(x: u64, dp_bits: u32) -> bool {
    dp_bits == 0 || (x.wrapping_mul(0xC2B2_AE3D_27D4_EB4F) >> (64 - dp_bits)) == 0
}

/// The r-adding walk's jump table: 32 multiples `[c_j]G`.  It does not
/// depend on the target, so one table serves every target, as one
/// logarithm database does on the index-calculus side, and its cost is
/// charged once.
pub struct RhoJumps {
    jumps: Vec<(FastPoint, u64)>,
    /// Group operations building the table.
    pub ops: u64,
}

impl RhoJumps {
    pub fn new(c: &OrbitCurve, seed: u64) -> Self {
        let mut rng = StdRng::seed_from_u64(seed ^ 0x6a75_6d70_5f74_6162);
        let jumps: Vec<(FastPoint, u64)> = (0..32)
            .map(|_| {
                let u = rng.gen_range(1..c.r);
                (c.mul_g(u), u)
            })
            .collect();
        let ops = jumps.len() as u64 * scalar_mul_ops(c.r);
        Self { jumps, ops }
    }
}

/// Distinguished-point Pollard rho for `Q = [d]G` (van Oorschot–Wiener).
///
/// Each walk starts at `[a]G + [b]Q` with its own random `b` and steps by
/// the shared `[c_j]G`, so `b` is constant along it and a collision of two
/// walks solves for `d`.  The walks advance together sharing one inversion
/// per step; a walk reports each point whose hash has `dp_bits` leading
/// zeros and walks on, and two reports of one abscissa solve for `d`,
/// checked as `[d]G == Q`.  A walk is reseeded only after a degenerate
/// collision (with itself) or `32 · 2^dp_bits` steps without a report.
///
/// The walk count is sized to the instance — `≈ √r / 1024`, 4 to 32 — so
/// that seeding the walks stays near a tenth of the expected steps rather
/// than swamping them on a small curve, and `dp_bits` keeps the detection
/// lag, `walks · 2^dp_bits`, near `√r / 32`.  The walk is not folded by
/// `Aut`.
pub fn rho_baseline(
    c: &OrbitCurve,
    table: &RhoJumps,
    q: FastPoint,
    seed: u64,
    max_steps: u64,
) -> RhoReport {
    let begin = Instant::now();
    let r = c.r;
    let f = c.fast.f;
    let rf = r as f64;
    let expected = (std::f64::consts::PI * rf / 2.0).sqrt();
    let walks = ((expected / 1024.0).round() as usize).clamp(4, 32);
    let dp_bits = ((expected / (walks as f64 * 32.0)).max(1.0).log2().floor() as u32).min(24);
    let mut rep = RhoReport {
        walks,
        dp_bits,
        expected_steps: expected,
        expected_steps_folded: expected / (c.automorphism_order() as f64).sqrt(),
        ..RhoReport::default()
    };
    // [a]G + [b]Q costs two scalar multiplications and an addition.
    let seed_ops = 2 * scalar_mul_ops(r) + 1;
    let mut rng = StdRng::seed_from_u64(seed ^ 0x7268_6f5f_6261_7365);
    let jumps = &table.jumps;
    let fresh = |rng: &mut StdRng| {
        let (a, b) = (rng.gen_range(0..r), rng.gen_range(1..r));
        (c.fast.add(c.mul_g(a), c.fast.scalar_mul(q, b)), a, b)
    };
    let mut state: Vec<(FastPoint, u64, u64)> = (0..walks).map(|_| fresh(&mut rng)).collect();
    rep.setup_ops = walks as u64 * seed_ops;
    let mut since_report = vec![0u64; walks];
    let stall = 32u64 << dp_bits;
    let mut seen: FxMap<u64, (u64, u64, u64)> = FxMap::default();
    let max_steps = if max_steps == 0 {
        (64.0 * expected) as u64 + 1_000_000
    } else {
        max_steps
    };
    let (mut den, mut scratch) = (vec![0u64; walks], vec![0u64; walks]);
    'walk: while rep.steps < max_steps {
        // Classify: an ordinary addition, or a special case finished alone.
        for (k, (pt, _, _)) in state.iter().enumerate() {
            let jp = jumps[partition(pt.x)].0;
            den[k] = if pt.infinity || jp.infinity || pt.x == jp.x {
                f.one()
            } else {
                f.sub(jp.x, pt.x)
            };
        }
        f.batch_inv(&mut den, &mut scratch);
        for k in 0..walks {
            let (pt, a, b) = state[k];
            let (jp, u) = jumps[partition(pt.x)];
            let next = if pt.infinity || jp.infinity || pt.x == jp.x {
                c.fast.add(pt, jp)
            } else {
                let lam = f.mul(f.sub(jp.y, pt.y), den[k]);
                let x3 = f.sub(f.sub(f.sqr(lam), pt.x), jp.x);
                FastPoint {
                    x: x3,
                    y: f.sub(f.mul(lam, f.sub(pt.x, x3)), pt.y),
                    infinity: false,
                }
            };
            state[k] = (next, add_r(a, u, r), b);
            rep.steps += 1;
            since_report[k] += 1;
            let (pt, a, b) = state[k];
            let reseed = if pt.infinity || since_report[k] > stall {
                true
            } else if !distinguished(pt.x, dp_bits) {
                false
            } else {
                rep.distinguished_points += 1;
                since_report[k] = 0;
                match seen.get(&pt.x) {
                    Some(&(a2, b2, y2)) => {
                        // Same abscissa: P = ±P', so a + bd ≡ ±(a2 + b2 d).
                        let (num, den_b) = if pt.y == y2 {
                            (sub_r(a2, a, r), sub_r(b, b2, r))
                        } else {
                            (r - add_r(a, a2, r) % r, add_r(b, b2, r))
                        };
                        if let Some(inv) = inv_r(den_b, r) {
                            let d = mul_r(num % r, inv, r);
                            if c.mul_g(d) == q {
                                rep.recovered = Some(d);
                                rep.verified = true;
                                break 'walk;
                            }
                        }
                        // Degenerate (the walk met itself, so b = b2): it
                        // is on a cycle it cannot leave, so it is spent.
                        true
                    }
                    None => {
                        seen.insert(pt.x, (a, b, pt.y));
                        false
                    }
                }
            };
            if reseed {
                state[k] = fresh(&mut rng);
                since_report[k] = 0;
                rep.setup_ops += seed_ops;
            }
        }
    }
    rep.seconds = begin.elapsed().as_secs_f64();
    rep
}

/// The auto-sized orbit count: `⌈width · √r / w⌉`, at least 8.
pub fn auto_orbits(c: &OrbitCurve, width: f64) -> usize {
    let w = c.automorphism_order() as f64;
    ((width * (c.r as f64).sqrt() / w).ceil() as usize).max(8)
}

/// Select the base, precompute its logarithms once, then descend every
/// target against that database and run the rho baseline on each: the
/// whole known-answer experiment.  Target `i` seeds its descent and its
/// rho walk with `seed + i`.
pub fn run_known_answer(
    c: &OrbitCurve,
    targets: &[FastPoint],
    opts: &OrbitIcOptions,
) -> OrbitIcReport {
    let orbits = if opts.orbits == 0 {
        auto_orbits(c, opts.width)
    } else {
        opts.orbits
    };
    let fb = OrbitFactorBase::select(c, orbits, opts.seed);
    let (solved, logs, logs_report) = solve_logs(c, &fb, opts);
    let per_target = |i: usize| OrbitIcOptions {
        seed: opts.seed.wrapping_add(i as u64),
        ..*opts
    };
    let descents = targets
        .iter()
        .enumerate()
        .map(|(i, &q)| descend(c, &solved, &logs, q, &per_target(i)))
        .collect();
    let (rhos, rho_precompute_ops) = if opts.skip_rho {
        (Vec::new(), 0)
    } else {
        let table = RhoJumps::new(c, opts.seed);
        let rhos = targets
            .iter()
            .enumerate()
            .map(|(i, &q)| rho_baseline(c, &table, q, per_target(i).seed, opts.rho_max_steps))
            .collect();
        (rhos, table.ops)
    };
    OrbitIcReport {
        automorphism_order: c.automorphism_order(),
        logs: logs_report,
        descents,
        rhos,
        rho_precompute_ops,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::j0_twists::naive_point_count;

    fn instance(kind: CurveKind, bits: u32, seed: u64) -> GeneratedInstance {
        generate_instance(ScaledShape::of_kind(kind), bits, None, seed).unwrap()
    }

    #[test]
    fn primality_agrees_with_trial_division() {
        for n in 0u64..3000 {
            let naive = n >= 2 && (2..n).all(|d| !n.is_multiple_of(d));
            assert_eq!(is_prime_u64(n), naive, "{n}");
        }
        assert!(is_prime_u64((1u64 << 61) - 1));
        assert!(!is_prime_u64(((1u64 << 31) - 1) * ((1u64 << 31) - 1)));
    }

    #[test]
    fn square_roots_mod_r() {
        for r in [13u64, 17, 97, 65537, 1_000_000_007] {
            for a in 1..200u64 {
                if let Some(s) = sqrt_r(a, r) {
                    assert_eq!(mul_r(s, s, r), a % r, "r={r} a={a}");
                }
            }
        }
    }

    #[test]
    fn certified_orders_match_a_direct_count() {
        for kind in [CurveKind::Generic, CurveKind::J0, CurveKind::J1728] {
            for seed in 0..4 {
                let inst = instance(kind, 14, seed);
                let params = inst.curve.params("t");
                let direct = naive_point_count(&params.p, &params.a, &params.b);
                assert_eq!(
                    direct,
                    BigUint::from(inst.certificate.group_order),
                    "{kind:?} seed {seed}"
                );
                assert_eq!(
                    inst.certificate.cofactor * inst.certificate.subgroup_order,
                    inst.certificate.group_order
                );
            }
        }
    }

    #[test]
    fn automorphism_tables_by_type() {
        let g = instance(CurveKind::Generic, 20, 1);
        assert_eq!(g.curve.automorphism_order(), 2);
        let j0 = instance(CurveKind::J0, 20, 1);
        assert_eq!(j0.curve.automorphism_order(), 6);
        assert_eq!(j0.curve.xmul.len(), 3);
        let j1728 = instance(CurveKind::J1728, 20, 1);
        assert_eq!(j1728.curve.automorphism_order(), 4);
        assert_eq!(j1728.curve.xmul.len(), 2);
        assert!(j1728.certificate.cofactor >= 2);
        // Every eigenvalue acts on a random subgroup point, not only on G.
        for inst in [&g, &j0, &j1728] {
            let c = &inst.curve;
            let pt = c.mul_g(123_457);
            for al in &c.aut {
                assert_eq!(c.apply(al, pt), c.fast.scalar_mul(pt, al.eig));
            }
            // The GLV relation on j = 0 and μ² ≡ −1 on j = 1728.
            if c.kind == CurveKind::J0 {
                let l = c.aut[1].eig;
                assert_eq!(add_r(add_r(mul_r(l, l, c.r), l, c.r), 1, c.r), 0);
            }
            if c.kind == CurveKind::J1728 {
                let m = c.aut[1].eig;
                assert_eq!(mul_r(m, m, c.r), c.r - 1);
            }
        }
    }

    #[test]
    fn shapes_keep_the_deployed_coefficients() {
        let s = ScaledShape::of_curve(&CurveParams::secp256k1());
        assert_eq!(s.kind, CurveKind::J0);
        assert_eq!(s.b, Coefficient::Fixed(7));
        let p = ScaledShape::of_curve(&CurveParams::p224());
        assert_eq!(p.kind, CurveKind::Generic);
        assert_eq!(p.a, Coefficient::Fixed(-3));
        assert_eq!(p.b, Coefficient::Random);
        let bp = ScaledShape::of_curve(&CurveParams::brainpool_p256r1());
        assert_eq!((bp.a, bp.b), (Coefficient::Random, Coefficient::Random));
        // The scaled secp256k1 really is y² = x³ + 7 with |Aut| = 6.
        let inst = generate_instance(s, 20, None, 3).unwrap();
        let params = inst.curve.params("t");
        assert_eq!(params.a, BigUint::from(0u32));
        assert_eq!(params.b, BigUint::from(7u32));
        assert_eq!(inst.curve.automorphism_order(), 6);
        let inst = generate_instance(p, 20, None, 3).unwrap();
        let params = inst.curve.params("t");
        assert_eq!(&params.p - &params.a, BigUint::from(3u32));
    }

    #[test]
    fn factor_base_is_orbits_of_subgroup_points() {
        let inst = instance(CurveKind::J0, 20, 2);
        let c = &inst.curve;
        let fb = OrbitFactorBase::select(c, 64, 9);
        assert_eq!(fb.len(), 64);
        let params = c.params("t");
        for rep in &fb.reps {
            let pt = c.fast.lower(*rep);
            assert!(params.is_on_curve(&pt));
            assert!(c.fast.scalar_mul(*rep, c.r).infinity, "not in <G>");
            // Every abscissa of the orbit indexes back to it.
            for al in &c.aut {
                let img = c.apply(al, *rep);
                let o = fb.index[&img.x] as usize;
                assert_eq!(fb.reps[o], *rep);
            }
        }
        // Representatives are distinct orbits.
        let xs: std::collections::HashSet<_> = fb.reps.iter().map(|p| p.x).collect();
        assert_eq!(xs.len(), fb.len());
    }

    #[test]
    fn every_decomposition_re_adds_in_the_group() {
        for kind in [CurveKind::Generic, CurveKind::J0, CurveKind::J1728] {
            let inst = instance(kind, 18, 4);
            let c = &inst.curve;
            let fb = OrbitFactorBase::select(c, auto_orbits(c, 2.0), 5);
            let mut sweep = Sweep::default();
            let (mut ops, mut hits) = (0u64, 0);
            for k in 1..400u64 {
                let target = c.mul_g(k.wrapping_mul(0x9E37_79B9) % c.r);
                if let Some(terms) = decompose(c, &fb, target, &mut sweep, &mut ops) {
                    hits += 1;
                    assert!(verify_terms(c, &fb, target, &terms), "{kind:?}");
                }
            }
            assert!(hits > 50, "{kind:?}: only {hits} of 399 decomposed");
        }
    }

    #[test]
    fn two_term_solver_recovers_a_planted_solution() {
        let r = 1_000_003u64;
        let mut rng = StdRng::seed_from_u64(11);
        let m = 400;
        let x: Vec<u64> = (0..m).map(|_| rng.gen_range(0..r)).collect();
        let mut rows = Vec::new();
        for _ in 0..(3 * m / 2) {
            let (o1, o2) = (rng.gen_range(0..m), rng.gen_range(0..m));
            let (c1, c2) = (rng.gen_range(1..r), rng.gen_range(1..r));
            let rhs = add_r(mul_r(c1, x[o1], r), mul_r(c2, x[o2], r), r);
            rows.push(Relation {
                terms: vec![(o1 as u32, c1), (o2 as u32, c2)],
                rhs,
            });
        }
        let (sol, stats) = solve_two_term_system(m, &rows, r);
        assert_eq!(stats.inconsistent_components, 0);
        assert!(stats.solved_columns > m * 8 / 10, "{stats:?}");
        for (o, v) in sol.iter().enumerate() {
            if let Some(v) = v {
                assert_eq!(*v, x[o], "column {o}");
            }
        }
        // A contradiction is caught, not solved around.
        let mut bad = rows.clone();
        bad[0].rhs = add_r(bad[0].rhs, 1, r);
        let (_, stats) = solve_two_term_system(m, &bad, r);
        assert!(stats.inconsistent_components >= 1);
    }

    #[test]
    fn gain_one_cycles_do_not_pin_a_component() {
        // x0 + x1 ≡ 5 and x0 + x1 ≡ 5 again: a doubled edge of gain one.
        let r = 101u64;
        let rows = vec![
            Relation {
                terms: vec![(0, 1), (1, 1)],
                rhs: 5,
            },
            Relation {
                terms: vec![(0, 1), (1, 1)],
                rhs: 5,
            },
        ];
        let (sol, stats) = solve_two_term_system(2, &rows, r);
        assert_eq!(stats.determined_components, 0);
        assert!(sol.iter().all(Option::is_none));
        // x0 − x1 ≡ 2 alongside pins both: 2 x0 ≡ 7.
        let mut rows = rows;
        rows.push(Relation {
            terms: vec![(0, 1), (1, r - 1)],
            rhs: 2,
        });
        let (sol, _) = solve_two_term_system(2, &rows, r);
        let x0 = mul_r(7, inv_r(2, r).unwrap(), r);
        assert_eq!(sol[0], Some(x0));
        assert_eq!(sol[1], Some(sub_r(5, x0, r)));
    }

    #[test]
    fn known_answer_runs_for_every_type() {
        for kind in [CurveKind::Generic, CurveKind::J0, CurveKind::J1728] {
            let inst = instance(kind, 20, 6);
            let targets = inst.targets(4, 1);
            assert_eq!(targets[0], (inst.known_log, inst.target));
            let points: Vec<FastPoint> = targets.iter().map(|&(_, q)| q).collect();
            let rep = run_known_answer(&inst.curve, &points, &OrbitIcOptions::default());
            assert_eq!(rep.logs.rejected_relations, 0, "{kind:?}");
            assert_eq!(rep.logs.uncertified_columns, 0, "{kind:?}");
            assert_eq!(rep.logs.system.inconsistent_components, 0, "{kind:?}");
            assert!(
                rep.logs.certified_columns > rep.logs.orbits * 3 / 4,
                "{kind:?}"
            );
            assert_eq!(rep.descents_verified(), targets.len(), "{kind:?}");
            assert_eq!(rep.rhos_verified(), targets.len(), "{kind:?}");
            for (i, &(k, _)) in targets.iter().enumerate() {
                assert_eq!(rep.descents[i].recovered, Some(k), "{kind:?} target {i}");
                assert_eq!(rep.rhos[i].recovered, Some(k), "{kind:?} target {i}");
            }
        }
    }

    #[test]
    fn the_extra_automorphisms_multiply_the_yield() {
        // Same j = 0 curve, same number of unknowns: the full μ₆ orbits
        // against the {±1} control.  Coverage scales as (w·m)², so the
        // yield per probe should rise by about (6/2)² = 9, a little less
        // as the full base starts to saturate (≈ 8.7 here).  256 orbits
        // give the control about 56 hits in 6000 probes, so the ratio is
        // known to about ±1.2 and both bounds sit near three sigma.
        let inst = instance(CurveKind::J0, 24, 8);
        let full = &inst.curve;
        let control = full.negation_only();
        let m = 256;
        let yield_of = |c: &OrbitCurve| {
            let fb = OrbitFactorBase::select(c, m, 3);
            let mut sweep = Sweep::default();
            let mut ops = 0u64;
            (1..6000u64)
                .filter(|k| {
                    let t = c.mul_g(k.wrapping_mul(0x2545_F491_4F6C_DD1D) % c.r);
                    decompose(c, &fb, t, &mut sweep, &mut ops).is_some()
                })
                .count()
        };
        let (y_full, y_control) = (yield_of(full), yield_of(&control));
        assert!(
            y_control > 20,
            "control yield {y_control} is too small to compare"
        );
        let ratio = y_full as f64 / y_control as f64;
        assert!(
            (5.0..13.0).contains(&ratio),
            "μ₆ orbits yield {y_full}, the ±1 control {y_control}: ratio {ratio:.2}"
        );
    }

    #[test]
    fn a_wide_base_still_covers_its_orbits() {
        // At width 8 every probe decomposes many ways.  With a fixed sweep
        // start the first hit is nearly always a low-index orbit, and on a
        // 28-bit j = 0 curve one column in six went uncovered (84%
        // certified); the rotated start keeps the certified fraction where
        // a random relation graph puts it, about 94%.
        let inst = instance(CurveKind::J0, 24, 5);
        let opts = OrbitIcOptions {
            width: 8.0,
            skip_rho: true,
            ..OrbitIcOptions::default()
        };
        let rep = run_known_answer(&inst.curve, &[inst.target], &opts);
        let frac = rep.logs.certified_columns as f64 / rep.logs.orbits as f64;
        assert!(frac > 0.88, "certified fraction {frac:.3} at width 8");
        assert_eq!(rep.descents_verified(), 1);
    }

    #[test]
    fn runs_are_reproducible_from_the_seed() {
        let inst = instance(CurveKind::Generic, 20, 9);
        let again = instance(CurveKind::Generic, 20, 9);
        assert_eq!(inst.curve.params("t").b, again.curve.params("t").b);
        assert_eq!(inst.known_log, again.known_log);
        let points: Vec<FastPoint> = inst.targets(3, 2).iter().map(|&(_, q)| q).collect();
        let a = run_known_answer(&inst.curve, &points, &OrbitIcOptions::default());
        let b = run_known_answer(&again.curve, &points, &OrbitIcOptions::default());
        assert_eq!(a.precompute_ops(), b.precompute_ops());
        assert_eq!(a.descent_ops_total(), b.descent_ops_total());
        assert_eq!(a.rho_ops_total(), b.rho_ops_total());
    }

    #[test]
    fn the_scaled_view_matches_the_reference_arithmetic() {
        let inst = instance(CurveKind::J0, 16, 2);
        let s = inst.scaled();
        assert!(s.curve.is_on_curve(&s.generator));
        assert_eq!(
            s.generator.scalar_mul(&s.known_log, &s.curve.a_fe()),
            s.target
        );
    }
}
