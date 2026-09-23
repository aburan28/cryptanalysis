//! **A signed-Frobenius rho built from the suite's fast primitives.**
//!
//! The crossover fixtures compare the direct index-calculus route against
//! `koblitz_rho_fixture`, whose walk stores every point, canonicalises by
//! a squaring chain on both coordinates, and inverts once per step.  That
//! is a correct control and a slow one.  This walk is the same algorithm
//! with the costs a rho implementation would normally not pay removed:
//!
//! - `W` walks per thread step together, so one inversion serves `W`
//!   additions (`FastCurve::add_pairwise`, Montgomery's trick);
//! - the orbit is named in a normal basis (`FrobeniusCanon`), where the
//!   Frobenius is a rotation — the rotation that names it is also the
//!   power of `π` that maps the point onto its representative;
//! - only distinguished points are stored.
//!
//! One cost is left in on purpose, in index calculus's favour: moving
//! `y` onto the representative is up to `n − 1` squarings rather than a
//! second basis rotation.
//!
//! Fruitless 2-cycles, which the negation map makes about one step in
//! `2·JUMPS`, are escaped by doubling the lesser of the two points: a
//! function of the cycle alone, so walks that meet in it still merge.
//!
//! Known-answer control only: the target is `[d]G` for a published
//! scalar, recovered from a collision and accepted only after
//! `[d]G = Q` is checked independently.
//!
//! Usage: `koblitz_batched_rho <n> <a> <scalar> [threads] [walks_per_thread] [dist_bits] [seed]`

use std::collections::HashMap;
use std::time::Instant;

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{
    BatchScratch, FastCurve, FastPoint, FrobeniusCanon,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use rayon::prelude::*;
use serde_json::json;

const JUMPS: usize = 32;
/// Steps each walk takes between merges of the distinguished tables.
const ROUND: usize = 256;

fn mulmod(a: u64, b: u64, r: u64) -> u64 {
    ((a as u128 * b as u128) % r as u128) as u64
}

fn addmod(a: u64, b: u64, r: u64) -> u64 {
    let s = a as u128 + b as u128;
    (s % r as u128) as u64
}

fn negmod(a: u64, r: u64) -> u64 {
    if a == 0 {
        0
    } else {
        r - a
    }
}

fn invmod(a: u64, r: u64) -> u64 {
    let mut result = 1u64;
    let (mut base, mut e) = (a % r, r - 2);
    while e != 0 {
        if e & 1 == 1 {
            result = mulmod(result, base, r);
        }
        base = mulmod(base, base, r);
        e >>= 1;
    }
    result
}

fn mix(v: u64) -> u64 {
    let mut z = v.wrapping_mul(0x9e37_79b9_7f4a_7c15);
    z ^= z >> 31;
    z = z.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    z ^ (z >> 29)
}

struct Ctx {
    fc: FastCurve,
    canon: FrobeniusCanon,
    n: u32,
    mask: u64,
    r: u64,
    /// `λ^i mod r`, the scalar by which `π^i` acts on the subgroup.
    lambda_pow: Vec<u64>,
    jumps: Vec<(FastPoint, u64, u64)>,
    dist_mask: u64,
}

#[derive(Clone, Copy)]
struct Walk {
    p: FastPoint,
    a: u64,
    b: u64,
    /// Orbit key two steps back, for 2-cycle detection.
    prev_key: u64,
    prev2_key: u64,
    steps: u64,
}

impl Ctx {
    /// The orbit representative of `±π^i(P)` and its key, with the
    /// scalar the representative carries relative to `P`.
    fn canonical(&self, p: FastPoint) -> (FastPoint, u64, bool, u64) {
        let c = self.canon.coords(p.x);
        let n = self.n;
        let (mut best, mut best_i, mut v) = (c, 0u32, c);
        for i in 1..n {
            v = ((v << 1) | (v >> (n - 1))) & self.mask;
            if v < best {
                best = v;
                best_i = i;
            }
        }
        let f = &self.fc.field;
        let (x, y) = (f.sqr_k(p.x, best_i), f.sqr_k(p.y, best_i));
        let negate = y > (x ^ y);
        let rep = FastPoint::affine(x, if negate { x ^ y } else { y });
        (rep, self.lambda_pow[best_i as usize], negate, best)
    }

    fn apply(&self, w: &mut Walk, sum: FastPoint, da: u64, db: u64) -> u64 {
        let r = self.r;
        let a = addmod(w.a, da, r);
        let b = addmod(w.b, db, r);
        let (rep, mult, negate, key) = self.canonical(sum);
        let (mut a, mut b) = (mulmod(a, mult, r), mulmod(b, mult, r));
        if negate {
            a = negmod(a, r);
            b = negmod(b, r);
        }
        w.p = rep;
        w.a = a;
        w.b = b;
        key
    }

    /// A walk started at `aG + bQ` for random `a, b`: two scalar
    /// multiplications, paid once per walk slot.
    fn fresh(&self, rng: &mut StdRng, g: FastPoint, q: FastPoint) -> Walk {
        loop {
            let a = rng.gen_range(1..self.r);
            let b = rng.gen_range(1..self.r);
            let p = self.fc.add(self.fc.mul_u64(g, a), self.fc.mul_u64(q, b));
            if p.infinity {
                continue;
            }
            return self.start(p, a, b);
        }
    }

    fn start(&self, p: FastPoint, a: u64, b: u64) -> Walk {
        let mut w = Walk {
            p,
            a: 0,
            b: 0,
            prev_key: u64::MAX,
            prev2_key: u64::MAX,
            steps: 0,
        };
        let key = self.apply(&mut w, p, a, b);
        w.prev_key = key;
        w
    }

    /// Restart a slot from where its walk ended, moved by a fixed offset
    /// no jump shares: one addition instead of two scalar
    /// multiplications.  The new start is still `aG + bQ` with known
    /// `a, b`, and distinct endpoints give distinct starts.
    fn restart(
        &self,
        w: &Walk,
        offset: (FastPoint, u64, u64),
        rng: &mut StdRng,
        g: FastPoint,
        q: FastPoint,
    ) -> Walk {
        let p = self.fc.add(w.p, offset.0);
        if p.infinity {
            return self.fresh(rng, g, q);
        }
        self.start(
            p,
            addmod(w.a, offset.1, self.r),
            addmod(w.b, offset.2, self.r),
        )
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let n: u32 = args[1].parse().unwrap();
    let a_coef: u8 = args[2].parse().unwrap();
    let scalar: u64 = args[3].parse().unwrap();
    let threads: usize = args.get(4).map_or(1, |s| s.parse().unwrap());
    let walks: usize = args.get(5).map_or(64, |s| s.parse().unwrap());
    let dist_bits: u32 = args.get(6).map_or(6, |s| s.parse().unwrap());
    let seed: u64 = args.get(7).map_or(1, |s| s.parse().unwrap());

    let setup = Instant::now();
    let kc = KoblitzCurve::new(a_coef, n).expect("curve");
    let fc = FastCurve::new(&kc.curve).expect("fast curve");
    let canon = FrobeniusCanon::new(&fc.field, n).expect("normal basis");
    let r = kc.subgroup_order.to_u64().unwrap();
    let lambda = kc.lambda.to_u64().unwrap();
    let g = fc.lift(kc.generator());
    let q = fc.mul_u64(g, scalar);
    // π acts on the subgroup as λ: check the orientation the walk relies on.
    assert_eq!(fc.frobenius_k(g, 1), fc.mul_u64(g, lambda), "π(G) = λG");
    let mut lambda_pow = vec![1u64; n as usize];
    for i in 1..n as usize {
        lambda_pow[i] = mulmod(lambda_pow[i - 1], lambda, r);
    }
    let mut rng = StdRng::seed_from_u64(seed);
    let jumps: Vec<_> = (0..JUMPS)
        .map(|_| {
            let (c, d) = (rng.gen_range(1..r), rng.gen_range(1..r));
            (fc.add(fc.mul_u64(g, c), fc.mul_u64(q, d)), c, d)
        })
        .collect();
    let ctx = Ctx {
        fc,
        canon,
        n,
        mask: (1u64 << n) - 1,
        r,
        lambda_pow,
        jumps,
        dist_mask: (1u64 << dist_bits) - 1,
    };
    let setup_ms = setup.elapsed().as_secs_f64() * 1e3;

    let pool = rayon::ThreadPoolBuilder::new()
        .num_threads(threads)
        .build()
        .unwrap();
    let started = Instant::now();
    let mut states: Vec<(Vec<Walk>, StdRng, BatchScratch, (FastPoint, u64, u64))> = (0..threads)
        .map(|t| {
            let mut trng = StdRng::seed_from_u64(mix(seed ^ (t as u64 + 1)));
            let ws = (0..walks).map(|_| ctx.fresh(&mut trng, g, q)).collect();
            let (c, d) = (trng.gen_range(1..r), trng.gen_range(1..r));
            let offset = (ctx.fc.add(ctx.fc.mul_u64(g, c), ctx.fc.mul_u64(q, d)), c, d);
            (ws, trng, BatchScratch::default(), offset)
        })
        .collect();
    let mut table: HashMap<(u64, u64), (u64, u64)> = HashMap::new();
    let mut total_steps = 0u64;
    let mut doublings = 0u64;
    let mut restarts = 0u64;
    let mut useless = 0u64;
    let max_walk = 40u64 << dist_bits;
    let recovered = 'outer: loop {
        let outputs: Vec<(Vec<(FastPoint, u64, u64)>, u64, u64, u64)> = pool.install(|| {
            states
                .par_iter_mut()
                .map(|(ws, trng, scratch, offset)| {
                    let mut found = Vec::new();
                    let (mut dbl, mut rst, mut steps) = (0u64, 0u64, 0u64);
                    let mut addends = Vec::with_capacity(ws.len());
                    let mut ps = Vec::with_capacity(ws.len());
                    let mut sums = Vec::with_capacity(ws.len());
                    let mut which = Vec::with_capacity(ws.len());
                    for _ in 0..ROUND {
                        addends.clear();
                        ps.clear();
                        which.clear();
                        for w in ws.iter() {
                            let j = (mix(w.prev_key) >> 59) as usize % JUMPS;
                            ps.push(w.p);
                            addends.push(ctx.jumps[j].0);
                            which.push(j);
                        }
                        sums.clear();
                        ctx.fc.add_pairwise(&ps, &addends, &mut sums, scratch);
                        for (i, w) in ws.iter_mut().enumerate() {
                            let (_, c, d) = ctx.jumps[which[i]];
                            let mut key = if sums[i].infinity {
                                u64::MAX
                            } else {
                                ctx.apply(w, sums[i], c, d)
                            };
                            steps += 1;
                            w.steps += 1;
                            if key == w.prev2_key && key != u64::MAX {
                                // Fruitless 2-cycle {A = w.p, B = step(A)}:
                                // double whichever has the lesser key, so
                                // the escape depends on the cycle and not on
                                // which of its two points a walk arrived at.
                                if w.prev_key < key {
                                    let j = (mix(key) >> 59) as usize % JUMPS;
                                    let (jp, jc, jd) = ctx.jumps[j];
                                    let other = ctx.fc.add(w.p, jp);
                                    ctx.apply(w, other, jc, jd);
                                }
                                let doubled = ctx.fc.double(w.p);
                                let (a2, b2) = (w.a, w.b);
                                w.a = 0;
                                w.b = 0;
                                key = ctx.apply(
                                    w,
                                    doubled,
                                    addmod(a2, a2, ctx.r),
                                    addmod(b2, b2, ctx.r),
                                );
                                dbl += 1;
                            }
                            if key == u64::MAX || w.steps > max_walk {
                                *w = ctx.restart(w, *offset, trng, g, q);
                                rst += 1;
                                continue;
                            }
                            w.prev2_key = w.prev_key;
                            w.prev_key = key;
                            if mix(key ^ 0x5555) & ctx.dist_mask == 0 {
                                found.push((w.p, w.a, w.b));
                                *w = ctx.restart(w, *offset, trng, g, q);
                            }
                        }
                    }
                    (found, dbl, rst, steps)
                })
                .collect()
        });
        for (found, dbl, rst, steps) in outputs {
            doublings += dbl;
            restarts += rst;
            total_steps += steps;
            for (p, a, b) in found {
                match table.get(&(p.x, p.y)) {
                    Some(&(a0, b0)) if b0 != b => {
                        // a0 G + b0 Q = a G + b Q  ⇒  d = (a − a0)/(b0 − b).
                        let num = addmod(a, negmod(a0, r), r);
                        let den = addmod(b0, negmod(b, r), r);
                        let d = mulmod(num, invmod(den, r), r);
                        if ctx.fc.mul_u64(g, d) == q {
                            break 'outer d;
                        }
                        useless += 1;
                    }
                    Some(_) => useless += 1,
                    None => {
                        table.insert((p.x, p.y), (a, b));
                    }
                }
            }
        }
    };
    let walk_ms = started.elapsed().as_secs_f64() * 1e3;
    let verified =
        recovered == scalar && kc.mul(kc.generator(), &BigUint::from(recovered)) == ctx.fc.lower(q);
    let ideal = (std::f64::consts::PI * r as f64 / (4.0 * n as f64)).sqrt();
    println!(
        "{}",
        json!({
            "kind": "batched_signed_frobenius_rho",
            "n": n,
            "subgroup_order": r,
            "published_q": [q.x, q.y],
            "scalar": scalar,
            "recovered": recovered,
            "verified": verified,
            "threads": threads,
            "walks_per_thread": walks,
            "dist_bits": dist_bits,
            "seed": seed,
            "steps": total_steps,
            "ideal_steps": ideal,
            "distinguished_stored": table.len(),
            "doublings": doublings,
            "restarts": restarts,
            "useless_collisions": useless,
            "setup_ms": setup_ms,
            "walk_ms": walk_ms,
            "ns_per_step_wall": walk_ms * 1e6 / total_steps as f64,
        })
    );
    assert!(verified, "recovered scalar failed [d]G = Q");
}
