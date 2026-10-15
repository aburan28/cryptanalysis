//! The five exact n = 131 canonicalizers of `canon-n131-20261014`, measured
//! inside a decomposition-style loop instead of in isolation.
//!
//! Per key the loop does what the n = 83 E-1 target stage does, in miniature:
//!
//! 1. **Field work on a serial chain.**  The state `s` (polynomial basis of the
//!    ECC2K-130 walk, `ecc2k130/src/f131.h`) advances by a fixed recurrence of
//!    real 131-bit field operations: `W1` is one multiply and one squaring,
//!    `W5` five multiplies and one squaring.  The recurrence is a *proxy* for
//!    a point operation: the elements are genuine field elements but not
//!    x-coordinates of curve points.
//! 2. **Conversion to the normal basis.**  `x = to_cyclic(from_polynomial(s))`:
//!    the walk's own polynomial -> permuted type-II normal basis network, then
//!    the fixed bit permutation to the cyclic order in which Frobenius
//!    (squaring) is a rotation by one.  Both are common to every arm.
//! 3. **Canonicalization** of `x` by the arm under test (the canon-n131 code
//!    itself, through its `G<131, 64>` functions, inlined into the loop).
//! 4. **Probe** of a hashed table of canonical keys: bucket directory plus
//!    exact 24-byte records, as in the E-1 design (22-bit directory, 18-byte
//!    records there).  A hit is counted; it does not feed back.
//!
//! The next state depends only on the previous state, never on the key, so
//! steps 2-4 of key `i` are off the critical path and can overlap with the
//! field chain of keys `i+1, ...` as far as the core's window allows.  That
//! overlap, and the branch behaviour of each arm next to the probe's own
//! branches, is what this crate measures.

#![allow(clippy::needless_range_loop)]

pub use canon_n131::{Rng, F131, W3};

#[cfg(all(target_arch = "x86_64", not(target_feature = "pclmulqdq")))]
compile_error!("build with -C target-feature=+pclmulqdq (see .cargo/config.toml)");

// ---- field: a line-for-line port of ecc2k130/src/f131.h ------------------

pub mod field {
    use super::W3;

    /// 64 x 64 -> 128 carry-less multiply (PCLMULQDQ).
    #[inline(always)]
    pub fn clmul(a: u64, b: u64) -> (u64, u64) {
        #[cfg(target_arch = "x86_64")]
        unsafe {
            use core::arch::x86_64::*;
            let p = _mm_clmulepi64_si128(_mm_cvtsi64_si128(a as i64), _mm_cvtsi64_si128(b as i64), 0);
            (_mm_cvtsi128_si64(p) as u64, _mm_cvtsi128_si64(_mm_unpackhi_epi64(p, p)) as u64)
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            let (mut lo, mut hi) = (0u64, 0u64);
            for i in 0..64 {
                if (b >> i) & 1 == 1 {
                    lo ^= a << i;
                    if i > 0 {
                        hi ^= a >> (64 - i);
                    }
                }
            }
            (lo, hi)
        }
    }

    /// `x * y` for a 3-bit `x` (f131.h `mulTiny`).
    #[inline(always)]
    fn mul_tiny(x: u64, y: u64) -> (u64, u64) {
        let m0 = 0u64.wrapping_sub(x & 1);
        let m1 = 0u64.wrapping_sub((x >> 1) & 1);
        let m2 = 0u64.wrapping_sub((x >> 2) & 1);
        ((y & m0) ^ ((y << 1) & m1) ^ ((y << 2) & m2), ((y >> 63) & m1) ^ ((y >> 62) & m2))
    }

    /// `H mod m` for a product of degree <= 260 (f131.h `reduce`).
    #[inline(always)]
    pub fn reduce(h: [u64; 5]) -> W3 {
        let d0 = (h[2] >> 3) | (h[3] << 61);
        let d1 = (h[3] >> 3) | (h[4] << 61);
        let d2 = (h[4] >> 3) & 3;
        let r0 = d0 ^ (d0 >> 1) ^ (d1 << 63) ^ (d0 >> 3) ^ (d1 << 61);
        let r1 = d1 ^ (d1 >> 1) ^ (d2 << 63) ^ (d1 >> 3) ^ (d2 << 61);
        let r2 = d2 ^ (d2 >> 1);
        let q0 = d0 ^ (r0 >> 1) ^ (r1 << 63) ^ (r0 >> 9) ^ (r1 << 55) ^ (r0 >> 25) ^ (r1 << 39)
            ^ (r0 >> 57) ^ (r1 << 7) ^ (r1 >> 57) ^ (r2 << 7);
        let q1 = d1 ^ (r1 >> 1) ^ (r2 << 63) ^ (r1 >> 9) ^ (r2 << 55) ^ (r1 >> 25) ^ (r2 << 39)
            ^ (r1 >> 57) ^ (r2 << 7);
        let q2 = d2 ^ (r2 >> 1);
        let t0 = q0 ^ (q0 << 2) ^ (q0 << 3);
        let t1 = q1 ^ (q1 << 2) ^ (q0 >> 62) ^ (q1 << 3) ^ (q0 >> 61);
        let t2 = q2 ^ (q2 << 2) ^ (q1 >> 62) ^ (q2 << 3) ^ (q1 >> 61);
        [
            h[0] ^ t0,
            h[1] ^ t1 ^ t0 ^ (t0 << 32) ^ (t0 << 48) ^ (t0 << 56) ^ (q0 << 60),
            (h[2] ^ t2 ^ t1 ^ (t0 >> 32) ^ (t0 >> 16) ^ (t0 >> 8) ^ t0 ^ (q0 >> 4)) & 7,
        ]
    }

    /// Unreduced product: Karatsuba on the two full limbs, then the 3-bit top
    /// limbs' cross terms (f131.h `product`, x86-64 path).
    #[inline(always)]
    pub fn product(a: &W3, b: &W3) -> [u64; 5] {
        let (l0, l1) = clmul(a[0], b[0]);
        let (h0, h1) = clmul(a[1], b[1]);
        let (mut m0, mut m1) = clmul(a[0] ^ a[1], b[0] ^ b[1]);
        m0 ^= l0 ^ h0;
        m1 ^= l1 ^ h1;
        let (x0, x1) = mul_tiny(a[2], b[0]);
        let (y0, y1) = mul_tiny(b[2], a[0]);
        let (u0, u1) = mul_tiny(a[2], b[1]);
        let (v0, v1) = mul_tiny(b[2], a[1]);
        let (top, _) = mul_tiny(a[2], b[2]);
        [l0, l1 ^ m0, h0 ^ m1 ^ x0 ^ y0, h1 ^ x1 ^ y1 ^ u0 ^ v0, u1 ^ v1 ^ top]
    }

    #[inline(always)]
    pub fn mul(a: &W3, b: &W3) -> W3 {
        reduce(product(a, b))
    }

    #[inline(always)]
    pub fn sqr(a: &W3) -> W3 {
        let (h0, h1) = clmul(a[0], a[0]);
        let (h2, h3) = clmul(a[1], a[1]);
        let h4 = (a[2] & 1) | ((a[2] & 2) << 1) | ((a[2] & 4) << 2);
        reduce([h0, h1, h2, h3, h4])
    }

    /// Reduced polynomial basis -> permuted type-II normal basis
    /// (f131.h `fromPolynomial`): bit `i - 1` holds the coefficient of
    /// `beta_i = gamma^i + gamma^-i`, `gamma` a primitive 263rd root of unity.
    #[inline(always)]
    pub fn from_polynomial(a: &W3) -> W3 {
        let (mut w0, mut w1) = (a[0], a[1]);
        let w2 = a[2];
        w0 ^= w1 & 0xffffffff00000000;
        w0 ^= ((w0 >> 32) | (w1 << 32)) & 0xffff0000ffff0000;
        w1 ^= ((w1 >> 32) | (w2 << 32)) & 0x00000000ffff0000;
        w0 ^= ((w0 >> 16) | (w1 << 48)) & 0xff00ff00ff00ff00;
        w1 ^= ((w1 >> 16) | (w2 << 48)) & 0x0000ff00ff00ff00;
        w0 ^= ((w0 >> 8) | (w1 << 56)) & 0xf0f0f0f0f0f0f0f0;
        w1 ^= ((w1 >> 8) | (w2 << 56)) & 0x00f0f0f0f0f0f0f0;
        w0 ^= ((w0 >> 4) | (w1 << 60)) & 0xcccccccccccccccc;
        w1 ^= ((w1 >> 4) | (w2 << 60)) & 0x4ccccccccccccccc;
        w0 ^= ((w0 >> 2) | (w1 << 62)) & 0xaaaaaaaaaaaaaaaa;
        w1 ^= ((w1 >> 2) | (w2 << 62)) & 0xaaaaaaaaaaaaaaaa;
        let sign = 0u64.wrapping_sub(w0 & 1);
        [
            ((w0 >> 1) | (w1 << 63)) ^ sign,
            ((w1 >> 1) | (w2 << 63)) ^ sign,
            ((w2 >> 1) ^ sign) & 7,
        ]
    }

    /// Bitwise schoolbook product mod the walk's modulus, derived from
    /// `reduce` applied to the single monomials z^131..z^260 (each reduced
    /// one at a time), so it shares the reduction but none of the clmul,
    /// Karatsuba or tiny-limb code.  Test oracle only.
    pub fn mul_ref(a: &W3, b: &W3) -> W3 {
        let mut t = [0u64; 5];
        for i in 0..131u32 {
            if (a[(i / 64) as usize] >> (i % 64)) & 1 == 1 {
                for j in 0..131u32 {
                    if (b[(j / 64) as usize] >> (j % 64)) & 1 == 1 {
                        let k = i + j;
                        t[(k / 64) as usize] ^= 1u64 << (k % 64);
                    }
                }
            }
        }
        reduce(t)
    }
}

// ---- permuted type-II normal basis -> cyclic normal basis ----------------

/// `fold(t) = t` for `t <= 131`, else `263 - t`.
pub const fn fold(t: u32) -> u32 {
    if t <= 131 {
        t
    } else {
        263 - t
    }
}

/// `CYC_SRC[j]` = the permuted bit holding normal-basis coordinate `j`, i.e.
/// the coefficient of `alpha^(2^j)` with `alpha = beta_1`:
/// `beta_1^(2^j) = beta_{fold(2^j mod 263)}`, at bit `fold(2^j mod 263) - 1`.
/// 263 = 2 * 131 + 1 is prime and 2 has order 131 modulo 263 with -1 a
/// non-residue, so `j -> fold(2^j)` is a bijection onto 1..=131.
pub fn cyc_src() -> [u32; 131] {
    let mut out = [0u32; 131];
    let mut p = 1u32;
    for j in 0..131 {
        out[j] = fold(p) - 1;
        p = (p * 2) % 263;
    }
    out
}

/// Nibble tables for the permutation: entry `[k][v]` is the cyclic word for
/// permuted bits `4k..4k+3` equal to `v`.  33 x 16 x 24 B = 12.7 KB (L1).
pub struct ToCyclic {
    pub t: Box<[[W3; 16]; 33]>,
}

impl ToCyclic {
    pub fn new() -> Self {
        let src = cyc_src();
        let mut dst = [0u32; 131]; // permuted bit -> cyclic bit
        for (j, &s) in src.iter().enumerate() {
            dst[s as usize] = j as u32;
        }
        let mut t = Box::new([[[0u64; 3]; 16]; 33]);
        for k in 0..33 {
            for v in 0..16u32 {
                let mut w = [0u64; 3];
                for b in 0..4 {
                    let pb = 4 * k as u32 + b;
                    if pb < 131 && (v >> b) & 1 == 1 {
                        let c = dst[pb as usize];
                        w[(c / 64) as usize] |= 1u64 << (c % 64);
                    }
                }
                t[k][v as usize] = w;
            }
        }
        ToCyclic { t }
    }

    #[inline(always)]
    pub fn apply(&self, x: &W3) -> W3 {
        let mut o = [0u64; 3];
        for k in 0..33 {
            let l = k / 16;
            let v = ((x[l] >> (4 * (k % 16))) & 15) as usize;
            let e = &self.t[k][v];
            o[0] ^= e[0];
            o[1] ^= e[1];
            o[2] ^= e[2];
        }
        o
    }

    /// Bit-by-bit reference (test oracle).
    pub fn apply_ref(x: &W3) -> W3 {
        let src = cyc_src();
        let mut o = [0u64; 3];
        for j in 0..131u32 {
            let s = src[j as usize];
            if (x[(s / 64) as usize] >> (s % 64)) & 1 == 1 {
                o[(j / 64) as usize] |= 1u64 << (j % 64);
            }
        }
        o
    }
}

impl Default for ToCyclic {
    fn default() -> Self {
        Self::new()
    }
}

// ---- per-key field work ---------------------------------------------------

/// Fixed constants of the recurrences (arbitrary, from SplitMix64 seed 131).
pub fn consts() -> [W3; 4] {
    let mut r = Rng(131);
    [r.word131(), r.word131(), r.word131(), r.word131()]
}

/// `W1`: `s' = s * g0 + s^2` (one multiply, one squaring on the chain).
#[inline(always)]
pub fn step_w1(s: &W3, g: &[W3; 4]) -> W3 {
    let a = field::mul(s, &g[0]);
    let b = field::sqr(s);
    [a[0] ^ b[0], a[1] ^ b[1], a[2] ^ b[2]]
}

#[inline(always)]
fn add(a: &W3, b: &W3) -> W3 {
    [a[0] ^ b[0], a[1] ^ b[1], a[2] ^ b[2]]
}

/// `W5`: five multiplies and one squaring, about the field work of an affine
/// point addition with its share of a batched (Montgomery) inversion.
#[inline(always)]
pub fn step_w5(s: &W3, g: &[W3; 4]) -> W3 {
    let t1 = field::mul(s, &g[0]);
    let t2 = add(&field::mul(&t1, &g[1]), s);
    let t3 = field::sqr(&t2);
    let t4 = add(&field::mul(&t3, &g[2]), &t1);
    let t5 = field::mul(&t4, &t2);
    add(&field::mul(&t5, &g[3]), &t3)
}

#[inline(always)]
pub fn step<const WORK: u8>(s: &W3, g: &[W3; 4]) -> W3 {
    if WORK == 1 {
        step_w1(s, g)
    } else {
        step_w5(s, g)
    }
}

// ---- hashed table of canonical keys ---------------------------------------

#[inline(always)]
pub fn hash(k: &W3, bits: u32) -> usize {
    let v = k[0].wrapping_mul(0x9E37_79B9_7F4A_7C15)
        ^ k[1].wrapping_mul(0xC2B2_AE3D_27D4_EB4F)
        ^ k[2].wrapping_mul(0x1656_67B1_9E37_79F9);
    ((v ^ (v >> 29)).wrapping_mul(0xBF58_476D_1CE4_E5B9) >> (64 - bits)) as usize
}

/// Bucket directory (`dir[b]..dir[b+1]`) over exact records grouped by
/// bucket.  Built by a counting sort; lookups compare all three limbs.
pub struct Table {
    pub bits: u32,
    pub dir: Vec<u32>,
    pub recs: Vec<W3>,
}

impl Table {
    pub fn build(keys: &[W3], bits: u32) -> Table {
        let nb = 1usize << bits;
        let mut cnt = vec![0u32; nb + 1];
        for k in keys {
            cnt[hash(k, bits) + 1] += 1;
        }
        for b in 0..nb {
            cnt[b + 1] += cnt[b];
        }
        let dir = cnt.clone();
        let mut fill = cnt;
        let mut recs = vec![[0u64; 3]; keys.len()];
        for k in keys {
            let b = hash(k, bits);
            recs[fill[b] as usize] = *k;
            fill[b] += 1;
        }
        Table { bits, dir, recs }
    }

    #[inline(always)]
    pub fn probe(&self, k: &W3) -> bool {
        let b = hash(k, self.bits);
        let (lo, hi) = (self.dir[b] as usize, self.dir[b + 1] as usize);
        for r in &self.recs[lo..hi] {
            if r[0] == k[0] && r[1] == k[1] && r[2] == k[2] {
                return true;
            }
        }
        false
    }

    pub fn bytes(&self) -> usize {
        self.dir.len() * 4 + self.recs.len() * 24
    }
}

// ---- arms ------------------------------------------------------------------

pub const ARM_NULL: u8 = 0;
pub const ARM_EXHAUSTIVE: u8 = 1;
pub const ARM_GAP_SCAN: u8 = 2;
pub const ARM_REFINE_BF: u8 = 3;
pub const ARM_EXHAUSTIVE_BF: u8 = 4;
pub const ARM_LIFT_SCAN: u8 = 5;
/// A second copy of `lift_scan` at its own address: the A/A negative control.
pub const ARM_LIFT_SCAN_AA: u8 = 6;

pub const ARM_NAMES: [&str; 7] =
    ["null", "exhaustive", "gap_scan", "refine_bf", "exhaustive_bf", "lift_scan", "lift_scan_aa"];

#[inline(always)]
pub fn canon<const ARM: u8>(x: W3) -> (W3, u32) {
    match ARM {
        ARM_NULL => (x, 0),
        ARM_EXHAUSTIVE => F131::exhaustive(x),
        ARM_GAP_SCAN => F131::gap_scan(x),
        ARM_REFINE_BF => F131::refine_bf(x),
        ARM_EXHAUSTIVE_BF => F131::exhaustive_bf(x),
        _ => F131::lift_scan(x),
    }
}

/// What a pass returns; equal across the five real arms (and the A/A copy)
/// on the same workload, by construction of an exact canonicalizer.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub struct Summary {
    pub hits: u64,
    pub key_hash: u64,
    pub shift_sum: u64,
    pub last_state: W3,
}

#[inline(always)]
pub fn fold_key(h: u64, k: &W3, s: u32) -> u64 {
    (h ^ k[0] ^ k[1].rotate_left(21) ^ k[2].rotate_left(42) ^ ((s as u64) << 56))
        .wrapping_mul(0x9E37_79B9_7F4A_7C15)
        .rotate_left(29)
}

/// Shared environment of every pass on one workload.
pub struct Ctx {
    pub g: [W3; 4],
    pub cyc: ToCyclic,
}

/// One pass over `n` keys from state `s0`.  `rec`, when given, receives every
/// `(key, shift, hit)`; the timed entry points pass `None` and the branch on
/// it is resolved at compile time.
#[inline(always)]
pub fn run_loop<const ARM: u8, const WORK: u8, const REC: bool>(
    t: &Table,
    c: &Ctx,
    s0: W3,
    n: usize,
    rec: &mut Vec<(W3, u32, bool)>,
) -> Summary {
    let mut s = s0;
    let mut out = Summary::default();
    for _ in 0..n {
        s = step::<WORK>(&s, &c.g);
        let x = c.cyc.apply(&field::from_polynomial(&s));
        let (k, sh) = canon::<ARM>(x);
        let hit = t.probe(&k);
        out.hits += hit as u64;
        out.key_hash = fold_key(out.key_hash, &k, sh);
        out.shift_sum += sh as u64;
        if REC {
            rec.push((k, sh, hit));
        }
    }
    out.last_state = s;
    out
}

/// The `n` normal-basis words of the stream (no canonicalization), for the
/// verifier and the table builder.
pub fn stream<const WORK: u8>(c: &Ctx, s0: W3, n: usize) -> Vec<W3> {
    let mut s = s0;
    (0..n)
        .map(|_| {
            s = step::<WORK>(&s, &c.g);
            c.cyc.apply(&field::from_polynomial(&s))
        })
        .collect()
}

pub type LoopFn = fn(&Table, &Ctx, W3, usize) -> Summary;

macro_rules! entries {
    ($( $name:ident = ($arm:expr, $work:expr) ),* $(,)?) => {
        $(
            /// Stable symbol for cachegrind: the whole loop body of one arm
            /// and work level, canonicalizer and field code inlined.
            #[no_mangle]
            #[inline(never)]
            pub fn $name(t: &Table, c: &Ctx, s0: W3, n: usize) -> Summary {
                // An empty asm block whose text names the arm and work level: it
                // emits no instruction, but it keeps LLVM's function merging from
                // folding lift_scan_aa into lift_scan (it did, before this).
                #[cfg(target_arch = "x86_64")]
                unsafe {
                    core::arch::asm!("/* arm {0} work {1} */", const $arm, const $work,
                                     options(nomem, nostack, preserves_flags));
                }
                let mut v = Vec::new();
                run_loop::<{ $arm }, { $work }, false>(t, c, s0, n, &mut v)
            }
        )*
    };
}

entries!(
    loop_null_w1 = (ARM_NULL, 1),
    loop_exhaustive_w1 = (ARM_EXHAUSTIVE, 1),
    loop_gap_scan_w1 = (ARM_GAP_SCAN, 1),
    loop_refine_bf_w1 = (ARM_REFINE_BF, 1),
    loop_exhaustive_bf_w1 = (ARM_EXHAUSTIVE_BF, 1),
    loop_lift_scan_w1 = (ARM_LIFT_SCAN, 1),
    loop_lift_scan_aa_w1 = (ARM_LIFT_SCAN_AA, 1),
    loop_null_w5 = (ARM_NULL, 5),
    loop_exhaustive_w5 = (ARM_EXHAUSTIVE, 5),
    loop_gap_scan_w5 = (ARM_GAP_SCAN, 5),
    loop_refine_bf_w5 = (ARM_REFINE_BF, 5),
    loop_exhaustive_bf_w5 = (ARM_EXHAUSTIVE_BF, 5),
    loop_lift_scan_w5 = (ARM_LIFT_SCAN, 5),
    loop_lift_scan_aa_w5 = (ARM_LIFT_SCAN_AA, 5),
);

/// `loop_fn(arm, work)`: the entry point for an arm index and work level.
pub fn loop_fn(arm: usize, work: u8) -> LoopFn {
    const W1: [LoopFn; 7] = [
        loop_null_w1, loop_exhaustive_w1, loop_gap_scan_w1, loop_refine_bf_w1,
        loop_exhaustive_bf_w1, loop_lift_scan_w1, loop_lift_scan_aa_w1,
    ];
    const W5: [LoopFn; 7] = [
        loop_null_w5, loop_exhaustive_w5, loop_gap_scan_w5, loop_refine_bf_w5,
        loop_exhaustive_bf_w5, loop_lift_scan_w5, loop_lift_scan_aa_w5,
    ];
    if work == 1 { W1[arm] } else { W5[arm] }
}

/// Recording pass for an arm index (verifier only, not timed).
pub fn record(arm: usize, work: u8, t: &Table, c: &Ctx, s0: W3, n: usize) -> (Summary, Vec<(W3, u32, bool)>) {
    let mut v = Vec::with_capacity(n);
    macro_rules! go {
        ($a:expr) => {
            if work == 1 {
                run_loop::<{ $a }, 1, true>(t, c, s0, n, &mut v)
            } else {
                run_loop::<{ $a }, 5, true>(t, c, s0, n, &mut v)
            }
        };
    }
    let s = match arm {
        0 => go!(0),
        1 => go!(1),
        2 => go!(2),
        3 => go!(3),
        4 => go!(4),
        5 => go!(5),
        _ => go!(6),
    };
    (s, v)
}

// ---- workloads ------------------------------------------------------------

/// One frozen workload: work level, table size, seeds.  The values are
/// copied from `protocol.json` by the binaries (which check them).
#[derive(Clone, Debug)]
pub struct Workload {
    pub name: String,
    pub work: u8,
    /// Total records in the table, a power of two.
    pub records_log2: u32,
    /// Directory bits: records / 4 buckets on average.
    pub dir_bits: u32,
    /// Keys whose canonical forms are planted: index `i < plant_span` with
    /// `plant_mix(i) % plant_period == 0`.
    pub plant_span: usize,
    pub plant_period: u64,
    pub seed: u64,
}

pub fn plant_mix(seed: u64, i: u64) -> u64 {
    let mut r = Rng(seed ^ i.wrapping_mul(0xD1B5_4A32_D192_ED03));
    r.next()
}

impl Workload {
    pub fn s0(&self) -> W3 {
        let mut r = Rng(self.seed);
        r.word131()
    }

    pub fn planted(&self, i: usize) -> bool {
        i < self.plant_span && plant_mix(self.seed ^ 0x706c616e74, i as u64) % self.plant_period == 0
    }

    /// The table: planted keys (canonical forms of planted stream positions,
    /// by the canon-n131 `exhaustive` reference) plus filler keys
    /// (canonical forms of independent uniform words, by `lift_scan`, which
    /// canon-n131 verified exact on 10^7 uniform words and the structured
    /// families).  Returns the table and the planted positions.
    pub fn build(&self, c: &Ctx) -> (Table, Vec<usize>) {
        let xs = match self.work {
            1 => stream::<1>(c, self.s0(), self.plant_span),
            _ => stream::<5>(c, self.s0(), self.plant_span),
        };
        let mut keys = Vec::with_capacity(1 << self.records_log2);
        let mut pos = vec![];
        for (i, x) in xs.iter().enumerate() {
            if self.planted(i) {
                keys.push(F131::exhaustive(*x).0);
                pos.push(i);
            }
        }
        let total = 1usize << self.records_log2;
        assert!(keys.len() < total, "planted keys exceed the table");
        let mut r = Rng(self.seed ^ 0x66696c6c6572);
        while keys.len() < total {
            keys.push(F131::lift_scan(r.word131()).0);
        }
        (Table::build(&keys, self.dir_bits), pos)
    }
}

// ---- minimal JSON reader for protocol.json (no dependencies) ---------------

/// Extracts the integer after `"key":` in the first object after `"name": "<w>"`.
/// Good enough for the flat workload records written in protocol.json.
pub fn json_int(text: &str, key: &str) -> Option<u64> {
    let pat = format!("\"{key}\":");
    let i = text.find(&pat)? + pat.len();
    let rest = text[i..].trim_start();
    let end = rest.find(|c: char| !c.is_ascii_digit()).unwrap_or(rest.len());
    rest[..end].parse().ok()
}

pub fn workloads_from_protocol(text: &str) -> Vec<Workload> {
    let mut out = vec![];
    let mut rest = text;
    while let Some(i) = rest.find("\"workload\":") {
        let obj_start = i;
        let obj_end = rest[obj_start..].find('}').map(|e| obj_start + e).expect("workload object");
        let obj = &rest[obj_start..obj_end];
        let name_i = obj.find("\"workload\":").unwrap() + 11;
        let name = obj[name_i..].trim_start().trim_start_matches('"');
        let name = name[..name.find('"').unwrap()].to_string();
        out.push(Workload {
            name,
            work: json_int(obj, "work_muls").expect("work_muls") as u8,
            records_log2: json_int(obj, "records_log2").expect("records_log2") as u32,
            dir_bits: json_int(obj, "dir_bits").expect("dir_bits") as u32,
            plant_span: json_int(obj, "plant_span").expect("plant_span") as usize,
            plant_period: json_int(obj, "plant_period").expect("plant_period"),
            seed: json_int(obj, "seed").expect("seed"),
        });
        rest = &rest[obj_end..];
    }
    out
}
