//! Least-rotation canonicalization of an `N`-bit cyclic word held in three
//! limbs of `B` bits each (production: `N = 131`, `B = 64`, limbs 64/64/3).
//!
//! Convention (the same as `canonical_gap` in
//! `experiments/koblitz-n83-index-design-20260929/packed_index_e1_canonical_20261009/native_packed_index.rs`
//! and `FrobeniusCanon::least_rotation` in `crypto:src/cryptanalysis/koblitz_fast.rs`):
//! bit `i` of the integer is normal-basis coefficient `i`, limb `l` holds bits
//! `l*B .. l*B + B - 1`, `rotl(x, s) = ((x << s) | (x >> (N - s))) & mask`, and the
//! canonical form is `(min_s rotl(x, s), least such s)`.  The paper's `rot_j`
//! (word `w_0` most significant) is `rotl` with `w_j = bit N-1-j`.
//!
//! Arms (every one returns `(canonical word, shift k)`):
//! * [`exhaustive`]   reference: all `N` rotations, first minimum.
//! * [`gap_scan`]     variant-B analogue: set-bit ctz scan of the cyclic gaps,
//!                    rotate at every running-maximum gap.
//! * [`refine_bf`]    branch-free: bit-parallel candidate refinement with a
//!                    fixed `N - 1` steps, mask selects only, final rotation by
//!                    a fixed 8-stage masked barrel shifter.
//! * [`exhaustive_bf`] supplementary branch-free: the exhaustive chain with a
//!                    borrow-chain compare and mask selects (scalar "variant C").
//! * [`lift_scan`]    supplementary variant-A analogue: branch-free binary
//!                    lifting of the longest run, then a branchy candidate loop.
//!
//! The code is generic over `N` and `B` so the multi-limb paths (cross-limb
//! carries, the wrap from bit `N-1` to bit 0, empty or partial top limbs) can be
//! checked exhaustively at small `N` with small limbs (`tests/small_n.rs`).

#![allow(clippy::needless_range_loop)]

pub type W3 = [u64; 3];

/// Value barrier: returns `m` unchanged through an empty `asm!` block, so
/// the optimizer can no longer see that a selection mask is 0 or all-ones
/// and cannot turn the mask select back into a conditional jump (the first
/// build of `exhaustive_bf` without it compiled to a data-dependent `jne`).
/// No instruction is emitted.
#[inline(always)]
pub fn barrier(mut m: u64) -> u64 {
    #[cfg(any(target_arch = "x86_64", target_arch = "aarch64"))]
    unsafe {
        core::arch::asm!("/* {0} */", inout(reg) m, options(pure, nomem, nostack, preserves_flags));
    }
    #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
    {
        m = core::hint::black_box(m);
    }
    m
}

/// Geometry of an `N`-bit word in three `B`-bit limbs.
pub struct G<const N: u32, const B: u32>;

const fn limb_bits(n: u32, b: u32, l: u32) -> u32 {
    let lo = l * b;
    if n <= lo {
        0
    } else if n - lo >= b {
        b
    } else {
        n - lo
    }
}

const fn low_mask(bits: u32) -> u64 {
    if bits >= 64 {
        u64::MAX
    } else {
        (1u64 << bits) - 1
    }
}

impl<const N: u32, const B: u32> G<N, B> {
    pub const LIMB: u64 = low_mask(B);
    pub const MASK: W3 = [
        low_mask(limb_bits(N, B, 0)),
        low_mask(limb_bits(N, B, 1)),
        low_mask(limb_bits(N, B, 2)),
    ];
    /// Number of binary-lifting / barrel levels: bits of `N - 1`.
    pub const LEVELS: u32 = u32::BITS - (N - 1).leading_zeros();
    const OK: () = assert!(N >= 2 && N <= 256 && B >= 1 && B <= 64 && N <= 3 * B);

    #[inline(always)]
    pub fn mask(x: W3) -> W3 {
        let m = Self::MASK;
        [x[0] & m[0], x[1] & m[1], x[2] & m[2]]
    }

    #[inline(always)]
    pub fn is_zero(x: W3) -> bool {
        (x[0] | x[1] | x[2]) == 0
    }

    #[inline(always)]
    pub fn bit(x: W3, i: u32) -> u64 {
        (x[(i / B) as usize] >> (i % B)) & 1
    }

    /// `x << c` in the 3B-bit container (bits pushed past 3B are dropped).
    /// Branches only on `c`; called with constant `c` in the branch-free arms.
    #[inline(always)]
    pub fn shl(x: W3, c: u32) -> W3 {
        let _ = Self::OK;
        let q = (c / B) as usize;
        let r = c % B;
        let mut o = [0u64; 3];
        for i in 0..3 {
            if i < q {
                continue;
            }
            let mut v = (x[i - q] << r) & Self::LIMB;
            if r != 0 && i > q {
                v |= x[i - q - 1] >> (B - r);
            }
            o[i] = v;
        }
        o
    }

    /// `x >> c` in the 3B-bit container.
    #[inline(always)]
    pub fn shr(x: W3, c: u32) -> W3 {
        let q = (c / B) as usize;
        let r = c % B;
        let mut o = [0u64; 3];
        for i in 0..3 {
            if i + q > 2 {
                continue;
            }
            let mut v = x[i + q] >> r;
            if r != 0 && i + q + 1 <= 2 {
                v |= (x[i + q + 1] << (B - r)) & Self::LIMB;
            }
            o[i] = v;
        }
        o
    }

    /// Cyclic left rotation by `0 <= s < N`.
    #[inline(always)]
    pub fn rotl(x: W3, s: u32) -> W3 {
        if s == 0 {
            return x;
        }
        let a = Self::shl(x, s);
        let b = Self::shr(x, N - s);
        Self::mask([a[0] | b[0], a[1] | b[1], a[2] | b[2]])
    }

    /// Lexicographic (= numeric) `a < b`, top limb first (branchy form).
    #[inline(always)]
    pub fn lt(a: W3, b: W3) -> bool {
        (a[2], a[1], a[0]) < (b[2], b[1], b[0])
    }

    // ---- branch-free primitives -------------------------------------------

    /// All-ones when `x != 0`, else zero; no jump.
    #[inline(always)]
    pub fn nz_mask(x: W3) -> u64 {
        let v = x[0] | x[1] | x[2];
        // (v | -v) has its top bit set iff v != 0.
        0u64.wrapping_sub((v | v.wrapping_neg()) >> 63)
    }

    #[inline(always)]
    pub fn nz_mask1(v: u64) -> u64 {
        0u64.wrapping_sub((v | v.wrapping_neg()) >> 63)
    }

    /// All-ones when `a < b`: the borrow out of the three-limb subtraction.
    #[inline(always)]
    pub fn lt_mask(a: W3, b: W3) -> u64 {
        let (d0, c0) = a[0].overflowing_sub(b[0]);
        let _ = d0;
        let (d1, c1a) = a[1].overflowing_sub(b[1]);
        let (_, c1b) = d1.overflowing_sub(c0 as u64);
        let c1 = (c1a as u64) | (c1b as u64);
        let (d2, c2a) = a[2].overflowing_sub(b[2]);
        let (_, c2b) = d2.overflowing_sub(c1);
        let c2 = (c2a as u64) | (c2b as u64);
        0u64.wrapping_sub(c2)
    }

    #[inline(always)]
    pub fn sel(m: u64, a: W3, b: W3) -> W3 {
        let m = barrier(m);
        [
            (a[0] & m) | (b[0] & !m),
            (a[1] & m) | (b[1] & !m),
            (a[2] & m) | (b[2] & !m),
        ]
    }

    #[inline(always)]
    pub fn sel1(m: u64, a: u64, b: u64) -> u64 {
        let m = barrier(m);
        (a & m) | (b & !m)
    }

    /// Index of the highest set bit of a nonzero word, without a jump:
    /// per-limb `leading_zeros` (lzcnt, or bsr+cmov on baseline x86-64) and
    /// mask selection of the highest nonzero limb.
    #[inline(always)]
    pub fn msb_bf(x: W3) -> u32 {
        let p0 = (63u64).wrapping_sub(x[0].leading_zeros() as u64);
        let p1 = (B as u64 + 63).wrapping_sub(x[1].leading_zeros() as u64);
        let p2 = (2 * B as u64 + 63).wrapping_sub(x[2].leading_zeros() as u64);
        let mut p = p0;
        p = Self::sel1(Self::nz_mask1(x[1]), p1, p);
        p = Self::sel1(Self::nz_mask1(x[2]), p2, p);
        p as u32
    }

    /// Rotation by a secret `0 <= s < N`: `LEVELS` stages, stage `k` computes
    /// the constant rotation by `2^k` and keeps it under bit `k` of `s`.  The
    /// stages are written out (const generic `K`), so no loop or branch on
    /// the stage index survives in the object code.
    #[inline(always)]
    pub fn rotl_bf(x: W3, s: u32) -> W3 {
        let x = Self::barrel_stage::<0>(x, s);
        let x = Self::barrel_stage::<1>(x, s);
        let x = Self::barrel_stage::<2>(x, s);
        let x = Self::barrel_stage::<3>(x, s);
        let x = Self::barrel_stage::<4>(x, s);
        let x = Self::barrel_stage::<5>(x, s);
        let x = Self::barrel_stage::<6>(x, s);
        Self::barrel_stage::<7>(x, s)
    }

    #[inline(always)]
    fn barrel_stage<const K: u32>(x: W3, s: u32) -> W3 {
        if K >= Self::LEVELS {
            return x; // resolved at compile time
        }
        let r = Self::rotl(x, 1 << K);
        let m = 0u64.wrapping_sub(((s >> K) & 1) as u64);
        Self::sel(m, r, x)
    }

    #[inline(always)]
    fn double_stage<const K: u32>(pow: &mut [W3; 8]) {
        if K == 0 || K >= Self::LEVELS {
            return;
        }
        let p = pow[K as usize - 1];
        let r = Self::rotl(p, 1 << (K - 1));
        pow[K as usize] = [p[0] & r[0], p[1] & r[1], p[2] & r[2]];
    }

    #[inline(always)]
    fn lift_stage<const K: u32>(pow: &[W3; 8], run: &mut W3, len: &mut u64) {
        if K >= Self::LEVELS {
            return;
        }
        let r = Self::rotl(*run, 1 << K);
        let p = pow[K as usize];
        let next = [p[0] & r[0], p[1] & r[1], p[2] & r[2]];
        let m = Self::nz_mask(next);
        *run = Self::sel(m, next, *run);
        *len += m & (1u64 << K);
    }

    // ---- arms --------------------------------------------------------------

    /// (a) Exhaustive reference: rotate by one `N - 1` times, keep the first
    /// strict minimum, so ties take the smallest shift.
    #[inline(always)]
    pub fn exhaustive(x: W3) -> (W3, u32) {
        let mut best = x;
        let mut bs = 0;
        let mut cur = x;
        for s in 1..N {
            cur = Self::rotl(cur, 1);
            if Self::lt(cur, best) {
                best = cur;
                bs = s;
            }
        }
        (best, bs)
    }

    /// (b) Zero-gap set-bit scan, the variant-B analogue on three limbs.
    /// `ROT` counts the rotate-and-compare evaluations when `COUNT` is set.
    #[inline(always)]
    pub fn gap_scan_c<const COUNT: bool>(x: W3, rot: &mut u32) -> (W3, u32) {
        if Self::is_zero(x) || x == Self::MASK {
            return (x, 0);
        }
        let mut best = x;
        let mut best_shift = 0u32;
        let mut best_gap = 0u32;
        let mut first = u32::MAX;
        let mut prev = 0u32;
        let mut consider = |gap: u32, one: u32, best: &mut W3, bs: &mut u32, bg: &mut u32| {
            if gap == 0 || gap < *bg {
                return;
            }
            let shift = if one == 0 { 0 } else { N - one };
            let r = Self::rotl(x, shift);
            if COUNT {
                *rot += 1;
            }
            if gap > *bg || Self::lt(r, *best) || (r == *best && shift < *bs) {
                *bg = gap;
                *best = r;
                *bs = shift;
            }
        };
        for l in 0..3u32 {
            let mut rem = x[l as usize];
            while rem != 0 {
                let p = l * B + rem.trailing_zeros();
                rem &= rem - 1;
                if first == u32::MAX {
                    first = p;
                } else {
                    consider(p - prev - 1, p, &mut best, &mut best_shift, &mut best_gap);
                }
                prev = p;
            }
        }
        consider(first + N - prev - 1, first, &mut best, &mut best_shift, &mut best_gap);
        (best, best_shift)
    }

    #[inline(always)]
    pub fn gap_scan(x: W3) -> (W3, u32) {
        let mut r = 0;
        Self::gap_scan_c::<false>(x, &mut r)
    }

    /// (c) Branch-free bit-parallel refinement.
    ///
    /// `C` is a mask of candidate top positions `p` (the rotation by
    /// `s = N - 1 - p` reads bits `p, p-1, ...` from its most significant end).
    /// `B_t = rotl(x, t)` holds at position `p` bit `t` (from the top) of
    /// candidate `p`'s rotation.  Step `t` keeps the candidates with a zero
    /// there, unless none has one.  After `N - 1` steps the survivors are the
    /// minimal rotations (step `N - 1` never splits: all rotations have the
    /// same weight).  The first `Z` steps are exactly the zero-run growth of
    /// the zero-gap lemma.  The least shift is the highest surviving `p`; the
    /// constant words keep every position and so get `p = N - 1`, `s = 0`.
    #[inline(always)]
    pub fn refine_bf(x: W3) -> (W3, u32) {
        let mut c = Self::MASK;
        let mut b = x;
        for _ in 0..N - 1 {
            let cand = [c[0] & !b[0], c[1] & !b[1], c[2] & !b[2]];
            c = Self::sel(Self::nz_mask(cand), cand, c);
            b = Self::rotl(b, 1);
        }
        let p = Self::msb_bf(c);
        let s = N - 1 - p;
        (Self::rotl_bf(x, s), s)
    }

    /// Refinement with counts: (steps until one candidate is left — 0 for
    /// the constant words, which never get there — and the candidate count
    /// after the first `Z` steps, i.e. after the zero-gap filter).
    pub fn refine_depth(x: W3) -> u32 {
        let mut c = Self::MASK;
        let mut b = x;
        let pc = |c: W3| c[0].count_ones() + c[1].count_ones() + c[2].count_ones();
        if pc(c) == 1 {
            return 0;
        }
        for t in 0..N - 1 {
            let cand = [c[0] & !b[0], c[1] & !b[1], c[2] & !b[2]];
            if !Self::is_zero(cand) {
                c = cand;
            }
            b = Self::rotl(b, 1);
            if pc(c) == 1 {
                return t + 1;
            }
        }
        0
    }

    /// Supplementary branch-free exhaustive chain.
    #[inline(always)]
    pub fn exhaustive_bf(x: W3) -> (W3, u32) {
        let mut best = x;
        let mut bs = 0u64;
        let mut cur = x;
        for s in 1..N {
            cur = Self::rotl(cur, 1);
            let m = Self::lt_mask(cur, best);
            best = Self::sel(m, cur, best);
            bs = Self::sel1(m, s as u64, bs);
        }
        (best, bs as u32)
    }

    /// Branch-free longest-zero-run mask: bit `p` set iff a longest cyclic
    /// zero run has its top at `p`; also returns its length `Z`.  Needs
    /// `x != 0, MASK`.  Uses only constant rotations:
    /// `Z_{2a} = Z_a & rotl(Z_a, a)` and `Z_{l+2^k} = Z_{2^k} & rotl(Z_l, 2^k)`.
    #[inline(always)]
    pub fn longest_runs_bf(x: W3) -> (W3, u32) {
        let z = Self::mask([!x[0], !x[1], !x[2]]);
        let mut pow = [[0u64; 3]; 8];
        pow[0] = z;
        Self::double_stage::<1>(&mut pow);
        Self::double_stage::<2>(&mut pow);
        Self::double_stage::<3>(&mut pow);
        Self::double_stage::<4>(&mut pow);
        Self::double_stage::<5>(&mut pow);
        Self::double_stage::<6>(&mut pow);
        Self::double_stage::<7>(&mut pow);
        let mut run = z;
        let mut len = 1u64;
        // greedy top-down lifting
        Self::lift_stage::<7>(&pow, &mut run, &mut len);
        Self::lift_stage::<6>(&pow, &mut run, &mut len);
        Self::lift_stage::<5>(&pow, &mut run, &mut len);
        Self::lift_stage::<4>(&pow, &mut run, &mut len);
        Self::lift_stage::<3>(&pow, &mut run, &mut len);
        Self::lift_stage::<2>(&pow, &mut run, &mut len);
        Self::lift_stage::<1>(&pow, &mut run, &mut len);
        Self::lift_stage::<0>(&pow, &mut run, &mut len);
        (run, len as u32)
    }

    /// Supplementary variant-A analogue: branch-free lifting, then a loop
    /// over the longest-run tops (data-dependent trip count).
    #[inline(always)]
    pub fn lift_scan(x: W3) -> (W3, u32) {
        if Self::is_zero(x) || x == Self::MASK {
            return (x, 0);
        }
        let (run, _) = Self::longest_runs_bf(x);
        let mut best = Self::MASK;
        let mut bs = 0u32;
        for l in 0..3u32 {
            let mut rem = run[l as usize];
            while rem != 0 {
                let p = l * B + rem.trailing_zeros();
                rem &= rem - 1;
                let s = N - 1 - p;
                let v = Self::rotl(x, s);
                if Self::lt(v, best) || (v == best && s < bs) {
                    best = v;
                    bs = s;
                }
            }
        }
        (best, bs)
    }

    /// Diagnostics for one word: (longest zero run `Z`, number `c` of longest
    /// runs, gap-scan rotations).  Constant words give (N or 0, 0, 0).
    pub fn stats(x: W3) -> (u32, u32, u32) {
        if Self::is_zero(x) {
            return (N, 0, 0);
        }
        if x == Self::MASK {
            return (0, 0, 0);
        }
        let (run, z) = Self::longest_runs_bf(x);
        let c = run[0].count_ones() + run[1].count_ones() + run[2].count_ones();
        let mut rot = 0;
        Self::gap_scan_c::<true>(x, &mut rot);
        (z, c, rot)
    }
}

pub type F131 = G<131, 64>;
pub const MASK131: W3 = F131::MASK;

// ---- C-ABI entry points: stable names for cachegrind and objdump ---------

macro_rules! entry {
    ($name:ident, $f:ident) => {
        #[no_mangle]
        #[inline(never)]
        pub extern "C" fn $name(x: &W3, out: &mut W3) -> u32 {
            let (w, s) = F131::$f(*x);
            *out = w;
            s
        }
    };
}
entry!(canon131_exhaustive, exhaustive);
entry!(canon131_gap_scan, gap_scan);
entry!(canon131_refine_bf, refine_bf);
entry!(canon131_exhaustive_bf, exhaustive_bf);
entry!(canon131_lift_scan, lift_scan);

/// Null arm: copies the word.  Its Ir is the call/return/copy overhead that
/// every entry point also pays.
#[no_mangle]
#[inline(never)]
pub extern "C" fn canon131_null(x: &W3, out: &mut W3) -> u32 {
    *out = *x;
    0
}

pub const ARMS: [(&str, extern "C" fn(&W3, &mut W3) -> u32); 6] = [
    ("exhaustive", canon131_exhaustive),
    ("gap_scan", canon131_gap_scan),
    ("refine_bf", canon131_refine_bf),
    ("exhaustive_bf", canon131_exhaustive_bf),
    ("lift_scan", canon131_lift_scan),
    ("null", canon131_null),
];

// ---- deterministic generators -------------------------------------------

/// SplitMix64 (Steele, Lea, Flood 2014).
pub struct Rng(pub u64);
impl Rng {
    #[inline]
    pub fn next(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }
    pub fn below(&mut self, n: u64) -> u64 {
        ((self.next() as u128 * n as u128) >> 64) as u64
    }
    pub fn word131(&mut self) -> W3 {
        [self.next(), self.next(), self.next() & 7]
    }
}

pub fn set_bit(x: &mut W3, i: u32) {
    x[(i / 64) as usize] |= 1u64 << (i % 64);
}
pub fn clear_bit(x: &mut W3, i: u32) {
    x[(i / 64) as usize] &= !(1u64 << (i % 64));
}
pub fn flip_bit(x: &mut W3, i: u32) {
    x[(i / 64) as usize] ^= 1u64 << (i % 64);
}

/// The "structured" distribution of the protocol: a random pattern of
/// period `d` in 2..=20 repeated over 131 bits, then one random bit flipped
/// with probability 1/2.  These words have many tied longest runs and need
/// deep refinement.
pub fn structured131(rng: &mut Rng) -> W3 {
    let d = 2 + rng.below(19) as u32;
    let pat = rng.next() & ((1u64 << d) - 1);
    let mut x = [0u64; 3];
    for i in 0..131 {
        if (pat >> (i % d)) & 1 == 1 {
            set_bit(&mut x, i);
        }
    }
    if rng.next() & 1 == 1 {
        flip_bit(&mut x, rng.below(131) as u32);
    }
    x
}

// ---- independent oracle --------------------------------------------------

/// Bit-string oracle sharing no code with the limb arithmetic: the word as
/// a `Vec<bool>` (index 0 = most significant = bit N-1), every rotation
/// compared as a slice.
pub fn oracle(x: &W3, n: u32, b: u32) -> (Vec<bool>, u32) {
    let bit = |i: u32| (x[(i / b) as usize] >> (i % b)) & 1 == 1;
    let msb_first: Vec<bool> = (0..n).rev().map(bit).collect();
    let n = n as usize;
    let mut best: Vec<bool> = msb_first.clone();
    let mut bs = 0;
    for s in 1..n {
        // rotl by s: the integer's top bit becomes old bit N-1-s, i.e. the
        // msb-first string rotated left by s.
        let r: Vec<bool> = (0..n).map(|i| msb_first[(i + s) % n]).collect();
        if r < best {
            best = r;
            bs = s;
        }
    }
    (best, bs as u32)
}

pub fn to_msb_first(x: &W3, n: u32, b: u32) -> Vec<bool> {
    (0..n).rev().map(|i| (x[(i / b) as usize] >> (i % b)) & 1 == 1).collect()
}

// ---- field multiplication cost proxy -------------------------------------

/// Polynomial-basis product in F_2[z]/(z^131 + z^13 + z^2 + z + 1), three
/// limbs, PCLMULQDQ schoolbook.  A cost *proxy* only: neither crypto nor
/// this crate has a 131-bit normal-basis multiply.
pub mod fmul {
    use super::W3;

    #[cfg(target_arch = "x86_64")]
    #[target_feature(enable = "pclmulqdq,sse2")]
    unsafe fn clmul(a: u64, b: u64) -> (u64, u64) {
        use core::arch::x86_64::*;
        let r = _mm_clmulepi64_si128(_mm_cvtsi64_si128(a as i64), _mm_cvtsi64_si128(b as i64), 0);
        let lo = _mm_cvtsi128_si64(r) as u64;
        let hi = _mm_cvtsi128_si64(_mm_srli_si128(r, 8)) as u64;
        (lo, hi)
    }

    /// Reduce a 5-limb (< 2^262) product modulo z^131 + z^13 + z^2 + z + 1.
    #[inline(always)]
    pub fn reduce(mut t: [u64; 5]) -> W3 {
        for _ in 0..2 {
            // h = t >> 131 (at most 131 bits), t &= 2^131 - 1
            let h = [
                (t[2] >> 3) | (t[3] << 61),
                (t[3] >> 3) | (t[4] << 61),
                t[4] >> 3,
            ];
            t[2] &= 7;
            t[3] = 0;
            t[4] = 0;
            // t ^= h * (1 + z + z^2 + z^13)
            for &s in &[0u32, 1, 2, 13] {
                let sh = [
                    h[0] << s,
                    (h[1] << s) | if s == 0 { 0 } else { h[0] >> (64 - s) },
                    (h[2] << s) | if s == 0 { 0 } else { h[1] >> (64 - s) },
                    if s == 0 { 0 } else { h[2] >> (64 - s) },
                ];
                for i in 0..4 {
                    t[i] ^= sh[i];
                }
            }
        }
        [t[0], t[1], t[2]]
    }

    #[cfg(target_arch = "x86_64")]
    #[target_feature(enable = "pclmulqdq,sse2")]
    pub unsafe fn mul_clmul(a: &W3, b: &W3) -> W3 {
        let mut t = [0u64; 5];
        for i in 0..3 {
            for j in 0..3 {
                let (lo, hi) = clmul(a[i], b[j]);
                t[i + j] ^= lo;
                if i + j + 1 < 5 {
                    t[i + j + 1] ^= hi;
                }
            }
        }
        reduce(t)
    }

    /// Bitwise schoolbook reference.
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
        // bit-serial reduction
        for k in (131..262u32).rev() {
            if (t[(k / 64) as usize] >> (k % 64)) & 1 == 1 {
                for &e in &[131u32, 13, 2, 1, 0] {
                    let kk = k - 131 + e;
                    t[(kk / 64) as usize] ^= 1u64 << (kk % 64);
                }
            }
        }
        [t[0], t[1], t[2]]
    }
}

/// One 131-bit polynomial-basis multiply as a stable symbol for cachegrind.
#[cfg(target_arch = "x86_64")]
#[no_mangle]
#[inline(never)]
pub extern "C" fn fmul131_clmul(a: &W3, b: &W3, out: &mut W3) {
    *out = unsafe { fmul::mul_clmul(a, b) };
}
