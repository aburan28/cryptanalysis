//! Assumption 1's predicate, made sound: the degree-4 closure on targets
//! **verified non-decomposable**, where resolving *is* refuting.
//!
//! `examples/assumption1_closure.rs` records why the naive version fails: the
//! `m = 2` swap symmetry `(P1,P2) <-> (P2,P1)` gives every decomposable target
//! at least two solutions, so no variable is ever pinned and "unresolved"
//! measures decomposability rather than degree.
//!
//! The fix is not symmetry-breaking constraints (which would raise the degree
//! and change the object) but the choice of target. On a target with **no**
//! solution the only possible resolution is a refutation, the symmetry has
//! nothing to act on, and the predicate becomes clean:
//!
//! * degree-4 closure **refutes** ⟹ degree 4 suffices to decide this instance;
//! * degree-4 closure **does not refute** ⟹ no degree-≤4 computation can decide
//!   it, F4 included ⟹ `d_F4 ≥ 5` at that cell.
//!
//! Both directions are now sound, because the target's non-decomposability is
//! established by exhaustive search rather than assumed.
//!
//! ## How non-decomposability is verified
//!
//! `S3(x1, x2, X) = (x1x2 + x1X + x2X)^2 + x1x2X + b` is quadratic in `X`, so
//! for each of the `2^{2k}` pairs `(x1,x2) in V^2` its roots in `X` are the
//! targets that pair decomposes. Sweeping `V^2` and collecting every root gives
//! the **exact** decomposable set; any `X` outside it provably has no
//! decomposition over `V`. At `k = ceil(n/2)` that sweep is `~2^{n+1}` field
//! operations — affordable to about `n = 25`, and it is the real ceiling here.
//!
//! Roots come from solving that quadratic directly (half-trace), which is `O(1)`
//! per pair. Each chosen target is then re-checked by evaluating `S3` over all of
//! `V^2` directly, independently of the root solver.
//!
//! ## Scope
//!
//! This reaches `n <= ~25`, which sits **inside** the `n <= 21` region Semaev's
//! 2300 MAGMA systems already cover. It therefore does **not** touch the
//! disputed `n = 40` versus `n = 45` boundary. What it does supply is the first
//! independent, commensurable test of the `d_F4 <= 4` predicate in this
//! repository, on his own support region — a reproduction check, which is worth
//! having precisely because nobody here has run one.
//!
//! ```sh
//! F4_F2_MAX_ROWS=300000 F4_F2_MAX_COLS=600000 \
//!   cargo run --release --example assumption1_refutation -- --n-max 17
//! ```

use cryptanalysis_suite::binary_ecc::{F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, matrix_f4_f2, solving_profile, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::collections::HashSet;

/// `S3(x1,x2,x3) = (x1x2 + x1x3 + x2x3)^2 + x1x2x3 + b` on `y^2+xy=x^3+b`.
fn s3(
    x1: &F2mElement,
    x2: &F2mElement,
    x3: &F2mElement,
    b: &F2mElement,
    irr: &IrreduciblePoly,
) -> F2mElement {
    let p12 = x1.mul(x2, irr);
    let p13 = x1.mul(x3, irr);
    let p23 = x2.mul(x3, irr);
    let sum = p12.add(&p13).add(&p23);
    sum.square(irr).add(&p12.mul(x3, irr)).add(b)
}

fn elem(bits: u64, n: u32) -> F2mElement {
    F2mElement::from_bit_positions(
        &(0..n).filter(|i| (bits >> i) & 1 == 1).collect::<Vec<_>>(),
        n,
    )
}

fn bits_of(e: &F2mElement) -> u64 {
    e.raw_bits().first().copied().unwrap_or(0)
}

fn random_subspace_basis(n: u32, k: u32, rng: &mut StdRng) -> Option<Vec<F2mElement>> {
    let mut basis: Vec<F2mElement> = Vec::new();
    let mut pivots: Vec<(u32, u64)> = Vec::new();
    for _ in 0..(64 * k + 256) {
        if basis.len() == k as usize {
            return Some(basis);
        }
        let bits: u64 = rng.gen::<u64>() & ((1u64 << n) - 1);
        if bits == 0 {
            continue;
        }
        let mut v = bits;
        for (p, row) in &pivots {
            if (v >> p) & 1 == 1 {
                v ^= row;
            }
        }
        if v == 0 {
            continue;
        }
        pivots.push((63 - v.leading_zeros(), v));
        pivots.sort_by_key(|a| std::cmp::Reverse(a.0));
        basis.push(elem(bits, n));
    }
    None
}

/// Every element of the span of `basis`, as raw bit patterns.
fn span(basis: &[F2mElement], n: u32) -> Vec<F2mElement> {
    let k = basis.len();
    (0..(1u64 << k))
        .map(|mask| {
            let mut acc = F2mElement::zero(n);
            for (i, b) in basis.iter().enumerate() {
                if (mask >> i) & 1 == 1 {
                    acc = acc.add(b);
                }
            }
            acc
        })
        .collect()
}

/// `Tr(a) = sum_{i<n} a^{2^i}`.
fn trace(a: &F2mElement, n: u32, irr: &IrreduciblePoly) -> bool {
    let mut acc = F2mElement::zero(n);
    let mut t = a.clone();
    for _ in 0..n {
        acc = acc.add(&t);
        t = t.square(irr);
    }
    !acc.is_zero()
}

/// Half-trace: `z` with `z^2 + z = a`, valid for odd `n` when `Tr(a) = 0`.
fn half_trace(a: &F2mElement, n: u32, irr: &IrreduciblePoly) -> F2mElement {
    let mut acc = a.clone();
    let mut t = a.clone();
    for _ in 0..((n - 1) / 2) {
        t = t.square(irr).square(irr);
        acc = acc.add(&t);
    }
    acc
}

/// Roots in `X` of `S3(x1,x2,X) = 0`, which is the quadratic
/// `A X^2 + B X + C` with `A = (x1+x2)^2`, `B = x1 x2`, `C = (x1 x2)^2 + b`.
///
/// Solving it is `O(1)` per pair. The first version of this example swept the
/// whole field per pair instead, which is `O(2^{2n+1})` overall and did not
/// finish at `n = 15`.
fn s3_roots_in_x3(
    x1: &F2mElement,
    x2: &F2mElement,
    b: &F2mElement,
    n: u32,
    irr: &IrreduciblePoly,
) -> Vec<F2mElement> {
    let a = x1.add(x2).square(irr);
    let bb = x1.mul(x2, irr);
    let c = bb.square(irr).add(b);
    if a.is_zero() {
        // linear: B X = C
        if bb.is_zero() {
            return Vec::new(); // B = C = 0 impossible here since b != 0
        }
        let inv = match bb.flt_inverse(irr) {
            Some(i) => i,
            None => return Vec::new(),
        };
        return vec![c.mul(&inv, irr)];
    }
    let a_inv = match a.flt_inverse(irr) {
        Some(i) => i,
        None => return Vec::new(),
    };
    if bb.is_zero() {
        // X^2 = C/A has the unique root (C/A)^{2^{n-1}} in characteristic 2
        let mut r = c.mul(&a_inv, irr);
        for _ in 0..(n - 1) {
            r = r.square(irr);
        }
        return vec![r];
    }
    // X = (B/A) Z  =>  Z^2 + Z = C A / B^2
    let t = bb.mul(&a_inv, irr); // B/A
    let rhs = c.mul(&a, irr).mul(
        &match bb.square(irr).flt_inverse(irr) {
            Some(i) => i,
            None => return Vec::new(),
        },
        irr,
    );
    if trace(&rhs, n, irr) {
        return Vec::new(); // unsolvable
    }
    let z = half_trace(&rhs, n, irr);
    let one = F2mElement::one(n);
    vec![t.mul(&z, irr), t.mul(&z.add(&one), irr)]
}

/// The EXACT decomposable set: every `X` admitting some `(x1,x2) in V^2` with
/// `S3(x1,x2,X) = 0`, by solving the quadratic for each pair.
fn decomposable_set(
    v: &[F2mElement],
    n: u32,
    b: &F2mElement,
    irr: &IrreduciblePoly,
) -> HashSet<u64> {
    let mut out = HashSet::new();
    for x1 in v.iter() {
        for x2 in v.iter() {
            for r in s3_roots_in_x3(x1, x2, b, n, irr) {
                out.insert(bits_of(&r));
            }
        }
    }
    out
}

fn signature(polys: &[F2BoolPoly]) -> Vec<Vec<u64>> {
    let mut s: Vec<Vec<u64>> = polys
        .iter()
        .map(|p| {
            let mut m: Vec<u64> = p.terms.iter().map(|t| t.mask).collect();
            m.sort_unstable();
            m
        })
        .filter(|m: &Vec<u64>| !m.is_empty())
        .collect();
    s.sort();
    s
}

/// Why a degree-`d` closure stopped. A `d_F4 >= d+1` verdict requires the FULL
/// degree-`d` part of the ideal, so it may only be drawn from `Converged`: a
/// generating set still changing when the round budget ran out supports no
/// claim about degree at all.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
enum Closure {
    /// Fixed point reached: the set is the full degree-`d` part.
    Converged,
    /// Macaulay matrix exceeded `F4_F2_MAX_ROWS`/`COLS`.
    SizeCap,
    /// `max_rounds` exhausted while still changing. NOT a degree result.
    RoundsExhausted,
}

/// Degree-`d` closure: feed degree falls back to a fixed point.
fn degree_closure(
    polys: &[F2BoolPoly],
    n_vars: usize,
    d: u32,
    max_rounds: usize,
) -> (Vec<F2BoolPoly>, usize, Closure) {
    let mut gens = polys.to_vec();
    let mut prev = signature(&gens);
    for round in 1..=max_rounds {
        let reduced = match matrix_f4_f2(&gens, n_vars, d) {
            Some(r) => r,
            None => return (gens, round - 1, Closure::SizeCap),
        };
        let next: Vec<_> = reduced
            .into_iter()
            .filter(|p| !p.terms.is_empty())
            .collect();
        let sig = signature(&next);
        if sig == prev {
            return (next, round, Closure::Converged);
        }
        prev = sig;
        gens = next;
    }
    (gens, max_rounds, Closure::RoundsExhausted)
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let flag = |name: &str, default: i64| -> i64 {
        args.iter()
            .position(|a| a == name)
            .and_then(|i| args.get(i + 1))
            .and_then(|v| v.parse().ok())
            .unwrap_or(default)
    };
    let n_min = flag("--n-min", 5) as u32;
    let n_max = flag("--n-max", 17) as u32;
    let trials = flag("--trials", 2) as usize;
    let d = flag("--degree", 4) as u32;
    let rounds = flag("--rounds", 8) as usize;
    let seed = flag("--seed", 0x5A1E) as u64;
    let m = 2usize;

    println!("# Assumption 1's d_F4 <= {d} predicate on VERIFIED NON-DECOMPOSABLE targets");
    println!();
    println!("m = {m}, trials = {trials}, seed = {seed:#x}");
    println!();
    println!("On a target with no decomposition the only resolution is a refutation, so");
    println!("the swap symmetry cannot confound the verdict (cf. assumption1_closure.rs).");
    println!("  REFUTES     => degree {d} decides this instance");
    println!(
        "  NO REFUTE   => no degree-<= {d} computation can decide it => d_F4 >= {}",
        d + 1
    );
    println!();
    println!("| n | k | vars | field | decomposable | non-dec | rounds | converged | refuted | verdict |");
    println!("|--:|--:|-----:|------:|-------------:|--------:|-------:|:---------:|:-------:|:--------|");

    let mut rng = StdRng::seed_from_u64(seed);
    for n in (n_min..=n_max).step_by(2) {
        let k = n.div_ceil(2); // ceil(n/2)
        let irr = match find_irreducible_sparse(n) {
            Some(i) => i,
            None => continue,
        };
        let st = FieldStructure::new(n, &irr);
        let b = F2mElement::one(n);

        let basis = match random_subspace_basis(n, k, &mut rng) {
            Some(x) => x,
            None => continue,
        };
        let v = span(&basis, n);
        let dec = decomposable_set(&v, n, &b, &irr);
        let field_sz = 1u64 << n;
        let non_dec: Vec<u64> = (0..field_sz).filter(|x| !dec.contains(x)).collect();
        if non_dec.is_empty() {
            println!(
                "| {} | {} | — | {} | {} | 0 | — | — | no non-decomposable target exists |",
                n,
                k,
                field_sz,
                dec.len()
            );
            continue;
        }

        for t in 0..trials.min(non_dec.len()) {
            let x_r = elem(non_dec[(t * 7 + 1) % non_dec.len()], n);
            // sanity: re-verify this specific target has no solution
            let target_bits = bits_of(&x_r);
            let mut solvable = false;
            'outer: for x1 in v.iter() {
                for x2 in v.iter() {
                    // independent check: evaluate S3 directly, not via the root solver
                    if s3(x1, x2, &x_r, &b, &irr).is_zero() {
                        solvable = true;
                        break 'outer;
                    }
                }
            }
            let _ = target_bits;
            if solvable {
                println!(
                    "| {} | {} | — | — | — | — | — | — | GATE FAILED: target is decomposable |",
                    n, k
                );
                continue;
            }
            let sys = match build_decomposition_system(&basis, &x_r, &b, m, &st) {
                Some(s) => s,
                None => continue,
            };
            let (closure, used, outcome) = degree_closure(&sys.equations, sys.n_vars, d, rounds);
            let (refuted, verdict) = match solving_profile(&closure, sys.n_vars, d) {
                None => ("—".to_string(), "SIZE CAP (no verdict)".to_string()),
                Some(p) if p.refuted => (
                    // A refutation found is a refutation, whether or not the
                    // closure had converged: it exhibits 1 in the degree-d part.
                    "yes".to_string(),
                    format!("REFUTES: degree {d} decides"),
                ),
                Some(_) => match outcome {
                    // The d_F4 >= d+1 verdict needs the FULL degree-d part.
                    Closure::Converged => (
                        "no".to_string(),
                        format!("NO REFUTE at converged closure => d_F4 >= {}", d + 1),
                    ),
                    Closure::SizeCap => ("no".to_string(), "SIZE CAP (no verdict)".to_string()),
                    Closure::RoundsExhausted => (
                        "no".to_string(),
                        "NOT CONVERGED in round budget (no degree verdict)".to_string(),
                    ),
                },
            };
            println!(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |",
                n,
                k,
                sys.n_vars,
                field_sz,
                dec.len(),
                non_dec.len(),
                used,
                if outcome == Closure::Converged {
                    "yes"
                } else {
                    "NO"
                },
                refuted,
                verdict
            );
        }
    }
    println!();
    println!("Reaches n <= ~25, inside Semaev's own n <= 21 support region: a reproduction");
    println!("check, not a test of the disputed n = 40 versus n = 45 boundary.");
}
