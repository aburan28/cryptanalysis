//! Two-limb binary-lifting least-rotation canonicalizer (`lift_scan`) for
//! `N`-bit cyclic words, `B < N <= 2B`, held as `[lo, hi]`: `lo` has bits
//! `0 .. B-1`, `hi` has bits `B .. N-1`.  Production geometry: `N = 83`,
//! `B = 64` (limbs 64 + 19), the n = 83 normal-basis words of the
//! `koblitz_orbit_dlp_fast_online` wide path and of the E-1 packed-index stage.
//!
//! Convention (identical to `NormalBasis128::canonical` in crypto 770f6a69
//! `examples/koblitz_orbit_dlp_fast_online.rs`, to `Cycle::canonical` in
//! `packed_index_e1_canonical_20261009/native_packed_index.rs`, and to
//! `canon-n131-20261014`): bit `i` of the integer is normal-basis coefficient
//! `i`, `rotl(x, s) = ((x << s) | (x >> (N - s))) & mask`, and the canonical
//! form of `x` is `(min_s rotl(x, s), least such s)`.  The words `0` and
//! `mask` return shift 0, as the full scan does.
//!
//! Method (the variant-A analogue of `canon-n131-20261014`'s `lift_scan`):
//! for a nonconstant word the least rotation begins with a longest cyclic
//! zero run.  `Z_1 = !x`; `Z_{2a} = Z_a & rotl(Z_a, a)` gives the masks of
//! zero runs of length `2^k` (bit `p` set iff bits `p, p-1, ..., p-2^k+1`
//! are zero, cyclically); greedy top-down lifting
//! `R <- Z_{2^k} & rotl(R, 2^k)` (kept only when nonzero) ends with `R` = the
//! tops of all longest runs.  Every top `p` gives the candidate rotation
//! `s = N - 1 - p`; the least candidate wins, ties to the smaller shift.
//! The lifting uses only constant rotations and mask selects (no jumps);
//! the candidate loop has a data-dependent trip count (the number of
//! longest runs).
//!
//! The code is generic over `N` and `B` so that the cross-limb paths (the
//! carry between limbs, the wrap from bit `N-1` to bit 0, a one-bit top
//! limb) are checked exhaustively at small `N` (`tests/exhaustive.rs`).

#![allow(clippy::needless_range_loop)]

/// Two limbs: `[lo, hi]`.
pub type W2 = [u64; 2];

/// Value barrier: an empty `asm!` block hides whether a select mask is 0 or
/// all-ones, so the mask select is not turned back into a jump.  It emits no
/// instruction.
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

const fn low_mask(bits: u32) -> u64 {
    if bits >= 64 {
        u64::MAX
    } else {
        (1u64 << bits) - 1
    }
}

/// Geometry of an `N`-bit word in a `B`-bit low limb and an `(N - B)`-bit
/// high limb.
pub struct L2<const N: u32, const B: u32>;

impl<const N: u32, const B: u32> L2<N, B> {
    pub const LO: u64 = low_mask(B);
    pub const HI: u64 = low_mask(N - B);
    pub const MASK: W2 = [Self::LO, Self::HI];
    /// Lifting levels `k = 0 .. LEVELS-1`, the bits of `N - 1`: the longest
    /// zero run of a nonconstant word has length at most `N - 1`.
    pub const LEVELS: u32 = u32::BITS - (N - 1).leading_zeros();
    const OK: () = assert!(N >= 3 && B >= 2 && B <= 64 && B < N && N <= 2 * B && N <= 128);

    #[inline(always)]
    pub fn from_u128(v: u128) -> W2 {
        let _ = Self::OK;
        [(v as u64) & Self::LO, ((v >> B) as u64) & Self::HI]
    }

    #[inline(always)]
    pub fn to_u128(x: W2) -> u128 {
        (x[0] as u128) | ((x[1] as u128) << B)
    }

    #[inline(always)]
    pub fn is_zero(x: W2) -> bool {
        (x[0] | x[1]) == 0
    }

    #[inline(always)]
    pub fn is_mask(x: W2) -> bool {
        x[0] == Self::LO && x[1] == Self::HI
    }

    /// `x << c` for `0 < c < N`, truncated to `N` bits.
    #[inline(always)]
    pub fn shl(x: W2, c: u32) -> W2 {
        if c < B {
            [(x[0] << c) & Self::LO, ((x[1] << c) | (x[0] >> (B - c))) & Self::HI]
        } else if c == B {
            [0, x[0] & Self::HI]
        } else {
            [0, (x[0] << (c - B)) & Self::HI]
        }
    }

    /// `x >> c` for `0 < c < N`.
    #[inline(always)]
    pub fn shr(x: W2, c: u32) -> W2 {
        if c < B {
            [((x[0] >> c) | (x[1] << (B - c))) & Self::LO, x[1] >> c]
        } else if c == B {
            [x[1], 0]
        } else {
            [x[1] >> (c - B), 0]
        }
    }

    /// Cyclic left rotation by `0 <= s < N`.
    #[inline(always)]
    pub fn rotl(x: W2, s: u32) -> W2 {
        if s == 0 {
            return x;
        }
        let a = Self::shl(x, s);
        let b = Self::shr(x, N - s);
        [a[0] | b[0], a[1] | b[1]]
    }

    /// Numeric `a < b`, high limb first.
    #[inline(always)]
    pub fn lt(a: W2, b: W2) -> bool {
        (a[1], a[0]) < (b[1], b[0])
    }

    /// All-ones when `x != 0`, else zero, without a jump.
    #[inline(always)]
    fn nz_mask(x: W2) -> u64 {
        let v = x[0] | x[1];
        barrier(0u64.wrapping_sub((v | v.wrapping_neg()) >> 63))
    }

    #[inline(always)]
    fn and(a: W2, b: W2) -> W2 {
        [a[0] & b[0], a[1] & b[1]]
    }

    #[inline(always)]
    fn sel(m: u64, a: W2, b: W2) -> W2 {
        [(a[0] & m) | (b[0] & !m), (a[1] & m) | (b[1] & !m)]
    }

    #[inline(always)]
    fn double_stage<const K: u32>(pow: &mut [W2; 8]) {
        if K == 0 || K >= Self::LEVELS {
            return;
        }
        let p = pow[K as usize - 1];
        pow[K as usize] = Self::and(p, Self::rotl(p, 1 << (K - 1)));
    }

    #[inline(always)]
    fn lift_stage<const K: u32>(pow: &[W2; 8], run: &mut W2, len: &mut u64) {
        if K >= Self::LEVELS {
            return;
        }
        let next = Self::and(pow[K as usize], Self::rotl(*run, 1 << K));
        let m = Self::nz_mask(next);
        *run = Self::sel(m, next, *run);
        *len += m & (1u64 << K);
    }

    /// Branch-free longest-zero-run tops of a nonconstant `x`, and the run
    /// length `Z`.
    #[inline(always)]
    pub fn longest_runs(x: W2) -> (W2, u32) {
        let z = [!x[0] & Self::LO, !x[1] & Self::HI];
        let mut pow = [[0u64; 2]; 8];
        pow[0] = z;
        Self::double_stage::<1>(&mut pow);
        Self::double_stage::<2>(&mut pow);
        Self::double_stage::<3>(&mut pow);
        Self::double_stage::<4>(&mut pow);
        Self::double_stage::<5>(&mut pow);
        Self::double_stage::<6>(&mut pow);
        let mut run = z;
        let mut len = 1u64;
        Self::lift_stage::<6>(&pow, &mut run, &mut len);
        Self::lift_stage::<5>(&pow, &mut run, &mut len);
        Self::lift_stage::<4>(&pow, &mut run, &mut len);
        Self::lift_stage::<3>(&pow, &mut run, &mut len);
        Self::lift_stage::<2>(&pow, &mut run, &mut len);
        Self::lift_stage::<1>(&pow, &mut run, &mut len);
        Self::lift_stage::<0>(&pow, &mut run, &mut len);
        (run, len as u32)
    }

    /// `lift_scan` with a count of the candidate rotations by a nonzero
    /// shift (the unit `canonical_rotation_steps` of the E-1 stage counts).
    #[inline(always)]
    pub fn lift_scan_c<const COUNT: bool>(x: W2, rotations: &mut u64) -> (W2, u32) {
        if Self::is_zero(x) || Self::is_mask(x) {
            return (x, 0);
        }
        let (run, _) = Self::longest_runs(x);
        let mut best = Self::MASK;
        let mut best_shift = 0u32;
        for limb in 0..2u32 {
            let mut rem = run[limb as usize];
            while rem != 0 {
                let p = limb * B + rem.trailing_zeros();
                rem &= rem - 1;
                let s = N - 1 - p;
                let v = Self::rotl(x, s);
                if COUNT && s != 0 {
                    *rotations += 1;
                }
                if Self::lt(v, best) || (v == best && s < best_shift) {
                    best = v;
                    best_shift = s;
                }
            }
        }
        (best, best_shift)
    }

    #[inline(always)]
    pub fn lift_scan(x: W2) -> (W2, u32) {
        let mut unused = 0u64;
        Self::lift_scan_c::<false>(x, &mut unused)
    }

    /// `lift_scan` on a `u128` holding an `N`-bit word.
    #[inline(always)]
    pub fn canonical_u128(v: u128) -> (u128, u32) {
        let (w, s) = Self::lift_scan(Self::from_u128(v));
        (Self::to_u128(w), s)
    }

    #[inline(always)]
    pub fn canonical_u128_counted(v: u128, rotations: &mut u64) -> (u128, u32) {
        let (w, s) = Self::lift_scan_c::<true>(Self::from_u128(v), rotations);
        (Self::to_u128(w), s)
    }

    /// Reference: all `N` rotations, first minimum (the pipeline's full scan).
    pub fn full_scan(x: W2) -> (W2, u32) {
        let mut best = x;
        let mut best_shift = 0;
        let mut cur = x;
        for s in 1..N {
            cur = Self::rotl(cur, 1);
            if Self::lt(cur, best) {
                best = cur;
                best_shift = s;
            }
        }
        (best, best_shift)
    }
}

/// The production geometry.
pub type F83 = L2<83, 64>;

/// Reference full scan on a `u128` word of `n` bits, written exactly as the
/// pipelines' `canonical` (one-bit rotations, first minimum).
pub fn full_scan_u128(v: u128, n: u32) -> (u128, u32) {
    let mask = if n == 128 { u128::MAX } else { (1u128 << n) - 1 };
    let mut best = v;
    let mut best_shift = 0;
    let mut current = v;
    for shift in 1..n {
        current = ((current << 1) | (current >> (n - 1))) & mask;
        if current < best {
            best = current;
            best_shift = shift;
        }
    }
    (best, best_shift)
}

macro_rules! dispatch {
    ($v:expr, $n:expr, $f:ident, $($deg:literal),*) => {
        match $n {
            $($deg => L2::<$deg, 64>::$f($v),)*
            _ => panic!("lift_scan: unsupported wide degree {}", $n),
        }
    };
}

/// `lift_scan` for the wide (`65 <= n <= 127`) binary degrees used by the
/// pipelines here; monomorphized per degree, so the rotations are constant.
#[inline(always)]
pub fn lift_scan_wide(v: u128, n: u32) -> (u128, u32) {
    if n == 83 {
        return F83::canonical_u128(v);
    }
    dispatch!(v, n, canonical_u128, 65, 67, 71, 73, 79, 89, 97, 101, 103, 107, 109, 113, 127)
}
