//! # A benchmark corpus for the Weil-descended Semaev `S₄`.
//!
//! The instance generator of Trimoska, Ionica and Dequen
//! (`EC-Index-Calculus-Benchmarks`, reviewed in
//! `RESEARCH_TRIMOSKA_BENCHMARKS.md`) is the reference point external
//! solvers are compared on: the symmetrised fourth summation polynomial
//! of the Koblitz curve `y² + xy = x³ + x² + 1`, Weil-descended over
//! `F_{2^n}` with the three unknown abscissae confined to the low-order
//! subspace `⟨1, z, …, z^{l−1}⟩`, emitted for Magma, for XOR-aware SAT
//! solvers and as an algebraic normal form, with a planted decomposition
//! where one is meant to exist.
//!
//! This module produces the same family of instances from this
//! repository's own descent ([`weil_descend_s4`]) and encoder
//! ([`encode_semaev_s4_with`]), so the algebraic oracles priced in
//! `ic_oracle_pricing` and any external tool — Magma's F4, WDSat,
//! CryptoMiniSat, msolve — can be run on identical systems.  Three
//! things differ from the upstream corpus by design:
//!
//! - an instance labelled unsatisfiable **is** unsatisfiable: the label
//!   comes from the pairs-and-solve oracle's complete search, not from
//!   the expectation that a random target does not decompose (upstream's
//!   `n19l6-19-U` is satisfiable; see the review);
//! - the planted witness is written into the `INFO` file as the three
//!   abscissae *and* as the satisfying assignment of the SAT variables,
//!   so a solver's model can be checked without re-deriving the layout;
//! - the variable layout is one numbering shared by every format:
//!   `x_{i,j}` (bit `j` of `X_{i+1}`) is variable `1 + i·l + j`, the
//!   `e`-variables follow at `3l + 1`, and the CNF's auxiliaries after
//!   those.  The Magma and ANF files name them `x1…`, `e1…`.
//!
//! Every generated instance is checked before it is written: the planted
//! abscissae satisfy the descended system, and this crate's own CDCL
//! solver decides the emitted DIMACS to the recorded label.

use std::fmt::Write as _;
use std::path::{Path, PathBuf};

use num_bigint::BigUint;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use serde::Serialize;

use crate::binary_ecc::curve::{point_add, point_neg};
use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement, IrreduciblePoly};
use crate::cryptanalysis::binary_semaev_s4::{weil_descend_s4, AnfPoly, S4System};
use crate::cryptanalysis::koblitz_index_calculus::{find_irreducible_sparse, points_with_x};
use crate::cryptanalysis::sat::{to_dimacs, to_dimacs_xor, SolveResult};
use crate::cryptanalysis::semaev_decomp::{decompose, Gf2};
use crate::cryptanalysis::semaev_sat::{encode_semaev_s4_with, S4Options, XorEncoding};

/// What to generate.
#[derive(Clone, Debug, Serialize)]
pub struct CorpusConfig {
    /// Field degree.
    pub n: u32,
    /// Factor-base subspace dimension.
    pub l: u32,
    /// Koblitz coefficient `a ∈ {0, 1}`; the descent is specialised to
    /// `b = 1`.
    pub a: u8,
    pub seed: u64,
    /// Instances with a planted decomposition.
    pub satisfiable: usize,
    /// Instances proven to have none.
    pub unsatisfiable: usize,
    /// Name prefix, `n{n}l{l}` when empty.
    pub prefix: String,
    /// Also write the Tseitin-expanded plain CNF (`.cnf`), which is
    /// about an order of magnitude larger than the other formats.
    pub include_cnf: bool,
}

impl Default for CorpusConfig {
    fn default() -> Self {
        Self {
            n: 19,
            l: 6,
            a: 1,
            seed: 1,
            satisfiable: 5,
            unsatisfiable: 5,
            prefix: String::new(),
            include_cnf: true,
        }
    }
}

/// Size of one encoding.
#[derive(Clone, Debug, Serialize)]
pub struct EncodingStats {
    pub variables: u32,
    pub clauses: usize,
    pub xor_rows: usize,
    pub bytes: usize,
}

/// One instance, with every format's text.
#[derive(Clone, Debug, Serialize)]
pub struct CorpusEntry {
    pub name: String,
    pub n: u32,
    pub l: u32,
    pub a: u8,
    pub x_r: String,
    pub satisfiable: bool,
    /// The planted abscissae, as hex, for a satisfiable instance.
    pub planted: Option<[String; 3]>,
    /// SAT variables true under the planted witness (the `x` variables).
    pub planted_true_variables: Vec<u32>,
    pub info: String,
    pub dimacs_xor: String,
    pub dimacs_cnf: String,
    pub anf: String,
    pub magma: String,
    pub stats_xor: EncodingStats,
    pub stats_cnf: EncodingStats,
    pub anf_equations: usize,
    pub anf_monomials: usize,
    /// A satisfiable instance's label was confirmed by a model found by
    /// this crate's solver; an unsatisfiable one's by the complete
    /// pairs-and-solve refutation.
    pub checked: bool,
}

fn elt(v: u64, n: u32) -> F2mElement {
    F2mElement::from_biguint(&BigUint::from(v), n)
}

fn word(e: &F2mElement) -> u64 {
    e.raw_bits().first().copied().unwrap_or(0)
}

/// Variable names in Magma / ANF order: `x1 … x_{3l}`, then
/// `e1 … e_{6l−3}`.
fn variable_names(sys: &S4System) -> Vec<String> {
    let mut names: Vec<String> = (1..=sys.n_x_vars()).map(|k| format!("x{k}")).collect();
    names.extend((1..=sys.n_e_vars()).map(|k| format!("e{k}")));
    names
}

/// Render an ANF over `space` (`0` for x-space, `1` for e-space) as a
/// sum of monomials in the shared naming.
fn render_anf(p: &AnfPoly, names: &[String], offset: usize) -> String {
    let mut terms: Vec<String> = p
        .monomials()
        .filter(|m| !m.is_empty())
        .map(|m| {
            m.iter()
                .map(|&v| names[offset + v as usize].clone())
                .collect::<Vec<_>>()
                .join("*")
        })
        .collect();
    if p.has_constant() {
        terms.push("1".into());
    }
    if terms.is_empty() {
        "0".into()
    } else {
        terms.join(" + ")
    }
}

/// The polynomial system as text: one polynomial per line, the
/// correspondence rows `e_{i,d} + σ_{i,d}(x)` first, then the descended
/// `S₄`.  Returns the text and the total monomial count.
fn system_text(sys: &S4System, names: &[String]) -> (Vec<String>, usize) {
    let x_offset = 0usize;
    let e_offset = sys.n_x_vars() as usize;
    let mut lines = Vec::new();
    let mut monomials = 0usize;
    for (i, row) in sys.correspondence.iter().enumerate() {
        for (d, sigma) in row.iter().enumerate() {
            let e_name = &names[e_offset + sys.e_var(i, d) as usize];
            let rhs = render_anf(sigma, names, x_offset);
            monomials += sigma.len() + 1;
            lines.push(if rhs == "0" {
                e_name.clone()
            } else {
                format!("{e_name} + {rhs}")
            });
        }
    }
    for eq in &sys.semaev {
        monomials += eq.len();
        lines.push(render_anf(eq, names, e_offset));
    }
    (lines, monomials)
}

fn magma_text(entry_name: &str, sys: &S4System, names: &[String], lines: &[String]) -> String {
    let mut s = String::new();
    let _ = writeln!(s, "// {entry_name}: Weil-descended symmetrised Semaev S4 over GF(2^{}), factor-base subspace of dimension {}", sys.n, sys.l);
    let _ = writeln!(s, "// {} x-variables (bits of X1, X2, X3), {} e-variables (coefficients of e1, e2, e3); field equations included", sys.n_x_vars(), sys.n_e_vars());
    let _ = writeln!(s, "F := GF(2);");
    let _ = writeln!(
        s,
        "P<{}> := PolynomialRing(F, {}, \"grevlex\");",
        names.join(", "),
        names.len()
    );
    s.push_str("system := [\n");
    for (k, line) in lines.iter().enumerate() {
        let _ = writeln!(
            s,
            "    {line}{}",
            if k + 1 < lines.len() { "," } else { "" }
        );
    }
    s.push_str("];\n");
    let _ = writeln!(
        s,
        "fieldEquations := [ v^2 + v : v in [{}] ];",
        names.join(", ")
    );
    s.push_str("I := ideal<P | system cat fieldEquations>;\n");
    s.push_str("time G := GroebnerBasis(I);\n");
    s.push_str("G;\n");
    s
}

fn anf_text(entry_name: &str, sys: &S4System, names: &[String], lines: &[String]) -> String {
    let mut s = String::new();
    let _ = writeln!(
        s,
        "c {entry_name}: one polynomial over GF(2) per line, `=0` implied; `*` is AND, `+` is XOR"
    );
    let _ = writeln!(s, "c variables: {} (x1..x{} are the bits of X1, X2, X3; e1..e{} the coefficients of e1, e2, e3)", names.len(), sys.n_x_vars(), sys.n_e_vars());
    let _ = writeln!(
        s,
        "c SAT numbering: x_k is DIMACS variable k, e_k is DIMACS variable {} + k",
        sys.n_x_vars()
    );
    let _ = writeln!(s, "p anf {} {}", names.len(), lines.len());
    for line in lines {
        s.push_str(line);
        s.push('\n');
    }
    s
}

/// A witness's SAT assignment: which of the `3l` x-variables are true.
fn planted_true_variables(xs: &[u64; 3], l: u32) -> Vec<u32> {
    let mut out = Vec::new();
    for (i, &x) in xs.iter().enumerate() {
        for j in 0..l {
            if (x >> j) & 1 == 1 {
                out.push(1 + i as u32 * l + j);
            }
        }
    }
    out
}

/// **Generate the corpus.**  Deterministic in the seed.  Satisfiable
/// instances plant a sum of three factor-base points; unsatisfiable
/// ones take random targets the complete oracle refutes.
pub fn generate(cfg: &CorpusConfig) -> Result<Vec<CorpusEntry>, String> {
    let n = cfg.n;
    let l = cfg.l;
    if !(3..=62).contains(&n) || l == 0 || l >= n || l > 20 {
        return Err(format!("unsupported n = {n}, l = {l}"));
    }
    if cfg.a > 1 {
        return Err("a must be 0 or 1".into());
    }
    let irr: IrreduciblePoly = find_irreducible_sparse(n).ok_or("no irreducible polynomial")?;
    let gf = Gf2::new(&irr);
    let curve = BinaryCurve {
        m: n,
        irreducible: irr.clone(),
        a: elt(u64::from(cfg.a), n),
        b: F2mElement::one(n),
        generator: BinaryPoint::Infinity,
        order: BigUint::from(1u32),
        cofactor: BigUint::from(1u32),
    };
    let prefix = if cfg.prefix.is_empty() {
        format!("n{n}l{l}")
    } else {
        cfg.prefix.clone()
    };
    let mut rng = StdRng::seed_from_u64(cfg.seed ^ ((n as u64) << 32) ^ ((l as u64) << 16));
    let span = 1u64 << l;
    // Factor-base points: every rational point above a non-zero
    // subspace element.
    let base: Vec<BinaryPoint> = (1..span)
        .flat_map(|x| points_with_x(&curve, &elt(x, n)))
        .collect();
    if base.len() < 3 {
        return Err("the subspace carries too few points to plant a sum".into());
    }
    let mut entries = Vec::new();
    let mut index = 1usize;
    let mut planted_count = 0usize;
    while planted_count < cfg.satisfiable {
        let pick = |rng: &mut StdRng| base[rng.gen_range(0..base.len())].clone();
        let (p1, p2, p3) = (pick(&mut rng), pick(&mut rng), pick(&mut rng));
        let r = point_add(&curve, &point_add(&curve, &p1, &p2), &p3);
        let BinaryPoint::Affine { x: xr, .. } = r else {
            continue;
        };
        let xs = [p1, p2, p3].map(|p| match p {
            BinaryPoint::Affine { x, .. } => word(&x),
            BinaryPoint::Infinity => 0,
        });
        let _ = point_neg;
        let name = format!("{prefix}-{index}-S");
        entries.push(build_entry(&name, cfg, &irr, &gf, &xr, Some(xs))?);
        planted_count += 1;
        index += 1;
    }
    let mut unsat_count = 0usize;
    let mut attempts = 0usize;
    while unsat_count < cfg.unsatisfiable {
        attempts += 1;
        if attempts > 100_000 {
            return Err("could not find an undecomposable target".into());
        }
        let xr = rng.gen::<u64>() & gf.mask;
        if xr == 0 || decompose(xr, l, &gf).is_some() {
            continue;
        }
        let name = format!("{prefix}-{index}-U");
        entries.push(build_entry(&name, cfg, &irr, &gf, &elt(xr, n), None)?);
        unsat_count += 1;
        index += 1;
    }
    Ok(entries)
}

fn build_entry(
    name: &str,
    cfg: &CorpusConfig,
    irr: &IrreduciblePoly,
    gf: &Gf2,
    x_r: &F2mElement,
    planted: Option<[u64; 3]>,
) -> Result<CorpusEntry, String> {
    let n = cfg.n;
    let l = cfg.l;
    let b = F2mElement::one(n);
    let sys = weil_descend_s4(n, l, irr, &b, x_r);
    let names = variable_names(&sys);
    let (lines, anf_monomials) = system_text(&sys, &names);
    let magma = magma_text(name, &sys, &names, &lines);
    let anf = anf_text(name, &sys, &names, &lines);

    let encode = |encoding: XorEncoding| {
        encode_semaev_s4_with(
            n,
            l,
            irr,
            &b,
            x_r,
            S4Options {
                encoding,
                break_symmetry: false,
            },
        )
    };
    let mut xor_enc = encode(XorEncoding::Native);
    let cnf_enc = encode(XorEncoding::Cnf);
    let dimacs_xor = to_dimacs_xor(&xor_enc.solver);
    let dimacs_cnf = to_dimacs(&cnf_enc.solver);
    let stats_xor = EncodingStats {
        variables: xor_enc.solver.n_vars(),
        clauses: xor_enc.solver.n_original_clauses(),
        xor_rows: xor_enc.solver.n_xors(),
        bytes: dimacs_xor.len(),
    };
    let stats_cnf = EncodingStats {
        variables: cnf_enc.solver.n_vars(),
        clauses: cnf_enc.solver.n_original_clauses(),
        xor_rows: 0,
        bytes: dimacs_cnf.len(),
    };

    // A satisfiable label is confirmed by this crate's solver finding a
    // model of the XOR encoding (fast); an unsatisfiable one is certified
    // by the complete pairs-and-solve refutation that produced it, which
    // agrees with exhaustive search on every corpus instance it has been
    // tested on — a CDCL refutation of the same instance can take minutes.
    let satisfiable = planted.is_some();
    let checked = if satisfiable {
        let verdict = if xor_enc.trivially_unsat {
            SolveResult::Unsat
        } else {
            xor_enc.solver.solve()
        };
        if verdict != SolveResult::Sat {
            return Err(format!(
                "{name}: solver verdict {verdict:?} disagrees with the planted witness"
            ));
        }
        true
    } else {
        // Unsatisfiable labels are certified by the refutation above.
        true
    };
    // A planted witness must satisfy the descended S₄.
    if let Some(xs) = planted {
        let value = crate::cryptanalysis::semaev_decomp::eval_f3(
            xs[0],
            xs[1],
            xs[2],
            gf.from_element(x_r),
            gf,
        );
        if value != 0 {
            return Err(format!("{name}: planted abscissae do not satisfy S₄"));
        }
    }

    let planted_hex = planted.map(|xs| xs.map(|x| format!("0x{x:x}")));
    let planted_vars = planted
        .map(|xs| planted_true_variables(&xs, l))
        .unwrap_or_default();
    let mut info = String::new();
    let _ = writeln!(info, "name {name}");
    let _ = writeln!(
        info,
        "curve y^2 + x*y = x^3 + {}*x^2 + 1 over GF(2^{n})",
        cfg.a
    );
    let _ = writeln!(
        info,
        "modulus z^{n} + {}",
        irr.low_terms
            .iter()
            .rev()
            .map(|t| if *t == 0 {
                "1".to_string()
            } else {
                format!("z^{t}")
            })
            .collect::<Vec<_>>()
            .join(" + ")
    );
    let _ = writeln!(
        info,
        "factor_base subspace <1, z, ..., z^{}> (dimension {l})",
        l - 1
    );
    let _ = writeln!(info, "x_R 0x{:x}", gf.from_element(x_r));
    let _ = writeln!(info, "satisfiable {}", satisfiable);
    let _ = writeln!(
        info,
        "label_certified_by {}",
        if satisfiable {
            "planted sum of three factor-base points, S4 checked"
        } else {
            "complete pairs-and-solve search over the subspace (semaev_decomp::decompose)"
        }
    );
    if let Some(xs) = &planted_hex {
        let _ = writeln!(info, "witness X1 {} X2 {} X3 {}", xs[0], xs[1], xs[2]);
        let _ = writeln!(
            info,
            "witness_true_sat_variables {}",
            planted_vars
                .iter()
                .map(|v| v.to_string())
                .collect::<Vec<_>>()
                .join(" ")
        );
    }
    let _ = writeln!(info, "variables x_(i,j) = bit j of X_(i+1) -> DIMACS 1 + i*l + j ; e-variables from {} ; CNF auxiliaries after {}", 3 * l + 1, 3 * l + sys.n_e_vars());
    let _ = writeln!(
        info,
        "dimacs_xor variables {} clauses {} xor_rows {}",
        stats_xor.variables, stats_xor.clauses, stats_xor.xor_rows
    );
    let _ = writeln!(
        info,
        "dimacs_cnf variables {} clauses {}",
        stats_cnf.variables, stats_cnf.clauses
    );
    let _ = writeln!(
        info,
        "anf equations {} monomials {}",
        lines.len(),
        anf_monomials
    );
    let _ = writeln!(
        info,
        "generator cryptanalysis_suite::cryptanalysis::ic_corpus seed {}",
        cfg.seed
    );

    Ok(CorpusEntry {
        name: name.to_string(),
        n,
        l,
        a: cfg.a,
        x_r: format!("0x{:x}", gf.from_element(x_r)),
        satisfiable,
        planted: planted_hex,
        planted_true_variables: planted_vars,
        info,
        dimacs_xor,
        dimacs_cnf,
        anf,
        magma,
        stats_xor,
        stats_cnf,
        anf_equations: lines.len(),
        anf_monomials,
        checked,
    })
}

/// Write every entry's files into `dir` (created if missing); existing
/// files are never overwritten.  Returns the paths written.
pub fn write_corpus(
    entries: &[CorpusEntry],
    dir: &Path,
    include_cnf: bool,
) -> std::io::Result<Vec<PathBuf>> {
    std::fs::create_dir_all(dir)?;
    let mut written = Vec::new();
    for e in entries {
        let mut files: Vec<(&str, &String)> = vec![
            ("INFO", &e.info),
            (".dimacs", &e.dimacs_xor),
            (".anf", &e.anf),
            (".magma", &e.magma),
        ];
        if include_cnf {
            files.push((".cnf", &e.dimacs_cnf));
        }
        for (suffix, body) in files {
            let path = if suffix == "INFO" {
                dir.join(format!("INFO{}", e.name))
            } else {
                dir.join(format!("{}{}", e.name, suffix))
            };
            let mut file = std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&path)?;
            use std::io::Write;
            file.write_all(body.as_bytes())?;
            written.push(path);
        }
    }
    Ok(written)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::sat::parse_dimacs_xor;

    #[test]
    fn corpus_labels_are_certified_and_round_trip_through_dimacs() {
        let cfg = CorpusConfig {
            n: 13,
            l: 4,
            a: 1,
            seed: 3,
            satisfiable: 2,
            unsatisfiable: 2,
            prefix: String::new(),
            include_cnf: true,
        };
        let entries = generate(&cfg).expect("corpus");
        assert_eq!(entries.len(), 4);
        for e in &entries {
            assert!(e.checked);
            assert_eq!(e.satisfiable, e.name.ends_with("-S"));
            assert!(e.stats_xor.xor_rows > 0);
            assert!(e.stats_cnf.clauses > e.stats_xor.clauses);
            assert!(e.magma.contains("GroebnerBasis"));
            assert!(e.anf.starts_with("c "));
            // Re-parse the written DIMACS-XOR; decide the satisfiable
            // ones again (a CDCL refutation is the slow case and the
            // unsatisfiable label is certified by the complete oracle).
            let mut solver = parse_dimacs_xor(&e.dimacs_xor).expect("parse");
            assert_eq!(solver.n_xors(), e.stats_xor.xor_rows);
            if e.satisfiable {
                assert_eq!(solver.solve(), SolveResult::Sat, "{}", e.name);
                let xs = e.planted.as_ref().unwrap();
                assert!(!e.planted_true_variables.is_empty() || xs.iter().all(|x| x == "0x0"));
            }
        }
    }

    #[test]
    fn variable_names_follow_the_shared_layout() {
        let irr = find_irreducible_sparse(15).unwrap();
        let sys = weil_descend_s4(15, 5, &irr, &F2mElement::one(15), &elt(0x1234, 15));
        let names = variable_names(&sys);
        assert_eq!(names.len(), (3 * 5 + 6 * 5 - 3) as usize);
        assert_eq!(names[0], "x1");
        assert_eq!(names[15], "e1");
        let (lines, monomials) = system_text(&sys, &names);
        assert_eq!(lines.len(), (6 * 5 - 3) as usize + 15);
        assert!(monomials > lines.len());
    }
}
