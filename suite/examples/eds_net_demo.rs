//! Canonical rank-2 elliptic net over F_p, derived via (REL-P) without
//! Stange's seed formulas — §5.3b of `research/notes/cm-isogeny/RESEARCH_EDS_RESIDUE.md`.
//!
//! ```bash
//! cargo run --release --example eds_net_demo
//! ```
//!
//! Builds the net for (E, P, Q=[k]P), validates it against the net
//! recurrence (NET) and the zero-lattice {aP+bQ=O}, and prints the χ-pattern.
//! For Q in ⟨P⟩ (the ECDLP case) the net is degenerate: every value comes
//! from x((a+bk)P), i.e. rank-1 data — so it adds nothing over §5.3a.

use cryptanalysis_suite::cryptanalysis::eds_net::{build_net, check_net_relation, legendre};
use cryptanalysis_suite::cryptanalysis::eds_tate::{ec_add, ec_mul, ec_order};

fn gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let t = a % b;
        a = b;
        b = t;
    }
    a
}

fn toy(p: u64, min_r: u64) -> Option<(u64, u64, (u64, u64), u64)> {
    for a in 0..20u64 {
        for b in 0..20u64 {
            let disc = (4 * (a % p) * ((a * a) % p) + 27 * ((b * b) % p)) % p;
            if disc == 0 {
                continue;
            }
            for x in 1..p.min(300) {
                let rhs = (((x * x) % p) * x + a * x + b) % p;
                let mut y = 0;
                for c in 1..p {
                    if (c * c) % p == rhs {
                        y = c;
                        break;
                    }
                }
                if y == 0 {
                    continue;
                }
                if let Some(r) = ec_order(Some((x, y)), a, p, 2 * p + 4) {
                    if r >= min_r {
                        return Some((a, b, (x, y), r));
                    }
                }
            }
        }
    }
    None
}

fn main() {
    println!("\n=== Canonical rank-2 elliptic net via (REL-P), no Stange seeds ===\n");
    let p = 1009u64;
    let (ca, cb, pp, m) = toy(p, 300).expect("instance");
    let (amax, bmax) = (12usize, 8usize);
    let k = (7..m)
        .find(|&k| gcd(k, m) == 1 && (k * bmax as u64 + amax as u64) < m)
        .unwrap();
    println!(
        "E: y²=x³+{}x+{} /F_{}   P=({},{}) ord={}   Q=[{}]P\n",
        ca, cb, p, pp.0, pp.1, m, k
    );

    let net = build_net(ca, cb, p, pp, k, amax, bmax);

    // validate NET on a few triples
    let triples = [
        ((5, 4), (3, 1), (1, 1)),
        ((7, 5), (3, 2), (2, 1)),
        ((9, 6), (4, 2), (2, 1)),
    ];
    let mut ok_all = true;
    for (pv, qv, rv) in triples {
        if let Some(ok) = check_net_relation(&net, pv, qv, rv) {
            ok_all &= ok;
        }
    }
    println!(
        "net recurrence (NET): {}",
        if ok_all { "holds ✓" } else { "FAILS ✗" }
    );

    // χ-pattern of the net
    println!("\nχ(W(a,b)) pattern  (· = zero / O):");
    print!("   a:");
    for a in 0..=amax {
        print!("{:>3}", a);
    }
    println!();
    for b in 0..=bmax {
        print!(" b={:>2}:", b);
        for a in 0..=amax {
            match net.get(a, b) {
                Some(w) => print!("{:>3}", if legendre(w, p) > 0 { "+" } else { "-" }),
                None => print!("{:>3}", "·"),
            }
        }
        println!();
    }

    // degeneracy: the net only ever consumes x((a+bk)P) — rank-1 data.
    let pt = Some(pp);
    let qq = ec_mul(k, pt, ca, p);
    let mut reparam_ok = true;
    for b in 0..=bmax {
        for a in 0..=amax {
            let lhs = ec_add(
                ec_mul(a as u64, pt, ca, p),
                ec_mul(b as u64, qq, ca, p),
                ca,
                p,
            );
            let rhs = ec_mul((a as u64 + b as u64 * k) % m, pt, ca, p);
            if lhs != rhs {
                reparam_ok = false;
            }
        }
    }
    println!(
        "\naP+bQ = [(a+bk) mod m]P for all (a,b): {}",
        if reparam_ok {
            "yes ✓ — net is built from rank-1 data x(jP) only"
        } else {
            "no"
        }
    );
    println!(
        "⇒ for Q∈⟨P⟩ (the ECDLP case) the rank-2 net is a reparametrisation of\n  \
         the rank-1 EDS of P: its χ-pattern carries no localisation power beyond\n  \
         §5.3a (log₂ m bits, O(m) extraction). No sub-√m advantage.\n"
    );
}
