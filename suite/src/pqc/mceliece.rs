//! McEliece — code-based public-key cryptosystem (1978).
//!
//! McEliece is the oldest post-quantum public-key scheme still considered
//! secure.  Its security rests on the hardness of decoding a random binary
//! linear code (NP-hard in the general case).  Classic McEliece is a NIST
//! PQC standardisation candidate.
//!
//! # Construction
//!
//!   - Pick a binary Goppa code C with parameters (n, k, t):
//!     n: code length
//!     k = n − m·t: dimension     (m = log₂(field size))
//!     t: error-correction capability
//!     The code is defined by a *support* L ⊂ GF(2^m) of n distinct elements
//!     and an irreducible *Goppa polynomial* g(x) ∈ GF(2^m)x of degree t.
//!
//!   - Public key:   G' = S · G · P, where
//!     G:  k×n generator matrix in systematic form for C
//!     S:  random invertible k×k binary matrix  (the "scrambler")
//!     P:  random n×n permutation matrix        (the "permuter")
//!     The transformation hides the algebraic structure of the Goppa code.
//!
//!   - Encrypt(m, G'):
//!     Pick e ∈ GF(2)^n with Hamming weight exactly t
//!     c = m·G' + e
//!
//!   - Decrypt(c, S, L, g, P):
//!     c' = c · P⁻¹            (still has weight-t error)
//!     Patterson-decode c' over Goppa(L, g) → m·S
//!     m   = (m·S) · S⁻¹
//!
//! # This implementation
//! Educational toy parameters: m = 6, n = 32, t = 3, k = 14.  These are
//! *vastly* too small for security (Classic McEliece uses m = 13, n = 6960,
//! t = 119 with public keys of about 1 MB).  The implementation prioritises
//! clarity over speed; in particular, polynomial multiplication is
//! schoolbook O(n²) and the decoder uses a generic Frobenius-based square
//! root.  For production, use the `classic-mceliece-rust` crate.

use crate::utils::random::random_bytes_vec;
use rand::Rng;

// ── Parameters ────────────────────────────────────────────────────────────────

/// Bits per GF(2^m) element.
pub const M: usize = 6;
/// Code length (number of support points).
pub const N: usize = 32;
/// Error-correction capability.
pub const T: usize = 3;
/// Message dimension (k = n − m·t).
pub const K: usize = N - M * T;

const FIELD_SIZE: u32 = 1u32 << M; // 64
const GF_PRIM: u32 = 0b100_0011; // x^6 + x + 1, primitive over GF(2)

// ── GF(2^m) field arithmetic via log/antilog tables ──────────────────────────

/// Precomputed log/antilog tables for GF(2^m).  `exp[i] = α^i` and
/// `log[α^i] = i`, where α = 2 (primitive element).  `exp` is doubled in
/// length so additions of two logarithms can be looked up without modular
/// reduction.
#[derive(Clone, Debug)]
pub struct GfTables {
    exp: Vec<u32>, // length 2*(field_size-1) = 126
    log: Vec<u32>, // length field_size = 64; log[0] is unused (sentinel)
}

impl Default for GfTables {
    fn default() -> Self {
        Self::new()
    }
}

impl GfTables {
    pub fn new() -> Self {
        let mut exp = vec![0u32; 2 * (FIELD_SIZE as usize - 1)];
        let mut log = vec![0u32; FIELD_SIZE as usize];
        let mut x: u32 = 1;
        for i in 0..(FIELD_SIZE - 1) as usize {
            exp[i] = x;
            log[x as usize] = i as u32;
            x <<= 1;
            if x & FIELD_SIZE != 0 {
                x ^= GF_PRIM;
            }
        }
        for i in (FIELD_SIZE as usize - 1)..exp.len() {
            exp[i] = exp[i - (FIELD_SIZE as usize - 1)];
        }
        GfTables { exp, log }
    }
}

#[inline]
fn gf_add(a: u32, b: u32) -> u32 {
    a ^ b
}

fn gf_mul(a: u32, b: u32, gf: &GfTables) -> u32 {
    if a == 0 || b == 0 {
        return 0;
    }
    gf.exp[(gf.log[a as usize] + gf.log[b as usize]) as usize]
}

fn gf_inv(a: u32, gf: &GfTables) -> u32 {
    assert!(a != 0, "GF inverse of zero");
    gf.exp[FIELD_SIZE as usize - 1 - gf.log[a as usize] as usize]
}

#[allow(dead_code)]
fn gf_div(a: u32, b: u32, gf: &GfTables) -> u32 {
    if a == 0 {
        return 0;
    }
    assert!(b != 0, "GF division by zero");
    gf.exp[(gf.log[a as usize] as usize + (FIELD_SIZE as usize - 1) - gf.log[b as usize] as usize)
        % (FIELD_SIZE as usize - 1)]
}

// ── Polynomial arithmetic in GF(2^m)[x] ──────────────────────────────────────

/// A polynomial in GF(2^m)[x], stored low-degree first (a[0] is constant term).
type Poly = Vec<u32>;

fn poly_trim(a: &mut Poly) {
    while a.last() == Some(&0) {
        a.pop();
    }
}

fn poly_deg(a: &Poly) -> isize {
    if a.is_empty() {
        -1
    } else {
        a.len() as isize - 1
    }
}

fn poly_add(a: &Poly, b: &Poly) -> Poly {
    let mut out = vec![0u32; a.len().max(b.len())];
    for (i, &x) in a.iter().enumerate() {
        out[i] ^= x;
    }
    for (i, &x) in b.iter().enumerate() {
        out[i] ^= x;
    }
    poly_trim(&mut out);
    out
}

fn poly_scale(a: &Poly, c: u32, gf: &GfTables) -> Poly {
    if c == 0 {
        return vec![];
    }
    a.iter().map(|&x| gf_mul(x, c, gf)).collect()
}

fn poly_mul(a: &Poly, b: &Poly, gf: &GfTables) -> Poly {
    if a.is_empty() || b.is_empty() {
        return vec![];
    }
    let mut out = vec![0u32; a.len() + b.len() - 1];
    for (i, &ai) in a.iter().enumerate() {
        if ai == 0 {
            continue;
        }
        for (j, &bj) in b.iter().enumerate() {
            if bj == 0 {
                continue;
            }
            out[i + j] ^= gf_mul(ai, bj, gf);
        }
    }
    poly_trim(&mut out);
    out
}

/// Polynomial squaring in characteristic 2: (Σ aᵢ xⁱ)² = Σ aᵢ² x^{2i}.
fn poly_square(a: &Poly, gf: &GfTables) -> Poly {
    if a.is_empty() {
        return vec![];
    }
    let mut out = vec![0u32; 2 * a.len() - 1];
    for (i, &x) in a.iter().enumerate() {
        out[2 * i] = gf_mul(x, x, gf);
    }
    poly_trim(&mut out);
    out
}

/// Polynomial division: returns (quotient, remainder) such that a = q·b + r.
fn poly_divmod(a: &Poly, b: &Poly, gf: &GfTables) -> (Poly, Poly) {
    assert!(!b.is_empty(), "divide by zero polynomial");
    if poly_deg(a) < poly_deg(b) {
        return (vec![], a.clone());
    }
    let mut r = a.clone();
    let q_len = (poly_deg(a) - poly_deg(b) + 1) as usize;
    let mut q = vec![0u32; q_len];
    let b_lead_inv = gf_inv(b[b.len() - 1], gf);
    while !r.is_empty() && poly_deg(&r) >= poly_deg(b) {
        let shift = (poly_deg(&r) - poly_deg(b)) as usize;
        let coef = gf_mul(r[r.len() - 1], b_lead_inv, gf);
        q[shift] = coef;
        for (i, &bi) in b.iter().enumerate() {
            if bi == 0 {
                continue;
            }
            r[i + shift] ^= gf_mul(coef, bi, gf);
        }
        poly_trim(&mut r);
    }
    poly_trim(&mut q);
    (q, r)
}

fn poly_mod(a: &Poly, m: &Poly, gf: &GfTables) -> Poly {
    poly_divmod(a, m, gf).1
}

fn poly_eval(a: &Poly, x: u32, gf: &GfTables) -> u32 {
    let mut r = 0u32;
    for &c in a.iter().rev() {
        r = gf_add(gf_mul(r, x, gf), c);
    }
    r
}

/// Extended Euclidean: returns (g, u) with g = u·a + v·b for some v.
/// (We don't need v for this implementation.)
fn poly_gcd_ext(a: &Poly, b: &Poly, gf: &GfTables) -> (Poly, Poly) {
    let (mut r0, mut r1) = (a.clone(), b.clone());
    let (mut s0, mut s1): (Poly, Poly) = (vec![1], vec![]);
    while !r1.is_empty() {
        let (q, r) = poly_divmod(&r0, &r1, gf);
        let s = poly_add(&s0, &poly_mul(&q, &s1, gf));
        r0 = r1;
        r1 = r;
        s0 = s1;
        s1 = s;
    }
    (r0, s0)
}

fn poly_inv_mod(a: &Poly, m: &Poly, gf: &GfTables) -> Poly {
    let (g, u) = poly_gcd_ext(a, m, gf);
    assert_eq!(g.len(), 1, "polynomials not coprime");
    let g_inv = gf_inv(g[0], gf);
    poly_scale(&u, g_inv, gf)
}

/// Square root in GF(2^m)[x] / g(x): √v = v^(2^{mt-1}) mod g.
/// In a field of order 2^{mt}, squaring is a bijection and its inverse is
/// the (2^{mt-1})-th power.
fn poly_sqrt_mod_g(v: &Poly, g: &Poly, gf: &GfTables) -> Poly {
    let t = g.len() - 1;
    let mut r = poly_mod(v, g, gf);
    for _ in 0..(M * t - 1) {
        r = poly_square(&r, gf);
        r = poly_mod(&r, g, gf);
    }
    r
}

// ── Goppa code: parity-check construction and Patterson decoder ──────────────

/// Build the t×n parity-check matrix over GF(2^m): H[i][j] = α_jⁱ / g(α_j).
fn parity_check_gf(support: &[u32], g: &Poly, gf: &GfTables) -> Vec<Vec<u32>> {
    let n = support.len();
    let t = g.len() - 1;
    let mut h = vec![vec![0u32; n]; t];
    for j in 0..n {
        let aj = support[j];
        let g_aj = poly_eval(g, aj, gf);
        assert!(g_aj != 0, "support point is a root of g");
        let inv_g_aj = gf_inv(g_aj, gf);
        let mut p: u32 = inv_g_aj; // α_j^0 / g(α_j) = 1/g(α_j)
        for i in 0..t {
            h[i][j] = p;
            p = gf_mul(p, aj, gf);
        }
    }
    h
}

/// Expand each GF(2^m) entry into m binary rows: produces an (m·t)×n binary
/// parity-check matrix.
fn expand_to_binary(h: &[Vec<u32>]) -> Vec<Vec<u8>> {
    let t = h.len();
    let n = h[0].len();
    let mut h_bin = vec![vec![0u8; n]; t * M];
    for i in 0..t {
        for j in 0..n {
            let v = h[i][j];
            for b in 0..M {
                h_bin[i * M + b][j] = ((v >> b) & 1) as u8;
            }
        }
    }
    h_bin
}

/// Patterson's decoding algorithm.
///
/// Given received word `r` (length n binary) with up to t bit-errors against
/// a Goppa code with support `L` and Goppa polynomial `g`, return the
/// codeword (corrected `r`) and the error pattern `e`.
pub fn patterson_decode(r: &[u8], support: &[u32], g: &Poly, gf: &GfTables) -> (Vec<u8>, Vec<u8>) {
    let n = support.len();
    let t = g.len() - 1;
    assert_eq!(r.len(), n);

    // Step 1: syndrome S(x) = Σ_{i: r_i = 1} 1/(x - α_i) mod g(x)
    let mut s_poly: Poly = vec![];
    for i in 0..n {
        if r[i] == 1 {
            // (x - α_i) = α_i ⊕ x   (over char 2)
            let denom = vec![support[i], 1];
            let inv = poly_inv_mod(&denom, g, gf);
            s_poly = poly_add(&s_poly, &inv);
        }
    }

    // No errors?
    if s_poly.is_empty() {
        return (r.to_vec(), vec![0u8; n]);
    }

    // Step 2: T(x) = S(x)^{-1} mod g(x)
    let t_poly = poly_inv_mod(&s_poly, g, gf);

    // Step 3: V(x) = T(x) + x   (mod g, but deg ≤ t-1 already)
    let mut v_poly = t_poly.clone();
    if v_poly.len() < 2 {
        v_poly.resize(2, 0);
    }
    v_poly[1] ^= 1;
    poly_trim(&mut v_poly);

    // Step 4: U(x) = √V(x) mod g(x)
    let u_poly = poly_sqrt_mod_g(&v_poly, g, gf);

    // Step 5: extended Euclidean on (g, U), stop when deg(rᵢ) ≤ ⌊t/2⌋
    let stop = (t / 2) as isize;
    let (mut r0, mut r1) = (g.clone(), u_poly);
    let (mut b0, mut b1): (Poly, Poly) = (vec![], vec![1]);
    while poly_deg(&r1) > stop {
        let (q, rem) = poly_divmod(&r0, &r1, gf);
        let b_new = poly_add(&b0, &poly_mul(&q, &b1, gf));
        r0 = r1;
        r1 = rem;
        b0 = b1;
        b1 = b_new;
    }
    // After the loop, r1 = A(x), b1 = B(x): B·U ≡ A (mod g), with
    // deg A ≤ ⌊t/2⌋ and deg B ≤ ⌊(t-1)/2⌋.
    let a_poly = r1;
    let b_poly = b1;

    // Step 6: error locator σ(x) = A(x)² + x · B(x)²
    let a2 = poly_square(&a_poly, gf);
    let b2 = poly_square(&b_poly, gf);
    let xb2 = {
        let mut t = vec![0u32];
        t.extend_from_slice(&b2);
        poly_trim(&mut t);
        t
    };
    let sigma = poly_add(&a2, &xb2);

    // Step 7: roots of σ → error positions
    let mut e = vec![0u8; n];
    for i in 0..n {
        if poly_eval(&sigma, support[i], gf) == 0 {
            e[i] = 1;
        }
    }
    let mut corrected = r.to_vec();
    for i in 0..n {
        corrected[i] ^= e[i];
    }
    (corrected, e)
}

// ── Binary matrix utilities ──────────────────────────────────────────────────

type BinMat = Vec<Vec<u8>>;

fn mat_zeros(rows: usize, cols: usize) -> BinMat {
    vec![vec![0u8; cols]; rows]
}

fn mat_identity(n: usize) -> BinMat {
    let mut m = mat_zeros(n, n);
    for i in 0..n {
        m[i][i] = 1;
    }
    m
}

fn mat_mul(a: &BinMat, b: &BinMat) -> BinMat {
    let r = a.len();
    let inner = b.len();
    let c = b[0].len();
    assert_eq!(a[0].len(), inner);
    let mut out = mat_zeros(r, c);
    for i in 0..r {
        for j in 0..c {
            let mut sum: u8 = 0;
            for k in 0..inner {
                sum ^= a[i][k] & b[k][j];
            }
            out[i][j] = sum;
        }
    }
    out
}

/// Solve in place: row-reduce `m` (rows × n with rows ≤ n) and track an
/// associated identity-augmented matrix for inversion.  Returns inverse
/// of `m` when `m` is square and invertible.
fn invert_binary(m: &BinMat) -> Option<BinMat> {
    let n = m.len();
    assert_eq!(m[0].len(), n);
    let mut a: BinMat = m.to_vec();
    let mut inv = mat_identity(n);
    for i in 0..n {
        if a[i][i] == 0 {
            let mut found = false;
            for r in (i + 1)..n {
                if a[r][i] == 1 {
                    a.swap(i, r);
                    inv.swap(i, r);
                    found = true;
                    break;
                }
            }
            if !found {
                return None;
            }
        }
        for r in 0..n {
            if r != i && a[r][i] == 1 {
                for c in 0..n {
                    a[r][c] ^= a[i][c];
                    inv[r][c] ^= inv[i][c];
                }
            }
        }
    }
    Some(inv)
}

/// Reduce the (mt × n) parity-check `h` to systematic form [I_{mt} | B] by
/// Gaussian elimination with column swaps.  Returns the reduced matrix and a
/// permutation `perm` such that column `i` of the reduced matrix is column
/// `perm[i]` of the input.
fn systematic_form(h: &BinMat) -> Option<(BinMat, Vec<usize>)> {
    let mt = h.len();
    let n = h[0].len();
    let mut a: BinMat = h.to_vec();
    let mut perm: Vec<usize> = (0..n).collect();

    for i in 0..mt {
        // Find a pivot at (≥i, ≥i)
        let mut pivot: Option<(usize, usize)> = None;
        'outer: for col in i..n {
            for row in i..mt {
                if a[row][col] == 1 {
                    pivot = Some((row, col));
                    break 'outer;
                }
            }
        }
        let (pr, pc) = pivot?;
        if pr != i {
            a.swap(pr, i);
        }
        if pc != i {
            for row in a.iter_mut() {
                row.swap(i, pc);
            }
            perm.swap(i, pc);
        }
        for r in 0..mt {
            if r != i && a[r][i] == 1 {
                for c in 0..n {
                    a[r][c] ^= a[i][c];
                }
            }
        }
    }
    Some((a, perm))
}

/// Build the k×n binary generator matrix in *systematic-form column order*:
/// G' = [B^T | I_k], where the input H' = [I_{mt} | B].
fn generator_from_systematic(h_sys: &BinMat) -> BinMat {
    let mt = h_sys.len();
    let n = h_sys[0].len();
    let k = n - mt;
    let mut g = mat_zeros(k, n);
    for r in 0..k {
        for c in 0..mt {
            g[r][c] = h_sys[c][mt + r]; // B^T
        }
        g[r][mt + r] = 1; // I_k
    }
    g
}

// ── Random sampling helpers ──────────────────────────────────────────────────

/// Sample a random irreducible polynomial of degree `t` over GF(2^m).
/// Strategy: random monic poly of degree t, reject if it has a root in
/// GF(2^m).  For t ≤ 3 this is equivalent to irreducibility.
fn random_irreducible_poly(t: usize, gf: &GfTables) -> Poly {
    assert!((1..=3).contains(&t), "this implementation supports t ≤ 3");
    let mut rng = rand::rngs::OsRng;
    loop {
        let mut g: Poly = vec![0u32; t + 1];
        g[t] = 1;
        for i in 0..t {
            g[i] = rng.gen_range(0..FIELD_SIZE);
        }
        if g[0] == 0 {
            continue;
        }
        let mut has_root = false;
        for alpha in 0..FIELD_SIZE {
            if poly_eval(&g, alpha, gf) == 0 {
                has_root = true;
                break;
            }
        }
        if !has_root {
            return g;
        }
    }
}

/// Sample a random invertible k×k binary matrix together with its inverse.
fn random_invertible_matrix(k: usize) -> (BinMat, BinMat) {
    loop {
        let bytes = random_bytes_vec(k * k);
        let mut s = mat_zeros(k, k);
        for r in 0..k {
            for c in 0..k {
                s[r][c] = bytes[r * k + c] & 1;
            }
        }
        if let Some(inv) = invert_binary(&s) {
            return (s, inv);
        }
    }
}

/// Sample a uniformly-random permutation of {0,1,…,n-1} (Fisher–Yates).
fn random_permutation(n: usize) -> Vec<usize> {
    let mut rng = rand::rngs::OsRng;
    let mut p: Vec<usize> = (0..n).collect();
    for i in (1..n).rev() {
        let j = rng.gen_range(0..=i);
        p.swap(i, j);
    }
    p
}

/// Apply a permutation to a row vector: out[perm[i]] = v[i].
#[cfg(test)]
fn apply_perm(v: &[u8], perm: &[usize]) -> Vec<u8> {
    let mut out = vec![0u8; v.len()];
    for (i, &p) in perm.iter().enumerate() {
        out[p] = v[i];
    }
    out
}

/// Apply the inverse of a permutation to a row vector: out[i] = v[perm[i]].
fn apply_inv_perm(v: &[u8], perm: &[usize]) -> Vec<u8> {
    let mut out = vec![0u8; v.len()];
    for (i, &p) in perm.iter().enumerate() {
        out[i] = v[p];
    }
    out
}

/// Multiply a row vector by a matrix: r·M (size 1×k by k×n → 1×n).
fn vec_mat_mul(v: &[u8], m: &BinMat) -> Vec<u8> {
    let cols = m[0].len();
    let mut out = vec![0u8; cols];
    for (i, &vi) in v.iter().enumerate() {
        if vi == 0 {
            continue;
        }
        for j in 0..cols {
            out[j] ^= m[i][j];
        }
    }
    out
}

/// Sample a random binary error vector of length `n` and Hamming weight `t`.
fn random_error(n: usize, t: usize) -> Vec<u8> {
    let mut rng = rand::rngs::OsRng;
    let mut e = vec![0u8; n];
    let mut placed = 0usize;
    while placed < t {
        let idx = rng.gen_range(0..n);
        if e[idx] == 0 {
            e[idx] = 1;
            placed += 1;
        }
    }
    e
}

// ── Public API ───────────────────────────────────────────────────────────────

/// McEliece public key: the scrambled generator matrix G' = S·G·P.
#[derive(Clone, Debug)]
pub struct McElieceePublicKey {
    pub g_prime: BinMat,
    pub n: usize,
    pub k: usize,
    pub t: usize,
}

/// McEliece private key: everything needed to invert encryption.
///
/// All four secret components — `s_inv`, `support`, `g_poly`, `perm` —
/// are zeroized on drop.  Knowing any of them defeats the cryptosystem,
/// so they are all treated as secret material.
#[derive(Clone, Debug)]
pub struct McEliecePrivateKey {
    /// k×k inverse of the scrambler S.
    pub s_inv: BinMat,
    /// Goppa-code support (length n) in *systematic column order*.
    pub support: Vec<u32>,
    /// Goppa polynomial of degree t.
    pub g_poly: Poly,
    /// n-element permutation P used in the public key.
    pub perm: Vec<usize>,
    /// Cached field tables.
    pub gf: GfTables,
}

impl Drop for McEliecePrivateKey {
    fn drop(&mut self) {
        for row in self.s_inv.iter_mut() {
            for b in row.iter_mut() {
                *b = 0;
            }
        }
        for s in self.support.iter_mut() {
            *s = 0;
        }
        for c in self.g_poly.iter_mut() {
            *c = 0;
        }
        for p in self.perm.iter_mut() {
            *p = 0;
        }
    }
}

/// A McEliece keypair.
pub struct McElieceKeyPair {
    pub public: McElieceePublicKey,
    pub private: McEliecePrivateKey,
}

impl McElieceKeyPair {
    /// Generate a fresh McEliece keypair.
    ///
    /// Tries random Goppa polynomials and supports until the resulting
    /// parity-check matrix has full rank (so a systematic generator exists).
    pub fn generate() -> Self {
        let gf = GfTables::new();

        loop {
            let g_poly = random_irreducible_poly(T, &gf);
            // Use the first N elements of GF(2^m) as the support.  The Goppa
            // construction is valid as long as g(α_i) ≠ 0 for each support
            // point — which is automatic when g is irreducible of degree ≥ 2,
            // since then g has no roots in GF(2^m).
            let support: Vec<u32> = (0..N as u32).collect();

            let h_gf = parity_check_gf(&support, &g_poly, &gf);
            let h_bin = expand_to_binary(&h_gf);

            let (h_sys, sys_perm) = match systematic_form(&h_bin) {
                Some(p) => p,
                None => continue, // singular: retry with a new g
            };

            // Re-order the support so that column i corresponds to support
            // point `support[sys_perm[i]]`.
            let support_sys: Vec<u32> = sys_perm.iter().map(|&i| support[i]).collect();

            let g_sys = generator_from_systematic(&h_sys);

            // Apply random S, P to obtain the public key G' = S·G·P.
            let (s, s_inv) = random_invertible_matrix(K);
            let p_perm = random_permutation(N);

            // SG (k×n)
            let sg = mat_mul(&s, &g_sys);
            // SGP: column j of (SG·P) = column p_perm^{-1}(j) of SG, i.e.,
            // applying P from the right means: (SGP)[r][p_perm[c]] = SG[r][c].
            let mut g_prime = mat_zeros(K, N);
            for r in 0..K {
                for c in 0..N {
                    g_prime[r][p_perm[c]] = sg[r][c];
                }
            }

            return McElieceKeyPair {
                public: McElieceePublicKey {
                    g_prime,
                    n: N,
                    k: K,
                    t: T,
                },
                private: McEliecePrivateKey {
                    s_inv,
                    support: support_sys,
                    g_poly,
                    perm: p_perm,
                    gf,
                },
            };
        }
    }
}

/// Encrypt a `K`-bit message (one bit per byte, value 0 or 1).
/// Returns an `N`-byte ciphertext (one bit per byte).
pub fn mceliece_encrypt(msg: &[u8], pk: &McElieceePublicKey) -> Vec<u8> {
    assert_eq!(msg.len(), pk.k, "message must be exactly k bits");
    for &b in msg {
        assert!(b <= 1, "message bits must be 0 or 1");
    }
    let mg = vec_mat_mul(msg, &pk.g_prime);
    let e = random_error(pk.n, pk.t);
    let mut c = vec![0u8; pk.n];
    for i in 0..pk.n {
        c[i] = mg[i] ^ e[i];
    }
    c
}

/// Decrypt an `N`-bit ciphertext back into the original `K`-bit message.
/// Returns `None` on decoding failure.
pub fn mceliece_decrypt(ct: &[u8], sk: &McEliecePrivateKey) -> Option<Vec<u8>> {
    if ct.len() != N {
        return None;
    }

    // Strip the public permutation: c·P^{-1}.
    let c_unperm = apply_inv_perm(ct, &sk.perm);

    // Patterson decode against the Goppa code.
    let (codeword, e) = patterson_decode(&c_unperm, &sk.support, &sk.g_poly, &sk.gf);

    // Verify weight ≤ t (Patterson always returns weight ≤ t when valid).
    let weight: usize = e.iter().map(|&x| x as usize).sum();
    if weight > T {
        return None;
    }

    // Generator was in systematic form [B^T | I_k]: message is the last K
    // bits of the codeword.
    let m_s: Vec<u8> = codeword[N - K..].to_vec();

    // Apply S^{-1}.
    Some(vec_mat_mul(&m_s, &sk.s_inv))
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── Field arithmetic ─────────────────────────────────────────────────────

    #[test]
    fn gf_mul_inv_roundtrip() {
        let gf = GfTables::new();
        for a in 1..FIELD_SIZE {
            let inv = gf_inv(a, &gf);
            assert_eq!(gf_mul(a, inv, &gf), 1, "a={a}");
        }
    }

    #[test]
    fn gf_mul_distributive() {
        let gf = GfTables::new();
        for a in 0..FIELD_SIZE {
            for b in 0..FIELD_SIZE {
                for c in 0..FIELD_SIZE {
                    let lhs = gf_mul(a, gf_add(b, c), &gf);
                    let rhs = gf_add(gf_mul(a, b, &gf), gf_mul(a, c, &gf));
                    assert_eq!(lhs, rhs);
                }
            }
        }
    }

    #[test]
    fn gf_div_is_inv_mul() {
        let gf = GfTables::new();
        for a in 0..FIELD_SIZE {
            for b in 1..FIELD_SIZE {
                assert_eq!(gf_div(a, b, &gf), gf_mul(a, gf_inv(b, &gf), &gf));
            }
        }
    }

    // ── Polynomial arithmetic ────────────────────────────────────────────────

    #[test]
    fn poly_divmod_consistency() {
        let gf = GfTables::new();
        let a: Poly = vec![3, 5, 1, 7, 2, 1]; // degree 5
        let b: Poly = vec![1, 0, 1]; // x^2 + 1
        let (q, r) = poly_divmod(&a, &b, &gf);
        // a == q·b + r
        let recombined = poly_add(&poly_mul(&q, &b, &gf), &r);
        assert_eq!(recombined, a);
        assert!(poly_deg(&r) < poly_deg(&b));
    }

    #[test]
    fn poly_inv_mod_roundtrip() {
        let gf = GfTables::new();
        // g(x) = x^3 + x + 1 — pick a random irreducible cubic for the test.
        let g = random_irreducible_poly(3, &gf);
        // Pick a non-zero polynomial of lower degree.
        let a: Poly = vec![1, 2, 3];
        let inv = poly_inv_mod(&a, &g, &gf);
        let prod = poly_mod(&poly_mul(&a, &inv, &gf), &g, &gf);
        assert_eq!(prod, vec![1u32]);
    }

    #[test]
    fn poly_sqrt_roundtrip() {
        let gf = GfTables::new();
        let g = random_irreducible_poly(3, &gf);
        let v: Poly = vec![1, 2, 3]; // any polynomial mod g
        let r = poly_sqrt_mod_g(&v, &g, &gf);
        // r^2 ≡ v (mod g)
        let r2 = poly_mod(&poly_square(&r, &gf), &g, &gf);
        let v_reduced = poly_mod(&v, &g, &gf);
        assert_eq!(r2, v_reduced);
    }

    // ── Binary matrix utilities ──────────────────────────────────────────────

    #[test]
    fn binary_matrix_invert_roundtrip() {
        let (s, s_inv) = random_invertible_matrix(K);
        let prod = mat_mul(&s, &s_inv);
        let id = mat_identity(K);
        assert_eq!(prod, id);
        let prod2 = mat_mul(&s_inv, &s);
        assert_eq!(prod2, id);
    }

    #[test]
    fn permutation_inverse_roundtrip() {
        let p = random_permutation(N);
        let v: Vec<u8> = (0..N as u8).collect();
        let pv = apply_perm(&v, &p);
        let v2 = apply_inv_perm(&pv, &p);
        assert_eq!(v, v2);
    }

    // ── Goppa decoder ────────────────────────────────────────────────────────

    #[test]
    fn patterson_decode_zero_errors() {
        // A zero received word has zero syndrome; decoder must return zero
        // codeword and zero error.
        let gf = GfTables::new();
        let g = random_irreducible_poly(T, &gf);
        let support: Vec<u32> = (0..N as u32).collect();
        let r = vec![0u8; N];
        let (cw, e) = patterson_decode(&r, &support, &g, &gf);
        assert_eq!(cw, vec![0u8; N]);
        assert_eq!(e, vec![0u8; N]);
    }

    #[test]
    fn patterson_corrects_t_random_errors() {
        // Generate a fresh code, take a real codeword, inject t errors, and
        // confirm the decoder recovers them.
        let kp = McElieceKeyPair::generate();
        let sk = &kp.private;
        let gf = &sk.gf;

        // Build the Goppa-code generator in systematic order from H.
        let h_gf = parity_check_gf(&sk.support, &sk.g_poly, gf);
        let h_bin = expand_to_binary(&h_gf);
        let (h_sys, perm) = systematic_form(&h_bin).unwrap();
        // The systematic_form pivoting may not equal the identity perm here
        // since the support is *already* in systematic order; we re-apply
        // any residual pivot perm.
        let support_after: Vec<u32> = perm.iter().map(|&i| sk.support[i]).collect();
        let g_sys = generator_from_systematic(&h_sys);

        // Take an arbitrary message and encode to get a codeword.
        let msg: Vec<u8> = (0..K).map(|i| (i % 2) as u8).collect();
        let codeword = vec_mat_mul(&msg, &g_sys);

        // Inject T errors.
        let e = random_error(N, T);
        let mut received = codeword.clone();
        for i in 0..N {
            received[i] ^= e[i];
        }

        let (decoded, e_rec) = patterson_decode(&received, &support_after, &sk.g_poly, gf);
        assert_eq!(decoded, codeword, "decoder must recover the codeword");
        assert_eq!(e_rec, e, "decoder must recover the error pattern");
    }

    // ── End-to-end McEliece ──────────────────────────────────────────────────

    #[test]
    fn mceliece_keygen_shapes() {
        let kp = McElieceKeyPair::generate();
        assert_eq!(kp.public.g_prime.len(), K);
        assert_eq!(kp.public.g_prime[0].len(), N);
        assert_eq!(kp.private.s_inv.len(), K);
        assert_eq!(kp.private.s_inv[0].len(), K);
        assert_eq!(kp.private.support.len(), N);
        assert_eq!(kp.private.g_poly.len(), T + 1);
        assert_eq!(kp.private.perm.len(), N);
    }

    #[test]
    fn mceliece_encrypt_decrypt_roundtrip() {
        let kp = McElieceKeyPair::generate();
        for _ in 0..16 {
            let msg: Vec<u8> = (0..K).map(|_| rand::random::<u8>() & 1).collect();
            let ct = mceliece_encrypt(&msg, &kp.public);
            let pt = mceliece_decrypt(&ct, &kp.private).expect("decode failed");
            assert_eq!(pt, msg);
        }
    }

    #[test]
    fn mceliece_ciphertext_differs_from_plaintext_image() {
        // Because each encryption injects t random errors, two encryptions
        // of the same message yield different ciphertexts (overwhelmingly).
        let kp = McElieceKeyPair::generate();
        let msg: Vec<u8> = (0..K).map(|_| rand::random::<u8>() & 1).collect();
        let c1 = mceliece_encrypt(&msg, &kp.public);
        let c2 = mceliece_encrypt(&msg, &kp.public);
        assert_ne!(c1, c2, "encryption must be randomized");
        assert_eq!(mceliece_decrypt(&c1, &kp.private).unwrap(), msg);
        assert_eq!(mceliece_decrypt(&c2, &kp.private).unwrap(), msg);
    }

    #[test]
    fn mceliece_wrong_key_fails_to_recover() {
        // A different keypair's secret must not recover the plaintext.
        let kp1 = McElieceKeyPair::generate();
        let kp2 = McElieceKeyPair::generate();
        let msg: Vec<u8> = (0..K).map(|_| rand::random::<u8>() & 1).collect();
        let ct = mceliece_encrypt(&msg, &kp1.public);
        match mceliece_decrypt(&ct, &kp2.private) {
            None => {} // decoding failure is fine
            Some(plain) => assert_ne!(plain, msg),
        }
    }
}
