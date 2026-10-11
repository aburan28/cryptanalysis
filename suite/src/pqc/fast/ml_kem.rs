//! **ML-KEM** (FIPS 203) written for speed.
//!
//! Byte-for-byte interchangeable with [`crate::pqc::ml_kem`], which stays the
//! readable reference and is validated against the NIST ACVP vectors. The tests
//! at the bottom of this file hold the two implementations against each other
//! on every parameter set, so the ACVP validation carries over.
//!
//! # Where the time was going
//!
//! Measured on the reference implementation, ML-KEM-768 key generation cost
//! 337 kilocycles, of which hashing was 40. The other 88% was ring arithmetic,
//! and almost all of that came from two lines rather than from the modular
//! reductions one would suspect:
//!
//! * `ntt` and `ntt_inv` each began by calling `zetas()`, which rebuilds all
//!   128 twiddle factors by square-and-multiply. That is roughly 1800 modular
//!   multiplications to set up a transform that only performs 1024.
//! * `multiply_ntts` called `zeta_pow(2·BitRev7(i) + 1)` inside its loop, so a
//!   single pointwise product ran 128 modular exponentiations.
//!
//! Both are pure setup that does not depend on the input, so this module keeps
//! them in `const` tables computed at compile time.
//!
//! # What else changed
//!
//! * **Signed coefficients and Montgomery multiplication.** Coefficients are
//!   `i16` in `(-q, q)` rather than `u16` in `[0, q)`, and products go through
//!   `montgomery_reduce`, which is two multiplications and a shift. The
//!   reference reduced with `% q` on `u32`, which the compiler turns into a
//!   multiply-shift pair as well, so this is worth less than it looks; the
//!   gain is that intermediate values need reducing far less often.
//! * **Streaming rejection sampling.** `sample_ntt` needs an unpredictable
//!   number of SHAKE128 bytes. The reference asked for a fixed length and, when
//!   that ran short, re-ran the whole sponge with a doubled request, repeating
//!   every permutation it had already done. This one squeezes another block
//!   from the same state.
//! * **No allocation in the hot paths.** Polynomials and vectors are fixed
//!   arrays. The reference returned `Vec` from `byte_encode`, `prf` and the
//!   polynomial operators, so a single key generation made hundreds of
//!   short-lived heap allocations.
//!
//! # Domains
//!
//! The convention is the one the pq-crystals reference uses, because it is the
//! one whose constant factors are known to work out:
//!
//! * twiddle factors are stored in Montgomery form, so `fqmul(x, zeta)` is the
//!   true product `x·ζ` rather than `x·ζ/2^16`;
//! * `ntt` therefore computes the true transform;
//! * `basemul` multiplies two ordinary values and so produces the true product
//!   divided by `2^16`;
//! * `invntt` folds in `2^16/128`, so it produces its result multiplied by
//!   `2^16`, which exactly cancels what `basemul` left behind.
//!
//! The one place this does not cancel is `t̂ = Â∘ŝ + ê`, where the matrix
//! product stays in the NTT domain and never meets an `invntt`. There the
//! product is scaled back up with `poly_tomont` before `ê` is added. Getting
//! this wrong produces output that is wrong by a constant factor, which the
//! differential tests catch immediately.
//!
//! # Not constant-time
//!
//! As with the rest of this library: the rejection samplers branch on their
//! output and the compressions are not written to avoid data-dependent timing.
//! Do not use this for anything real. See `SECURITY.md`.

use super::keccak::{sha3_256, sha3_512_2, shake256_2_into, Sponge, SHAKE128_RATE};
use crate::pqc::ml_kem::{MlKemDecapsKey, MlKemEncapsKey, MlKemParams, SHARED_SECRET_BYTES};
use crate::utils::random::random_bytes;
use subtle::{ConditionallySelectable, ConstantTimeEq};

// ── ring parameters ──────────────────────────────────────────────────────────

/// Polynomial degree: `R_q = Z_q[X]/(X^256 + 1)`.
const N: usize = 256;
/// Coefficient modulus.
const Q: i16 = 3329;
const QI: i32 = Q as i32;
/// `q^-1 mod 2^16`, as the `i16` it is reinterpreted as (62209 − 65536).
const QINV: i16 = -3327;
/// `ζ = 17` generates the 256th roots of unity mod q.
const ZETA: i32 = 17;
/// The largest module rank over the three parameter sets, so that vectors can
/// be fixed-size arrays instead of `Vec`.
const KMAX: usize = 4;

// ── Montgomery and Barrett reduction ─────────────────────────────────────────

/// `a · 2^-16 mod q`, as a value in `(-q, q)`.
///
/// Requires `|a| < q · 2^15`, which every caller here satisfies because both
/// factors of the product are bounded by `q` in absolute value.
#[inline(always)]
const fn montgomery_reduce(a: i32) -> i16 {
    let t = (a as i16).wrapping_mul(QINV);
    ((a - (t as i32) * QI) >> 16) as i16
}

/// `a mod q` as a value in `[-(q-1)/2, (q-1)/2]`, for any `i16`.
#[inline(always)]
const fn barrett_reduce(a: i16) -> i16 {
    // v = round(2^26 / q); the +2^25 makes the shift round to nearest.
    const V: i32 = ((1i32 << 26) / QI) + 1;
    let t = ((V * a as i32 + (1 << 25)) >> 26) as i16;
    a - t.wrapping_mul(Q)
}

/// The true product of two ordinary values, divided by `2^16`. With a
/// Montgomery-form second argument this is the true product.
#[inline(always)]
const fn fqmul(a: i16, b: i16) -> i16 {
    montgomery_reduce(a as i32 * b as i32)
}

/// Map a value in `(-q, q)` to its representative in `[0, q)`.
#[inline(always)]
const fn to_canonical(a: i16) -> u16 {
    (a + ((a >> 15) & Q)) as u16
}

// ── compile-time twiddle tables ──────────────────────────────────────────────

/// `base^exp mod q`, for table construction only.
const fn pow_mod(base: i32, exp: u32) -> i32 {
    let mut r: i64 = 1;
    let mut b: i64 = (base % QI) as i64;
    let mut e = exp;
    while e > 0 {
        if e & 1 == 1 {
            r = r * b % QI as i64;
        }
        b = b * b % QI as i64;
        e >>= 1;
    }
    r as i32
}

/// `v · 2^16 mod q`, as a signed value in `[-(q-1)/2, (q-1)/2]`.
const fn to_mont_signed(v: i32) -> i16 {
    let m = ((v as i64) * 65536 % QI as i64) as i32;
    let m = if m > QI / 2 { m - QI } else { m };
    m as i16
}

/// Reverse the low seven bits (FIPS 203 §2.3 `BitRev7`).
const fn bitrev7(x: usize) -> usize {
    let mut r = 0;
    let mut b = 0;
    while b < 7 {
        r |= ((x >> b) & 1) << (6 - b);
        b += 1;
    }
    r
}

/// `ζ^BitRev7(i)` in Montgomery form: the twiddles the seven NTT layers use.
const fn zetas_table() -> [i16; 128] {
    let mut z = [0i16; 128];
    let mut i = 0;
    while i < 128 {
        z[i] = to_mont_signed(pow_mod(ZETA, bitrev7(i) as u32));
        i += 1;
    }
    z
}

/// `ζ^(2·BitRev7(i)+1)` in Montgomery form: the modulus of the i-th quadratic
/// residue class, needed once per `basemul` pair.
///
/// The reference recomputed this by modular exponentiation inside the pointwise
/// multiplication loop, 128 times per product.
const fn basemul_zetas_table() -> [i16; 128] {
    let mut z = [0i16; 128];
    let mut i = 0;
    while i < 128 {
        z[i] = to_mont_signed(pow_mod(ZETA, 2 * bitrev7(i) as u32 + 1));
        i += 1;
    }
    z
}

static ZETAS: [i16; 128] = zetas_table();
static BASEMUL_ZETAS: [i16; 128] = basemul_zetas_table();

/// `2^32 mod q`: multiplying by this through `fqmul` scales by `2^16`.
const MONT2: i16 = ((1i64 << 32) % QI as i64) as i16;
/// `2^32 / 128 mod q`: the inverse NTT's final scaling, which folds the `1/128`
/// together with the move into the Montgomery domain.
const INVNTT_F: i16 = 1441;

// ── polynomials ──────────────────────────────────────────────────────────────

/// A polynomial of `R_q`, coefficients in `(-q, q)` unless stated otherwise.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
struct Poly([i16; N]);

impl Poly {
    const fn zero() -> Self {
        Poly([0; N])
    }
}

#[inline]
fn poly_add(r: &mut Poly, a: &Poly) {
    for i in 0..N {
        r.0[i] = r.0[i].wrapping_add(a.0[i]);
    }
}

#[inline]
fn poly_sub(r: &mut Poly, a: &Poly) {
    for i in 0..N {
        r.0[i] = r.0[i].wrapping_sub(a.0[i]);
    }
}

#[inline]
fn poly_reduce(r: &mut Poly) {
    for c in r.0.iter_mut() {
        *c = barrett_reduce(*c);
    }
}

/// Scale by `2^16`, cancelling the factor `basemul` divides out.
#[inline]
fn poly_tomont(r: &mut Poly) {
    for c in r.0.iter_mut() {
        *c = fqmul(*c, MONT2);
    }
}

/// Forward NTT, in place. Input coefficients bounded by `q` in absolute value;
/// output bounded by `8q` before the final reduction, which is applied here.
fn ntt(r: &mut Poly) {
    let mut k = 1usize;
    let mut len = 128usize;
    while len >= 2 {
        let mut start = 0usize;
        while start < N {
            let zeta = ZETAS[k];
            k += 1;
            for j in start..start + len {
                let t = fqmul(zeta, r.0[j + len]);
                r.0[j + len] = r.0[j] - t;
                r.0[j] += t;
            }
            start += 2 * len;
        }
        len >>= 1;
    }
    poly_reduce(r);
}

/// Inverse NTT, in place, including the `1/128` and the move into the
/// Montgomery domain (see the domain note in the module docs).
fn invntt(r: &mut Poly) {
    let mut k = 127usize;
    let mut len = 2usize;
    while len <= 128 {
        let mut start = 0usize;
        while start < N {
            let zeta = ZETAS[k];
            k = k.wrapping_sub(1);
            for j in start..start + len {
                let t = r.0[j];
                // Gentleman–Sande: the sum needs reducing, the difference does
                // not because fqmul brings it back into (-q, q).
                r.0[j] = barrett_reduce(t + r.0[j + len]);
                r.0[j + len] -= t;
                r.0[j + len] = fqmul(zeta, r.0[j + len]);
            }
            start += 2 * len;
        }
        len <<= 1;
    }
    for c in r.0.iter_mut() {
        *c = fqmul(*c, INVNTT_F);
    }
}

/// One pair of the pointwise product: multiply two linear polynomials modulo
/// `X² − γ`.
#[inline(always)]
fn basemul(r: &mut [i16], a: &[i16], b: &[i16], gamma: i16) {
    r[0] = fqmul(fqmul(a[1], b[1]), gamma) + fqmul(a[0], b[0]);
    r[1] = fqmul(a[0], b[1]) + fqmul(a[1], b[0]);
}

/// `r += a ∘ b` in the NTT domain.
fn poly_basemul_acc(r: &mut Poly, a: &Poly, b: &Poly) {
    let mut t = [0i16; 2];
    for i in 0..128 {
        basemul(
            &mut t,
            &a.0[2 * i..2 * i + 2],
            &b.0[2 * i..2 * i + 2],
            BASEMUL_ZETAS[i],
        );
        r.0[2 * i] = r.0[2 * i].wrapping_add(t[0]);
        r.0[2 * i + 1] = r.0[2 * i + 1].wrapping_add(t[1]);
    }
}

// ── sampling ─────────────────────────────────────────────────────────────────

/// `SampleNTT`: rejection-sample a uniform NTT-domain polynomial from
/// SHAKE128(ρ ‖ j ‖ i).
///
/// The sponge is squeezed a block at a time and continues where it left off,
/// so an unlucky draw costs one more permutation rather than a restart.
fn sample_ntt(rho: &[u8; 32], j: u8, i: u8) -> Poly {
    let mut xof = Sponge::<SHAKE128_RATE>::new();
    xof.absorb(rho);
    xof.absorb(&[j, i]);
    xof.finalize(0x1f);

    let mut buf = [0u8; SHAKE128_RATE];
    let mut f = Poly::zero();
    let mut count = 0usize;
    while count < N {
        xof.squeeze(&mut buf);
        let mut pos = 0usize;
        while pos + 3 <= SHAKE128_RATE && count < N {
            let c0 = buf[pos] as u16;
            let c1 = buf[pos + 1] as u16;
            let c2 = buf[pos + 2] as u16;
            pos += 3;
            let d1 = c0 | ((c1 & 0x0f) << 8);
            let d2 = (c1 >> 4) | (c2 << 4);
            if d1 < Q as u16 {
                f.0[count] = d1 as i16;
                count += 1;
            }
            if d2 < Q as u16 && count < N {
                f.0[count] = d2 as i16;
                count += 1;
            }
        }
    }
    f
}

/// `SamplePolyCBD_2` from 128 bytes: each coefficient is a difference of two
/// two-bit popcounts, computed four coefficients at a time out of one word.
fn cbd2(buf: &[u8; 128]) -> Poly {
    let mut f = Poly::zero();
    for i in 0..N / 8 {
        let t = u32::from_le_bytes([buf[4 * i], buf[4 * i + 1], buf[4 * i + 2], buf[4 * i + 3]]);
        // Sum adjacent bit pairs in parallel across the word.
        let d = (t & 0x5555_5555) + ((t >> 1) & 0x5555_5555);
        for j in 0..8 {
            let a = ((d >> (4 * j)) & 0x3) as i16;
            let b = ((d >> (4 * j + 2)) & 0x3) as i16;
            f.0[8 * i + j] = a - b;
        }
    }
    f
}

/// `SamplePolyCBD_3` from 192 bytes: three-bit popcounts, four coefficients per
/// three bytes.
fn cbd3(buf: &[u8; 192]) -> Poly {
    let mut f = Poly::zero();
    for i in 0..N / 4 {
        let t = u32::from_le_bytes([buf[3 * i], buf[3 * i + 1], buf[3 * i + 2], 0]);
        let d = (t & 0x0024_9249) + ((t >> 1) & 0x0024_9249) + ((t >> 2) & 0x0024_9249);
        for j in 0..4 {
            let a = ((d >> (6 * j)) & 0x7) as i16;
            let b = ((d >> (6 * j + 3)) & 0x7) as i16;
            f.0[4 * i + j] = a - b;
        }
    }
    f
}

/// `SamplePolyCBD_η(PRF_η(s, b))`.
fn sample_cbd_prf(s: &[u8; 32], b: u8, eta: usize) -> Poly {
    if eta == 2 {
        let mut buf = [0u8; 128];
        shake256_2_into(&mut buf, s, &[b]);
        cbd2(&buf)
    } else {
        debug_assert_eq!(eta, 3);
        let mut buf = [0u8; 192];
        shake256_2_into(&mut buf, s, &[b]);
        cbd3(&buf)
    }
}

// ── compression and byte encoding ────────────────────────────────────────────

/// `Compress_d(x)` for canonical `x`, exactly as FIPS 203 §4.2.1 defines it.
#[inline(always)]
fn compress(x: u16, d: usize) -> u16 {
    ((((x as u32) << d) + (Q as u32) / 2) / (Q as u32)) as u16 & ((1u16 << d) - 1)
}

/// `Decompress_d(y)`.
#[inline(always)]
fn decompress(y: u16, d: usize) -> i16 {
    (((y as u32) * (Q as u32) + (1 << (d - 1))) >> d) as i16
}

/// `ByteEncode_d` of a polynomial whose coefficients are already canonical.
///
/// A 64-bit accumulator rather than a bit at a time: at d = 12 the bitwise
/// version ran 3072 iterations, each with a division and a shift, to write 384
/// bytes.  Since d ≤ 12 at least five coefficients always fit in the
/// accumulator, so it never has to spill mid-coefficient.
fn byte_encode_into(out: &mut [u8], f: &Poly, d: usize) {
    debug_assert_eq!(out.len(), 32 * d);
    debug_assert!(d <= 12);
    let mask = (1u64 << d) - 1;
    let mut acc = 0u64;
    let mut nbits = 0usize;
    let mut o = 0usize;
    for &c in f.0.iter() {
        acc |= ((c as u16 as u64) & mask) << nbits;
        nbits += d;
        while nbits >= 8 {
            out[o] = acc as u8;
            o += 1;
            acc >>= 8;
            nbits -= 8;
        }
    }
    debug_assert_eq!(nbits, 0);
    debug_assert_eq!(o, out.len());
}

/// `ByteEncode_d` of a polynomial in `(-q, q)`, canonicalising first.
fn poly_encode_canonical(out: &mut [u8], f: &Poly, d: usize) {
    let mut c = Poly::zero();
    for i in 0..N {
        c.0[i] = to_canonical(barrett_reduce(f.0[i])) as i16;
    }
    byte_encode_into(out, &c, d);
}

/// `ByteDecode_d`. For `d = 12` the values are reduced mod q, which makes the
/// decode lossy exactly as the reference documents; callers must not treat a
/// successful decode as proof that the input was canonical.
fn byte_decode(bytes: &[u8], d: usize) -> Poly {
    debug_assert_eq!(bytes.len(), 32 * d);
    debug_assert!(d <= 12);
    let mask = (1u64 << d) - 1;
    let mut f = Poly::zero();
    let mut acc = 0u64;
    let mut nbits = 0usize;
    let mut i = 0usize;
    for out in f.0.iter_mut() {
        while nbits < d {
            acc |= (bytes[i] as u64) << nbits;
            i += 1;
            nbits += 8;
        }
        let c = (acc & mask) as u32;
        acc >>= d;
        nbits -= d;
        *out = if d == 12 {
            (c % Q as u32) as i16
        } else {
            c as i16
        };
    }
    f
}

fn poly_compress_encode(out: &mut [u8], f: &Poly, d: usize) {
    let mut c = Poly::zero();
    for i in 0..N {
        c.0[i] = compress(to_canonical(barrett_reduce(f.0[i])), d) as i16;
    }
    byte_encode_into(out, &c, d);
}

fn poly_decode_decompress(bytes: &[u8], d: usize) -> Poly {
    let f = byte_decode(bytes, d);
    let mut r = Poly::zero();
    for i in 0..N {
        r.0[i] = decompress(f.0[i] as u16, d);
    }
    r
}

// ── K-PKE ────────────────────────────────────────────────────────────────────

/// Expand ρ into the k×k matrix `Â` in NTT form. Entry `(i, j)` comes from
/// `XOF(ρ ‖ j ‖ i)`: the column index goes first, as in the final standard.
fn expand_matrix(rho: &[u8; 32], k: usize, a: &mut [[Poly; KMAX]; KMAX]) {
    for i in 0..k {
        for j in 0..k {
            a[i][j] = sample_ntt(rho, j as u8, i as u8);
        }
    }
}

fn kpke_keygen(p: &MlKemParams, d: &[u8; 32], ek: &mut [u8], dk: &mut [u8]) {
    let k = p.k;
    let g = sha3_512_2(d, &[k as u8]);
    let mut rho = [0u8; 32];
    let mut sigma = [0u8; 32];
    rho.copy_from_slice(&g[..32]);
    sigma.copy_from_slice(&g[32..]);

    let mut a = [[Poly::zero(); KMAX]; KMAX];
    expand_matrix(&rho, k, &mut a);

    let mut s_hat = [Poly::zero(); KMAX];
    let mut e_hat = [Poly::zero(); KMAX];
    let mut n = 0u8;
    for item in s_hat.iter_mut().take(k) {
        *item = sample_cbd_prf(&sigma, n, p.eta1);
        n += 1;
        ntt(item);
    }
    for item in e_hat.iter_mut().take(k) {
        *item = sample_cbd_prf(&sigma, n, p.eta1);
        n += 1;
        ntt(item);
    }

    // t̂ = Â∘ŝ + ê. The accumulated product is short by 2^16 (see the domain
    // note), so it is scaled back before ê joins it.
    for i in 0..k {
        let mut acc = Poly::zero();
        for j in 0..k {
            poly_basemul_acc(&mut acc, &a[i][j], &s_hat[j]);
        }
        poly_reduce(&mut acc);
        poly_tomont(&mut acc);
        poly_add(&mut acc, &e_hat[i]);
        poly_reduce(&mut acc);
        poly_encode_canonical(&mut ek[384 * i..384 * (i + 1)], &acc, 12);
    }
    ek[384 * k..384 * k + 32].copy_from_slice(&rho);

    for i in 0..k {
        poly_encode_canonical(&mut dk[384 * i..384 * (i + 1)], &s_hat[i], 12);
    }
}

fn kpke_encrypt(p: &MlKemParams, ek: &[u8], m: &[u8; 32], r: &[u8; 32], c: &mut [u8]) {
    let k = p.k;
    let mut t_hat = [Poly::zero(); KMAX];
    for (i, item) in t_hat.iter_mut().enumerate().take(k) {
        *item = byte_decode(&ek[384 * i..384 * (i + 1)], 12);
    }
    let mut rho = [0u8; 32];
    rho.copy_from_slice(&ek[384 * k..384 * k + 32]);

    let mut a = [[Poly::zero(); KMAX]; KMAX];
    expand_matrix(&rho, k, &mut a);

    let mut y_hat = [Poly::zero(); KMAX];
    let mut e1 = [Poly::zero(); KMAX];
    let mut n = 0u8;
    for item in y_hat.iter_mut().take(k) {
        *item = sample_cbd_prf(r, n, p.eta1);
        n += 1;
        ntt(item);
    }
    for item in e1.iter_mut().take(k) {
        *item = sample_cbd_prf(r, n, p.eta2);
        n += 1;
    }
    let e2 = sample_cbd_prf(r, n, p.eta2);

    // u = NTT^-1(Â^T ∘ ŷ) + e1
    let du_bytes = 32 * p.du;
    for i in 0..k {
        let mut acc = Poly::zero();
        for j in 0..k {
            poly_basemul_acc(&mut acc, &a[j][i], &y_hat[j]);
        }
        poly_reduce(&mut acc);
        invntt(&mut acc);
        poly_add(&mut acc, &e1[i]);
        poly_reduce(&mut acc);
        poly_compress_encode(&mut c[du_bytes * i..du_bytes * (i + 1)], &acc, p.du);
    }

    // v = NTT^-1(t̂^T ∘ ŷ) + e2 + Decompress_1(m)
    let mut v = Poly::zero();
    for j in 0..k {
        poly_basemul_acc(&mut v, &t_hat[j], &y_hat[j]);
    }
    poly_reduce(&mut v);
    invntt(&mut v);
    poly_add(&mut v, &e2);
    let mu = poly_decode_decompress(m, 1);
    poly_add(&mut v, &mu);
    poly_reduce(&mut v);
    poly_compress_encode(&mut c[du_bytes * k..], &v, p.dv);
}

fn kpke_decrypt(p: &MlKemParams, dk: &[u8], c: &[u8]) -> [u8; 32] {
    let k = p.k;
    let du_bytes = 32 * p.du;
    let mut w = Poly::zero();
    for i in 0..k {
        let mut u = poly_decode_decompress(&c[du_bytes * i..du_bytes * (i + 1)], p.du);
        ntt(&mut u);
        let s = byte_decode(&dk[384 * i..384 * (i + 1)], 12);
        poly_basemul_acc(&mut w, &s, &u);
    }
    poly_reduce(&mut w);
    invntt(&mut w);

    let mut v = poly_decode_decompress(&c[du_bytes * k..], p.dv);
    poly_sub(&mut v, &w);
    poly_reduce(&mut v);

    let mut out = [0u8; 32];
    poly_compress_encode(&mut out, &v, 1);
    out
}

// ── ML-KEM ───────────────────────────────────────────────────────────────────

/// `ML-KEM.KeyGen_internal(d, z)`. Deterministic; the seeds are the caller's.
pub fn ml_kem_keygen_internal(
    p: &MlKemParams,
    d: &[u8; 32],
    z: &[u8; 32],
) -> (MlKemEncapsKey, MlKemDecapsKey) {
    let k = p.k;
    let mut ek = vec![0u8; p.ek_len()];
    let mut dk_pke = vec![0u8; 384 * k];
    kpke_keygen(p, d, &mut ek, &mut dk_pke);

    let mut dk = Vec::with_capacity(p.dk_len());
    dk.extend_from_slice(&dk_pke);
    dk.extend_from_slice(&ek);
    dk.extend_from_slice(&sha3_256(&ek));
    dk.extend_from_slice(z);
    (MlKemEncapsKey(ek), MlKemDecapsKey(dk))
}

/// `ML-KEM.KeyGen`.
pub fn ml_kem_keygen(p: &MlKemParams) -> (MlKemEncapsKey, MlKemDecapsKey) {
    let mut d = [0u8; 32];
    let mut z = [0u8; 32];
    random_bytes(&mut d);
    random_bytes(&mut z);
    ml_kem_keygen_internal(p, &d, &z)
}

/// `ML-KEM.Encaps_internal(ek, m)`. Deterministic; the message is the caller's.
pub fn ml_kem_encaps_internal(
    p: &MlKemParams,
    ek: &MlKemEncapsKey,
    m: &[u8; 32],
) -> Option<(Vec<u8>, [u8; SHARED_SECRET_BYTES])> {
    if ek.0.len() != p.ek_len() {
        return None;
    }
    let g = sha3_512_2(m, &sha3_256(&ek.0));
    let mut key = [0u8; 32];
    let mut r = [0u8; 32];
    key.copy_from_slice(&g[..32]);
    r.copy_from_slice(&g[32..]);

    let mut c = vec![0u8; p.ct_len()];
    kpke_encrypt(p, &ek.0, m, &r, &mut c);
    Some((c, key))
}

/// `ML-KEM.Encaps`.
pub fn ml_kem_encaps(
    p: &MlKemParams,
    ek: &MlKemEncapsKey,
) -> Option<(Vec<u8>, [u8; SHARED_SECRET_BYTES])> {
    let mut m = [0u8; 32];
    random_bytes(&mut m);
    ml_kem_encaps_internal(p, ek, &m)
}

/// `ML-KEM.Decaps`. Returns `None` only for malformed input lengths; a
/// well-formed but forged ciphertext yields the implicit-rejection secret
/// `J(z ‖ c)`, never an error.
pub fn ml_kem_decaps(
    p: &MlKemParams,
    dk: &MlKemDecapsKey,
    c: &[u8],
) -> Option<[u8; SHARED_SECRET_BYTES]> {
    let k = p.k;
    if dk.0.len() != p.dk_len() || c.len() != p.ct_len() {
        return None;
    }
    let dk_pke = &dk.0[..384 * k];
    let ek = &dk.0[384 * k..768 * k + 32];
    let h = &dk.0[768 * k + 32..768 * k + 64];
    let z = &dk.0[768 * k + 64..];

    let m_prime = kpke_decrypt(p, dk_pke, c);
    let g = sha3_512_2(&m_prime, h);
    let mut k_prime = [0u8; 32];
    let mut r_prime = [0u8; 32];
    k_prime.copy_from_slice(&g[..32]);
    r_prime.copy_from_slice(&g[32..]);

    let mut k_bar = [0u8; 32];
    shake256_2_into(&mut k_bar, z, c);

    let mut c_prime = vec![0u8; p.ct_len()];
    kpke_encrypt(p, ek, &m_prime, &r_prime, &mut c_prime);

    // Implicit rejection: select without branching on the comparison.
    let same = c_prime.ct_eq(c);
    let mut out = [0u8; 32];
    for i in 0..32 {
        out[i] = u8::conditional_select(&k_bar[i], &k_prime[i], same);
    }
    Some(out)
}

/// `ML-KEM.EncapsKeyCheck`: the §7.2 modulus check, by decode/re-encode.
pub fn ml_kem_check_ek(p: &MlKemParams, ek: &[u8]) -> bool {
    if ek.len() != p.ek_len() {
        return false;
    }
    let mut buf = [0u8; 384];
    for i in 0..p.k {
        let f = byte_decode(&ek[384 * i..384 * (i + 1)], 12);
        byte_encode_into(&mut buf, &f, 12);
        if buf[..] != ek[384 * i..384 * (i + 1)] {
            return false;
        }
    }
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::pqc::ml_kem as slow;

    /// A cheap deterministic generator, so a failure names a seed.
    fn seeded(n: usize, tag: u8) -> Vec<u8> {
        let mut out = vec![0u8; n];
        let mut x = 0x9e37_79b9_7f4a_7c15u64 ^ ((tag as u64) << 32);
        for b in out.iter_mut() {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            *b = (x >> 24) as u8;
        }
        out
    }

    fn sets() -> [MlKemParams; 3] {
        [slow::ML_KEM_512, slow::ML_KEM_768, slow::ML_KEM_1024]
    }

    /// The constants the domain argument rests on. If any of these is wrong the
    /// scheme is wrong by a constant factor, which is exactly the bug class the
    /// Montgomery rewrite invites.
    #[test]
    fn montgomery_constants_are_what_they_claim() {
        assert_eq!((Q as i32 * QINV as i32) as i16, 1, "q * q^-1 = 1 mod 2^16");
        assert_eq!(MONT2 as i32, (1i64 << 32).rem_euclid(QI as i64) as i32);
        assert_eq!(
            (INVNTT_F as i64 * 128) % QI as i64,
            MONT2 as i64,
            "invntt scaling folds 1/128 into the Montgomery factor"
        );
        // fqmul with a Montgomery-form constant is the true product.
        for v in [1i32, 2, 17, 1000, 3328] {
            let m = to_mont_signed(v);
            assert_eq!(
                to_canonical(barrett_reduce(fqmul(5, m))) as i32,
                (5 * v).rem_euclid(QI),
                "fqmul(5, mont({v}))"
            );
        }
    }

    /// The twiddle tables, against a schoolbook exponentiation written here so
    /// the check does not share any code with the `const fn` it is checking.
    #[test]
    fn twiddle_tables_hold_the_right_powers() {
        fn pow(mut e: u32) -> u32 {
            let (mut r, mut b) = (1u32, 17u32);
            while e > 0 {
                if e & 1 == 1 {
                    r = r * b % 3329;
                }
                b = b * b % 3329;
                e >>= 1;
            }
            r
        }
        fn brv(x: u32) -> u32 {
            (0..7).fold(0, |r, b| r | (((x >> b) & 1) << (6 - b)))
        }
        for i in 0..128u32 {
            let k = i as usize;
            // fqmul(1, mont(v)) = v, so this reads the table back out of the
            // Montgomery domain without using to_mont_signed again.
            assert_eq!(
                to_canonical(barrett_reduce(fqmul(1, ZETAS[k]))) as u32,
                pow(brv(i)),
                "ZETAS[{i}]"
            );
            assert_eq!(
                to_canonical(barrett_reduce(fqmul(1, BASEMUL_ZETAS[k]))) as u32,
                pow(2 * brv(i) + 1),
                "BASEMUL_ZETAS[{i}]"
            );
        }
    }

    /// NTT then inverse NTT is the identity, which pins the scaling constants
    /// independently of everything above.
    #[test]
    fn ntt_round_trips() {
        for tag in 0..8u8 {
            let bytes = seeded(N * 2, tag);
            let mut f = Poly::zero();
            for i in 0..N {
                f.0[i] = (u16::from_le_bytes([bytes[2 * i], bytes[2 * i + 1]]) % Q as u16) as i16;
            }
            let orig = f;
            ntt(&mut f);
            invntt(&mut f);
            for i in 0..N {
                // invntt leaves the result multiplied by 2^16, so dividing by
                // 2^16 is one fqmul against 1.
                let got = to_canonical(barrett_reduce(fqmul(f.0[i], 1)));
                assert_eq!(got as i16, orig.0[i], "coefficient {i}, tag {tag}");
            }
        }
    }

    /// Keys must be byte-identical to the reference, over many seeds and all
    /// three parameter sets. This is what carries the ACVP validation across.
    #[test]
    fn keygen_matches_the_reference_byte_for_byte() {
        for p in sets() {
            for tag in 0..12u8 {
                let ds = seeded(32, tag);
                let zs = seeded(32, tag ^ 0x5a);
                let d: [u8; 32] = ds.try_into().unwrap();
                let z: [u8; 32] = zs.try_into().unwrap();

                let (ek_f, dk_f) = ml_kem_keygen_internal(&p, &d, &z);
                let (ek_s, dk_s) = slow::ml_kem_keygen_internal(&p, &d, &z);
                assert_eq!(ek_f.0, ek_s.0, "{} ek, tag {tag}", p.name);
                assert_eq!(dk_f.0, dk_s.0, "{} dk, tag {tag}", p.name);
            }
        }
    }

    #[test]
    fn encaps_matches_the_reference_byte_for_byte() {
        for p in sets() {
            for tag in 0..12u8 {
                let d: [u8; 32] = seeded(32, tag).try_into().unwrap();
                let z: [u8; 32] = seeded(32, tag ^ 0x5a).try_into().unwrap();
                let m: [u8; 32] = seeded(32, tag ^ 0xa5).try_into().unwrap();
                let (ek, _) = ml_kem_keygen_internal(&p, &d, &z);

                let (c_f, k_f) = ml_kem_encaps_internal(&p, &ek, &m).unwrap();
                let (c_s, k_s) = slow::ml_kem_encaps_internal(&p, &ek, &m).unwrap();
                assert_eq!(c_f, c_s, "{} ciphertext, tag {tag}", p.name);
                assert_eq!(k_f, k_s, "{} shared secret, tag {tag}", p.name);
            }
        }
    }

    #[test]
    fn decaps_matches_the_reference_including_implicit_rejection() {
        for p in sets() {
            for tag in 0..8u8 {
                let d: [u8; 32] = seeded(32, tag).try_into().unwrap();
                let z: [u8; 32] = seeded(32, tag ^ 0x5a).try_into().unwrap();
                let m: [u8; 32] = seeded(32, tag ^ 0xa5).try_into().unwrap();
                let (ek, dk) = ml_kem_keygen_internal(&p, &d, &z);
                let (c, k) = ml_kem_encaps_internal(&p, &ek, &m).unwrap();

                // Honest ciphertext: both agree, and agree with encapsulation.
                let kf = ml_kem_decaps(&p, &dk, &c).unwrap();
                let ks = slow::ml_kem_decaps(&p, &dk, &c).unwrap();
                assert_eq!(kf, ks, "{} decaps, tag {tag}", p.name);
                assert_eq!(kf, k, "{} round trip, tag {tag}", p.name);

                // Forged ciphertext: the rejection key must match too, which is
                // the part an implementation can get wrong without any test
                // that only checks round trips ever noticing.
                for bit in [0usize, 7, 100, c.len() * 8 - 1] {
                    let mut bad = c.clone();
                    bad[bit / 8] ^= 1 << (bit % 8);
                    let kf = ml_kem_decaps(&p, &dk, &bad).unwrap();
                    let ks = slow::ml_kem_decaps(&p, &dk, &bad).unwrap();
                    assert_eq!(kf, ks, "{} rejection key, tag {tag}, bit {bit}", p.name);
                    assert_ne!(kf, k, "{} rejection differs from real key", p.name);
                }
            }
        }
    }

    #[test]
    fn malformed_lengths_are_rejected() {
        let p = slow::ML_KEM_768;
        let d = [1u8; 32];
        let z = [2u8; 32];
        let (ek, dk) = ml_kem_keygen_internal(&p, &d, &z);

        assert!(ml_kem_decaps(&p, &dk, &vec![0u8; p.ct_len() - 1]).is_none());
        assert!(ml_kem_decaps(&p, &dk, &vec![0u8; p.ct_len() + 1]).is_none());
        let short = MlKemEncapsKey(ek.0[..ek.0.len() - 1].to_vec());
        assert!(ml_kem_encaps_internal(&p, &short, &[0u8; 32]).is_none());
    }

    #[test]
    fn encaps_key_check_matches_the_reference() {
        let p = slow::ML_KEM_768;
        let (ek, _) = ml_kem_keygen_internal(&p, &[3u8; 32], &[4u8; 32]);
        assert!(ml_kem_check_ek(&p, &ek.0));
        assert_eq!(ml_kem_check_ek(&p, &ek.0), slow::ml_kem_check_ek(&p, &ek.0));

        // A non-canonical coefficient: the first 12-bit field set to q itself,
        // which decodes to 0 and so re-encodes differently.  The packing is
        // little-endian by bit, so coefficient 0 is byte 0 plus the LOW nibble
        // of byte 1, and q = 0xd01 splits as 0x01 and 0xd.
        let mut bad = ek.0.clone();
        bad[0] = 0x01;
        bad[1] = (bad[1] & 0xf0) | 0x0d;
        assert!(!ml_kem_check_ek(&p, &bad));
        assert_eq!(ml_kem_check_ek(&p, &bad), slow::ml_kem_check_ek(&p, &bad));

        assert!(!ml_kem_check_ek(&p, &ek.0[..ek.0.len() - 1]));
    }

    /// Randomised end-to-end agreement, without fixed seeds, so the suite is
    /// not only exercising one path through the rejection samplers.
    #[test]
    fn random_round_trips_agree_with_the_reference() {
        for p in sets() {
            for _ in 0..4 {
                let (ek, dk) = ml_kem_keygen(&p);
                let (c, k) = ml_kem_encaps(&p, &ek).unwrap();
                assert_eq!(ml_kem_decaps(&p, &dk, &c).unwrap(), k);
                assert_eq!(slow::ml_kem_decaps(&p, &dk, &c).unwrap(), k);
                assert!(slow::ml_kem_check_ek(&p, &ek.0));
            }
        }
    }
}
