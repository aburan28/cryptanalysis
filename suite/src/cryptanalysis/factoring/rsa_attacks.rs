//! **Classic attacks on weak RSA keys** — each exploits a structural
//! mistake rather than the size of `n`.
//!
//! | attack | weakness | cost |
//! |---|---|---|
//! | [`fermat`] | `|p − q|` small | `O((p − q)² / √n)` steps (1 step if `|p − q| < n^{1/4}`) |
//! | [`wiener`] | `d < n^{1/4} / 3` | `O(log n)` continued-fraction convergents |
//! | [`hastad_broadcast`] | same `m`, small `e`, `e` moduli | one CRT + one integer root |
//! | [`common_modulus`] | same `m` and `n`, coprime `e₁, e₂` | one extended gcd |
//! | [`small_e_root`] | `mᵉ < n` (or `mᵉ < k·n` for tiny `k`), no padding | integer roots |
//! | [`batch_gcd`] | moduli sharing a prime (bad RNG) | product + remainder trees, quasi-linear |
//! | [`factor_from_private_exponent`] | a leaked `d` | expected ≤ 2 random bases |
//!
//! **Wiener (1990).**  `e·d − k·φ(n) = 1` with `φ(n) ≈ n` means `k/d` is an
//! unusually good rational approximation of `e/n`; when
//! `d < n^{1/4}/3` (and `q < p < 2q`) Legendre's theorem makes `k/d` a
//! convergent of the continued fraction of `e/n`.  Each convergent gives a
//! candidate `φ = (e·d − 1)/k`, and `p, q` are the roots of
//! `x² − (n − φ + 1)x + n`.  Boneh–Durfee (`d < n^{0.292}`, a lattice
//! attack) is not implemented.
//!
//! **Håstad (1985), broadcast.**  `cᵢ = mᵉ mod nᵢ` for `i = 1..e`; the CRT
//! gives `mᵉ mod ∏ nᵢ`, and `mᵉ < ∏ nᵢ` so it is `mᵉ` over the integers.
//! (Non-coprime moduli are a bonus: their gcd factors both.)
//!
//! **Batch GCD (Bernstein 2004; Heninger et al., "Mining your Ps and Qs",
//! USENIX Security 2012).**  With `P = ∏ nᵢ` from a product tree,
//! `gᵢ = gcd(nᵢ, (P mod nᵢ²)/nᵢ)` is the product of the primes `nᵢ`
//! shares with the others; the remainders come down a remainder tree.
//!
//! **(n, e, d) → p, q** (folklore; e.g. Boneh, "Twenty years of attacks on
//! the RSA cryptosystem", 1999).  `k = e·d − 1` is a multiple of
//! `λ(n)`; write `k = 2ᵗ r`, pick random `g`: the sequence
//! `g^r, g^{2r}, …` reaches 1, and the element before that is a
//! non-trivial square root of 1 with probability ≥ 1/2, giving
//! `gcd(x − 1, n) ∈ {p, q}`.
//!
//! Every result is verified: factors by multiplication, recovered
//! plaintexts by re-encryption, recovered exponents by `e·d ≡ 1 (mod λ)`
//! and a test encryption.

use num_bigint::{BigInt, BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Signed, ToPrimitive, Zero};
use rand::{rngs::SmallRng, SeedableRng};
use serde::Serialize;
use std::time::Instant;

use super::arith::{exact_root, ext_gcd, isqrt_exact, secs};
use super::serde_big;
use crate::utils::mod_inverse;

/// Two verified prime-candidate factors `p ≤ q` of `n`, if `p·q = n`.
fn verified_pair(n: &BigUint, p: BigUint) -> Option<(BigUint, BigUint)> {
    if p.is_zero() || p.is_one() || &p >= n {
        return None;
    }
    let (q, r) = n.div_rem(&p);
    if r.is_zero() && &p * &q == *n {
        Some(if p <= q { (p, q) } else { (q, p) })
    } else {
        None
    }
}

/// Outcome of an attack that factors `n`.
#[derive(Clone, Debug, Serialize)]
pub struct FactorAttackResult {
    /// Attack name.
    pub attack: &'static str,
    /// The modulus.
    #[serde(with = "serde_big::biguint")]
    pub n: BigUint,
    /// Smaller factor.
    #[serde(with = "serde_big::opt_biguint")]
    pub p: Option<BigUint>,
    /// Larger factor.
    #[serde(with = "serde_big::opt_biguint")]
    pub q: Option<BigUint>,
    /// Recovered private exponent (Wiener).
    #[serde(with = "serde_big::opt_biguint")]
    pub d: Option<BigUint>,
    /// `p·q = n` (and, for Wiener, `e·d ≡ 1`) was checked.
    pub verified: bool,
    /// Iterations / convergents / bases tried.
    pub iterations: u64,
    /// Wall-clock seconds.
    pub seconds: f64,
}

impl FactorAttackResult {
    fn new(attack: &'static str, n: &BigUint) -> Self {
        FactorAttackResult {
            attack,
            n: n.clone(),
            p: None,
            q: None,
            d: None,
            verified: false,
            iterations: 0,
            seconds: 0.0,
        }
    }

    fn set_factor(&mut self, f: BigUint) -> bool {
        match verified_pair(&self.n, f) {
            Some((p, q)) => {
                self.p = Some(p);
                self.q = Some(q);
                self.verified = true;
                true
            }
            None => false,
        }
    }
}

/// **Fermat's method**: `n = a² − b²` with `a = (p+q)/2`, `b = (q−p)/2`,
/// searching `a = ⌈√n⌉, ⌈√n⌉ + 1, …` for `max_iterations` steps.
pub fn fermat(n: &BigUint, max_iterations: u64) -> FactorAttackResult {
    let t0 = Instant::now();
    let mut res = FactorAttackResult::new("fermat", n);
    if n.is_even() {
        if n > &BigUint::from(2u32) {
            res.set_factor(BigUint::from(2u32));
        }
        res.seconds = secs(t0);
        return res;
    }
    let (mut a, exact) = isqrt_exact(n);
    if exact {
        res.set_factor(a);
        res.seconds = secs(t0);
        return res;
    }
    a += 1u32;
    let mut b2 = &a * &a - n;
    for i in 0..max_iterations {
        res.iterations = i + 1;
        let (b, exact) = isqrt_exact(&b2);
        if exact && res.set_factor(&a - &b) {
            break;
        }
        // (a + 1)² − n = b2 + 2a + 1
        b2 += &a * 2u32 + 1u32;
        a += 1u32;
    }
    res.seconds = secs(t0);
    res
}

/// Continued-fraction partial quotients of `num / den`.
fn continued_fraction(num: &BigUint, den: &BigUint) -> Vec<BigUint> {
    let (mut a, mut b) = (num.clone(), den.clone());
    let mut out = Vec::new();
    while !b.is_zero() {
        let (q, r) = a.div_rem(&b);
        out.push(q);
        a = b;
        b = r;
    }
    out
}

/// **Wiener's attack** on a small private exponent.
pub fn wiener(n: &BigUint, e: &BigUint) -> FactorAttackResult {
    let t0 = Instant::now();
    let mut res = FactorAttackResult::new("wiener", n);
    let cf = continued_fraction(e, n);
    // Convergents h/k: h = k in e·d − k·φ = 1 notation below is "kk".
    let (mut h_prev, mut h) = (BigUint::zero(), BigUint::one());
    let (mut k_prev, mut k) = (BigUint::one(), BigUint::zero());
    for a in &cf {
        let h_next = a * &h + &h_prev;
        let k_next = a * &k + &k_prev;
        (h_prev, h) = (h, h_next);
        (k_prev, k) = (k, k_next);
        res.iterations += 1;
        // Candidate: kk/d = h/k.
        let (kk, d) = (&h, &k);
        if kk.is_zero() || d.is_zero() {
            continue;
        }
        let ed1 = e * d - 1u32;
        let (phi, r) = ed1.div_rem(kk);
        if !r.is_zero() || phi >= *n {
            continue;
        }
        // x² − s·x + n with s = n − φ + 1 = p + q.
        let s: BigInt = BigInt::from(n.clone()) - BigInt::from(phi.clone()) + 1;
        if s.is_negative() {
            continue;
        }
        let disc: BigInt = &s * &s - BigInt::from(n.clone()) * 4;
        if disc.is_negative() {
            continue;
        }
        let (root, exact) = isqrt_exact(disc.magnitude());
        if !exact {
            continue;
        }
        let p: BigInt = (&s - BigInt::from(root)) / 2;
        let Some(p) = p.to_biguint() else { continue };
        if res.set_factor(p) {
            // Check e·d ≡ 1 (mod λ(n)) through a test encryption.
            let m = BigUint::from(0xC0FFEEu32) % n;
            if m.modpow(e, n).modpow(d, n) == m {
                res.d = Some(d.clone());
            } else {
                res.verified = false;
            }
            break;
        }
    }
    res.seconds = secs(t0);
    res
}

/// Outcome of an attack that recovers a plaintext.
#[derive(Clone, Debug, Serialize)]
pub struct MessageAttackResult {
    /// Attack name.
    pub attack: &'static str,
    /// The recovered message `m`.
    #[serde(with = "serde_big::opt_biguint")]
    pub message: Option<BigUint>,
    /// Re-encrypting `m` reproduced every ciphertext.
    pub verified: bool,
    /// A modulus factor found along the way (non-coprime moduli, or a
    /// ciphertext sharing a factor with `n`).
    #[serde(with = "serde_big::opt_biguint")]
    pub factor_found: Option<BigUint>,
    /// Extra detail (e.g. `k` for the cube-root attack).
    pub detail: String,
    /// Wall-clock seconds.
    pub seconds: f64,
}

impl MessageAttackResult {
    fn new(attack: &'static str) -> Self {
        MessageAttackResult {
            attack,
            message: None,
            verified: false,
            factor_found: None,
            detail: String::new(),
            seconds: 0.0,
        }
    }
}

/// Chinese remaindering of `x ≡ rᵢ (mod mᵢ)` for pairwise-coprime `mᵢ`.
fn crt(residues: &[(BigUint, BigUint)]) -> Option<(BigUint, BigUint)> {
    let mut x = BigUint::zero();
    let mut m = BigUint::one();
    for (r, mi) in residues {
        let inv = mod_inverse(&(&m % mi), mi)?;
        // x' = x + m·((r − x)·m⁻¹ mod mi)
        let diff = (r + mi - (&x % mi)) % mi;
        let t = diff * inv % mi;
        x += &m * t;
        m *= mi;
    }
    Some((x % &m, m))
}

/// **Håstad's broadcast attack**: `ciphertexts[i] = (cᵢ, nᵢ)` with
/// `cᵢ = mᵉ mod nᵢ`; needs at least `e` of them.
pub fn hastad_broadcast(e: u32, ciphertexts: &[(BigUint, BigUint)]) -> MessageAttackResult {
    let t0 = Instant::now();
    let mut res = MessageAttackResult::new("hastad-broadcast");
    if e == 0 || ciphertexts.len() < e as usize {
        res.detail = format!("need at least e = {e} ciphertexts");
        return res;
    }
    let used = &ciphertexts[..e as usize];
    // Non-coprime moduli leak a factor directly.
    for i in 0..used.len() {
        for j in i + 1..used.len() {
            let g = used[i].1.gcd(&used[j].1);
            if !g.is_one() && g != used[i].1 {
                res.factor_found = Some(g);
            }
        }
    }
    if res.factor_found.is_some() {
        res.detail = "moduli are not pairwise coprime".into();
        res.seconds = secs(t0);
        return res;
    }
    let residues: Vec<(BigUint, BigUint)> = used.to_vec();
    if let Some((c, _)) = crt(&residues) {
        if let Some(m) = exact_root(&c, e) {
            let eb = BigUint::from(e);
            res.verified = ciphertexts.iter().all(|(ci, ni)| &m.modpow(&eb, ni) == ci);
            res.message = Some(m);
        } else {
            res.detail = "CRT value is not a perfect e-th power (padding?)".into();
        }
    }
    res.seconds = secs(t0);
    res
}

/// **Common-modulus attack**: the same `m` encrypted under `(n, e₁)` and
/// `(n, e₂)` with `gcd(e₁, e₂) = 1`.
pub fn common_modulus(
    n: &BigUint,
    e1: &BigUint,
    c1: &BigUint,
    e2: &BigUint,
    c2: &BigUint,
) -> MessageAttackResult {
    let t0 = Instant::now();
    let mut res = MessageAttackResult::new("common-modulus");
    let (g, s1, s2) = ext_gcd(&BigInt::from(e1.clone()), &BigInt::from(e2.clone()));
    let pow_signed = |c: &BigUint, s: &BigInt| -> Result<BigUint, BigUint> {
        if s.is_negative() {
            match mod_inverse(c, n) {
                Some(ci) => Ok(ci.modpow(s.magnitude(), n)),
                None => Err(c.gcd(n)),
            }
        } else {
            Ok(c.modpow(s.magnitude(), n))
        }
    };
    let prod = pow_signed(c1, &s1).and_then(|a| pow_signed(c2, &s2).map(|b| a * b % n));
    match prod {
        Err(f) => {
            res.factor_found = Some(f);
            res.detail = "a ciphertext shares a factor with n".into();
        }
        Ok(mg) => {
            // mg = m^g; for g > 1 try an exact integer root.
            let g32 = g.to_u32().unwrap_or(0);
            let m = if g32 == 1 {
                Some(mg)
            } else {
                res.detail = format!("gcd(e1, e2) = {g}; trying the integer root");
                exact_root(&mg, g32)
            };
            if let Some(m) = m {
                res.verified = &m.modpow(e1, n) == c1 && &m.modpow(e2, n) == c2;
                res.message = Some(m);
            }
        }
    }
    res.seconds = secs(t0);
    res
}

/// **Small-exponent root**: find `m` with `mᵉ = c + k·n` for
/// `k = 0..=max_k` (textbook RSA with no padding and a short message).
pub fn small_e_root(c: &BigUint, e: u32, n: &BigUint, max_k: u64) -> MessageAttackResult {
    let t0 = Instant::now();
    let mut res = MessageAttackResult::new("small-e-root");
    let mut v = c.clone();
    for k in 0..=max_k {
        if let Some(m) = exact_root(&v, e) {
            res.verified = &m.modpow(&BigUint::from(e), n) == c;
            if res.verified {
                res.message = Some(m);
                res.detail = format!("m^e = c + {k}·n");
                break;
            }
        }
        v += n;
    }
    res.seconds = secs(t0);
    res
}

/// One modulus in a [`batch_gcd`] result.
#[derive(Clone, Debug, Serialize)]
pub struct BatchGcdEntry {
    /// Index into the input list.
    pub index: usize,
    /// Smaller factor.
    #[serde(with = "serde_big::biguint")]
    pub p: BigUint,
    /// Larger factor.
    #[serde(with = "serde_big::biguint")]
    pub q: BigUint,
}

/// Outcome of [`batch_gcd`].
#[derive(Clone, Debug, Serialize)]
pub struct BatchGcdResult {
    /// Moduli examined.
    pub moduli: usize,
    /// Factored moduli (all verified `p·q = nᵢ`).
    pub factored: Vec<BatchGcdEntry>,
    /// Indices of duplicated moduli (identical keys: nothing to learn
    /// from the gcd).
    pub duplicates: Vec<usize>,
    /// Wall-clock seconds.
    pub seconds: f64,
}

/// **Batch GCD**: find every modulus sharing a prime with another.
pub fn batch_gcd(moduli: &[BigUint]) -> BatchGcdResult {
    let t0 = Instant::now();
    let mut res = BatchGcdResult {
        moduli: moduli.len(),
        factored: Vec::new(),
        duplicates: Vec::new(),
        seconds: 0.0,
    };
    if moduli.len() < 2 {
        return res;
    }
    // Product tree: levels[0] = moduli, last level = [P].
    let mut levels: Vec<Vec<BigUint>> = vec![moduli.to_vec()];
    while levels.last().map(|l| l.len()).unwrap_or(0) > 1 {
        let prev = levels.last().expect("non-empty");
        let next: Vec<BigUint> = prev
            .chunks(2)
            .map(|c| {
                if c.len() == 2 {
                    &c[0] * &c[1]
                } else {
                    c[0].clone()
                }
            })
            .collect();
        levels.push(next);
    }
    // Remainder tree: P mod nᵢ² going down.
    let mut rems = levels.last().expect("root").clone();
    for level in levels.iter().rev().skip(1) {
        rems = level
            .iter()
            .enumerate()
            .map(|(i, x)| &rems[i / 2] % (x * x))
            .collect();
    }
    for (i, n) in moduli.iter().enumerate() {
        let g = (&rems[i] / n).gcd(n);
        if g.is_one() {
            continue;
        }
        if &g == n {
            // Both primes shared (or a duplicate): pairwise gcds.
            for (j, m) in moduli.iter().enumerate() {
                if i == j {
                    continue;
                }
                if m == n {
                    if !res.duplicates.contains(&i) {
                        res.duplicates.push(i);
                    }
                    continue;
                }
                let h = n.gcd(m);
                if let Some((p, q)) = verified_pair(n, h) {
                    res.factored.push(BatchGcdEntry { index: i, p, q });
                    break;
                }
            }
            continue;
        }
        if let Some((p, q)) = verified_pair(n, g) {
            res.factored.push(BatchGcdEntry { index: i, p, q });
        }
    }
    res.seconds = secs(t0);
    res
}

/// **Factor `n` from a known private exponent `d`.**
pub fn factor_from_private_exponent(
    n: &BigUint,
    e: &BigUint,
    d: &BigUint,
    seed: u64,
) -> FactorAttackResult {
    let t0 = Instant::now();
    let mut res = FactorAttackResult::new("private-exponent", n);
    let k = e * d - 1u32;
    if k.is_zero() || n.is_even() {
        if n.is_even() && n > &BigUint::from(2u32) {
            res.set_factor(BigUint::from(2u32));
        }
        res.seconds = secs(t0);
        return res;
    }
    let t = k.trailing_zeros().unwrap_or(0);
    let r = &k >> t;
    let mut rng = SmallRng::seed_from_u64(seed);
    let two = BigUint::from(2u32);
    let nm1 = n - 1u32;
    for _ in 0..200 {
        res.iterations += 1;
        let g = rng.gen_biguint_range(&two, &nm1);
        let gg = g.gcd(n);
        if !gg.is_one() {
            res.set_factor(gg);
            break;
        }
        let mut x = g.modpow(&r, n);
        if x.is_one() || x == nm1 {
            continue;
        }
        for _ in 0..t {
            let y = &x * &x % n;
            if y.is_one() {
                // x is a non-trivial square root of 1.
                res.set_factor((&x - 1u32).gcd(n));
                break;
            }
            if y == nm1 {
                break;
            }
            x = y;
        }
        if res.verified {
            break;
        }
    }
    res.seconds = secs(t0);
    res
}

#[cfg(test)]
mod tests {
    use super::*;

    fn big(s: &str) -> BigUint {
        s.parse().unwrap()
    }

    // Two 64-bit primes and friends for fast tests.
    const P: &str = "18446744073709551557"; // largest prime < 2^64
    const Q: &str = "18446744073709551533";

    #[test]
    fn fermat_splits_close_primes() {
        let n = big(P) * big(Q);
        let r = fermat(&n, 10);
        assert!(r.verified);
        assert_eq!(r.p.unwrap(), big(Q));
    }

    #[test]
    fn wiener_recovers_small_d() {
        // p, q ~ 2^64; choose d tiny, e = d⁻¹ mod φ.
        let (p, q) = (big(P), big("18446744073709551253"));
        let n = &p * &q;
        let phi = (&p - 1u32) * (&q - 1u32);
        let d = BigUint::from(1_000_003u64); // < n^{1/4}/3 ≈ 1.4e9
        let e = mod_inverse(&d, &phi).expect("coprime");
        let r = wiener(&n, &e);
        assert!(r.verified, "{r:?}");
        assert_eq!(r.d.unwrap(), d);
    }

    #[test]
    fn hastad_recovers_broadcast_message() {
        let ns = [
            big("18446744073709551557") * big("18446744073709551533"),
            big("18446744073709551521") * big("18446744073709551437"),
            big("18446744073709551427") * big("18446744073709551359"),
        ];
        let m = big("123456789012345678901234567890");
        let cts: Vec<(BigUint, BigUint)> = ns
            .iter()
            .map(|n| (m.modpow(&BigUint::from(3u32), n), n.clone()))
            .collect();
        let r = hastad_broadcast(3, &cts);
        assert!(r.verified);
        assert_eq!(r.message.unwrap(), m);
    }

    #[test]
    fn common_modulus_recovers_message() {
        let n = big(P) * big(Q);
        let m = big("987654321987654321");
        let (e1, e2) = (BigUint::from(65537u32), BigUint::from(17u32));
        let c1 = m.modpow(&e1, &n);
        let c2 = m.modpow(&e2, &n);
        let r = common_modulus(&n, &e1, &c1, &e2, &c2);
        assert!(r.verified);
        assert_eq!(r.message.unwrap(), m);
    }

    #[test]
    fn small_e_root_with_and_without_wrap() {
        let n = big(P) * big(Q);
        let m = BigUint::from(1_000_000u32);
        let c = m.modpow(&BigUint::from(3u32), &n);
        let r = small_e_root(&c, 3, &n, 0);
        assert_eq!(r.message.unwrap(), m);
        // m³ slightly above n: needs k ≥ 1.
        let m2 = n.nth_root(3) + 5u32;
        let c2 = m2.modpow(&BigUint::from(3u32), &n);
        let r2 = small_e_root(&c2, 3, &n, 10);
        assert!(r2.verified);
        assert_eq!(r2.message.unwrap(), m2);
    }

    #[test]
    fn batch_gcd_finds_shared_primes() {
        let shared = big(P);
        let moduli = vec![
            &shared * big(Q),
            big("18446744073709551521") * big("18446744073709551437"),
            &shared * big("18446744073709551427"),
            big("18446744073709551359") * big("18446744073709551337"),
        ];
        let r = batch_gcd(&moduli);
        let idx: Vec<usize> = r.factored.iter().map(|e| e.index).collect();
        assert_eq!(idx, vec![0, 2]);
        for e in &r.factored {
            assert_eq!(&e.p * &e.q, moduli[e.index]);
        }
    }

    #[test]
    fn private_exponent_reveals_factors() {
        let (p, q) = (big(P), big(Q));
        let n = &p * &q;
        let phi = (&p - 1u32) * (&q - 1u32);
        let e = BigUint::from(65537u32);
        let d = mod_inverse(&e, &phi).unwrap();
        let r = factor_from_private_exponent(&n, &e, &d, 1);
        assert!(r.verified);
        assert_eq!(r.p.unwrap(), q);
    }
}
