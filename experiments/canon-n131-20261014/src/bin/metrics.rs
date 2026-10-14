//! Deterministic per-word counts at n = 131 (no timing):
//! longest zero run Z, number c of longest runs (= variant-A / lift_scan
//! candidate rotations), gap-scan rotate-and-compare evaluations, and the
//! refinement depth (steps until one candidate is left).
//!
//! usage: metrics <uniform|structured> <words> <seed>

use canon_n131::*;

fn hist_json(h: &[u64]) -> String {
    let parts: Vec<String> = h
        .iter()
        .enumerate()
        .filter(|(_, &v)| v > 0)
        .map(|(i, v)| format!("\"{i}\":{v}"))
        .collect();
    format!("{{{}}}", parts.join(","))
}

fn summary(name: &str, h: &[u64]) -> String {
    let n: u64 = h.iter().sum();
    let s: u128 = h.iter().enumerate().map(|(i, &v)| i as u128 * v as u128).sum();
    let s2: u128 = h.iter().enumerate().map(|(i, &v)| (i * i) as u128 * v as u128).sum();
    let mean = s as f64 / n as f64;
    let var = s2 as f64 / n as f64 - mean * mean;
    let max = h.iter().rposition(|&v| v > 0).unwrap_or(0);
    let min = h.iter().position(|&v| v > 0).unwrap_or(0);
    // median
    let mut acc = 0;
    let mut med = 0;
    for (i, &v) in h.iter().enumerate() {
        acc += v;
        if acc * 2 >= n {
            med = i;
            break;
        }
    }
    format!(
        "\"{name}\":{{\"mean\":{mean:.6},\"sd\":{:.6},\"min\":{min},\"median\":{med},\"max\":{max},\"hist\":{}}}",
        var.max(0.0).sqrt(),
        hist_json(h)
    )
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let dist = a.get(1).cloned().unwrap_or("uniform".into());
    let words: u64 = a.get(2).map(|s| s.parse().unwrap()).unwrap_or(10_000_000);
    let seed: u64 = a.get(3).map(|s| s.parse().unwrap()).unwrap_or(1);
    let mut rng = Rng(seed);
    let (mut hz, mut hc, mut hg, mut hd) = (vec![0u64; 132], vec![0u64; 132], vec![0u64; 132], vec![0u64; 132]);
    let mut constant = 0u64;
    for _ in 0..words {
        let x = if dist == "uniform" { rng.word131() } else { structured131(&mut rng) };
        if x == [0; 3] || x == MASK131 {
            constant += 1;
            continue;
        }
        let (z, c, g) = F131::stats(x);
        hz[z as usize] += 1;
        hc[c as usize] += 1;
        hg[g as usize] += 1;
        hd[F131::refine_depth(x) as usize] += 1;
    }
    let nonconst = words - constant;
    println!(
        "{{\"distribution\":\"{dist}\",\"seed\":{seed},\"words\":{words},\"constant_words_skipped\":{constant},\
\"fraction_one_longest_run\":{:.8},\"one_longest_run_words\":{},{},{},{},{}}}",
        hc[1] as f64 / nonconst as f64,
        hc[1],
        summary("longest_zero_run_Z", &hz),
        summary("longest_runs_c", &hc),
        summary("gap_scan_rotations", &hg),
        summary("refine_depth", &hd)
    );
}
