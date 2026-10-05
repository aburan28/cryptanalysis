#![recursion_limit = "256"]

//! Frozen ordinary-query PDP holdout for the N53 weight-three root index.
//!
//! The factor base is the frozen W3 normal-mask projected representative list,
//! expanded into signed Frobenius orbits in the declared subgroup. Its logarithms
//! are not supplied. The S3 index samples one target-seeded global Frobenius
//! orientation per state. Every frozen public query is searched to a verified
//! four-point witness or exhaustion; there is no rank-dependent stop and no
//! fixture scalar input to this executable.
//!
//! The one-worker index builder retains the same deterministic state and
//! duplicate tie-breaking order as the root-index IC experiment.
//!
//! Usage: <public_points.json> <representatives.json> <out.jsonl>

use crypto_lib::cryptanalysis::koblitz_fast_arith::{s3_x_roots, FastBinaryCurve, FastPoint};
use crypto_lib::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use crypto_lib::cryptanalysis::semaev_decomp::Gf2;
use num_bigint::BigUint;
use num_traits::ToPrimitive;
use serde_json::json;
use std::collections::HashMap;
use std::io::Write;
use std::thread;
use std::time::Instant;

/// F2-linear map on n <= 64 bits applied by byte tables.
struct Linear {
    tables: Vec<[u64; 256]>,
}

impl Linear {
    fn from_images(images: &[u64]) -> Self {
        let chunks = (images.len() + 7) / 8;
        let mut tables = vec![[0u64; 256]; chunks];
        for (chunk, table) in tables.iter_mut().enumerate() {
            for byte in 1usize..256 {
                let low = byte & (byte - 1);
                let bit = chunk * 8 + byte.trailing_zeros() as usize;
                let image = images.get(bit).copied().unwrap_or(0);
                table[byte] = table[low] ^ image;
            }
        }
        Self { tables }
    }

    #[inline(always)]
    fn apply(&self, v: u64) -> u64 {
        let mut acc = 0u64;
        for (chunk, table) in self.tables.iter().enumerate() {
            acc ^= table[((v >> (8 * chunk)) & 0xff) as usize];
        }
        acc
    }
}

struct NormalBasis {
    n: u32,
    mask: u64,
    to_normal: Linear,
    to_poly: Linear,
}

impl NormalBasis {
    fn new(gf: &Gf2) -> Self {
        let n = gf.n as usize;
        let mask = if n == 64 { u64::MAX } else { (1u64 << n) - 1 };
        for candidate in 2u64.. {
            let mut conjugates = Vec::with_capacity(n);
            let mut value = candidate & mask;
            for _ in 0..n {
                conjugates.push(value);
                value = gf.sqr(value);
            }
            let Some(inverse_columns) = invert_columns(&conjugates, n) else {
                continue;
            };
            let basis = Self {
                n: gf.n,
                mask,
                to_normal: Linear::from_images(&inverse_columns),
                to_poly: Linear::from_images(&conjugates),
            };
            return basis;
        }
        unreachable!()
    }

    #[inline(always)]
    fn rotate(&self, v: u64, k: u32) -> u64 {
        if k == 0 {
            return v;
        }
        ((v << k) | (v >> (self.n - k))) & self.mask
    }

    /// Smallest rotation of `v` and the shift that produces it.
    #[inline(always)]
    fn canonical(&self, v: u64) -> (u64, u32) {
        let mut best = v;
        let mut best_shift = 0;
        let mut current = v;
        for shift in 1..self.n {
            current = ((current << 1) | (current >> (self.n - 1))) & self.mask;
            if current < best {
                best = current;
                best_shift = shift;
            }
        }
        (best, best_shift)
    }
}

/// Columns `c_i` form matrix M (poly = M * normal). Returns the images of the
/// poly basis vectors under M^{-1}, or None when M is singular.
fn invert_columns(columns: &[u64], n: usize) -> Option<Vec<u64>> {
    // Row r of [M | I]: low n bits are M[r][i] over normal index i.
    let mut rows: Vec<u128> = (0..n)
        .map(|r| {
            let mut row = 0u128;
            for (i, &column) in columns.iter().enumerate() {
                if (column >> r) & 1 == 1 {
                    row |= 1u128 << i;
                }
            }
            row | (1u128 << (64 + r))
        })
        .collect();
    for pivot in 0..n {
        let found = (pivot..n).find(|&r| (rows[r] >> pivot) & 1 == 1)?;
        rows.swap(pivot, found);
        for r in 0..n {
            if r != pivot && (rows[r] >> pivot) & 1 == 1 {
                rows[r] ^= rows[pivot];
            }
        }
    }
    // Row i now reads x_i = sum_r Minv[i][r] y_r in its high half.
    let mut images = vec![0u64; n];
    for (i, row) in rows.iter().enumerate() {
        let high = (row >> 64) as u64;
        for (r, image) in images.iter_mut().enumerate() {
            if (high >> r) & 1 == 1 {
                *image |= 1u64 << i;
            }
        }
    }
    Some(images)
}

/// Table-driven S3 root solver: S3(u, v, t) = 0 as a quadratic in v.
struct S3Solver {
    square: Linear,
    half_trace: Linear,
    trace_mask: u64,
    b: u64,
}

impl S3Solver {
    fn new(gf: &Gf2, b: u64) -> Self {
        let n = gf.n as usize;
        assert!(n % 2 == 1, "half-trace solver needs odd n");
        let unit: Vec<u64> = (0..n).map(|bit| 1u64 << bit).collect();
        let half_trace_images: Vec<u64> = unit
            .iter()
            .map(|&e| {
                let mut acc = e;
                let mut power = e;
                for _ in 0..(n - 1) / 2 {
                    power = gf.sqr(gf.sqr(power));
                    acc ^= power;
                }
                acc
            })
            .collect();
        let mut trace_mask = 0u64;
        for (bit, &e) in unit.iter().enumerate() {
            let mut acc = e;
            let mut power = e;
            for _ in 1..n {
                power = gf.sqr(power);
                acc ^= power;
            }
            if acc & 1 == 1 {
                trace_mask |= 1u64 << bit;
            }
        }
        Self {
            square: Linear::from_images(&unit.iter().map(|&e| gf.sqr(e)).collect::<Vec<_>>()),
            half_trace: Linear::from_images(&half_trace_images),
            trace_mask,
            b,
        }
    }

    /// Same roots, in the same order, as `s3_x_roots` on the generic branch.
    #[inline(always)]
    fn roots(&self, gf: &Gf2, basis: &NormalBasis, left: u64, right: u64) -> Option<[u64; 2]> {
        let s = left ^ right;
        let a = self.square.apply(s);
        let p = gf.mul(left, right);
        let ps = self.square.apply(p);
        if a == 0 || ps == 0 {
            return s3_x_roots(gf, self.b, left, right);
        }
        let inv_combined = invert(gf, basis, gf.mul(a, ps));
        let q = gf.mul(p, gf.mul(ps, inv_combined));
        let c = ps ^ self.b;
        let d = gf.mul(gf.mul(c, a), gf.mul(a, inv_combined));
        if (d & self.trace_mask).count_ones() & 1 == 1 {
            return None;
        }
        let first = gf.mul(q, self.half_trace.apply(d));
        Some([first, first ^ q])
    }
}

/// Itoh-Tsujii inversion with the `a^(2^k)` steps done as normal-basis rotations.
#[inline(always)]
fn invert(gf: &Gf2, basis: &NormalBasis, a: u64) -> u64 {
    let e = gf.n - 1;
    let mut c = a;
    let mut k = 1u32;
    let bits = 32 - e.leading_zeros();
    for i in (0..bits - 1).rev() {
        let raised = basis
            .to_poly
            .apply(basis.rotate(basis.to_normal.apply(c), k));
        c = gf.mul(c, raised);
        k *= 2;
        if (e >> i) & 1 == 1 {
            c = gf.mul(gf.sqr(c), a);
            k += 1;
        }
    }
    gf.sqr(c)
}

/// Open-addressing u64 -> u64 table; keys are < 2^63 so u64::MAX marks empty.
/// Key and value share a slot so a probe touches one cache line.
struct RootTable {
    slots: Vec<(u64, u64)>,
    shift: u32,
    len: usize,
}

impl RootTable {
    fn with_capacity(entries: usize) -> Self {
        let slots = (entries * 2).next_power_of_two().max(16);
        Self {
            slots: vec![(u64::MAX, 0); slots],
            shift: 64 - slots.trailing_zeros(),
            len: 0,
        }
    }

    #[inline(always)]
    fn slot(&self, key: u64) -> usize {
        (key.wrapping_mul(0x9E37_79B9_7F4A_7C15) >> self.shift) as usize
    }

    fn insert_if_absent(&mut self, key: u64, value: u64) {
        let mask = self.slots.len() - 1;
        let mut slot = self.slot(key);
        loop {
            if self.slots[slot].0 == u64::MAX {
                self.slots[slot] = (key, value);
                self.len += 1;
                return;
            }
            if self.slots[slot].0 == key {
                return;
            }
            slot = (slot + 1) & mask;
        }
    }

    #[inline(always)]
    fn get(&self, key: u64) -> Option<u64> {
        let mask = self.slots.len() - 1;
        let mut slot = self.slot(key);
        loop {
            let (stored, value) = self.slots[slot];
            if stored == key {
                return Some(value);
            }
            if stored == u64::MAX {
                return None;
            }
            slot = (slot + 1) & mask;
        }
    }
}

struct State {
    left: u16,
    right: u16,
    relative: u16,
    normal_roots: [u64; 2],
}

struct Index {
    states: Vec<State>,
    table: RootTable,
    shifted: Vec<Vec<u64>>,
}

fn pack(left: u16, right: u16, relative: u16, shift: u32) -> u64 {
    (left as u64) | ((right as u64) << 16) | ((relative as u64) << 32) | ((shift as u64) << 48)
}

fn unpack(value: u64) -> (usize, usize, usize, u32) {
    (
        (value & 0xffff) as usize,
        ((value >> 16) & 0xffff) as usize,
        ((value >> 32) & 0xffff) as usize,
        ((value >> 48) & 0xffff) as u32,
    )
}

fn build_index(
    gf: &Gf2,
    basis: &NormalBasis,
    solver: &S3Solver,
    reps: &[u64],
    workers: usize,
) -> (Index, f64, f64) {
    let n = gf.n as usize;
    let shifted: Vec<Vec<u64>> = reps
        .iter()
        .map(|&code| {
            let mut row = Vec::with_capacity(n);
            let mut value = code;
            for _ in 0..n {
                row.push(value);
                value = gf.sqr(value);
            }
            row
        })
        .collect();
    let state_generation_started = Instant::now();
    let worker_count = workers.max(1).min(reps.len().max(1));
    let lefts_per_worker = reps.len().div_ceil(worker_count);
    let mut state_chunks = Vec::with_capacity(worker_count);
    thread::scope(|scope| {
        let gf = gf;
        let basis = basis;
        let solver = solver;
        let reps = reps;
        let shifted = &shifted;
        let handles: Vec<_> = (0..worker_count)
            .map(|worker| {
                let first_left = worker * lefts_per_worker;
                let end_left = (first_left + lefts_per_worker).min(reps.len());
                scope.spawn(move || {
                    let mut states = Vec::new();
                    for left in first_left..end_left {
                        for right in 0..reps.len() {
                            for relative in 0..n {
                                if let Some(roots) = solver.roots(
                                    gf,
                                    basis,
                                    shifted[left][0],
                                    shifted[right][relative],
                                ) {
                                    states.push(State {
                                        left: left as u16,
                                        right: right as u16,
                                        relative: relative as u16,
                                        normal_roots: [
                                            basis.to_normal.apply(roots[0]),
                                            basis.to_normal.apply(roots[1]),
                                        ],
                                    });
                                }
                            }
                        }
                    }
                    states
                })
            })
            .collect();
        for handle in handles {
            state_chunks.push(handle.join().expect("index worker panicked"));
        }
    });
    let state_generation_ms = state_generation_started.elapsed().as_secs_f64() * 1000.0;

    // Worker chunks cover consecutive `left` ranges. Appending in spawn order
    // restores the exact serial enumeration order and therefore preserves the
    // first-witness choice for duplicate canonical roots.
    let state_count = state_chunks.iter().map(Vec::len).sum();
    let mut states = Vec::with_capacity(state_count);
    for mut chunk in state_chunks {
        states.append(&mut chunk);
    }

    let root_table_started = Instant::now();
    let mut table = RootTable::with_capacity(states.len() * 2);
    for state in &states {
        for &root in &state.normal_roots {
            let (canonical, shift) = basis.canonical(root);
            table.insert_if_absent(
                canonical,
                pack(state.left, state.right, state.relative, shift),
            );
        }
    }
    let root_table_build_ms = root_table_started.elapsed().as_secs_f64() * 1000.0;
    (
        Index {
            states,
            table,
            shifted,
        },
        state_generation_ms,
        root_table_build_ms,
    )
}

struct Relation {
    point_indices: [usize; 4],
    x_codes: [u64; 4],
    probes: u64,
    relation_check_ms: f64,
}

struct Base {
    points: Vec<FastPoint>,
    labels: Vec<(usize, u64)>,
    by_x: HashMap<u64, Vec<usize>>,
    columns: usize,
}

fn lift(
    fast: &FastBinaryCurve,
    base: &Base,
    codes: &[u64; 4],
    target: FastPoint,
) -> Option<[usize; 4]> {
    let choices: Vec<&Vec<usize>> = codes
        .iter()
        .map(|code| base.by_x.get(code))
        .collect::<Option<_>>()?;
    for &a in choices[0] {
        for &b in choices[1] {
            let ab = fast.add(base.points[a], base.points[b]);
            for &c in choices[2] {
                let abc = fast.add(ab, base.points[c]);
                for &d in choices[3] {
                    if fast.add(abc, base.points[d]) == target {
                        return Some([a, b, c, d]);
                    }
                }
            }
        }
    }
    None
}

fn extract(
    gf: &Gf2,
    fast: &FastBinaryCurve,
    basis: &NormalBasis,
    solver: &S3Solver,
    index: &Index,
    base: &Base,
    target: FastPoint,
    start: usize,
) -> (Option<Relation>, u64, u64) {
    let Some((target_x, target_y)) = target else {
        return (None, 0, 0);
    };
    let n = gf.n;
    let mut probes = 0u64;
    let mut state_probes = 0u64;
    let mut target_s3_calls = 0u64;
    let mut relation_check_ms = 0.0;
    // Callers provide a rotating, target-dependent origin so rank-stage rows
    // do not concentrate on the same early columns.
    let start = start % index.states.len().max(1);
    let target_seed = target_x ^ target_y.rotate_left(29) ^ 0xD6E8_FEB8_6659_FD93;
    for (offset, state) in index.states[start..]
        .iter()
        .chain(&index.states[..start])
        .enumerate()
    {
        state_probes += 1;
        // Frobenius closure makes each quotient state represent n global
        // orientations. Sample one orientation per state; ordinary relations
        // are therefore sampled with probability about 1/n.
        let mut orientation_seed = target_seed
            ^ (offset as u64).wrapping_mul(0x9E37_79B9_7F4A_7C15)
            ^ ((state.left as u64) << 32)
            ^ ((state.right as u64) << 16)
            ^ state.relative as u64;
        let shift = (splitmix64(&mut orientation_seed) % n as u64) as usize;
        let left_x = index.shifted[state.left as usize][shift];
        let right_x =
            index.shifted[state.right as usize][(shift + state.relative as usize) % n as usize];
        for &normal_root in &state.normal_roots {
            let absolute = basis.to_poly.apply(basis.rotate(normal_root, shift as u32));
            target_s3_calls += 1;
            let Some(partners) = solver.roots(gf, basis, absolute, target_x) else {
                continue;
            };
            for partner in partners {
                probes += 1;
                let (canonical, partner_shift) = basis.canonical(basis.to_normal.apply(partner));
                let Some(value) = index.table.get(canonical) else {
                    continue;
                };
                let (left2, right2, relative2, stored_shift) = unpack(value);
                let left_shift2 = ((stored_shift + n - partner_shift) % n) as usize;
                let right_shift2 = (left_shift2 + relative2) % n as usize;
                let codes = [
                    left_x,
                    right_x,
                    index.shifted[left2][left_shift2],
                    index.shifted[right2][right_shift2],
                ];
                let relation_check_started = Instant::now();
                let point_indices = lift(fast, base, &codes, target);
                relation_check_ms += relation_check_started.elapsed().as_secs_f64() * 1000.0;
                if let Some(point_indices) = point_indices {
                    return (
                        Some(Relation {
                            point_indices,
                            x_codes: codes,
                            probes,
                            relation_check_ms,
                        }),
                        state_probes,
                        target_s3_calls,
                    );
                }
            }
        }
    }
    (None, state_probes, target_s3_calls)
}

/// Frobenius-closed signed-orbit base from the frozen W3 representative list.
///
/// The supplied representatives were independently checked against the exact
/// weight-three rational-x/cofactor-projected set. Point logs are unknown; the
/// label of member `phi^k(+-R_j)` is `(j, +-lambda^k)`.
fn construct_base(
    fast: &FastBinaryCurve,
    curve: &KoblitzCurve,
    b: u64,
    columns: usize,
    r: u64,
    representatives_path: &str,
) -> (
    Vec<FastPoint>,
    Vec<(usize, u64)>,
    Vec<Option<[u64; 2]>>,
    u64,
) {
    let gf = &fast.gf;
    let n = fast.n as usize;
    let lambda = curve.lambda.to_u64().unwrap();
    let input: serde_json::Value = serde_json::from_slice(
        &std::fs::read(representatives_path).expect("read W3 representative list"),
    )
    .expect("parse W3 representative list");
    assert_eq!(input["schema_version"].as_u64(), Some(1));
    assert_eq!(input["subgroup_order"].as_u64(), Some(r));
    assert_eq!(input["cofactor"].as_u64(), curve.cofactor.to_u64());
    assert_eq!(input["lambda_mod_r"].as_u64(), Some(lambda));
    assert_eq!(input["normal_element"].as_u64(), Some(3));
    let supplied = input["representatives"]
        .as_array()
        .expect("W3 representatives array");
    assert_eq!(supplied.len(), columns);
    let mut seen = std::collections::HashSet::new();
    let mut points = Vec::with_capacity(columns * 2 * n);
    let mut labels = Vec::with_capacity(columns * 2 * n);
    let mut reps = Vec::with_capacity(columns);
    for value in supplied {
        let pair = value.as_array().expect("representative must be [x,y]");
        assert_eq!(pair.len(), 2);
        let px = pair[0].as_u64().expect("x must be a nonnegative word");
        let py = pair[1].as_u64().expect("y must be a nonnegative word");
        let lhs = gf.sqr(py) ^ gf.mul(px, py);
        let rhs = gf.mul(gf.sqr(px), px) ^ gf.mul(gf.from_element(&curve.curve.a), gf.sqr(px)) ^ b;
        assert_eq!(lhs, rhs, "W3 representative must lie on the curve");
        assert_eq!(fast.scalar_mul(Some((px, py)), &BigUint::from(r)), None);
        let mut key = px;
        let mut x = px;
        for _ in 1..n {
            x = gf.sqr(x);
            key = key.min(x);
        }
        assert!(seen.insert(key), "duplicate signed Frobenius orbit");
        let column = reps.len();
        reps.push(Some([px, py]));
        let (mut cx, mut cy) = (px, py);
        let mut coefficient = 1u64;
        for _ in 0..n {
            points.push(Some((cx, cy)));
            labels.push((column, coefficient));
            points.push(Some((cx, cx ^ cy)));
            labels.push((column, (r - coefficient) % r));
            cx = gf.sqr(cx);
            cy = gf.sqr(cy);
            coefficient = mulmod(coefficient, lambda, r);
        }
    }
    let rep = reps[0].map(|[x, y]| (x, y));
    assert_eq!(
        fast.scalar_mul(rep, &BigUint::from(lambda)),
        rep.map(|(x, y)| (gf.sqr(x), gf.sqr(y))),
        "Frobenius must act as lambda on the subgroup"
    );
    (points, labels, reps, 0)
}

fn mulmod(a: u64, b: u64, r: u64) -> u64 {
    ((a as u128 * b as u128) % r as u128) as u64
}

fn powmod(mut a: u64, mut e: u64, r: u64) -> u64 {
    let mut acc = 1u64;
    while e > 0 {
        if e & 1 == 1 {
            acc = mulmod(acc, a, r);
        }
        a = mulmod(a, a, r);
        e >>= 1;
    }
    acc
}

/// Incremental row echelon mod prime r over K unknowns plus a right-hand side.
struct Echelon {
    r: u64,
    columns: usize,
    pivots: Vec<Option<Vec<u64>>>,
    rank: usize,
}

impl Echelon {
    fn insert(&mut self, mut row: Vec<u64>) -> bool {
        for column in 0..self.columns {
            if row[column] == 0 {
                continue;
            }
            if let Some(pivot) = &self.pivots[column] {
                let factor = row[column];
                for (value, &p) in row.iter_mut().zip(pivot.iter()).skip(column) {
                    *value = (*value + self.r - mulmod(factor, p, self.r)) % self.r;
                }
            } else {
                let inverse = powmod(row[column], self.r - 2, self.r);
                for value in row.iter_mut().skip(column) {
                    *value = mulmod(*value, inverse, self.r);
                }
                self.pivots[column] = Some(row);
                self.rank += 1;
                return true;
            }
        }
        false
    }

    /// Recover the right-hand-side combination for a coefficient vector that
    /// lies in the span of the currently inserted relation rows.
    fn span_value(&self, coefficients: &[u64]) -> Option<u64> {
        if coefficients.len() != self.columns {
            return None;
        }
        let mut remainder = coefficients.to_vec();
        let mut value = 0u64;
        for column in 0..self.columns {
            let factor = remainder[column];
            if factor == 0 {
                continue;
            }
            let pivot = self.pivots[column].as_ref()?;
            for index in column..self.columns {
                remainder[index] =
                    (remainder[index] + self.r - mulmod(factor, pivot[index], self.r)) % self.r;
            }
            value = (value + mulmod(factor, pivot[self.columns], self.r)) % self.r;
        }
        if remainder.iter().all(|&entry| entry == 0) {
            Some(value)
        } else {
            None
        }
    }

    fn solve(&self) -> Vec<u64> {
        let mut solution = vec![0u64; self.columns];
        for column in (0..self.columns).rev() {
            let pivot = self.pivots[column].as_ref().expect("full rank");
            let mut value = pivot[self.columns];
            for other in column + 1..self.columns {
                value = (value + self.r - mulmod(pivot[other], solution[other], self.r)) % self.r;
            }
            solution[column] = value;
        }
        solution
    }
}

#[cfg(test)]
mod target_span_tests {
    use super::Echelon;

    #[test]
    fn recovers_rhs_for_a_spanned_vector_and_rejects_an_unspanned_one() {
        let mut echelon = Echelon {
            r: 101,
            columns: 3,
            pivots: vec![None; 3],
            rank: 0,
        };
        assert!(echelon.insert(vec![1, 2, 0, 5]));
        assert!(echelon.insert(vec![0, 1, 4, 7]));
        assert_eq!(echelon.span_value(&[1, 4, 8]), Some(19));
        assert_eq!(echelon.span_value(&[0, 0, 1]), None);
    }
}

fn relation_row(base: &Base, relation: &Relation, rhs: u64, r: u64) -> Vec<u64> {
    let mut row = vec![0u64; base.columns + 1];
    for &index in &relation.point_indices {
        let (column, coefficient) = base.labels[index];
        row[column] = (row[column] + coefficient) % r;
    }
    row[base.columns] = rhs % r;
    row
}

fn peak_rss_bytes() -> Option<u64> {
    let output = std::process::Command::new("ps")
        .args(["-o", "rss=", "-p", &std::process::id().to_string()])
        .output()
        .ok()?;
    let kib: u64 = String::from_utf8_lossy(&output.stdout)
        .trim()
        .parse()
        .ok()?;
    Some(kib * 1024)
}

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9E37_79B9_7F4A_7C15);
    let mut z = *state;
    z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    z ^ (z >> 31)
}

fn point_hash(point: FastPoint) -> u64 {
    let (x, y) = point.expect("point must be affine");
    let mut hash = x ^ y.rotate_left(29) ^ 0x9E37_79B9_7F4A_7C15;
    hash = (hash ^ (hash >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    hash = (hash ^ (hash >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    hash ^ (hash >> 31)
}

fn main() {
    let arguments: Vec<String> = std::env::args().collect();
    assert_eq!(
        arguments.len(),
        4,
        "usage: <public_points.json> <representatives.json> <out.jsonl>"
    );
    let public_points: Vec<[u64; 2]> =
        serde_json::from_slice(&std::fs::read(&arguments[1]).expect("read public query panel"))
            .expect("public query panel must be an array of [x,y] points");
    assert!(!public_points.is_empty() && public_points.len() <= 1024);

    let setup_started = Instant::now();
    let curve = KoblitzCurve::new(0, 53).expect("frozen N53 Koblitz curve");
    let r = curve.subgroup_order.to_u64().unwrap();
    let fast = FastBinaryCurve::new(&curve.curve.irreducible, 0).unwrap();
    let gf = Gf2::new(&curve.curve.irreducible);
    let b = gf.from_element(&curve.curve.b);
    let (points, labels, representatives, _) =
        construct_base(&fast, &curve, b, 221, r, &arguments[2]);
    let mut by_x: HashMap<u64, Vec<usize>> = HashMap::new();
    for (index, point) in points.iter().enumerate() {
        if let Some((x, _)) = point {
            by_x.entry(*x).or_default().push(index);
        }
    }
    let base = Base {
        points,
        labels,
        by_x,
        columns: representatives.len(),
    };
    let basis = NormalBasis::new(&gf);
    let solver = S3Solver::new(&gf, b);
    let rep_x: Vec<u64> = representatives
        .iter()
        .map(|point| point.expect("representative point")[0])
        .collect();
    let (index, state_generation_ms, root_table_build_ms) =
        build_index(&gf, &basis, &solver, &rep_x, 1);
    let setup_ms = setup_started.elapsed().as_secs_f64() * 1000.0;

    let mut out = std::fs::File::create(&arguments[3]).expect("create panel result");
    writeln!(
        out,
        "{}",
        json!({
            "kind":"n53_w3_root_ordinary_query_panel_header",
            "schema_version":1,
            "n":53,
            "subgroup_order":r,
            "query_count":public_points.len(),
            "factor_base_points":base.points.len(),
            "orbit_columns":base.columns,
            "regular_index_states":index.states.len(),
            "root_table_entries":index.table.len,
            "setup_ms_excluded_from_query_intervals":setup_ms,
            "index_state_generation_ms":state_generation_ms,
            "root_table_build_ms":root_table_build_ms,
            "query_policy":"one target-seeded orientation per index state; full state scan on miss; no rank stop"
        })
    )
    .unwrap();
    out.flush().unwrap();

    let mut seen = std::collections::HashSet::new();
    for (query_index, pair) in public_points.iter().enumerate() {
        let (x, y) = (pair[0], pair[1]);
        let query_started = Instant::now();
        let duplicate = !seen.insert((x, y));
        let in_field = x < (1u64 << 53) && y < (1u64 << 53);
        let on_curve = in_field && ((gf.sqr(y) ^ gf.mul(x, y)) == (gf.mul(gf.sqr(x), x) ^ b));
        let target: FastPoint = Some((x, y));
        let in_subgroup = on_curve && fast.scalar_mul(target, &BigUint::from(r)).is_none();
        let validation_ms = query_started.elapsed().as_secs_f64() * 1000.0;
        if duplicate || !in_subgroup {
            writeln!(
                out,
                "{}",
                json!({
                    "kind":"n53_w3_root_ordinary_query",
                    "query_index":query_index,
                    "target_point":pair,
                    "status":if duplicate { "DUPLICATE_POINT" } else { "INVALID_INPUT" },
                    "group_verified":false,
                    "point_indices":null,
                    "x_codes":null,
                    "state_probes":0,
                    "target_s3_calls":0,
                    "partner_probes":0,
                    "validation_ms":validation_ms,
                    "extraction_ms":0.0,
                    "query_wall_ms":query_started.elapsed().as_secs_f64()*1000.0
                })
            )
            .unwrap();
            out.flush().unwrap();
            continue;
        }

        let extract_started = Instant::now();
        let (relation, state_probes, target_s3_calls) = extract(
            &gf,
            &fast,
            &basis,
            &solver,
            &index,
            &base,
            target,
            point_hash(target) as usize,
        );
        let extraction_ms = extract_started.elapsed().as_secs_f64() * 1000.0;
        let found = relation.is_some();
        let (point_indices, x_codes, partner_probes, relation_check_ms) = relation
            .map(|value| {
                (
                    Some(value.point_indices),
                    Some(value.x_codes),
                    value.probes,
                    value.relation_check_ms,
                )
            })
            .unwrap_or((None, None, 0, 0.0));
        writeln!(
            out,
            "{}",
            json!({
                "kind":"n53_w3_root_ordinary_query",
                "query_index":query_index,
                "target_point":pair,
                "status":if found { "VERIFIED_DECOMPOSITION" } else { "NO_DECOMPOSITION_FOUND" },
                "group_verified":found,
                "point_indices":point_indices,
                "x_codes":x_codes,
                "state_probes":state_probes,
                "target_s3_calls":target_s3_calls,
                "partner_probes":partner_probes,
                "relation_check_ms":relation_check_ms,
                "validation_ms":validation_ms,
                "extraction_ms":extraction_ms,
                "query_wall_ms":query_started.elapsed().as_secs_f64()*1000.0
            })
        )
        .unwrap();
        out.flush().unwrap();
    }
}
