//! `crax challenge`: the elliptic-curve challenge corpus in `challenges/ecc/`.
//!
//! `list` and `show` read the catalog and the records; `rho-job` exports a
//! collaborative Pollard-rho job; `solve` reads what a record says about its
//! curve (trace, embedding degree, endomorphism, subgroup order), picks the
//! cheapest attack that applies, runs it, and verifies the answer with an
//! independent scalar multiplication. On `check`-tier records the answer is
//! also compared with the stored discrete log.

use std::path::PathBuf;

use clap::{Args, Subcommand, ValueEnum};
use num_bigint::BigUint;
use num_traits::{One, ToPrimitive, Zero};
use serde::Serialize;
use serde_json::Value;

use super::output::{CmdResult, Failure, Out};
use crate::ecc::challenges::{
    default_corpus_root, load_record, prime_field_challenge, Catalog, PrimeFieldChallenge,
};
use crate::ecc::point::Point;

#[derive(Args, Clone, Debug)]
pub struct ChallengeArgs {
    /// Directory holding catalog.json, curves/ and inspect/.
    #[arg(long, global = true)]
    pub corpus: Option<PathBuf>,
    #[command(subcommand)]
    pub cmd: ChallengeCmd,
}

#[derive(Subcommand, Clone, Debug)]
pub enum ChallengeCmd {
    /// List the catalog, optionally filtered.
    List {
        #[arg(long)]
        family: Option<String>,
        #[arg(long)]
        tag: Option<String>,
        /// `check` (known answer stored) or `open`.
        #[arg(long)]
        tier: Option<String>,
        #[arg(long)]
        min_bits: Option<u64>,
        #[arg(long)]
        max_bits: Option<u64>,
    },
    /// Print one curve record.
    Show { id: String },
    /// Emit a collaborative Pollard-rho job (`crax rho-collab work --job`).
    RhoJob {
        id: String,
        #[arg(long, default_value_t = 1)]
        seed: u64,
    },
    /// Pick the cheapest applicable attack, run it and verify the answer.
    Solve(SolveArgs),
}

/// A forced method for `crax challenge solve`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Method {
    /// The cheapest method whose preconditions the curve meets.
    Auto,
    /// Pohlig-Hellman with rho in each prime subgroup (C library, p < 2^64).
    PohligHellman,
    /// Rho folded by the j = 0 / 1728 automorphisms (C library, p < 2^64).
    Glv,
    /// Plain rho with the negation map (C library, p < 2^64).
    Rho,
}

#[derive(Args, Clone, Debug)]
pub struct SolveArgs {
    /// Challenge id (see `crax challenge list`).
    pub id: String,
    #[arg(long, value_enum, default_value_t = Method::Auto)]
    pub method: Method,
    /// Refuse generic methods whose expected cost exceeds 2^this group
    /// operations, instead of starting a run that cannot finish.
    #[arg(long, default_value_t = 44)]
    pub max_log2_ops: u32,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    #[arg(long, default_value_t = 1)]
    pub threads: u32,
}

fn root(args: &ChallengeArgs) -> PathBuf {
    args.corpus.clone().unwrap_or_else(default_corpus_root)
}

pub fn run(out: Out, args: &ChallengeArgs) -> CmdResult {
    let root = root(args);
    match &args.cmd {
        ChallengeCmd::List {
            family,
            tag,
            tier,
            min_bits,
            max_bits,
        } => {
            let catalog = Catalog::load(&root)?;
            let rows: Vec<_> = catalog
                .curves
                .iter()
                .filter(|c| family.as_ref().is_none_or(|f| &c.family == f))
                .filter(|c| tag.as_ref().is_none_or(|t| c.tags.contains(t)))
                .filter(|c| tier.as_ref().is_none_or(|t| &c.tier == t))
                .filter(|c| min_bits.is_none_or(|m| c.cardinality_bits >= m))
                .filter(|c| max_bits.is_none_or(|m| c.cardinality_bits <= m))
                .collect();
            #[derive(Serialize)]
            struct Row<'a> {
                id: &'a str,
                family: &'a str,
                tier: &'a str,
                field_bits: u64,
                field_type: &'a str,
                tags: &'a [String],
            }
            let json: Vec<Row> = rows
                .iter()
                .map(|c| Row {
                    id: &c.id,
                    family: &c.family,
                    tier: &c.tier,
                    field_bits: c.cardinality_bits,
                    field_type: &c.field_type,
                    tags: &c.tags,
                })
                .collect();
            out.emit(&json, || {
                let mut s = format!(
                    "{:<34} {:<24} {:<6} {:>5}  tags\n",
                    "id", "family", "tier", "bits"
                );
                for c in &rows {
                    s += &format!(
                        "{:<34} {:<24} {:<6} {:>5}  {}\n",
                        c.id,
                        c.family,
                        c.tier,
                        c.cardinality_bits,
                        c.tags.join(",")
                    );
                }
                s + &format!("{} of {} curves\n", rows.len(), catalog.curves.len())
            })
        }
        ChallengeCmd::Show { id } => {
            let rec = load_record(&root, id)?;
            out.emit(&rec, || {
                serde_json::to_string_pretty(&rec).unwrap_or_default()
            })
        }
        ChallengeCmd::RhoJob { id, seed } => {
            let rec = load_record(&root, id)?;
            let ch = prime_field_challenge(&rec)?;
            let job = ch.rho_job(*seed)?;
            let s = serde_json::to_string_pretty(&job).map_err(|e| e.to_string())?;
            println!("{s}");
            Ok(())
        }
        ChallengeCmd::Solve(a) => solve(out, &root, a),
    }
}

/// What `solve` found out about the curve before choosing.
#[derive(Clone, Debug, Serialize)]
pub struct Analysis {
    pub field_bits: u64,
    pub subgroup_bits: u64,
    pub subgroup_factors: Vec<String>,
    pub largest_prime_bits: u64,
    pub anomalous: bool,
    pub embedding_degree: Option<u64>,
    pub endomorphism: Option<String>,
    pub suggested_solvers: Vec<String>,
}

#[derive(Clone, Debug, Serialize)]
pub struct SolveReport {
    pub status: &'static str,
    pub id: String,
    pub tier: String,
    pub method: String,
    pub analysis: Analysis,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub x: Option<String>,
    /// `[x] G == target`, checked with the arbitrary-precision group law.
    pub verified: bool,
    /// `check` tier: whether `x` equals the stored discrete log.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub matches_known_log: Option<bool>,
    pub seconds: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub group_ops: Option<u64>,
    pub notes: Vec<String>,
}

impl SolveReport {
    fn text(&self) -> String {
        let a = &self.analysis;
        let mut s = format!(
            "{} ({}): {}\n  curve    {}-bit field, {}-bit subgroup = {}\n",
            self.id,
            self.tier,
            match (&self.x, self.verified) {
                (Some(x), true) => format!("x = {x} (verified: [x]G = target)"),
                (Some(x), false) => format!("x = {x} (NOT VERIFIED)"),
                (None, _) => "not solved".to_string(),
            },
            a.field_bits,
            a.subgroup_bits,
            a.subgroup_factors.join(" * ")
        );
        s += &format!(
            "  checks   anomalous={} embedding_degree={} endomorphism={}\n",
            a.anomalous,
            a.embedding_degree
                .map_or_else(|| "large".to_string(), |k| k.to_string()),
            a.endomorphism.as_deref().unwrap_or("none")
        );
        s += &format!("  method   {} ({:.3} s", self.method, self.seconds);
        if let Some(ops) = self.group_ops {
            s += &format!(", {ops} group ops");
        }
        s += ")\n";
        if let Some(m) = self.matches_known_log {
            s += &format!(
                "  known    {}\n",
                if m {
                    "matches the stored log"
                } else {
                    "DIFFERS from the stored log"
                }
            );
        }
        for n in &self.notes {
            s += &format!("  note     {n}\n");
        }
        s
    }
}

fn bits(n: &BigUint) -> u64 {
    n.bits()
}

/// Smallest `k <= bound` with `n | p^k - 1`.
fn embedding_degree(p: &BigUint, n: &BigUint, bound: u64) -> Option<u64> {
    if n.is_zero() || n.is_one() {
        return None;
    }
    let pm = p % n;
    let mut acc = pm.clone();
    for k in 1..=bound {
        if acc.is_one() {
            return Some(k);
        }
        acc = (&acc * &pm) % n;
    }
    None
}

/// Trial division, Miller-Rabin and Pollard-Brent rho: enough for the
/// corpus's subgroup orders (a large prime is recognised, not trial-divided).
pub fn factor(n: &BigUint) -> Vec<(BigUint, u32)> {
    use crate::asymmetric::rsa::is_prime;
    let mut out: Vec<(BigUint, u32)> = Vec::new();
    let push =
        |q: BigUint, out: &mut Vec<(BigUint, u32)>| match out.iter_mut().find(|(p, _)| *p == q) {
            Some((_, e)) => *e += 1,
            None => out.push((q, 1)),
        };
    let mut m = n.clone();
    if m.is_zero() {
        return out;
    }
    for p in 2u32..10_000 {
        let bp = BigUint::from(p);
        while (&m % &bp).is_zero() {
            m /= &bp;
            push(bp.clone(), &mut out);
        }
    }
    let mut stack = vec![m];
    while let Some(c) = stack.pop() {
        if c.is_one() {
            continue;
        }
        if is_prime(&c) {
            push(c, &mut out);
            continue;
        }
        let d = brent(&c);
        stack.push(&c / &d);
        stack.push(d);
    }
    out.sort();
    out
}

/// A non-trivial factor of the odd composite `n` (Pollard-Brent rho).
fn brent(n: &BigUint) -> BigUint {
    use num_integer::Integer;
    for c in 1u32.. {
        let c = BigUint::from(c);
        let f = |x: &BigUint| (x * x + &c) % n;
        let (mut y, mut r, mut q) = (BigUint::from(2u32), 1u64, BigUint::one());
        let (mut x, mut ys, mut g);
        loop {
            x = y.clone();
            for _ in 0..r {
                y = f(&y);
            }
            let mut k = 0;
            loop {
                ys = y.clone();
                for _ in 0..r.saturating_sub(k).min(128) {
                    y = f(&y);
                    let diff = if x > y { &x - &y } else { &y - &x };
                    q = (q * diff) % n;
                }
                g = q.gcd(n);
                k += 128;
                if k >= r || !g.is_one() {
                    break;
                }
            }
            r *= 2;
            if !g.is_one() {
                break;
            }
        }
        if &g == n {
            loop {
                ys = f(&ys);
                let diff = if x > ys { &x - &ys } else { &ys - &x };
                g = diff.gcd(n);
                if !g.is_one() {
                    break;
                }
            }
        }
        if &g != n {
            return g;
        }
    }
    unreachable!("a composite always has a rho factor for some c")
}

fn analyse(rec: &Value, ch: &PrimeFieldChallenge) -> Analysis {
    let factors = factor(&ch.subgroup_order);
    let largest = factors
        .iter()
        .map(|(q, _)| q.clone())
        .max()
        .unwrap_or_default();
    Analysis {
        field_bits: bits(&ch.p),
        subgroup_bits: bits(&ch.subgroup_order),
        subgroup_factors: factors
            .iter()
            .map(|(q, e)| {
                if *e > 1 {
                    format!("{q}^{e}")
                } else {
                    q.to_string()
                }
            })
            .collect(),
        largest_prime_bits: bits(&largest),
        anomalous: ch.subgroup_order == ch.p,
        embedding_degree: embedding_degree(&ch.p, &largest, 24),
        endomorphism: rec["endomorphism"]["kind"].as_str().map(str::to_string),
        suggested_solvers: rec["suggested_solvers"]
            .as_array()
            .map(|a| {
                a.iter()
                    .filter_map(|s| s.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default(),
    }
}

fn verify(ch: &PrimeFieldChallenge, x: &BigUint) -> bool {
    let gx = ch.generator.scalar_mul(x, &ch.a_fe());
    gx == ch.target
}

fn solve(out: Out, root: &std::path::Path, a: &SolveArgs) -> CmdResult {
    let rec = load_record(root, &a.id)?;
    let field_type = rec["field"]["type"].as_str().unwrap_or("");
    if field_type != "prime" {
        return Err(format!(
            "{}: automatic solving covers prime-field curves; this is a {field_type} curve \
             (see `crax ic` for binary and extension-field index calculus)",
            a.id
        )
        .into());
    }
    let ch = prime_field_challenge(&rec).map_err(|e| {
        format!(
            "{}: {e}; automatic solving covers short-Weierstrass curves over F_p, p > 3",
            a.id
        )
    })?;
    let analysis = analyse(&rec, &ch);
    let tier = rec["tier"].as_str().unwrap_or("").to_string();
    let t0 = std::time::Instant::now();
    let mut notes = Vec::new();

    let small = ch.p.bits() <= 64 && ch.subgroup_order.bits() <= 64;
    let method = match a.method {
        Method::Auto if small && analysis.endomorphism.as_deref().is_some_and(is_glv) => {
            if ch.subgroup_order.bits() >= 2 && analysis.subgroup_factors.len() == 1 {
                Method::Glv
            } else {
                Method::PohligHellman
            }
        }
        Method::Auto => Method::PohligHellman,
        m => m,
    };
    // Generic methods cost about sqrt(largest prime factor) group operations.
    let log2_cost = analysis.largest_prime_bits.div_ceil(2);
    if log2_cost > u64::from(a.max_log2_ops) {
        return Err(format!(
            "{}: the largest prime factor of the subgroup order has {} bits, so a generic \
             method needs about 2^{log2_cost} group operations (limit 2^{}; raise it with \
             --max-log2-ops). Structural checks: anomalous={}, embedding degree={:?}.",
            a.id,
            analysis.largest_prime_bits,
            a.max_log2_ops,
            analysis.anomalous,
            analysis.embedding_degree
        )
        .into());
    }
    if !small {
        return Err(format!(
            "{}: {}-bit field; the generic solvers here need p < 2^64",
            a.id, analysis.field_bits
        )
        .into());
    }
    let (x, ops) = solve_small(&ch, method, a.seed, a.threads)?;
    let verified = verify(&ch, &x);
    // The stored log is unique only modulo ord(G), which can be a proper
    // divisor of the recorded subgroup order: compare the points.
    let matches_known_log = ch.known_log.as_ref().map(|k| {
        let a = ch.a_fe();
        ch.generator.scalar_mul(k, &a) == ch.generator.scalar_mul(&x, &a)
    });
    if tier == "open" {
        notes.push("open tier: no stored answer; the scalar multiplication is the check".into());
    }
    let report = SolveReport {
        status: if verified { "ok" } else { "unverified" },
        id: a.id.clone(),
        tier,
        method: format!("{method:?}"),
        analysis,
        x: Some(x.to_string()),
        verified,
        matches_known_log,
        seconds: t0.elapsed().as_secs_f64(),
        group_ops: Some(ops),
        notes,
    };
    out.emit(&report, || report.text())?;
    match (verified, matches_known_log) {
        (true, Some(false)) => Err(Failure::reported(
            "verified answer differs from the stored log",
        )),
        (true, _) => Ok(()),
        (false, _) => Err(Failure::reported(
            "the answer does not satisfy [x]G = target",
        )),
    }
}

fn is_glv(kind: &str) -> bool {
    kind.contains("j0") || kind.contains("j1728") || kind.contains("glv")
}

fn solve_small(
    ch: &PrimeFieldChallenge,
    method: Method,
    seed: u64,
    threads: u32,
) -> Result<(BigUint, u64), String> {
    let u = |v: &BigUint| v.to_u64().ok_or("value exceeds 64 bits".to_string());
    let (p, a, b, n) = (u(&ch.p)?, u(&ch.a)?, u(&ch.b)?, u(&ch.subgroup_order)?);
    let pt = |q: &Point| -> Result<libca::Elem, String> {
        match q {
            Point::Infinity => Ok(libca::Elem::ec_infinity()),
            Point::Affine { x, y } => Ok(libca::Elem::ec(u(&x.value)?, u(&y.value)?)),
        }
    };
    let group = libca::Group::ec(p, a, b, n).map_err(|e| format!("curve: {e}"))?;
    let (g, h) = (pt(&ch.generator)?, pt(&ch.target)?);
    let opts = libca::Options {
        seed,
        threads: threads.max(1),
        ..libca::Options::default()
    };
    let (x, st) = match method {
        Method::Glv => group
            .curve_solve(&g, &h, seed)
            .map(|(x, _, st)| (x, st))
            .map_err(|e| format!("glv: {e}"))?,
        Method::Rho => group.rho(&g, &h, &opts).map_err(|e| format!("rho: {e}"))?,
        Method::PohligHellman | Method::Auto => group
            .dlog(&g, &h, &opts)
            .map_err(|e| format!("pohlig-hellman: {e}"))?,
    };
    Ok((BigUint::from(x), st.group_ops))
}
