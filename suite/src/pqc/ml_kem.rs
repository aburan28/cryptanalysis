//! **ML-KEM** — Module-Lattice-based Key-Encapsulation Mechanism
//! (NIST FIPS 203, August 2024; formerly CRYSTALS-Kyber).
//!
//! # Background
//! ML-KEM is the NIST post-quantum standard for key encapsulation.
//! Its security reduces to the hardness of the Module Learning With
//! Errors (Module-LWE) problem over the ring
//! `R_q = Z_q[X] / (X^256 + 1)` with `q = 3329 = 13·256 + 1`.  The
//! prime is chosen so that `Z_q` contains a primitive 256-th root of
//! unity (`ζ = 17`), enabling a Number Theoretic Transform (NTT) for
//! fast polynomial multiplication.
//!
//! # High level
//! The scheme is built in two layers:
//!
//! 1. **K-PKE** — an IND-CPA public-key encryption scheme.
//!    - KeyGen: expand a seed into a public matrix `Â` (in NTT form),
//!      sample small secret `s` and error `e` from a centred binomial
//!      distribution; publish `t̂ = Â∘ŝ + ê`.
//!    - Encrypt: sample fresh small `y, e1, e2`; ciphertext is the
//!      *compressed* pair `(u, v) = (Aᵀy + e1, tᵀy + e2 + ⌈q/2⌋·m)`.
//!    - Decrypt: `w = v − sᵀu ≈ ⌈q/2⌋·m + small`; round to recover `m`.
//! 2. **ML-KEM** — the Fujisaki–Okamoto (FO) transform with *implicit
//!    rejection* turns K-PKE into an IND-CCA2 KEM:
//!    - Encaps: `(K, r) = G(m ‖ H(ek))`, `c = Encrypt(ek, m, r)`.
//!    - Decaps: decrypt to `m'`, *re-encrypt* deterministically and
//!      compare; on mismatch return the pseudorandom rejection key
//!      `J(z ‖ c)` instead of an error (so an attacker cannot use
//!      decryption failures as an oracle).
//!
//! Hash instantiations (FIPS 203 §4.1): `H = SHA3-256`, `G = SHA3-512`,
//! `J = SHAKE256(·, 32)`, `PRF_η(s, b) = SHAKE256(s‖b, 64·η)`, and the
//! matrix XOF is SHAKE128.
//!
//! # Parameter sets (FIPS 203 §8, Table 2)
//!
//! | set         | k | η1 | η2 | du | dv | ek    | dk    | ct    |
//! |-------------|---|----|----|----|----|-------|-------|-------|
//! | ML-KEM-512  | 2 | 3  | 2  | 10 | 4  | 800   | 1632  | 768   |
//! | ML-KEM-768  | 3 | 2  | 2  | 10 | 4  | 1184  | 2400  | 1088  |
//! | ML-KEM-1024 | 4 | 2  | 2  | 11 | 5  | 1568  | 3168  | 1568  |
//!
//! # This implementation
//! Faithful to FIPS 203 at bit level: key generation, encapsulation and
//! decapsulation are validated in the tests against the official NIST
//! ACVP test vectors for the final standard (including the exact
//! implicit-rejection output on a modified ciphertext).  All three
//! parameter sets are provided.
//!
//! The older `pqc::kyber` module in this library is a *didactic toy*
//! (no NTT, no FO transform, not interoperable); this module is the
//! real standard.  Educational implementation: no constant-time
//! guarantees — see SECURITY.md.

use crate::hash::sha3::{sha3_256, sha3_512, shake128, shake256};
use crate::utils::random::random_bytes;
use subtle::{ConditionallySelectable, ConstantTimeEq};

// ── Ring parameters ───────────────────────────────────────────────────────────

/// Polynomial degree: R_q = Z_q[X]/(X^N + 1).
const N: usize = 256;
/// Coefficient modulus.
const Q: u32 = 3329;
/// ζ = 17 is a primitive 256-th root of unity mod q.
const ZETA: u32 = 17;
/// 128⁻¹ mod q, the final scaling of the inverse NTT.
const INV_128: u32 = 3303;

/// Shared-secret length (bytes) — fixed 32 for every parameter set.
pub const SHARED_SECRET_BYTES: usize = 32;

// ── Parameter sets ────────────────────────────────────────────────────────────

/// One row of FIPS 203 Table 2.
#[derive(Clone, Copy, Debug)]
pub struct MlKemParams {
    pub name: &'static str,
    /// Module rank: `Â` is a k×k matrix over R_q.
    pub k: usize,
    /// CBD parameter for the secret/error in keygen and `y` in encrypt.
    pub eta1: usize,
    /// CBD parameter for `e1`, `e2` in encrypt.
    pub eta2: usize,
    /// Compression bits for the `u` ciphertext component.
    pub du: usize,
    /// Compression bits for the `v` ciphertext component.
    pub dv: usize,
}

pub const ML_KEM_512: MlKemParams = MlKemParams {
    name: "ML-KEM-512",
    k: 2,
    eta1: 3,
    eta2: 2,
    du: 10,
    dv: 4,
};
pub const ML_KEM_768: MlKemParams = MlKemParams {
    name: "ML-KEM-768",
    k: 3,
    eta1: 2,
    eta2: 2,
    du: 10,
    dv: 4,
};
pub const ML_KEM_1024: MlKemParams = MlKemParams {
    name: "ML-KEM-1024",
    k: 4,
    eta1: 2,
    eta2: 2,
    du: 11,
    dv: 5,
};

impl MlKemParams {
    /// Encapsulation-key length: 384·k + 32 bytes.
    pub fn ek_len(&self) -> usize {
        384 * self.k + 32
    }
    /// Decapsulation-key length: 768·k + 96 bytes.
    pub fn dk_len(&self) -> usize {
        768 * self.k + 96
    }
    /// Ciphertext length: 32·(du·k + dv) bytes.
    pub fn ct_len(&self) -> usize {
        32 * (self.du * self.k + self.dv)
    }
}

// ── Polynomials and modular arithmetic ────────────────────────────────────────

/// A polynomial in R_q, coefficients in [0, q).
#[derive(Clone, Debug, PartialEq)]
struct Poly([u16; N]);

impl Poly {
    fn zero() -> Self {
        Poly([0; N])
    }
    fn add(&self, other: &Poly) -> Poly {
        let mut r = Poly::zero();
        for i in 0..N {
            r.0[i] = ((self.0[i] as u32 + other.0[i] as u32) % Q) as u16;
        }
        r
    }
    fn sub(&self, other: &Poly) -> Poly {
        let mut r = Poly::zero();
        for i in 0..N {
            r.0[i] = ((self.0[i] as u32 + Q - other.0[i] as u32) % Q) as u16;
        }
        r
    }
}

fn mul_mod(a: u32, b: u32) -> u32 {
    (a * b) % Q
}

/// ζ^e mod q by square-and-multiply (only used for table setup).
fn zeta_pow(e: u32) -> u32 {
    let mut result = 1u32;
    let mut base = ZETA;
    let mut e = e;
    while e > 0 {
        if e & 1 == 1 {
            result = mul_mod(result, base);
        }
        base = mul_mod(base, base);
        e >>= 1;
    }
    result
}

/// Reverse the low 7 bits of `x` (FIPS 203 §2.3 `BitRev7`).
fn bitrev7(x: u32) -> u32 {
    let mut r = 0;
    for b in 0..7 {
        r |= ((x >> b) & 1) << (6 - b);
    }
    r
}

/// The 128 twiddle factors ζ^BitRev7(i) used by the NTT layers.
fn zetas() -> [u32; 128] {
    let mut z = [0u32; 128];
    for (i, zi) in z.iter_mut().enumerate() {
        *zi = zeta_pow(bitrev7(i as u32));
    }
    z
}

// ── Number Theoretic Transform (FIPS 203 Algorithms 9–11) ────────────────────
//
// Because X^256 + 1 factors mod q into 128 quadratics
// (X² − ζ^{2·BitRev7(i)+1}), the "NTT domain" representation of a
// polynomial is 128 degree-1 residues, stored interleaved in the same
// 256-coefficient array.  Pointwise multiplication is then 128
// independent products of linear polynomials (`BaseCaseMultiply`).

/// Forward NTT, in place (Algorithm 9).
fn ntt(f: &mut Poly) {
    let z = zetas();
    let mut i = 1;
    let mut len = 128;
    while len >= 2 {
        let mut start = 0;
        while start < N {
            let zeta = z[i];
            i += 1;
            for j in start..start + len {
                let t = mul_mod(zeta, f.0[j + len] as u32);
                f.0[j + len] = ((f.0[j] as u32 + Q - t) % Q) as u16;
                f.0[j] = ((f.0[j] as u32 + t) % Q) as u16;
            }
            start += 2 * len;
        }
        len /= 2;
    }
}

/// Inverse NTT, in place (Algorithm 10).
fn ntt_inv(f: &mut Poly) {
    let z = zetas();
    let mut i = 127;
    let mut len = 2;
    while len <= 128 {
        let mut start = 0;
        while start < N {
            let zeta = z[i];
            i -= 1;
            for j in start..start + len {
                let t = f.0[j] as u32;
                f.0[j] = ((t + f.0[j + len] as u32) % Q) as u16;
                f.0[j + len] = mul_mod(zeta, (f.0[j + len] as u32 + Q - t) % Q) as u16;
            }
            start += 2 * len;
        }
        len *= 2;
    }
    for c in f.0.iter_mut() {
        *c = mul_mod(*c as u32, INV_128) as u16;
    }
}

/// Multiply two polynomials in the NTT domain (Algorithms 11–12).
fn multiply_ntts(f: &Poly, g: &Poly) -> Poly {
    let mut h = Poly::zero();
    for i in 0..128 {
        // The i-th residue is mod (X² − γ), γ = ζ^{2·BitRev7(i)+1}.
        let gamma = zeta_pow(2 * bitrev7(i as u32) + 1);
        let (a0, a1) = (f.0[2 * i] as u32, f.0[2 * i + 1] as u32);
        let (b0, b1) = (g.0[2 * i] as u32, g.0[2 * i + 1] as u32);
        h.0[2 * i] = ((mul_mod(a0, b0) + mul_mod(mul_mod(a1, b1), gamma)) % Q) as u16;
        h.0[2 * i + 1] = ((mul_mod(a0, b1) + mul_mod(a1, b0)) % Q) as u16;
    }
    h
}

// ── Sampling (FIPS 203 Algorithms 7–8) ───────────────────────────────────────

/// `SampleNTT`: rejection-sample a uniform NTT-domain polynomial from
/// SHAKE128(seed).  Each 3-byte group yields two 12-bit candidates,
/// each accepted iff < q.
///
/// Our SHAKE implementation is one-shot rather than streaming, but XOF
/// output has the prefix property (asking for more output extends the
/// stream), so on the rare draw that needs more than the initial
/// buffer we simply re-squeeze a longer output.
fn sample_ntt(seed: &[u8]) -> Poly {
    let mut buf_len = 3 * 168; // three SHAKE128 blocks; enough for ~99.9% of draws
    let mut stream = shake128(seed, buf_len);
    let mut a = Poly::zero();
    let mut count = 0;
    let mut pos = 0;
    while count < N {
        if pos + 3 > stream.len() {
            buf_len *= 2;
            stream = shake128(seed, buf_len);
        }
        let (c0, c1, c2) = (
            stream[pos] as u32,
            stream[pos + 1] as u32,
            stream[pos + 2] as u32,
        );
        pos += 3;
        let d1 = c0 + 256 * (c1 % 16);
        let d2 = c1 / 16 + 16 * c2;
        if d1 < Q {
            a.0[count] = d1 as u16;
            count += 1;
        }
        if d2 < Q && count < N {
            a.0[count] = d2 as u16;
            count += 1;
        }
    }
    a
}

/// `SamplePolyCBD_η`: sample a polynomial with coefficients from the
/// centred binomial distribution with parameter η, from 64·η bytes of
/// PRF output.  Each coefficient is (sum of η bits) − (sum of η bits).
fn sample_poly_cbd(bytes: &[u8], eta: usize) -> Poly {
    debug_assert_eq!(bytes.len(), 64 * eta);
    let bit = |i: usize| -> u32 { ((bytes[i / 8] >> (i % 8)) & 1) as u32 };
    let mut f = Poly::zero();
    for i in 0..N {
        let mut x = 0;
        let mut y = 0;
        for j in 0..eta {
            x += bit(2 * i * eta + j);
            y += bit(2 * i * eta + eta + j);
        }
        f.0[i] = ((x + Q - y) % Q) as u16;
    }
    f
}

/// `PRF_η(s, b) = SHAKE256(s ‖ b, 64·η)`.
fn prf(s: &[u8], b: u8, eta: usize) -> Vec<u8> {
    let mut input = s.to_vec();
    input.push(b);
    shake256(&input, 64 * eta)
}

// ── Compression and byte encoding (FIPS 203 §4.2.1) ─────────────────────────

/// `Compress_d(x) = ⌈(2^d / q)·x⌋ mod 2^d`.  Since q is odd the
/// quotient is never exactly a half-integer, so adding ⌊q/2⌋ before
/// the floor division implements round-to-nearest exactly.
fn compress(x: u32, d: usize) -> u32 {
    (((x << d) + Q / 2) / Q) & ((1 << d) - 1)
}

/// `Decompress_d(y) = ⌈(q / 2^d)·y⌋` with ties rounded up.
fn decompress(y: u32, d: usize) -> u32 {
    (y * Q + (1 << (d - 1))) >> d
}

/// `ByteEncode_d`: pack 256 d-bit integers little-endian into 32·d bytes.
fn byte_encode(f: &Poly, d: usize) -> Vec<u8> {
    let mut out = vec![0u8; 32 * d];
    for (i, &c) in f.0.iter().enumerate() {
        for b in 0..d {
            if (c >> b) & 1 == 1 {
                let bit_index = i * d + b;
                out[bit_index / 8] |= 1 << (bit_index % 8);
            }
        }
    }
    out
}

/// `ByteDecode_d`: inverse of `ByteEncode_d`.  For d = 12 the decoded
/// values are additionally reduced mod q per FIPS 203 (Algorithm 6),
/// which makes decoding *lossy*: a non-canonical 12-bit coefficient in
/// [q, 2¹²) collapses onto its residue.  Callers must therefore NOT
/// treat a successful decode as proof of canonicity — the "modulus
/// check" of §7.2 is done by `ml_kem_check_ek` via a decode/re-encode
/// roundtrip (the re-encoded bytes differ from a non-canonical input),
/// never by inspecting decoded values.
fn byte_decode(bytes: &[u8], d: usize) -> Poly {
    debug_assert_eq!(bytes.len(), 32 * d);
    let mut f = Poly::zero();
    for i in 0..N {
        let mut c = 0u32;
        for b in 0..d {
            let bit_index = i * d + b;
            c |= (((bytes[bit_index / 8] >> (bit_index % 8)) & 1) as u32) << b;
        }
        f.0[i] = if d == 12 { (c % Q) as u16 } else { c as u16 };
    }
    f
}

fn compress_poly(f: &Poly, d: usize) -> Poly {
    let mut r = Poly::zero();
    for i in 0..N {
        r.0[i] = compress(f.0[i] as u32, d) as u16;
    }
    r
}

fn decompress_poly(f: &Poly, d: usize) -> Poly {
    let mut r = Poly::zero();
    for i in 0..N {
        r.0[i] = decompress(f.0[i] as u32, d) as u16;
    }
    r
}

// ── K-PKE (FIPS 203 Algorithms 13–15) ────────────────────────────────────────

/// Expand the seed ρ into the k×k public matrix `Â` in NTT form.
/// Entry (i, j) is sampled from XOF(ρ ‖ j ‖ i) — note the *column*
/// index is appended first (final FIPS 203; the draft had them
/// swapped, which transposed the matrix relative to Kyber).
fn expand_matrix(rho: &[u8], k: usize) -> Vec<Vec<Poly>> {
    let mut a = Vec::with_capacity(k);
    for i in 0..k {
        let mut row = Vec::with_capacity(k);
        for j in 0..k {
            let mut seed = rho.to_vec();
            seed.push(j as u8);
            seed.push(i as u8);
            row.push(sample_ntt(&seed));
        }
        a.push(row);
    }
    a
}

/// K-PKE.KeyGen: returns `(ek_pke, dk_pke)`.
fn kpke_keygen(p: &MlKemParams, d: &[u8; 32]) -> (Vec<u8>, Vec<u8>) {
    // (ρ, σ) = G(d ‖ k): domain separation by parameter set.
    let mut input = d.to_vec();
    input.push(p.k as u8);
    let g = sha3_512(&input);
    let (rho, sigma) = (&g[..32], &g[32..]);

    let a = expand_matrix(rho, p.k);

    // Secret s and error e from CBD_η1, PRF counter N = 0..2k.
    let mut n = 0u8;
    let mut s_hat = Vec::with_capacity(p.k);
    for _ in 0..p.k {
        let mut s = sample_poly_cbd(&prf(sigma, n, p.eta1), p.eta1);
        n += 1;
        ntt(&mut s);
        s_hat.push(s);
    }
    let mut e_hat = Vec::with_capacity(p.k);
    for _ in 0..p.k {
        let mut e = sample_poly_cbd(&prf(sigma, n, p.eta1), p.eta1);
        n += 1;
        ntt(&mut e);
        e_hat.push(e);
    }

    // t̂ = Â∘ŝ + ê, all in the NTT domain.
    let mut t_hat = Vec::with_capacity(p.k);
    for i in 0..p.k {
        let mut acc = Poly::zero();
        for j in 0..p.k {
            acc = acc.add(&multiply_ntts(&a[i][j], &s_hat[j]));
        }
        t_hat.push(acc.add(&e_hat[i]));
    }

    let mut ek = Vec::with_capacity(p.ek_len());
    for t in &t_hat {
        ek.extend_from_slice(&byte_encode(t, 12));
    }
    ek.extend_from_slice(rho);

    let mut dk = Vec::with_capacity(384 * p.k);
    for s in &s_hat {
        dk.extend_from_slice(&byte_encode(s, 12));
    }
    (ek, dk)
}

/// K-PKE.Encrypt: encrypt the 32-byte message `m` under `ek_pke` with
/// encryption randomness `r`.
fn kpke_encrypt(p: &MlKemParams, ek: &[u8], m: &[u8; 32], r: &[u8; 32]) -> Vec<u8> {
    let mut t_hat = Vec::with_capacity(p.k);
    for i in 0..p.k {
        t_hat.push(byte_decode(&ek[384 * i..384 * (i + 1)], 12));
    }
    let rho = &ek[384 * p.k..];
    let a = expand_matrix(rho, p.k);

    // y from CBD_η1, e1 from CBD_η2, e2 from CBD_η2; PRF counter 0..2k+1.
    let mut n = 0u8;
    let mut y_hat = Vec::with_capacity(p.k);
    for _ in 0..p.k {
        let mut y = sample_poly_cbd(&prf(r, n, p.eta1), p.eta1);
        n += 1;
        ntt(&mut y);
        y_hat.push(y);
    }
    let mut e1 = Vec::with_capacity(p.k);
    for _ in 0..p.k {
        e1.push(sample_poly_cbd(&prf(r, n, p.eta2), p.eta2));
        n += 1;
    }
    let e2 = sample_poly_cbd(&prf(r, n, p.eta2), p.eta2);

    // u = NTT⁻¹(Âᵀ∘ŷ) + e1.
    let mut c = Vec::with_capacity(p.ct_len());
    let mut u = Vec::with_capacity(p.k);
    for i in 0..p.k {
        let mut acc = Poly::zero();
        for j in 0..p.k {
            // Transpose: entry (j, i).
            acc = acc.add(&multiply_ntts(&a[j][i], &y_hat[j]));
        }
        ntt_inv(&mut acc);
        u.push(acc.add(&e1[i]));
    }

    // v = NTT⁻¹(t̂ᵀ∘ŷ) + e2 + Decompress_1(m).
    let mu = decompress_poly(&byte_decode(m, 1), 1);
    let mut v = Poly::zero();
    for j in 0..p.k {
        v = v.add(&multiply_ntts(&t_hat[j], &y_hat[j]));
    }
    ntt_inv(&mut v);
    let v = v.add(&e2).add(&mu);

    for ui in &u {
        c.extend_from_slice(&byte_encode(&compress_poly(ui, p.du), p.du));
    }
    c.extend_from_slice(&byte_encode(&compress_poly(&v, p.dv), p.dv));
    c
}

/// K-PKE.Decrypt: recover the 32-byte message from a ciphertext.
fn kpke_decrypt(p: &MlKemParams, dk: &[u8], c: &[u8]) -> [u8; 32] {
    let u_bytes = 32 * p.du;
    let mut w_acc = Poly::zero();
    for i in 0..p.k {
        let mut u = decompress_poly(&byte_decode(&c[u_bytes * i..u_bytes * (i + 1)], p.du), p.du);
        ntt(&mut u);
        let s = byte_decode(&dk[384 * i..384 * (i + 1)], 12);
        w_acc = w_acc.add(&multiply_ntts(&s, &u));
    }
    ntt_inv(&mut w_acc);
    let v = decompress_poly(&byte_decode(&c[u_bytes * p.k..], p.dv), p.dv);
    let w = v.sub(&w_acc);
    byte_encode(&compress_poly(&w, 1), 1).try_into().unwrap()
}

// ── Research hooks for cryptanalysis ─────────────────────────────────────────
//
// Both functions below are `pub(crate)`: they are not part of the library's
// public surface and nothing outside this crate can reach them. They exist so
// that `crate::cryptanalysis::ml_kem_pco` can mount its attack against *this*
// implementation rather than against a re-implementation written to be
// attackable — the difference between demonstrating an attack and asserting one.

/// K-PKE decryption, exposed inside the crate.
///
/// This models the information a side channel gives up. An FO-protected
/// decapsulation never reveals `K-PKE.Decrypt`'s output; a decapsulation whose
/// re-encryption comparison or message decoding leaks does, and that leak is
/// the entire basis of the chosen-ciphertext attacks on ML-KEM. See
/// [`crate::cryptanalysis::ml_kem_pco`].
pub(crate) fn kpke_decrypt_for_analysis(p: &MlKemParams, dk_pke: &[u8], c: &[u8]) -> [u8; 32] {
    kpke_decrypt(p, dk_pke, c)
}

/// The K-PKE secret `s`, as centred coefficients, one vector per module
/// component.
///
/// `dk_pke` stores `ŝ` in the NTT domain packed at 12 bits; this undoes both.
/// Used only to score an attack's output against the truth.
pub(crate) fn secret_coefficients_for_analysis(p: &MlKemParams, dk_pke: &[u8]) -> Vec<Vec<i16>> {
    (0..p.k)
        .map(|i| {
            let mut f = byte_decode(&dk_pke[384 * i..384 * (i + 1)], 12);
            ntt_inv(&mut f);
            f.0.iter()
                .map(|&c| {
                    let c = c as i32;
                    (if c > Q as i32 / 2 { c - Q as i32 } else { c }) as i16
                })
                .collect()
        })
        .collect()
}

// ── ML-KEM (FIPS 203 Algorithms 16–18) ───────────────────────────────────────

#[derive(Clone, Debug, PartialEq)]
pub struct MlKemEncapsKey(pub Vec<u8>);

#[derive(Clone, Debug, PartialEq)]
pub struct MlKemDecapsKey(pub Vec<u8>);

/// `ML-KEM.KeyGen_internal(d, z)` — deterministic keygen from the two
/// 32-byte seeds.  `dk = dk_pke ‖ ek ‖ H(ek) ‖ z`.
pub fn ml_kem_keygen_internal(
    p: &MlKemParams,
    d: &[u8; 32],
    z: &[u8; 32],
) -> (MlKemEncapsKey, MlKemDecapsKey) {
    let (ek, dk_pke) = kpke_keygen(p, d);
    let mut dk = dk_pke;
    dk.extend_from_slice(&ek);
    dk.extend_from_slice(&sha3_256(&ek));
    dk.extend_from_slice(z);
    (MlKemEncapsKey(ek), MlKemDecapsKey(dk))
}

/// `ML-KEM.KeyGen` with fresh OS randomness.
pub fn ml_kem_keygen(p: &MlKemParams) -> (MlKemEncapsKey, MlKemDecapsKey) {
    let mut d = [0u8; 32];
    let mut z = [0u8; 32];
    random_bytes(&mut d);
    random_bytes(&mut z);
    ml_kem_keygen_internal(p, &d, &z)
}

/// Encapsulation-key check (FIPS 203 §7.2): correct length, and every
/// encoded coefficient must be a canonical value mod q (verified by a
/// decode/re-encode round trip).
pub fn ml_kem_check_ek(p: &MlKemParams, ek: &[u8]) -> bool {
    if ek.len() != p.ek_len() {
        return false;
    }
    for i in 0..p.k {
        let chunk = &ek[384 * i..384 * (i + 1)];
        if byte_encode(&byte_decode(chunk, 12), 12) != chunk {
            return false;
        }
    }
    true
}

/// `ML-KEM.Encaps_internal(ek, m)` — deterministic encapsulation from
/// the 32-byte seed `m`.  Returns `None` if the key fails the §7.2
/// input check, else `(ciphertext, shared_secret)`.
pub fn ml_kem_encaps_internal(
    p: &MlKemParams,
    ek: &MlKemEncapsKey,
    m: &[u8; 32],
) -> Option<(Vec<u8>, [u8; SHARED_SECRET_BYTES])> {
    if !ml_kem_check_ek(p, &ek.0) {
        return None;
    }
    // (K, r) = G(m ‖ H(ek)).
    let mut input = m.to_vec();
    input.extend_from_slice(&sha3_256(&ek.0));
    let g = sha3_512(&input);
    let key: [u8; 32] = g[..32].try_into().unwrap();
    let r: [u8; 32] = g[32..].try_into().unwrap();
    let c = kpke_encrypt(p, &ek.0, m, &r);
    Some((c, key))
}

/// `ML-KEM.Encaps` with fresh OS randomness.
pub fn ml_kem_encaps(
    p: &MlKemParams,
    ek: &MlKemEncapsKey,
) -> Option<(Vec<u8>, [u8; SHARED_SECRET_BYTES])> {
    let mut m = [0u8; 32];
    random_bytes(&mut m);
    ml_kem_encaps_internal(p, ek, &m)
}

/// `ML-KEM.Decaps`.  Returns `None` only for malformed input lengths
/// (§7.3 check); a well-formed but forged ciphertext yields the
/// implicit-rejection secret `J(z ‖ c)`, never an error.
pub fn ml_kem_decaps(
    p: &MlKemParams,
    dk: &MlKemDecapsKey,
    c: &[u8],
) -> Option<[u8; SHARED_SECRET_BYTES]> {
    if dk.0.len() != p.dk_len() || c.len() != p.ct_len() {
        return None;
    }
    let dk_pke = &dk.0[..384 * p.k];
    let ek = &dk.0[384 * p.k..768 * p.k + 32];
    let h = &dk.0[768 * p.k + 32..768 * p.k + 64];
    let z = &dk.0[768 * p.k + 64..];

    let m_prime = kpke_decrypt(p, dk_pke, c);
    let mut input = m_prime.to_vec();
    input.extend_from_slice(h);
    let g = sha3_512(&input);
    let k_prime: [u8; 32] = g[..32].try_into().unwrap();
    let r_prime: [u8; 32] = g[32..].try_into().unwrap();

    // Implicit rejection key K̄ = J(z ‖ c).
    let mut j_input = z.to_vec();
    j_input.extend_from_slice(c);
    let k_bar: [u8; 32] = shake256(&j_input, 32).try_into().unwrap();

    // Re-encrypt and compare (FO transform).  The comparison and the
    // resulting key selection are done in constant time: a data-
    // dependent branch here would leak, via timing, how much of the
    // re-encryption matched — an oracle on ciphertext validity that
    // defeats the point of implicit rejection (FIPS 203 §7.3 requires
    // the comparison be independent of the secret).  `ct_eq` scans all
    // bytes with no early exit and `conditional_select` is branchless.
    let c_prime = kpke_encrypt(p, ek, &m_prime, &r_prime);
    let matches = c_prime.ct_eq(c);
    let mut out = [0u8; SHARED_SECRET_BYTES];
    for i in 0..SHARED_SECRET_BYTES {
        out[i] = u8::conditional_select(&k_bar[i], &k_prime[i], matches);
    }
    Some(out)
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn hx(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }
    fn hx32(s: &str) -> [u8; 32] {
        hx(s).try_into().unwrap()
    }

    // Official NIST ACVP test vectors for the final FIPS 203 standard
    // (usnistgov/ACVP-Server, gen-val JSON files ML-KEM-keyGen-FIPS203 and
    // ML-KEM-encapDecap-FIPS203, internalProjection.json).  For ML-KEM-768
    // the full keys/ciphertexts are embedded; for the other parameter sets
    // we compare SHA3-256 digests of the outputs to keep the source compact
    // (inputs are always embedded in full).

    // ML-KEM-512 KeyGen (ACVP keyGen tgId=1 tcId=1)
    const KAT512_KG_D: &str = "47b893474672ba92e4b12ee44fb32953af8e8503b5fb471d1614fb8a021a660a";
    const KAT512_KG_Z: &str = "1f8cb39e9e30bc458a0dc5408884b1187fb217018df760fa57317703b844a0a9";
    const KAT512_KG_EK_SHA3: &str =
        "3a389831056ed8fd81476869245782689c84b3ce90fe6a9e78d0a380fd6a1573";
    const KAT512_KG_DK_SHA3: &str =
        "c26aff5b9f97b5b9ca824755d053a1b1aece2b965af6bfbd527b77ea22538468";
    // ML-KEM-768 KeyGen (ACVP keyGen tgId=2 tcId=26)
    const KAT768_KG_D: &str = "e582b7d75e6c80b05ae392a1fc9f7153b12390fd99930368cc67a768baebc8a0";
    const KAT768_KG_Z: &str = "1cdacb8740c0b87c4a379575f187b367cbfa3b300bf591b109f79816e9cbe8f0";
    const KAT768_KG_EK: &str = "28c793778741b80b02b4339f2aa4347255b099f17264e1b8cc0a2c7c2a1a79f7997b907fd0496c6e6c8ad7714f5f339d75f11f625591a869be1175ae47f05fd4313468232ba6957d7807b824f445ac99a0d568ab1ad54dca8249d1482e61275f52248c77f61a4248753188cd1794cd0a465ec0dc4b025985c461b74e76286e4c37e77405695cc9fd0654374b427a20343aec0ff1a187768273bfc4905472a1da387f14559d6ce87313f6a5b6138434539f9a13684055b177e543f8b40f432abd7cc49989a50a9084c660913f45a8593b17499bc4cf936c2bc1851421cb986808a0ef30afe97aab5b8b8eb3f0b3506a95b91563a0e57db7231044987ef141bdab3537c316ad16f17805a81f29329879a94e96157e4b7447f7d59603b21bd896cc47b7cd4e232322eb9c5d2215696bcffca3a04efcc4c5d9cc39ac9a6e8700d38c244b0169e7fa1fe81b4b10365e74e6a1f7f756d11acdc84043f81006d62995376c22535958feb53f78117ee0f61c4c862640d06dc57a2b8be62a41a642af3bc63f6bac98bbbbff70570f37b8f8d9572f2735657a6c98f96caf57a849868720b2640b8bb2732237a1f984c18872d10289ce43c952c9257e06529aeb76afd127b17596fd25c5216c9cabd9b18efc50e87bbb04568bb7d5c4e9288c006483af5912e19108573700bd10cd77224b80659ea75aa74270b33ac4008b738bfee271e78658c8742ff13c96ad0781a03c7576ca26dd58b52980ba58c0505e446afa140cdcea0490db1f9b18815d4314b2459cacc562441c91f4084e5426c88e632cf7482e79907911d06473260835d7b85e7856a829aea0381707b939ce86882cc09c4448c6ae94a9c303107c5667eefb8df7763cc21189a3c590c40aa51f491503a7935ec08f4fc300cbe607ed8c9100c29fbf45584b13c8d780069337aec76c36ceb70373e2ab6e7b934b466f53fb32eaf040055496b8540e23a2a277e534468608d5ec0f8d38cea5bbb806c1bf4f164f6ac826fe733f95461e29dcc11200c0aada1b8332023eab329718ce25cc0a09555903f3578bbc863b1752ca94365da556df54c3b7e05cbb7115fbc1b6c57a172c31b9906560c8fb54f3c563a2256cc073243b8179b4a28d60e086cf51082ee429272996f0aabe03ba0eafd3c8e7d954bd0933e2f60ed0c32cede7b820a28e48f3ca3c40913cccae2337abfc59843f08c9863325d65a4e9e15c1f46172b118b2b5eb0f1d5158a00134f27b085488c3a0621fe4e5678698250fb74ee5152e3e35a66544a05d279ea99131fbc15165060b90f88eeb7b20892a4de4cb1683495bd7da037966b47cc040f1764c5deb06b5499d4267391cebbb47f734d8539e39528436a1858182854bf20b1f93279afb706464c65ccc5ae099b37cc03556c26abf4c3f8b9ba3a936707211a49a59b268f5284f7970c77612719450377417428c4ba47c9ca115cf95304c4759c5d8859b44985c06a6c924689237ba320d610960d61c53e85431789e67a40113f167ff93429c264f6cabc95448c903437d39a6577be0cf0012852aa476351a9046a110a1a625a3d74c910b78bce9cfca735e4f91b8a4c57dbe489e849446098aacf73070aee638fcc8896473d3c159d3afb4b687b40dfbf371a9c2644b605187b71a14bc4c8678fe8247";
    const KAT768_KG_DK: &str = "3808b98d9a093c7853b0b814d1ca5f392677d3d0a38f81c852f95b9a69b374a24588c0add5b510be567c5a24688ec91ed0f28bb4c86978c09793795c36b94e5dd8498eb4353ff40ea87b17e921b5b4cba08e5b7be5a9c8bc69ac5ac3075dd947d04b8695097ac39790a0c8abe11200c9f136ed7b0c10077e36111c1f139d9bd27142993f5883925c4918413cb8043962a28567397a1c7e003bac30644055155ce9464e623fc5e2160cd1143fd2c90c03a08d0b333fbb40a308cacd81618674b406809790b2538d30431f064f65ebba7c41b2a53146a3abca66754cae591534045c1d640d6308472ebca660a8a7d372470d3869115b8860b577311980b2c66b8352229abc17b0c31f58e5a5ebdbca6e3b157d9ca79ee890778a4cf28429c2a82c80dc9c524b0864e385e355bd4e65732d395e464070f61828e57c3e1be2a50052c4ff1951f5d0c89720987d8941f085871113a91f518fc79b7189056990b2447bf54fc170c932e0a4e0f7a262542f56d1b49eebc392106d93c77de9186dfbb824e73b2f7fc796b312875b43414877afb356214492c19c748dd381bc7a9237bf097cc606a03119a240a5536ac7844f6a79d0e2b821b68d96542450179bcca231f2da68c5eb6d118b99a1b66eaa566c78a9009008b0d66155ba4839f8e518c650177dec170eb09e8bf6a89905320590c642b801cf5b5151c2af3e7271cb9961c65a5bd17479429a31be9081f2767d94816c16d1b04772012382b689ab2d3fb9bdc66547bfeb23052600bb369771494d9c914ec93a066abc9611940b947310da04197312425d736a1933b785c95dc430791e42cd691c79ba63be06ec80765c9c07053eac706697f21720c672b9803df9935532197b0485bbe42b0dd16561ac0605e9da73c189c9e29aba3aeca19c21621b209326418543c44b88843eb3720a2cec3db52c59d6507ee5cb03c268b31fc4bf115695eb0b8ad3f11fedea1a5d0724a5d5284d0c10e9844d0d32bb5735448421bc5317650beac4829b234b787339812f2316ace8c22c42d6346214934fc0b49eccbdf8da19aee64de9628c4f7ab3e512a399b0c227b677ac4a69891a6874f6641d2cc95460b751e17e434c924b2947d806856665696e3cc4db9553b81606c31c3800b48756a073bf685eea20899c176769e902db971827d153b9c33516e959c6b469841946c0d921a371a5de9740c6ab9ca272b5850ba8753ca023a460ebf7bd573c0745f40b90f105ee17c19b6832e019b80f8858bb515f7c709e68f29c1375b22567afe7b528f4431a94b553df825cdeb84b4ea9296eab9ad66271eec5aef6f79509a20a182279fdf92f87fb6e7509968d22ca750b5056974841b9654e5716bdc33a2c6a116a4117fa757a1d22710668412b8878e134b70fe32158a2317fbc62f01371296aa42e33c903e0c439f19684b11e2f911f7fb79860c8800f9ca146eabe29db07237aabb503a9be2aa7263a0626c162a27537775792b2e7b0fd347929934ad8f521d4159059f611312ab903879490059be8b38920e2cb4a256b8b35783e909346d13e9888beb9350369f7c1a8501331110c651621a616b365a026d1cc47df440c9e650dd0c0bfc8295439114528c793778741b80b02b4339f2aa4347255b099f17264e1b8cc0a2c7c2a1a79f7997b907fd0496c6e6c8ad7714f5f339d75f11f625591a869be1175ae47f05fd4313468232ba6957d7807b824f445ac99a0d568ab1ad54dca8249d1482e61275f52248c77f61a4248753188cd1794cd0a465ec0dc4b025985c461b74e76286e4c37e77405695cc9fd0654374b427a20343aec0ff1a187768273bfc4905472a1da387f14559d6ce87313f6a5b6138434539f9a13684055b177e543f8b40f432abd7cc49989a50a9084c660913f45a8593b17499bc4cf936c2bc1851421cb986808a0ef30afe97aab5b8b8eb3f0b3506a95b91563a0e57db7231044987ef141bdab3537c316ad16f17805a81f29329879a94e96157e4b7447f7d59603b21bd896cc47b7cd4e232322eb9c5d2215696bcffca3a04efcc4c5d9cc39ac9a6e8700d38c244b0169e7fa1fe81b4b10365e74e6a1f7f756d11acdc84043f81006d62995376c22535958feb53f78117ee0f61c4c862640d06dc57a2b8be62a41a642af3bc63f6bac98bbbbff70570f37b8f8d9572f2735657a6c98f96caf57a849868720b2640b8bb2732237a1f984c18872d10289ce43c952c9257e06529aeb76afd127b17596fd25c5216c9cabd9b18efc50e87bbb04568bb7d5c4e9288c006483af5912e19108573700bd10cd77224b80659ea75aa74270b33ac4008b738bfee271e78658c8742ff13c96ad0781a03c7576ca26dd58b52980ba58c0505e446afa140cdcea0490db1f9b18815d4314b2459cacc562441c91f4084e5426c88e632cf7482e79907911d06473260835d7b85e7856a829aea0381707b939ce86882cc09c4448c6ae94a9c303107c5667eefb8df7763cc21189a3c590c40aa51f491503a7935ec08f4fc300cbe607ed8c9100c29fbf45584b13c8d780069337aec76c36ceb70373e2ab6e7b934b466f53fb32eaf040055496b8540e23a2a277e534468608d5ec0f8d38cea5bbb806c1bf4f164f6ac826fe733f95461e29dcc11200c0aada1b8332023eab329718ce25cc0a09555903f3578bbc863b1752ca94365da556df54c3b7e05cbb7115fbc1b6c57a172c31b9906560c8fb54f3c563a2256cc073243b8179b4a28d60e086cf51082ee429272996f0aabe03ba0eafd3c8e7d954bd0933e2f60ed0c32cede7b820a28e48f3ca3c40913cccae2337abfc59843f08c9863325d65a4e9e15c1f46172b118b2b5eb0f1d5158a00134f27b085488c3a0621fe4e5678698250fb74ee5152e3e35a66544a05d279ea99131fbc15165060b90f88eeb7b20892a4de4cb1683495bd7da037966b47cc040f1764c5deb06b5499d4267391cebbb47f734d8539e39528436a1858182854bf20b1f93279afb706464c65ccc5ae099b37cc03556c26abf4c3f8b9ba3a936707211a49a59b268f5284f7970c77612719450377417428c4ba47c9ca115cf95304c4759c5d8859b44985c06a6c924689237ba320d610960d61c53e85431789e67a40113f167ff93429c264f6cabc95448c903437d39a6577be0cf0012852aa476351a9046a110a1a625a3d74c910b78bce9cfca735e4f91b8a4c57dbe489e849446098aacf73070aee638fcc8896473d3c159d3afb4b687b40dfbf371a9c2644b605187b71a14bc4c8678fe824781e66ef5a7a221619f6a64039cc369843e10df5c859f6959cc3fd8e5272330fd1cdacb8740c0b87c4a379575f187b367cbfa3b300bf591b109f79816e9cbe8f0";
    // ML-KEM-1024 KeyGen (ACVP keyGen tgId=3 tcId=51)
    const KAT1024_KG_D: &str = "f3a706faf090c03db506863ab0b20bd8a1627956318e88c67eb875e8e7266009";
    const KAT1024_KG_Z: &str = "35d2bc43dd1cc879f765bf2a0c5e297889dde910e57e2bb0eae417b90ab7a275";
    const KAT1024_KG_EK_SHA3: &str =
        "9370fe5b05ddc92c939f62cbde4c0fea36f45cd20c5748cf3ac891a4c2604496";
    const KAT1024_KG_DK_SHA3: &str =
        "b8c683c71564ff8e2391c57b68c3a1ff186734b13e31d2a075b65307c8b80888";
    // ML-KEM-512 Encaps (ACVP encapDecap tgId=1 tcId=1)
    const KAT512_ENC_EK: &str = "86c64c4cc2b50533235a338a567b089e57bb11160254b75b91a45d31a59ddfd133cde0b5d2776bdec5ceb392566243cf0796809d75c429aac4ddf4a9e58cc13999c90cf3c03da754e6aab9a9f22625dabe8f5c0030c796a73ab114d905ffdcbc0d135d34f79bcfa2cc550036466415e96257d56a85da1c294c7938f3c92992b55335f3c1bdea0350345a87e600903a3f9327858ee0c4cd20c47588b8ec613ac8076fb1483160d356c1442e9400b210b07af2baada476a01d6583c23a882b889cbf055f2a31cac0574e0423c2d22a178fb233969857742739d01a71b4903655031740065c1370464683b3916bb1f9133264a447e3e92111b99adcf5234b1403fd8a570ea20df29c43245a4298b20c83b9b2fab930dbe818c3940e1a5805770874a140b12dc3be7df9b0fe546222645a01b93daba66d5648c064fa89e32792faa12c5f76747317a3304164583691ad98a01854422b322488ba6f077825cdb8c0754a3937422b16656c3d80001d760ebdcc8a3e5980f6c353cdbc89bd7c10d4a24b3614aac13497416977f9bbb73cd742bfc94496549fd4fb4e48ac91b87b432db64e51377a1b54c5a54662babca2fd68b52de239098c067d544b7dd69fa6ab16a22143965c24af3b0736718c2f9230e2534dd9bb9e190462577856d19c0c309931993c942aca682cb030ddf36ee0784333593b501466b9090923190ea707313fb6179f58c42bda8eb16c141973ce45a577f3a96e72caabacb7b5d056be10da8199b28b86f58c819cafbf6c7ce2d5b45f4023c6391e1070774f1c033af830a8d2b1b81a8b07727c117aa3812812bdf768f25ccf06bc1af5c058221341c4f6b27a6b7bd1177bd55323239a57dd5021b6a92485553a8c30917215bceef97968a11a42fc0da997c0984c7f9c277112dcac0ff83ccb6517d54c5eb6e2ab9520aa39e260862b0b99d40e701064821576d78ac4908b1e8fe8c4825603f0545f2059674ef6a04cac900aeba76bfa8d21d7036f679dcd146d0ae7c1f4c340f41b2985f32344e5bedffc6c286aa2edd252b78c3a5f3576d1252c2a96b91d23453e2c9476747c845554fe4d1dc2d29fb6d8f3897fd8abe600cf428c76e77f3ad0a034ebd24845";
    const KAT512_ENC_M: &str = "19c44d35ab9ef31b1360f0bf33cf63d80e405962d698415c5888f0af385dcff4";
    const KAT512_ENC_K: &str = "4b7b1514d1bc9808f80e3bee7b528e13b753c99d153f7ea116a5887063bfcacf";
    const KAT512_ENC_C_SHA3: &str =
        "9dadf2968e267f2f4736b8a5d37328a5fc39fa0462607a7c155f35f93da06670";
    // ML-KEM-768 Encaps (ACVP encapDecap tgId=2 tcId=26)
    const KAT768_ENC_EK: &str = "b649b9ad5a59aa45640b03ace153499bc1244465735dca6e5ed0c7116070287758e7a31ee53ba171e7c8964b3615075286a4af1ea12479ab0218608692a2606a024d12fcae691c8114828f3547c9d0344af9920d952ba6bce6aae6a47360da1588697f91ab5475c5588ad6328389a34ba50e41514343c534ad7947c5aa4220c73d335bb24f6676cc2549fd40759cd4b54549b04d8932921b183ecb634b579a54742dd6734c7225741ba32ac196aa68faaf3d1425d4a44cc563aaf8816a8258bf745842f1ca7d8eda9a7a6ccd72966abab9061ee21ef3d2b1155133f4b8099b653ba8b5224360cf00295f2b3887d1b12d601b18bd407b80d167aefa0d3f6a906fc2cd08a663b7766815a26c6e2bc83318ac99b5a56d338ec347adbd9a57ec53359ce898fb637b32fc4a6fc216bfa30eec501681751bee46c5c02317c3b3b98f24ac67acc53941cd20035fe2a59890e9ab7cf063fe07a62703643e0580d99c152343c5bdd8cb9f9c1fd0c194ee7281913a7d1f0473722c024df76568a731d309cd5fa87fb3a0c771aa42efd160af89752c1c3eeac74a934b163af92d4ee74c709a31e901045fe6202de9622b552acd807829f46ad9c47087e2856f294b97546103568292a4b7462895f161891af4a66d537e79087f87f63e4e5a7d767a5d6a4a52267c8ce41413ef6c3dc4b1c64ee5ad75d9542099361ef81246a64ad997885fe0631d02919ab6b967b8c441d73b67d52b5fa64ac7789d30e659d776334da3a65a3b4081014455bc858637b23a991fe8ec315c687c36d81553c79f159c2b4b285604c0541ab62749cba6c29472b5dc6ab61b2be2e6a57a1942e729c1e95ba95c8100d4554fcedc0d73ac8023f736a94ac757b7b5108807a5eaba507b6f22e627ef325c0ef3b28123be7882840b7a8efcba7e0d82434c330b37b7c7f546b123d460a0d0c58893a7e4664f49acc9150a5dfbb71fbef44374a987e3192be4a50fc1f1160a0488844864532689e9f29d55366969e014b19869251977c34049437bb41b334c2de7a2eb63cc3ff21b042aa0e6839469e4bfa226cdbf8331cd1640e04b4cf2a89bffc20283dc2d90706604c1021153417b26c650b483856463df2c2c064ab4a9f316c5ba02109b1023370dded31ab1da2eb837bd8ccc52106712eb91a019119bd60951b3662f3f6291ecb76561b253dc4a1cb8e41b3a16b2ec87a252c4b747448823902845527b31c15a3ef18e174b644f548faf30b3da5610edccb73e3a8714bbbdd668c14a9472718b34efc545fff2783f033f13fc1665bc324ca244f1e91851d8ce2df2b388ea24b2cb8eab400f5a8ac1d01442f765688393ce21c4c63113ba49480b247c3fb4d49df82b1f493430bfa78f6d948da4e927bdd9bd2d18a7f230046853bd8be51cd59178d0295509213b7e1b0798584dce835b48312f0257a185d9360e0a702ad8bb0a53c119336889974b8e52b636328556ca1a9eec413f5259c66503c90206a7857925c727815c94fd545f0112c6a7e89c2ef54ae897a4b0792f98f5710ca174288658f5c8596c7807008369831135e1d50d5ac77f6ae9641de0622bca6a8e746700818c4a22a9ad30c9bc660117f3462617baf392280de09f5695b3cdda5e931c5b521bdaa455c3d0f0f7375153a754ed9620da68dd";
    const KAT768_ENC_M: &str = "7d5201502fad05b1463bc2212d6aec1c8503204c491f12d9366ae750144b7831";
    const KAT768_ENC_K: &str = "11b62291b1a9d307c8240d70be0b45436db445793173f6e79fcd2b273d7f3b01";
    const KAT768_ENC_C: &str = "04f4a18c69708a17f561778b2ac10d94380abea4a20835939c9015d78dac41a5012ced1bed948aed6c79193f8b2fc6deabd3b092ec33ae2f54778f1c54ce762a69521764e20c05bc2ef96992f463ca95d09dd588af622c297bbd8805113e985388fc9e16fda06b5eed42da629d514f86ed84acff0a09418e720201b794b49d072df15e7b7d6ec6d82379a212c71c7603a1c9bbe57fb1cb9a431de1980ecada0a4fbf5cace9ad0ceedbfdc40761839d9cc1c8590eb6335179075892a8015e04ecadad37fdcd4644ec2284cf4cbb4620fbab6055a163e3733e3a7747044b766ebc356436b33e28fa4e67b083592b05811361445c719f6ae8add4ef8ce145e3933cee75d19e98bb964d58044b6de2b46107f80c3d4690114cc84fb0d3b3d4c3af671ea7b833746b54fce5cc761ca4fd20cd163afa849e5797619c31144a74140abe1c7540d1a3c557a9f23af6e6e3523667ffd13b92444cd3be01b1581ca0cf7a536ce4c073dc17de955ba22e469bc1c0ec213b3b7ceddfc47567a7ecfc2a58a6c2a3c2185563277866f8979bbb86af844349c6021eb9926acfe0188fd0f809e056a8e0a8aaa2a4208562e775ef60c56cadd6e26a9e52d60187bf6ed0565616020e0c2bfd79d961b1069ff261b2abf40c9ee2a2c442877f4edb8d9ad717cb434fed67ef2eacd629da1ce78023548853eeaf7d998923db7ceb0174e67875e787f398435da84c26b478ff6bf785c4714bc6f8e91804e10cc699e1be342c952d57d3c84654d603709f4f6bb596e022e2e6149c81025226b9925045ff365d83991f7d4c8693544ca7ba6da60f8e4f6723c9f14ac48882556336ed88c20163544c55ab4238e510aa910b04f445252d507af02ad24e7467920c81f2d31a71a7241be2726bb9f8b20bf2100633f616a1233801eb37597ddbe2def36ef0727515e7da178da7760a41edf9ffe98fbaa3495a35025f2bd100b3d63e940ba7d997104ac67f653d0a24a2ba2c8a355af1ee048cb116b1a492577cc7cf61226fbbbabd9cbb043839585f2e00ae673ee6becaaf5da7919921c90c74d5b8b173b8a1a650f379b3b5e5f1d04538b936fc2cd0d4f8b9df9f5052ecd9e66602815b4f96586d038d5bd5a3e44bde1ef9ff9cfcb6b9aece3129ef1f026befd299a7a8ad324149b156bc5ab868099df52a2056103432879b495b0655fc1fe8073b502f3f40d403548b1629118ce0edd41558e4215e8e241a45637a3434bf070f17dac885ed656f80783a4c47000464fe78b9db0dbb55895e271d3376bf0c50cec9a403a8729982dc5b9172b5e80a0ef03fa2a24873188f8022a6f9da8ca4f2e24aa7e29987b1060ecfe0b08e039ee1f7fb55a0cd35a73b6c25dc26e469bbc2d034265db5f74e644842bb99199f83947c97bf87532b37a8d40a06f8bc5508efb117d11dfb07325d9482cdce60aa34529546d4c8d8f98e3f5b34b5c757075fee9c3443e0a1109253f5f0a905c571e5343b277e0636a5a46ab36becf5672e93b712b9bc8e3cd3656cad1b29c16e";
    // ML-KEM-1024 Encaps (ACVP encapDecap tgId=3 tcId=51)
    const KAT1024_ENC_EK: &str = "f6690e77251a47a0126f3cae222b8873eb0ec9669aa7b08f4854aa72c0731649ce60eaa8b08198b8712158238dbe83caefd7641434ce1a1346f6900a53c105462b4f1e909e680476000c8e8ff43dff9ac7f36657bf852262d383e68ca2c8764b59441523f009b5a752278491dbf89192fab92bc873ddfc5b5fb49f9160769bd228844127fddba4949a1ce958b6fc1388dee6cad9f549287b7e0c85300d636ac1a68c1f0860af00ce50963e3db200f651147c4425df62467fb4bfbd3b89da337aa74444409ba3fa73b8cd1454f7e7c730352f894387e79c7547c077c19496322817d3d540e496922f1063235b78ea66ba23918e79115277965e67760a2ffc91530aa85575474dc344f11130fc77ceec03adf4937fd7fbc838c05bf88263a9903ba10718b6c43e97047902827a491abfa8d83780191c96fc8924817fa3ab625c76132cea34273b3d74589e91114216989c8e98c5b4ec2e5aa01805bb598cb7137e61cb6907952a51ba54c52e9e8c629305b7982779d0cc9d43e14c254277a5124e06257cf7a61efc186118a808ce4ba0fcd31b34559d77643be90bd017b5c90c235615b61258d6432ee6138a90a0b3da38b6c8c20157644c010b6bbc327ac4b515e2ad5c46ad63ba0871946b6455a303448662a1cbccba1a462389b7ea4aafd4a411e2a45d92146fe4508094c8e4f2747e918a2e57874c934a5c654f137695c67084a3ec50f3e7c777dc42aac0aa9727015546cae376c68504aa99a8ae585c2be6e84e510124b5ea9169c356be0239cd8c900da93203716c3557bab802c846c31948b7b2eb064e2de01e9fca837d4986e43a019bd351dce5218fc1386a46684f2347f6ea999c07586ae66da4a129fe3c36e1435b0715b155477000768ef7877c618579ccd958dcf74323e9c065a04f0f1b23ace41b0faa69dfd53ea2c62af467b0df64800e79c4fe72419958ab1d470250b5122a915eb00a44f4545dc83b78a0942702b71d9339115e007fab9684fb3880b0e97221d5867d4cb0a4921fa29a81a939231f2c1cc5d329652052c3484602316b792abcd55036e1f41fdee702ba1216ab71918f469503ec85e9321ab8d4287bd537194560e1f140fe3900d1864f588b4aac648d1647612837cd11ec6b730768528a96d825bd06033a4734b04b2aa6f26586a345605e59781f046738c51747564183b139e772b94194b3eb64407c462dc54c14cfc81bab301f9091950b5a97bff836990c0a419ab1c8f08a8d200aa3b968a19224e03b140c998a58b86221cc258c407f0dda752a890d58425d6269b4cb03052da31cd0ecb04b36a42d30a1edf98570a31ceaa81ec9382f6dc012f63728f38a5983b50df7c65491934f2cbb9cdd714284c0706ff79bb1f879b6ea423c71198bfa0afb628469bb0e6f79c174463fdda6ba4a78a886ec690fda63cd93b66cb01e384395fe0281a7dcb55661b2dfaa7990cc19beb96bcc29740f305ff3c72281a5991f3b39135b066389c1dab7b0a2babbeee76bd99b394c82a28ebb275643c288e421bffc94ab317dd5191220e9527549670c67aa4d26ce8a6aa1c8629601631b35fb9fb881c1ff03ca68c2be4d913269274b04668305a6ace7129654c51dc9c78ea9b07b489241a0e4c83fd5b2857a13ab4aa9d7139202ac08e2877624d07aee9c6954dc7e0ba693f260b714b80c92f6b411d510e6276061451d99e54ad55954993b9624fab31debb0ff700b10fa3d7c3952e48082f4d87ddb703e55cb65577450a375c56644501364b871766ddfe57cefa187745ca3b6f87890c2ac65b89ddbb9ae7af90f9baaa353043cd382a4089c5744d11e78d71a61d01f4c345c5caa9b385c7af35a72545c677bcb363b129a0392033956064fc199cff4baafd03a3413c65b025fc186475690ae93699db6d0b71b285aba96201d149968574613865cfa26cfeae7c249fa5d5fb18480a752c368681a5969aee20da1f0acce6281852441862b1b4c01a1c0352211d49204a46701f72c52287e4c8a8ffd8668e0227329e84b1e0a8d47418a4af44a6e80cba470a4a04c1817156a87f4ab7055389ab3b51dec6cd64cb8d7890b2d4bb85e4ab20ac3aca6762b0100640f92040be73906e68e8103a57669532120312fe50ddd47ac0b19151fd6137b16a09324948629b84fa2e7c8ec150fb8c7db1d800c0825ac18915be2529771b8390945e6da65f324";
    const KAT1024_ENC_M: &str = "bf233cf6121d41585b4af0ea74b35df7ed52bb5782107a8259cd4aecc3587e61";
    const KAT1024_ENC_K: &str = "bcf2efed1e45c35c5fafe170aac3f4f5b3ef11220ea6b9a254f0b90ee8d56b94";
    const KAT1024_ENC_C_SHA3: &str =
        "099d8327089ecc0cf27fb546bcaf8eb3e6fd224935ae397572df1c99bc2d80e0";
    // ML-KEM-768 Decaps (ACVP tgId=5, valid tcId=89, modified tcId=86)
    const KAT768_DEC_DK: &str = "cd4178d37142a91c7c597854df1b00e6147df88c58769b10b2a0b9bbd875fbe05ba228847d94c01ed4c57860339d6735b0f73788c495688395bcd51e4a36bcc15c1f3311162f8525557cbefa176d0fd8bcfff79843085b78c0ade09104ef77179927c37e739aaf7166cf6539c35097c0c3769051186572735b600c3eb07a412932650ca28d469d971b635d789c7fa608cbf819b7b7707291b9d22c25cbb55b0d875ea903ce778c81a2e96bf6e96baa1a484e69524c644fc3d8c564140e32d4ae0be1b1cc875cb4ec7764c498e5f01c04c9a41cf26bbdbc08c8e65bbda78a1c4c0f362aac60e16f5d225454c2103a99758b0a93864c5f32179808d2a3855ac837424e00f0a0a3055c07f5ab5bd04bc6950603960c29aa2b18c60c154a1022c32ef59bb718e94adef990c045c27e3943c115c1d12a96eba503a01098e33673c98b0421a7c71189530d08b4933912c37c1dcffb0a14a93a3ea6603a6035cc194c58532d70e2b1b7b0ca5254bd7e010d7409ca58973c7f2062eac9ba196429d7da3dd512c1d81182e17b7cec7c630659602c117f74008070e967f5f2293e9643cf70a1f5a38069d0359d76a84c6846ba1a1bb91b5279864b9671c3896bb2d43278de11b1a89b8f95f96a9ee815a6e7b063989a13d32080ca55d6c0421e6893b77632dcf96d09f11ac5a740029273cbeb42c7c96fd36c1ee5589f61d70b57e93b8405bdfaa460fa09be4a345b1d9939466806b9e462929240051b57dd614626a813bae8248a66c3c0bba804c52b345924a76cceed5468ec066dfd5a1770656f3a3b956531a6d4166cb36480235a4e62cc7a9dba2b45f464eb39002ba71a1211963a86b16880c83b3bbbefa5a7bc4b31b2a69c09d9675a4b300a829f6a438649e26b82a7cda8b80cb65986e47baa2f544cfde7b46cd17fcf1baae568bb28c8235c591ae717bbc05c0cf86344e4627542639fabb11bb5f6c66bbab92f981cf6bb217942b95f635e7ee75e314cc97f050276801b32bb86ca586e79c40638db283c3948da4c7195c4421a1b3bc35886678c33eb0a5a52ba5c78b138d51cac85704bc0140ca5b830117225cf4b0e363b8155eb4b83c7073bb20af2798376ba442d309577c62705c7a9172527faea9ce21b3863f32dae7a2d4b2314a376c14917563ae41de067007567a9e22bb30b834afef2b6b07846ac30b54104b8083248cd23afccf794c1f59c1c62803b28873013296f5048f0637dff072529443ffecb57e12a7f0ce52cc8a85d258372dcbb5c0612735d1a6ba7e0ae02215547b28f5e77488b3a241eabb2f3f19f89974b2d822604e74495a2091c363e9e88a7b80769d4492f6b7a7a3bb27da60a1ba326882b7732c9118e545b6c4b79787225ba598378bad7b3cae90edc06cd0eac43a2c559cd554c5344a2751952f4b4bd2bb694016b41f65494a1c750a9d9c338a25f5ae26bfe851540e6b84202114adb75986193737a5f28c2bc2658cd6c960fb0c069c910a8f259593f2770984c87178c29530b6e6424b70bea514f8568255b62ca6cc39340515ee1968aa800db4b19aa7676984b798ed5b134116cef52b5634c7997f33c58e18d1a64499b6450f247a3555ba2a4d44782e02ec6397c69764fd9c08f87e6b802a01bd3e77e0f544cc39944d86a5225878b435b260bd6236f2a68ee1440ab7c06f93991c7fa6aaff20a1d862d7c73686f071cc7e6624a5b5568e10cb3c23e6fccca3fbc63c445472a235758129fd8067b839588a7221c250791243a8c020cccbd29425201a53bc84621412cdd0ba72ac75d2da4a13f26a59a7629bc372e78d54776f2c781b99b9110b4833c9e69136a5098bc7fd3a4fa9c3280557eaeeb89d0b15af4016452e42eb0d608d5850bb7491d8db6c703bb8d00251d69950df0e99553160122d4c5fbab7be3727f74da52ba2a240cb5140b9704a7742d17113022b9260a15cc6a9ccbf23349ad94b57b04a29d3859badcbf979515b433c86008bb43e010a2c7aff8ec7bfe508b7565b6b3898459599fdb830b7461c1c1c52b145b2829e59f09b0ca28863c70ca1d8a7aadaf6b0fdfaa45096268505a70af267da7771555d66802405f72d190189411c5a0bbf7a7185f857edd5a4aefc948b6b6997c3bb9ffac18153785ff752481839cb39027709a8306538687f2501118617e5c8a67e41a2c856dbb274be4fb17ea47097f81693ed7389b21c8eebc200f601dd2d78e89ebb919d9387768311e04c9894b08e73c4122b41d334a56e930084645c000e21c7738765bd02fa9f6a7a3188b15739f50ab5ef1713879d94b19964fd272a949a275e289a7c0ba9eb52558926146a280b1036501dc76400993ba71698afc4318e38847c3f77134d7300f211862f6078bf3685928c5a8a809a945be058b4a2e000e25e88eb7907bb7977993d9c0183248fdbb8106ea3ade37b4b7b8a2e139c2aa19088c25227fc5bdd59826f6fa15462301eeca0f4b76bc8992891d066b41700701b10d37899898ac9e69f7257f9330bb0770e0621417ac392d7685c7e47497d096dd0b26161b8a41ca9d9d67664c8120de5c4ed303c5926126b58979c3f7300ea8533ac0cbf32178a0531ca634634b46b097b367fb2612ea461ac8e04dcda2c5eb9543457969f9481457188a56e115dd965a810c3cf3217cfbbc51cc316d7799107b20256ee08ddfa87cf318a92d489c030ac57c25344182a5c8b770f0e4b8c03838050cc56a0b91fe84c46034c8dad78f74161d0e93a9b9c4cfba5384d023981ab6734977b1e0f900443b4b62f6bdf3227570acb36b0b2e5d69cdfd9b7a05f45300e5a8918290cb0968ff1363c6048fdcb53f63207bc841bc3c900074e48ab4c73c38662f66c9996b3a926de61a0b784e2a392e93db87ea841a190a6002c9b4bf237003e79961c07f156b606ac861ece75f44ac60717871fb3b0cc2d9c987aa768eac3497b9893eb809ea4a8b24b144c2bb014a8a7d51d94fa5a05bef7c47459260d2ccb035806f286793343acbcfd207fd086b00cd517979abba9159c889bc6191290beb2aa793ba19da9ddd6275b430182eac87c5b27115029a696cae0afa5c38aa506f486ff52b6a9eac1414516f7fc34255633b1abb7252218a67c213966ba6fb237a0a43b59e45c0a34902494359b19304d9f04cd432715a17c70432680de20fbc1bcbdddc3c24037573d9a22fdb34f987c610a9799861369288405a138cd4850b14393a6b6344fcc38cbf07875f37a3ca04da17cf188e017e8cee406db439078d7b0e5170aa973c154d3ef4a59628ed3739622864bd402c715eb878247bcaf1f1070aa50599421d778cce8ffe07bdee87dd36086fb6fcd1edb33aa50ea330f9abd98f1d6117191bb3caacb0e3f2c139";
    const KAT768_DEC_C_VALID: &str = "997f33a26049e8467f96e36b0f30a68ba7b99cb86a65dec373dc53388ffcd140bddb7f966064c3f95766ebb90482089a136ebbc5727b8cfea68f1a5119817735eb71eee31444fdb38f70b67b9560d8ef6d807e3339b1c824047233ad57d8d4adcf2097b017487bfabc85f6d23c6449cd2d0a8dab7aee9bfffc5a2a1fcfecb289d1940a11bf1573945971d2e80d117b00ea95aa06be7e7a91dec35b291f971e790b4bff8a07d6099e40232746e550470a64205de84911c1e8eb88dceb615b43792d040031c38d1bfe55108b18e64706fd7e26384e31970655e033c26d7c27595dcdb469a95f5a19727b38d150cd8538b5ccc14936e49a0d92692273c3ca9ebfb2ac760a77b527e3e2b537d50900819f5d1274d4f4952f1c776f0ba4e01df91de2d51afd4e2fe9b98208b60313961140188ec6f9ab0e8b346cb3306a2bff3734958163a66663b93b7f5a0e3863c37b3d2803b7c29ea6ec49dacfe6ddc589ea41c4d0543c8a8e05092b0eb2956d974042b0cb522da76f8f611bf9fc956917922c010d7ddb50563abc7479f05e7d80b583a3335afbe569f6f3d5683eb131c6b3f2a0b5284ebe03eea6cc7c3435ee7b47b1680122a562428c936ddd90aad907989a4bd26730f444900a48889582eaf39897fe19d3cac3b08d28b0e663b7cf2c30c6cfd6b73dc227e6267503cf8ec2def07af399fa171e31248f23b8ddf33ba95c463df012e20170204ed8c3a6bdfafbe82a398fa5ee2e61fac25a0107614d7545421a4ea899f0dbd2a1c34517004764c15ecb0a8bf41dad12b5b555ed4a29d4240d6060ea3f9cbc08991f140a7ccd886b2b6a4ee6a0f87afaa9169aad9f354851e7513ef9c85c109d617563f42057866b9cbcfba2733ab06fbdca8d4350f8afac77bc28758ce2435196a281f13096235077ae75ac0ecb09dd123469b645796a8153c158934bec4c7b40174a002b6993fdbc39f187e69e465cf773515beadda077b13271d24d8c2e05f02fc8dda19f7ab0ad5d8deb5f4aa124e3ef5288e4c8c46027ab067b94e130c41460b68be068c6be2c62a3772e23cd13cdfa36d01b21b62b166c0955c728c234970731d73c1bbc1967178ee146803e81772549377872cc46ebe017ecf40955dfe47a98f6a2b85e51a9e8f9070d844e24c3f4bbfc11392c87dacf1f963ca1c91fea33abfc662fdb709b7adaf81ac17740bbb2699a40d1d162ff55f277b7a9a3be7e8081a203f4c08284c8637994b0692b66cca611177bc2fb9850a367dad0b7abab85c88880947bad9c02d54ea60ec0d9c7c36ce1a62c3cc7fa15bf22ce2b292886485e496af718aff7a8c64915d9267d3ab89d47317fad00dcb2bfb4953cf90a3cb849d87eb4ff67f1850684e2fd2ad26bb6681c50ce8b9817cfe1c1e4f30e07adc3022020361b1bad3c98a49fe3d0d75a2a7dab6e3e665a3e801f6f124a00818dfabe19a22cc684c5bdfb94af3823294367f95c9ce3d8accc91faebddd096adc90543744ba5fc61bf166b8e9ac1dc03fda0ce29755b17ddef3c";
    const KAT768_DEC_K_VALID: &str =
        "96980f7c1b160a45a8f56fb38d38d7faec7844ddf617fa47522ca2998605a71c";
    const KAT768_DEC_DK2: &str = "bc4775a9a1393e32c28976cdcfda0e25f9192fd11ba2175a7b9608b591c63501194fe6606af76b9f1b22cd2b4d6f86a20fe4039df0812d78889ca25a31b130a3c9092407448c0318600612cbeb81ddf8a3b760309a5a4c928b0f72f9c8cf530675d46a683261c60108820a9b48751dcbc62526196b02e23892e93a784796b87a99e78c1c348107b68a56eb3874ec63258eaa2b61d70da2491c0b1c667bf55dd5a373efd61fba302281e588f7180b620500d90148e6805be7e17b05608b2b716017ec87235ba27b0a8ba5f40ee18b0015f9af1bf3bcd729bd79dc231f603273669a79f5ad09e2a146f2b8782a64fad55f0e8b6894cba795f59e9d2211caca8d39ea6e30da6c5ad475b2410aa6c73ce0e622a09008ace68f1e80906b1426b54b723f4b5ec5a9cb831756fc7580b82a149e31485bc84f05b8c37a61813dbc445e56c081bccba33147c3a7152378a6ae6a8639029e1d451811e9b5d11c9e80c9026326b9e13066afbc734faa8f4f45452b172085a48d9c445c66d6b95b12321d286d4b0b4df12678e9e973a1fc2bb4bbb579b648766b5e7170424825199ae1a0add60c4da2466302b06a9c4e15b1c423a461f50802e1559d36cc5808d6b2c37a5f5b797b6d24a7d659c7d0a99fd4f4a9b05700afb90cc830355a5bb73aab91dba6ccc5217911725fc5e8ce41d012c3f640093c00649a3373e4cdda657607833da75cab69388d0e40aee4e8abbc5750b2701b77bc7dbea983b42ab0714a8acd6225a054672ca32938fc967e26282414b06c809827e1c4c3098396bb9dd3da763e3b9d35dcad3c4cb20d64c27e15a3203980f754739c091c28e11d0d4caf6976a81d087b99e84b73a28c52179ea40a8c12c8634e5b8f6da6cdd8c89a8ea08fb7664bcb9491c90b767138bcff701ec9cbc4aa91a45b8a13ccc63b6903c8d5e2aeefb4883fe7a4d5e55e2b2b67a483132a18546ea5986b27c9a34a4404254c2a37744b6914d1194d9afa4caf6bb45d3bca763c88f3e67776a3796e2a9e7d797ec4195f89118c98457b8d94c6abdb770be3ab67cb7c0af38d84bb6eb96c6989221680120074fc3e6126539c93b17411c3000d725354c6a8e582eb76c399d1be6582b10737bff083177958130a603df9b37ff8356c06b1718f4205eb3c6e5dc56f8016900c9a8fce3092803ace13ec14b9715a2fb96f2942c95cd4cd6d1a68f16b495826bcf8085620a98b4c10a86d072e68220579ab2783442317581d1ff5cc734164bd08b788514bf171a3446229f949038e814de557a76359493d193a67b57a5165621a3090bf50c807f68a0f570435a712db001c8f3078a3041af3ea64d6901da5f731d9e3732d34152dd3c4aaec3b6ba2755cc70c79a906e69860b4d15a5bd62a8d98b41ba39eddd65618f2327347ba5ea977750a48a85ba249c2b9d080b114a56e6eec4e9acb6ef9caa51b2134b6752847471e23b82385922efad11daedc882350b3c8e67bd3a8bd7ba052fae55b91798b89851b1e1b3aee041efb66729c508e9ca9c550807ee26619b6c251171c9552d787b57a38491b053c7c72a528bb79c8377ed0b596c57238435abd1b7458b3b9aa1b70485271e18731e8a3a67ed034de1b1459e2c251e55c2fa5a0c3842e2bf65c0e6ba46215c0c4f94d6af8b455ab329c92bf330104993c550bc9149be0b705407b4d7459e12aa93b337e630597e8d7483fb403e8ec7e3f0aaf19cccb04c6c29a4a0db8a9c32ac8729b62cfa90855704383c49c9bd7b0020899a8ca0266e5875eec2c826a530af7951ecf280bc33b6158674108d3287d087b656858d22a4063977e4cf04890c18b9ab09e302562e6baa32f6c07ced990372771d04a13a9f90c8d87b9339c8aa8f47170e5aeb6fbca56b448da78122894732f62b5c2e88d53077d91d3c933c741a4c704fa91651cbc81628a3bb2356ec6da2444f83b2c301ad6cbae21e0583cb24f05b3bc746805536c3e1f65c1fc0044f2f36230f21232c84a7f2ca325b85ac0c470ea02a6046a4ca22355a4f56715589890c6366de1972c081e3a7362e380aa4af3913fd284d8a33ab5ca04886bc7e52b03a6e153c1bb39de929a5a0339f921be4baa63614500eb8497efa27c69e661ba500d3ac661a135304e425e87b371a3e20d3567929903c8363b8c4f33c4cf1975b99980d60638caf44800868f508b8b2756af4572554e49c4c655065cd576e28310e665104ae51109b7b7404018a4a66f49743a1bc182ad32cb6c029860c45fa2292d408934608205124082c4998848517dd8b418a33935aee37c8a551cdfd1b32f1aa901ac1c616343a93c542bc6cbb147025069491ac14c9bebc156947d9328a373d2843ab877551a862a8a7a554249668c08cc388333f33bfca60b4e0abcee33260ff3b3d8347d1dcc231a247f88d3c2204b9aa4f429b58015f358727409c53247048b887f213593b37461c7d4a11702b84083400235c54bb79a70e8306cb01b6183649c5684e6e8493cc0afba6a90aa9c44d13bc56e71b32b3b7fb965176a96afc350a39e27bc083064167c5b4d652447815dbb4ac68a7bbf355972f4ea4d0f2099955c40ddbc6ab6c832baf1c41351cd88e93318cb5926f20acefc688dc48247b9027e7800e772cffce51eb50c79ee39cac8784377181bc6a373675c133200484d54230f610799d04a79da6ec5e82d4ea75a26015e7725392da31ec1e644d151bd4fc5c808f76da16a2eb0e7b279227f3000c2a6f3bdcebc75622b2c684c800848ac55490edc119756165c5a2560a385781ae34ebeec3c7718725433b0911aafc09ab641e5be03c6c6b5d42485e83d98e79689ac4a7e4a0ea95652583b6db8465e7a2064528ab62ac555e249ccb5f028682981e3d70efb64a556462814b094fd5c952e1541bc1cb735ab273b220b0e5a4661e78e02f913bb0875287535bad77fb82786cf564ed0cb53bbd42249664b1d20122a1851b482b64705165d17804ac43e647728cfe9c87b4a91ccb54700dbb88af79150c831bc4255eb06763448ba80f0afd0da840fe643c59035327a401af141e2981b0d630a52d633a690b9cc31197aeb78ce5983bfd3044df438fb983f8fc28c9925c435a5ba796cb776daccd52995ccc281d007b0d0f1a697e766b4a09327e656c9825cc4d983a0809dc7e000049abf49ecc337c72255835806ca55e91767d6f860b638030a0a9671fcb7ca8647faa932a7814127e55268c90e41045a7cf577ce1c5c3d3792b183a5052581419f93cb0b1927c168ded5089b2d0991b923ddd0c6084681a60137caa6b28acbb363711316dce101ccd5c056296502c26be239b505a01db7291efe1f52377053382045516057442b00aa7fb31c1a0ae0718e911821f7044512a8";
    const KAT768_DEC_C_MOD: &str = "38e6d9f5e24cc216630e8b9fcc01fd6e724dd31b55c22c76bc3f4f3a151f6369e313acefecc22b11bdec684c3e7d6dcb7656586cd41c553bd3fb730d17768f89ab9f51a2b18ca3dced1ea271148f23bb02948f6c38343d33d1de3e2ddbe507df7a96d2c6123b9c75e4f96fea0e8f3a048ab0870ed63e94e5a45db461d7eabc338f66f0aa5d939b1f1da50e1172fe01682a29563b2d25b06da0910f782da04b7c69bb5796897f48c338044d702b1819c04327b21eb3ce9c2a5533e20dff5b18eb1310a05cb46cccdfbddc0f2e9c348a03f02e01a7425a2a75d97427e570d4c20ce3ec0c27c6228c5076119211e6599a6aa300ad952fe05ac0059a7cdb80a20d6fd91d8d6c1ea05d56098e387e1cabdad4968ab37d6dc4d26e0cfa953b7eeb6044aa2c52a73f700090d970ec5461e1b4563cdd94d8e79e730ae41a9a1ce7a43e49735450df09e3111dc2c35560c90f8c98cf3d5235a17679cc7dedc0bc71933b9f4623436294d06f2f072b31ec9c9b803e8d8d6a7e6d1fc4556b704aec6a7c82262a1f2a31eab9de97416349b7cd7dc34333b8e40e928f94c4dd19eb762ce02a6bef2d503db5fc57894e7cf236821274a79262a05527f079d4d0e513fd9a786d826b667c0656681f13eb2599590ad9854c9e5378d8defc5d688b861bf5be6847d475d435f8ac78e3f5a3ed162c6d7534a8faaf8366c12b095cc1c4724d12da31b32f229c3ccb328f28e1ac46c48bae3c9608feee472430aa40f9906aebfeb7650788582b60404586805ce870fbca22cad8ff251e6a61384ae1092282d87eefefeaff9dca2e4b6b1fe7920e860de8b2232dda16933323462b1433ec7c2e236b1eb15c0a79dcb264537c42b6818c8d2bff3afda6deead3fd3493afc799d5a74f2718c15d959819b6a5e8be3e580edcea1a8f96683c7ee318e704f312f9efc26ce0fdaaa6a389930514a1c97ac0d8dce8516ec8bcc15e5c6436ab49b819d004ccaa90398ad1c13bb5c2fe9a537a9f6c29692de939f3c9e87f6732bc85456f3e596d86988b69a4cc813aadf1ec0a2e7d10f60822cc415276a204cd2c1844ddbdfac8d910c5384a5ed2c8d9b8160a5b74bb3efcfe7484b4742cbce861800993d68eb9431f40d495428f9eabe3cc530ab7a9410fcabcd1c9cfae431e652af9ee19eae0f5433def0cba53936e3369bf479a5287b5fd271d0b9f0c294b759dc59f8b0b470d9bf98eb496ee1149abac53ca0665d64c16e0069b654ec376c66c456adc29bf1f6dcae4afc020b9783d3f85c48c479e583c477e2218061b9b82efd0a6a9c9440014b22f9458719191e4baa1b90c30789974efca17c8dd78cb09eddee078bfcf5b44b21c7559b9b29a06532d416cf83d3c205e06f0402f89a88e24135948e3a8bdb9dc2e9cd99919cd69b41a51a6211bf2589fd457be77ca4bca6c97da0dcaa1f4ddb886315137212e93877fc8c23e4260a7dfe9679458876026a6044663c42231a1ab5d1ba9dd7bb05e236b80ad48cb9fae69da66dddbba337090849f4b6916e2";
    const KAT768_DEC_K_MOD: &str =
        "9652336bb52a7ad8f781e6d8c00e798fefa7071211d39fc9987779727fd9270c";

    #[test]
    fn ntt_roundtrip() {
        let mut f = Poly::zero();
        for i in 0..N {
            f.0[i] = ((i as u32 * 7 + 1) % Q) as u16;
        }
        let orig = f.clone();
        ntt(&mut f);
        assert_ne!(f, orig);
        ntt_inv(&mut f);
        assert_eq!(f, orig);
    }

    #[test]
    fn ntt_multiplication_matches_schoolbook() {
        // (X + 2)·(3X + 4) = 3X² + 10X + 8 in R_q.
        let mut f = Poly::zero();
        f.0[0] = 2;
        f.0[1] = 1;
        let mut g = Poly::zero();
        g.0[0] = 4;
        g.0[1] = 3;
        let (mut fh, mut gh) = (f.clone(), g.clone());
        ntt(&mut fh);
        ntt(&mut gh);
        let mut h = multiply_ntts(&fh, &gh);
        ntt_inv(&mut h);
        assert_eq!(h.0[0], 8);
        assert_eq!(h.0[1], 10);
        assert_eq!(h.0[2], 3);
        assert!(h.0[3..].iter().all(|&c| c == 0));
    }

    #[test]
    fn negacyclic_wraparound() {
        // X^255 · X = X^256 = −1 in R_q.
        let mut f = Poly::zero();
        f.0[255] = 1;
        let mut g = Poly::zero();
        g.0[1] = 1;
        let (mut fh, mut gh) = (f.clone(), g.clone());
        ntt(&mut fh);
        ntt(&mut gh);
        let mut h = multiply_ntts(&fh, &gh);
        ntt_inv(&mut h);
        assert_eq!(h.0[0], (Q - 1) as u16);
        assert!(h.0[1..].iter().all(|&c| c == 0));
    }

    #[test]
    fn compress_decompress_error_bound() {
        // |Decompress_d(Compress_d(x)) − x| ≤ ⌈q / 2^{d+1}⌋ (FIPS 203 §4.2.1).
        for d in [1usize, 4, 5, 10, 11] {
            let bound = Q.div_ceil(1 << (d + 1));
            for x in 0..Q {
                let y = decompress(compress(x, d), d);
                let diff = {
                    let raw = (x as i64 - y as i64).rem_euclid(Q as i64);
                    raw.min(Q as i64 - raw)
                };
                assert!(diff as u32 <= bound, "d={d} x={x} y={y} diff={diff}");
            }
        }
    }

    fn kat_keygen_hashed(p: &MlKemParams, d: &str, z: &str, ek_sha3: &str, dk_sha3: &str) {
        let (ek, dk) = ml_kem_keygen_internal(p, &hx32(d), &hx32(z));
        assert_eq!(hex::encode(sha3_256(&ek.0)), ek_sha3, "{} ek", p.name);
        assert_eq!(hex::encode(sha3_256(&dk.0)), dk_sha3, "{} dk", p.name);
    }

    fn kat_encaps_hashed(p: &MlKemParams, ek: &str, m: &str, c_sha3: &str, k: &str) {
        let ek = MlKemEncapsKey(hx(ek));
        let (c, key) = ml_kem_encaps_internal(p, &ek, &hx32(m)).unwrap();
        assert_eq!(hex::encode(sha3_256(&c)), c_sha3, "{} ct", p.name);
        assert_eq!(hex::encode(key), k, "{} shared secret", p.name);
    }

    #[test]
    fn kat_ml_kem_512() {
        kat_keygen_hashed(
            &ML_KEM_512,
            KAT512_KG_D,
            KAT512_KG_Z,
            KAT512_KG_EK_SHA3,
            KAT512_KG_DK_SHA3,
        );
        kat_encaps_hashed(
            &ML_KEM_512,
            KAT512_ENC_EK,
            KAT512_ENC_M,
            KAT512_ENC_C_SHA3,
            KAT512_ENC_K,
        );
    }

    #[test]
    fn kat_ml_kem_1024() {
        kat_keygen_hashed(
            &ML_KEM_1024,
            KAT1024_KG_D,
            KAT1024_KG_Z,
            KAT1024_KG_EK_SHA3,
            KAT1024_KG_DK_SHA3,
        );
        kat_encaps_hashed(
            &ML_KEM_1024,
            KAT1024_ENC_EK,
            KAT1024_ENC_M,
            KAT1024_ENC_C_SHA3,
            KAT1024_ENC_K,
        );
    }

    #[test]
    fn kat_ml_kem_768_keygen_full() {
        let (ek, dk) = ml_kem_keygen_internal(&ML_KEM_768, &hx32(KAT768_KG_D), &hx32(KAT768_KG_Z));
        assert_eq!(hex::encode(&ek.0), KAT768_KG_EK, "ek mismatch");
        assert_eq!(hex::encode(&dk.0), KAT768_KG_DK, "dk mismatch");
    }

    #[test]
    fn kat_ml_kem_768_encaps_full() {
        let ek = MlKemEncapsKey(hx(KAT768_ENC_EK));
        let (c, key) = ml_kem_encaps_internal(&ML_KEM_768, &ek, &hx32(KAT768_ENC_M)).unwrap();
        assert_eq!(hex::encode(&c), KAT768_ENC_C, "ciphertext mismatch");
        assert_eq!(hex::encode(key), KAT768_ENC_K, "shared secret mismatch");
    }

    #[test]
    fn kat_ml_kem_768_decaps() {
        // Valid ciphertext: decapsulation recovers the official shared secret.
        let dk = MlKemDecapsKey(hx(KAT768_DEC_DK));
        let k = ml_kem_decaps(&ML_KEM_768, &dk, &hx(KAT768_DEC_C_VALID)).unwrap();
        assert_eq!(hex::encode(k), KAT768_DEC_K_VALID);
        // Modified ciphertext: implicit rejection must produce exactly the
        // official J(z ‖ c) value, not an error.
        let dk2 = MlKemDecapsKey(hx(KAT768_DEC_DK2));
        let k2 = ml_kem_decaps(&ML_KEM_768, &dk2, &hx(KAT768_DEC_C_MOD)).unwrap();
        assert_eq!(hex::encode(k2), KAT768_DEC_K_MOD);
    }

    #[test]
    fn roundtrip_all_parameter_sets_random_keys() {
        for p in [&ML_KEM_512, &ML_KEM_768, &ML_KEM_1024] {
            let (ek, dk) = ml_kem_keygen(p);
            assert_eq!(ek.0.len(), p.ek_len());
            assert_eq!(dk.0.len(), p.dk_len());
            let (c, k1) = ml_kem_encaps(p, &ek).unwrap();
            assert_eq!(c.len(), p.ct_len());
            let k2 = ml_kem_decaps(p, &dk, &c).unwrap();
            assert_eq!(k1, k2, "{}", p.name);
        }
    }

    #[test]
    fn implicit_rejection_on_forged_ciphertext() {
        let p = &ML_KEM_768;
        let (ek, dk) = ml_kem_keygen(p);
        let (mut c, k1) = ml_kem_encaps(p, &ek).unwrap();
        c[0] ^= 1;
        let k_reject = ml_kem_decaps(p, &dk, &c).unwrap();
        // Implicit rejection: no error, but a different (pseudorandom) key.
        assert_ne!(k_reject, k1);
        // Deterministic: the same forged ciphertext rejects to the same key.
        assert_eq!(ml_kem_decaps(p, &dk, &c).unwrap(), k_reject);
    }

    #[test]
    fn encaps_rejects_non_canonical_key() {
        let p = &ML_KEM_512;
        let (ek, _) = ml_kem_keygen(p);
        // Wrong length.
        let short = MlKemEncapsKey(ek.0[..p.ek_len() - 1].to_vec());
        assert!(ml_kem_encaps(p, &short).is_none());
        // Non-canonical coefficient: force a 12-bit value ≥ q into the
        // first encoded coefficient (0xFFF > 3329).
        let mut bad = ek.clone();
        bad.0[0] = 0xff;
        bad.0[1] |= 0x0f;
        assert!(ml_kem_encaps(p, &bad).is_none());
    }

    #[test]
    fn decaps_rejects_malformed_lengths() {
        let p = &ML_KEM_512;
        let (ek, dk) = ml_kem_keygen(p);
        let (c, _) = ml_kem_encaps(p, &ek).unwrap();
        assert!(ml_kem_decaps(p, &dk, &c[..c.len() - 1]).is_none());
        let short_dk = MlKemDecapsKey(dk.0[..dk.0.len() - 1].to_vec());
        assert!(ml_kem_decaps(p, &short_dk, &c).is_none());
    }
}
