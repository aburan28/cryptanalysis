//! **What the orbit fold would cost per probe, against what it saves.**
//!
//! Folding the pair table by `⟨π, −1⟩` divides the stored pairs by `2n`
//! and so multiplies the affordable base by `√(2n)` and divides the
//! descent's `2r/|F|²` probes by `2n`.  The price is canonicalising each
//! looked-up point: the least abscissa in its Frobenius orbit, which is
//! `n − 1` squarings and a running minimum.
//!
//! Whether that trade is worth taking is an arithmetic-against-memory
//! question, and this measures both sides on the machine that would run
//! it.  Three canonicalisations are timed: the obvious serial chain, the
//! same chain over independent lanes (a decomposition scan has `|F|`
//! independent rests in flight, so the chain need not be latency-bound),
//! and a squaring that reduces by shifts when the field's irreducible is
//! sparse enough to allow it.
//!
//! The memory side is a dependent random access over a real Sattolo
//! cycle, which is the only pointer chase that cannot be prefetched.

use std::time::Instant;

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_fast::{FastCurve, FrobeniusCanon};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};

const LANES: usize = 8;

fn main() {
    let degree: u32 = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(61);
    let kc = KoblitzCurve::new(0, degree).expect("curve");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let n = fc.n;
    let irr = &kc.curve.irreducible;
    println!("n = {n}, irreducible z^{n} + {:?}", irr.low_terms);
    let _ = F2mElement::from_bit_positions(&[0], n);

    let mask = if n == 64 { !0u64 } else { (1u64 << n) - 1 };
    let mut rng = StdRng::seed_from_u64(1);
    let sample: Vec<u64> = (0..1 << 14).map(|_| rng.gen::<u64>() & mask).collect();

    // (a) serial canonicalisation.
    let iters = 200_000usize;
    let start = Instant::now();
    let mut acc = 0u64;
    for t in 0..iters {
        let mut v = sample[t & (sample.len() - 1)];
        let mut best = v;
        for _ in 1..n {
            v = fc.field.sqr(v);
            best = best.min(v);
        }
        acc ^= best;
    }
    let serial_ns = start.elapsed().as_secs_f64() * 1e9 / iters as f64;

    // (b) the same chain over LANES independent points.
    let start = Instant::now();
    let rounds = iters / LANES;
    for t in 0..rounds {
        let mut v = [0u64; LANES];
        let mut best = [0u64; LANES];
        for l in 0..LANES {
            v[l] = sample[(t * LANES + l) & (sample.len() - 1)];
            best[l] = v[l];
        }
        for _ in 1..n {
            for l in 0..LANES {
                v[l] = fc.field.sqr(v[l]);
                best[l] = best[l].min(v[l]);
            }
        }
        for l in 0..LANES {
            acc ^= best[l];
        }
    }
    let lanes_ns = start.elapsed().as_secs_f64() * 1e9 / (rounds * LANES) as f64;

    // (c) squaring that reduces by shifts, for a sparse irreducible.
    let sparse = irr.low_terms.len() <= 4 && irr.low_terms.iter().all(|&t| t < n / 2);
    let mut shift_ns = f64::NAN;
    if sparse {
        let terms: Vec<u32> = irr.low_terms.clone();
        let sqr_shift = |a: u64| -> u64 {
            // spread the bits, then fold the high half down by the
            // irreducible's low terms: z^n ≡ Σ z^t.
            let lo = spread32(a);
            let hi = spread32(a >> 32);
            let mut w = (lo as u128) | ((hi as u128) << 64);
            for _ in 0..2 {
                let high = (w >> n) as u128;
                if high == 0 {
                    break;
                }
                w &= (1u128 << n) - 1;
                for &t in &terms {
                    w ^= high << t;
                }
            }
            (w as u64) & mask
        };
        // agreement check
        let mut agree = true;
        for &s in sample.iter().take(256) {
            if sqr_shift(s) != fc.field.sqr(s) {
                agree = false;
                break;
            }
        }
        let start = Instant::now();
        let rounds = iters / LANES;
        for t in 0..rounds {
            let mut v = [0u64; LANES];
            let mut best = [0u64; LANES];
            for l in 0..LANES {
                v[l] = sample[(t * LANES + l) & (sample.len() - 1)];
                best[l] = v[l];
            }
            for _ in 1..n {
                for l in 0..LANES {
                    v[l] = sqr_shift(v[l]);
                    best[l] = best[l].min(v[l]);
                }
            }
            for l in 0..LANES {
                acc ^= best[l];
            }
        }
        shift_ns = start.elapsed().as_secs_f64() * 1e9 / (rounds * LANES) as f64;
        println!("shift-reduce squaring agrees with the field: {agree}");
    } else {
        println!("irreducible is not sparse enough for a shift reduce; skipping (c)");
    }

    // (c2) the same canonicalisation in a normal basis, where the
    // Frobenius is a rotation of the coordinate word: one byte-table
    // change of basis, then `n − 1` rotations and a running minimum.
    // No field arithmetic, and no dependency chain, so this is timed
    // one point at a time — the lane trick has nothing left to hide.
    let nb = FrobeniusCanon::new(&fc.field, n).expect("a normal element");
    {
        let mut agree = true;
        for &s in sample.iter().take(4096) {
            let mut v = s;
            let mut best = s;
            for _ in 1..n {
                v = fc.field.sqr(v);
                best = best.min(v);
            }
            // Different representative, same orbit: what must agree is
            // that two elements share a key exactly when they share an
            // orbit, which the library tests check by enumeration.  Here
            // it is enough that the orbit's own images all key alike.
            if nb.canon(s) != nb.canon(best) {
                agree = false;
                break;
            }
        }
        println!("normal-basis key is constant on the Frobenius orbit: {agree}");
    }
    let start = Instant::now();
    for t in 0..iters {
        acc ^= nb.canon(sample[t & (sample.len() - 1)]);
    }
    let nb_ns = start.elapsed().as_secs_f64() * 1e9 / iters as f64;

    // (d) a real dependent random access, over a Sattolo cycle.
    for &log_bytes in &[27u32, 30, 32] {
        let entries = (1usize << log_bytes) / 8;
        if entries * 8 > 6 << 30 {
            continue;
        }
        let mut next: Vec<u64> = (0..entries as u64).collect();
        // Sattolo: one single cycle through every slot.
        let mut r = StdRng::seed_from_u64(7);
        for i in (1..entries).rev() {
            let j = r.gen_range(0..i);
            next.swap(i, j);
        }
        // turn the permutation into a chase: slot i points at next[i]
        let probes = 5_000_000u64;
        let mut idx = 0usize;
        let start = Instant::now();
        for _ in 0..probes {
            idx = next[idx] as usize;
        }
        let probe_ns = start.elapsed().as_secs_f64() * 1e9 / probes as f64;
        acc ^= idx as u64;
        let sqr_canon = if shift_ns.is_nan() {
            lanes_ns
        } else {
            shift_ns.min(lanes_ns)
        };
        let fold = 2.0 * n as f64;
        println!(
            "table {:>4} MiB: probe {probe_ns:6.1} ns | canon serial {serial_ns:6.1} \
             lanes {lanes_ns:6.1} shift {shift_ns:6.1} nb {nb_ns:6.1} | fold {fold:.0}x probes",
            (1usize << log_bytes) >> 20,
        );
        for (name, canon) in [("squarings", sqr_canon), ("normal basis", nb_ns)] {
            println!(
                "                  {name:>12}: {:.2}x per probe -> net {:.1}x",
                (probe_ns + canon) / probe_ns,
                fold * probe_ns / (probe_ns + canon)
            );
        }
    }
    println!("(checksum {acc})");
}

#[inline]
fn spread32(x: u64) -> u64 {
    let mut x = x & 0xFFFF_FFFF;
    x = (x | (x << 16)) & 0x0000_FFFF_0000_FFFF;
    x = (x | (x << 8)) & 0x00FF_00FF_00FF_00FF;
    x = (x | (x << 4)) & 0x0F0F_0F0F_0F0F_0F0F;
    x = (x | (x << 2)) & 0x3333_3333_3333_3333;
    x = (x | (x << 1)) & 0x5555_5555_5555_5555;
    x
}
