//! Microbenchmark for the binary-field and summation-polynomial primitives.
//!
//! `cargo run --release --example f2m_field_bench`
//!
//! Times `F2mElement` mul / square / inverse at the NIST and toy field
//! sizes, `F2mPoly` division and gcd, and the one-word `Gf2` inverse,
//! and prints a checksum so the optimiser cannot drop the work.

use cryptanalysis_suite::binary_ecc::{F2mElement, F2mPoly, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::semaev_decomp::Gf2;
use std::hint::black_box;
use std::time::Instant;

fn rand_elem(state: &mut u64, m: u32) -> F2mElement {
    let mut pos = Vec::new();
    for i in 0..m {
        *state ^= *state << 13;
        *state ^= *state >> 7;
        *state ^= *state << 17;
        if *state & 1 == 1 {
            pos.push(i);
        }
    }
    F2mElement::from_bit_positions(&pos, m)
}

fn time<F: FnMut() -> u64>(label: &str, iters: u64, mut f: F) {
    let t = Instant::now();
    let mut acc = 0u64;
    for _ in 0..iters {
        acc ^= f();
    }
    let dt = t.elapsed();
    println!(
        "{label:<34} {:>10.1} ns/op   (chk {:016x})",
        dt.as_nanos() as f64 / iters as f64,
        acc
    );
}

fn main() {
    let fields: Vec<(&str, IrreduciblePoly)> = vec![
        ("F_2^16", IrreduciblePoly::deg_16()),
        ("F_2^113", IrreduciblePoly::deg_113()),
        ("F_2^131", IrreduciblePoly::deg_131()),
        ("F_2^163", IrreduciblePoly::deg_163()),
        ("F_2^233", IrreduciblePoly::deg_233()),
    ];
    let mut s = 0x9E37_79B9_7F4A_7C15u64;
    for (name, irr) in &fields {
        let m = irr.degree;
        let a0 = rand_elem(&mut s, m);
        let b0 = rand_elem(&mut s, m);
        let iters = 200_000;
        let mut a = a0.clone();
        time(&format!("{name} mul"), iters, || {
            a = a.mul(black_box(&b0), irr);
            a.raw_bits()[0]
        });
        let mut a = a0.clone();
        time(&format!("{name} square"), iters, || {
            a = a.square(irr);
            a.raw_bits()[0]
        });
        let mut a = a0.clone();
        time(&format!("{name} flt_inverse"), iters / 50, || {
            a = a.flt_inverse(irr).unwrap().add(&b0);
            a.raw_bits()[0]
        });
    }

    // Polynomial ring: division and gcd at the degrees the summation
    // polynomial and descent code reach.
    let irr = IrreduciblePoly::deg_113();
    let m = irr.degree;
    let mk = |s: &mut u64, d: usize| {
        let coeffs: Vec<F2mElement> = (0..=d).map(|_| rand_elem(s, m)).collect();
        F2mPoly::from_coeffs(coeffs, m)
    };
    let f = mk(&mut s, 32);
    let g = mk(&mut s, 16);
    time("F_2^113[x] divrem 32/16", 2_000, || {
        let (q, _r) = f.divrem(black_box(&g), &irr);
        q.coeffs[0].raw_bits()[0]
    });
    time("F_2^113[x] gcd 32,16", 200, || {
        let d = f.gcd(black_box(&g), &irr);
        d.coeffs.len() as u64
    });
    time("F_2^113[x] mul 32x16", 2_000, || {
        let p = f.mul(black_box(&g), &irr);
        p.coeffs[0].raw_bits()[0]
    });

    for (name, irr) in [
        (
            "Gf2 n=24 inv",
            cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse(24)
                .unwrap(),
        ),
        (
            "Gf2 n=53 inv",
            cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse(53)
                .unwrap(),
        ),
    ] {
        let gf = Gf2::new(&irr);
        let mask = (1u64 << gf.n) - 1;
        let mut x = 0x1234_5678_9abcu64 & mask;
        let mut y = 0x5a5a_1234u64 & mask;
        time(&format!("{name} (mul)"), 10_000_000, || {
            y = gf.mul(y, 0x1234_5677 & mask) | 1;
            y
        });
        time(&format!("{name} (sqr)"), 10_000_000, || {
            y = gf.sqr(y) | 1;
            y
        });
        time(name, 1_000_000, || {
            x = gf.inv(x | 1) ^ 0x55;
            x &= mask;
            x
        });
    }

    // Dense index-calculus linear algebra: Gauss-Jordan mod a 61-bit
    // prime, the word-sized case every toy-to-mid-size curve hits.
    {
        use cryptanalysis_suite::cryptanalysis::ec_index_calculus::gaussian_eliminate_mod_n;
        use num_bigint::BigUint;
        let n = (1u64 << 61) - 1;
        let nb = BigUint::from(n);
        let dim = 120usize;
        let mut st = 0x1234_5678_9ABC_DEF1u64;
        let mut nx = || {
            st ^= st << 13;
            st ^= st >> 7;
            st ^= st << 17;
            st
        };
        let mat: Vec<Vec<BigUint>> = (0..dim + 10)
            .map(|_| (0..dim).map(|_| BigUint::from(nx() % n)).collect())
            .collect();
        let rhs: Vec<BigUint> = (0..dim + 10).map(|_| BigUint::from(nx() % n)).collect();
        time("gauss mod 2^61-1, 130x120", 3, || {
            let (mut m, mut r) = (mat.clone(), rhs.clone());
            let sol = gaussian_eliminate_mod_n(&mut m, &mut r, black_box(&nb)).unwrap();
            sol[0].to_u64_digits().first().copied().unwrap_or(0)
        });
    }
}
