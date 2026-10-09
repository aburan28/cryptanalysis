#![recursion_limit = "256"]

//! Natural-factor-base orbit-slice IC experiment with parallel, sharded index
//! construction and parallel relation batches.
//!
//! The factor base is the deterministic low-x scan, filtered into the declared
//! prime-order subgroup and folded into signed Frobenius orbits. Its logarithms
//! are not supplied. The S3 index samples one target-seeded global Frobenius
//! orientation per state. Ordinary known-scalar subgroup queries collect four
//! point relations; incremental Gaussian elimination recovers and certifies
//! the factor-base logs. The supplied public target is then decomposed and its
//! scalar recovered from those logs. Independent known-scalar relation targets
//! are searched in parallel batches before their matrix rows are inserted.
//!
//! The final worker argument controls both the S3-root index builder and the
//! relation collector. Index states are merged in their original
//! left/right/relative order before root-table insertion, preserving the
//! serial builder's deterministic duplicate tie-breaking. Canonical roots are
//! assigned to hash shards with independent open-addressed tables.
//!
//! Usage: <n> <a> <orbit_columns> <relation_seed> <target_point.json> <out.jsonl> <workers>

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

    /// Solve both S3 queries for one indexed state with one generic inversion.
    /// Exceptional pairs retain the scalar path and result order.
    #[inline(always)]
    fn roots_pair(
        &self,
        gf: &Gf2,
        basis: &NormalBasis,
        left: [u64; 2],
        right: u64,
    ) -> [Option<[u64; 2]>; 2] {
        let a = [
            self.square.apply(left[0] ^ right),
            self.square.apply(left[1] ^ right),
        ];
        let p = [gf.mul(left[0], right), gf.mul(left[1], right)];
        let ps = [self.square.apply(p[0]), self.square.apply(p[1])];
        if a[0] == 0 || ps[0] == 0 || a[1] == 0 || ps[1] == 0 {
            return [
                self.roots(gf, basis, left[0], right),
                self.roots(gf, basis, left[1], right),
            ];
        }
        let denominator = [gf.mul(a[0], ps[0]), gf.mul(a[1], ps[1])];
        let inverse_product = invert(gf, basis, gf.mul(denominator[0], denominator[1]));
        let inverse = [
            gf.mul(inverse_product, denominator[1]),
            gf.mul(inverse_product, denominator[0]),
        ];
        std::array::from_fn(|i| {
            let q = gf.mul(p[i], gf.mul(ps[i], inverse[i]));
            let c = ps[i] ^ self.b;
            let d = gf.mul(gf.mul(c, a[i]), gf.mul(a[i], inverse[i]));
            if (d & self.trace_mask).count_ones() & 1 == 1 {
                return None;
            }
            let first = gf.mul(q, self.half_trace.apply(d));
            Some([first, first ^ q])
        })
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
    shard_bits: u32,
    len: usize,
}

impl RootTable {
    fn with_capacity(entries: usize, shard_bits: u32) -> Self {
        let doubled = entries
            .checked_mul(2)
            .unwrap_or_else(|| panic!("root shard capacity overflow: entries={entries}"));
        let slots = doubled
            .checked_next_power_of_two()
            .unwrap_or_else(|| panic!("root shard slot overflow: entries={entries}"))
            .max(16);
        let mut storage = Vec::new();
        storage.try_reserve_exact(slots).unwrap_or_else(|error| {
            panic!("root shard allocation failed: entries={entries} slots={slots} error={error}")
        });
        storage.resize(slots, (u64::MAX, 0));
        Self {
            slots: storage,
            shard_bits,
            len: 0,
        }
    }

    #[inline(always)]
    fn hash(key: u64) -> u64 {
        key.wrapping_mul(0x9E37_79B9_7F4A_7C15)
    }

    #[inline(always)]
    fn shard(hash: u64, shard_bits: u32) -> usize {
        (hash >> (64 - shard_bits)) as usize
    }

    #[inline(always)]
    fn slot(&self, hash: u64) -> usize {
        ((hash >> self.shard_bits) as usize) & (self.slots.len() - 1)
    }

    fn insert_if_absent_hashed(&mut self, key: u64, value: u64, hash: u64) {
        let mask = self.slots.len() - 1;
        let mut slot = self.slot(hash);
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
    fn get_hashed(&self, key: u64, hash: u64) -> Option<u64> {
        let mask = self.slots.len() - 1;
        let mut slot = self.slot(hash);
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

/// Deterministic hash partition over independent open-addressed root tables.
/// The low hash bits select a shard, and the following bits select its slot.
struct ShardedRootTable {
    shards: Vec<RootTable>,
    shard_mask: usize,
    shard_bits: u32,
    len: usize,
    slots: usize,
    input_entries_per_shard: Vec<usize>,
    slots_per_shard: Vec<usize>,
}

impl ShardedRootTable {
    fn get(&self, key: u64) -> Option<u64> {
        let hash = RootTable::hash(key);
        let shard = RootTable::shard(hash, self.shard_bits) & self.shard_mask;
        self.shards[shard].get_hashed(key, hash)
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
    table: ShardedRootTable,
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
) -> (Index, f64, f64, f64, f64, f64) {
    let n = gf.n as usize;
    let shifted_started = Instant::now();
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
    let shifted_generation_ms = shifted_started.elapsed().as_secs_f64() * 1000.0;
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
    let state_merge_started = Instant::now();
    let state_count = state_chunks.iter().map(Vec::len).sum();
    let mut states = Vec::with_capacity(state_count);
    for mut chunk in state_chunks {
        states.append(&mut chunk);
    }
    let state_merge_ms = state_merge_started.elapsed().as_secs_f64() * 1000.0;

    let root_scatter_started = Instant::now();
    const SHARD_COUNT: usize = 64;
    let shard_bits = SHARD_COUNT.trailing_zeros();
    let shard_mask = SHARD_COUNT - 1;

    // Each worker handles a consecutive state interval and appends canonical
    // roots to thread-local shard vectors. Joining in worker order preserves
    // serial state/root order inside every shard, making duplicate-root
    // resolution deterministic without a global insertion lock.
    let scatter_workers = workers.max(1).min(states.len().max(1));
    let states_per_scatter_worker = states.len().div_ceil(scatter_workers);
    let mut worker_entries: Vec<Vec<Vec<(u64, u64)>>> = Vec::with_capacity(scatter_workers);
    thread::scope(|scope| {
        let handles: Vec<_> = (0..scatter_workers)
            .map(|worker| {
                let first = worker * states_per_scatter_worker;
                let end = (first + states_per_scatter_worker).min(states.len());
                let states = &states;
                let basis = basis;
                scope.spawn(move || {
                    let mut entries = (0..SHARD_COUNT).map(|_| Vec::new()).collect::<Vec<_>>();
                    for state in &states[first..end] {
                        for &root in &state.normal_roots {
                            let (canonical, shift) = basis.canonical(root);
                            let hash = RootTable::hash(canonical);
                            let shard = RootTable::shard(hash, shard_bits) & shard_mask;
                            entries[shard].push((
                                canonical,
                                pack(state.left, state.right, state.relative, shift),
                            ));
                        }
                    }
                    entries
                })
            })
            .collect();
        for handle in handles {
            worker_entries.push(handle.join().expect("root scatter worker panicked"));
        }
    });
    let root_scatter_ms = root_scatter_started.elapsed().as_secs_f64() * 1000.0;

    // Shards are independent because equal keys share a hash prefix. Per-
    // shard insertion consumes the state chunks in their original order, so
    // insert-if-absent picks the same first witness as the serial table.
    let root_insert_started = Instant::now();
    let table_workers = workers.max(1).min(SHARD_COUNT);
    let mut built_shards: Vec<Option<RootTable>> =
        std::iter::repeat_with(|| None).take(SHARD_COUNT).collect();
    thread::scope(|scope| {
        let handles: Vec<_> = (0..table_workers)
            .map(|worker| {
                let first_shard = worker * SHARD_COUNT / table_workers;
                let end_shard = (worker + 1) * SHARD_COUNT / table_workers;
                let worker_entries = &worker_entries;
                scope.spawn(move || {
                    let mut built = Vec::with_capacity(end_shard - first_shard);
                    for shard in first_shard..end_shard {
                        let entries_count: usize =
                            worker_entries.iter().map(|chunk| chunk[shard].len()).sum();
                        let mut table = RootTable::with_capacity(entries_count, shard_bits);
                        for chunk in worker_entries {
                            for &(key, value) in &chunk[shard] {
                                let hash = RootTable::hash(key);
                                table.insert_if_absent_hashed(key, value, hash);
                            }
                        }
                        built.push((shard, table));
                    }
                    built
                })
            })
            .collect();
        for handle in handles {
            for (shard, table) in handle.join().expect("root shard worker panicked") {
                built_shards[shard] = Some(table);
            }
        }
    });
    let input_entries_per_shard: Vec<usize> = (0..SHARD_COUNT)
        .map(|shard| worker_entries.iter().map(|chunk| chunk[shard].len()).sum())
        .collect();
    let shards: Vec<RootTable> = built_shards
        .into_iter()
        .map(|shard| shard.expect("root shard was not built"))
        .collect();
    let len = shards.iter().map(|shard| shard.len).sum();
    let slots = shards.iter().map(|shard| shard.slots.len()).sum();
    let slots_per_shard = shards.iter().map(|shard| shard.slots.len()).collect();
    let table = ShardedRootTable {
        shards,
        shard_mask,
        shard_bits,
        len,
        slots,
        input_entries_per_shard,
        slots_per_shard,
    };
    let root_shard_insert_ms = root_insert_started.elapsed().as_secs_f64() * 1000.0;
    (
        Index {
            states,
            table,
            shifted,
        },
        state_generation_ms,
        shifted_generation_ms,
        state_merge_ms,
        root_scatter_ms,
        root_shard_insert_ms,
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
        let absolute = state
            .normal_roots
            .map(|root| basis.to_poly.apply(basis.rotate(root, shift as u32)));
        let partner_sets = solver.roots_pair(gf, basis, absolute, target_x);
        target_s3_calls += 2;
        for possible_partners in partner_sets {
            let Some(partners) = possible_partners else {
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

/// Frobenius-closed signed-orbit base from a deterministic public x-scan.
///
/// Each accepted x lifts to a point, is projected into the order-r subgroup by
/// the cofactor, and contributes its whole signed Frobenius orbit. Point logs
/// are unknown; the label of member `phi^k(+-R_j)` is `(j, +-lambda^k)`.
fn construct_base(
    fast: &FastBinaryCurve,
    curve: &KoblitzCurve,
    b: u64,
    columns: usize,
    r: u64,
) -> (
    Vec<FastPoint>,
    Vec<(usize, u64)>,
    Vec<Option<[u64; 2]>>,
    u64,
) {
    let gf = &fast.gf;
    let n = fast.n as usize;
    let lambda = curve.lambda.to_u64().unwrap();
    let mut seen = std::collections::HashSet::new();
    let mut points = Vec::with_capacity(columns * 2 * n);
    let mut labels = Vec::with_capacity(columns * 2 * n);
    let mut reps = Vec::with_capacity(columns);
    let mut scanned = 0u64;
    let mut raw_x = 1u64;
    while reps.len() < columns {
        scanned += 1;
        for point in fast.points_with_x(b, raw_x) {
            let Some((px, py)) = fast.scalar_mul(point, &curve.cofactor) else {
                continue;
            };
            if px <= 1 {
                continue;
            }
            let mut key = px;
            let mut x = px;
            for _ in 1..n {
                x = gf.sqr(x);
                key = key.min(x);
            }
            if !seen.insert(key) {
                continue;
            }
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
            if reps.len() == columns {
                break;
            }
        }
        raw_x += 1;
    }
    let rep = reps[0].map(|[x, y]| (x, y));
    assert_eq!(
        fast.scalar_mul(rep, &BigUint::from(lambda)),
        rep.map(|(x, y)| (gf.sqr(x), gf.sqr(y))),
        "Frobenius must act as lambda on the subgroup"
    );
    (points, labels, reps, scanned)
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
        8,
        "usage: <n> <a> <orbit_columns> <relation_seed> <target_point.json> <out.jsonl> <workers>"
    );
    let process_started = Instant::now();
    let n: u32 = arguments[1].parse().unwrap();
    let a: u8 = arguments[2].parse().unwrap();
    let columns: usize = arguments[3].parse().unwrap();
    let relation_seed: u64 = arguments[4].parse().unwrap();
    let relation_workers: usize = arguments[7].parse().unwrap();
    assert!(
        relation_workers > 0,
        "relation worker count must be positive"
    );
    let target_raw: [u64; 2] =
        serde_json::from_slice(&std::fs::read(&arguments[5]).expect("read public target point"))
            .expect("target point must be [x,y]");
    let mut out = std::fs::File::create(&arguments[6]).unwrap();

    // Input loading and output setup are outside both online clocks.
    let cold_started = Instant::now();
    let setup_started = Instant::now();
    let curve = KoblitzCurve::new(a, n).expect("admitted Koblitz rung");
    let r = curve.subgroup_order.to_u64().unwrap();
    let fast = FastBinaryCurve::new(&curve.curve.irreducible, a as u64).unwrap();
    let gf = Gf2::new(&curve.curve.irreducible);
    let b = gf.from_element(&curve.curve.b);
    let generator: FastPoint = match curve.generator() {
        crypto_lib::binary_ecc::BinaryPoint::Affine { x, y } => Some((fast.word(x), fast.word(y))),
        crypto_lib::binary_ecc::BinaryPoint::Infinity => panic!("generator must be affine"),
    };
    let target: FastPoint = Some((target_raw[0], target_raw[1]));
    assert_eq!(
        fast.scalar_mul(generator, &BigUint::from(r)),
        None,
        "G must have order r"
    );
    assert_eq!(fast.scalar_mul(generator, &BigUint::from(1u64)), generator);
    let curve_setup_ms = setup_started.elapsed().as_secs_f64() * 1000.0;

    // The base is defined by the public low-x construction and subgroup
    // filtering. No base logarithm is supplied to this solver.
    let base_started = Instant::now();
    let (points, labels, representatives, scanned_x) = construct_base(&fast, &curve, b, columns, r);
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
    let base_build_ms = base_started.elapsed().as_secs_f64() * 1000.0;

    let mut hasher = blake3::Hasher::new();
    hasher.update(b"koblitz-natural-xscan-signed-frobenius-base-v1");
    for (point, &(column, coefficient)) in base.points.iter().zip(&base.labels) {
        let (x, y) = point.unwrap();
        for word in [x, y, column as u64, coefficient] {
            hasher.update(&word.to_le_bytes());
        }
    }
    let base_digest_started = Instant::now();
    let base_hash = hasher.finalize().to_hex().to_string();
    let base_digest_ms = base_digest_started.elapsed().as_secs_f64() * 1000.0;

    let basis_started = Instant::now();
    let basis = NormalBasis::new(&gf);
    let solver = S3Solver::new(&gf, b);
    for probe in 1..2048u64 {
        let x = probe.wrapping_mul(0x2545_F491_4F6C_DD1D) & basis.mask;
        assert_eq!(
            basis
                .to_poly
                .apply(basis.rotate(basis.to_normal.apply(x), 1)),
            gf.sqr(x)
        );
        let y = (probe * 0x9E37_79B9) & basis.mask;
        assert_eq!(solver.roots(&gf, &basis, x, y), s3_x_roots(&gf, b, x, y));
    }
    let basis_ms = basis_started.elapsed().as_secs_f64() * 1000.0;

    let representative_x_started = Instant::now();
    let rep_x: Vec<u64> = representatives
        .iter()
        .map(|point| point.expect("representative point")[0])
        .collect();
    let representative_x_ms = representative_x_started.elapsed().as_secs_f64() * 1000.0;
    let index_started = Instant::now();
    let (
        index,
        index_state_generation_ms,
        index_shifted_generation_ms,
        index_state_merge_ms,
        index_root_scatter_ms,
        index_root_shard_insert_ms,
    ) = build_index(&gf, &basis, &solver, &rep_x, relation_workers);
    let index_ms = index_started.elapsed().as_secs_f64() * 1000.0;
    let index_charged_subphases_ms = index_state_generation_ms
        + index_shifted_generation_ms
        + index_state_merge_ms
        + index_root_scatter_ms
        + index_root_shard_insert_ms;
    let index_unattributed_overhead_ms = (index_ms - index_charged_subphases_ms).max(0.0);
    assert!(index_ms + 0.02 >= index_charged_subphases_ms);

    // This candidate decomposes the public target first, then collects only
    // enough known-scalar relations for its coefficient vector to enter the
    // verified row space. Every operation from here through scalar replay is
    // target-dependent and belongs to the one-target online interval.
    let reusable_setup_ms = cold_started.elapsed().as_secs_f64() * 1000.0;
    let setup_charged_subphases_ms =
        curve_setup_ms + base_build_ms + base_digest_ms + basis_ms + representative_x_ms + index_ms;
    let setup_timer_boundary_residual_ms = reusable_setup_ms - setup_charged_subphases_ms;
    assert!(setup_timer_boundary_residual_ms >= -0.02);
    let target_online_started = Instant::now();
    let target_validation_started = Instant::now();
    let (qx, qy) = target.expect("Q must be affine");
    let lhs = gf.sqr(qy) ^ gf.mul(qx, qy);
    let rhs = gf.mul(gf.sqr(qx), qx) ^ gf.mul(gf.from_element(&curve.curve.a), gf.sqr(qx)) ^ b;
    assert_eq!(lhs, rhs, "Q must lie on the declared curve");
    assert_eq!(
        fast.scalar_mul(target, &BigUint::from(r)),
        None,
        "Q must lie in the declared subgroup"
    );
    let target_validation_ms = target_validation_started.elapsed().as_secs_f64() * 1000.0;
    let target_hash_started = Instant::now();
    let target_hash = point_hash(target);
    let target_query_hash_ms = target_hash_started.elapsed().as_secs_f64() * 1000.0;
    let target_query_started = Instant::now();
    let (target_relation, target_state_probes, target_s3_calls) = extract(
        &gf,
        &fast,
        &basis,
        &solver,
        &index,
        &base,
        target,
        target_hash as usize,
    );
    let target_extract_ms = target_query_started.elapsed().as_secs_f64() * 1000.0;
    let target_relation_check_ms = target_relation
        .as_ref()
        .map(|relation| relation.relation_check_ms)
        .unwrap_or(0.0);
    let target_pdp_ms = (target_extract_ms - target_relation_check_ms).max(0.0);
    let target_coefficients = target_relation
        .as_ref()
        .map(|relation| relation_row(&base, relation, 0, r)[..base.columns].to_vec());

    // Relation targets R=[a]G are sampled independently, but collection stops
    // at the first completed 14-query batch whose rows span the target vector.
    let rank_started = Instant::now();
    let mut echelon = Echelon {
        r,
        columns: base.columns,
        pivots: vec![None; base.columns],
        rank: 0,
    };
    let mut relation_rng = relation_seed;
    let mut used_relation_scalars = std::collections::HashSet::new();
    let max_relation_attempts = base.columns.saturating_mul(8).max(base.columns + 32);
    let mut rank_attempts = 0usize;
    let mut rank_failures = 0usize;
    let mut rank_verified_relations = 0usize;
    let mut rank_new_rows = 0usize;
    let mut rank_dependent_rows = 0usize;
    let mut rank_state_probes = 0u64;
    let mut rank_target_s3_calls = 0u64;
    let mut rank_attempts_completed = 0usize;
    let mut rank_query_generation_ms = 0.0;
    let mut rank_pdp_ms = 0.0;
    let mut rank_pdp_wall_ms = 0.0;
    let mut rank_relation_check_ms = 0.0;
    let mut rank_matrix_build_ms = 0.0;
    let mut rank_linear_algebra_ms = 0.0;
    let mut target_span_check_ms = 0.0;
    let mut target_span_checks = 0usize;
    let mut target_span_value = None;
    let mut target_span_relation_prefix = None;
    let mut target_span_attempt_prefix = None;
    let mut rank_witnesses = Vec::new();

    while target_span_value.is_none() && rank_attempts < max_relation_attempts {
        let mut batch =
            Vec::with_capacity(relation_workers.min(max_relation_attempts - rank_attempts));
        while batch.len() < relation_workers && rank_attempts + batch.len() < max_relation_attempts
        {
            let query_generation_started = Instant::now();
            let relation_scalar = splitmix64(&mut relation_rng) % (r - 1) + 1;
            if !used_relation_scalars.insert(relation_scalar) {
                rank_query_generation_ms +=
                    query_generation_started.elapsed().as_secs_f64() * 1000.0;
                continue;
            }
            let relation_target = fast
                .scalar_mul(generator, &BigUint::from(relation_scalar))
                .expect("nonzero relation target");
            let relation_hash = point_hash(Some(relation_target));
            rank_query_generation_ms += query_generation_started.elapsed().as_secs_f64() * 1000.0;
            batch.push((relation_scalar, relation_target, relation_hash));
        }
        if batch.is_empty() {
            break;
        }
        rank_attempts += batch.len();

        let batch_pdp_started = Instant::now();
        let batch_results = thread::scope(|scope| {
            let handles: Vec<_> = batch
                .iter()
                .copied()
                .map(|(relation_scalar, relation_target, relation_hash)| {
                    let gf = &gf;
                    let fast = &fast;
                    let basis = &basis;
                    let solver = &solver;
                    let index = &index;
                    let base = &base;
                    scope.spawn(move || {
                        let pdp_started = Instant::now();
                        let (relation, state_probes, s3_calls) = extract(
                            &gf,
                            &fast,
                            &basis,
                            &solver,
                            &index,
                            &base,
                            Some(relation_target),
                            relation_hash as usize,
                        );
                        let extraction_ms = pdp_started.elapsed().as_secs_f64() * 1000.0;
                        (
                            relation_scalar,
                            relation,
                            state_probes,
                            s3_calls,
                            extraction_ms,
                        )
                    })
                })
                .collect();
            handles
                .into_iter()
                .map(|handle| handle.join().expect("relation worker panicked"))
                .collect::<Vec<_>>()
        });
        rank_pdp_wall_ms += batch_pdp_started.elapsed().as_secs_f64() * 1000.0;

        for (relation_scalar, relation, state_probes, s3_calls, extraction_ms) in batch_results {
            rank_attempts_completed += 1;
            rank_state_probes += state_probes;
            rank_target_s3_calls += s3_calls;
            let relation_check_ms = relation
                .as_ref()
                .map(|found| found.relation_check_ms)
                .unwrap_or(0.0);
            rank_relation_check_ms += relation_check_ms;
            rank_pdp_ms += (extraction_ms - relation_check_ms).max(0.0);

            let Some(relation) = relation else {
                rank_failures += 1;
                continue;
            };
            rank_verified_relations += 1;
            let matrix_started = Instant::now();
            let row = relation_row(&base, &relation, relation_scalar, r);
            rank_matrix_build_ms += matrix_started.elapsed().as_secs_f64() * 1000.0;
            let la_started = Instant::now();
            let new_rank = echelon.insert(row);
            rank_linear_algebra_ms += la_started.elapsed().as_secs_f64() * 1000.0;
            if new_rank {
                rank_new_rows += 1;
            } else {
                rank_dependent_rows += 1;
            }
            rank_witnesses.push(json!({
                "relation_scalar": relation_scalar,
                "point_indices": relation.point_indices,
                "x_codes": relation.x_codes,
                "state_probes": state_probes,
                "target_s3_calls": s3_calls,
                "partner_probes": relation.probes,
                "rank_gain": new_rank
            }));
            if new_rank && target_span_value.is_none() {
                if let Some(coefficients) = &target_coefficients {
                    let span_started = Instant::now();
                    target_span_value = echelon.span_value(coefficients);
                    target_span_check_ms += span_started.elapsed().as_secs_f64() * 1000.0;
                    target_span_checks += 1;
                    if target_span_value.is_some() {
                        target_span_relation_prefix = Some(rank_verified_relations);
                        target_span_attempt_prefix = Some(rank_attempts_completed);
                    }
                }
            }
        }
    }
    let rank_collection_ms = rank_started.elapsed().as_secs_f64() * 1000.0;
    let rank_complete = echelon.rank == base.columns;
    let final_la_started = Instant::now();
    let logs = if rank_complete {
        Some(echelon.solve())
    } else {
        None
    };
    let final_linear_algebra_ms = final_la_started.elapsed().as_secs_f64() * 1000.0;

    let log_certificate_started = Instant::now();
    if let Some(logs) = &logs {
        for (column, representative) in representatives.iter().enumerate() {
            let [x, y] = representative.expect("representative point");
            assert_eq!(
                fast.scalar_mul(generator, &BigUint::from(logs[column])),
                Some((x, y)),
                "recovered base log must replay"
            );
        }
    }
    let log_certificate_ms = log_certificate_started.elapsed().as_secs_f64() * 1000.0;
    let descent_started = Instant::now();
    let recovered = target_span_value.or_else(|| {
        target_relation.as_ref().and_then(|relation| {
            logs.as_ref().map(|logs| {
                relation.point_indices.iter().fold(0u64, |acc, &index| {
                    let (column, coefficient) = base.labels[index];
                    (acc + mulmod(coefficient, logs[column], r)) % r
                })
            })
        })
    });
    let target_descent_work_ms = target_span_check_ms
        + descent_started.elapsed().as_secs_f64() * 1000.0
        + rank_query_generation_ms
        + rank_matrix_build_ms
        + rank_linear_algebra_ms
        + final_linear_algebra_ms
        + log_certificate_ms;
    let recovery_check_started = Instant::now();
    let verified = recovered.map(|d| fast.scalar_mul(generator, &BigUint::from(d)) == target);
    let target_recovery_check_ms = recovery_check_started.elapsed().as_secs_f64() * 1000.0;
    let target_query_ms = target_validation_ms + target_query_hash_ms;
    let cold_after_launch_ms = cold_started.elapsed().as_secs_f64() * 1000.0;
    let online_elapsed_ms = target_online_started.elapsed().as_secs_f64() * 1000.0;
    // Charge the parallel relation-collection wall interval to target PDP;
    // exact checks inside that interval are retained as worker-time diagnostics.
    // Assign only the remaining serial wall interval to descent so the exclusive
    // phase costs sum exactly to the charged online interval.
    let target_pdp_charged_ms = target_pdp_ms + rank_pdp_wall_ms;
    let target_descent_charged_ms = (online_elapsed_ms
        - target_query_ms
        - target_pdp_charged_ms
        - target_relation_check_ms
        - target_recovery_check_ms)
        .max(0.0);
    let online_phase_sum_ms = target_query_ms
        + target_pdp_charged_ms
        + target_relation_check_ms
        + target_descent_charged_ms
        + target_recovery_check_ms;
    assert!((online_phase_sum_ms - online_elapsed_ms).abs() < 0.02);

    let record = json!({
        "kind":"unknown_log_orbit_slice_ic_run",
        "schema_version":"1.0",
        "n":n, "a":a, "subgroup_order":r,
        "relation_seed":relation_seed,
        "factor_base_scan_start_x":1,
        "factor_base_scanned_x":scanned_x,
        "orbit_columns":base.columns,
        "factor_base_points":base.points.len(),
        "factor_base_digest":base_hash,
        "regular_states":index.states.len(),
        "root_table_entries":index.table.len,
        "root_table_slots":index.table.slots,
        "root_table_shards":64,
        "root_table_input_entries_per_shard":index.table.input_entries_per_shard,
        "root_table_slots_per_shard":index.table.slots_per_shard,
        "index_build_workers":relation_workers,
        "target":target.map(|(x,y)| [x,y]),
        "orientation_policy":"one target-seeded pseudorandom global Frobenius shift per S3 state",
        "rank_attempt_limit":max_relation_attempts,
        "relation_collection_workers":relation_workers,
        "relation_collection_batching":"fixed-size batches; stop after the first completed batch for which the target coefficient vector lies in the verified relation row space; if the target decomposition is unavailable, fall back to full rank",
        "rank_attempts":rank_attempts,
        "rank_attempts_completed":rank_attempts_completed,
        "rank_failures":rank_failures,
        "rank_verified_relations":rank_verified_relations,
        "rank_new_rows":rank_new_rows,
        "rank_dependent_rows":rank_dependent_rows,
        "rank":echelon.rank,
        "rank_complete":rank_complete,
        "target_span_stop_relation_prefix":target_span_relation_prefix,
        "target_span_stop_attempt_prefix":target_span_attempt_prefix,
        "target_span_checks":target_span_checks,
        "target_span_recovered_scalar":target_span_value,
        "rank_state_probes":rank_state_probes,
        "rank_target_s3_calls":rank_target_s3_calls,
        "rank_relation_witnesses":rank_witnesses,
        "solved_base_logs":logs,
        "target_relation_found":target_relation.is_some(),
        "target_relation_indices":target_relation.as_ref().map(|relation| relation.point_indices),
        "target_relation_probes":target_relation.as_ref().map(|relation| relation.probes),
        "target_state_probes":target_state_probes,
        "target_s3_calls":target_s3_calls,
        "recovered_scalar":recovered,
        "group_verified":verified,
        "timing_ms":{
            "curve_setup_and_checks":curve_setup_ms,
            "factor_base_construct":base_build_ms,
            "factor_base_digest":base_digest_ms,
            "normal_basis_and_selftest":basis_ms,
            "representative_x_conversion":representative_x_ms,
            "index_build":index_ms,
            "index_state_generation":index_state_generation_ms,
            "index_shifted_points_generation":index_shifted_generation_ms,
            "index_state_merge":index_state_merge_ms,
            "index_root_scatter_parallel":index_root_scatter_ms,
            "index_root_shard_insert_parallel":index_root_shard_insert_ms,
            "index_unattributed_overhead":index_unattributed_overhead_ms,
            "rank_query_generation":rank_query_generation_ms,
            "rank_pdp":rank_pdp_ms,
            "rank_pdp_worker_time_sum":rank_pdp_ms,
            "rank_pdp_wall":rank_pdp_wall_ms,
            "rank_relation_check":rank_relation_check_ms,
            "rank_matrix_build":rank_matrix_build_ms,
            "rank_linear_algebra_incremental":rank_linear_algebra_ms,
            "rank_linear_algebra_final":final_linear_algebra_ms,
            "rank_collection_total":rank_collection_ms,
            "base_log_certificate":log_certificate_ms,
            "reusable_setup_total":reusable_setup_ms,
            "setup_phase_sum":setup_charged_subphases_ms + setup_timer_boundary_residual_ms,
            "setup_timer_boundary_residual":setup_timer_boundary_residual_ms,
            "target_query":target_query_ms,
            "target_point_validation":target_validation_ms,
            "target_query_hash":target_query_hash_ms,
            "target_pdp":target_pdp_ms,
            "target_pdp_charged":target_pdp_charged_ms,
            "target_relation_check":target_relation_check_ms,
            "target_descent_work_diagnostic":target_descent_work_ms,
            "target_descent":target_descent_charged_ms,
            "target_recovery_check":target_recovery_check_ms,
            "target_online_after_reusable_setup":online_elapsed_ms,
            "target_online_phase_sum":online_phase_sum_ms,
            "cold_after_launch":cold_after_launch_ms
        },
        "peak_rss_bytes":peak_rss_bytes(),
        "threads":1,
        "rank_stage":"random known-scalar subgroup queries; stop when target coefficient vector lies in relation row space, otherwise fallback to full rank",
        "linear_algebra":"incremental Gaussian elimination modulo subgroup order",
        "target_count":1
    });
    let _process_after_launch_ms = process_started.elapsed().as_secs_f64() * 1000.0;
    writeln!(out, "{record}").unwrap();
    println!("{record}");

    if let Ok(path) = std::env::var("KIC_DUMP_BASE") {
        let dump = json!({
            "kind":"unknown_log_orbit_factor_base",
            "n":n,"a":a,"subgroup_order":r,
            "factor_base_scan_start_x":1,"factor_base_scanned_x":scanned_x,
            "orbit_columns":base.columns,"base_hash":base_hash,
            "representative_points":representatives.iter().map(|point| point.map(|[x,y]| [x,y])).collect::<Vec<_>>(),
            "factor_base_point_coordinates":base.points.iter().map(|p| p.map(|(x,y)| [x,y])).collect::<Vec<_>>(),
            "factor_base_point_labels":base.labels
        });
        std::fs::write(path, format!("{dump}\n")).expect("write base dump");
    }
}

#[cfg(test)]
mod pair_root_tests {
    use super::*;

    #[test]
    fn shared_inversion_preserves_both_ordered_s3_answers() {
        for n in [13, 53] {
            let curve = KoblitzCurve::new(0, n).expect("Koblitz test curve");
            let gf = Gf2::new(&curve.curve.irreducible);
            let basis = NormalBasis::new(&gf);
            let solver = S3Solver::new(&gf, gf.from_element(&curve.curve.b));
            let mut seed = 0x5A17_2026_1006_0001u64;
            for i in 0..4096 {
                let right = splitmix64(&mut seed) & basis.mask;
                let mut left = [
                    splitmix64(&mut seed) & basis.mask,
                    splitmix64(&mut seed) & basis.mask,
                ];
                // Exercise the zero and diagonal fallbacks as well as the
                // ordinary two-inversion path.
                if i % 16 == 0 {
                    left[0] = right;
                }
                if i % 16 == 1 {
                    left[1] = 0;
                }
                let expected = [
                    solver.roots(&gf, &basis, left[0], right),
                    solver.roots(&gf, &basis, left[1], right),
                ];
                assert_eq!(solver.roots_pair(&gf, &basis, left, right), expected);
            }
        }
    }
}

#[cfg(test)]
mod parallel_index_tests {
    use super::*;

    #[test]
    fn sharded_index_matches_serial_root_map_and_worker_order() {
        let curve = KoblitzCurve::new(0, 13).expect("N13 Koblitz test curve");
        let gf = Gf2::new(&curve.curve.irreducible);
        let b = gf.from_element(&curve.curve.b);
        let basis = NormalBasis::new(&gf);
        let solver = S3Solver::new(&gf, b);
        let reps: Vec<u64> = (1..=9).collect();

        let serial = build_index(&gf, &basis, &solver, &reps, 1).0;
        let parallel = build_index(&gf, &basis, &solver, &reps, 4).0;

        assert!(!serial.states.is_empty());
        assert_eq!(serial.states.len(), parallel.states.len());
        for (left, right) in serial.states.iter().zip(&parallel.states) {
            assert_eq!(left.left, right.left);
            assert_eq!(left.right, right.right);
            assert_eq!(left.relative, right.relative);
            assert_eq!(left.normal_roots, right.normal_roots);
        }
        assert_eq!(serial.table.len, parallel.table.len);
        assert_eq!(serial.table.slots, parallel.table.slots);
        for (left, right) in serial.table.shards.iter().zip(&parallel.table.shards) {
            assert_eq!(left.slots, right.slots);
        }

        let mut serial_root_map = HashMap::new();
        for state in &serial.states {
            for &root in &state.normal_roots {
                let (canonical, shift) = basis.canonical(root);
                serial_root_map
                    .entry(canonical)
                    .or_insert_with(|| pack(state.left, state.right, state.relative, shift));
            }
        }
        assert_eq!(serial.table.len, serial_root_map.len());
        for (key, value) in serial_root_map {
            assert_eq!(serial.table.get(key), Some(value));
            assert_eq!(parallel.table.get(key), Some(value));
        }
        assert_eq!(serial.shifted, parallel.shifted);
    }
}

#[cfg(test)]
mod n53_shard_capacity_control {
    use super::*;

    #[test]
    fn exact_n53_base_builds_sharded_index_and_reports_distribution() {
        let curve = KoblitzCurve::new(0, 53).expect("N53 Koblitz curve");
        let r = curve.subgroup_order.to_u64().unwrap();
        let fast = FastBinaryCurve::new(&curve.curve.irreducible, 0).unwrap();
        let gf = Gf2::new(&curve.curve.irreducible);
        let b = gf.from_element(&curve.curve.b);
        let basis = NormalBasis::new(&gf);
        let solver = S3Solver::new(&gf, b);
        let (_, _, representatives, _) = construct_base(&fast, &curve, b, 244, r);
        let rep_x: Vec<u64> = representatives
            .iter()
            .map(|point| point.expect("representative point")[0])
            .collect();

        let (index, _, _, _, _, _) = build_index(&gf, &basis, &solver, &rep_x, 14);
        assert_eq!(index.states.len(), 3_155_408);
        assert_eq!(index.table.len, 3_154_661);
        assert_eq!(index.table.slots_per_shard.len(), 64);
        assert_eq!(index.table.input_entries_per_shard.len(), 64);
        assert!(index
            .table
            .input_entries_per_shard
            .iter()
            .all(|&count| count > 0));
        eprintln!(
            "N53 shard input entries: {:?}; slots: {:?}",
            index.table.input_entries_per_shard, index.table.slots_per_shard
        );
    }
}
