//! `crax ic zp`: index calculus in `(Z/pZ)^*` on the C library.
//!
//! The Coppersmith-Odlyzko-Schroeppel linear sieve (`L_p[1/2, 1]`), with
//! Pohlig-Hellman for the small factors of `p - 1`, structured Gaussian
//! elimination and Lanczos for the large one, Hensel lifting, and every
//! factor-base logarithm verified. Primes below `2^63`.
//!
//! The elliptic-curve index-calculus tools (`crax ic ecdlp`, `crax ic run`,
//! ...) are the suite's; they are wired in beside this command.

use clap::{Args, ValueEnum};
use libca::index_calculus::{self, IcMethod, IcParams, IcStats};
use serde::Serialize;

use super::output::{parse_u64, CmdResult, Failure, Out};

/// Relation-collection method.
#[derive(Clone, Copy, Debug, ValueEnum)]
pub enum Method {
    /// Linear sieve, `L_p[1/2, 1]`.
    LinearSieve,
    /// Random exponents, `L_p[1/2, 2]`; kept for comparison.
    RandomExponent,
}

/// `crax ic zp`.
#[derive(Args, Clone, Debug)]
pub struct ZpArgs {
    /// An odd prime below 2^63.
    #[arg(long)]
    pub p: String,
    /// Base (default: the smallest primitive root).
    #[arg(long)]
    pub g: Option<String>,
    /// Target. Omit it and give --x to plant a known answer.
    #[arg(long)]
    pub h: Option<String>,
    /// Plant this secret: h = g^x mod p.
    #[arg(long, conflicts_with = "h")]
    pub x: Option<String>,
    #[arg(long, value_enum, default_value_t = Method::LinearSieve)]
    pub method: Method,
    /// Factor-base bound B (default: from the size of p).
    #[arg(long)]
    pub fb_bound: Option<u32>,
    /// Sieve radius C (default: from the size of p).
    #[arg(long)]
    pub sieve_radius: Option<u32>,
    /// Relations beyond the number of unknowns (default: automatic).
    #[arg(long)]
    pub extra_relations: Option<u32>,
    #[arg(long, default_value_t = 1)]
    pub threads: u32,
    #[arg(long, default_value_t = 1)]
    pub seed: u64,
    /// Stage reports on stderr.
    #[arg(long)]
    pub verbose: bool,
}

#[derive(Serialize)]
struct ZpReport {
    status: &'static str,
    algorithm: &'static str,
    p: String,
    g: String,
    h: String,
    x: String,
    verified: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    matches_planted: Option<bool>,
    factor_base_bound: u32,
    sieve_radius: u32,
    factor_base: u32,
    unknowns: u32,
    relations: u32,
    verified_logs: u32,
    sieve_seconds: f64,
    linalg_seconds: f64,
    total_seconds: f64,
    threads: u32,
}

pub fn run_zp(out: Out, a: &ZpArgs) -> CmdResult {
    let p = parse_u64(&a.p)?;
    if !(3..1 << 63).contains(&p) || !libca::is_prime(p) {
        return Err(format!("--p must be an odd prime below 2^63, got {p}").into());
    }
    let g = match &a.g {
        Some(s) => parse_u64(s)? % p,
        None => libca::primitive_root(p),
    };
    if g == 0 {
        return Err("--g must be a unit mod p".into());
    }
    let planted = a.x.as_deref().map(parse_u64).transpose()?;
    let h = match (&a.h, planted) {
        (Some(s), _) => parse_u64(s)? % p,
        (None, Some(x)) => libca::powmod(g, x, p),
        (None, None) => return Err("give --h, or --x to plant a target".into()),
    };
    if h == 0 {
        return Err("--h must be a unit mod p".into());
    }
    let (auto_b, auto_c) = index_calculus::auto_params(64 - p.leading_zeros());
    let params = IcParams {
        method: match a.method {
            Method::LinearSieve => IcMethod::LinearSieve,
            Method::RandomExponent => IcMethod::RandomExponent,
        },
        factor_base_bound: a.fb_bound.unwrap_or(0),
        sieve_radius: a.sieve_radius.unwrap_or(0),
        threads: a.threads.max(1),
        extra_relations: a.extra_relations.unwrap_or(0),
        seed: a.seed,
        verbose: a.verbose,
        ..IcParams::default()
    };
    let (x, st): (u64, IcStats) =
        index_calculus::solve(p, g, h, &params).map_err(|e| format!("ic zp: {e}"))?;
    let verified = libca::powmod(g, x, p) == h;
    let ord = p - 1;
    let report = ZpReport {
        status: if verified { "ok" } else { "unverified" },
        algorithm: "ic-zp-linear-sieve",
        p: p.to_string(),
        g: g.to_string(),
        h: h.to_string(),
        x: x.to_string(),
        verified,
        // Any x' = x (mod ord g) is a valid answer; compare the images.
        matches_planted: planted.map(|t| libca::powmod(g, t % ord, p) == libca::powmod(g, x, p)),
        factor_base_bound: a.fb_bound.unwrap_or(auto_b),
        sieve_radius: a.sieve_radius.unwrap_or(auto_c),
        factor_base: st.factor_base_size,
        unknowns: st.unknowns,
        relations: st.relations,
        verified_logs: st.verified_logs,
        sieve_seconds: st.sieve_seconds,
        linalg_seconds: st.linalg_seconds,
        total_seconds: st.total_seconds,
        threads: st.threads,
    };
    out.emit(&report, || {
        format!(
            "ic zp: x = {} ({})\n  p = {}, g = {}, h = {}\n  factor base {} primes (B = {}), {} unknowns, {} relations, {} logs verified\n  sieve {:.3} s, linear algebra {:.3} s, total {:.3} s\n",
            report.x,
            if verified { "verified: g^x = h" } else { "NOT VERIFIED" },
            p, g, h,
            st.factor_base_size, report.factor_base_bound, st.unknowns, st.relations, st.verified_logs,
            st.sieve_seconds, st.linalg_seconds, st.total_seconds
        )
    })?;
    if verified {
        Ok(())
    } else {
        Err(Failure::reported(
            "ic zp: the answer does not satisfy g^x = h",
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn solves_a_40_bit_planted_log() {
        let a = ZpArgs {
            p: "1099511627791".into(),
            g: Some("3".into()),
            h: None,
            x: Some("240852468320".into()),
            method: Method::LinearSieve,
            fb_bound: None,
            sieve_radius: None,
            extra_relations: None,
            threads: 1,
            seed: 1,
            verbose: false,
        };
        run_zp(Out { json: true }, &a).unwrap();
    }

    #[test]
    fn refuses_composite_moduli() {
        let a = ZpArgs {
            p: "1000001".into(),
            g: None,
            h: Some("5".into()),
            x: None,
            method: Method::LinearSieve,
            fb_bound: None,
            sieve_radius: None,
            extra_relations: None,
            threads: 1,
            seed: 1,
            verbose: false,
        };
        assert!(run_zp(Out { json: true }, &a).is_err());
    }
}
