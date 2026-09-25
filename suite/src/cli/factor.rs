//! Integer factoring and RSA attacks: `crax factor | gnfs | snfs | qs |
//! ecm | pm1 | rho-factor | rsa ...`.
//!
//! These run [`crate::cryptanalysis::factoring`]: a general and a special
//! number field sieve, the self-initialising quadratic sieve, Pollard
//! p-1 / Williams p+1, Pollard-Brent rho, Lenstra ECM, the classic RSA
//! attacks, and a full-factorisation ladder that picks among them. Every
//! reported factor has been checked by multiplication. Integers may be
//! written as expressions: `2^227-1`, `(2^239+1)/3`, `3*10^40+7`.

use clap::{Args, Subcommand};
use num_bigint::{BigInt, BigUint};
use num_integer::Integer;
use num_traits::{One, Zero};
use serde::Serialize;

use super::output::{CmdResult, Failure, Out};
use crate::cryptanalysis::factoring::nfs::snfs::SnfsInput;
use crate::cryptanalysis::factoring::{
    self,
    nfs::{gnfs::GnfsParams, snfs::SnfsParams, NfsParams, NfsReport},
    pm1::{Pm1Params, Pp1Params},
    qs::{QsParams, QsReport},
    rho_factor::RhoParams,
    rsa_attacks, FactorOptions, FactorReport, Progress,
};

// ---- integer expressions --------------------------------------------------

/// Parse an integer expression: decimal or 0x literals, `+ - * / ^` and
/// parentheses. Division must be exact; the result must be non-negative.
pub fn parse_expr(s: &str) -> Result<BigUint, String> {
    let toks: Vec<char> = s
        .chars()
        .filter(|c| !c.is_whitespace() && *c != '_')
        .collect();
    let mut p = Parser { t: &toks, i: 0 };
    let v = p.sum()?;
    if p.i != toks.len() {
        return Err(format!("unexpected {:?} in {s:?}", toks[p.i]));
    }
    v.to_biguint().ok_or_else(|| format!("{s:?} is negative"))
}

struct Parser<'a> {
    t: &'a [char],
    i: usize,
}

impl Parser<'_> {
    fn peek(&self) -> Option<char> {
        self.t.get(self.i).copied()
    }
    fn sum(&mut self) -> Result<BigInt, String> {
        let mut v = self.product()?;
        while let Some(c @ ('+' | '-')) = self.peek() {
            self.i += 1;
            let r = self.product()?;
            v = if c == '+' { v + r } else { v - r };
        }
        Ok(v)
    }
    fn product(&mut self) -> Result<BigInt, String> {
        let mut v = self.power()?;
        while let Some(c @ ('*' | '/')) = self.peek() {
            self.i += 1;
            let r = self.power()?;
            if c == '*' {
                v *= r;
            } else {
                if r.is_zero() {
                    return Err("division by zero".into());
                }
                let (q, rem) = v.div_rem(&r);
                if !rem.is_zero() {
                    return Err(format!("{v} is not divisible by {r}"));
                }
                v = q;
            }
        }
        Ok(v)
    }
    fn power(&mut self) -> Result<BigInt, String> {
        let base = self.atom()?;
        if self.peek() == Some('^') {
            self.i += 1;
            let e = self.power()?;
            let e = u32::try_from(&e).map_err(|_| format!("exponent {e} out of range"))?;
            if e > 100_000 {
                return Err(format!("exponent {e} is too large"));
            }
            return Ok(base.pow(e));
        }
        Ok(base)
    }
    fn atom(&mut self) -> Result<BigInt, String> {
        match self.peek() {
            Some('(') => {
                self.i += 1;
                let v = self.sum()?;
                if self.peek() != Some(')') {
                    return Err("missing ')'".into());
                }
                self.i += 1;
                Ok(v)
            }
            Some('-') => {
                self.i += 1;
                Ok(-self.atom()?)
            }
            Some(c) if c.is_ascii_digit() => {
                let start = self.i;
                let hex = c == '0' && matches!(self.t.get(self.i + 1), Some('x' | 'X'));
                if hex {
                    self.i += 2;
                }
                while self.peek().is_some_and(|c| {
                    if hex {
                        c.is_ascii_hexdigit()
                    } else {
                        c.is_ascii_digit()
                    }
                }) {
                    self.i += 1;
                }
                let lit: String = self.t[start..self.i].iter().collect();
                let v = if hex {
                    BigInt::parse_bytes(&lit.as_bytes()[2..], 16)
                } else {
                    BigInt::parse_bytes(lit.as_bytes(), 10)
                };
                v.ok_or_else(|| format!("bad number {lit:?}"))
            }
            other => Err(format!("expected a number, found {other:?}")),
        }
    }
}

/// Parse an SNFS form `(c*)r^e(+|-)s`, e.g. `2^227-1`, `3*10^80+7`.
pub fn parse_form(s: &str) -> Result<SnfsInput, String> {
    let t: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    let bad = || format!("expected an SNFS form [c*]r^e+s or [c*]r^e-s, got {s:?}");
    let (head, sign, tail) = match t.rfind(['+', '-']) {
        Some(i) if i > 0 => (&t[..i], &t[i..i + 1], &t[i + 1..]),
        _ => return Err(bad()),
    };
    let (c, re) = match head.split_once('*') {
        Some((c, re)) => (c.parse::<u64>().map_err(|_| bad())?, re),
        None => (1, head),
    };
    let (r, e) = re.split_once('^').ok_or_else(bad)?;
    let s_abs: i64 = tail.parse().map_err(|_| bad())?;
    Ok(SnfsInput::Form {
        r: r.parse().map_err(|_| bad())?,
        e: e.parse().map_err(|_| bad())?,
        s: if sign == "-" { -s_abs } else { s_abs },
        c,
    })
}

fn progress_printer(verbose: bool) -> Option<impl Fn(&Progress)> {
    verbose.then_some(|p: &Progress| {
        eprintln!(
            "[{:>8.2}s] {:<10} {}/{}",
            p.seconds, p.stage, p.done, p.target
        )
    })
}

fn digits(n: &BigUint) -> usize {
    n.to_str_radix(10).len()
}

/// Refuse a size the implementation cannot finish in reasonable time
/// unless `--force` is given: these are educational sieves (see the
/// module docs), not CADO-NFS or msieve.
fn size_guard(n: &BigUint, method: &str, max: usize, force: bool) -> Result<(), String> {
    let d = digits(n);
    if d > max && !force {
        return Err(format!(
            "{method}: n has {d} digits; this implementation is practical up to about {max} \
             (measured: GNFS 55 digits ~18 s, 59 digits ~2 min; SIQS 60 digits ~16 s). \
             Pass --force to run it anyway."
        ));
    }
    Ok(())
}

fn split_line(n: &BigUint, f: &Option<BigUint>, c: &Option<BigUint>, verified: bool) -> String {
    match (f, c) {
        (Some(f), Some(c)) => format!(
            "{n} ({} digits) = {f} * {c}  ({})",
            digits(n),
            if verified { "verified" } else { "NOT VERIFIED" }
        ),
        _ => format!("{n} ({} digits): no factor found", digits(n)),
    }
}

fn verdict(verified: bool, found: bool, what: &str) -> CmdResult {
    match (found, verified) {
        (true, true) => Ok(()),
        (true, false) => Err(Failure::reported(format!("{what}: factor not verified"))),
        (false, _) => Err(Failure::reported(format!("{what}: no factor found"))),
    }
}

// ---- crax factor -----------------------------------------------------------

#[derive(Args, Clone, Debug)]
pub struct FactorArgs {
    /// The integer (an expression such as 2^227-1 is accepted).
    pub n: String,
    /// n divides this SNFS form ((c*)r^e+s), enabling the special sieve.
    #[arg(long)]
    pub snfs_form: Option<String>,
    /// Use the number field sieve instead of the quadratic sieve from
    /// --nfs-min-digits on (the QS is faster at every size here).
    #[arg(long)]
    pub prefer_nfs: bool,
    /// Also run Williams p+1.
    #[arg(long)]
    pub pp1: bool,
    /// Largest cofactor size the quadratic sieve takes, in digits.
    #[arg(long)]
    pub qs_max_digits: Option<usize>,
    #[arg(long, default_value_t = 1)]
    pub threads: usize,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
}

fn factor_text(r: &FactorReport) -> String {
    let mut s = format!("{} ({} digits) =", r.n, digits(&r.n));
    let parts: Vec<String> = r
        .factors
        .iter()
        .map(|f| {
            let e = if f.exponent > 1 {
                format!("^{}", f.exponent)
            } else {
                String::new()
            };
            format!(" {}{e}", f.prime)
        })
        .chain(r.unfactored.iter().map(|(c, e)| {
            format!(
                " [{c}]{}",
                if *e > 1 {
                    format!("^{e}")
                } else {
                    String::new()
                }
            )
        }))
        .collect();
    s += &parts.join(" *");
    s += &format!(
        "\n  {} ({:.3} s)\n",
        match (r.complete, r.verified) {
            (true, true) => "complete, product verified",
            (false, true) => "INCOMPLETE: bracketed composites were not split",
            _ => "NOT VERIFIED",
        },
        r.total_seconds
    );
    for f in &r.factors {
        s += &format!(
            "  {:<40} {:?}{}\n",
            f.prime.to_string(),
            f.method,
            if f.proven {
                ", proven prime"
            } else {
                ", probable prime"
            }
        );
    }
    s
}

pub fn run_factor(out: Out, a: &FactorArgs) -> CmdResult {
    let n = parse_expr(&a.n)?;
    if n.is_zero() {
        return Err("cannot factor 0".into());
    }
    let mut o = FactorOptions {
        prefer_nfs: a.prefer_nfs,
        seed: a.seed,
        ..FactorOptions::default()
    };
    if let Some(f) = &a.snfs_form {
        o.snfs_form = Some(parse_form(f)?);
    }
    if a.pp1 {
        o.pp1 = Some(Pp1Params::default());
    }
    if let Some(d) = a.qs_max_digits {
        o.qs_max_digits = d;
    }
    o.qs.threads = a.threads.max(1);
    o.gnfs.nfs.threads = a.threads.max(1);
    o.snfs.nfs.threads = a.threads.max(1);
    let r = factoring::factor(&n, &o);
    out.emit(&r, || factor_text(&r))?;
    match (r.complete, r.verified) {
        (true, true) => Ok(()),
        (_, false) => Err(Failure::reported("the factors do not multiply back to n")),
        (false, true) => Err(Failure::reported(
            "incomplete: some composite parts were not split",
        )),
    }
}

// ---- number field sieves ---------------------------------------------------

#[derive(Args, Clone, Debug)]
pub struct NfsArgs {
    /// Rational factor-base bound (default: from the size of n).
    #[arg(long)]
    pub rational_bound: Option<u64>,
    /// Algebraic factor-base bound (default: from the size of n).
    #[arg(long)]
    pub algebraic_bound: Option<u64>,
    /// Sieve half-width in a (default: from the size of n).
    #[arg(long)]
    pub sieve_half_width: Option<u64>,
    /// Sieving threads.
    #[arg(long, default_value_t = 1)]
    pub threads: usize,
    /// Stage progress on stderr.
    #[arg(long)]
    pub verbose: bool,
    /// Run even above the size this implementation is practical for.
    #[arg(long)]
    pub force: bool,
}

impl NfsArgs {
    fn params(&self) -> NfsParams {
        NfsParams {
            rational_bound: self.rational_bound,
            algebraic_bound: self.algebraic_bound,
            sieve_half_width: self.sieve_half_width,
            threads: self.threads.max(1),
            ..NfsParams::default()
        }
    }
}

fn nfs_text(r: &NfsReport) -> String {
    let mut s = format!(
        "{}: {}\n",
        r.method,
        split_line(&r.n, &r.factor, &r.cofactor, r.verified)
    );
    s += &format!(
        "  polynomial  {} (degree {}, m = {}, skewness {:.2}, alpha {:.2})\n",
        r.polynomial, r.degree, r.m, r.skewness, r.alpha
    );
    s += &format!(
        "  factor base rational {} primes (B = {}), algebraic {} ideals (B = {}), {} quadratic characters\n",
        r.rational_fb_size, r.rational_bound, r.algebraic_fb_size, r.algebraic_bound, r.quadratic_characters
    );
    s += &format!(
        "  sieve       {} lines, {} relations ({} full, {} from partials)\n",
        r.lines_sieved,
        r.full_relations + r.partial_relations,
        r.full_relations,
        r.partial_relations
    );
    s += &format!(
        "  matrix      {} x {} -> {} x {} after filtering, {} dependencies; {} square roots tried\n",
        r.linalg.rows_in,
        r.linalg.cols_in,
        r.linalg.rows_filtered,
        r.linalg.cols_filtered,
        r.linalg.dependencies,
        r.dependencies_tried
    );
    s += &format!(
        "  time        polyselect {:.2} s, sieve {:.2} s, linear algebra {:.2} s, sqrt {:.2} s, total {:.2} s\n",
        r.polyselect_seconds, r.sieve_seconds, r.linalg_seconds, r.sqrt_seconds, r.total_seconds
    );
    if let Some(f) = &r.failure {
        s += &format!("  failure     {f}\n");
    }
    s
}

#[derive(Args, Clone, Debug)]
pub struct GnfsArgs {
    /// The integer to split (an expression is accepted).
    pub n: String,
    /// Polynomial degree (default: 3 below 66 digits, then 4, 5).
    #[arg(long)]
    pub degree: Option<usize>,
    #[command(flatten)]
    pub nfs: NfsArgs,
}

pub fn run_gnfs(out: Out, a: &GnfsArgs) -> CmdResult {
    let n = parse_expr(&a.n)?;
    size_guard(&n, "gnfs", 65, a.nfs.force)?;
    let params = GnfsParams {
        degree: a.degree,
        nfs: a.nfs.params(),
        ..GnfsParams::default()
    };
    let pr = progress_printer(a.nfs.verbose);
    let r = factoring::gnfs(&n, &params, pr.as_ref().map(|f| f as &dyn Fn(&Progress)));
    out.emit(&r, || nfs_text(&r))?;
    verdict(r.verified, r.factor.is_some(), "gnfs")
}

#[derive(Args, Clone, Debug)]
pub struct SnfsArgs {
    /// The integer to split: n divides the special form.
    pub n: String,
    /// The special form (c*)r^e+s or (c*)r^e-s (default: n itself, if it
    /// is written in that form).
    #[arg(long, conflicts_with = "poly")]
    pub form: Option<String>,
    /// An explicit polynomial, coefficients from the constant term up:
    /// "c0,c1,...,cd"; needs --m.
    #[arg(long, requires = "m", allow_hyphen_values = true)]
    pub poly: Option<String>,
    /// The common root: f(m) = 0 (mod n).
    #[arg(long)]
    pub m: Option<String>,
    /// Polynomial degree for --form (default: chosen from the size).
    #[arg(long)]
    pub degree: Option<usize>,
    #[command(flatten)]
    pub nfs: NfsArgs,
}

pub fn run_snfs(out: Out, a: &SnfsArgs) -> CmdResult {
    let n = parse_expr(&a.n)?;
    let input = match (&a.form, &a.poly) {
        (Some(f), _) => parse_form(f)?,
        (None, Some(p)) => SnfsInput::Poly {
            coeffs: p
                .split(',')
                .map(|c| {
                    BigInt::parse_bytes(c.trim().as_bytes(), 10)
                        .ok_or_else(|| format!("bad coefficient {c:?}"))
                })
                .collect::<Result<_, _>>()?,
            m: parse_expr(a.m.as_deref().unwrap_or_default())?,
        },
        (None, None) => parse_form(&a.n).map_err(|_| {
            "give --form [c*]r^e+s (or --poly with --m), or write n itself as r^e+s".to_string()
        })?,
    };
    size_guard(&n, "snfs", 90, a.nfs.force)?;
    let params = SnfsParams {
        degree: a.degree,
        nfs: a.nfs.params(),
    };
    let pr = progress_printer(a.nfs.verbose);
    let r = factoring::snfs(
        &n,
        &input,
        &params,
        pr.as_ref().map(|f| f as &dyn Fn(&Progress)),
    );
    out.emit(&r, || nfs_text(&r))?;
    verdict(r.verified, r.factor.is_some(), "snfs")
}

// ---- quadratic sieve --------------------------------------------------------

#[derive(Args, Clone, Debug)]
pub struct QsArgs {
    /// The integer to split (an expression is accepted).
    pub n: String,
    /// Factor-base size (default: from the size of n).
    #[arg(long)]
    pub factor_base_size: Option<usize>,
    /// Knuth-Schroeppel multiplier (default: chosen automatically).
    #[arg(long)]
    pub multiplier: Option<u64>,
    #[arg(long, default_value_t = 1)]
    pub threads: usize,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    /// Stage progress on stderr.
    #[arg(long)]
    pub verbose: bool,
    /// Run even above the size this implementation is practical for.
    #[arg(long)]
    pub force: bool,
}

fn qs_text(r: &QsReport) -> String {
    let mut s = format!(
        "siqs: {}\n",
        split_line(&r.n, &r.factor, &r.cofactor, r.verified)
    );
    s += &format!(
        "  factor base {} primes up to {} (multiplier {}), {} polynomials from {} a-values\n",
        r.factor_base_size, r.largest_prime, r.multiplier, r.polynomials, r.a_values
    );
    s += &format!(
        "  relations   {} full, {} from partials; matrix {} x {}, {} dependencies\n",
        r.full_relations,
        r.partial_relations,
        r.linalg.rows_filtered,
        r.linalg.cols_filtered,
        r.linalg.dependencies
    );
    s += &format!(
        "  time        sieve {:.2} s, linear algebra {:.2} s, sqrt {:.2} s, total {:.2} s\n",
        r.sieve_seconds, r.linalg_seconds, r.sqrt_seconds, r.total_seconds
    );
    if let Some(f) = &r.failure {
        s += &format!("  failure     {f}\n");
    }
    s
}

pub fn run_qs(out: Out, a: &QsArgs) -> CmdResult {
    let n = parse_expr(&a.n)?;
    size_guard(&n, "qs", 75, a.force)?;
    let params = QsParams {
        factor_base_size: a.factor_base_size,
        multiplier: a.multiplier,
        threads: a.threads.max(1),
        seed: a.seed,
        ..QsParams::default()
    };
    let pr = progress_printer(a.verbose);
    let r = factoring::qs(&n, &params, pr.as_ref().map(|f| f as &dyn Fn(&Progress)));
    out.emit(&r, || qs_text(&r))?;
    verdict(r.verified, r.factor.is_some(), "qs")
}

// ---- ECM, p-1, p+1, rho ----------------------------------------------------

#[derive(Args, Clone, Debug)]
pub struct EcmArgs {
    pub n: String,
    /// Stage-1 bound.
    #[arg(long, default_value_t = 11_000)]
    pub b1: u64,
    /// Curves to try.
    #[arg(long, default_value_t = 64)]
    pub curves: u64,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
}

#[derive(Serialize)]
struct SplitReport {
    method: &'static str,
    n: String,
    factor: Option<String>,
    cofactor: Option<String>,
    verified: bool,
    seconds: f64,
    detail: String,
}

impl SplitReport {
    fn text(&self) -> String {
        let (n, f, c) = (
            self.n.parse::<BigUint>().unwrap_or_default(),
            self.factor.as_ref().and_then(|s| s.parse().ok()),
            self.cofactor.as_ref().and_then(|s| s.parse().ok()),
        );
        format!(
            "{}: {}\n  {} ({:.3} s)\n",
            self.method,
            split_line(&n, &f, &c, self.verified),
            self.detail,
            self.seconds
        )
    }
}

fn split(
    method: &'static str,
    n: &BigUint,
    f: Option<BigUint>,
    seconds: f64,
    detail: String,
) -> SplitReport {
    let f = f.filter(|f| !f.is_one() && f != n && (n % f).is_zero());
    let c = f.as_ref().map(|f| n / f);
    SplitReport {
        method,
        n: n.to_string(),
        verified: matches!((&f, &c), (Some(f), Some(c)) if &(f * c) == n),
        factor: f.map(|f| f.to_string()),
        cofactor: c.map(|c| c.to_string()),
        seconds,
        detail,
    }
}

pub fn run_ecm(out: Out, a: &EcmArgs) -> CmdResult {
    let n = parse_expr(&a.n)?;
    let t0 = std::time::Instant::now();
    let f = crate::cryptanalysis::ecm::ecm_factor(&n, a.b1, a.curves, a.seed);
    let r = split(
        "ecm",
        &n,
        f,
        t0.elapsed().as_secs_f64(),
        format!("B1 = {}, up to {} curves", a.b1, a.curves),
    );
    out.emit(&r, || r.text())?;
    verdict(r.verified, r.factor.is_some(), "ecm")
}

#[derive(Args, Clone, Debug)]
pub struct Pm1Args {
    pub n: String,
    /// Stage-1 bound.
    #[arg(long, default_value_t = 100_000)]
    pub b1: u64,
    /// Stage-2 bound.
    #[arg(long, default_value_t = 10_000_000)]
    pub b2: u64,
    /// Williams p+1 instead of Pollard p-1 (finds p when p+1 is smooth).
    #[arg(long)]
    pub pp1: bool,
}

pub fn run_pm1(out: Out, a: &Pm1Args) -> CmdResult {
    let n = parse_expr(&a.n)?;
    let r = if a.pp1 {
        factoring::pp1(
            &n,
            &Pp1Params {
                b1: a.b1,
                ..Pp1Params::default()
            },
        )
    } else {
        factoring::pm1(
            &n,
            &Pm1Params {
                b1: a.b1,
                b2: a.b2,
                ..Pm1Params::default()
            },
        )
    };
    let s = split(
        r.method,
        &n,
        r.factor.clone(),
        r.seconds,
        format!("B1 = {}, B2 = {}, found in stage {}", a.b1, a.b2, r.stage),
    );
    out.emit(&r, || s.text())?;
    verdict(r.verified, r.factor.is_some(), r.method)
}

#[derive(Args, Clone, Debug)]
pub struct RhoFactorArgs {
    pub n: String,
    /// Iterations per attempt.
    #[arg(long, default_value_t = 1 << 26)]
    pub iterations: u64,
}

pub fn run_rho_factor(out: Out, a: &RhoFactorArgs) -> CmdResult {
    let n = parse_expr(&a.n)?;
    let r = factoring::rho(
        &n,
        &RhoParams {
            max_iterations: a.iterations,
            ..RhoParams::default()
        },
    );
    let s = split(
        "pollard-brent-rho",
        &n,
        r.factor.clone(),
        r.seconds,
        format!("{} iterations", r.iterations),
    );
    out.emit(&r, || s.text())?;
    verdict(r.verified, r.factor.is_some(), "rho-factor")
}

// ---- RSA -------------------------------------------------------------------

#[derive(Subcommand, Clone, Debug)]
pub enum RsaCmd {
    /// Fermat's method: p and q close together.
    Fermat {
        n: String,
        #[arg(long, default_value_t = 1 << 24)]
        iterations: u64,
    },
    /// Wiener's continued-fraction attack: small private exponent d.
    Wiener {
        n: String,
        #[arg(long)]
        e: String,
    },
    /// Factor n from a known private exponent d.
    FromD {
        n: String,
        #[arg(long)]
        e: String,
        #[arg(long)]
        d: String,
    },
    /// Håstad's broadcast attack: one message, e moduli, public exponent e.
    Hastad {
        /// Public exponent.
        #[arg(long)]
        e: u32,
        /// Ciphertext:modulus pairs c:n (e of them).
        #[arg(required = true)]
        pairs: Vec<String>,
    },
    /// Common-modulus attack: one message under two exponents of one n.
    CommonModulus {
        #[arg(long)]
        n: String,
        #[arg(long)]
        e1: String,
        #[arg(long)]
        c1: String,
        #[arg(long)]
        e2: String,
        #[arg(long)]
        c2: String,
    },
    /// Small public exponent: m^e barely (or not) wrapped mod n.
    SmallE {
        #[arg(long)]
        n: String,
        #[arg(long)]
        e: u32,
        #[arg(long)]
        c: String,
        /// Try c + k n for k below this.
        #[arg(long, default_value_t = 1 << 16)]
        max_k: u64,
    },
    /// Shared primes across many moduli (product and remainder trees).
    BatchGcd {
        /// Moduli, or @file with one per line.
        #[arg(required = true)]
        moduli: Vec<String>,
    },
}

fn big(s: &str) -> Result<BigUint, String> {
    parse_expr(s)
}

pub fn run_rsa(out: Out, cmd: &RsaCmd) -> CmdResult {
    match cmd {
        RsaCmd::Fermat { n, iterations } => {
            let r = rsa_attacks::fermat(&big(n)?, *iterations);
            factor_attack(out, &r)
        }
        RsaCmd::Wiener { n, e } => factor_attack(out, &rsa_attacks::wiener(&big(n)?, &big(e)?)),
        RsaCmd::FromD { n, e, d } => factor_attack(
            out,
            &rsa_attacks::factor_from_private_exponent(&big(n)?, &big(e)?, &big(d)?, 1),
        ),
        RsaCmd::Hastad { e, pairs } => {
            let pairs = pairs
                .iter()
                .map(|p| {
                    let (c, n) = p
                        .split_once(':')
                        .ok_or_else(|| format!("expected c:n, got {p:?}"))?;
                    Ok((big(c)?, big(n)?))
                })
                .collect::<Result<Vec<_>, String>>()?;
            message_attack(out, &rsa_attacks::hastad_broadcast(*e, &pairs))
        }
        RsaCmd::CommonModulus { n, e1, c1, e2, c2 } => message_attack(
            out,
            &rsa_attacks::common_modulus(&big(n)?, &big(e1)?, &big(c1)?, &big(e2)?, &big(c2)?),
        ),
        RsaCmd::SmallE { n, e, c, max_k } => message_attack(
            out,
            &rsa_attacks::small_e_root(&big(c)?, *e, &big(n)?, *max_k),
        ),
        RsaCmd::BatchGcd { moduli } => {
            let mut ns = Vec::new();
            for m in moduli {
                if let Some(path) = m.strip_prefix('@') {
                    let text = std::fs::read_to_string(path)
                        .map_err(|e| format!("reading {path}: {e}"))?;
                    for line in text.lines().map(str::trim).filter(|l| !l.is_empty()) {
                        ns.push(big(line)?);
                    }
                } else {
                    ns.push(big(m)?);
                }
            }
            let r = rsa_attacks::batch_gcd(&ns);
            out.emit(&r, || {
                let mut s = format!(
                    "batch-gcd: {} of {} moduli share a prime ({:.3} s)\n",
                    r.factored.len(),
                    r.moduli,
                    r.seconds
                );
                for f in &r.factored {
                    s += &format!("  #{}: p = {}, q = {}\n", f.index, f.p, f.q);
                }
                if !r.duplicates.is_empty() {
                    s += &format!(
                        "  duplicate moduli (no gcd information): {:?}\n",
                        r.duplicates
                    );
                }
                s
            })
        }
    }
}

fn factor_attack(out: Out, r: &rsa_attacks::FactorAttackResult) -> CmdResult {
    out.emit(r, || {
        let mut s = format!(
            "{}: {} ({} iterations, {:.3} s)\n",
            r.attack,
            match (&r.p, &r.q) {
                (Some(p), Some(q)) => format!(
                    "n = {p} * {q} ({})",
                    if r.verified {
                        "verified"
                    } else {
                        "NOT VERIFIED"
                    }
                ),
                _ => "not factored".to_string(),
            },
            r.iterations,
            r.seconds
        );
        if let Some(d) = &r.d {
            s += &format!("  d = {d}\n");
        }
        s
    })?;
    verdict(r.verified, r.p.is_some(), r.attack)
}

fn message_attack(out: Out, r: &rsa_attacks::MessageAttackResult) -> CmdResult {
    out.emit(r, || {
        let mut s = format!(
            "{}: {} ({:.3} s)\n{}",
            r.attack,
            match &r.message {
                Some(m) => format!(
                    "m = {m} ({})",
                    if r.verified {
                        "verified: re-encrypts to the ciphertext"
                    } else {
                        "NOT VERIFIED"
                    }
                ),
                None => "message not recovered".to_string(),
            },
            r.seconds,
            if r.detail.is_empty() {
                String::new()
            } else {
                format!("  {}\n", r.detail)
            }
        );
        if let Some(m) = &r.message {
            let bytes = m.to_bytes_be();
            if bytes.iter().all(|b| b.is_ascii_graphic() || *b == b' ') {
                s += &format!("  as text: {}\n", String::from_utf8_lossy(&bytes));
            }
        }
        if let Some(f) = &r.factor_found {
            s += &format!("  a modulus factor turned up along the way: {f}\n");
        }
        s
    })?;
    verdict(r.verified, r.message.is_some(), r.attack)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn expressions_and_forms() {
        assert_eq!(parse_expr("2^10-1").unwrap(), BigUint::from(1023u32));
        assert_eq!(parse_expr("(2^5+1)/3").unwrap(), BigUint::from(11u32));
        assert_eq!(parse_expr("3*10^2 + 0x10").unwrap(), BigUint::from(316u32));
        assert_eq!(parse_expr("2^3^2").unwrap(), BigUint::from(512u32));
        assert!(parse_expr("7/2").is_err());
        assert!(parse_expr("1-2").is_err());
        assert!(parse_expr("2^").is_err());
        match parse_form("3*10^80+7").unwrap() {
            SnfsInput::Form { r, e, s, c } => assert_eq!((r, e, s, c), (10, 80, 7, 3)),
            _ => panic!(),
        }
        match parse_form("2^227-1").unwrap() {
            SnfsInput::Form { r, e, s, c } => assert_eq!((r, e, s, c), (2, 227, -1, 1)),
            _ => panic!(),
        }
        assert!(parse_form("12345").is_err());
    }

    #[test]
    fn every_command_factors_a_small_semiprime() {
        let out = Out { json: true };
        // 1000003 * 1000033: small enough for everything to be quick.
        let n = "1000036000099".to_string();
        run_factor(
            out,
            &FactorArgs {
                n: n.clone(),
                snfs_form: None,
                prefer_nfs: false,
                pp1: false,
                qs_max_digits: None,
                threads: 1,
                seed: 1,
            },
        )
        .unwrap();
        run_rho_factor(
            out,
            &RhoFactorArgs {
                n: n.clone(),
                iterations: 1 << 20,
            },
        )
        .unwrap();
        run_rsa(
            out,
            &RsaCmd::Fermat {
                n,
                iterations: 1 << 16,
            },
        )
        .unwrap();
    }

    #[test]
    fn qs_splits_a_30_digit_semiprime() {
        // 1000000000000037 * 100000000000031 (16 and 15 digits).
        let out = Out { json: true };
        run_qs(
            out,
            &QsArgs {
                n: "1000000000000037*100000000000031".into(),
                factor_base_size: None,
                multiplier: None,
                threads: 1,
                seed: 1,
                verbose: false,
                force: false,
            },
        )
        .unwrap();
    }
}
