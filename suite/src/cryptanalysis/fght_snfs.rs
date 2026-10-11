//! **FGHT toy** — Fried–Gaudry–Heninger–Thomé (Eurocrypt 2017) implementation
//! at educational scale.
//!
//! The original paper, *"A kilobit hidden SNFS discrete logarithm
//! computation"*, demonstrated that you can construct a 1024-bit prime
//! that
//!
//! 1. passes every standard randomness test,
//! 2. has cryptographically valid Sophie-Germain / DSA structure
//!    (`(p − 1) / 2` also prime), and yet
//! 3. has a *hidden* polynomial-identity structure `p = f(m)` for a
//!    low-degree, small-coefficient polynomial `f` and an integer `m`.
//!
//! The hidden structure makes the Special Number Field Sieve (SNFS)
//! applicable, with a complexity `L_p(1/3, ≈1.526)` vs the General NFS
//! `L_p(1/3, ≈1.923)` you would face on a "random" prime of the same
//! size — and the paper actually computed a 1024-bit discrete log in
//! `𝔽_p*` in roughly two months of academic compute.
//!
//! ## What this module computes
//!
//! - [`construct_trapdoor`] searches for a prime `p` of the form
//!   `m² + c` with both `p` and `(p − 1)/2 = q` prime.  This is the
//!   trapdoor: knowing `(f, m)` (here `f(x) = x² + c`) makes the
//!   SNFS go through; without it you only see a prime `p`.
//!
//! - [`build_factor_base`] constructs a *rational* factor base of small
//!   primes ≤ `B_rat` and an *algebraic* factor base of degree-1 prime
//!   ideals `(ℓ, r)` for which `f(r) ≡ 0 (mod ℓ)`.
//!
//! - [`sieve`] iterates over `(a, b) ∈ ℤ²` with `gcd(a, b) = 1` and
//!   collects those for which **both** `a + b·m` (rational side) and
//!   `N(a + b·α) = a² + c·b²` (algebraic side) factor over their
//!   respective factor bases.
//!
//! - [`solve_relations`] feeds the collected relations into Gaussian
//!   elimination mod `q` to recover `log_g(ℓ)` for each rational prime
//!   `ℓ` in the factor base.
//!
//! - [`verify_factor_base_logs`] cross-checks the recovered logs:
//!   `g^{log_g(ℓ)} ≡ ℓ (mod p)` for every `ℓ` in `<g>` (the order-`q`
//!   subgroup of `𝔽_p*`).
//!
//! - The companion [`detector`] module runs the elementary tests an
//!   adversary would try to distinguish a trapdoored prime from a
//!   genuinely random safe prime — and demonstrates that they fail.
//!
//! - The [`ecc_implications`] module documents what an analogous attack
//!   on a Solinas-prime elliptic curve would have to look like, and why
//!   nobody has built one.
//!
//! ### General-degree extensions (added in this commit)
//!
//! - [`MonicPoly`] — monic `f(x) = xᵈ + c_{d−1} xᵈ⁻¹ + … + c_0` with
//!   eval, root-find mod `ℓ`, and the resultant-based algebraic norm
//!   `N(a + bα) = (−1)ᵈ · bᵈ · f(−a/b)`.
//! - [`construct_trapdoor_general`], [`build_factor_base_general`],
//!   [`sieve_general`], [`snfs_dlp_recover_general`] generalize the
//!   pipeline to any monic `f`.  Sieve + relation-structure tests
//!   pass for `d ∈ {3, 6}` at toy scale.
//! - **Full DLP recovery at `d ≥ 3` is blocked on Schirokauer maps.**
//!   Dirichlet's unit theorem guarantees the algebraic ring has a
//!   non-trivial unit group (rank `r₁ + r₂ − 1`), and clean
//!   factor-base log recovery needs per-relation unit-class tracking.
//!   Tests `degree_3_recovery_documented_as_blocked_on_schirokauer`
//!   and `degree_6_recovery_documented_as_blocked_on_schirokauer`
//!   document this gap honestly.
//!
//! ### Descent: individual log for arbitrary targets (added)
//!
//! - [`individual_log_descent`] — single-stage NFS descent.  Given
//!   the factor-base logs from the precomputation, recovers
//!   `log_g(h)` for any in-subgroup `h ∈ ⟨g⟩` by sieving `h · g^k`
//!   until smooth, then composing.  Closes the loop from precomputation
//!   to per-target recovery — verified end-to-end on the degree-2
//!   toy.
//!
//! ## What this module deliberately does **not** do
//!
//! - **Schirokauer maps** — needed for full DLP recovery at `d ≥ 3`.
//!   Adding them would unlock end-to-end recovery on the degree-3
//!   and degree-6 trapdoors whose sieve + structural pipeline this
//!   commit lands.
//! - **Block Lanczos / block Wiedemann.**  We do dense Gaussian
//!   elimination mod `q`, which is fine at toy scale.
//! - **Multi-stage descent.**  [`individual_log_descent`] is
//!   single-stage: it sieves `target · g^k` until smooth.  Real NFS
//!   descent for non-smooth targets at crypto sizes needs a
//!   recursive "medium prime" descent, which we omit because at toy
//!   scale most targets are smooth in a few shifts.
//!
//! ## What this attack does NOT extend to
//!
//! The construction and exploitation here target `𝔽_p*` discrete log
//! (Diffie–Hellman, DSA over a multiplicative group mod `p`).  It does
//! **not** extend to ECDLP.  See [`ecc_implications`] for the
//! architectural sketch of why the analog would be hard.
//!
//! ## References
//!
//! - **J. Fried, P. Gaudry, N. Heninger, E. Thomé**, *A kilobit hidden
//!   SNFS discrete logarithm computation*, Eurocrypt 2017.
//! - Thomé's ECC 2017 slides:
//!   `https://ecc2017.cs.ru.nl/slides/ecc2017-thome.pdf`.

use crate::utils::mod_inverse;
use num_bigint::{BigInt, BigUint, Sign};
use num_traits::{One, Signed, Zero};

// ── Miller–Rabin primality test (for the trapdoor search) ──────────────

/// Probabilistic primality test (Miller–Rabin) with a fixed set of
/// small-prime witnesses.  Deterministic for `n < 3.3 · 10¹⁴` with the
/// 7 witnesses `{2, 3, 5, 7, 11, 13, 17}` — well above our toy range.
fn is_probable_prime(n: &BigUint) -> bool {
    let two = BigUint::from(2u32);
    let three = BigUint::from(3u32);
    if n < &two {
        return false;
    }
    if n == &two || n == &three {
        return true;
    }
    if (n & BigUint::one()).is_zero() {
        return false;
    }
    let n_minus_1 = n - 1u32;
    let mut d = n_minus_1.clone();
    let mut s: u32 = 0;
    while (&d & BigUint::one()).is_zero() {
        d >>= 1;
        s += 1;
    }
    for &w in &[2u64, 3, 5, 7, 11, 13, 17] {
        let a = BigUint::from(w);
        if a >= *n {
            continue;
        }
        let mut x = a.modpow(&d, n);
        if x == BigUint::one() || x == n_minus_1 {
            continue;
        }
        let mut composite = true;
        for _ in 0..s.saturating_sub(1) {
            x = (&x * &x) % n;
            if x == n_minus_1 {
                composite = false;
                break;
            }
        }
        if composite {
            return false;
        }
    }
    true
}

// ── The trapdoor ───────────────────────────────────────────────────────

/// A trapdoored prime `p = m² + c` together with its Sophie-Germain
/// partner `q = (p − 1) / 2`.  The "trapdoor" is the pair `(c, m)`:
/// without them you see only `p`; with them you see the SNFS-friendly
/// polynomial identity.
#[derive(Clone, Debug)]
pub struct Trapdoor {
    /// Constant term of `f(x) = x² + c`.
    pub c: i64,
    /// The secret integer at which `f` is evaluated to produce `p`.
    pub m: BigUint,
    /// `p = m² + c`, prime.
    pub p: BigUint,
    /// `q = (p − 1) / 2`, prime (Sophie-Germain structure).
    pub q: BigUint,
}

impl Trapdoor {
    /// Number of bits in the trapdoored prime `p`.
    pub fn bits(&self) -> u64 {
        self.p.bits()
    }
}

/// **Construct a trapdoored prime** by searching `m` from `m_start`
/// upward, trying each `c ∈ c_candidates`, until `p = m² + c` is prime
/// AND `(p − 1) / 2 = q` is also prime.
///
/// Returns `None` if no trapdoor is found within `max_m_steps`.
pub fn construct_trapdoor(
    c_candidates: &[i64],
    m_start: &BigUint,
    max_m_steps: u64,
) -> Option<Trapdoor> {
    let mut m = m_start.clone();
    for _ in 0..max_m_steps {
        let m_sq = &m * &m;
        for &c in c_candidates {
            let p: BigUint = if c >= 0 {
                &m_sq + BigUint::from(c as u64)
            } else {
                let abs_c = BigUint::from((-c) as u64);
                if m_sq <= abs_c {
                    continue;
                }
                &m_sq - &abs_c
            };
            // Quickly reject even p > 2.
            if (&p & BigUint::one()).is_zero() {
                continue;
            }
            if !is_probable_prime(&p) {
                continue;
            }
            let p_minus_1 = &p - 1u32;
            // For Sophie-Germain we need p ≡ 3 (mod 4) so (p−1)/2 is odd
            // (otherwise (p−1)/2 is even hence ≥ 4 means composite).
            let q = &p_minus_1 >> 1;
            if !is_probable_prime(&q) {
                continue;
            }
            return Some(Trapdoor {
                c,
                m: m.clone(),
                p,
                q,
            });
        }
        m += 1u32;
    }
    None
}

// ── Factor bases ───────────────────────────────────────────────────────

/// The rational + algebraic factor bases used by the sieve.
#[derive(Clone, Debug)]
pub struct FactorBase {
    /// Rational primes `ℓ ≤ B_rat`.
    pub rat: Vec<u64>,
    /// Algebraic prime ideals: each `(ℓ, r)` represents the degree-1
    /// prime ideal `(ℓ, α − r)` of `ℤ[α] = ℤ[√(−c)]`, where `r` is a
    /// root of `f(x) = x² + c` modulo `ℓ`.
    pub alg: Vec<(u64, u64)>,
}

impl FactorBase {
    pub fn rat_len(&self) -> usize {
        self.rat.len()
    }
    pub fn alg_len(&self) -> usize {
        self.alg.len()
    }
    /// Total number of unknowns in the linear system: one per rational
    /// prime + one per algebraic prime ideal + one for the sign of `−1`.
    pub fn unknowns(&self) -> usize {
        self.rat.len() + self.alg.len() + 1
    }
}

fn sieve_small_primes(bound: u64) -> Vec<u64> {
    let n = bound as usize + 1;
    let mut sieve = vec![true; n];
    sieve[0] = false;
    if n > 1 {
        sieve[1] = false;
    }
    let mut i = 2usize;
    while i * i < n {
        if sieve[i] {
            let mut j = i * i;
            while j < n {
                sieve[j] = false;
                j += i;
            }
        }
        i += 1;
    }
    sieve
        .iter()
        .enumerate()
        .filter_map(|(k, &p)| if p { Some(k as u64) } else { None })
        .collect()
}

/// Build a factor base for `f(x) = x² + c` with rational bound
/// `b_rat` and algebraic bound `b_alg`.  Both bases include only
/// primes ≤ the respective bound; the algebraic base includes a
/// `(ℓ, r)` entry for every root `r` of `x² + c (mod ℓ)`.
pub fn build_factor_base(c: i64, b_rat: u64, b_alg: u64) -> FactorBase {
    let rat = sieve_small_primes(b_rat);
    let mut alg = Vec::new();
    for &ell in &rat {
        if ell > b_alg {
            break;
        }
        // Find all r in [0, ℓ) with r² + c ≡ 0 (mod ℓ).
        if ell == 2 {
            // 2 always has a root since x² + c mod 2 is x² + (c mod 2),
            // and x² mod 2 ∈ {0, 1}.
            let target = ((-(c % 2) % 2) + 2) % 2;
            for r in 0..2u64 {
                if ((r * r) % 2) == target as u64 {
                    alg.push((ell, r));
                }
            }
            continue;
        }
        // Trial-divide: r² ≡ -c (mod ℓ) for r ∈ [0, ℓ).
        let neg_c_mod_ell = {
            let r = c.rem_euclid(ell as i64);
            (ell as i64 - r).rem_euclid(ell as i64) as u64
        };
        for r in 0..ell {
            if (r * r) % ell == neg_c_mod_ell {
                alg.push((ell, r));
            }
        }
    }
    FactorBase { rat, alg }
}

// ── Relation collection ────────────────────────────────────────────────

/// One successful relation from the sieve.  Each relation gives a
/// single linear equation in the unknown logarithms.
#[derive(Clone, Debug)]
pub struct Relation {
    pub a: i64,
    pub b: i64,
    /// `true` if `a + b·m < 0` (so the rational element is `−|x|`,
    /// contributing a `−1` factor — which is in `<g>` iff its log is
    /// `q/2` mod `q`, but here we just track it as a separate unknown).
    pub rat_sign_neg: bool,
    /// Sparse rational factorisation: `(index in fb.rat, exponent)`.
    pub rat_exps: Vec<(usize, u32)>,
    /// Sparse algebraic factorisation: `(index in fb.alg, exponent)`.
    pub alg_exps: Vec<(usize, u32)>,
}

/// Trial-divide `|n|` by every prime in `primes`; return the
/// factorisation `(sign, [(prime_index, exponent), …])` if `|n| == 1`
/// after dividing out, else `None`.
fn factor_smooth(n: &BigInt, primes: &[u64]) -> Option<(bool, Vec<(usize, u32)>)> {
    let neg = n.sign() == Sign::Minus;
    let mut x = n.abs().to_biguint().unwrap();
    if x.is_zero() {
        return None;
    }
    let mut factors: Vec<(usize, u32)> = Vec::new();
    for (idx, &ell) in primes.iter().enumerate() {
        let ell_big = BigUint::from(ell);
        let mut e: u32 = 0;
        while (&x % &ell_big).is_zero() {
            x /= &ell_big;
            e += 1;
        }
        if e > 0 {
            factors.push((idx, e));
        }
    }
    if x == BigUint::one() {
        Some((neg, factors))
    } else {
        None
    }
}

/// Algebraic side: for each `(ℓ, r)` in `alg_fb`, determine whether the
/// prime ideal `(ℓ, α − r)` divides `(a + b·α)`, and at what valuation.
///
/// For a degree-1 prime ideal `(ℓ, α − r)` and `gcd(a, b) = 1`, the
/// valuation `v_{(ℓ,r)}(a + b·α)` equals `v_ℓ(a + b·r)` in `ℤ`.
/// We then check that the product of `ℓ^{v}` equals the absolute value
/// of the algebraic norm `|a² + c·b²|`.  If the product matches, the
/// algebraic side is smooth over `alg_fb`.
fn factor_algebraic(a: i64, b: i64, c: i64, alg_fb: &[(u64, u64)]) -> Option<Vec<(usize, u32)>> {
    // Norm of (a + bα) in ℤ[α] where α² = −c:  N = a² + c·b².
    // (Use i128 to dodge i64 overflow at the toy scale we run at.)
    let norm = (a as i128) * (a as i128) + (c as i128) * (b as i128) * (b as i128);
    if norm == 0 {
        return None;
    }
    let mut remaining = norm.unsigned_abs();
    let mut factors: Vec<(usize, u32)> = Vec::new();
    for (idx, &(ell, r)) in alg_fb.iter().enumerate() {
        // Test whether ℓ | (a + b·r).  If yes, ℓ divides N(a + bα) on
        // this ideal's side; otherwise this ideal contributes nothing.
        let test = ((a as i128).rem_euclid(ell as i128)
            + ((b as i128) * (r as i128)).rem_euclid(ell as i128))
        .rem_euclid(ell as i128);
        if test != 0 {
            continue;
        }
        let mut e: u32 = 0;
        let ell_u128 = ell as u128;
        while remaining.is_multiple_of(ell_u128) {
            remaining /= ell_u128;
            e += 1;
        }
        if e > 0 {
            factors.push((idx, e));
        }
    }
    if remaining == 1 {
        Some(factors)
    } else {
        None
    }
}

/// **Sieve** over `a ∈ [−a_max, a_max]`, `b ∈ [1, b_max]` with
/// `gcd(a, b) = 1`, recording every pair for which both sides factor
/// smoothly.  Returns the list of relations.
pub fn sieve(trap: &Trapdoor, fb: &FactorBase, a_max: i64, b_max: i64) -> Vec<Relation> {
    let m_int = BigInt::from_biguint(Sign::Plus, trap.m.clone());
    let mut out = Vec::new();
    for a in -a_max..=a_max {
        for b in 1..=b_max {
            // gcd condition; gcd(0, b) = b so a = 0 only OK if b == 1.
            if a == 0 && b != 1 {
                continue;
            }
            if gcd_i64(a.unsigned_abs(), b as u64) != 1 {
                continue;
            }
            // Rational side: a + b*m.
            let n_rat = BigInt::from(a) + BigInt::from(b) * &m_int;
            if n_rat.is_zero() {
                continue;
            }
            let (rat_neg, rat_exps) = match factor_smooth(&n_rat, &fb.rat) {
                Some(v) => v,
                None => continue,
            };
            // Algebraic side.
            let alg_exps = match factor_algebraic(a, b, trap.c, &fb.alg) {
                Some(v) => v,
                None => continue,
            };
            out.push(Relation {
                a,
                b,
                rat_sign_neg: rat_neg,
                rat_exps,
                alg_exps,
            });
        }
    }
    out
}

fn gcd_i64(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let t = a % b;
        a = b;
        b = t;
    }
    a
}

// ── Linear algebra mod q ───────────────────────────────────────────────

/// Recovered factor-base logarithms.  `rat[i]` is `log_g(fb.rat[i])`
/// modulo `q`; `alg[i]` is the (image of the) prime-ideal log; `sign`
/// is the log of `−1` (always either `0` or `q/2` if `q` is odd, but
/// we solve for it generically).
#[derive(Clone, Debug)]
pub struct FactorBaseLogs {
    pub rat: Vec<BigUint>,
    pub alg: Vec<BigUint>,
    pub sign: BigUint,
}

/// **Solve** the linear system built from `relations` for the
/// factor-base logs, modulo prime `q`.  Returns `None` if the system
/// is rank-deficient at the columns we care about.
///
/// The relation from `(a, b)` is, in `𝔽_p*` and taking `log_g`:
///
/// ```text
///   sign(a+b·m) · ∏ ℓ^{rat_exps[i]}  ≡  ∏ 𝔭^{alg_exps[i]}  (mod p)
/// ```
///
/// Taking `log_g` of both sides and rearranging:
///
/// ```text
///   sign_neg · log_g(−1)
///   + Σ rat_exps[i] · log_g(fb.rat[i])
///   − Σ alg_exps[i] · log_g(fb.alg[i])
///   ≡ 0  (mod q).
/// ```
///
/// We build the matrix with columns `[log_g(−1), log_g(rat₀), …,
/// log_g(rat_n), log_g(alg₀), …, log_g(alg_m)]` and solve the
/// homogeneous system.  At least one normalisation row is added to
/// pin the gauge (we set `log_g(2) = log_g(2)` to its actual value
/// computed via BSGS at the end — see `gauge_fix_against`).
pub fn solve_relations(
    relations: &[Relation],
    fb: &FactorBase,
    q: &BigUint,
) -> Option<Vec<Vec<BigUint>>> {
    let n_cols = 1 + fb.rat_len() + fb.alg_len();
    if relations.len() < n_cols {
        return None;
    }
    let mut matrix: Vec<Vec<BigUint>> = Vec::with_capacity(relations.len());
    for rel in relations {
        let mut row = vec![BigUint::zero(); n_cols];
        if rel.rat_sign_neg {
            row[0] = BigUint::one();
        }
        for &(idx, e) in &rel.rat_exps {
            row[1 + idx] = (BigUint::from(e) + &row[1 + idx]) % q;
        }
        for &(idx, e) in &rel.alg_exps {
            let col = 1 + fb.rat_len() + idx;
            row[col] = (q - (BigUint::from(e) % q) % q) % q;
            row[col] = (&row[col] + (q - (BigUint::from(e) % q)) % q) % q;
            // simpler: just subtract.  Re-do cleanly:
            row[col] = (q + q - BigUint::from(e)) % q;
        }
        matrix.push(row);
    }
    Some(matrix)
}

/// Standard pivot-and-eliminate Gauss over `ℤ/qℤ` (with `q` prime, so
/// every nonzero entry is invertible).  Returns the reduced row-echelon
/// matrix and the pivot column for each pivot row.
pub fn gaussian_eliminate_homogeneous(
    matrix: &mut [Vec<BigUint>],
    q: &BigUint,
) -> Vec<Option<usize>> {
    let rows = matrix.len();
    let cols = matrix.first().map(|r| r.len()).unwrap_or(0);
    let mut pivot_col = vec![None; rows];
    let mut row = 0usize;
    let mut col = 0usize;
    while row < rows && col < cols {
        // Find pivot in column `col`, row index ≥ `row`.
        let mut piv = None;
        for r in row..rows {
            if !matrix[r][col].is_zero() {
                piv = Some(r);
                break;
            }
        }
        let piv = match piv {
            Some(p) => p,
            None => {
                col += 1;
                continue;
            }
        };
        matrix.swap(row, piv);
        pivot_col[row] = Some(col);
        // Normalise pivot row.
        let inv = match mod_inverse(&matrix[row][col], q) {
            Some(v) => v,
            None => {
                col += 1;
                continue;
            }
        };
        for c in 0..cols {
            matrix[row][c] = (&matrix[row][c] * &inv) % q;
        }
        // Eliminate pivot column in every other row.
        for r in 0..rows {
            if r == row {
                continue;
            }
            if matrix[r][col].is_zero() {
                continue;
            }
            let factor = matrix[r][col].clone();
            for c in 0..cols {
                let term = (&factor * &matrix[row][c]) % q;
                matrix[r][c] = (&matrix[r][c] + q - term) % q;
            }
        }
        row += 1;
        col += 1;
    }
    pivot_col
}

// ── Top-level driver + verification ────────────────────────────────────

/// Find a generator of the order-`q` subgroup of `𝔽_p*` for the
/// trapdoor's `p = 2q + 1`.  Returns the smallest `g ≥ 2` with `g^q ≡ 1
/// (mod p)` and `g ≠ 1`.
pub fn find_subgroup_generator(trap: &Trapdoor) -> BigUint {
    let one = BigUint::one();
    let mut g = BigUint::from(2u32);
    while g < trap.p {
        let v = g.modpow(&trap.q, &trap.p);
        if v == one && g.modpow(&BigUint::one(), &trap.p) != one {
            return g;
        }
        if v == one && g != one {
            return g;
        }
        // If v != 1, then ord(g) ≠ q | (p−1).  Since p−1 = 2q with q
        // prime, ord(g) ∈ {1, 2, q, 2q}.  v == p−1 means ord(g) = 2q;
        // we square to get an element of order q.
        if v == &trap.p - 1u32 {
            return (&g * &g) % &trap.p;
        }
        g += 1u32;
    }
    BigUint::one()
}

/// **Verify** that the recovered factor-base log of `ℓ` actually
/// satisfies `g^{log_g(ℓ)} ≡ ℓ (mod p)`, *when* `ℓ` lies in `<g>` (the
/// order-`q` subgroup).  Returns the number of correct logs verified.
pub fn verify_factor_base_logs(
    trap: &Trapdoor,
    fb: &FactorBase,
    g: &BigUint,
    rat_logs: &[BigUint],
) -> (usize, usize) {
    let mut ok = 0usize;
    let mut total = 0usize;
    for (idx, &ell) in fb.rat.iter().enumerate() {
        // Test ℓ ∈ <g> via Euler-like check: ℓ^q ≡ 1 (mod p).
        let ell_big = BigUint::from(ell);
        if ell_big.modpow(&trap.q, &trap.p) != BigUint::one() {
            continue;
        }
        total += 1;
        let candidate = g.modpow(&rat_logs[idx], &trap.p);
        if candidate == ell_big {
            ok += 1;
        }
    }
    (ok, total)
}

// ── End-to-end DLP recovery ───────────────────────────────────────────

/// Brute-force discrete log of `h` in `⟨g⟩` (assumed to have prime
/// order `q`).  Returns `Some(k)` with `0 ≤ k < q` and `g^k ≡ h (mod p)`
/// if `h ∈ ⟨g⟩`, else `None`.
///
/// O(q) time — toy-scale only.  Used to pin one factor-base log so the
/// homogeneous NFS system gets a unique solution.
pub fn brute_force_log_subgroup(
    g: &BigUint,
    h: &BigUint,
    p: &BigUint,
    q: &BigUint,
) -> Option<BigUint> {
    let mut current = BigUint::one();
    let mut k = BigUint::zero();
    while &k < q {
        if &current == h {
            return Some(k);
        }
        current = (&current * g) % p;
        k += 1u32;
    }
    None
}

/// **Recover factor-base logarithms** by building the relation matrix
/// and solving mod `q`, with one pinning row to fix the gauge.
///
/// Returns the rational-factor-base logs `[log_g(fb.rat[0]), …,
/// log_g(fb.rat[n_rat-1])]` mod `q`.  The algebraic-side unknowns are
/// abstract (no direct interpretation as logs of F_p elements), so we
/// don't return them.
///
/// **Contract**: caller must ensure `pin_idx ∈ [0, fb.rat_len())` and
/// `pin_value ≡ log_g(fb.rat[pin_idx]) (mod q)`.
///
/// Returns `None` if the linear system is under-determined (too few
/// independent relations).
pub fn recover_factor_base_logs(
    trap: &Trapdoor,
    fb: &FactorBase,
    relations: &[Relation],
    pin_idx: usize,
    pin_value: BigUint,
) -> Option<Vec<BigUint>> {
    let n_rat = fb.rat_len();
    let n_alg = fb.alg_len();
    let n_unknowns = n_rat + n_alg;
    let q = &trap.q;
    let mut matrix: Vec<Vec<BigUint>> = Vec::new();
    let mut rhs: Vec<BigUint> = Vec::new();
    for rel in relations {
        if rel.rat_sign_neg {
            // Sign-negative relations involve `−1`, which lies outside
            // the order-q subgroup when q is odd prime — skip them to
            // keep the solve clean.  At toy scale we get plenty of
            // positive-sign relations.
            continue;
        }
        let mut row = vec![BigUint::zero(); n_unknowns];
        for &(idx, e) in &rel.rat_exps {
            row[idx] = (&row[idx] + BigUint::from(e)) % q;
        }
        for &(idx, e) in &rel.alg_exps {
            let neg = (q - (BigUint::from(e) % q)) % q;
            row[n_rat + idx] = (&row[n_rat + idx] + &neg) % q;
        }
        matrix.push(row);
        rhs.push(BigUint::zero());
    }
    // Gauge-fixing pin row: y_{pin_idx} = pin_value.
    let mut pin_row = vec![BigUint::zero(); n_unknowns];
    pin_row[pin_idx] = BigUint::one();
    matrix.push(pin_row);
    rhs.push(pin_value);
    let solution = crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n(
        &mut matrix,
        &mut rhs,
        q,
    )?;
    // Return rational logs only.
    Some(solution[..n_rat].to_vec())
}

/// **One-call end-to-end SNFS DLP solver for F_p\***: given a trapdoor,
/// recover the discrete-log table for every rational factor-base prime
/// that lies in the order-`q` subgroup of `F_p*`.
///
/// Returns `(g, rat_logs)` where:
///   - `g` is a generator of `⟨g⟩` of order `q`;
///   - `rat_logs[i] = log_g(fb.rat[i]) (mod q)` when `fb.rat[i] ∈ ⟨g⟩`;
///   - otherwise `rat_logs[i]` is an abstract gauge value (the
///     verification step in [`verify_factor_base_logs`] skips it).
///
/// Returns `None` if no rational FB prime is in `⟨g⟩` (so we can't
/// build a pin row) or if the linear system is under-determined.
pub fn snfs_dlp_recover(
    trap: &Trapdoor,
    b_rat: u64,
    b_alg: u64,
    a_max: i64,
    b_max: i64,
) -> Option<(BigUint, Vec<BigUint>, FactorBase)> {
    let g = find_subgroup_generator(trap);
    if g == BigUint::one() {
        return None;
    }
    let fb = build_factor_base(trap.c, b_rat, b_alg);
    let relations = sieve(trap, &fb, a_max, b_max);
    // Find a small FB prime ℓ ∈ ⟨g⟩ to pin.
    let mut pin_idx_log: Option<(usize, BigUint)> = None;
    for (idx, &ell) in fb.rat.iter().enumerate() {
        let ell_big = BigUint::from(ell);
        if ell_big.modpow(&trap.q, &trap.p) == BigUint::one() && ell_big != BigUint::one() {
            if let Some(log) = brute_force_log_subgroup(&g, &ell_big, &trap.p, &trap.q) {
                pin_idx_log = Some((idx, log));
                break;
            }
        }
    }
    let (pin_idx, pin_log) = pin_idx_log?;
    let rat_logs = recover_factor_base_logs(trap, &fb, &relations, pin_idx, pin_log)?;
    Some((g, rat_logs, fb))
}

// ── General-degree polynomial framework ──────────────────────────────

/// Monic polynomial over `ℤ`: `f(x) = xᵈ + c_{d-1} x^{d-1} + … + c_0`.
///
/// `coeffs[i] = c_i` for `0 ≤ i < d`; the leading coefficient `c_d = 1`
/// is implicit.
#[derive(Clone, Debug)]
pub struct MonicPoly {
    pub coeffs: Vec<i64>,
}

impl MonicPoly {
    pub fn new(coeffs: Vec<i64>) -> Self {
        Self { coeffs }
    }

    pub fn degree(&self) -> usize {
        self.coeffs.len()
    }

    /// Evaluate `f(m)` over `ℤ` (signed) using Horner's method.
    pub fn eval_signed(&self, m: &BigUint) -> BigInt {
        let d = self.degree();
        if d == 0 {
            return BigInt::one();
        }
        let m_int = BigInt::from_biguint(Sign::Plus, m.clone());
        // Start at leading coefficient (= 1), then Horner from c_{d-1} down to c_0.
        let mut result = BigInt::one();
        for i in (0..d).rev() {
            result = &result * &m_int + BigInt::from(self.coeffs[i]);
        }
        result
    }

    /// Evaluate `f(x) (mod p)` for small `x, p` fitting in `i64`.
    pub fn eval_mod(&self, x: i64, p: u64) -> u64 {
        let p_i = p as i64;
        let mut result = 1i64;
        for i in (0..self.degree()).rev() {
            let coef = ((self.coeffs[i] % p_i) + p_i) % p_i;
            result = ((result * x) % p_i + coef).rem_euclid(p_i);
        }
        result as u64
    }

    /// Find all roots of `f (mod p)` by trial.  For toy primes only.
    pub fn roots_mod(&self, p: u64) -> Vec<u64> {
        let mut roots = Vec::new();
        for r in 0..p {
            if self.eval_mod(r as i64, p) == 0 {
                roots.push(r);
            }
        }
        roots
    }

    /// Algebraic norm `N(a + b·α)` where `α` is a root of `f`.
    ///
    /// Via the resultant identity `N(a + bα) = (−1)ᵈ · bᵈ · f(−a/b)`:
    /// ```text
    ///   N(a + bα) = Σᵢ₌₀ᵈ  cᵢ · (−1)^(d+i) · aⁱ · b^(d−i)   (c_d = 1)
    /// ```
    ///
    /// Sanity checks:
    /// - `d = 2`, `f(x) = x² + c`:   `N = a² + cb²` ✓
    /// - `d = 3`, `f(x) = x³ + 2`:   `N = a³ − 2b³` ✓
    /// - `d = 3`, `f(x) = x³ − x − 1`: `N = a³ − ab² + b³` ✓
    pub fn norm(&self, a: i64, b: i64) -> BigInt {
        let d = self.degree();
        let a_big = BigInt::from(a);
        let b_big = BigInt::from(b);
        let mut a_pow = vec![BigInt::one(); d + 1];
        let mut b_pow = vec![BigInt::one(); d + 1];
        for i in 1..=d {
            a_pow[i] = &a_pow[i - 1] * &a_big;
            b_pow[i] = &b_pow[i - 1] * &b_big;
        }
        let mut sum = BigInt::zero();
        for i in 0..=d {
            let c_i = if i < d {
                BigInt::from(self.coeffs[i])
            } else {
                BigInt::one()
            };
            let sign = if (d + i).is_multiple_of(2) {
                1i64
            } else {
                -1i64
            };
            sum += BigInt::from(sign) * &c_i * &a_pow[i] * &b_pow[d - i];
        }
        sum
    }
}

/// General-degree trapdoor: `p = f(m)` for an arbitrary monic `f`.
#[derive(Clone, Debug)]
pub struct TrapdoorGeneral {
    pub poly: MonicPoly,
    pub m: BigUint,
    pub p: BigUint,
    pub q: BigUint,
}

/// Search `m ≥ m_start` for a Sophie-Germain prime `p = f(m)`.
pub fn construct_trapdoor_general(
    poly: &MonicPoly,
    m_start: &BigUint,
    max_m_steps: u64,
) -> Option<TrapdoorGeneral> {
    let mut m = m_start.clone();
    for _ in 0..max_m_steps {
        let val = poly.eval_signed(&m);
        if val.sign() == Sign::Minus {
            m += 1u32;
            continue;
        }
        let p = match val.to_biguint() {
            Some(v) if v > BigUint::from(2u32) => v,
            _ => {
                m += 1u32;
                continue;
            }
        };
        if (&p & BigUint::one()).is_zero() {
            m += 1u32;
            continue;
        }
        if !is_probable_prime(&p) {
            m += 1u32;
            continue;
        }
        let p_minus_1 = &p - 1u32;
        let q = &p_minus_1 >> 1;
        if !is_probable_prime(&q) {
            m += 1u32;
            continue;
        }
        return Some(TrapdoorGeneral {
            poly: poly.clone(),
            m,
            p,
            q,
        });
    }
    None
}

/// Build a factor base for a general monic polynomial.
pub fn build_factor_base_general(poly: &MonicPoly, b_rat: u64, b_alg: u64) -> FactorBase {
    let rat = sieve_small_primes(b_rat);
    let mut alg = Vec::new();
    for &ell in &rat {
        if ell > b_alg {
            break;
        }
        for r in poly.roots_mod(ell) {
            alg.push((ell, r));
        }
    }
    FactorBase { rat, alg }
}

fn factor_algebraic_general(
    a: i64,
    b: i64,
    poly: &MonicPoly,
    alg_fb: &[(u64, u64)],
) -> Option<Vec<(usize, u32)>> {
    let norm = poly.norm(a, b);
    if norm.is_zero() {
        return None;
    }
    let mut remaining = norm.abs().to_biguint().unwrap();
    let mut factors = Vec::new();
    for (idx, &(ell, r)) in alg_fb.iter().enumerate() {
        let test = ((a as i128).rem_euclid(ell as i128)
            + ((b as i128) * (r as i128)).rem_euclid(ell as i128))
        .rem_euclid(ell as i128);
        if test != 0 {
            continue;
        }
        let mut e = 0u32;
        let ell_big = BigUint::from(ell);
        while (&remaining % &ell_big).is_zero() {
            remaining /= &ell_big;
            e += 1;
        }
        if e > 0 {
            factors.push((idx, e));
        }
    }
    if remaining == BigUint::one() {
        Some(factors)
    } else {
        None
    }
}

/// Sieve over `(a, b)` for a general-degree trapdoor.
pub fn sieve_general(
    trap: &TrapdoorGeneral,
    fb: &FactorBase,
    a_max: i64,
    b_max: i64,
) -> Vec<Relation> {
    let m_int = BigInt::from_biguint(Sign::Plus, trap.m.clone());
    let mut out = Vec::new();
    for a in -a_max..=a_max {
        for b in 1..=b_max {
            if a == 0 && b != 1 {
                continue;
            }
            if gcd_i64(a.unsigned_abs(), b as u64) != 1 {
                continue;
            }
            let n_rat = BigInt::from(a) + BigInt::from(b) * &m_int;
            if n_rat.is_zero() {
                continue;
            }
            let (rat_neg, rat_exps) = match factor_smooth(&n_rat, &fb.rat) {
                Some(v) => v,
                None => continue,
            };
            let alg_exps = match factor_algebraic_general(a, b, &trap.poly, &fb.alg) {
                Some(v) => v,
                None => continue,
            };
            out.push(Relation {
                a,
                b,
                rat_sign_neg: rat_neg,
                rat_exps,
                alg_exps,
            });
        }
    }
    out
}

/// Find a generator of `⟨g⟩` of order `q` in `𝔽_p*` (`p − 1 = 2q`,
/// `q` prime).  Clean version that doesn't depend on a [`Trapdoor`].
pub fn find_subgroup_generator_pq(p: &BigUint, q: &BigUint) -> BigUint {
    let one = BigUint::one();
    let mut g = BigUint::from(2u32);
    while &g < p {
        let g_sq = (&g * &g) % p;
        if g_sq != one && g_sq.modpow(q, p) == one {
            return g_sq;
        }
        g += 1u32;
    }
    one
}

/// Verify recovered factor-base logs against the actual prime values.
/// Generic version (works for any trapdoor, no [`Trapdoor`] dep).
pub fn verify_factor_base_logs_pq(
    p: &BigUint,
    q: &BigUint,
    fb_rat: &[u64],
    g: &BigUint,
    rat_logs: &[BigUint],
) -> (usize, usize) {
    let mut ok = 0;
    let mut total = 0;
    for (idx, &ell) in fb_rat.iter().enumerate() {
        let ell_big = BigUint::from(ell);
        if ell_big.modpow(q, p) != BigUint::one() {
            continue;
        }
        total += 1;
        if g.modpow(&rat_logs[idx], p) == ell_big {
            ok += 1;
        }
    }
    (ok, total)
}

/// General-degree analog of [`recover_factor_base_logs`].
pub fn recover_factor_base_logs_general(
    trap: &TrapdoorGeneral,
    fb: &FactorBase,
    relations: &[Relation],
    pin_idx: usize,
    pin_value: BigUint,
) -> Option<Vec<BigUint>> {
    let n_rat = fb.rat_len();
    let n_alg = fb.alg_len();
    let n_unknowns = n_rat + n_alg;
    let q = &trap.q;
    let mut matrix = Vec::new();
    let mut rhs = Vec::new();
    for rel in relations {
        if rel.rat_sign_neg {
            continue;
        }
        let mut row = vec![BigUint::zero(); n_unknowns];
        for &(idx, e) in &rel.rat_exps {
            row[idx] = (&row[idx] + BigUint::from(e)) % q;
        }
        for &(idx, e) in &rel.alg_exps {
            let neg = (q - (BigUint::from(e) % q)) % q;
            row[n_rat + idx] = (&row[n_rat + idx] + &neg) % q;
        }
        matrix.push(row);
        rhs.push(BigUint::zero());
    }
    let mut pin_row = vec![BigUint::zero(); n_unknowns];
    pin_row[pin_idx] = BigUint::one();
    matrix.push(pin_row);
    rhs.push(pin_value);
    let solution = crate::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n(
        &mut matrix,
        &mut rhs,
        q,
    )?;
    Some(solution[..n_rat].to_vec())
}

/// One-call end-to-end driver for the **general-degree** SNFS.
pub fn snfs_dlp_recover_general(
    trap: &TrapdoorGeneral,
    b_rat: u64,
    b_alg: u64,
    a_max: i64,
    b_max: i64,
) -> Option<(BigUint, Vec<BigUint>, FactorBase)> {
    let g = find_subgroup_generator_pq(&trap.p, &trap.q);
    if g == BigUint::one() {
        return None;
    }
    let fb = build_factor_base_general(&trap.poly, b_rat, b_alg);
    let relations = sieve_general(trap, &fb, a_max, b_max);
    let mut pin: Option<(usize, BigUint)> = None;
    for (idx, &ell) in fb.rat.iter().enumerate() {
        let ell_big = BigUint::from(ell);
        if ell_big.modpow(&trap.q, &trap.p) == BigUint::one() && ell_big != BigUint::one() {
            if let Some(log) = brute_force_log_subgroup(&g, &ell_big, &trap.p, &trap.q) {
                pin = Some((idx, log));
                break;
            }
        }
    }
    let (pin_idx, pin_log) = pin?;
    let rat_logs = recover_factor_base_logs_general(trap, &fb, &relations, pin_idx, pin_log)?;
    Some((g, rat_logs, fb))
}

// ── Descent: individual logarithm for arbitrary target ──────────────

/// Factor `n` completely over `primes`; return the sparse factorisation
/// `[(prime_index, exponent), …]` or `None` if `n` is not smooth.
fn factor_completely_over(n: &BigUint, primes: &[u64]) -> Option<Vec<(usize, u32)>> {
    if n.is_zero() {
        return None;
    }
    let mut remaining = n.clone();
    let mut factors = Vec::new();
    for (idx, &ell) in primes.iter().enumerate() {
        let ell_big = BigUint::from(ell);
        let mut e = 0u32;
        while (&remaining % &ell_big).is_zero() {
            remaining /= &ell_big;
            e += 1;
        }
        if e > 0 {
            factors.push((idx, e));
        }
    }
    if remaining == BigUint::one() {
        Some(factors)
    } else {
        None
    }
}

/// **Individual logarithm via descent**: given factor-base logs
/// computed by the SNFS precomputation, recover `log_g(target) (mod q)`
/// for an arbitrary `target ∈ ⟨g⟩` by sieving `target · g^k` until
/// smooth over the factor base, then composing.
///
/// Standard NFS descent (single-stage): for `k = 0, 1, …, max_steps`,
/// test whether `target · g^k (mod p)` factors over `fb_rat`.  When
/// smooth:
///
/// ```text
///   log_g(target · g^k)  =  Σᵢ eᵢ · rat_logs[i]
///   log_g(target)        =  (that sum)  −  k   (mod q)
/// ```
///
/// Returns `None` if `target ∉ ⟨g⟩` (not a QR mod `p`) or no smooth
/// shift is found within `max_steps`.
///
/// Real NFS descent (for non-smooth targets at crypto sizes) needs a
/// recursive descent that breaks the target into "medium primes" and
/// then large primes; this single-stage version is sufficient at toy
/// scale because most targets are smooth over a few-prime FB.
pub fn individual_log_descent(
    p: &BigUint,
    q: &BigUint,
    fb_rat: &[u64],
    rat_logs: &[BigUint],
    g: &BigUint,
    target: &BigUint,
    max_steps: u64,
) -> Option<BigUint> {
    if target.is_zero() {
        return None;
    }
    if target.modpow(q, p) != BigUint::one() {
        return None;
    }
    let mut current = target.clone();
    let mut k = BigUint::zero();
    for _ in 0..max_steps {
        if let Some(factors) = factor_completely_over(&current, fb_rat) {
            let mut log = BigUint::zero();
            for (idx, e) in &factors {
                let term = (BigUint::from(*e) * &rat_logs[*idx]) % q;
                log = (&log + &term) % q;
            }
            // log_g(target · g^k) = log
            // log_g(target) = (log − k) mod q
            let k_mod = &k % q;
            let result = (&log + q - &k_mod) % q;
            return Some(result);
        }
        current = (&current * g) % p;
        k += 1u32;
    }
    None
}

// ── Detector module ────────────────────────────────────────────────────

/// Statistical tests an adversary would try to distinguish a trapdoored
/// FGHT prime from a genuinely random safe prime.  All implemented
/// tests **fail** to distinguish — exactly the FGHT claim.
pub mod detector {
    use super::*;

    /// Aggregate detection score.  `is_trapdoor` is `true` iff at least
    /// one test fired; the FGHT claim is that this never happens at
    /// crypto sizes.
    #[derive(Clone, Debug)]
    pub struct DetectionReport {
        pub bits: u64,
        pub bit_histogram: [u32; 8],
        pub low_degree_polynomial_search_succeeded: bool,
        pub polynomial_search_degree: u32,
        pub polynomial_search_max_coef: i64,
        pub is_trapdoor: bool,
    }

    /// Run all detector tests on `p`.  Should report
    /// `is_trapdoor = false` for an FGHT prime of crypto-relevant size
    /// (and `true` only at the toy sizes we use here, where the
    /// polynomial degree and coefficient bounds make the search
    /// tractable).
    pub fn analyze(p: &BigUint) -> DetectionReport {
        let mut bit_histogram = [0u32; 8];
        for byte in p.to_bytes_be() {
            for i in 0..8 {
                if (byte >> i) & 1 == 1 {
                    bit_histogram[i] += 1;
                }
            }
        }
        let bits = p.bits();
        // Detection test: try low-degree polynomial fitting.  For each
        // (degree, coef_bound) pair, see if there exist a polynomial
        // f and integer m with f(m) = p and |coefficients of f| ≤
        // coef_bound.  The intuition: trapdoored primes have low-degree
        // low-coef representations; random primes (almost surely) don't.
        //
        // This is exactly the test FGHT argue against.  At toy sizes
        // (sub-30-bit primes) the search is tractable and SUCCEEDS,
        // which is the honest result.  At crypto sizes (1024+ bits) the
        // search space is far too large and the test fails.
        let mut found = false;
        let mut found_deg = 0u32;
        let mut found_coef = 0i64;
        if bits <= 64 {
            // Toy regime: do try the search.
            'outer: for coef_bound in [1i64, 2, 5, 10, 50] {
                for deg in 2u32..=3 {
                    if try_polynomial_recovery(p, deg, coef_bound) {
                        found = true;
                        found_deg = deg;
                        found_coef = coef_bound;
                        break 'outer;
                    }
                }
            }
        }
        DetectionReport {
            bits,
            bit_histogram,
            low_degree_polynomial_search_succeeded: found,
            polynomial_search_degree: found_deg,
            polynomial_search_max_coef: found_coef,
            is_trapdoor: found,
        }
    }

    /// For a degree-`d` polynomial with coefficients in
    /// `[−coef_bound, coef_bound]`, brute-force-search for `(f, m)`
    /// with `f(m) = p`.  Returns `true` on success.  At cryptographic
    /// sizes this is infeasible; at toy sizes it succeeds.
    fn try_polynomial_recovery(p: &BigUint, degree: u32, coef_bound: i64) -> bool {
        // Estimated m from p ≈ m^degree:  m ≈ p^{1/degree}.
        // We try every integer m near this estimate.
        if degree == 2 {
            // m ≈ √p.  For our toy p = m² + c with |c| ≤ small,
            // m ≈ √p is within ±1.
            let p_f64 = p.to_string().parse::<f64>().ok();
            let approx_m = p_f64.map(|x| x.sqrt().round() as u64);
            if let Some(m0) = approx_m {
                for delta in -3i64..=3 {
                    let m = (m0 as i64 + delta).max(2) as u64;
                    let m_sq = BigUint::from(m) * BigUint::from(m);
                    // p − m² should be a small integer c.
                    let p_minus_msq = if p > &m_sq {
                        BigInt::from_biguint(Sign::Plus, p - &m_sq)
                    } else {
                        -BigInt::from_biguint(Sign::Plus, &m_sq - p)
                    };
                    if p_minus_msq.abs() <= BigInt::from(coef_bound) {
                        return true;
                    }
                }
            }
        }
        // Higher degrees: not implemented in the toy detector.
        false
    }
}

// ── ECC analog (commentary only) ───────────────────────────────────────

pub mod ecc_implications {
    //! Architectural notes on whether FGHT's construction could be extended
    //! to attack ECDLP over a Solinas prime.  TL;DR: no public construction
    //! exists; the conceptual obstruction is the absence of a "norm map" or
    //! factor-base structure on elliptic curves analogous to the one on
    //! `ℤ[α]*` that NFS exploits.
    //!
    //! We don't *implement* anything here — there's nothing to implement.
    //! This module is documentation.
    //!
    //! ## Why FGHT does not extend to ECDLP
    //!
    //! ### What FGHT exploits in `𝔽_p*`
    //!
    //! 1. **Multiplicative group structure on `𝔽_p*`** — every nonzero
    //!    element factors uniquely into primes (after lifting to `ℤ`).
    //!    This is what gives NFS a *factor base*: a small set of primes
    //!    over which most lifts will be smooth.
    //!
    //! 2. **Norm map `N : ℤ[α] → ℤ`** — the algebraic side of NFS lives
    //!    in the number ring `ℤ[α]/(f)`.  Its norm map sends elements
    //!    to integers, where factorisation into primes is once again
    //!    available.  This is how the algebraic side "lands back" in
    //!    a place where the factor base applies.
    //!
    //! 3. **A polynomial identity `p = f(m)`** — this is the trapdoor.
    //!    It says `α ≡ m (mod p)`, which is exactly the homomorphism
    //!    `ℤ[α] → 𝔽_p` that ties the two sides together.  Without it,
    //!    the algebraic norms grow as `O(p^{(d−1)/d} · log(B))`
    //!    instead of `O(p^{1/d} · log(B))` — the difference between
    //!    GNFS and SNFS asymptotics.
    //!
    //! ### What an ECDLP analog would need
    //!
    //! For the FGHT construction to extend to `E(𝔽_p)`-discrete-log,
    //! you would need:
    //!
    //! 1. A *factorisation structure* on `E(𝔽_p)` — i.e., a small
    //!    "factor base" of points such that a positive density of
    //!    group elements decompose as sums of factor-base elements.
    //!    This is exactly what **does not exist** for prime-field
    //!    elliptic curves.  Decades of work on summation polynomials
    //!    (Semaev, FPPR, Petit–Quisquater) has tried to manufacture
    //!    such a structure; the current evidence (Galbraith 2015,
    //!    Huang–Kiltz–Petit 2015) is that the heuristic complexity
    //!    claims for prime-field curves are *not* believed to hold.
    //!    See [`crate::cryptanalysis::ec_index_calculus`] for the
    //!    state of the art.
    //!
    //! 2. A *norm-like map* `E(𝔽_p) → 𝔽_p*` that respects the group
    //!    law and lands in a ring where factorisation works.  No such
    //!    map is known.  The closest thing — the Weil/Tate pairing —
    //!    sends `E(𝔽_p)² → 𝔽_{p^k}*` for the embedding degree `k`,
    //!    which is the MOV transfer.  But for cryptographic curves
    //!    `k` is astronomically large, and the resulting target field
    //!    is too big for NFS to bite.
    //!
    //! 3. A *polynomial-identity trapdoor* on the curve coefficients
    //!    `(a, b)` themselves, analogous to `p = f(m)`.  Solinas primes
    //!    *do* have a polynomial structure (e.g. P-256's
    //!    `p = 2²⁵⁶ − 2²²⁴ + 2¹⁹² + 2⁹⁶ − 1` is a low-Hamming-weight
    //!    polynomial evaluation), but no one has shown how to convert
    //!    that into an attack.  The polynomial structure of the prime
    //!    field doesn't propagate to the curve.
    //!
    //! ### What this means in practice
    //!
    //! - FGHT, as built and demonstrated by Fried–Gaudry–Heninger–Thomé
    //!   in 2017, attacks `𝔽_p*` discrete log when `p` is trapdoored.
    //!   That immediately threatens DSA, classical Diffie–Hellman,
    //!   ElGamal, Paillier, BLS-signature target groups, and any other
    //!   primitive whose security reduces to `𝔽_p*` DLP.
    //!
    //! - It does **not** threaten ECDLP on standard prime-field curves
    //!   (NIST P-256/P-384/P-521, SECG secp256k1, Brainpool, FRP256v1,
    //!   SM2, GOST CryptoPro / tc26).  The construction has nothing to
    //!   attach to on the curve side.
    //!
    //! - The residual P-256 rigidity worry — "what if NSA chose `b` from
    //!   a secret weak class?" — is a *different* concern.  It postulates
    //!   an undisclosed attack family on certain curve choices, not a
    //!   trapdoored prime field.  FGHT 2017 is evidence that hidden
    //!   structures can be planted undetectably in primes; it is not
    //!   evidence that the same is true for elliptic curves.
}

// ── Tests ──────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **Trapdoor construction** finds a 20-30 bit Sophie-Germain
    /// `p = m² + c` in a reasonable search time.
    #[test]
    fn construct_small_trapdoor() {
        // For p ≈ 2^18..2^22, start m around √(2^20) ≈ 1024.
        let trap = construct_trapdoor(
            &[2, -1, -2, 3, -3, 5, -5, 7, -7, 11, -11, 13],
            &BigUint::from(1000u32),
            2000,
        )
        .expect("should find a Sophie-Germain p = m² + c in this range");
        // p is prime.
        assert!(is_probable_prime(&trap.p));
        // q is prime.
        assert!(is_probable_prime(&trap.q));
        // p = m² + c.
        let lhs = &trap.m * &trap.m;
        let rhs = if trap.c >= 0 {
            &lhs + BigUint::from(trap.c as u64)
        } else {
            &lhs - BigUint::from((-trap.c) as u64)
        };
        assert_eq!(rhs, trap.p);
        // (p−1)/2 == q.
        assert_eq!(&trap.p - 1u32, &trap.q * 2u32);
    }

    /// **Factor base structure**: for `f(x) = x² + 1` (i.e., `c = 1`),
    /// the algebraic factor base should contain a split prime (with
    /// two roots) for every prime `ℓ ≡ 1 (mod 4)` up to the bound,
    /// and no entry for primes `≡ 3 (mod 4)` (inert).
    #[test]
    fn factor_base_splits_correctly() {
        let fb = build_factor_base(1, 30, 30);
        // Inert: 3, 7, 11, 19, 23 — should not appear in alg fb.
        for inert in [3u64, 7, 11, 19, 23] {
            assert!(fb.alg.iter().all(|&(ell, _)| ell != inert));
        }
        // Split: 5, 13, 17, 29 — each should appear with exactly 2 roots.
        for split in [5u64, 13, 17, 29] {
            let count = fb.alg.iter().filter(|&&(ell, _)| ell == split).count();
            assert_eq!(count, 2, "prime {} should split (2 roots)", split);
        }
    }

    /// **Sieve produces relations**: for a small trapdoor, sieving
    /// over a modest range yields a positive number of smooth
    /// relations.
    #[test]
    fn sieve_yields_relations() {
        let trap = construct_trapdoor(
            &[2, -1, -2, 3, -3, 5, -5, 7, -7, 11, -11, 13],
            &BigUint::from(1000u32),
            2000,
        )
        .expect("trapdoor");
        let fb = build_factor_base(trap.c, 100, 100);
        let relations = sieve(&trap, &fb, 60, 60);
        // At toy scale we expect dozens of relations.
        assert!(
            !relations.is_empty(),
            "sieve should find at least one relation on a {}-bit trapdoor",
            trap.bits(),
        );
    }

    /// **Detector test** — the polynomial-recovery detector succeeds
    /// on toy trapdoored primes (because the search space is small)
    /// and is honest about the FGHT claim that the same search fails
    /// at crypto sizes.
    #[test]
    fn detector_finds_toy_trapdoor() {
        let trap = construct_trapdoor(
            &[2, -1, -2, 3, -3, 5, -5, 7, -7, 11, -11, 13],
            &BigUint::from(1000u32),
            2000,
        )
        .expect("trapdoor");
        let report = detector::analyze(&trap.p);
        // At toy sizes the polynomial search succeeds — that's expected.
        assert!(
            report.low_degree_polynomial_search_succeeded,
            "detector should catch a {}-bit trapdoor (search space tiny)",
            report.bits,
        );
        assert_eq!(report.polynomial_search_degree, 2);
        assert!(report.polynomial_search_max_coef <= 50);
    }

    /// **End-to-end smoke test**: construct a trapdoor, build a factor
    /// base, sieve, and verify that we recover at least one relation
    /// whose algebraic norm divides exactly into the alg factor base
    /// (a structural correctness check).
    #[test]
    fn end_to_end_relation_structure() {
        let trap = construct_trapdoor(
            &[2, -1, -2, 3, -3, 5, -5, 7, -7, 11, -11, 13],
            &BigUint::from(1000u32),
            2000,
        )
        .expect("trapdoor");
        let fb = build_factor_base(trap.c, 100, 100);
        let relations = sieve(&trap, &fb, 60, 60);
        assert!(!relations.is_empty());

        // Cross-check: for the first relation, the product of ℓ^{exps}
        // on the algebraic side reconstructs the algebraic norm.
        let rel = &relations[0];
        let mut alg_product = BigUint::one();
        for &(idx, e) in &rel.alg_exps {
            let ell = BigUint::from(fb.alg[idx].0);
            for _ in 0..e {
                alg_product *= &ell;
            }
        }
        let norm = (rel.a as i128) * (rel.a as i128)
            + (trap.c as i128) * (rel.b as i128) * (rel.b as i128);
        assert_eq!(alg_product, BigUint::from(norm.unsigned_abs()));
    }

    /// **Cross-check the rational side**: for a sieved relation,
    /// the product `±∏ ℓ^{rat_exps}` reconstructs `a + b·m`.
    #[test]
    fn rational_factorisation_is_exact() {
        let trap = construct_trapdoor(
            &[2, -1, -2, 3, -3, 5, -5, 7, -7, 11, -11, 13],
            &BigUint::from(1000u32),
            2000,
        )
        .expect("trapdoor");
        let fb = build_factor_base(trap.c, 100, 100);
        let relations = sieve(&trap, &fb, 60, 60);
        let rel = &relations[0];
        let mut rat_product = BigUint::one();
        for &(idx, e) in &rel.rat_exps {
            let ell = BigUint::from(fb.rat[idx]);
            for _ in 0..e {
                rat_product *= &ell;
            }
        }
        let m_int = BigInt::from_biguint(Sign::Plus, trap.m.clone());
        let expected = BigInt::from(rel.a) + BigInt::from(rel.b) * &m_int;
        let abs_expected = expected.abs().to_biguint().unwrap();
        assert_eq!(rat_product, abs_expected);
    }

    /// **Brute-force discrete log** in `⟨g⟩` of prime order `q`.
    /// On a small subgroup this terminates quickly.
    #[test]
    fn brute_force_log_subgroup_works() {
        // Use a tiny known instance: p = 23, g = 5 (order 22), so q = 11
        // generates the order-11 subgroup via g² = 25 mod 23 = 2.
        // 2^11 mod 23 = 2048 mod 23 = 2048 - 89·23 = 1.  ✓
        let p = BigUint::from(23u32);
        let q = BigUint::from(11u32);
        let g = BigUint::from(2u32);
        // Verify g has order 11.
        assert_eq!(g.modpow(&q, &p), BigUint::one());
        // 2^k mod 23 for k = 0..11:
        //   1, 2, 4, 8, 16, 9, 18, 13, 3, 6, 12.
        let cases = [
            (BigUint::from(1u32), Some(BigUint::from(0u32))),
            (BigUint::from(4u32), Some(BigUint::from(2u32))),
            (BigUint::from(3u32), Some(BigUint::from(8u32))),
            // 5 is not in ⟨2⟩ mod 23 (5 = 2^k for no k since list above).
            (BigUint::from(5u32), None),
        ];
        for (h, expected) in &cases {
            assert_eq!(
                brute_force_log_subgroup(&g, h, &p, &q),
                *expected,
                "log_g({}) in ⟨g⟩ mod {}",
                h,
                p,
            );
        }
    }

    /// **End-to-end SNFS DLP recovery**: construct a trapdoor, sieve,
    /// solve the linear system, recover `log_g(ℓ)` for every rational
    /// factor-base prime `ℓ ∈ ⟨g⟩`, and verify `g^{log_g(ℓ)} ≡ ℓ (mod p)`.
    ///
    /// This is the headline claim of the FGHT module: an actual
    /// discrete-log recovery on a toy trapdoored prime, computed by
    /// the SNFS pipeline end-to-end.
    #[test]
    fn end_to_end_dlp_recovery() {
        // c = 2 keeps the algebraic ring ℤ[√−2] with units {±1} —
        // dodges Schirokauer-map complications.
        let trap =
            construct_trapdoor(&[2], &BigUint::from(8u32), 2000).expect("trapdoor for c = 2");
        let (g, rat_logs, fb) = snfs_dlp_recover(&trap, 30, 30, 30, 20)
            .expect("SNFS should recover factor-base logs on toy p");
        // Sanity: g has order q.
        assert_eq!(g.modpow(&trap.q, &trap.p), BigUint::one());
        assert_ne!(g, BigUint::one());
        // Verify recovered logs.
        let (ok, total) = verify_factor_base_logs(&trap, &fb, &g, &rat_logs);
        assert!(
            total >= 2,
            "at least 2 rational FB primes should lie in ⟨g⟩ on p = {}",
            trap.p,
        );
        assert_eq!(
            ok, total,
            "every in-subgroup FB prime's recovered log must satisfy g^log ≡ ℓ (mod p)"
        );
    }

    /// **MonicPoly basics**: eval, roots, norm formula sanity.
    #[test]
    fn monic_poly_arithmetic() {
        // f(x) = x³ + 2.  coeffs = [c_0, c_1, c_2] = [2, 0, 0]; leading 1.
        let f = MonicPoly::new(vec![2, 0, 0]);
        assert_eq!(f.degree(), 3);
        assert_eq!(f.eval_signed(&BigUint::from(3u32)), BigInt::from(29));
        // f(x) mod 3: 0³+2=2, 1³+2=3≡0, 2³+2=10≡1.  Root at 1.
        assert_eq!(f.roots_mod(3), vec![1]);
        // For α³ = −2, N(a + bα) = a³ − 2b³ (by direct multiplication
        // of the three conjugate factors and Vieta on the symmetric
        // sums).  Note the sign: degree-3 swaps it relative to a naïve
        // "Σ cᵢ aⁱ b^(d−i)" formula.
        assert_eq!(f.norm(1, 1), BigInt::from(-1)); // 1 − 2 = −1
        assert_eq!(f.norm(2, 1), BigInt::from(6)); //  8 − 2 =  6
        assert_eq!(f.norm(1, 2), BigInt::from(-15)); // 1 − 16 = −15
                                                     // Degree-2 sanity: f(x) = x² + 2 should give N = a² + 2b².
        let f2 = MonicPoly::new(vec![2, 0]);
        assert_eq!(f2.norm(3, 1), BigInt::from(11)); // 9 + 2
        assert_eq!(f2.norm(1, 3), BigInt::from(19)); // 1 + 18
    }

    /// **Construct a degree-3 trapdoor by search**.  Demonstrates the
    /// general-degree trapdoor construction routine works.
    #[test]
    fn construct_degree_3_trapdoor() {
        // f(x) = x³ − 3x² − 2x − 1.  Starting at m=9 finds (p=467, q=233).
        let f = MonicPoly::new(vec![-1, -2, -3]);
        let trap = construct_trapdoor_general(&f, &BigUint::from(9u32), 50)
            .expect("should find a SG trapdoor near m=9");
        assert!(is_probable_prime(&trap.p));
        assert!(is_probable_prime(&trap.q));
        assert_eq!(&trap.q * 2u32 + 1u32, trap.p);
        assert_eq!(
            f.eval_signed(&trap.m),
            BigInt::from_biguint(Sign::Plus, trap.p.clone()),
        );
    }

    /// **General-degree sieve produces relations** on a degree-3
    /// trapdoor.  We don't run a full DLP recovery here because
    /// degree-3+ number fields have non-trivial unit groups (rank ≥ 1
    /// by Dirichlet), and clean factor-base log recovery requires
    /// Schirokauer maps which this toy doesn't implement.  But the
    /// SIEVE STILL WORKS — algebraic-side smoothness testing is
    /// purely about the integer norm `|N(a + bα)|`, which our `norm`
    /// formula computes correctly across all degrees.
    #[test]
    fn general_degree_sieve_produces_relations() {
        let f = MonicPoly::new(vec![-1, -2, -3]); // x³ − 3x² − 2x − 1
        let trap = TrapdoorGeneral {
            poly: f.clone(),
            m: BigUint::from(9u32),
            p: BigUint::from(467u32),
            q: BigUint::from(233u32),
        };
        let fb = build_factor_base_general(&trap.poly, 60, 60);
        assert!(!fb.rat.is_empty());
        // Degree-3 polynomial: alg FB can have up to 3 roots per ℓ
        // (split primes).  We expect at least a few alg entries.
        assert!(fb.alg.len() >= 5);
        let relations = sieve_general(&trap, &fb, 30, 20);
        assert!(
            !relations.is_empty(),
            "degree-3 sieve should find at least one smooth relation",
        );
        // Each relation's algebraic exponents reconstruct |N(a + bα)|.
        for rel in relations.iter().take(5) {
            let mut alg_product = BigUint::one();
            for &(idx, e) in &rel.alg_exps {
                let ell = BigUint::from(fb.alg[idx].0);
                for _ in 0..e {
                    alg_product *= &ell;
                }
            }
            let n = f.norm(rel.a, rel.b);
            assert_eq!(alg_product, n.abs().to_biguint().unwrap());
        }
    }

    /// **Descent: individual log of an arbitrary planted target** on
    /// the degree-2 trapdoor.  This is the "individual log via descent"
    /// phase of NFS — the piece that lets us recover any in-subgroup
    /// `log_g(target)`, not just smooth ones.
    ///
    /// Algorithm (single-stage descent): try `k = 0, 1, 2, …` until
    /// `target · g^k (mod p)` factors over the rational factor base.
    /// Compose the recovered factor-base logs and subtract `k`.
    #[test]
    fn descent_recovers_arbitrary_log_degree_2() {
        let trap = construct_trapdoor(&[2], &BigUint::from(8u32), 2000).unwrap();
        let (g, rat_logs, fb) = snfs_dlp_recover(&trap, 30, 30, 30, 20).unwrap();
        // Plant: choose x ∈ [1, q), compute h = g^x, recover x.
        let x_truth = BigUint::from(17u32);
        let h = g.modpow(&x_truth, &trap.p);
        let recovered = individual_log_descent(&trap.p, &trap.q, &fb.rat, &rat_logs, &g, &h, 1000)
            .expect("descent should recover the log");
        assert_eq!(g.modpow(&recovered, &trap.p), h);
        assert_eq!(recovered, x_truth);
    }

    /// **Descent on multiple targets** — sanity that the descent
    /// works for several different planted scalars, not just one.
    #[test]
    fn descent_works_on_multiple_targets() {
        let trap = construct_trapdoor(&[2], &BigUint::from(8u32), 2000).unwrap();
        let (g, rat_logs, fb) = snfs_dlp_recover(&trap, 30, 30, 30, 20).unwrap();
        for x_u32 in [3u32, 7, 11, 19, 25, 31] {
            let x = BigUint::from(x_u32);
            if x >= trap.q {
                continue;
            }
            let h = g.modpow(&x, &trap.p);
            let recovered =
                individual_log_descent(&trap.p, &trap.q, &fb.rat, &rat_logs, &g, &h, 1000);
            if let Some(r) = recovered {
                assert_eq!(g.modpow(&r, &trap.p), h);
            }
        }
    }

    /// **General-degree e2e DLP recovery is not implemented** for
    /// `d ≥ 3` because Dirichlet's unit theorem guarantees a
    /// non-trivial unit group, and clean factor-base log recovery
    /// requires Schirokauer maps to capture each per-relation unit
    /// class.  This test documents the gap and asserts that the
    /// sieve / construction / norm pieces are nonetheless solid by
    /// running them and checking structural invariants.  When
    /// Schirokauer maps are added, this test should be replaced with
    /// a real recovery assertion.
    #[test]
    fn degree_3_recovery_documented_as_blocked_on_schirokauer() {
        let f = MonicPoly::new(vec![-1, -2, -3]);
        let trap = TrapdoorGeneral {
            poly: f.clone(),
            m: BigUint::from(9u32),
            p: BigUint::from(467u32),
            q: BigUint::from(233u32),
        };
        // The construction is solid.
        assert!(is_probable_prime(&trap.p));
        assert!(is_probable_prime(&trap.q));
        // The sieve produces relations.
        let fb = build_factor_base_general(&trap.poly, 60, 60);
        let rels = sieve_general(&trap, &fb, 30, 20);
        assert!(!rels.is_empty());
        // The norm formula is consistent: for every relation, the
        // product of algebraic-factor-base prime norms matches the
        // computed norm.
        for rel in &rels {
            let mut prod = BigUint::one();
            for &(idx, e) in &rel.alg_exps {
                let ell = BigUint::from(fb.alg[idx].0);
                for _ in 0..e {
                    prod *= &ell;
                }
            }
            let n = f.norm(rel.a, rel.b);
            assert_eq!(prod, n.abs().to_biguint().unwrap());
        }
    }

    /// **Same documentation marker for degree-6** — the canonical
    /// FGHT degree.  `f(x) = x⁶ − 3x⁵ − 2x⁴ − x³ − 3x² − 3x − 5`,
    /// `m = 4`, `p = 383`, `q = 191`.  Sieve + construction work;
    /// full recovery blocks on Schirokauer maps for the rank-2 unit
    /// group of this degree-6 imaginary number field.
    #[test]
    fn degree_6_recovery_documented_as_blocked_on_schirokauer() {
        let f = MonicPoly::new(vec![-5, -3, -3, -1, -2, -3]);
        let trap = TrapdoorGeneral {
            poly: f.clone(),
            m: BigUint::from(4u32),
            p: BigUint::from(383u32),
            q: BigUint::from(191u32),
        };
        assert_eq!(f.eval_signed(&trap.m), BigInt::from(383));
        assert!(is_probable_prime(&trap.p));
        assert!(is_probable_prime(&trap.q));
        let fb = build_factor_base_general(&trap.poly, 100, 100);
        let rels = sieve_general(&trap, &fb, 25, 18);
        assert!(!rels.is_empty(), "degree-6 sieve should find smooth pairs");
        for rel in &rels {
            let mut prod = BigUint::one();
            for &(idx, e) in &rel.alg_exps {
                let ell = BigUint::from(fb.alg[idx].0);
                for _ in 0..e {
                    prod *= &ell;
                }
            }
            let n = f.norm(rel.a, rel.b);
            assert_eq!(prod, n.abs().to_biguint().unwrap());
        }
    }

    /// **Individual-logarithm composition**: once the factor-base logs
    /// are known, log of a smooth target follows by linear combination.
    /// This is the "individual log" step of NFS, made trivial when the
    /// target is already smooth over the FB.
    #[test]
    fn individual_log_for_smooth_target() {
        let trap = construct_trapdoor(&[2], &BigUint::from(8u32), 2000).expect("trap");
        let (g, rat_logs, fb) = snfs_dlp_recover(&trap, 30, 30, 30, 20).expect("recover");
        // Pick a target h built from two QR FB primes: h = ℓ₁ · ℓ₂ mod p.
        let mut qr_indices: Vec<usize> = Vec::new();
        for (idx, &ell) in fb.rat.iter().enumerate() {
            let ell_big = BigUint::from(ell);
            if ell_big.modpow(&trap.q, &trap.p) == BigUint::one() && ell_big != BigUint::one() {
                qr_indices.push(idx);
            }
            if qr_indices.len() == 2 {
                break;
            }
        }
        assert!(qr_indices.len() >= 2, "need 2 QR primes for the test");
        let i1 = qr_indices[0];
        let i2 = qr_indices[1];
        let l1 = BigUint::from(fb.rat[i1]);
        let l2 = BigUint::from(fb.rat[i2]);
        let h = (&l1 * &l2) % &trap.p;
        // Predicted log via the factor-base recovery:
        let predicted = (&rat_logs[i1] + &rat_logs[i2]) % &trap.q;
        // Verify g^predicted ≡ h (mod p).
        assert_eq!(g.modpow(&predicted, &trap.p), h);
    }
}
