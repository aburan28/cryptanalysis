//! Area `fp_gb`: Gröbner bases over prime fields and extension fields:
//! degree-bounded F4 over `F_p` (`f4_fp`), F4 over the tower quotient
//! ring (`f4_fp_tower`), Gaudry's Macaulay solve of the symmetrised `S₄`
//! over `F_{p³}` (`gaudry_cubic`), and the textbook Buchberger
//! (`groebner_f4`).
//!
//! The PKM tower systems are built here the way
//! `examples/pkm_tower_pilot.rs` builds them (Kummer towers, `S₃` or its
//! chain, planted or random targets), from fixed seeds; the quartic
//! Macaulay kernels build the planted generic systems of
//! `examples/gaudry_quartic_c4.rs` (`gaudry_quartic::solve_system4`); the standard
//! benchmarks (Katsura, cyclic, dense random) are written out directly.
//! Every kernel fingerprints the whole basis it gets back plus every
//! deterministic counter of the report; wall-clock fields are left out.
//!
//! These are the crypto crate's `fp_gb` kernels, same IDs and inputs,
//! less the four signature-F4 cells: this crate has no `sig_fp_tower`.
//! Its tower step trace carries no `basis_kept` / `basis_entries`, so a
//! step fingerprints the counters it has.
//!
//! The tower and dense engines run parts of a step on the rayon pool;
//! their outputs, counters included, do not depend on the pool size
//! (checked at 1 and 4 threads when the kernels were added).

use std::collections::{BTreeMap, HashMap};

use crate::harness::{Closure, Fp, Kernel, Tier, Workload};
use cryptanalysis_suite::cryptanalysis::f4_fp::{
    self, F4Options, F4Report, Ordering, Poly, Verdict,
};
use cryptanalysis_suite::cryptanalysis::f4_fp_tower::{
    self, RPoly, SquareRule, StepTrace, TowerF4Options, TowerF4Report, TowerRing,
};
use cryptanalysis_suite::cryptanalysis::gaudry_cubic::{
    generate_instance3, solve_s4_subspace_with, SolveMode, SolveStats, SymmetrisedS4, E3,
};
use cryptanalysis_suite::cryptanalysis::gaudry_quartic::{solve_system4, QuarticSolve};
use cryptanalysis_suite::cryptanalysis::groebner_f4::{self, buchberger, reduce_basis};
use cryptanalysis_suite::cryptanalysis::ic_boundary::{
    CountedGroup, GroupOps, PrimeCurve, PrimePoint,
};
use cryptanalysis_suite::cryptanalysis::symmetrized_semaev::MPoly;
use cryptanalysis_suite::ecc::field::FieldElement;
use num_bigint::BigUint;
use rand::{rngs::StdRng, Rng, SeedableRng};

// ── F_p helpers (setup only) ──────────────────────────────────────────

fn mulm(a: u64, b: u64, p: u64) -> u64 {
    ((a as u128 * b as u128) % p as u128) as u64
}

fn powm(mut a: u64, mut e: u64, p: u64) -> u64 {
    let mut r = 1u64;
    a %= p;
    while e > 0 {
        if e & 1 == 1 {
            r = mulm(r, a, p);
        }
        a = mulm(a, a, p);
        e >>= 1;
    }
    r
}

/// A polynomial over `F_p` for building systems: exponent vector →
/// non-zero coefficient.
#[derive(Clone, Debug)]
struct Pol {
    n: usize,
    terms: BTreeMap<Vec<u32>, u64>,
}

impl Pol {
    fn zero(n: usize) -> Self {
        Pol {
            n,
            terms: BTreeMap::new(),
        }
    }
    fn constant(n: usize, c: u64, p: u64) -> Self {
        let mut f = Pol::zero(n);
        let c = c % p;
        if c != 0 {
            f.terms.insert(vec![0; n], c);
        }
        f
    }
    fn var(n: usize, i: usize) -> Self {
        let mut e = vec![0; n];
        e[i] = 1;
        let mut f = Pol::zero(n);
        f.terms.insert(e, 1);
        f
    }
    fn add(&self, o: &Pol, p: u64) -> Pol {
        let mut f = self.clone();
        for (e, c) in &o.terms {
            let v = f.terms.entry(e.clone()).or_insert(0);
            *v = (*v + c) % p;
        }
        f.terms.retain(|_, c| *c != 0);
        f
    }
    fn scale(&self, k: u64, p: u64) -> Pol {
        let mut f = Pol::zero(self.n);
        for (e, c) in &self.terms {
            let v = mulm(*c, k, p);
            if v != 0 {
                f.terms.insert(e.clone(), v);
            }
        }
        f
    }
    fn sub(&self, o: &Pol, p: u64) -> Pol {
        self.add(&o.scale(p - 1, p), p)
    }
    fn mul(&self, o: &Pol, p: u64) -> Pol {
        let mut f = Pol::zero(self.n);
        for (e1, c1) in &self.terms {
            for (e2, c2) in &o.terms {
                let e: Vec<u32> = e1.iter().zip(e2).map(|(a, b)| a + b).collect();
                let v = f.terms.entry(e).or_insert(0);
                *v = (*v + mulm(*c1, *c2, p)) % p;
            }
        }
        f.terms.retain(|_, c| *c != 0);
        f
    }
    fn eval(&self, x: &[u64], p: u64) -> u64 {
        let mut acc = 0u64;
        for (e, c) in &self.terms {
            let mut t = *c;
            for (i, k) in e.iter().enumerate() {
                if *k > 0 {
                    t = mulm(t, powm(x[i], *k as u64, p), p);
                }
            }
            acc = (acc + t) % p;
        }
        acc
    }
    fn raw(&self) -> Vec<(Vec<u32>, u64)> {
        self.terms.iter().map(|(e, c)| (e.clone(), *c)).collect()
    }
    fn to_poly(&self, p: u64) -> Poly {
        f4_fp::normalise(&self.raw(), p, Ordering::Grevlex)
    }
}

// ── Standard benchmark systems ────────────────────────────────────────

/// Katsura-`n` over `F_p`: `n + 1` unknowns `x_0 … x_n`, one linear and `n`
/// quadratic equations.
fn katsura(n: usize, p: u64) -> Vec<Pol> {
    let nv = n + 1;
    let x = |i: i64| -> Pol {
        let i = i.unsigned_abs() as usize;
        if i <= n {
            Pol::var(nv, i)
        } else {
            Pol::zero(nv)
        }
    };
    let mut eqs = Vec::new();
    let mut lin = Pol::constant(nv, p - 1, p);
    lin = lin.add(&Pol::var(nv, 0), p);
    for i in 1..=n {
        lin = lin.add(&Pol::var(nv, i).scale(2, p), p);
    }
    eqs.push(lin);
    for m in 0..n as i64 {
        let mut f = Pol::zero(nv);
        for l in -(n as i64)..=n as i64 {
            f = f.add(&x(l).mul(&x(m - l), p), p);
        }
        eqs.push(f.sub(&x(m), p));
    }
    eqs
}

/// Cyclic-`n` over `F_p`: `Σ_i Π_{j<k} x_{i+j}` for `k < n`, and
/// `Π x_i − 1`.
fn cyclic(n: usize, p: u64) -> Vec<Pol> {
    let mut eqs = Vec::new();
    for k in 1..n {
        let mut f = Pol::zero(n);
        for i in 0..n {
            let mut t = Pol::constant(n, 1, p);
            for j in 0..k {
                t = t.mul(&Pol::var(n, (i + j) % n), p);
            }
            f = f.add(&t, p);
        }
        eqs.push(f);
    }
    let mut t = Pol::constant(n, 1, p);
    for i in 0..n {
        t = t.mul(&Pol::var(n, i), p);
    }
    eqs.push(t.sub(&Pol::constant(n, 1, p), p));
    eqs
}

/// Every monomial of total degree at most `d` in `n` unknowns.
fn monomials(n: usize, d: u32) -> Vec<Vec<u32>> {
    fn rec(n: usize, d: u32, cur: &mut Vec<u32>, out: &mut Vec<Vec<u32>>) {
        if cur.len() == n {
            out.push(cur.clone());
            return;
        }
        let used: u32 = cur.iter().sum();
        for k in 0..=d - used {
            cur.push(k);
            rec(n, d, cur, out);
            cur.pop();
        }
    }
    let mut out = Vec::new();
    rec(n, d, &mut Vec::new(), &mut out);
    out
}

/// `m` dense random polynomials of degree `d` in `n` unknowns, the
/// generator of `examples/f4_fp_bench.rs` (xorshift, same seed rule), so
/// these kernels time the cases that benchmark prints.
fn dense_system(n: usize, m: usize, d: u32, p: u64) -> Vec<Poly> {
    let mut s = (0x9e37_79b9_7f4a_7c15 ^ (n as u64 * 131 + d as u64)) | 1;
    let mut rnd = move || {
        s ^= s << 13;
        s ^= s >> 7;
        s ^= s << 17;
        s
    };
    let monos = monomials(n, d);
    (0..m)
        .map(|_| monos.iter().map(|e| (e.clone(), rnd() % p)).collect())
        .collect()
}

// ── PKM Kummer-tower systems (as `examples/pkm_tower_pilot.rs`) ───────

/// `786 433 = 3·2^18 + 1`, the pilot's prime: `2^t | p − 1` for `t ≤ 18`.
const PKM_P: u64 = 786_433;

/// Semaev's third summation polynomial on three polynomial arguments.
fn s3(x1: &Pol, x2: &Pol, x3: &Pol, a: u64, b: u64, p: u64) -> Pol {
    let n = x1.n;
    let d = x1.sub(x2, p);
    let t1 = d.mul(&d, p).mul(x3, p).mul(x3, p);
    let s = x1.add(x2, p);
    let pr = x1.mul(x2, p);
    let inner = s
        .mul(&pr.add(&Pol::constant(n, a, p), p), p)
        .add(&Pol::constant(n, mulm(2, b, p), p), p);
    let t2 = inner.mul(x3, p).scale(p - 2, p);
    let q = pr.sub(&Pol::constant(n, a, p), p);
    let t3 = q.mul(&q, p).sub(&s.scale(mulm(4, b, p), p), p);
    t1.add(&t2, p).add(&t3, p)
}

/// A Kummer tower `x = g·y_0`, `y_{j+1} = y_j²`, `y_{t−1}² = 1`: the factor
/// base abscissae `V = g·μ_{2^t}`.
struct Kummer {
    t: usize,
    g: u64,
    v: Vec<u64>,
}

impl Kummer {
    fn new(p: u64, t: usize, rng: &mut StdRng) -> Self {
        let zeta = loop {
            let h = rng.gen_range(2..p);
            if powm(h, (p - 1) / 2, p) == p - 1 {
                break powm(h, (p - 1) >> t, p);
            }
        };
        let g = rng.gen_range(2..p);
        let v = (0..1u64 << t)
            .map(|k| mulm(g, powm(zeta, k, p), p))
            .collect();
        Kummer { t, g, v }
    }

    /// `y_0 … y_{t−1}` of an abscissa of `V`.
    fn values(&self, x: u64, p: u64) -> Vec<u64> {
        let mut y = vec![0u64; self.t];
        y[0] = mulm(x, powm(self.g, p - 2, p), p);
        for j in 0..self.t - 1 {
            y[j + 1] = mulm(y[j], y[j], p);
        }
        y
    }

    /// The raw tower equations of one block whose variables start at `base`.
    fn equations(&self, n: usize, base: usize, p: u64) -> Vec<Pol> {
        (0..self.t)
            .map(|j| {
                let yj = Pol::var(n, base + j);
                let next = if j + 1 < self.t {
                    Pol::var(n, base + j + 1)
                } else {
                    Pol::constant(n, 1, p)
                };
                next.sub(&yj.mul(&yj, p), p)
            })
            .collect()
    }

    /// The same, as `f4_fp_tower` square rules.
    fn square_rules(&self, base: usize) -> Vec<SquareRule> {
        (0..self.t)
            .map(|j| {
                let top = j + 1 == self.t;
                SquareRule {
                    next: (!top).then_some((base + j + 1) as u8),
                    a: 0,
                    b: u64::from(!top),
                    c: 0,
                    d: u64::from(top),
                }
            })
            .collect()
    }
}

/// One PKM decomposition system: `S₃` (or its chain at `m ≥ 3`) and the
/// raw tower equations, `m·t + (m − 2)` unknowns.
struct PkmSystem {
    n: usize,
    /// Summation equations first, then the tower equations.
    eqs: Vec<Pol>,
    /// Index of the first tower equation.
    towers_from: usize,
    ring: TowerRing,
    /// The planted solution, when the target was planted.
    solution: Option<Vec<u64>>,
}

impl PkmSystem {
    /// Kummer tower of height `t`, `m` summands, curve and target from
    /// `seed`; `planted` puts a decomposition in, otherwise the target is
    /// a random point (almost always refuted).
    fn build(m: usize, t: usize, planted: bool, seed: u64) -> Self {
        let p = PKM_P;
        let mut rng = StdRng::seed_from_u64(seed);
        let tower = Kummer::new(p, t, &mut rng);
        let (curve, on) = loop {
            let a = rng.gen_range(0..p);
            let b = rng.gen_range(1..p);
            let disc = (mulm(4, powm(a, 3, p), p) + mulm(27, mulm(b, b, p), p)) % p;
            if disc == 0 {
                continue;
            }
            let curve = PrimeCurve { p, a, b };
            let on: Vec<u64> = tower
                .v
                .iter()
                .copied()
                .filter(|&x| curve.legendre(curve.rhs(x)) == 1)
                .collect();
            if on.len() >= m.max(2) {
                break (curve, on);
            }
        };
        let n = m * t + (m - 2);
        let (x_r, solution) = if planted {
            loop {
                let mut pick: Vec<u64> = Vec::with_capacity(m);
                while pick.len() < m {
                    let x = on[rng.gen_range(0..on.len())];
                    if !pick.contains(&x) {
                        pick.push(x);
                    }
                }
                let pts: Vec<PrimePoint> = pick
                    .iter()
                    .map(|&x| {
                        let y = curve.sqrt(curve.rhs(x)).expect("on the curve");
                        PrimePoint::affine(x, if rng.gen::<bool>() { y } else { p - y })
                    })
                    .collect();
                let mut ops = GroupOps::default();
                let mut acc = pts[0];
                let mut partial = Vec::new();
                let mut hit_identity = false;
                for pt in &pts[1..] {
                    acc = curve.add(&mut ops, acc, *pt);
                    if acc.infinity {
                        hit_identity = true;
                        break;
                    }
                    partial.push(acc.x);
                }
                if hit_identity {
                    continue;
                }
                let mut sol = vec![0u64; n];
                for (i, &x) in pick.iter().enumerate() {
                    sol[i * t..(i + 1) * t].copy_from_slice(&tower.values(x, p));
                }
                for k in 0..m - 2 {
                    sol[m * t + k] = partial[k];
                }
                break (acc.x, Some(sol));
            }
        } else {
            let x_r = loop {
                let x = rng.gen_range(0..p);
                let r = curve.rhs(x);
                if r != 0 && curve.legendre(r) == 1 {
                    break x;
                }
            };
            (x_r, None)
        };
        let (a, b) = (curve.a, curve.b);
        let x = |i: usize| Pol::var(n, i * t).scale(tower.g, p);
        let xr = Pol::constant(n, x_r, p);
        let mut eqs = if m == 2 {
            vec![s3(&x(0), &x(1), &xr, a, b, p)]
        } else {
            let u = |k: usize| Pol::var(n, m * t + k);
            let mut eqs = vec![s3(&x(0), &x(1), &u(0), a, b, p)];
            for k in 1..m - 2 {
                eqs.push(s3(&u(k - 1), &x(k + 1), &u(k), a, b, p));
            }
            eqs.push(s3(&u(m - 3), &x(m - 1), &xr, a, b, p));
            eqs
        };
        let towers_from = eqs.len();
        for i in 0..m {
            eqs.extend(tower.equations(n, i * t, p));
        }
        if let Some(sol) = &solution {
            for e in &eqs {
                assert_eq!(e.eval(sol, p), 0, "the planted solution must vanish");
            }
        }
        let mut rules = Vec::with_capacity(m * t);
        for i in 0..m {
            rules.extend(tower.square_rules(i * t));
        }
        let ring = TowerRing {
            p,
            rules,
            n_free: m - 2,
        };
        for e in &eqs[towers_from..] {
            assert!(ring.from_raw(&e.raw()).is_empty(), "tower rule mismatch");
        }
        PkmSystem {
            n,
            eqs,
            towers_from,
            ring,
            solution,
        }
    }

    /// The raw presentation for `f4_fp`: every equation, monic.
    fn raw_input(&self) -> Vec<Poly> {
        self.eqs
            .iter()
            .map(|e| e.to_poly(PKM_P))
            .filter(|f| !f.is_empty())
            .collect()
    }

    /// The reduced presentation for the tower engines: the summation
    /// equations in normal form.
    fn ring_input(&self) -> Vec<RPoly> {
        self.eqs[..self.towers_from]
            .iter()
            .map(|e| self.ring.from_raw(&e.raw()))
            .filter(|f| !f.is_empty())
            .collect()
    }

    /// The pilot's default degree cap: `n + d_max + 6`.
    fn max_degree(&self) -> u32 {
        self.n as u32 + 4 + 6
    }
}

// ── Fingerprints ──────────────────────────────────────────────────────

fn fp_poly(mut fp: Fp, f: &Poly) -> Fp {
    fp = fp.usize(f.len());
    for (e, c) in f {
        fp = fp.usize(e.len());
        for &x in e {
            fp = fp.u64(u64::from(x));
        }
        fp = fp.u64(*c);
    }
    fp
}

fn fp_f4_report(r: &F4Report) -> u64 {
    let mut fp = Fp::new().usize(r.basis.len());
    for f in &r.basis {
        fp = fp_poly(fp, f);
    }
    fp.bool(r.inconsistent)
        .u64(u64::from(r.degree_reached))
        .u64(u64::from(r.solving_degree))
        .u64(u64::from(r.solving_degree_max))
        .usize(r.max_cols_to_solution)
        .usize(r.steps_to_solution)
        .usize(r.steps)
        .usize(r.max_rows)
        .usize(r.max_cols)
        .bool(r.timed_out)
        .usize(r.pairs_above_bound)
        .u64(r.staircase_at_stop.map_or(u64::MAX, |s| s as u64))
        .finish()
}

fn fp_rpoly(mut fp: Fp, f: &RPoly) -> Fp {
    fp = fp.usize(f.monos.len());
    for (&m, &c) in f.monos.iter().zip(&f.coefs) {
        fp = fp.u128(m).u64(u64::from(c));
    }
    fp
}

fn fp_step(fp: Fp, s: &StepTrace) -> Fp {
    fp.u64(u64::from(s.degree))
        .usize(s.critical_pairs)
        .usize(s.tower_pairs)
        .usize(s.s_rows)
        .usize(s.reducer_rows)
        .usize(s.promoted_rows)
        .usize(s.cols)
        .u64(s.nnz)
        .usize(s.residual_rows)
        .usize(s.residual_cols)
        .u64(s.dense_entries)
        .usize(s.fresh)
        .u64(u64::from(s.fresh_min_degree))
        .u64(s.muladds)
        .usize(s.basis_active)
        .usize(s.pairs_left)
}

fn fp_tower_report(mut fp: Fp, r: &TowerF4Report) -> Fp {
    fp = fp.usize(r.basis.len());
    for f in &r.basis {
        fp = fp_rpoly(fp, f);
    }
    fp = fp
        .bool(r.inconsistent)
        .u64(u64::from(r.degree_reached))
        .u64(u64::from(r.solving_degree_max))
        .u64(u64::from(r.last_productive_degree))
        .usize(r.max_cols_to_solution)
        .usize(r.steps_to_solution)
        .usize(r.steps)
        .usize(r.max_rows)
        .usize(r.max_cols)
        .u64(r.max_nnz)
        .usize(r.max_residual_rows)
        .u64(r.max_dense_entries)
        .u64(r.muladds)
        .u64(r.critical_pairs_reduced)
        .u64(r.tower_pairs_reduced)
        .u64(r.pairs_product_skipped)
        .u64(r.pairs_chain_skipped)
        .u64(r.reducer_rows)
        .usize(r.pairs_above_bound)
        .u64(r.staircase_at_stop.map_or(u64::MAX, |s| s as u64))
        .bool(r.timed_out)
        .bool(r.oversize)
        .usize(r.trace.len());
    for s in &r.trace {
        fp = fp_step(fp, s);
    }
    fp
}

// ── Kernels: degree-bounded F4 over F_p ───────────────────────────────

fn f4_kernel(input: Vec<Poly>, n: usize, p: u64, max_degree: u32) -> Box<dyn Workload> {
    let opts = F4Options::new(Ordering::Grevlex, max_degree);
    f4_kernel_with(input, n, p, opts)
}

fn f4_kernel_with(input: Vec<Poly>, n: usize, p: u64, opts: F4Options) -> Box<dyn Workload> {
    Box::new(Closure(move || {
        let r = f4_fp::f4(&input, n, p, &opts);
        assert!(!r.timed_out);
        fp_f4_report(&r)
    }))
}

fn f4_katsura6() -> Box<dyn Workload> {
    let p = 65_521;
    let input: Vec<Poly> = katsura(6, p).iter().map(|f| f.to_poly(p)).collect();
    f4_kernel(input, 7, p, 20)
}

fn f4_katsura7() -> Box<dyn Workload> {
    let p = 65_521;
    let input: Vec<Poly> = katsura(7, p).iter().map(|f| f.to_poly(p)).collect();
    f4_kernel(input, 8, p, 20)
}

fn f4_cyclic5() -> Box<dyn Workload> {
    let p = 65_521;
    let input: Vec<Poly> = cyclic(5, p).iter().map(|f| f.to_poly(p)).collect();
    f4_kernel(input, 5, p, 20)
}

fn f4_cyclic6() -> Box<dyn Workload> {
    let p = 65_521;
    let input: Vec<Poly> = cyclic(6, p).iter().map(|f| f.to_poly(p)).collect();
    f4_kernel(input, 6, p, 20)
}

fn f4_quad_n7() -> Box<dyn Workload> {
    let p = 65_521;
    f4_kernel(dense_system(7, 7, 2, p), 7, p, 12)
}

fn f4_quad_n8() -> Box<dyn Workload> {
    let p = 65_521;
    f4_kernel(dense_system(8, 8, 2, p), 8, p, 12)
}

fn f4_cubic_n4_p31() -> Box<dyn Workload> {
    f4_kernel(dense_system(4, 4, 3, 31), 4, 31, 14)
}

/// `f4_fp::f4` on a planted PKM system, raw presentation. Setup runs it
/// once and checks that the basis vanishes at the planted solution.
fn f4_pkm(m: usize, t: usize, seed: u64) -> Box<dyn Workload> {
    let sys = PkmSystem::build(m, t, true, seed);
    let (n, input) = (sys.n, sys.raw_input());
    let opts = F4Options::new(Ordering::Grevlex, sys.max_degree());
    let r = f4_fp::f4(&input, n, PKM_P, &opts);
    let sol = sys.solution.as_ref().expect("planted");
    assert!(!r.inconsistent && r.basis.iter().all(|f| f4_fp::eval(f, sol, PKM_P) == 0));
    f4_kernel_with(input, n, PKM_P, opts)
}

fn f4_pkm_m2_t5() -> Box<dyn Workload> {
    f4_pkm(2, 5, 0x504B_4D01)
}

fn f4_pkm_m3_t2() -> Box<dyn Workload> {
    f4_pkm(3, 2, 0x504B_4D02)
}

fn f4_pkm_m2_t6() -> Box<dyn Workload> {
    f4_pkm(2, 6, 0x504B_4D03)
}

/// `f4_fp::solve` (F4, univariate roots, substitution, recursion) on a
/// dense cubic system in three unknowns over `F_29`.
fn f4_solve_kernel(n: usize, d: u32, p: u64, max_degree: u32) -> Box<dyn Workload> {
    let input = dense_system(n, n, d, p);
    let opts = F4Options::new(Ordering::Grevlex, max_degree);
    Box::new(Closure(move || {
        let r = f4_fp::solve(&input, n, p, &opts);
        assert!(!r.timed_out);
        let mut fp = Fp::new()
            .u64(u64::from(r.solving_degree))
            .u64(u64::from(r.degree_reached))
            .usize(r.max_rows)
            .usize(r.max_cols)
            .usize(r.f4_runs);
        match &r.verdict {
            Verdict::Inconsistent => fp = fp.u64(1),
            Verdict::Undetermined => fp = fp.u64(2),
            Verdict::Solutions(sols) => {
                fp = fp.u64(3).usize(sols.len());
                for s in sols {
                    fp = fp.words(s);
                }
            }
        }
        fp.finish()
    }))
}

fn f4_solve_cubic_n3_p29() -> Box<dyn Workload> {
    f4_solve_kernel(3, 3, 29, 12)
}

fn f4_solve_quart_n3_p31() -> Box<dyn Workload> {
    f4_solve_kernel(3, 4, 31, 16)
}

fn f4_solve_quad_n4_p31() -> Box<dyn Workload> {
    f4_solve_kernel(4, 2, 31, 12)
}

/// `f4_fp::autoreduce` then `f4_fp::interreduce` of a PKM system's raw
/// equations times every monomial of degree at most two:
/// the heap-based sparse reduction `coordinate_descent::f4_time` runs on
/// every descended system before F4.
fn f4_autoreduce_pkm() -> Box<dyn Workload> {
    let sys = PkmSystem::build(2, 4, true, 0x504B_4D04);
    let p = PKM_P;
    let mut gens: Vec<Poly> = Vec::new();
    for e in &sys.eqs {
        for mono in monomials(sys.n, 2) {
            let mut t = Pol::zero(sys.n);
            t.terms.insert(mono, 1);
            gens.push(e.mul(&t, p).to_poly(p));
        }
    }
    Box::new(Closure(move || {
        let a = f4_fp::autoreduce(&gens, p, Ordering::Grevlex);
        let b = f4_fp::interreduce(&a, p, Ordering::Grevlex);
        let mut fp = Fp::new().usize(a.len());
        for f in &a {
            fp = fp_poly(fp, f);
        }
        fp = fp.usize(b.len());
        for f in &b {
            fp = fp_poly(fp, f);
        }
        fp.finish()
    }))
}

// ── Kernels: tower F4 ─────────────────────────────────────────────────

fn tower_kernel(m: usize, t: usize, planted: bool, seed: u64) -> Box<dyn Workload> {
    let sys = PkmSystem::build(m, t, planted, seed);
    let input = sys.ring_input();
    let ring = sys.ring.clone();
    let opts = TowerF4Options::new(sys.max_degree());
    if let Some(sol) = &sys.solution {
        // Setup runs the planted system once: its basis must vanish there.
        let r = f4_fp_tower::f4_tower(&input, &ring, &opts);
        assert!(!r.inconsistent && r.basis.iter().all(|f| ring.eval(f, sol) == 0));
    }
    Box::new(Closure(move || {
        let r = f4_fp_tower::f4_tower(&input, &ring, &opts);
        assert!(!r.timed_out && !r.oversize);
        fp_tower_report(Fp::new(), &r).finish()
    }))
}

fn tower_m2_n12() -> Box<dyn Workload> {
    tower_kernel(2, 6, false, 0x544F_5701)
}

fn tower_m2_n12_planted() -> Box<dyn Workload> {
    tower_kernel(2, 6, true, 0x544F_5702)
}

fn tower_m3_n9() -> Box<dyn Workload> {
    tower_kernel(3, 3, false, 0x544F_5703)
}

fn tower_m4_n8() -> Box<dyn Workload> {
    tower_kernel(4, 2, false, 0x544F_5704)
}

fn tower_m2_n16() -> Box<dyn Workload> {
    tower_kernel(2, 8, false, 0x544F_5705)
}

// ── Kernel: Gaudry's Macaulay solve of the symmetrised S₄ over F_{p³} ──

/// `gaudry_cubic::solve_s4_subspace_with` (full elimination) on a fixed
/// stream of residual abscissae: Weil restriction, the degree-10 Macaulay
/// matrix over `F_p`, normal forms, the multiplication matrix of `e₁`, its
/// eigenvalues and eigenvectors, and the cubic splits.
fn gaudry_s4(p: u64, residuals: usize) -> Box<dyn Workload> {
    let inst = generate_instance3(p, 1);
    let pre = SymmetrisedS4::precompute(&inst.curve);
    let mut rng = StdRng::seed_from_u64(0x4741_5544);
    let xs: Vec<E3> = (0..residuals)
        .map(|_| {
            let k = rng.gen_range(1..inst.curve.n);
            inst.curve.mul(&inst.curve.g, k).x
        })
        .collect();
    let mode = SolveMode::default();
    Box::new(Closure(move || {
        let mut rng = StdRng::seed_from_u64(0x524F_4F54);
        let mut stats = SolveStats::default();
        let mut fp = Fp::new();
        for x in &xs {
            match solve_s4_subspace_with(&inst, &pre, x, &mut rng, &mut stats, mode) {
                None => fp = fp.u64(u64::MAX),
                Some(triples) => {
                    fp = fp.usize(triples.len());
                    for t in triples {
                        fp = fp.words(&t);
                    }
                }
            }
        }
        fp.u64(stats.solves)
            .u64(stats.e_solutions)
            .u64(stats.split_cubics)
            .u64(stats.unsolved)
            .u64(stats.macaulay_rows)
            .u64(stats.retried_at_degree_11)
            .u64(stats.border_unreachable)
            .u64(stats.quotient_dim_total)
            .finish()
    }))
}

fn gaudry_s4_p1039() -> Box<dyn Workload> {
    gaudry_s4(1039, 8)
}

// ── Kernel: the quartic Macaulay solve over F_p (`gaudry_quartic`) ─────

/// `gaudry_quartic::solve_system4` on the system `examples/gaudry_quartic_c4.rs
/// --generic` builds: four dense equations of degree `d` in four unknowns
/// over `F_269` with a planted root, Macaulay degree `4(d − 1) + 1`, then
/// the multiplication matrix, its eigenvectors and the verification.
fn gaudry_quartic_generic(d: u8, seed: u64) -> Box<dyn Workload> {
    let p = 269u64;
    let mut rng = StdRng::seed_from_u64(seed);
    let root: [u64; 4] = std::array::from_fn(|_| rng.gen_range(0..p));
    let mut monos: Vec<[u8; 4]> = Vec::new();
    for a in 0..=d {
        for b in 0..=(d - a) {
            for c in 0..=(d - a - b) {
                for e in 0..=(d - a - b - c) {
                    monos.push([a, b, c, e]);
                }
            }
        }
    }
    let eval = |c: &HashMap<[u8; 4], u64>| -> u64 {
        c.iter().fold(0u64, |acc, (m, &k)| {
            let mut t = k;
            for i in 0..4 {
                for _ in 0..m[i] {
                    t = t * root[i] % p;
                }
            }
            (acc + t) % p
        })
    };
    let comps: Vec<HashMap<[u8; 4], u64>> = (0..4)
        .map(|_| {
            let mut c: HashMap<[u8; 4], u64> =
                monos.iter().map(|m| (*m, rng.gen_range(0..p))).collect();
            let v = eval(&c);
            let e = c.entry([0, 0, 0, 0]).or_insert(0);
            *e = (*e + p - v) % p;
            c
        })
        .collect();
    let solve_rng = rng;
    Box::new(Closure(move || {
        let mut rng = solve_rng.clone();
        let mut st = QuarticSolve::default();
        let sols = solve_system4(&comps, d, 4 * (d - 1) + 1, p, &mut rng, &mut st, false);
        let sols = sols.expect("the generic system closes at the regularity bound");
        assert!(sols.contains(&root), "the planted root must be found");
        let mut fp = Fp::new().usize(sols.len());
        for s in &sols {
            fp = fp.words(s);
        }
        fp.u64(u64::from(st.equation_degree))
            .u64(u64::from(st.macaulay_degree))
            .usize(st.rows)
            .usize(st.cols)
            .usize(st.pivots)
            .usize(st.zero_rows)
            .usize(st.dim)
            .usize(st.reached_pivots)
            .u64(st.weil_muls)
            .u64(st.triangularise_muls)
            .u64(st.echelon_muls)
            .u64(st.nf_muls)
            .u64(st.charpoly_muls)
            .u64(st.roots_muls)
            .u64(st.eigenvector_muls)
            .u64(st.verify_muls)
            .u64(st.split_muls)
            .u64(st.total_muls)
            .usize(st.rational_eigenvalues)
            .usize(st.degenerate_eigenspaces)
            .usize(st.e_solutions)
            .str(&st.outcome)
            .finish()
    }))
}

fn gaudry_quartic_generic_d3() -> Box<dyn Workload> {
    gaudry_quartic_generic(3, 0x4751_3403)
}

fn gaudry_quartic_generic_d4() -> Box<dyn Workload> {
    gaudry_quartic_generic(4, 0x4751_3404)
}

// ── Kernel: textbook Buchberger over BigUint (`groebner_f4`) ──────────

fn to_mpoly(f: &Pol, p: u64) -> MPoly {
    let pb = BigUint::from(p);
    let mut out = MPoly::zero(f.n, pb.clone());
    for (e, c) in &f.terms {
        out.terms.insert(
            e.clone(),
            FieldElement {
                value: BigUint::from(*c),
                modulus: pb.clone(),
            },
        );
    }
    out
}

/// `buchberger` then `reduce_basis` on Katsura-3 over `F_32003`, as
/// `coordinate_descent::groebner_time` runs them.
fn buchberger_katsura3() -> Box<dyn Workload> {
    let p = 32_003;
    let input: Vec<MPoly> = katsura(3, p).iter().map(|f| to_mpoly(f, p)).collect();
    Box::new(Closure(move || {
        let gb = buchberger(&input, groebner_f4::Ordering::Grevlex);
        let red = reduce_basis(&gb, groebner_f4::Ordering::Grevlex);
        let mut fp = Fp::new().usize(gb.len()).usize(red.len());
        for g in &red {
            fp = fp.usize(g.terms.len());
            for (e, c) in &g.terms {
                for &x in e {
                    fp = fp.u64(u64::from(x));
                }
                fp = fp.words(&c.value.to_u64_digits());
            }
        }
        fp.finish()
    }))
}

// ── Registry ──────────────────────────────────────────────────────────

pub fn register(kernels: &mut Vec<Kernel>) {
    let mut k =
        |id: &'static str, tier: Tier, desc: &'static str, setup: fn() -> Box<dyn Workload>| {
            kernels.push(Kernel {
                id,
                area: "fp_gb",
                desc,
                tier,
                setup,
            })
        };
    k(
        "fp_gb/f4_katsura6_p65521",
        Tier::Quick,
        "f4_fp::f4 (grevlex, D <= 20) on Katsura-6 over F_65521",
        f4_katsura6,
    );
    k(
        "fp_gb/f4_katsura7_p65521",
        Tier::Full,
        "f4_fp::f4 (grevlex, D <= 20) on Katsura-7 over F_65521",
        f4_katsura7,
    );
    k(
        "fp_gb/f4_cyclic5_p65521",
        Tier::Quick,
        "f4_fp::f4 (grevlex, D <= 20) on cyclic-5 over F_65521",
        f4_cyclic5,
    );
    k(
        "fp_gb/f4_cyclic6_p65521",
        Tier::Full,
        "f4_fp::f4 (grevlex, D <= 20) on cyclic-6 over F_65521",
        f4_cyclic6,
    );
    k(
        "fp_gb/f4_quad_n7_p65521",
        Tier::Quick,
        "f4_fp::f4 (D <= 12) on f4_fp_bench's dense random quadratic n=m=7 system over F_65521",
        f4_quad_n7,
    );
    k(
        "fp_gb/f4_quad_n8_p65521",
        Tier::Full,
        "f4_fp::f4 (D <= 12) on f4_fp_bench's dense random quadratic n=m=8 system over F_65521",
        f4_quad_n8,
    );
    k(
        "fp_gb/f4_cubic_n4_p31",
        Tier::Quick,
        "f4_fp::f4 (D <= 14) on f4_fp_bench's dense random cubic n=m=4 system over F_31",
        f4_cubic_n4_p31,
    );
    k(
        "fp_gb/f4_solve_cubic_n3_p29",
        Tier::Quick,
        "f4_fp::solve (F4 + univariate roots + substitution) on a dense cubic n=m=3 system over F_29",
        f4_solve_cubic_n3_p29,
    );
    k(
        "fp_gb/f4_solve_quart_n3_p31",
        Tier::Quick,
        "f4_fp::solve on f4_fp_bench's dense quartic n=m=3 system over F_31",
        f4_solve_quart_n3_p31,
    );
    k(
        "fp_gb/f4_solve_quad_n4_p31",
        Tier::Quick,
        "f4_fp::solve on f4_fp_bench's dense quadratic n=m=4 system over F_31",
        f4_solve_quad_n4_p31,
    );
    k(
        "fp_gb/f4_pkm_kummer_m2_t5",
        Tier::Quick,
        "f4_fp::f4 on a planted PKM Kummer-tower S3 system, m=2, t=5 (raw presentation, 10 unknowns)",
        f4_pkm_m2_t5,
    );
    k(
        "fp_gb/f4_pkm_kummer_m3_t2",
        Tier::Quick,
        "f4_fp::f4 on a planted PKM Kummer-tower S3-chain system, m=3, t=2 (7 unknowns)",
        f4_pkm_m3_t2,
    );
    k(
        "fp_gb/f4_pkm_kummer_m2_t6",
        Tier::Full,
        "f4_fp::f4 on a planted PKM Kummer-tower S3 system, m=2, t=6 (raw presentation, 12 unknowns)",
        f4_pkm_m2_t6,
    );
    k(
        "fp_gb/f4_autoreduce_pkm_m2_t4_x2",
        Tier::Quick,
        "f4_fp::autoreduce + interreduce of a PKM m=2 t=4 system times every monomial of degree <= 2",
        f4_autoreduce_pkm,
    );
    k(
        "fp_gb/tower_f4_kummer_m2_n12",
        Tier::Quick,
        "f4_fp_tower::f4_tower on a random-target PKM Kummer system, m=2, N=12",
        tower_m2_n12,
    );
    k(
        "fp_gb/tower_f4_kummer_m2_n12_planted",
        Tier::Quick,
        "f4_fp_tower::f4_tower on a planted PKM Kummer system, m=2, N=12",
        tower_m2_n12_planted,
    );
    k(
        "fp_gb/tower_f4_kummer_m3_n9",
        Tier::Quick,
        "f4_fp_tower::f4_tower on a random-target PKM Kummer S3-chain system, m=3, N=9",
        tower_m3_n9,
    );
    k(
        "fp_gb/tower_f4_kummer_m4_n8",
        Tier::Quick,
        "f4_fp_tower::f4_tower on a random-target PKM Kummer S3-chain system, m=4, N=8",
        tower_m4_n8,
    );
    k(
        "fp_gb/tower_f4_kummer_m2_n16",
        Tier::Full,
        "f4_fp_tower::f4_tower on a random-target PKM Kummer system, m=2, N=16",
        tower_m2_n16,
    );
    k(
        "fp_gb/gaudry_s4_macaulay_p1039",
        Tier::Quick,
        "gaudry_cubic::solve_s4_subspace_with (full elimination) on 8 fixed residuals, p=1039 (F_{p^3})",
        gaudry_s4_p1039,
    );
    k(
        "fp_gb/gaudry_quartic_generic_d3_p269",
        Tier::Quick,
        "gaudry_quartic::solve_system4 on a planted dense degree-3 system in 4 unknowns over F_269 (Macaulay degree 9)",
        gaudry_quartic_generic_d3,
    );
    k(
        "fp_gb/gaudry_quartic_generic_d4_p269",
        Tier::Full,
        "gaudry_quartic::solve_system4 on a planted dense degree-4 system in 4 unknowns over F_269 (Macaulay degree 13)",
        gaudry_quartic_generic_d4,
    );
    k(
        "fp_gb/buchberger_katsura3_p32003",
        Tier::Quick,
        "groebner_f4::buchberger + reduce_basis (BigUint coefficients) on Katsura-3 over F_32003",
        buchberger_katsura3,
    );
}
