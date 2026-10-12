//! **Partial-decomposition residual walks** — does a collision search
//! over *decompositions* generate index-calculus relations more cheaply
//! than a collision search over *points*?
//!
//! # Finding points versus finding relations
//!
//! Let `Q = dG` in a subgroup of prime order `n` with factor base
//! `F = {P_0, …, P_{B−1}}` and `ℓ_i = log_G P_i`.  An index-calculus
//! *relation* is an equation
//!
//! ```text
//!   aG + bQ = Σ_i c_i P_i      ⟺      a + b·d ≡ Σ_i c_i ℓ_i   (mod n),
//! ```
//!
//! and `d` falls out once enough independent relations are known.  A
//! random walk is very good at finding *points* with a property — for
//! instance points that happen to lie in `F` — but a factor base only
//! helps if independently chosen targets *decompose* over it, which is
//! a different question.  This module tests the hybrid suggested by that
//! distinction: walk through a space of *partial* decompositions and
//! collide their leftovers.
//!
//! A state `s = (a, b, i_1, …, i_k)` evaluates to the residual
//!
//! ```text
//!   L(s) = aG + bQ − Σ_j P_{i_j}.
//! ```
//!
//! Two states with `L(s) = L(s')` give
//!
//! ```text
//!   (a − a')G + (b − b')Q = Σ_j P_{i_j} − Σ_j P_{i'_j},
//! ```
//!
//! a relation entirely over `F`: the leftover cancels, exactly as in the
//! large-prime variation of index calculus.  A residual that itself
//! lands in `±F ∪ {O}` is a complete decomposition.
//!
//! # Strategies
//!
//! All strategies share one factor base, one group-operation counter,
//! one exact hash table keyed on the affine residual, one relation
//! verifier (every relation is re-checked by scalar multiplication
//! before it is accepted) and one incremental rank tracker over
//! `ℤ/nℤ`, so that "work per useful relation" and "work to recover `d`"
//! are measured on the same footing.
//!
//! | tag | [`Strategy`]             | state space                | next residual costs            | collision-preserving |
//! |-----|--------------------------|----------------------------|--------------------------------|----------------------|
//! | A   | `IndependentSamples`     | random `(a, b, k-tuple)`   | 2 scalar mults + `k` adds      | no                   |
//! | B   | `LocalMutationWalk`      | mutate one slot at a time  | 1–2 adds                       | no                   |
//! | C1  | `RAddingResidualWalk`    | `L ← L + α_jG + β_jQ − P_j`| 1 add                          | yes                  |
//! | C2  | `FreshHashWalk`          | `s_{t+1} = H(L(s_t))`      | 2 scalar mults + `k` adds      | yes                  |
//! | R   | `PlainRho`               | `L ← L + α_jG + β_jQ`      | 1 add                          | yes (reference)      |
//!
//! *Collision-preserving* means that equal residuals lead to equal
//! successors, which is what makes distinguished-point storage (and
//! hence low memory) legitimate.  Note the corollary: after two walks
//! merge, a memoryless walk (C2) carries identical states, so the
//! relation lives only at the merge point and must be recovered by
//! replaying both walks from their starts; C1 and R keep their
//! coefficient history and replay for the same reason.  Strategies A and B are not; for them
//! `filter_bound` implements the "reject residuals outside a small set"
//! idea so its cost can be measured directly.
//!
//! # What the cost model predicts
//!
//! If residuals behave like uniform points in the subgroup, `T` stored
//! residuals produce `≈ T²/(2n)` collisions, so `R` relations need
//! `T ≈ √(2nR)` residuals.  Recovering `d` needs `R ≈ B + 1` independent
//! relations, i.e. `√(2n(B+1))` residuals — a factor `√(2(B+1))` *more*
//! than plain rho's single collision.  For an r-adding walk the
//! relation vectors also live in the span of the `r` update vectors, so
//! `rank ≤ r + 1` however long it runs.  Rejecting all residuals outside
//! a set of size `M` costs `n/M` samples per accepted residual and
//! `√(2MR)` accepted residuals, a total of `n√(2R/M)`, never better than
//! the unfiltered `√(2nR)`.  [`mitm_four_decomposition`] measures the
//! meet-in-the-middle route `P_i + P_j = R − P_k − P_l`, which finds
//! weight-4 relations at `≈ B²/2` operations each.
//!
//! The numbers behind these predictions are collected by
//! `examples/residual_walk_bench.rs` and discussed in
//! `research/notes/index-calculus/RESEARCH_RESIDUAL_WALKS.md`.
//!
//! # Scope
//!
//! Toy prime-field curves with `p < 2^60` and prime group order, `u64`
//! affine arithmetic (one field inversion per group operation, counted
//! as one *group operation*).  Nothing here threatens any deployed
//! curve; the point of the module is the measurement.

use std::cell::Cell;
use std::collections::HashMap;
use std::time::{Duration, Instant};

use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde::Serialize;

/// Largest supported field size in bits (keeps `x + y` and all
/// intermediate `u128` products in range).
pub const MAX_BITS: u32 = 60;

// ── u64 modular arithmetic ─────────────────────────────────────────────

#[inline]
fn mul_mod(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}

#[inline]
fn add_mod(a: u64, b: u64, p: u64) -> u64 {
    let s = a + b;
    if s >= p {
        s - p
    } else {
        s
    }
}

#[inline]
fn sub_mod(a: u64, b: u64, p: u64) -> u64 {
    if a >= b {
        a - b
    } else {
        a + p - b
    }
}

/// `base^e mod p`.
pub fn pow_mod(mut base: u64, mut e: u64, p: u64) -> u64 {
    let mut acc = 1u64 % p;
    base %= p;
    while e > 0 {
        if e & 1 == 1 {
            acc = mul_mod(acc, base, p);
        }
        base = mul_mod(base, base, p);
        e >>= 1;
    }
    acc
}

/// Modular inverse by the extended Euclidean algorithm.  `a` must be
/// non-zero mod `p` and `p` prime.
pub fn inv_mod(a: u64, p: u64) -> u64 {
    let (mut old_r, mut r) = (a as i128 % p as i128, p as i128);
    let (mut old_s, mut s) = (1i128, 0i128);
    while r != 0 {
        let q = old_r / r;
        let tmp = old_r - q * r;
        old_r = r;
        r = tmp;
        let tmp = old_s - q * s;
        old_s = s;
        s = tmp;
    }
    debug_assert_eq!(old_r, 1, "inv_mod of a non-unit");
    old_s.rem_euclid(p as i128) as u64
}

/// Square root mod an odd prime (Tonelli–Shanks).  Returns `None` for
/// non-residues.
pub fn sqrt_mod(n: u64, p: u64) -> Option<u64> {
    let n = n % p;
    if n == 0 {
        return Some(0);
    }
    if pow_mod(n, (p - 1) / 2, p) != 1 {
        return None;
    }
    if p % 4 == 3 {
        return Some(pow_mod(n, (p + 1) / 4, p));
    }
    let mut q = p - 1;
    let mut s = 0u32;
    while q.is_multiple_of(2) {
        q /= 2;
        s += 1;
    }
    let mut z = 2u64;
    while pow_mod(z, (p - 1) / 2, p) != p - 1 {
        z += 1;
    }
    let mut m = s;
    let mut c = pow_mod(z, q, p);
    let mut t = pow_mod(n, q, p);
    let mut r = pow_mod(n, q.div_ceil(2), p);
    loop {
        if t == 1 {
            return Some(r);
        }
        let mut i = 0u32;
        let mut tt = t;
        while tt != 1 {
            tt = mul_mod(tt, tt, p);
            i += 1;
            if i == m {
                return None;
            }
        }
        let mut b = c;
        for _ in 0..(m - i - 1) {
            b = mul_mod(b, b, p);
        }
        m = i;
        c = mul_mod(b, b, p);
        t = mul_mod(t, c, p);
        r = mul_mod(r, b, p);
    }
}

/// Deterministic Miller–Rabin for `u64` (the first twelve prime bases
/// are a proven witness set below `3.3·10^24`).
pub fn is_prime_u64(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    for &sp in &[2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
        if n.is_multiple_of(sp) {
            return n == sp;
        }
    }
    let mut d = n - 1;
    let mut s = 0;
    while d.is_multiple_of(2) {
        d /= 2;
        s += 1;
    }
    'witness: for &a in &[2u64, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37] {
        let mut x = pow_mod(a, d, n);
        if x == 1 || x == n - 1 {
            continue;
        }
        for _ in 1..s {
            x = mul_mod(x, x, n);
            if x == n - 1 {
                continue 'witness;
            }
        }
        return false;
    }
    true
}

fn isqrt(n: u64) -> u64 {
    let mut r = (n as f64).sqrt() as u64;
    while r.checked_mul(r).is_none_or(|sq| sq > n) {
        r -= 1;
    }
    while (r + 1).checked_mul(r + 1).is_some_and(|sq| sq <= n) {
        r += 1;
    }
    r
}

/// SplitMix64 finaliser — the hash behind every "hash the residual"
/// decision in this module (multiplier index, distinguished-point test,
/// fresh-state derivation).
pub fn mix64(mut z: u64) -> u64 {
    z = z.wrapping_add(0x9E37_79B9_7F4A_7C15);
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

// ── Curve arithmetic ───────────────────────────────────────────────────

/// Affine point on a short-Weierstrass curve over `F_p`, `p < 2^60`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
pub struct Pt {
    pub x: u64,
    pub y: u64,
    pub inf: bool,
}

impl Pt {
    pub const INFINITY: Pt = Pt {
        x: 0,
        y: 0,
        inf: true,
    };

    pub fn affine(x: u64, y: u64) -> Pt {
        Pt { x, y, inf: false }
    }
}

/// `y² = x³ + ax + b` over `F_p` with a generator `g` of prime order
/// `n`.  Every affine addition or doubling increments `ops`; scalar
/// multiplications are counted through the additions they perform.
#[derive(Clone, Debug, Serialize)]
pub struct Curve {
    pub p: u64,
    pub a: u64,
    pub b: u64,
    pub n: u64,
    pub g: Pt,
    #[serde(skip)]
    ops: Cell<u64>,
}

impl Curve {
    pub fn new(p: u64, a: u64, b: u64, n: u64, g: Pt) -> Curve {
        Curve {
            p,
            a,
            b,
            n,
            g,
            ops: Cell::new(0),
        }
    }

    /// Group operations performed so far.
    pub fn ops(&self) -> u64 {
        self.ops.get()
    }

    pub fn reset_ops(&self) {
        self.ops.set(0);
    }

    pub fn bits(&self) -> u32 {
        64 - self.n.leading_zeros()
    }

    pub fn is_on_curve(&self, pt: &Pt) -> bool {
        if pt.inf {
            return true;
        }
        let p = self.p;
        let lhs = mul_mod(pt.y, pt.y, p);
        let x2 = mul_mod(pt.x, pt.x, p);
        let rhs = add_mod(
            add_mod(mul_mod(x2, pt.x, p), mul_mod(self.a, pt.x, p), p),
            self.b,
            p,
        );
        lhs == rhs
    }

    pub fn neg(&self, pt: &Pt) -> Pt {
        if pt.inf || pt.y == 0 {
            *pt
        } else {
            Pt::affine(pt.x, self.p - pt.y)
        }
    }

    /// Affine addition (one field inversion).  Counts one group op.
    pub fn add(&self, u: &Pt, v: &Pt) -> Pt {
        if u.inf {
            return *v;
        }
        if v.inf {
            return *u;
        }
        let p = self.p;
        if u.x == v.x {
            if add_mod(u.y, v.y, p) == 0 {
                return Pt::INFINITY;
            }
            return self.double(u);
        }
        self.ops.set(self.ops.get() + 1);
        let lambda = mul_mod(sub_mod(v.y, u.y, p), inv_mod(sub_mod(v.x, u.x, p), p), p);
        let x3 = sub_mod(sub_mod(mul_mod(lambda, lambda, p), u.x, p), v.x, p);
        let y3 = sub_mod(mul_mod(lambda, sub_mod(u.x, x3, p), p), u.y, p);
        Pt::affine(x3, y3)
    }

    /// Affine doubling (one field inversion).  Counts one group op.
    pub fn double(&self, u: &Pt) -> Pt {
        if u.inf || u.y == 0 {
            return Pt::INFINITY;
        }
        self.ops.set(self.ops.get() + 1);
        let p = self.p;
        let num = add_mod(mul_mod(3 % p, mul_mod(u.x, u.x, p), p), self.a, p);
        let lambda = mul_mod(num, inv_mod(add_mod(u.y, u.y, p), p), p);
        let x3 = sub_mod(sub_mod(mul_mod(lambda, lambda, p), u.x, p), u.x, p);
        let y3 = sub_mod(mul_mod(lambda, sub_mod(u.x, x3, p), p), u.y, p);
        Pt::affine(x3, y3)
    }

    pub fn sub(&self, u: &Pt, v: &Pt) -> Pt {
        self.add(u, &self.neg(v))
    }

    /// Left-to-right double-and-add.
    pub fn mul(&self, pt: &Pt, k: u64) -> Pt {
        let mut acc = Pt::INFINITY;
        if k == 0 || pt.inf {
            return acc;
        }
        let top = 63 - k.leading_zeros();
        for i in (0..=top).rev() {
            acc = self.double(&acc);
            if (k >> i) & 1 == 1 {
                acc = self.add(&acc, pt);
            }
        }
        acc
    }

    /// `c · pt` for a signed coefficient.
    pub fn mul_signed(&self, pt: &Pt, c: i64) -> Pt {
        if c >= 0 {
            self.mul(pt, c as u64)
        } else {
            self.mul(&self.neg(pt), c.unsigned_abs())
        }
    }

    /// `aG + bQ`.
    pub fn combine(&self, q: &Pt, a: u64, b: u64) -> Pt {
        self.add(&self.mul(&self.g, a), &self.mul(q, b))
    }

    /// Lift `x` to a curve point with the canonical (smaller) `y`, if
    /// `x³ + ax + b` is a square.
    pub fn lift_x(&self, x: u64) -> Option<Pt> {
        let p = self.p;
        let rhs = add_mod(
            add_mod(mul_mod(mul_mod(x, x, p), x, p), mul_mod(self.a, x, p), p),
            self.b,
            p,
        );
        let y = sqrt_mod(rhs, p)?;
        let y = if y * 2 < p { y } else { p - y };
        Some(Pt::affine(x, y))
    }
}

// ── Instance generation ────────────────────────────────────────────────

/// The order-3 automorphism `ζ(x, y) = (ωx, y)` of a `j = 0` curve
/// `y² = x³ + b` over `p ≡ 1 (mod 3)`, acting on the prime-order
/// subgroup as multiplication by `λ` (`λ² + λ + 1 ≡ 0 mod n`).
#[derive(Clone, Copy, Debug, Serialize)]
pub struct Automorphism {
    pub omega: u64,
    pub lambda: u64,
}

/// A known-answer ECDLP instance: `q = d · curve.g`.
#[derive(Clone, Debug, Serialize)]
pub struct Instance {
    pub curve: Curve,
    pub q: Pt,
    /// The planted answer, used only to score the recovered value.
    pub d: u64,
    /// Present on `j = 0` instances: the extra structure the 6-fold
    /// residual folding exploits.
    pub aut: Option<Automorphism>,
}

impl Instance {
    /// `ζ(pt) = (ωx, y)`; the identity when the instance has no
    /// automorphism.
    pub fn zeta(&self, pt: &Pt) -> Pt {
        match (&self.aut, pt.inf) {
            (Some(aut), false) => Pt::affine(mul_mod(aut.omega, pt.x, self.curve.p), pt.y),
            _ => *pt,
        }
    }
}

fn random_prime(bits: u32, rng: &mut StdRng) -> u64 {
    loop {
        let candidate = rng.gen_range((1u64 << (bits - 1))..(1u64 << bits)) | 1;
        if is_prime_u64(candidate) {
            return candidate;
        }
    }
}

/// Order of `pt` if it is the unique `m` in the Hasse interval with
/// `m · pt = O` (baby-step giant-step over the interval, `O(p^{1/4})`).
fn unique_hasse_multiple(curve: &Curve, pt: &Pt) -> Option<u64> {
    let p = curve.p;
    let two_sqrt = 2 * isqrt(p) + 2;
    let lo = p + 1 - two_sqrt;
    let hi = p + 1 + two_sqrt;
    let width = hi - lo + 1;
    let s = isqrt(width) + 1;

    let mut baby: HashMap<Pt, u64> = HashMap::with_capacity(s as usize);
    let mut cur = Pt::INFINITY;
    for j in 0..s {
        baby.entry(cur).or_insert(j);
        cur = curve.add(&cur, pt);
    }
    let giant = curve.mul(pt, s);
    let mut t = curve.mul(pt, lo);
    let mut found: Option<u64> = None;
    let mut i = 0u64;
    while lo + i * s <= hi {
        // (lo + i·s + j)·pt = O  ⟺  j·pt = −t.
        if let Some(&j) = baby.get(&curve.neg(&t)) {
            let m = lo + i * s + j;
            if m >= lo && m <= hi {
                if found.is_some() && found != Some(m) {
                    return None;
                }
                found = Some(m);
            }
        }
        t = curve.add(&t, &giant);
        i += 1;
    }
    found
}

/// Generate a random prime-field curve of about `bits` bits whose group
/// order is prime, together with a random known-answer target.
pub fn generate_instance(bits: u32, seed: u64) -> Instance {
    assert!(
        (12..=MAX_BITS).contains(&bits),
        "bits must lie in 12..={MAX_BITS}"
    );
    let mut rng = StdRng::seed_from_u64(seed ^ 0x5EED_C0DE);
    loop {
        let p = random_prime(bits, &mut rng);
        let a = rng.gen_range(1..p);
        let b = rng.gen_range(1..p);
        // Non-singular: 4a³ + 27b² ≠ 0.
        let disc = add_mod(
            mul_mod(4, mul_mod(mul_mod(a, a, p), a, p), p),
            mul_mod(27, mul_mod(b, b, p), p),
            p,
        );
        if disc == 0 {
            continue;
        }
        let curve = Curve::new(p, a, b, 0, Pt::INFINITY);
        let g = loop {
            let x = rng.gen_range(1..p);
            if let Some(pt) = curve.lift_x(x) {
                break pt;
            }
        };
        let Some(order) = unique_hasse_multiple(&curve, &g) else {
            continue;
        };
        if !is_prime_u64(order) {
            continue;
        }
        let curve = Curve::new(p, a, b, order, g);
        assert!(curve.mul(&g, order).inf, "order check failed");
        let d = rng.gen_range(1..order);
        let q = curve.mul(&g, d);
        curve.reset_ops();
        return Instance {
            curve,
            q,
            d,
            aut: None,
        };
    }
}

/// Generate a random `j = 0` curve `y² = x³ + b` over a prime
/// `p ≡ 1 (mod 3)` of about `bits` bits with prime group order, its
/// order-3 automorphism, and a random known-answer target.
pub fn generate_j0_instance(bits: u32, seed: u64) -> Instance {
    assert!(
        (12..=MAX_BITS).contains(&bits),
        "bits must lie in 12..={MAX_BITS}"
    );
    let mut rng = StdRng::seed_from_u64(seed ^ 0x1_0000_5EED);
    loop {
        let p = random_prime(bits, &mut rng);
        if p % 3 != 1 {
            continue;
        }
        // A primitive cube root of unity mod p.
        let omega = loop {
            let g = rng.gen_range(2..p);
            let w = pow_mod(g, (p - 1) / 3, p);
            if w != 1 {
                break w;
            }
        };
        let b = rng.gen_range(1..p);
        let curve = Curve::new(p, 0, b, 0, Pt::INFINITY);
        let g = loop {
            let x = rng.gen_range(1..p);
            if let Some(pt) = curve.lift_x(x) {
                break pt;
            }
        };
        let Some(order) = unique_hasse_multiple(&curve, &g) else {
            continue;
        };
        if !is_prime_u64(order) || order % 3 != 1 {
            continue;
        }
        let curve = Curve::new(p, 0, b, order, g);
        // λ = (−1 ± √−3) / 2 mod n; pick the root that matches ζ.
        let root = sqrt_mod(order - 3, order).expect("−3 is a square mod n when n ≡ 1 mod 3");
        let half = inv_mod(2, order);
        let zeta_g = Pt::affine(mul_mod(omega, g.x, p), g.y);
        let lambda = [root, order - root]
            .into_iter()
            .map(|r| mul_mod(sub_mod(r, 1, order), half, order))
            .find(|&l| curve.mul(&g, l) == zeta_g)
            .expect("one root of λ² + λ + 1 matches ζ");
        let d = rng.gen_range(1..order);
        let q = curve.mul(&g, d);
        curve.reset_ops();
        return Instance {
            curve,
            q,
            d,
            aut: Some(Automorphism { omega, lambda }),
        };
    }
}

// ── Factor base ────────────────────────────────────────────────────────

/// Factor base of points with the smallest `x`-coordinates, indexed
/// by `x` so a residual can be tested for membership in `±F` in `O(1)`.
#[derive(Clone, Debug)]
pub struct FactorBase {
    pub points: Vec<Pt>,
    by_x: HashMap<u64, usize>,
}

impl FactorBase {
    pub fn build(curve: &Curve, size: usize) -> FactorBase {
        let mut points = Vec::with_capacity(size);
        let mut by_x = HashMap::with_capacity(size);
        let mut x = 1u64;
        while points.len() < size && x < curve.p {
            if let Some(pt) = curve.lift_x(x) {
                if pt.y != 0 {
                    by_x.insert(x, points.len());
                    points.push(pt);
                }
            }
            x += 1;
        }
        FactorBase { points, by_x }
    }

    /// Factor base of the `size` smallest-`x` points that are canonical
    /// under the instance's automorphism folding (one representative per
    /// `⟨±1, ζ⟩`-orbit).  Without an automorphism this is [`Self::build`].
    pub fn build_orbit_reps(inst: &Instance, size: usize) -> FactorBase {
        if inst.aut.is_none() {
            return FactorBase::build(&inst.curve, size);
        }
        let curve = &inst.curve;
        let mut points = Vec::with_capacity(size);
        let mut by_x = HashMap::with_capacity(size);
        let mut x = 1u64;
        while points.len() < size && x < curve.p {
            if let Some(pt) = curve.lift_x(x) {
                let (canon, _) = fold(inst, Fold::Automorphism, &pt);
                if pt.y != 0 && canon == pt {
                    by_x.insert(x, points.len());
                    points.push(pt);
                }
            }
            x += 1;
        }
        FactorBase { points, by_x }
    }

    pub fn len(&self) -> usize {
        self.points.len()
    }

    pub fn is_empty(&self) -> bool {
        self.points.is_empty()
    }

    /// `Some((i, +1))` if `pt = P_i`, `Some((i, −1))` if `pt = −P_i`.
    pub fn lookup(&self, pt: &Pt) -> Option<(usize, i64)> {
        if pt.inf {
            return None;
        }
        let &i = self.by_x.get(&pt.x)?;
        Some((i, if self.points[i].y == pt.y { 1 } else { -1 }))
    }
}

// ── Relations and the linear system ────────────────────────────────────

/// `da·G + db·Q = Σ coeffs_i · P_i`, i.e.
/// `da + db·d ≡ Σ coeffs_i · ℓ_i (mod n)`.
#[derive(Clone, Debug, PartialEq, Eq, Serialize)]
pub struct Relation {
    pub da: u64,
    pub db: u64,
    /// Sparse signed coefficients `(factor_base_index, multiplicity)`.
    pub coeffs: Vec<(usize, i64)>,
    /// Factored form `f1·R1 − f2·R2` with small-coefficient residuals
    /// `R_j = a_j G + b_j Q − Σ c_j P`, kept for relations whose scaled
    /// coefficients are full-size scalars (automorphism folding) so that
    /// verification costs two large scalar multiplications instead of
    /// one per coefficient.
    #[serde(skip)]
    pub factored: Option<Box<FactoredRelation>>,
}

/// See [`Relation::factored`].
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FactoredRelation {
    pub f1: u64,
    pub r1: (u64, u64, Vec<(usize, i64)>),
    pub f2: u64,
    pub r2: (u64, u64, Vec<(usize, i64)>),
}

/// What a residual collision turned out to be.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum CollisionKind {
    /// Same canonical state twice (a walk revisiting itself, or two
    /// orderings of one multiset).  Not progress.
    Trivial,
    /// Same multiset, different `(a, b)`: `da + db·d ≡ 0`, which is a
    /// plain rho collision and solves `d` outright.
    Direct,
    /// `da = db = 0`: a relation among factor-base logarithms only.
    FactorBaseOnly,
    /// Involves `d` and at least one factor-base element.
    Mixed,
}

impl Relation {
    pub fn kind(&self) -> CollisionKind {
        match (self.coeffs.is_empty(), self.da == 0 && self.db == 0) {
            (true, true) => CollisionKind::Trivial,
            (true, false) => CollisionKind::Direct,
            (false, true) => CollisionKind::FactorBaseOnly,
            (false, false) => CollisionKind::Mixed,
        }
    }

    /// Check `da·G + db·Q − Σ c_i P_i = O` with actual group arithmetic.
    pub fn verify(&self, inst: &Instance, fb: &FactorBase) -> bool {
        let curve = &inst.curve;
        let eval = |a: u64, b: u64, coeffs: &[(usize, i64)]| {
            let mut acc = curve.combine(&inst.q, a, b);
            for &(i, c) in coeffs {
                acc = curve.sub(&acc, &curve.mul_signed(&fb.points[i], c));
            }
            acc
        };
        match &self.factored {
            Some(fr) => {
                let x1 = eval(fr.r1.0, fr.r1.1, &fr.r1.2);
                let x2 = eval(fr.r2.0, fr.r2.1, &fr.r2.2);
                curve.mul(&x1, fr.f1) == curve.mul(&x2, fr.f2)
            }
            None => eval(self.da, self.db, &self.coeffs).inf,
        }
    }

    /// `f1·(a1 G + b1 Q − Σ c1 P) − f2·(a2 G + b2 Q − Σ c2 P) = O` as a
    /// relation; the factored form is retained when either factor is
    /// not `±1`.
    pub fn scaled(
        n: u64,
        f1: u64,
        r1: (u64, u64, Vec<(usize, i64)>),
        f2: u64,
        r2: (u64, u64, Vec<(usize, i64)>),
    ) -> Relation {
        let (f1, f2) = (f1 % n, f2 % n);
        let mut acc: HashMap<usize, u64> = HashMap::new();
        for (f, coeffs, negate) in [(f1, &r1.2, false), (f2, &r2.2, true)] {
            for &(i, c) in coeffs {
                let mag = mul_mod(f, c.unsigned_abs() % n, n);
                let v = if (c < 0) ^ negate { (n - mag) % n } else { mag };
                let e = acc.entry(i).or_insert(0);
                *e = add_mod(*e, v, n);
            }
        }
        let mut coeffs: Vec<(usize, i64)> = acc
            .into_iter()
            .filter(|&(_, v)| v != 0)
            .map(|(i, v)| (i, centred(v, n)))
            .collect();
        coeffs.sort_unstable();
        let small = |f: u64| f == 1 || f == n - 1;
        let factored = if small(f1) && small(f2) {
            None
        } else {
            Some(Box::new(FactoredRelation {
                f1,
                r1: r1.clone(),
                f2,
                r2: r2.clone(),
            }))
        };
        Relation {
            da: sub_mod(mul_mod(f1, r1.0 % n, n), mul_mod(f2, r2.0 % n, n), n),
            db: sub_mod(mul_mod(f1, r1.1 % n, n), mul_mod(f2, r2.1 % n, n), n),
            coeffs,
            factored,
        }
    }

    /// Dense row over `ℤ/nℤ` in the unknowns `(ℓ_0, …, ℓ_{B−1}, d)` plus
    /// its right-hand side: `Σ c_i ℓ_i − db·d = da`.
    pub fn row(&self, n: u64, fb_size: usize) -> (Vec<u64>, u64) {
        let mut row = vec![0u64; fb_size + 1];
        for &(i, c) in &self.coeffs {
            let v = c.unsigned_abs() % n;
            row[i] = if c >= 0 { v } else { (n - v) % n };
        }
        row[fb_size] = (n - self.db % n) % n;
        (row, self.da % n)
    }
}

/// How residuals are folded before they are keyed in the table.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Fold {
    /// Exact points.
    Identity,
    /// Classes `{P, −P}`.
    Negation,
    /// Classes `{±ζ^k P}` on a `j = 0` instance (six points).
    Automorphism,
}

impl Fold {
    pub fn order(self) -> u32 {
        match self {
            Fold::Identity => 1,
            Fold::Negation => 2,
            Fold::Automorphism => 6,
        }
    }
}

/// Canonical representative `C` of the fold class of `pt` and the scalar
/// `f` with `pt = f · C`.  The representative has the smallest `x` among
/// `{x, ωx, ω²x}` (automorphism only) and the smaller `y`.  Costs field
/// multiplications only, never a group operation.
fn fold(inst: &Instance, mode: Fold, pt: &Pt) -> (Pt, u64) {
    let curve = &inst.curve;
    let n = curve.n;
    if pt.inf || mode == Fold::Identity {
        return (*pt, 1);
    }
    let (x, k) = match (mode, &inst.aut) {
        (Fold::Automorphism, Some(aut)) => {
            let x1 = mul_mod(aut.omega, pt.x, curve.p);
            let x2 = mul_mod(aut.omega, x1, curve.p);
            let (mut x, mut k) = (pt.x, 0u32);
            if x1 < x {
                x = x1;
                k = 1;
            }
            if x2 < x {
                x = x2;
                k = 2;
            }
            (x, k)
        }
        _ => (pt.x, 0),
    };
    // ζ^k(pt) = (x, y) = λ^k · pt, so pt = λ^{−k} · (x, y) = λ^{3−k} · (x, y).
    let mut f = match (&inst.aut, k) {
        (Some(aut), 1) => mul_mod(aut.lambda, aut.lambda, n),
        (Some(aut), 2) => aut.lambda,
        _ => 1,
    };
    let y = if pt.y * 2 > curve.p {
        f = (n - f) % n;
        curve.p - pt.y
    } else {
        pt.y
    };
    (Pt::affine(x, y), f)
}

/// Centre a residue mod `n` into `(−n/2, n/2]` as a signed coefficient.
fn centred(v: u64, n: u64) -> i64 {
    if v > n / 2 {
        v as i64 - n as i64
    } else {
        v as i64
    }
}

fn multiset_diff(t1: &[u32], t2: &[u32]) -> Vec<(usize, i64)> {
    let mut m: HashMap<u32, i64> = HashMap::new();
    for &i in t1 {
        *m.entry(i).or_insert(0) += 1;
    }
    for &i in t2 {
        *m.entry(i).or_insert(0) -= 1;
    }
    let mut out: Vec<(usize, i64)> = m
        .into_iter()
        .filter(|&(_, c)| c != 0)
        .map(|(i, c)| (i as usize, c))
        .collect();
    out.sort_unstable();
    out
}

/// Incrementally maintained reduced row-echelon system over `ℤ/nℤ`
/// (`n` prime).  Tracks the rank of the relations seen so far and
/// reports the moment a given unknown becomes determined.
#[derive(Clone, Debug)]
pub struct RelationSystem {
    n: u64,
    cols: usize,
    pivots: Vec<(usize, Vec<u64>, u64)>,
    /// Multiplications modulo `n` performed so far.
    ops: u64,
}

impl RelationSystem {
    pub fn new(n: u64, unknowns: usize) -> RelationSystem {
        RelationSystem {
            n,
            cols: unknowns,
            pivots: Vec::new(),
            ops: 0,
        }
    }

    pub fn rank(&self) -> usize {
        self.pivots.len()
    }

    /// Multiplications modulo `n` performed by `insert` so far.
    pub fn ops(&self) -> u64 {
        self.ops
    }

    /// Insert one equation; returns `true` if it was independent of the
    /// rows already present.
    pub fn insert(&mut self, mut row: Vec<u64>, mut rhs: u64) -> bool {
        assert_eq!(row.len(), self.cols);
        let n = self.n;
        let mut ops = 0u64;
        for (col, prow, prhs) in &self.pivots {
            let f = row[*col];
            if f != 0 {
                for c in 0..self.cols {
                    if prow[c] != 0 {
                        row[c] = sub_mod(row[c], mul_mod(f, prow[c], n), n);
                        ops += 1;
                    }
                }
                rhs = sub_mod(rhs, mul_mod(f, *prhs, n), n);
                ops += 1;
            }
        }
        self.ops += ops;
        let Some(col) = row.iter().position(|&v| v != 0) else {
            return false;
        };
        let inv = inv_mod(row[col], n);
        for v in row.iter_mut() {
            *v = mul_mod(*v, inv, n);
        }
        rhs = mul_mod(rhs, inv, n);
        let mut ops = self.cols as u64 + 1;
        for (_, prow, prhs) in self.pivots.iter_mut() {
            let f = prow[col];
            if f != 0 {
                for c in 0..self.cols {
                    if row[c] != 0 {
                        prow[c] = sub_mod(prow[c], mul_mod(f, row[c], n), n);
                        ops += 1;
                    }
                }
                *prhs = sub_mod(*prhs, mul_mod(f, rhs, n), n);
                ops += 1;
            }
        }
        self.ops += ops;
        self.pivots.push((col, row, rhs));
        true
    }

    /// The value of unknown `col` if the unit vector `e_col` lies in the
    /// row space (its pivot row has no other non-zero entry).
    pub fn solved(&self, col: usize) -> Option<u64> {
        let (_, row, rhs) = self.pivots.iter().find(|(c, _, _)| *c == col)?;
        if row.iter().enumerate().all(|(c, &v)| c == col || v == 0) {
            Some(*rhs)
        } else {
            None
        }
    }
}

// ── Strategies ─────────────────────────────────────────────────────────

/// Relation-generation strategy; see the module docs for the table.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum Strategy {
    /// A: independent random `(a, b, k-tuple)` per residual.
    IndependentSamples,
    /// B: one tuple, one slot changed per step, residual updated by
    /// `L ← L + P_old − P_new`; occasional `+G` / `+Q` steps.
    LocalMutationWalk,
    /// C1: r-adding walk on residuals whose multipliers each subtract a
    /// factor-base point.  Collision-preserving.
    RAddingResidualWalk,
    /// C2: `s_{t+1} = H(L(s_t))`, residual recomputed from scratch.
    /// Collision-preserving.
    FreshHashWalk,
    /// Reference: r-adding Pollard rho with no factor base.
    PlainRho,
}

impl Strategy {
    pub const ALL: [Strategy; 5] = [
        Strategy::IndependentSamples,
        Strategy::LocalMutationWalk,
        Strategy::RAddingResidualWalk,
        Strategy::FreshHashWalk,
        Strategy::PlainRho,
    ];

    pub fn tag(&self) -> &'static str {
        match self {
            Strategy::IndependentSamples => "A",
            Strategy::LocalMutationWalk => "B",
            Strategy::RAddingResidualWalk => "C1",
            Strategy::FreshHashWalk => "C2",
            Strategy::PlainRho => "R",
        }
    }

    pub fn name(&self) -> &'static str {
        match self {
            Strategy::IndependentSamples => "independent-samples",
            Strategy::LocalMutationWalk => "local-mutation-walk",
            Strategy::RAddingResidualWalk => "r-adding-residual-walk",
            Strategy::FreshHashWalk => "fresh-hash-walk",
            Strategy::PlainRho => "plain-rho",
        }
    }

    pub fn parse(s: &str) -> Option<Strategy> {
        Strategy::ALL
            .iter()
            .copied()
            .find(|st| st.tag().eq_ignore_ascii_case(s) || st.name() == s)
    }

    pub fn collision_preserving(&self) -> bool {
        matches!(
            self,
            Strategy::RAddingResidualWalk | Strategy::FreshHashWalk | Strategy::PlainRho
        )
    }
}

/// Knobs shared by every strategy.
#[derive(Clone, Debug, Serialize)]
pub struct WalkOptions {
    /// Tuple length `k` for the explicit-state strategies (A, B, C2).
    pub k: usize,
    /// Total group-operation budget (walk + replay + verification).
    pub max_ops: u64,
    /// Distinguished-point bits for the collision-preserving strategies
    /// (`0` = store every residual).  Rejected for A and B.
    pub dp_bits: u32,
    /// Number of multipliers `r` for the r-adding strategies
    /// (`0` = `B` for C1, `32` for plain rho).
    pub multipliers: usize,
    /// Only look up / store residuals with `x < M` (A and B only).
    pub filter_bound: Option<u64>,
    pub seed: u64,
    /// Abandon a collision-preserving walk after this many steps
    /// (`0` = automatic: `max(64·2^dp_bits, 8√n)`).
    pub walk_cap: u64,
    /// Stop as soon as `d` is determined (`true`), or keep collecting
    /// until the budget is spent so relation yield can be compared at a
    /// fixed cost (`false`; `ops_at_solve` still records the first solve).
    pub stop_when_solved: bool,
    /// Key the residual table on the class `{L, −L}` so a residual also
    /// collides with the negative of a stored one (`L(s) = −L(s')` gives
    /// `(a+a')G + (b+b')Q = ΣT + ΣT'`).  Halves the effective search
    /// space; only for `dp_bits = 0`, where every residual is stored and
    /// nothing has to propagate along a walk.
    pub negation_map: bool,
    /// Local-mutation walk only: precompute `P_i − P_j` for all pairs so
    /// a swap costs one addition instead of two (`B(B−1)/2` setup
    /// operations and points).
    pub diff_table: bool,
    /// r-adding walks only: restart the walk after this many steps
    /// (`0` = never).  Bounds the coefficient replay per collision to
    /// `2·segment_len` at the price of two scalar multiplications per
    /// restart.
    pub segment_len: u64,
    /// Local-mutation walk only: keep mutating after a collision instead
    /// of drawing a fresh random state.  The walk is driven by its own
    /// randomness, not by the residual, so nothing merges and the two
    /// scalar multiplications of a restart are simply saved.  (The
    /// collision-preserving walks must restart: after a merge every
    /// further step would re-collide.)
    pub continue_after_collision: bool,
    /// Fold residuals by the instance's order-3 automorphism as well as
    /// by negation (six points per table class; `j = 0` instances only,
    /// exhaustive storage only).  Implies `negation_map`.
    pub use_automorphism: bool,
    /// Explicit-state strategies only: seed the residual table with every
    /// signed pair `±P_i ± P_j` before walking.  Each seed is a residual
    /// with a known decomposition and is counted in `seeded_points`.
    pub seed_pairs: bool,
    /// Explicit-state strategies only: test every residual for
    /// `L = ±P_i ± P_j` algebraically with Semaev's `S₃` (one quadratic
    /// in `x_j` per factor-base `x_i`, roots looked up in the base)
    /// instead of from a seed table.  Each quadratic solved is charged as
    /// one operation-equivalent in `oracle_ops`.
    pub s3_oracle: bool,
    /// Explicit-state strategies only: test every residual for
    /// `L = ±P_i ± P_j ± P_k` (distinct indices) algebraically — `S₃`
    /// applied twice: the roots `x(L ∓ P_i)` for each `i`, then for each
    /// `j > i` the quadratic in `x_k` — with no table.  `B²` quadratics
    /// per residual, each charged as one operation-equivalent.
    pub s4_oracle: bool,
    /// Explicit-state strategies only: look the `2B` neighbours
    /// `L ∓ P_k` of every residual up in the table (one group operation
    /// each, charged to the oracle).  With `seed_pairs` this is the
    /// meet-in-the-middle triple oracle; a neighbour that is `±P_m` is a
    /// pair decomposition and one that matches a walked residual is an
    /// ordinary collision with one extra term.
    pub mitm_neighbours: bool,
}

impl Default for WalkOptions {
    fn default() -> Self {
        WalkOptions {
            k: 3,
            max_ops: 1 << 32,
            dp_bits: 0,
            multipliers: 0,
            filter_bound: None,
            seed: 1,
            walk_cap: 0,
            stop_when_solved: true,
            negation_map: false,
            diff_table: false,
            segment_len: 0,
            continue_after_collision: false,
            use_automorphism: false,
            seed_pairs: false,
            s3_oracle: false,
            s4_oracle: false,
            mitm_neighbours: false,
        }
    }
}

/// Everything measured for one strategy on one instance.
#[derive(Clone, Debug, Serialize)]
pub struct StrategyReport {
    pub strategy: &'static str,
    pub tag: &'static str,
    pub bits: u32,
    pub p: u64,
    pub n: u64,
    pub factor_base: usize,
    pub k: usize,
    pub dp_bits: u32,
    pub multipliers: usize,
    pub filter_bound: Option<u64>,
    pub negation_map: bool,
    pub diff_table: bool,
    pub segment_len: u64,
    pub continue_after_collision: bool,
    /// Size of the fold classes the table is keyed on: 1, 2 or 6.
    pub fold_order: u32,
    /// Whether the instance is a `j = 0` curve with its automorphism.
    pub j_zero: bool,
    /// Residuals with known decomposition inserted before walking
    /// (signed pair sums); they count towards the total point count.
    pub seeded_points: u64,
    pub s3_oracle: bool,
    pub s4_oracle: bool,
    pub mitm_neighbours: bool,
    /// Work charged to the oracles and included in `total_ops`:
    /// quadratics solved (one operation-equivalent each — a square root
    /// costs about what an affine addition costs) plus the group
    /// operations of the neighbour lookups.
    pub oracle_ops: u64,
    /// Complete decompositions the oracles found (`L = ±P_i ± P_j`, or
    /// `± P_k` more).
    pub oracle_hits: u64,
    /// Neighbour lookups that matched a *walked* residual rather than a
    /// seed: ordinary collisions with one extra term.
    pub neighbour_collisions: u64,
    /// Residuals evaluated (independent samples or walk steps).
    pub samples: u64,
    /// Residuals that passed the filter / distinguished-point test and
    /// were looked up in the table.
    pub accepted: u64,
    /// Peak number of stored residuals.
    pub table_entries: usize,
    pub walks: u64,
    pub abandoned_walks: u64,
    pub setup_ops: u64,
    pub walk_ops: u64,
    pub replay_ops: u64,
    pub verify_ops: u64,
    pub total_ops: u64,
    pub collisions_trivial: u64,
    pub collisions_direct: u64,
    pub collisions_fb_only: u64,
    pub collisions_mixed: u64,
    pub full_decompositions: u64,
    pub relations_verified: u64,
    pub relations_failed_verification: u64,
    pub relations_independent: u64,
    pub relations_dependent: u64,
    pub rank: usize,
    pub solved: bool,
    pub recovered: Option<u64>,
    pub correct: Option<bool>,
    pub ops_at_solve: Option<u64>,
    pub wall_ms: f64,
    pub linear_algebra_ms: f64,
    pub ops_per_independent_relation: Option<f64>,
    /// `√(2n(B+1))`: residuals needed for `B+1` birthday collisions.
    pub predicted_birthday_samples: f64,
    /// `√(πn/2)`: plain rho's expected steps to its first collision.
    pub predicted_rho_steps: f64,
}

impl StrategyReport {
    fn new(inst: &Instance, fb: &FactorBase, strategy: Strategy, opts: &WalkOptions) -> Self {
        let n = inst.curve.n;
        StrategyReport {
            strategy: strategy.name(),
            tag: strategy.tag(),
            bits: inst.curve.bits(),
            p: inst.curve.p,
            n,
            factor_base: fb.len(),
            k: opts.k,
            dp_bits: opts.dp_bits,
            multipliers: opts.multipliers,
            filter_bound: opts.filter_bound,
            negation_map: opts.negation_map,
            diff_table: opts.diff_table,
            segment_len: opts.segment_len,
            continue_after_collision: opts.continue_after_collision,
            fold_order: fold_mode(inst, opts).order(),
            j_zero: inst.aut.is_some(),
            seeded_points: 0,
            s3_oracle: opts.s3_oracle,
            s4_oracle: opts.s4_oracle,
            mitm_neighbours: opts.mitm_neighbours,
            oracle_ops: 0,
            oracle_hits: 0,
            neighbour_collisions: 0,
            samples: 0,
            accepted: 0,
            table_entries: 0,
            walks: 0,
            abandoned_walks: 0,
            setup_ops: 0,
            walk_ops: 0,
            replay_ops: 0,
            verify_ops: 0,
            total_ops: 0,
            collisions_trivial: 0,
            collisions_direct: 0,
            collisions_fb_only: 0,
            collisions_mixed: 0,
            full_decompositions: 0,
            relations_verified: 0,
            relations_failed_verification: 0,
            relations_independent: 0,
            relations_dependent: 0,
            rank: 0,
            solved: false,
            recovered: None,
            correct: None,
            ops_at_solve: None,
            wall_ms: 0.0,
            linear_algebra_ms: 0.0,
            ops_per_independent_relation: None,
            predicted_birthday_samples: (2.0 * n as f64 * (fb.len() as f64 + 1.0)).sqrt(),
            predicted_rho_steps: (std::f64::consts::PI * n as f64 / 2.0).sqrt(),
        }
    }
}

/// Shared relation pipeline: classify → verify → insert → check `d`.
struct Collector<'a> {
    inst: &'a Instance,
    fb: &'a FactorBase,
    system: RelationSystem,
    report: StrategyReport,
    la_time: Duration,
    /// Oracle work that was *not* a group operation (quadratic solves);
    /// `report.oracle_ops` additionally holds the oracle's group ops,
    /// which the curve counter already contains.
    oracle_solves: u64,
}

impl<'a> Collector<'a> {
    fn new(inst: &'a Instance, fb: &'a FactorBase, strategy: Strategy, opts: &WalkOptions) -> Self {
        Collector {
            inst,
            fb,
            system: RelationSystem::new(inst.curve.n, fb.len() + 1),
            report: StrategyReport::new(inst, fb, strategy, opts),
            la_time: Duration::ZERO,
            oracle_solves: 0,
        }
    }

    /// Charge `solves` quadratic solves to the oracle.
    fn charge_solves(&mut self, solves: u64) {
        self.oracle_solves += solves;
        self.report.oracle_ops += solves;
    }

    /// Charge group operations performed since `before` to the oracle
    /// (they are already in the curve counter).
    fn charge_group_ops(&mut self, before: u64) {
        self.report.oracle_ops += self.inst.curve.ops() - before;
    }

    /// Group operations plus non-group oracle work so far.
    fn spent(&self) -> u64 {
        self.inst.curve.ops() + self.oracle_solves
    }

    fn count_collision(&mut self, kind: CollisionKind) {
        match kind {
            CollisionKind::Trivial => self.report.collisions_trivial += 1,
            CollisionKind::Direct => self.report.collisions_direct += 1,
            CollisionKind::FactorBaseOnly => self.report.collisions_fb_only += 1,
            CollisionKind::Mixed => self.report.collisions_mixed += 1,
        }
    }

    /// Feed a relation obtained from a residual collision.
    fn push_collision(&mut self, rel: Relation) {
        let kind = rel.kind();
        self.count_collision(kind);
        if kind != CollisionKind::Trivial {
            self.push(rel);
        }
    }

    /// Feed a relation obtained from a complete decomposition.
    fn push_full(&mut self, rel: Relation) {
        self.report.full_decompositions += 1;
        if rel.kind() != CollisionKind::Trivial {
            self.push(rel);
        }
    }

    fn push(&mut self, rel: Relation) {
        let curve = &self.inst.curve;
        let before = curve.ops();
        let ok = rel.verify(self.inst, self.fb);
        self.report.verify_ops += curve.ops() - before;
        if !ok {
            self.report.relations_failed_verification += 1;
            return;
        }
        self.report.relations_verified += 1;
        let (row, rhs) = rel.row(curve.n, self.fb.len());
        let t0 = Instant::now();
        let independent = self.system.insert(row, rhs);
        if independent {
            self.report.relations_independent += 1;
            if let Some(d) = self.system.solved(self.fb.len()) {
                if !self.report.solved {
                    self.report.solved = true;
                    self.report.recovered = Some(d);
                    self.report.correct = Some(d == self.inst.d);
                    self.report.ops_at_solve = Some(curve.ops() + self.oracle_solves);
                }
            }
        } else {
            self.report.relations_dependent += 1;
        }
        self.la_time += t0.elapsed();
        self.report.rank = self.system.rank();
    }

    fn finish(mut self, start: Instant, setup_ops: u64) -> StrategyReport {
        let total = self.inst.curve.ops() + self.oracle_solves;
        self.report.setup_ops = setup_ops;
        self.report.total_ops = total;
        self.report.walk_ops = total
            .saturating_sub(setup_ops)
            .saturating_sub(self.report.replay_ops)
            .saturating_sub(self.report.verify_ops)
            .saturating_sub(self.report.oracle_ops);
        self.report.wall_ms = start.elapsed().as_secs_f64() * 1e3;
        self.report.linear_algebra_ms = self.la_time.as_secs_f64() * 1e3;
        if self.report.relations_independent > 0 {
            self.report.ops_per_independent_relation =
                Some(total as f64 / self.report.relations_independent as f64);
        }
        self.report
    }
}

// ── Explicit partial-decomposition states (A, B, C2) ───────────────────

/// `(a, b, sorted multisets of factor-base indices)`: the residual is
/// `aG + bQ − Σ P_tuple + Σ P_minus`.  Walked states have an empty
/// `minus`; seeded pair states (`±P_i ± P_j`) use it.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct DecompState {
    pub a: u64,
    pub b: u64,
    pub tuple: Vec<u32>,
    pub minus: Vec<u32>,
}

impl DecompState {
    fn canonical(mut self) -> Self {
        self.tuple.sort_unstable();
        self.minus.sort_unstable();
        self
    }

    pub fn random(rng: &mut StdRng, n: u64, fb_size: usize, k: usize) -> DecompState {
        DecompState {
            a: rng.gen_range(0..n),
            b: rng.gen_range(1..n),
            tuple: (0..k).map(|_| rng.gen_range(0..fb_size as u32)).collect(),
            minus: Vec::new(),
        }
        .canonical()
    }

    /// The hash-to-state map `H` of the fresh-hash walk: a function of
    /// the residual alone.
    pub fn from_residual(pt: &Pt, n: u64, fb_size: usize, k: usize) -> DecompState {
        let seed = mix64(pt.x ^ mix64(pt.y ^ (pt.inf as u64)));
        let mut h = seed;
        let mut next = || {
            h = mix64(h);
            h
        };
        let a = next() % n;
        let b = 1 + next() % (n - 1);
        let tuple = (0..k).map(|_| (next() % fb_size as u64) as u32).collect();
        DecompState {
            a,
            b,
            tuple,
            minus: Vec::new(),
        }
        .canonical()
    }

    /// `aG + bQ − Σ P_{tuple} + Σ P_{minus}`.
    pub fn residual(&self, inst: &Instance, fb: &FactorBase) -> Pt {
        let curve = &inst.curve;
        let mut l = curve.combine(&inst.q, self.a, self.b);
        for &i in &self.tuple {
            l = curve.sub(&l, &fb.points[i as usize]);
        }
        for &i in &self.minus {
            l = curve.add(&l, &fb.points[i as usize]);
        }
        l
    }

    /// Relation implied by `L(self) = L(other)`.
    pub fn relation_to(&self, other: &DecompState, n: u64) -> Relation {
        self.relation_scaled(1, other, 1, n)
    }

    /// Relation implied by `L(self) = f · C` and `L(other) = f' · C` for
    /// the same fold representative `C`, i.e. `f' · L(self) = f · L(other)`:
    /// `(f'a − fa')G + (f'b − fb')Q = f'·ΣT − f·ΣT'`.  With `f, f' ∈ {±1}`
    /// this is the negation-map relation; with `λ` powers it is the
    /// automorphism-folded one.
    pub fn relation_scaled(&self, f: u64, other: &DecompState, f_other: u64, n: u64) -> Relation {
        Relation::scaled(
            n,
            f_other,
            (
                self.a % n,
                self.b % n,
                multiset_diff(&self.tuple, &self.minus),
            ),
            f,
            (
                other.a % n,
                other.b % n,
                multiset_diff(&other.tuple, &other.minus),
            ),
        )
    }

    /// Relation implied by `L(self) = c·P_i` (or `O` when `hit` is
    /// `None`), with `c` a centred signed coefficient.
    pub fn full_relation(&self, hit: Option<(usize, i64)>) -> Relation {
        match hit {
            Some(term) => self.full_relation_with(&[term]),
            None => self.full_relation_with(&[]),
        }
    }

    /// Relation implied by `L(self) = Σ c_i P_i` for the given signed
    /// terms (a complete decomposition of the residual).
    pub fn full_relation_with(&self, terms: &[(usize, i64)]) -> Relation {
        let mut coeffs = multiset_diff(&self.tuple, &self.minus);
        for &(i, c) in terms {
            match coeffs.iter_mut().find(|(j, _)| *j == i) {
                Some(entry) => entry.1 += c,
                None => coeffs.push((i, c)),
            }
        }
        coeffs.retain(|&(_, c)| c != 0);
        coeffs.sort_unstable();
        Relation {
            da: self.a,
            db: self.b,
            coeffs,
            factored: None,
        }
    }
}

// ── Semaev S₃ pair-decomposition oracle ────────────────────────────────

/// Semaev's third summation polynomial for `y² = x³ + ax + b` as a
/// quadratic in its last argument: `S₃(x₁, x₂, X) = A·X² + B·X + C` with
///
/// ```text
///   A = (x₁ − x₂)²
///   B = −2[(x₁ + x₂)(x₁x₂ + a) + 2b]
///   C = (x₁x₂ − a)² − 4b(x₁ + x₂),
/// ```
///
/// which vanishes exactly at `X = x(P₁ ± P₂)`.
pub fn s3_in_x3(curve: &Curve, x1: u64, x2: u64) -> (u64, u64, u64) {
    let p = curve.p;
    let x1x2 = mul_mod(x1, x2, p);
    let sum = add_mod(x1, x2, p);
    let diff = sub_mod(x1, x2, p);
    let a_coef = mul_mod(diff, diff, p);
    let inner = add_mod(
        mul_mod(sum, add_mod(x1x2, curve.a, p), p),
        mul_mod(2, curve.b, p),
        p,
    );
    let b_coef = (p - mul_mod(2, inner, p)) % p;
    let part = sub_mod(x1x2, curve.a, p);
    let c_coef = sub_mod(
        mul_mod(part, part, p),
        mul_mod(mul_mod(4, curve.b, p), sum, p),
        p,
    );
    (a_coef, b_coef, c_coef)
}

/// One-exponentiation square root when `p ≡ 3 (mod 4)`; Tonelli–Shanks
/// otherwise.  Either way it is the unit the oracle is charged in.
fn sqrt_fast(d: u64, p: u64) -> Option<u64> {
    if d == 0 {
        return Some(0);
    }
    if p % 4 == 3 {
        let r = pow_mod(d, (p + 1) / 4, p);
        if mul_mod(r, r, p) == d {
            Some(r)
        } else {
            None
        }
    } else {
        sqrt_mod(d, p)
    }
}

/// Decide `L = s_i·P_i + s_j·P_j` (`i ≤ j`, `s ∈ {±1}`) with Semaev's
/// `S₃`: for every `i` solve the quadratic `S₃(x_L, x_i, X) = 0` and look
/// its roots up in the factor base; the signs are then settled by two
/// group operations.  Returns the decompositions as coefficient lists
/// and the number of quadratics solved.  `L = ±P_i` itself is left to the
/// factor-base lookup.
pub fn s3_pair_oracle(inst: &Instance, fb: &FactorBase, l: &Pt) -> (Vec<Vec<(usize, i64)>>, u64) {
    let curve = &inst.curve;
    let p = curve.p;
    let mut found = Vec::new();
    let mut solves = 0u64;
    if l.inf {
        return (found, 0);
    }
    for (i, pi) in fb.points.iter().enumerate() {
        if pi.x == l.x {
            continue;
        }
        solves += 1;
        let (a, b, c) = s3_in_x3(curve, l.x, pi.x);
        // A = (x_L − x_i)² ≠ 0 here.
        let disc = sub_mod(mul_mod(b, b, p), mul_mod(4, mul_mod(a, c, p), p), p);
        let Some(r) = sqrt_fast(disc, p) else {
            continue;
        };
        let inv2a = inv_mod(mul_mod(2, a, p), p);
        let mut roots = vec![mul_mod(sub_mod(p - b, r, p), inv2a, p)];
        if r != 0 {
            roots.push(mul_mod(add_mod(p - b, r, p), inv2a, p));
        }
        for x in roots {
            let Some(&j) = fb.by_x.get(&x) else {
                continue;
            };
            if j < i {
                continue; // found from the smaller index already
            }
            let pj = fb.points[j];
            // L − s_i P_i = s_j P_j for some signs: two additions decide.
            for s_i in [1i64, -1] {
                let rest = if s_i == 1 {
                    curve.sub(l, pi)
                } else {
                    curve.add(l, pi)
                };
                let s_j = if rest == pj {
                    1
                } else if rest == curve.neg(&pj) {
                    -1
                } else {
                    continue;
                };
                let terms = if i == j {
                    vec![(i, s_i + s_j)]
                } else {
                    vec![(i, s_i), (j, s_j)]
                };
                if terms.iter().all(|&(_, c)| c != 0) {
                    found.push(terms);
                }
            }
        }
    }
    found.sort();
    found.dedup();
    (found, solves)
}

/// Roots of `S₃(x₁, x₂, X) = 0`, i.e. the candidates for `x(P₁ ± P₂)`,
/// and whether a quadratic was solved (`x₁ = x₂` is skipped).
fn s3_roots(curve: &Curve, x1: u64, x2: u64) -> (Vec<u64>, bool) {
    if x1 == x2 {
        return (Vec::new(), false);
    }
    let p = curve.p;
    let (a, b, c) = s3_in_x3(curve, x1, x2);
    let disc = sub_mod(mul_mod(b, b, p), mul_mod(4, mul_mod(a, c, p), p), p);
    let Some(r) = sqrt_fast(disc, p) else {
        return (Vec::new(), true);
    };
    let inv2a = inv_mod(mul_mod(2, a, p), p);
    let mut roots = vec![mul_mod(sub_mod(p - b, r, p), inv2a, p)];
    if r != 0 {
        roots.push(mul_mod(add_mod(p - b, r, p), inv2a, p));
    }
    (roots, true)
}

/// Decide `L = s_i P_i + s_j P_j + s_k P_k` with `i < j < k` by applying
/// `S₃` twice: the roots `Y = x(L ∓ P_i)` for each `i`, then for each
/// `j > i` the roots `X` of `S₃(Y, x_j, X)`, looked up in the factor base.
/// Signs are settled by group arithmetic.  Returns the decompositions
/// and the number of quadratics solved (`≈ B²`).  Pairs and repeated
/// indices are left to the other oracles.
pub fn s4_triple_oracle(inst: &Instance, fb: &FactorBase, l: &Pt) -> (Vec<Vec<(usize, i64)>>, u64) {
    let curve = &inst.curve;
    let mut found = Vec::new();
    let mut solves = 0u64;
    if l.inf {
        return (found, 0);
    }
    let bsize = fb.len();
    for i in 0..bsize {
        let (ys, solved) = s3_roots(curve, l.x, fb.points[i].x);
        solves += solved as u64;
        for y in ys {
            for j in (i + 1)..bsize {
                let (xs, solved) = s3_roots(curve, y, fb.points[j].x);
                solves += solved as u64;
                for x in xs {
                    let Some(&k) = fb.by_x.get(&x) else {
                        continue;
                    };
                    if k <= j {
                        continue;
                    }
                    // L − s_i P_i − s_j P_j = s_k P_k for some signs.
                    for s_i in [1i64, -1] {
                        let after_i = curve.sub(l, &curve.mul_signed(&fb.points[i], s_i));
                        for s_j in [1i64, -1] {
                            let rest = curve.sub(&after_i, &curve.mul_signed(&fb.points[j], s_j));
                            let pk = fb.points[k];
                            let s_k = if rest == pk {
                                1
                            } else if rest == curve.neg(&pk) {
                                -1
                            } else {
                                continue;
                            };
                            found.push(vec![(i, s_i), (j, s_j), (k, s_k)]);
                        }
                    }
                }
            }
        }
    }
    found.sort();
    found.dedup();
    (found, solves)
}

/// The fold the options ask for on this instance.
fn fold_mode(inst: &Instance, opts: &WalkOptions) -> Fold {
    if opts.use_automorphism && inst.aut.is_some() {
        Fold::Automorphism
    } else if opts.negation_map || opts.use_automorphism {
        Fold::Negation
    } else {
        Fold::Identity
    }
}

/// Complete-decomposition test under a fold: `pt = c · P_i` for a
/// factor-base point, with `c` centred.
fn fold_lookup(inst: &Instance, fb: &FactorBase, mode: Fold, pt: &Pt) -> Option<(usize, i64)> {
    let (canon, f) = fold(inst, mode, pt);
    let (i, sign) = fb.lookup(&canon)?;
    let c = if sign == 1 {
        f
    } else {
        (inst.curve.n - f) % inst.curve.n
    };
    Some((i, centred(c, inst.curve.n)))
}

const DP_SALT: u64 = 0xD15_71C7;

fn is_distinguished(pt: &Pt, dp_bits: u32) -> bool {
    dp_bits == 0 || (mix64(pt.x ^ DP_SALT) & ((1u64 << dp_bits) - 1)) == 0
}

fn run_explicit(
    inst: &Instance,
    fb: &FactorBase,
    strategy: Strategy,
    opts: &WalkOptions,
) -> StrategyReport {
    let curve = &inst.curve;
    let n = curve.n;
    let bsize = fb.len();
    let k = opts.k.max(1);
    assert!(
        opts.dp_bits == 0,
        "distinguished points need a collision-preserving walk with merge-point replay"
    );
    let mut rng = StdRng::seed_from_u64(opts.seed ^ mix64(strategy.tag().len() as u64 + 17));
    curve.reset_ops();
    let start = Instant::now();
    let mut col = Collector::new(inst, fb, strategy, opts);
    let mode = fold_mode(inst, opts);
    let mut table: HashMap<Pt, (DecompState, u64)> = HashMap::new();

    // Optional seeding with every signed pair sum.  A seed is a residual
    // of the state `(0, 0, tuple, minus)` whose decomposition is known;
    // it collides with walked residuals exactly like a stored one and
    // is counted in `seeded_points`.
    if opts.seed_pairs {
        let seed_state = |tuple: Vec<u32>, minus: Vec<u32>| {
            DecompState {
                a: 0,
                b: 0,
                tuple,
                minus,
            }
            .canonical()
        };
        for i in 0..bsize {
            for j in (i + 1)..bsize {
                let (pi, pj) = (fb.points[i], fb.points[j]);
                let (iu, ju) = (i as u32, j as u32);
                let sum = curve.add(&pi, &pj);
                let dif = curve.sub(&pi, &pj);
                let mut seeds = vec![
                    (sum, seed_state(vec![], vec![iu, ju])),
                    (dif, seed_state(vec![ju], vec![iu])),
                ];
                if mode == Fold::Identity {
                    seeds.push((curve.neg(&sum), seed_state(vec![iu, ju], vec![])));
                    seeds.push((curve.neg(&dif), seed_state(vec![iu], vec![ju])));
                }
                for (pt, state) in seeds {
                    if let Some(hit) = fold_lookup(inst, fb, mode, &pt) {
                        col.push_full(state.full_relation(Some(hit)));
                    }
                    let (key, f) = fold(inst, mode, &pt);
                    match table.get(&key) {
                        Some((prev, prev_f)) => {
                            col.push_collision(state.relation_scaled(f, prev, *prev_f, n));
                        }
                        None => {
                            table.insert(key, (state, f));
                            col.report.seeded_points += 1;
                        }
                    }
                }
            }
        }
    }

    // Optional `P_i − P_j` table for the local-mutation walk.
    let diff: Vec<Pt> = if strategy == Strategy::LocalMutationWalk && opts.diff_table {
        let mut d = vec![Pt::INFINITY; bsize * bsize];
        for i in 0..bsize {
            for j in (i + 1)..bsize {
                let dij = curve.sub(&fb.points[i], &fb.points[j]);
                d[i * bsize + j] = dij;
                d[j * bsize + i] = curve.neg(&dij);
            }
        }
        d
    } else {
        Vec::new()
    };
    let setup_ops = curve.ops();

    let mut state = DecompState::random(&mut rng, n, bsize, k);
    let mut l = state.residual(inst, fb);
    col.report.walks = 1;
    let mut steps_since_check = 0u64;

    loop {
        col.report.samples += 1;
        let mut restart = false;
        let passes_filter = match opts.filter_bound {
            Some(m) => !l.inf && l.x < m,
            None => true,
        };
        if passes_filter {
            if l.inf {
                col.push_full(state.full_relation(None));
            } else if let Some(hit) = fold_lookup(inst, fb, mode, &l) {
                col.push_full(state.full_relation(Some(hit)));
            }
            if opts.s3_oracle {
                let before = curve.ops();
                let (hits, solves) = s3_pair_oracle(inst, fb, &l);
                col.charge_solves(solves);
                col.charge_group_ops(before);
                for terms in hits {
                    col.report.oracle_hits += 1;
                    col.push_full(state.full_relation_with(&terms));
                }
            }
            if opts.s4_oracle {
                let before = curve.ops();
                let (hits, solves) = s4_triple_oracle(inst, fb, &l);
                col.charge_solves(solves);
                col.charge_group_ops(before);
                for terms in hits {
                    col.report.oracle_hits += 1;
                    col.push_full(state.full_relation_with(&terms));
                }
            }
            if opts.mitm_neighbours {
                let before = curve.ops();
                for kk in 0..bsize {
                    for sign in [1i64, -1] {
                        // z = L − sign·P_k is the residual of `state` with
                        // one more term.
                        let z = if sign == 1 {
                            curve.sub(&l, &fb.points[kk])
                        } else {
                            curve.add(&l, &fb.points[kk])
                        };
                        let mut zs = state.clone();
                        if sign == 1 {
                            zs.tuple.push(kk as u32);
                        } else {
                            zs.minus.push(kk as u32);
                        }
                        let zs = zs.canonical();
                        if z.inf {
                            col.report.oracle_hits += 1;
                            col.push_full(zs.full_relation(None));
                            continue;
                        }
                        if let Some(hit) = fold_lookup(inst, fb, mode, &z) {
                            col.report.oracle_hits += 1;
                            col.push_full(zs.full_relation(Some(hit)));
                        }
                        let (zkey, zf) = fold(inst, mode, &z);
                        if let Some((prev, prev_f)) = table.get(&zkey) {
                            if prev.a == 0 && prev.b == 0 {
                                col.report.oracle_hits += 1;
                            } else {
                                col.report.neighbour_collisions += 1;
                            }
                            if *prev != zs {
                                col.push_collision(zs.relation_scaled(zf, prev, *prev_f, n));
                            }
                        }
                    }
                }
                col.charge_group_ops(before);
            }
            col.report.accepted += 1;
            let (key, f) = fold(inst, mode, &l);
            match table.get(&key) {
                Some((prev, prev_f)) => {
                    if *prev == state {
                        // Same state: a revisit, or `f·L = f'·L` with
                        // `f ≠ f'`, i.e. `L = O`, already reported as a
                        // complete decomposition.  Neither is progress.
                        col.count_collision(CollisionKind::Trivial);
                    } else {
                        col.push_collision(state.relation_scaled(f, prev, *prev_f, n));
                    }
                    restart = true;
                }
                None => {
                    table.insert(key, (state.clone(), f));
                }
            }
        }
        if (opts.stop_when_solved && col.report.solved) || col.spent() >= opts.max_ops {
            break;
        }
        match strategy {
            Strategy::IndependentSamples => {
                state = DecompState::random(&mut rng, n, bsize, k);
                l = state.residual(inst, fb);
            }
            Strategy::FreshHashWalk => {
                state = if restart {
                    col.report.walks += 1;
                    DecompState::random(&mut rng, n, bsize, k)
                } else {
                    DecompState::from_residual(&l, n, bsize, k)
                };
                l = state.residual(inst, fb);
            }
            Strategy::LocalMutationWalk => {
                if restart && !opts.continue_after_collision {
                    col.report.walks += 1;
                    state = DecompState::random(&mut rng, n, bsize, k);
                    l = state.residual(inst, fb);
                } else {
                    match rng.gen_range(0..8u32) {
                        0 => {
                            l = curve.add(&l, &curve.g);
                            state.a = add_mod(state.a, 1, n);
                        }
                        1 => {
                            l = curve.add(&l, &inst.q);
                            state.b = add_mod(state.b, 1, n);
                        }
                        _ => {
                            let slot = rng.gen_range(0..k);
                            let new = rng.gen_range(0..bsize as u32);
                            let old = state.tuple[slot];
                            if old != new {
                                if diff.is_empty() {
                                    l = curve.add(&l, &fb.points[old as usize]);
                                    l = curve.sub(&l, &fb.points[new as usize]);
                                } else {
                                    l = curve.add(&l, &diff[old as usize * bsize + new as usize]);
                                }
                                state.tuple[slot] = new;
                                state.tuple.sort_unstable();
                            }
                        }
                    }
                    steps_since_check += 1;
                    if steps_since_check == 1 << 16 {
                        // Guard against drift in the incremental update.
                        steps_since_check = 0;
                        let before = curve.ops();
                        let fresh = state.residual(inst, fb);
                        col.report.verify_ops += curve.ops() - before;
                        assert_eq!(fresh, l, "incremental residual drifted");
                    }
                }
            }
            _ => unreachable!(),
        }
    }
    col.report.table_entries = table.len();
    col.finish(start, setup_ops)
}

/// Fresh-hash walk with distinguished-point storage.
///
/// The state `s_{t+1} = H(L(s_t))` is memoryless, so once two walks
/// have merged they carry *identical* states, and the collision seen at
/// the next distinguished point is trivial.  The only relation lives at
/// the merge point, where the two predecessor states differ; as in van
/// Oorschot–Wiener, it is located by replaying both walks from their
/// stored starts, aligning them to equal distance from the distinguished
/// point and stepping in lockstep until the residuals first agree.
fn run_fresh_hash_dp(inst: &Instance, fb: &FactorBase, opts: &WalkOptions) -> StrategyReport {
    let strategy = Strategy::FreshHashWalk;
    assert!(
        !opts.negation_map
            && !opts.use_automorphism
            && !opts.seed_pairs
            && !opts.s3_oracle
            && !opts.s4_oracle
            && !opts.mitm_neighbours,
        "folding and seeding are implemented for exhaustive storage (dp_bits = 0) only"
    );
    let curve = &inst.curve;
    let n = curve.n;
    let bsize = fb.len();
    let k = opts.k.max(1);
    let mut rng = StdRng::seed_from_u64(opts.seed ^ mix64(strategy.tag().len() as u64 + 17));
    curve.reset_ops();
    let start = Instant::now();
    let mut col = Collector::new(inst, fb, strategy, opts);
    let sqrt_n = (n as f64).sqrt() as u64;
    let walk_cap = if opts.walk_cap > 0 {
        opts.walk_cap
    } else {
        (64u64 << opts.dp_bits).max(8 * sqrt_n)
    };
    let mut starts: Vec<DecompState> = Vec::new();
    let mut table: HashMap<Pt, (u32, u32)> = HashMap::new();

    let advance = |state: &mut DecompState, l: &mut Pt| {
        *state = DecompState::from_residual(l, n, bsize, k);
        *l = state.residual(inst, fb);
    };
    // Predecessor states at the merge point of walk `w1` after `t1`
    // transitions and walk `w2` after `t2`, both of which sit on the
    // same distinguished residual.
    let locate_merge = |starts: &[DecompState], w1: usize, t1: u64, w2: usize, t2: u64| {
        let mut s1 = starts[w1].clone();
        let mut l1 = s1.residual(inst, fb);
        let mut s2 = starts[w2].clone();
        let mut l2 = s2.residual(inst, fb);
        let (mut i1, mut i2) = (0u64, 0u64);
        while t1 - i1 > t2 - i2 {
            advance(&mut s1, &mut l1);
            i1 += 1;
        }
        while t2 - i2 > t1 - i1 {
            advance(&mut s2, &mut l2);
            i2 += 1;
        }
        loop {
            if l1 == l2 {
                return Some(s1.relation_to(&s2, n));
            }
            if i1 >= t1 {
                return None;
            }
            advance(&mut s1, &mut l1);
            advance(&mut s2, &mut l2);
            i1 += 1;
        }
    };

    'outer: loop {
        let w = starts.len();
        let mut state = DecompState::random(&mut rng, n, bsize, k);
        starts.push(state.clone());
        col.report.walks += 1;
        let mut l = state.residual(inst, fb);
        let mut step = 0u64;
        loop {
            col.report.samples += 1;
            if l.inf {
                col.push_full(state.full_relation(None));
            } else if let Some(hit) = fb.lookup(&l) {
                col.push_full(state.full_relation(Some(hit)));
            }
            if is_distinguished(&l, opts.dp_bits) {
                col.report.accepted += 1;
                match table.get(&l) {
                    Some(&(w2, s2)) => {
                        let before = curve.ops();
                        let rel = locate_merge(&starts, w, step, w2 as usize, s2 as u64);
                        col.report.replay_ops += curve.ops() - before;
                        match rel {
                            Some(rel) => col.push_collision(rel),
                            None => col.report.relations_failed_verification += 1,
                        }
                        break;
                    }
                    None => {
                        table.insert(l, (w as u32, step as u32));
                    }
                }
            }
            if (opts.stop_when_solved && col.report.solved) || curve.ops() >= opts.max_ops {
                break 'outer;
            }
            if step >= walk_cap {
                col.report.abandoned_walks += 1;
                break;
            }
            advance(&mut state, &mut l);
            step += 1;
        }
    }
    col.report.table_entries = table.len();
    col.finish(start, 0)
}

// ── r-adding walks on residuals (C1 and plain rho) ─────────────────────

struct Multiplier {
    alpha: u64,
    beta: u64,
    fb_index: Option<usize>,
    pt: Pt,
}

struct RAddingWalk<'a> {
    inst: &'a Instance,
    mults: Vec<Multiplier>,
    starts: Vec<(u64, u64)>,
}

/// Coefficient view of a walk position: `L = aG + bQ − Σ_j counts_j · P_{fb(j)}`.
struct WalkPosition {
    a: u64,
    b: u64,
    counts: Vec<u32>,
    residual: Pt,
}

impl<'a> RAddingWalk<'a> {
    fn index(&self, pt: &Pt) -> usize {
        (mix64(pt.x ^ 0xA11CE) % self.mults.len() as u64) as usize
    }

    fn step(&self, pt: &Pt) -> (usize, Pt) {
        let j = self.index(pt);
        (j, self.inst.curve.add(pt, &self.mults[j].pt))
    }

    /// Recompute the coefficients of walk `w` after `steps` steps.
    fn replay(&self, w: usize, steps: u64) -> WalkPosition {
        let curve = &self.inst.curve;
        let n = curve.n;
        let (a0, b0) = self.starts[w];
        let mut pos = WalkPosition {
            a: a0,
            b: b0,
            counts: vec![0; self.mults.len()],
            residual: curve.combine(&self.inst.q, a0, b0),
        };
        for _ in 0..steps {
            let (j, next) = self.step(&pos.residual);
            pos.counts[j] += 1;
            pos.a = add_mod(pos.a, self.mults[j].alpha, n);
            pos.b = add_mod(pos.b, self.mults[j].beta, n);
            pos.residual = next;
        }
        pos
    }

    fn relation(&self, here: &WalkPosition, there: &WalkPosition) -> Relation {
        let n = self.inst.curve.n;
        let mut by_fb: HashMap<usize, i64> = HashMap::new();
        for (j, m) in self.mults.iter().enumerate() {
            let delta = here.counts[j] as i64 - there.counts[j] as i64;
            if delta != 0 {
                if let Some(i) = m.fb_index {
                    *by_fb.entry(i).or_insert(0) += delta;
                }
            }
        }
        let mut coeffs: Vec<(usize, i64)> = by_fb.into_iter().filter(|&(_, c)| c != 0).collect();
        coeffs.sort_unstable();
        Relation {
            da: sub_mod(here.a, there.a, n),
            db: sub_mod(here.b, there.b, n),
            coeffs,
            factored: None,
        }
    }

    /// Small-coefficient view of a walk position over the factor base.
    fn small_form(&self, pos: &WalkPosition) -> (u64, u64, Vec<(usize, i64)>) {
        let mut by_fb: HashMap<usize, i64> = HashMap::new();
        for (j, m) in self.mults.iter().enumerate() {
            if pos.counts[j] != 0 {
                if let Some(i) = m.fb_index {
                    *by_fb.entry(i).or_insert(0) += pos.counts[j] as i64;
                }
            }
        }
        let mut coeffs: Vec<(usize, i64)> = by_fb.into_iter().collect();
        coeffs.sort_unstable();
        (pos.a, pos.b, coeffs)
    }

    /// Relation implied by `L(here) = f·C`, `L(there) = f'·C`, i.e.
    /// `f'·L(here) = f·L(there)`.
    fn relation_scaled(
        &self,
        here: &WalkPosition,
        f: u64,
        there: &WalkPosition,
        f_there: u64,
    ) -> Relation {
        if f == 1 && f_there == 1 {
            return self.relation(here, there);
        }
        let n = self.inst.curve.n;
        Relation::scaled(n, f_there, self.small_form(here), f, self.small_form(there))
    }

    /// Relation from `L = sign·P_i` (or `O`).
    fn full_relation(&self, here: &WalkPosition, hit: Option<(usize, i64)>) -> Relation {
        let empty = WalkPosition {
            a: 0,
            b: 0,
            counts: vec![0; self.mults.len()],
            residual: Pt::INFINITY,
        };
        let mut rel = self.relation(here, &empty);
        if let Some((i, sign)) = hit {
            match rel.coeffs.iter_mut().find(|(j, _)| *j == i) {
                Some(entry) => entry.1 += sign,
                None => rel.coeffs.push((i, sign)),
            }
            rel.coeffs.retain(|&(_, c)| c != 0);
            rel.coeffs.sort_unstable();
        }
        rel
    }
}

fn run_radding(
    inst: &Instance,
    fb: &FactorBase,
    strategy: Strategy,
    opts: &WalkOptions,
) -> StrategyReport {
    let curve = &inst.curve;
    let n = curve.n;
    let with_fb = strategy == Strategy::RAddingResidualWalk;
    let r = match (opts.multipliers, with_fb) {
        (0, true) => fb.len(),
        (0, false) => 32,
        (r, true) => r.min(fb.len()),
        (r, false) => r,
    };
    assert!(r >= 2, "need at least two multipliers");
    assert!(
        !((opts.negation_map || opts.use_automorphism) && opts.dp_bits > 0),
        "folding is implemented for exhaustive storage (dp_bits = 0) only"
    );
    let mode = fold_mode(inst, opts);
    let mut rng = StdRng::seed_from_u64(opts.seed ^ mix64(strategy.tag().len() as u64 + 29));
    curve.reset_ops();
    let start = Instant::now();

    let mults: Vec<Multiplier> = (0..r)
        .map(|j| {
            let alpha = rng.gen_range(0..n);
            let beta = rng.gen_range(1..n);
            let mut pt = curve.combine(&inst.q, alpha, beta);
            let fb_index = if with_fb {
                pt = curve.sub(&pt, &fb.points[j]);
                Some(j)
            } else {
                None
            };
            Multiplier {
                alpha,
                beta,
                fb_index,
                pt,
            }
        })
        .collect();
    let setup_ops = curve.ops();

    let mut walk = RAddingWalk {
        inst,
        mults,
        starts: Vec::new(),
    };
    let mut col = Collector::new(inst, fb, strategy, opts);
    col.report.multipliers = r;
    let sqrt_n = (n as f64).sqrt() as u64;
    let walk_cap = if opts.walk_cap > 0 {
        opts.walk_cap
    } else {
        (64u64 << opts.dp_bits).max(8 * sqrt_n)
    };
    let mut table: HashMap<Pt, (u32, u32, u64)> = HashMap::new();

    'outer: loop {
        let w = walk.starts.len();
        let a0 = rng.gen_range(0..n);
        let b0 = rng.gen_range(1..n);
        walk.starts.push((a0, b0));
        col.report.walks += 1;
        let mut l = curve.combine(&inst.q, a0, b0);
        let mut step = 0u64;
        loop {
            col.report.samples += 1;
            let full_hit = if l.inf {
                Some(None)
            } else {
                fold_lookup(inst, fb, mode, &l).map(Some)
            };
            if let Some(hit) = full_hit {
                let before = curve.ops();
                let pos = walk.replay(w, step);
                col.report.replay_ops += curve.ops() - before;
                debug_assert_eq!(pos.residual, l);
                let rel = walk.full_relation(&pos, hit);
                col.push_full(rel);
            }
            if is_distinguished(&l, opts.dp_bits) {
                col.report.accepted += 1;
                let (key, f) = fold(inst, mode, &l);
                match table.get(&key) {
                    Some(&(w2, s2, f2)) => {
                        let before = curve.ops();
                        let here = walk.replay(w, step);
                        let there = walk.replay(w2 as usize, s2 as u64);
                        col.report.replay_ops += curve.ops() - before;
                        let there_fold = fold(inst, mode, &there.residual);
                        if here.residual != l || there_fold != (key, f2) {
                            // Never expected: the walk is deterministic.
                            col.report.relations_failed_verification += 1;
                        } else {
                            col.push_collision(walk.relation_scaled(&here, f, &there, f2));
                        }
                        break;
                    }
                    None => {
                        table.insert(key, (w as u32, step as u32, f));
                    }
                }
            }
            if (opts.stop_when_solved && col.report.solved) || curve.ops() >= opts.max_ops {
                break 'outer;
            }
            if opts.segment_len > 0 && step >= opts.segment_len {
                // Segment boundary: start a fresh walk so that replay
                // never has to reach back further than one segment.
                break;
            }
            if step >= walk_cap {
                col.report.abandoned_walks += 1;
                break;
            }
            l = walk.step(&l).1;
            step += 1;
        }
    }
    col.report.table_entries = table.len();
    col.finish(start, setup_ops)
}

/// Run one strategy on one instance with one factor base.
pub fn run_strategy(
    inst: &Instance,
    fb: &FactorBase,
    strategy: Strategy,
    opts: &WalkOptions,
) -> StrategyReport {
    assert!(!fb.is_empty(), "empty factor base");
    match strategy {
        Strategy::FreshHashWalk if opts.dp_bits > 0 => run_fresh_hash_dp(inst, fb, opts),
        Strategy::IndependentSamples | Strategy::LocalMutationWalk | Strategy::FreshHashWalk => {
            run_explicit(inst, fb, strategy, opts)
        }
        Strategy::RAddingResidualWalk | Strategy::PlainRho => run_radding(inst, fb, strategy, opts),
    }
}

// ── Meet in the middle on 4-decompositions ─────────────────────────────

/// Report for [`mitm_four_decomposition`].
#[derive(Clone, Debug, Serialize)]
pub struct MitmReport {
    pub bits: u32,
    pub n: u64,
    pub factor_base: usize,
    pub pair_table: usize,
    /// Distinct unordered pairs whose sums coincided while building the
    /// table: each is a relation `P_i + P_j = P_k + P_l` over `F` alone.
    pub pair_coincidences: u64,
    pub targets: u64,
    pub relations_verified: u64,
    pub relations_independent: u64,
    pub rank: usize,
    pub setup_ops: u64,
    pub search_ops: u64,
    pub verify_ops: u64,
    pub total_ops: u64,
    pub solved: bool,
    pub recovered: Option<u64>,
    pub correct: Option<bool>,
    pub wall_ms: f64,
    /// `(B(B+1)/2)² / n`: expected matches per target under the
    /// uniform model.
    pub predicted_matches_per_target: f64,
    pub ops_per_independent_relation: Option<f64>,
}

/// Decompose targets `R = aG + bQ` as `P_i + P_j + P_k + P_l` by
/// colliding the family `{P_i + P_j}` (stored once) against the family
/// `{R − P_k − P_l}` (streamed per target).  Stops when `d` is
/// determined or after `max_targets` targets.
pub fn mitm_four_decomposition(
    inst: &Instance,
    fb: &FactorBase,
    max_targets: u64,
    seed: u64,
) -> MitmReport {
    let curve = &inst.curve;
    let n = curve.n;
    let bsize = fb.len();
    let mut rng = StdRng::seed_from_u64(seed ^ 0x4D17);
    curve.reset_ops();
    let start = Instant::now();

    let mut pairs: HashMap<Pt, (u32, u32)> = HashMap::with_capacity(bsize * (bsize + 1) / 2);
    let mut system = RelationSystem::new(n, bsize + 1);
    let mut verified = 0u64;
    let mut independent = 0u64;
    let mut verify_ops = 0u64;
    let mut coincidences = 0u64;
    for i in 0..bsize {
        for j in i..bsize {
            let s = curve.add(&fb.points[i], &fb.points[j]);
            if s.inf {
                continue;
            }
            match pairs.get(&s) {
                Some(&(k, l)) => {
                    coincidences += 1;
                    let rel = Relation {
                        da: 0,
                        db: 0,
                        coeffs: multiset_diff(&[i as u32, j as u32], &[k, l]),
                        factored: None,
                    };
                    if rel.kind() != CollisionKind::Trivial {
                        let before = curve.ops();
                        if rel.verify(inst, fb) {
                            verified += 1;
                            let (row, rhs) = rel.row(n, bsize);
                            if system.insert(row, rhs) {
                                independent += 1;
                            }
                        }
                        verify_ops += curve.ops() - before;
                    }
                }
                None => {
                    pairs.insert(s, (i as u32, j as u32));
                }
            }
        }
    }
    let setup_ops = curve.ops();

    let mut targets = 0u64;
    let mut solved = None;
    while targets < max_targets && solved.is_none() {
        targets += 1;
        let a = rng.gen_range(0..n);
        let b = rng.gen_range(1..n);
        let r_pt = curve.combine(&inst.q, a, b);
        for k in 0..bsize {
            let rk = curve.sub(&r_pt, &fb.points[k]);
            for l in k..bsize {
                let t = curve.sub(&rk, &fb.points[l]);
                if let Some(&(i, j)) = pairs.get(&t) {
                    let mut coeffs = multiset_diff(&[i, j, k as u32, l as u32], &[]);
                    coeffs.sort_unstable();
                    let rel = Relation {
                        da: a,
                        db: b,
                        coeffs,
                        factored: None,
                    };
                    let before = curve.ops();
                    let ok = rel.verify(inst, fb);
                    verify_ops += curve.ops() - before;
                    if ok {
                        verified += 1;
                        let (row, rhs) = rel.row(n, bsize);
                        if system.insert(row, rhs) {
                            independent += 1;
                            if let Some(d) = system.solved(bsize) {
                                solved = Some(d);
                            }
                        }
                    }
                }
            }
            if solved.is_some() {
                break;
            }
        }
    }
    let total = curve.ops();
    let pt = bsize as f64 * (bsize as f64 + 1.0) / 2.0;
    MitmReport {
        bits: curve.bits(),
        n,
        factor_base: bsize,
        pair_table: pairs.len(),
        pair_coincidences: coincidences,
        targets,
        relations_verified: verified,
        relations_independent: independent,
        rank: system.rank(),
        setup_ops,
        search_ops: total - setup_ops - verify_ops,
        verify_ops,
        total_ops: total,
        solved: solved.is_some(),
        recovered: solved,
        correct: solved.map(|d| d == inst.d),
        wall_ms: start.elapsed().as_secs_f64() * 1e3,
        predicted_matches_per_target: pt * pt / n as f64,
        ops_per_independent_relation: if independent > 0 {
            Some(total as f64 / independent as f64)
        } else {
            None
        },
    }
}

// ── Tests ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ecc::field::FieldElement;
    use crate::ecc::point::Point;
    use num_bigint::BigUint;

    /// Toy curve `y² = x³ + 2x + 3` over `F_271` (shared with
    /// `ec_index_calculus`); `(3, 6)` generates a subgroup of order 87
    /// — enough to cross-check the u64 arithmetic against the crate's
    /// `BigUint` point arithmetic.
    fn cross_check_curve() -> Curve {
        let curve = Curve::new(271, 2, 3, 0, Pt::INFINITY);
        let g = curve.lift_x(3).unwrap();
        Curve::new(271, 2, 3, 0, g)
    }

    fn to_big(pt: &Pt, p: u64) -> Point {
        if pt.inf {
            Point::Infinity
        } else {
            let p = BigUint::from(p);
            Point::Affine {
                x: FieldElement::new(BigUint::from(pt.x), p.clone()),
                y: FieldElement::new(BigUint::from(pt.y), p),
            }
        }
    }

    #[test]
    fn u64_arithmetic_matches_biguint_point_arithmetic() {
        let curve = cross_check_curve();
        let a_fe = FieldElement::new(BigUint::from(2u32), BigUint::from(271u32));
        let g_big = to_big(&curve.g, curve.p);
        let mut acc = Pt::INFINITY;
        for k in 0..200u64 {
            assert_eq!(
                to_big(&acc, curve.p),
                g_big.scalar_mul(&BigUint::from(k), &a_fe)
            );
            assert_eq!(
                to_big(&curve.mul(&curve.g, k), curve.p),
                to_big(&acc, curve.p)
            );
            assert!(curve.is_on_curve(&acc));
            acc = curve.add(&acc, &curve.g);
        }
        let h = curve.mul(&curve.g, 17);
        let s = curve.add(&h, &curve.mul(&curve.g, 40));
        assert_eq!(
            to_big(&s, curve.p),
            to_big(&h, curve.p).add(&g_big.scalar_mul(&BigUint::from(40u32), &a_fe), &a_fe)
        );
    }

    #[test]
    fn field_helpers() {
        let p = 1_000_003u64;
        for v in [1u64, 2, 12345, 999_999] {
            assert_eq!(mul_mod(v, inv_mod(v, p), p), 1);
            let sq = mul_mod(v, v, p);
            let r = sqrt_mod(sq, p).unwrap();
            assert!(r == v || r == p - v);
        }
        // p ≡ 1 mod 4 exercises the general Tonelli–Shanks branch.
        let p = 1_000_033u64;
        assert_eq!(p % 4, 1);
        let r = sqrt_mod(mul_mod(777, 777, p), p).unwrap();
        assert!(r == 777 || r == p - 777);
        assert!(is_prime_u64(p));
        assert!(!is_prime_u64(p + 2));
        assert!(is_prime_u64(2));
        assert!(!is_prime_u64(1));
        assert_eq!(isqrt(15), 3);
        assert_eq!(isqrt(16), 4);
    }

    #[test]
    fn generated_instance_has_prime_order_and_known_answer() {
        let inst = generate_instance(20, 7);
        let c = &inst.curve;
        assert!(is_prime_u64(c.n));
        assert!(c.is_on_curve(&c.g));
        assert!(c.is_on_curve(&inst.q));
        let two_sqrt = 2.0 * (c.p as f64).sqrt();
        assert!((c.n as f64 - (c.p as f64 + 1.0)).abs() <= two_sqrt + 2.0);
        assert!(c.mul(&c.g, c.n).inf);
        assert_eq!(c.mul(&c.g, inst.d), inst.q);
    }

    #[test]
    fn factor_base_lookup_reports_sign() {
        let inst = generate_instance(16, 3);
        let fb = FactorBase::build(&inst.curve, 16);
        assert_eq!(fb.len(), 16);
        for (i, pt) in fb.points.iter().enumerate() {
            assert_eq!(fb.lookup(pt), Some((i, 1)));
            assert_eq!(fb.lookup(&inst.curve.neg(pt)), Some((i, -1)));
        }
        assert_eq!(fb.lookup(&Pt::INFINITY), None);
    }

    #[test]
    fn relation_system_tracks_rank_and_determination() {
        let n = 1_000_003u64;
        let mut sys = RelationSystem::new(n, 3);
        // x0 + x1 = 5, x1 + x2 = 7, x0 + x1 + x2 = 9  ⇒  x2 = 4, x0 = 2, x1 = 3.
        assert!(sys.insert(vec![1, 1, 0], 5));
        assert!(sys.insert(vec![0, 1, 1], 7));
        assert_eq!(sys.solved(2), None);
        assert!(!sys.insert(vec![1, 2, 1], 12)); // dependent (sum of the first two)
        assert!(sys.insert(vec![1, 1, 1], 9));
        assert_eq!(sys.rank(), 3);
        assert_eq!(sys.solved(0), Some(2));
        assert_eq!(sys.solved(1), Some(3));
        assert_eq!(sys.solved(2), Some(4));
    }

    #[test]
    fn multiset_difference_ignores_order() {
        assert!(multiset_diff(&[3, 1, 2], &[2, 3, 1]).is_empty());
        assert_eq!(multiset_diff(&[1, 1, 2], &[2, 5]), vec![(1, 2), (5, -1)]);
    }

    fn small_setup(bits: u32, fb_size: usize, seed: u64) -> (Instance, FactorBase) {
        let inst = generate_instance(bits, seed);
        let fb = FactorBase::build(&inst.curve, fb_size);
        (inst, fb)
    }

    #[test]
    fn every_strategy_recovers_the_planted_logarithm() {
        let (inst, fb) = small_setup(18, 24, 11);
        for strategy in Strategy::ALL {
            let opts = WalkOptions {
                k: 3,
                max_ops: 1 << 26,
                seed: 5,
                ..WalkOptions::default()
            };
            let rep = run_strategy(&inst, &fb, strategy, &opts);
            assert!(
                rep.solved,
                "{} did not solve within budget: {rep:?}",
                rep.strategy
            );
            assert_eq!(
                rep.correct,
                Some(true),
                "{} recovered the wrong d",
                rep.strategy
            );
            assert_eq!(rep.relations_failed_verification, 0);
            assert!(rep.relations_independent >= 1);
            assert!(rep.total_ops >= rep.setup_ops + rep.replay_ops + rep.verify_ops);
        }
    }

    #[test]
    fn collision_preserving_walks_work_with_distinguished_points() {
        let (inst, fb) = small_setup(18, 16, 13);
        for strategy in [
            Strategy::RAddingResidualWalk,
            Strategy::FreshHashWalk,
            Strategy::PlainRho,
        ] {
            let opts = WalkOptions {
                k: 2,
                dp_bits: 3,
                max_ops: 1 << 26,
                seed: 9,
                ..WalkOptions::default()
            };
            let rep = run_strategy(&inst, &fb, strategy, &opts);
            assert_eq!(
                rep.correct,
                Some(true),
                "{} with DPs failed: {rep:?}",
                rep.strategy
            );
            assert!(
                rep.table_entries * 4 < rep.samples as usize,
                "DP storage should be sparse"
            );
            // Merged walks must be resolved to their merge point, not
            // reported as a trivial collision of identical states.
            assert_eq!(
                rep.collisions_trivial, 0,
                "{} with DPs: {rep:?}",
                rep.strategy
            );
            assert_eq!(rep.relations_failed_verification, 0);
            let full = run_strategy(
                &inst,
                &fb,
                strategy,
                &WalkOptions {
                    dp_bits: 0,
                    ..opts.clone()
                },
            );
            assert!(
                rep.samples < 3 * full.samples + 1000,
                "{}: DP mode needed {} samples vs {} without DPs",
                rep.strategy,
                rep.samples,
                full.samples
            );
        }
    }

    #[test]
    #[should_panic(expected = "collision-preserving")]
    fn distinguished_points_are_rejected_for_independent_sampling() {
        let (inst, fb) = small_setup(14, 8, 1);
        let opts = WalkOptions {
            dp_bits: 2,
            ..WalkOptions::default()
        };
        run_strategy(&inst, &fb, Strategy::IndependentSamples, &opts);
    }

    #[test]
    fn residual_walk_is_collision_preserving() {
        // Two walks whose starting residuals coincide (a + b·d ≡ a' + b'·d)
        // must produce identical residual sequences.
        let (inst, fb) = small_setup(16, 8, 21);
        let n = inst.curve.n;
        let mut rng = StdRng::seed_from_u64(3);
        let mults: Vec<Multiplier> = (0..fb.len())
            .map(|j| {
                let alpha = rng.gen_range(0..n);
                let beta = rng.gen_range(1..n);
                let pt = inst
                    .curve
                    .sub(&inst.curve.combine(&inst.q, alpha, beta), &fb.points[j]);
                Multiplier {
                    alpha,
                    beta,
                    fb_index: Some(j),
                    pt,
                }
            })
            .collect();
        let (a, b) = (123u64 % n, 45u64 % n);
        let b2 = 46u64 % n;
        // a + b d = a2 + b2 d  ⇒  a2 = a + (b − b2) d = a − d.
        let a2 = sub_mod(a, inst.d % n, n);
        let walk = RAddingWalk {
            inst: &inst,
            mults,
            starts: vec![(a, b), (a2, b2)],
        };
        let p0 = walk.replay(0, 0);
        let p1 = walk.replay(1, 0);
        assert_eq!(p0.residual, p1.residual);
        let p0 = walk.replay(0, 50);
        let p1 = walk.replay(1, 50);
        assert_eq!(p0.residual, p1.residual);
        assert_eq!(p0.counts, p1.counts);
        let rel = walk.relation(&p0, &p1);
        assert_eq!(rel.kind(), CollisionKind::Direct);
        assert!(rel.verify(&inst, &fb));

        // The fresh-hash map is a function of the residual alone.
        let s = DecompState::from_residual(&p0.residual, n, fb.len(), 3);
        let s2 = DecompState::from_residual(&p1.residual, n, fb.len(), 3);
        assert_eq!(s, s2);
    }

    #[test]
    fn reordered_tuples_are_trivial_collisions() {
        let s1 = DecompState {
            a: 5,
            b: 7,
            tuple: vec![2, 9, 4],
            minus: vec![],
        }
        .canonical();
        let s2 = DecompState {
            a: 5,
            b: 7,
            tuple: vec![9, 4, 2],
            minus: vec![],
        }
        .canonical();
        assert_eq!(s1, s2);
        assert_eq!(s1.relation_to(&s2, 101).kind(), CollisionKind::Trivial);
        let s3 = DecompState {
            a: 6,
            b: 7,
            tuple: vec![9, 4, 2],
            minus: vec![],
        }
        .canonical();
        assert_eq!(s1.relation_to(&s3, 101).kind(), CollisionKind::Direct);
        let s4 = DecompState {
            a: 5,
            b: 7,
            tuple: vec![9, 4, 3],
            minus: vec![],
        }
        .canonical();
        assert_eq!(
            s1.relation_to(&s4, 101).kind(),
            CollisionKind::FactorBaseOnly
        );
    }

    #[test]
    fn radding_rank_is_capped_by_the_number_of_multipliers() {
        // With r < B multipliers every relation lies in the span of the
        // r update vectors (plus the d column), so the rank can never
        // exceed r + 1 however long the walk runs.  Since those r + 1
        // dimensions include d, the walk is just Pollard rho whose r
        // multiplier logarithms happen to be unknown: d is determined
        // after r + 1 independent relations and never needs more.
        let (inst, fb) = small_setup(16, 32, 8);
        let opts = WalkOptions {
            multipliers: 6,
            max_ops: 1 << 22,
            seed: 2,
            stop_when_solved: false,
            ..WalkOptions::default()
        };
        let rep = run_strategy(&inst, &fb, Strategy::RAddingResidualWalk, &opts);
        // Complete decompositions (residual ∈ ±F, probability 2B/n per
        // step — frequent on a 16-bit toy, negligible at scale) are the
        // only other source of directions, one each at most.
        let cap = 7 + rep.full_decompositions as usize;
        assert!(
            rep.rank <= cap,
            "rank {} exceeds r + 1 + full hits = {cap}",
            rep.rank
        );
        assert_eq!(rep.correct, Some(true));
        assert!(rep.relations_independent <= cap as u64);
        assert!(
            rep.relations_verified > 7,
            "should have kept collecting: {rep:?}"
        );
        assert!(rep.relations_dependent > 0);
        assert!(rep.ops_at_solve.unwrap() < rep.total_ops);
    }

    #[test]
    fn filtering_residuals_only_costs_samples() {
        let (inst, fb) = small_setup(16, 16, 4);
        let unfiltered = run_strategy(
            &inst,
            &fb,
            Strategy::IndependentSamples,
            &WalkOptions {
                max_ops: 1 << 24,
                seed: 6,
                ..WalkOptions::default()
            },
        );
        let filtered = run_strategy(
            &inst,
            &fb,
            Strategy::IndependentSamples,
            &WalkOptions {
                max_ops: 1 << 24,
                seed: 6,
                filter_bound: Some(inst.curve.p / 8),
                ..WalkOptions::default()
            },
        );
        assert_eq!(unfiltered.correct, Some(true));
        assert_eq!(filtered.correct, Some(true));
        assert!(filtered.accepted < filtered.samples / 4);
        assert!(filtered.samples > unfiltered.samples);
    }

    #[test]
    fn generic_levers_recover_the_planted_logarithm() {
        // Negation map on every strategy, the difference table on the
        // local-mutation walk, segmented walks on the r-adding ones.
        let (inst, fb) = small_setup(18, 24, 31);
        for strategy in Strategy::ALL {
            let opts = WalkOptions {
                k: 3,
                max_ops: 1 << 26,
                seed: 7,
                negation_map: true,
                diff_table: true,
                segment_len: 300,
                continue_after_collision: true,
                ..WalkOptions::default()
            };
            let rep = run_strategy(&inst, &fb, strategy, &opts);
            assert_eq!(
                rep.correct,
                Some(true),
                "{} with levers failed: {rep:?}",
                rep.strategy
            );
            if strategy == Strategy::LocalMutationWalk {
                assert_eq!(rep.walks, 1, "a continuing mutation walk never restarts");
            }
            assert_eq!(rep.relations_failed_verification, 0, "{}", rep.strategy);
            assert!(rep.negation_map && rep.diff_table && rep.segment_len == 300);
        }
        // The difference table is paid for in setup and shows up as fewer
        // walk operations per residual.
        let plain = run_strategy(
            &inst,
            &fb,
            Strategy::LocalMutationWalk,
            &WalkOptions {
                seed: 7,
                ..WalkOptions::default()
            },
        );
        let tabled = run_strategy(
            &inst,
            &fb,
            Strategy::LocalMutationWalk,
            &WalkOptions {
                seed: 7,
                diff_table: true,
                ..WalkOptions::default()
            },
        );
        assert_eq!(tabled.setup_ops as usize, fb.len() * (fb.len() - 1) / 2);
        let per_residual = |r: &StrategyReport| r.walk_ops as f64 / (r.samples as f64);
        assert!(per_residual(&tabled) < per_residual(&plain));
    }

    #[test]
    fn negation_class_is_consistent() {
        let inst = generate_instance(16, 2);
        let c = &inst.curve;
        let pt = c.mul(&c.g, 12345);
        let (k1, f1) = fold(&inst, Fold::Negation, &pt);
        let (k2, f2) = fold(&inst, Fold::Negation, &c.neg(&pt));
        assert_eq!(k1, k2);
        assert_eq!(add_mod(f1, f2, c.n), 0);
        assert_eq!(c.mul(&k1, f1), pt);
        // Signed relations from mirrored states verify by arithmetic.
        let fb = FactorBase::build(c, 8);
        let s = DecompState {
            a: 5,
            b: 9,
            tuple: vec![1, 3, 3],
            minus: vec![6],
        };
        let t = DecompState {
            a: 11,
            b: 2,
            tuple: vec![0, 4, 7],
            minus: vec![],
        };
        // The scaled relation f'·L(s) − f·L(t) must evaluate, by group
        // arithmetic, to f'·L(s) − f·L(t) for arbitrary factors.
        let combo = |rel: &Relation| {
            let mut acc = c.combine(&inst.q, rel.da, rel.db);
            for &(i, coef) in &rel.coeffs {
                acc = c.sub(&acc, &c.mul_signed(&fb.points[i], coef));
            }
            acc
        };
        let (ls, lt) = (s.residual(&inst, &fb), t.residual(&inst, &fb));
        let rel = s.relation_scaled(1, &t, c.n - 1, c.n);
        assert_eq!(combo(&rel), c.sub(&c.mul(&ls, c.n - 1), &lt));
        let (f, ft) = (777u64, 12_345u64);
        let rel = s.relation_scaled(f, &t, ft, c.n);
        assert_eq!(combo(&rel), c.sub(&c.mul(&ls, ft), &c.mul(&lt, f)));
    }

    #[test]
    fn j0_instance_has_a_matching_automorphism() {
        let inst = generate_j0_instance(18, 4);
        let c = &inst.curve;
        let aut = inst.aut.unwrap();
        assert_eq!(c.a, 0);
        assert_eq!(c.p % 3, 1);
        assert_eq!(c.n % 3, 1);
        assert!(is_prime_u64(c.n));
        assert_eq!(pow_mod(aut.omega, 3, c.p), 1);
        assert_ne!(aut.omega, 1);
        let l2 = mul_mod(aut.lambda, aut.lambda, c.n);
        assert_eq!(add_mod(add_mod(l2, aut.lambda, c.n), 1, c.n), 0);
        for k in [1u64, 2, 999, 123_456] {
            let pt = c.mul(&c.g, k);
            assert_eq!(c.mul(&pt, aut.lambda), inst.zeta(&pt));
            // Every point of the orbit folds to the same representative
            // with a factor that reproduces the point.
            let (canon, _) = fold(&inst, Fold::Automorphism, &pt);
            let mut img = pt;
            for _ in 0..3 {
                for q in [img, c.neg(&img)] {
                    let (cq, fq) = fold(&inst, Fold::Automorphism, &q);
                    assert_eq!(cq, canon);
                    assert_eq!(c.mul(&cq, fq), q);
                }
                img = inst.zeta(&img);
            }
        }
        let fb = FactorBase::build_orbit_reps(&inst, 12);
        assert_eq!(fb.len(), 12);
        for pt in &fb.points {
            assert_eq!(fold(&inst, Fold::Automorphism, pt).0, *pt);
        }
    }

    #[test]
    fn automorphism_folding_recovers_the_planted_logarithm() {
        let inst = generate_j0_instance(18, 9);
        let fb = FactorBase::build_orbit_reps(&inst, 24);
        for strategy in Strategy::ALL {
            let opts = WalkOptions {
                k: 3,
                max_ops: 1 << 26,
                seed: 3,
                use_automorphism: true,
                diff_table: true,
                segment_len: 300,
                continue_after_collision: true,
                ..WalkOptions::default()
            };
            let rep = run_strategy(&inst, &fb, strategy, &opts);
            assert_eq!(
                rep.correct,
                Some(true),
                "{} folded failed: {rep:?}",
                rep.strategy
            );
            assert_eq!(rep.relations_failed_verification, 0, "{}", rep.strategy);
            assert_eq!(rep.fold_order, 6);
            assert!(rep.j_zero);
        }
    }

    #[test]
    fn s3_quadratic_matches_the_crate_and_vanishes_on_sums() {
        // Coefficients against the BigUint implementation on the shared
        // toy curve y² = x³ + 2x + 3 over F_271.
        let curve = Curve::new(271, 2, 3, 0, Pt::INFINITY);
        let p = BigUint::from(271u32);
        let fe = |v: u64| FieldElement::new(BigUint::from(v), p.clone());
        for (x1, x2) in [(10u64, 17u64), (3, 200), (100, 101)] {
            let (a, b, c) = s3_in_x3(&curve, x1, x2);
            let (ba, bb, bc) = crate::cryptanalysis::ec_index_calculus::semaev_s3_in_x3(
                &fe(x1),
                &fe(x2),
                &fe(2),
                &fe(3),
            );
            assert_eq!(BigUint::from(a), ba.value);
            assert_eq!(BigUint::from(b), bb.value);
            assert_eq!(BigUint::from(c), bc.value);
        }
        // S₃(x_P, x_Q, x_{P±Q}) = 0 on a random instance.
        let inst = generate_instance(20, 5);
        let c = &inst.curve;
        for (u, v) in [(3u64, 77u64), (1234, 5678), (99_991, 7)] {
            let pu = c.mul(&c.g, u);
            let pv = c.mul(&c.g, v);
            let (a, b, cc) = s3_in_x3(c, pu.x, pv.x);
            for x in [c.add(&pu, &pv).x, c.sub(&pu, &pv).x] {
                let val = add_mod(
                    add_mod(mul_mod(a, mul_mod(x, x, c.p), c.p), mul_mod(b, x, c.p), c.p),
                    cc,
                    c.p,
                );
                assert_eq!(val, 0);
            }
        }
    }

    #[test]
    fn s3_oracle_agrees_with_brute_force_pairs() {
        let inst = generate_instance(18, 21);
        let c = &inst.curve;
        let fb = FactorBase::build(c, 24);
        let brute = |l: &Pt| {
            let mut out = Vec::new();
            for i in 0..fb.len() {
                for j in i..fb.len() {
                    for s_i in [1i64, -1] {
                        for s_j in [1i64, -1] {
                            let pt = c.add(
                                &c.mul_signed(&fb.points[i], s_i),
                                &c.mul_signed(&fb.points[j], s_j),
                            );
                            if pt == *l && !(i == j && s_i + s_j == 0) {
                                let terms = if i == j {
                                    vec![(i, s_i + s_j)]
                                } else {
                                    vec![(i, s_i), (j, s_j)]
                                };
                                out.push(terms);
                            }
                        }
                    }
                }
            }
            out.sort();
            out.dedup();
            out
        };
        let mut targets: Vec<Pt> = vec![
            c.add(&fb.points[2], &fb.points[9]),
            c.sub(&fb.points[5], &fb.points[17]),
            c.double(&fb.points[7]),
            c.mul(&c.g, 424_242),
        ];
        for k in 1..40u64 {
            targets.push(c.mul(&c.g, k * 7919));
        }
        let mut hits = 0;
        for l in &targets {
            let (oracle, solves) = s3_pair_oracle(&inst, &fb, l);
            assert_eq!(
                oracle,
                brute(l),
                "oracle disagrees with brute force at {l:?}"
            );
            assert!(solves <= fb.len() as u64);
            hits += oracle.len();
        }
        assert!(hits >= 3, "the constructed targets must be found");
    }

    #[test]
    fn s4_oracle_agrees_with_brute_force_triples() {
        let inst = generate_instance(18, 23);
        let c = &inst.curve;
        let fb = FactorBase::build(c, 12);
        let brute = |l: &Pt| {
            let mut out = Vec::new();
            for i in 0..fb.len() {
                for j in (i + 1)..fb.len() {
                    for k in (j + 1)..fb.len() {
                        for s_i in [1i64, -1] {
                            for s_j in [1i64, -1] {
                                for s_k in [1i64, -1] {
                                    let pt = c.add(
                                        &c.add(
                                            &c.mul_signed(&fb.points[i], s_i),
                                            &c.mul_signed(&fb.points[j], s_j),
                                        ),
                                        &c.mul_signed(&fb.points[k], s_k),
                                    );
                                    if pt == *l {
                                        out.push(vec![(i, s_i), (j, s_j), (k, s_k)]);
                                    }
                                }
                            }
                        }
                    }
                }
            }
            out.sort();
            out.dedup();
            out
        };
        let mut targets = vec![
            c.add(&c.add(&fb.points[1], &fb.points[5]), &c.neg(&fb.points[9])),
            c.sub(&c.sub(&fb.points[0], &fb.points[3]), &fb.points[11]),
            c.add(&c.add(&fb.points[2], &fb.points[7]), &fb.points[8]),
        ];
        for k in 1..25u64 {
            targets.push(c.mul(&c.g, k * 104_729));
        }
        let mut hits = 0;
        for l in &targets {
            let (oracle, solves) = s4_triple_oracle(&inst, &fb, l);
            assert_eq!(
                oracle,
                brute(l),
                "S4 oracle disagrees with brute force at {l:?}"
            );
            assert!(solves <= (fb.len() * fb.len()) as u64);
            hits += oracle.len();
        }
        assert!(hits >= 3);
    }

    #[test]
    fn s4_and_mitm_runs_solve_and_are_charged() {
        let (inst, fb) = small_setup(18, 16, 14);
        let s4 = run_strategy(
            &inst,
            &fb,
            Strategy::LocalMutationWalk,
            &WalkOptions {
                k: 3,
                max_ops: 1 << 30,
                seed: 5,
                negation_map: true,
                s4_oracle: true,
                ..WalkOptions::default()
            },
        );
        assert_eq!(s4.correct, Some(true), "{s4:?}");
        assert_eq!(s4.relations_failed_verification, 0);
        assert!(s4.oracle_ops >= s4.samples * 100);
        let mitm = run_strategy(
            &inst,
            &fb,
            Strategy::LocalMutationWalk,
            &WalkOptions {
                k: 3,
                max_ops: 1 << 30,
                seed: 5,
                negation_map: true,
                seed_pairs: true,
                mitm_neighbours: true,
                ..WalkOptions::default()
            },
        );
        assert_eq!(mitm.correct, Some(true), "{mitm:?}");
        assert_eq!(mitm.relations_failed_verification, 0);
        // Two group operations per factor-base point per residual.
        assert!(mitm.oracle_ops >= mitm.samples * 2 * fb.len() as u64);
        assert!(mitm.total_ops >= mitm.oracle_ops + mitm.setup_ops);
    }

    #[test]
    fn s3_oracle_run_solves_and_is_charged() {
        let (inst, fb) = small_setup(18, 24, 12);
        let opts = WalkOptions {
            k: 3,
            max_ops: 1 << 28,
            seed: 5,
            negation_map: true,
            s3_oracle: true,
            ..WalkOptions::default()
        };
        let rep = run_strategy(&inst, &fb, Strategy::LocalMutationWalk, &opts);
        assert_eq!(rep.correct, Some(true), "{rep:?}");
        assert_eq!(rep.relations_failed_verification, 0);
        assert!(rep.s3_oracle);
        assert!(rep.oracle_ops >= rep.samples * (fb.len() as u64 - 1));
        assert!(rep.total_ops >= rep.oracle_ops);
    }

    #[test]
    fn seeded_pairs_count_and_solve() {
        let (inst, fb) = small_setup(18, 24, 12);
        let opts = WalkOptions {
            k: 3,
            max_ops: 1 << 26,
            seed: 5,
            negation_map: true,
            seed_pairs: true,
            ..WalkOptions::default()
        };
        let rep = run_strategy(&inst, &fb, Strategy::LocalMutationWalk, &opts);
        assert_eq!(rep.correct, Some(true), "{rep:?}");
        assert_eq!(rep.relations_failed_verification, 0);
        // 24·23/2 pairs, two classes each under the negation map (minus
        // any coincidences already present).
        assert!(rep.seeded_points as usize <= 24 * 23);
        assert!(rep.seeded_points as usize > 24 * 23 - 24);
        assert_eq!(rep.setup_ops as usize, 24 * 23);
    }

    #[test]
    fn mitm_finds_weight_four_relations() {
        let inst = generate_instance(18, 17);
        let bsize = ((4.0 * inst.curve.n as f64).powf(0.25).ceil() as usize).max(8) * 2;
        let fb = FactorBase::build(&inst.curve, bsize);
        let rep = mitm_four_decomposition(&inst, &fb, 2000, 1);
        assert!(rep.relations_verified > 0);
        assert_eq!(rep.correct, Some(true), "{rep:?}");
    }
}
