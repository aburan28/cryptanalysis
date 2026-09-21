//! The ML-KEM and ML-DSA parameter sets, restated as the lattice problems an
//! attacker actually faces.
//!
//! Every estimator in this module consumes one of two shapes:
//!
//! * [`LweInstance`] — "given `(A, b = A·s + e)` over `Z_q`, find `s`".  This is
//!   the *key-recovery* problem.  For ML-KEM it is the public key `t̂ = Â·ŝ + ê`;
//!   for ML-DSA it is `t = A·s1 + s2`.
//! * [`SisInstance`] — "given `A`, find a short nonzero `z` with `A·z = 0`".
//!   This is the *forgery* problem for ML-DSA.  ML-KEM has no SIS side.
//!
//! # Why the module structure is dropped
//!
//! Both schemes are stated over the ring `R_q = Z_q[X]/(X^256+1)` with a module
//! rank `k`, but no known attack exploits the ring or module structure to beat
//! the plain-lattice attacks: the best algorithms treat the module-LWE instance
//! of rank `k` over `R_q` as a plain LWE instance of dimension `256·k` over
//! `Z_q`.  Every published estimate for these schemes — including the ones in
//! the FIPS 203/204 submissions — does exactly this.  So do we, and the
//! `n = 256·k` fields below are that flattening.
//!
//! The one caveat worth stating: this means our numbers cannot reflect an
//! attack that *does* use the structure.  None is known; if one appears, the
//! flattening here is the assumption it would break.
//!
//! # Noise conventions
//!
//! Estimators want a standard deviation, so each distribution is reduced to
//! its second moment:
//!
//! * ML-KEM's secret and error are centred binomial `CBD(η)`, the sum of `η`
//!   differences of fair bits, with variance `η/2`.
//! * ML-DSA's `s1`, `s2` are uniform on the integers `[-η, η]`, with variance
//!   `η(η+1)/3`.
//!
//! Reducing a bounded distribution to its variance is what every estimator
//! does and it is slightly pessimistic for the attacker (a bounded secret is
//! easier than a Gaussian of the same variance, which is what the hybrid and
//! guessing attacks in [`super::hybrid`] cash in on).  The bounds are kept in
//! [`LweInstance::secret_bound`] so those attacks can use them.

/// A Learning-With-Errors instance, flattened over `Z_q`.
///
/// The estimators read this and nothing else, so a parameter set that is not
/// one of the six standard ones can be estimated by constructing this
/// directly — see `crypto mlwe estimate --custom`.
#[derive(Clone, Debug, PartialEq)]
pub struct LweInstance {
    /// Human-readable name, used in reports.
    pub name: String,
    /// Secret dimension over `Z_q`, i.e. `256·k` for a rank-`k` module.
    pub n: usize,
    /// Number of LWE samples the attacker is handed. For a key-recovery
    /// instance this is fixed by the public key's size and cannot be grown:
    /// `256·k` for ML-KEM, `256·k` for ML-DSA.
    pub m: usize,
    /// Modulus.
    pub q: u64,
    /// Standard deviation of each secret coordinate.
    pub sigma_s: f64,
    /// Standard deviation of each error coordinate.
    pub sigma_e: f64,
    /// `|s_i| ≤ secret_bound` with probability 1, or `None` for an unbounded
    /// (e.g. discrete Gaussian) secret. Drives the guessing attacks.
    pub secret_bound: Option<u32>,
    /// Number of values each secret coordinate can take, when bounded.
    /// `2·secret_bound + 1` for a uniform secret; for `CBD(η)` it is the same
    /// support but the distribution is not flat, so [`Self::secret_entropy`]
    /// is what the guessing estimators use.
    pub secret_support: Option<usize>,
    /// Shannon entropy of one secret coordinate, in bits.
    pub secret_entropy_bits: f64,
    /// NIST security category the parameter set targets (1, 3 or 5), and the
    /// classical gate-count requirement that goes with it.
    pub category: Option<Category>,
}

/// A NIST PQC security category and the bit-security it demands.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Category {
    /// Category 1 — at least as hard as AES-128 key search: 2^143 classical gates.
    One,
    /// Category 3 — at least as hard as AES-192 key search: 2^207 classical gates.
    Three,
    /// Category 5 — at least as hard as AES-256 key search: 2^272 classical gates.
    Five,
}

impl Category {
    /// The classical gate-count floor NIST attaches to this category.
    ///
    /// These are the gate counts of exhaustive key search on AES-128/192/256
    /// as tabulated in NIST's call for proposals (2^143, 2^207, 2^272), not
    /// the bare key lengths. Comparisons against them are only meaningful for
    /// a *gate-count* cost model — see [`super::cost::SvpModel::GateCount`].
    /// Comparing a core-SVP number against them understates security.
    pub fn gate_floor_bits(self) -> f64 {
        match self {
            Category::One => 143.0,
            Category::Three => 207.0,
            Category::Five => 272.0,
        }
    }

    /// The category number, for display.
    pub fn number(self) -> u32 {
        match self {
            Category::One => 1,
            Category::Three => 3,
            Category::Five => 5,
        }
    }
}

/// A Short-Integer-Solution instance: find `z ≠ 0` with `‖z‖ ≤ bound` and
/// `A·z ≡ 0 mod q`, where `A` is `n × m` over `Z_q`.
#[derive(Clone, Debug, PartialEq)]
pub struct SisInstance {
    pub name: String,
    /// Number of rows of `A`, i.e. the number of `Z_q` constraints.
    pub n: usize,
    /// Number of columns of `A`, i.e. the dimension of `z`.
    pub m: usize,
    pub q: u64,
    /// The norm bound a solution must meet.
    pub bound: f64,
    /// Which norm `bound` is measured in.
    pub norm: Norm,
    pub category: Option<Category>,
}

/// Which norm an SIS bound is stated in.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Norm {
    /// Euclidean.
    L2,
    /// Infinity. Converted to an `l2` bound of `bound·√m` for the lattice
    /// estimates, which is the standard (attacker-pessimistic) reduction: a
    /// vector with every coordinate at the `l∞` bound has that `l2` norm, and
    /// lattice reduction controls `l2`.
    LInf,
}

impl SisInstance {
    /// The bound expressed in the Euclidean norm.
    pub fn l2_bound(&self) -> f64 {
        match self.norm {
            Norm::L2 => self.bound,
            Norm::LInf => self.bound * (self.m as f64).sqrt(),
        }
    }
}

/// Variance of the centred binomial distribution `CBD(η)`.
fn cbd_variance(eta: usize) -> f64 {
    eta as f64 / 2.0
}

/// Shannon entropy of `CBD(η)` in bits.
///
/// `CBD(η)` puts mass `C(2η, η+v) / 2^{2η}` on `v ∈ [-η, η]`.
fn cbd_entropy_bits(eta: usize) -> f64 {
    let two_eta = 2 * eta;
    let total = 2f64.powi(two_eta as i32);
    let mut h = 0.0;
    for v in 0..=two_eta {
        let p = binomial(two_eta, v) as f64 / total;
        if p > 0.0 {
            h -= p * p.log2();
        }
    }
    h
}

fn binomial(n: usize, k: usize) -> u128 {
    let mut r: u128 = 1;
    for i in 0..k.min(n - k) {
        r = r * (n - i) as u128 / (i as u128 + 1);
    }
    r
}

/// Variance of the uniform distribution on the integers `[-η, η]`.
fn uniform_variance(eta: u32) -> f64 {
    let e = eta as f64;
    e * (e + 1.0) / 3.0
}

// ── ML-KEM (FIPS 203) ────────────────────────────────────────────────────────

/// ML-KEM's key-recovery instance: `t̂ = Â·ŝ + ê` with both `ŝ` and `ê` drawn
/// from `CBD(η₁)`.
///
/// `k` is the module rank, `eta1` the keygen noise parameter. `q = 3329`.
pub fn ml_kem_lwe(name: &str, k: usize, eta1: usize, category: Category) -> LweInstance {
    let sigma = cbd_variance(eta1).sqrt();
    LweInstance {
        name: name.to_string(),
        n: 256 * k,
        m: 256 * k,
        q: 3329,
        sigma_s: sigma,
        sigma_e: sigma,
        secret_bound: Some(eta1 as u32),
        secret_support: Some(2 * eta1 + 1),
        secret_entropy_bits: cbd_entropy_bits(eta1),
        category: Some(category),
    }
}

/// ML-KEM-512: rank 2, `η₁ = 3`, category 1.
pub fn ml_kem_512() -> LweInstance {
    ml_kem_lwe("ML-KEM-512", 2, 3, Category::One)
}
/// ML-KEM-768: rank 3, `η₁ = 2`, category 3.
pub fn ml_kem_768() -> LweInstance {
    ml_kem_lwe("ML-KEM-768", 3, 2, Category::Three)
}
/// ML-KEM-1024: rank 4, `η₁ = 2`, category 5.
pub fn ml_kem_1024() -> LweInstance {
    ml_kem_lwe("ML-KEM-1024", 4, 2, Category::Five)
}

// ── ML-DSA (FIPS 204) ────────────────────────────────────────────────────────

/// One ML-DSA parameter set, in the fields the two lattice problems need.
#[derive(Clone, Copy, Debug)]
pub struct MlDsaSet {
    pub name: &'static str,
    /// Rows of `A` (length of `s2`, `t`).
    pub k: usize,
    /// Columns of `A` (length of `s1`, `z`).
    pub l: usize,
    /// Secret coefficients are uniform on `[-η, η]`.
    pub eta: u32,
    /// `γ₁`: the masking vector's range, `y_i ∈ (-γ₁, γ₁]`.
    pub gamma1: i64,
    /// `γ₂`: the high/low-bits split, `(q-1)/88` or `(q-1)/32`.
    pub gamma2: i64,
    /// `τ`: the challenge's Hamming weight.
    pub tau: usize,
    /// `ω`: the hint budget.
    pub omega: usize,
    pub category: Category,
}

/// ML-DSA's modulus, `2^23 - 2^13 + 1`.
pub const ML_DSA_Q: u64 = 8_380_417;

/// ML-DSA-44: `(k, ℓ, η) = (4, 4, 2)`, category 2 in FIPS 204's own table,
/// which NIST counts against category 1's floor.
pub fn ml_dsa_44_set() -> MlDsaSet {
    MlDsaSet {
        name: "ML-DSA-44",
        k: 4,
        l: 4,
        eta: 2,
        gamma1: 1 << 17,
        gamma2: (ML_DSA_Q as i64 - 1) / 88,
        tau: 39,
        omega: 80,
        category: Category::One,
    }
}
/// ML-DSA-65: `(k, ℓ, η) = (6, 5, 4)`, category 3.
pub fn ml_dsa_65_set() -> MlDsaSet {
    MlDsaSet {
        name: "ML-DSA-65",
        k: 6,
        l: 5,
        eta: 4,
        gamma1: 1 << 19,
        gamma2: (ML_DSA_Q as i64 - 1) / 32,
        tau: 49,
        omega: 55,
        category: Category::Three,
    }
}
/// ML-DSA-87: `(k, ℓ, η) = (8, 7, 2)`, category 5.
pub fn ml_dsa_87_set() -> MlDsaSet {
    MlDsaSet {
        name: "ML-DSA-87",
        k: 8,
        l: 7,
        eta: 2,
        gamma1: 1 << 19,
        gamma2: (ML_DSA_Q as i64 - 1) / 32,
        tau: 60,
        omega: 75,
        category: Category::Five,
    }
}

impl MlDsaSet {
    /// The key-recovery MLWE instance `t = A·s1 + s2`.
    ///
    /// `A` is `k × ℓ` over `R_q`, so flattened there are `256·ℓ` secret
    /// coordinates and `256·k` samples. `s2` plays the error's role, and since
    /// `s1` and `s2` are drawn from the same uniform range the two standard
    /// deviations coincide.
    ///
    /// Note `m` here can be *smaller* than `n` when `k < ℓ` — it never is for
    /// the standardised sets (`k > ℓ` in all three), but the estimators do not
    /// assume otherwise.
    pub fn lwe(&self) -> LweInstance {
        let sigma = uniform_variance(self.eta).sqrt();
        let support = 2 * self.eta as usize + 1;
        LweInstance {
            name: format!("{} (key recovery, MLWE)", self.name),
            n: 256 * self.l,
            m: 256 * self.k,
            q: ML_DSA_Q,
            sigma_s: sigma,
            sigma_e: sigma,
            secret_bound: Some(self.eta),
            secret_support: Some(support),
            secret_entropy_bits: (support as f64).log2(),
            category: Some(self.category),
        }
    }

    /// The forgery MSIS instance.
    ///
    /// A forgery yields a short solution to `[A | I | c] · z = 0` with an `l∞`
    /// bound of `ζ' = max(2(γ₁ - β), 4γ₂ + 2)` (FIPS 204 §C / the Dilithium
    /// submission's §C.3), over `256·(k + ℓ)` columns and `256·k` rows.
    ///
    /// `β = τ·η` is the challenge-times-secret bound.
    pub fn sis(&self) -> SisInstance {
        let beta = self.tau as i64 * self.eta as i64;
        let zeta = std::cmp::max(2 * (self.gamma1 - beta), 4 * self.gamma2 + 2);
        SisInstance {
            name: format!("{} (forgery, MSIS)", self.name),
            n: 256 * self.k,
            m: 256 * (self.k + self.l),
            q: ML_DSA_Q,
            bound: zeta as f64,
            norm: Norm::LInf,
            category: Some(self.category),
        }
    }
}

/// Every standardised parameter set of both schemes, as LWE instances.
pub fn all_lwe() -> Vec<LweInstance> {
    vec![
        ml_kem_512(),
        ml_kem_768(),
        ml_kem_1024(),
        ml_dsa_44_set().lwe(),
        ml_dsa_65_set().lwe(),
        ml_dsa_87_set().lwe(),
    ]
}

/// Every ML-DSA forgery instance.
pub fn all_sis() -> Vec<SisInstance> {
    vec![
        ml_dsa_44_set().sis(),
        ml_dsa_65_set().sis(),
        ml_dsa_87_set().sis(),
    ]
}

/// Look an instance up by a CLI-friendly name, case- and separator-insensitive.
pub fn lwe_by_name(name: &str) -> Option<LweInstance> {
    let key = normalise(name);
    all_lwe()
        .into_iter()
        .find(|i| normalise(&i.name).starts_with(&key) || normalise(&i.name) == key)
}

/// Look an ML-DSA parameter set up by name.
pub fn ml_dsa_by_name(name: &str) -> Option<MlDsaSet> {
    let key = normalise(name);
    [ml_dsa_44_set(), ml_dsa_65_set(), ml_dsa_87_set()]
        .into_iter()
        .find(|s| normalise(s.name) == key)
}

fn normalise(s: &str) -> String {
    s.chars()
        .filter(|c| c.is_ascii_alphanumeric())
        .map(|c| c.to_ascii_lowercase())
        .collect()
}

impl LweInstance {
    /// Entropy of the whole secret, in bits — the cost of dumb exhaustive
    /// search, and the ceiling any attack has to come in under to be
    /// interesting.
    pub fn secret_entropy(&self) -> f64 {
        self.n as f64 * self.secret_entropy_bits
    }

    /// The instance rescaled so secret and error have the same standard
    /// deviation, which is what the primal and dual lattice conditions assume.
    ///
    /// When `σ_s < σ_e` the secret's block of the embedding lattice is scaled
    /// up by `σ_e/σ_s`, which raises the lattice volume; the estimators apply
    /// this through [`Self::volume_scale_log2`] rather than by rewriting the
    /// instance, so the returned value is the factor, not a new instance.
    pub fn volume_scale_log2(&self) -> f64 {
        if self.sigma_s <= 0.0 {
            return 0.0;
        }
        (self.sigma_e / self.sigma_s).log2()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cbd_moments_match_the_closed_form() {
        // Variance η/2, checked against the definition as a sum of η iid
        // differences of fair bits (each of variance 1/2).
        for eta in 1..=8 {
            assert!((cbd_variance(eta) - eta as f64 / 2.0).abs() < 1e-12);
        }
        // CBD(1) is (-1,0,1) with mass (1/4, 1/2, 1/4): entropy 1.5 bits.
        assert!((cbd_entropy_bits(1) - 1.5).abs() < 1e-12);
        // CBD(η) entropy must sit strictly under log2(2η+1), the uniform bound.
        for eta in 1..=8 {
            assert!(cbd_entropy_bits(eta) < ((2 * eta + 1) as f64).log2());
        }
    }

    #[test]
    fn uniform_variance_matches_the_closed_form() {
        // Uniform on [-2,2]: E[X²] = (4+1+0+1+4)/5 = 2 = 2·3/3.
        assert!((uniform_variance(2) - 2.0).abs() < 1e-12);
        // Uniform on [-4,4]: (16+9+4+1+0+1+4+9+16)/9 = 60/9 = 20/3 = 4·5/3.
        assert!((uniform_variance(4) - 20.0 / 3.0).abs() < 1e-12);
    }

    #[test]
    fn ml_kem_dimensions_are_the_fips_203_ones() {
        let s = ml_kem_512();
        assert_eq!((s.n, s.m, s.q), (512, 512, 3329));
        assert!((s.sigma_s - 1.5f64.sqrt()).abs() < 1e-12);
        assert_eq!(ml_kem_768().n, 768);
        assert_eq!(ml_kem_1024().n, 1024);
        // η₁ drops from 3 to 2 at rank 3, so the noise shrinks as n grows.
        assert!(ml_kem_768().sigma_s < ml_kem_512().sigma_s);
        assert!((ml_kem_1024().sigma_s - 1.0).abs() < 1e-12);
    }

    #[test]
    fn ml_dsa_dimensions_are_the_fips_204_ones() {
        let s = ml_dsa_65_set();
        let lwe = s.lwe();
        assert_eq!((lwe.n, lwe.m, lwe.q), (256 * 5, 256 * 6, ML_DSA_Q));
        assert!((lwe.sigma_s - (20.0f64 / 3.0).sqrt()).abs() < 1e-12);

        let sis = s.sis();
        assert_eq!((sis.n, sis.m), (256 * 6, 256 * 11));
        // ζ' = max(2(γ₁-β), 4γ₂+2) with γ₁=2^19, β=49·4=196, γ₂=(q-1)/32.
        let expect = std::cmp::max(2 * ((1 << 19) - 196), 4 * ((ML_DSA_Q as i64 - 1) / 32) + 2);
        assert!((sis.bound - expect as f64).abs() < 1e-9);
        assert_eq!(sis.norm, Norm::LInf);
    }

    #[test]
    fn q_is_the_nist_prime() {
        assert_eq!(ML_DSA_Q, (1u64 << 23) - (1u64 << 13) + 1);
    }

    #[test]
    fn names_resolve_through_the_cli_spellings() {
        for n in ["ml-kem-768", "ML_KEM_768", "mlkem768"] {
            assert_eq!(lwe_by_name(n).unwrap().n, 768, "{n}");
        }
        assert_eq!(ml_dsa_by_name("ml-dsa-87").unwrap().k, 8);
        assert!(lwe_by_name("kyber-512-but-not-really").is_none());
    }

    #[test]
    fn secret_entropy_is_below_the_uniform_bound() {
        for i in all_lwe() {
            let support = i.secret_support.unwrap();
            assert!(i.secret_entropy() <= i.n as f64 * (support as f64).log2() + 1e-9);
            // Every set has far more secret entropy than its category floor,
            // so exhaustive search is never the cheapest attack.
            assert!(i.secret_entropy() > i.category.unwrap().gate_floor_bits());
        }
    }

    #[test]
    fn linf_bounds_convert_to_l2_by_sqrt_m() {
        let s = ml_dsa_44_set().sis();
        assert!((s.l2_bound() - s.bound * (s.m as f64).sqrt()).abs() < 1e-6);
    }
}
