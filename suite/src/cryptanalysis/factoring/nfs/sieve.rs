//! Factor bases and the **line siever** for the NFS.
//!
//! A pair `(a, b)` with `gcd(a, b) = 1`, `b > 0` is a *relation* when
//! both norms are smooth:
//!
//! - rational: `a − b·m`, divisible by `p` iff `a ≡ b·m (mod p)`;
//! - algebraic: `F(a, b) = bᵈ f(a/b)`, divisible by `p` iff `a ≡ b·r
//!   (mod p)` for a root `r` of `f` mod `p` — the prime ideal `(p, α − r)`
//!   of degree one — or `p | b` when `p` divides the leading coefficient
//!   (the *projective* root, stored as `r = p`).
//!
//! For each line `b = 1, 2, …` the siever walks `a ∈ [−A, A)` in blocks of
//! 64 KiB, adding rounded `log₂ p` at every hit of every factor-base
//! prime `p ≥ 30` on each side (one byte per cell per side).  A cell
//! survives if both sums reach `log₂|norm| − log₂(large prime bound) −
//! slack`, the norm logs being estimated in floating point once per 1024
//! cells.  Survivors are factored exactly: primes below 2¹⁰ by checking
//! their roots, larger primes by **resieving** the block against the few
//! survivor cells, and the leftover cofactor must be 1 or a single large
//! prime (below `bound²`, so it is automatically prime).
//!
//! This is the classical line siever of the early NFS factorisations;
//! lattice sieving (Pollard 1993; Franke–Kleinjung) is several times
//! faster at scale and is not implemented.

use num_bigint::{BigInt, BigUint, Sign};
use num_integer::Integer;
use num_traits::{ToPrimitive, Zero};

use super::super::arith::{big_mod_u64, gcd_i64, inv_mod, mul_mod, primes_up_to};
use super::poly::{fp, IntPoly};

/// A factor-base entry: prime `p`, root `r` (`m mod p` on the rational
/// side, a root of `f` on the algebraic side) and its rounded `log₂ p`.
#[derive(Clone, Copy, Debug)]
pub struct FbEntry {
    /// The prime.
    pub p: u32,
    /// The root.
    pub r: u32,
    /// Rounded `log₂ p`.
    pub log: u8,
}

/// Rational and algebraic factor bases.
#[derive(Clone, Debug)]
pub struct FactorBases {
    /// Rational side: one entry per prime `p ≤ rat_bound`.
    pub rat: Vec<FbEntry>,
    /// Algebraic side: one entry per degree-one prime ideal `(p, r)`.
    pub alg: Vec<FbEntry>,
    /// Primes `≤ alg_bound` dividing the leading coefficient.
    pub alg_projective: Vec<u64>,
    /// Rational bound.
    pub rat_bound: u64,
    /// Algebraic bound.
    pub alg_bound: u64,
}

impl FactorBases {
    /// Build both factor bases for `(f, m)`.
    pub fn build(f: &IntPoly, m: &BigUint, rat_bound: u64, alg_bound: u64) -> Self {
        let log = |p: u64| (p as f64).log2().round() as u8;
        let rat = primes_up_to(rat_bound)
            .into_iter()
            .map(|p| FbEntry {
                p: p as u32,
                r: big_mod_u64(m, p) as u32,
                log: log(p),
            })
            .collect();
        let mut alg = Vec::new();
        let mut alg_projective = Vec::new();
        for p in primes_up_to(alg_bound) {
            let fpp = f.mod_p(p);
            for r in fp::roots(&fpp, p) {
                alg.push(FbEntry {
                    p: p as u32,
                    r: r as u32,
                    log: log(p),
                });
            }
            if fpp.last() == Some(&0) {
                alg_projective.push(p);
            }
        }
        FactorBases {
            rat,
            alg,
            alg_projective,
            rat_bound,
            alg_bound,
        }
    }
}

/// A relation `(a, b)` with both norms factored.
#[derive(Clone, Debug)]
pub struct Relation {
    /// `a`.
    pub a: i64,
    /// `b > 0`.
    pub b: u64,
    /// `a − b·m < 0`.
    pub rat_negative: bool,
    /// Primes of `|a − b·m|` with multiplicity.
    pub rat: Vec<u64>,
    /// Prime ideals `(p, r)` of `F(a, b)` with multiplicity (`r = p`:
    /// projective).
    pub alg: Vec<(u64, u64)>,
}

impl Relation {
    /// Number of large primes (primes above the factor-base bounds).
    pub fn large_primes(&self, rat_bound: u64, alg_bound: u64) -> usize {
        self.rat.iter().filter(|&&p| p > rat_bound).count()
            + self.alg.iter().filter(|&&(p, _)| p > alg_bound).count()
    }
}

/// Everything a sieve worker needs (shared read-only between threads).
pub struct SieveConfig<'a> {
    /// Algebraic polynomial.
    pub f: &'a IntPoly,
    /// The rational root `m` as a signed big integer.
    pub m: BigInt,
    /// `m` as a float (threshold estimates).
    pub m_f64: f64,
    /// Factor bases.
    pub fb: &'a FactorBases,
    /// Rational large-prime bound (≤ bound means acceptable cofactor).
    pub rat_lp: u64,
    /// Algebraic large-prime bound.
    pub alg_lp: u64,
    /// Threshold slack in bits (compensates skipped small primes).
    pub slack_bits: f64,
    /// Smallest prime that is sieved (smaller ones are only trial-divided).
    pub min_sieve_prime: u32,
}

/// Output of sieving one segment of one line.
#[derive(Default)]
pub struct SegmentOutput {
    /// Relations found.
    pub relations: Vec<Relation>,
    /// Survivors that were factored.
    pub candidates: u64,
    /// Cells sieved.
    pub cells: u64,
}

const BLOCK: usize = 1 << 16;
const CHUNK_SHIFT: usize = 10;
const RESIEVE_MIN: u32 = 1 << 10;

/// A norm being trial-divided: native `u128` when it fits (always, at
/// the sizes this siever reaches), `BigUint` otherwise.
enum Norm {
    Small(u128),
    Big(BigUint),
}

impl Norm {
    fn new(x: &BigUint) -> Self {
        match x.to_u128() {
            Some(v) => Norm::Small(v),
            None => Norm::Big(x.clone()),
        }
    }

    /// Divide out every power of `p`; returns the exponent.
    fn divide_out(&mut self, p: u64) -> u32 {
        let mut e = 0;
        match self {
            Norm::Small(v) => {
                let p = p as u128;
                while *v != 0 && v.is_multiple_of(p) {
                    *v /= p;
                    e += 1;
                }
            }
            Norm::Big(v) => {
                let pb = BigUint::from(p);
                loop {
                    let (q, r) = v.div_rem(&pb);
                    if !r.is_zero() {
                        break;
                    }
                    *v = q;
                    e += 1;
                }
                if let Some(s) = v.to_u128() {
                    *self = Norm::Small(s);
                }
            }
        }
        e
    }

    /// The cofactor if it is `1` (→ `Some(1)`) or a prime `≤ bound`.
    fn large_prime(&self, bound: u64) -> Option<u64> {
        match self {
            Norm::Small(v) if *v <= bound as u128 => Some(*v as u64),
            _ => None,
        }
    }
}

/// SWAR test: does any byte of `x` reach `t`?  May report false positives
/// (a carry into the next byte), never false negatives; callers re-check
/// the bytes exactly.
#[inline]
fn any_byte_ge(x: u64, t: u8) -> bool {
    const H: u64 = 0x8080_8080_8080_8080;
    if t > 128 {
        return x & H != 0;
    }
    let k = (128 - t as u64) * 0x0101_0101_0101_0101;
    (x.wrapping_add(k) | x) & H != 0
}

/// Sieve `a ∈ [lo, hi)` on line `b`.
pub fn sieve_segment(cfg: &SieveConfig, b: u64, lo: i64, hi: i64) -> SegmentOutput {
    let fb = cfg.fb;
    let len = (hi - lo) as usize;
    let mut out = SegmentOutput {
        cells: len as u64,
        ..Default::default()
    };
    // Per-line roots b·r mod p and first-hit offsets relative to `lo`.
    let line_roots = |ents: &[FbEntry]| -> Vec<u32> {
        ents.iter()
            .map(|e| mul_mod(b % e.p as u64, e.r as u64, e.p as u64) as u32)
            .collect()
    };
    let rat_rb = line_roots(&fb.rat);
    let alg_rb = line_roots(&fb.alg);
    let first = |ents: &[FbEntry], rb: &[u32]| -> Vec<u64> {
        ents.iter()
            .zip(rb)
            .map(|(e, &r)| {
                let p = e.p as i64;
                (r as i64 - lo).rem_euclid(p) as u64
            })
            .collect()
    };
    let mut rat_next = first(&fb.rat, &rat_rb);
    let mut alg_next = first(&fb.alg, &alg_rb);
    let rat_s0 = fb.rat.partition_point(|e| e.p < cfg.min_sieve_prime);
    let alg_s0 = fb.alg.partition_point(|e| e.p < cfg.min_sieve_prime);
    let rat_r0 = fb.rat.partition_point(|e| e.p < RESIEVE_MIN);
    let alg_r0 = fb.alg.partition_point(|e| e.p < RESIEVE_MIN);
    let mut rat_snap = vec![0u64; fb.rat.len()];
    let mut alg_snap = vec![0u64; fb.alg.len()];
    // Lemire's divisibility test: x < 2³² is divisible by p iff
    // x·c mod 2⁶⁴ < c with c = ⌊(2⁶⁴ − 1)/p⌋ + 1 (one multiplication).
    let magic = |ents: &[FbEntry], upto: usize| -> Vec<u64> {
        ents[..upto]
            .iter()
            .map(|e| u64::MAX / e.p as u64 + 1)
            .collect()
    };
    let rat_magic = magic(&fb.rat, rat_r0);
    let alg_magic = magic(&fb.alg, alg_r0);

    let mut rs = vec![0u8; BLOCK];
    let mut asv = vec![0u8; BLOCK];
    let mut slot = vec![u32::MAX; BLOCK];
    let rat_lp_bits = (cfg.rat_lp as f64).log2();
    let alg_lp_bits = (cfg.alg_lp as f64).log2();
    let bf = b as f64;

    let mut start = 0usize;
    while start < len {
        let bl = BLOCK.min(len - start);
        let end = (start + bl) as u64;
        rs[..bl].fill(0);
        asv[..bl].fill(0);
        rat_snap.copy_from_slice(&rat_next);
        alg_snap.copy_from_slice(&alg_next);
        for (arr, ents, next, s0) in [
            (&mut rs, &fb.rat, &mut rat_next, rat_s0),
            (&mut asv, &fb.alg, &mut alg_next, alg_s0),
        ] {
            let arr = &mut arr[..bl];
            for (e, nx) in ents[s0..].iter().zip(next[s0..].iter_mut()) {
                let p = e.p as usize;
                let mut i = (*nx as usize) - start;
                while i < arr.len() {
                    arr[i] = arr[i].wrapping_add(e.log);
                    i += p;
                }
                *nx = (start + i) as u64;
            }
        }
        // Thresholds per 1024-cell chunk.
        let nchunks = bl.div_ceil(1 << CHUNK_SHIFT);
        let mut th_r = vec![0u8; nchunks];
        let mut th_a = vec![0u8; nchunks];
        for c in 0..nchunks {
            let ac = (lo + start as i64 + ((c << CHUNK_SHIFT) + 512) as i64) as f64;
            let lr = (ac - bf * cfg.m_f64).abs().max(1.0).log2();
            let la = cfg.f.log2_hom(ac, bf);
            th_r[c] = (lr - rat_lp_bits - cfg.slack_bits).clamp(0.0, 255.0) as u8;
            th_a[c] = (la - alg_lp_bits - cfg.slack_bits).clamp(0.0, 255.0) as u8;
        }
        let mut cands: Vec<usize> = Vec::new();
        let full_words = bl / 8;
        for wi in 0..full_words {
            let c = (wi * 8) >> CHUNK_SHIFT;
            let (tr, ta) = (th_r[c], th_a[c]);
            let wr = u64::from_le_bytes(rs[wi * 8..wi * 8 + 8].try_into().expect("8 bytes"));
            let wa = u64::from_le_bytes(asv[wi * 8..wi * 8 + 8].try_into().expect("8 bytes"));
            if !any_byte_ge(wr, tr) || !any_byte_ge(wa, ta) {
                continue;
            }
            for i in wi * 8..wi * 8 + 8 {
                if rs[i] >= tr && asv[i] >= ta {
                    let a = lo + (start + i) as i64;
                    if gcd_i64(a, b as i64) == 1 {
                        cands.push(i);
                    }
                }
            }
        }
        for i in full_words * 8..bl {
            let c = i >> CHUNK_SHIFT;
            if rs[i] >= th_r[c] && asv[i] >= th_a[c] {
                let a = lo + (start + i) as i64;
                if gcd_i64(a, b as i64) == 1 {
                    cands.push(i);
                }
            }
        }
        if !cands.is_empty() {
            out.candidates += cands.len() as u64;
            for (j, &i) in cands.iter().enumerate() {
                slot[i] = j as u32;
            }
            // Resieve the large primes against the survivors.
            let mut rat_hits: Vec<Vec<u32>> = vec![Vec::new(); cands.len()];
            let mut alg_hits: Vec<Vec<u32>> = vec![Vec::new(); cands.len()];
            for (snap, ents, hits, r0) in [
                (&rat_snap, &fb.rat, &mut rat_hits, rat_r0),
                (&alg_snap, &fb.alg, &mut alg_hits, alg_r0),
            ] {
                for k in r0..ents.len() {
                    let p = ents[k].p as u64;
                    let mut pos = snap[k];
                    while pos < end {
                        let s = slot[(pos as usize) - start];
                        if s != u32::MAX {
                            hits[s as usize].push(k as u32);
                        }
                        pos += p;
                    }
                }
            }
            for (j, &i) in cands.iter().enumerate() {
                slot[i] = u32::MAX;
                let a = lo + (start + i) as i64;
                // Small primes: unsieved ones by their root, sieved ones by
                // their offset in this block.
                let small = |ents: &[FbEntry],
                             rb: &[u32],
                             s0: usize,
                             r0: usize,
                             snap: &[u64],
                             mg: &[u64]| {
                    let mut hits: Vec<u32> = Vec::new();
                    for k in 0..s0 {
                        if a.rem_euclid(ents[k].p as i64) as u32 == rb[k] {
                            hits.push(k as u32);
                        }
                    }
                    for k in s0..r0 {
                        let off = (snap[k] as usize) - start;
                        if i >= off && ((i - off) as u64).wrapping_mul(mg[k]) < mg[k] {
                            hits.push(k as u32);
                        }
                    }
                    hits
                };
                let mut rh = small(&fb.rat, &rat_rb, rat_s0, rat_r0, &rat_snap, &rat_magic);
                rh.extend_from_slice(&rat_hits[j]);
                let mut ah = small(&fb.alg, &alg_rb, alg_s0, alg_r0, &alg_snap, &alg_magic);
                ah.extend_from_slice(&alg_hits[j]);
                if let Some(rel) = factor_candidate(cfg, a, b, &rh, &ah) {
                    out.relations.push(rel);
                }
            }
        }
        start += bl;
    }
    out
}

/// Exact factorisation of both norms of a survivor.
fn factor_candidate(
    cfg: &SieveConfig,
    a: i64,
    b: u64,
    rat_hits: &[u32],
    alg_hits: &[u32],
) -> Option<Relation> {
    let fb = cfg.fb;
    // Rational side.
    let rn = BigInt::from(a) - BigInt::from(b) * &cfg.m;
    if rn.is_zero() {
        return None;
    }
    let rat_negative = rn.sign() == Sign::Minus;
    let mut v = Norm::new(rn.magnitude());
    let mut rat = Vec::new();
    for &k in rat_hits {
        let p = fb.rat[k as usize].p as u64;
        let e = v.divide_out(p);
        rat.extend(std::iter::repeat_n(p, e as usize));
    }
    let l = v.large_prime(cfg.rat_lp)?;
    if l > 1 {
        rat.push(l);
    }
    // Algebraic side.
    let an = cfg.f.eval_hom(a, b as i64);
    if an.is_zero() {
        return None;
    }
    let mut w = Norm::new(an.magnitude());
    let mut alg = Vec::new();
    for &k in alg_hits {
        let e = fb.alg[k as usize];
        let n = w.divide_out(e.p as u64);
        alg.extend(std::iter::repeat_n((e.p as u64, e.r as u64), n as usize));
    }
    for &p in &fb.alg_projective {
        if b.is_multiple_of(p) {
            let n = w.divide_out(p);
            alg.extend(std::iter::repeat_n((p, p), n as usize));
        }
    }
    let l = w.large_prime(cfg.alg_lp)?;
    if l > 1 {
        if b.is_multiple_of(l) {
            return None;
        }
        let r = mul_mod(a.rem_euclid(l as i64) as u64, inv_mod(b % l, l)?, l);
        alg.push((l, r));
    }
    Some(Relation {
        a,
        b,
        rat_negative,
        rat,
        alg,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn swar_byte_threshold_has_no_false_negatives() {
        for t in [0u8, 1, 17, 64, 127, 128, 129, 200, 255] {
            for x in [
                0u64,
                0x7f,
                0x80,
                0xff,
                0x0102_0304_0506_0708,
                0x40ff_0000_0000_0000,
                u64::MAX,
            ] {
                let exact = x.to_le_bytes().iter().any(|&b| b >= t);
                if exact {
                    assert!(any_byte_ge(x, t), "x = {x:#x}, t = {t}");
                }
            }
        }
    }

    #[test]
    fn relations_are_exact_factorisations() {
        // f = x³ + 2, m = 1000 (n = f(m) = 10⁹ + 2).
        let f = IntPoly::from_i64(&[2, 0, 0, 1]);
        let m = BigUint::from(1000u32);
        let fb = FactorBases::build(&f, &m, 2000, 2000);
        let cfg = SieveConfig {
            f: &f,
            m: BigInt::from(1000),
            m_f64: 1000.0,
            fb: &fb,
            rat_lp: 100_000,
            alg_lp: 100_000,
            slack_bits: 3.0,
            min_sieve_prime: 30,
        };
        let mut total = 0;
        for b in 1..=20u64 {
            let out = sieve_segment(&cfg, b, -5000, 5000);
            for r in &out.relations {
                let rn: BigInt = BigInt::from(r.a) - BigInt::from(r.b) * 1000;
                let prod: BigUint = r.rat.iter().map(|&p| BigUint::from(p)).product();
                assert_eq!(&prod, rn.magnitude());
                assert_eq!(r.rat_negative, rn.sign() == Sign::Minus);
                let an = f.eval_hom(r.a, r.b as i64);
                let prod: BigUint = r.alg.iter().map(|&(p, _)| BigUint::from(p)).product();
                assert_eq!(&prod, an.magnitude());
                for &(p, root) in &r.alg {
                    if root != p {
                        assert_eq!(
                            (r.a as i128 - r.b as i128 * root as i128).rem_euclid(p as i128),
                            0
                        );
                    }
                }
                assert_eq!(gcd_i64(r.a, r.b as i64), 1);
            }
            total += out.relations.len();
        }
        assert!(total > 100, "only {total} relations");
    }
}
