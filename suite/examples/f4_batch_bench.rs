//! Batched Gröbner decomposition: every execution mode on one frozen
//! target set, and the raw decision throughput of every backend.
//!
//! ```bash
//! cargo run --release --example f4_batch_bench -- --targets 64
//! cargo run --release --features gpu-emulator --example f4_batch_bench -- \
//!     --modes sequential,rayon,lockstep:cpu,lockstep:emulate
//! cargo run --release --example f4_batch_bench -- --modes lockstep:cpu,lockstep:cuda  # GPU host
//! ```
//!
//! **Part 1 — modes.**  The same targets on `K_a/2^n` are decomposed by
//! `groebner_decompose` one at a time (`sequential`), the same across the
//! cores (`rayon`), and by `groebner_decompose_batch` in lockstep on a
//! backend (`lockstep:cpu`, `lockstep:emulate`, `lockstep:cuda[:N]`).  A
//! verdict digest over every target's decomposition, and the summed solver
//! counters, must be identical across modes; the run aborts otherwise.
//!
//! **Part 2 — decision throughput.**  The Macaulay decisions the lockstep
//! searches actually requested are recorded and replayed through each
//! backend, in batches of `--replay-batch`, so the kernel is priced on the
//! real distribution of matrices without the searches' bookkeeping.  Every
//! backend's decisions are checked against the host kernel's.
//!
//! This is a stage diagnostic (AGENTS.md): the decomposition oracle only,
//! not an end-to-end ECDLP cost.

use cryptanalysis_suite::binary_ecc::BinaryPoint;
use cryptanalysis_suite::cryptanalysis::f4_batch::{BatchDecider, CpuDecider, DecisionRequest};
use cryptanalysis_suite::cryptanalysis::f4_gf2::{self, Decision, KernelCounters, MacaulayCaps};
use cryptanalysis_suite::cryptanalysis::f4_gpu::decider_from_spec;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    f4_kernel, f4_profile, f4_profile_reset, FieldStructure, SolveStats, SolverEngine,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, groebner_decompose, groebner_decompose_batch, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use cryptanalysis_suite::hash::sha256::sha256;
use num_bigint::BigUint;
use rayon::prelude::*;
use serde_json::json;
use std::time::Instant;

fn arg<'a>(args: &'a [String], name: &str) -> Option<&'a str> {
    args.windows(2)
        .find(|w| w[0] == name)
        .map(|w| w[1].as_str())
}

fn target_scalar(i: u32) -> BigUint {
    BigUint::from(1u64 + (i as u64).wrapping_mul(2_654_435_761) % 1_000_003)
}

/// Forwards to the host kernel and keeps a copy of every request.
struct Recorder {
    requests: Vec<(Vec<F2BoolPoly>, usize, u32)>,
    cap: usize,
}

impl BatchDecider for Recorder {
    fn name(&self) -> String {
        "recorder".into()
    }

    fn decide(
        &mut self,
        requests: &[DecisionRequest<'_>],
        caps: MacaulayCaps,
    ) -> Vec<(Option<Decision>, KernelCounters)> {
        for r in requests {
            if self.requests.len() < self.cap {
                self.requests.push((r.polys.to_vec(), r.n_vars, r.degree));
            }
        }
        CpuDecider.decide(requests, caps)
    }
}

#[derive(Default)]
struct Totals {
    reductions: usize,
    infeasible: usize,
    propagations: usize,
    splits: usize,
    exhausted: usize,
}

impl Totals {
    fn add(&mut self, s: &SolveStats) {
        self.reductions += s.reductions;
        self.infeasible += s.infeasible_branches;
        self.propagations += s.propagations;
        self.splits += s.splits;
        self.exhausted += usize::from(s.exhausted);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n: u32 = arg(&args, "--degree").map_or(23, |v| v.parse().unwrap());
    let a: u8 = arg(&args, "--curve-a").map_or(1, |v| v.parse().unwrap());
    let targets: u32 = arg(&args, "--targets").map_or(64, |v| v.parse().unwrap());
    let budget: usize = arg(&args, "--node-budget").map_or(4096, |v| v.parse().unwrap());
    let replay_batch: usize = arg(&args, "--replay-batch").map_or(4096, |v| v.parse().unwrap());
    let replay_cap: usize = arg(&args, "--replay-cap").map_or(100_000, |v| v.parse().unwrap());
    let modes: Vec<String> = arg(&args, "--modes")
        .unwrap_or("sequential,rayon,lockstep:cpu")
        .split(',')
        .map(String::from)
        .collect();
    let out = arg(&args, "--out");

    let kc = KoblitzCurve::new(a, n).expect("no Koblitz curve at this degree");
    let fb = build_frobenius_factor_base(&kc, 0).expect("no factor base");
    // The base's identity for the candidate manifest: SHA-256 over its
    // points as sorted "x,y" lines of lowercase 0x-hex coordinates.
    let mut lines: Vec<String> = fb
        .points
        .iter()
        .filter_map(|p| match p {
            BinaryPoint::Affine { x, y } => {
                Some(format!("{:#x},{:#x}", x.to_biguint(), y.to_biguint()))
            }
            BinaryPoint::Infinity => None,
        })
        .collect();
    lines.sort();
    let fb_digest = hex::encode(sha256(lines.join("\n").as_bytes()));
    println!(
        "factor base: {} points, SHA-256 {fb_digest} (sorted \"x,y\" hex lines)",
        lines.len()
    );
    let index_of = fb.index_map();
    let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
    let g = kc.generator().clone();
    let points: Vec<_> = (0..targets)
        .map(|i| kc.mul(&g, &target_scalar(i)))
        .collect();
    let engine = SolverEngine::default();
    println!(
        "K_{a}/2^{n}: {} base points (l = {}), {targets} targets, node budget {budget}, kernel {:?}, {} threads",
        fb.points.len(),
        fb.ell,
        f4_kernel(),
        rayon::current_num_threads()
    );

    let digest_of = |results: &[(Option<Vec<usize>>, SolveStats)]| {
        let mut verdicts = Vec::new();
        let mut totals = Totals::default();
        for (i, (idxs, stats)) in results.iter().enumerate() {
            totals.add(stats);
            verdicts.push(match idxs {
                Some(v) => {
                    let mut v = v.clone();
                    v.sort_unstable();
                    format!("{i}:{v:?}")
                }
                None => format!("{i}:none{}", if stats.exhausted { "!" } else { "" }),
            });
        }
        (
            blake3::hash(verdicts.join("|").as_bytes())
                .to_hex()
                .to_string(),
            totals,
            results.iter().filter(|r| r.0.is_some()).count(),
        )
    };

    println!();
    println!("| mode | wall s | decomposed | reductions | splits | F4 calls | rounds | mean round | digest |");
    println!("|:-----|-------:|-----------:|-----------:|-------:|---------:|-------:|-----------:|:-------|");
    let mut rows = Vec::new();
    let mut reference_digest: Option<String> = None;
    for mode in &modes {
        // A backend's setup (for CUDA: driver, NVRTC compile, module load)
        // is timed apart from the mode's wall.
        let setup = Instant::now();
        let mut decider = match mode.strip_prefix("lockstep:").map(decider_from_spec) {
            Some(Ok(d)) => Some(d),
            Some(Err(e)) => {
                println!("| {mode} | skipped: {e} |");
                continue;
            }
            None => None,
        };
        let setup_seconds = setup.elapsed().as_secs_f64();
        f4_profile_reset();
        let t0 = Instant::now();
        let (results, rounds, requests): (Vec<_>, usize, usize) =
            match (mode.as_str(), decider.as_mut()) {
                (_, Some(decider)) => {
                    let (r, report) = groebner_decompose_batch(
                        &kc,
                        &fb,
                        &index_of,
                        &st,
                        &points,
                        2,
                        engine,
                        budget,
                        decider.as_mut(),
                    );
                    (r, report.rounds, report.requests)
                }
                ("sequential", None) => (
                    points
                        .iter()
                        .map(|p| groebner_decompose(&kc, &fb, &index_of, &st, p, 2, engine, budget))
                        .collect(),
                    0,
                    0,
                ),
                ("rayon", None) => (
                    points
                        .par_iter()
                        .map(|p| groebner_decompose(&kc, &fb, &index_of, &st, p, 2, engine, budget))
                        .collect(),
                    0,
                    0,
                ),
                (other, None) => panic!("unknown mode {other}"),
            };
        let wall = t0.elapsed().as_secs_f64();
        let profile = f4_profile();
        let (digest, totals, decomposed) = digest_of(&results);
        match &reference_digest {
            None => reference_digest = Some(digest.clone()),
            Some(want) => assert_eq!(&digest, want, "{mode} decided differently"),
        }
        println!(
            "| {mode} | {wall:.3} | {decomposed} | {} | {} | {} | {rounds} | {:.1} | {} |",
            totals.reductions,
            totals.splits,
            profile.calls,
            if rounds > 0 {
                requests as f64 / rounds as f64
            } else {
                0.0
            },
            &digest[..16]
        );
        rows.push(json!({
            "mode": mode, "wall_seconds": wall, "decomposed": decomposed, "digest": digest,
            "decider": decider.as_ref().map(|d| d.name()), "setup_seconds": setup_seconds,
            "reductions": totals.reductions, "infeasible_branches": totals.infeasible,
            "propagations": totals.propagations, "splits": totals.splits,
            "exhausted": totals.exhausted, "f4_calls": profile.calls,
            "f4_rows": profile.rows, "f4_cols": profile.cols,
            "f4_eliminated_rows": profile.eliminated_rows,
            "f4_eliminated_cols": profile.eliminated_cols, "f4_word_ops": profile.word_ops,
            "lockstep_rounds": rounds, "lockstep_requests": requests,
        }));
    }

    // Part 2: record the lockstep requests, replay them through each backend.
    let mut recorder = Recorder {
        requests: Vec::new(),
        cap: replay_cap,
    };
    let _ = groebner_decompose_batch(
        &kc,
        &fb,
        &index_of,
        &st,
        &points,
        2,
        engine,
        budget,
        &mut recorder,
    );
    let recorded = recorder.requests;
    let caps = f4_gf2::default_caps();
    let requests: Vec<DecisionRequest<'_>> = recorded
        .iter()
        .map(|(p, v, d)| DecisionRequest {
            polys: p,
            n_vars: *v,
            degree: *d,
        })
        .collect();
    let truth: Vec<Option<Decision>> = requests
        .par_iter()
        .map(|r| f4_gf2::decide(r.polys, r.n_vars, r.degree, caps).0)
        .collect();
    println!();
    println!(
        "Decision throughput on {} recorded requests, batches of {replay_batch}:",
        requests.len()
    );
    println!("| backend | wall s | decisions/s | µs/decision |");
    println!("|:--------|-------:|------------:|------------:|");
    let mut replays = Vec::new();
    let mut backends: Vec<String> = vec!["host-1-thread".into(), "cpu".into()];
    for mode in &modes {
        if let Some(b) = mode.strip_prefix("lockstep:") {
            if b != "cpu" {
                backends.push(b.to_string());
            }
        }
    }
    for backend in backends {
        let setup = Instant::now();
        let mut decider = if backend == "host-1-thread" {
            None
        } else {
            match decider_from_spec(&backend) {
                Ok(d) => Some(d),
                Err(e) => {
                    println!("| {backend} | skipped: {e} |");
                    continue;
                }
            }
        };
        let setup_seconds = setup.elapsed().as_secs_f64();
        let t0 = Instant::now();
        let got: Vec<Option<Decision>> = match decider.as_mut() {
            None => requests
                .iter()
                .map(|r| f4_gf2::decide(r.polys, r.n_vars, r.degree, caps).0)
                .collect(),
            Some(decider) => requests
                .chunks(replay_batch.max(1))
                .flat_map(|chunk| decider.decide(chunk, caps))
                .map(|(d, _)| d)
                .collect(),
        };
        let wall = t0.elapsed().as_secs_f64();
        assert_eq!(
            got, truth,
            "{backend} decided a replayed request differently"
        );
        let rate = requests.len() as f64 / wall.max(1e-12);
        println!(
            "| {backend} | {wall:.3} | {rate:.0} | {:.2} |",
            1e6 * wall / requests.len().max(1) as f64
        );
        replays.push(json!({
            "backend": backend, "decider": decider.as_ref().map(|d| d.name()),
            "setup_seconds": setup_seconds, "wall_seconds": wall,
            "decisions": requests.len(), "decisions_per_second": rate,
        }));
    }
    println!();
    println!("Stage diagnostic only: the decomposition oracle, not an end-to-end ECDLP cost.");

    if let Some(dir) = out {
        std::fs::create_dir_all(dir).expect("create output directory");
        let path = format!("{dir}/f4_batch.json");
        assert!(
            !std::path::Path::new(&path).exists(),
            "{path} exists; save each run in a new directory"
        );
        let doc = json!({
            "harness": "examples/f4_batch_bench.rs",
            "curve": format!("K_{a}/2^{n}"), "factor_base_points": fb.points.len(), "ell": fb.ell,
            "factor_base_sha256": fb_digest,
            "targets": targets, "node_budget": budget, "kernel": format!("{:?}", f4_kernel()),
            "threads": rayon::current_num_threads(), "modes": rows,
            "replay": {"requests": requests.len(), "batch": replay_batch, "backends": replays},
            "scope": "decomposition-oracle stage only; not an end-to-end ECDLP cost",
        });
        std::fs::write(&path, serde_json::to_string_pretty(&doc).unwrap()).unwrap();
        println!("Wrote {path}");
    }
}
