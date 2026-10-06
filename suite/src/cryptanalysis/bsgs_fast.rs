//! Single-word baby-step / giant-step for the ECDLP: the fast path behind
//! [`crate::cryptanalysis::ecdlp_variants::bsgs`].
//!
//! That module is the readable one.  It states every row of the
//! Galbraith–Wang–Zhang table in the crate's general arithmetic --
//! [`BigUint`] coordinates, a `HashMap` keyed by the big-endian bytes of a
//! coordinate -- and pays for it: a field multiplication allocates, a
//! table probe allocates and hashes a heap `Vec`, and a `√n` search that
//! should be a few million adds becomes a few million allocations.
//!
//! This module is the same algorithm with the representation the hot loop
//! wants, and it is a port of the structure worked out for the GPU in
//! `gpu/ecc/bsgs.cuh`, which is where the design notes live:
//!
//! - **Single-word Montgomery arithmetic.**  A field element is one `u64`
//!   in Montgomery form, for any odd prime below `2^63`.  A multiply is
//!   one `u64 × u64 → u128` and a REDC; nothing allocates, ever.
//! - **Parallel chains.**  Both phases are sets of independent *chains*,
//!   each adding one constant point per step -- `G` for the baby chains,
//!   `−S` for the giant chains.  A chain owns a contiguous index range,
//!   is seeded once by a scalar multiplication, and from then on every
//!   step is one affine addition.  Chains are disjoint, so they go out to
//!   [`rayon`] with no shared mutable state but the table.
//! - **Batched inversion.**  A worker advances `W` chains together and
//!   shares one field inversion across them by Montgomery's trick, so a
//!   step costs about `6 + inv/W` multiplications instead of one
//!   inversion.
//! - **A flat x-keyed table.**  Open addressing with linear probing over
//!   8-byte slots holding a 32-bit tag and a 32-bit index, inserted with
//!   `compare_exchange` so the baby phase is lock-free.  Keying on the
//!   x-coordinate alone folds `jG` and `−jG` into one entry, which is
//!   what lets the giant stride be `2m − 1` and the whole search cost
//!   `~1.0 √width` instead of `~1.41 √width`.
//!
//! Every hit is a *candidate*: the table stores a 32-bit tag, not the
//! point, so a match is only probably right.  `BsgsFast::verify` settles
//! it with one scalar multiplication, so a false positive costs time and
//! never correctness -- the answer this module returns has always been
//! checked as `kG == Q`.
//!
//! The formulas are exactly those of [`crate::ecc::point::Point`], and
//! [`FastCurve::lift`] / [`FastCurve::lower`] convert, so the two
//! representations are interchangeable; the tests below check the field,
//! the group law and whole solves against that reference.
//!
//! # Scope
//!
//! `O(√width)`, so exponential in the bit length: this is for the sizes a
//! machine actually finishes, and for the interval problems where `width`
//! is small even when the group is not (a known-range key, or one
//! Pohlig–Hellman sub-problem).  The table costs 16 bytes per entry, so
//! `√width` entries is `16 √width` bytes and memory, not time, is what
//! bounds the method: a 64 GB host reaches `width ≈ 2^62`.

use std::sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering};

use num_bigint::BigUint;
use rayon::prelude::*;

use crate::ecc::curve::CurveParams;
use crate::ecc::field::FieldElement;
use crate::ecc::point::Point;

// ── field ───────────────────────────────────────────────────────────────

/// Montgomery arithmetic mod an odd prime `p < 2^63`, one `u64` per
/// element.
///
/// The bound is what keeps a REDC in one word: with `p < 2^63` the
/// reduced value before the conditional subtraction is below `2p < 2^64`,
/// so a single `u128` product and one compare finish the multiply.
#[derive(Clone, Copy, Debug)]
pub struct FastField {
    p: u64,
    /// `-p^{-1} mod 2^64`
    n0inv: u64,
    /// `2^64 mod p`, the Montgomery form of 1
    r: u64,
    /// `2^128 mod p`, for converting into Montgomery form
    r2: u64,
}

impl FastField {
    /// Build the arithmetic for an odd prime `p` below `2^63`.
    pub fn new(p: u64) -> Option<Self> {
        if p < 3 || p.is_multiple_of(2) || p >= 1u64 << 63 {
            return None;
        }
        // -p^{-1} mod 2^64 by Newton iteration: x_{k+1} = x_k (2 - p x_k)
        // doubles the number of correct bits from the 3 that x = p gives.
        let mut inv = 1u64;
        for _ in 0..6 {
            inv = inv.wrapping_mul(2u64.wrapping_sub(p.wrapping_mul(inv)));
        }
        let n0inv = inv.wrapping_neg();
        debug_assert_eq!(p.wrapping_mul(n0inv), 1u64.wrapping_neg());
        let r = ((1u128 << 64) % p as u128) as u64;
        let r2 = ((r as u128 * r as u128) % p as u128) as u64;
        Some(Self { p, n0inv, r, r2 })
    }

    /// The prime.
    pub fn modulus(&self) -> u64 {
        self.p
    }
    /// Montgomery form of `0`.
    pub fn zero(&self) -> u64 {
        0
    }
    /// Montgomery form of `1`.
    pub fn one(&self) -> u64 {
        self.r
    }

    /// `a * b * 2^-64 mod p`.
    #[inline(always)]
    pub fn mul(&self, a: u64, b: u64) -> u64 {
        let t = a as u128 * b as u128;
        let m = (t as u64).wrapping_mul(self.n0inv);
        let t = (t + m as u128 * self.p as u128) >> 64;
        let t = t as u64;
        if t >= self.p {
            t - self.p
        } else {
            t
        }
    }

    /// `a²` in Montgomery form.
    #[inline(always)]
    pub fn sqr(&self, a: u64) -> u64 {
        self.mul(a, a)
    }

    #[inline(always)]
    pub fn add(&self, a: u64, b: u64) -> u64 {
        let s = a.wrapping_add(b);
        if s >= self.p || s < a {
            s.wrapping_sub(self.p)
        } else {
            s
        }
    }

    #[inline(always)]
    pub fn sub(&self, a: u64, b: u64) -> u64 {
        if a >= b {
            a - b
        } else {
            a.wrapping_sub(b).wrapping_add(self.p)
        }
    }

    #[inline(always)]
    pub fn neg(&self, a: u64) -> u64 {
        if a == 0 {
            0
        } else {
            self.p - a
        }
    }

    #[inline(always)]
    pub fn dbl(&self, a: u64) -> u64 {
        self.add(a, a)
    }

    /// Canonical integer → Montgomery form.
    pub fn to_mont(&self, x: u64) -> u64 {
        self.mul(x % self.p, self.r2)
    }

    /// Montgomery form → canonical integer.
    pub fn from_mont(&self, x: u64) -> u64 {
        self.mul(x, 1)
    }

    /// `a^e` by square-and-multiply, both operands in Montgomery form.
    pub fn pow(&self, a: u64, e: u64) -> u64 {
        let mut acc = self.one();
        let mut base = a;
        let mut e = e;
        while e > 0 {
            if e & 1 == 1 {
                acc = self.mul(acc, base);
            }
            base = self.sqr(base);
            e >>= 1;
        }
        acc
    }

    /// `a^{-1}` by Fermat, `inv(0) = 0`.
    ///
    /// One inversion is a few hundred multiplications, which is exactly
    /// why the chains batch: [`Self::batch_inv`] pays it once for `W` of
    /// them.
    pub fn inv(&self, a: u64) -> u64 {
        if a == 0 {
            0
        } else {
            self.pow(a, self.p - 2)
        }
    }

    /// Montgomery's simultaneous inversion: invert every element of `xs`
    /// in place with one inversion and `3(k-1)` multiplications.
    /// `scratch` must be at least `xs.len()` long.  No element may be zero
    /// -- callers substitute `1` for the steps that need no inverse.
    pub fn batch_inv(&self, xs: &mut [u64], scratch: &mut [u64]) {
        let k = xs.len();
        if k == 0 {
            return;
        }
        scratch[0] = xs[0];
        for i in 1..k {
            scratch[i] = self.mul(scratch[i - 1], xs[i]);
        }
        let mut acc = self.inv(scratch[k - 1]);
        for i in (1..k).rev() {
            let xi = self.mul(acc, scratch[i - 1]);
            acc = self.mul(acc, xs[i]);
            xs[i] = xi;
        }
        xs[0] = acc;
    }
}

// ── points ──────────────────────────────────────────────────────────────

/// An affine point with single-word Montgomery coordinates, or `O`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FastPoint {
    pub x: u64,
    pub y: u64,
    pub infinity: bool,
}

impl FastPoint {
    /// The point at infinity.
    pub const INFINITY: Self = Self {
        x: 0,
        y: 0,
        infinity: true,
    };
}

/// How a step must be finished once its denominator has been inverted.
///
/// Splitting the step in two is what lets a whole block of chains share
/// one inversion: the classification happens first for all of them, the
/// steps that need no inverse contribute `1` to the batch, and the batch
/// is then always invertible.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum StepMode {
    /// Generic affine addition.
    Add,
    /// `P == A`, so the step is a doubling.
    Double,
    /// `P == -A`, so the sum is `O`.
    ToInfinity,
    /// `P == O`, so the sum is `A`.
    FromInfinity,
}

/// `y² = x³ + ax + b` over `F_p` with single-word coordinates.
#[derive(Clone, Copy, Debug)]
pub struct FastCurve {
    pub f: FastField,
    /// `a` in Montgomery form.
    a: u64,
    /// `b` in Montgomery form.
    b: u64,
    /// Order of the generator's subgroup.
    pub n: u64,
    /// The generator.
    pub g: FastPoint,
}

impl FastCurve {
    /// Adopt a [`CurveParams`] whose prime, order and coordinates all fit
    /// a single word.  Returns `None` when they do not -- callers stay on
    /// the general arithmetic then.
    pub fn from_params(c: &CurveParams) -> Option<Self> {
        let p = biguint_to_u64(&c.p)?;
        let n = biguint_to_u64(&c.n)?;
        let f = FastField::new(p)?;
        let a = f.to_mont(biguint_to_u64(&c.a)?);
        let b = f.to_mont(biguint_to_u64(&c.b)?);
        let g = FastPoint {
            x: f.to_mont(biguint_to_u64(&c.gx)?),
            y: f.to_mont(biguint_to_u64(&c.gy)?),
            infinity: false,
        };
        let curve = Self { f, a, b, n, g };
        curve.on_curve(g).then_some(curve)
    }

    /// Is `p` on the curve?  `O` always is.
    pub fn on_curve(&self, p: FastPoint) -> bool {
        if p.infinity {
            return true;
        }
        let lhs = self.f.sqr(p.y);
        let x2 = self.f.sqr(p.x);
        let mut rhs = self.f.mul(x2, p.x);
        rhs = self.f.add(rhs, self.f.mul(self.a, p.x));
        rhs = self.f.add(rhs, self.b);
        lhs == rhs
    }

    /// A general [`Point`] in this representation.
    pub fn lift(&self, p: &Point) -> FastPoint {
        match p {
            Point::Infinity => FastPoint::INFINITY,
            Point::Affine { x, y } => FastPoint {
                x: self
                    .f
                    .to_mont(biguint_to_u64(&x.value).expect("coordinate fits a word")),
                y: self
                    .f
                    .to_mont(biguint_to_u64(&y.value).expect("coordinate fits a word")),
                infinity: false,
            },
        }
    }

    /// Back to a general [`Point`].
    pub fn lower(&self, p: FastPoint) -> Point {
        if p.infinity {
            return Point::Infinity;
        }
        let m = BigUint::from(self.f.modulus());
        Point::Affine {
            x: FieldElement::new(BigUint::from(self.f.from_mont(p.x)), m.clone()),
            y: FieldElement::new(BigUint::from(self.f.from_mont(p.y)), m),
        }
    }

    /// `-P`.
    #[inline]
    pub fn neg(&self, p: FastPoint) -> FastPoint {
        if p.infinity {
            p
        } else {
            FastPoint {
                x: p.x,
                y: self.f.neg(p.y),
                infinity: false,
            }
        }
    }

    /// Classify `P + A` and produce the denominator to invert.  The modes
    /// that need no inverse report `1`, so a batch is always invertible.
    #[inline]
    fn step_mode(&self, p: FastPoint, a: FastPoint) -> (StepMode, u64) {
        if p.infinity {
            return (StepMode::FromInfinity, self.f.one());
        }
        if a.infinity {
            // Adding O leaves P; treat it as a no-op doubling-free step.
            return (StepMode::FromInfinity, self.f.one());
        }
        let d = self.f.sub(a.x, p.x);
        if d != 0 {
            return (StepMode::Add, d);
        }
        if p.y == a.y {
            let den = self.f.dbl(p.y);
            if den != 0 {
                return (StepMode::Double, den);
            }
        }
        (StepMode::ToInfinity, self.f.one())
    }

    /// Finish a classified step given `inv = 1/den`.
    #[inline]
    fn step_finish(&self, p: FastPoint, a: FastPoint, mode: StepMode, inv: u64) -> FastPoint {
        match mode {
            StepMode::FromInfinity => {
                if p.infinity {
                    a
                } else {
                    p
                }
            }
            StepMode::ToInfinity => FastPoint::INFINITY,
            StepMode::Add => {
                let num = self.f.sub(a.y, p.y);
                self.slope_step(p, a, num, inv)
            }
            StepMode::Double => {
                let x2 = self.f.sqr(p.x);
                let num = self.f.add(self.f.add(self.f.dbl(x2), x2), self.a);
                self.slope_step(p, a, num, inv)
            }
        }
    }

    /// The shared tail of both affine formulas: `λ = num · inv`, then
    /// `x₃ = λ² − x₁ − x₂`, `y₃ = λ(x₁ − x₃) − y₁`.
    #[inline]
    fn slope_step(&self, p: FastPoint, a: FastPoint, num: u64, inv: u64) -> FastPoint {
        let lam = self.f.mul(num, inv);
        let x3 = self.f.sub(self.f.sub(self.f.sqr(lam), p.x), a.x);
        let y3 = self.f.sub(self.f.mul(lam, self.f.sub(p.x, x3)), p.y);
        FastPoint {
            x: x3,
            y: y3,
            infinity: false,
        }
    }

    /// `P + Q`, paying its own inversion.  The chains do not use this --
    /// they batch -- but seeding and verification do.
    pub fn add(&self, p: FastPoint, q: FastPoint) -> FastPoint {
        if p.infinity {
            return q;
        }
        if q.infinity {
            return p;
        }
        let (mode, den) = self.step_mode(p, q);
        self.step_finish(p, q, mode, self.f.inv(den))
    }

    /// `2P`.
    pub fn double(&self, p: FastPoint) -> FastPoint {
        self.add(p, p)
    }

    /// `kP` by double-and-add from the top set bit.
    pub fn scalar_mul(&self, p: FastPoint, k: u64) -> FastPoint {
        if k == 0 || p.infinity {
            return FastPoint::INFINITY;
        }
        let mut acc = FastPoint::INFINITY;
        let top = 63 - k.leading_zeros();
        for i in (0..=top).rev() {
            acc = self.double(acc);
            if (k >> i) & 1 == 1 {
                acc = self.add(acc, p);
            }
        }
        acc
    }
}

/// A `BigUint` as a `u64`, or `None` if it is wider.
fn biguint_to_u64(v: &BigUint) -> Option<u64> {
    let d = v.iter_u64_digits().collect::<Vec<_>>();
    match d.len() {
        0 => Some(0),
        1 => Some(d[0]),
        _ => None,
    }
}

// ── table ───────────────────────────────────────────────────────────────

/// Empty-slot marker.  An entry's low word is an index below `2^32 - 1`,
/// so a real entry can never collide with it.
const EMPTY: u64 = u64::MAX;

/// 64-bit hash of an x-coordinate (Montgomery form), splitmix64's
/// finaliser.  The low bits choose the slot and the high 32 are the tag.
#[inline]
fn hash_x(x: u64) -> u64 {
    let mut h = x ^ 0x243F_6A88_85A3_08D3;
    h ^= h >> 30;
    h = h.wrapping_mul(0xBF58_476D_1CE4_E5B9);
    h ^= h >> 27;
    h = h.wrapping_mul(0x94D0_49BB_1331_11EB);
    h ^= h >> 31;
    h
}

#[inline]
fn tag_of(h: u64) -> u32 {
    (h >> 32) as u32
}

/// The baby table: open addressing, linear probing, lock-free insertion.
///
/// A slot is `(tag << 32) | j`.  The slot position carries the low hash
/// bits and the tag the high 32, so an entry is pinned by `32 + bits` bits
/// and a probe is a false candidate with probability about
/// `load / 2^32` -- verified away by the caller, never a wrong answer.
pub struct BabyTable {
    bits: u32,
    slots: Vec<AtomicU64>,
}

impl BabyTable {
    /// A table of `2^bits` slots.  Keep the load at or below one half:
    /// a probe then touches about 2.5 slots.
    pub fn new(bits: u32) -> Self {
        let n = 1usize << bits;
        let mut slots = Vec::with_capacity(n);
        slots.resize_with(n, || AtomicU64::new(EMPTY));
        Self { bits, slots }
    }

    #[inline]
    fn mask(&self) -> u64 {
        (1u64 << self.bits) - 1
    }

    /// Insert `j` under the hash of `x`.  `false` means the table was
    /// full, which the planner sizes against.
    pub fn insert(&self, x: u64, j: u32) -> bool {
        let h = hash_x(x);
        let entry = ((tag_of(h) as u64) << 32) | j as u64;
        let mask = self.mask();
        let start = h & mask;
        for probe in 0..=mask {
            let slot = &self.slots[((start + probe) & mask) as usize];
            if slot
                .compare_exchange(EMPTY, entry, Ordering::Relaxed, Ordering::Relaxed)
                .is_ok()
            {
                return true;
            }
        }
        false
    }

    /// Every index whose tag matches the hash of `x`, passed to `f`.
    /// Probing stops at the first empty slot, so nothing stored is missed.
    #[inline]
    pub fn for_each_match<F: FnMut(u32)>(&self, x: u64, mut f: F) {
        let h = hash_x(x);
        let tag = tag_of(h);
        let mask = self.mask();
        let start = h & mask;
        for probe in 0..=mask {
            let e = self.slots[((start + probe) & mask) as usize].load(Ordering::Relaxed);
            if e == EMPTY {
                return;
            }
            if (e >> 32) as u32 == tag {
                f(e as u32);
            }
        }
    }

    /// Slots in use.
    pub fn len(&self) -> usize {
        self.slots
            .iter()
            .filter(|s| s.load(Ordering::Relaxed) != EMPTY)
            .count()
    }

    /// Is the table empty?
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

// ── the plan ────────────────────────────────────────────────────────────

/// How a solve is laid out: how many baby steps, what the giant stride
/// is, how big the table is, and how the index ranges are split into
/// chains.
#[derive(Clone, Debug)]
pub struct BsgsFastPlan {
    /// Fold `±P` into one table entry and stride `2m − 1`.  With it a
    /// solve costs about `1.00 √width`; without it, `1.41 √width`.
    pub neg_map: bool,
    /// Search `x ∈ [x0, x0 + width)`.
    pub width: u64,
    /// Interval start.
    pub x0: u64,
    /// Baby indices `1 ≤ j < m` are stored (`j = 0` is `O`).
    pub m: u64,
    /// Giant stride.
    pub stride: u64,
    /// Giant indices searched.
    pub giant_count: u64,
    /// Table is `2^table_bits` slots.
    pub table_bits: u32,
    /// Workers.
    pub workers: usize,
    /// Chains per worker, sharing one inversion per step.
    pub chains_per_worker: usize,
    /// Baby chain length.
    pub baby_len: u64,
    /// Giant chain length.
    pub giant_len: u64,
}

impl BsgsFastPlan {
    /// Balance the phases for a uniform target, given that the giant
    /// phase stops at the first hit and so does half its stride count:
    ///
    /// - `neg_map`: `m + width/(2M)` with `M = 2m − 1`, minimal at
    ///   `m = √width / 2`, giving `≈ 1.00 √width`;
    /// - plain: `m + width/(2m)`, minimal at `m = √(width/2)`, giving
    ///   `≈ 1.41 √width`.
    pub fn new(
        width: u64,
        x0: u64,
        neg_map: bool,
        workers: usize,
        chains_per_worker: usize,
    ) -> Self {
        let workers = workers.max(1);
        let chains_per_worker = chains_per_worker.max(1);
        let isqrt = |v: u64| {
            let mut s = (v as f64).sqrt() as u64;
            while s > 0 && s.saturating_mul(s) > v {
                s -= 1;
            }
            while (s + 1).saturating_mul(s + 1) <= v {
                s += 1;
            }
            s
        };
        let ceil_div = |a: u64, b: u64| a.div_ceil(b);
        let m = if neg_map {
            ceil_div(isqrt(width), 2).max(1)
        } else {
            isqrt(ceil_div(width, 2)).max(1)
        }
        // j has to fit the table's 32-bit index field.
        .min(0xFFFF_FFF0);
        let stride = if neg_map { 2 * m - 1 } else { m };
        let giant_count = if width == 0 {
            2
        } else {
            (width - 1) / stride + 2
        };
        let mut table_bits = 4u32;
        while (1u64 << table_bits) < 2 * m {
            table_bits += 1;
        }
        let chains = (workers * chains_per_worker) as u64;
        Self {
            neg_map,
            width,
            x0,
            m,
            stride,
            giant_count,
            table_bits,
            workers,
            chains_per_worker,
            baby_len: ceil_div(m, chains).max(1),
            giant_len: ceil_div(giant_count, chains).max(1),
        }
    }

    /// Bytes the table occupies.
    pub fn table_bytes(&self) -> u64 {
        8u64 << self.table_bits
    }
}

/// What a solve cost, in the same units as the GPU engine's accounting.
#[derive(Clone, Copy, Debug, Default)]
pub struct BsgsFastStats {
    /// Chain-steps taken building the table.
    pub baby_steps: u64,
    /// Chain-steps taken searching, summed over every target.
    pub giant_steps: u64,
    /// Table hits handed to verification.
    pub candidates: u64,
    /// Hits that verification rejected.
    pub false_candidates: u64,
    /// Entries stored.
    pub table_entries: u64,
}

// ── the solver ──────────────────────────────────────────────────────────

/// One chain of a phase: a point, the index it stands for, and where it
/// stops.
#[derive(Clone, Copy)]
struct Chain {
    p: FastPoint,
    pos: u64,
    end: u64,
}

/// A built baby table and everything needed to search it.
pub struct BsgsFast {
    curve: FastCurve,
    plan: BsgsFastPlan,
    table: BabyTable,
    /// `stride · G`.
    s: FastPoint,
    stats: BsgsFastStats,
}

impl BsgsFast {
    /// Build the baby table for `[x0, x0 + width)`.
    ///
    /// The table is a function of the curve and the plan alone, so it is
    /// built once and then serves every target in that interval --
    /// [`Self::solve`] may be called as often as wanted, and each call
    /// after the first costs only its giant phase.
    pub fn build(curve: FastCurve, plan: BsgsFastPlan) -> Self {
        let table = BabyTable::new(plan.table_bits);
        let w = plan.chains_per_worker;

        // Chain c walks j = c·baby_len upward by G; it starts at that
        // multiple of G, which is one scalar multiplication.
        let steps: u64 = (0..plan.workers)
            .into_par_iter()
            .map(|t| {
                let mut cs: Vec<Chain> = (0..w)
                    .map(|k| {
                        let c = (t * w + k) as u64;
                        let start = c * plan.baby_len;
                        let end = ((c + 1) * plan.baby_len).min(plan.m);
                        Chain {
                            p: curve.scalar_mul(curve.g, start),
                            pos: start,
                            end,
                        }
                    })
                    .collect();
                run_chains(&curve, &mut cs, curve.g, |p, pos| {
                    // j = 0 is O and has no x; the giant phase reports a
                    // giant point landing on O as the j = 0 hit instead.
                    if !p.infinity && pos > 0 {
                        table.insert(p.x, pos as u32);
                    }
                    true
                })
            })
            .sum();

        let s = curve.scalar_mul(curve.g, plan.stride);
        let entries = table.len() as u64;
        Self {
            curve,
            plan,
            table,
            s,
            stats: BsgsFastStats {
                baby_steps: steps,
                table_entries: entries,
                ..Default::default()
            },
        }
    }

    /// The plan this table was built for.
    pub fn plan(&self) -> &BsgsFastPlan {
        &self.plan
    }
    /// Costs so far, table build and every solve since.
    pub fn stats(&self) -> BsgsFastStats {
        self.stats
    }
    /// Entries stored.
    pub fn table_entries(&self) -> u64 {
        self.stats.table_entries
    }

    /// `x = x0 + i·stride ± j (mod n)`.
    fn candidate_scalar(&self, i: u64, j: u32, plus: bool) -> u64 {
        let n = self.curve.n as u128;
        let base = (self.plan.x0 as u128 + i as u128 * self.plan.stride as u128) % n;
        let j = j as u128 % n;
        let v = if plus {
            (base + j) % n
        } else {
            (base + n - j) % n
        };
        v as u64
    }

    /// Check a candidate both ways round, returning the `k` with
    /// `kG = Q` if either is it.
    fn verify(&self, q: FastPoint, i: u64, j: u32) -> Option<u64> {
        for plus in [true, false] {
            if j == 0 && !plus {
                break; // ±0 is one candidate
            }
            let k = self.candidate_scalar(i, j, plus);
            if self.curve.scalar_mul(self.curve.g, k) == q {
                return Some(k);
            }
        }
        None
    }

    /// Solve `Q = xG` for `x` in this table's interval.
    ///
    /// Returns the verified `x`, or `None` when the target's logarithm is
    /// not in `[x0, x0 + width)`.
    pub fn solve(&mut self, q: &FastPoint) -> Option<u64> {
        let plan = &self.plan;
        let curve = &self.curve;
        // Q' = Q - x0·G, so the giant walk searches from the interval's
        // start rather than from zero.
        let qprime = curve.add(*q, curve.neg(curve.scalar_mul(curve.g, plan.x0 % curve.n)));
        let neg_s = curve.neg(self.s);
        let w = plan.chains_per_worker;

        let found = AtomicU64::new(u64::MAX);
        let stop = AtomicBool::new(false);
        let cands = AtomicUsize::new(0);
        let falses = AtomicUsize::new(0);

        let steps: u64 = (0..plan.workers)
            .into_par_iter()
            .map(|t| {
                let mut cs: Vec<Chain> = (0..w)
                    .map(|k| {
                        let c = (t * w + k) as u64;
                        let start = c * plan.giant_len;
                        let end = ((c + 1) * plan.giant_len).min(plan.giant_count);
                        // Chain c starts at Q' - (c·giant_len)·S.
                        let off = curve.scalar_mul(self.s, start);
                        Chain {
                            p: curve.add(qprime, curve.neg(off)),
                            pos: start,
                            end,
                        }
                    })
                    .collect();
                run_chains(curve, &mut cs, neg_s, |p, i| {
                    if stop.load(Ordering::Relaxed) {
                        return false;
                    }
                    // A giant point at O is the j = 0 hit: Q' = i·S.
                    if p.infinity {
                        cands.fetch_add(1, Ordering::Relaxed);
                        if let Some(k) = self.verify(*q, i, 0) {
                            found.store(k, Ordering::Relaxed);
                            stop.store(true, Ordering::Relaxed);
                            return false;
                        }
                        falses.fetch_add(1, Ordering::Relaxed);
                        return true;
                    }
                    let mut hit = None;
                    self.table.for_each_match(p.x, |j| {
                        if hit.is_none() {
                            cands.fetch_add(1, Ordering::Relaxed);
                            match self.verify(*q, i, j) {
                                Some(k) => hit = Some(k),
                                None => {
                                    falses.fetch_add(1, Ordering::Relaxed);
                                }
                            }
                        }
                    });
                    match hit {
                        Some(k) => {
                            found.store(k, Ordering::Relaxed);
                            stop.store(true, Ordering::Relaxed);
                            false
                        }
                        None => true,
                    }
                })
            })
            .sum();

        self.stats.giant_steps += steps;
        self.stats.candidates += cands.load(Ordering::Relaxed) as u64;
        self.stats.false_candidates += falses.load(Ordering::Relaxed) as u64;
        match found.load(Ordering::Relaxed) {
            u64::MAX => None,
            k => Some(k),
        }
    }

    /// Solve a batch of targets against this one table.
    ///
    /// Only the first target pays for the table, so per-target cost falls
    /// from about `1.0 √width` towards the giant phase's own
    /// `0.5 √width` as the batch grows.
    pub fn solve_many(&mut self, qs: &[FastPoint]) -> Vec<Option<u64>> {
        qs.iter().map(|q| self.solve(q)).collect()
    }
}

/// Advance a worker's chains to their ends, `visit`ing each point before
/// its step and sharing one inversion per sweep.
///
/// `visit` returns `false` to stop the worker -- the giant phase uses that
/// for the early exit once a candidate has verified.  Returns the number
/// of chain-steps taken, which is exact: a worker that stops early is
/// charged only for what it did.
fn run_chains<F>(curve: &FastCurve, cs: &mut [Chain], addend: FastPoint, mut visit: F) -> u64
where
    F: FnMut(&FastPoint, u64) -> bool,
{
    let w = cs.len();
    let mut den = vec![0u64; w];
    let mut scratch = vec![0u64; w];
    let mut mode = vec![StepMode::Add; w];
    let mut steps = 0u64;
    loop {
        let mut live = false;
        for c in cs.iter() {
            if c.pos < c.end {
                live = true;
                break;
            }
        }
        if !live {
            return steps;
        }
        for (k, c) in cs.iter().enumerate() {
            if c.pos < c.end && !visit(&c.p, c.pos) {
                return steps;
            }
            let (m, d) = curve.step_mode(c.p, addend);
            mode[k] = m;
            den[k] = d;
        }
        curve.f.batch_inv(&mut den, &mut scratch);
        for (k, c) in cs.iter_mut().enumerate() {
            if c.pos < c.end {
                steps += 1;
            }
            c.p = curve.step_finish(c.p, addend, mode[k], den[k]);
            c.pos += 1;
        }
    }
}

// ── convenience ─────────────────────────────────────────────────────────

/// Solve `Q = xG` over the whole group of a single-word curve.
///
/// Builds a table sized for `n` and searches it once.  For several
/// targets build a [`BsgsFast`] yourself and call [`BsgsFast::solve`] per
/// target, which pays for the table only once.
pub fn solve_full_group(curve: FastCurve, q: &FastPoint, neg_map: bool) -> Option<u64> {
    let workers = rayon::current_num_threads().max(1);
    let plan = BsgsFastPlan::new(curve.n, 0, neg_map, workers, 8);
    let mut solver = BsgsFast::build(curve, plan);
    solver.solve(q)
}

/// Solve `Q = xG` knowing `x ∈ [x0, x0 + width)`.
pub fn solve_interval(
    curve: FastCurve,
    q: &FastPoint,
    x0: u64,
    width: u64,
    neg_map: bool,
) -> Option<u64> {
    let workers = rayon::current_num_threads().max(1);
    let plan = BsgsFastPlan::new(width, x0, neg_map, workers, 8);
    let mut solver = BsgsFast::build(curve, plan);
    solver.solve(q)
}

/// The 40-bit curve the GPU engine's tests use (`gpu/ecc/ecref.py
/// --curve toy40`): `y² = x³ + ax + b` over a 40-bit prime with prime
/// order, `a ≠ 0` so the general doubling path is exercised.
///
/// Shared so a number measured here and a number measured there are
/// measured on the same instance.
pub fn toy40_params() -> CurveParams {
    CurveParams {
        name: "toy40",
        p: BigUint::from(0x973a902931u64),
        a: BigUint::from(0x80b610a9f8u64),
        b: BigUint::from(0x816c0f345au64),
        gx: BigUint::from(0x7fe1ea24c4u64),
        gy: BigUint::from(0x8dcde39813u64),
        n: BigUint::from(0x973a97e2f1u64),
        h: 1,
    }
}

/// The toy40 curve in this representation.
pub fn toy40() -> FastCurve {
    FastCurve::from_params(&toy40_params()).expect("toy40 fits a single word")
}

/// `a` as a [`FieldElement`] mod `p`, for driving the general arithmetic
/// alongside this one in tests and cross-checks.
pub fn params_a_fe(c: &CurveParams) -> FieldElement {
    FieldElement::new(c.a.clone(), c.p.clone())
}

/// `kG` on the general arithmetic, for cross-checking.
pub fn reference_scalar_mul(c: &CurveParams, k: u64) -> Point {
    let g = Point::Affine {
        x: FieldElement::new(c.gx.clone(), c.p.clone()),
        y: FieldElement::new(c.gy.clone(), c.p.clone()),
    };
    if k == 0 {
        return Point::Infinity;
    }
    g.scalar_mul(&BigUint::from(k), &params_a_fe(c))
}

/// `√v`, rounded down.
fn isqrt_u64(v: u64) -> u64 {
    let mut s = (v as f64).sqrt() as u64;
    while s > 0 && s.saturating_mul(s) > v {
        s -= 1;
    }
    while (s + 1).saturating_mul(s + 1) <= v {
        s += 1;
    }
    s
}

/// `S = operations / √width`, the unit the repository's ECDLP threads
/// report in, so a row here sits in the same table as a row from the GPU
/// engine or from Pollard rho.
pub fn cost_ratio(stats: &BsgsFastStats, width: u64, targets: u64) -> f64 {
    let ops = stats.baby_steps + stats.giant_steps + stats.candidates;
    let sqrt_w = isqrt_u64(width).max(1) as f64;
    ops as f64 / targets.max(1) as f64 / sqrt_w
}

// ── tests ───────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ecdlp_variants::{bsgs as slow, EcGroup};

    /// A deterministic xorshift, so a failure is reproducible.
    struct Rng(u64);
    impl Rng {
        fn next(&mut self) -> u64 {
            let mut x = self.0;
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            self.0 = x;
            x
        }
        fn below(&mut self, n: u64) -> u64 {
            self.next() % n
        }
    }

    /// `y² = x³ + 3x + 6` over `F_10007`, generator `(0, 1973)` of prime
    /// order 10039 — the same curve as
    /// [`crate::cryptanalysis::ecdlp_variants::demo_group_small`], so the
    /// two solvers can be pointed at one instance.
    fn demo_params() -> CurveParams {
        CurveParams {
            name: "demo-10007",
            p: BigUint::from(10_007u32),
            a: BigUint::from(3u32),
            b: BigUint::from(6u32),
            gx: BigUint::from(0u32),
            gy: BigUint::from(1973u32),
            n: BigUint::from(10_039u32),
            h: 1,
        }
    }

    #[test]
    fn field_matches_biguint() {
        let c = toy40_params();
        let p = biguint_to_u64(&c.p).unwrap();
        let f = FastField::new(p).unwrap();
        let big = BigUint::from(p);
        let mut rng = Rng(0x1234_5678_9abc_def1);
        for i in 0..200 {
            let a = if i == 0 { 0 } else { rng.below(p) };
            let b = if i == 1 { p - 1 } else { rng.below(p) };
            let (ma, mb) = (f.to_mont(a), f.to_mont(b));
            assert_eq!(f.from_mont(ma), a, "round trip a");
            assert_eq!(f.from_mont(mb), b, "round trip b");
            assert_eq!(f.from_mont(f.add(ma, mb)), (a + b) % p, "add");
            assert_eq!(f.from_mont(f.sub(ma, mb)), (a + p - b) % p, "sub");
            let want_mul = (BigUint::from(a) * BigUint::from(b)) % &big;
            assert_eq!(
                BigUint::from(f.from_mont(f.mul(ma, mb))),
                want_mul,
                "mul {a} * {b}"
            );
            assert_eq!(f.from_mont(f.sqr(ma)), f.from_mont(f.mul(ma, ma)), "sqr");
            if a != 0 {
                assert_eq!(f.mul(ma, f.inv(ma)), f.one(), "a * a^-1");
            }
        }
        assert_eq!(f.inv(0), 0, "inv(0) is 0 by convention");
    }

    #[test]
    fn batch_inversion_matches_one_at_a_time() {
        let f = FastField::new(biguint_to_u64(&toy40_params().p).unwrap()).unwrap();
        let mut rng = Rng(99);
        for len in [1usize, 2, 7, 8, 16] {
            let vals: Vec<u64> = (0..len)
                .map(|_| f.to_mont(rng.below(f.modulus() - 1) + 1))
                .collect();
            let want: Vec<u64> = vals.iter().map(|&v| f.inv(v)).collect();
            let mut got = vals.clone();
            let mut scratch = vec![0u64; len];
            f.batch_inv(&mut got, &mut scratch);
            assert_eq!(got, want, "batch_inv len {len}");
        }
    }

    /// Every group operation against [`Point`], the crate's reference,
    /// including the three exceptional cases.
    #[test]
    fn group_law_matches_reference() {
        let params = toy40_params();
        let curve = FastCurve::from_params(&params).unwrap();
        let a_fe = params_a_fe(&params);
        let mut rng = Rng(0xdead_beef_cafe_1234);
        let g_ref = reference_scalar_mul(&params, 1);

        for _ in 0..40 {
            let ka = rng.below(curve.n - 1) + 1;
            let kb = rng.below(curve.n - 1) + 1;
            let (pa, pb) = (curve.scalar_mul(curve.g, ka), curve.scalar_mul(curve.g, kb));
            let (ra, rb) = (
                reference_scalar_mul(&params, ka),
                reference_scalar_mul(&params, kb),
            );
            assert_eq!(curve.lower(pa), ra, "scalar_mul {ka}");
            assert!(curve.on_curve(pa), "{ka}G on curve");
            assert_eq!(curve.lift(&ra), pa, "lift is the inverse of lower");
            assert_eq!(curve.lower(curve.add(pa, pb)), ra.add(&rb, &a_fe), "add");
            assert_eq!(curve.lower(curve.double(pa)), ra.double(&a_fe), "double");
            assert_eq!(curve.lower(curve.neg(pa)), ra.neg(), "neg");
            // P + (-P) = O, P + O = P, O + P = P
            assert!(curve.add(pa, curve.neg(pa)).infinity, "P + (-P)");
            assert_eq!(curve.add(pa, FastPoint::INFINITY), pa, "P + O");
            assert_eq!(curve.add(FastPoint::INFINITY, pa), pa, "O + P");
        }
        assert!(curve.scalar_mul(curve.g, curve.n).infinity, "nG = O");
        assert_eq!(curve.lower(curve.g), g_ref, "generator");
    }

    #[test]
    fn table_inserts_and_finds() {
        let t = BabyTable::new(15);
        let n = 12_000u32;
        let mut rng = Rng(7);
        let keys: Vec<u64> = (0..n).map(|_| rng.next()).collect();
        for (j, &k) in keys.iter().enumerate() {
            assert!(t.insert(k, j as u32 + 1), "insert {j}");
        }
        assert_eq!(t.len(), n as usize, "every entry stored");
        for (j, &k) in keys.iter().enumerate() {
            let mut hit = false;
            t.for_each_match(k, |v| hit |= v == j as u32 + 1);
            assert!(hit, "lookup {j}");
        }
        let mut fp = 0u32;
        for _ in 0..200_000 {
            t.for_each_match(rng.next(), |_| fp += 1);
        }
        assert!(fp < 8, "{fp} false positives on absent keys");
        // A full table refuses rather than spinning.
        let tiny = BabyTable::new(4);
        for j in 0..16 {
            assert!(tiny.insert(rng.next(), j));
        }
        assert!(!tiny.insert(rng.next(), 99), "full table must refuse");
    }

    /// Every `x` in a small interval is recovered, under both layouts and
    /// at several widths — this is the index arithmetic at its seams.
    #[test]
    fn covers_every_x_in_small_intervals() {
        let curve = toy40();
        for neg_map in [true, false] {
            for width in [1u64, 2, 3, 7, 16, 61, 200] {
                let x0 = 1_234_567u64;
                let plan = BsgsFastPlan::new(width, x0, neg_map, 2, 2);
                let mut solver = BsgsFast::build(curve, plan);
                assert_eq!(
                    solver.table_entries(),
                    solver.plan().m - 1,
                    "neg={neg_map} width={width} table"
                );
                for r in 0..width {
                    let x = x0 + r;
                    let q = curve.scalar_mul(curve.g, x);
                    assert_eq!(
                        solver.solve(&q),
                        Some(x),
                        "neg={neg_map} width={width} x={x}"
                    );
                }
            }
        }
    }

    /// A target outside the interval is reported as absent, not wrong.
    #[test]
    fn target_outside_the_interval_is_not_found() {
        let curve = toy40();
        let plan = BsgsFastPlan::new(1 << 12, 5_000_000, true, 2, 4);
        let mut solver = BsgsFast::build(curve, plan);
        let outside = curve.scalar_mul(curve.g, 99_999_999);
        assert_eq!(solver.solve(&outside), None);
        assert_eq!(solver.stats().false_candidates, solver.stats().candidates);
    }

    /// Interval logs at the seams of the layout and at random.
    #[test]
    fn solves_intervals_on_toy40() {
        let curve = toy40();
        let width = 1u64 << 20;
        let x0 = 0x3f_ffff_0000u64;
        let plan = BsgsFastPlan::new(width, x0, true, 4, 8);
        let mut solver = BsgsFast::build(curve, plan);
        let m = solver.plan().m;
        let stride = solver.plan().stride;
        let mut rng = Rng(0xfeed_face);
        let mut offsets = vec![0, 1, m - 1, m, stride - 1, stride, stride + 1, width - 1];
        for _ in 0..6 {
            offsets.push(rng.below(width));
        }
        for r in offsets {
            let x = x0 + r;
            let q = curve.scalar_mul(curve.g, x);
            assert_eq!(solver.solve(&q), Some(x), "x0 + {r}");
        }
        assert_eq!(
            solver.stats().false_candidates,
            0,
            "no false candidates expected at this size"
        );
    }

    /// The whole group, both layouts, on the 40-bit curve.
    #[test]
    fn solves_the_full_group_on_toy40() {
        let curve = toy40();
        for neg_map in [true, false] {
            let mut rng = Rng(if neg_map { 11 } else { 22 });
            for x in [0u64, 1, curve.n - 1, rng.below(curve.n)] {
                let q = curve.scalar_mul(curve.g, x);
                assert_eq!(
                    solve_full_group(curve, &q, neg_map),
                    Some(x),
                    "neg={neg_map} x={x}"
                );
            }
        }
    }

    /// One table, many targets: per-target cost must fall below what a
    /// single cold solve costs.
    #[test]
    fn one_table_serves_many_targets() {
        let curve = toy40();
        let width = 1u64 << 22;
        let x0 = 777_000u64;
        let plan = BsgsFastPlan::new(width, x0, true, 4, 8);
        let mut solver = BsgsFast::build(curve, plan);
        let table_cost = solver.stats().baby_steps;
        let mut rng = Rng(0xabc_123);
        let secrets: Vec<u64> = (0..12).map(|_| x0 + rng.below(width)).collect();
        let qs: Vec<FastPoint> = secrets
            .iter()
            .map(|&x| curve.scalar_mul(curve.g, x))
            .collect();
        let got = solver.solve_many(&qs);
        assert_eq!(
            got,
            secrets.iter().copied().map(Some).collect::<Vec<_>>(),
            "every target recovered"
        );
        let st = solver.stats();
        let n = secrets.len() as u64;
        let amortised = cost_ratio(&st, width, n);
        let cold = (table_cost + st.giant_steps / n) as f64 / isqrt_u64(width) as f64;
        assert!(
            amortised < cold,
            "amortised {amortised:.3} should beat a cold solve {cold:.3}"
        );
    }

    /// The fast solver and the general one must agree on the same
    /// instance: same curve, same target, same logarithm.
    #[test]
    fn agrees_with_the_general_bsgs() {
        let params = demo_params();
        let curve = FastCurve::from_params(&params).unwrap();
        let group = EcGroup::from_curve(&params);
        let mut rng = Rng(0x5eed);
        for _ in 0..8 {
            let x = rng.below(curve.n);
            let fast_q = curve.scalar_mul(curve.g, x);
            let slow_q = group.mul_setup(&BigUint::from(x));
            assert_eq!(curve.lower(fast_q), slow_q, "the two agree on xG");

            let fast = solve_full_group(curve, &fast_q, true).expect("fast solves");
            let reference = slow::bsgs_negation(&group, &slow_q).expect("general solves");
            assert_eq!(BigUint::from(fast), reference.x, "same logarithm for x={x}");
            assert_eq!(fast, x, "and it is the planted one");
        }
    }

    /// Whatever the solver returns has been verified as `kG == Q`, so a
    /// false candidate can never become an answer.  Force the issue with
    /// a deliberately overloaded table, where tag collisions are common.
    #[test]
    fn false_candidates_are_rejected_not_returned() {
        let curve = toy40();
        let width = 1u64 << 18;
        let x0 = 4242u64;
        let mut plan = BsgsFastPlan::new(width, x0, true, 2, 4);
        // Shrink the table to the legal minimum for m so probes are long
        // and tag matches frequent.
        plan.table_bits = {
            let mut b = 1u32;
            while (1u64 << b) < plan.m + 1 {
                b += 1;
            }
            b
        };
        let mut solver = BsgsFast::build(curve, plan);
        let mut rng = Rng(0x7777);
        for _ in 0..6 {
            let x = x0 + rng.below(width);
            let q = curve.scalar_mul(curve.g, x);
            assert_eq!(solver.solve(&q), Some(x), "x={x} under a tight table");
        }
    }
}
