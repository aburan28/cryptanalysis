//! Working MOV attack on a supersingular curve via the F_{p²} distortion
//! Tate pairing — §5.10 of `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`.
//!
//! ```bash
//! cargo run --release --example eds_mov_demo
//! ```
//!
//! This is the one regime where the EDS / elliptic-net → pairing machinery
//! actually breaks the ECDLP: y²=x³+x over p≡3 (mod 4) is supersingular
//! (embedding degree 2), and the distortion pairing transfers the ECDLP into
//! a DLP in the small group μ_r ⊂ F_{p²}*.

use cryptanalysis_suite::cryptanalysis::eds_mov::{modified_tate, mov_solve, point_of_order};
use cryptanalysis_suite::cryptanalysis::eds_tate::{ec_mul, ec_order};

fn main() {
    println!("\n=== MOV attack on a supersingular curve (EDS → pairing) ===\n");
    let (p, a, b) = (1283u64, 1u64, 0u64); // y²=x³+x, 1283 ≡ 3 (mod 4)
    let r = 107u64; // 107 | p+1 = 1284  (#E = p+1, embedding degree 2)
    println!(
        "E: y²=x³+x / F_{p}   supersingular (#E=p+1={n})",
        p = p,
        n = p + 1
    );
    println!("p ≡ 3 (mod 4); distortion φ(x,y)=(−x, iy), i²=−1 ∈ F_{{p²}}\n");

    let pp = point_of_order(p, a, b, r).expect("order-r point");
    println!("P = ({}, {})  of order r = {}", pp.0, pp.1, r);
    let alpha = modified_tate(pp, pp, r, a, p).expect("pairing");
    println!(
        "t_r(P, φ(P)) = {:?} ∈ μ_{}  (nondegenerate: {})\n",
        alpha,
        r,
        alpha != (1, 0)
    );

    println!("Transferring ECDLP Q=[k]P  →  DLP  α^k = β  in μ_{}:", r);
    for k_true in [7u64, 42, 99, 106] {
        let qq = ec_mul(k_true, Some(pp), a, p).unwrap();
        let ord_q = ec_order(Some(qq), a, p, r + 1).unwrap();
        let k = mov_solve(pp, qq, r, a, p).expect("solved");
        println!(
            "  Q=[{:>3}]P (ord {})  →  recovered k = {:>3}   {}",
            k_true,
            ord_q,
            k,
            if k == k_true { "✓" } else { "✗" }
        );
    }
    println!(
        "\nThe EDS/net handle is inert on generic curves (no sub-√m attack),\n\
         but it *computes the pairing* — and on supersingular / low-embedding\n\
         curves the pairing collapses the ECDLP to an easy F_{{p²}}* DLP. That is\n\
         exactly the Lauter–Stange 'EDS Association ⇒ weak curve' boundary.\n"
    );
}
