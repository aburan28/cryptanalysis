//! EDS-Residue **χ-localisation** sweep — the rank-1, fully-certifiable
//! probe of §5.3 in `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`.
//!
//! ```bash
//! cargo run --release --example eds_localisation
//! ```
//!
//! For Q = [k]P, the residues χ(ψ_n(Q)) (computable from Q alone) are the
//! k-decimation of P's EDS residues.  This sweep measures, over many k, the
//! minimal window of residues needed to pin k (up to the unavoidable ±k
//! sign), and whether the sign itself is resolved — predicted to follow a
//! `p mod 4` dichotomy (resolved iff χ(−1) = −1, i.e. p ≡ 3 mod 4).

use cryptanalysis_suite::cryptanalysis::eds_residue::{find_toy_point, localisation_sweep};
use num_bigint::BigUint;

fn run(p: u64, a: u64, b: u64) {
    let (pp, aa, bb) = (BigUint::from(p), BigUint::from(a), BigUint::from(b));
    let Some((px, py, m)) = find_toy_point(&pp, &aa, &bb, 1, 30) else {
        println!("p={}: no suitable point\n", p);
        return;
    };
    let s = localisation_sweep(&pp, &aa, &bb, &px, &py, m, 48, 200);
    println!(
        "p={p:>5} (≡{pm} mod4)  ord(P)={m:>4}  tested k={t:>4}\n  \
         pinned to ±k: {pin}/{t}   window: mean={mean:.2} median={med} max={mx}\n  \
         sign resolved (k exact): {sr}/{pin}   DEC-χ ok: {dok}\n",
        p = p,
        pm = s.p_mod4,
        m = s.order,
        t = s.tested,
        pin = s.pinned,
        mean = s.mean_window,
        med = s.median_window,
        mx = s.max_window_seen,
        sr = s.sign_resolved,
        dok = s.decimation_ok,
    );
}

fn main() {
    println!("\n=== EDS-Residue χ-localisation sweep ===\n");
    println!("# p ≡ 3 (mod 4)  — χ(−1) = −1, sign should resolve:");
    run(1019, 11, 7);
    run(2003, 11, 19);
    run(4099, 5, 3);
    println!("# p ≡ 1 (mod 4)  — χ(−1) = +1, only up to ±k:");
    run(1009, 37, 2);
    run(2017, 7, 5);
    run(4093, 3, 9);
}
