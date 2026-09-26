//! Trimoska [WDSat](https://github.com/mtrimoska/WDSat) as a point-decomposition
//! oracle for Koblitz index calculus on prime-degree extension fields.
//!
//! The algebraic system is the same Semaev / Weil-restriction instance the
//! native [`crate::cryptanalysis::koblitz_index_calculus::sat_decompose`]
//! path builds.  This module emits it in the ANF format WDSat expects
//! (matching `mtrimoska/EC-Index-Calculus-Benchmarks`), shells out to a
//! WDSat binary, and lifts any model through the existing group check.
//!
//! ECC2K-130 lives in this family: `n = 131` is prime, the curve is Koblitz
//! `K_0`, and the decomposition question is identical.  WDSat's static
//! allocation and the free-oracle floor in
//! [`RESEARCH_ECC2K130_DECOMPOSITION.md`](../../RESEARCH_ECC2K130_DECOMPOSITION.md)
//! still bound full-size runs; the unification is the shared oracle API on
//! the measured prime-degree ladder.

use crate::binary_ecc::{BinaryPoint, F2mElement};
use crate::cryptanalysis::koblitz_groebner::FieldStructure;
use crate::cryptanalysis::koblitz_index_calculus::{
    lift_candidate, FrobeniusFactorBase, KoblitzCurve, SatDecompositionStats,
};
use crate::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use num_bigint::BigUint;
use std::collections::HashMap;
use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

/// One ANF equation in the Trimoska / WDSat row format.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AnfRow {
    /// Square-free monomials as zero-based variable ids.
    pub monomials: Vec<Vec<u32>>,
    /// Whether the polynomial has a constant term `1`.
    pub constant: bool,
}

impl AnfRow {
    /// Convert a Boolean polynomial into an ANF row.
    pub fn from_poly(poly: &F2BoolPoly) -> Self {
        let mut monomials = Vec::new();
        let mut constant = false;
        for term in &poly.terms {
            if term.mask == 0 {
                constant = !constant;
                continue;
            }
            let mut vars: Vec<u32> = (0..64).filter(|i| (term.mask >> i) & 1 == 1).collect();
            vars.sort_unstable();
            monomials.push(vars);
        }
        Self {
            monomials,
            constant,
        }
    }
}

/// Format ANF rows exactly as WDSat and the Trimoska corpus expect.
pub fn format_anf(n_vars: u32, rows: &[AnfRow]) -> String {
    let active: Vec<&AnfRow> = rows
        .iter()
        .filter(|row| row.constant || !row.monomials.is_empty())
        .collect();
    let mut out = format!("p cnf {n_vars} {}\n", active.len());
    for row in active {
        out.push('x');
        for monomial in &row.monomials {
            if monomial.len() > 1 {
                out.push_str(&format!(" .{}", monomial.len()));
            }
            for variable in monomial {
                out.push_str(&format!(" {}", variable + 1));
            }
        }
        // WDSat ANF rows have odd parity.  Emit `T` exactly when the
        // polynomial's constant is zero so the remaining terms equal 0.
        if !row.constant {
            out.push_str(" T");
        }
        out.push_str(" 0\n");
    }
    out
}

/// Capacity hints derived from one ANF instance (for `config.h`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct WdsatCapacity {
    pub max_anf_id: u32,
    pub max_degree_plus_one: u32,
    pub max_eq: u32,
    pub xor_atom_count: u32,
}

/// Suggest static WDSat allocation bounds from an ANF file body.
pub fn suggest_capacity(anf: &str) -> WdsatCapacity {
    let mut max_degree = 1u32;
    let mut equations = 0u32;
    let mut xor_atoms = 0u32;
    let mut n_vars = 0u32;
    for (index, line) in anf.lines().enumerate() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if index == 0 {
            let parts: Vec<_> = line.split_whitespace().collect();
            if parts.len() >= 4 {
                n_vars = parts[2].parse().unwrap_or(0);
            }
            continue;
        }
        equations += 1;
        let tokens: Vec<_> = line.split_whitespace().collect();
        let mut i = 1usize; // skip leading `x`
        while i + 1 < tokens.len() {
            let token = tokens[i];
            if token == "T" {
                i += 1;
            } else if let Some(rest) = token.strip_prefix('.') {
                let degree: u32 = rest.parse().unwrap_or(1);
                max_degree = max_degree.max(degree);
                xor_atoms += 1;
                i += degree as usize + 1;
            } else {
                max_degree = max_degree.max(1);
                xor_atoms += 1;
                i += 1;
            }
        }
    }
    WdsatCapacity {
        max_anf_id: n_vars.saturating_add(1),
        max_degree_plus_one: max_degree.saturating_add(1),
        max_eq: equations.saturating_add(8),
        xor_atom_count: xor_atoms,
    }
}

/// Parse the first 0/1 model line WDSat prints.
pub fn parse_wdsat_model(stdout: &str, n_vars: usize) -> Option<Vec<bool>> {
    for line in stdout.lines() {
        let value = line.trim();
        if value.len() >= n_vars && value.bytes().all(|b| b == b'0' || b == b'1') {
            return Some(
                value.as_bytes()[..n_vars]
                    .iter()
                    .map(|b| *b == b'1')
                    .collect(),
            );
        }
    }
    None
}

/// Evaluate every ANF equation on a model (export convention for `T`).
pub fn validate_anf(anf: &str, model: &[bool]) -> bool {
    for (index, line) in anf.lines().enumerate() {
        let line = line.trim();
        if index == 0 || line.is_empty() {
            continue;
        }
        let tokens: Vec<_> = line.split_whitespace().collect();
        if tokens.is_empty() {
            continue;
        }
        let mut monomials: Vec<Vec<usize>> = Vec::new();
        let mut has_t = false;
        let mut i = 1usize;
        while i < tokens.len() {
            let token = tokens[i];
            if token == "0" {
                break;
            }
            if token == "T" {
                has_t = true;
                i += 1;
            } else if let Some(rest) = token.strip_prefix('.') {
                let degree: usize = match rest.parse() {
                    Ok(d) => d,
                    Err(_) => return false,
                };
                if i + degree >= tokens.len() {
                    return false;
                }
                let mut mono = Vec::with_capacity(degree);
                for tok in &tokens[i + 1..=i + degree] {
                    let var: usize = match tok.parse::<usize>() {
                        Ok(v) if v >= 1 => v - 1,
                        _ => return false,
                    };
                    mono.push(var);
                }
                monomials.push(mono);
                i += degree + 1;
            } else {
                let var: usize = match token.parse::<usize>() {
                    Ok(v) if v >= 1 => v - 1,
                    _ => return false,
                };
                monomials.push(vec![var]);
                i += 1;
            }
        }
        let mut parity = !has_t;
        for monomial in &monomials {
            if monomial
                .iter()
                .all(|&v| model.get(v).copied().unwrap_or(false))
            {
                parity = !parity;
            }
        }
        if parity {
            return false;
        }
    }
    true
}

fn model_to_u64(model: &[bool]) -> Option<u64> {
    if model.len() > 64 {
        return None;
    }
    let mut root = 0u64;
    for (i, bit) in model.iter().enumerate() {
        if *bit {
            root |= 1u64 << i;
        }
    }
    Some(root)
}

/// How to invoke an external WDSat binary.
#[derive(Clone, Debug)]
pub struct WdsatSolveOptions {
    /// Path to `wdsat_solver`.
    pub binary: PathBuf,
    /// Optional working directory for the child process.
    pub work_dir: Option<PathBuf>,
    /// Soft wall-clock budget for the child.
    pub timeout: Duration,
    /// Keep the generated ANF under this path instead of a temporary file.
    pub keep_anf: Option<PathBuf>,
}

/// Run WDSat on a pre-built ANF string.
pub fn run_wdsat(
    anf: &str,
    _n_vars: u32,
    branch_vars: &[u32],
    options: &WdsatSolveOptions,
) -> Result<(String, String, Duration), String> {
    let anf_path = if let Some(path) = &options.keep_anf {
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("create ANF parent: {e}"))?;
        }
        fs::write(path, anf).map_err(|e| format!("write ANF {}: {e}", path.display()))?;
        path.clone()
    } else {
        let dir = options.work_dir.clone().unwrap_or_else(std::env::temp_dir);
        fs::create_dir_all(&dir).map_err(|e| format!("create work dir: {e}"))?;
        let path = dir.join(format!("wdsat-ic-{}.anf", std::process::id()));
        fs::write(&path, anf).map_err(|e| format!("write temp ANF: {e}"))?;
        path
    };

    let branch = branch_vars
        .iter()
        .map(|v| v.to_string())
        .collect::<Vec<_>>()
        .join(",");
    let started = Instant::now();
    let mut child = Command::new(&options.binary)
        .arg("-i")
        .arg(&anf_path)
        .arg("-g")
        .arg(&branch)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("spawn WDSat {}: {e}", options.binary.display()))?;

    let deadline = started + options.timeout;
    loop {
        match child.try_wait() {
            Ok(Some(_)) => break,
            Ok(None) if Instant::now() >= deadline => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(format!(
                    "WDSat timed out after {} ms",
                    options.timeout.as_millis()
                ));
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(5)),
            Err(e) => return Err(format!("wait WDSat: {e}")),
        }
    }
    let output = child
        .wait_with_output()
        .map_err(|e| format!("collect WDSat output: {e}"))?;
    let elapsed = started.elapsed();
    if options.keep_anf.is_none() {
        let _ = fs::remove_file(&anf_path);
    }
    if !output.status.success() {
        return Err(format!("WDSat exited with status {}", output.status));
    }
    Ok((
        String::from_utf8_lossy(&output.stdout).into_owned(),
        String::from_utf8_lossy(&output.stderr).into_owned(),
        elapsed,
    ))
}

/// The first recognized line is decisive. Upstream WDSat 61c6ff3 prints
/// `UNSAT` before its decimal conflict counter, which may itself contain
/// only 0/1 digits; find-all mode can instead print a model before a terminal
/// `UNSAT`. Successful empty output has no documented UNSAT meaning.
#[derive(Debug, PartialEq, Eq)]
enum WdsatStdoutVerdict {
    Model(Vec<bool>),
    Unsat,
    Unknown,
}

fn parse_wdsat_stdout(stdout: &str, n_vars: usize) -> WdsatStdoutVerdict {
    for line in stdout.lines() {
        let value = line.trim();
        if matches!(value, "UNSAT" | "UNSAT on XORGAUSS init") {
            return WdsatStdoutVerdict::Unsat;
        }
        if !value.is_empty() {
            if let Some(model) = parse_wdsat_model(value, n_vars) {
                return WdsatStdoutVerdict::Model(model);
            }
        }
    }
    WdsatStdoutVerdict::Unknown
}

/// Solve one Semaev decomposition instance with an external WDSat binary.
///
/// Returns the same shape as [`crate::cryptanalysis::koblitz_index_calculus::sat_decompose`]:
/// lifted factor-base indices plus solver accounting. A successful child
/// with an explicit upstream UNSAT marker is a refutation; empty output,
/// nonzero exit, timeout or capacity failure is reported as exhausted.
pub fn wdsat_decompose(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    index_of: &HashMap<(BigUint, BigUint), usize>,
    st: &FieldStructure,
    target: &BinaryPoint,
    m: usize,
    options: &WdsatSolveOptions,
) -> (Option<Vec<usize>>, SatDecompositionStats) {
    let mut stats = SatDecompositionStats::default();
    let x_r = match target {
        BinaryPoint::Affine { x, .. } => x.clone(),
        BinaryPoint::Infinity => return (None, stats),
    };
    let sys = match crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing(
        &fb.subspace_basis,
        &x_r,
        &kc.curve.b,
        m,
        st,
    ) {
        Some(sys) => sys,
        None => {
            stats.exhausted = true;
            return (None, stats);
        }
    };

    let rows: Vec<AnfRow> = sys.equations.iter().map(AnfRow::from_poly).collect();
    let anf = format_anf(sys.n_vars as u32, &rows);
    let ell = fb.subspace_basis.len() as u32;
    let branch: Vec<u32> = (1..=(m as u32 * ell)).collect();

    stats.solver_calls = 1;
    let (stdout, stderr, _elapsed) = match run_wdsat(&anf, sys.n_vars as u32, &branch, options) {
        Ok(result) => result,
        Err(_) => {
            stats.exhausted = true;
            return (None, stats);
        }
    };
    if stderr.contains("not enough")
        || stderr.contains("buffer") && stderr.to_lowercase().contains("error")
        || stdout.contains("FATAL")
        || stderr.contains("FATAL")
    {
        stats.exhausted = true;
        return (None, stats);
    }

    let model = match parse_wdsat_stdout(&stdout, sys.n_vars) {
        WdsatStdoutVerdict::Model(model) => model,
        WdsatStdoutVerdict::Unsat => {
            stats.refuted = true;
            return (None, stats);
        }
        WdsatStdoutVerdict::Unknown => {
            stats.exhausted = true;
            return (None, stats);
        }
    };

    if !validate_anf(&anf, &model) {
        stats.spurious += 1;
        stats.exhausted = true;
        return (None, stats);
    }
    let root = match model_to_u64(&model) {
        Some(root) => root,
        None => {
            stats.exhausted = true;
            return (None, stats);
        }
    };
    if !sys.equations.iter().all(|e| e.eval(root) == 0) {
        stats.spurious += 1;
        stats.exhausted = true;
        return (None, stats);
    }
    stats.models = 1;
    let xs: Vec<F2mElement> = (0..m)
        .map(|i| sys.summand_x(&fb.subspace_basis, root, i, kc.n))
        .collect();
    if let Some(idxs) = lift_candidate(kc, fb, index_of, &xs, target) {
        (Some(idxs), stats)
    } else {
        // A model that fails to lift is not a point decomposition; treat
        // as exhausted rather than a proved refutation.
        stats.exhausted = true;
        (None, stats)
    }
}

/// Write a minimal `config.h` sized for one ANF instance.
pub fn write_config_for_anf(anf: &str, path: &Path) -> Result<WdsatCapacity, String> {
    let cap = suggest_capacity(anf);
    let body = format!(
        r#"#define __XG_ENHANCED__
#ifdef __XG_ENHANCED__
#define __MAX_ANF_ID__ {anf_id}
#define __MAX_DEGREE__ {deg}
#endif
#define __MAX_ID__ {id}
#define __MAX_BUFFER_SIZE__ {buf}
#define __MAX_EQ__ {eq}
#define __MAX_EQ_SIZE__ {eqs}
#define __MAX_XEQ__ {xeq}
#define __MAX_XEQ_SIZE__ {xeqs}
"#,
        anf_id = cap.max_anf_id.max(8),
        deg = cap.max_degree_plus_one.max(3),
        id = (cap.xor_atom_count.saturating_mul(4) + cap.max_anf_id + 64).max(64),
        buf = (cap.xor_atom_count.saturating_mul(64) + 5000).max(5000),
        eq = cap.max_eq.max(64),
        eqs = cap.max_degree_plus_one.saturating_add(2).max(4),
        xeq = cap.max_anf_id.saturating_add(64).max(64),
        xeqs = (cap.xor_atom_count.saturating_add(cap.max_anf_id) + 64).max(64),
    );
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let mut file = fs::File::create(path).map_err(|e| e.to_string())?;
    file.write_all(body.as_bytes()).map_err(|e| e.to_string())?;
    Ok(cap)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::pq_groebner_f2::{F2BoolMono, F2BoolPoly};

    #[test]
    fn anf_row_round_trips_a_quadratic() {
        let poly = F2BoolPoly::from_monos(
            vec![
                F2BoolMono::var(0).mul(F2BoolMono::var(1)),
                F2BoolMono::var(2),
                F2BoolMono::one(),
            ],
            3,
        );
        let row = AnfRow::from_poly(&poly);
        assert!(row.constant);
        assert_eq!(row.monomials.len(), 2);
        let anf = format_anf(3, &[row]);
        assert!(anf.starts_with("p cnf 3 1\n"));
        assert!(anf.contains(".2 1 2") || anf.contains(".2 2 1"));
        assert!(!anf.contains(" T "));
    }

    #[test]
    fn validate_anf_accepts_a_satisfying_model() {
        let anf = "p cnf 2 1\nx T 1 2 0\n";
        assert!(validate_anf(anf, &[true, true]));
        assert!(!validate_anf(anf, &[true, false]));
    }

    #[test]
    fn parse_model_reads_first_bitstring() {
        let stdout = "c comment\n01011\n42\n";
        assert_eq!(
            parse_wdsat_model(stdout, 5),
            Some(vec![false, true, false, true, true])
        );
    }

    /// A child crash or missing status is never a proof of UNSAT. These
    /// shell children exercise the actual process boundary without depending
    /// on a locally built WDSat binary.
    #[cfg(unix)]
    #[test]
    fn mock_child_exit_and_empty_output_are_not_refutations() {
        use crate::cryptanalysis::koblitz_index_calculus::{
            build_frobenius_factor_base, point_key,
        };
        use std::os::unix::fs::PermissionsExt;

        let dir = std::env::temp_dir().join(format!(
            "wdsat-triage-{}-{}",
            std::process::id(),
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .expect("clock")
                .as_nanos()
        ));
        fs::create_dir_all(&dir).expect("mock directory");
        let make_child = |name: &str, body: &str| {
            let path = dir.join(name);
            fs::write(&path, body).expect("mock child script");
            let mut permissions = fs::metadata(&path).expect("mock metadata").permissions();
            permissions.set_mode(0o700);
            fs::set_permissions(&path, permissions).expect("mock executable");
            path
        };
        let empty_ok = make_child("empty-ok.sh", "#!/bin/sh\nexit 0\n");
        let empty_failure = make_child("empty-failure.sh", "#!/bin/sh\nexit 23\n");
        let false_unsat = make_child("false-unsat.sh", "#!/bin/sh\nprintf 'UNSAT\\n'\nexit 23\n");
        let stderr_unsat = make_child(
            "stderr-unsat.sh",
            "#!/bin/sh\nprintf 'UNSAT\\n' >&2\nexit 0\n",
        );
        let explicit_unsat = make_child(
            "explicit-unsat.sh",
            "#!/bin/sh\nprintf 'UNSAT\\n101\\n'\nexit 0\n",
        );
        let model = make_child("model.sh", "#!/bin/sh\nprintf '01011\\n'\nexit 0\n");
        let options = |binary: PathBuf| WdsatSolveOptions {
            binary,
            work_dir: Some(dir.clone()),
            timeout: Duration::from_secs(2),
            keep_anf: None,
        };
        let anf = "p cnf 5 0\n";
        let (stdout, _, _) =
            run_wdsat(anf, 5, &[], &options(empty_ok.clone())).expect("successful empty child");
        assert!(stdout.is_empty());
        assert_eq!(parse_wdsat_stdout(&stdout, 5), WdsatStdoutVerdict::Unknown);
        for binary in [&empty_failure, &false_unsat] {
            assert!(run_wdsat(anf, 5, &[], &options(binary.clone()))
                .expect_err("nonzero child must fail")
                .contains("status exit status: 23"));
        }
        let (stdout, _, _) =
            run_wdsat(anf, 5, &[], &options(explicit_unsat.clone())).expect("explicit UNSAT child");
        assert_eq!(parse_wdsat_stdout(&stdout, 2), WdsatStdoutVerdict::Unsat);
        assert_eq!(
            parse_wdsat_stdout("UNSAT on XORGAUSS init\n", 2),
            WdsatStdoutVerdict::Unsat
        );
        assert_eq!(
            parse_wdsat_stdout("not UNSAT\n", 2),
            WdsatStdoutVerdict::Unknown
        );
        assert_eq!(
            parse_wdsat_stdout("01011\nUNSAT\n", 5),
            WdsatStdoutVerdict::Model(vec![false, true, false, true, true])
        );
        let (stdout, _, _) =
            run_wdsat(anf, 5, &[], &options(model)).expect("successful model child");
        assert_eq!(
            parse_wdsat_stdout(&stdout, 5),
            WdsatStdoutVerdict::Model(vec![false, true, false, true, true])
        );

        let kc = KoblitzCurve::new(1, 7).expect("K_1/F_2^7");
        let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let index_of: HashMap<_, _> = fb
            .points
            .iter()
            .enumerate()
            .map(|(i, point)| (point_key(point), i))
            .collect();
        let mut affine = fb
            .points
            .iter()
            .filter(|point| matches!(point, BinaryPoint::Affine { .. }));
        let target = kc.add(
            affine.next().expect("first point"),
            affine.next().expect("second point"),
        );
        for binary in [empty_ok, empty_failure, false_unsat, stderr_unsat] {
            let (_, stats) =
                wdsat_decompose(&kc, &fb, &index_of, &st, &target, 2, &options(binary));
            assert_eq!(stats.solver_calls, 1);
            assert!(stats.exhausted);
            assert!(!stats.refuted);
        }
        let (_, stats) = wdsat_decompose(
            &kc,
            &fb,
            &index_of,
            &st,
            &target,
            2,
            &options(explicit_unsat),
        );
        assert_eq!(stats.solver_calls, 1);
        assert!(stats.refuted);
        assert!(!stats.exhausted);

        // Construct model-output children from the exact frozen tiny system,
        // then replay a valid point relation independently in the group.
        let BinaryPoint::Affine { x: target_x, .. } = &target else {
            panic!("planted target is infinity");
        };
        let sys = crate::cryptanalysis::polynomial_reuse::build_decomposition_system_reusing(
            &fb.subspace_basis,
            target_x,
            &kc.curve.b,
            2,
            &st,
        )
        .expect("tiny decomposition system");
        assert!(sys.n_vars <= 16, "mock witness search must stay tiny");
        let limit = 1u64 << sys.n_vars;
        let good_root = (0..limit)
            .find(|&root| {
                if !sys
                    .equations
                    .iter()
                    .all(|equation| equation.eval(root) == 0)
                {
                    return false;
                }
                let xs: Vec<F2mElement> = (0..2)
                    .map(|i| sys.summand_x(&fb.subspace_basis, root, i, kc.n))
                    .collect();
                lift_candidate(&kc, &fb, &index_of, &xs, &target).is_some()
            })
            .expect("planted target has a lifted system root");
        let bad_root = (0..limit)
            .find(|&root| {
                sys.equations
                    .iter()
                    .any(|equation| equation.eval(root) != 0)
            })
            .expect("system has an invalid root candidate");
        let bits = |root: u64| {
            (0..sys.n_vars)
                .map(|i| if (root >> i) & 1 == 1 { '1' } else { '0' })
                .collect::<String>()
        };
        let valid_model = make_child(
            "valid-model.sh",
            &format!(
                "#!/bin/sh\nprintf '{}\\nUNSAT\\n'\nexit 0\n",
                bits(good_root)
            ),
        );
        let invalid_model = make_child(
            "invalid-model.sh",
            &format!("#!/bin/sh\nprintf '{}\\n'\nexit 0\n", bits(bad_root)),
        );
        let (indices, stats) =
            wdsat_decompose(&kc, &fb, &index_of, &st, &target, 2, &options(valid_model));
        assert_eq!(stats.solver_calls, 1);
        assert_eq!(stats.models, 1);
        let indices = indices.expect("mock valid model must lift");
        let mut replay = BinaryPoint::Infinity;
        for index in indices {
            replay = kc.add(&replay, &fb.points[index]);
        }
        assert_eq!(replay, target);
        let (indices, stats) = wdsat_decompose(
            &kc,
            &fb,
            &index_of,
            &st,
            &target,
            2,
            &options(invalid_model),
        );
        assert!(indices.is_none());
        assert_eq!(stats.spurious, 1);
        assert!(stats.exhausted);
        assert!(!stats.refuted);
        fs::remove_dir_all(dir).expect("remove mock directory");
    }

    #[test]
    fn capacity_reads_header_and_degrees() {
        let anf = "p cnf 4 2\nx T .2 1 2 0\nx 3 4 0\n";
        let cap = suggest_capacity(anf);
        assert_eq!(cap.max_anf_id, 5);
        assert_eq!(cap.max_degree_plus_one, 3);
        assert!(cap.max_eq >= 2);
    }

    /// Cross-check WDSat against the native SAT oracle on a planted
    /// two-summand instance over a prime-degree Koblitz field.
    ///
    /// ```text
    /// WDSAT_BINARY=/path/to/wdsat_solver cargo test -p crypto --lib \
    ///   wdsat_agrees_with_native_sat_on_prime_degree -- --ignored --nocapture
    /// ```
    #[test]
    #[ignore = "requires WDSAT_BINARY pointing at a capacity-sufficient wdsat_solver"]
    fn wdsat_agrees_with_native_sat_on_prime_degree() {
        use crate::cryptanalysis::koblitz_groebner::FieldStructure;
        use crate::cryptanalysis::koblitz_index_calculus::{
            build_frobenius_factor_base, point_key, sat_decompose, KoblitzCurve,
        };
        use std::collections::HashMap;
        use std::path::PathBuf;
        use std::time::Duration;

        let binary = std::env::var_os("WDSAT_BINARY").expect("WDSAT_BINARY unset");
        let binary = PathBuf::from(binary);
        assert!(
            binary.is_file(),
            "WDSAT_BINARY is not a file: {}",
            binary.display()
        );

        // n = 7 is prime; K_1 has a usable invariant factor base.
        let kc = KoblitzCurve::new(1, 7).expect("K_1/F_2^7");
        let fb = build_frobenius_factor_base(&kc, 0).expect("factor base");
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
        let index_of: HashMap<_, _> = fb
            .points
            .iter()
            .enumerate()
            .map(|(i, p)| (point_key(p), i))
            .collect();

        // Plant R = P_i + P_j for the first two distinct affine points.
        let mut affine = fb.points.iter().enumerate().filter_map(|(i, p)| match p {
            BinaryPoint::Affine { .. } => Some(i),
            BinaryPoint::Infinity => None,
        });
        let i = affine.next().expect("factor base point");
        let j = affine.next().expect("second factor base point");
        let target = kc.add(&fb.points[i], &fb.points[j]);

        let (native, native_stats) =
            sat_decompose(&kc, &fb, &index_of, &st, &target, 2, 8, Some(2));
        assert!(
            native.is_some(),
            "native SAT missed a planted decomposition: {native_stats:?}"
        );

        let options = WdsatSolveOptions {
            binary,
            work_dir: None,
            timeout: Duration::from_secs(5),
            keep_anf: None,
        };
        let (wdsat, wdsat_stats) = wdsat_decompose(&kc, &fb, &index_of, &st, &target, 2, &options);
        assert!(
            wdsat.is_some(),
            "WDSat missed a planted decomposition: {wdsat_stats:?}"
        );
        // Both lift to some ordered multiset of base indices summing to R.
        let mut a = native.unwrap();
        let mut b = wdsat.unwrap();
        a.sort_unstable();
        b.sort_unstable();
        assert_eq!(a, b);
    }
}
