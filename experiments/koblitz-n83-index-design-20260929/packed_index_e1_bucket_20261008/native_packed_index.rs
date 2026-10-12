//! Bounded four-leaf S3 root-index search on the frozen Q1301/Q1325 inputs.
//!
//! This is a point-decomposition stage, not a complete index-calculus solve.
//! Index construction is target independent. Ordinary queries sample one
//! global Frobenius orientation per indexed pair state. The manifest can
//! request full orientations and Montgomery-batched S3 roots for controls
//! and matched implementation variants. Every arithmetic call is charged.

#![recursion_limit = "256"]

use crypto_lib::binary_ecc::IrreduciblePoly;
use crypto_lib::cryptanalysis::semaev_decomp::{Gf2, Gf2_128};
use serde_json::{json, Value};
use std::env;
use std::fs;
use std::time::Instant;

trait Field {
    fn degree(&self) -> u32;
    fn mul(&self, left: u128, right: u128) -> u128;
    fn sqr(&self, value: u128) -> u128;
    fn inv(&self, value: u128) -> u128;
}

impl Field for Gf2 {
    fn degree(&self) -> u32 { self.n }
    #[inline(always)]
    fn mul(&self, left: u128, right: u128) -> u128 {
        Gf2::mul(self, left as u64, right as u64) as u128
    }
    #[inline(always)]
    fn sqr(&self, value: u128) -> u128 {
        Gf2::sqr(self, value as u64) as u128
    }
    #[inline(always)]
    fn inv(&self, value: u128) -> u128 {
        Gf2::inv(self, value as u64) as u128
    }
}

impl Field for Gf2_128 {
    fn degree(&self) -> u32 { self.n }
    #[inline(always)]
    fn mul(&self, left: u128, right: u128) -> u128 {
        Gf2_128::mul(self, left, right)
    }
    #[inline(always)]
    fn sqr(&self, value: u128) -> u128 {
        Gf2_128::sqr(self, value)
    }
    #[inline(always)]
    fn inv(&self, value: u128) -> u128 {
        Gf2_128::inv(self, value)
    }
}

#[derive(Clone, Copy, Default)]
struct Ops {
    mul: u64,
    sqr: u64,
    inv: u64,
    s3_calls: u64,
    basis_conversions: u64,
    canonical_rotations: u64,
    point_lifts: u64,
    point_adds: u64,
    relation_candidates: u64,
}

impl Ops {
    fn minus(self, prior: Self) -> Self {
        Self {
            mul: self.mul - prior.mul,
            sqr: self.sqr - prior.sqr,
            inv: self.inv - prior.inv,
            s3_calls: self.s3_calls - prior.s3_calls,
            basis_conversions: self.basis_conversions - prior.basis_conversions,
            canonical_rotations: self.canonical_rotations - prior.canonical_rotations,
            point_lifts: self.point_lifts - prior.point_lifts,
            point_adds: self.point_adds - prior.point_adds,
            relation_candidates: self.relation_candidates - prior.relation_candidates,
        }
    }
    fn value(self) -> Value {
        json!({
            "field_mul_calls": self.mul,
            "field_sqr_calls": self.sqr,
            "field_inv_calls": self.inv,
            "s3_root_calls": self.s3_calls,
            "basis_conversions": self.basis_conversions,
            "canonical_rotation_steps": self.canonical_rotations,
            "point_lifts": self.point_lifts,
            "point_add_calls": self.point_adds,
            "relation_candidates_checked": self.relation_candidates,
        })
    }
}

struct Counted<F: Field> {
    field: F,
    ops: Ops,
}

impl<F: Field> Counted<F> {
    #[inline(always)]
    fn mul(&mut self, left: u128, right: u128) -> u128 {
        self.ops.mul += 1;
        self.field.mul(left, right)
    }
    #[inline(always)]
    fn sqr(&mut self, value: u128) -> u128 {
        self.ops.sqr += 1;
        self.field.sqr(value)
    }
    #[inline(always)]
    fn inv(&mut self, value: u128) -> u128 {
        self.ops.inv += 1;
        self.field.inv(value)
    }
}

/// F2-linear map; the byte tables keep per-call conversion work bounded.
struct Linear {
    tables: Vec<[u128; 256]>,
}

impl Linear {
    fn from_images(images: &[u128]) -> Self {
        let chunks = (images.len() + 7) / 8;
        let mut tables = vec![[0u128; 256]; chunks];
        for (chunk, table) in tables.iter_mut().enumerate() {
            for byte in 1usize..256 {
                let low = byte & (byte - 1);
                let bit = chunk * 8 + byte.trailing_zeros() as usize;
                table[byte] = table[low] ^ images.get(bit).copied().unwrap_or(0);
            }
        }
        Self { tables }
    }
    #[inline(always)]
    fn apply(&self, value: u128) -> u128 {
        let mut result = 0;
        for (chunk, table) in self.tables.iter().enumerate() {
            result ^= table[((value >> (8 * chunk)) & 255) as usize];
        }
        result
    }
}

struct Cycle {
    n: u32,
    mask: u128,
    to_cycle: Linear,
    to_poly: Linear,
}

impl Cycle {
    fn from_bridge(bridge: &Value, n: u32) -> Self {
        let forward: Vec<u128> = bridge["onb_to_poly_basis_images"]
            .as_array().unwrap().iter().map(exact_integer).collect();
        let inverse: Vec<u128> = bridge["poly_to_onb_basis_images"]
            .as_array().unwrap().iter().map(exact_integer).collect();
        let positions: Vec<usize> = bridge["onb_gamma_frobenius_coordinate_cycle"]
            .as_array().unwrap().iter().map(|v| v.as_u64().unwrap() as usize).collect();
        assert_eq!(forward.len(), n as usize);
        assert_eq!(inverse.len(), n as usize);
        assert_eq!(positions.len(), n as usize);
        let to_cycle_images: Vec<u128> = inverse.iter().map(|&image| {
            positions.iter().enumerate().fold(0u128, |acc, (i, &position)| {
                acc | (((image >> position) & 1) << i)
            })
        }).collect();
        let to_poly_images: Vec<u128> = positions.iter().map(|&p| forward[p]).collect();
        let result = Self {
            n,
            mask: (1u128 << n) - 1,
            to_cycle: Linear::from_images(&to_cycle_images),
            to_poly: Linear::from_images(&to_poly_images),
        };
        for i in 0..n {
            assert_eq!(result.to_poly.apply(result.to_cycle.apply(1u128 << i)), 1u128 << i);
            assert_eq!(result.to_cycle.apply(result.to_poly.apply(1u128 << i)), 1u128 << i);
        }
        result
    }
    #[inline(always)]
    fn rotate(&self, value: u128, steps: u32) -> u128 {
        if steps == 0 { value } else {
            ((value << steps) | (value >> (self.n - steps))) & self.mask
        }
    }
    fn canonical(&self, value: u128, ops: &mut Ops) -> (u128, u32) {
        let mut best = value;
        let mut best_shift = 0;
        let mut current = value;
        for shift in 1..self.n {
            current = self.rotate(current, 1);
            ops.canonical_rotations += 1;
            if current < best {
                best = current;
                best_shift = shift;
            }
        }
        (best, best_shift)
    }
}

/// Quadratic S3 root evaluator with precomputed F2-linear half-trace.
struct S3 {
    square: Linear,
    half_trace: Linear,
    trace_mask: u128,
}

enum PreparedS3 {
    NoRoot,
    EqualInputs { ps: u128 },
    ZeroProduct,
    Regular { a: u128, p: u128, ps: u128 },
}

impl S3 {
    fn new<F: Field>(ctx: &mut Counted<F>, n: u32) -> Self {
        assert!(n % 2 == 1);
        let mut squares = Vec::with_capacity(n as usize);
        let mut traces = Vec::with_capacity(n as usize);
        let mut trace_mask = 0u128;
        for bit in 0..n {
            let e = 1u128 << bit;
            squares.push(ctx.sqr(e));
            let mut half = e;
            let mut power = e;
            for _ in 0..(n - 1) / 2 {
                let squared = ctx.sqr(power);
                power = ctx.sqr(squared);
                half ^= power;
            }
            traces.push(half);
            let mut tr = e;
            let mut p = e;
            for _ in 1..n {
                p = ctx.sqr(p);
                tr ^= p;
            }
            assert!(tr == 0 || tr == 1);
            if tr == 1 { trace_mask |= e; }
        }
        Self { square: Linear::from_images(&squares),
               half_trace: Linear::from_images(&traces), trace_mask }
    }
    #[inline(always)]
    fn roots<F: Field>(&self, ctx: &mut Counted<F>, left: u128,
                       right: u128) -> Option<[u128; 2]> {
        ctx.ops.s3_calls += 1;
        let a = self.square.apply(left ^ right);
        let p = ctx.mul(left, right);
        let ps = self.square.apply(p);
        if a == 0 {
            if left == 0 { return None; }
            let inverse = ctx.inv(p);
            let root = ctx.mul(ps ^ 1, inverse);
            return Some([root, root]);
        }
        if ps == 0 {
            let inverse = ctx.inv(a);
            let root = ctx.mul(1, inverse);
            let mut value = root;
            for _ in 0..(ctx.field_degree() - 1) { value = ctx.sqr(value); }
            return Some([value, value]);
        }
        let combined = ctx.mul(a, ps);
        let combined_inv = ctx.inv(combined);
        let ps_over_combined = ctx.mul(ps, combined_inv);
        let q = ctx.mul(p, ps_over_combined);
        let c = ps ^ 1;
        let ca = ctx.mul(c, a);
        let a_over_combined = ctx.mul(a, combined_inv);
        let d = ctx.mul(ca, a_over_combined);
        if (d & self.trace_mask).count_ones() & 1 == 1 { return None; }
        let first = ctx.mul(q, self.half_trace.apply(d));
        Some([first, first ^ q])
    }

    /// Evaluate independent S3 quadratics with one inversion per batch.
    /// Every field multiplication inside Montgomery's trick is charged.
    fn roots_batch<F: Field>(&self, ctx: &mut Counted<F>,
                             inputs: &[(u128, u128)]) -> Vec<Option<[u128; 2]>> {
        let mut prepared = Vec::with_capacity(inputs.len());
        let mut denoms = Vec::with_capacity(inputs.len());
        for &(left, right) in inputs {
            ctx.ops.s3_calls += 1;
            let a = self.square.apply(left ^ right);
            let p = ctx.mul(left, right);
            let ps = self.square.apply(p);
            if a == 0 {
                if left == 0 {
                    prepared.push(PreparedS3::NoRoot);
                    denoms.push(0);
                } else {
                    prepared.push(PreparedS3::EqualInputs { ps });
                    denoms.push(p);
                }
            } else if ps == 0 {
                prepared.push(PreparedS3::ZeroProduct);
                denoms.push(a);
            } else {
                prepared.push(PreparedS3::Regular { a, p, ps });
                denoms.push(ctx.mul(a, ps));
            }
        }
        let mut prefix = Vec::with_capacity(denoms.len());
        let mut acc = 1u128;
        let mut first_nonzero = None;
        for (index, &denom) in denoms.iter().enumerate() {
            prefix.push(acc);
            if denom != 0 {
                if first_nonzero.is_none() {
                    first_nonzero = Some(index);
                    acc = denom;
                } else {
                    acc = ctx.mul(acc, denom);
                }
            }
        }
        let mut inverses = vec![0u128; denoms.len()];
        if let Some(first) = first_nonzero {
            let mut inverse_acc = ctx.inv(acc);
            for index in (first..denoms.len()).rev() {
                let denom = denoms[index];
                if denom == 0 { continue; }
                if index == first {
                    inverses[index] = inverse_acc;
                } else {
                    inverses[index] = ctx.mul(inverse_acc, prefix[index]);
                    inverse_acc = ctx.mul(inverse_acc, denom);
                }
            }
        }
        prepared.into_iter().zip(inverses).map(|(state, inverse)| {
            match state {
                PreparedS3::NoRoot => None,
                PreparedS3::EqualInputs { ps } => {
                    let root = ctx.mul(ps ^ 1, inverse);
                    Some([root, root])
                }
                PreparedS3::ZeroProduct => {
                    let mut root = ctx.mul(1, inverse);
                    for _ in 0..(ctx.field_degree() - 1) {
                        root = ctx.sqr(root);
                    }
                    Some([root, root])
                }
                PreparedS3::Regular { a, p, ps } => {
                    let ps_over_combined = ctx.mul(ps, inverse);
                    let q = ctx.mul(p, ps_over_combined);
                    let c = ps ^ 1;
                    let ca = ctx.mul(c, a);
                    let a_over_combined = ctx.mul(a, inverse);
                    let d = ctx.mul(ca, a_over_combined);
                    if (d & self.trace_mask).count_ones() & 1 == 1 {
                        return None;
                    }
                    let first = ctx.mul(q, self.half_trace.apply(d));
                    Some([first, first ^ q])
                }
            }
        }).collect()
    }
}

impl<F: Field> Counted<F> {
    fn field_degree(&self) -> u32 { self.field.degree() }
}

type Point = Option<(u128, u128)>;

fn point_add<F: Field>(ctx: &mut Counted<F>, left: Point, right: Point) -> Point {
    ctx.ops.point_adds += 1;
    match (left, right) {
        (None, other) | (other, None) => other,
        (Some((x1, y1)), Some((x2, y2))) => {
            if x1 == x2 {
                if y1 ^ y2 == x1 { return None; }
                if x1 == 0 { return None; }
                let inverse = ctx.inv(x1);
                let lambda = x1 ^ ctx.mul(y1, inverse);
                let x3 = ctx.sqr(lambda) ^ lambda;
                let y3 = ctx.sqr(x1) ^ ctx.mul(lambda ^ 1, x3);
                return Some((x3, y3));
            }
            let inverse = ctx.inv(x1 ^ x2);
            let lambda = ctx.mul(y1 ^ y2, inverse);
            let x3 = ctx.sqr(lambda) ^ lambda ^ x1 ^ x2;
            let y3 = ctx.mul(lambda, x1 ^ x3) ^ x3 ^ y1;
            Some((x3, y3))
        }
    }
}

fn point_lifts<F: Field>(ctx: &mut Counted<F>, solver: &S3, x: u128) -> Option<[Point; 2]> {
    ctx.ops.point_lifts += 1;
    if x == 0 { return Some([Some((0, 1)), Some((0, 1))]); }
    let inverse = ctx.inv(x);
    let inverse_squared = ctx.sqr(inverse);
    let rhs = x ^ ctx.mul(1, inverse_squared);
    let u = solver.half_trace.apply(rhs);
    if (ctx.sqr(u) ^ u) != rhs { return None; }
    let y = ctx.mul(x, u);
    Some([Some((x, y)), Some((x, x ^ y))])
}

fn lift_relation<F: Field>(ctx: &mut Counted<F>, solver: &S3,
                           xs: [u128; 4], target: Point) -> Option<[Point; 4]> {
    ctx.ops.relation_candidates += 1;
    let p0 = point_lifts(ctx, solver, xs[0])?;
    let p1 = point_lifts(ctx, solver, xs[1])?;
    let p2 = point_lifts(ctx, solver, xs[2])?;
    let p3 = point_lifts(ctx, solver, xs[3])?;
    for a in p0 {
        for b in p1 {
            let ab = point_add(ctx, a, b);
            for c in p2 {
                let abc = point_add(ctx, ab, c);
                for d in p3 {
                    if point_add(ctx, abc, d) == target {
                        return Some([a, b, c, d]);
                    }
                }
            }
        }
    }
    None
}

#[derive(Clone)]
struct State {
    left: usize,
    right: usize,
    relative: usize,
    roots_cycle: [u128; 2],
}

struct TargetQuery {
    state_offset: usize,
    orientation: usize,
    left_x: u128,
    right_x: u128,
}

fn insert_index_state<F: Field>(ctx: &mut Counted<F>, cycle: &Cycle,
                                states: &mut Vec<State>, table: &mut RootTable,
                                left: usize, right: usize, relative: usize,
                                roots: Option<[u128; 2]>) {
    if let Some(roots) = roots {
        let roots_cycle = roots.map(|root| {
            ctx.ops.basis_conversions += 1;
            cycle.to_cycle.apply(root)
        });
        let index = states.len();
        states.push(State { left, right, relative, roots_cycle });
        for (selector, &root_cycle) in roots_cycle.iter().enumerate() {
            let (key, shift) = cycle.canonical(root_cycle, &mut ctx.ops);
            table.insert(key, index as u64, selector as u8, shift);
        }
    }
}

fn check_partner<F: Field>(ctx: &mut Counted<F>, cycle: &Cycle,
                           table: &mut RootTable, states: &[State],
                           shifted: &[u128], solver: &S3, partner: u128,
                           left_x: u128, right_x: u128, target: Point,
                           table_hits: &mut u64) -> Option<([Point; 4], [u128; 4])> {
    let partner_cycle = cycle.to_cycle.apply(partner);
    ctx.ops.basis_conversions += 1;
    let (key, partner_shift) = cycle.canonical(partner_cycle, &mut ctx.ops);
    let value = table.get(key)?;
    *table_hits += 1;
    let other_index = (value >> 7) as usize;
    let stored_shift = (value & 127) as u32;
    let other = &states[other_index];
    let n = cycle.n;
    let shift2 = ((stored_shift + n - partner_shift) % n) as usize;
    let xs = [left_x, right_x,
              shifted[other.left * n as usize + shift2],
              shifted[other.right * n as usize
                  + (shift2 + other.relative) % n as usize]];
    lift_relation(ctx, solver, xs, target).map(|points| (points, xs))
}

/// Open-addressing root table. Separate key/value arrays avoid HashMap's
/// per-entry control bytes, padding, and randomized hasher on this hot path.
struct HashRootTable {
    keys: Vec<u128>,
    values: Vec<u64>,
    len: usize,
    insert_probes: u64,
    lookup_probes: u64,
    rehash_probes: u64,
}

impl HashRootTable {
    fn new(expected_states: usize) -> Self {
        let slots = expected_states.saturating_mul(3).div_ceil(2)
            .max(16).next_power_of_two();
        Self {
            keys: vec![u128::MAX; slots],
            values: vec![0; slots],
            len: 0,
            insert_probes: 0,
            lookup_probes: 0,
            rehash_probes: 0,
        }
    }

    #[inline(always)]
    fn slot(key: u128, mask: usize) -> usize {
        let mut value = key as u64 ^ ((key >> 64) as u64).rotate_left(27);
        value ^= value >> 30;
        value = value.wrapping_mul(0xbf58_476d_1ce4_e5b9);
        value ^= value >> 27;
        value = value.wrapping_mul(0x94d0_49bb_1331_11eb);
        (value ^ (value >> 31)) as usize & mask
    }

    fn grow(&mut self) {
        let slots = self.keys.len() * 2;
        let old_keys = std::mem::replace(&mut self.keys, vec![u128::MAX; slots]);
        let old_values = std::mem::replace(&mut self.values, vec![0; slots]);
        let mask = slots - 1;
        for (key, value) in old_keys.into_iter().zip(old_values) {
            if key == u128::MAX { continue; }
            let mut slot = Self::slot(key, mask);
            loop {
                self.rehash_probes += 1;
                if self.keys[slot] == u128::MAX {
                    self.keys[slot] = key;
                    self.values[slot] = value;
                    break;
                }
                slot = (slot + 1) & mask;
            }
        }
    }

    fn insert_if_absent(&mut self, key: u128, value: u64) {
        assert_ne!(key, u128::MAX);
        if self.len * 4 >= self.keys.len() * 3 { self.grow(); }
        let mask = self.keys.len() - 1;
        let mut slot = Self::slot(key, mask);
        loop {
            self.insert_probes += 1;
            if self.keys[slot] == u128::MAX {
                self.keys[slot] = key;
                self.values[slot] = value;
                self.len += 1;
                return;
            }
            if self.keys[slot] == key { return; }
            slot = (slot + 1) & mask;
        }
    }

    #[inline(always)]
    fn get(&mut self, key: u128) -> Option<u64> {
        let mask = self.keys.len() - 1;
        let mut slot = Self::slot(key, mask);
        loop {
            self.lookup_probes += 1;
            if self.keys[slot] == key { return Some(self.values[slot]); }
            if self.keys[slot] == u128::MAX { return None; }
            slot = (slot + 1) & mask;
        }
    }
}

/// Exact 11-byte N83 key followed by a 7-byte descriptor. The descriptor
/// stores a 42-bit offset in the satisfiable-state vector, one root selector,
/// and a 7-bit Frobenius shift. Keeping both root records preserves duplicates;
/// sorting by the descriptor makes the first lookup match the hash table's
/// first-inserted witness, even for a sampled pair-state traversal.
struct PackedRootTable {
    records: Vec<[u8; 18]>,
    prefix_offsets: Vec<u64>,
    bucket_offsets: Vec<u32>,
    hashed_prefix: bool,
    prefix_bits: u32,
    bucket_sort: bool,
    distinct_keys: usize,
    lookup_probes: u64,
}

impl PackedRootTable {
    fn new(expected_states: usize, hashed_prefix: bool,
           prefix_bits: u32, bucket_sort: bool) -> Self {
        assert!((1..=22).contains(&prefix_bits));
        assert!(!bucket_sort || hashed_prefix);
        Self {
            records: Vec::with_capacity(expected_states.saturating_mul(2)),
            prefix_offsets: Vec::new(),
            bucket_offsets: Vec::new(),
            hashed_prefix,
            prefix_bits,
            bucket_sort,
            distinct_keys: 0,
            lookup_probes: 0,
        }
    }

    #[inline(always)]
    fn prefix(key: u128, hashed_prefix: bool, prefix_bits: u32) -> usize {
        if hashed_prefix {
            HashRootTable::slot(key, (1usize << prefix_bits) - 1)
        } else {
            (key >> (83 - prefix_bits)) as usize
        }
    }

    fn encode(key: u128, state_offset: u64, selector: u8, shift: u32) -> [u8; 18] {
        assert!(key < (1u128 << 83));
        assert!(state_offset < (1u64 << 42));
        assert!(selector < 2);
        assert!(shift < 83);
        let descriptor = (state_offset << 8) | ((selector as u64) << 7) | shift as u64;
        let key_bytes = key.to_be_bytes();
        let descriptor_bytes = descriptor.to_be_bytes();
        let mut record = [0u8; 18];
        record[..11].copy_from_slice(&key_bytes[5..]);
        record[11..].copy_from_slice(&descriptor_bytes[1..]);
        record
    }

    fn key(record: &[u8; 18]) -> u128 {
        let mut bytes = [0u8; 16];
        bytes[5..].copy_from_slice(&record[..11]);
        u128::from_be_bytes(bytes)
    }

    fn value(record: &[u8; 18]) -> u64 {
        let mut bytes = [0u8; 8];
        bytes[1..].copy_from_slice(&record[11..]);
        let descriptor = u64::from_be_bytes(bytes);
        let selector = (descriptor >> 7) & 1;
        let shift = descriptor & 127;
        assert!(selector < 2 && shift < 83);
        (descriptor & !255) >> 1 | shift
    }

    fn insert(&mut self, key: u128, state_offset: u64, selector: u8, shift: u32) {
        self.records.push(Self::encode(key, state_offset, selector, shift));
    }

    fn finish(&mut self) {
        if self.bucket_sort {
            self.finish_buckets();
            return;
        }
        if self.hashed_prefix {
            let bits = self.prefix_bits;
            self.records.sort_unstable_by(|left, right| {
                Self::prefix(Self::key(left), true, bits)
                    .cmp(&Self::prefix(Self::key(right), true, bits))
                    .then_with(|| left.cmp(right))
            });
        } else {
            self.records.sort_unstable();
        }
        self.distinct_keys = self.records.iter().enumerate()
            .filter(|(i, record)| *i == 0 ||
                record[..11] != self.records[*i - 1][..11]).count();
        let mut offsets = vec![0u64; (1usize << self.prefix_bits) + 1];
        let mut next = 0usize;
        for (i, record) in self.records.iter().enumerate() {
            let prefix = Self::prefix(Self::key(record), self.hashed_prefix,
                                      self.prefix_bits);
            while next <= prefix {
                offsets[next] = i as u64;
                next += 1;
            }
        }
        while next < offsets.len() {
            offsets[next] = self.records.len() as u64;
            next += 1;
        }
        self.prefix_offsets = offsets;
    }

    /// Count keys by hashed prefix, scatter once, then sort each bucket by
    /// exact key and descriptor. The 32-bit directory is valid while the
    /// complete record count fits u32, which is checked before allocation.
    fn finish_buckets(&mut self) {
        let count = u32::try_from(self.records.len())
            .expect("bucket directory requires at most u32::MAX records");
        let bits = self.prefix_bits;
        let buckets = 1usize << bits;
        let mut offsets = vec![0u32; buckets + 1];
        for record in &self.records {
            let bucket = Self::prefix(Self::key(record), true, bits);
            offsets[bucket] += 1;
        }
        let mut running = 0u32;
        for entry in offsets.iter_mut().take(buckets) {
            let size = *entry;
            *entry = running;
            running = running.checked_add(size).expect("record count overflow");
        }
        assert_eq!(running, count);
        offsets[buckets] = count;
        let mut cursors = offsets[..buckets].to_vec();
        let mut reordered = vec![[0u8; 18]; self.records.len()];
        for record in self.records.drain(..) {
            let bucket = Self::prefix(Self::key(&record), true, bits);
            let position = cursors[bucket] as usize;
            reordered[position] = record;
            cursors[bucket] += 1;
        }
        for bucket in 0..buckets {
            let start = offsets[bucket] as usize;
            let end = offsets[bucket + 1] as usize;
            if end - start > 1 { reordered[start..end].sort_unstable(); }
        }
        self.records = reordered;
        self.bucket_offsets = offsets;
        self.distinct_keys = self.records.iter().enumerate()
            .filter(|(i, record)| *i == 0 ||
                record[..11] != self.records[*i - 1][..11]).count();
    }

    fn get(&mut self, key: u128) -> Option<u64> {
        let prefix = Self::prefix(key, self.hashed_prefix, self.prefix_bits);
        let (mut low, mut high) = if self.bucket_sort {
            (self.bucket_offsets[prefix] as usize,
             self.bucket_offsets[prefix + 1] as usize)
        } else {
            (self.prefix_offsets[prefix] as usize,
             self.prefix_offsets[prefix + 1] as usize)
        };
        if low == high { return None; }
        let bucket_end = high;
        while low < high {
            let middle = low + (high - low) / 2;
            self.lookup_probes += 1;
            if Self::key(&self.records[middle]) < key { low = middle + 1; }
            else { high = middle; }
        }
        if low == bucket_end { return None; }
        self.lookup_probes += 1;
        if Self::key(&self.records[low]) == key {
            Some(Self::value(&self.records[low]))
        } else { None }
    }
}

enum RootTable {
    Hash(HashRootTable),
    Packed(PackedRootTable),
}

impl RootTable {
    fn new(mode: &str, expected_states: usize) -> Self {
        match mode {
            "hash" => Self::Hash(HashRootTable::new(expected_states)),
            "packed" => Self::Packed(PackedRootTable::new(expected_states, false, 20, false)),
            "packed_hashprefix" => Self::Packed(PackedRootTable::new(expected_states, true, 20, false)),
            "packed_bucket20" => Self::Packed(PackedRootTable::new(expected_states, true, 20, true)),
            "packed_bucket22" => Self::Packed(PackedRootTable::new(expected_states, true, 22, true)),
            _ => panic!("unknown root-index mode"),
        }
    }

    fn insert(&mut self, key: u128, offset: u64, selector: u8, shift: u32) {
        match self {
            Self::Hash(table) => table.insert_if_absent(key, (offset << 7) | shift as u64),
            Self::Packed(table) => table.insert(key, offset, selector, shift),
        }
    }

    fn finish(&mut self) {
        if let Self::Packed(table) = self { table.finish(); }
    }

    fn get(&mut self, key: u128) -> Option<u64> {
        match self {
            Self::Hash(table) => table.get(key),
            Self::Packed(table) => table.get(key),
        }
    }

    fn distinct_keys(&self) -> usize {
        match self {
            Self::Hash(table) => table.len,
            Self::Packed(table) => table.distinct_keys,
        }
    }

    fn slots_or_records(&self) -> usize {
        match self {
            Self::Hash(table) => table.keys.len(),
            Self::Packed(table) => table.records.len(),
        }
    }

    fn directory_entries(&self) -> usize {
        match self {
            Self::Hash(_) => 0,
            Self::Packed(table) if table.bucket_sort => table.bucket_offsets.len(),
            Self::Packed(table) => table.prefix_offsets.len(),
        }
    }

    fn directory_offset_bytes(&self) -> usize {
        match self {
            Self::Hash(_) => 0,
            Self::Packed(table) if table.bucket_sort => 4,
            Self::Packed(_) => 8,
        }
    }

    fn allocated_bytes(&self) -> usize {
        match self {
            Self::Hash(table) => table.keys.capacity() * 16 + table.values.capacity() * 8,
            Self::Packed(table) => table.records.capacity() * 18 +
                table.prefix_offsets.capacity() * 8 +
                table.bucket_offsets.capacity() * 4,
        }
    }

    fn insert_probes(&self) -> u64 {
        match self {
            Self::Hash(table) => table.insert_probes + table.rehash_probes,
            Self::Packed(_) => 0,
        }
    }

    fn lookup_probes(&self) -> u64 {
        match self {
            Self::Hash(table) => table.lookup_probes,
            Self::Packed(table) => table.lookup_probes,
        }
    }

}

fn gcd(mut left: u64, mut right: u64) -> u64 {
    while right != 0 { (left, right) = (right, left % right); }
    left
}

fn state_id(position: u64, total: u64, sampled: bool,
            origin: u64, step: u64) -> u64 {
    if sampled { ((origin as u128 + position as u128 * step as u128)
                  % total as u128) as u64 } else { position }
}

fn decode_state(id: u64, k: usize, n: usize) -> (usize, usize, usize) {
    let relative = id as usize % n;
    let pair = id as usize / n;
    (pair / k, pair % k, relative)
}

fn peak_rss_bytes() -> u64 {
    unsafe {
        let mut use_data: libc::rusage = std::mem::zeroed();
        assert_eq!(libc::getrusage(libc::RUSAGE_SELF, &mut use_data), 0);
        #[cfg(target_os = "macos")]
        { use_data.ru_maxrss as u64 }
        #[cfg(not(target_os = "macos"))]
        { (use_data.ru_maxrss as u64) * 1024 }
    }
}

fn exact_integer(value: &Value) -> u128 {
    value.as_str().map(|s| s.parse::<u128>().unwrap())
        .or_else(|| value.as_u64().map(u128::from))
        .unwrap_or_else(|| value.to_string().parse::<u128>().unwrap())
}

fn run<F: Field>(field: F, manifest: &Value, bridge: &Value,
                 reps: &[u128], state_cap: u64, memory_cap_bytes: u64,
                 index_mode: &str) -> Value {
    assert_eq!(manifest["target_count"].as_u64(), Some(1),
               "adaptive window runs must contain exactly one target");
    let n = manifest["field_degree"].as_u64().unwrap() as u32;
    let k = reps.len();
    let total = (k as u64).checked_mul(k as u64).unwrap()
        .checked_mul(n as u64).unwrap();
    let state_cap = state_cap.min(total);
    let sampled = state_cap < total;
    let origin = 0x7e52_18ac_2026_1003u64 % total;
    let mut step = 0x9e37_79b9_7f4a_7c15u64 % total;
    if step == 0 { step = 1; }
    while gcd(step, total) != 1 { step += 1; }
    let target_array = manifest["target_poly_xy"].as_array().unwrap();
    let target_xy = (exact_integer(&target_array[0]), exact_integer(&target_array[1]));
    let target: Point = Some(target_xy);
    let orientations_per_state = manifest["orientations_per_state"]
        .as_u64().unwrap_or(1) as u32;
    assert!((1..=n).contains(&orientations_per_state));
    let index_window_size = manifest["index_s3_window_size"]
        .as_u64().unwrap_or(1) as usize;
    assert!((1..=65_536).contains(&index_window_size));
    let target_window_schedule: Vec<usize> = manifest
        .get("target_s3_window_schedule")
        .and_then(Value::as_array)
        .map(|values| values.iter().map(|value| value.as_u64().unwrap() as usize)
             .collect())
        .unwrap_or_default();
    assert!(target_window_schedule.iter().all(|size| (1..=65_536).contains(size)));
    let mut ctx = Counted { field, ops: Ops::default() };
    let start = Instant::now();
    let cycle = Cycle::from_bridge(bridge, n);
    let solver = S3::new(&mut ctx, n);
    let generator_words = bridge["mapped_generator_poly"].as_array().unwrap();
    let generator_xy = (exact_integer(&generator_words[0]),
                        exact_integer(&generator_words[1]));
    let generator: Point = Some(generator_xy);
    for &(x, y) in &[generator_xy, target_xy] {
        let lhs = ctx.sqr(y) ^ ctx.mul(x, y);
        let x2 = ctx.sqr(x);
        let rhs = ctx.mul(x2, x) ^ 1;
        assert_eq!(lhs, rhs);
    }
    let control_sum = point_add(&mut ctx, generator, target);
    let control_x = control_sum.unwrap().0;
    let control_roots = solver.roots(&mut ctx, generator_xy.0, target_xy.0).unwrap();
    assert!(control_roots.contains(&control_x));
    let generator_lifts = point_lifts(&mut ctx, &solver, generator_xy.0).unwrap();
    assert!(generator_lifts.contains(&generator));
    let mut shifted = Vec::with_capacity(k * n as usize);
    for &rep in reps {
        let mut value = rep;
        for _ in 0..n {
            shifted.push(value);
            value = ctx.sqr(value);
        }
        assert_eq!(value, rep);
    }
    let setup_ns = start.elapsed().as_nanos();
    let setup_ops = ctx.ops;
    let mut states = Vec::with_capacity((state_cap / 2) as usize);
    let mut table = RootTable::new(index_mode, state_cap as usize);
    let index_start = Instant::now();
    let mut examined = 0u64;
    let mut index_root_windows = 0u64;
    let mut memory_exceeded = false;
    if index_window_size == 1 {
        for position in 0..state_cap {
            let id = state_id(position, total, sampled, origin, step);
            let (left, right, relative) = decode_state(id, k, n as usize);
            let left_x = shifted[left * n as usize];
            let right_x = shifted[right * n as usize + relative];
            examined += 1;
            index_root_windows += 1;
            let roots = solver.roots(&mut ctx, left_x, right_x);
            insert_index_state(&mut ctx, &cycle, &mut states, &mut table,
                               left, right, relative, roots);
            if position % 10_000 == 0 && peak_rss_bytes() > memory_cap_bytes {
                memory_exceeded = true;
                break;
            }
        }
    } else {
        for start in (0..state_cap).step_by(index_window_size) {
            let end = (start + index_window_size as u64).min(state_cap);
            let mut meta = Vec::with_capacity((end - start) as usize);
            let mut inputs = Vec::with_capacity((end - start) as usize);
            for position in start..end {
                let id = state_id(position, total, sampled, origin, step);
                let (left, right, relative) = decode_state(id, k, n as usize);
                meta.push((left, right, relative));
                inputs.push((shifted[left * n as usize],
                             shifted[right * n as usize + relative]));
            }
            let roots = solver.roots_batch(&mut ctx, &inputs);
            index_root_windows += 1;
            for ((left, right, relative), roots) in meta.into_iter().zip(roots) {
                examined += 1;
                insert_index_state(&mut ctx, &cycle, &mut states, &mut table,
                                   left, right, relative, roots);
            }
            if peak_rss_bytes() > memory_cap_bytes {
                memory_exceeded = true;
                break;
            }
        }
    }
    table.finish();
    let index_ns = index_start.elapsed().as_nanos();
    let after_index_ops = ctx.ops;
    let index_ops = after_index_ops.minus(setup_ops);
    let after_index_rss = peak_rss_bytes();
    let index_table_probes = table.insert_probes();
    let lookup_sample: Vec<Value> = states.iter().take(32).enumerate()
        .flat_map(|(offset, state)| state.roots_cycle.iter().map(move |&root| (offset, root)))
        .map(|(offset, root)| {
            let mut uncharged = Ops::default();
            let (key, _) = cycle.canonical(root, &mut uncharged);
            let value = table.get(key);
            assert_eq!(value.map(|v| (v >> 7) as usize), Some(offset));
            json!([key.to_string(), value])
        }).collect();
    let sample_lookup_probes = table.lookup_probes();
    let online_start = Instant::now();
    let mut scanned = 0u64;
    let mut oriented_states = 0u64;
    let mut prepared_states = 0u64;
    let mut prepared_orientations = 0u64;
    let mut target_root_windows = 0u64;
    let mut partner_roots = 0u64;
    let mut table_hits = 0u64;
    let mut relation: Option<[Point; 4]> = None;
    let mut relation_xs = [0u128; 4];
    if !memory_exceeded {
        let target_seed = (target_xy.0 as u64) ^ ((target_xy.1 >> 64) as u64)
            ^ (target_xy.1 as u64).rotate_left(29) ^ 0xd6e8_feb8_6659_fd93;
        if index_window_size == 1 {
            for (offset, state) in states.iter().enumerate() {
                scanned += 1;
                let mut seed = target_seed
                    ^ (offset as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15)
                    ^ ((state.left as u64) << 32)
                    ^ ((state.right as u64) << 16)
                    ^ state.relative as u64;
                let first_shift = (splitmix64(&mut seed) % n as u64) as usize;
                for orientation in 0..orientations_per_state as usize {
                    oriented_states += 1;
                    let shift = (first_shift + orientation) % n as usize;
                    let left_x = shifted[state.left * n as usize + shift];
                    let right_x = shifted[state.right * n as usize
                        + (shift + state.relative) % n as usize];
                    for &root_cycle in &state.roots_cycle {
                        let absolute = cycle.to_poly.apply(cycle.rotate(root_cycle, shift as u32));
                        ctx.ops.basis_conversions += 1;
                        if let Some(partners) = solver.roots(&mut ctx, absolute, target_xy.0) {
                            for partner in partners {
                                partner_roots += 1;
                                if let Some((points, xs)) = check_partner(
                                    &mut ctx, &cycle, &mut table, &states, &shifted,
                                    &solver, partner, left_x, right_x, target,
                                    &mut table_hits) {
                                    relation = Some(points);
                                    relation_xs = xs;
                                    break;
                                }
                            }
                        }
                        if relation.is_some() { break; }
                    }
                    if relation.is_some() { break; }
                }
                if relation.is_some() { break; }
                if offset % 10_000 == 0 && peak_rss_bytes() > memory_cap_bytes {
                    memory_exceeded = true;
                    break;
                }
            }
            prepared_states = scanned;
            prepared_orientations = oriented_states;
        } else {
            let mut start = 0usize;
            let mut schedule_index = 0usize;
            while start < states.len() {
                let target_window_size = target_window_schedule
                    .get(schedule_index)
                    .copied()
                    .unwrap_or(index_window_size);
                let end = (start + target_window_size).min(states.len());
                let mut inputs = Vec::with_capacity(
                    2 * (end - start) * orientations_per_state as usize);
                let mut queries = Vec::with_capacity(inputs.capacity());
                for (local, state) in states[start..end].iter().enumerate() {
                    let offset = start + local;
                    let mut seed = target_seed
                        ^ (offset as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15)
                        ^ ((state.left as u64) << 32)
                        ^ ((state.right as u64) << 16)
                        ^ state.relative as u64;
                    let first_shift = (splitmix64(&mut seed) % n as u64) as usize;
                    for orientation in 0..orientations_per_state as usize {
                        let shift = (first_shift + orientation) % n as usize;
                        let left_x = shifted[state.left * n as usize + shift];
                        let right_x = shifted[state.right * n as usize
                            + (shift + state.relative) % n as usize];
                        for &root_cycle in &state.roots_cycle {
                            let absolute = cycle.to_poly.apply(
                                cycle.rotate(root_cycle, shift as u32));
                            ctx.ops.basis_conversions += 1;
                            inputs.push((absolute, target_xy.0));
                            queries.push(TargetQuery {
                                state_offset: offset, orientation,
                                left_x, right_x,
                            });
                        }
                    }
                }
                prepared_states += (end - start) as u64;
                prepared_orientations += (
                    (end - start) * orientations_per_state as usize) as u64;
                let roots = solver.roots_batch(&mut ctx, &inputs);
                target_root_windows += 1;
                if peak_rss_bytes() > memory_cap_bytes {
                    memory_exceeded = true;
                    break;
                }
                let mut last_orientation = None;
                for (query, roots) in queries.into_iter().zip(roots) {
                    scanned = query.state_offset as u64 + 1;
                    let marker = (query.state_offset, query.orientation);
                    if last_orientation != Some(marker) {
                        oriented_states += 1;
                        last_orientation = Some(marker);
                    }
                    if let Some(partners) = roots {
                        for partner in partners {
                            partner_roots += 1;
                            if let Some((points, xs)) = check_partner(
                                &mut ctx, &cycle, &mut table, &states, &shifted,
                                &solver, partner, query.left_x, query.right_x,
                                target, &mut table_hits) {
                                relation = Some(points);
                                relation_xs = xs;
                                break;
                            }
                        }
                    }
                    if relation.is_some() { break; }
                }
                if relation.is_some() { break; }
                if peak_rss_bytes() > memory_cap_bytes {
                    memory_exceeded = true;
                    break;
                }
                start = end;
                schedule_index += 1;
            }
        }
    }
    let online_ns = online_start.elapsed().as_nanos();
    let target_ops = ctx.ops.minus(after_index_ops);
    if index_window_size == 1 { target_root_windows = target_ops.s3_calls; }
    let relation_json = relation.map(|points| {
        json!({
            "poly_points_xy_decimal": points.map(|p| {
                let (x, y) = p.unwrap();
                [x.to_string(), y.to_string()]
            }),
            "poly_x_words_decimal": relation_xs.map(|v| v.to_string()),
            "native_group_sum_verified": true,
        })
    });
    let (control_sum_x, control_sum_y) = control_sum.unwrap();
    let control_json = json!({
        "status": "PASS",
        "sum_poly_xy_decimal": [control_sum_x.to_string(), control_sum_y.to_string()],
        "sum_x_is_s3_root": true,
        "generator_lift_recovered": true,
    });
    json!({
        "kind": "bounded_native_s3_root_stage_run",
        "native_source_sha256": env!("NATIVE_S3_SOURCE_SHA256"),
        "cargo_manifest_sha256": env!("NATIVE_S3_BUILD_MANIFEST_SHA256"),
        "proposal_id": manifest["proposal_id"],
        "parent_factor_base_proposal_id": manifest["parent_factor_base_proposal_id"],
        "stage_protocol_sha256": manifest["stage_protocol_sha256"],
        "candidate_id": null,
        "run_id": null,
        "curve_id": manifest["curve_id"],
        "workload_id": manifest["workload_id"],
        "target_count": manifest["target_count"],
        "isogeny": "none",
        "field_degree": n,
        "actual_usable_points_B": manifest["actual_usable_points_B"],
        "folded_columns_K": k,
        "factor_base_enumerated_set_sha256": manifest["factor_base_enumerated_set_sha256"],
        "input_representatives_sha256": manifest["representatives_file_sha256"],
        "status": if relation_json.is_some() { "native_relation_found" }
                  else if memory_exceeded { "memory_cap_exceeded" }
                  else { "state_cap_no_relation" },
        "relation": relation_json,
        "limits": { "pair_state_cap": state_cap, "peak_rss_cap_bytes": memory_cap_bytes },
        "sampling": { "kind": if sampled { "coprime_stride_without_replacement" }
                             else { "complete_lexicographic" },
                      "origin": if sampled { origin } else { 0 },
                      "step": if sampled { step } else { 1 },
                      "orientations_per_state": orientations_per_state },
        "index_s3_window_size": index_window_size,
        "target_s3_window_schedule": if target_window_schedule.is_empty() {
            vec![index_window_size]
        } else {
            target_window_schedule
        },
        "index_root_windows": index_root_windows,
        "total_quotient_pair_states": total,
        "index_pair_states_examined": examined,
        "index_satisfiable_s3_states": states.len(),
        "index_mode": index_mode,
        "index_distinct_root_keys": table.distinct_keys(),
        "root_table_slots_or_records": table.slots_or_records(),
        "root_table_allocated_bytes": table.allocated_bytes(),
        "root_table_directory_entries": table.directory_entries(),
        "root_table_directory_offset_bytes": table.directory_offset_bytes(),
        "root_table_record_bytes": if index_mode == "hash" { 24 } else { 18 },
        "lookup_sample": lookup_sample,
        "lookup_sample_probes_outside_online": sample_lookup_probes,
        "root_table_hash_probes": {
            "index_insert_and_rehash": index_table_probes,
            "target_lookup": table.lookup_probes() - sample_lookup_probes,
        },
        "target_states_scanned": scanned,
        "target_state_orientations_tested": oriented_states,
        "target_states_prepared": prepared_states,
        "target_state_orientations_prepared": prepared_orientations,
        "target_root_windows": target_root_windows,
        "target_partner_roots": partner_roots,
        "target_table_hits": table_hits,
        "native_s3_generator_target_control": control_json,
        "timing_ns": { "setup": setup_ns.to_string(), "index_build": index_ns.to_string(),
                       "target_pdp_and_native_check": online_ns.to_string() },
        "operation_counts": { "setup": setup_ops.value(), "index_build": index_ops.value(),
                              "target_pdp_and_native_check": target_ops.value() },
        "peak_rss_bytes": peak_rss_bytes(),
        "rss_after_index_bytes": after_index_rss,
        "verified_single_target_dlp": false,
        "complete_work_log2": null,
    })
}

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert_eq!(args.len(), 8,
        "usage: native_packed_index manifest.json bridge.json reps.bin state_cap memory_cap_mib hash|packed|packed_hashprefix|packed_bucket20|packed_bucket22 output.json");
    let manifest: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
    let bridge: Value = serde_json::from_slice(&fs::read(&args[2]).unwrap()).unwrap();
    let data = fs::read(&args[3]).unwrap();
    assert_eq!(data.len() % 16, 0);
    let reps: Vec<u128> = data.chunks_exact(16)
        .map(|chunk| u128::from_le_bytes(chunk.try_into().unwrap())).collect();
    let n = manifest["field_degree"].as_u64().unwrap() as u32;
    assert_eq!(manifest["representative_count_K"].as_u64().unwrap() as usize, reps.len());
    assert_eq!(bridge["field_degree"].as_u64().unwrap() as u32, n);
    assert_eq!(manifest["curve_id"], bridge["curve_id"]);
    let cap = args[4].parse::<u64>().unwrap();
    let memory_mib = args[5].parse::<u64>().unwrap();
    assert_eq!(cap, manifest["pair_state_cap"].as_u64().unwrap());
    assert_eq!(memory_mib, manifest["peak_rss_cap_mib"].as_u64().unwrap());
    let memory_bytes = memory_mib.checked_mul(1024 * 1024).unwrap();
    let low_terms: Vec<u32> = manifest["polynomial_low_terms"].as_array().unwrap()
        .iter().map(|v| v.as_u64().unwrap() as u32).collect();
    let irr = IrreduciblePoly { degree: n, low_terms };
    let mode = args[6].as_str();
    let report = if n == 53 {
        run(Gf2::new(&irr), &manifest, &bridge, &reps, cap, memory_bytes, mode)
    } else if n == 83 {
        run(Gf2_128::new(&irr), &manifest, &bridge, &reps, cap, memory_bytes, mode)
    } else { panic!("unsupported field degree") };
    fs::write(&args[7], serde_json::to_vec_pretty(&report).unwrap()).unwrap();
    println!("{}", json!({"status": report["status"], "field_degree": n,
                          "index_states": report["index_pair_states_examined"],
                          "target_states": report["target_states_scanned"],
                          "peak_rss_bytes": report["peak_rss_bytes"]}));
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn packed_index_matches_first_hash_witness_and_keeps_duplicates() {
        let mut hash = RootTable::new("hash", 8);
        let mut packed = RootTable::new("packed", 8);
        for (offset, key, selector, shift) in [
            (0, 5, 0, 7), (0, 5, 1, 8), (1, 3, 0, 82),
            (2, 5, 0, 2), (3, (1u128 << 83) - 1, 1, 0),
        ] {
            hash.insert(key, offset, selector, shift);
            packed.insert(key, offset, selector, shift);
        }
        hash.finish();
        packed.finish();
        assert_eq!(packed.distinct_keys(), 3);
        assert_eq!(packed.slots_or_records(), 5);
        assert!(packed.allocated_bytes() >= 16 * 18);
        for key in [0, 3, 4, 5, 6, (1u128 << 83) - 1] {
            assert_eq!(hash.get(key), packed.get(key), "key {key}");
        }
        let maximum = PackedRootTable::encode((1u128 << 83) - 1,
            (1u64 << 42) - 1, 1, 82);
        assert_eq!(PackedRootTable::key(&maximum), (1u128 << 83) - 1);
        assert_eq!(PackedRootTable::value(&maximum),
            (((1u64 << 42) - 1) << 7) | 82);
    }

    #[test]
    fn hashed_prefix_matches_hash_for_hits_misses_and_duplicates() {
        for mode in ["packed_hashprefix", "packed_bucket20", "packed_bucket22"] {
            let mut hash = RootTable::new("hash", 50_000);
            let mut packed = RootTable::new(mode, 50_000);
            let mut seed = 0x2f6e_7a91_b3c4_d508u64;
            let mut keys = Vec::new();
            for offset in 0..50_000u64 {
                let low = splitmix64(&mut seed) as u128;
                let high = (splitmix64(&mut seed) as u128) & ((1u128 << 19) - 1);
                let key = (high << 64) | low;
                keys.push(key);
                hash.insert(key, offset, 0, (offset % 83) as u32);
                packed.insert(key, offset, 0, (offset % 83) as u32);
                if offset % 37 == 0 {
                    hash.insert(key, offset + 50_000, 1, 82);
                    packed.insert(key, offset + 50_000, 1, 82);
                }
            }
            hash.finish();
            packed.finish();
            assert_eq!(hash.distinct_keys(), packed.distinct_keys());
            assert_eq!(packed.directory_offset_bytes(),
                       if mode == "packed_hashprefix" { 8 } else { 4 });
            for key in keys {
                assert_eq!(hash.get(key), packed.get(key), "{mode} hit {key}");
                let absent = key ^ (1u128 << 82);
                assert_eq!(hash.get(absent), packed.get(absent),
                           "{mode} miss {absent}");
            }
        }
    }

    #[test]
    fn batch_roots_match_direct_for_every_gf32_input_pair() {
        let modulus = IrreduciblePoly { degree: 5, low_terms: vec![0, 2] };
        let mut direct = Counted {
            field: Gf2::new(&modulus), ops: Ops::default(),
        };
        let solver = S3::new(&mut direct, 5);
        let inputs: Vec<(u128, u128)> = (0..32u128)
            .flat_map(|left| (0..32u128).map(move |right| (left, right)))
            .collect();
        let expected: Vec<_> = inputs.iter().map(|&(left, right)| {
            solver.roots(&mut direct, left, right)
        }).collect();
        for size in [1, 2, 7, 128, 1024] {
            let mut batched = Counted {
                field: Gf2::new(&modulus), ops: Ops::default(),
            };
            let got: Vec<_> = inputs.chunks(size).flat_map(|chunk| {
                solver.roots_batch(&mut batched, chunk)
            }).collect();
            assert_eq!(got, expected, "batch size {size}");
            assert_eq!(batched.ops.s3_calls, 1024);
        }
    }
}
