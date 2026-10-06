//! Matched native Pollard-rho iteration benchmark for P-256 isogenous curves.
//!
//! Every curve uses the suite's fixed-limb P-256 Montgomery field and the
//! same general-a complete projective addition formula.  Sixty-four walks are
//! batch-normalized with one inversion, then partitioned by affine x.  This is
//! comparative research code, not a production ECDLP solver.

use cryptanalysis_suite::ct_bignum::{Uint, U256};
use cryptanalysis_suite::ecc::p256_field::P256FieldElement as Fe;
use num_bigint::BigUint;
use num_traits::Zero;
use serde_json::{json, Value};
use std::collections::HashMap;
use std::env;
use std::fs;
use std::hint::black_box;
use std::path::PathBuf;
use std::time::{Duration, Instant};

const BATCH_WIDTH: usize = 64;
const TABLE_SIZE: usize = 16;

#[derive(Clone)]
struct Candidate {
    id: String,
    a: BigUint,
    b: BigUint,
    n: BigUint,
    gx: BigUint,
    gy: BigUint,
    path_degrees: Vec<u64>,
}

#[derive(Copy, Clone, Debug)]
struct Point {
    x: Fe,
    y: Fe,
    z: Fe,
}

impl Point {
    const IDENTITY: Self = Self {
        x: Fe::ZERO,
        y: Fe::ONE,
        z: Fe::ZERO,
    };

    fn affine(x: &BigUint, y: &BigUint) -> Self {
        Self {
            x: Fe::from_biguint(x),
            y: Fe::from_biguint(y),
            z: Fe::ONE,
        }
    }
}

#[derive(Copy, Clone)]
struct Curve {
    a: Fe,
    b: Fe,
    b3: Fe,
}

impl Curve {
    fn new(a: &BigUint, b: &BigUint) -> Self {
        let b_fe = Fe::from_biguint(b);
        Self {
            a: Fe::from_biguint(a),
            b: b_fe,
            b3: b_fe.add(&b_fe).add(&b_fe),
        }
    }

    /// Renes-Costello-Batina Algorithm 1, identical for every candidate.
    #[inline(always)]
    fn add(&self, left: &Point, right: &Point) -> Point {
        let (x1, y1, z1) = (&left.x, &left.y, &left.z);
        let (x2, y2, z2) = (&right.x, &right.y, &right.z);
        let mut t0 = x1.mul(x2);
        let mut t1 = y1.mul(y2);
        let mut t2 = z1.mul(z2);
        let mut t3 = x1.add(y1);
        let mut t4 = x2.add(y2);
        t3 = t3.mul(&t4);
        t4 = t0.add(&t1);
        t3 = t3.sub(&t4);
        t4 = x1.add(z1);
        let mut t5 = x2.add(z2);
        t4 = t4.mul(&t5);
        t5 = t0.add(&t2);
        t4 = t4.sub(&t5);
        t5 = y1.add(z1);
        let mut x3 = y2.add(z2);
        t5 = t5.mul(&x3);
        x3 = t1.add(&t2);
        t5 = t5.sub(&x3);
        let mut z3 = self.a.mul(&t4);
        x3 = self.b3.mul(&t2);
        z3 = x3.add(&z3);
        x3 = t1.sub(&z3);
        z3 = t1.add(&z3);
        let mut y3 = x3.mul(&z3);
        t1 = t0.add(&t0);
        t1 = t1.add(&t0);
        t2 = self.a.mul(&t2);
        t4 = self.b3.mul(&t4);
        t1 = t1.add(&t2);
        t2 = t0.sub(&t2);
        t2 = self.a.mul(&t2);
        t4 = t4.add(&t2);
        t0 = t1.mul(&t4);
        y3 = y3.add(&t0);
        t0 = t5.mul(&t4);
        x3 = t3.mul(&x3);
        x3 = x3.sub(&t0);
        t0 = t3.mul(&t1);
        z3 = t5.mul(&z3);
        z3 = z3.add(&t0);
        Point {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// Renes-Costello-Batina Algorithm 3, with the same dynamic a,b on all curves.
    #[inline(always)]
    fn double(&self, point: &Point) -> Point {
        let (x, y, z) = (&point.x, &point.y, &point.z);
        let mut t0 = x.mul(x);
        let t1 = y.mul(y);
        let mut t2 = z.mul(z);
        let mut t3 = x.mul(y);
        t3 = t3.add(&t3);
        let mut z3 = x.mul(z);
        z3 = z3.add(&z3);
        let mut x3 = self.a.mul(&z3);
        let mut y3 = self.b3.mul(&t2);
        y3 = x3.add(&y3);
        x3 = t1.sub(&y3);
        y3 = t1.add(&y3);
        y3 = x3.mul(&y3);
        x3 = t3.mul(&x3);
        z3 = self.b3.mul(&z3);
        t2 = self.a.mul(&t2);
        t3 = t0.sub(&t2);
        t3 = self.a.mul(&t3);
        t3 = t3.add(&z3);
        z3 = t0.add(&t0);
        t0 = z3.add(&t0);
        t0 = t0.add(&t2);
        t0 = t0.mul(&t3);
        y3 = y3.add(&t0);
        t2 = y.mul(z);
        t2 = t2.add(&t2);
        t0 = t2.mul(&t3);
        x3 = x3.sub(&t0);
        z3 = t2.mul(&t1);
        z3 = z3.add(&z3);
        z3 = z3.add(&z3);
        Point {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    fn scalar_mul(&self, point: &Point, scalar: &BigUint) -> Point {
        let mut acc = Point::IDENTITY;
        let mut base = *point;
        let mut value = scalar.clone();
        while !value.is_zero() {
            if value.bit(0) {
                acc = self.add(&acc, &base);
            }
            base = self.double(&base);
            value >>= 1usize;
        }
        acc
    }

    fn normalize(&self, point: &Point) -> Point {
        if bool::from(point.z.ct_is_zero()) {
            return Point::IDENTITY;
        }
        let inverse = point.z.inv();
        Point {
            x: point.x.mul(&inverse),
            y: point.y.mul(&inverse),
            z: Fe::ONE,
        }
    }

    fn on_curve(&self, point: &Point) -> bool {
        if bool::from(point.z.ct_is_zero()) {
            return true;
        }
        let affine = self.normalize(point);
        let lhs = affine.y.mul(&affine.y);
        let rhs = affine
            .x
            .mul(&affine.x)
            .mul(&affine.x)
            .add(&self.a.mul(&affine.x))
            .add(&self.b);
        lhs == rhs
    }
}

fn batch_normalize(points: &mut [Point]) {
    let mut prefixes = vec![Fe::ONE; points.len()];
    let mut product = Fe::ONE;
    for (index, point) in points.iter().enumerate() {
        prefixes[index] = product;
        if !bool::from(point.z.ct_is_zero()) {
            product = product.mul(&point.z);
        }
    }
    let mut inverse = product.inv();
    for index in (0..points.len()).rev() {
        if bool::from(points[index].z.ct_is_zero()) {
            points[index] = Point::IDENTITY;
            continue;
        }
        let z = points[index].z;
        let z_inverse = inverse.mul(&prefixes[index]);
        inverse = inverse.mul(&z);
        points[index].x = points[index].x.mul(&z_inverse);
        points[index].y = points[index].y.mul(&z_inverse);
        points[index].z = Fe::ONE;
    }
}

#[derive(Clone)]
struct State {
    point: Point,
    alpha: U256,
    beta: U256,
}

struct Rng(u64);

impl Rng {
    fn new(seed: u64) -> Self {
        Self(seed)
    }

    fn next_u64(&mut self) -> u64 {
        let mut x = self.0;
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        self.0 = x;
        x
    }

    fn scalar(&mut self, modulus: &BigUint) -> (BigUint, U256) {
        let limbs = Uint([
            self.next_u64(),
            self.next_u64(),
            self.next_u64(),
            self.next_u64(),
        ]);
        let value = limbs.to_biguint() % modulus;
        let encoded = U256::from_biguint(&value);
        (value, encoded)
    }
}

struct Walk {
    curve: Curve,
    generator: Point,
    target: Point,
    order: U256,
    order_big: BigUint,
    table: Vec<(Point, U256, U256)>,
}

impl Walk {
    fn new(candidate: &Candidate, seed: u64) -> Self {
        let curve = Curve::new(&candidate.a, &candidate.b);
        let generator = Point::affine(&candidate.gx, &candidate.gy);
        assert!(curve.on_curve(&generator), "generator is not on candidate curve");
        let secret = BigUint::from(0x0c0d_ec0f_fee1_2345u64);
        let target = curve.scalar_mul(&generator, &secret);
        let order = U256::from_biguint(&candidate.n);
        let mut rng = Rng::new(seed);
        let mut table = Vec::with_capacity(TABLE_SIZE);
        while table.len() < TABLE_SIZE {
            let (alpha_big, alpha) = rng.scalar(&candidate.n);
            let (beta_big, beta) = rng.scalar(&candidate.n);
            let left = curve.scalar_mul(&generator, &alpha_big);
            let right = curve.scalar_mul(&target, &beta_big);
            let point = curve.normalize(&curve.add(&left, &right));
            if !bool::from(point.z.ct_is_zero()) {
                table.push((point, alpha, beta));
            }
        }
        Self {
            curve,
            generator,
            target,
            order,
            order_big: candidate.n.clone(),
            table,
        }
    }

    fn initial_states(&self, seed: u64) -> Vec<State> {
        let mut rng = Rng::new(seed);
        (0..BATCH_WIDTH)
            .map(|_| {
                let (alpha_big, alpha) = rng.scalar(&self.order_big);
                let (beta_big, beta) = rng.scalar(&self.order_big);
                let left = self.curve.scalar_mul(&self.generator, &alpha_big);
                let right = self.curve.scalar_mul(&self.target, &beta_big);
                State {
                    point: self.curve.normalize(&self.curve.add(&left, &right)),
                    alpha,
                    beta,
                }
            })
            .collect()
    }

    #[inline]
    fn advance_batch(&self, states: &mut [State]) {
        for state in states.iter_mut() {
            debug_assert_eq!(state.point.z, Fe::ONE);
            let index = state.point.x.to_canonical().0[0] as usize & (TABLE_SIZE - 1);
            let (increment, alpha, beta) = &self.table[index];
            state.point = self.curve.add(&state.point, increment);
            state.alpha = state.alpha.add_mod(alpha, &self.order);
            state.beta = state.beta.add_mod(beta, &self.order);
        }
        let mut points: Vec<Point> = states.iter().map(|state| state.point).collect();
        batch_normalize(&mut points);
        for (state, point) in states.iter_mut().zip(points) {
            state.point = point;
        }
    }

    fn relation_holds(&self, state: &State) -> bool {
        let left = self
            .curve
            .scalar_mul(&self.generator, &state.alpha.to_biguint());
        let right = self
            .curve
            .scalar_mul(&self.target, &state.beta.to_biguint());
        let expected = self.curve.normalize(&self.curve.add(&left, &right));
        expected.x == state.point.x && expected.y == state.point.y && expected.z == state.point.z
    }
}

fn run_once(candidate: &Candidate, seconds: f64, seed: u64) -> (f64, u64, bool, u64) {
    let walk = Walk::new(candidate, seed);
    let mut states = walk.initial_states(seed ^ 0xa5a5_a5a5_a5a5_a5a5);
    for _ in 0..8 {
        walk.advance_batch(&mut states);
    }
    let duration = Duration::from_secs_f64(seconds);
    let start = Instant::now();
    let mut iterations = 0u64;
    loop {
        for _ in 0..8 {
            walk.advance_batch(&mut states);
        }
        iterations += (8 * BATCH_WIDTH) as u64;
        if start.elapsed() >= duration {
            break;
        }
    }
    let elapsed = start.elapsed().as_secs_f64();
    let relation = walk.relation_holds(&states[0]);
    let checksum = states[0].point.x.to_canonical().0[0];
    black_box(checksum);
    (iterations as f64 / elapsed, iterations, relation, checksum)
}

fn parse_big(value: &Value, key: &str) -> BigUint {
    BigUint::parse_bytes(
        value[key].as_str().unwrap_or_else(|| panic!("missing {key}")) .as_bytes(),
        10,
    )
    .unwrap_or_else(|| panic!("invalid {key}"))
}

fn parse_candidate(value: &Value) -> Candidate {
    let curve = &value["curve"];
    Candidate {
        id: value["candidate_id"].as_str().expect("candidate_id").to_owned(),
        a: parse_big(curve, "a"),
        b: parse_big(curve, "b"),
        n: parse_big(curve, "n"),
        gx: parse_big(&curve["generator"], "x"),
        gy: parse_big(&curve["generator"], "y"),
        path_degrees: value["path"]
            .as_array()
            .expect("path")
            .iter()
            .map(|step| step["degree"].as_u64().expect("degree"))
            .collect(),
    }
}

fn mean(values: &[f64]) -> f64 {
    values.iter().sum::<f64>() / values.len() as f64
}

fn stdev(values: &[f64]) -> f64 {
    if values.len() < 2 {
        return 0.0;
    }
    let average = mean(values);
    (values
        .iter()
        .map(|value| (value - average).powi(2))
        .sum::<f64>()
        / (values.len() - 1) as f64)
        .sqrt()
}

fn t95(df: usize) -> f64 {
    if df == 0 {
        return 0.0;
    }
    let z = 1.959_963_984_540_054_f64;
    let v = df as f64;
    z + (z.powi(3) + z) / (4.0 * v)
        + (5.0 * z.powi(5) + 16.0 * z.powi(3) + 3.0 * z) / (96.0 * v.powi(2))
        + (3.0 * z.powi(7) + 19.0 * z.powi(5) + 17.0 * z.powi(3) - 15.0 * z)
            / (384.0 * v.powi(3))
}

fn mean_ci(values: &[f64]) -> (f64, f64, f64) {
    let average = mean(values);
    let half = t95(values.len() - 1) * stdev(values) / (values.len() as f64).sqrt();
    (average, average - half, average + half)
}

struct Options {
    candidate_files: Vec<PathBuf>,
    candidate_ids: Vec<String>,
    seconds: f64,
    trials: usize,
    warmup_seconds: f64,
    output: PathBuf,
}

fn options() -> Options {
    let mut out = Options {
        candidate_files: Vec::new(),
        candidate_ids: Vec::new(),
        seconds: 1.0,
        trials: 15,
        warmup_seconds: 0.2,
        output: PathBuf::from("native-benchmark.json"),
    };
    let args: Vec<String> = env::args().skip(1).collect();
    let mut index = 0;
    while index < args.len() {
        let value = args.get(index + 1).unwrap_or_else(|| panic!("missing value for {}", args[index]));
        match args[index].as_str() {
            "--candidates" => out.candidate_files.push(PathBuf::from(value)),
            "--candidate-id" => out.candidate_ids.push(value.clone()),
            "--seconds" => out.seconds = value.parse().expect("seconds"),
            "--trials" => out.trials = value.parse().expect("trials"),
            "--warmup-seconds" => out.warmup_seconds = value.parse().expect("warmup-seconds"),
            "--output" => out.output = PathBuf::from(value),
            unknown => panic!("unknown argument {unknown}"),
        }
        index += 2;
    }
    assert!(!out.candidate_files.is_empty(), "at least one --candidates is required");
    assert!(out.seconds > 0.0 && out.trials >= 2 && out.warmup_seconds >= 0.0);
    out
}

fn execution_order(count: usize, trial: usize) -> Vec<usize> {
    let block = trial / count;
    let offset = trial % count;
    let mut order: Vec<usize> = (0..count).collect();
    if block % 2 == 1 {
        order.reverse();
    }
    order.rotate_left(offset);
    order
}

fn main() {
    let opts = options();
    let mut by_id = HashMap::<String, Candidate>::new();
    let mut input_paths = Vec::new();
    for path in &opts.candidate_files {
        let payload: Value = serde_json::from_slice(&fs::read(path).expect("read candidates"))
            .expect("parse candidates");
        input_paths.push(path.display().to_string());
        for raw in payload["candidates"].as_array().expect("candidates") {
            let candidate = parse_candidate(raw);
            by_id.entry(candidate.id.clone()).or_insert(candidate);
        }
    }

    let mut selected_ids = vec!["p256-root".to_owned()];
    selected_ids.extend(opts.candidate_ids.clone());
    let candidates: Vec<Candidate> = selected_ids
        .iter()
        .map(|id| by_id.get(id).unwrap_or_else(|| panic!("candidate not found: {id}")).clone())
        .collect();

    for (index, candidate) in candidates.iter().enumerate() {
        if opts.warmup_seconds > 0.0 {
            let (_, _, relation, _) = run_once(
                candidate,
                opts.warmup_seconds,
                0x2026_1006_u64.wrapping_sub(104_729 + index as u64),
            );
            assert!(relation, "warmup relation check failed for {}", candidate.id);
        }
    }

    let mut rates = vec![Vec::<f64>::new(); candidates.len()];
    let mut iterations = vec![Vec::<u64>::new(); candidates.len()];
    let mut checksums = vec![Vec::<u64>::new(); candidates.len()];
    let mut relations = vec![Vec::<bool>::new(); candidates.len()];
    let mut orders = Vec::new();
    let wall_start = Instant::now();
    for trial in 0..opts.trials {
        let order = execution_order(candidates.len(), trial);
        orders.push(
            order
                .iter()
                .map(|&index| candidates[index].id.clone())
                .collect::<Vec<_>>(),
        );
        for index in order {
            let seed = 0x2026_1006_u64.wrapping_add(trial as u64 * 65_537);
            let (rate, count, relation, checksum) =
                run_once(&candidates[index], opts.seconds, seed);
            rates[index].push(rate);
            iterations[index].push(count);
            relations[index].push(relation);
            checksums[index].push(checksum);
            assert!(relation, "rho relation check failed for {}", candidates[index].id);
        }
    }

    let baseline = &rates[0];
    let results: Vec<Value> = candidates
        .iter()
        .enumerate()
        .map(|(index, candidate)| {
            let (rate_mean, rate_low, rate_high) = mean_ci(&rates[index]);
            let log2_ratios: Vec<f64> = rates[index]
                .iter()
                .zip(baseline)
                .map(|(candidate_rate, baseline_rate)| (candidate_rate / baseline_rate).log2())
                .collect();
            let (ratio_bits, low_bits, high_bits) = mean_ci(&log2_ratios);
            let degree_product: u64 = candidate.path_degrees.iter().product();
            json!({
                "candidate_id": candidate.id,
                "path_degrees": candidate.path_degrees,
                "path_degree_product": degree_product,
                "iterations_per_second": rate_mean,
                "rate_95_percent_ci": [rate_low, rate_high],
                "rate_trials": rates[index],
                "iterations_by_trial": iterations[index],
                "paired_log2_speedup_mean": ratio_bits,
                "paired_log2_speedup_95_percent_ci": [low_bits, high_bits],
                "paired_relative_iteration_speed": 2.0_f64.powf(ratio_bits),
                "paired_relative_iteration_speed_95_percent_ci": [
                    2.0_f64.powf(low_bits), 2.0_f64.powf(high_bits)
                ],
                "paired_speedup_significant_at_95_percent": low_bits > 0.0,
                "linear_relation_verified_every_trial": relations[index].iter().all(|value| *value),
                "checksum_low_64_by_trial": checksums[index],
            })
        })
        .collect();

    let output = json!({
        "schema_version": 1,
        "benchmark": "native matched P-256-field batch-normalized r-adding walk",
        "backend": {
            "field": "suite P256FieldElement fixed-limb Montgomery arithmetic",
            "point_addition": "Renes-Costello-Batina Algorithm 1 with dynamic a and 3b",
            "partition": "affine x mod 16 after 64-way batch normalization",
            "scalar_tracking": "U256 modular addition modulo the P-256 group order",
            "walks": BATCH_WIDTH,
            "table_size": TABLE_SIZE,
        },
        "inputs": input_paths,
        "baseline_candidate_id": "p256-root",
        "benchmark_design": {
            "seconds_per_trial": opts.seconds,
            "trials_per_candidate": opts.trials,
            "warmup_seconds_per_candidate": opts.warmup_seconds,
            "candidate_order": "rotating Latin-square positions; reversed on alternate full blocks",
            "execution_order_by_trial": orders,
            "comparison": "paired per-trial log2 iteration-rate ratio",
            "comparison_ci": "two-sided Student-t interval",
            "host_cpu_isolation": "unverified; wall-time results are exploratory",
        },
        "results": results,
        "elapsed_wall_seconds": wall_start.elapsed().as_secs_f64(),
    });
    if let Some(parent) = opts.output.parent() {
        fs::create_dir_all(parent).expect("create output directory");
    }
    fs::write(&opts.output, serde_json::to_vec_pretty(&output).unwrap()).expect("write output");
    println!("{}", opts.output.display());
}
