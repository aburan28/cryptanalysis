//! `crax ecdlp`: discrete logarithms on prime-field curves of any size,
//! by the structural attacks of [`crate::cryptanalysis::weak_curves`].
//!
//! The curve is analysed first — singular? anomalous (`#E = p`)? small
//! embedding degree? smooth order? — and the cheapest attack whose
//! preconditions hold is run: the singular-cubic map, Smart's p-adic lift,
//! Pohlig-Hellman with BSGS / rho in each prime subgroup, or (on request)
//! the MOV / Frey-Rück transfer to `F_{p^k}^*` with a real Tate pairing.
//! Every recovered scalar is checked by scalar multiplication. A curve
//! with none of these weaknesses is reported as such, with each check's
//! reason, rather than started on a generic walk that cannot finish.

use clap::{Args, ValueEnum};
use num_bigint::BigUint;
use serde::Serialize;

use super::output::{parse_biguint, parse_pair, CmdResult, Failure, Out};
use crate::cryptanalysis::weak_curves::{
    self, AttackOptions, AttackOutcome, Method as WeakMethod, WeakCurveReport,
};
use crate::ecc::curve::CurveParams;
use crate::ecc::field::FieldElement;
use crate::ecc::point::Point;

/// A method to force instead of the recommendation.
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum)]
pub enum Method {
    /// The cheapest applicable attack.
    Auto,
    /// Singular cubic: map to (F_p, +), F_p^* or the norm-one torus.
    Singular,
    /// Smart's attack on an anomalous curve (#E = p).
    Smart,
    /// Pohlig-Hellman with BSGS / rho per prime subgroup.
    PohligHellman,
    /// MOV / Frey-Rück transfer to F_{p^k}^* (generic DLP there).
    Mov,
}

impl Method {
    fn weak(self) -> Option<WeakMethod> {
        match self {
            Method::Auto => None,
            Method::Singular => Some(WeakMethod::Singular),
            Method::Smart => Some(WeakMethod::Smart),
            Method::PohligHellman => Some(WeakMethod::PohligHellman),
            Method::Mov => Some(WeakMethod::Mov),
        }
    }
}

#[derive(Args, Clone, Debug)]
pub struct EcdlpArgs {
    /// A named curve: secp256k1, p256, sm2 (sets p, a, b, G and n).
    #[arg(long, conflicts_with_all = ["p", "a", "b"])]
    pub curve: Option<String>,
    /// Field prime (decimal or 0x hex).
    #[arg(long)]
    pub p: Option<String>,
    #[arg(long)]
    pub a: Option<String>,
    #[arg(long)]
    pub b: Option<String>,
    /// Base point G as x,y (default: the named curve's generator).
    #[arg(long)]
    pub g: Option<String>,
    /// Order of G (default: the named curve's n).
    #[arg(long)]
    pub order: Option<String>,
    /// #E(F_p), for the embedding-degree check (default: order x cofactor
    /// when that is consistent).
    #[arg(long)]
    pub curve_order: Option<String>,
    /// Target Q as x,y.
    #[arg(long)]
    pub q: Option<String>,
    /// Plant Q = x·G instead of giving --q.
    #[arg(long, conflicts_with = "q")]
    pub x: Option<String>,
    #[arg(long, value_enum, default_value_t = Method::Auto)]
    pub method: Method,
    /// Only analyse the curve; run nothing.
    #[arg(long)]
    pub analyze_only: bool,
    /// Pohlig-Hellman is chosen only when it costs at most 2^this group
    /// operations.
    #[arg(long, default_value_t = 34.0)]
    pub max_log2_ops: f64,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
}

/// A problem on a prime-field curve.
pub struct Instance {
    pub curve: CurveParams,
    pub g: Point,
    pub q: Point,
    pub order: BigUint,
    pub planted: Option<BigUint>,
}

fn point(s: &str, p: &BigUint) -> Result<Point, String> {
    let (x, y) = parse_pair(s)?;
    Ok(Point::Affine {
        x: FieldElement::new(x, p.clone()),
        y: FieldElement::new(y, p.clone()),
    })
}

fn named(name: &str) -> Option<CurveParams> {
    match name.to_ascii_lowercase().replace('-', "").as_str() {
        "secp256k1" => Some(CurveParams::secp256k1()),
        "p256" | "secp256r1" | "prime256v1" => Some(CurveParams::p256()),
        "sm2" => Some(CurveParams::sm2()),
        _ => None,
    }
}

impl EcdlpArgs {
    pub fn instance(&self) -> Result<Instance, String> {
        let big = |s: &Option<String>| s.as_deref().map(parse_biguint).transpose();
        let mut curve = match &self.curve {
            Some(n) => named(n).ok_or_else(|| {
                format!("unknown curve {n:?}; known: secp256k1, p256, sm2 (or give --p --a --b)")
            })?,
            None => {
                let p = big(&self.p)?.ok_or("--p (or --curve) is required")?;
                CurveParams {
                    name: "custom",
                    a: big(&self.a)?.unwrap_or_default() % &p,
                    b: big(&self.b)?.ok_or("--b is required")? % &p,
                    gx: BigUint::default(),
                    gy: BigUint::default(),
                    n: BigUint::default(),
                    h: 1,
                    p,
                }
            }
        };
        let g = match &self.g {
            Some(s) => point(s, &curve.p)?,
            None if self.curve.is_some() => curve.generator(),
            None => return Err("--g is required for a custom curve".into()),
        };
        if !curve.is_on_curve(&g) {
            return Err("G is not on the curve".into());
        }
        let order = match big(&self.order)? {
            Some(n) => n,
            None if self.curve.is_some() => curve.n.clone(),
            None => return Err("--order (the order of G) is required for a custom curve".into()),
        };
        if let Point::Affine { x, y } = &g {
            curve.gx = x.value.clone();
            curve.gy = y.value.clone();
        }
        curve.n = order.clone();
        let planted = big(&self.x)?;
        let q = match (&self.q, &planted) {
            (Some(s), _) => point(s, &curve.p)?,
            (None, Some(x)) => g.scalar_mul(x, &curve.a_fe()),
            (None, None) => return Err("give --q, or --x to plant a target".into()),
        };
        if !curve.is_on_curve(&q) {
            return Err("Q is not on the curve".into());
        }
        Ok(Instance {
            curve,
            g,
            q,
            order,
            planted,
        })
    }
}

/// What `crax ecdlp` prints.
#[derive(Serialize)]
pub struct EcdlpReport {
    pub status: &'static str,
    pub analysis: WeakCurveReport,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub method: Option<WeakMethod>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub x: Option<String>,
    pub verified: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub matches_planted: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub attack_ms: Option<f64>,
}

impl EcdlpReport {
    pub fn text(&self) -> String {
        let a = &self.analysis;
        let mut s = format!(
            "ecdlp on a {}-bit prime field: {}\n",
            a.p_bits,
            match (&self.x, self.verified) {
                (Some(x), true) => format!("x = {x} (verified: [x]G = Q)"),
                (Some(x), false) => format!("x = {x} (NOT VERIFIED)"),
                (None, _) => "not solved".to_string(),
            }
        );
        for p in &a.input_problems {
            s += &format!("  input    {p}\n");
        }
        for c in &a.checks {
            s += &format!(
                "  {:<14} {:<3} {}{}\n",
                format!("{:?}", c.method),
                if c.applicable { "yes" } else { "no" },
                c.explanation,
                c.estimated_log2_ops
                    .map_or_else(String::new, |l| format!(" (~2^{l:.1} ops)"))
            );
        }
        if let Some(m) = self.method {
            s += &format!(
                "  method   {m:?} ({:.1} ms)\n",
                self.attack_ms.unwrap_or_default()
            );
        }
        if let Some(m) = self.matches_planted {
            s += &format!("  planted  {}\n", if m { "recovered" } else { "DIFFERENT" });
        }
        if let Some(e) = &self.error {
            s += &format!("  result   {e}\n");
        }
        s
    }
}

/// Analyse, then (unless `analyze_only`) attack.
pub fn solve(inst: &Instance, a: &EcdlpArgs, curve_order: Option<BigUint>) -> EcdlpReport {
    let mut opts = AttackOptions {
        force: a.method.weak(),
        curve_order,
        max_log2_ops: a.max_log2_ops,
        ..AttackOptions::default()
    };
    opts.solver.seed = a.seed;
    let analysis = weak_curves::analyze_with(&inst.curve, &inst.g, &inst.q, &inst.order, &opts);
    if a.analyze_only {
        return EcdlpReport {
            status: "analysed",
            analysis,
            method: None,
            x: None,
            verified: false,
            matches_planted: None,
            error: None,
            attack_ms: None,
        };
    }
    match weak_curves::attack_with(&inst.curve, &inst.g, &inst.q, &inst.order, &opts) {
        Ok(AttackOutcome {
            method,
            scalar,
            verified,
            report,
            attack_ms,
            ..
        }) => {
            let af = inst.curve.a_fe();
            EcdlpReport {
                status: if verified { "ok" } else { "unverified" },
                analysis: report,
                method: Some(method),
                matches_planted: inst
                    .planted
                    .as_ref()
                    .map(|t| inst.g.scalar_mul(t, &af) == inst.g.scalar_mul(&scalar, &af)),
                x: Some(scalar.to_string()),
                verified,
                error: None,
                attack_ms: Some(attack_ms),
            }
        }
        Err(e) => EcdlpReport {
            status: "not_solved",
            analysis,
            method: None,
            x: None,
            verified: false,
            matches_planted: None,
            error: Some(e.to_string()),
            attack_ms: None,
        },
    }
}

pub fn run(out: Out, a: &EcdlpArgs) -> CmdResult {
    let inst = a.instance()?;
    let curve_order = a.curve_order.as_deref().map(parse_biguint).transpose()?;
    let r = solve(&inst, a, curve_order);
    out.emit(&r, || r.text())?;
    match r.status {
        "ok" | "analysed" => Ok(()),
        _ => Err(Failure::reported(
            r.error
                .clone()
                .unwrap_or_else(|| "the answer did not verify".into()),
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args() -> EcdlpArgs {
        EcdlpArgs {
            curve: None,
            p: None,
            a: None,
            b: None,
            g: None,
            order: None,
            curve_order: None,
            q: None,
            x: None,
            method: Method::Auto,
            analyze_only: false,
            max_log2_ops: 34.0,
            seed: 1,
        }
    }

    #[test]
    fn p256_is_analysed_and_refused_with_reasons() {
        let mut a = args();
        a.curve = Some("p256".into());
        a.x = Some("12345".into());
        let inst = a.instance().unwrap();
        let r = solve(&inst, &a, None);
        assert_eq!(r.status, "not_solved");
        assert!(r.analysis.checks.iter().all(|c| !c.applicable));
    }

    #[test]
    fn singular_cusp_over_a_256_bit_prime() {
        // y^2 = x^3 over the P-256 prime: a cusp, mapped to (F_p, +).
        let p = CurveParams::p256().p;
        let mut a = args();
        a.p = Some(p.to_string());
        a.a = Some("0".into());
        a.b = Some("0".into());
        // (t^2, t^3) is on y^2 = x^3; take t = 5.
        a.g = Some("25,125".into());
        a.order = Some(p.to_string());
        a.x = Some("987654321987654321".into());
        let inst = a.instance().unwrap();
        let r = solve(&inst, &a, None);
        assert_eq!(r.status, "ok", "{:?}", r.error);
        assert_eq!(r.matches_planted, Some(true));
    }

    #[test]
    fn bad_input_is_refused_before_any_attack() {
        let mut a = args();
        a.curve = Some("secp256k1".into());
        a.q = Some("1,1".into());
        assert!(a.instance().is_err());
    }
}
