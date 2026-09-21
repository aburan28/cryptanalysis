//! **ML-DSA-65** (FIPS 204), speed-oriented.
//!
//! Byte-for-byte interchangeable with [`crate::pqc::ml_dsa`], which stays as
//! the readable reference and as the oracle these tests are written against.
//! The public key and secret key types are re-used from that module, so the
//! two implementations can be mixed freely: a key made here verifies there and
//! the other way round.
//!
//! # What is different from the reference
//!
//! The reference is not naive in shape — it already hoists everything that
//! does not depend on the signing candidate out of the rejection loop, and its
//! zeta table is a compile-time `const`. What it does pay for, everywhere, is
//! the way a single coefficient product is reduced:
//!
//!   * every butterfly and every pointwise product goes through
//!     `(a as i64 * b as i64) % q`, a 64-bit division-by-constant sequence, and
//!     every add/sub goes through `rem_euclid`;
//!   * the zeta table is in the plain domain, so no cheaper reduction is
//!     available to it;
//!   * `shake128`/`shake256` from `crate::hash::sha3` return a `Vec`, so each
//!     of the 30 `ExpandA` samples, each mask polynomial and each challenge
//!     allocates, and a rejection-sampler restart re-runs the whole sponge from
//!     the beginning with a doubled output length.
//!
//! This module replaces those three with, respectively: Montgomery arithmetic
//! over a `const` zeta table in the Montgomery domain (computed by a `const fn`
//! from ζ = 1753, not pasted in); the incremental sponge from
//! [`crate::pqc::fast::keccak`], so a rejection sampler squeezes one more block
//! instead of restarting; and fixed-size arrays throughout, with no heap
//! traffic in any hot path.
//!
//! Everything else — the algorithm, the sampling order, the packing, the
//! rejection conditions — is the reference's, deliberately, because the
//! requirement here is bit-identical output and not a second opinion on FIPS
//! 204.
//!
//! # Not constant time
//!
//! Neither is the reference. The rejection loops branch on secret-derived
//! data, `chknorm` branches on the coefficient it is checking, and nothing here
//! was written with a side channel in mind. Educational only; see
//! `SECURITY.md`.

use crate::pqc::fast::keccak::{Sponge, SHAKE128_RATE, SHAKE256_RATE};
use crate::pqc::ml_dsa::{MlDsaPublicKey, MlDsaSecretKey};

// ── Parameters (ML-DSA-65), identical to the reference ───────────────────────

const N: usize = 256;
const Q: i32 = 8_380_417;
const D: u32 = 13;
const TAU: usize = 49;
const LAMBDA: usize = 192;
const GAMMA1: i32 = 1 << 19;
const GAMMA2: i32 = (Q - 1) / 32;
const K: usize = 6;
const L: usize = 5;
const ETA: i32 = 4;
const BETA: i32 = (TAU as i32) * ETA; // 196
const OMEGA: usize = 55;

const SEED_BYTES: usize = 32;
const TR_BYTES: usize = 64;
const C_TILDE_BYTES: usize = LAMBDA / 4; // 48
const POLYT1_PACKED: usize = 320;
const POLYT0_PACKED: usize = 416;
const POLYETA_PACKED: usize = 128;
const POLYZ_PACKED: usize = 640;
const POLYW1_PACKED: usize = 128;

const PUBKEY_BYTES: usize = SEED_BYTES + K * POLYT1_PACKED; // 1952
const SECKEY_BYTES: usize = SEED_BYTES
    + SEED_BYTES
    + TR_BYTES
    + L * POLYETA_PACKED
    + K * POLYETA_PACKED
    + K * POLYT0_PACKED; // 4032
const SIG_BYTES: usize = C_TILDE_BYTES + L * POLYZ_PACKED + OMEGA + K; // 3309

// ── Montgomery arithmetic ────────────────────────────────────────────────────
//
// R = 2^32.  A value `a` is "in the Montgomery domain" when it is stored as
// `a·R mod q`.  The only thing kept there permanently is the zeta table; every
// polynomial coefficient in this file is a plain residue, and the R factors
// introduced by `montgomery_reduce` are cancelled by the `F` scaling at the end
// of the inverse NTT exactly as in the pq-crystals reference.

/// `q^{-1} mod 2^32`, as the two's-complement bit pattern.  `const`-asserted
/// below rather than trusted.
const QINV: i32 = 58_728_449;

/// Montgomery reduction: given `a` with `|a| < 2^31·q`, return `t ≡ a·R^{-1}
/// (mod q)` with `|t| < q`.
#[inline(always)]
fn montgomery_reduce(a: i64) -> i32 {
    let t = (a as i32).wrapping_mul(QINV) as i64;
    ((a - t * (Q as i64)) >> 32) as i32
}

/// Reduce to a representative with `|r| < 6283009`, congruent mod q.
#[inline(always)]
fn reduce32(a: i32) -> i32 {
    let t = (a + (1 << 22)) >> 23;
    a - t * Q
}

/// Add q to a negative input, mapping `(-q, q)` onto `[0, q)`.
#[inline(always)]
fn caddq(a: i32) -> i32 {
    a + ((a >> 31) & Q)
}

/// Canonical representative in `[0, q)` from anything congruent to it that
/// `reduce32` can handle.
#[inline(always)]
fn canon(a: i32) -> i32 {
    caddq(reduce32(a))
}

/// Centered representative, matching the reference's `to_centered` exactly:
/// input in `[0, q)`, output in `[-(q-1)/2, q/2]`.
#[inline(always)]
fn to_centered(a: i32) -> i32 {
    if a > Q / 2 {
        a - Q
    } else {
        a
    }
}

// ── Zeta table ───────────────────────────────────────────────────────────────

/// `ZETAS[k] = ζ^{brv₈(k)} · R mod± q` with ζ = 1753, the canonical primitive
/// 512-th root of unity of FIPS 204 §7.5, in the bit-reversed order the
/// Cooley-Tukey layers consume.
///
/// Computed here rather than pasted: a reader can check the recurrence, and it
/// is the same ζ and the same bit-reversal the reference module spells out.
/// Entry 0 is never read (the butterfly loop pre-increments `k`).
const ZETAS: [i32; N] = build_zetas();

const fn build_zetas() -> [i32; N] {
    let q = Q as i64;

    // R = 2^32 mod q, by doubling (no i128 in const arithmetic needed).
    let mut r: i64 = 1;
    let mut b = 0;
    while b < 32 {
        r = (r * 2) % q;
        b += 1;
    }

    // ζ^i mod q for i in 0..256.
    let mut pow = [0i64; N];
    pow[0] = 1;
    let mut i = 1;
    while i < N {
        pow[i] = (pow[i - 1] * 1753) % q;
        i += 1;
    }

    let mut out = [0i32; N];
    let mut k = 0;
    while k < N {
        // 8-bit bit reversal of k.
        let mut br = 0usize;
        let mut x = k;
        let mut c = 0;
        while c < 8 {
            br = (br << 1) | (x & 1);
            x >>= 1;
            c += 1;
        }
        // Both factors are < 2^23, so the product fits an i64 comfortably.
        let mut v = (pow[br] * r) % q;
        if v > q / 2 {
            v -= q;
        }
        out[k] = v as i32;
        k += 1;
    }
    out
}

/// `R² / 256 mod± q`: the scaling the inverse NTT applies at the end, which
/// simultaneously divides by n and puts the result back in the plain domain.
const F: i32 = build_f();

const fn build_f() -> i32 {
    let q = Q as i64;
    let mut r: i64 = 1;
    let mut b = 0;
    while b < 32 {
        r = (r * 2) % q;
        b += 1;
    }
    // 256^{-1} mod q, stated by the reference module and re-checked in `tests`.
    let n_inv: i64 = 8_347_681;
    let mut v = (((r * r) % q) * n_inv) % q;
    if v > q / 2 {
        v -= q;
    }
    v as i32
}

// Compile-time checks on the two constants that are easy to get wrong.
const _: () = {
    assert!(
        (Q as i64 * QINV as i64) as u32 == 1,
        "QINV is not the inverse of q mod 2^32"
    );
    assert!(F == 41978, "F is not R squared over 256 mod q");
};

// ── Polynomials ──────────────────────────────────────────────────────────────

type Poly = [i32; N];
type PolyVecL = [Poly; L];
type PolyVecK = [Poly; K];
/// `A` is K×L, stored row-major; 30 polynomials, 30 KiB, on the stack.
type Matrix = [[Poly; L]; K];

const ZERO_POLY: Poly = [0i32; N];

/// Forward NTT, in place, Cooley-Tukey decimation-in-time.
///
/// Input coefficients must satisfy `|a| < q`; output coefficients satisfy
/// `|a| < 9q`, which every consumer here either reduces or feeds to a
/// `montgomery_reduce` that tolerates it.
fn ntt(a: &mut Poly) {
    let mut k = 0usize;
    let mut len = 128usize;
    while len > 0 {
        let mut start = 0usize;
        while start < N {
            k += 1;
            let zeta = ZETAS[k] as i64;
            let mut j = start;
            while j < start + len {
                let t = montgomery_reduce(zeta * (a[j + len] as i64));
                a[j + len] = a[j] - t;
                a[j] += t;
                j += 1;
            }
            start += 2 * len;
        }
        len >>= 1;
    }
}

/// Inverse NTT, in place, Gentleman-Sande, with the `F` scaling folded into the
/// final pass.  Output coefficients satisfy `|a| < q`.
fn inv_ntt(a: &mut Poly) {
    let mut k = N;
    let mut len = 1usize;
    while len < N {
        let mut start = 0usize;
        while start < N {
            k -= 1;
            let zeta = -(ZETAS[k] as i64);
            let mut j = start;
            while j < start + len {
                let t = a[j];
                a[j] = t + a[j + len];
                a[j + len] = montgomery_reduce(zeta * ((t - a[j + len]) as i64));
                j += 1;
            }
            start += 2 * len;
        }
        len <<= 1;
    }
    for c in a.iter_mut() {
        *c = montgomery_reduce((F as i64) * (*c as i64));
    }
}

/// `c ← a ∘ b · R^{-1}`, the pointwise product with no exponentiation and no
/// division anywhere in it.
#[inline]
fn poly_pointwise(c: &mut Poly, a: &Poly, b: &Poly) {
    for i in 0..N {
        c[i] = montgomery_reduce((a[i] as i64) * (b[i] as i64));
    }
}

/// `c ← c + a ∘ b · R^{-1}`.  Summing L = 5 terms keeps `|c| < 5q < 2^26`.
#[inline]
fn poly_pointwise_acc(c: &mut Poly, a: &Poly, b: &Poly) {
    for i in 0..N {
        c[i] += montgomery_reduce((a[i] as i64) * (b[i] as i64));
    }
}

#[inline]
fn poly_reduce(a: &mut Poly) {
    for c in a.iter_mut() {
        *c = reduce32(*c);
    }
}

#[inline]
fn poly_caddq(a: &mut Poly) {
    for c in a.iter_mut() {
        *c = caddq(*c);
    }
}

/// `true` if some centered coefficient has absolute value `>= bound`.
/// Input must be canonical, in `[0, q)`.
#[inline]
fn chknorm(a: &Poly, bound: i32) -> bool {
    for &c in a.iter() {
        if to_centered(c).abs() >= bound {
            return true;
        }
    }
    false
}

/// `Â · v̂` for the K×L matrix, accumulating in the `R^{-1}` domain.
fn matrix_pointwise(out: &mut PolyVecK, a: &Matrix, v: &PolyVecL) {
    for i in 0..K {
        poly_pointwise(&mut out[i], &a[i][0], &v[0]);
        for j in 1..L {
            poly_pointwise_acc(&mut out[i], &a[i][j], &v[j]);
        }
    }
}

// ── Power2Round / Decompose / hints ──────────────────────────────────────────
//
// These are the FIPS 204 §7.4 routines in their branch-free arithmetic form.
// `decompose` in particular reproduces the reference's boundary case — where
// `r⁺ - r₀ = q - 1` collapses `r₁` to 0 and decrements `r₀` — through the
// `& 15` and the conditional `- q`, and `tests::decompose_matches_reference`
// checks that over the whole of `[0, q)` rather than on a sample.

/// `r = r₁·2^D + r₀` with `r₀ ∈ (-2^{D-1}, 2^{D-1}]`.  Input in `[0, q)`.
#[inline(always)]
fn power2_round(r: i32) -> (i32, i32) {
    let r1 = (r + (1 << (D - 1)) - 1) >> D;
    (r1, r - (r1 << D))
}

/// FIPS 204 Algorithm 36 with α = 2γ₂ = (q-1)/16.  Input in `[0, q)`.
#[inline(always)]
fn decompose(r: i32) -> (i32, i32) {
    let mut r1 = (r + 127) >> 7;
    r1 = (r1 * 1025 + (1 << 21)) >> 22;
    r1 &= 15;
    let mut r0 = r - r1 * 2 * GAMMA2;
    r0 -= (((Q - 1) / 2 - r0) >> 31) & Q;
    (r1, r0)
}

/// `decompose(r).0` without computing the low half.
#[inline(always)]
fn high_bits(r: i32) -> i32 {
    let mut r1 = (r + 127) >> 7;
    r1 = (r1 * 1025 + (1 << 21)) >> 22;
    r1 & 15
}

/// FIPS 204 Algorithm 40.  Input in `[0, q)`.
#[inline(always)]
fn use_hint(h: u8, r: i32) -> i32 {
    let (r1, r0) = decompose(r);
    if h == 0 {
        r1
    } else if r0 > 0 {
        (r1 + 1) & 15
    } else {
        (r1 - 1) & 15
    }
}

// ── Sampling ─────────────────────────────────────────────────────────────────
//
// Each of these streams from a single sponge.  The reference asks `shake*` for
// a fixed number of bytes and, if the rejection rate was unlucky, throws the
// result away and asks for twice as many — which re-derives the identical
// prefix, so the byte sequence consumed is the same one these functions walk
// incrementally.  That equivalence is why the outputs match bit for bit, and
// `tests::keygen_is_byte_identical_to_the_reference` and
// `tests::sign_is_byte_identical_to_the_reference` are what check it end to
// end: every one of these samplers feeds those two.

/// RejNTTPoly (FIPS 204 Algorithm 30): uniform in `[0, q)`, in the NTT domain.
///
/// Both 840 (the first request) and 168 (each top-up) are multiples of 3, so a
/// three-byte group never straddles a block boundary and no carry is needed.
fn rej_uniform(out: &mut Poly, rho: &[u8; SEED_BYTES], nonce: u16) {
    const NBLOCKS: usize = 5;
    let mut s = Sponge::<SHAKE128_RATE>::new();
    s.absorb(rho);
    s.absorb(&[(nonce & 0xff) as u8, (nonce >> 8) as u8]);
    s.finalize(0x1f);

    let mut buf = [0u8; NBLOCKS * SHAKE128_RATE];
    s.squeeze_blocks(&mut buf, NBLOCKS);
    let mut len = NBLOCKS * SHAKE128_RATE;
    let mut ctr = 0usize;
    let mut pos = 0usize;
    loop {
        while pos + 3 <= len && ctr < N {
            let t = (buf[pos] as u32)
                | ((buf[pos + 1] as u32) << 8)
                | (((buf[pos + 2] as u32) & 0x7f) << 16);
            pos += 3;
            if (t as i32) < Q {
                out[ctr] = t as i32;
                ctr += 1;
            }
        }
        if ctr == N {
            return;
        }
        s.squeeze_blocks(&mut buf, 1);
        len = SHAKE128_RATE;
        pos = 0;
    }
}

/// RejBoundedPoly (FIPS 204 Algorithm 31) for η = 4.
fn rej_eta(out: &mut Poly, seed: &[u8; 64], nonce: u16) {
    const NBLOCKS: usize = 3;
    let mut s = Sponge::<SHAKE256_RATE>::new();
    s.absorb(seed);
    s.absorb(&[(nonce & 0xff) as u8, (nonce >> 8) as u8]);
    s.finalize(0x1f);

    let mut buf = [0u8; NBLOCKS * SHAKE256_RATE];
    s.squeeze_blocks(&mut buf, NBLOCKS);
    let mut len = NBLOCKS * SHAKE256_RATE;
    let mut ctr = 0usize;
    let mut pos = 0usize;
    loop {
        while pos < len && ctr < N {
            let byte = buf[pos];
            pos += 1;
            let lo = byte & 0x0f;
            let hi = byte >> 4;
            if lo < 9 {
                out[ctr] = ETA - lo as i32;
                ctr += 1;
            }
            if hi < 9 && ctr < N {
                out[ctr] = ETA - hi as i32;
                ctr += 1;
            }
        }
        if ctr == N {
            return;
        }
        s.squeeze_blocks(&mut buf, 1);
        len = SHAKE256_RATE;
        pos = 0;
    }
}

/// ExpandA (FIPS 204 Algorithm 32).
fn expand_a(a: &mut Matrix, rho: &[u8; SEED_BYTES]) {
    for i in 0..K {
        for j in 0..L {
            rej_uniform(&mut a[i][j], rho, ((i as u16) << 8) | (j as u16));
        }
    }
}

/// ExpandS (FIPS 204 Algorithm 33).
fn expand_s(s1: &mut PolyVecL, s2: &mut PolyVecK, rho_prime: &[u8; 64]) {
    for i in 0..L {
        rej_eta(&mut s1[i], rho_prime, i as u16);
    }
    for i in 0..K {
        rej_eta(&mut s2[i], rho_prime, (L + i) as u16);
    }
}

/// One polynomial of ExpandMask (FIPS 204 Algorithm 34): coefficients in
/// `(-γ₁, γ₁]`, 20 bits each, 640 bytes of stream.
fn expand_mask_poly(out: &mut Poly, seed: &[u8; 64], nonce: u16) {
    let mut s = Sponge::<SHAKE256_RATE>::new();
    s.absorb(seed);
    s.absorb(&[(nonce & 0xff) as u8, (nonce >> 8) as u8]);
    s.finalize(0x1f);
    let mut buf = [0u8; POLYZ_PACKED];
    s.squeeze(&mut buf);

    for i in 0..(N / 2) {
        let b0 = buf[5 * i] as u32;
        let b1 = buf[5 * i + 1] as u32;
        let b2 = buf[5 * i + 2] as u32;
        let b3 = buf[5 * i + 3] as u32;
        let b4 = buf[5 * i + 4] as u32;
        let a = b0 | (b1 << 8) | ((b2 & 0x0f) << 16);
        let b = (b2 >> 4) | (b3 << 4) | (b4 << 12);
        out[2 * i] = GAMMA1 - a as i32;
        out[2 * i + 1] = GAMMA1 - b as i32;
    }
}

fn expand_mask(y: &mut PolyVecL, seed: &[u8; 64], kappa: u16) {
    for i in 0..L {
        expand_mask_poly(&mut y[i], seed, kappa + i as u16);
    }
}

/// SampleInBall (FIPS 204 Algorithm 29): τ = 49 coefficients in {-1, +1}.
fn sample_in_ball(c_tilde: &[u8]) -> Poly {
    let mut s = Sponge::<SHAKE256_RATE>::new();
    s.absorb(c_tilde);
    s.finalize(0x1f);
    let mut buf = [0u8; SHAKE256_RATE];
    s.squeeze_blocks(&mut buf, 1);

    let signs = u64::from_le_bytes([
        buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7],
    ]);
    let mut c = ZERO_POLY;
    let mut pos = 8usize;
    let mut sign_idx = 0u32;
    for i in (N - TAU)..N {
        loop {
            if pos == SHAKE256_RATE {
                s.squeeze_blocks(&mut buf, 1);
                pos = 0;
            }
            let j = buf[pos] as usize;
            pos += 1;
            if j <= i {
                c[i] = c[j];
                c[j] = 1 - 2 * ((signs >> sign_idx) & 1) as i32;
                sign_idx += 1;
                break;
            }
        }
    }
    c
}

// ── Packing ──────────────────────────────────────────────────────────────────

fn pack_t1(out: &mut [u8], p: &Poly) {
    for i in 0..(N / 4) {
        let a0 = p[4 * i] as u32 & 0x3ff;
        let a1 = p[4 * i + 1] as u32 & 0x3ff;
        let a2 = p[4 * i + 2] as u32 & 0x3ff;
        let a3 = p[4 * i + 3] as u32 & 0x3ff;
        out[5 * i] = a0 as u8;
        out[5 * i + 1] = ((a0 >> 8) | (a1 << 2)) as u8;
        out[5 * i + 2] = ((a1 >> 6) | (a2 << 4)) as u8;
        out[5 * i + 3] = ((a2 >> 4) | (a3 << 6)) as u8;
        out[5 * i + 4] = (a3 >> 2) as u8;
    }
}

fn unpack_t1(out: &mut Poly, b: &[u8]) {
    for i in 0..(N / 4) {
        let b0 = b[5 * i] as u32;
        let b1 = b[5 * i + 1] as u32;
        let b2 = b[5 * i + 2] as u32;
        let b3 = b[5 * i + 3] as u32;
        let b4 = b[5 * i + 4] as u32;
        out[4 * i] = (b0 | (b1 << 8)) as i32 & 0x3ff;
        out[4 * i + 1] = ((b1 >> 2) | (b2 << 6)) as i32 & 0x3ff;
        out[4 * i + 2] = ((b2 >> 4) | (b3 << 4)) as i32 & 0x3ff;
        out[4 * i + 3] = ((b3 >> 6) | (b4 << 2)) as i32 & 0x3ff;
    }
}

fn pack_t0(out: &mut [u8], p: &Poly) {
    let bias = 1i32 << (D - 1);
    for i in 0..(N / 8) {
        let t: [u32; 8] = core::array::from_fn(|j| ((bias - p[8 * i + j]) as u32) & 0x1fff);
        out[13 * i] = t[0] as u8;
        out[13 * i + 1] = ((t[0] >> 8) | (t[1] << 5)) as u8;
        out[13 * i + 2] = (t[1] >> 3) as u8;
        out[13 * i + 3] = ((t[1] >> 11) | (t[2] << 2)) as u8;
        out[13 * i + 4] = ((t[2] >> 6) | (t[3] << 7)) as u8;
        out[13 * i + 5] = (t[3] >> 1) as u8;
        out[13 * i + 6] = ((t[3] >> 9) | (t[4] << 4)) as u8;
        out[13 * i + 7] = (t[4] >> 4) as u8;
        out[13 * i + 8] = ((t[4] >> 12) | (t[5] << 1)) as u8;
        out[13 * i + 9] = ((t[5] >> 7) | (t[6] << 6)) as u8;
        out[13 * i + 10] = (t[6] >> 2) as u8;
        out[13 * i + 11] = ((t[6] >> 10) | (t[7] << 3)) as u8;
        out[13 * i + 12] = (t[7] >> 5) as u8;
    }
}

fn unpack_t0(out: &mut Poly, bytes: &[u8]) {
    let bias = 1i32 << (D - 1);
    for i in 0..(N / 8) {
        let b: [u32; 13] = core::array::from_fn(|j| bytes[13 * i + j] as u32);
        let mut t = [0u32; 8];
        t[0] = (b[0] | (b[1] << 8)) & 0x1fff;
        t[1] = ((b[1] >> 5) | (b[2] << 3) | (b[3] << 11)) & 0x1fff;
        t[2] = ((b[3] >> 2) | (b[4] << 6)) & 0x1fff;
        t[3] = ((b[4] >> 7) | (b[5] << 1) | (b[6] << 9)) & 0x1fff;
        t[4] = ((b[6] >> 4) | (b[7] << 4) | (b[8] << 12)) & 0x1fff;
        t[5] = ((b[8] >> 1) | (b[9] << 7)) & 0x1fff;
        t[6] = ((b[9] >> 6) | (b[10] << 2) | (b[11] << 10)) & 0x1fff;
        t[7] = ((b[11] >> 3) | (b[12] << 5)) & 0x1fff;
        for j in 0..8 {
            out[8 * i + j] = bias - t[j] as i32;
        }
    }
}

fn pack_eta(out: &mut [u8], p: &Poly) {
    for i in 0..(N / 2) {
        let a = (ETA - p[2 * i]) as u32 & 0x0f;
        let b = (ETA - p[2 * i + 1]) as u32 & 0x0f;
        out[i] = (a | (b << 4)) as u8;
    }
}

fn unpack_eta(out: &mut Poly, bytes: &[u8]) {
    for i in 0..(N / 2) {
        out[2 * i] = ETA - (bytes[i] & 0x0f) as i32;
        out[2 * i + 1] = ETA - (bytes[i] >> 4) as i32;
    }
}

/// `p` must be canonical, in `[0, q)`; the centered value is what gets packed.
fn pack_z(out: &mut [u8], p: &Poly) {
    for i in 0..(N / 2) {
        let a = (GAMMA1 - to_centered(p[2 * i])) as u32 & 0xfffff;
        let b = (GAMMA1 - to_centered(p[2 * i + 1])) as u32 & 0xfffff;
        out[5 * i] = a as u8;
        out[5 * i + 1] = (a >> 8) as u8;
        out[5 * i + 2] = ((a >> 16) | (b << 4)) as u8;
        out[5 * i + 3] = (b >> 4) as u8;
        out[5 * i + 4] = (b >> 12) as u8;
    }
}

fn unpack_z(out: &mut Poly, bytes: &[u8]) {
    for i in 0..(N / 2) {
        let b0 = bytes[5 * i] as u32;
        let b1 = bytes[5 * i + 1] as u32;
        let b2 = bytes[5 * i + 2] as u32;
        let b3 = bytes[5 * i + 3] as u32;
        let b4 = bytes[5 * i + 4] as u32;
        let a = b0 | (b1 << 8) | ((b2 & 0x0f) << 16);
        let b = (b2 >> 4) | (b3 << 4) | (b4 << 12);
        out[2 * i] = GAMMA1 - a as i32;
        out[2 * i + 1] = GAMMA1 - b as i32;
    }
}

fn pack_w1(out: &mut [u8], p: &Poly) {
    for i in 0..(N / 2) {
        out[i] = ((p[2 * i] & 0x0f) | ((p[2 * i + 1] & 0x0f) << 4)) as u8;
    }
}

// ── Key generation ───────────────────────────────────────────────────────────

/// ML-DSA-65 key generation from a 32-byte seed.  Deterministic in `seed`, and
/// byte-identical to [`crate::pqc::ml_dsa::ml_dsa_65_keygen`].
pub fn ml_dsa_65_keygen(seed: &[u8; SEED_BYTES]) -> (MlDsaPublicKey, MlDsaSecretKey) {
    // (ρ, ρ′, K) ← H(ξ ‖ k ‖ ℓ, 128)
    let mut h = [0u8; 128];
    {
        let mut s = Sponge::<SHAKE256_RATE>::new();
        s.absorb(seed);
        s.absorb(&[K as u8, L as u8]);
        s.finalize(0x1f);
        s.squeeze(&mut h);
    }
    let mut rho = [0u8; SEED_BYTES];
    rho.copy_from_slice(&h[0..32]);
    let mut rho_prime = [0u8; 64];
    rho_prime.copy_from_slice(&h[32..96]);
    let mut big_k = [0u8; SEED_BYTES];
    big_k.copy_from_slice(&h[96..128]);

    let mut a: Matrix = [[ZERO_POLY; L]; K];
    expand_a(&mut a, &rho);
    let mut s1: PolyVecL = [ZERO_POLY; L];
    let mut s2: PolyVecK = [ZERO_POLY; K];
    expand_s(&mut s1, &mut s2, &rho_prime);

    // t = A·s1 + s2
    let mut s1_hat = s1;
    for p in s1_hat.iter_mut() {
        ntt(p);
    }
    let mut t: PolyVecK = [ZERO_POLY; K];
    matrix_pointwise(&mut t, &a, &s1_hat);
    for i in 0..K {
        poly_reduce(&mut t[i]);
        inv_ntt(&mut t[i]);
        for j in 0..N {
            t[i][j] = canon(t[i][j] + s2[i][j]);
        }
    }

    // (t1, t0) ← Power2Round(t)
    let mut t1: PolyVecK = [ZERO_POLY; K];
    let mut t0: PolyVecK = [ZERO_POLY; K];
    for i in 0..K {
        for j in 0..N {
            let (h1, h0) = power2_round(t[i][j]);
            t1[i][j] = h1;
            t0[i][j] = h0;
        }
    }

    let mut pk = [0u8; PUBKEY_BYTES];
    pk[0..SEED_BYTES].copy_from_slice(&rho);
    for i in 0..K {
        let off = SEED_BYTES + i * POLYT1_PACKED;
        pack_t1(&mut pk[off..off + POLYT1_PACKED], &t1[i]);
    }

    let mut tr = [0u8; TR_BYTES];
    {
        let mut s = Sponge::<SHAKE256_RATE>::new();
        s.absorb(&pk);
        s.finalize(0x1f);
        s.squeeze(&mut tr);
    }

    let mut sk = [0u8; SECKEY_BYTES];
    sk[0..SEED_BYTES].copy_from_slice(&rho);
    sk[SEED_BYTES..2 * SEED_BYTES].copy_from_slice(&big_k);
    sk[2 * SEED_BYTES..2 * SEED_BYTES + TR_BYTES].copy_from_slice(&tr);
    let mut off = 2 * SEED_BYTES + TR_BYTES;
    for i in 0..L {
        pack_eta(&mut sk[off..off + POLYETA_PACKED], &s1[i]);
        off += POLYETA_PACKED;
    }
    for i in 0..K {
        pack_eta(&mut sk[off..off + POLYETA_PACKED], &s2[i]);
        off += POLYETA_PACKED;
    }
    for i in 0..K {
        pack_t0(&mut sk[off..off + POLYT0_PACKED], &t0[i]);
        off += POLYT0_PACKED;
    }

    (MlDsaPublicKey(pk.to_vec()), MlDsaSecretKey(sk.to_vec()))
}

// ── Signing ──────────────────────────────────────────────────────────────────

/// ML-DSA-65 signing (FIPS 204 Algorithm 7, the "internal" interface: the raw
/// message, no domain-separator prefix).  `rnd` is the hedging seed; pass
/// `[0u8; 32]` for deterministic signatures.
///
/// Byte-identical to [`crate::pqc::ml_dsa::ml_dsa_65_sign`].
pub fn ml_dsa_65_sign(sk: &MlDsaSecretKey, msg: &[u8], rnd: &[u8; SEED_BYTES]) -> Vec<u8> {
    let skb = &sk.0;
    let mut rho = [0u8; SEED_BYTES];
    rho.copy_from_slice(&skb[0..SEED_BYTES]);
    let mut big_k = [0u8; SEED_BYTES];
    big_k.copy_from_slice(&skb[SEED_BYTES..2 * SEED_BYTES]);
    let tr = &skb[2 * SEED_BYTES..2 * SEED_BYTES + TR_BYTES];

    let mut off = 2 * SEED_BYTES + TR_BYTES;
    let mut s1: PolyVecL = [ZERO_POLY; L];
    for p in s1.iter_mut() {
        unpack_eta(p, &skb[off..off + POLYETA_PACKED]);
        off += POLYETA_PACKED;
    }
    let mut s2: PolyVecK = [ZERO_POLY; K];
    for p in s2.iter_mut() {
        unpack_eta(p, &skb[off..off + POLYETA_PACKED]);
        off += POLYETA_PACKED;
    }
    let mut t0: PolyVecK = [ZERO_POLY; K];
    for p in t0.iter_mut() {
        unpack_t0(p, &skb[off..off + POLYT0_PACKED]);
        off += POLYT0_PACKED;
    }

    // μ = H(tr ‖ M, 64);  ρ″ = H(K ‖ rnd ‖ μ, 64)
    let mut mu = [0u8; 64];
    {
        let mut s = Sponge::<SHAKE256_RATE>::new();
        s.absorb(tr);
        s.absorb(msg);
        s.finalize(0x1f);
        s.squeeze(&mut mu);
    }
    let mut rho_pp = [0u8; 64];
    {
        let mut s = Sponge::<SHAKE256_RATE>::new();
        s.absorb(&big_k);
        s.absorb(rnd);
        s.absorb(&mu);
        s.finalize(0x1f);
        s.squeeze(&mut rho_pp);
    }

    // Everything below this line is independent of the candidate mask, so it is
    // computed once even though the loop may run several times.
    let mut a: Matrix = [[ZERO_POLY; L]; K];
    expand_a(&mut a, &rho);
    let mut s1_hat = s1;
    for p in s1_hat.iter_mut() {
        ntt(p);
    }
    let mut s2_hat = s2;
    for p in s2_hat.iter_mut() {
        ntt(p);
    }
    let mut t0_hat = t0;
    for p in t0_hat.iter_mut() {
        ntt(p);
    }

    // Scratch reused across rejection iterations; nothing here allocates.
    let mut y: PolyVecL = [ZERO_POLY; L];
    let mut y_hat: PolyVecL = [ZERO_POLY; L];
    let mut w: PolyVecK = [ZERO_POLY; K];
    let mut w1: PolyVecK = [ZERO_POLY; K];
    let mut tmp: PolyVecK = [ZERO_POLY; K];
    let mut z: PolyVecL = [ZERO_POLY; L];
    let mut w0c: PolyVecK = [ZERO_POLY; K];
    let mut ct0: PolyVecK = [ZERO_POLY; K];
    let mut hints = [[0u8; N]; K];
    let mut w1_packed = [0u8; POLYW1_PACKED];

    let mut kappa: u16 = 0;
    loop {
        expand_mask(&mut y, &rho_pp, kappa);
        kappa += L as u16;

        // w = A·y
        y_hat.copy_from_slice(&y);
        for p in y_hat.iter_mut() {
            ntt(p);
        }
        matrix_pointwise(&mut w, &a, &y_hat);
        for i in 0..K {
            poly_reduce(&mut w[i]);
            inv_ntt(&mut w[i]);
            poly_caddq(&mut w[i]);
            for j in 0..N {
                w1[i][j] = high_bits(w[i][j]);
            }
        }

        // c̃ = H(μ ‖ w1Encode(w1), λ/4)
        let mut c_tilde = [0u8; C_TILDE_BYTES];
        {
            let mut s = Sponge::<SHAKE256_RATE>::new();
            s.absorb(&mu);
            for i in 0..K {
                pack_w1(&mut w1_packed, &w1[i]);
                s.absorb(&w1_packed);
            }
            s.finalize(0x1f);
            s.squeeze(&mut c_tilde);
        }

        let mut c_hat = sample_in_ball(&c_tilde);
        ntt(&mut c_hat);

        // z = y + c·s1
        let mut z_ok = true;
        for i in 0..L {
            poly_pointwise(&mut z[i], &c_hat, &s1_hat[i]);
            inv_ntt(&mut z[i]);
            for j in 0..N {
                z[i][j] = canon(z[i][j] + y[i][j]);
            }
            if chknorm(&z[i], GAMMA1 - BETA) {
                z_ok = false;
                break;
            }
        }
        if !z_ok {
            continue;
        }

        // r0 = LowBits(w - c·s2)
        let mut r0_ok = true;
        for i in 0..K {
            poly_pointwise(&mut tmp[i], &c_hat, &s2_hat[i]);
            inv_ntt(&mut tmp[i]);
            for j in 0..N {
                w0c[i][j] = canon(w[i][j] - tmp[i][j]);
                if decompose(w0c[i][j]).1.abs() >= GAMMA2 - BETA {
                    r0_ok = false;
                }
            }
            if !r0_ok {
                break;
            }
        }
        if !r0_ok {
            continue;
        }

        // ‖c·t0‖_∞ < γ₂
        let mut ct0_ok = true;
        for i in 0..K {
            poly_pointwise(&mut ct0[i], &c_hat, &t0_hat[i]);
            inv_ntt(&mut ct0[i]);
            poly_caddq(&mut ct0[i]);
            if chknorm(&ct0[i], GAMMA2) {
                ct0_ok = false;
                break;
            }
        }
        if !ct0_ok {
            continue;
        }

        // h = MakeHint(-c·t0, w - c·s2 + c·t0).  Adding the two arguments gives
        // back `w0c`, so the literal FIPS test "do the high bits move?" is one
        // `high_bits` on each of the two polynomials and no modular inverse.
        let mut total = 0usize;
        for i in 0..K {
            for j in 0..N {
                let arg = canon(w0c[i][j] + ct0[i][j]);
                let h = (high_bits(arg) != high_bits(w0c[i][j])) as u8;
                hints[i][j] = h;
                total += h as usize;
            }
        }
        if total > OMEGA {
            continue;
        }

        let mut sig = vec![0u8; SIG_BYTES];
        sig[0..C_TILDE_BYTES].copy_from_slice(&c_tilde);
        for i in 0..L {
            let off = C_TILDE_BYTES + i * POLYZ_PACKED;
            pack_z(&mut sig[off..off + POLYZ_PACKED], &z[i]);
        }
        let hoff = C_TILDE_BYTES + L * POLYZ_PACKED;
        let mut kp = 0usize;
        for i in 0..K {
            for j in 0..N {
                if hints[i][j] == 1 {
                    sig[hoff + kp] = j as u8;
                    kp += 1;
                }
            }
            sig[hoff + OMEGA + i] = kp as u8;
        }
        return sig;
    }
}

// ── Verification ─────────────────────────────────────────────────────────────

/// ML-DSA-65 verification.  Accepts exactly what
/// [`crate::pqc::ml_dsa::ml_dsa_65_verify`] accepts, including the
/// HintBitUnpack canonicity rules.
pub fn ml_dsa_65_verify(pk: &MlDsaPublicKey, msg: &[u8], sig: &[u8]) -> bool {
    if pk.0.len() != PUBKEY_BYTES || sig.len() != SIG_BYTES {
        return false;
    }
    let mut rho = [0u8; SEED_BYTES];
    rho.copy_from_slice(&pk.0[0..SEED_BYTES]);
    let mut t1: PolyVecK = [ZERO_POLY; K];
    for i in 0..K {
        let off = SEED_BYTES + i * POLYT1_PACKED;
        unpack_t1(&mut t1[i], &pk.0[off..off + POLYT1_PACKED]);
    }

    let c_tilde = &sig[0..C_TILDE_BYTES];
    let mut z: PolyVecL = [ZERO_POLY; L];
    for i in 0..L {
        let off = C_TILDE_BYTES + i * POLYZ_PACKED;
        unpack_z(&mut z[i], &sig[off..off + POLYZ_PACKED]);
    }

    // HintBitUnpack (FIPS 204 Algorithm 21), including the canonicity rules:
    // running totals non-decreasing and bounded, positions strictly increasing
    // within a polynomial, unused slots zero.
    let hint_off = C_TILDE_BYTES + L * POLYZ_PACKED;
    let hb = &sig[hint_off..hint_off + OMEGA + K];
    let mut hints = [[0u8; N]; K];
    let mut kp = 0usize;
    for i in 0..K {
        let end = hb[OMEGA + i] as usize;
        if end < kp || end > OMEGA {
            return false;
        }
        for j in kp..end {
            if j > kp && hb[j] <= hb[j - 1] {
                return false;
            }
            hints[i][hb[j] as usize] = 1;
        }
        kp = end;
    }
    for j in kp..OMEGA {
        if hb[j] != 0 {
            return false;
        }
    }

    // ‖z‖_∞ < γ₁ - β.  `unpack_z` already yields the centered value, but it is
    // put through the canonical form first so the comparison is the same one
    // the reference makes.
    for i in 0..L {
        let mut zc = z[i];
        for c in zc.iter_mut() {
            *c = canon(*c);
        }
        if chknorm(&zc, GAMMA1 - BETA) {
            return false;
        }
    }

    // μ = H(H(pk, 64) ‖ M, 64)
    let mut tr = [0u8; TR_BYTES];
    {
        let mut s = Sponge::<SHAKE256_RATE>::new();
        s.absorb(&pk.0);
        s.finalize(0x1f);
        s.squeeze(&mut tr);
    }
    let mut mu = [0u8; 64];
    {
        let mut s = Sponge::<SHAKE256_RATE>::new();
        s.absorb(&tr);
        s.absorb(msg);
        s.finalize(0x1f);
        s.squeeze(&mut mu);
    }

    let mut c_hat = sample_in_ball(c_tilde);
    ntt(&mut c_hat);

    // A·z - c·t1·2^D
    let mut a: Matrix = [[ZERO_POLY; L]; K];
    expand_a(&mut a, &rho);
    let mut z_hat = z;
    for p in z_hat.iter_mut() {
        ntt(p);
    }
    let mut az: PolyVecK = [ZERO_POLY; K];
    matrix_pointwise(&mut az, &a, &z_hat);

    let mut ct1 = ZERO_POLY;
    let mut w1 = ZERO_POLY;
    let mut w1_packed = [0u8; POLYW1_PACKED];
    let mut s = Sponge::<SHAKE256_RATE>::new();
    s.absorb(&mu);
    for i in 0..K {
        // t1 is 10 bits, so t1 << 13 <= q - 1: no reduction needed here.
        let mut shifted = ZERO_POLY;
        for j in 0..N {
            shifted[j] = t1[i][j] << D;
        }
        ntt(&mut shifted);
        poly_pointwise(&mut ct1, &c_hat, &shifted);
        for j in 0..N {
            az[i][j] = reduce32(az[i][j] - ct1[j]);
        }
        inv_ntt(&mut az[i]);
        poly_caddq(&mut az[i]);
        for j in 0..N {
            w1[j] = use_hint(hints[i][j], az[i][j]);
        }
        pack_w1(&mut w1_packed, &w1);
        s.absorb(&w1_packed);
    }
    s.finalize(0x1f);
    let mut c_tilde_prime = [0u8; C_TILDE_BYTES];
    s.squeeze(&mut c_tilde_prime);

    c_tilde_prime.as_slice() == c_tilde
}

// ── Tests ────────────────────────────────────────────────────────────────────
//
// The contract of this module is not "produces valid ML-DSA signatures", it is
// "produces exactly the same bytes as `crate::pqc::ml_dsa`".  So the bulk of
// what follows is differential: the same input into both, and a byte
// comparison.  The reference in turn is pinned to the NIST ACVP vectors, which
// are re-run here directly against the fast code so that a shared mistake in
// both implementations could not pass unnoticed.

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pqc::ml_dsa as reference;

    // ── constants and arithmetic ─────────────────────────────────────────────

    #[test]
    fn montgomery_constants_are_what_they_claim() {
        // q·QINV ≡ 1 (mod 2^32).
        assert_eq!((Q as i64).wrapping_mul(QINV as i64) as u32, 1);
        // R = 2^32 mod q.
        let r = ((1u64 << 32) % Q as u64) as i64;
        // 256^{-1} mod q, the constant the reference module uses by name.
        assert_eq!((256i64 * 8_347_681) % Q as i64, 1);
        // F = R²/256 mod q, and the pq-crystals value for it.
        assert_eq!(F, 41978);
        assert_eq!(
            ((F as i64).rem_euclid(Q as i64) * 256) % Q as i64,
            (r * r) % Q as i64
        );
        // ZETAS[k] = ζ^{brv(k)}·R, spot-checked against the published table.
        assert_eq!(ZETAS[1], 25847);
        assert_eq!(ZETAS[2], -2608894);
        assert_eq!(ZETAS[255], 1976782);
    }

    #[test]
    fn zeta_table_is_the_bit_reversed_powers_of_1753() {
        // Recompute independently of the `const fn`, in plain arithmetic.
        let q = Q as i64;
        let r = ((1u64 << 32) % Q as u64) as i64;
        for k in 0..N {
            let br = (k as u8).reverse_bits() as u32;
            let mut v: i64 = 1;
            for _ in 0..br {
                v = v * 1753 % q;
            }
            let mut want = v * r % q;
            if want > q / 2 {
                want -= q;
            }
            assert_eq!(ZETAS[k] as i64, want, "zeta {k}");
        }
    }

    #[test]
    fn montgomery_reduce_is_multiplication_by_r_inverse() {
        let r_inv = {
            // R^{-1} mod q by Fermat: R^(q-2).
            let mut acc: i64 = 1;
            let mut base = ((1u64 << 32) % Q as u64) as i64;
            let mut e = Q as i64 - 2;
            while e > 0 {
                if e & 1 == 1 {
                    acc = acc * base % Q as i64;
                }
                base = base * base % Q as i64;
                e >>= 1;
            }
            acc
        };
        for a in [
            0i64,
            1,
            12345,
            -999,
            4_190_208,
            -8_380_416,
            1 << 40,
            -(1 << 40),
        ] {
            let got = montgomery_reduce(a) as i64;
            assert!(got.abs() < Q as i64);
            assert_eq!(
                got.rem_euclid(Q as i64),
                (a * r_inv).rem_euclid(Q as i64),
                "a={a}"
            );
        }
    }

    #[test]
    fn decompose_matches_the_literal_fips_definition_everywhere() {
        // The branch-free `decompose` against FIPS 204 Algorithm 36 written out
        // exactly as the spec states it, over the whole of [0, q).  This is the
        // routine whose boundary case (r⁺ - r₀ = q - 1) a random test would
        // essentially never reach.
        let two_g2 = 2 * GAMMA2;
        for r in 0..Q {
            let mut r0 = r % two_g2;
            if r0 > GAMMA2 {
                r0 -= two_g2;
            }
            let (want1, want0) = if r - r0 == Q - 1 {
                (0, r0 - 1)
            } else {
                ((r - r0) / two_g2, r0)
            };
            let (got1, got0) = decompose(r);
            assert_eq!((got1, got0), (want1, want0), "decompose({r})");
            assert_eq!(high_bits(r), want1, "high_bits({r})");
        }
    }

    #[test]
    fn power2_round_reconstructs() {
        for r in (0..Q).step_by(1021) {
            let (r1, r0) = power2_round(r);
            assert_eq!(r1 * (1 << D) + r0, r);
            assert!(r0 > -(1 << (D - 1)) && r0 <= (1 << (D - 1)));
        }
    }

    #[test]
    fn inverse_ntt_undoes_the_forward_ntt_up_to_the_montgomery_factor() {
        // `inv_ntt` is the pq-crystals `invntt_tomont`: it scales by R as well
        // as by n^{-1}, so on its own it is *not* the inverse of `ntt`. The
        // extra R is what cancels the R^{-1} that `poly_pointwise` introduces,
        // which is why every real use of it has a pointwise multiply in
        // between (and why `ntt_multiplication_matches_schoolbook` below is the
        // test that pins the composition callers actually rely on). Stating the
        // factor here rather than hiding it keeps the convention checkable.
        let r = ((1u64 << 32) % Q as u64) as i64;
        let mut p: Poly = [0; N];
        for (i, c) in p.iter_mut().enumerate() {
            *c = ((i as i64 * 12345 + 7) % Q as i64) as i32;
        }
        let original = p;
        ntt(&mut p);
        inv_ntt(&mut p);
        for i in 0..N {
            let want = ((original[i] as i64 * r) % Q as i64) as i32;
            assert_eq!(caddq(reduce32(p[i])), want, "coefficient {i}");
        }
    }

    #[test]
    fn ntt_multiplication_matches_schoolbook() {
        let mut a: Poly = [0; N];
        let mut b: Poly = [0; N];
        for i in 0..16 {
            a[i] = i as i32 * 7 + 3;
            b[i] = i as i32 * 5 + 11;
        }
        let mut expect: Poly = [0; N];
        for i in 0..N {
            for j in 0..N {
                let idx = (i + j) % N;
                let sign: i64 = if i + j >= N { -1 } else { 1 };
                let term = sign * (a[i] as i64) * (b[j] as i64);
                expect[idx] = ((expect[idx] as i64 + term).rem_euclid(Q as i64)) as i32;
            }
        }
        let (mut ah, mut bh) = (a, b);
        ntt(&mut ah);
        ntt(&mut bh);
        let mut c: Poly = [0; N];
        poly_pointwise(&mut c, &ah, &bh);
        inv_ntt(&mut c);
        for i in 0..N {
            assert_eq!(caddq(reduce32(c[i])), expect[i], "coefficient {i}");
        }
    }

    // ── differential against the reference implementation ────────────────────

    /// A seed that varies in every byte, so the 20+ cases are not near-copies.
    fn seed_of(i: u8) -> [u8; SEED_BYTES] {
        let mut s = [0u8; SEED_BYTES];
        for (j, b) in s.iter_mut().enumerate() {
            *b = i.wrapping_mul(37).wrapping_add(j as u8).wrapping_mul(29) ^ i;
        }
        s
    }

    fn rnd_of(i: u8) -> [u8; SEED_BYTES] {
        let mut s = [0u8; SEED_BYTES];
        for (j, b) in s.iter_mut().enumerate() {
            *b = (i ^ 0xa5).wrapping_add((j as u8).wrapping_mul(17));
        }
        s
    }

    /// Messages covering the empty case, sub-block, exactly one SHAKE256 block
    /// (136 bytes) and several blocks.
    fn message_of(i: u8) -> Vec<u8> {
        match i % 5 {
            0 => Vec::new(),
            1 => vec![i; 1],
            2 => b"the quick brown fox jumps over the lazy dog".to_vec(),
            3 => (0..136u16).map(|j| (j as u8) ^ i).collect(),
            _ => (0..500u16)
                .map(|j| (j as u8).wrapping_mul(11) ^ i)
                .collect(),
        }
    }

    #[test]
    fn keygen_is_byte_identical_to_the_reference() {
        for i in 0..24u8 {
            let seed = seed_of(i);
            let (fpk, fsk) = ml_dsa_65_keygen(&seed);
            let (rpk, rsk) = reference::ml_dsa_65_keygen(&seed);
            assert_eq!(fpk.0, rpk.0, "public key differs, seed index {i}");
            assert_eq!(fsk.0, rsk.0, "secret key differs, seed index {i}");
            assert_eq!(fpk.0.len(), PUBKEY_BYTES);
            assert_eq!(fsk.0.len(), SECKEY_BYTES);
        }
    }

    #[test]
    fn sign_is_byte_identical_to_the_reference() {
        for i in 0..24u8 {
            let seed = seed_of(i);
            let rnd = rnd_of(i);
            let msg = message_of(i);
            let (_, sk) = ml_dsa_65_keygen(&seed);
            let fsig = ml_dsa_65_sign(&sk, &msg, &rnd);
            let rsig = reference::ml_dsa_65_sign(&sk, &msg, &rnd);
            assert_eq!(
                fsig,
                rsig,
                "signature differs at index {i}: seed {}, rnd {}, message length {}",
                hex::encode(seed),
                hex::encode(rnd),
                msg.len()
            );
            assert_eq!(fsig.len(), SIG_BYTES);
        }
    }

    #[test]
    fn signing_is_identical_for_the_empty_and_multi_block_messages_under_both_hedges() {
        // Called out separately because they are the two cases the padding and
        // the sponge-continuation logic are most likely to get wrong.
        for (i, msg) in [Vec::new(), vec![0x5au8; 1000]].into_iter().enumerate() {
            for rnd in [[0u8; SEED_BYTES], [0xffu8; SEED_BYTES]] {
                let seed = seed_of(200 + i as u8);
                let (_, sk) = ml_dsa_65_keygen(&seed);
                assert_eq!(
                    ml_dsa_65_sign(&sk, &msg, &rnd),
                    reference::ml_dsa_65_sign(&sk, &msg, &rnd),
                    "message length {}, rnd {}",
                    msg.len(),
                    rnd[0]
                );
            }
        }
    }

    #[test]
    fn signatures_cross_verify_in_both_directions() {
        for i in 0..24u8 {
            let seed = seed_of(i);
            let rnd = rnd_of(i);
            let msg = message_of(i);
            let (fpk, fsk) = ml_dsa_65_keygen(&seed);
            let (rpk, rsk) = reference::ml_dsa_65_keygen(&seed);

            let fsig = ml_dsa_65_sign(&fsk, &msg, &rnd);
            let rsig = reference::ml_dsa_65_sign(&rsk, &msg, &rnd);

            assert!(ml_dsa_65_verify(&fpk, &msg, &fsig), "fast/fast, index {i}");
            assert!(
                reference::ml_dsa_65_verify(&rpk, &msg, &fsig),
                "reference verifier on fast signature, index {i}"
            );
            assert!(
                ml_dsa_65_verify(&fpk, &msg, &rsig),
                "fast verifier on reference signature, index {i}"
            );
            // A different message under the same key must not verify.
            let mut other = msg.clone();
            other.push(0x01);
            assert!(
                !ml_dsa_65_verify(&fpk, &other, &fsig),
                "wrong message, index {i}"
            );
        }
    }

    #[test]
    fn a_flipped_bit_is_rejected() {
        let seed = seed_of(3);
        let rnd = rnd_of(3);
        let msg = b"a message that will be signed and then quietly corrupted".to_vec();
        let (pk, sk) = ml_dsa_65_keygen(&seed);
        let sig = ml_dsa_65_sign(&sk, &msg, &rnd);
        assert!(ml_dsa_65_verify(&pk, &msg, &sig));

        // Positions spread over all three regions of the encoding: the
        // commitment hash, the packed z vector (start, middle, end) and the
        // hint block (positions and the running counts).
        let z_start = C_TILDE_BYTES;
        let z_end = C_TILDE_BYTES + L * POLYZ_PACKED;
        let hint_start = z_end;
        let byte_positions = [
            0,
            1,
            C_TILDE_BYTES - 1,
            z_start,
            z_start + 1,
            z_start + POLYZ_PACKED,
            (z_start + z_end) / 2,
            z_end - 1,
            hint_start,
            hint_start + OMEGA - 1,
            hint_start + OMEGA,
            SIG_BYTES - 1,
        ];
        for &pos in &byte_positions {
            for bit in [0u32, 3, 7] {
                let mut bad = sig.clone();
                bad[pos] ^= 1 << bit;
                if bad == sig {
                    continue;
                }
                assert!(
                    !ml_dsa_65_verify(&pk, &msg, &bad),
                    "byte {pos} bit {bit} still verified"
                );
            }
        }

        // Length errors, which the reference also rejects rather than panics on.
        assert!(!ml_dsa_65_verify(&pk, &msg, &sig[..SIG_BYTES - 1]));
        let mut longer = sig.clone();
        longer.push(0);
        assert!(!ml_dsa_65_verify(&pk, &msg, &longer));
        assert!(!ml_dsa_65_verify(
            &MlDsaPublicKey(pk.0[..10].to_vec()),
            &msg,
            &sig
        ));
    }

    #[test]
    fn verifier_agrees_with_the_reference_on_corrupted_input() {
        // Not just "rejects", but "rejects exactly the same things": the two
        // verifiers are supposed to be interchangeable on bad input too.
        let seed = seed_of(11);
        let rnd = rnd_of(11);
        let msg = message_of(4);
        let (pk, sk) = ml_dsa_65_keygen(&seed);
        let sig = ml_dsa_65_sign(&sk, &msg, &rnd);
        let mut state = 0x243f_6a88_85a3_08d3u64;
        for _ in 0..64 {
            state = state
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            let pos = (state >> 11) as usize % SIG_BYTES;
            let bit = (state >> 3) as u32 % 8;
            let mut bad = sig.clone();
            bad[pos] ^= 1 << bit;
            assert_eq!(
                ml_dsa_65_verify(&pk, &msg, &bad),
                reference::ml_dsa_65_verify(&pk, &msg, &bad),
                "verifiers disagree on byte {pos} bit {bit}"
            );
        }
    }

    #[test]
    fn sizes_match_the_spec() {
        assert_eq!(PUBKEY_BYTES, 1952);
        assert_eq!(SECKEY_BYTES, 4032);
        assert_eq!(SIG_BYTES, 3309);
    }

    // ── Official NIST ACVP known-answer tests (final FIPS 204) ───────────────
    //
    // The same vectors the reference module carries, from the usnistgov
    // ACVP-Server gen-val JSON files, run against the fast code directly.  Long
    // outputs are compared by SHA3-256 digest to keep the source readable;
    // inputs are embedded in full.  They are duplicated here rather than shared
    // because the reference's copies live in its own private `#[cfg(test)]`
    // module — and a duplicated vector is the point: both implementations are
    // pinned to NIST independently, so a shared bug has nowhere to hide.

    // ML-DSA-65 KeyGen (NIST ACVP ML-DSA-keyGen-FIPS204, tgId=2 tcId=26)
    const KAT_KG_SEED: &str = "1bd67dc782b2958e189e315c040dd1f64c8ab232a6a170e1a7a52c33f10851b1";
    const KAT_KG_PK_SHA3: &str = "aaa07f586d78b67b964de8def0df7f34a6c160f110ba701a7c1a28b9ba2f8ba6";
    const KAT_KG_SK_SHA3: &str = "0ad8c5371e61cd026e0dad72dfc3740840187e2094c27f915eb5cef8fd19126e";
    // ML-DSA-65 SigGen, deterministic, internal interface (ACVP tgId=10 tcId=139)
    const KAT_SIG_SK: &str = "7404a35777fae6cf45286b069cf3fbd640f4006282d3071b4182fb89f8265405c5bb9f4c3b7cccef4edfbfb1a4a4326cef627e6748628ca0541147014d559c7f30781eca6d4fcabdf1d0d147f593a55c703b98a4f21c4d1a6d044486b81cc657461553dd8c7a998539b1fc3aa334b5f63e500ec4dcd017500de4e75d5bbda6ea47100045201577518686008070128156667330420042080026351413380876654514537284576735336821534831802147240812558105885828318784386336523148884688030477658023003502076272715168446863145644671838420722468366275252465543148238031372814476668680708321477765342644411353563362887158733458221315817028015247461488235716518582185151472272226115151542348044381607714150062813626310025847023728870102624466146477778487677757853227643644153465337544126012110014314676608380055201032755542103762847332106478836645663808021647705348185528536767721412641747537381312257713776114332462725536865575115857433042521482578274882766656610424733147254375622733231460511686373014233071117835625363308828862021778837120831002767110104401501812322871630627746440703760474107183168101708676158376378121247278062666682726372887450450516320538045874027113114443060580423363311841835554345607515303762033565440207763351722210775070525010188067762640457417028248012661615630188842021414241822605615400716112526682180426111485531371603507081315831782686083336467773156517300654477824668568410865332452575533847540165646724437134244544735451021073713550050205461528402555716834843141022780732300621778666662068227463018325560330426765028241364873081623854857177162248726774307856736526435003530136286370146725848804405765372818687825470370160456800650252048102585846724343682662662536821637810008414224527823220565212115658211386314540858837750560840188858462520481182602383175317551712836154820737478134540672281140750252503487616651285063045687745638570864134484046205737508226104640043347050666408627153155872725351113382018005356220484047145238014766772510782755454772803472884067586537282104542368681862860315352652707821182444444710453458234461417526278705788175302807027265771071245605313362230188643000458226368003746131045242253026071680714405241563343818415328173701678673806765345217712572718040000127614010481567044548005707455804835685241136800037514288630506840785235608608175688370340313753387851800353174088134443242747274503144033876466620462560015852083105841143712487405180160537402474710034641156404546414624682728366620677422744615366454868525527218462580341363637474637401658760336884006384214436577385842164327180158840136408113564227737383636510850842366143434671620130025652167501432870705463536356205436647500217711502621366647255310314685801230668572212252588223625487006785585684150815566113527676754438248450185748065828035347627638584462307562354521312182805152878066434416664117507011421040186044436860558840562771254806468527230363236302614275524067580578572010385720263183341255324543363181188646727564448130022385877807780233031170733225337041531134241013412280080586151144052571612283370526051021253471773356663276076725711340653544515781033728563321101115811551543000467253042882665864087782154340788357374115113185b5f193ea651c4b2b831e2d64898ba95b4a939cf8a3bcbce24af71d839834201da87206583acf0880ffc65d44db72e5a9d6eb8641d430bc1d7bec251c8d53e39e7c0348a091a33d25d2b194d1505efd61e9da2391b1ca672101ef93a4c3453662d3ba503f90819aa3fa0bb420a091fa047f6d92b291de2a3b8c0f0fe4ba7f74cd749c28f972c7db939ca1855ca431b65a0bde23ddbbef76a9848eb59704dfa73eb24b700ba1dbfc9d86c651c7068d6bb2dcd1a73d25581f027a2afb4e26433d66b658c8d1aab480a05ce07d772f7c1fad2ddf28969cf447d7efd16ddb85a4018c1e2057ad8a3af7943053f30363f530d16230883e07734f78630dab4f17201a52b161e36eb11eec0ad1de1cf37dc28d19cecee85ad5d0208c3a4a4e94ba56f554adf8076559293ab30ad62d9fc976451b0dbde14bb989d26f52d61de17cb50f5443ebf5b08fe815370c6f5809c45c160c96c5a4f1c8bc87942584b393453cee13ab81986515a8aef6ff81c9174c2004e115e4c24bf1b156f97402cb5b573dd030cc43752a22b249a0f7a241cdb379821b3c5a5729e2eeab5fe874e940d8eb38b305c92fa0905e5ede2e3d060378f965f540c0029f15de3d72616752b6b8a719a072badb7414abdfa96a866b5d7fa36c5619f91c9922044008b87b5abcb2331aa69c900b05701f875f917e4778b3fc4464098b545cf4b1b608d717dc4c60d6df429ee49027a66b0abf3085b8e9e2fd6008d494c091a14703dcd3f3a579d6bf7c6c686f5aab66c5da721c0013b67dba0bf85f6486c891a3c12cfc23470df147b60a8471096f70d777cbf5c59530804391f6678a2d6b64badb5850d502e5db945b13065deff491eb33429d55c286f7024096bf2380e708c901fc2034634ecd5e322b2d72587bb2d5ee46d761e66722e14e4dc94c6eba8a216f7b4df364fa41d2f166f2bc0bc9367718d837e92108960519910d172d1200ed941121c8ee70a180867d67c9cf648099c51780f56bb2428ef579ab547b36929fb9e461452da85030db43fc1fbce788adf905fc27dceff80e9c7f62ab270cfaa74def9cb7ef95040f1684ccf88d174955fbae8ef50b0631387fe3b2963d92493449fa4d464bed6b8ce1022ed3d77988572fc39307eaaeb34a0be45ae161430c654c5a6536e1d265f9c1e660583bc5d2a5d2df06e8cdaa995f0f9e71e138b4d147f2a96edb0b85d946a4793317ba48e789ec0ae1030fe7f522208ddfef542f5b2fe7cf36593b8d9af2b7b3721b9f82a6f54eb5ca6700a811fe0bd53bca2dc58aa34770e108c19eec4b1bd5ef29b0b73d71cd025803efeaabad990f7e6b92c4555d77828351cbdf8f8de2b8e62e6f3c4d8515762a1050ec1219e8501a56e6831213d8c2413b08186b7dd67db3ab66f5a0466f168ac5e195e264684034f5cfca9e03d31b28dd5ecbc91c5f80b68b4fa570a35e353f95a4e64c96dc5e7a3e5c39da1e35b204efe8f84936de28967158ca9039c288c58495c1464b8c109b02fe06cf40aa802b35a804551c01adf919ad1530a490d827f7528dad358b11d2c3887ac6d101ae3f38138b27d65827039f6b41e9da77c74146cf897a204b67eb23f1d9c4af99097d60511d42c6e57bb157c09508a3658b76a49aee254c6d925677eb9be02fdb54e55c98de13d8b3573dd9a34ac2e7b9d9495635531d649e74f57d32ad88081f2307056e709335ee4dfc421cc9e21fbf161bc62dc0df7f40339f70b93ce98942b67795844f6f6834c3b3650cfb859e1fce54d014cc1310160ea15e7c488d0b3e7d5b919b70423373f1bf590ed3076fe933d6f34c46e95b353052f74a36b7bbae447e27138c8bd6a231c8036047cc68d2c95ab399077140d49086a3a2524a8c22d2a039b5a28fec5928827241b292d41bf4b348deec6995408e4856af6cd48fade4d40e7cd5844a03b6ad61a2f4581e44515fffa8d00aa55288bccb514837ac858ee443108187a473e78edbd78f532392d6abfddc275a8cca4470ac1895012724477a5eabc697ab863049bb3ca06df0aad029a0b40fb4a0be4a555ad0b6eaa63b16e656a1ab515728b29d64907914358abdec015d5b32b592afdcb928b3aef0449ab6b146cdb2b68421d36b528a1a65bd519fc015a4105f3fe6d07b7a1d4b590fdd134d8ad2b7e2adcad2cee8fc704f8e9bf7d37d054787f7d8e4524cac5cb444ebb7fc130f362e853ebbf949e43b2779d80a588a736fedb82a12da5f4d38c8a7cb07226ab60889d0ae720ea4464c512ab1ecd62e58d5ca768c16d091feb44e8c3df628152bd0217d4ae2648704095138f65cd502ba40c7118fe7062a9aec6c0e53d6d999fa24f2d7eadf2a11b87277f158767716148a7f9ddcfa56bd5adc81af2d9aed0dc7c77d0ff2041783ab8d9b6398d5c29ee186d267a7cbc1dd3ade7c1624427cb926958b5bb14fc119299332bd8613f2af8969f57212ebc7316e8dafae087cf112af2cf3d78262af9dda2bae45e13df81f1fa04fc5a27fd09f15a548eeda5d1f4f19fa9a27ec17f574eed25a0d8c6198284d16ebdc60d355dae37bdcdb01e7acab874ed10668db9cabb4de25e4535b75f7b5311857e7dfe45f8dccb907f7c62835f9da1cc27d05ea93fa56cd05ecf8efe719832c311c9d2d1225991d874db7ea495681e96414a37ce038df3c41dfb8c172f0443d9b2c395b189efdf85dec1390d67694ed9b5e0a50bcce0f6e885fccca09bb08fa22803f8562d29a8a247a1615dafadc0befa7ee6eecb4a4e0cf145801ab0e693f056dbadbf296a212018528e23d198d6cca85c9e56e0f6d781d6b4670c548a997885353634aae8f8939d5290086455818d56c1015f97e9423ebf2e69d3ea1525a4b908acfa0a21d676c53528e046259e965dd171d999d183923f044aa979e0a19055b8c8f5fea21758a7540bf2af68a291ef74698df89a10b1388325fc6913f5994f6618b18ae91c7e723e3c4c54a1454b5a9cf669d1c5cfda94b56777aa4e547bbef429734343b35acf9846652ce5a33f6c25523232b6011103372fae09f87216857de6a04589475e767e838df07a39347dd310adc516e78595180dd80ad0be1ab03afafc1fd26e53fdbefe02e3aed1d142976a7aee36f77f6823522a27514dfd1d90ce89053022b2dc8e44303a366595bda176a1dfca0e6c1446646a851347f72706f99c039f539e4e9b36a1d5c4ecb716d4f7f3025a179717dacd2774d8f43be39ecb4395d96ed222790e24b24bcbc38ed344f1081fabbaf74693ec70b03a89d11c8719ec184045a511898b5b3a74cec8b207bd36726b4b7471c5a73a26c03b15ce36bf1bca6464dedea7f332bbde189b46003d71d1f576eb2a2bb78a722765fc920298ecfad064e4a5fc46ee598a2099b2bffb2e0522f459f9d04cafe4f56f2ebf90451c5ace062c27b8895a2229b12f2bd33151294044ae33f40afe9653792001ac66770a9a069cdec86360d00e8573b6847f43693831e04b7df3ccf7f94a9a250279ad56d72e4b33d244e0298477f8b";
    const KAT_SIG_MSG: &str = "71";
    const KAT_SIG_SHA3: &str = "69ed14277b5b79f45fb72d11506ee8f4bfa52af50d07943264c9b419ccb03a59";
    // ML-DSA-65 SigVer (ACVP tgId=10 tcId=141: valid - signature should verify successfully)
    const KAT_SV_VALID_PK: &str = "ca69f918c81ce9fa9eb9ee09228bd265bd1f2ad63f48522263bb732a68aa8aa4c7b2ed29792a06c05245703137841ac2448f290eab350ee95172f0caa5fc8127e90c92d1a1b51ab41f6b788f7425f46936a60aa3d3a16f7930da5625ce3529985f32d7d3d4ec15cb9adca9c3592d93b89515728a58ecba668c2a845bf9cbcbdcc6906450bf8efee66a31a7b2c7ce2e36ec472d6d1b97d8e6bf44a6a74f75d6adb584ebda92a7900e2e75f4389b4da185fd789628542ebb120b231ad3bb954e952c23c75c88254182ebf78f0a810f92411773b4c1fad6bc98a634c21f68875ce4650bd8c23a24c339177b048ced2c7b5613ddf819df1ea6e589a791dbe3c99db3c5a83560aa365966d3da3cdc402bf1b68535c823e34ce83f2de4921ced5156b2fdce6fcf846aebccdd86f41d83df248fe32577b0e976efebb74578e8239116f9d2d7b8c79e9b3f12951e11cfef70fc1b8dc02265aa860d0df5174667de96972b80e70c88c332c26139037eb45dd1b16d6565c511c1b67b27fdd37913482899feaef8a55e0af0a0c3fadfed3fac4c4714f166ca476f15dba0f9fa60bac09f793da0e7de6bb3f682f84253d30a51dcdb2c83a93cd1491bd708d27ab51437dc0fbf48b0102e8fcd8b96bc7bf9f642b4ea5d2b15ff63e0b06e71003dddfd3cf4ea66248a71acf39f2cc0d6db58b76d0e5a6f173a7bf811ab670d6206fff9b242ec48316e5c85ef2e0229c4ec1df16eeaa467f1f4dbe0adf2ef3c72a384e1eba7256a08555af0cd23bbc28230414f3dbf96ce148fb398bac9512e9e83a77dcbd608e957ea9a24236a3df0ad22d5ab38f136cb3e91f3929db45b88c80a9a620290e5ae249af5b3095c48518d3b5ca26e59355816c641276f7827961b5462301a7a3daeda872eb311fdebf9617fb5b5cc397234be680a21e9b402d20ea4936c4409658669beb91711107fd5cd2235f822cfe4d7e1e0d38c36f96c9bf75e709a58902b8bf5f2c96cbedeab05bb97d27891bcacb3ab474704ba3675cbdc70daa19a275b7498afbc28a4f81c10ac79a9c2e0335b981cffe839684d352564820c3cc7fb9fb802eab31448930c90dd34d9567090b3861e6a35a4ee2b74e0137e2a0b1b11a118720726e46b1c3b9ef87eb4d1f740fc96c302f3a62145b37a291bffc531bbaaf7d45f81b6e5fe516e305ccf63e9e85a28740b56a1cef65230fd0b5686ebda445a73b41b5a01b35dc460b461a7db4d25cb69f8995f8742ca3933aacd9eceb6c42e3d7646c7f9ead58eb6893bf87430e02376666783dc0c3c33f600ec86885eccba6569442d52432ae779b7e20f2d5893ff19c7d216548f0fff22c01c5c28ff77d794a20fe354b69a7f3ca7a2e11fde384380a7b6cfaf77cbbad421d38251467c95b3aa9d1a887afc4667ae70641a5757b490fbe54931b21d289811c4c3678182edd8121fa66222eb947733daaffc48ec1028d9cdc348e5738c8f612519a5c8defcc3071488c728c71d6913ceadd3a617a44431c47149dff0c0feb2eef06efed4c9686c07067dd58ae8cc7cccf1c5384cc1b50e8f08294b362705f790300eb82d51f239db3e07ccbdb5eb83069dd4c492522c1190e3e5ddefd206333f1a102ecf255dc9b30aa1d4682952266b865a0615119f8d05f553707a3eebf2621ef238b625e7f3863fd42a9473cae974f50098cdf630178bd6fb6eaffd15088dd53cbc5e9a25998475002539d19845aaf89bcd2642fb15448a6acf241d7983d4c3047427237f7177fc9e8b182e48cc36fe43059639a9f3e6475c3ad91b6da5289ca9897b428f44e6b930cb296a910dc2ca50a81529f4a54263109fb5eeb5afe2e97ef59de0188dc120d9cbb3d76ff881315069dab6e8670dfae9d30fabacc14921d95a62133d7ef4332a56954171406a6a1424e48f2759d8394f0ff02de11f064ad262cc86db97c4d501f69c14af0ddb1ec56d79c479e948b9e93e5d458bc11c3b71c97f07a71c423b541e9fd3d809ae5942725efed77e8fe817bcd1383ea31acf6a97ec603dfc483864a8e96f433e57bdcec8116b4fe54ebb6077914286f36cad1f52fbdd315523dab34dc25f885af4ad11bafa1b4d5531777de1e11701d2333af043d9076892e0fa263653b6573804f948ccbd46c7c2dee02e722dd8a7e231d299f6558b277df702d0bb663065c06860755f54dcda553adcf3e432031c111af210bf81700989cbfe9a1cf60717c1180a0fe768299a4c204a8c8777f4f64ddfa5b22f79a09253397b05298add05dc0dab63362126f634bc547c2fdbc7f083efe7c28bf548439a431b78896c5127a8014400feb4efff410d8bfa2794adc26fd405d622cdececa5ef8e36c2560fbeade18fe53f614d3d881dc44f6a07427681a72dee0f9f0ae21d87e09a9f029d47a8d58a235b48db6b1130b285e5f2074f993bac1521bc57a8ce8cf302bac500a38fd7bdc23f19fce8326d8b3d117b8d87789a5cc9602e43b3c13f76ac34d2d2b2829015519e74e94703ffd3899c0be14446ccc4f548ed7ec926e1d33296295ffcac3c6ba186c81623ccd7d9579ab6b98f90be1a9d361fb4110415fc1242e5d7ad688f23a667dfc5821280bd1c6412f2081db0967c80f02e6cf73c576c90782e3cf00ce4b9ea742d93c248d8f3601f365ed360c3de59030cb8417b2a47c5b5f67206b05be07dc4d4122bf1bd9fb8c21362eda47f8fa693e5ab230948b4091cd5077478db798913f1017b27e0cd088e76d815078eec212b10";
    const KAT_SV_VALID_MSG: &str = "21889f7e3e848f2eb5c8e561bd3c4318b1b970b4febf3de0ac472f0fc0612fa3a35869b57588fa3a75e9def111d72b31264c6018716c538b3d150739bf041794baf738e96d696512d2e121514a7bf5b380ee14d8f5e99bdc41d71fda9bcd1c963b296c078bac1f3b2456010c4894625defa206db9b52bd26fec3958da58968d4ee69e6acd8e45687c9b02bb20f9a9fd664c46304a10a0021d645ebe133e8eb4f0911a6e86bc62153a6a7e59c74936ceaa5c87690d972e595525273fa37fd2eaf4c9f467c84459fda553c76869f5274493f23de619738ef508e2b2d0ba076901c2e85eee9ddac0e842a0dc8c8c274c17f5d1371c8195c343b89242892c9c9e81d0538fa60d2d25db1ebf8becc737874b7bef6d48894955429e6c0bb3a5df97ce8da3c40362b7f76329c055e6e851afc455e868c45b2c259466e26e04805f9b6496744e66fbdd33d4b3c874beedcc34fc609c1341443e42dc0abfe0968cbb2b9e7f33a32d5e00506939ad029df830545778eabfbbee1aa849919c775c366d81c6666cef4213bdd72047f15bec77d468821c26f40e71920b6e85b6db2530a86a85998a7250b2607e7cf9314df9792df06cc1a7f490e31b40d8cda1a2822ad05195fac51a78412a3a00c7e729c27ac90028390605823e555aa3f2b38afc71366412f3b8b289563962c73a32f63dbf439c58ae23c88ef3555ead4e60a1b3f17443be24d9160711ae5c0194f8d78cf29904a4678c60b4f488fc09cfd427a23b07c011cfe8d6c3f7f3d50ee8bd17ef6f1e817612dcbbc18603a6fb9d0e0af6bd34beace836ab741f1771135df6c89b748917cadae4d6e9a4a8586b6ce5eb691732f5b1488c7876d95c5af9c65079de7f13d178772229a2e6072950bd84d06a114773c7c547af56018efcf487ccf0de0905e04d4ffcb09b0acaf8f7d279f5d650e2b6b72e72e46f51216527bd247ddeff0bcaa35b214cc80ea24aa9a6f07776b6ba2905abefd9c3b94b6e9cb4bf3d45749ff859e0bc8079e852a708469daabfbe29e6fa79e27ee755bb6fdbab351ab5aa814741b03590adb4a2f81ad72f8f191709d1df64e7d6bbe1a88f815a352ce07d8e37c5a6b1b990095be240ae609fe53cba00c8159833d256fe0379c5a9f996f3a67b7714bbc327c1e767a8ca2db9f522552b53cc1086e9054c8179d98b876104ac7e5855b23a680ddce8ac71392ed867ed054d0afe4361fec1395f23d0f4ba93e8e1e90611d227a236520f8285ba3e9bb55ade361b59e685847a27e9dcae5fec6b223b77ba8dc2bb4b5864e4d8f678f9132bc230d115b624599393e49d62faab36d878feb351c7779baf5bc17e3029186ec55cd74996c4e410eec982055e6a9719e315021ed7ce60031bc79609c7132325a943080a148e4bea97d671c1da835345559891534eb1a1cd56fbc7d2af7bf7609b5c98b1bffca2747850d0899bc70ee3aa3575be73be7231f4b806c702b43b68501d88d9770d8adb471511c0f396855dc2ca96dad4477e24360fbf3ad7f9898a11c4101114c1be41005a05f1e2a841b3e2dec08c4e4d2c702eadab254e8b355d06f469354a783c9356e51800b7acd1d124fdb61d56908e8b096a8951550526286acdaeb47966b1a8fc171cccc835eab80f002a64b3901ab5b8e2ac0c1128aa73a1e0369264d0d15f6279bd6146377da576aa7a0f78c818915003955ac61412a988630445db5152890fa33ccc317ab94e4d621033c232d6b62611e3b769e0f29f35eedc0f85bb1786de4c425f7e3eb343caff3bb8b35898646299f0f2d830c541f2bb0af4be844d892ad39c5a9739402704cbf83f32f55a40e39a83d334325a7aa6d988ce65c81fc32e6ebe0da97bfee66d352532bb7c2b8b7960bcde477be7d8d135d6962fad5c3a0ea3ab5e70c3b19068cb4f2c1b3bb07d6fa86bb2022e66d9cd2ec15b0c67b1ac51407e6bf99b33d522befcbe45b507a290d2fdd149bd7a7d0f94e9a498d45f657984d112de41506d89b56f8c9b766ea6d36a3f6bdd2b3132534cad49f8bd8a923b8824b45bdb0cc04ecb0c7aefddc9bceee26223669afdae393cedeb119f3886205f5a55235d89359da5f6cad96a6f3127bee93143bae195ed5801e500aa763595d5e55f1ee17bc813a5ee4820db064b11ee8587c4ce6c15ae7946af259cdb7bfe17a5dfb5812fbd46be0fbfd0800f33f73781dc26645d3bb59ad04eaeb2861355bed8300f0d72a3caabec220a21b08eb7f551abb0313ac657b4dd2824fa6922d009d1810eb72958d3321d512aa4e092c3053917e5561d374fd6f7285655d5d80d16c6eac48383f10d3701dd688aad4edd238e0ad27649a6f4960492b8268fd50f75dbd7e3cdc641101b8e2efd11dd5469af5ed62ae55de8eebab88ad4940c8b560eef35df16ee3c09a8f0205f2851ad20d926b4a1e5d3febbbaeec1f9dffa004bed475ecefe3d905400cc0ee409a3dd8cb26acea44868ad5dae340cb7423cc5b7d439f305de5f8ba7cb0d1a8331acefc7a60436a5b1d475e05d3d2e89d56b612b4f4080f96b7390e9007078be58fa9acccde212a35814f855236e797f489c2843cb738ddc79bda9b8b78ebaaa29994ec6ac67260dbf2c9edd1cfaa7153c4867cb2aa24797c14733e3efd1cfe6e2054fca73b5b7a05742f6130b4f13ad91999a7775acbf7953b27c64177d40a53f9a2c209838aec6bfdd67da2bab5a4dab4b513076ff811e35d803227c778dbf1d11be559cbee8f2da0176f6cae55156d4f8db953c6db6edffb8df713b88c836d422bf7cf23f3676d09d9e3ded80c705593eab44ae61e1dc9eb084c325c980683f647781eaba85803d8a072e3a55ae848c053abbf107ab5bb";
    const KAT_SV_VALID_SIG: &str = "693ec4fb248ad4888e30d0a154277ad4c987c11413342f7f3aa0b927f073a85e1c92ce72d70fd35b466439a61186bbf21c3d4d046d313d08c43a8f0ec2e9713a28d2790a5de0e3c360c6f0abaa8a0805b970101c33874a11769f87e6e3b9d4e625c589bfc8b4358aa247666d7759aaed9b4b2d86cec039a1d7119ac156e98f4347d835f99622fc2b88d4ffd4f3faf256299ab855f69edd8fc8328ab919290104cbf8c21f5752378b5ba9a1ad2f085c488413a69516118a9b19fca0e3c6a4e4db8f7b3681f673ae662826f1668df5cc00d7fb7c8b706f7f3821f9372bb8fecbbb59913c779b3ba0750cb6f50b5f2d45401dad963e53e7a83415e981dcf20f24835bef793cef4f3aedd7b11e60713e52b3f0130c79783a9b71e1aabaa56f6d4873b6abd37e1202ae7d14ec8eceb04d0ac60db99c016f5b5f3f5fd971940efbb25e5c604399bba059393bd553609305ecd3488ef7db0effe85a117d469b64d062dcd0ac0235ce342af67771f818c15338a93762b54a5764e874d9475e8c887f48faaba00780abd49c1e9ac1327288456f8ad182e67197d521147ad120ed99c30eb1060ff45cfacb370d4e1858c1c80cf2c5d72e16079963e63b2d3724af33046ee4dbfe59914745ab4dedb43147252edc7e170e9f0899e3d16795f473d1d4408e566a9bbb72403b168be324e8630223ec6e69c2e15aca5dbd067a91ed334aa0d51a3d98d04c4b5d990821c501511dfd9d69dee1d31e0df6abc3b78310fcb1d1a9159b090ffdd36701b4f7b0513ad2866d92ed84eea0c6741faaa54f88e840eddfda407e90f5463b064f7aa2eddd1730cea124e306609c83f7e1014e94bfe2f29f2ee21769bc92b5fdc1f4264b8f3e66502f886c14e6b340f1af488dfd3fff99d3b5fb69fb686914b3084930a58cec8eb43ddb8a07ecdf465f7a52bc0b7c217730c417143aa5457c039e4e868968925b87e2bca67a1f7d7078adde6280b73f8e468af934e6d4a21c1c11c297b73432d875aa438ef486778109367659d6d90a36b0e0dea07fa0cd0ac327544ed6cc4ea668374131eb3ba493a964726326ddf8ecd17849a01f800afd369f3854a1c116aa9795029c597ca312870cee0578e01f717cad7c29ef648af8ff4aecc293ea9b3adbd6e99f19495228f04cbdb950c3076b11a61a66b42ac67ef20fb3535d741b44be3a6f3fd9cdab643a35bc7ac566a1b40048718a5f2a538b10eeb4ebe54e032c84f81aac23401a6bb3b355aed54609ee74bea3b89197cb21404c83290b200292ac6009de9e00ce3ee9549b913e162505562edd93a386a4fd3fdeb6b47105666c04a5cb8efa307445fa0ae5c10b5391054717625a6c7de9d19939bf0eb3bedc88988899f6dc94257d435650a441d345d67177009e7486bba39724ea0e82f17a944027463fc526fed1921bea78c640bd75030628e9a1a4696ebe0dba419d102b8ea42f45478594f0872937a682ebe7d62cdc4153425273cdf9c34a66533f1f8c586eb0e671b10c010287bf6f022188ae2a5e10cb0bbd807d3fd9e36990a26412f27c54e45264429ce8a01cc2045906854d016d60309c4790a8d3660bb305eb3269d93780bac8d9fdb9746e41747f5a5cb48bfe41d0e8cd408db80a4f26d301e367d9ca5170c98d24f33aacd5332485cf21940e56d587cc48ad99818f5dc4663129717845a1cd35e438545f0040897b16618731669434f121857091ca2f37a97c811cf2baea07b7dacc058340af7c58e46fb4b1cf5a0f7ca6b5c758db2418a5fca175fce762b777c58f4ee498dd2f90534c10d263ab2ad565bb8f186f8ed27cb8057b892c390a3db3d7d1ad75eca6eb9e9e417a231c925a08d2bca8b31ad8ab1b95a132375555f0bd7c06a582d4533a66945e6f4a9fb896018df05ad16e694a0029c1cd0bd2b2725482ba34b23628c3dbf36e98f9c4066d1d9601615dd8884cb6616091b4dde0ad03776ac500cd2c7401b53e9376b65a369054e7d23b11542d3c2bafddf15f4feeed5963b46a38b40e429bcd1fbec897b87e6507af53ccc3aa949e08bc9c529afc7ed268955c8dfdc6d436bb8550c701d427af0bd1465d91dd7aaa38cc2cd03c9388d52e7a08b27eac89854e354e6e377af6c691e4a3d1d3eceaa6337e18ced104b328dccdb219798ed4dcc9536a33f996df9977551c948dcbf6a8c77ec47c9b55ba916094b961ec1e35c91d7b3a3e69e44f8ba4fb5b67c7540871b29638cd86d5bf0ad1dccc515b578b3c2b6cbbf437e6bfad7e80b006b10da63b5c381ac83f9a803902489dcfa1ed05123622179e8ffadca7d3a2c2be4b5b98685aa322987b4bf66896d6d667d256314b7e9ad16519ec7bf749fd99bcb08b18a5fcf9956ef1e95c11a9befef80036130e08d7470d30b88d0b62e792434a094bf0442a11eb9825d8796653d8e4c1e8e15ad841edf0623a2dd444f4673cb169abbe74ac8ec67e01ae31e5a4635be51e393d60180add33c10d942ff90f7144936aac7e0a0895cf9881b0101d5f511f72f29cb5d2cb10c4c892a588d5c9ed17bb666c2570df62f5a662df858cdc1b2548ae113b1699cec02feadc257d525beadca375c9a25b370c6103ae926c3e54338b2f8b993b821888ebb1b60636b941ffa7946a05ec0807f540622afa812f57fccce1a3d4dd98941a2c7ef8893a62872e24904c83d00202e6ca9507c5166456e9b32958d7823dace416c4c21750a0f06683da32c7cbc9baf21e0e6cf4911071522cc03cfcf9d36d3dd1575574163a63bb82ba035de277d8b79040eada342ead7b77dbe078971333c271007986cacd08182b4059f535e4b8960f57970e62c743ed41a9c5df22088f502df450d3fe0557a8c8f612864881e90abce2aeaaa5db8c4783242bb622f7978f77c95007b1e7d996df3f2c03b789a537808664f08320ac08dccd6f56606b9e64175f0f369d908b176c44059b5595e56270436f405a77b4df9dee861c0f50028f4f58e1fa0d3a636eec774b00034147355873805beeb2c221d50e2b2afa5b1c0785fde34fc8c2b848e601a4d050876604aafc2da09c19422be45405c9a316268bb5c692ef88b9981494af7342e93d22f2eb300239043dd4608b511457e5f12953f9bc95bb4d9f3fe485083da8912e96f8f6ccc0079b644027ad319add64a70932547d5031fb5d342a12834349dadf55ff10664965e7210e88a4e0f8f5ae9a3e7265759d846ade82c2847e1961bdf352b05d5363be86b313751712c466a815af3b99138abcdc3f9c0f6900e082153193531c7137f2907867670b4a75c8bb886ecc1187d3cd1076b10a99ab19f45a49618331fd57d8ed8d030eeeb24c2dda9bac64524c13da7952024a7c8edec014d97218d6529bfbde3cf6be60109e2b407a0b3c0c5b62b56d9609f5153c49fb5c1f91800805711009944c90e709e51c19e65f705109f7274ded24180c911836e16ed303bf7a68ba063b9485fb56c25f69433f5a3d27dbe2430943288976205301ddcd79a4d9bb99ba9179a2d0a58c447f3bd6664afb161f46af944090cdde102778647643def4a5c6918e673a82b81ebc947f746d2ef26345646261a961aac2ae023e0a419e828cdc28d7c9f5bfee3eec6059d578af407fd2cbc41ea68ba1dd15c87d874003c03561c196e30079717cb96c6fabe1af16c419bc827058794b2f5fb308974b1c42adb34011bcc7d9a855bc8f94a736737d08d32eac9fdcca2b1fc989d5f2d6236c288d9e82de68ede228bcde7edf630331de6fbe4861d8c8fe91fa450adbfbc430fc14f96fabd57d8f501f0ce0734e302ef8e2ca3e218f217cca2e724119024039fd7b7d5a5a36a675ff5c0ebf121f4505eabe85c28011e72c4742bb6c0a048da0e0d95a8d1de79af7731826265dc224d944f3145bca8266e4c31ef79d57ce48ce9dbe68961aecd347f49164dbd00ea2c2e8edd2e22d86dbf6ea700d9a6f936bbebef0d32803b97d340d2e3aa7dc3984cbfaeb49ae1a7cb01374546e843ef9faa97fc09fac79b82a6b6b299c28afe8610e70f936abb6ea7dd314c7282590f50238c5b4c250386b02b217d1aefe04acbbbad61773662d0efed8b966e69bf3f9886412dd8c3e8330f299a9bc45a51433cd4e56a89647fbc6be51e72f2e7b822e0c4d82a88f2df7bb0e1a7b4099f0af07101e468e1bf457316b16db614cb8d074773a861551bf6f2cd94dddc13b6ddd7e6eb53227d243bb55076ec790607ec16d8df9c9a73ec2311536c21bc2737c23a16f99c2db3191be665d4620c70bb62b8ce6800a171bfee52d43ffc8897f0670a468f2e60a5d4e76a43191bad34d44aa9ba8d0b365f2c007843da9f1f877de2f5b1fc3276f06737881a4d448d9a98e8d17f85e7a115e5e6af9c75422bdf6927c06027f56ee4dfacdb1b0c457239d16e7e7b11ac6826181d7eaff803de212c566ba360adbb14b46b6d63dd90e90c0437aff9ac7294fb5125e3156d9ce8bd2d4bae22b570a450ec1eb6e19243c6d4c2d05f21607f93dea5bc319df48f13ab2b85422eee32e40438192c750933594a33a7ed24497c784b28299bc81e6ed39016336128accf4f17cc454d79badc583062c4e9cb8090c1f75a9c9f02f64ad395571798ac51d34363c8f9a9cb229474b8a9bb3f400000000000000000000000000000000000000050c0f151d24";
    // ML-DSA-65 SigVer (ACVP tgId=10 tcId=149: modified signature - hint)
    const KAT_SV_BADHINT_PK: &str = "5a6ff43594231341f625b7fcfd2cca2e5c1e8ac866ffd80d8189ca2f3634c462eb13275d478d82404141b567b6e23764e13d58f4eac641257a38f16ab5ee23dfbfa602ef1fd3e66f936207cd6ab90f5de49b9700dcb8830dc71c9577fd812c08bb6dbaaaace85f2358da9b5f44354830ff027ebfeeb4aee225e8963d3b1297b7647599f0dbf6b95c10418700c0d011b9bb68769a9e9bcc64e4222de353091beb91fcbc589973eda5f4c44b54a99d800ef7248bb420739eb585b40ff366fdd5be0cb4f5eae060a189e8cce17b344b3cfcec21e59ae3e59a70af4f014c7b33111059d6c22851ec5d9a71210b960f44c24747f62844421bab51f1c7280b9632b4d2dc4297c66d7981353faecd2dc285967514ab8d8173920a795dddbcdd3ee8347383bad23ae0df04a02e528a300c5fb12d47c5a276254b9689cc9dc9a835cd468d53667021fe4b15e660fa3733cb1aa50024d3f6249839c3ad5737a7e8dae99ec018ed254df1d3e6c21a79ce6cb7d48de8ac2868a123f37a5a0799119113352b0b3fb89a14a57847501c27c679659635794677dad74627d4b77322d2447f7ce60de87755134118406d2ac130afa239950db73e0cdac877e28d7179dde496565ef3ca11071737903654d41f82fddd2e1f7e260566b7f69182f595bf475d633a43226d2687d7de3b5c876bf820a41d14dc2630767b4c0004e9cee09ad163553278b0bfde7d3c7c1d31dcaecc6ab13386d67352d2224546d49fd5dc50a7a82c9610f915ef2fd4a9b2c59f11c3e84145bade115384ec04bde7f98816dd6dc140f7441336869d58d25d93c90ac22c601d849e01e0a4ecae77ce88e82b47478460c01a655fd2201f3517e5a5b1cfd9ddccd38ca7dd456df7dd9215506b07b0924726d9af844b38e7b59c761044e8c46ca1f3ec7c0e0b072801148d1724429df45f5d47f82da24a75a8e825197c07c4c5d0461a9ff20ee5986f59fe4aa108dff427624221f6c6b71c02ef17457b2b114120e073fa9083be1a18b6a53fbc597996d530fa8c840b2b898dce574368b84ac78d28e4c52f4e524c31ee0dc4f7d8623f095d2e9188cb332db16ae527aa2cddfa5a9c5c2c399d5f606fa56e52e1931555124df5c50c8c1b0c3afb20a489cbe325ea58c84e269f9d0b3cb2c405a2708a0e479639e588f719fc7fd4dc0c9d214806e9fa7c290b841946da3193e996171918b726178b498aadb2273d0c3a2cceb8cd98e622fe2dbd240c76b779b5df5c2d84750d17e55ee1a46e8c6e0b353c19e7c958e0d4cbea9a2a92bbbcb00e068ee5bf6fb3977032c0a686d00d6fe481940df18f17c4f91674a23c9335468b70426bf2055801472a21f507b706af022e19a42ec3c809d6cfcb9fad50259147eb565e111804dae78d5736927a73b663f284b17baf0049bdb8f88c96d2f85b99bdf93c5aeed1606fcfcd7f6bb10fa58d65060e7fbb9a53a9ae2072d112c42ade69d615369c4980a32bb6dbd3e645862433db30bcdd258d3d88b5e538705c6260a1e341839d3d3a2fd92e8f5c7383827b3cff494893b324530385c971f7d3539c1fe692b4c7634a954843b602b413b88e7cf02a27f5b9f7852c0443b6639cf98c8b02e743ac957462de128fbf49c6a6445046bd68c13ca6a7f19cfef15027b79c027c29261bffdea3c4d468489b16b9e8591d28f4c25c1492c210236c1a719704e4f1c91794cda358d8d98598a7ae674e58eb164bf33ea36efa26e493e20f930e0505c70a342ef68422a6a2dc08c4eb4c5e5888169086b6d0caf72060f27598e83be3ebcfd37dd23250e8297bbf3f957b5ae7b6e72a94743d10b5372f7c941bb01680192aeb8da3c693e8d7f29a1a4ed22f1ce3ffdd30ae35ee670544bea741776505cb9123139b2ac81b4b41b802c293b1e44214ba9f65e842a0a703714b926f48a570017ac07613a9cae33d16bcda2228d42b2be1f7a9ccef833b957db25cfe162abf9fa4c07345a91e7e921f78755e3e3e4ce1771bd2267711e71f5747a4adb1a62b96a1b37f8b49d890b208b350deb928067c502a9b3828a0f39223ab60991d44506abefa2a3fc7413500141fbb7310f31fca0fa3460b735d9de8d5ad7a498cbf136e0074bd210334f4ad1f49576023ff3e0215c8fe59997ab0b5dbf5050c75032db8626bb063093cd7d2a1d7902fa84afef1d9e13aac6dfb5d2fa7daa11e03ae394c71ce73e4ea4dc149bdc2950caf31c9ad92127ff5a7439b8754f14eebea9ac649dd8be3d47f66c72a1435a353876eb0ee701e3c0f40b29e6a1bb38dbaad378e14f6438703f51e04deda85fd2a4c54153540d91be2e46426153c56d7ac5dccf14775dd2ab3962394fd25d3b4b79ed10bd5f8bb2e61e1878bd3bcdfa69f8a28450a0e330b5de7cfbc2d7510e3ae7867bb9f9e2ec783fcbb41eb513803ddcf1f9b09aab29e214947618a440ea4ee3af83b19aa8652b424ee438b61bdb36012d5ba2f14b0c4af2b7707229554b64e171d19f268dacbe2e90926513b7ffd8264e728302a70608bef52edae204936fab46425beb34423829fbbb5bda4145b0f76e1c900b7a42b7f6594813f004af3726cb2d87361c02577479873ca2bd86aed1ee9a5fd6403716584374f22a71f7bff0a1efb4b8c60e0a218b7133863229b9666354d71476b7abe228c82bee43a44bf6e75309fc9d4ceae95c81a09b96ce8e75076314593fc727dfa207b9ae02f373b82c462d2833f347ac1064b5b7994c5077e92b983c736c4fd";
    const KAT_SV_BADHINT_MSG: &str = "42c6f1c22d766834800365c60b29fd128c389973e600b613375a65e5059c5b4dde9ed43ae9a7ebd154073e8771622c915c5bb3a5a474821700da691947bd3cbe8ad72938bb5a6d3fde3ee76817b6eea174ada3415be62407d7909457e6ca0f3c70563e5f03a03fff9c0f8cc97b59a8953250e357f9ac15c8372dd9fa590a4e6a0863c2bf4c20f157049cee71af5c34b08bee623534179f33158a80f5f8439c8b803b26b00a33849486186e99e02b53b722d13ef696cfa52e13ccf3d0b5776f7236ce9c02145781cae4f804da45b300095b356d67b6d25a1c3d3a078cfd688d8bf2b44ce034aeed9038f4c9f0ebe3681a59f1394202622783afd0b101e7babeaee9f0beaece59fa947870c9dd560aedef3cee46bc16777bb1621a3a2f42660002d11ffad8d2a409a0ad50ba7e138a9ee900f368e7bc90cde4c99153d7f9a8e432eedc67f4f4ede3a4d5034ce45b4442b6f233d72799eede3914efc5b548dfa3f93415c25540901dd71b01d69bc9e2d38f479cb69da21948b131a78511c5fea5ac9f15c62fd38952a9d07940e1a010e099008bb4ee8b430ffb4496de923aee515ce376aca97bd41afb8a42e0b1148d47103abfff165a88224bbf4203ed84dcebb12b556ee8211b5900a10f77ae8ece3e4784636f259f7db2515ecdc4d5d4bb0a01f16f8052d4cc73a9e59f930cda81188418d7a98ededc20aba843b494c43fa0351b5130a753561f2df24d02c0285a951362891474f126532116d3a9f4f965f7e85fbc6770957a0e2d4c9ab531fe377e5138aefabc27fff183c2c52261836bc8a77f01f7a7accdc15c453c74e3a915e639342c60c10d76e95664143e56d75369c07d5f47e570b37e986f073211565697001bf9b4ed2c4506c6e6675a2a663164784eca3941150233e9198c07133cd0bebf3fa4873bccb88bb6a15ce8a39c9825771b6fe21415d7a4a33580a5b8fca723ce0bf7c38ba87fe730df4e19baa6686abf4403bb609fc9b6022f2fbab3e96a04ba178e0c06576a7ad6cf81ddcbd9d3d3f0348e2200623a5d17fd1af52356b7b2bd19f28d79589e4d67041d9afce0b41c2453106b9b271eaca40864a5a5d17ff4697ebe7ff6f826009f2a4a1f0fdf657ca2bfc6a24a20317b99e886a0593e78b2232c79625c57dcebf55b8ccda3b7952ba8bee31e84a221e3e11bd7d3e31c5c2bf8eed7a40a0d3a86dd4a456b04139670bb6abcb56a70a0fad1836f97ddba363ac690e03a28519564744e8e249df26651b3b48d1a5722bbd928fff6a072aed46c6fe35e6a644925498413d82649c8fac823e246b227a51d25fb45844d9b1a774c74d8ec98ba8a33f967b5c07447b71eac4d92baeafb49455c7b18f597438cff458820dd6875485adecc42fb6d02993df0dcc8da9a5f006d514061e01469ff3c6322c20e85a7fb74282c1aea689b86be5b2d5e9780f0210896a68563e97086f8b6ab96f3c0f46b4f7448cabc689613d7a44b509b61b5e7fa168302f0f76fbcf3e982807c722a09acc8c04d67ea378b98977cd2a663707b3727091ecaa03410c1afb5f4f32faa5476f1b40bdded0f03344da32408306c";
    const KAT_SV_BADHINT_SIG: &str = "e48dbc7d3f8176506ceef709081ef99244682b921df599de51aeb42c99bc8143ad28b0b67c5aa92813795236b66b47a3c5c5d1dcb6526c476c9419296ffb290211a553aa4128b5ac03a285cdf1e7780c8004d98eb8741d7e6dc7d865c0c44e4b72702219abc7d86df454edb7b852e960ec97b3cdea06f045a855d6b4f272e95640777225df699d4cda8e2d6dcb7c4b3ba24bfb05487a2f6ca70de6fc5752eaae42d4a749ca5ccbba8b43980e7f3a96a6e7d3b4787a5d04f36f1b85964f93dc3eaf61f88f30ac368f70d58fd6074e8e13b1f40f6ebf59d82f2b734bf6c9626adb2920be4e585c9a95d25aebca1895e79f4a3e79d6cfd6ae2122ad97657cfc4d396e556bb17c64edcbe5aef2d34de9a7934864ae364431cbfaac40f723edfec23c14a57a8f3506f0862c561c356055a191cd2032c9768025731152175481ce88cfb09ccb46223746fd6c60c5294e40d1d8565f8bdccbc4a9d37218a4f9b962b3b8c526dcfc0909e5ec63344145ae85e1c361299c4d39e9383287978c281635516dab8c9f7a1cabf14021bd00ef2cddc247c5b77f2d4a419ca6a6a3ac7b480153de38b644d3013936b16e7836410406d41bc2007149c41212a53acde06061ead466596d89e407023cf62c013bb3b5f57cc40c14917288a9fc63895a77a0ba19a977ce1a94b311656942944053beba6db778b6c73343ad0b4f7b8451e649e7590dd3961362f27955ba687b6380765f98eeb469ea63e9cadac2a00af377240de8a0e813c58660a9088f039dd663d8c3c45cb9de77d43dd0a416f3c87cb858e7d5d1275dafa1b4f2b2ea6105733e61c981c7394d0897db42bb6ebb60130cc8379e50028831b0f67800cf71a688485a441a7b3109b2493c4424bf2e4eaf7c33139eb919a3169088f1e4415fddf57cb7cee6ac7be798b8885e1cc24e480dba876f1f815f72d755ff51184cd6823fee7c31e106cd475cdf95a324111675b8fb12c188da535f97d2e62b18840873a26b5bb64ae0ed5cff8af3c0809b221be5751d6a3fbe649883b008f784b0755e376cccaf6b5ee9f44427935032eddf748b5960904467b50beb9ba6a2d267ed0bccbd248e6ac04250be6f01ae71a58752f1d527fccfd90720fb10da5c0f89022dad2a57a228adf687ab80d662396186c0376b6fa16a7c83f97cfd6cffed88f8b5a77d626e5f073990d851ef6214e784d08c8f090f1f061afb6effb1ab3cb9bb5895861cbd960772fc85820ba4a63c653d82535d27f00ac96f897bbf931fbf0e0ed9bc56857e49493092b1c102898e2056890baf49e6e33d6b564e5b3f69ec2776bf2ebf8f602153f2b7647e82e4bd3523124974ccfce768e97dfdb22b8292dafb8bd95445b6b6effff50ceff5757c263c921a23fbb7cdc3bf150cf7a17838eb15ea9972d5fdfc08f4ca76c0b77935548179f327ec4f7470db4e3b7e32561223998f403e465e40270a57e12e93ae872ae49f07f9e09f7d03782f5b0b92ebeede01507fbbac4c54b453d7bd1a2721960c3ed96f0842c9c8f03e12dcb85154a2f1b11c6a53bd40d3ddc3d6ad530bb7dec12ca0f2c5207fb9599e52ade0530c88624eb825bbd080f5f7365a862f074aa419aa4662ea434fac0232f74068f9b0652e6cd889e95afac980ebc4d6df70a83838ad71f7082c2f0c5f5e96a31b70cd376080191418735553369e42b67e04ae7b6113105d4147d240bd608376818e0b08c98a3a833452d93d04f952bab0c6b337f05e6997afdfd3a188dafddca409d84546733d0f5ca6a2ad94a9668e35d6f67f1ed303383c0e5c9e19568d54a4b85c480bbf879bb6e23bfd301f0cea2cf39c86543d0002b89d1e22b6231b6ad19ad4ac6b246f896251d5a39f360542aea6e4ce2ec7abeb0f20b526b85a2a723fca1ae1de731fa548f6b292f7819fda0134f83299c97c88810c83ba4eebdd22f422c3ddf966a7b1df53a1282f2eacaed4fdad245bdbe472dbddbf1e918ab9e6cb12715f1c6a812a136c1ca2f794b6c8325304743c43c9984867035d47135e792a9477096f017a1f08e97327a8785f45f950fe2f83309d102aed0d3d587c819d4d5f0d118876d3bd1ce0a24a3fb1a521f6d2e078c3b5dc822cc5d88c73a9d68862f3e1ea58e6ee991ad4ade9f90ab2a9946630917596a7ad3e6ea1a7cba4c30554149715ff03aa341cf8627f0dfb70bc1f6e7444bedf40ace68d704093a5e237c682985697f2519bf3110cc42b9cb254da235948e4815b1e38e0b2833e4f10ca14eec75b98725e516acd0548dd50aa6fc4cd2cc17e9054d51ce8af7a24a0e5a5ae3730b3ab1d2eded82434aacfab8f5d0db7cefd5c554f53e1ab842ec0f1f5dbb774275679f185090ac1516ff9e598c2626e791a77447551a7aa7ace186f1f2ae7a3f4ec9fee4ee2cd8640f5cb61f54049377031f1270d2509054881416b18c75bdd14213898b3e3e2dc80485df3b3c9ad630786b309996a4cec1cbb876014e942ee1ee0995dc3087f1e947ce8f20ba08d320ea6c479eea9dd09b3b1a83858a5cae0f7c881894806488c6d6b72fcadaaf00f4eea8ba777c5c74f3cf427a4b8fff5675e973db505ce5800e46cafb43ec364dbe42bf51b0e2b9d233a38c332d8699b390a045524e0bc924cae582fc283649e9865c719cae0880d59a9902aea0ea138942b01565e0d6c0eb83587fed20f117d4ec9a85836d491d4e69a6090e9b8bab0aef42535207f3059ab6133eb97fb6c54421ce47b2e86a1abcd41e3f698c80591ee7e9078fd33d73327a54c8d1b07336d6eb16fdd5f22a37b68e654410979dc5850cf4d0055aaae07693e315a2c7780256efc8cf39a4e0ca57f30212a6d6dd09a8b4fef59a12666fde78b63919d62c0aa9269d05ec3c4ead513f08144aa2db4fdbd57fadab06351b0dc77b141ac6e6f49fd998d39a1166dd7eaeab96d79d827a5af82e8a865aa68ba5e55d0661aefb12f95151910feda2adfcfe3b5c0e9362d317978d6f8f6ea97a19223930c1fafbd2d92b3c08e4e29e8fe92e0c81b13108817c7037062831b3625ea10373b286cfb7f63dff688e2683b95c7f646019fa3e6a813cd990aa032ac771559b659468d1e08454dabee70fd9fc1b3bf9e34decae6ac746615ae3b13e8768f62327f8c1da78cc1ed1ea296961dd151c090a28a22f6b7306c97688ee825e8163da93049f6531a78ea4553aa668129a88b6a797982385fcea160eafcb69c8e92bb5640c8f186ef5c55b0f0f59899049af61df65174be07b165411b6a02167f7d0235fd11bd1be7b795beba1ce95448b7cf37a6ad5d04345871128066795042cfb8cc48872b31164088972f7f3aa7dd4b7087e39cbb077778471662bb184d5d853a7b015f5e18a6b363417618539bf9da763544da0eaa6f72ba560761bb75362c2f8e7332771b3314d28380736b11cf39fa7d12bc7b6ce785bd0fb17929fb876e2651484f2a167691b6f72f2cb747f29f0f037783fc60da29831bb44ee56a5d3673de8d270f4bd946c81e3f7e1eab52add3d1cce7425a4d243cba96f41ffe356ecda6859d022c0013559a06870da63295700f90337e6cd8bde15beb04eb235e1d322a3fd15ce54257cd6903ac5d965100db78898011b8b2c17a7e51c1c776333843f1518e68416b600ac6dcdcfe947f6ce967ab8fde7051a70e37cc951f124116ef0d79019e532a91ee24eaa9db70ca9558678dbc6ec3fe09f85896cc81222ed5a53298f89b35dff22b7ebf91e393002c3e06b38e3cf459335f8243bfa9ca3b73fd573ae02d2be4b0122d6ab55b22613e8091f44df5e4bdbbd266dfe20afe879c87c0d852fffa3a35c1e58ea8bc0c989d1c13639e1ec7d08fd67f034f5f5c9f8b9c5451136983278cf7c810ece8b1337903a1cabbb5968fd3b589f357770aabe757ff8628a7bd47db92768d7b23e7397aaaf6e800bb6b6714cb0380edbec43c344e61a254fcc6586ef49a8a8a4a1d08348cffdd1519bd9a8fc04cf42423e2f429ebeb7b42f11f6c4ae134aa76c263472724979b59884950cb0c71a8ad7a13ecda60317d1a1fdc0bf4767b3916fa99e7bb7d2d0e9f356b9156b8fed5e09e7090c4fdea92c4923848103e55a77831714a89c753839d4d703ff896d530345146b1010c439ff6fda6dde00f824d5defdff92b848b9a35ec0b42aad56d984a44f32d22b63c24efbd78564fe91e27de326d90c8d291b573fdc301eff9e665a81583dbbe90d3411007f9ac74eebf1e3eba8da3019f12c692cd8ca50498b7e7d4efb4650aeb30cde3d84118ad2acb3cb15c58d4ae2b45e841f87a1a195d1d67fbb3cea6cd67ab76a455c45916f93c38da063b9f8ecbb9d074290234ee7abeed82e41bbc03259e72c6243397e991caf4ffaf942092f6f1ce695924debba69d7e2b3173ea7116b9c87dd1b6f0b1c460bed1705e5e0afa0b9329c59b779b590fd3516a4348f3a2c17233489f339bc891510e690150f7ad2cd82fc681a5de6412127fca71beca23735bf88023660aa4786e8ede4f5f69b073d82e4a95ddae681eb986014058bc78f8f2262764a3ecf031bf69b798785e78c9a16deacc6586b7bc425acffef4c80d3461065d64de4878809ede163c777cdc0265698ebef5262a3b3e77808b999ca6af102a768fb4d8dafb0000000000000000000000000000000004090e141f26";
    // ML-DSA-65 SigVer (ACVP tgId=10 tcId=136: modified signature - commitment)
    const KAT_SV_BADCOMM_PK: &str = "a3f39be503dc1c051f033a6d44ce3db88fcfc73ec4de54dd54c9aa967cdcfd255212e83797a31928e149f2762c4b3f59ad1f01ea61c9591a77028705f2200890b5d1cc7827cd3d61daf5ce73b1ef295cb58a05890e7d1f7b7e3496f32c2234a85279564733f97ee7efa215974d8b45814d9e4bb776bf51c33b8495dd591b210a4b8f4c75568fb989d85e2a398ef34f93d6617d874bbd2e4af08dbd97c3cc987c5213213d0279ebccd27f52dedbfab15322fc5358d660c2a4f34a2331fa29228d090780590116366e5466d00c2a655503674bb9c22502fb316074374a4b55343c6b198e3ab84465e80efced14fee2a5f9dc0c2fbb5de30a46eb306a229adead623ce71887caa9b32920862220d0a2f1e681230bab779c886587ff67443ecbc2f82da904994d4d48ae34cf669da032acaefa9770abe57f53cea7227abe9219ab2d0648c28ec68bb9f8cb9613824ead0ddf0012903a1b2d8c5f3eb4fe7ba3a533d67d06d851f05a0375b27c936a1bf9940268637f91a1aaeee8c55de7d9e4386569eb95d1a5b04bd4d22def8759e1fad0041cb4cd5a86d9dd1142e170bb1d22c440448abf03d3d4f629e0018606079d0627edf8b8e2fbf55f954acb64cbf8c98e88a2aa2b06f570bc148c0c6c006ab6e525b7ff8ddfeb04120def17183aca2fa2d9e55ed771a2006dc4e1fede2d0b7376938360be38b4048d13907de405acdf8e17304f7ccb63bb7f26ca8418df231805bf06cbe77c9c50c82e3d0d67e6e2b8857d8922633f9dcdb5431190cf01b8a19d9293ff79cfae2ba51962371e5de375f1e0f60576d41cb689a3dc46b1f6de35d6286eb86d2f679d4e47ac3eb15dfcf0538cae3f0180c1fccda7e97346bae976d52d2c24ddda46be64a9c40d2ff5fd80f9b5712918b9460920f9150693c1855de88bd8433efe256f48fcb2c0c152946e38bacab7aa834b1370f3f085a6d0eb5c810af23d50e5233f6e7ee4e56e41d8208820e3b2cd735aa6972fc6a8b1625e4cb31a376f4509dd995f6b115a4d7d4ba8fa8aab61ad44facb3140e573deee9370c816f75623e6b403c6797c631a1d42e7599a417e80434644e6aa8f8f79ad8ffe7152e7cd554ea66306ccf9f6425ad264428f4b87b23f6a9a0c15affbdf049eafa8c2e20cf9fadf20d0a32824c23f2063985fef473127bacc7ffc7788c5d792af373203f16f6ee165f7007e82a81ddaf4c08916938e165667566d90013e0c32b25d0d649505ca713f8adf042392337748690c201680ca3c0608ea85d3a8341d524895446c28c25efb83f5ae8c2be7157aec98564d762d34e47beebb67e76eaa69bf556d150c59e8914db8cd8e47acb04eff512dbf2c4377236467bd13224dbfa2c239ce8a0617d817d1bf9a34b2b72ea9901f5297e20b6a6b780bce806b504db463d7bde3088def31e0ffe0f5dd5921c06649ca831224f63978f5d564e765d4578f9021f7dcb918c3967e93b99cb6503f759003c217698f19128d2fb1abf455b8d68b469fa1d2ce0f13252d389286a06a8f1e9ce1e6b9eeba4a0b9159afab088b3bddf0b3359a46177b2b48de2a2aad1c5c9730051ff598430c2343abddfffc287951966602f7d8a5684fd8b4a2a3cc0b91141b85c7f01c936d1297382611815f0f5ee733d30d0877ae591bf572595aec28d2c7b06042e70d5c138c4f470b6ce3de76bb987efa24d6abacbc92f2389dfb9e8f3c7852c1244d7af2eb4de2a7bcf8793b18606316a6e2c1e3199dabff71d3ea748ed1b09184c9ecbb2d8eac8fee325cf4dbf4f2a5df77c0e796cc055a2ec0161a25ff8316edf16369cb788e1b776585e5f45bde94e41033096ce22f1d5384e23b45672c15887efcfea48bcbcb15235361b8c0701241fd983b102e8b67fd7a197f7be2cb4c62f95e29282b73a047c4d1d0efbe41065dd305bc678079c4bd3df3366f801c545e89eaf549b33ac18c370fc9b725857af49b0e66f5f408c617b0cc01fea3cb32e19dc610b2f0cdc13d679657c5c4bf1c562e3cbd0cb53229a709f2a3e3cdc4cd289daa340d7b8ea9ba3dfdac81291167ca4194af3003375c95f7a7457b00aea7b9e135443a9bd0ae0ef10787a685fb2ea35a27c052e57ca99fcb45eaa4d5d88883b8d0210a33cea1762971f21c9eb3349ec65b779017c572508f57a00432bfccb94296a7a9f5ccd1708aa240dd3e8a375da1c374af70408722c3d1a43c313ce612f1fcffe3999bbb5cd6b28fdb7f6dc17e7e0e6070c893e4e2733363b0c25fa3fcf118dbc79e330d6d29efd930461569bb8dd3b6434c6b97accf97b2c1dfafb71206362e5c0c329415b006d7000c265824d5db232748c6bc82ec5b50d7f56af5b3a284cb42580331d8a5f09a8b55ba91dd7fe8e538da8b21b4864f1cfe5047ec6754482a41c6c52b6348eefd4aad9a31232f9824a15d8a660c2cfebbdf624950a1247654326ca619c277c4234d528ae6392f94cd7b4924b5d6aa89edba7361ccc5a342737c308e852e90afaa0af0a87172777307a82f8cc4b4d7533694d9a7558eb6a6fa8b50ba5a0b72a3c98b3c16ad51283d18855bfccf97dadb40b295dae9f358a468d8bcf984760c61cbd67e107afa873c07e7561184378b2bf660f01d07098c884ebf87babd9f83932e669ab44e814e3e77fe741c7144630a5f5d31332f57c8a7441a2dd8aa235789d8c2c6326c286c747f1d7f141607cffb8939f4622d30921e6f80b89f3e5efa56e731bdcf49cb33e989bce2acd33da3e4b5";
    const KAT_SV_BADCOMM_MSG: &str = "9af72de16466fe2ce26f5a640264c401034fb3dbcca62736afb5bbe62eab0c96b14e75826e9083719a4fc3d1f53950b246ab6be9e07856107a9c71e7d8987ca6404f9d52160bac6f39945423b7a1d2219c937faa514ce54ea18c8e1bffbc05ee737a72c85aec46c555bc36c5c7f89d08b770a4de87ef21b217f73f5dd1022b6f591b1b54a98a914172069972fffd46e1ea5f1d2a2c5f0a8fcf1b52ec2eb8ccef2e35c20dd98867d49bd13d917ef0ce69e36e169ef25aa51c29f5dc115e2d12af981863cd662a4f01fd1085d17b3384ab2db0194168650892022938288965e420a2b9c5029cfb1afdaf7f03faeca745621e6576434eb5695e1bffc88028ff81000a7179c095a211a3f468f6d1c32391cba960280a66ef921c7a5ba5ae9e0e65a651c61e7e73efc24670dc33e1d1e3b9c0ad678f8da6d2c729efecb058e882802849c8b57ce33e3239eecedc2e1982082ab38d301e36ae6f064302bca628b0144d0a4c63da0d6c4edd86c63c15d80b2bac92d809fdcf8a74ada3c2e9321cb9ff2ae4b539452f9b02bc8bffa9ab5c12c82d34d95f28dbf803449193761029d9dd2f719828a1396086f200e4f6d2cf064019d2130bfae971c30c5773a5b58d03a182d278b29d2c9b4140d348999f055ab737490413cb5bafa82435553d7aa0593a9a84fb2d863e891ee6df67a99196f96194ed460fc89e267dfffff0264b8120a87dd92f9967efa57e58ccb1f1d9afa7155ca0bf9a49d714ca1e631c2cbce2ea98d0415939ab560253888fe6dc6844e11c2bad09361af1e9d612dbf069432e0d3fa91a36bacbd3c266d6d98c32ad27a50ecc5f5aca2294b207fc250c6ebdd82d14c294030e53ae7c86772ccacdf8e5fb1f49ae427043d0d4ad288a68485a3a92a0a68418a946eebc0fcf9e9af641db92656d66a85079d399da3e4afc10bd4c2412230ba88a4a6986f1febc43ddaa12f8259a26947e4db5ac4e0f6313cde0bbcb137b450939002d8b01e5f5062621a93d5118ddcc895f9f572c45a9b8d66a6be705e26586e864100267aff31ea4e2f1f7c8397d39c8c0ae78012d6e4903943bf5039ae918197177cf51a58c38d8a1859b8eac4c11606f82eefb7ef85f3462a8f3e8cbc02a7e80a4144bdea94aafaaf7fa8da3abac8823c1c4c46798bd86c2adfbf03ce2cf9c123e3a58d43521344655943c7e21e25d9930ca9b5c3cbcbbfce880ffdd91053e3479af850845b8ee5c20012354ba6e43add88241200415c1c3439d8c237d544879e8f7ed658f351b71eb9f72fd80ff9a75a37d32d97e272c6614143e6029d9fc92ffa35355e3e62a0a5bc047307cd5d882feb6fc7ae7471d3c4dd14bb940773133cfefd35881982ba0f719219c63793860ce7ed75b0ccc82d2fcd5ee0f8722247d5caba9b435a700d5110947691a19123be0d3dc64f48ede79a30900826e3da93f833bb576b41833abe2cbe9eb4525dbfc585c4c3161a7b811215dcd6952e3a1fbf48c8ff5166b972c043d0baca000d6717252660f399ecb1231cbe14b4538e8ee7889eb1c964e4fbf6b85cf2dbae9dd03a812a13bd21985dfa92643652a02b2d46ac5967d037e83138e3828be7e743975310b4df70c53b30e07ef9b1a61ddf794444ea2f35e0f0ef60aae8e86288dcf4440a5432196f7220cb9f48d12758dc11dbe504c4db97a1a752de4ee2f606d03950110a823fab6e4909b5b6d79843cdaf9ddeff32b22d054e9c93ed87b87be68266e114e50879f0cb17c6f1d0d63e3b3055f76edc89471a74f602fc3066860ffb869d15d38413a70cbb7879dc91fb5188c4540dc8776d1f8cb4a8f8bf76bc33819383cc37c70f8463cfe649a8c3df1dfeb262ecaa07a38f52c4dcd3188776e2f5113dabbfea13fbb10e156c06bfe45997b1802669b154cf3f33a64bb2c092793bfd098d2d66cf7ee8ccae0ed6e2c2f9108f93aaf0a2e00eae5b127f58fcb85f1cec5ed9b8f4e93b5c70c949b0031a51b2ff486b1faf658ac6b27206a21befa2065e01f13475f858fab34a562db6c12061b49b489ecebd1edd835fb15de3ee96d6e6f071238c064e37e739ccce331e1673dffa90b2c68906df357d4ac43030248008993bdd34f06c455e0f27c58c545ade13e19e187eaf7022cdb613e85b9c470eff59128dec3a656e030f6236abd48549659660874f23d91b2718079a5e6f54b045d39a119db0648478ed3c57ca973ad5407257a05c9ce2996ab04e50cede4b4f572cdde6a9d5bbbd46bd1431cd43cb6578c668a9beabdd13ca43e7596dbb318d1ef9ab960cb3abb91c065c29b0acdd5209ac0c005b5a48f2b2da9a558ed7b392e6c4eeaaa5d51174d6c403f7ae8ffe64997631214e2841fd94416b1e28727d100dfab9af1176c84add4a28ad47ed442df8c2c80bf7c18da073f0116e1feeceff615bd4e2bdf737617228e2dbc8c5edb5af8afce771de6be2ed67a648e84a73b015e1633592f3a8f5ba39ea63a47b081a38f9b8939ee4e0c48177d656ece1ab6c9c9746d0d026bf681e9bcc52a2fd5ab3ce832a83a700476cc2335c425bc781869c8d510f3ed69d637d6f93e641a307edca322e7e6837f9fd9675b77d9a3cc7b2820e05aaeb24e5fcf192bba0fdddd279b0f67f237a139492383c2424c39f06390091c4142cb8d44955a881fcca2239ba9a8b0c9065d84456222253bf7e4b95739f85d327987cf4bd86e4fbce69c6b49bfb9260690295bed3c96c9111765b2e4166ebb38ece255d0ae41f2614bc0db2b343ca1aac9cfc5f5304915cf577d8dcbd09a7cc1c79f866163efd5561e8b365266208fa431837f933083d77244b9bf839811ed8212414cc3e1d22d4862f67807bb5989160126dcbd1c8f03146367349138384d9793f2abef3791ca0d409c2333983ada784af7bce5a88074be318455ace06de5852a114296d2d30ebe0c853d914e3498b81414fe1dbe77a8d5887ec24650d7927d2e716830f3ee8c49157b5d5155fd3cf3caa58372eb13f7924236845e1c243969d7938f8b28625d9787ea30b609eb0b0ddddf6a89406911bdfc9193518613334631663c610a1ad3342fc4dcfcd0f423d5870a72506a6bd013f599a5fc978d5b64e701aa2dc193174f2fd4f5107d0657a28d2bdee2771a47dc94fdf52269030924d45a032796b10166ecea6ab2476411eabc0fffa1b130beea2941dfc2f9043a9a873c758ff113b18ccc90123605701d73c0ef27a49d90614ae9f43b483ecef6ff21702264d8d2d9e3b39d32137aa8df64891d90f0045b0aaaa14e61cbf7652afea38ddee4d5a79050df2bffa83a03984bbf32ae68cc998cff54f80c6922b90fb3466c1613f39f9737855d8a905b5fa2aeb784840618706bb9a0d2846cdf16ae69bc5a08ddb150d04439c6d838532cd2d865eb80d023cb0e4e4ac763c4e3d1fe5e95ddbd2d3807993855a7d227beb6810396673ede754347798840e44b8825eb0cee97eed4306940a3c9f5146a45968e2e12ebeacfddedf684b2ee9678aa632d6a1218be4de493ef80361bcb6bc8fa671eb98faeb590fe24ace5d3681fe977bf9561dd65adb547bec1a17acd0299db581b0d80ef69f88e4877c57395a35590fb041e64472115759fa9f9a744d876ea207a76beafe57cddfaa8fe7a2355f0b768e55244edb955cfd9bd656c47f23646f2e8c9865abd754d490b1e9cf0ef330515409a7a1f68d3e900d17c2533c5e91845ef6a565a06f7036072acc0a256a055e39831310b7b365c3e238c52c1d5bff5ccc1f39144169d4671a5f655c5120d8c233dfbf3bbb5d93880af6cf84c69a956c772d2afe2c392de8bece6e5b4b60bab1cd8bb6a2c87689e71d654d7f52933588aaa0cd1bd2965dea7287a23544a0ed58661227fc13401d44390d948a23a07060f3b2fc28c920d3e587c9e2d5cab2e4a1ef711fc304293ba6d9863ca67bd5b4556d7ce83952ccc985e52";
    const KAT_SV_BADCOMM_SIG: &str = "6b41cbab4d2b2d33e1f4d1c0ec3642d5b56388eaabe652ca2b34d51efd5af1b72ee08ade5d9af9efedebe0a3f97e846ae4781dcf68d8fbd8944c37eb9aaab7afbfab774fa2a5af2e025d301186084c65337180e4784c9daed64df560b1a7ba10086a7c16ec68bc07b37b53b684348970ed8dd14be3b6c80da70293f042ff7581865e5fd4d6c8222070c9c2c2d3a3c1e2490be7a850b724ccb37bad5a78ef955f2238e36c6fec7e5ca85e03f2385cd98ab481a2456a1e6a53d829c3a502460bdf599693447978fa960ff10f05f5db90318ff16e69dcbba413a6b6a8877068149b7f0cfe435be05ed1f2bc7b77495a93c78a120c24fe788bb8a5762a36194a54b52946e14af75d812137ffebcc62f7d71a1e6ef0df52d2cb952d9460eb366fccba25ee7e585553d4791667c103302330d391c3283d91005aa761b0700294eeabb42db7fd785593bfb4340f02f7a5c6e731a414beca8c2a353019da778ede60a0d5946c741f52889c9d4586914dac96aaab56b40a6e31a4f68be097c02ee5d34d0a9d5dbe180b9cda4927a85735249a1c76c7891a9afce600f6b803f95fedbdded04cdaf45be821558547122767840c32d219b049cad102a61348ede593d0f1ba6357633fa56673eeabedba3f23bea7740cc2cb30039c3c4dc8fb56f5f29ecb78a9248b813242f9a9006c9394e9ddeb964be7c0fde551263125e711bf85af5254f37e285f132d79dad336074f993201b4a61c83d68ddb07834d58fc3b24d4839c2b72e8d810ab699da0147c81c4a629fd5e2b07a8e0b4b8b96dad3c1b92a4db94c4f7aff1d924817ddd2c17a8d0c5db4215ec5a57fde18238d3d14c48fd1e5902a3cc4709cc31d8404351c9abee0be02b69e5e30c56d6748f22fbc1a2a6b0a60fe212c365bc36995d83ad82fcc009ec899edad9eb8a8e68eefdea0fe8eec10b44ba441cef5d4bbc356d170801ea53e787c6bec28aee13056b6c4c6a3df9dc50998fc4a1f7372427e6ec81867c22568240650f333a239a3d92eb9a4b7b90c9839b03b07c54d73342cd62963fdfc38839df9f7a66ef1501faf8402ed4c4a744446b00499647fb81804762a47084e2b8195207169e7e206dd5025f74e4cfca20f98ccc0f1e37a77000881475150448ab17f322856fca47816185f2ca561d5594fc6e4e58e2a6267eafe98c806967977babb4f2be2b81d368e5edbac30d30ecf70d313c362bbf1b651c52eaba20b98d5a9cc8265fc2b6fac637dc9ef67268e3d98b96f2813166850f05f7381ca3768b8bfa5f6f43814cade12ee8eceb4f9bc156fcefd721360ac1257120e35b0bda77610ce86586c6ba2763a906301b065e1bbc225f5594f630079e4e14094f9b31af6b1f55e79cd8d8e2b6083958a7504c0788b7ae2315e6e72527535f31749160fe4e1e41cbd6da188dc1ee145ebdffc33a273df3b573459c2a3c6a468953f08ac809fab19764eafd595a714b328b5f08468dd1daf49f0bedbd3f4ab6aa84b922a821a8bc163e9bfa02d36afbef7d8f412b61bfbd130beff46ec549ce2563403ccbb329efb4b4ce796228c88e8a01e29a68c61b2fed0d4310d4841e5fbb704fb10b5a7fe3279e6c83fc9656eda5503bce08229c6ee106b51e80610d1e8079deb41b808a5cbd1dd421d4b9529e23de3c60a1bed52b3d3e050c9375c460063c8346cefa02980bd7d67151aa7f824ee20ce7f665c74d2229f171329e81024cb0ad88d28b11106a73aa018edf3a6103bbecbd92aea62db2eb07f762d9f759691d364608b8b6eb6166606708b470061b2b077cc990c86cb5decc3c60d25944b4c6d92e784e9ec287537086c4f0a74156e375fb3cb7be0d67bf6bf2d93b1f30b1427b5df21d0a248e8bfc97f73a12179ad0ea1d099740288a21d6a864c7be9d447a2e690dc1c02732f1b9a6f454d642a27c1ee88708476a8854f2e28a67fe80997f100de0238c19b09bf085cbcc4706fd480ac4aafcbbcc28747998ad84ed92c16feaf491747c52e3b5bb5fbc15f6cbf99568043081f514b30cd225bde7a06c839fea5c0b53a05d5fdad574ac0380f3472436edfbe6ba7e1cb157abd54cae79fc26e3c19a824dc239861549783d11121ad86807c9216f1d95413d54f0b1697f9e4001e5fa2cf37b2758f7ec1d751da168319622d005b3ccd980900111bd37739ff88cc8f16b94c51becfd7a4a837bbf1442aef8a2a05764cd226625155870178f2d085cc00955d613d804872bb7677be4b0003b8ac5297a6ec2564c80d3f8e2c3240ec71bdffe6e793d22b15d479d4502bb6372fdf1b5da7ce48a93e870132ca30c61471d37a808b00ed0b5a0bdc7db860346af3986595bdaf0373f4a1dd11663fec481977e654cb6d2cb0794a66973ec2fe68dc8ebf7b338a153d1b83cfc92adafcd401774fc93a64b6cd142e89ebe5bc5f6fb947b20829ef8cd2e4be31f0ba9ae463b41fd4bfa9bc4f888f52eb70799d4c4ac025434e68ea098c3f1730797868a8ac37c263a982022706ea0aad7699c972d3647707401b788c58efed45e1b0cc39c120786402345e7e0f311b1a11992e38aa0f7c00be001287a3c923658e92dcd891d25e624670c1851f6b0f490aebc9ee7845fefb1b0f755b9a8c7498c33922dc3b2374d40287874cc914108f76e2bbe4616587251a7399dfd7be1830e37ff41562e4b1a132908384c26cacdb6887bfd7f6eb8e889f1a9e8b2abf73933ff20d30a022a934ce29994d4ec2b486246f226a66be6481b6d64295c27bfe374c9b10dd10a49ebd74b1f383b8d86b51d3d85ee80228d1bc74b700437371c390210de594bf25774f0d66a2920b7c1baff74670fc65961cb1dea83daf2c7920afc4aad1844ab3f152226034d83c834c698e5a476472fdcf3d58a306a771177b7cfa5580365b18e948130f7c248f5ef0a888ba141f3be2afab5748f36f21b5cfd98b58763c91aea1bab0aa6f50370ae6061d3cb8b6a9b9f3f208cabdd568b542228743002d4b8370bdfcfb9bd53673978f968863e2bbf6a4070683cdf16b446d6e79da8219a71851619a3f1d501e9ba196f9a8e34fcc7bcdf34b327e55a921298f7ede9fdc23a4cb55e088bc137529dfd7b2a04d9b315467e61fc2ecdd7fd474671ecd47099c2853c4328513ad5f161f9af6ee022110e5e7de5e875cd17fd3f6f3020d8a5e65771a7ed2d239038675d400d100dec62e98af0995eb789f3f906b504c487d30190ea4df9135753e354d019ec33921862752d6eab007ad3ef764e85f7f4b940166d30e6b44d359399622e1823cf5f99a1c319946e2b63aef65d59b560538ed2fd5f00380505b30064ec7e772c04a2444aede21f4570f9e5776ad99ee10e91ee2c0619818d8b0df714b27949699c25f2edc3743de8cc7231fe73f20a4a870d092b17f8cfcd86b861b1ba2f36d370b2f7acf02cc43c58cd8363c738098859afe15145a90d19ddd3ea9307666767e141118d0e4ec214c81f3689d1e39bcd0cfd954d0b336e03a57e153b704aa81deab77e73e966b1583a49131f2d45f63972b6502dac6cb0645e87b49550907521bf7db626e439fcf12256c083553e5d3744f36e636ab5ba397cca46484f72bae4b3d7f28b3d445e5d51c6926b9436bb7d69b8cd7533587151dfb5e44477db78fa0e05eefad380bcca4b4701e31c8e7c640ba03e2ba51e15fb8a4b7e8d08e8a3bf4eaa1863a9c5658dde6682cc3ad23216030ac3ed1df97db41a7f414126618cb607bfbb26235da8db98b15b4fa0f14c6690bd681c9f47eede6472993f0f5c61c007b5691c66b3654ff7cfe66abc2b8117ac93db3717fcb2a75f0885409f45276f2c3bb4156104306142be11f373b9b9fcc8db5d548802e3387b5098092cf61c2dc14c40a474180314b869a253a530a1bacdea468068e0fac111428a4605729e6755d87fb0f75c43da0aec9ac033b40b9c01880ebef82fa4450694f5eb8a37a44ac7b1a96ed4919d6098c702deb020b45e0df182cfdf4057ed2ccbfae2aa2713023d78ac556278f8cec1977cf00304c529ac29f24a53cbd7d952164467d8e871d869cad88405e54398cbc5bee5ff346fbced0c59413168c3fe19c1cd46327de5200fb63b429c376340838287b767842d851a126e77efed1efb15f880e109b531e0d8dedbfbec236106b2f367cbb66c79b038e6a228f6552c8e39f2c1a0c1dec8bd1392a2868f0c558c4619abb927c1c9497b61f4166a3de04818e435ff4f44e84fed10515745ae21959eab42a7843728a89b382c02f29db5993f749d5c7c8a7e48dd454c8c1b922295f67cbff24a26dca9410caf1edc4e55474b7357b4e1f2803cd91428e4fd3830c97a70c34e9505f39a73b39b78f8c0f768b52906af55146ff854d0a7428f079b57fe107f9ab2c065d10091fbb1c00fc2a78e7ae1b953f1eddfa8256ede592af32b5e56d073f9f690d8154d350e38910336186082c36e7111c5d15e838865dcb478a8a19d3dd6b29730fb822407288158f8e7992fdfea59edb5d6c4ed9ade49efcb7016fbfbeae2a4d67feaca92bda4dba6a87d1ab0ad48d6a24e108a73842aada4833a10be7c04c6e00c7275d536265902b514081e627090bddc30668c9db6d4dbdee30f629eac081a9621464d63696f87071f8fa5dd0000000000000000000000000000000000000000071014171e23";

    fn hx(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    #[test]
    fn kat_acvp_keygen() {
        use crate::hash::sha3::sha3_256;
        let seed: [u8; SEED_BYTES] = hx(KAT_KG_SEED).try_into().unwrap();
        let (pk, sk) = ml_dsa_65_keygen(&seed);
        assert_eq!(hex::encode(sha3_256(&pk.0)), KAT_KG_PK_SHA3, "pk mismatch");
        assert_eq!(hex::encode(sha3_256(&sk.0)), KAT_KG_SK_SHA3, "sk mismatch");
    }

    #[test]
    fn kat_acvp_sign_deterministic() {
        use crate::hash::sha3::sha3_256;
        let sk = MlDsaSecretKey(hx(KAT_SIG_SK));
        let sig = ml_dsa_65_sign(&sk, &hx(KAT_SIG_MSG), &[0u8; SEED_BYTES]);
        assert_eq!(
            hex::encode(sha3_256(&sig)),
            KAT_SIG_SHA3,
            "signature mismatch"
        );
    }

    #[test]
    fn kat_acvp_verify() {
        let ok = |pk: &str, msg: &str, sig: &str| {
            ml_dsa_65_verify(&MlDsaPublicKey(hx(pk)), &hx(msg), &hx(sig))
        };
        assert!(ok(KAT_SV_VALID_PK, KAT_SV_VALID_MSG, KAT_SV_VALID_SIG));
        // Modified hint: exercises the HintBitUnpack canonicity rules (FIPS 204
        // Algorithm 21) that a random bit flip essentially never reaches.
        assert!(!ok(
            KAT_SV_BADHINT_PK,
            KAT_SV_BADHINT_MSG,
            KAT_SV_BADHINT_SIG
        ));
        // Modified commitment hash.
        assert!(!ok(
            KAT_SV_BADCOMM_PK,
            KAT_SV_BADCOMM_MSG,
            KAT_SV_BADCOMM_SIG
        ));
    }
}
