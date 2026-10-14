//! Runs one arm over `words` words generated in memory from a seed.
//!
//! usage: bench <arm> <uniform|structured> <words> <seed> [reps]
//!
//! Under cachegrind the arm's own Ir is read from its `canon131_<arm>`
//! symbol (cg_annotate); `reps = 0` skips the wall clock.  With reps > 0 it
//! prints the median ns/word over `reps` passes — an UNISOLATED,
//! exploratory wall time.  `arm = fmul` times the 131-bit multiply proxy.

use canon_n131::*;
use std::hint::black_box;
use std::time::Instant;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let arm = a[1].clone();
    let dist = a[2].clone();
    let words: usize = a[3].parse().unwrap();
    let seed: u64 = a[4].parse().unwrap();
    let reps: usize = a.get(5).map(|s| s.parse().unwrap()).unwrap_or(1);
    let mut rng = Rng(seed);
    let xs: Vec<W3> = (0..words)
        .map(|_| if dist == "uniform" { rng.word131() } else { structured131(&mut rng) })
        .collect();
    let mut times = vec![];
    let mut check = 0u64;
    for _ in 0..reps.max(1) {
        let t0 = Instant::now();
        if arm == "fmul" {
            let mut acc = xs[0];
            for x in &xs {
                let mut o = [0u64; 3];
                assert!(is_x86_feature_detected!("pclmulqdq"));
                unsafe { fmul131_clmul(black_box(&acc), x, &mut o) };
                acc = o;
            }
            check ^= acc[0];
        } else {
            let f = ARMS.iter().find(|(n, _)| *n == arm).expect("arm").1;
            let mut o = [0u64; 3];
            for x in &xs {
                let s = f(black_box(x), &mut o);
                check = check.wrapping_add(o[0] ^ o[1] ^ o[2] ^ s as u64);
            }
        }
        times.push(t0.elapsed().as_nanos() as f64 / words as f64);
    }
    times.sort_by(|a, b| a.partial_cmp(b).unwrap());
    println!(
        "{{\"arm\":\"{arm}\",\"distribution\":\"{dist}\",\"words\":{words},\"seed\":{seed},\"reps\":{reps},\
\"median_ns_per_word_unisolated\":{:.3},\"min_ns\":{:.3},\"max_ns\":{:.3},\"checksum\":{check}}}",
        times[times.len() / 2], times[0], times[times.len() - 1]
    );
}
