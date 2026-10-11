//! Key recovery for ML-DSA from leakage of the masking vector.
//!
//! ML-DSA signs with `z = y + c·s1`, where `y` is a fresh secret mask. `z` and
//! `c` are both public — `z` is in the signature and `c` is derived from it —
//! so the *only* thing standing between an observer and `s1` is `y`. Every bit
//! of `y` that leaks is a bit of `s1` handed over.
//!
//! This is not a theoretical worry. It is the attack class that the 2024–2026
//! literature on ML-DSA is almost entirely about, for a structural reason: a
//! KEM's secret is touched once per decapsulation and can be protected once,
//! but a signature scheme's mask is generated fresh on every rejection-loop
//! iteration, of which there are several per signature, and each one is an
//! opportunity.
//!
//! # What is implemented
//!
//! * [`recover_s1_from_coefficient_leakage`] — the exact attack. When whole
//!   coefficients of `y` leak, each one gives a linear equation over `Z_q` in
//!   the 256 coefficients of one component of `s1`. Collect 256 independent
//!   equations per component and solve. No lattice, no approximation, no
//!   failure probability: it is Gaussian elimination. Runs at full ML-DSA-65
//!   scale, and the recovered `s1` is then used to forge.
//! * [`recover_from_partial_bits`] — the approximate attack, for when only some
//!   bits of each coefficient leak. Each equation is then correct up to a
//!   bounded error, which is a hidden-number problem, which is a lattice
//!   problem. Implemented over `Z_q` at a dimension LLL can reach; see that
//!   function for why the full 256-dimensional instance is out of scope here
//!   and what it would take.
//! * [`leakage_budget`] — how much leakage the counting bound says is needed,
//!   alongside the figures the published analyses report.
//!
//! # Why recovering `s1` is the whole game
//!
//! `s1` alone is a universal forgery, without `s2` and without `t0`. The reason
//! is in [`crate::pqc::ml_dsa`]'s forger: verification only ever involves the
//! combination `t0 - s2`, and that combination equals `A·s1 - t1·2^d`, which is
//! computable from `s1` and the public key. So the attacks here stop at `s1`
//! and then forge, and [`AttackReport::forged`] is the success criterion —
//! checked by the library's own `ml_dsa_65_verify`, not by us.
//!
//! # References
//!
//! * Key recovery from randomness leakage in ML-DSA, *Journal of Cryptology*
//!   2026 — reports 84 / 136 / 208 leaked bits for ML-DSA-44/65/87 when 256
//!   coordinates leak.
//! * Boneh and Venkatesan, *Hardness of computing the most significant bits of
//!   secret keys in Diffie–Hellman*, CRYPTO 1996 — the hidden-number problem.
//! * Howgrave-Graham and Smart, *Lattice attacks on digital signature schemes*,
//!   2001 — the HNP-from-signatures pattern the partial-bit attack follows.

use crate::cryptanalysis::lattice::lll_reduce;
use crate::pqc::ml_dsa::{
    ml_dsa_65_forge_from_s1, ml_dsa_65_keygen, ml_dsa_65_secret_vectors, ml_dsa_65_sign_traced,
    ml_dsa_65_signature_parts, ml_dsa_65_verify, MlDsaPublicKey, MlDsaSecretKey, ML_DSA_65_ETA,
    ML_DSA_65_GAMMA1, ML_DSA_65_L, ML_DSA_65_Q,
};
use num_bigint::BigInt;
use num_traits::ToPrimitive;
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};

/// ML-DSA's modulus, as an `i64` for the linear algebra.
pub const Q: i64 = ML_DSA_65_Q as i64;
/// Polynomial degree.
pub const N: usize = 256;

// ── Arithmetic mod q ─────────────────────────────────────────────────────────

/// `a^{-1} mod q` by the extended Euclidean algorithm. `q` is prime, so this
/// exists for every `a ≢ 0`.
pub fn inv_mod_q(a: i64) -> Option<i64> {
    let a = a.rem_euclid(Q);
    if a == 0 {
        return None;
    }
    let (mut old_r, mut r) = (a, Q);
    let (mut old_s, mut s) = (1i64, 0i64);
    while r != 0 {
        let quot = old_r / r;
        let (nr, ns) = (old_r - quot * r, old_s - quot * s);
        old_r = r;
        r = nr;
        old_s = s;
        s = ns;
    }
    if old_r != 1 {
        return None;
    }
    Some(old_s.rem_euclid(Q))
}

/// Solve `M·x ≡ b (mod q)` for `x ∈ Z_q^n` by Gaussian elimination.
///
/// `rows` is `(coefficients, rhs)`. More rows than unknowns is fine and
/// expected — extra rows are redundancy against a rank-deficient draw.
///
/// Returns `None` when the rows do not determine a unique solution. The caller
/// should then collect more.
// Gaussian elimination indexes rows and columns by position, and rewriting the
// pivot loops as iterator chains obscures which of the two is being walked. The
// indices are the subject here, not an accident of the loop.
#[allow(clippy::needless_range_loop)]
pub fn solve_mod_q(rows: &[(Vec<i64>, i64)], n: usize) -> Option<Vec<i64>> {
    if rows.len() < n {
        return None;
    }
    let mut m: Vec<Vec<i64>> = rows
        .iter()
        .map(|(a, b)| {
            let mut r: Vec<i64> = a.iter().map(|x| x.rem_euclid(Q)).collect();
            r.push(b.rem_euclid(Q));
            r
        })
        .collect();

    let mut pivot_row = 0usize;
    let mut pivots = vec![usize::MAX; n];
    for col in 0..n {
        let Some(sel) = (pivot_row..m.len()).find(|&r| m[r][col] != 0) else {
            continue;
        };
        m.swap(pivot_row, sel);
        let inv = inv_mod_q(m[pivot_row][col])?;
        for v in m[pivot_row].iter_mut() {
            *v = (*v as i128 * inv as i128).rem_euclid(Q as i128) as i64;
        }
        for r in 0..m.len() {
            if r == pivot_row || m[r][col] == 0 {
                continue;
            }
            let f = m[r][col];
            for c in col..=n {
                let d = (m[r][c] as i128 - f as i128 * m[pivot_row][c] as i128)
                    .rem_euclid(Q as i128) as i64;
                m[r][c] = d;
            }
        }
        pivots[col] = pivot_row;
        pivot_row += 1;
        if pivot_row == m.len() {
            break;
        }
    }
    if pivots.contains(&usize::MAX) {
        return None;
    }
    // Rows below the pivots must be consistent.
    for r in pivot_row..m.len() {
        if m[r][..n].iter().all(|&v| v == 0) && m[r][n] != 0 {
            return None;
        }
    }
    Some((0..n).map(|c| m[pivots[c]][n]).collect())
}

/// Centre a residue into `(-q/2, q/2]`.
pub fn centre(x: i64) -> i64 {
    let x = x.rem_euclid(Q);
    if x > Q / 2 {
        x - Q
    } else {
        x
    }
}

/// Row `j` of the matrix of "multiply by `c`" in `R_q = Z_q[X]/(X^256+1)`.
///
/// `(c·s)[j] = Σ_u σ(j,u)·c[(j-u) mod 256]·s[u]` with `σ = -1` exactly when
/// `u > j`, because that term wraps through `X^256 = -1`.
pub fn negacyclic_row(c: &[i32], j: usize) -> Vec<i64> {
    (0..N)
        .map(|u| {
            let t = (j + N - u) % N;
            let v = c[t] as i64;
            if u <= j {
                v.rem_euclid(Q)
            } else {
                (-v).rem_euclid(Q)
            }
        })
        .collect()
}

/// Negacyclic product, for checking the row construction and for the fault
/// module.
pub fn negacyclic_mul(a: &[i32], b: &[i64]) -> Vec<i64> {
    (0..N)
        .map(|j| {
            negacyclic_row(a, j)
                .iter()
                .zip(b)
                .map(|(&r, &s)| (r as i128 * s as i128) % Q as i128)
                .sum::<i128>()
                .rem_euclid(Q as i128) as i64
        })
        .collect()
}

// ── Leakage models ───────────────────────────────────────────────────────────

/// Which coefficients of `y` a signature gives up, and how completely.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LeakageModel {
    /// `per_poly` whole coefficients of each of the `ℓ` polynomials of `y`,
    /// chosen at positions the attacker cannot pick but can observe.
    ///
    /// Models a fault or a leak that exposes complete words — a DMA snoop, an
    /// unmasked buffer, a rowhammer read. Gives exact equations.
    WholeCoefficients { per_poly: usize },
    /// The top `bits` of `per_poly` coefficients of each polynomial.
    ///
    /// Models the far more common situation: a power or EM trace resolves the
    /// Hamming weight of the high byte, or an unmasked comparison reveals a
    /// range. Gives equations with bounded error.
    HighBits { per_poly: usize, bits: usize },
}

/// One observation the attacker made.
#[derive(Clone, Debug, PartialEq)]
pub struct Observation {
    /// Which polynomial of `y`/`z`.
    pub component: usize,
    /// Which coefficient.
    pub index: usize,
    /// `z[component][index]`, from the signature.
    pub z: i64,
    /// What is known about `y[component][index]`: the exact value, or the
    /// centre of the interval the leaked bits pin it to.
    pub y_known: i64,
    /// Half-width of the interval. Zero when the coefficient leaked whole.
    pub y_error_bound: i64,
    /// The challenge polynomial for this signature.
    pub c: Vec<i32>,
}

/// A signer that leaks. Wraps the library's real ML-DSA-65 signer.
pub struct LeakySigner {
    sk: MlDsaSecretKey,
    model: LeakageModel,
    rng: SmallRng,
    signatures: u64,
    leaked_bits: u64,
}

impl LeakySigner {
    pub fn new(sk: MlDsaSecretKey, model: LeakageModel, seed: u64) -> Self {
        LeakySigner {
            sk,
            model,
            rng: SmallRng::seed_from_u64(seed),
            signatures: 0,
            leaked_bits: 0,
        }
    }

    /// Sign one message and hand back what the side channel saw.
    ///
    /// The signature itself is returned too, because `z` comes from it and an
    /// attacker who could not see the signature would not be attacking.
    #[allow(clippy::needless_range_loop)]
    pub fn sign(&mut self, msg: &[u8]) -> (Vec<u8>, Vec<Observation>) {
        let mut rnd = [0u8; 32];
        self.rng.fill(&mut rnd);
        let (sig, trace) = ml_dsa_65_sign_traced(&self.sk, msg, &rnd);
        self.signatures += 1;
        // `z` and `c` come out of the signature, not the trace: they are public,
        // and taking them from the trace would quietly hand the attacker
        // something an observer does not have. Only `y` is leakage.
        let (c_pub, z_pub) =
            ml_dsa_65_signature_parts(&sig).expect("our own signer emits parseable signatures");

        let (per_poly, bits) = match self.model {
            LeakageModel::WholeCoefficients { per_poly } => (per_poly, 0usize),
            LeakageModel::HighBits { per_poly, bits } => (per_poly, bits),
        };
        // γ₁ = 2^19, so a coefficient is 20 bits wide plus a sign.
        let width = 21usize;
        let mut obs = Vec::new();
        for comp in 0..ML_DSA_65_L {
            // Positions are drawn without replacement, and the draw is the
            // attacker's observation, not their choice.
            let mut idx: Vec<usize> = (0..N).collect();
            for i in 0..per_poly.min(N) {
                let j = self.rng.gen_range(i..N);
                idx.swap(i, j);
                let index = idx[i];
                let y = trace.y[comp][index] as i64;
                let (y_known, bound, leaked) = if bits == 0 {
                    (y, 0i64, width)
                } else {
                    // Keep the top `bits` of the value's 21-bit two's-complement
                    // range: the unknown part is the low `width - bits`.
                    let shift = width.saturating_sub(bits) as u32;
                    let step = 1i64 << shift;
                    let lo = (y.div_euclid(step)) * step;
                    let half = step / 2;
                    (lo + half, half, bits)
                };
                self.leaked_bits += leaked as u64;
                obs.push(Observation {
                    component: comp,
                    index,
                    z: z_pub[comp][index] as i64,
                    y_known,
                    y_error_bound: bound,
                    c: c_pub.clone(),
                });
            }
        }
        (sig, obs)
    }

    pub fn signatures(&self) -> u64 {
        self.signatures
    }
    pub fn leaked_bits(&self) -> u64 {
        self.leaked_bits
    }
}

// ── The exact attack ─────────────────────────────────────────────────────────

/// Recover `s1` from whole-coefficient leakage.
///
/// Each observation `(i, j)` gives `(c·s1_i)[j] = z_i[j] - y_i[j]`, a linear
/// equation over `Z_q` in the 256 coefficients of `s1_i`. Components do not mix,
/// so this is `ℓ` independent 256-unknown systems.
///
/// Returns `None` until every component has 256 independent equations.
pub fn recover_s1_from_coefficient_leakage(obs: &[Observation]) -> Option<Vec<Vec<i32>>> {
    let mut systems: Vec<Vec<(Vec<i64>, i64)>> = vec![Vec::new(); ML_DSA_65_L];
    for o in obs {
        if o.y_error_bound != 0 {
            // A bounded observation is not an equation. Use the lattice attack.
            continue;
        }
        let row = negacyclic_row(&o.c, o.index);
        let rhs = (o.z - o.y_known).rem_euclid(Q);
        systems[o.component].push((row, rhs));
    }
    let mut out = Vec::with_capacity(ML_DSA_65_L);
    for sys in &systems {
        let sol = solve_mod_q(sys, N)?;
        out.push(sol.iter().map(|&v| centre(v) as i32).collect::<Vec<i32>>());
    }
    Some(out)
}

/// What one attack run achieved.
#[derive(Clone, Debug, PartialEq)]
pub struct AttackReport {
    pub method: &'static str,
    /// Signatures the attacker observed.
    pub signatures: u64,
    /// Bits of `y` the side channel gave up in total.
    pub leaked_bits: u64,
    /// Coefficients of `s1` recovered, `256·ℓ`.
    pub coefficients: usize,
    /// How many matched.
    pub correct: usize,
    /// Whether the recovered `s1` produced a forgery that the library's own
    /// verifier accepted. This, not the coefficient count, is the claim.
    pub forged: bool,
}

impl AttackReport {
    pub fn succeeded(&self) -> bool {
        self.correct == self.coefficients && self.forged
    }
}

/// Run the exact attack end to end: generate a key, observe leaky signatures
/// until `s1` falls out, then forge on a message never signed.
pub fn run_coefficient_attack(per_poly: usize, seed: u64) -> Option<AttackReport> {
    let mut kseed = [0u8; 32];
    kseed[..8].copy_from_slice(&seed.to_le_bytes());
    let (pk, sk) = ml_dsa_65_keygen(&kseed);
    let (true_s1, _) = ml_dsa_65_secret_vectors(&sk);

    let mut signer = LeakySigner::new(
        sk,
        LeakageModel::WholeCoefficients { per_poly },
        seed ^ 0xA5A5,
    );
    let mut obs = Vec::new();
    let mut recovered = None;
    // 256 equations per component are needed; a little slack covers a
    // rank-deficient draw, and the loop stops the moment the system solves.
    let max_sigs = 4 * N / per_poly.max(1) + 8;
    for t in 0..max_sigs {
        let msg = format!("leaky message {t}");
        let (_sig, o) = signer.sign(msg.as_bytes());
        obs.extend(o);
        if obs.len() >= ML_DSA_65_L * N {
            if let Some(s1) = recover_s1_from_coefficient_leakage(&obs) {
                recovered = Some(s1);
                break;
            }
        }
    }
    let s1 = recovered?;
    let correct = true_s1
        .iter()
        .zip(&s1)
        .map(|(t, r)| t.iter().zip(r).filter(|(a, b)| a == b).count())
        .sum();
    let forged = forge_and_verify(&pk, &s1, b"a message the signer never saw");

    Some(AttackReport {
        method: "whole-coefficient leakage (linear algebra over Z_q)",
        signatures: signer.signatures(),
        leaked_bits: signer.leaked_bits(),
        coefficients: ML_DSA_65_L * N,
        correct,
        forged,
    })
}

/// Forge with a recovered `s1` and check the library's verifier accepts.
pub fn forge_and_verify(pk: &MlDsaPublicKey, s1: &[Vec<i32>], msg: &[u8]) -> bool {
    match ml_dsa_65_forge_from_s1(pk, s1, msg, b"forgery-mask-seed-0123456789abcd", 256) {
        Some(sig) => ml_dsa_65_verify(pk, msg, &sig),
        None => false,
    }
}

// ── The approximate attack ───────────────────────────────────────────────────

/// A hidden-number-problem instance: `⟨a_t, s⟩ ≡ v_t + e_t (mod q)` with
/// `|e_t| ≤ error_bound` and `|s_i| ≤ secret_bound`.
#[derive(Clone, Debug, PartialEq)]
pub struct HnpInstance {
    pub a: Vec<Vec<i64>>,
    pub v: Vec<i64>,
    pub error_bound: i64,
    pub secret_bound: i64,
    pub n: usize,
}

/// Solve a hidden-number problem by lattice reduction.
///
/// The embedding is the standard one: the lattice spanned by
///
/// ```text
/// [ q·I_m        0            0 ]
/// [ Aᵗ           (E/S)·I_n    0 ]
/// [ vᵗ           0            E ]
/// ```
///
/// contains `(e, (E/S)·s, E)`, whose norm is about `E·√(m + n + 1)` — short,
/// because `E` bounds the errors and the scaling makes the secret's block
/// contribute the same per coordinate. LLL finds it when the lattice's
/// Gaussian heuristic is comfortably above that, which needs roughly
/// `m ≥ n·log q / (log q - log E)` equations.
///
/// # Scale
///
/// This runs at whatever dimension the caller asks for, and the caller should
/// keep `m + n` under about 60. The real ML-DSA instance has `n = 256`, so its
/// embedding is 500-dimensional and LLL alone will not solve it — it needs BKZ
/// at a serious block size, which means fplll or G6K, not this crate's
/// `BigInt` LLL. What is demonstrated here is that the instance *is* an HNP and
/// how its data requirement behaves; the published attacks differ in scale and
/// in reduction quality, not in kind.
// The embedding's rows are built by position in three blocks, and naming the
// positions is what makes the matrix in the doc comment above readable.
#[allow(clippy::needless_range_loop)]
pub fn solve_hnp(inst: &HnpInstance) -> Option<Vec<i64>> {
    let m = inst.a.len();
    let n = inst.n;
    if m == 0 || n == 0 || inst.secret_bound <= 0 {
        return None;
    }
    let dim = m + n + 1;
    let e = inst.error_bound.max(1);
    // Integer scale factor for the secret block: round E/S up so the matrix
    // stays integral without losing the balance.
    let scale = (e + inst.secret_bound - 1) / inst.secret_bound;
    let scale = scale.max(1);

    let mut basis: Vec<Vec<BigInt>> = Vec::with_capacity(dim);
    for t in 0..m {
        let mut row = vec![BigInt::from(0); dim];
        row[t] = BigInt::from(Q);
        basis.push(row);
    }
    for i in 0..n {
        let mut row = vec![BigInt::from(0); dim];
        for t in 0..m {
            row[t] = BigInt::from(inst.a[t][i].rem_euclid(Q));
        }
        row[m + i] = BigInt::from(scale);
        basis.push(row);
    }
    let mut last = vec![BigInt::from(0); dim];
    for t in 0..m {
        last[t] = BigInt::from(inst.v[t].rem_euclid(Q));
    }
    last[dim - 1] = BigInt::from(e);
    basis.push(last);

    lll_reduce(&mut basis, 0.99).ok()?;

    // Look for a reduced row whose last entry is ±E: that is the embedding
    // coordinate, and the secret block sits next to it.
    //
    // The sign is worth deriving rather than guessing. With `v = A·s + e`, the
    // short lattice vector is
    //
    //     last_row - Σ s_i·secret_row_i  =  (e, -scale·s, E)   (mod the q rows)
    //
    // so the middle block holds *minus* the scaled secret when the tail is
    // `+E`, and LLL is equally happy to return the whole vector negated.
    for row in &basis {
        let tail = row[dim - 1].to_i64()?;
        if tail.abs() != e {
            continue;
        }
        let sign = if tail == e { -1i64 } else { 1 };
        let mut s = Vec::with_capacity(n);
        let mut ok = true;
        for i in 0..n {
            let Some(v) = row[m + i].to_i64() else {
                ok = false;
                break;
            };
            if v % scale != 0 {
                ok = false;
                break;
            }
            let si = sign * (v / scale);
            if si.abs() > inst.secret_bound {
                ok = false;
                break;
            }
            s.push(si);
        }
        if ok && s.len() == n {
            return Some(s);
        }
    }
    None
}

/// Build an HNP instance from partial-bit observations of a *scaled-down*
/// ML-DSA-shaped signer, and solve it.
///
/// `n` is the ring degree of the reduced instance; `m` the number of equations.
/// The secret is uniform on `[-η, η]` with ML-DSA-65's `η = 4`, the mask is
/// uniform on `(-γ₁, γ₁]` with ML-DSA-65's `γ₁`, and `known_bits` of each mask
/// coefficient leak — the same shape as the real thing, at a dimension LLL can
/// finish.
pub fn recover_from_partial_bits(
    n: usize,
    m: usize,
    known_bits: usize,
    seed: u64,
) -> Option<(Vec<i64>, Vec<i64>)> {
    let (truth, inst) = partial_bit_instance(n, m, known_bits, seed)?;
    let found = solve_hnp(&inst)?;
    Some((truth, found))
}

/// Build the reduced-dimension instance without solving it, so a caller can
/// check a candidate solution against the equations it came from.
///
/// `known_bits` must leave the mask's range inside one quantisation step, which
/// means at least 1 — with zero leaked bits the "known" value would not bracket
/// the mask and the instance would be malformed rather than merely hard.
pub fn partial_bit_instance(
    n: usize,
    m: usize,
    known_bits: usize,
    seed: u64,
) -> Option<(Vec<i64>, HnpInstance)> {
    if known_bits == 0 || n == 0 || m == 0 {
        return None;
    }
    let mut rng = SmallRng::seed_from_u64(seed);
    let eta = ML_DSA_65_ETA as i64;
    let gamma1 = ML_DSA_65_GAMMA1 as i64;
    let width = 21usize;
    let shift = width.saturating_sub(known_bits) as u32;
    let step = 1i64 << shift;

    let secret: Vec<i64> = (0..n).map(|_| rng.gen_range(-eta..=eta)).collect();
    let mut a = Vec::with_capacity(m);
    let mut v = Vec::with_capacity(m);
    for _ in 0..m {
        let row: Vec<i64> = (0..n).map(|_| rng.gen_range(0..Q)).collect();
        let y: i64 = rng.gen_range(-gamma1 + 1..=gamma1);
        let z: i128 = row
            .iter()
            .zip(&secret)
            .map(|(&ai, &si)| ai as i128 * si as i128)
            .sum::<i128>()
            + y as i128;
        let z = z.rem_euclid(Q as i128) as i64;
        // The attacker sees z and the top bits of y.
        let y_known = y.div_euclid(step) * step + step / 2;
        v.push((z - y_known).rem_euclid(Q));
        a.push(row);
    }
    Some((
        secret,
        HnpInstance {
            a,
            v,
            error_bound: step / 2,
            secret_bound: eta,
            n,
        },
    ))
}

/// The residual `⟨a_t, s⟩ - v_t` of each equation, centred. A solution is
/// consistent exactly when every residual is within the instance's error bound.
pub fn hnp_residuals(inst: &HnpInstance, s: &[i64]) -> Vec<i64> {
    inst.a
        .iter()
        .zip(&inst.v)
        .map(|(a, &v)| {
            let dot = a
                .iter()
                .zip(s)
                .map(|(&ai, &si)| ai as i128 * si as i128)
                .sum::<i128>();
            centre((dot - v as i128).rem_euclid(Q as i128) as i64)
        })
        .collect()
}

// ── Budgets ──────────────────────────────────────────────────────────────────

/// How much leakage is needed, by counting, and what the literature reports.
#[derive(Clone, Debug, PartialEq)]
pub struct LeakageBudget {
    pub parameter_set: &'static str,
    /// Bits of entropy in `s1`.
    pub secret_entropy_bits: f64,
    /// Whole coefficients of `y` needed for the exact attack: `256·ℓ`, one
    /// equation per unknown.
    pub coefficients_for_exact_attack: usize,
    /// The counting lower bound: an equation over `Z_q` cannot carry more than
    /// `log2 q` bits, so no attack of this shape can work on fewer leaked bits
    /// than this.
    pub counting_bound_bits: f64,
    /// What the published lattice analysis reports for 256 leaking coordinates.
    pub published_bits: u32,
}

/// Budgets for the three parameter sets.
///
/// The `published_bits` column is the *Journal of Cryptology* 2026 figure
/// (84 / 136 / 208 for ML-DSA-44/65/87 with 256 leaking coordinates). It comes
/// from a lattice analysis, not from our counting bound, and the two answer
/// different questions: the counting bound says what is impossible, the
/// published figure says what was achieved. They are listed together so the gap
/// between them is visible.
pub fn leakage_budget() -> Vec<LeakageBudget> {
    let log2q = (Q as f64).log2();
    let sets: [(&'static str, usize, i64, u32); 3] = [
        ("ML-DSA-44", 4, 2, 84),
        ("ML-DSA-65", 5, 4, 136),
        ("ML-DSA-87", 7, 2, 208),
    ];
    sets.into_iter()
        .map(|(name, l, eta, published)| {
            let entropy = (l * N) as f64 * ((2 * eta + 1) as f64).log2();
            LeakageBudget {
                parameter_set: name,
                secret_entropy_bits: entropy,
                coefficients_for_exact_attack: l * N,
                counting_bound_bits: entropy.min((l * N) as f64 * log2q),
                published_bits: published,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modular_inverse_is_an_inverse() {
        for a in [1i64, 2, 3, 12345, Q - 1, Q / 2] {
            let inv = inv_mod_q(a).unwrap();
            assert_eq!(
                (a as i128 * inv as i128).rem_euclid(Q as i128),
                1,
                "a = {a}"
            );
        }
        assert!(inv_mod_q(0).is_none());
        assert!(inv_mod_q(Q).is_none());
    }

    #[test]
    fn solve_mod_q_solves_a_known_system() {
        // 2x + 3y = 8, x + y = 3  ⟹  x = 1, y = 2.
        let rows = vec![(vec![2i64, 3], 8i64), (vec![1, 1], 3)];
        assert_eq!(solve_mod_q(&rows, 2), Some(vec![1, 2]));
        // Redundant but consistent rows are fine.
        let rows = vec![(vec![2i64, 3], 8i64), (vec![1, 1], 3), (vec![3, 4], 11)];
        assert_eq!(solve_mod_q(&rows, 2), Some(vec![1, 2]));
    }

    #[test]
    fn solve_mod_q_refuses_a_rank_deficient_system() {
        // Two copies of the same equation determine nothing.
        let rows = vec![(vec![1i64, 1], 3i64), (vec![2, 2], 6)];
        assert!(solve_mod_q(&rows, 2).is_none());
        // Too few rows.
        assert!(solve_mod_q(&[(vec![1i64, 1], 3i64)], 2).is_none());
    }

    #[test]
    fn solve_mod_q_handles_a_random_full_rank_system() {
        let mut rng = SmallRng::seed_from_u64(1);
        let n = 20;
        let x: Vec<i64> = (0..n).map(|_| rng.gen_range(0..Q)).collect();
        let rows: Vec<(Vec<i64>, i64)> = (0..n + 4)
            .map(|_| {
                let a: Vec<i64> = (0..n).map(|_| rng.gen_range(0..Q)).collect();
                let b = a
                    .iter()
                    .zip(&x)
                    .map(|(&ai, &xi)| ai as i128 * xi as i128)
                    .sum::<i128>()
                    .rem_euclid(Q as i128) as i64;
                (a, b)
            })
            .collect();
        assert_eq!(solve_mod_q(&rows, n), Some(x));
    }

    #[test]
    fn negacyclic_row_matches_schoolbook_multiplication() {
        let mut rng = SmallRng::seed_from_u64(7);
        let c: Vec<i32> = (0..N).map(|_| rng.gen_range(-1..=1)).collect();
        let s: Vec<i64> = (0..N).map(|_| rng.gen_range(-4..=4)).collect();
        // Schoolbook, with X^256 = -1.
        let mut expect = vec![0i128; N];
        for (t, &ct) in c.iter().enumerate() {
            for (u, &su) in s.iter().enumerate() {
                let k = t + u;
                if k < N {
                    expect[k] += ct as i128 * su as i128;
                } else {
                    expect[k - N] -= ct as i128 * su as i128;
                }
            }
        }
        let got = negacyclic_mul(&c, &s);
        for j in 0..N {
            assert_eq!(got[j], expect[j].rem_euclid(Q as i128) as i64, "j = {j}");
        }
    }

    #[test]
    fn negacyclic_row_is_minus_one_past_the_wrap() {
        // X^255 · X^1: c = X, s = X^255 → product is -1 at index 0.
        let mut c = vec![0i32; N];
        c[1] = 1;
        let mut s = vec![0i64; N];
        s[255] = 1;
        let p = negacyclic_mul(&c, &s);
        assert_eq!(p[0], Q - 1);
        assert!(p[1..].iter().all(|&x| x == 0));
    }

    #[test]
    fn whole_coefficient_leakage_recovers_s1_and_forges() {
        // 64 coefficients per polynomial per signature: four signatures'
        // worth of equations, plus slack for a rank-deficient draw.
        let r = run_coefficient_attack(64, 1).expect("attack ran");
        assert_eq!(r.correct, r.coefficients, "{r:?}");
        assert!(r.forged, "recovered s1 but could not forge: {r:?}");
        assert!(r.succeeded());
        assert!(r.signatures >= 4, "{} signatures", r.signatures);
        assert!(r.signatures <= 24, "{} signatures", r.signatures);
    }

    #[test]
    fn fewer_leaked_coefficients_needs_more_signatures() {
        let a = run_coefficient_attack(128, 5).unwrap();
        let b = run_coefficient_attack(32, 5).unwrap();
        assert!(a.succeeded() && b.succeeded());
        assert!(
            b.signatures > a.signatures,
            "{} vs {} signatures",
            b.signatures,
            a.signatures
        );
        // Total leaked bits should be comparable: the attack needs 256
        // equations per component either way.
        let ratio = b.leaked_bits as f64 / a.leaked_bits as f64;
        assert!(ratio > 0.5 && ratio < 2.5, "leaked-bit ratio {ratio}");
    }

    #[test]
    fn the_attack_is_stable_across_keys() {
        for seed in [2u64, 13, 29] {
            let r = run_coefficient_attack(96, seed).unwrap();
            assert!(r.succeeded(), "seed {seed}: {r:?}");
        }
    }

    #[test]
    fn a_forgery_from_the_true_s1_verifies() {
        // Sanity on the forger itself, independent of any recovery: given the
        // real s1 it must produce signatures the library accepts, on messages
        // the signer never saw.
        let (pk, sk) = ml_dsa_65_keygen(&[9u8; 32]);
        let (s1, _) = ml_dsa_65_secret_vectors(&sk);
        for m in [b"one".as_slice(), b"two", b"a third message entirely"] {
            assert!(forge_and_verify(&pk, &s1, m), "failed on {m:?}");
        }
    }

    #[test]
    fn a_forgery_from_a_wrong_s1_does_not_verify() {
        let (pk, sk) = ml_dsa_65_keygen(&[9u8; 32]);
        let (mut s1, _) = ml_dsa_65_secret_vectors(&sk);
        s1[0][0] = s1[0][0].wrapping_add(1);
        assert!(!forge_and_verify(&pk, &s1, b"nope"));
    }

    #[test]
    fn leaky_signatures_are_still_valid_signatures() {
        // The leakage is a side channel, not a modification: the signer's
        // output must remain exactly what ML-DSA-65 would produce.
        let (pk, sk) = ml_dsa_65_keygen(&[4u8; 32]);
        let mut signer = LeakySigner::new(sk, LeakageModel::WholeCoefficients { per_poly: 8 }, 77);
        for t in 0..4 {
            let msg = format!("message {t}");
            let (sig, obs) = signer.sign(msg.as_bytes());
            assert!(ml_dsa_65_verify(&pk, msg.as_bytes(), &sig));
            assert_eq!(obs.len(), 8 * ML_DSA_65_L);
            for o in &obs {
                assert!(o.index < N);
                assert!(o.component < ML_DSA_65_L);
                assert_eq!(o.y_error_bound, 0);
                assert_eq!(o.c.len(), N);
            }
        }
    }

    #[test]
    fn high_bit_observations_bracket_the_true_mask() {
        let (_, sk) = ml_dsa_65_keygen(&[6u8; 32]);
        let (s1, _) = ml_dsa_65_secret_vectors(&sk);
        let mut signer = LeakySigner::new(
            sk,
            LeakageModel::HighBits {
                per_poly: 4,
                bits: 8,
            },
            13,
        );
        let (_sig, obs) = signer.sign(b"bracket me");
        for o in &obs {
            assert!(o.y_error_bound > 0);
            // z - c·s1 is the true y; the observation must contain it.
            let cs1 = negacyclic_mul(
                &o.c,
                &s1[o.component]
                    .iter()
                    .map(|&x| x as i64)
                    .collect::<Vec<_>>(),
            );
            let y_true = centre(o.z - cs1[o.index]);
            assert!(
                (y_true - o.y_known).abs() <= o.y_error_bound,
                "y = {y_true} outside {} ± {}",
                o.y_known,
                o.y_error_bound
            );
        }
    }

    #[test]
    fn partial_bit_leakage_recovers_a_small_secret_by_lattice() {
        // The HNP shape, at a dimension LLL finishes. Leaking the top 12 bits
        // of a 21-bit mask leaves a 9-bit error, which is small enough against
        // q ≈ 2^23 that the embedding's short vector is unique.
        let (truth, found) = recover_from_partial_bits(8, 22, 12, 3).expect("lattice solved");
        assert_eq!(truth, found);
    }

    #[test]
    fn an_hnp_solution_is_always_consistent_with_its_equations() {
        // The property that matters: the solver may fail, but it must never
        // return a vector that does not satisfy the instance. Swept across
        // leakage budgets, including ones so thin the attack should struggle.
        for bits in [1usize, 4, 8, 12, 16] {
            for (n, m) in [(6usize, 14usize), (8, 22)] {
                let (truth, inst) = partial_bit_instance(n, m, bits, 5).unwrap();
                // The instance itself must bracket the truth.
                for r in hnp_residuals(&inst, &truth) {
                    assert!(
                        r.abs() <= inst.error_bound,
                        "instance malformed at {bits} bits: residual {r} > {}",
                        inst.error_bound
                    );
                }
                if let Some(found) = solve_hnp(&inst) {
                    assert!(found.iter().all(|&x| x.abs() <= inst.secret_bound));
                    for r in hnp_residuals(&inst, &found) {
                        assert!(
                            r.abs() <= inst.error_bound,
                            "solver returned an inconsistent vector at {bits} bits, n = {n}"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn a_thin_leakage_budget_still_solves_at_small_dimension() {
        // Worth recording because it is the opposite of the intuition: at
        // n = 8, even one leaked bit per mask coefficient is enough, because
        // q ≈ 2^23 dwarfs η = 4 and each equation is still worth several bits.
        // What makes real ML-DSA hard is *dimension* — 256 unknowns per
        // component — not the bit budget. Do not read this as "one bit breaks
        // ML-DSA"; read it as "the bit budget is the wrong axis to worry about
        // at toy scale".
        let (truth, found) = recover_from_partial_bits(8, 24, 1, 21).expect("solved");
        assert_eq!(truth, found);
    }

    #[test]
    fn partial_bit_instances_reject_a_zero_bit_budget() {
        // Zero leaked bits is not "hard", it is malformed: the quantisation
        // step would exceed the mask's range and the stated error bound would
        // not hold. The constructor says so rather than producing a broken
        // instance.
        assert!(partial_bit_instance(8, 20, 0, 1).is_none());
        assert!(recover_from_partial_bits(8, 20, 0, 1).is_none());
    }

    #[test]
    fn budgets_are_consistent_and_list_the_published_figures() {
        let b = leakage_budget();
        assert_eq!(b.len(), 3);
        assert_eq!(b[1].parameter_set, "ML-DSA-65");
        assert_eq!(b[1].coefficients_for_exact_attack, 5 * 256);
        assert_eq!(b[1].published_bits, 136);
        for r in &b {
            // Entropy grows with the parameter set, and the counting bound
            // never exceeds it.
            assert!(r.counting_bound_bits <= r.secret_entropy_bits + 1e-9);
            // The published figure is far below the whole secret's entropy —
            // which is the point: leakage is leveraged, not transcribed.
            assert!((r.published_bits as f64) < r.secret_entropy_bits);
        }
        assert!(b[0].secret_entropy_bits < b[1].secret_entropy_bits);
    }
}
