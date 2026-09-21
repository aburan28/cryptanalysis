//! # Fast factor-base decomposition for binary Semaev `S₄`.
//!
//! The question an index-calculus run asks over and over: given a
//! target x-coordinate `x_R`, are there three factor-base elements
//! `X₁, X₂, X₃` with `S₄(X₁, X₂, X₃, x_R) = 0`?  Almost all of an
//! attack's time goes here, and almost all of *that* on the `~5/6` of
//! targets that do not decompose.
//!
//! # Don't enumerate triples
//!
//! The obvious method walks every sorted triple of the factor base —
//! `2^{3l}/3!` of them — and evaluates.  That is what
//! [`crate::cryptanalysis::semaev_corpus::CorpusInstance::decide_exhaustively`]
//! does, and what the SAT solver turns out to do as well (one conflict
//! per triple; see `research/notes/index-calculus/RESEARCH_SAT_SEMAEV.md`).
//!
//! But `S₄` is a *quartic in its last argument*.  Fix `X₁` and `X₂`
//! and it becomes a degree-4 polynomial in `X₃`, whose roots are the
//! only candidates worth considering.  So loop over **pairs**, not
//! triples, and solve for the third point:
//!
//! ```text
//!   for each pair (X₁ ≤ X₂):          2^{2l}/2 of them
//!       build the quartic in X₃
//!       find its roots that lie in the factor base
//! ```
//!
//! Finding those roots is the part that has to be cheap, and it is:
//! the factor base is an `F₂`-subspace `V`, so
//! `L_V(t) = Π_{v ∈ V}(t + v)` is a **linearized** polynomial,
//! `Σ aᵢ t^{2^i}`, with only `l + 1` coefficients despite having degree
//! `2^l`.  Reducing it modulo the quartic costs `l` squarings of a
//! degree-3 polynomial, and `gcd(quartic, L_V mod quartic)` then has
//! exactly the subspace roots as its roots.  No search over `V`.
//!
//! Per pair that is `O(l)` field operations instead of `2^l`
//! evaluations, so the saving grows like `2^l / l` — a constant factor
//! at `l = 5` and orders of magnitude by `l = 12`, which is where
//! enumeration stops being possible at all.
//!
//! # Where the time goes, and what was done about it
//!
//! Pairs-and-solve only pays off if a pair costs a few hundred field
//! operations rather than a few thousand.  Three things stood between
//! the first working version (28 µs per pair) and the current one
//! (about 1 µs):
//!
//! - **Inversions.**  A textbook polynomial remainder divides by the
//!   divisor's leading coefficient, and at `n = 24` one field inversion
//!   costs about fifty multiplications.  A single pair ran thirteen of
//!   them.  Now the modulus is made monic once — for a whole *row* of
//!   the pair loop at a time, by [`Gf2::batch_inv`] — and the gcd uses
//!   pseudo-remainders, which scale the dividend up instead of scaling
//!   the divisor down.  One inversion per row, none per pair.
//! - **The multiply itself.**  The schoolbook shift-and-xor loop runs
//!   `n` iterations with two unpredictable branches in each.  [`Gf2`]
//!   uses a carry-less multiply and folds the result down through a
//!   byte-indexed reduction table; squaring skips the multiply
//!   altogether, since in characteristic 2 it is bit-spreading.
//! - **Branches in straight-line code.**  Zero-operand early-outs and
//!   a "while the high part is non-zero" reduction loop both cost more
//!   in mispredictions than the work they skip.
//!
//! The general [`crate::binary_ecc::F2mElement`] is `Vec<u64>`-backed
//! and allocates twice per multiplication, which for a single-word
//! field costs about a hundred times what the arithmetic does; that is
//! why this module has its own field rather than reusing it.
//!
//! # This does not rescue index calculus
//!
//! Worth being explicit, because the speedups are large enough to be
//! misleading.  Collecting relations needs `2^l` of them; a random
//! target decomposes with probability `2^{3l−n}/3!`, so it takes
//! `3!·2^{n−3l}` targets per relation; and each target costs `Θ(2^{2l})`
//! here.  Multiply:
//!
//! ```text
//!   2^l · 3!·2^{n−3l} · Θ(2^{2l}) = Θ(2^n)
//! ```
//!
//! — **independent of `l`**.  A larger factor base needs fewer tries but
//! makes each try proportionally more expensive, and the two cancel
//! exactly.  Any oracle built on enumerating the factor base sits at
//! `2^n`, against `2^{n/2}` for Pollard rho, however fast its inner
//! loop.  `examples/semaev_decomp_bench.rs` measures this directly: the
//! projected relation-collection cost divided by `2^n` is flat across
//! the ladder.
//!
//! What the speed buys is not a better attack but a usable experiment.
//! Deciding a target at `l = 12` took hours by enumeration and takes
//! seconds here, which is the range where a genuinely sub-`2^{2l}`
//! oracle — the only thing that would change the conclusion — could be
//! tested.
//!
//! # References
//!
//! - **P. Gaudry**, *Index calculus for abelian varieties of small
//!   dimension and the elliptic curve discrete logarithm problem*,
//!   J. Symbolic Computation 2009 — the pairs-and-solve structure.
//! - **C. Diem**, *On the discrete logarithm problem in elliptic curves*,
//!   2011 — factor bases as subspaces.
//! - **R. Lidl, H. Niederreiter**, *Finite Fields*, §3.4 — linearized
//!   polynomials and subspace polynomials.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};

/// Highest polynomial degree the fixed-size helpers handle.  The
/// quartic is degree 4 and squaring one of its remainders reaches 6,
/// which is the most anything here needs.
const MAX_DEG: usize = 6;

/// A binary field `F_{2ⁿ}` for `n ≤ 63`, one `u64` per element.
///
/// The two things that make it fast:
///
/// - **Carry-less multiply.**  `a·b` is one `pclmulqdq` producing the
///   unreduced 128-bit product, where the textbook shift-and-xor loop
///   runs `n` iterations with two unpredictable branches in each.
///   A scalar carry-less loop stands in where the instruction is
///   unavailable.
/// - **Table reduction.**  Folding the high half back down uses a
///   byte-indexed table of `z^{n+8j} · v mod irr`, so reduction is
///   `⌈(n−1)/8⌉` lookups rather than `n` conditional shifts.
///
/// Squaring skips the multiply entirely: in characteristic 2 it is the
/// `F₂`-linear bit-spreading `Σ aᵢ zⁱ ↦ Σ aᵢ z^{2i}`, then the same
/// reduction.
#[derive(Clone, Debug)]
pub struct Gf2 {
    pub n: u32,
    /// The irreducible polynomial including its leading `z^n` bit.
    pub irr: u64,
    pub(crate) mask: u64,
    /// `red[j][v] = (v · z^{n + 8j}) mod irr`, flattened.
    red: Vec<u64>,
    positions: usize,
    has_clmul: bool,
}

/// Spread the low 32 bits of `x` so that bit `i` lands at bit `2i`.
#[inline(always)]
fn spread32(x: u64) -> u64 {
    let mut x = x & 0xFFFF_FFFF;
    x = (x | (x << 16)) & 0x0000_FFFF_0000_FFFF;
    x = (x | (x << 8)) & 0x00FF_00FF_00FF_00FF;
    x = (x | (x << 4)) & 0x0F0F_0F0F_0F0F_0F0F;
    x = (x | (x << 2)) & 0x3333_3333_3333_3333;
    x = (x | (x << 1)) & 0x5555_5555_5555_5555;
    x
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "pclmulqdq")]
unsafe fn clmul_u64(a: u64, b: u64) -> u128 {
    use std::arch::x86_64::*;
    let x = _mm_set_epi64x(0, a as i64);
    let y = _mm_set_epi64x(0, b as i64);
    let z = _mm_clmulepi64_si128::<0x00>(x, y);
    let lo = _mm_cvtsi128_si64(z) as u64;
    let hi = _mm_cvtsi128_si64(_mm_srli_si128::<8>(z)) as u64;
    ((hi as u128) << 64) | (lo as u128)
}

impl Gf2 {
    pub fn new(irr: &IrreduciblePoly) -> Self {
        assert!(irr.degree <= 63, "Gf2 handles n ≤ 63");
        let n = irr.degree;
        let bits = irr
            .low_terms
            .iter()
            .fold(1u64 << n, |acc, &t| acc | (1u64 << t));

        // `pow[i] = z^{n+i} mod irr`, enough of them to cover the
        // `n − 1` high bits a product of two field elements can have.
        let positions = (n as usize - 1).div_ceil(8);
        let positions = positions.max(1);
        let mut pow = vec![0u64; positions * 8];
        let mut cur = bits ^ (1u64 << n); // z^n ≡ the low terms
        for slot in pow.iter_mut() {
            *slot = cur;
            cur <<= 1;
            if (cur >> n) & 1 != 0 {
                cur ^= bits;
            }
        }

        let mut red = vec![0u64; positions * 256];
        for j in 0..positions {
            for v in 1usize..256 {
                red[j * 256 + v] =
                    red[j * 256 + (v & (v - 1))] ^ pow[j * 8 + v.trailing_zeros() as usize];
            }
        }

        #[cfg(target_arch = "x86_64")]
        let has_clmul = std::arch::is_x86_feature_detected!("pclmulqdq");
        #[cfg(not(target_arch = "x86_64"))]
        let has_clmul = false;

        Self {
            n,
            irr: bits,
            mask: (1u64 << n) - 1,
            red,
            positions,
            has_clmul,
        }
    }

    /// Fold a `< 2^{2n−1}` carry-less product back into the field.
    ///
    /// The trip count is fixed at `positions` rather than "while the
    /// high part is non-zero": a data-dependent exit here is a branch
    /// the predictor cannot learn, and costs more than the one or two
    /// redundant lookups it saves.
    #[inline(always)]
    fn reduce(&self, w: u128) -> u64 {
        let mut acc = (w as u64) & self.mask;
        let mut h = (w >> self.n) as u64;
        for j in 0..self.positions {
            acc ^= self.red[j * 256 + (h & 0xff) as usize];
            h >>= 8;
        }
        debug_assert_eq!(h, 0, "product wider than the reduction table");
        acc
    }

    #[inline(always)]
    fn clmul(&self, a: u64, b: u64) -> u128 {
        #[cfg(target_arch = "x86_64")]
        if self.has_clmul {
            // SAFETY: guarded by the runtime feature detection recorded
            // in `has_clmul` at construction.
            return unsafe { clmul_u64(a, b) };
        }
        let mut w = 0u128;
        let mut aa = a as u128;
        let mut bb = b;
        while bb != 0 {
            if bb & 1 != 0 {
                w ^= aa;
            }
            aa <<= 1;
            bb >>= 1;
        }
        w
    }

    /// No early-out on a zero operand: `clmul` handles it correctly and
    /// the branch would be unpredictable, which costs more than the
    /// multiply it skips.
    #[inline]
    pub fn mul(&self, a: u64, b: u64) -> u64 {
        self.reduce(self.clmul(a, b))
    }

    #[inline]
    pub fn sqr(&self, a: u64) -> u64 {
        let w = (spread32(a) as u128) | ((spread32(a >> 32) as u128) << 64);
        self.reduce(w)
    }

    /// `a^(2^k)`.
    pub fn sqr_k(&self, mut a: u64, k: u32) -> u64 {
        for _ in 0..k {
            a = self.sqr(a);
        }
        a
    }

    /// `a^{-1}` by Fermat: `a^(2^n − 2)`.  Zero maps to zero.
    ///
    /// Still `n` squarings and `n` multiplications — which is why the
    /// code above it goes to some length to need only one per *row* of
    /// the pair loop rather than one per polynomial division.
    pub fn inv(&self, a: u64) -> u64 {
        if a == 0 {
            return 0;
        }
        let mut result = 1u64;
        let mut base = a;
        for _ in 1..self.n {
            base = self.sqr(base);
            result = if result == 1 {
                base
            } else {
                self.mul(result, base)
            };
        }
        result
    }

    /// Invert a whole slice with **one** field inversion, by
    /// Montgomery's trick: accumulate the running product, invert once,
    /// then walk back peeling off one factor at a time.  Costs
    /// `3(k − 1)` multiplications plus a single inversion for `k`
    /// elements, so the inversion's cost per element goes to zero.
    ///
    /// Zeros are left as zero and skipped.
    pub fn batch_inv(&self, xs: &mut [u64], scratch: &mut Vec<u64>) {
        scratch.clear();
        scratch.reserve(xs.len());
        let mut acc = 1u64;
        for &x in xs.iter() {
            scratch.push(acc);
            if x != 0 {
                acc = self.mul(acc, x);
            }
        }
        let mut inv_acc = self.inv(acc);
        for i in (0..xs.len()).rev() {
            if xs[i] != 0 {
                let xi = xs[i];
                xs[i] = self.mul(inv_acc, scratch[i]);
                inv_acc = self.mul(inv_acc, xi);
            }
        }
    }

    /// Lift to the crate's general element type.
    pub fn to_element(&self, a: u64) -> F2mElement {
        let bits: Vec<u32> = (0..self.n).filter(|i| (a >> i) & 1 == 1).collect();
        F2mElement::from_bit_positions(&bits, self.n)
    }

    /// Project a general element down, assuming it fits.
    pub fn from_element(&self, e: &F2mElement) -> u64 {
        let raw = e.raw_bits();
        raw.first().copied().unwrap_or(0) & self.mask
    }
}

// ── Polynomials over F_{2ⁿ}, degree ≤ MAX_DEG ───────────────────────

/// Coefficients low-to-high; `deg` is the index of the highest
/// non-zero one, or `None` for the zero polynomial.
///
/// Every routine here is written to avoid field inversions, because at
/// `n = 24` one inversion costs about as much as fifty multiplications.
/// Division by a leading coefficient is either arranged away (the
/// modulus is made monic once, in a batch) or replaced by a
/// pseudo-remainder, which scales the dividend up instead of scaling
/// the divisor down.  Pseudo-remainders change a gcd by a non-zero
/// scalar, which changes neither its degree nor its roots.
#[derive(Clone, Copy, Debug)]
pub struct Poly {
    pub c: [u64; MAX_DEG + 1],
}

impl Poly {
    pub fn zero() -> Self {
        Self {
            c: [0; MAX_DEG + 1],
        }
    }

    pub fn deg(&self) -> Option<usize> {
        (0..=MAX_DEG).rev().find(|&i| self.c[i] != 0)
    }

    pub fn is_zero(&self) -> bool {
        self.deg().is_none()
    }

    /// Multiply coefficients `0..=hi` by `k`, in place.  Callers pass
    /// the live degree so the dead tail costs nothing.
    fn scale_in_place(&mut self, k: u64, hi: usize, gf: &Gf2) {
        for i in 0..=hi {
            self.c[i] = gf.mul(self.c[i], k);
        }
    }

    /// Remainder modulo a **monic** `m` of degree `dm`.  No inversion:
    /// the leading coefficient is one, so each elimination step is a
    /// scale-and-subtract by the coefficient being cleared.
    fn rem_monic(&self, m: &Self, dm: usize, gf: &Gf2) -> Self {
        let mut r = *self;
        let mut dr = MAX_DEG;
        loop {
            while r.c[dr] == 0 {
                if dr == 0 || dr == dm {
                    return r;
                }
                dr -= 1;
            }
            if dr < dm {
                return r;
            }
            let factor = r.c[dr];
            for i in 0..dm {
                r.c[dr - dm + i] ^= gf.mul(m.c[i], factor);
            }
            r.c[dr] = 0;
            if dr == 0 {
                return r;
            }
            dr -= 1;
        }
    }

    /// `self²  mod m` for monic `m`, exploiting that squaring is
    /// `F₂`-linear: `(Σ cᵢ tⁱ)² = Σ cᵢ² t^{2i}`, so the wide product is
    /// four field squarings rather than a convolution.
    fn sqr_mod_monic(&self, m: &Self, dm: usize, gf: &Gf2) -> Self {
        let mut wide = Self::zero();
        for i in 0..=MAX_DEG / 2 {
            if self.c[i] != 0 {
                wide.c[2 * i] = gf.sqr(self.c[i]);
            }
        }
        wide.rem_monic(m, dm, gf)
    }

    /// Pseudo-remainder: the remainder of `lead(b)^k · self` by `b`,
    /// computed without ever inverting.  Used only inside [`Self::gcd`],
    /// where a scalar multiple is harmless.
    fn prem(&self, b: &Self, gf: &Gf2) -> Self {
        let db = match b.deg() {
            Some(d) => d,
            None => return *self,
        };
        let lb = b.c[db];
        let mut r = *self;
        while let Some(dr) = r.deg() {
            if dr < db {
                break;
            }
            let lr = r.c[dr];
            r.scale_in_place(lb, dr, gf);
            for i in 0..=db {
                r.c[dr - db + i] ^= gf.mul(b.c[i], lr);
            }
            r.c[dr] = 0;
        }
        r
    }

    /// Greatest common divisor **up to a non-zero scalar**, via
    /// pseudo-remainders.  Degree and root set are exact, which is all
    /// the caller uses.
    fn gcd(&self, other: &Self, gf: &Gf2) -> Self {
        let mut a = *self;
        let mut b = *other;
        loop {
            match b.deg() {
                None => return a,
                // A non-zero constant: the gcd is 1, and in this
                // application that is the overwhelmingly common case,
                // so returning here skips most of the Euclid steps.
                Some(0) => return b,
                Some(_) => {}
            }
            let r = a.prem(&b, gf);
            a = b;
            b = r;
        }
    }
}

// ── The subspace polynomial ─────────────────────────────────────────

/// Coefficients `a₀ … a_l` of the linearized polynomial
/// `L_V(t) = Σ aᵢ t^{2^i}` whose roots are exactly the `l`-dimensional
/// subspace `V = ⟨1, z, …, z^{l−1}⟩`.
///
/// Built one basis vector at a time from
/// `L_{i+1}(t) = L_i(t)² + L_i(b)·L_i(t)`, which holds because `L_i` is
/// additive: `Π_{v ∈ V_i ∪ (b + V_i)}(t + v) = L_i(t)·L_i(t + b)`.
pub fn subspace_poly(l: u32, gf: &Gf2) -> Vec<u64> {
    // L_0(t) = t.
    let mut a = vec![1u64];
    for i in 0..l {
        let b = 1u64 << i; // basis vector z^i
                           // L_i(b)
        let lb = a.iter().enumerate().fold(0u64, |acc, (j, &aj)| {
            acc ^ gf.mul(aj, gf.sqr_k(b, j as u32))
        });
        let mut next = vec![0u64; a.len() + 1];
        for (j, &aj) in a.iter().enumerate() {
            next[j + 1] ^= gf.sqr(aj); // from L_i(t)²
            next[j] ^= gf.mul(lb, aj); // from L_i(b)·L_i(t)
        }
        a = next;
    }
    a
}

/// `gcd(f, L_V mod f)` — a polynomial whose roots are exactly the
/// roots of monic `f` that lie in the subspace `V`.
///
/// `L_V` has degree `2^l` but only `l + 1` non-zero coefficients, so
/// reducing it costs `l` squarings of something no bigger than `f`.
/// That is the whole point: `O(l)` work per pair where evaluating over
/// the factor base would be `2^l`.
fn roots_in_subspace(f: &Poly, df: usize, lv: &[u64], gf: &Gf2) -> Poly {
    let mut t = Poly::zero();
    t.c[1] = 1; // t
    let mut acc = Poly::zero();
    let mut pow = t.rem_monic(f, df, gf); // t^(2^0) mod f
    for (i, &ai) in lv.iter().enumerate() {
        if ai != 0 {
            for j in 0..df.max(1) {
                acc.c[j] ^= gf.mul(pow.c[j], ai);
            }
        }
        if i + 1 < lv.len() {
            pow = pow.sqr_mod_monic(f, df, gf);
        }
    }
    f.gcd(&acc, gf)
}

// ── Semaev S₄ as a quartic in its last argument ─────────────────────

/// Powers of the target that every quartic needs.  Hoisted out of the
/// pair loop, where they would otherwise be recomputed `2^{2l}` times.
#[derive(Clone, Copy)]
struct TargetPowers {
    xr: u64,
    xr2: u64,
    xr3: u64,
    xr4: u64,
}

impl TargetPowers {
    fn new(xr: u64, gf: &Gf2) -> Self {
        let xr2 = gf.sqr(xr);
        Self {
            xr,
            xr2,
            xr3: gf.mul(xr2, xr),
            xr4: gf.sqr(xr2),
        }
    }
}

fn quartic_with(x1: u64, x2: u64, t: &TargetPowers, gf: &Gf2) -> Poly {
    let s = x1 ^ x2;
    let p = gf.mul(x1, x2);
    let (s2, p2) = (gf.sqr(s), gf.sqr(p));
    let (s4, p4) = (gf.sqr(s2), gf.sqr(p2));
    let p3 = gf.mul(p2, p);
    let p_s2 = gf.mul(p, s2);
    let p2_xr2 = gf.mul(p2, t.xr2);

    let mut q = Poly::zero();
    // constant: x_R⁴ + s⁴ + p⁴x_R⁴ + p²x_R²
    q.c[0] = t.xr4 ^ s4 ^ gf.mul(p4, t.xr4) ^ p2_xr2;
    // t: p³x_R³ + p·s²·x_R + p·x_R³
    q.c[1] = gf.mul(p3, t.xr3) ^ gf.mul(p_s2, t.xr) ^ gf.mul(p, t.xr3);
    // t²: p²s²x_R² + p²x_R⁴ + p² + s²x_R²
    q.c[2] = gf.mul(gf.mul(p2, s2), t.xr2) ^ gf.mul(p2, t.xr4) ^ p2 ^ gf.mul(s2, t.xr2);
    // t³: p³x_R + p·s²·x_R³ + p·x_R
    q.c[3] = gf.mul(p3, t.xr) ^ gf.mul(p_s2, t.xr3) ^ gf.mul(p, t.xr);
    // t⁴: 1 + p⁴ + s⁴x_R⁴ + p²x_R²
    q.c[4] = 1 ^ p4 ^ gf.mul(s4, t.xr4) ^ p2_xr2;
    q
}

/// Coefficients of `f₃(X₁, X₂, t, x_R)` as a polynomial in `t`, for
/// the Koblitz curve `y² + xy = x³ + x² + 1`.
///
/// Substituting `e₁ = s + t`, `e₂ = p + s·t`, `e₃ = p·t` with
/// `s = X₁ + X₂`, `p = X₁X₂` into the twelve-term symmetrised form and
/// collecting powers of `t`.  Squaring is linear in characteristic 2,
/// which is what keeps this a quartic rather than a mess.
pub fn quartic_in_x3(x1: u64, x2: u64, xr: u64, gf: &Gf2) -> Poly {
    quartic_with(x1, x2, &TargetPowers::new(xr, gf), gf)
}

/// **Does `x_R` decompose over the factor base?**  Returns a witness
/// `(X₁, X₂, X₃)` if so.
///
/// Loops over pairs and solves for the third point, so the work is
/// `O(2^{2l} · l)` field operations rather than the `O(2^{3l})` of
/// walking every triple.  One field inversion is spent per row of the
/// pair loop, not per pair: the leading coefficients of a whole row's
/// quartics are inverted together (see [`Gf2::batch_inv`]), which is
/// what lets every polynomial division below be inversion-free.
pub fn decompose(xr: u64, l: u32, gf: &Gf2) -> Option<[u64; 3]> {
    let lv = subspace_poly(l, gf);
    let tp = TargetPowers::new(xr, gf);
    let span = 1u64 << l;

    let mut qs: Vec<Poly> = Vec::with_capacity(span as usize);
    let mut leads: Vec<u64> = Vec::with_capacity(span as usize);
    let mut scratch: Vec<u64> = Vec::with_capacity(span as usize);

    for x1 in 0..span {
        qs.clear();
        leads.clear();
        for x2 in x1..span {
            let q = quartic_with(x1, x2, &tp, gf);
            match q.deg() {
                // Every `t` is a root, so any factor-base element works.
                None => return Some([x1, x2, 0]),
                Some(d) => leads.push(q.c[d]),
            }
            qs.push(q);
        }
        gf.batch_inv(&mut leads, &mut scratch);

        for (i, q) in qs.iter().enumerate() {
            let d = q.deg().expect("zero quartics returned above");
            let mut monic = *q;
            monic.scale_in_place(leads[i], d, gf);
            let g = roots_in_subspace(&monic, d, &lv, gf);
            let x2 = x1 + i as u64;
            match g.deg() {
                None | Some(0) => continue,
                // Root of `c₁t + c₀`, the only place a second inversion
                // is spent — and only when a decomposition is found.
                Some(1) => return Some([x1, x2, gf.mul(g.c[0], gf.inv(g.c[1]))]),
                Some(_) => {
                    // Several subspace roots.  Rare enough that finding
                    // one by evaluation costs nothing overall, and it
                    // avoids a full root-extraction routine.
                    for t in 0..span {
                        let mut v = 0u64;
                        for j in (0..=MAX_DEG).rev() {
                            v = gf.mul(v, t) ^ g.c[j];
                        }
                        if v == 0 {
                            return Some([x1, x2, t]);
                        }
                    }
                }
            }
        }
    }
    None
}

/// Evaluate the symmetrised `f₃` directly, for cross-checking.
pub fn eval_f3(x1: u64, x2: u64, x3: u64, xr: u64, gf: &Gf2) -> u64 {
    let q = quartic_in_x3(x1, x2, xr, gf);
    let mut v = 0u64;
    for i in (0..=MAX_DEG).rev() {
        v = gf.mul(v, x3) ^ q.c[i];
    }
    v
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::IrreduciblePoly;
    use crate::cryptanalysis::binary_semaev_s4::{elementary_symmetric_3, symmetrised_s4_eval};
    use crate::cryptanalysis::semaev_corpus::CORPUS;

    fn gf_for(inst: &crate::cryptanalysis::semaev_corpus::CorpusInstance) -> Gf2 {
        Gf2::new(&inst.irr())
    }

    fn xorshift(state: &mut u64) -> u64 {
        *state ^= *state >> 12;
        *state ^= *state << 25;
        *state ^= *state >> 27;
        state.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// The one-word field must agree with the general implementation —
    /// across a spread of `n`, since the reduction table's width and
    /// the carry-less product's shape both depend on it.
    #[test]
    fn field_arithmetic_matches_the_general_implementation() {
        for n in [15u32, 17, 18, 21, 24, 27, 30, 33] {
            let irr = IrreduciblePoly {
                degree: n,
                low_terms: match n {
                    15 => vec![0, 1],
                    17 => vec![0, 3],
                    18 => vec![0, 3],
                    21 => vec![0, 2],
                    24 => vec![0, 1, 3, 4],
                    27 => vec![0, 1, 2, 5],
                    30 => vec![0, 1],
                    _ => vec![0, 10],
                },
            };
            let gf = Gf2::new(&irr);
            let mut state = 0x1234_5678_9ABC_DEF0u64 ^ (n as u64);
            for _ in 0..1000 {
                let a = xorshift(&mut state) & gf.mask;
                let b = xorshift(&mut state) & gf.mask;

                let want = gf.to_element(a).mul(&gf.to_element(b), &irr);
                assert_eq!(gf.mul(a, b), gf.from_element(&want), "n={n}: mul({a}, {b})");

                let want_sq = gf.to_element(a).mul(&gf.to_element(a), &irr);
                assert_eq!(gf.sqr(a), gf.from_element(&want_sq), "n={n}: sqr({a})");

                if a != 0 {
                    assert_eq!(gf.mul(a, gf.inv(a)), 1, "n={n}: inv({a})");
                }
            }

            // Batch inversion must match one-at-a-time inversion, zeros
            // and all.
            let mut xs: Vec<u64> = (0..64).map(|_| xorshift(&mut state) & gf.mask).collect();
            xs[7] = 0;
            xs[40] = 0;
            let want: Vec<u64> = xs.iter().map(|&x| gf.inv(x)).collect();
            let mut got = xs.clone();
            gf.batch_inv(&mut got, &mut Vec::new());
            assert_eq!(got, want, "n={n}: batch inversion");
        }
    }

    /// Pairs-and-solve must agree with triple enumeration on targets it
    /// was not built from — the corpus only reaches `l = 6`, and the
    /// polynomial machinery is exercised much harder above that.
    #[test]
    fn decomposition_agrees_with_enumeration_on_random_targets() {
        let irr = IrreduciblePoly {
            degree: 21,
            low_terms: vec![0, 2],
        };
        let gf = Gf2::new(&irr);
        let l = 7u32;
        let span = 1u64 << l;

        let enumerate = |xr: u64| -> bool {
            for a in 0..span {
                for b in a..span {
                    for c in b..span {
                        if eval_f3(a, b, c, xr, &gf) == 0 {
                            return true;
                        }
                    }
                }
            }
            false
        };

        let mut state = 0xDEAD_BEEF_CAFE_1234u64;
        let (mut sat, mut unsat) = (0, 0);
        for _ in 0..40 {
            let xr = xorshift(&mut state) & gf.mask;
            let found = decompose(xr, l, &gf);
            assert_eq!(found.is_some(), enumerate(xr), "x_R = {xr}");
            if let Some([a, b, c]) = found {
                assert!(a < span && b < span && c < span, "witness outside V");
                assert_eq!(eval_f3(a, b, c, xr, &gf), 0, "x_R = {xr}: bad witness");
                sat += 1;
            } else {
                unsat += 1;
            }
        }
        // Both verdicts must actually occur, or the test proves nothing.
        assert!(
            sat > 0 && unsat > 0,
            "degenerate corpus: {sat} sat, {unsat} unsat"
        );
    }

    /// The quartic-in-`X₃` rearrangement must agree with the twelve-term
    /// form evaluated directly.
    #[test]
    fn quartic_matches_the_symmetrised_form() {
        for inst in CORPUS.iter().filter(|c| c.n == 15).take(2) {
            let irr = inst.irr();
            let gf = gf_for(inst);
            let xr = gf.from_element(&inst.x_r());
            for x1 in 0..40u64 {
                for x2 in 0..40u64 {
                    for x3 in 0..40u64 {
                        let (e1, e2, e3) = elementary_symmetric_3(
                            &gf.to_element(x1),
                            &gf.to_element(x2),
                            &gf.to_element(x3),
                            &irr,
                        );
                        let want = symmetrised_s4_eval(&e1, &e2, &e3, &inst.x_r(), &irr);
                        let got = eval_f3(x1, x2, x3, xr, &gf);
                        assert_eq!(
                            got,
                            gf.from_element(&want),
                            "f₃({x1}, {x2}, {x3}) for {}",
                            inst.name
                        );
                    }
                }
            }
        }
    }

    /// The subspace polynomial must vanish on exactly the subspace.
    ///
    /// Small fields are swept completely; the largest is checked on all
    /// of `V` plus a random sample outside it, since `2^36` points is
    /// not a unit test.
    #[test]
    fn subspace_polynomial_vanishes_on_the_subspace() {
        for (n, l, low) in [
            (15u32, 5u32, vec![0u32, 1]),
            (21, 7, vec![0, 2]),
            (36, 12, vec![0, 9]),
        ] {
            let irr = IrreduciblePoly {
                degree: n,
                low_terms: low,
            };
            let gf = Gf2::new(&irr);
            let lv = subspace_poly(l, &gf);
            assert_eq!(lv.len() as u32, l + 1);
            assert_eq!(*lv.last().unwrap(), 1, "n={n}: must be monic");
            let eval = |t: u64| {
                lv.iter().enumerate().fold(0u64, |acc, (i, &ai)| {
                    acc ^ gf.mul(ai, gf.sqr_k(t, i as u32))
                })
            };

            for t in 0..(1u64 << l) {
                assert_eq!(eval(t), 0, "n={n}: L_V({t}) must vanish on V");
            }

            if n <= 21 {
                for t in (1u64 << l)..(1u64 << n) {
                    assert_ne!(eval(t), 0, "n={n}: L_V({t}) must not vanish off V");
                }
            } else {
                let mut state = 0xA5A5_1234_5678_9ABCu64 ^ (n as u64);
                for _ in 0..20_000 {
                    let t = xorshift(&mut state) & gf.mask;
                    if t < (1 << l) {
                        continue;
                    }
                    assert_ne!(eval(t), 0, "n={n}: L_V({t}) must not vanish off V");
                }
            }
        }
    }

    /// **The decisive check.**  The pairs-and-solve oracle must give the
    /// same verdict as walking every triple, on every corpus instance —
    /// and any witness it returns must genuinely decompose the target.
    #[test]
    fn decomposition_agrees_with_exhaustive_search() {
        for inst in CORPUS {
            let irr = inst.irr();
            let gf = gf_for(inst);
            let xr = gf.from_element(&inst.x_r());
            let found = decompose(xr, inst.l, &gf);
            assert_eq!(
                found.is_some(),
                inst.truly_sat,
                "{}: disagrees with the recorded truth",
                inst.name
            );
            if let Some([a, b, c]) = found {
                assert!(a < (1 << inst.l) && b < (1 << inst.l) && c < (1 << inst.l));
                let (e1, e2, e3) = elementary_symmetric_3(
                    &gf.to_element(a),
                    &gf.to_element(b),
                    &gf.to_element(c),
                    &irr,
                );
                assert!(
                    symmetrised_s4_eval(&e1, &e2, &e3, &inst.x_r(), &irr).is_zero(),
                    "{}: witness does not decompose the target",
                    inst.name
                );
            }
        }
    }
}
