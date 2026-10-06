//! Test the conjecture **χ(B) = χ(⟨P,P⟩_r)** linking the EDS shift-multiplier
//! character to the self-Tate pairing (program item 2 / §5.5).
//!
//! ```bash
//! cargo run --release --example eds_tate_demo
//! ```
//!
//! For each embedding-degree-1 instance (point P of even order r | p−1) the
//! self-Tate pairing ⟨P,P⟩_r ∈ μ_r is computed (and validated: lands in μ_r,
//! bilinear), alongside the EDS multiplier B.  We tally whether χ(B)=χ(t).

use cryptanalysis_suite::cryptanalysis::eds_tate::{enumerate_embedding1, study};

fn v2(mut n: u64) -> u32 {
    let mut k = 0;
    while n.is_multiple_of(2) {
        n /= 2;
        k += 1;
    }
    k
}

fn main() {
    println!("\n=== χ(B) vs χ(⟨P,P⟩_r):  EDS multiplier vs self-Tate pairing ===\n");
    let primes = [1021u64, 1033, 2017, 4093, 1013, 2069, 3001];
    // tallies split by regime: "nondeg" = v2(r)==v2(p-1) (χ(t) can be −1),
    // "forced" = v2(r)<v2(p-1) (χ(t) structurally +1).
    let (mut nd_agree, mut nd_total) = (0usize, 0usize);
    let (mut f_forcedpos, mut f_total) = (0usize, 0usize);
    let mut valid = 0usize;
    for p in primes {
        let insts = enumerate_embedding1(p, 6, 12);
        for (a, b, pp, r) in insts {
            if let Some(s) = study(p, a, b, pp, r) {
                if s.in_mu_r && s.bilinear {
                    valid += 1;
                }
                let nondeg = v2(r) == v2(p - 1);
                let hit = s.chi_tate == s.chi_b;
                if nondeg {
                    nd_total += 1;
                    if hit {
                        nd_agree += 1;
                    }
                } else {
                    f_total += 1;
                    if s.chi_tate == 1 {
                        f_forcedpos += 1;
                    }
                }
                println!(
                    "p={p:>4} r={r:>4} v2(r)={vr} v2(p-1)={vp} [{reg}]  χ(t)={ct:+} χ(B)={cb:+}  {mark}",
                    p = p, r = r, vr = v2(r), vp = v2(p - 1),
                    reg = if nondeg { "nondeg" } else { "forced" },
                    ct = s.chi_tate, cb = s.chi_b,
                    mark = if hit { "match" } else { "DIFFER" },
                );
            }
        }
    }
    println!("\n— nondegenerate regime  v2(r)=v2(p-1)  (χ(t) can be ±1):");
    println!("    χ(B)=χ(⟨P,P⟩_r):  {}/{}", nd_agree, nd_total);
    println!("— forced regime  v2(r)<v2(p-1):");
    println!("    χ(⟨P,P⟩_r)=+1 (no info): {}/{}", f_forcedpos, f_total);
    println!("\n({} pairings validated bilinear and in μ_r)", valid);
}
