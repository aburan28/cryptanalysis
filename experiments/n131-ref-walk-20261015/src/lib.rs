//! Signed-Frobenius rho walks on Koblitz curves `y^2 + xy = x^3 + a x^2 + 1`,
//! written once over a three-limb field word and instantiated at
//!
//! * `n = 131, a = 0` (ECC2K-130's curve), field arithmetic = the Rust port of
//!   `cryptanalysis:ecc2k130/src/f131.h` in `canon-n131-loop-20261014`
//!   (KAT-exact against the header), and
//! * `n = 83, a = 1` (crypto's legacy n = 83 fixture, r ~ 2^52.93), where walks
//!   run to verified logarithms.
//!
//! The walk structure follows crypto's `StrongRhoG` (rung 3): lockstep lanes,
//! one batched (Montgomery) inversion per step, normal-basis canonicalization
//! of the signed-Frobenius orbit, Itoh-Tsujii inversion with Frobenius powers
//! as rotations, a fruitless-cycle history.  Two designs are priced:
//!
//! * **(a) Bailey's walk** (ePrint 2009/541 sec. 3): `P <- P + sigma^j(P)`,
//!   `j = 3 + ((HW(x)/2) mod 8)`, HW in the normal basis; the state is never
//!   canonicalized except at a distinguished point.
//! * **(b) a canonicalizing adding walk**: `P <- canon(P + R_{h(P)})`, the
//!   canonical form by `lift_scan` of `canon-n131-20261014`.
//!
//! Both use the same class-invariant distinguished-point predicate
//! `HW(x) <= t` and continue after a distinguished point (the 2009 design).

#![allow(clippy::needless_range_loop, clippy::too_many_arguments)]

pub use canon_n131::{Rng, G, W3};
use canon_n131_loop::{field as f131, ToCyclic};
use std::collections::HashMap;

#[cfg(all(target_arch = "x86_64", not(target_feature = "pclmulqdq")))]
compile_error!("build with -C target-feature=+pclmulqdq (see .cargo/config.toml)");

// ---------------------------------------------------------------- fields ---

/// A binary field of degree `N <= 192` in three 64-bit limbs, plus the
/// cyclic-word operations of `canon-n131` instantiated at the same `N`.
pub trait Field: 'static {
    const N: u32;
    const NAME: &'static str;
    fn mul(a: &W3, b: &W3) -> W3;
    fn sqr(a: &W3) -> W3;
    /// `to_nb(z^i)` for `i < N`: the polynomial -> cyclic normal basis map,
    /// in which squaring is `rotl` by one.
    fn nb_images() -> Vec<W3>;
    fn rotl(x: W3, s: u32) -> W3;
    fn lift_scan(x: W3) -> (W3, u32);
    fn exhaustive(x: W3) -> (W3, u32);
    fn lt(a: W3, b: W3) -> bool;
    fn mask() -> W3;
}

/// GF(2^131) in the polynomial basis of f131.h (modulus
/// `0xd1d0d000d0000000d000000000000000d`).
pub struct F131;

impl Field for F131 {
    const N: u32 = 131;
    const NAME: &'static str = "f131h";
    #[inline(always)]
    fn mul(a: &W3, b: &W3) -> W3 {
        f131::mul(a, b)
    }
    #[inline(always)]
    fn sqr(a: &W3) -> W3 {
        f131::sqr(a)
    }
    fn nb_images() -> Vec<W3> {
        (0..131)
            .map(|i| ToCyclic::apply_ref(&f131::from_polynomial(&unit(i))))
            .collect()
    }
    #[inline(always)]
    fn rotl(x: W3, s: u32) -> W3 {
        G::<131, 64>::rotl(x, s)
    }
    #[inline(always)]
    fn lift_scan(x: W3) -> (W3, u32) {
        G::<131, 64>::lift_scan(x)
    }
    #[inline(always)]
    fn exhaustive(x: W3) -> (W3, u32) {
        G::<131, 64>::exhaustive(x)
    }
    #[inline(always)]
    fn lt(a: W3, b: W3) -> bool {
        G::<131, 64>::lt(a, b)
    }
    fn mask() -> W3 {
        G::<131, 64>::MASK
    }
}

/// GF(2^83) = GF(2)[z]/(z^83 + z^7 + z^4 + z^2 + 1) (crypto's legacy fixture).
pub struct F83;

pub const M83_LOW: u128 = (1 << 7) | (1 << 4) | (1 << 2) | 1;
const MASK83: u128 = (1u128 << 83) - 1;

#[inline(always)]
fn to128(a: &W3) -> u128 {
    a[0] as u128 | ((a[1] as u128) << 64)
}
#[inline(always)]
fn from128(v: u128) -> W3 {
    [v as u64, (v >> 64) as u64, 0]
}

impl F83 {
    #[inline(always)]
    fn reduce(lo: u128, hi: u128) -> u128 {
        // V = lo + hi * z^128, degree <= 164.
        let h = (lo >> 83) | (hi << 45);
        let mut l = (lo & MASK83) ^ h ^ (h << 2) ^ (h << 4) ^ (h << 7);
        let h2 = l >> 83;
        l = (l & MASK83) ^ h2 ^ (h2 << 2) ^ (h2 << 4) ^ (h2 << 7);
        l
    }
}

impl Field for F83 {
    const N: u32 = 83;
    const NAME: &'static str = "f83";
    #[inline(always)]
    fn mul(a: &W3, b: &W3) -> W3 {
        let (l0, l1) = f131::clmul(a[0], b[0]);
        let (h0, h1) = f131::clmul(a[1], b[1]);
        let (mut m0, mut m1) = f131::clmul(a[0] ^ a[1], b[0] ^ b[1]);
        m0 ^= l0 ^ h0;
        m1 ^= l1 ^ h1;
        let lo = l0 as u128 | (((l1 ^ m0) as u128) << 64);
        let hi = (h0 ^ m1) as u128 | ((h1 as u128) << 64);
        from128(Self::reduce(lo, hi))
    }
    #[inline(always)]
    fn sqr(a: &W3) -> W3 {
        let (l0, l1) = f131::clmul(a[0], a[0]);
        let (h0, h1) = f131::clmul(a[1], a[1]);
        from128(Self::reduce(l0 as u128 | ((l1 as u128) << 64), h0 as u128 | ((h1 as u128) << 64)))
    }
    fn nb_images() -> Vec<W3> {
        // First normal element among 2, 3, ... (crypto's NormalBasis::new):
        // columns of to_poly are its conjugates; to_nb is the inverse.
        for cand in 2u64.. {
            let mut conj = Vec::with_capacity(83);
            let mut v = [cand, 0, 0];
            for _ in 0..83 {
                conj.push(v);
                v = Self::sqr(&v);
            }
            if let Some(inv) = invert_columns(&conj, 83) {
                return inv;
            }
        }
        unreachable!()
    }
    #[inline(always)]
    fn rotl(x: W3, s: u32) -> W3 {
        G::<83, 64>::rotl(x, s)
    }
    #[inline(always)]
    fn lift_scan(x: W3) -> (W3, u32) {
        G::<83, 64>::lift_scan(x)
    }
    #[inline(always)]
    fn exhaustive(x: W3) -> (W3, u32) {
        G::<83, 64>::exhaustive(x)
    }
    #[inline(always)]
    fn lt(a: W3, b: W3) -> bool {
        G::<83, 64>::lt(a, b)
    }
    fn mask() -> W3 {
        G::<83, 64>::MASK
    }
}

pub fn unit(i: u32) -> W3 {
    let mut w = [0u64; 3];
    w[(i / 64) as usize] = 1 << (i % 64);
    w
}

#[inline(always)]
pub fn xor(a: &W3, b: &W3) -> W3 {
    [a[0] ^ b[0], a[1] ^ b[1], a[2] ^ b[2]]
}

#[inline(always)]
pub fn is_zero(a: &W3) -> bool {
    (a[0] | a[1] | a[2]) == 0
}

#[inline(always)]
pub fn bit(a: &W3, i: u32) -> bool {
    (a[(i / 64) as usize] >> (i % 64)) & 1 == 1
}

#[inline(always)]
pub fn popcnt(a: &W3) -> u32 {
    a[0].count_ones() + a[1].count_ones() + a[2].count_ones()
}

/// Columns of the inverse of the `n x n` F2 matrix whose columns are `cols`.
pub fn invert_columns(cols: &[W3], n: usize) -> Option<Vec<W3>> {
    // rows[r] = (row r of the matrix, row r of the identity)
    let mut rows: Vec<(W3, W3)> = (0..n)
        .map(|r| {
            let mut row = [0u64; 3];
            for (i, c) in cols.iter().enumerate() {
                if bit(c, r as u32) {
                    row[i / 64] |= 1 << (i % 64);
                }
            }
            (row, unit(r as u32))
        })
        .collect();
    for p in 0..n {
        let f = (p..n).find(|&r| bit(&rows[r].0, p as u32))?;
        rows.swap(p, f);
        let (pc, pa) = rows[p];
        for r in 0..n {
            if r != p && bit(&rows[r].0, p as u32) {
                rows[r] = (xor(&rows[r].0, &pc), xor(&rows[r].1, &pa));
            }
        }
    }
    // rows now hold the inverse's rows; return its columns.
    let mut out = vec![[0u64; 3]; n];
    for (i, row) in rows.iter().enumerate() {
        for c in 0..n {
            if bit(&row.1, c as u32) {
                out[c][i / 64] |= 1 << (i % 64);
            }
        }
    }
    Some(out)
}

/// An F2-linear map on `<= 192` bits applied by nibble tables.
pub struct Linear {
    pub t: Vec<[W3; 16]>,
}

impl Linear {
    pub fn from_images(images: &[W3]) -> Self {
        let chunks = images.len().div_ceil(4);
        let mut t = vec![[[0u64; 3]; 16]; chunks];
        for k in 0..chunks {
            for v in 1..16usize {
                let mut w = [0u64; 3];
                for b in 0..4 {
                    if (v >> b) & 1 == 1 {
                        if let Some(im) = images.get(4 * k + b) {
                            w = xor(&w, im);
                        }
                    }
                }
                t[k][v] = w;
            }
        }
        Linear { t }
    }

    #[inline(always)]
    pub fn apply(&self, x: &W3) -> W3 {
        let mut o = [0u64; 3];
        for (k, e) in self.t.iter().enumerate() {
            let v = ((x[k / 16] >> (4 * (k % 16))) & 15) as usize;
            let w = &e[v];
            o[0] ^= w[0];
            o[1] ^= w[1];
            o[2] ^= w[2];
        }
        o
    }

    /// Bit-by-bit reference (test oracle).
    pub fn apply_ref(images: &[W3], x: &W3) -> W3 {
        let mut o = [0u64; 3];
        for (i, im) in images.iter().enumerate() {
            if bit(x, i as u32) {
                o = xor(&o, im);
            }
        }
        o
    }
}

/// Both directions of the polynomial <-> cyclic normal basis change.
pub struct Basis {
    pub to_nb: Linear,
    pub from_nb: Linear,
    pub to_images: Vec<W3>,
    pub from_images: Vec<W3>,
}

impl Basis {
    pub fn new<F: Field>() -> Self {
        let to_images = F::nb_images();
        let from_images = invert_columns(&to_images, F::N as usize).expect("basis change invertible");
        Basis {
            to_nb: Linear::from_images(&to_images),
            from_nb: Linear::from_images(&from_images),
            to_images,
            from_images,
        }
    }
}

// ---------------------------------------------------------------- curve ---

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct Pt {
    pub x: W3,
    pub y: W3,
    pub inf: bool,
}

pub const INF: Pt = Pt { x: [0; 3], y: [0; 3], inf: true };

impl Pt {
    pub fn new(x: W3, y: W3) -> Pt {
        Pt { x, y, inf: false }
    }
}

/// `y^2 + xy = x^3 + a x^2 + 1` over `F`.
pub struct Curve<F: Field> {
    pub a: W3,
    pub b: Basis,
    _f: std::marker::PhantomData<F>,
}

impl<F: Field> Curve<F> {
    pub fn new(a: u64) -> Self {
        assert!(a <= 1);
        Curve { a: [a, 0, 0], b: Basis::new::<F>(), _f: std::marker::PhantomData }
    }

    #[inline(always)]
    pub fn to_nb(&self, x: &W3) -> W3 {
        self.b.to_nb.apply(x)
    }
    #[inline(always)]
    pub fn from_nb(&self, x: &W3) -> W3 {
        self.b.from_nb.apply(x)
    }

    /// `x^(2^k)` as a rotation of normal coordinates.
    #[inline(always)]
    pub fn pow2k(&self, x: &W3, k: u32) -> W3 {
        self.from_nb(&F::rotl(self.to_nb(x), k % F::N))
    }

    /// Itoh-Tsujii inversion with the `x^(2^k)` steps as rotations (crypto's
    /// `StrongRhoG::inv`).
    pub fn inv(&self, v: &W3) -> W3 {
        assert!(!is_zero(v), "inverse of zero");
        let e = F::N - 1;
        let mut c = *v;
        let mut k = 1u32;
        let bits = 32 - e.leading_zeros();
        for i in (0..bits - 1).rev() {
            let raised = self.pow2k(&c, k);
            c = F::mul(&c, &raised);
            k *= 2;
            if (e >> i) & 1 == 1 {
                c = F::mul(&F::sqr(&c), v);
                k += 1;
            }
        }
        F::sqr(&c)
    }

    /// Montgomery's trick in place: every nonzero entry inverted; zero entries
    /// are left zero (the caller falls back to the generic group law).
    pub fn batch_inv(&self, xs: &mut [W3], pre: &mut Vec<W3>) {
        pre.clear();
        let mut acc = [1u64, 0, 0];
        for x in xs.iter() {
            if !is_zero(x) {
                acc = F::mul(&acc, x);
            }
            pre.push(acc);
        }
        if pre.is_empty() {
            return;
        }
        let mut inv = self.inv(&acc);
        for i in (0..xs.len()).rev() {
            if is_zero(&xs[i]) {
                continue;
            }
            let before = if i == 0 { [1u64, 0, 0] } else { pre[i - 1] };
            let xi = xs[i];
            xs[i] = F::mul(&inv, &before);
            inv = F::mul(&inv, &xi);
        }
    }

    pub fn on_curve(&self, p: &Pt) -> bool {
        if p.inf {
            return true;
        }
        let x2 = F::sqr(&p.x);
        let lhs = xor(&F::sqr(&p.y), &F::mul(&p.x, &p.y));
        let rhs = xor(&xor(&F::mul(&x2, &p.x), &F::mul(&self.a, &x2)), &[1, 0, 0]);
        lhs == rhs
    }

    pub fn neg(&self, p: &Pt) -> Pt {
        if p.inf {
            *p
        } else {
            Pt::new(p.x, xor(&p.x, &p.y))
        }
    }

    #[inline(always)]
    pub fn add_slope(&self, p: &Pt, q: &Pt, lam: &W3) -> Pt {
        let x3 = xor(&xor(&xor(&F::sqr(lam), lam), &xor(&p.x, &q.x)), &self.a);
        let y3 = xor(&xor(&F::mul(lam, &xor(&p.x, &x3)), &x3), &p.y);
        Pt::new(x3, y3)
    }

    pub fn double(&self, p: &Pt) -> Pt {
        if p.inf || is_zero(&p.x) {
            return INF;
        }
        let lam = xor(&p.x, &F::mul(&p.y, &self.inv(&p.x)));
        let x3 = xor(&xor(&F::sqr(&lam), &lam), &self.a);
        let y3 = xor(&F::sqr(&p.x), &F::mul(&xor(&lam, &[1, 0, 0]), &x3));
        Pt::new(x3, y3)
    }

    pub fn add(&self, p: &Pt, q: &Pt) -> Pt {
        if p.inf {
            return *q;
        }
        if q.inf {
            return *p;
        }
        if p.x == q.x {
            return if xor(&p.y, &q.y) == p.x { INF } else { self.double(p) };
        }
        let lam = F::mul(&xor(&p.y, &q.y), &self.inv(&xor(&p.x, &q.x)));
        self.add_slope(p, q, &lam)
    }

    /// `[k]P` for a scalar of up to 192 bits.
    pub fn smul(&self, p: &Pt, k: &W3) -> Pt {
        let mut r = INF;
        for i in (0..192).rev() {
            r = self.double(&r);
            if bit(k, i) {
                r = self.add(&r, p);
            }
        }
        r
    }

    pub fn frob(&self, p: &Pt, t: u32) -> Pt {
        if p.inf {
            return *p;
        }
        Pt::new(self.pow2k(&p.x, t), self.pow2k(&p.y, t))
    }

    /// Canonical representative of `{±phi^k(P)}`: least rotation of the x
    /// normal coordinates (lift_scan), sign by the smaller y normal word.
    /// Returns `(point, x normal word, k, negated)`.
    #[inline(always)]
    pub fn canon_with<const EXH: bool>(&self, p: &Pt) -> (Pt, W3, u32, bool) {
        let xc = self.to_nb(&p.x);
        let (cx, k) = if EXH { F::exhaustive(xc) } else { F::lift_scan(xc) };
        let yk = F::rotl(self.to_nb(&p.y), k);
        let yn = xor(&yk, &cx);
        let neg = F::lt(yn, yk);
        let cy = if neg { yn } else { yk };
        (Pt::new(self.from_nb(&cx), self.from_nb(&cy)), cx, k, neg)
    }

    /// Exhaustive definition over all `2N` orbit members (test oracle).
    pub fn canon_ref(&self, p: &Pt) -> Pt {
        let mut best: Option<(W3, W3)> = None;
        let xc = self.to_nb(&p.x);
        let yc = self.to_nb(&p.y);
        for k in 0..F::N {
            let xk = F::rotl(xc, k);
            let yk = F::rotl(yc, k);
            for y in [yk, xor(&yk, &xk)] {
                let better = match &best {
                    None => true,
                    Some((bx, by)) => F::lt(xk, *bx) || (xk == *bx && F::lt(y, *by)),
                };
                if better {
                    best = Some((xk, y));
                }
            }
        }
        let (bx, by) = best.unwrap();
        Pt::new(self.from_nb(&bx), self.from_nb(&by))
    }
}

// --------------------------------------------------------------- scalars ---

/// Arithmetic modulo a prime `r < 2^63` (the n = 83 subgroup, r ~ 2^52.93).
#[derive(Clone, Copy, Debug)]
pub struct Zr {
    pub r: u64,
}

impl Zr {
    #[inline(always)]
    pub fn mul(&self, a: u64, b: u64) -> u64 {
        ((a as u128 * b as u128) % self.r as u128) as u64
    }
    #[inline(always)]
    pub fn add(&self, a: u64, b: u64) -> u64 {
        let s = a + b;
        if s >= self.r {
            s - self.r
        } else {
            s
        }
    }
    #[inline(always)]
    pub fn sub(&self, a: u64, b: u64) -> u64 {
        if a >= b {
            a - b
        } else {
            a + self.r - b
        }
    }
    #[inline(always)]
    pub fn neg(&self, a: u64) -> u64 {
        if a == 0 {
            0
        } else {
            self.r - a
        }
    }
    pub fn pow(&self, mut b: u64, mut e: u64) -> u64 {
        let mut acc = 1u64;
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mul(acc, b);
            }
            b = self.mul(b, b);
            e >>= 1;
        }
        acc
    }
    pub fn inv(&self, a: u64) -> Option<u64> {
        if a % self.r == 0 {
            None
        } else {
            Some(self.pow(a, self.r - 2))
        }
    }
}

// ------------------------------------------------------------------ walks ---

/// Arms: what a lane does per step.
pub const BAILEY: u8 = 0;
/// Bailey with the distinguished-point canonicalization replaced by the raw
/// x word (ablation: the at-DP canonicalization's share).  Timing only.
pub const BAILEY_NODPC: u8 = 1;
/// Canonicalizing adding walk, lift_scan.
pub const CANON: u8 = 2;
/// Canonicalizing walk with lift_scan replaced by `k = 0` (the basis changes
/// and sign fold kept; the fruitless-cycle test computed but not acted on,
/// amendment 1): lift_scan's share.  Timing only.
pub const CANON_NOLIFT: u8 = 3;
/// Adding walk with no canonicalization at all (HW for the DP test kept):
/// canonicalization's whole share.  Timing only; not a class walk.
pub const CANON_NULL: u8 = 4;
/// Canonicalizing walk with the exhaustive canonicalizer: the timing
/// positive control (a known, large extra cost on the same path).
pub const CANON_EXH: u8 = 5;
/// Canonicalizing walk on Frobenius orbits only (no negation fold): the
/// classes halve in size (A = n instead of 2n), so the expected steps grow by
/// exactly sqrt(2) with the selector unchanged.  The steps-to-collision
/// positive control.  The DP key carries a fingerprint of y so that P and -P
/// (different classes here) do not share a key.
pub const CANON_NONEG: u8 = 6;

pub fn is_bailey(arm: u8) -> bool {
    arm <= BAILEY_NODPC
}

/// Per-curve walk context.
pub struct Ctx<F: Field> {
    pub c: Curve<F>,
    /// Distinguished when `HW(x in normal basis) <= dp_hw`.
    pub dp_hw: u32,
    /// Adding-walk jumps and, when tracking, their logs (`R_i = [s_i]G`).
    pub jumps: Vec<Pt>,
    pub jump_s: Vec<u64>,
    /// Scalar ring (tracking only; `r = 0` when no logs are tracked).
    pub zr: Zr,
    pub lam_pow: Vec<u64>,
    /// `1 + lambda^j` for `j = 0..N` (Bailey tracking).
    pub one_plus: Vec<u64>,
    /// Restart stream: `cursor <- cursor + stride`, `cursor_a += stride_a`.
    pub stride: Pt,
    pub stride_a: u64,
    /// Walk length without a distinguished point before a restart.
    pub cap: u32,
}

impl<F: Field> Ctx<F> {
    pub fn new(c: Curve<F>, dp_hw: u32, jumps: Vec<Pt>, jump_s: Vec<u64>, r: u64, lambda: u64, stride: Pt, stride_a: u64, cap: u32) -> Self {
        let zr = Zr { r: r.max(2) };
        let mut lam_pow = vec![];
        let mut one_plus = vec![];
        let mut cur = 1u64 % zr.r;
        for _ in 0..F::N {
            lam_pow.push(cur);
            one_plus.push(zr.add(1, cur));
            cur = zr.mul(cur, lambda % zr.r);
        }
        if r > 1 {
            assert_eq!(cur, 1, "lambda must have order dividing N");
        }
        Ctx { c, dp_hw, jumps, jump_s, zr, lam_pow, one_plus, stride, stride_a, cap }
    }
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Hist {
    pub p: Pt,
    pub a: u64,
    pub b: u64,
}

#[derive(Clone, Copy, Debug, Default)]
pub struct Lane {
    pub p: Pt,
    /// Normal-basis x word of `p` for the canonical arms (the DP key).
    pub key: W3,
    pub hw: u32,
    pub a: u64,
    pub b: u64,
    pub hist: [Hist; 4],
    pub since_dp: u32,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Stats {
    pub steps: u64,
    pub dps: u64,
    pub escapes: u64,
    pub restarts: u64,
    pub zero_den: u64,
    pub checksum: u64,
}

/// What a distinguished point tells the walker.
pub enum Ctl {
    Go,
    Restart,
    Stop,
}

pub trait Sink {
    fn dp(&mut self, lane: usize, key: &W3, a: u64, b: u64) -> Ctl;
}

/// Timing sink: counts and folds the keys (no table).
#[derive(Default)]
pub struct Fold {
    pub h: u64,
    pub n: u64,
}

impl Sink for Fold {
    #[inline(always)]
    fn dp(&mut self, lane: usize, key: &W3, _a: u64, _b: u64) -> Ctl {
        self.n += 1;
        self.h = (self.h ^ key[0] ^ key[1].rotate_left(21) ^ key[2].rotate_left(42) ^ lane as u64)
            .wrapping_mul(0x9E37_79B9_7F4A_7C15)
            .rotate_left(29);
        Ctl::Go
    }
}

/// Jump index of a canonical point (fixed mixer on its polynomial x).
#[inline(always)]
pub fn jump_index(x: &W3, r: usize) -> usize {
    let mut v = x[0] ^ x[1].rotate_left(21) ^ x[2].rotate_left(42) ^ 0x9e37_79b9_7f4a_7c15;
    v ^= v >> 30;
    v = v.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    v ^= v >> 27;
    v = v.wrapping_mul(0x94d0_49bb_1331_11eb);
    v ^= v >> 31;
    (v % r as u64) as usize
}

#[derive(Clone)]
pub struct Walker {
    pub lanes: Vec<Lane>,
    pub cursor: Pt,
    pub cursor_a: u64,
    pub st: Stats,
    den: Vec<W3>,
    pre: Vec<W3>,
    addend: Vec<Pt>,
    mult: Vec<u64>,
}

impl Walker {
    /// Lanes start at `starts` (with logs `a_i`, `b = 1` when tracking);
    /// canonical arms canonicalize the start first.
    pub fn new<F: Field>(ctx: &Ctx<F>, arm: u8, starts: &[Pt], start_a: &[u64], cursor: Pt, cursor_a: u64) -> Self {
        let n = starts.len();
        let mut w = Walker {
            lanes: vec![Lane::default(); n],
            cursor,
            cursor_a,
            st: Stats::default(),
            den: vec![[0; 3]; n],
            pre: Vec::with_capacity(n),
            addend: vec![INF; n],
            mult: vec![1; n],
        };
        for i in 0..n {
            w.set_lane::<F>(ctx, arm, i, starts[i], start_a.get(i).copied().unwrap_or(0), 1);
        }
        w
    }

    fn set_lane<F: Field>(&mut self, ctx: &Ctx<F>, arm: u8, i: usize, p: Pt, a: u64, b: u64) {
        let z = &ctx.zr;
        let l = &mut self.lanes[i];
        if is_bailey(arm) || arm == CANON_NULL {
            l.p = p;
            l.key = ctx.c.to_nb(&p.x);
            l.hw = popcnt(&l.key);
            l.a = a;
            l.b = b;
        } else {
            let (q, cx, k, neg) = if arm == CANON_NONEG { canon_arm::<F, CANON_NONEG>(&ctx.c, &p) } else { ctx.c.canon_with::<false>(&p) };
            let m = if neg { z.neg(ctx.lam_pow[k as usize]) } else { ctx.lam_pow[k as usize] };
            l.p = q;
            l.key = cx;
            l.hw = xhw::<F>(&cx);
            l.a = z.mul(a, m);
            l.b = z.mul(b, m);
        }
        l.hist = [Hist::default(); 4];
        l.since_dp = 0;
    }

    fn restart<F: Field>(&mut self, ctx: &Ctx<F>, arm: u8, i: usize) {
        self.cursor = ctx.c.add(&self.cursor, &ctx.stride);
        self.cursor_a = ctx.zr.add(self.cursor_a, ctx.stride_a);
        self.st.restarts += 1;
        let (p, a) = (self.cursor, self.cursor_a);
        self.set_lane::<F>(ctx, arm, i, p, a, 1);
    }

    /// `steps` lockstep steps (or until the sink says stop).  `ARM`, the
    /// jump count `R` (adding arms) or multiplier count `M` (Bailey arms,
    /// `j = 3 + ((HW >> 1) & (M - 1))`), and `TRACK` (keep `a, b` with
    /// `P = aG + bQ`) are compile-time.  Returns true when stopped.
    #[inline(always)]
    pub fn run<F: Field, const ARM: u8, const R: usize, const M: u32, const TRACK: bool, S: Sink>(
        &mut self,
        ctx: &Ctx<F>,
        steps: u64,
        sink: &mut S,
    ) -> bool {
        let n = self.lanes.len();
        let c = &ctx.c;
        let z = ctx.zr;
        for _ in 0..steps {
            // Phase 1: distinguished points, selection, denominators.
            for i in 0..n {
                let mut l = self.lanes[i];
                if l.hw <= ctx.dp_hw {
                    self.st.dps += 1;
                    let ctl = if ARM == BAILEY {
                        // canonicalize at the DP only
                        let (cx, k) = F::lift_scan(l.key);
                        let yk = F::rotl(c.to_nb(&l.p.y), k);
                        let neg = F::lt(xor(&yk, &cx), yk);
                        let (ra, rb) = if TRACK {
                            let m = if neg { z.neg(ctx.lam_pow[k as usize]) } else { ctx.lam_pow[k as usize] };
                            (z.mul(l.a, m), z.mul(l.b, m))
                        } else {
                            (0, neg as u64)
                        };
                        sink.dp(i, &cx, ra, rb)
                    } else {
                        sink.dp(i, &l.key, l.a, l.b)
                    };
                    l.since_dp = 0;
                    match ctl {
                        Ctl::Go => {}
                        Ctl::Restart => {
                            self.restart::<F>(ctx, ARM, i);
                            l = self.lanes[i];
                        }
                        Ctl::Stop => return true,
                    }
                } else if l.since_dp > ctx.cap {
                    self.restart::<F>(ctx, ARM, i);
                    l = self.lanes[i];
                }
                let q = if is_bailey(ARM) {
                    let j = 3 + ((l.hw >> 1) & (M - 1));
                    if TRACK {
                        self.mult[i] = ctx.one_plus[j as usize];
                    }
                    let yc = c.to_nb(&l.p.y);
                    Pt::new(c.from_nb(&F::rotl(l.key, j)), c.from_nb(&F::rotl(yc, j)))
                } else {
                    let ji = jump_index(&l.p.x, R);
                    if TRACK {
                        self.mult[i] = ctx.jump_s[ji];
                    }
                    ctx.jumps[ji]
                };
                self.addend[i] = q;
                self.den[i] = xor(&l.p.x, &q.x);
                self.lanes[i] = l;
            }
            // Phase 2: one inversion for all lanes.
            c.batch_inv(&mut self.den, &mut self.pre);
            // Phase 3: the additions and (adding arms) canonicalization.
            for i in 0..n {
                let mut l = self.lanes[i];
                let q = self.addend[i];
                let sum = if is_zero(&self.den[i]) {
                    self.st.zero_den += 1;
                    c.add(&l.p, &q)
                } else {
                    let lam = F::mul(&xor(&l.p.y, &q.y), &self.den[i]);
                    c.add_slope(&l.p, &q, &lam)
                };
                let (mut na, mut nb) = (l.a, l.b);
                if TRACK {
                    if is_bailey(ARM) {
                        na = z.mul(na, self.mult[i]);
                        nb = z.mul(nb, self.mult[i]);
                    } else {
                        na = z.add(na, self.mult[i]);
                    }
                }
                self.st.steps += 1;
                l.since_dp += 1;
                if is_bailey(ARM) || ARM == CANON_NULL {
                    l.p = sum;
                    l.key = c.to_nb(&sum.x);
                    l.hw = popcnt(&l.key);
                    l.a = na;
                    l.b = nb;
                    self.lanes[i] = l;
                    continue;
                }
                let (np, key, k, neg) = canon_arm::<F, ARM>(c, &sum);
                if TRACK {
                    let m = if neg { z.neg(ctx.lam_pow[k as usize]) } else { ctx.lam_pow[k as usize] };
                    na = z.mul(na, m);
                    nb = z.mul(nb, m);
                }
                // Fruitless cycles of length 2 and 4 (and a fixed point).
                let cyc = if np == l.p {
                    1
                } else if np == l.hist[0].p {
                    2
                } else if np == l.hist[2].p {
                    4
                } else {
                    0
                };
                // CANON_NOLIFT (k = 0) would meet negation 2-cycles at 1/(2R) per step
                // instead of 1/(2Rn); it computes the test but does not escape, so the
                // ablation removes lift_scan only (amendment 1).
                if cyc != 0 && ARM != CANON_NOLIFT {
                    // Escape from the least point of the cycle by doubling:
                    // a function of the cycle, so merged walks escape alike.
                    let mut cand = [Hist { p: l.p, a: l.a, b: l.b }; 4];
                    let len = if cyc == 4 { 4 } else { cyc };
                    if cyc >= 2 {
                        cand[1] = l.hist[0];
                    }
                    if cyc == 4 {
                        cand[2] = l.hist[1];
                        cand[3] = l.hist[2];
                    }
                    let mut best = cand[0];
                    for h in &cand[1..len] {
                        if F::lt(h.p.x, best.p.x) || (h.p.x == best.p.x && F::lt(h.p.y, best.p.y)) {
                            best = *h;
                        }
                    }
                    let d = c.double(&best.p);
                    let (ep, ekey, ek, eneg) = canon_arm::<F, ARM>(c, &d);
                    let (mut ea, mut eb) = (best.a, best.b);
                    if TRACK {
                        let m = if eneg { z.neg(ctx.lam_pow[ek as usize]) } else { ctx.lam_pow[ek as usize] };
                        let m2 = z.add(m, m);
                        ea = z.mul(ea, m2);
                        eb = z.mul(eb, m2);
                    }
                    self.st.escapes += 1;
                    l.p = ep;
                    l.key = ekey;
                    l.hw = xhw::<F>(&ekey);
                    l.a = ea;
                    l.b = eb;
                    l.hist = [Hist::default(); 4];
                } else {
                    l.hist = [Hist { p: l.p, a: l.a, b: l.b }, l.hist[0], l.hist[1], l.hist[2]];
                    l.p = np;
                    l.key = key;
                    l.hw = xhw::<F>(&key);
                    l.a = na;
                    l.b = nb;
                }
                self.lanes[i] = l;
            }
        }
        false
    }

    /// Fold of every lane's point: equal for equal trajectories.
    pub fn state_hash(&self) -> u64 {
        let mut h = 0u64;
        for l in &self.lanes {
            for w in l.p.x.iter().chain(l.p.y.iter()) {
                h = (h ^ w).wrapping_mul(0x9E37_79B9_7F4A_7C15).rotate_left(23);
            }
        }
        h
    }
}

/// Hamming weight of the x normal word inside a DP key (the CANON_NONEG key
/// carries a y fingerprint above bit N).
#[inline(always)]
pub fn xhw<F: Field>(key: &W3) -> u32 {
    let m = F::mask();
    (key[0] & m[0]).count_ones() + (key[1] & m[1]).count_ones() + (key[2] & m[2]).count_ones()
}

/// The adding arms' canonicalization step: `(point, DP key, k, negated)`.
#[inline(always)]
pub fn canon_arm<F: Field, const ARM: u8>(c: &Curve<F>, p: &Pt) -> (Pt, W3, u32, bool) {
    match ARM {
        CANON_EXH => c.canon_with::<true>(p),
        CANON_NONEG => {
            let xc = c.to_nb(&p.x);
            let (cx, k) = F::lift_scan(xc);
            let cy = F::rotl(c.to_nb(&p.y), k);
            let mut key = cx;
            let fp = (cy[0] ^ cy[1].rotate_left(17) ^ cy[2].rotate_left(41)).wrapping_mul(0x9E37_79B9_7F4A_7C15);
            key[2] ^= fp & !((1u64 << 8) - 1); // bits >= 136 of the key: above every x word (N <= 131)
            (Pt::new(c.from_nb(&cx), c.from_nb(&cy)), key, k, false)
        }
        CANON_NOLIFT => {
            let xc = c.to_nb(&p.x);
            let yk = c.to_nb(&p.y);
            let yn = xor(&yk, &xc);
            let neg = F::lt(yn, yk);
            let cy = if neg { yn } else { yk };
            (Pt::new(c.from_nb(&xc), c.from_nb(&cy)), xc, 0, neg)
        }
        _ => c.canon_with::<false>(p),
    }
}

// --------------------------------------------- timing entry points (bench) ---

pub type StepFn<F> = fn(&mut Walker, &Ctx<F>, u64, &mut Fold) -> bool;

macro_rules! entries {
    ($f:ty, $( $name:ident = ($arm:expr, $r:expr, $m:expr, $aa:expr) ),* $(,)?) => {
        $(
            /// Stable symbol (cachegrind): one arm's whole step loop, untracked.
            #[no_mangle]
            #[inline(never)]
            pub fn $name(w: &mut Walker, ctx: &Ctx<$f>, steps: u64, s: &mut Fold) -> bool {
                // Names the arm in an empty asm block so LLVM cannot merge the
                // A/A copy into its original (no instruction is emitted).
                #[cfg(target_arch = "x86_64")]
                unsafe {
                    core::arch::asm!("/* arm {0} aa {1} n {2} */", const $arm, const $aa, const <$f as Field>::N,
                                     options(nomem, nostack, preserves_flags));
                }
                w.run::<$f, { $arm }, { $r }, { $m }, false, Fold>(ctx, steps, s)
            }
        )*
    };
}

entries!(F131,
    t131_bailey = (BAILEY, 32, 8, 0),
    t131_bailey_aa = (BAILEY, 32, 8, 1),
    t131_bailey_nodpc = (BAILEY_NODPC, 32, 8, 0),
    t131_canon = (CANON, 32, 8, 0),
    t131_canon_aa = (CANON, 32, 8, 1),
    t131_canon_nolift = (CANON_NOLIFT, 32, 8, 0),
    t131_canon_null = (CANON_NULL, 32, 8, 0),
    t131_canon_exh = (CANON_EXH, 32, 8, 0),
);

entries!(F83,
    t83_bailey = (BAILEY, 32, 8, 0),
    t83_bailey_aa = (BAILEY, 32, 8, 1),
    t83_bailey_nodpc = (BAILEY_NODPC, 32, 8, 0),
    t83_canon = (CANON, 32, 8, 0),
    t83_canon_aa = (CANON, 32, 8, 1),
    t83_canon_nolift = (CANON_NOLIFT, 32, 8, 0),
    t83_canon_null = (CANON_NULL, 32, 8, 0),
    t83_canon_exh = (CANON_EXH, 32, 8, 0),
);

pub const TIMING_ARMS: [&str; 8] =
    ["bailey", "bailey_aa", "bailey_nodpc", "canon", "canon_aa", "canon_nolift", "canon_null", "canon_exh"];

pub fn arm_code(name: &str) -> u8 {
    match name {
        "bailey" | "bailey_aa" => BAILEY,
        "bailey_nodpc" => BAILEY_NODPC,
        "canon" | "canon_aa" | "canon32" | "canon8" => CANON,
        "canon_nolift" => CANON_NOLIFT,
        "canon_null" => CANON_NULL,
        "canon_exh" => CANON_EXH,
        "canon32_noneg" => CANON_NONEG,
        _ => panic!("unknown arm {name}"),
    }
}

pub fn step131(name: &str) -> StepFn<F131> {
    match name {
        "bailey" => t131_bailey,
        "bailey_aa" => t131_bailey_aa,
        "bailey_nodpc" => t131_bailey_nodpc,
        "canon" => t131_canon,
        "canon_aa" => t131_canon_aa,
        "canon_nolift" => t131_canon_nolift,
        "canon_null" => t131_canon_null,
        "canon_exh" => t131_canon_exh,
        _ => panic!("unknown arm {name}"),
    }
}

pub fn step83(name: &str) -> StepFn<F83> {
    match name {
        "bailey" => t83_bailey,
        "bailey_aa" => t83_bailey_aa,
        "bailey_nodpc" => t83_bailey_nodpc,
        "canon" => t83_canon,
        "canon_aa" => t83_canon_aa,
        "canon_nolift" => t83_canon_nolift,
        "canon_null" => t83_canon_null,
        "canon_exh" => t83_canon_exh,
        _ => panic!("unknown arm {name}"),
    }
}

// ------------------------------------------------------------ n = 83 solve ---

pub mod n83 {
    use super::*;

    /// crypto `KoblitzCurve::new(1, 83)` legacy fixture (asserted in tests and
    /// by `indep.py`).
    pub const R: u64 = 8569786107849059;
    pub const LAMBDA: u64 = 2998004823950457;
    pub const COFACTOR: u64 = 1128547018;
    pub const GX: u128 = 6614244651398184860292015;
    pub const GY: u128 = 8868260410029249391539529;
    /// Size of the signed-Frobenius group on the subgroup (asserted: lambda
    /// has exact order 83, and -1 is not a power of lambda).
    pub const A: u64 = 166;

    pub fn pt(x: u128, y: u128) -> Pt {
        Pt::new(from128(x), from128(y))
    }

    pub fn gen() -> Pt {
        pt(GX, GY)
    }

    pub fn floor() -> f64 {
        (std::f64::consts::PI * R as f64 / (2.0 * A as f64)).sqrt()
    }

    pub fn to_u128(w: &W3) -> u128 {
        to128(w)
    }

    /// DP table keyed by the canonical x normal word.
    pub struct Solve<'a> {
        pub c: &'a Curve<F83>,
        pub g: Pt,
        pub q: Pt,
        pub zr: Zr,
        pub table: HashMap<W3, (u64, u64, usize)>,
        pub answer: Option<u64>,
        pub failed: u64,
        pub wasted: u64,
        pub self_hits: u64,
    }

    impl Sink for Solve<'_> {
        fn dp(&mut self, lane: usize, key: &W3, a: u64, b: u64) -> Ctl {
            let Some(&(a2, b2, lane2)) = self.table.get(key) else {
                self.table.insert(*key, (a, b, lane));
                return Ctl::Go;
            };
            if a == a2 && b == b2 {
                return Ctl::Go; // the same point with the same log: no news
            }
            // a + b d = a2 + b2 d
            let Some(inv) = self.zr.inv(self.zr.sub(b2, b)) else {
                self.wasted += 1;
                return if lane2 == lane { Ctl::Restart } else { Ctl::Go };
            };
            let d = self.zr.mul(self.zr.sub(a, a2), inv);
            if self.c.smul(&self.g, &[d, 0, 0]) == self.q {
                self.answer = Some(d);
                return Ctl::Stop;
            }
            self.failed += 1;
            if lane2 == lane {
                self.self_hits += 1;
                Ctl::Restart
            } else {
                Ctl::Go
            }
        }
    }

    #[derive(Debug, Clone)]
    pub struct Outcome {
        pub d: Option<u64>,
        pub st: Stats,
        pub failed: u64,
        pub wasted: u64,
        pub self_hits: u64,
        pub table: usize,
    }

    /// Solve `Q = [d]G` with one walk design.  `arm` in
    /// {bailey (M=8), canon32 (R=32), canon8 (R=8), canon32_noneg (R=32,
    /// Frobenius-only classes)}.
    pub fn solve(c: &Curve<F83>, arm: &str, q: Pt, seed: u64, lanes: usize, dp_hw: u32, step_cap: u64) -> Outcome {
        let g = gen();
        let zr = Zr { r: R };
        let mut rng = Rng(seed);
        let rnd = |rng: &mut Rng| 1 + rng.next() % (R - 1);
        let rcount = if arm == "canon8" { 8 } else { 32 };
        let jump_s: Vec<u64> = (0..rcount).map(|_| rnd(&mut rng)).collect();
        let jumps: Vec<Pt> = jump_s.iter().map(|&s| c.smul(&g, &[s, 0, 0])).collect();
        let stride_a = rnd(&mut rng);
        let stride = c.smul(&g, &[stride_a, 0, 0]);
        let mut cursor_a = rnd(&mut rng);
        let mut cursor = c.add(&c.smul(&g, &[cursor_a, 0, 0]), &q);
        let mut starts = vec![];
        let mut start_a = vec![];
        for _ in 0..lanes {
            starts.push(cursor);
            start_a.push(cursor_a);
            cursor = c.add(&cursor, &stride);
            cursor_a = zr.add(cursor_a, stride_a);
        }
        let curve = Curve::<F83>::new(1);
        let ctx = Ctx::new(curve, dp_hw, jumps, jump_s, R, LAMBDA, stride, stride_a, 64 << 6);
        let code = arm_code(arm);
        let mut w = Walker::new(&ctx, code, &starts, &start_a, cursor, cursor_a);
        let mut s = Solve { c, g, q, zr, table: HashMap::new(), answer: None, failed: 0, wasted: 0, self_hits: 0 };
        let chunk = 1024u64;
        while w.st.steps < step_cap {
            let stop = match arm {
                "bailey" => w.run::<F83, BAILEY, 32, 8, true, _>(&ctx, chunk, &mut s),
                "canon32_noneg" => w.run::<F83, CANON_NONEG, 32, 8, true, _>(&ctx, chunk, &mut s),
                "canon32" => w.run::<F83, CANON, 32, 8, true, _>(&ctx, chunk, &mut s),
                "canon8" => w.run::<F83, CANON, 8, 8, true, _>(&ctx, chunk, &mut s),
                _ => panic!("unknown solve arm {arm}"),
            };
            if stop {
                break;
            }
        }
        Outcome { d: s.answer, st: w.st, failed: s.failed, wasted: s.wasted, self_hits: s.self_hits, table: s.table.len() }
    }
}

// ------------------------------------------------------------ JSON helpers ---

/// Points from a flat JSON array of `["x_hex", "y_hex"]` pairs under `key`
/// (as written by `make_inputs.py`).
pub fn hex_points(text: &str, key: &str) -> Vec<Pt> {
    let i = text.find(&format!("\"{key}\"")).unwrap_or_else(|| panic!("no key {key}"));
    let rest = &text[i..];
    let open = rest.find('[').unwrap();
    // matching bracket
    let mut depth = 0;
    let mut end = open;
    for (j, ch) in rest[open..].char_indices() {
        match ch {
            '[' => depth += 1,
            ']' => {
                depth -= 1;
                if depth == 0 {
                    end = open + j;
                    break;
                }
            }
            _ => {}
        }
    }
    let body = &rest[open + 1..end];
    let words: Vec<W3> = body
        .split('"')
        .filter(|s| s.starts_with("0x"))
        .map(|s| parse_hex(s))
        .collect();
    words.chunks(2).map(|c| Pt::new(c[0], c[1])).collect()
}

pub fn parse_hex(s: &str) -> W3 {
    let v = s.trim_start_matches("0x");
    let mut w = [0u64; 3];
    let digits: Vec<u8> = v.bytes().rev().collect();
    for (i, d) in digits.iter().enumerate() {
        let x = (*d as char).to_digit(16).unwrap() as u64;
        w[i / 16] |= x << (4 * (i % 16));
    }
    w
}

pub fn hex(w: &W3) -> String {
    format!("0x{:016x}{:016x}{:016x}", w[2], w[1], w[0])
}
