//! `crax curve`: the C library's curve registry and structure detection.

use clap::{Args, Subcommand};
use serde::Serialize;

use super::output::{parse_u64, CmdResult, Out};

#[derive(Subcommand, Clone, Debug)]
pub enum CurveCmd {
    /// The named curves the generic solvers accept with `--curve`.
    Names,
    /// Group order, its factorisation, the endomorphism structure and the
    /// solver the library would pick.
    Info(CurveInfoArgs),
}

#[derive(Args, Clone, Debug)]
pub struct CurveInfoArgs {
    /// A registry curve.
    #[arg(long, conflicts_with_all = ["p", "a", "b"])]
    pub name: Option<String>,
    #[arg(long)]
    pub p: Option<String>,
    #[arg(long)]
    pub a: Option<String>,
    #[arg(long)]
    pub b: Option<String>,
    /// Subgroup order (default: the full group order, counted).
    #[arg(long)]
    pub order: Option<String>,
}

#[derive(Serialize)]
struct InfoReport {
    status: &'static str,
    p: String,
    a: String,
    b: String,
    group_order: String,
    factors: Vec<(String, u32)>,
    subgroup_order: String,
    endomorphism: String,
    aut_order: u32,
    beta: String,
    lambda: String,
    rho_speedup: f64,
    solver: &'static str,
}

pub fn run(out: Out, cmd: &CurveCmd) -> CmdResult {
    match cmd {
        CurveCmd::Names => {
            let names = libca::curve::names();
            out.emit(&names, || names.join("\n"))
        }
        CurveCmd::Info(a) => {
            let (p, ca, cb, named_order) = match &a.name {
                Some(n) => {
                    let (p, ca, cb, o) =
                        libca::curve::by_name(n).map_err(|e| format!("curve {n:?}: {e}"))?;
                    (p, ca, cb, Some(o))
                }
                None => (
                    parse_u64(a.p.as_deref().ok_or("--p or --name is required")?)?,
                    parse_u64(a.a.as_deref().unwrap_or("0"))?,
                    parse_u64(a.b.as_deref().ok_or("--b is required")?)?,
                    None,
                ),
            };
            let full = libca::Group::ec_count_points(p, ca, cb)
                .map_err(|e| format!("counting points: {e}"))?;
            let sub = match &a.order {
                Some(o) => parse_u64(o)?,
                None => named_order.unwrap_or(full),
            };
            let info = libca::curve::detect(p, ca, cb, sub).map_err(|e| e.to_string())?;
            let factors = libca::factorize(full);
            let report = InfoReport {
                status: "ok",
                p: p.to_string(),
                a: ca.to_string(),
                b: cb.to_string(),
                group_order: full.to_string(),
                factors: factors.iter().map(|&(q, e)| (q.to_string(), e)).collect(),
                subgroup_order: sub.to_string(),
                endomorphism: format!("{:?}", info.endo),
                aut_order: info.aut_order,
                beta: info.beta.to_string(),
                lambda: info.lambda.to_string(),
                rho_speedup: info.rho_speedup,
                solver: if info.aut_order > 2 {
                    "glv-rho"
                } else {
                    "rho (negation map)"
                },
            };
            out.emit(&report, || {
                format!(
                    "y^2 = x^3 + {ca} x + {cb} over F_{p}\n  #E = {full} = {}\n  subgroup order {sub}\n  endomorphism {} (|Aut| = {}), rho speed-up {:.4} -> {}\n",
                    factors
                        .iter()
                        .map(|&(q, e)| if e > 1 { format!("{q}^{e}") } else { q.to_string() })
                        .collect::<Vec<_>>()
                        .join(" * "),
                    report.endomorphism, info.aut_order, info.rho_speedup, report.solver
                )
            })
        }
    }
}
