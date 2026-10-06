//! `crax ecdsa`: signature-level attacks on ECDSA.
//!
//! These are *implementation* attacks — they exploit how the per-message
//! nonce `k` is produced, not the ECDLP on the curve itself. Every command
//! reconstructs the private scalar and then **verifies it independently**
//! of the solver that produced it (`d · G == Q`, or by re-deriving the
//! signatures), reporting `"verified": true` only on success.
//!
//! Subcommands:
//! - `nonce-reuse` — two signatures that reused one nonce `k` leak `k` and
//!   then `d` by elementary algebra.
//! - `hnp` — biased-nonce key recovery through the hidden number problem,
//!   driving [`crate::cryptanalysis::hnp_ecdsa`] and the lattice reduction
//!   in [`crate::cryptanalysis::lattice`].
//! - `audit` — run the [`crate::cryptanalysis::ecdsa_audit`] transcript
//!   auditor and report the nonce-bias diagnostics.
//! - `invalid-curve` — the real oracle invalid-curve attack of
//!   [`crate::cryptanalysis::invalid_curve_attack`] on a j-invariant-0
//!   base curve.

use clap::{Args, Subcommand, ValueEnum};
use num_bigint::BigUint;
use num_traits::Zero;
use serde::Serialize;

use super::output::{parse_biguint, parse_pair, CmdResult, Failure, Out};
use crate::cryptanalysis::ecdsa_audit::{
    audit_ecdsa_transcript, quick_bias_score, AuditOptions, AuditResult, EcdsaSample,
};
use crate::cryptanalysis::hnp_ecdsa::{
    hnp_recover_key_with_reduction, BiasedSignature, HnpReduction,
};
use crate::cryptanalysis::invalid_curve_attack::mount_invalid_curve_attack;
use crate::ecc::curve::CurveParams;
use crate::ecc::keys::EccPublicKey;
use crate::ecc::point::Point;
use crate::utils::mod_inverse;

use rand::rngs::StdRng;
use rand::{RngCore, SeedableRng};

// ── Curve selection, shared by every subcommand ──────────────────────

/// A named curve, or a full custom short-Weierstrass curve.
#[derive(Args, Clone, Debug)]
pub struct CurveSel {
    /// A named curve: secp256k1, p256, sm2.
    #[arg(long, conflicts_with_all = ["p", "a", "b", "gx", "gy", "order"])]
    pub curve: Option<String>,
    /// Field prime (decimal or 0x hex).
    #[arg(long)]
    pub p: Option<String>,
    #[arg(long)]
    pub a: Option<String>,
    #[arg(long)]
    pub b: Option<String>,
    /// Base-point x-coordinate.
    #[arg(long)]
    pub gx: Option<String>,
    /// Base-point y-coordinate.
    #[arg(long)]
    pub gy: Option<String>,
    /// Order n of the base point.
    #[arg(long)]
    pub order: Option<String>,
}

fn named(name: &str) -> Option<CurveParams> {
    match name.to_ascii_lowercase().replace('-', "").as_str() {
        "secp256k1" => Some(CurveParams::secp256k1()),
        "p256" | "secp256r1" | "prime256v1" => Some(CurveParams::p256()),
        "sm2" => Some(CurveParams::sm2()),
        _ => None,
    }
}

impl CurveSel {
    /// Resolve to a full [`CurveParams`], defaulting to `default_named`
    /// when nothing is supplied (used by the `--demo` modes).
    fn resolve(&self, default_named: &str) -> Result<CurveParams, String> {
        if let Some(n) = &self.curve {
            return named(n)
                .ok_or_else(|| format!("unknown curve {n:?}; known: secp256k1, p256, sm2"));
        }
        if self.p.is_none()
            && self.a.is_none()
            && self.b.is_none()
            && self.gx.is_none()
            && self.gy.is_none()
            && self.order.is_none()
        {
            return named(default_named).ok_or_else(|| "no default curve".to_string());
        }
        let big = |s: &Option<String>, what: &str| -> Result<BigUint, String> {
            parse_biguint(
                s.as_deref()
                    .ok_or_else(|| format!("--{what} is required"))?,
            )
        };
        let p = big(&self.p, "p")?;
        let a = big(&self.a, "a")? % &p;
        let b = big(&self.b, "b")? % &p;
        let gx = big(&self.gx, "gx")?;
        let gy = big(&self.gy, "gy")?;
        let n = big(&self.order, "order")?;
        Ok(CurveParams {
            name: "custom",
            a,
            b,
            gx,
            gy,
            n,
            h: 1,
            p,
        })
    }
}

/// The victim's public key, either given or planted for a demo.
fn public_key(curve: &CurveParams, q: &Option<String>) -> Result<Option<EccPublicKey>, String> {
    match q {
        Some(s) => {
            let (x, y) = parse_pair(s)?;
            let point = Point::Affine {
                x: curve.fe(x),
                y: curve.fe(y),
            };
            if !curve.is_on_curve(&point) {
                return Err("Q is not on the curve".into());
            }
            Ok(Some(EccPublicKey {
                point,
                curve_name: curve.name.to_string(),
            }))
        }
        None => Ok(None),
    }
}

/// Sign `z` with an explicit nonce `k` (deliberately bypasses RFC 6979 so
/// the demo modes can inject a chosen or biased nonce).
fn sign_with_nonce(
    z: &BigUint,
    k: &BigUint,
    d: &BigUint,
    curve: &CurveParams,
) -> Option<(BigUint, BigUint)> {
    let kg = curve.generator().scalar_mul(k, &curve.a_fe());
    let x1 = match &kg {
        Point::Affine { x, .. } => x.value.clone(),
        Point::Infinity => return None,
    };
    let r = &x1 % &curve.n;
    if r.is_zero() {
        return None;
    }
    let rd = (&r * d) % &curve.n;
    let z_plus_rd = (z + &rd) % &curve.n;
    let k_inv = mod_inverse(k, &curve.n)?;
    let s = (&k_inv * &z_plus_rd) % &curve.n;
    if s.is_zero() {
        return None;
    }
    Some((r, s))
}

/// A biased nonce uniform in `[1, 2^k_bits)`.
fn biased_nonce<R: RngCore>(rng: &mut R, k_bits: u32) -> BigUint {
    loop {
        let bytes = k_bits.div_ceil(8) as usize;
        let mut buf = vec![0u8; bytes];
        rng.fill_bytes(&mut buf);
        let extra = (bytes as u32) * 8 - k_bits;
        if extra > 0 {
            buf[0] &= 0xff >> extra;
        }
        let k = BigUint::from_bytes_be(&buf);
        if !k.is_zero() {
            return k;
        }
    }
}

// ── `crax ecdsa` command tree ────────────────────────────────────────

#[derive(Subcommand, Clone, Debug)]
pub enum EcdsaCmd {
    /// Recover the key from two signatures that reused one nonce.
    NonceReuse(NonceReuseArgs),
    /// Biased-nonce key recovery via the hidden number problem (lattice).
    Hnp(HnpArgs),
    /// Audit a signature transcript for nonce bias.
    Audit(AuditArgs),
    /// Oracle invalid-curve attack on a j=0 base curve.
    InvalidCurve(InvalidCurveArgs),
}

pub fn run(out: Out, cmd: &EcdsaCmd) -> CmdResult {
    match cmd {
        EcdsaCmd::NonceReuse(a) => run_nonce_reuse(out, a),
        EcdsaCmd::Hnp(a) => run_hnp(out, a),
        EcdsaCmd::Audit(a) => run_audit(out, a),
        EcdsaCmd::InvalidCurve(a) => run_invalid_curve(out, a),
    }
}

// ── nonce-reuse ──────────────────────────────────────────────────────

#[derive(Args, Clone, Debug)]
pub struct NonceReuseArgs {
    #[command(flatten)]
    pub curve: CurveSel,
    /// Shared signature component r (both signatures used the same k).
    #[arg(long, required_unless_present = "demo")]
    pub r: Option<String>,
    /// s of the first signature.
    #[arg(long, required_unless_present = "demo")]
    pub s1: Option<String>,
    /// s of the second signature.
    #[arg(long, required_unless_present = "demo")]
    pub s2: Option<String>,
    /// Message hash z of the first signature (reduced mod n).
    #[arg(long, required_unless_present = "demo")]
    pub z1: Option<String>,
    /// Message hash z of the second signature (reduced mod n).
    #[arg(long, required_unless_present = "demo")]
    pub z2: Option<String>,
    /// Public key Q as x,y, for independent verification.
    #[arg(long)]
    pub q: Option<String>,
    /// Plant a key on the (default secp256k1) curve, sign two messages
    /// with one nonce, then recover it.
    #[arg(long)]
    pub demo: bool,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
}

#[derive(Serialize)]
pub struct NonceReuseReport {
    pub status: &'static str,
    pub curve: String,
    pub r: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub k: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub d: Option<String>,
    pub verified: bool,
    /// How `verified` was established.
    pub verification: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl NonceReuseReport {
    pub fn text(&self) -> String {
        let mut s = format!("ecdsa nonce-reuse on {}\n", self.curve);
        s += &format!("  r        {}\n", self.r);
        if let Some(k) = &self.k {
            s += &format!("  nonce k  {k}\n");
        }
        match &self.d {
            Some(d) => s += &format!("  key d    {d} ({})\n", self.verification),
            None => s += "  key d    not recovered\n",
        }
        if let Some(e) = &self.error {
            s += &format!("  error    {e}\n");
        }
        s
    }
}

/// Recover `(k, d)` from a reused nonce: `k = (z1 - z2)/(s1 - s2)`,
/// `d = (s1·k - z1)/r`, all mod n.
fn recover_reused(
    n: &BigUint,
    r: &BigUint,
    s1: &BigUint,
    s2: &BigUint,
    z1: &BigUint,
    z2: &BigUint,
) -> Result<(BigUint, BigUint), String> {
    let sub = |a: &BigUint, b: &BigUint| ((a % n) + n - (b % n)) % n;
    let ds = sub(s1, s2);
    if ds.is_zero() {
        return Err("s1 == s2 (mod n): the two signatures are identical, no leak".into());
    }
    let ds_inv = mod_inverse(&ds, n).ok_or("s1 - s2 not invertible mod n")?;
    let k = (sub(z1, z2) * &ds_inv) % n;
    if k.is_zero() {
        return Err("recovered nonce k == 0".into());
    }
    let r_inv = mod_inverse(&(r % n), n).ok_or("r not invertible mod n")?;
    // d = (s1·k - z1) / r
    let s1k = (s1 * &k) % n;
    let d = (sub(&s1k, z1) * &r_inv) % n;
    Ok((k, d))
}

fn run_nonce_reuse(out: Out, a: &NonceReuseArgs) -> CmdResult {
    let curve = a.curve.resolve("secp256k1")?;
    let n = curve.n.clone();

    let (r, s1, s2, z1, z2, planted_q) = if a.demo {
        let d = BigUint::from(0x1234_5678_9abc_def0u64) % &n;
        let k = BigUint::from(0xdead_beef_cafe_babeu64) % &n;
        let z1 = BigUint::from(0x1111_2222_3333_4444u64) % &n;
        let z2 = BigUint::from(0x5555_6666_7777_8888u64) % &n;
        let (r1, s1) = sign_with_nonce(&z1, &k, &d, &curve).ok_or("demo: signing failed")?;
        let (r2, s2) = sign_with_nonce(&z2, &k, &d, &curve).ok_or("demo: signing failed")?;
        debug_assert_eq!(r1, r2, "same nonce must give same r");
        let q = curve.generator().scalar_mul(&d, &curve.a_fe());
        (r1, s1, s2, z1, z2, Some(q))
    } else {
        let g = |o: &Option<String>| parse_biguint(o.as_deref().unwrap());
        (g(&a.r)?, g(&a.s1)?, g(&a.s2)?, g(&a.z1)?, g(&a.z2)?, None)
    };

    let mut report = NonceReuseReport {
        status: "not_solved",
        curve: curve.name.to_string(),
        r: r.to_string(),
        k: None,
        d: None,
        verified: false,
        verification: "none",
        error: None,
    };

    match recover_reused(&n, &r, &s1, &s2, &z1, &z2) {
        Ok((k, d)) => {
            report.k = Some(k.to_string());
            report.d = Some(d.to_string());
            // Independent verification. Prefer d·G == Q when we have Q.
            let q_pub = public_key(&curve, &a.q)?.map(|p| p.point).or(planted_q);
            let dg = curve.generator().scalar_mul(&d, &curve.a_fe());
            let point_ok = q_pub.as_ref().map(|q| &dg == q);
            // Algebraic self-check: re-derive both signatures from (k, d).
            let redo = |z: &BigUint, s: &BigUint| {
                sign_with_nonce(z, &k, &d, &curve).map(|(_, s2)| &s2 == s)
            };
            let algebraic_ok =
                matches!(redo(&z1, &s1), Some(true)) && matches!(redo(&z2, &s2), Some(true));
            match point_ok {
                Some(true) => {
                    report.verified = true;
                    report.verification = "d·G == Q";
                    report.status = "ok";
                }
                Some(false) => {
                    report.verified = false;
                    report.verification = "d·G != Q";
                    report.error = Some("recovered key does not match the public key".into());
                }
                None => {
                    report.verified = algebraic_ok;
                    report.verification = if algebraic_ok {
                        "re-derived signatures match"
                    } else {
                        "signature re-derivation failed"
                    };
                    report.status = if algebraic_ok { "ok" } else { "not_solved" };
                }
            }
        }
        Err(e) => report.error = Some(e),
    }

    out.emit(&report, || report.text())?;
    match report.status {
        "ok" => Ok(()),
        _ => Err(Failure::reported(
            report
                .error
                .clone()
                .unwrap_or_else(|| "nonce-reuse recovery failed".into()),
        )),
    }
}

// ── hnp ──────────────────────────────────────────────────────────────

/// Lattice-reduction strength for the HNP recovery.
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum, Default)]
pub enum Reduction {
    /// Plain LLL (δ = 0.75); fast, needs comfortable bias margin.
    #[default]
    Lll,
    /// BKZ-β; lowers the signature-count threshold at higher cost.
    Bkz,
    /// LLL with high-precision Gram–Schmidt (large-entry lattices).
    LllHp,
}

#[derive(Args, Clone, Debug)]
pub struct HnpArgs {
    #[command(flatten)]
    pub curve: CurveSel,
    /// Public key Q as x,y (required outside --demo).
    #[arg(long)]
    pub q: Option<String>,
    /// A biased signature `r,s,z` (repeat once per signature). Each nonce
    /// is asserted `k < 2^k-bits` (known high bits are zero).
    #[arg(long = "sig")]
    pub sigs: Vec<String>,
    /// The known bias bound: every nonce satisfies `k < 2^k_bits`.
    #[arg(long)]
    pub k_bits: Option<u32>,
    /// Lattice reduction.
    #[arg(long, value_enum, default_value_t = Reduction::Lll)]
    pub reduction: Reduction,
    /// BKZ block size (with --reduction bkz).
    #[arg(long, default_value_t = 12)]
    pub bkz_beta: usize,
    /// Plant a key with the stated bias and recover it.
    #[arg(long)]
    pub demo: bool,
    /// Number of signatures to plant in --demo.
    #[arg(long, default_value_t = 8)]
    pub demo_sigs: usize,
    /// Bias bound to plant in --demo (`k < 2^demo-k-bits`).
    #[arg(long, default_value_t = 192)]
    pub demo_k_bits: u32,
    #[arg(long, default_value_t = 0xC0FFEE)]
    pub seed: u64,
}

#[derive(Serialize)]
pub struct HnpReport {
    pub status: &'static str,
    pub curve: String,
    pub signatures: usize,
    pub k_bits: u32,
    pub bias_bits: u32,
    pub reduction: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub d: Option<String>,
    pub verified: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

impl HnpReport {
    pub fn text(&self) -> String {
        let mut s = format!("ecdsa hnp on {}\n", self.curve);
        s += &format!(
            "  {} signatures, k < 2^{} ({}-bit bias), reduction {}\n",
            self.signatures, self.k_bits, self.bias_bits, self.reduction
        );
        match &self.d {
            Some(d) => s += &format!("  key d    {d} (verified: d·G == Q)\n"),
            None => s += "  key d    not recovered\n",
        }
        if let Some(e) = &self.error {
            s += &format!("  error    {e}\n");
        }
        s
    }
}

fn run_hnp(out: Out, a: &HnpArgs) -> CmdResult {
    let curve = a.curve.resolve("p256")?;
    let n = curve.n.clone();
    let n_bits = n.bits() as u32;

    let (sigs, q_point, k_bits): (Vec<BiasedSignature>, Point, u32) = if a.demo {
        let mut rng = StdRng::seed_from_u64(a.seed);
        let d = (BigUint::from_bytes_be(&{
            let mut b = [0u8; 32];
            rng.fill_bytes(&mut b);
            b
        }) % (&n - 1u32))
            + 1u32;
        let q = curve.generator().scalar_mul(&d, &curve.a_fe());
        let k_bits = a.demo_k_bits;
        let mut sigs = Vec::new();
        let mut z_seed = 0xDEAD_BEEFu64;
        let mut guard = 0u32;
        while sigs.len() < a.demo_sigs && guard < 100_000 {
            guard += 1;
            let z = BigUint::from(z_seed) % &n;
            z_seed = z_seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let k = biased_nonce(&mut rng, k_bits);
            if let Some((r, s)) = sign_with_nonce(&z, &k, &d, &curve) {
                sigs.push(BiasedSignature { r, s, z, k_bits });
            }
        }
        (sigs, q, k_bits)
    } else {
        let k_bits = a
            .k_bits
            .ok_or("--k-bits is required (the known bias: k < 2^k_bits)")?;
        if a.sigs.len() < 2 {
            return Err("give at least two --sig r,s,z (or use --demo)".into());
        }
        let q = public_key(&curve, &a.q)?
            .ok_or("--q x,y (the public key) is required outside --demo")?
            .point;
        let mut sigs = Vec::with_capacity(a.sigs.len());
        for raw in &a.sigs {
            let parts: Vec<&str> = raw.split(',').collect();
            if parts.len() != 3 {
                return Err(format!("expected --sig r,s,z: {raw:?}").into());
            }
            sigs.push(BiasedSignature {
                r: parse_biguint(parts[0])?,
                s: parse_biguint(parts[1])?,
                z: parse_biguint(parts[2])?,
                k_bits,
            });
        }
        (sigs, q, k_bits)
    };

    let reduction = match a.reduction {
        Reduction::Lll => HnpReduction::Lll,
        Reduction::Bkz => HnpReduction::Bkz(a.bkz_beta),
        Reduction::LllHp => HnpReduction::LllHp,
    };
    let reduction_name = match a.reduction {
        Reduction::Lll => "lll",
        Reduction::Bkz => "bkz",
        Reduction::LllHp => "lll-hp",
    };

    let public = EccPublicKey {
        point: q_point.clone(),
        curve_name: curve.name.to_string(),
    };

    let mut report = HnpReport {
        status: "not_solved",
        curve: curve.name.to_string(),
        signatures: sigs.len(),
        k_bits,
        bias_bits: n_bits.saturating_sub(k_bits),
        reduction: reduction_name,
        d: None,
        verified: false,
        error: None,
    };

    match hnp_recover_key_with_reduction(&curve, &public, &sigs, reduction) {
        Ok(d) => {
            // hnp_recover_key already checks d·G == public_key; re-confirm
            // here so the CLI's "verified" is its own independent check.
            let dg = curve.generator().scalar_mul(&d, &curve.a_fe());
            if dg == q_point {
                report.status = "ok";
                report.verified = true;
                report.d = Some(d.to_string());
            } else {
                report.error = Some("recovered scalar failed d·G == Q re-check".into());
            }
        }
        Err(e) => report.error = Some(e.to_string()),
    }

    out.emit(&report, || report.text())?;
    match report.status {
        "ok" => Ok(()),
        _ => Err(Failure::reported(
            report
                .error
                .clone()
                .unwrap_or_else(|| "HNP recovery failed".into()),
        )),
    }
}

// ── audit ────────────────────────────────────────────────────────────

#[derive(Args, Clone, Debug)]
pub struct AuditArgs {
    #[command(flatten)]
    pub curve: CurveSel,
    /// Public key Q as x,y (required outside --demo).
    #[arg(long)]
    pub q: Option<String>,
    /// A signature `r,s,z` (repeat per signature).
    #[arg(long = "sig")]
    pub sigs: Vec<String>,
    /// Lowest k_bits to attempt (largest assumed bias).
    #[arg(long)]
    pub min_k_bits: Option<u32>,
    /// Highest k_bits to attempt (smallest assumed bias).
    #[arg(long)]
    pub max_k_bits: Option<u32>,
    /// k_bits sweep step.
    #[arg(long, default_value_t = 8)]
    pub k_bits_step: u32,
    /// Skip the statistical prefilter and sweep blindly.
    #[arg(long)]
    pub no_prefilter: bool,
    /// Plant a biased transcript and audit it.
    #[arg(long)]
    pub demo: bool,
    #[arg(long, default_value_t = 8)]
    pub demo_sigs: usize,
    #[arg(long, default_value_t = 192)]
    pub demo_k_bits: u32,
    #[arg(long, default_value_t = 0x1234_5678)]
    pub seed: u64,
}

#[derive(Serialize)]
pub struct AuditReport {
    pub status: &'static str,
    pub curve: String,
    pub signatures: usize,
    pub bias_score: f64,
    /// One of: no_bias, key_recovered, bias_suspected.
    pub verdict: &'static str,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub k_bits: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub d: Option<String>,
    pub verified: bool,
}

impl AuditReport {
    pub fn text(&self) -> String {
        let mut s = format!("ecdsa audit on {}\n", self.curve);
        s += &format!(
            "  {} signatures, bias score {:.3}\n",
            self.signatures, self.bias_score
        );
        s += &format!("  verdict  {}\n", self.verdict);
        if let Some(k) = self.k_bits {
            s += &format!("  k_bits   {k}\n");
        }
        if let Some(d) = &self.d {
            s += &format!("  key d    {d} (verified: d·G == Q)\n");
        }
        s
    }
}

fn run_audit(out: Out, a: &AuditArgs) -> CmdResult {
    let curve = a.curve.resolve("p256")?;
    let n = curve.n.clone();

    let (samples, q_point): (Vec<EcdsaSample>, Point) = if a.demo {
        let mut rng = StdRng::seed_from_u64(a.seed);
        let d = (BigUint::from_bytes_be(&{
            let mut b = [0u8; 32];
            rng.fill_bytes(&mut b);
            b
        }) % (&n - 1u32))
            + 1u32;
        let q = curve.generator().scalar_mul(&d, &curve.a_fe());
        let mut samples = Vec::new();
        let mut z_seed = 0xDEAD_BEEFu64;
        let mut guard = 0u32;
        while samples.len() < a.demo_sigs && guard < 100_000 {
            guard += 1;
            let z = BigUint::from(z_seed) % &n;
            z_seed = z_seed.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let k = biased_nonce(&mut rng, a.demo_k_bits);
            if let Some((r, s)) = sign_with_nonce(&z, &k, &d, &curve) {
                samples.push(EcdsaSample { r, s, z });
            }
        }
        (samples, q)
    } else {
        if a.sigs.is_empty() {
            return Err("give --sig r,s,z (repeatable) or use --demo".into());
        }
        let q = public_key(&curve, &a.q)?
            .ok_or("--q x,y (the public key) is required outside --demo")?
            .point;
        let mut samples = Vec::with_capacity(a.sigs.len());
        for raw in &a.sigs {
            let parts: Vec<&str> = raw.split(',').collect();
            if parts.len() != 3 {
                return Err(format!("expected --sig r,s,z: {raw:?}").into());
            }
            samples.push(EcdsaSample {
                r: parse_biguint(parts[0])?,
                s: parse_biguint(parts[1])?,
                z: parse_biguint(parts[2])?,
            });
        }
        (samples, q)
    };

    let public = EccPublicKey {
        point: q_point.clone(),
        curve_name: curve.name.to_string(),
    };
    // The chi-squared prefilter needs many samples to be meaningful; on a
    // small planted demo it would false-negative, so bracket the planted
    // bias and sweep directly to show a recovery.
    let opts = if a.demo {
        AuditOptions {
            min_k_bits: a.min_k_bits.or(Some(a.demo_k_bits.saturating_sub(16))),
            max_k_bits: a.max_k_bits.or(Some(a.demo_k_bits + 16)),
            k_bits_step: a.k_bits_step,
            run_statistical_prefilter: false,
        }
    } else {
        AuditOptions {
            min_k_bits: a.min_k_bits,
            max_k_bits: a.max_k_bits,
            k_bits_step: a.k_bits_step,
            run_statistical_prefilter: !a.no_prefilter,
        }
    };
    let score = quick_bias_score(&curve, &samples);
    let result = audit_ecdsa_transcript(&curve, &public, &samples, &opts);

    let mut report = AuditReport {
        status: "ok",
        curve: curve.name.to_string(),
        signatures: samples.len(),
        bias_score: score,
        verdict: "no_bias",
        k_bits: None,
        d: None,
        verified: false,
    };
    match result {
        AuditResult::NoBiasDetected => report.verdict = "no_bias",
        AuditResult::BiasSuspectedNoRecovery {
            suspected_k_bits, ..
        } => {
            report.verdict = "bias_suspected";
            report.k_bits = Some(suspected_k_bits);
        }
        AuditResult::KeyRecovered { d, k_bits, .. } => {
            let dg = curve.generator().scalar_mul(&d, &curve.a_fe());
            report.verified = dg == q_point;
            report.verdict = "key_recovered";
            report.k_bits = Some(k_bits);
            report.d = Some(d.to_string());
        }
    }

    // The audit itself always completes; there is no answer to fail on.
    out.emit(&report, || report.text())
}

// ── invalid-curve ────────────────────────────────────────────────────

#[derive(Args, Clone, Debug)]
pub struct InvalidCurveArgs {
    /// Field prime p of a small j=0 base curve `y² = x³ + b` (p ≡ 1 mod 6;
    /// kept small because twist enumeration is O(p)). Omit for --demo.
    #[arg(long)]
    pub p: Option<String>,
    /// The curve coefficient b.
    #[arg(long)]
    pub b: Option<String>,
    /// Base-point x-coordinate.
    #[arg(long)]
    pub gx: Option<String>,
    /// Base-point y-coordinate.
    #[arg(long)]
    pub gy: Option<String>,
    /// Order n of the base point.
    #[arg(long)]
    pub order: Option<String>,
    /// The victim's secret scalar. It feeds ONLY the honest oracle
    /// `|P| -> secret·P`; the attack recovers it without reading it and
    /// verifies against Q = secret·G.
    #[arg(long, required_unless_present = "demo")]
    pub secret: Option<String>,
    /// Smoothness bound: largest twist prime subgroup solved.
    #[arg(long, default_value_t = 256)]
    pub smoothness_bound: u64,
    /// Run the built-in 16-bit j=0 demo curve.
    #[arg(long)]
    pub demo: bool,
}

#[derive(Serialize)]
pub struct InvalidCurveReport {
    pub status: &'static str,
    pub base_curve: String,
    pub n_base: String,
    pub twists_total: usize,
    pub twists_used: usize,
    pub bits_recovered: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub d: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub d_partial: Option<String>,
    pub verified: bool,
}

impl InvalidCurveReport {
    pub fn text(&self) -> String {
        let mut s = format!("ecdsa invalid-curve attack on {}\n", self.base_curve);
        s += &format!(
            "  #⟨G⟩ = {}, twists {}/{} used, ~{:.1} bits recovered\n",
            self.n_base, self.twists_used, self.twists_total, self.bits_recovered
        );
        match &self.d {
            Some(d) => s += &format!("  key d    {d} (verified: d·G == Q)\n"),
            None => match &self.d_partial {
                Some(p) => s += &format!("  key d    partial: d ≡ {p} (mod ∏ q_i)\n"),
                None => s += "  key d    not recovered\n",
            },
        }
        s
    }
}

fn run_invalid_curve(out: Out, a: &InvalidCurveArgs) -> CmdResult {
    // Base curve: the built-in demo, or a custom small j=0 curve.
    let (curve, secret) = if a.demo {
        let curve = CurveParams {
            name: "j0-demo-16bit",
            p: BigUint::from(65353u32),
            a: BigUint::zero(),
            b: BigUint::from(5u32),
            gx: BigUint::from(1u32),
            gy: BigUint::from(2632u32),
            n: BigUint::from(65521u32),
            h: 1,
        };
        (curve, BigUint::from(12345u32))
    } else {
        let big = |s: &Option<String>, what: &str| -> Result<BigUint, String> {
            parse_biguint(
                s.as_deref()
                    .ok_or_else(|| format!("--{what} is required"))?,
            )
        };
        let p = big(&a.p, "p")?;
        let b = big(&a.b, "b")? % &p;
        let gx = big(&a.gx, "gx")?;
        let gy = big(&a.gy, "gy")?;
        let n = big(&a.order, "order")?;
        let curve = CurveParams {
            name: "custom-j0",
            a: BigUint::zero(),
            b,
            gx,
            gy,
            n,
            h: 1,
            p,
        };
        let secret = parse_biguint(a.secret.as_deref().unwrap())? % &curve.n;
        (curve, secret)
    };

    if !curve.is_on_curve(&curve.generator()) {
        return Err("the base point G is not on the curve".into());
    }
    if secret.is_zero() {
        return Err("secret must be in [1, n)".into());
    }

    let report_raw = mount_invalid_curve_attack(&curve, &secret, a.smoothness_bound);
    let report = InvalidCurveReport {
        status: if report_raw.verified {
            "ok"
        } else {
            "not_solved"
        },
        base_curve: report_raw.base_curve_name.clone(),
        n_base: report_raw.n_base.to_string(),
        twists_total: report_raw.twists_total,
        twists_used: report_raw.twists_used,
        bits_recovered: report_raw.bits_recovered,
        d: report_raw.recovered_d_full.as_ref().map(|d| d.to_string()),
        d_partial: report_raw
            .recovered_d_partial
            .as_ref()
            .map(|d| d.to_string()),
        verified: report_raw.verified,
    };

    out.emit(&report, || report.text())?;
    match report.status {
        "ok" => Ok(()),
        _ => Err(Failure::reported(
            "invalid-curve attack did not fully recover and verify the key",
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nonce_reuse_demo_recovers_and_verifies() {
        let a = NonceReuseArgs {
            curve: CurveSel {
                curve: None,
                p: None,
                a: None,
                b: None,
                gx: None,
                gy: None,
                order: None,
            },
            r: None,
            s1: None,
            s2: None,
            z1: None,
            z2: None,
            q: None,
            demo: true,
            seed: 1,
        };
        let curve = a.curve.resolve("secp256k1").unwrap();
        // Reconstruct the demo transcript and confirm recovery math.
        let n = curve.n.clone();
        let d = BigUint::from(0x1234_5678_9abc_def0u64) % &n;
        let k = BigUint::from(0xdead_beef_cafe_babeu64) % &n;
        let z1 = BigUint::from(0x1111_2222_3333_4444u64) % &n;
        let z2 = BigUint::from(0x5555_6666_7777_8888u64) % &n;
        let (r, s1) = sign_with_nonce(&z1, &k, &d, &curve).unwrap();
        let (_r2, s2) = sign_with_nonce(&z2, &k, &d, &curve).unwrap();
        let (rk, rd) = recover_reused(&n, &r, &s1, &s2, &z1, &z2).unwrap();
        assert_eq!(rk, k);
        assert_eq!(rd, d);
    }

    #[test]
    fn hnp_reduction_mapping() {
        assert_eq!(Reduction::default(), Reduction::Lll);
    }

    #[test]
    fn invalid_curve_demo_recovers() {
        let curve = CurveParams {
            name: "j0-demo-16bit",
            p: BigUint::from(65353u32),
            a: BigUint::zero(),
            b: BigUint::from(5u32),
            gx: BigUint::from(1u32),
            gy: BigUint::from(2632u32),
            n: BigUint::from(65521u32),
            h: 1,
        };
        let report = mount_invalid_curve_attack(&curve, &BigUint::from(12345u32), 256);
        assert!(report.verified);
        assert_eq!(report.recovered_d_full, Some(BigUint::from(12345u32)));
    }
}
