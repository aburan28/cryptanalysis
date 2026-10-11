//! Elliptic-divisibility-sequence / EDS-Residue structural sweep.
//!
//! ```bash
//! cargo run --release --example eds_residue_demo
//! ```
//!
//! Builds the EDS `W_{E,P}` over `F_p` for several toy curves, verifies the
//! rank-of-apparition law and the Ward/Lauter–Stange shift multiplier, and
//! reports the Legendre-character invariants `(χ(A), χ(B))` plus the QR
//! balance of the apparition block.  Companion to `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`.

use cryptanalysis_suite::cryptanalysis::eds_residue::{
    analyze, find_toy_point, format_report, recover_dl_from_net_zeros,
};
use num_bigint::BigUint;

fn run(p: u64, a: u64, b: u64) {
    let (pp, aa, bb) = (BigUint::from(p), BigUint::from(a), BigUint::from(b));
    if let Some((px, py, ord)) = find_toy_point(&pp, &aa, &bb, 1, 7) {
        let r = analyze(&pp, &aa, &bb, &px, &py);
        println!("{}", format_report(&r));
        // DL recovery from the 2-D net zero-lattice.
        let k_true = (ord / 3).max(2) % ord;
        if let Some((k_rec, (za, zb))) =
            recover_dl_from_net_zeros(&px, &py, &aa, &pp, ord, k_true, ord + 1)
        {
            println!(
                "  net zero-lattice: Q=[{}]P recovered k={} from zero (a,b)=({},{})  {}\n",
                k_true,
                k_rec,
                za,
                zb,
                if k_rec == k_true { "✓" } else { "✗" }
            );
        }
    } else {
        println!("no suitable point on y²=x³+{}x+{} mod {}\n", a, b, p);
    }
}

fn main() {
    println!("\n=== EDS-Residue structural sweep ===\n");
    // A spread of toy curves / primes (all ≡ 1 and ≡ 3 mod 4 represented).
    run(1009, 37, 2);
    run(1013, 5, 7);
    run(2003, 11, 19);
    run(7919, 3, 8);
    run(10007, 17, 23);
}
