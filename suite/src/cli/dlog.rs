//! Generic discrete-logarithm solvers: `crax bsgs | rho | kangaroo | grumpy
//! | precomp | glv | pohlig-hellman | cheon | gpu-rho`.
//!
//! These run on the C library in the repository root (`libca`, through the
//! safe Rust bindings in `bindings/rust`): subgroups of `(Z/pZ)^*` and of
//! `E(F_p)` for short Weierstrass curves over primes below `2^64`, with
//! Montgomery arithmetic and batched affine curve walks. That is where the
//! measured solver constants in `docs/BENCHMARKS.md` come from.
//!
//! Every answer is checked by one independent exponentiation / scalar
//! multiplication before it is reported (`"verified": true`). A problem can
//! be given completely (`--g`, `--h`) or generated from a known secret
//! (`--x`), in which case the report also says whether the solver found the
//! planted value. Groups beyond 64 bits go to `crax ecdlp`, which runs the
//! arbitrary-precision attacks.

use clap::{Args, ValueEnum};
use libca::{Elem, Group, Kind, Options, PrecompOptions, Solver, Stats};
use serde::Serialize;

use super::output::{ops_per_sqrt, parse_pair, parse_u64, CmdResult, Failure, Out};

/// Which group the problem lives in.
#[derive(Clone, Copy, Debug, PartialEq, Eq, ValueEnum, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum GroupKind {
    /// The multiplicative group of the prime field, `(Z/pZ)^*`.
    Zp,
    /// Points of `y^2 = x^3 + a x + b` over `F_p`.
    Ec,
}

/// The group and the two elements of a problem `g^x = h`.
#[derive(Args, Clone, Debug)]
pub struct GroupArgs {
    /// A curve from the library's registry (`crax curve names`); sets
    /// `--p --a --b --order`.
    #[arg(long, conflicts_with_all = ["p", "a", "b"])]
    pub curve: Option<String>,
    /// `zp` or `ec` (default: `ec` when a curve or `--a/--b` is given).
    #[arg(long, value_enum)]
    pub group: Option<GroupKind>,
    /// Field prime, below 2^64 (decimal or 0x hex).
    #[arg(long)]
    pub p: Option<String>,
    /// Curve coefficient a.
    #[arg(long)]
    pub a: Option<String>,
    /// Curve coefficient b.
    #[arg(long)]
    pub b: Option<String>,
    /// Order of the (sub)group the logarithm lives in. Curves: counted when
    /// omitted. `Z_p^*`: `p - 1` when omitted.
    #[arg(long)]
    pub order: Option<String>,
    /// Base element: a residue for `zp`, `x,y` for `ec` (default: a
    /// generator of the order-`order` subgroup found from `--seed`).
    #[arg(long)]
    pub g: Option<String>,
    /// Target element, same format as `--g`. Omit it and give `--x` to
    /// generate a problem with a known answer.
    #[arg(long)]
    pub h: Option<String>,
    /// Plant this secret: `h = g^x`. The solver does not see it.
    #[arg(long)]
    pub x: Option<String>,
    /// RNG seed (0: random).
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    /// Worker threads.
    #[arg(long, default_value_t = 1)]
    pub threads: u32,
    /// Give up after this many group operations (0: no limit).
    #[arg(long, default_value_t = 0)]
    pub max_ops: u64,
}

/// A problem ready for a solver.
pub struct Problem {
    pub group: Group,
    pub g: Elem,
    pub h: Elem,
    pub planted: Option<u64>,
    pub desc: GroupDesc,
}

/// The group, as it appears in reports.
#[derive(Clone, Debug, Serialize)]
pub struct GroupDesc {
    pub kind: GroupKind,
    pub p: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub a: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub b: Option<String>,
    pub order: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cofactor: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub curve: Option<String>,
}

fn elem_string(kind: Kind, e: &Elem) -> String {
    match kind {
        Kind::Zp => e.residue().to_string(),
        Kind::Ec if e.is_infinity() => "infinity".into(),
        Kind::Ec => format!("{},{}", e.x(), e.y()),
    }
}

fn parse_elem(kind: Kind, s: &str) -> Result<Elem, String> {
    match kind {
        Kind::Zp => Ok(Elem::zp(parse_u64(s)?)),
        Kind::Ec => {
            let (x, y) = parse_pair(s)?;
            let x = u64::try_from(&x).map_err(|_| "x does not fit in 64 bits".to_string())?;
            let y = u64::try_from(&y).map_err(|_| "y does not fit in 64 bits".to_string())?;
            Ok(Elem::ec(x, y))
        }
    }
}

fn too_big(what: &str) -> String {
    format!(
        "{what} does not fit in 64 bits; the generic solvers here run on the 64-bit C library. \
         Use `crax ecdlp` for arbitrary-precision curves."
    )
}

impl GroupArgs {
    /// Build the group and the problem, validating every element.
    pub fn problem(&self) -> Result<Problem, String> {
        let u = |s: &Option<String>, what: &str| -> Result<Option<u64>, String> {
            s.as_deref()
                .map(|v| parse_u64(v).map_err(|_| too_big(what)))
                .transpose()
        };
        let (mut p, mut a, mut b, mut order) = (
            u(&self.p, "--p")?,
            u(&self.a, "--a")?,
            u(&self.b, "--b")?,
            u(&self.order, "--order")?,
        );
        if let Some(name) = &self.curve {
            let (cp, ca, cb, co) = libca::curve::by_name(name).map_err(|e| {
                format!(
                    "unknown curve {name:?} ({e}); known: {}",
                    libca::curve::names().join(", ")
                )
            })?;
            p = Some(cp);
            a = Some(ca);
            b = Some(cb);
            order = order.or(Some(co));
        }
        let kind = match self.group {
            Some(k) => k,
            None if self.curve.is_some() || a.is_some() || b.is_some() => GroupKind::Ec,
            None => GroupKind::Zp,
        };
        let p = p.ok_or("--p (or --curve) is required")?;
        let group = match kind {
            GroupKind::Zp => {
                let n = order.unwrap_or(p.saturating_sub(1));
                Group::zp(p, n).map_err(|e| format!("bad Z_p^* group: {e}"))?
            }
            GroupKind::Ec => {
                let (a, b) = (a.unwrap_or(0), b.ok_or("--b is required for a curve")?);
                let n = match order {
                    Some(n) => n,
                    None => Group::ec_count_points(p, a, b)
                        .map_err(|e| format!("counting points: {e}"))?,
                };
                Group::ec(p, a, b, n).map_err(|e| format!("bad curve: {e}"))?
            }
        };
        let k = group.kind();
        let g = match &self.g {
            Some(s) => parse_elem(k, s)?,
            None => group.find_generator(self.seed.max(1)).map_err(|e| {
                format!("no generator of the order-{} subgroup: {e}", group.order())
            })?,
        };
        if !group.validate(&g) {
            return Err(format!(
                "--g {} is not an element of the group",
                elem_string(k, &g)
            ));
        }
        let planted = self.x.as_deref().map(parse_u64).transpose()?;
        let h = match (&self.h, planted) {
            (Some(s), _) => parse_elem(k, s)?,
            (None, Some(x)) => group.mul(&g, x).map_err(|e| e.to_string())?,
            (None, None) => return Err("give --h, or --x to generate a target".into()),
        };
        if !group.validate(&h) {
            return Err(format!(
                "--h {} is not an element of the group",
                elem_string(k, &h)
            ));
        }
        let desc = GroupDesc {
            kind,
            p: group.p().to_string(),
            a: (kind == GroupKind::Ec).then(|| group.curve_a().to_string()),
            b: (kind == GroupKind::Ec).then(|| group.curve_b().to_string()),
            order: group.order().to_string(),
            cofactor: (group.cofactor() != 0).then(|| group.cofactor().to_string()),
            curve: self.curve.clone(),
        };
        Ok(Problem {
            group,
            g,
            h,
            planted,
            desc,
        })
    }

    fn options(&self) -> Options {
        Options {
            threads: self.threads.max(1),
            seed: self.seed,
            max_ops: self.max_ops,
            ..Options::default()
        }
    }
}

/// Work statistics, as reported.
#[derive(Clone, Debug, Serialize)]
pub struct StatsOut {
    pub group_ops: u64,
    pub iterations: u64,
    pub table_entries: u64,
    pub collisions: u64,
    pub bytes_peak: u64,
    pub seconds: f64,
    pub threads: u32,
    /// Group operations divided by the square root of the search width.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ops_per_sqrt_width: Option<f64>,
}

impl StatsOut {
    fn new(s: &Stats, width: f64) -> Self {
        StatsOut {
            group_ops: s.group_ops,
            iterations: s.iterations,
            table_entries: s.table_entries,
            collisions: s.collisions,
            bytes_peak: s.bytes_peak,
            seconds: s.seconds,
            threads: s.threads,
            ops_per_sqrt_width: ops_per_sqrt(s.group_ops, width),
        }
    }
}

/// The report every generic solver prints.
#[derive(Clone, Debug, Serialize)]
pub struct DlogReport {
    pub status: &'static str,
    pub algorithm: String,
    pub group: GroupDesc,
    pub g: String,
    pub h: String,
    pub x: String,
    /// `g^x == h`, checked independently of the solver.
    pub verified: bool,
    /// When the problem was generated with `--x`: whether `x` is that value
    /// modulo the order of `g`.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub matches_planted: Option<bool>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub interval: Option<[String; 2]>,
    pub stats: StatsOut,
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub notes: Vec<String>,
}

impl DlogReport {
    fn text(&self) -> String {
        let mut s = format!(
            "{}: x = {}  ({})\n  group    {} p={}{} order={}\n  g        {}\n  h        {}\n",
            self.algorithm,
            self.x,
            if self.verified {
                "verified: g^x = h"
            } else {
                "NOT VERIFIED"
            },
            match self.group.kind {
                GroupKind::Zp => "Z_p^*",
                GroupKind::Ec => "E(F_p)",
            },
            self.group.p,
            match (&self.group.a, &self.group.b) {
                (Some(a), Some(b)) => format!(" a={a} b={b}"),
                _ => String::new(),
            },
            self.group.order,
            self.g,
            self.h,
        );
        if let Some(m) = self.matches_planted {
            s += &format!("  planted  {}\n", if m { "recovered" } else { "DIFFERENT" });
        }
        if let Some([lo, hi]) = &self.interval {
            s += &format!("  interval [{lo}, {hi}]\n");
        }
        s += &format!(
            "  work     {} group ops, {} table entries, {:.3} s, {} thread(s)",
            self.stats.group_ops, self.stats.table_entries, self.stats.seconds, self.stats.threads
        );
        if let Some(r) = self.stats.ops_per_sqrt_width {
            s += &format!(", {r:.3} ops/sqrt(width)");
        }
        s.push('\n');
        for n in &self.notes {
            s += &format!("  note     {n}\n");
        }
        s
    }
}

fn finish(
    out: Out,
    pb: &Problem,
    algorithm: &str,
    x: u64,
    stats: &Stats,
    width: f64,
    interval: Option<(u64, u64)>,
    notes: Vec<String>,
) -> CmdResult {
    let k = pb.group.kind();
    let verified = pb
        .group
        .mul(&pb.g, x)
        .map(|gx| pb.group.equal(&gx, &pb.h))
        .unwrap_or(false);
    let matches_planted = pb.planted.map(|planted| {
        let n = pb
            .group
            .elem_order(&pb.g)
            .unwrap_or(pb.group.order())
            .max(1);
        planted % n == x % n
    });
    let report = DlogReport {
        status: if verified { "ok" } else { "unverified" },
        algorithm: algorithm.to_string(),
        group: pb.desc.clone(),
        g: elem_string(k, &pb.g),
        h: elem_string(k, &pb.h),
        x: x.to_string(),
        verified,
        matches_planted,
        interval: interval.map(|(lo, hi)| [lo.to_string(), hi.to_string()]),
        stats: StatsOut::new(stats, width),
        notes,
    };
    out.emit(&report, || report.text())?;
    if verified {
        Ok(())
    } else {
        Err(Failure::reported(
            "the solver's answer does not satisfy g^x = h",
        ))
    }
}

fn lib_err(algorithm: &str) -> impl Fn(libca::Error) -> String + '_ {
    move |e| format!("{algorithm}: {e}")
}

/// An interval `[lo, hi]` for the interval solvers.
#[derive(Args, Clone, Debug)]
pub struct IntervalArgs {
    #[command(flatten)]
    pub group: GroupArgs,
    /// Lower end of the interval the logarithm is known to lie in.
    #[arg(long)]
    pub lo: Option<String>,
    /// Upper end of the interval (inclusive). Both omitted: the whole group.
    #[arg(long)]
    pub hi: Option<String>,
}

impl IntervalArgs {
    fn interval(&self, pb: &Problem) -> Result<(u64, u64), String> {
        let lo = self.lo.as_deref().map(parse_u64).transpose()?.unwrap_or(0);
        let hi = match self.hi.as_deref().map(parse_u64).transpose()? {
            Some(hi) => hi,
            None if lo == 0 => 0,
            None => pb.group.order().saturating_sub(1),
        };
        if hi < lo {
            return Err(format!("empty interval [{lo}, {hi}]"));
        }
        Ok((lo, hi))
    }
}

fn width(pb: &Problem, (lo, hi): (u64, u64)) -> f64 {
    if lo == 0 && hi == 0 {
        pb.group.order() as f64
    } else {
        (hi - lo) as f64 + 1.0
    }
}

/// Which interval solver to run.
#[derive(Clone, Copy, Debug)]
pub enum IntervalSolver {
    Bsgs,
    Kangaroo,
    Grumpy,
}

/// `crax bsgs | kangaroo | grumpy`.
pub fn run_interval(out: Out, which: IntervalSolver, args: &IntervalArgs) -> CmdResult {
    let pb = args.group.problem()?;
    let iv = args.interval(&pb)?;
    let mut opts = args.group.options();
    // A kangaroo whose target lies outside the interval never meets the tame
    // herd; bound the walk at 64 times its expected 2 sqrt(width) unless the
    // caller chose a budget.
    if matches!(which, IntervalSolver::Kangaroo) && opts.max_ops == 0 {
        opts.max_ops = (128.0 * width(&pb, iv).sqrt()).max(1e6) as u64;
    }
    let (name, r) = match which {
        IntervalSolver::Bsgs => ("bsgs", pb.group.bsgs(&pb.g, &pb.h, iv.0, iv.1, &opts)),
        IntervalSolver::Kangaroo => (
            "kangaroo",
            pb.group.kangaroo(&pb.g, &pb.h, iv.0, iv.1, &opts),
        ),
        IntervalSolver::Grumpy => ("grumpy", pb.group.grumpy(&pb.g, &pb.h, iv.0, iv.1, &opts)),
    };
    let (x, st) = r.map_err(lib_err(name))?;
    let shown = (iv != (0, 0)).then_some(iv);
    finish(out, &pb, name, x, &st, width(&pb, iv), shown, Vec::new())
}

/// `crax rho`.
#[derive(Args, Clone, Debug)]
pub struct RhoArgs {
    #[command(flatten)]
    pub group: GroupArgs,
    /// Distinguished-point bits (default: automatic).
    #[arg(long)]
    pub dp_bits: Option<i32>,
    /// Partitions of the r-adding walk (default: automatic).
    #[arg(long)]
    pub r: Option<u32>,
    /// Concurrent walks per thread (default: automatic).
    #[arg(long)]
    pub walks_per_thread: Option<u32>,
    /// Do not fold the walk by the negation map on curves.
    #[arg(long)]
    pub no_negation: bool,
}

pub fn run_rho(out: Out, args: &RhoArgs) -> CmdResult {
    let pb = args.group.problem()?;
    let mut opts = args.group.options();
    opts.rho_negation_map = !args.no_negation;
    if let Some(d) = args.dp_bits {
        opts.rho_dp_bits = d;
    }
    if let Some(r) = args.r {
        opts.rho_r = r;
    }
    if let Some(w) = args.walks_per_thread {
        opts.rho_walks_per_thread = w;
    }
    let (x, st) = pb.group.rho(&pb.g, &pb.h, &opts).map_err(lib_err("rho"))?;
    let n = pb.group.order() as f64;
    finish(out, &pb, "rho", x, &st, n, None, Vec::new())
}

/// The per-subgroup solver of `crax pohlig-hellman`.
#[derive(Clone, Copy, Debug, ValueEnum)]
pub enum SubSolver {
    Auto,
    Bsgs,
    Rho,
    Kangaroo,
    Grumpy,
    Brute,
}

impl From<SubSolver> for Solver {
    fn from(s: SubSolver) -> Solver {
        match s {
            SubSolver::Auto => Solver::Auto,
            SubSolver::Bsgs => Solver::Bsgs,
            SubSolver::Rho => Solver::Rho,
            SubSolver::Kangaroo => Solver::Kangaroo,
            SubSolver::Grumpy => Solver::Grumpy,
            SubSolver::Brute => Solver::Brute,
        }
    }
}

/// `crax pohlig-hellman`.
#[derive(Args, Clone, Debug)]
pub struct PohligArgs {
    #[command(flatten)]
    pub group: GroupArgs,
    /// Solver inside each prime-power subgroup.
    #[arg(long, value_enum, default_value_t = SubSolver::Auto)]
    pub solver: SubSolver,
    /// With `auto`: BSGS for prime factors up to this, rho above.
    #[arg(long)]
    pub bsgs_max_prime: Option<u64>,
}

pub fn run_pohlig(out: Out, args: &PohligArgs) -> CmdResult {
    let pb = args.group.problem()?;
    let mut opts = args.group.options();
    opts.solver = args.solver.into();
    if let Some(m) = args.bsgs_max_prime {
        opts.bsgs_max_prime = m;
    }
    let (x, st) = pb
        .group
        .dlog(&pb.g, &pb.h, &opts)
        .map_err(lib_err("pohlig-hellman"))?;
    let factors = libca::factorize(pb.group.order());
    let largest = factors.iter().map(|&(q, _)| q).max().unwrap_or(1);
    let notes = vec![format!(
        "order = {}; the work is governed by the largest prime factor {largest}",
        factors
            .iter()
            .map(|&(q, e)| if e > 1 {
                format!("{q}^{e}")
            } else {
                q.to_string()
            })
            .collect::<Vec<_>>()
            .join(" * ")
    )];
    finish(
        out,
        &pb,
        "pohlig-hellman",
        x,
        &st,
        largest as f64,
        None,
        notes,
    )
}

/// `crax precomp`.
#[derive(Args, Clone, Debug)]
pub struct PrecompArgs {
    #[command(flatten)]
    pub group: GroupArgs,
    /// Distinguished-point bits (default: log2(n)/3).
    #[arg(long)]
    pub dp_bits: Option<i32>,
    /// Chains in the table (default: from the coverage factor).
    #[arg(long)]
    pub table_size: Option<u64>,
    /// Coverage factor of the precomputation (default: 1.0).
    #[arg(long)]
    pub coverage: Option<f64>,
}

pub fn run_precomp(out: Out, args: &PrecompArgs) -> CmdResult {
    let pb = args.group.problem()?;
    let opts = PrecompOptions {
        dp_bits: args.dp_bits.unwrap_or(-1),
        table_size: args.table_size.unwrap_or(0),
        coverage: args.coverage.unwrap_or(0.0),
        threads: args.group.threads.max(1),
        seed: args.group.seed,
    };
    let (x, st) = pb
        .group
        .precomp(&pb.g, &pb.h, &opts)
        .map_err(lib_err("precomp"))?;
    let notes = vec![
        "one-shot: the statistics include the n^(2/3) table build as well as the n^(1/3) online walk"
            .to_string(),
    ];
    let n = pb.group.order() as f64;
    finish(out, &pb, "precomp", x, &st, n, None, notes)
}

/// `crax glv`.
#[derive(Args, Clone, Debug)]
pub struct GlvArgs {
    #[command(flatten)]
    pub group: GroupArgs,
}

pub fn run_glv(out: Out, args: &GlvArgs) -> CmdResult {
    let pb = args.group.problem()?;
    if pb.group.kind() != Kind::Ec {
        return Err("glv needs a curve (--curve or --a/--b)".into());
    }
    let (x, info, st) = pb
        .group
        .curve_solve(&pb.g, &pb.h, args.group.seed)
        .map_err(lib_err("glv"))?;
    let notes = vec![format!(
        "endomorphism {:?}: walk folded by an automorphism group of order {} (rho speed-up {:.4})",
        info.endo, info.aut_order, info.rho_speedup
    )];
    let n = pb.group.order() as f64;
    finish(out, &pb, "glv-rho", x, &st, n, None, notes)
}

/// `crax cheon`: recover `alpha` from `g`, `g^alpha`, `g^(alpha^d)`.
#[derive(Args, Clone, Debug)]
pub struct CheonArgs {
    #[command(flatten)]
    pub group: GroupArgs,
    /// `g^alpha` (same format as --g).
    #[arg(long, requires = "g_alpha_d")]
    pub g_alpha: Option<String>,
    /// `g^(alpha^d)`.
    #[arg(long)]
    pub g_alpha_d: Option<String>,
    /// Plant this `alpha` and build `g^alpha`, `g^(alpha^d)` from it.
    #[arg(long, conflicts_with = "g_alpha")]
    pub alpha: Option<String>,
    /// The divisor `d` of `order - 1` (default: the cheapest one).
    #[arg(long)]
    pub d: Option<u64>,
}

#[derive(Serialize)]
struct CheonReport {
    status: &'static str,
    algorithm: &'static str,
    group: GroupDesc,
    d: u64,
    alpha: String,
    verified: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    matches_planted: Option<bool>,
    estimated_exponentiations: f64,
    stats: StatsOut,
}

pub fn run_cheon(out: Out, args: &CheonArgs) -> CmdResult {
    // The target of a Cheon instance is not a single `h`; plant a dummy so
    // the shared group parser accepts the arguments.
    let mut ga = args.group.clone();
    if ga.h.is_none() && ga.x.is_none() {
        ga.x = Some("1".into());
    }
    let pb = ga.problem()?;
    let k = pb.group.kind();
    let n = pb.group.order();
    let (best_d, cost) = libca::cheon_best_divisor(n);
    let d = args.d.unwrap_or(best_d);
    let planted = args.alpha.as_deref().map(parse_u64).transpose()?;
    let (g_a, g_ad) = match (planted, &args.g_alpha, &args.g_alpha_d) {
        (Some(alpha), _, _) => pb
            .group
            .cheon_instance(&pb.g, alpha, d)
            .map_err(lib_err("cheon"))?,
        (None, Some(a), Some(ad)) => (parse_elem(k, a)?, parse_elem(k, ad)?),
        _ => return Err("give --g-alpha and --g-alpha-d, or --alpha to plant one".into()),
    };
    let (alpha, st) = pb
        .group
        .cheon(&pb.g, &g_a, &g_ad, d, args.group.max_ops)
        .map_err(lib_err("cheon"))?;
    let verified = pb
        .group
        .mul(&pb.g, alpha)
        .map(|v| pb.group.equal(&v, &g_a))
        .unwrap_or(false);
    let report = CheonReport {
        status: if verified { "ok" } else { "unverified" },
        algorithm: "cheon",
        group: pb.desc.clone(),
        d,
        alpha: alpha.to_string(),
        verified,
        matches_planted: planted.map(|a| a % n == alpha % n),
        estimated_exponentiations: cost,
        stats: StatsOut::new(&st, n as f64),
    };
    out.emit(&report, || {
        format!(
            "cheon: alpha = {} ({}), d = {}, {} exponentiations, {:.3} s\n",
            report.alpha,
            if verified {
                "verified: g^alpha matches"
            } else {
                "NOT VERIFIED"
            },
            d,
            st.iterations,
            st.seconds
        )
    })?;
    if verified {
        Ok(())
    } else {
        Err(Failure::reported(
            "cheon: the recovered alpha does not reproduce g^alpha",
        ))
    }
}

/// Which walk kernel `crax gpu-rho` runs.
#[derive(Clone, Copy, Debug, ValueEnum)]
pub enum Backend {
    /// CUDA if compiled in and a device exists, else the emulator.
    Auto,
    Cuda,
    /// The host emulator running the same kernel code.
    Emulate,
}

/// `crax gpu-rho`.
#[derive(Args, Clone, Debug)]
pub struct GpuRhoArgs {
    #[command(flatten)]
    pub group: GroupArgs,
    #[arg(long, value_enum, default_value_t = Backend::Auto)]
    pub backend: Backend,
    /// CUDA device ordinal.
    #[arg(long, default_value_t = 0)]
    pub device: i32,
    /// Distinguished-point bits (default: automatic).
    #[arg(long)]
    pub dp_bits: Option<u32>,
}

pub fn run_gpu_rho(out: Out, args: &GpuRhoArgs) -> CmdResult {
    let pb = args.group.problem()?;
    let opts = libca::GpuOptions {
        backend: match args.backend {
            Backend::Auto => libca::GpuBackend::Auto,
            Backend::Cuda => libca::GpuBackend::Cuda,
            Backend::Emulate => libca::GpuBackend::Emulate,
        },
        device: args.device,
        dp_bits: args.dp_bits,
        seed: args.group.seed,
        ..libca::GpuOptions::default()
    };
    let (x, st) = pb
        .group
        .gpu_rho(&pb.g, &pb.h, &opts)
        .map_err(lib_err("gpu-rho"))?;
    let notes = vec![format!(
        "CUDA compiled in: {}; devices: {}",
        libca::gpu::cuda_compiled(),
        libca::gpu::device_count()
    )];
    let n = pb.group.order() as f64;
    finish(out, &pb, "gpu-rho", x, &st, n, None, notes)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn zp_args(x: &str) -> GroupArgs {
        GroupArgs {
            curve: None,
            group: None,
            p: Some("2000000579".into()),
            a: None,
            b: None,
            order: Some("1000000289".into()),
            g: None,
            h: None,
            x: Some(x.into()),
            seed: 1,
            threads: 1,
            max_ops: 0,
        }
    }

    #[test]
    fn planted_zp_problem_is_solved_by_every_whole_group_solver() {
        let out = Out { json: true };
        let args = zp_args("123456789");
        run_rho(
            out,
            &RhoArgs {
                group: args.clone(),
                dp_bits: None,
                r: None,
                walks_per_thread: None,
                no_negation: false,
            },
        )
        .unwrap();
        run_pohlig(
            out,
            &PohligArgs {
                group: args.clone(),
                solver: SubSolver::Auto,
                bsgs_max_prime: None,
            },
        )
        .unwrap();
        for which in [
            IntervalSolver::Bsgs,
            IntervalSolver::Kangaroo,
            IntervalSolver::Grumpy,
        ] {
            run_interval(
                out,
                which,
                &IntervalArgs {
                    group: args.clone(),
                    lo: None,
                    hi: None,
                },
            )
            .unwrap();
        }
    }

    #[test]
    fn interval_solvers_respect_the_interval() {
        let out = Out { json: true };
        let args = IntervalArgs {
            group: zp_args("500123"),
            lo: Some("500000".into()),
            hi: Some("600000".into()),
        };
        run_interval(out, IntervalSolver::Kangaroo, &args).unwrap();
        run_interval(out, IntervalSolver::Bsgs, &args).unwrap();
    }

    #[test]
    fn curve_problems_and_bad_input() {
        let out = Out { json: true };
        let mut g = zp_args("2130");
        g.p = Some("1000003".into());
        g.a = Some("1".into());
        g.b = Some("7".into());
        g.order = Some("2777".into());
        run_pohlig(
            out,
            &PohligArgs {
                group: g.clone(),
                solver: SubSolver::Bsgs,
                bsgs_max_prime: None,
            },
        )
        .unwrap();
        // A point that is not on the curve is refused before any solver runs.
        let mut bad = g.clone();
        bad.g = Some("1,1".into());
        assert!(bad.problem().is_err());
        // Beyond 64 bits the error points at the arbitrary-precision tools.
        let mut big = g;
        big.p = Some("340282366920938463463374607431768211507".into());
        assert!(big.problem().err().unwrap().contains("crax ecdlp"));
    }

    #[test]
    fn cheon_recovers_a_planted_alpha() {
        let out = Out { json: true };
        let mut g = zp_args("1");
        g.x = None;
        run_cheon(
            out,
            &CheonArgs {
                group: g,
                g_alpha: None,
                g_alpha_d: None,
                alpha: Some("987654321".into()),
                d: None,
            },
        )
        .unwrap();
    }
}
