//! Area `gf2_la`: dense and sparse linear algebra over F_2 (Four Russians
//! elimination, echelon forms, rank).

use crate::harness::{Fp, Fresh, Kernel, Tier, Workload};
use cryptanalysis_suite::cryptanalysis::gf2_elim;
use rand::{rngs::StdRng, Rng, SeedableRng};

fn random_matrix(rows: usize, cols: usize, seed: u64) -> Vec<Vec<u64>> {
    let mut rng = StdRng::seed_from_u64(seed);
    let words = cols.div_ceil(64);
    (0..rows)
        .map(|_| {
            let mut row: Vec<u64> = (0..words).map(|_| rng.gen()).collect();
            if !cols.is_multiple_of(64) {
                row[words - 1] &= (1u64 << (cols % 64)) - 1;
            }
            row
        })
        .collect()
}

fn rref_fp(m: &mut [Vec<u64>], cols: usize) -> u64 {
    let rank = gf2_elim::rref(m, cols);
    let mut fp = Fp::new().usize(rank);
    for row in m.iter() {
        fp = fp.words(row);
    }
    fp.finish()
}

fn rref_random_2048() -> Box<dyn Workload> {
    Box::new(Fresh::new(random_matrix(2048, 2048, 1), |m| {
        rref_fp(m, 2048)
    }))
}

pub fn register(kernels: &mut Vec<Kernel>) {
    kernels.push(Kernel {
        id: "gf2_la/rref_random_2048",
        area: "gf2_la",
        desc: "gf2_elim::rref on a dense uniformly random 2048x2048 matrix (seed 1)",
        tier: Tier::Quick,
        setup: rref_random_2048,
    });
}
