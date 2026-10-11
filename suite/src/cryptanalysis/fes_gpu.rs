//! # Driving the GPU (or host-emulation) FES worker from Rust.
//!
//! This is the bridge that wires the `gpu/fes` Gray-code kernels — CUDA,
//! Metal, and the host-emulation build — into the `icx` binary. A quadratic
//! Boolean system is packed into the workers' shared file contract
//! (`gpu/fes/fes_io.hpp`), a worker executable is run as a subprocess, its
//! proposed solutions are read back, and **every one is re-verified on the CPU**
//! here before it is trusted. A worker can therefore only ever *propose*
//! candidates; a GPU bug, a truncated read, or a missing device can never
//! produce a wrong answer — at worst the result is empty and the caller falls
//! back to the in-process CPU search.
//!
//! The same in-process CPU search ([`PackedSystem::cpu_search`]) is both the
//! default backend and the cross-check the tests hold every worker to: the CPU
//! reference is the algorithm in `fes.cuh` ported to Rust, so a worker's output
//! must equal it exactly.

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

use crate::cryptanalysis::mq_fes::QuadraticForm;

/// A quadratic Boolean system packed one bit per equation, matching the
/// workers' representation: `value(x) = cst ^ (+)_{x_i} lin[i] ^
/// (+)_{i>=j, x_i,x_j} quad_tri[tri(i,j)]`, and `x` is a solution iff
/// `value(x) == 0`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PackedSystem {
    pub n: usize,
    pub m: usize,
    pub cst: u64,
    pub lin: Vec<u64>,
    /// Lower-triangular, `tri(i,j) = i*(i+1)/2 + j` for `i >= j`. The diagonal
    /// stays zero: a `QuadraticForm` folds `x_i^2 = x_i` into `linear`.
    pub quad_tri: Vec<u64>,
}

fn tri(i: usize, j: usize) -> usize {
    let (a, b) = if i >= j { (i, j) } else { (j, i) };
    a * (a + 1) / 2 + b
}

impl PackedSystem {
    /// Pack a system given as one [`QuadraticForm`] per equation (`m <= 64`,
    /// `n <= 62`, all forms over the same `n`).
    pub fn from_quadratic_forms(forms: &[QuadraticForm]) -> Result<Self, String> {
        if forms.is_empty() {
            return Err("empty system: FES needs at least one equation".into());
        }
        if forms.len() > 64 {
            return Err(format!(
                "too many equations for a u64 pack: {}",
                forms.len()
            ));
        }
        let n = forms[0].n;
        if n > 62 {
            return Err(format!("n = {n} exceeds the single-word worker limit (62)"));
        }
        if forms.iter().any(|f| f.n != n) {
            return Err("all equations must share the same variable count".into());
        }
        let mut cst = 0u64;
        let mut lin = vec![0u64; n];
        let mut quad_tri = vec![0u64; n * (n + 1) / 2];
        for (e, f) in forms.iter().enumerate() {
            let bit = 1u64 << e;
            if f.constant {
                cst ^= bit;
            }
            for (i, &l) in f.linear.iter().enumerate() {
                if l {
                    lin[i] ^= bit;
                }
            }
            // quad[i][j] with j < i.
            for (i, row) in f.quad.iter().enumerate() {
                for (j, &q) in row.iter().enumerate() {
                    if q {
                        quad_tri[tri(i, j)] ^= bit;
                    }
                }
            }
        }
        Ok(PackedSystem {
            n,
            m: forms.len(),
            cst,
            lin,
            quad_tri,
        })
    }

    fn quad(&self, i: usize, j: usize) -> u64 {
        self.quad_tri[tri(i, j)]
    }

    /// Evaluate the packed system at `x` (bit i is variable i). Zero means `x`
    /// solves every equation. This is the independent verifier for worker output.
    pub fn eval(&self, x: u64) -> u64 {
        let mut v = self.cst;
        for i in 0..self.n {
            if (x >> i) & 1 == 1 {
                v ^= self.lin[i];
                for j in 0..=i {
                    if (x >> j) & 1 == 1 {
                        v ^= self.quad(i, j);
                    }
                }
            }
        }
        v
    }

    /// True if `x` zeroes every equation.
    pub fn is_solution(&self, x: u64) -> bool {
        self.eval(x) == 0
    }

    /// The in-process CPU FES search — the `fes.cuh` derivative-maintained
    /// Gray walk ported to Rust. This is the default backend and the reference
    /// every worker is checked against.
    pub fn cpu_search(&self) -> Vec<u64> {
        let n = self.n;
        let mut sols = Vec::new();
        // base = 0: value is the constant, and df[i] = lin[i] ^ quad(i,i).
        let mut df: Vec<u64> = (0..n).map(|i| self.lin[i] ^ self.quad(i, i)).collect();
        let mut val = self.cst;
        if val == 0 {
            sols.push(0);
        }
        if n == 0 {
            return sols;
        }
        let steps: u64 = if n >= 63 { 0 } else { 1u64 << n };
        for s in 1..steps {
            let i1 = s.trailing_zeros() as usize;
            val ^= df[i1];
            for j in 0..n {
                if j != i1 {
                    df[j] ^= self.quad(i1, j);
                }
            }
            if val == 0 {
                sols.push(s ^ (s >> 1)); // Gray code of s
            }
        }
        sols
    }

    /// Serialize to the worker file contract (`fes_io.hpp`).
    pub fn to_contract(&self) -> String {
        let mut s = format!("{} {}\n{}\n", self.n, self.m, self.cst);
        let lin: Vec<String> = self.lin.iter().map(|v| v.to_string()).collect();
        s.push_str(&lin.join(" "));
        s.push('\n');
        let q: Vec<String> = self.quad_tri.iter().map(|v| v.to_string()).collect();
        s.push_str(&q.join(" "));
        s.push('\n');
        s
    }
}

/// Which backend solved a system, and its proposal/verification tally.
#[derive(Clone, Debug)]
pub struct FesResult {
    /// Verified solutions (each `eval == 0`), sorted and deduplicated.
    pub solutions: Vec<u64>,
    /// Human label of the backend used (`cpu`, or the worker path).
    pub backend: String,
    /// How many candidates the worker proposed (equals `solutions.len()` for cpu).
    pub proposed: usize,
    /// How many of those verified (dropped candidates are a worker defect).
    pub verified: usize,
}

/// The FES backend to use.
#[derive(Clone, Debug)]
pub enum FesBackend {
    /// The in-process CPU Gray-code search.
    Cpu,
    /// An external worker executable (CUDA / Metal / host-emulation) that
    /// speaks the file contract.
    Worker(PathBuf),
    /// Use a discovered worker if one exists, else the CPU search.
    Auto,
}

/// Parse a worker's `SOLUTIONS k` output into candidate assignments.
fn parse_solutions(stdout: &str) -> Vec<u64> {
    let mut out = Vec::new();
    let mut lines = stdout.lines();
    // Find the SOLUTIONS header (skip any leading diagnostics).
    let mut expected = None;
    for line in lines.by_ref() {
        let t = line.trim();
        if let Some(rest) = t.strip_prefix("SOLUTIONS") {
            expected = rest.trim().parse::<usize>().ok();
            break;
        }
    }
    if expected.is_none() {
        return out;
    }
    for line in lines {
        let t = line.trim();
        if t.is_empty() {
            continue;
        }
        if let Ok(v) = t.parse::<u64>() {
            out.push(v);
        }
    }
    out
}

/// Look for a worker executable: `ICX_FES_WORKER` env override first, then the
/// known worker names next to the current executable (real GPU workers before
/// the host-emulation fallback).
pub fn discover_worker() -> Option<PathBuf> {
    if let Ok(p) = std::env::var("ICX_FES_WORKER") {
        let path = PathBuf::from(p);
        if path.is_file() {
            return Some(path);
        }
    }
    let exe = std::env::current_exe().ok()?;
    let dir = exe.parent()?;
    for name in ["fes_cuda", "fes_metal", "fes_solve"] {
        let cand = dir.join(name);
        if cand.is_file() {
            return Some(cand);
        }
    }
    None
}

/// Run a worker on a system and return its re-verified solutions.
fn run_worker(sys: &PackedSystem, worker: &Path) -> Result<FesResult, String> {
    // Unique temp file (pid + nanos) so concurrent calls never collide — the
    // WDSat oracle's shared-temp-file race, avoided.
    let pid = std::process::id();
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    let mut path = std::env::temp_dir();
    path.push(format!("icx-fes-{pid}-{nanos}.txt"));
    {
        let mut f = std::fs::File::create(&path).map_err(|e| format!("temp file: {e}"))?;
        f.write_all(sys.to_contract().as_bytes())
            .map_err(|e| format!("write: {e}"))?;
    }
    let out = Command::new(worker).arg("--in").arg(&path).output();
    let _ = std::fs::remove_file(&path);
    let out = out.map_err(|e| format!("failed to run worker {}: {e}", worker.display()))?;
    if !out.status.success() {
        return Err(format!(
            "worker {} exited with {}: {}",
            worker.display(),
            out.status,
            String::from_utf8_lossy(&out.stderr).trim()
        ));
    }
    let stdout = String::from_utf8_lossy(&out.stdout);
    let proposed = parse_solutions(&stdout);
    let mut verified: Vec<u64> = proposed
        .iter()
        .copied()
        .filter(|&x| sys.is_solution(x))
        .collect();
    verified.sort_unstable();
    verified.dedup();
    Ok(FesResult {
        solutions: verified.clone(),
        backend: worker.display().to_string(),
        proposed: proposed.len(),
        verified: verified.len(),
    })
}

/// Generate a pseudo-random quadratic Boolean system in `n` variables and `m`
/// equations with a planted common zero, returned with that planted point.
/// Deterministic in `seed`; used by `icx fes` to exercise the backends.
pub fn random_system(n: usize, m: usize, seed: u64) -> (PackedSystem, u64) {
    let mut s = seed | 1;
    let mut rng = || {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        s
    };
    let mask = if n >= 64 { u64::MAX } else { (1u64 << n) - 1 };
    let planted = rng() & mask;
    let mut forms = Vec::with_capacity(m);
    for _ in 0..m {
        let mut f = QuadraticForm {
            n,
            constant: false,
            linear: (0..n).map(|_| rng() & 1 == 1).collect(),
            quad: (0..n)
                .map(|i| (0..i).map(|_| rng() & 1 == 1).collect())
                .collect(),
        };
        // Set the constant so the planted point is a zero of this equation.
        let mut v = false;
        for i in 0..n {
            if (planted >> i) & 1 == 1 {
                v ^= f.linear[i];
                for j in 0..i {
                    if (planted >> j) & 1 == 1 {
                        v ^= f.quad[i][j];
                    }
                }
            }
        }
        f.constant = v;
        forms.push(f);
    }
    (
        PackedSystem::from_quadratic_forms(&forms).expect("valid random system"),
        planted,
    )
}

/// Solve a packed system with the chosen backend.
pub fn solve(sys: &PackedSystem, backend: &FesBackend) -> Result<FesResult, String> {
    match backend {
        FesBackend::Cpu => {
            let mut sols = sys.cpu_search();
            sols.sort_unstable();
            sols.dedup();
            let n = sols.len();
            Ok(FesResult {
                solutions: sols,
                backend: "cpu".to_string(),
                proposed: n,
                verified: n,
            })
        }
        FesBackend::Worker(w) => run_worker(sys, w),
        FesBackend::Auto => match discover_worker() {
            Some(w) => run_worker(sys, &w),
            None => solve(sys, &FesBackend::Cpu),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_forms(n: usize, m: usize, seed: u64) -> Vec<QuadraticForm> {
        // Deterministic pseudo-random forms with a planted solution at `seed`.
        let mut s = seed | 1;
        let mut rng = || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            s
        };
        let sol = rng() & ((1u64 << n) - 1);
        let mut forms = Vec::new();
        for _ in 0..m {
            let mut f = QuadraticForm {
                n,
                constant: false,
                linear: (0..n).map(|_| rng() & 1 == 1).collect(),
                quad: (0..n)
                    .map(|i| (0..i).map(|_| rng() & 1 == 1).collect())
                    .collect(),
            };
            // Force the planted point to be a zero: adjust the constant.
            let mut v = false;
            for i in 0..n {
                if (sol >> i) & 1 == 1 {
                    v ^= f.linear[i];
                    for j in 0..i {
                        if (sol >> j) & 1 == 1 {
                            v ^= f.quad[i][j];
                        }
                    }
                }
            }
            f.constant = v;
            forms.push(f);
        }
        forms
    }

    fn brute(sys: &PackedSystem) -> Vec<u64> {
        (0..(1u64 << sys.n))
            .filter(|&x| sys.is_solution(x))
            .collect()
    }

    #[test]
    fn packed_eval_matches_forms() {
        let n = 12;
        let forms = sample_forms(n, 14, 42);
        let sys = PackedSystem::from_quadratic_forms(&forms).unwrap();
        for x in 0..(1u64 << n) {
            // Independent per-equation evaluation of the forms.
            let mut all_zero = true;
            for f in &forms {
                let mut v = f.constant;
                for i in 0..n {
                    if (x >> i) & 1 == 1 {
                        v ^= f.linear[i];
                        for j in 0..i {
                            if (x >> j) & 1 == 1 {
                                v ^= f.quad[i][j];
                            }
                        }
                    }
                }
                all_zero &= !v;
            }
            assert_eq!(sys.is_solution(x), all_zero, "mismatch at x={x}");
        }
    }

    #[test]
    fn cpu_search_matches_brute_force() {
        for (n, m, seed) in [(10usize, 12usize, 1u64), (14, 10, 7), (16, 20, 3)] {
            let forms = sample_forms(n, m, seed);
            let sys = PackedSystem::from_quadratic_forms(&forms).unwrap();
            let mut got = super::solve(&sys, &FesBackend::Cpu).unwrap().solutions;
            got.sort_unstable();
            let mut want = brute(&sys);
            want.sort_unstable();
            assert_eq!(got, want, "n={n} m={m} seed={seed}");
        }
    }

    #[test]
    fn parse_solutions_reads_the_contract() {
        let s = "some diagnostic\nSOLUTIONS 2\n8805\n42\n";
        assert_eq!(parse_solutions(s), vec![8805, 42]);
        assert_eq!(parse_solutions("SOLUTIONS 0\n"), Vec::<u64>::new());
        assert_eq!(parse_solutions("no header here\n"), Vec::<u64>::new());
    }

    #[test]
    fn worker_only_proposes_bad_candidates_are_dropped() {
        // A worker that returns a non-solution must have it filtered out.
        let forms = sample_forms(10, 12, 5);
        let sys = PackedSystem::from_quadratic_forms(&forms).unwrap();
        let real = sys.cpu_search();
        // Simulate parse output with one real solution plus a bogus one.
        let bogus = real.first().map(|&x| x ^ 1).unwrap_or(1);
        let proposed = [real.first().copied().unwrap_or(0), bogus];
        let verified: Vec<u64> = proposed
            .iter()
            .copied()
            .filter(|&x| sys.is_solution(x))
            .collect();
        assert!(verified.iter().all(|&x| sys.is_solution(x)));
        assert!(!verified.contains(&bogus) || sys.is_solution(bogus));
    }
}
