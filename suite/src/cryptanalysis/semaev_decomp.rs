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
    /// `red[j][v] = (v · z^{n + 8j}) mod irr`.  Fixed-size rows indexed
    /// by a byte, so a lookup carries no bounds check; `n ≤ 63` means
    /// at most eight rows are ever used.
    red: Box<[[u64; 256]; 8]>,
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

/// AArch64 carry-less multiply via `PMULL` (`vmull_p64`), the ARM
/// counterpart of `pclmulqdq`.  Gated on the `aes` feature the same way
/// `binary_ecc::f2m` gates its PMULL path, so Apple M-series and Graviton
/// run the single-instruction product instead of the bit-serial loop.
#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "aes")]
unsafe fn clmul_u64_neon(a: u64, b: u64) -> u128 {
    // `vmull_p64` takes two 64-bit polynomials and returns their full
    // 128-bit carry-less product.
    std::arch::aarch64::vmull_p64(a, b)
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

        debug_assert!(positions <= 8);
        let mut red = Box::new([[0u64; 256]; 8]);
        for j in 0..positions {
            for v in 1usize..256 {
                red[j][v] = red[j][v & (v - 1)] ^ pow[j * 8 + v.trailing_zeros() as usize];
            }
        }

        #[cfg(target_arch = "x86_64")]
        let has_clmul = std::arch::is_x86_feature_detected!("pclmulqdq");
        #[cfg(target_arch = "aarch64")]
        let has_clmul = std::arch::is_aarch64_feature_detected!("aes");
        #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
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
        for row in &self.red[..self.positions] {
            acc ^= row[usize::from(h as u8)];
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
        #[cfg(target_arch = "aarch64")]
        if self.has_clmul {
            // SAFETY: `has_clmul` records `is_aarch64_feature_detected!("aes")`.
            return unsafe { clmul_u64_neon(a, b) };
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

    /// `a·b + c·d` with one reduction instead of two.  [`Self::reduce`]
    /// is `F₂`-linear and both carry-less products are below `2^{2n−1}`,
    /// so their sum folds down to exactly the sum of the two reduced
    /// products, and the fold is most of what a multiplication costs.
    #[inline(always)]
    fn dot2(&self, a: u64, b: u64, c: u64, d: u64) -> u64 {
        self.reduce(self.clmul(a, b) ^ self.clmul(c, d))
    }

    /// With `pclmulqdq`, `a·a` is one instruction and beats the
    /// twelve-step bit spread; without it the spread is the cheap path.
    #[inline]
    pub fn sqr(&self, a: u64) -> u64 {
        #[cfg(target_arch = "x86_64")]
        if self.has_clmul {
            // SAFETY: guarded by the runtime feature detection recorded
            // in `has_clmul` at construction.
            return self.reduce(unsafe { clmul_u64(a, a) });
        }
        #[cfg(target_arch = "aarch64")]
        if self.has_clmul {
            // SAFETY: `has_clmul` records `is_aarch64_feature_detected!("aes")`.
            return self.reduce(unsafe { clmul_u64_neon(a, a) });
        }
        let w = (spread32(a) as u128) | ((spread32(a >> 32) as u128) << 64);
        self.reduce(w)
    }

    /// [`Self::sqr`] as one [`Self::reduce`] after [`Self::sqr_wide`], so
    /// the two paths of the product share a single fold instead of each
    /// carrying its own.  The same value, compiled differently where it
    /// is inlined, and which form is cheaper depends on the loop: the
    /// subspace oracle's pair loop runs 13% fewer instructions with this
    /// one, while the `koblitz_fast` code under `PairSumTable` ran 5–7.5%
    /// more when `sqr` itself took this form.  So `sqr` keeps its shape
    /// and the quartic route below calls this.
    #[inline(always)]
    fn sqr_fused(&self, a: u64) -> u64 {
        self.reduce(self.sqr_wide(a))
    }

    /// `a²` before reduction, for callers that fold it into a sum first.
    #[inline(always)]
    fn sqr_wide(&self, a: u64) -> u128 {
        #[cfg(target_arch = "x86_64")]
        if self.has_clmul {
            // SAFETY: guarded by the runtime feature detection recorded
            // in `has_clmul` at construction.
            return unsafe { clmul_u64(a, a) };
        }
        #[cfg(target_arch = "aarch64")]
        if self.has_clmul {
            // SAFETY: `has_clmul` records `is_aarch64_feature_detected!("aes")`.
            return unsafe { clmul_u64_neon(a, a) };
        }
        (spread32(a) as u128) | ((spread32(a >> 32) as u128) << 64)
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
    /// Itoh–Tsujii addition chain: with `β_k = a^{2^k − 1}`, walk the
    /// bits of `n − 1` using `β_{2k} = β_k^{2^k} · β_k` and
    /// `β_{k+1} = β_k² · a`, then square once.  That is `n − 1`
    /// squarings but only `⌊log₂(n−1)⌋ + popcount(n−1) − 1`
    /// multiplications, against `n − 2` for square-and-multiply —
    /// 7 instead of 22 at `n = 24`.
    pub fn inv(&self, a: u64) -> u64 {
        if a == 0 || self.n <= 1 {
            return a;
        }
        let e = self.n - 1;
        let mut beta = a;
        let mut len = 1u32;
        for bit in (0..(31 - e.leading_zeros())).rev() {
            beta = self.mul(self.sqr_k(beta, len), beta);
            len *= 2;
            if (e >> bit) & 1 == 1 {
                beta = self.mul(self.sqr(beta), a);
                len += 1;
            }
        }
        debug_assert_eq!(len, e);
        self.sqr(beta)
    }

    /// Invert a whole slice with **one** field inversion, by
    /// Montgomery's trick: accumulate the running product, invert once,
    /// then walk back peeling off one factor at a time.  Costs
    /// `3(k − 1)` multiplications plus a single inversion for `k`
    /// elements, so the inversion's cost per element goes to zero.
    ///
    /// Zeros are left as zero and skipped.
    ///
    /// The running product and the running inverse are each a serial
    /// chain — every step waits for the previous multiplication — so on
    /// one accumulator an element costs two multiplication *latencies*
    /// however many multipliers the core has.  The slice is therefore
    /// dealt round-robin to `LANES` independent accumulators whose chains
    /// overlap; their `LANES` products are inverted together by the same
    /// trick in miniature, still with one field inversion.  Same inverses,
    /// same multiplication count, a quarter of the dependent chain.
    ///
    /// Both passes walk `xs` and `scratch` as zipped chunks, so the loops
    /// carry no bounds checks and no `Vec` growth checks.
    pub fn batch_inv(&self, xs: &mut [u64], scratch: &mut Vec<u64>) {
        const LANES: usize = 4;
        scratch.clear();
        scratch.resize(xs.len(), 0);
        let mut acc = [1u64; LANES];
        for (xc, pc) in xs.chunks(LANES).zip(scratch.chunks_mut(LANES)) {
            for ((&x, prefix), a) in xc.iter().zip(pc.iter_mut()).zip(acc.iter_mut()) {
                *prefix = *a;
                if x != 0 {
                    *a = self.mul(*a, x);
                }
            }
        }
        // Invert the four lane products with one inversion.  None is
        // zero: each starts at 1 and only ever takes non-zero factors.
        let p01 = self.mul(acc[0], acc[1]);
        let p23 = self.mul(acc[2], acc[3]);
        let inv_all = self.inv(self.mul(p01, p23));
        let i01 = self.mul(inv_all, p23);
        let i23 = self.mul(inv_all, p01);
        let mut inv_acc = [
            self.mul(i01, acc[1]),
            self.mul(i01, acc[0]),
            self.mul(i23, acc[3]),
            self.mul(i23, acc[2]),
        ];
        for (xc, pc) in xs.chunks_mut(LANES).zip(scratch.chunks(LANES)).rev() {
            for ((x, &prefix), ia) in xc.iter_mut().zip(pc.iter()).zip(inv_acc.iter_mut()) {
                if *x != 0 {
                    let xi = *x;
                    *x = self.mul(*ia, prefix);
                    *ia = self.mul(*ia, xi);
                }
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

// ── L_V modulo a monic quartic ──────────────────────────────────────
//
// Nearly every pair produces a quartic of full degree, and for those
// [`roots_in_subspace`] can be done with a fraction of its field
// operations.  None of what follows changes the value computed: a
// remainder modulo a monic polynomial is unique, so this route and the
// generic one return the same coefficients, bit for bit.
//
// - **Squaring modulo `f` is semilinear.**  `φ(u) = u² mod f` satisfies
//   `φ(u + v) = φ(u) + φ(v)` and `φ(c·u) = c²·φ(u)`, so the sum
//   `Σ aᵢ t^{2^i}` has a Horner form in `φ`:
//
//       L_V(t) ≡ φ(φ(… φ(b_l t) + b_{l−1} t …) + b_1 t) + b_0 t,
//       b_j = a_j^{2^{−j}}.
//
//   The `b_j` depend only on the subspace and are computed once per
//   target.  Each Horner step is then a `φ` and one addition, where the
//   direct sum spent four multiplications per coefficient on top of the
//   same `φ`.  The top three steps never reach degree 4 before the
//   last, so they fold into one multiple of `t⁴ mod f`.
// - **`φ` by a table.**  `(Σ cᵢ tⁱ)² = Σ cᵢ² t^{2i}`, and of those
//   powers only `t⁴` and `t⁶` need reducing.  With `t⁴ mod f` (the low
//   coefficients of `f`, since `−1 = 1`) and `t⁶ mod f` computed once
//   per quartic, a squaring is four field squarings and eight
//   multiplications with no data-dependent branch.  `rem_monic` instead
//   scans down from `MAX_DEG` and eliminates three leading terms one
//   after another, each waiting on the last.

/// `L_V` rearranged for Horner evaluation under `φ`; see the section
/// comment.  With `L = max(l + 1, 3)` and missing coefficients zero,
/// the head `b_{L−1}⁴ t⁴ + b_{L−2}² t² + b_{L−3} t` needs no squaring
/// modulo `f`, only one multiple of `t⁴ mod f`.
struct LvHorner {
    /// The head's `t⁴` coefficient, `b_{L−1}⁴`.
    top: u64,
    /// The head's `t` and `t²` coefficients, `b_{L−3}` and `b_{L−2}²`.
    lin: [u64; 2],
    /// `b_j` for `j = L − 4, …, 0`, in the order the Horner loop adds
    /// them.
    steps: Vec<u64>,
}

impl LvHorner {
    fn new(lv: &[u64], gf: &Gf2) -> Self {
        // The Frobenius `a ↦ a²` has order `n`, so its `j`-th inverse is
        // its `(n − j mod n)`-th power.
        let n = gf.n;
        let root = |a: u64, j: usize| gf.sqr_k(a, (n - j as u32 % n) % n);
        let coef = |j: usize| lv.get(j).copied().unwrap_or(0);
        let len = lv.len().max(3);
        // Every head coefficient is `b_j^{2^{j−h}} = a_j^{2^{−h}}`.
        let h = len - 3;
        Self {
            top: root(coef(len - 1), h),
            lin: [root(coef(len - 3), h), root(coef(len - 2), h)],
            steps: (0..h).rev().map(|j| root(coef(j), j)).collect(),
        }
    }
}

/// Squaring modulo a monic quartic `f = t⁴ + f₃t³ + f₂t² + f₁t + f₀`,
/// by its table of `t⁴ mod f` and `t⁶ mod f`.
struct QuarticFrobenius {
    r4: [u64; 4],
    r6: [u64; 4],
}

impl QuarticFrobenius {
    /// `f` is given by its four low coefficients; the leading one is 1.
    #[inline(always)]
    fn new(f: [u64; 4], gf: &Gf2) -> Self {
        // t⁴ ≡ f₀ + f₁t + f₂t² + f₃t³, and each further factor of `t`
        // pushes one term back up to `t⁴`, which folds through it again:
        //
        //   t⁵ ≡ f₃f₀ + (f₀ + f₃f₁)t + (f₁ + f₃f₂)t² + k·t³,  k = f₂ + f₃²,
        //   t⁶ ≡ k·f₀ + (k·f₁ + f₃f₀)t + (k·f₂ + f₀ + f₃f₁)t²
        //        + (k·f₃ + f₁ + f₃f₂)t³.
        let [f0, f1, f2, f3] = f;
        let k = f2 ^ gf.sqr_fused(f3);
        let r6 = [
            gf.mul(k, f0),
            gf.dot2(k, f1, f3, f0),
            gf.dot2(k, f2, f3, f1) ^ f0,
            gf.dot2(k, f3, f3, f2) ^ f1,
        ];
        Self { r4: f, r6 }
    }

    /// `u² mod f`: `u₀² + u₁²t² + u₂²·(t⁴ mod f) + u₃²·(t⁶ mod f)`.
    ///
    /// Only `u₂²` and `u₃²` are reduced on their own, because they are
    /// multiplied again; each output coefficient is a sum of carry-less
    /// products and squares folded down once, as in [`Gf2::dot2`].
    #[inline(always)]
    fn sqr(&self, u: [u64; 4], gf: &Gf2) -> [u64; 4] {
        let (s2, s3) = (gf.sqr_fused(u[2]), gf.sqr_fused(u[3]));
        let (r4, r6) = (&self.r4, &self.r6);
        [
            gf.reduce(gf.sqr_wide(u[0]) ^ gf.clmul(s2, r4[0]) ^ gf.clmul(s3, r6[0])),
            gf.dot2(s2, r4[1], s3, r6[1]),
            gf.reduce(gf.sqr_wide(u[1]) ^ gf.clmul(s2, r4[2]) ^ gf.clmul(s3, r6[2])),
            gf.dot2(s2, r4[3], s3, r6[3]),
        ]
    }
}

/// [`roots_in_subspace`] for a monic quartic, given by its four low
/// coefficients.  Same result, coefficient for coefficient.
#[inline(always)]
fn roots_in_subspace_quartic(f: [u64; 4], lv: &LvHorner, gf: &Gf2) -> Poly {
    let frob = QuarticFrobenius::new(f, gf);
    let mut u = [
        gf.mul(lv.top, f[0]),
        gf.mul(lv.top, f[1]) ^ lv.lin[0],
        gf.mul(lv.top, f[2]) ^ lv.lin[1],
        gf.mul(lv.top, f[3]),
    ];
    for &b in &lv.steps {
        u = frob.sqr(u, gf);
        u[1] ^= b;
    }
    gcd_quartic(f, u, gf)
}

/// `f.gcd(g)` for a monic quartic `f` and `deg g ≤ 3`, both given by
/// their four low coefficients: exactly the polynomial [`Poly::gcd`]
/// returns.
///
/// Almost always the pseudo-remainder sequence has the generic shape,
/// degrees 4, 3, 2, 1, 0 with two elimination steps per division, and
/// that shape is written out below without the loops, the degree scans,
/// the multiplications by `f`'s leading 1 and the ones into a
/// coefficient that is cleared straight after.  A single subspace root
/// keeps the shape: the last remainder is then zero and the degree-1
/// one before it is the gcd.  Each leading coefficient the shape relies
/// on is checked, and if one vanishes the generic routine recomputes
/// the sequence from the start.  That happens by chance, about `6/2ⁿ`
/// per pair; when the gcd has degree 2 or more; and on every pair with
/// `X₁X₂ = 0`, the `X₁ = 0` row of the pair loop.  There the quartic is
/// a polynomial in `t²`, the square of some `r`, and `L_V(t)` is `a₀t`
/// plus the square of a linearized `M`, so `L_V mod f = a₀t + (M mod r)²`
/// has degree at most 2.  That row is `2/(2^l + 1)` of the pairs, and
/// the generic routine on it costs about 1% of the loop.
#[inline(always)]
fn gcd_quartic(f: [u64; 4], g: [u64; 4], gf: &Gf2) -> Poly {
    let [f0, f1, f2, f3] = f;
    let [g0, g1, g2, g3] = g;
    // prem(f, g): scale by g₃, cancel t⁴ against g·t, leaving
    // a = g₃f + t·g with a₃ = f₃g₃ + g₂; then scale by g₃ and cancel t³
    // against g.  Only a₃ is needed on its own, so the rest of `a` is
    // folded into c = g₃²f + (g₃t + a₃)·g, one reduction a coefficient.
    let g3sq = gf.sqr_fused(g3);
    let a3 = gf.mul(f3, g3) ^ g2;
    let c0 = gf.dot2(f0, g3sq, g0, a3);
    let c1 = gf.reduce(gf.clmul(f1, g3sq) ^ gf.clmul(g0, g3) ^ gf.clmul(g1, a3));
    let c2 = gf.reduce(gf.clmul(f2, g3sq) ^ gf.clmul(g1, g3) ^ gf.clmul(g2, a3));
    // prem(g, c): scale by c₂, cancel t³ against c·t, then t² against c.
    let b0 = gf.mul(g0, c2);
    let b1 = gf.dot2(g1, c2, c0, g3);
    let b2 = gf.dot2(g2, c2, c1, g3);
    let d0 = gf.dot2(b0, c2, c0, b2);
    let d1 = gf.dot2(b1, c2, c1, b2);
    // prem(c, d): scale by d₁, cancel t² against d·t, then t against d.
    let e0 = gf.mul(c0, d1);
    let e1 = gf.dot2(c1, d1, d0, c2);
    let h0 = gf.dot2(e0, d1, d0, e1);

    let mut out = Poly::zero();
    if g3 == 0 || a3 == 0 || c2 == 0 || b2 == 0 || d1 == 0 || e1 == 0 {
        let mut monic = Poly::zero();
        monic.c[..4].copy_from_slice(&f);
        monic.c[4] = 1;
        out.c[..4].copy_from_slice(&g);
        return monic.gcd(&out, gf);
    }
    if h0 != 0 {
        out.c[0] = h0;
    } else {
        out.c[0] = d0;
        out.c[1] = d1;
    }
    out
}

/// The subspace roots of `q / lead(q)`, given `lead(q)⁻¹` and
/// `deg q = d`: the quartic route when `d = 4`, which is all but a
/// vanishing fraction of pairs, and the generic one otherwise.
#[inline(always)]
fn subspace_roots_of(
    q: &Poly,
    d: usize,
    lead_inv: u64,
    lv: &[u64],
    horner: &LvHorner,
    gf: &Gf2,
) -> Poly {
    if d == 4 {
        // `lead · lead⁻¹ = 1` exactly, so the leading coefficient is
        // set rather than multiplied out.
        debug_assert_eq!(gf.mul(q.c[4], lead_inv), 1);
        let f = [
            gf.mul(q.c[0], lead_inv),
            gf.mul(q.c[1], lead_inv),
            gf.mul(q.c[2], lead_inv),
            gf.mul(q.c[3], lead_inv),
        ];
        roots_in_subspace_quartic(f, horner, gf)
    } else {
        let mut monic = *q;
        monic.scale_in_place(lead_inv, d, gf);
        roots_in_subspace(&monic, d, lv, gf)
    }
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

#[inline(always)]
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
    // Dispatched like [`SubspaceOracle::decompose`], for the same reason.
    #[cfg(target_arch = "x86_64")]
    if gf.has_clmul {
        // SAFETY: `has_clmul` records `is_x86_feature_detected!("pclmulqdq")`.
        return unsafe { decompose_pclmulqdq(xr, l, gf) };
    }
    decompose_body(xr, l, gf)
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "pclmulqdq")]
unsafe fn decompose_pclmulqdq(xr: u64, l: u32, gf: &Gf2) -> Option<[u64; 3]> {
    decompose_body(xr, l, gf)
}

#[inline(always)]
fn decompose_body(xr: u64, l: u32, gf: &Gf2) -> Option<[u64; 3]> {
    let lv = subspace_poly(l, gf);
    let horner = LvHorner::new(&lv, gf);
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
            let g = subspace_roots_of(q, d, leads[i], &lv, &horner, gf);
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

// ── S₄ for any `b`, over any subspace ───────────────────────────────
//
// The quartic above folds `b = 1` into its constants.  The general
// fourth summation polynomial for `y² + xy = x³ + a x² + b` follows
// from the resultant of two copies of the third one,
//
//     S₃(X₁, X₂, X) = s² X² + p X + (p² + b),   s = X₁ + X₂, p = X₁X₂,
//
// (`a` drops out), so with `X₄ = x_R` and `X₃ = t`:
//
//     S₄ = (s² p'² + s'² p² + b(s² + s'²))² + (s² p' + s'² p)(p + p')(p p' + b),
//     s' = t + x_R,  p' = t x_R.
//
// Collected by powers of `t` (squaring is additive in characteristic 2):
//
//     c₄ = (s²x² + p² + b)² + p²x²
//     c₃ = p x (b + p² + s²x²)
//     c₂ = p² b + s²x² (b + p²) + p²x⁴
//     c₁ = p x (s² b + x² (b + p²))
//     c₀ = (x²p² + b s² + b x²)² + p²x² b
//
// At `b = 1` every line reduces to the coefficient `quartic_with`
// computes, which `general_quartic_agrees_with_the_b_equals_one_form`
// checks term by term.

/// Powers of the target and the curve constant `b`, hoisted out of the
/// pair loop.
#[derive(Clone, Copy)]
struct GeneralTargetPowers {
    xr: u64,
    xr2: u64,
    xr4: u64,
    b: u64,
}

impl GeneralTargetPowers {
    fn new(xr: u64, b: u64, gf: &Gf2) -> Self {
        let xr2 = gf.sqr(xr);
        Self {
            xr,
            xr2,
            xr4: gf.sqr(xr2),
            b,
        }
    }
}

#[inline(always)]
fn quartic_general_with(x1: u64, x2: u64, t: &GeneralTargetPowers, gf: &Gf2) -> Poly {
    let s = x1 ^ x2;
    let p = gf.mul(x1, x2);
    let s2 = gf.sqr_fused(s);
    let p2 = gf.sqr_fused(p);
    let b = t.b;
    let bp2 = b ^ p2; // b + p²
    let s2x2 = gf.mul(s2, t.xr2); // s² x²
    let px = gf.mul(p, t.xr); // p x
    let p2x2 = gf.mul(p2, t.xr2); // p² x²

    // x²p² + b s² + b x²: the base of `c₀`'s square, and also `c₁`'s
    // cofactor `s² b + x² (b + p²)` rearranged.
    let inner = p2x2 ^ gf.mul(b, s2 ^ t.xr2);

    // The coefficients of the comment above, with `p²b + p²x⁴` and
    // `b s² + b x²` collected into one product each, `c₁`'s cofactor
    // shared with `c₀`, and each sum of products folded down once (see
    // [`Gf2::dot2`]).  Exact field identities, so the values are the
    // same bits.
    let mut q = Poly::zero();
    q.c[4] = gf.sqr_fused(s2x2 ^ bp2) ^ p2x2;
    q.c[3] = gf.mul(px, bp2 ^ s2x2);
    q.c[2] = gf.dot2(p2, b ^ t.xr4, s2x2, bp2);
    q.c[1] = gf.mul(px, inner);
    q.c[0] = gf.reduce(gf.sqr_wide(inner) ^ gf.clmul(p2x2, b));
    q
}

/// Coefficients of `S₄(X₁, X₂, t, x_R)` as a quartic in `t` for the
/// curve `y² + xy = x³ + a x² + b`, any `b ≠ 0` — [`quartic_in_x3`]
/// without the `b = 1` specialisation.
pub fn quartic_in_x3_general(x1: u64, x2: u64, xr: u64, b: u64, gf: &Gf2) -> Poly {
    quartic_general_with(x1, x2, &GeneralTargetPowers::new(xr, b, gf), gf)
}

/// Evaluate the general `S₄(x1, x2, x3, x_R)` for curve constant `b`.
pub fn eval_s4_general(x1: u64, x2: u64, x3: u64, xr: u64, b: u64, gf: &Gf2) -> u64 {
    let q = quartic_in_x3_general(x1, x2, xr, b, gf);
    let mut v = 0u64;
    for i in (0..=MAX_DEG).rev() {
        v = gf.mul(v, x3) ^ q.c[i];
    }
    v
}

/// Coefficients of the linearized polynomial vanishing exactly on the
/// `F₂`-span of `basis` — [`subspace_poly`] for an arbitrary basis.
///
/// Same recurrence, `L_{W+⟨v⟩}(t) = L_W(t)² + L_W(v)·L_W(t)`, with the
/// basis vector `v` in place of `z^i`.  The basis must be independent:
/// a dependent vector has `L_W(v) = 0` and the recurrence would square
/// the polynomial instead of extending it.
pub fn subspace_poly_for_basis(basis: &[u64], gf: &Gf2) -> Vec<u64> {
    let mut a = vec![1u64];
    for &v in basis {
        let lv = a.iter().enumerate().fold(0u64, |acc, (j, &aj)| {
            acc ^ gf.mul(aj, gf.sqr_k(v, j as u32))
        });
        assert!(lv != 0, "subspace basis is not independent");
        let mut next = vec![0u64; a.len() + 1];
        for (j, &aj) in a.iter().enumerate() {
            next[j + 1] ^= gf.sqr(aj);
            next[j] ^= gf.mul(lv, aj);
        }
        a = next;
    }
    a
}

/// **Pairs-and-solve over any subspace, for any `b`.**
///
/// The oracle [`decompose`] specialises: the factor base is the
/// low-order subspace `⟨1, z, …, z^{l−1}⟩` and the curve is the Koblitz
/// `b = 1`.  This one takes the subspace as a basis (so a
/// Frobenius-invariant subspace of a Koblitz curve is as good a factor
/// base as the low-order one, and the relation columns can then be
/// folded by orbit) and the curve constant `b` explicitly (so a random
/// binary curve is a valid instance).  It also reports how many pairs
/// it processed, which is the oracle's cost in its own native unit.
#[derive(Clone, Debug)]
pub struct SubspaceOracle {
    /// Dimension of the factor-base subspace.
    pub l: u32,
    /// Curve constant.
    pub b: u64,
    /// Every element of the subspace, indexed by its coordinate word.
    pub span: Vec<u64>,
    /// Coefficients of `L_V`.
    pub lv: Vec<u64>,
}

impl SubspaceOracle {
    /// Build the oracle for the span of `basis` on the curve with
    /// constant `b`.  Panics if the basis is dependent.
    pub fn new(basis: &[u64], b: u64, gf: &Gf2) -> Self {
        assert!(b != 0, "the curve is singular at b = 0");
        assert!(basis.len() <= 30, "subspace too large to enumerate");
        let l = basis.len() as u32;
        let mut span = Vec::with_capacity(1usize << l);
        for idx in 0..(1u64 << l) {
            let mut v = 0u64;
            for (j, &e) in basis.iter().enumerate() {
                if (idx >> j) & 1 == 1 {
                    v ^= e;
                }
            }
            span.push(v);
        }
        let mut sorted = span.clone();
        sorted.sort_unstable();
        sorted.dedup();
        assert_eq!(
            sorted.len(),
            span.len(),
            "subspace basis is not independent"
        );
        let lv = subspace_poly_for_basis(basis, gf);
        Self { l, b, span, lv }
    }

    /// The low-order subspace `⟨1, z, …, z^{l−1}⟩` — the factor base of
    /// [`decompose`] — so the two oracles can be compared directly.
    pub fn low_order(l: u32, b: u64, gf: &Gf2) -> Self {
        let basis: Vec<u64> = (0..l).map(|i| 1u64 << i).collect();
        Self::new(&basis, b, gf)
    }

    /// Whether `x` lies in the subspace (a scan; the oracle's callers
    /// keep their own index of factor-base abscissae).
    pub fn contains(&self, x: u64, gf: &Gf2) -> bool {
        // L_V(x) = 0 exactly on the subspace.
        self.lv.iter().enumerate().fold(0u64, |acc, (i, &ai)| {
            acc ^ gf.mul(ai, gf.sqr_k(x, i as u32))
        }) == 0
    }

    /// **Does `x_R` decompose over the subspace?**  Returns a witness
    /// `(X₁, X₂, X₃)` with `S₄(X₁, X₂, X₃, x_R) = 0`, if one exists,
    /// together with the number of pairs the search processed — the
    /// full `2^l(2^l + 1)/2` when it refutes, fewer when it finds.
    ///
    /// The witness is a triple of *abscissae*; whether points with
    /// those abscissae are rational and sum to the target with some
    /// choice of signs is the caller's lift check.
    pub fn decompose(&self, xr: u64, gf: &Gf2) -> (Option<[u64; 3]>, u64) {
        // The pair loop is over a hundred carry-less products per pair,
        // and `clmul_u64` is a `#[target_feature]` function, which cannot
        // be inlined into code compiled without that feature: every
        // product would be a call.  So where the CPU has the instruction
        // the whole loop is compiled with it enabled, and the same body
        // runs as ordinary code on the portable path.
        #[cfg(target_arch = "x86_64")]
        if gf.has_clmul {
            // SAFETY: `has_clmul` records `is_x86_feature_detected!("pclmulqdq")`.
            return unsafe { self.decompose_pclmulqdq(xr, gf) };
        }
        self.decompose_body(xr, gf)
    }

    #[cfg(target_arch = "x86_64")]
    #[target_feature(enable = "pclmulqdq")]
    unsafe fn decompose_pclmulqdq(&self, xr: u64, gf: &Gf2) -> (Option<[u64; 3]>, u64) {
        self.decompose_body(xr, gf)
    }

    #[inline(always)]
    fn decompose_body(&self, xr: u64, gf: &Gf2) -> (Option<[u64; 3]>, u64) {
        let tp = GeneralTargetPowers::new(xr, self.b, gf);
        let horner = LvHorner::new(&self.lv, gf);
        let span = &self.span;
        let count = span.len();
        let mut pairs = 0u64;

        let mut qs: Vec<Poly> = Vec::with_capacity(count);
        let mut leads: Vec<u64> = Vec::with_capacity(count);
        let mut scratch: Vec<u64> = Vec::with_capacity(count);

        for i1 in 0..count {
            let x1 = span[i1];
            qs.clear();
            leads.clear();
            for &x2 in &span[i1..] {
                let q = quartic_general_with(x1, x2, &tp, gf);
                pairs += 1;
                match q.deg() {
                    // Every `t` is a root: the first non-zero subspace
                    // element is as good a witness as any.
                    None => {
                        let x3 = span.iter().copied().find(|&v| v != 0).unwrap_or(0);
                        return (Some([x1, x2, x3]), pairs);
                    }
                    Some(d) => leads.push(q.c[d]),
                }
                qs.push(q);
            }
            gf.batch_inv(&mut leads, &mut scratch);

            for (i, q) in qs.iter().enumerate() {
                let d = q.deg().expect("zero quartics returned above");
                let g = subspace_roots_of(q, d, leads[i], &self.lv, &horner, gf);
                let x2 = span[i1 + i];
                match g.deg() {
                    None | Some(0) => continue,
                    Some(1) => {
                        return (Some([x1, x2, gf.mul(g.c[0], gf.inv(g.c[1]))]), pairs);
                    }
                    Some(_) => {
                        for &t in span.iter() {
                            let mut v = 0u64;
                            for j in (0..=MAX_DEG).rev() {
                                v = gf.mul(v, t) ^ g.c[j];
                            }
                            if v == 0 {
                                return (Some([x1, x2, t]), pairs);
                            }
                        }
                    }
                }
            }
        }
        (None, pairs)
    }
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

    /// Batch inversion equals element-wise inversion on every length
    /// around the lane count and a full block, with zeros scattered in
    /// (left as zero) and a slice of nothing but zeros.
    #[test]
    fn batch_inversion_matches_elementwise() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        let mut s = 0xB47C_4111_7EE5_0001u64;
        for n in [7u32, 24, 53, 62] {
            let gf = Gf2::new(&find_irreducible_sparse(n).unwrap());
            let mut scratch = Vec::new();
            for len in (0..=17).chain([63, 64, 65, 1024, 1027]) {
                let mut xs: Vec<u64> = (0..len)
                    .map(|i| {
                        let v = xorshift(&mut s) & gf.mask;
                        if i % 7 == 3 {
                            0
                        } else {
                            v
                        }
                    })
                    .collect();
                let want: Vec<u64> = xs.iter().map(|&x| gf.inv(x)).collect();
                gf.batch_inv(&mut xs, &mut scratch);
                assert_eq!(xs, want, "n = {n}, len = {len}");
            }
            let mut zeros = vec![0u64; 9];
            gf.batch_inv(&mut zeros, &mut scratch);
            assert!(zeros.iter().all(|&z| z == 0));
        }
    }

    /// `mul`/`sqr` must equal an independent schoolbook multiply-then-reduce,
    /// whichever carry-less path runs (x86 PCLMULQDQ, aarch64 PMULL, or the
    /// bit-serial fallback).  This is the correctness gate for the ARM PMULL
    /// path added for Apple-silicon / Graviton mechanical sympathy.
    #[test]
    fn clmul_path_matches_independent_reference() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        // Independent reference: carry-less product in u128, then reduce
        // bit-by-bit modulo the irreducible (no shared table).
        fn ref_mul(a: u64, b: u64, irr_bits: u64, n: u32) -> u64 {
            let mut w = 0u128;
            for i in 0..64 {
                if (b >> i) & 1 == 1 {
                    w ^= (a as u128) << i;
                }
            }
            for i in (n..128).rev() {
                if (w >> i) & 1 == 1 {
                    w ^= (irr_bits as u128) << (i - n);
                }
            }
            (w as u64) & ((1u64 << n) - 1)
        }
        let mut s = 0x1234_5678_9ABC_DEF1u64;
        for n in [7u32, 13, 24, 41, 53, 62] {
            let gf = Gf2::new(&find_irreducible_sparse(n).unwrap());
            for _ in 0..2000 {
                let a = xorshift(&mut s) & gf.mask;
                let b = xorshift(&mut s) & gf.mask;
                assert_eq!(gf.mul(a, b), ref_mul(a, b, gf.irr, n), "mul n={n}");
                assert_eq!(gf.sqr(a), ref_mul(a, a, gf.irr, n), "sqr n={n}");
            }
        }
    }

    /// The Itoh–Tsujii inverse is a true inverse at every one-word
    /// field size, where the chain's shape follows the bits of `n − 1`.
    #[test]
    fn itoh_tsujii_inverse_roundtrips_at_every_width() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        let mut s = 0x0DDB_A11C_AFE0_F00Du64;
        for n in 2u32..=63 {
            let Some(irr) = find_irreducible_sparse(n) else {
                continue;
            };
            let gf = Gf2::new(&irr);
            assert_eq!(gf.inv(0), 0);
            assert_eq!(gf.inv(1), 1);
            for _ in 0..50 {
                let a = xorshift(&mut s) & gf.mask;
                if a == 0 {
                    continue;
                }
                assert_eq!(gf.mul(a, gf.inv(a)), 1, "n = {n}, a = {a:#x}");
            }
        }
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

    /// The quartic route must return exactly what the generic
    /// `rem_monic` route returns, every coefficient of the gcd, and the
    /// dispatch must hand every other degree to the generic route
    /// unchanged.  Random quartics almost never have a subspace root,
    /// so quartics are also planted with one to four roots in `V`,
    /// which is what drives the gcd off its usual shape; the small
    /// fields make zero intermediate coefficients common.  Run with the
    /// carry-less multiply and with the portable fallback, on subspace
    /// polynomials and on arbitrary coefficient vectors (the identity
    /// holds for any `Σ aᵢ t^{2^i}`) of every short length.
    #[test]
    fn quartic_route_matches_the_generic_remainder() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        // `k · Π (t + rᵢ)`, low coefficient first.
        fn from_roots(k: u64, roots: &[u64], gf: &Gf2) -> Poly {
            let mut p = Poly::zero();
            p.c[0] = k;
            for &r in roots {
                let mut next = Poly::zero();
                for i in 0..MAX_DEG {
                    next.c[i + 1] ^= p.c[i];
                    next.c[i] ^= gf.mul(p.c[i], r);
                }
                p = next;
            }
            p
        }
        let mut s = 0x51AB_0C7E_F00D_2026u64;
        let mut by_degree = [0usize; 5];
        for (n, l) in [
            (5u32, 2u32),
            (7, 3),
            (13, 0),
            (13, 1),
            (13, 2),
            (20, 7),
            (21, 7),
            (31, 10),
            (53, 12),
        ] {
            for portable in [false, true] {
                let mut gf = Gf2::new(&find_irreducible_sparse(n).unwrap());
                if portable {
                    gf.has_clmul = false;
                }
                let basis: Vec<u64> = (0..l).map(|i| 1u64 << (3 * i % n)).collect();
                let oracle = SubspaceOracle::new(&basis, 1, &gf);
                let random_lv: Vec<Vec<u64>> = (1..=6)
                    .map(|len| (0..len).map(|_| xorshift(&mut s) & gf.mask).collect())
                    .collect();
                for lv in std::iter::once(&oracle.lv).chain(&random_lv) {
                    let horner = LvHorner::new(lv, &gf);
                    for trial in 0..500 {
                        // Trials cycle through 0 to 4 planted subspace
                        // roots; the other roots, the scale and (with
                        // none planted) all five coefficients are
                        // random, so some quartics have lower degree.
                        let planted = trial % 5;
                        let q = if planted == 0 {
                            let mut q = Poly::zero();
                            for c in &mut q.c[..5] {
                                *c = xorshift(&mut s) & gf.mask;
                            }
                            q
                        } else {
                            let roots: Vec<u64> = (0..4)
                                .map(|i| {
                                    let r = xorshift(&mut s);
                                    if i < planted {
                                        oracle.span[(r >> 7) as usize % oracle.span.len()]
                                    } else {
                                        r & gf.mask
                                    }
                                })
                                .collect();
                            let k = (xorshift(&mut s) & gf.mask).max(1);
                            from_roots(k, &roots, &gf)
                        };
                        let Some(d) = q.deg() else { continue };
                        let lead_inv = gf.inv(q.c[d]);
                        let mut monic = q;
                        monic.scale_in_place(lead_inv, d, &gf);
                        let want = roots_in_subspace(&monic, d, lv, &gf);
                        let got = subspace_roots_of(&q, d, lead_inv, lv, &horner, &gf);
                        assert_eq!(
                            got.c, want.c,
                            "n={n} l={l} portable={portable} lv={lv:?} q={:?}",
                            q.c
                        );
                        if d == 4 {
                            by_degree[want.deg().expect("gcd with f is non-zero")] += 1;
                        }
                    }
                }
            }
        }
        // Every gcd degree must have occurred on the quartic route.
        assert!(
            by_degree.iter().all(|&k| k > 0),
            "gcd degrees seen: {by_degree:?}"
        );
    }

    /// The general quartic by its term-by-term formula: the coefficient
    /// list in the comment above `GeneralTargetPowers`, one reduction per
    /// product, as it was first written.
    fn quartic_term_by_term(x1: u64, x2: u64, xr: u64, b: u64, gf: &Gf2) -> [u64; 5] {
        let (s, p) = (x1 ^ x2, gf.mul(x1, x2));
        let (s2, p2, x2r, x4r) = (gf.sqr(s), gf.sqr(p), gf.sqr(xr), gf.sqr(gf.sqr(xr)));
        let (bp2, s2x2, px, p2x2) = (b ^ p2, gf.mul(s2, x2r), gf.mul(p, xr), gf.mul(p2, x2r));
        [
            gf.sqr(gf.mul(x2r, p2) ^ gf.mul(b, s2) ^ gf.mul(b, x2r)) ^ gf.mul(p2x2, b),
            gf.mul(px, gf.mul(s2, b) ^ gf.mul(x2r, bp2)),
            gf.mul(p2, b) ^ gf.mul(s2x2, bp2) ^ gf.mul(p2, x4r),
            gf.mul(px, bp2 ^ s2x2),
            gf.sqr(s2x2 ^ bp2) ^ p2x2,
        ]
    }

    /// The general quartic must equal [`quartic_term_by_term`] on random
    /// inputs, whichever multiply runs.
    #[test]
    fn general_quartic_matches_its_term_by_term_formula() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        let mut s = 0x0C0F_FEE5_EED5_0B0Eu64;
        for n in [5u32, 13, 20, 31, 53, 63] {
            for portable in [false, true] {
                let mut gf = Gf2::new(&find_irreducible_sparse(n).unwrap());
                gf.has_clmul &= !portable;
                for i in 0..3000 {
                    let mut r = || xorshift(&mut s) & gf.mask;
                    let (mut x1, x2, xr, b) = (r(), r(), r(), r());
                    if i % 10 == 0 {
                        x1 = x2; // s = 0
                    }
                    let got = quartic_in_x3_general(x1, x2, xr, b, &gf);
                    let want = quartic_term_by_term(x1, x2, xr, b, &gf);
                    assert_eq!(got.c[..5], want, "n={n} portable={portable}");
                    assert!(got.c[5..].iter().all(|&c| c == 0));
                }
            }
        }
    }

    /// Both decomposers run their pair loop compiled with the carry-less
    /// multiply where the CPU has it and as ordinary code otherwise; the
    /// two builds of the loop must return the same witnesses and pair
    /// counts, on targets that decompose and targets that do not.
    #[test]
    fn dispatched_and_portable_pair_loops_agree() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        let fast = Gf2::new(&find_irreducible_sparse(13).unwrap());
        let mut portable = fast.clone();
        portable.has_clmul = false;
        let basis: Vec<u64> = (0..5).map(|i| 1u64 << (3 * i)).collect();
        let oracle = SubspaceOracle::new(&basis, 0x1_2345 & fast.mask, &fast);
        let mut s = 0x7A61_E5CA_1AB1_E000u64;
        let mut found = [0usize; 2];
        for _ in 0..24 {
            let xr = xorshift(&mut s) & fast.mask;
            let want = oracle.decompose(xr, &portable);
            assert_eq!(oracle.decompose(xr, &fast), want, "x_R = {xr}");
            found[want.0.is_some() as usize] += 1;
            assert_eq!(
                decompose(xr, 5, &fast),
                decompose(xr, 5, &portable),
                "x_R = {xr}"
            );
        }
        assert!(found[0] > 0 && found[1] > 0, "degenerate: {found:?}");
    }

    /// [`SubspaceOracle::decompose`] as it was before the quartic route:
    /// the quartic term by term, made monic by `scale_in_place` (one
    /// inversion each; the batched inverses are the same values, see
    /// `batch_inversion_matches_elementwise`), and `roots_in_subspace` on
    /// the generic `rem_monic` route.  Same pair order, same exits.
    fn reference_decompose(oracle: &SubspaceOracle, xr: u64, gf: &Gf2) -> (Option<[u64; 3]>, u64) {
        let span = &oracle.span;
        let mut pairs = 0u64;
        for (i1, &x1) in span.iter().enumerate() {
            let mut row = Vec::new();
            for &x2 in &span[i1..] {
                let mut q = Poly::zero();
                q.c[..5].copy_from_slice(&quartic_term_by_term(x1, x2, xr, oracle.b, gf));
                pairs += 1;
                if q.is_zero() {
                    let x3 = span.iter().copied().find(|&v| v != 0).unwrap_or(0);
                    return (Some([x1, x2, x3]), pairs);
                }
                row.push((x2, q));
            }
            for (x2, q) in row {
                let d = q.deg().expect("zero quartics returned above");
                let mut monic = q;
                monic.scale_in_place(gf.inv(q.c[d]), d, gf);
                let g = roots_in_subspace(&monic, d, &oracle.lv, gf);
                match g.deg() {
                    None | Some(0) => continue,
                    Some(1) => return (Some([x1, x2, gf.mul(g.c[0], gf.inv(g.c[1]))]), pairs),
                    Some(_) => {
                        for &t in span {
                            let v = (0..=MAX_DEG).rev().fold(0, |v, j| gf.mul(v, t) ^ g.c[j]);
                            if v == 0 {
                                return (Some([x1, x2, t]), pairs);
                            }
                        }
                    }
                }
            }
        }
        (None, pairs)
    }

    /// The oracle must return exactly what the loop it replaced returns,
    /// witness and pair count, with the carry-less multiply and without:
    /// on the low-order subspace and on random ones, at `b = 1` and a
    /// random `b`, for `x_R = 0`, an `x_R` inside the subspace and random
    /// ones.  The fields are small enough that both verdicts are common,
    /// so every exit of the loop is taken, and the `X₁ = 0` row sends
    /// quartics to the generic gcd on every target.
    #[test]
    fn subspace_oracle_matches_the_loop_it_replaced() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        let independent = |basis: &[u64]| {
            let mut seen = std::collections::HashSet::new();
            (0..1u64 << basis.len()).all(|idx| {
                let v = (0..basis.len())
                    .filter(|j| (idx >> j) & 1 == 1)
                    .fold(0, |v, j| v ^ basis[j]);
                seen.insert(v)
            })
        };
        let mut s = 0x0AC1_E5EE_D0F0_2026u64;
        let mut found = [0usize; 2];
        for (n, l) in [(9u32, 4u32), (13, 5), (17, 6), (20, 7), (31, 5)] {
            let fast = Gf2::new(&find_irreducible_sparse(n).unwrap());
            let mut portable = fast.clone();
            portable.has_clmul = false;
            let random_basis = loop {
                let cand: Vec<u64> = (0..l).map(|_| xorshift(&mut s) & fast.mask).collect();
                if independent(&cand) {
                    break cand;
                }
            };
            let low_order: Vec<u64> = (0..l).map(|i| 1u64 << i).collect();
            for basis in [low_order, random_basis] {
                for b in [1, (xorshift(&mut s) & fast.mask) | 2] {
                    let oracle = SubspaceOracle::new(&basis, b, &fast);
                    let inside = oracle.span[xorshift(&mut s) as usize % oracle.span.len()];
                    let random = (0..4).map(|_| xorshift(&mut s) & fast.mask);
                    for xr in [0, inside].into_iter().chain(random) {
                        let want = reference_decompose(&oracle, xr, &fast);
                        assert_eq!(oracle.decompose(xr, &fast), want, "n={n} b={b} x_R={xr}");
                        assert_eq!(
                            oracle.decompose(xr, &portable),
                            want,
                            "n={n} b={b} x_R={xr}"
                        );
                        found[want.0.is_some() as usize] += 1;
                    }
                }
            }
        }
        assert!(found[0] > 0 && found[1] > 0, "degenerate: {found:?}");
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

    /// The general-`b` quartic must reduce to the specialised one at
    /// `b = 1`, coefficient by coefficient.
    #[test]
    fn general_quartic_agrees_with_the_b_equals_one_form() {
        let irr = IrreduciblePoly {
            degree: 21,
            low_terms: vec![0, 2],
        };
        let gf = Gf2::new(&irr);
        let mut state = 0x0BAD_F00D_1234_5678u64;
        for _ in 0..2000 {
            let x1 = xorshift(&mut state) & gf.mask;
            let x2 = xorshift(&mut state) & gf.mask;
            let xr = xorshift(&mut state) & gf.mask;
            let want = quartic_in_x3(x1, x2, xr, &gf);
            let got = quartic_in_x3_general(x1, x2, xr, 1, &gf);
            assert_eq!(got.c, want.c, "x1={x1} x2={x2} xr={xr}");
        }
    }

    /// The general oracle on the low-order subspace at `b = 1` must
    /// agree with the specialised one on every random target, and its
    /// pair count must be the whole search when it refutes.
    #[test]
    fn subspace_oracle_agrees_with_decompose_on_the_low_order_subspace() {
        let irr = IrreduciblePoly {
            degree: 21,
            low_terms: vec![0, 2],
        };
        let gf = Gf2::new(&irr);
        let l = 7u32;
        let oracle = SubspaceOracle::low_order(l, 1, &gf);
        assert_eq!(oracle.lv, subspace_poly(l, &gf));
        let all_pairs = {
            let s = 1u64 << l;
            s * (s + 1) / 2
        };
        let mut state = 0xFEED_FACE_0123_4567u64;
        let (mut sat, mut unsat) = (0, 0);
        for _ in 0..40 {
            let xr = xorshift(&mut state) & gf.mask;
            let want = decompose(xr, l, &gf);
            let (got, pairs) = oracle.decompose(xr, &gf);
            assert_eq!(got.is_some(), want.is_some(), "x_R = {xr}");
            match got {
                Some([a, b, c]) => {
                    assert_eq!(eval_s4_general(a, b, c, xr, 1, &gf), 0);
                    assert!(pairs <= all_pairs);
                    sat += 1;
                }
                None => {
                    assert_eq!(pairs, all_pairs, "a refutation must exhaust the pairs");
                    unsat += 1;
                }
            }
        }
        assert!(sat > 0 && unsat > 0, "degenerate: {sat} sat, {unsat} unsat");
    }

    /// On a random curve (`b ≠ 1`) the general `S₄` must vanish on the
    /// abscissae of any three points and their sum, and the oracle over
    /// a random subspace must find a witness for a planted sum whose
    /// abscissae lift to points that really add up to the target.
    #[test]
    fn general_s4_vanishes_on_point_sums_of_a_random_curve() {
        use crate::binary_ecc::{BinaryCurve, BinaryPoint};
        use crate::cryptanalysis::koblitz_fast::FastCurve;
        use crate::cryptanalysis::koblitz_index_calculus::points_with_x;
        use num_bigint::BigUint;

        let n = 15u32;
        let irr = IrreduciblePoly {
            degree: n,
            low_terms: vec![0, 1],
        };
        let gf = Gf2::new(&irr);
        let mut state = 0x5EED_5EED_5EED_5EEDu64;
        for a in [0u64, 1] {
            let b = (xorshift(&mut state) & gf.mask) | 2; // b ∉ {0, 1}
                                                          // The curve coefficient a₂ does not enter S₃ or S₄; both values
                                                          // are checked so that stays a fact rather than an assumption.
            let curve = BinaryCurve {
                m: n,
                irreducible: irr.clone(),
                a: gf.to_element(a),
                b: gf.to_element(b),
                generator: BinaryPoint::Infinity,
                order: BigUint::from(1u32),
                cofactor: BigUint::from(1u32),
            };
            let fast = FastCurve::new(&curve).unwrap();
            let random_point = |state: &mut u64| loop {
                let x = xorshift(state) & gf.mask;
                if x == 0 {
                    continue;
                }
                let pts = points_with_x(&curve, &gf.to_element(x));
                if let Some(p) = pts.first() {
                    return fast.lift(p);
                }
            };

            // S₄ vanishes on genuine sums …
            for _ in 0..50 {
                let p1 = random_point(&mut state);
                let p2 = random_point(&mut state);
                let p3 = random_point(&mut state);
                let r = fast.add(fast.add(p1, p2), p3);
                if r.infinity {
                    continue;
                }
                assert_eq!(
                    eval_s4_general(p1.x, p2.x, p3.x, r.x, b, &gf),
                    0,
                    "S₄ must vanish on a point sum"
                );
            }
            // … and not on random quadruples.
            let nonzero = (0..50)
                .filter(|_| {
                    let xs: Vec<u64> = (0..4).map(|_| xorshift(&mut state) & gf.mask).collect();
                    eval_s4_general(xs[0], xs[1], xs[2], xs[3], b, &gf) != 0
                })
                .count();
            assert!(
                nonzero > 40,
                "S₄ vanished on {} of 50 random quadruples",
                50 - nonzero
            );

            // A random 5-dimensional subspace, a planted sum, a found witness.
            let basis: Vec<u64> = loop {
                let cand: Vec<u64> = (0..5).map(|_| xorshift(&mut state) & gf.mask).collect();
                let mut span = std::collections::HashSet::new();
                for idx in 0..32u64 {
                    let v = (0..5)
                        .filter(|j| (idx >> j) & 1 == 1)
                        .fold(0u64, |a, j| a ^ cand[j]);
                    span.insert(v);
                }
                if span.len() == 32 {
                    break cand;
                }
            };
            let oracle = SubspaceOracle::new(&basis, b, &gf);
            let base_points: Vec<crate::cryptanalysis::koblitz_fast::FastPoint> = oracle
                .span
                .iter()
                .filter(|&&x| x != 0)
                .flat_map(|&x| points_with_x(&curve, &gf.to_element(x)))
                .map(|p| fast.lift(&p))
                .collect();
            assert!(base_points.len() >= 6, "subspace has too few points");
            let mut planted = 0;
            for _ in 0..20 {
                let pick = |state: &mut u64| {
                    base_points[(xorshift(state) % base_points.len() as u64) as usize]
                };
                let (p1, p2, p3) = (pick(&mut state), pick(&mut state), pick(&mut state));
                let r = fast.add(fast.add(p1, p2), p3);
                if r.infinity {
                    continue;
                }
                let (found, _) = oracle.decompose(r.x, &gf);
                let [a, bb, c] = found.expect("a planted sum must be found");
                assert!(
                    oracle.contains(a, &gf) && oracle.contains(bb, &gf) && oracle.contains(c, &gf)
                );
                assert_eq!(eval_s4_general(a, bb, c, r.x, b, &gf), 0);
                // Lift: some choice of signs sums to R or −R.
                let lifts: Vec<Vec<crate::cryptanalysis::koblitz_fast::FastPoint>> = [a, bb, c]
                    .iter()
                    .map(|&x| {
                        points_with_x(&curve, &gf.to_element(x))
                            .iter()
                            .map(|p| fast.lift(p))
                            .collect()
                    })
                    .collect();
                let mut ok = false;
                for q1 in &lifts[0] {
                    for q2 in &lifts[1] {
                        for q3 in &lifts[2] {
                            let s = fast.add(fast.add(*q1, *q2), *q3);
                            if s == r || s == fast.neg(r) {
                                ok = true;
                            }
                        }
                    }
                }
                assert!(ok, "witness abscissae do not lift to a decomposition");
                planted += 1;
            }
            assert!(planted >= 10);
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

/// Differential tests against the pair loop as it stood at `994784af`,
/// before the quartic route.  Everything under `old` is that revision's
/// code copied verbatim (the `Poly` methods as free functions over the
/// same `Poly`), so these tests do not lean on any routine the change
/// touched or might touch later: the reference is frozen here.
#[cfg(test)]
mod reference_994784af {
    use super::*;
    use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;

    mod old {
        use super::super::{GeneralTargetPowers, Gf2, Poly, SubspaceOracle, TargetPowers, MAX_DEG};

        fn scale_in_place(p: &mut Poly, k: u64, hi: usize, gf: &Gf2) {
            for i in 0..=hi {
                p.c[i] = gf.mul(p.c[i], k);
            }
        }

        fn rem_monic(p: &Poly, m: &Poly, dm: usize, gf: &Gf2) -> Poly {
            let mut r = *p;
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

        fn sqr_mod_monic(p: &Poly, m: &Poly, dm: usize, gf: &Gf2) -> Poly {
            let mut wide = Poly::zero();
            for i in 0..=MAX_DEG / 2 {
                if p.c[i] != 0 {
                    wide.c[2 * i] = gf.sqr(p.c[i]);
                }
            }
            rem_monic(&wide, m, dm, gf)
        }

        fn prem(p: &Poly, b: &Poly, gf: &Gf2) -> Poly {
            let db = match b.deg() {
                Some(d) => d,
                None => return *p,
            };
            let lb = b.c[db];
            let mut r = *p;
            while let Some(dr) = r.deg() {
                if dr < db {
                    break;
                }
                let lr = r.c[dr];
                scale_in_place(&mut r, lb, dr, gf);
                for i in 0..=db {
                    r.c[dr - db + i] ^= gf.mul(b.c[i], lr);
                }
                r.c[dr] = 0;
            }
            r
        }

        fn gcd(p: &Poly, other: &Poly, gf: &Gf2) -> Poly {
            let mut a = *p;
            let mut b = *other;
            loop {
                match b.deg() {
                    None => return a,
                    Some(0) => return b,
                    Some(_) => {}
                }
                let r = prem(&a, &b, gf);
                a = b;
                b = r;
            }
        }

        pub fn roots_in_subspace(f: &Poly, df: usize, lv: &[u64], gf: &Gf2) -> Poly {
            let mut t = Poly::zero();
            t.c[1] = 1; // t
            let mut acc = Poly::zero();
            let mut pow = rem_monic(&t, f, df, gf); // t^(2^0) mod f
            for (i, &ai) in lv.iter().enumerate() {
                if ai != 0 {
                    for j in 0..df.max(1) {
                        acc.c[j] ^= gf.mul(pow.c[j], ai);
                    }
                }
                if i + 1 < lv.len() {
                    pow = sqr_mod_monic(&pow, f, df, gf);
                }
            }
            gcd(f, &acc, gf)
        }

        /// The old route from an arbitrary non-zero `q`: made monic by
        /// `scale_in_place`, as the pair loops did.
        pub fn roots_of(q: &Poly, d: usize, lead_inv: u64, lv: &[u64], gf: &Gf2) -> Poly {
            let mut monic = *q;
            scale_in_place(&mut monic, lead_inv, d, gf);
            roots_in_subspace(&monic, d, lv, gf)
        }

        fn quartic_general_with(x1: u64, x2: u64, t: &GeneralTargetPowers, gf: &Gf2) -> Poly {
            let s = x1 ^ x2;
            let p = gf.mul(x1, x2);
            let s2 = gf.sqr(s);
            let p2 = gf.sqr(p);
            let b = t.b;
            let bp2 = b ^ p2; // b + p²
            let s2x2 = gf.mul(s2, t.xr2); // s² x²
            let px = gf.mul(p, t.xr); // p x
            let p2x2 = gf.mul(p2, t.xr2); // p² x²

            let mut q = Poly::zero();
            q.c[4] = gf.sqr(s2x2 ^ bp2) ^ p2x2;
            q.c[3] = gf.mul(px, bp2 ^ s2x2);
            q.c[2] = gf.mul(p2, b) ^ gf.mul(s2x2, bp2) ^ gf.mul(p2, t.xr4);
            q.c[1] = gf.mul(px, gf.mul(s2, b) ^ gf.mul(t.xr2, bp2));
            q.c[0] = gf.sqr(gf.mul(t.xr2, p2) ^ gf.mul(b, s2) ^ gf.mul(b, t.xr2)) ^ gf.mul(p2x2, b);
            q
        }

        pub fn quartic_in_x3_general(x1: u64, x2: u64, xr: u64, b: u64, gf: &Gf2) -> Poly {
            quartic_general_with(x1, x2, &GeneralTargetPowers::new(xr, b, gf), gf)
        }

        pub fn decompose(xr: u64, l: u32, gf: &Gf2) -> Option<[u64; 3]> {
            let lv = super::super::subspace_poly(l, gf);
            let tp = TargetPowers::new(xr, gf);
            let span = 1u64 << l;

            let mut qs: Vec<Poly> = Vec::with_capacity(span as usize);
            let mut leads: Vec<u64> = Vec::with_capacity(span as usize);
            let mut scratch: Vec<u64> = Vec::with_capacity(span as usize);

            for x1 in 0..span {
                qs.clear();
                leads.clear();
                for x2 in x1..span {
                    let q = super::super::quartic_with(x1, x2, &tp, gf);
                    match q.deg() {
                        None => return Some([x1, x2, 0]),
                        Some(d) => leads.push(q.c[d]),
                    }
                    qs.push(q);
                }
                gf.batch_inv(&mut leads, &mut scratch);

                for (i, q) in qs.iter().enumerate() {
                    let d = q.deg().expect("zero quartics returned above");
                    let mut monic = *q;
                    scale_in_place(&mut monic, leads[i], d, gf);
                    let g = roots_in_subspace(&monic, d, &lv, gf);
                    let x2 = x1 + i as u64;
                    match g.deg() {
                        None | Some(0) => continue,
                        Some(1) => return Some([x1, x2, gf.mul(g.c[0], gf.inv(g.c[1]))]),
                        Some(_) => {
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

        pub fn oracle_decompose(o: &SubspaceOracle, xr: u64, gf: &Gf2) -> (Option<[u64; 3]>, u64) {
            let tp = GeneralTargetPowers::new(xr, o.b, gf);
            let span = &o.span;
            let count = span.len();
            let mut pairs = 0u64;

            let mut qs: Vec<Poly> = Vec::with_capacity(count);
            let mut leads: Vec<u64> = Vec::with_capacity(count);
            let mut scratch: Vec<u64> = Vec::with_capacity(count);

            for i1 in 0..count {
                let x1 = span[i1];
                qs.clear();
                leads.clear();
                for &x2 in &span[i1..] {
                    let q = quartic_general_with(x1, x2, &tp, gf);
                    pairs += 1;
                    match q.deg() {
                        None => {
                            let x3 = span.iter().copied().find(|&v| v != 0).unwrap_or(0);
                            return (Some([x1, x2, x3]), pairs);
                        }
                        Some(d) => leads.push(q.c[d]),
                    }
                    qs.push(q);
                }
                gf.batch_inv(&mut leads, &mut scratch);

                for (i, q) in qs.iter().enumerate() {
                    let d = q.deg().expect("zero quartics returned above");
                    let mut monic = *q;
                    scale_in_place(&mut monic, leads[i], d, gf);
                    let g = roots_in_subspace(&monic, d, &o.lv, gf);
                    let x2 = span[i1 + i];
                    match g.deg() {
                        None | Some(0) => continue,
                        Some(1) => {
                            return (Some([x1, x2, gf.mul(g.c[0], gf.inv(g.c[1]))]), pairs);
                        }
                        Some(_) => {
                            for &t in span.iter() {
                                let mut v = 0u64;
                                for j in (0..=MAX_DEG).rev() {
                                    v = gf.mul(v, t) ^ g.c[j];
                                }
                                if v == 0 {
                                    return (Some([x1, x2, t]), pairs);
                                }
                            }
                        }
                    }
                }
            }
            (None, pairs)
        }
    }

    fn xorshift(state: &mut u64) -> u64 {
        *state ^= *state >> 12;
        *state ^= *state << 25;
        *state ^= *state >> 27;
        state.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    /// Which multiply `gf` dispatches to, for assertion messages.
    fn kernel_name(gf: &Gf2) -> &'static str {
        if gf.has_clmul {
            "carry-less"
        } else {
            "portable"
        }
    }

    /// Both multiplies of the field of degree `n`: the carry-less
    /// instruction where the host has it, and the portable fallback.
    fn both_fields(n: u32) -> [Gf2; 2] {
        let fast = Gf2::new(&find_irreducible_sparse(n).unwrap());
        let mut portable = fast.clone();
        portable.has_clmul = false;
        [fast, portable]
    }

    fn random_independent(l: u32, gf: &Gf2, s: &mut u64) -> Vec<u64> {
        'retry: loop {
            let cand: Vec<u64> = (0..l).map(|_| xorshift(s) & gf.mask).collect();
            let mut seen = std::collections::HashSet::new();
            for idx in 0..1u64 << l {
                let v = (0..l as usize)
                    .filter(|j| (idx >> j) & 1 == 1)
                    .fold(0, |v, j| v ^ cand[j]);
                if !seen.insert(v) {
                    continue 'retry;
                }
            }
            return cand;
        }
    }

    fn span_of(basis: &[u64]) -> Vec<u64> {
        (0..1u64 << basis.len())
            .map(|idx| {
                (0..basis.len())
                    .filter(|j| (idx >> j) & 1 == 1)
                    .fold(0, |v, j| v ^ basis[j])
            })
            .collect()
    }

    /// Subspace polynomials of every dimension `0..=min(n, 12)` (on the
    /// low-order and on a random basis) with the subspace they vanish
    /// on, then degenerate coefficient vectors and random ones of every
    /// short length, including lengths past `n` where the inverse
    /// Frobenius wraps; those come with the span `{0, 1}` to plant from.
    fn lv_family(gf: &Gf2, s: &mut u64) -> Vec<(Vec<u64>, Vec<u64>)> {
        let n = gf.n;
        let mut out = Vec::new();
        for l in 0..=n.min(12) {
            let low: Vec<u64> = (0..l).map(|i| 1u64 << i).collect();
            let random = random_independent(l, gf, s);
            for basis in [low, random] {
                out.push((subspace_poly_for_basis(&basis, gf), span_of(&basis)));
            }
        }
        let mut odd: Vec<Vec<u64>> = vec![
            vec![],
            vec![0],
            vec![0, 0, 0, 0, 1],
            vec![1, 0, 0, 0, 0, 0, 0, 0, 0],
        ];
        for len in 1..=9 {
            odd.push((0..len).map(|_| xorshift(s) & gf.mask).collect());
        }
        out.extend(odd.into_iter().map(|lv| (lv, vec![0, 1])));
        out
    }

    /// Every monic quartic over `F_{2^n}`, `n = 1..=4` (all `2^{4n}` of
    /// them), each scaled by a random non-zero leading coefficient, on
    /// every vector of `lv_family`: at these sizes each of the six
    /// leading coefficients the written-out gcd relies on vanishes on a
    /// large fraction of inputs, so every fallback exit and every gcd
    /// degree is taken many times.
    #[test]
    fn quartic_route_matches_994784af_on_every_quartic_of_tiny_fields() {
        let mut s = 0x0994_784A_F000_0001u64;
        for n in 1..=4u32 {
            for gf in both_fields(n) {
                let mut by_degree = [0usize; 5];
                for (lv, _) in lv_family(&gf, &mut s) {
                    let horner = LvHorner::new(&lv, &gf);
                    for idx in 0..1u64 << (4 * n) {
                        let k = (xorshift(&mut s) & gf.mask).max(1);
                        let mut q = Poly::zero();
                        for j in 0..4 {
                            q.c[j] = gf.mul((idx >> (j as u32 * n)) & gf.mask, k);
                        }
                        q.c[4] = k;
                        let lead_inv = gf.inv(k);
                        let want = old::roots_of(&q, 4, lead_inv, &lv, &gf);
                        let got = subspace_roots_of(&q, 4, lead_inv, &lv, &horner, &gf);
                        assert_eq!(
                            got.c,
                            want.c,
                            "n={n} lv={lv:?} q={:?} {}",
                            q.c,
                            kernel_name(&gf)
                        );
                        by_degree[want.deg().unwrap()] += 1;
                    }
                }
                assert!(by_degree.iter().all(|&c| c > 0), "n={n}: {by_degree:?}");
            }
        }
    }

    /// Random and structured quartics at mid and top widths (up to the
    /// `n = 63` limit of `Gf2`): squares (`f₁ = f₃ = 0`), `f₃ = 0`,
    /// `f₀ = 0` (the root 0 lies in every subspace), repeated subspace
    /// roots, and one to four planted subspace roots, against every
    /// degree `0..=4` of `q` so the dispatch is exercised as well.
    #[test]
    fn quartic_route_matches_994784af_at_wide_fields() {
        let mut s = 0x0994_784A_F000_0002u64;
        for n in [5u32, 8, 17, 24, 31, 40, 53, 62, 63] {
            for gf in both_fields(n) {
                let mut by_degree = [0usize; 5];
                for (lv, span) in lv_family(&gf, &mut s) {
                    let horner = LvHorner::new(&lv, &gf);
                    for trial in 0..400 {
                        let mut r = || xorshift(&mut s) & gf.mask;
                        let k = r().max(1);
                        let mut f = [r(), r(), r(), r()];
                        match trial % 8 {
                            0 => {}
                            1 => {
                                f[1] = 0;
                                f[3] = 0;
                            }
                            2 => f[3] = 0,
                            3 => f[0] = 0,
                            _ => {
                                // Roots: 1..=4 planted in the span (possibly
                                // repeated), the rest random.
                                let planted = trial % 8 - 3;
                                let roots: Vec<u64> = (0..4)
                                    .map(|i| {
                                        let x = xorshift(&mut s);
                                        if i < planted {
                                            span[(x >> 11) as usize % span.len()]
                                        } else if trial % 3 == 0 && i > 0 {
                                            0
                                        } else {
                                            x & gf.mask
                                        }
                                    })
                                    .collect();
                                let mut p = [1u64, 0, 0, 0, 0];
                                for &root in &roots {
                                    let mut next = [0u64; 5];
                                    for i in 0..4 {
                                        next[i + 1] ^= p[i];
                                        next[i] ^= gf.mul(p[i], root);
                                    }
                                    p = next;
                                }
                                f.copy_from_slice(&p[..4]);
                            }
                        }
                        // Degree 4 mostly; every 16th trial drops leading
                        // coefficients to reach the generic route.
                        let d = if trial % 16 == 15 {
                            (trial / 16) % 4
                        } else {
                            4
                        };
                        let mut q = Poly::zero();
                        for j in 0..d {
                            q.c[j] = gf.mul(f[j], k);
                        }
                        q.c[d] = k;
                        let lead_inv = gf.inv(k);
                        let want = old::roots_of(&q, d, lead_inv, &lv, &gf);
                        let got = subspace_roots_of(&q, d, lead_inv, &lv, &horner, &gf);
                        assert_eq!(
                            got.c,
                            want.c,
                            "n={n} d={d} lv={lv:?} q={:?} {}",
                            q.c,
                            kernel_name(&gf)
                        );
                        if d == 4 {
                            by_degree[want.deg().unwrap()] += 1;
                        }
                    }
                }
                assert!(
                    by_degree[0] > 0 && by_degree[1] > 0 && by_degree[2] > 0,
                    "n={n}: {by_degree:?}"
                );
            }
        }
    }

    /// The `b = 1` decomposer must return exactly what `994784af`'s did,
    /// with and without the carry-less multiply, on every target of the
    /// tiny fields and on random targets (plus 0, 1 and subspace
    /// elements) of larger ones.
    #[test]
    fn decompose_matches_994784af() {
        let mut s = 0x0994_784A_F000_0003u64;
        let mut found = [0usize; 2];
        for (n, ls) in [
            (2u32, &[0u32, 1, 2][..]),
            (3, &[0, 1, 2, 3]),
            (4, &[1, 2, 3]),
            (5, &[1, 2, 3]),
            (7, &[2, 3]),
            (11, &[3, 4]),
            (16, &[4, 5]),
            (20, &[5]),
            (63, &[3, 4]),
        ] {
            for gf in both_fields(n) {
                for &l in ls {
                    let xrs: Vec<u64> = if n <= 5 {
                        (0..1u64 << n).collect()
                    } else {
                        let mut v = vec![0, 1, (1u64 << l) - 1, 1u64 << l];
                        v.extend((0..12).map(|_| xorshift(&mut s) & gf.mask));
                        v
                    };
                    for xr in xrs {
                        let want = old::decompose(xr, l, &gf);
                        assert_eq!(
                            decompose(xr, l, &gf),
                            want,
                            "n={n} l={l} x_R={xr} {}",
                            kernel_name(&gf)
                        );
                        found[want.is_some() as usize] += 1;
                    }
                }
            }
        }
        assert!(found[0] > 0 && found[1] > 0, "degenerate: {found:?}");
    }

    /// `SubspaceOracle::decompose` against `994784af`'s loop verbatim
    /// (batched inverses, the old general quartic, the `rem_monic` gcd):
    /// witnesses and pair counts, every target of the tiny fields, random
    /// bases and `b`, up to `n = 63`.
    #[test]
    fn subspace_oracle_matches_994784af() {
        let mut s = 0x0994_784A_F000_0004u64;
        let mut found = [0usize; 2];
        for (n, ls) in [
            (1u32, &[0u32, 1][..]),
            (2, &[0, 1, 2]),
            (3, &[1, 2, 3]),
            (4, &[1, 2, 3, 4]),
            (6, &[2, 3, 4]),
            (9, &[3, 4]),
            (13, &[4, 5]),
            (24, &[5]),
            (40, &[4]),
            (63, &[3, 5]),
        ] {
            for gf in both_fields(n) {
                for &l in ls {
                    let bases = [
                        (0..l).map(|i| 1u64 << i).collect::<Vec<_>>(),
                        random_independent(l, &gf, &mut s),
                    ];
                    for basis in bases {
                        for b in [1, (xorshift(&mut s) & gf.mask).max(1)] {
                            let oracle = SubspaceOracle::new(&basis, b, &gf);
                            let xrs: Vec<u64> = if n <= 4 {
                                (0..1u64 << n).collect()
                            } else {
                                let mut v = vec![0, 1, oracle.span[oracle.span.len() - 1]];
                                v.extend((0..8).map(|_| xorshift(&mut s) & gf.mask));
                                v
                            };
                            for xr in xrs {
                                let want = old::oracle_decompose(&oracle, xr, &gf);
                                assert_eq!(
                                    oracle.decompose(xr, &gf),
                                    want,
                                    "n={n} l={l} b={b} basis={basis:?} x_R={xr} {}",
                                    kernel_name(&gf)
                                );
                                found[want.0.is_some() as usize] += 1;
                            }
                        }
                    }
                }
            }
        }
        assert!(found[0] > 0 && found[1] > 0, "degenerate: {found:?}");
    }

    /// The general quartic against `994784af`'s formula, including a
    /// curve constant with bits above the field width (the oracle does
    /// not reduce `b`): the rewrite leans on `reduce` being linear, which
    /// holds for any 128-bit input, so even that case must agree.
    #[test]
    fn general_quartic_matches_994784af_even_for_unreduced_b() {
        let mut s = 0x0994_784A_F000_0005u64;
        for n in [1u32, 2, 3, 7, 20, 33, 63] {
            for gf in both_fields(n) {
                for i in 0..4000 {
                    let mut r = || xorshift(&mut s) & gf.mask;
                    let (x1, x2, xr) = (r(), r(), r());
                    let b = if i % 2 == 0 {
                        r()
                    } else {
                        r() | (1u64 << 63) >> (i % 7)
                    };
                    // Unreduced b overflows the fold's table only when the
                    // product exceeds 2n−1 bits; `reduce`'s debug check
                    // would fire there, so keep that case to release.
                    if cfg!(debug_assertions) && b > gf.mask {
                        continue;
                    }
                    let want = old::quartic_in_x3_general(x1, x2, xr, b, &gf);
                    let got = quartic_in_x3_general(x1, x2, xr, b, &gf);
                    assert_eq!(got.c, want.c, "n={n} b={b} {}", kernel_name(&gf));
                }
            }
        }
    }
}
