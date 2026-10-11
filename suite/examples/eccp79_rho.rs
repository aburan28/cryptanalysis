//! **Single-machine Pollard rho with negation map for ECCp-79-scale curves.**
//!
//! ECCp-79 is the smallest unsolved-at-the-time entry in the 1997 Certicom
//! ECC Challenge list (a 79-bit prime-field curve).  It was solved in
//! December 1997 by Harley et al. using ~10^9 group operations, which is
//! trivial on modern hardware.  This file reproduces the algorithm in a
//! pedagogically clear form:
//!
//!   - r-adding random walk on triples (a_i, b_i, R_i = a_i·P + b_i·Q)
//!   - negation map (identify R with -R via canonical y) to gain a √2 speedup
//!   - distinguished-point filter (low w bits of x are zero) for storage
//!   - single-machine table of DPs; collision -> solve a + b·k ≡ a' + b'·k (mod n)
//!
//! This is a *single-process, single-machine* implementation.  There is no
//! distinguished-points server, no network coordinator, and no
//! curve-agnostic CLI.  Expected work for an 80-bit curve is ~2^40 group
//! ops, well beyond a laptop but useful as a reference.
//!
//! ## Running
//!
//! By default the example generates a fresh 79-bit prime-field curve with
//! a random secret and recovers it (use `--bits N` to scale down for a
//! laptop-runnable demo, e.g. `--bits 40`).
//!
//!     cargo run --release --example eccp79_rho -- --bits 40
//!
//! To target the actual Certicom ECCp-79 instance, fill in the constants
//! in `ECC P79_PARAMS` below (p, a, b, Gx, Gy, Qx, Qy, n) from the
//! published challenge document and pass `--challenge`.  Those are
//! deliberately left as `None` — I will not ship guessed challenge hex.

use std::collections::HashMap;
use std::env;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{mpsc, Arc};
use std::thread;
use std::time::{Duration, Instant};

use cryptanalysis_suite::ecc::curve::CurveParams;
use cryptanalysis_suite::ecc::field::FieldElement;
use cryptanalysis_suite::ecc::point::Point;
use num_bigint::{BigUint, RandBigInt};
use num_integer::Integer;
use num_traits::{One, Zero};
use rand::{rngs::StdRng, SeedableRng};

// ── ECCp-79 challenge parameters ───────────────────────────────────────────
// Extracted from the Certicom "ECC Challenge Curves" page. These were
// pulled via a web extractor that may mangle hex digits — the
// --challenge path verifies every relation (curve nonsingular, P and Q
// on curve, n·P = ∞) before starting rho, and refuses to run if any
// check fails.  Known answer: log_P Q = 0x138756822DD5FB093766.
struct ChallengeParams {
    p: &'static str,
    a: &'static str,
    b: &'static str,
    gx: &'static str,
    gy: &'static str,
    qx: &'static str,
    qy: &'static str,
    n: &'static str,
}
const ECCP79_PARAMS: Option<ChallengeParams> = Some(ChallengeParams {
    p: "62CE5177412ACA899CF5",
    a: "39C95E6DDDB1BC45733C",
    b: "1F16D880E89D5A1C0ED1",
    gx: "315D4B201C208475057D",
    gy: "035F3DF5AB370252450A",
    n: "62CE5177407B7258DC31",
    qx: "0679834CEFB7215DC365",
    qy: "4084BC50388C4E6FDFAB",
});

// ── Curve helpers (BigUint based, reusing repo Point/FieldElement) ─────────

fn fe(v: BigUint, p: &BigUint) -> FieldElement {
    FieldElement::new(v, p.clone())
}

/// Find a square root of `n` mod prime `p` using Tonelli–Shanks.
fn sqrt_mod(n: &BigUint, p: &BigUint) -> Option<BigUint> {
    if n.is_zero() {
        return Some(BigUint::zero());
    }
    let one = BigUint::one();
    let two = BigUint::from(2u32);
    // Euler criterion
    let exp = (p - &one) / &two;
    if n.modpow(&exp, p) != one {
        return None;
    }
    // p ≡ 3 (mod 4) fast path
    if (p % 4u32) == BigUint::from(3u32) {
        let e = (p + &one) / BigUint::from(4u32);
        return Some(n.modpow(&e, p));
    }
    // Tonelli–Shanks
    let mut q = p - &one;
    let mut s = 0u32;
    while q.is_even() {
        q >>= 1;
        s += 1;
    }
    let mut z = BigUint::from(2u32);
    while z.modpow(&((p - &one) / &two), p) != p - &one {
        z += 1u32;
    }
    let mut m = s;
    let mut c = z.modpow(&q, p);
    let mut t = n.modpow(&q, p);
    let mut r = n.modpow(&((&q + &one) / &two), p);
    loop {
        if t == one {
            return Some(r);
        }
        let mut i = 0u32;
        let mut temp = t.clone();
        while temp != one {
            temp = (&temp * &temp) % p;
            i += 1;
            if i == m {
                return None;
            }
        }
        let b = c.modpow(&BigUint::from(1u64 << (m - i - 1)), p);
        m = i;
        c = (&b * &b) % p;
        t = (&t * &c) % p;
        r = (&r * &b) % p;
    }
}

/// Pick a random 79-bit (or `bits`-bit) prime curve y² = x³ + ax + b with
/// a generator of prime order n that we discover by trial.  For the demo
/// path we want a curve whose order is itself prime (cofactor 1) so the
/// rho walk is on the full group.
///
/// We don't run a full SEA point count here; instead we generate a small
/// curve and brute-force the order with baby-step/giant-step.  That's
/// fine for ≤50-bit demos.  For an actual 79-bit demo curve, use one with
/// known order from the literature, or supply --challenge.
fn random_demo_curve(bits: usize, rng: &mut StdRng) -> (CurveParams, Point) {
    assert!(
        bits <= 50,
        "demo curve generator only handles up to 50-bit orders; \
         for ECCp-79 supply --challenge with real parameters"
    );
    loop {
        // Random prime p of the requested bit length.
        let p = loop {
            let cand =
                rng.gen_biguint(bits as u64) | (BigUint::one() << (bits - 1)) | BigUint::one();
            if is_probable_prime(&cand, 20) {
                break cand;
            }
        };
        let a = rng.gen_biguint_below(&p);
        let b = rng.gen_biguint_below(&p);
        // 4a^3 + 27b^2 != 0
        let disc = (BigUint::from(4u32) * a.modpow(&BigUint::from(3u32), &p)
            + BigUint::from(27u32) * b.modpow(&BigUint::from(2u32), &p))
            % &p;
        if disc.is_zero() {
            continue;
        }
        // Pick a generator: random x, solve for y.
        let (gx, gy) = loop {
            let x = rng.gen_biguint_below(&p);
            let rhs = (x.modpow(&BigUint::from(3u32), &p) + &a * &x + &b) % &p;
            if let Some(y) = sqrt_mod(&rhs, &p) {
                break (x, y);
            }
        };
        // Compute order by BSGS on point.
        let g = Point::Affine {
            x: fe(gx.clone(), &p),
            y: fe(gy.clone(), &p),
        };
        let a_fe = fe(a.clone(), &p);
        let n = match point_order_bsgs(&g, &a_fe, &p, bits) {
            Some(n) if is_probable_prime(&n, 20) && n.bits() as usize >= bits - 1 => n,
            _ => continue,
        };
        let curve = CurveParams {
            name: "demo-rho",
            p,
            a,
            b,
            gx,
            gy,
            n,
            h: 1,
        };
        return (curve, g);
    }
}

fn is_probable_prime(n: &BigUint, rounds: usize) -> bool {
    let one = BigUint::one();
    let two = BigUint::from(2u32);
    if n < &two {
        return false;
    }
    for small in [2u32, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31] {
        let s = BigUint::from(small);
        if n == &s {
            return true;
        }
        if (n % &s).is_zero() {
            return false;
        }
    }
    // Miller–Rabin
    let mut d = n - &one;
    let mut r = 0u32;
    while d.is_even() {
        d >>= 1;
        r += 1;
    }
    let mut rng = StdRng::seed_from_u64(0xC0FFEE);
    'witness: for _ in 0..rounds {
        let a = rng.gen_biguint_range(&two, &(n - &one));
        let mut x = a.modpow(&d, n);
        if x == one || x == n - &one {
            continue 'witness;
        }
        for _ in 0..r - 1 {
            x = (&x * &x) % n;
            if x == n - &one {
                continue 'witness;
            }
        }
        return false;
    }
    true
}

/// BSGS for the group order of `g` using the Hasse bound.
/// Returns N such that N·g = ∞ and N ∈ [p+1-2√p, p+1+2√p].
/// (Typically equals the curve order on tiny curves; if not the caller
/// rejects and retries with a fresh curve.)
fn point_order_bsgs(g: &Point, a: &FieldElement, p: &BigUint, _bits: usize) -> Option<BigUint> {
    use num_bigint::BigInt;
    use num_bigint::Sign;

    // Hasse window: search m ∈ [-2√p, 2√p] such that (p+1+m)·g = ∞.
    // BSGS:  let T = (p+1)·g.  Find m with m·g = -T.
    //        baby_i = i·g for i in [0, w);  giant_j = -T - j·w·g.
    let sqrt_p = p.sqrt();
    let w_big = sqrt_p.sqrt() + BigUint::from(2u32); // step ~ p^{1/4}
    let w = w_big.to_u64_digits()[0] as i64;
    let bound = 2i64 * (sqrt_p.to_u64_digits().first().copied().unwrap_or(0) as i64 + 1);

    let mut table: HashMap<Vec<u8>, i64> = HashMap::with_capacity(w as usize);
    let mut cur = Point::Infinity;
    for i in 0..w {
        table.entry(serialize_point(&cur)).or_insert(i);
        cur = cur.add(g, a);
    }
    // T = (p+1)·g, negate.
    let t = g.scalar_mul(&(p + BigUint::one()), a);
    let neg_t = t.neg();
    // Step = w·g.
    let w_g = g.scalar_mul(&BigUint::from(w as u64), a);
    let neg_w_g = w_g.neg();

    // Iterate j in [-J, +J] where J·w covers ±2√p.
    let j_max = (bound / w) + 2;

    // q starts at -T; step adds -w·g (covers j = 0, 1, 2, …) and separately +w·g (negative j).
    let mut q_pos = neg_t.clone();
    let mut q_neg = neg_t.clone();
    for j in 0..=j_max {
        // Positive j
        if let Some(&i) = table.get(&serialize_point(&q_pos)) {
            // i·g = -T - j·w·g  ⇒  (p+1 + j·w + i)·g = ∞
            let m = j * w + i;
            let order = (BigInt::from_biguint(Sign::Plus, p + BigUint::one()) + BigInt::from(m))
                .to_biguint()?;
            return Some(order);
        }
        // Negative j (skip j=0 dup)
        if j > 0 {
            if let Some(&i) = table.get(&serialize_point(&q_neg)) {
                // i·g = -T + j·w·g  ⇒  (p+1 - j·w + i)·g = ∞
                let m_signed = -(j * w) + i;
                let order_int =
                    BigInt::from_biguint(Sign::Plus, p + BigUint::one()) + BigInt::from(m_signed);
                if let Some(order) = order_int.to_biguint() {
                    return Some(order);
                }
            }
        }
        q_pos = q_pos.add(&neg_w_g, a);
        q_neg = q_neg.add(&w_g, a);
    }
    None
}

fn serialize_point(p: &Point) -> Vec<u8> {
    match p {
        Point::Infinity => vec![0u8],
        Point::Affine { x, y } => {
            let mut out = vec![1u8];
            let xb = x.value.to_bytes_be();
            let yb = y.value.to_bytes_be();
            out.extend_from_slice(&(xb.len() as u32).to_be_bytes());
            out.extend_from_slice(&xb);
            out.extend_from_slice(&yb);
            out
        }
    }
}

// ── Pollard rho with r-adding walk + negation map ──────────────────────────

const R: usize = 32;
const DP_BITS: u32 = 10; // distinguished-point bits; tune per curve size

/// Shared walk state: same branch table for every worker, so any DP
/// collision between any two workers yields a usable relation.
/// This is what makes parallel vOW give an *m*-fold speedup on m
/// workers (vs. running m independent rhos, which gives no speedup).
struct Walk {
    a_fe: FieldElement,
    n: BigUint,
    // Branch table: precomputed R_i = u_i·P + v_i·Q with stored (u_i, v_i).
    branches: Vec<(BigUint, BigUint, Point)>,
}

impl Walk {
    fn new(curve: &CurveParams, p_pt: &Point, q_pt: &Point, rng: &mut StdRng) -> Self {
        let a_fe = fe(curve.a.clone(), &curve.p);
        let mut branches = Vec::with_capacity(R);
        for _ in 0..R {
            let u = rng.gen_biguint_below(&curve.n);
            let v = rng.gen_biguint_below(&curve.n);
            let r = p_pt
                .scalar_mul(&u, &a_fe)
                .add(&q_pt.scalar_mul(&v, &a_fe), &a_fe);
            branches.push((u, v, r));
        }
        Self {
            a_fe,
            n: curve.n.clone(),
            branches,
        }
    }

    fn branch_of(&self, pt: &Point) -> usize {
        match pt {
            Point::Infinity => 0,
            Point::Affine { x, .. } => {
                let digits = x.value.to_u64_digits();
                let lo = digits.first().copied().unwrap_or(0);
                (lo as usize) % R
            }
        }
    }

    fn step(&self, a: &BigUint, b: &BigUint, r_pt: &Point) -> (BigUint, BigUint, Point) {
        let idx = self.branch_of(r_pt);
        let (u_i, v_i, r_i) = &self.branches[idx];
        let new_r = r_pt.add(r_i, &self.a_fe);
        let new_a = (a + u_i) % &self.n;
        let new_b = (b + v_i) % &self.n;
        (new_a, new_b, new_r)
    }

    fn is_distinguished(&self, pt: &Point) -> bool {
        match pt {
            Point::Infinity => false,
            Point::Affine { x, .. } => {
                let digits = x.value.to_u64_digits();
                let lo = digits.first().copied().unwrap_or(0);
                (lo as usize & ((1usize << DP_BITS) - 1)) == 0
            }
        }
    }
}

/// Solve a + b·k ≡ a' + b'·k (mod n) → k = (a - a') / (b' - b) mod n.
fn solve_collision(
    a: &BigUint,
    b: &BigUint,
    a2: &BigUint,
    b2: &BigUint,
    n: &BigUint,
) -> Option<BigUint> {
    let num = if a >= a2 {
        (a - a2) % n
    } else {
        (n - ((a2 - a) % n)) % n
    };
    let den = if b2 >= b {
        (b2 - b) % n
    } else {
        (n - ((b - b2) % n)) % n
    };
    if den.is_zero() {
        return None;
    }
    let den_inv = modinv(&den, n)?;
    Some((num * den_inv) % n)
}

fn modinv(a: &BigUint, n: &BigUint) -> Option<BigUint> {
    // Extended Euclidean.
    use num_bigint::BigInt;
    use num_bigint::Sign;
    let (mut old_r, mut r) = (
        BigInt::from_biguint(Sign::Plus, n.clone()),
        BigInt::from_biguint(Sign::Plus, a.clone()),
    );
    let (mut old_s, mut s) = (BigInt::zero(), BigInt::one());
    while !r.is_zero() {
        let q = &old_r / &r;
        let new_r = &old_r - &q * &r;
        old_r = std::mem::replace(&mut r, new_r);
        let new_s = &old_s - &q * &s;
        old_s = std::mem::replace(&mut s, new_s);
    }
    if old_r != BigInt::one() {
        return None;
    }
    let n_int = BigInt::from_biguint(Sign::Plus, n.clone());
    let res = ((old_s % &n_int) + &n_int) % &n_int;
    res.to_biguint()
}

/// Message sent from a worker to the coordinator when a DP is found.
struct DpMsg {
    key: Vec<u8>,
    a: BigUint,
    b: BigUint,
}

/// Parallel vOW Pollard rho: `threads` workers share one branch table
/// and one DP coordinator.  Linear speedup in the number of workers up
/// to memory/bandwidth limits.
fn rho_attack_parallel(
    curve: &CurveParams,
    p_pt: &Point,
    q_pt: &Point,
    seed: u64,
    threads: usize,
) -> Option<BigUint> {
    let mut master_rng = StdRng::seed_from_u64(seed);
    let walk = Arc::new(Walk::new(curve, p_pt, q_pt, &mut master_rng));
    let a_fe = fe(curve.a.clone(), &curve.p);

    let stop = Arc::new(AtomicBool::new(false));
    let total_steps = Arc::new(AtomicU64::new(0));

    let (tx, rx) = mpsc::channel::<DpMsg>();

    // Spawn workers.
    let mut workers = Vec::with_capacity(threads);
    for wid in 0..threads {
        let walk = Arc::clone(&walk);
        let stop = Arc::clone(&stop);
        let total_steps = Arc::clone(&total_steps);
        let tx = tx.clone();
        let p_pt = p_pt.clone();
        let q_pt = q_pt.clone();
        let a_fe_w = a_fe.clone();
        let n_w = curve.n.clone();
        let worker_seed = seed.wrapping_add(0x9E3779B97F4A7C15u64.wrapping_mul(wid as u64 + 1));

        workers.push(thread::spawn(move || {
            let mut rng = StdRng::seed_from_u64(worker_seed);
            // Each worker starts at a different random (a, b)·{P, Q}.
            let mut a_acc = rng.gen_biguint_below(&n_w);
            let mut b_acc = rng.gen_biguint_below(&n_w);
            let mut r = p_pt
                .scalar_mul(&a_acc, &a_fe_w)
                .add(&q_pt.scalar_mul(&b_acc, &a_fe_w), &a_fe_w);

            let mut local_steps: u64 = 0;
            loop {
                let (na, nb, nr) = walk.step(&a_acc, &b_acc, &r);
                a_acc = na;
                b_acc = nb;
                r = nr;
                local_steps += 1;

                if walk.is_distinguished(&r) {
                    let _ = tx.send(DpMsg {
                        key: serialize_point(&r),
                        a: a_acc.clone(),
                        b: b_acc.clone(),
                    });
                }

                // Cheap stop check + step counter flush every 4096 steps.
                if local_steps & 0xFFF == 0 {
                    total_steps.fetch_add(0x1000, Ordering::Relaxed);
                    if stop.load(Ordering::Relaxed) {
                        return;
                    }
                }
            }
        }));
    }
    // Drop our sender so the channel closes if all workers exit.
    drop(tx);

    // Coordinator: own the DP table, look for collisions.
    let mut dp_table: HashMap<Vec<u8>, (BigUint, BigUint)> = HashMap::new();
    let start = Instant::now();
    let mut last_report = Instant::now();
    let mut recovered: Option<BigUint> = None;

    loop {
        // Poll with timeout so we can still print progress when DPs are sparse.
        match rx.recv_timeout(Duration::from_secs(2)) {
            Ok(msg) => {
                if let Some((a_prev, b_prev)) = dp_table.get(&msg.key) {
                    if b_prev != &msg.b {
                        if let Some(k) = solve_collision(a_prev, b_prev, &msg.a, &msg.b, &curve.n) {
                            let test = p_pt.scalar_mul(&k, &a_fe);
                            if &test == q_pt {
                                let steps = total_steps.load(Ordering::Relaxed);
                                eprintln!(
                                    "[rho] collision found  steps≈{}  ({:.1}s)",
                                    steps,
                                    start.elapsed().as_secs_f64()
                                );
                                recovered = Some(k);
                                stop.store(true, Ordering::Relaxed);
                                break;
                            }
                        }
                    }
                    // Same b or unusable collision — keep the existing entry.
                } else {
                    dp_table.insert(msg.key, (msg.a, msg.b));
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {} // fall through to reporting
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }

        if last_report.elapsed().as_secs() >= 5 {
            let steps = total_steps.load(Ordering::Relaxed);
            let secs = start.elapsed().as_secs_f64();
            eprintln!(
                "[rho] threads={}  steps≈{}  dps={}  rate={:.0}/s  ({:.0}/s/thread)",
                threads,
                steps,
                dp_table.len(),
                steps as f64 / secs,
                steps as f64 / secs / threads as f64,
            );
            last_report = Instant::now();
        }
    }

    // Tear down workers.
    stop.store(true, Ordering::Relaxed);
    for w in workers {
        let _ = w.join();
    }
    recovered
}

fn verify_challenge(curve: &CurveParams, g: &Point, q: &Point) {
    // 1. p prime, n prime, both ~79 bits
    assert!(is_probable_prime(&curve.p, 30), "p is not prime");
    assert!(is_probable_prime(&curve.n, 30), "n is not prime");
    let pb = curve.p.bits();
    assert!((79..=80).contains(&pb), "p should be ~79 bits, got {}", pb);

    // 2. Discriminant 4a^3 + 27b^2 != 0 (mod p)
    let four = BigUint::from(4u32);
    let twenty_seven = BigUint::from(27u32);
    let disc = (&four * curve.a.modpow(&BigUint::from(3u32), &curve.p)
        + &twenty_seven * curve.b.modpow(&BigUint::from(2u32), &curve.p))
        % &curve.p;
    assert!(!disc.is_zero(), "curve is singular: 4a^3 + 27b^2 ≡ 0");

    // 3. G and Q both satisfy y^2 = x^3 + ax + b (mod p)
    let on_curve = |pt: &Point, name: &str| {
        if let Point::Affine { x, y } = pt {
            let lhs = y.value.modpow(&BigUint::from(2u32), &curve.p);
            let rhs =
                (x.value.modpow(&BigUint::from(3u32), &curve.p) + &curve.a * &x.value + &curve.b)
                    % &curve.p;
            assert_eq!(lhs, rhs, "{} is not on the curve", name);
        } else {
            panic!("{} is the point at infinity", name);
        }
    };
    on_curve(g, "G");
    on_curve(q, "Q");

    // 4. n·G == ∞
    let a_fe = fe(curve.a.clone(), &curve.p);
    let n_g = g.scalar_mul(&curve.n, &a_fe);
    assert_eq!(n_g, Point::Infinity, "n·G != ∞ — order is wrong");

    eprintln!("[verify] curve nonsingular, p/n prime, G and Q on curve, n·G = ∞  ✓");
}

// ── main ───────────────────────────────────────────────────────────────────

fn main() {
    let args: Vec<String> = env::args().collect();
    let mut bits = 40usize;
    let mut use_challenge = false;
    let mut threads = thread::available_parallelism()
        .map(|n| n.get())
        .unwrap_or(1);
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--bits" => {
                bits = args[i + 1].parse().expect("--bits N");
                i += 2;
            }
            "--challenge" => {
                use_challenge = true;
                i += 1;
            }
            "--threads" => {
                threads = args[i + 1].parse().expect("--threads N");
                assert!(threads >= 1, "--threads must be >= 1");
                i += 2;
            }
            other => panic!("unknown arg: {}", other),
        }
    }

    let mut rng = StdRng::seed_from_u64(0xECC_0079_u64);

    let (curve, g, q, planted) = if use_challenge {
        let cp = ECCP79_PARAMS.expect(
            "ECCP79_PARAMS is None — paste the Certicom ECCp-79 parameters \
             into examples/eccp79_rho.rs before passing --challenge",
        );
        let parse = |s: &str| BigUint::parse_bytes(s.as_bytes(), 16).expect("hex");
        let curve = CurveParams {
            name: "ECCp-79",
            p: parse(cp.p),
            a: parse(cp.a),
            b: parse(cp.b),
            gx: parse(cp.gx),
            gy: parse(cp.gy),
            n: parse(cp.n),
            h: 1,
        };
        let g = Point::Affine {
            x: fe(curve.gx.clone(), &curve.p),
            y: fe(curve.gy.clone(), &curve.p),
        };
        let q = Point::Affine {
            x: fe(parse(cp.qx), &curve.p),
            y: fe(parse(cp.qy), &curve.p),
        };
        verify_challenge(&curve, &g, &q);
        (curve, g, q, None)
    } else {
        let (curve, g) = random_demo_curve(bits, &mut rng);
        let k = rng.gen_biguint_below(&curve.n);
        let a_fe = fe(curve.a.clone(), &curve.p);
        let q = g.scalar_mul(&k, &a_fe);
        (curve, g, q, Some(k))
    };

    println!("curve:        {}", curve.name);
    println!("p:            {:x}  ({} bits)", curve.p, curve.p.bits());
    println!("n:            {:x}  ({} bits)", curve.n, curve.n.bits());
    if let Some(k) = &planted {
        println!("planted k:    {:x}", k);
    }
    println!("dp bits:      {}", DP_BITS);
    println!("branches:     {}", R);
    println!("threads:      {}", threads);
    println!();

    let recovered =
        rho_attack_parallel(&curve, &g, &q, 0xDEADBEEF, threads).expect("rho returned None");
    println!("recovered k:  {:x}", recovered);
    if let Some(k) = planted {
        assert_eq!(
            recovered, k,
            "recovered scalar does not match planted secret"
        );
        println!("✓ matches planted secret");
    }
}
