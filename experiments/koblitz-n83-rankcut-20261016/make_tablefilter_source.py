#!/usr/bin/env python3
"""Derive the two-level root-table online producer from the probe-pipeline producer, exactly.

Input: `snapshots/r770/examples/koblitz_orbit_dlp_fast_online_logcache.rs`
(crypto 770f6a69 plus B's `ic_log_cache.patch`, restored and digest-checked
by `restore.py`).

1. `make_probepipe_source.py` is `claude/n83-probe-pipeline`'s
   `make_online_source.py` @ ddbb86a9c, verbatim (it imports
   `make_combined_source.py`, `claude/n83-combined`'s derivation, verbatim).
   Its text must hash to the probe-pipeline protocol's frozen
   `online_source_sha256` (`PROBEPIPE_SHA256` below), so step 2 starts from
   the exact producer that run 38822490448 measures.
2. `table_edits`: counted, exact string replacements in the wide module add
   a root-table layout chosen once per process by `KIC_ROOT_TABLE`:

   * `base` (default): the 32-byte-slot `RootTable128` (2^27 slots, 4 GiB),
     built and probed exactly as before. `KIC_PROBE_PIPELINE=off|prefetch`
     run `scan_state128` / `scan_state128_pipelined`, unchanged.
   * `compact`: `CompactRootTable128`, one 16-byte word per slot holding
     the whole 83-bit key, the four `pack` fields in 11 bits each and an
     occupied bit; same capacity, hash and linear-probe sequence as the base
     table, so the same key -> value map (2 GiB instead of 4). No filter.
   * `filter`: the compact table plus `RootFilter128`, a register-blocked
     Bloom filter (one 64-bit word per key, 5 bits set in it;
     2^`KIC_ROOT_FILTER_LOG2_BITS` bits, default 2^28 = 32 MiB) built from
     the compact table's keys after the table, timed separately in setup.
   * `filter_plant` (planted positive control): `filter`, plus, for every
     probe the filter rejects, a discarded lookup of the same key in the
     compact table (prefetched with the filter word), i.e. the big-table
     access the filter removes; such a lookup must find nothing
     (`planted_rejected_found` = 0, a further exactness check).

   The three new layouts run `scan_state128_filtered` (only with
   `KIC_PROBE_PIPELINE=prefetch`, `KIC_TARGET_CANON=lift`,
   `KIC_SCAN_ORDER=feistel` in the runtime dispatch): the probe pipeline's
   root batch and key order; every key is followed by a prefetch of its
   filter word (`compact`: of its home slot); then, in probe order, the
   filter test, and every survivor's home slot is prefetched; then the
   survivors in probe order get the exact compact-table lookup, lift and
   relation check, with the probe counter set to the survivor's position, so
   probes, relation and early return are those of the pipeline. A filter
   false positive only costs a lookup that misses. Per target the record
   adds `root_table`, `filter_passes` (survivors consumed) and
   `planted_rejected_found`; the summary adds the layout, its bytes and the
   filter build time.

The rank stage is unchanged (it needs the base table; the new layouts
require the verified cached factor-log table, as every arm runs). `--check`
regenerates and requires byte identity with the existing output.
"""

import argparse
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_probepipe_source as probepipe  # noqa: E402  (claude/n83-probe-pipeline, verbatim)

EXAMPLES = HERE / "snapshots" / "r770" / "examples"
SOURCE = probepipe.SOURCE
OUTPUT = EXAMPLES / "koblitz_orbit_dlp_fast_online_tablefilter.rs"
# protocol.json "sources.online_source_sha256" of claude/n83-probe-pipeline @ ddbb86a9c.
PROBEPIPE_SHA256 = "840b164885fc66644132f8b80efa9104f7421a7536795fd28ce085d6927c8947"
WIDE_START = probepipe.WIDE_START
WIDE_END = probepipe.WIDE_END
replace = probepipe.replace

HEAD_OLD = """// (software-pipelined root-table probes with prefetch).
"""
HEAD_NEW = HEAD_OLD + """// koblitz-n83-tablefilter-20261015: derived from the probe-pipeline
// producer by make_online_source.py; adds the KIC_ROOT_TABLE layout selector
// (16-byte exact slots and a TLB-resident blocked filter in front of them).
"""

SPLIT_OLD = """    root_calls: u64,
    skipped_symmetric_states: u64,
}
"""
SPLIT_NEW = """    root_calls: u64,
    skipped_symmetric_states: u64,
    filter_passes: u64,
    planted_found: u64,
}
"""

SCRATCH_OLD = """    struct StateScan128 {
        inputs: Vec<(u128, u128)>,
        batch: RootBatch128,
        keys: Vec<ProbeKey128>,
    }

    impl StateScan128 {
        fn new(n: u32) -> Self {
            let entries = 2 * n as usize;
            Self {
                inputs: Vec::with_capacity(entries),
                batch: RootBatch128::with_capacity(entries),
                keys: Vec::with_capacity(2 * entries),
            }
        }
    }
"""
SCRATCH_NEW = """    struct StateScan128 {
        inputs: Vec<(u128, u128)>,
        batch: RootBatch128,
        keys: Vec<ProbeKey128>,
        survivors: Vec<u32>,
    }

    impl StateScan128 {
        fn new(n: u32) -> Self {
            let entries = 2 * n as usize;
            Self {
                inputs: Vec::with_capacity(entries),
                batch: RootBatch128::with_capacity(entries),
                keys: Vec::with_capacity(2 * entries),
                survivors: Vec::with_capacity(2 * entries),
            }
        }
    }
"""

TABLE_ANCHOR = """    struct State128 {
"""
TABLE_CODE = r"""    // koblitz-n83-tablefilter-20261015: root-table layout selector
    // (KIC_ROOT_TABLE), read once when the index is built.
    const TABLE_BASE: u8 = 0;
    const TABLE_COMPACT: u8 = 1;
    const TABLE_FILTER: u8 = 2;
    const TABLE_FILTER_PLANT: u8 = 3;
    const TABLE_NAMES: [&str; 4] = ["base", "compact", "filter", "filter_plant"];

    fn root_table_from_env() -> u8 {
        match std::env::var("KIC_ROOT_TABLE").as_deref() {
            Err(_) | Ok("") | Ok("base") => TABLE_BASE,
            Ok("compact") => TABLE_COMPACT,
            Ok("filter") => TABLE_FILTER,
            Ok("filter_plant") => TABLE_FILTER_PLANT,
            Ok(other) => panic!("unknown KIC_ROOT_TABLE {other}"),
        }
    }

    const ROOT_FILTER_DEFAULT_LOG2_BITS: u32 = 28;

    fn root_filter_log2_bits_from_env() -> u32 {
        match std::env::var("KIC_ROOT_FILTER_LOG2_BITS").as_deref() {
            Err(_) | Ok("") => ROOT_FILTER_DEFAULT_LOG2_BITS,
            Ok(value) => {
                let bits: u32 = value.parse().expect("KIC_ROOT_FILTER_LOG2_BITS must be an integer");
                assert!((12..=34).contains(&bits), "KIC_ROOT_FILTER_LOG2_BITS out of range");
                bits
            }
        }
    }

    /// Hint the cache line at `address`. A prefetch never faults and changes
    /// no architectural state.
    #[inline(always)]
    fn prefetch_address<T>(address: *const T) {
        #[cfg(target_arch = "x86_64")]
        {
            // SAFETY: `_mm_prefetch` is a hint; it does not dereference
            // `address` architecturally and cannot fault. SSE is part of
            // the x86_64 baseline.
            #[allow(unused_unsafe)]
            unsafe {
                std::arch::x86_64::_mm_prefetch(address as *const i8, std::arch::x86_64::_MM_HINT_T0);
            }
        }
        #[cfg(not(target_arch = "x86_64"))]
        {
            let _ = address;
        }
    }

    const COMPACT_KEY_BITS: u32 = 83;
    const COMPACT_KEY_MASK: u128 = (1u128 << COMPACT_KEY_BITS) - 1;
    const COMPACT_FIELD_BITS: u32 = 11;
    const COMPACT_OCCUPIED: u128 = 1u128 << 127;

    /// Exact open-addressing `u128 -> u64` root table with one 16-byte word
    /// per slot: bits 0..83 hold the key (an 83-bit normal-basis word),
    /// bits 83..127 the four `pack` fields in 11 bits each, bit 127 marks
    /// an occupied slot; 0 is empty. Same capacity rule, hash and
    /// linear-probe sequence as `RootTable128`, so the same key -> value
    /// map in half the bytes. Out-of-range keys or fields panic on insert.
    struct CompactRootTable128 {
        slots: Vec<u128>,
        shift: u32,
        len: usize,
    }

    impl CompactRootTable128 {
        fn with_capacity(entries: usize) -> Self {
            let slots = (entries * 2).next_power_of_two().max(16);
            Self {
                slots: vec![0; slots],
                shift: 128 - slots.trailing_zeros(),
                len: 0,
            }
        }

        #[inline(always)]
        fn slot(&self, key: u128) -> usize {
            (key.wrapping_mul(0x9E37_79B9_7F4A_7C15_9E37_79B9_7F4A_7C15) >> self.shift) as usize
        }

        fn compress(value: u64) -> u128 {
            let mut packed = 0u128;
            for field in 0..4 {
                let part = (value >> (16 * field)) & 0xffff;
                assert!(part < 1 << COMPACT_FIELD_BITS, "compact root slot field overflow");
                packed |= (part as u128) << (COMPACT_KEY_BITS + COMPACT_FIELD_BITS * field);
            }
            packed
        }

        #[inline(always)]
        fn expand(word: u128) -> u64 {
            let mut value = 0u64;
            for field in 0..4 {
                let part = (word >> (COMPACT_KEY_BITS + COMPACT_FIELD_BITS * field)) as u64
                    & ((1u64 << COMPACT_FIELD_BITS) - 1);
                value |= part << (16 * field);
            }
            value
        }

        fn insert_if_absent(&mut self, key: u128, value: u64) {
            assert!(key <= COMPACT_KEY_MASK, "compact root slot key exceeds 83 bits");
            let word = COMPACT_OCCUPIED | Self::compress(value) | key;
            debug_assert_eq!(Self::expand(word), value);
            let mask = self.slots.len() - 1;
            let mut slot = self.slot(key);
            loop {
                let stored = self.slots[slot];
                if stored == 0 {
                    self.slots[slot] = word;
                    self.len += 1;
                    return;
                }
                if stored & COMPACT_KEY_MASK == key {
                    return;
                }
                slot = (slot + 1) & mask;
            }
        }

        #[inline(always)]
        fn get(&self, key: u128) -> Option<u64> {
            if key > COMPACT_KEY_MASK {
                // Never inserted (insert asserts the width).
                return None;
            }
            let mask = self.slots.len() - 1;
            let mut slot = self.slot(key);
            loop {
                let stored = self.slots[slot];
                if stored == 0 {
                    return None;
                }
                if stored & COMPACT_KEY_MASK == key {
                    return Some(Self::expand(stored));
                }
                slot = (slot + 1) & mask;
            }
        }

        #[inline(always)]
        fn prefetch(&self, key: u128) {
            prefetch_address(self.slots.as_ptr().wrapping_add(self.slot(key)));
        }

        fn bytes(&self) -> usize {
            self.slots.len() * std::mem::size_of::<u128>()
        }
    }

    const ROOT_FILTER_HASHES: u32 = 5;

    /// Register-blocked Bloom filter over the root-table keys: one 64-bit
    /// word per key, chosen by the top bits of a 64-bit hash, with
    /// `ROOT_FILTER_HASHES` bits from its low 6-bit groups. No false
    /// negatives: every inserted key tests positive.
    struct RootFilter128 {
        words: Vec<u64>,
        word_shift: u32,
        log2_bits: u32,
    }

    impl RootFilter128 {
        fn new(log2_bits: u32) -> Self {
            let log2_words = log2_bits - 6;
            assert!(log2_words + 6 * ROOT_FILTER_HASHES <= 64, "root filter hash bits overlap");
            Self {
                words: vec![0; 1usize << log2_words],
                word_shift: 64 - log2_words,
                log2_bits,
            }
        }

        #[inline(always)]
        fn hash(key: u128) -> u64 {
            mix_root_bloom(key as u64 ^ mix_root_bloom((key >> 64) as u64 ^ 0x2545_F491_4F6C_DD1D))
        }

        #[inline(always)]
        fn locate(&self, key: u128) -> (usize, u64) {
            let hash = Self::hash(key);
            let mut mask = 0u64;
            for index in 0..ROOT_FILTER_HASHES {
                mask |= 1u64 << ((hash >> (6 * index)) & 63);
            }
            ((hash >> self.word_shift) as usize, mask)
        }

        fn insert(&mut self, key: u128) {
            let (word, mask) = self.locate(key);
            self.words[word] |= mask;
        }

        #[inline(always)]
        fn contains(&self, key: u128) -> bool {
            let (word, mask) = self.locate(key);
            self.words[word] & mask == mask
        }

        #[inline(always)]
        fn prefetch(&self, key: u128) {
            let word = (Self::hash(key) >> self.word_shift) as usize;
            prefetch_address(self.words.as_ptr().wrapping_add(word));
        }

        fn bytes(&self) -> usize {
            self.words.len() * std::mem::size_of::<u64>()
        }

        fn ones_fraction(&self) -> f64 {
            let ones: u64 = self.words.iter().map(|word| word.count_ones() as u64).sum();
            ones as f64 / (self.words.len() as f64 * 64.0)
        }
    }

"""

INDEX_OLD = """    struct Index128 {
        states: Vec<State128>,
        table: RootTable128,
        shifted: Vec<Vec<u128>>,
    }
"""
INDEX_NEW = """    struct Index128 {
        states: Vec<State128>,
        table: RootTable128,
        shifted: Vec<Vec<u128>>,
        root_table: u8,
        compact: Option<CompactRootTable128>,
        filter: Option<RootFilter128>,
        filter_build_ms: f64,
    }

    impl Index128 {
        /// Distinct root keys stored, in whichever layout this index uses.
        fn root_entries(&self) -> usize {
            self.compact.as_ref().map_or(self.table.len, |compact| compact.len)
        }

        fn root_table_bytes(&self) -> usize {
            self.compact.as_ref().map_or(
                self.table.slots.len() * std::mem::size_of::<(u128, u64)>(),
                CompactRootTable128::bytes,
            )
        }
    }
"""

BUILD_SIG_OLD = """    fn build_index128(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
    ) -> Index128 {
        let n = gf.n as usize;
"""
BUILD_SIG_NEW = """    fn build_index128(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
    ) -> Index128 {
        build_index128_mode(
            gf,
            basis,
            solver,
            reps,
            root_table_from_env(),
            root_filter_log2_bits_from_env(),
        )
    }

    fn build_index128_mode(
        gf: &Gf2_128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        reps: &[u128],
        root_table: u8,
        filter_log2_bits: u32,
    ) -> Index128 {
        let n = gf.n as usize;
"""

BUILD_TABLE_OLD = """        let mut table = RootTable128::with_capacity(states.len() * 2);
        for state in &states {
            for &root in &state.normal_roots {
                let (canonical, shift) = basis.canonical_selected(root);
                table.insert_if_absent(
                    canonical,
                    pack(state.left, state.right, state.relative, shift),
                );
            }
        }
        Index128 {
            states,
            table,
            shifted,
        }
    }
"""
BUILD_TABLE_NEW = """        let mut table = RootTable128::with_capacity(if root_table == TABLE_BASE {
            states.len() * 2
        } else {
            0
        });
        let mut compact = None;
        let mut filter = None;
        let mut filter_build_ms = 0.0;
        if root_table == TABLE_BASE {
            for state in &states {
                for &root in &state.normal_roots {
                    let (canonical, shift) = basis.canonical_selected(root);
                    table.insert_if_absent(
                        canonical,
                        pack(state.left, state.right, state.relative, shift),
                    );
                }
            }
        } else {
            // The same inserts, in the same order, into the 16-byte layout.
            let mut slots = CompactRootTable128::with_capacity(states.len() * 2);
            for state in &states {
                for &root in &state.normal_roots {
                    let (canonical, shift) = basis.canonical_selected(root);
                    slots.insert_if_absent(
                        canonical,
                        pack(state.left, state.right, state.relative, shift),
                    );
                }
            }
            if root_table != TABLE_COMPACT {
                let filter_started = Instant::now();
                let mut bloom = RootFilter128::new(filter_log2_bits);
                for &word in &slots.slots {
                    if word != 0 {
                        bloom.insert(word & COMPACT_KEY_MASK);
                    }
                }
                filter_build_ms = ms(filter_started.elapsed());
                filter = Some(bloom);
            }
            compact = Some(slots);
        }
        Index128 {
            states,
            table,
            shifted,
            root_table,
            compact,
            filter,
            filter_build_ms,
        }
    }
"""

SCAN_ANCHOR = """    /// `P` picks the target scan's probe loop at compile time.
"""
SCAN_CODE = r"""    // koblitz-n83-tablefilter-20261015: the scan loops of the new layouts.
    const PIPE_COMPACT: u8 = 2;
    const PIPE_FILTER: u8 = 3;
    const PIPE_FILTER_PLANT: u8 = 4;

    /// [`scan_state128_pipelined`] over the two-level root table. The same
    /// root batch and the same keys in the same order (shift outer, stored
    /// root inner, solver partner order); each key is followed by a
    /// prefetch of its filter word (`PIPE_COMPACT`: of its home slot). Then,
    /// in probe order, the filter test; each survivor's home slot is
    /// prefetched. Then the survivors, in probe order, get the exact
    /// compact-table lookup, lift and relation check; the probe counter is
    /// set to the survivor's position, so the probes, relation and early
    /// return are the pipeline's. The filter has no false negatives, so a
    /// rejected key is absent from the table; a false positive only costs a
    /// lookup that misses. `PIPE_FILTER_PLANT` also looks every rejected key
    /// up in the compact table (prefetched with its filter word) and
    /// discards the result, which must be `None`.
    #[inline(always)]
    #[allow(clippy::too_many_arguments)]
    fn scan_state128_filtered<const C: u8, const P: u8>(
        gf: &Gf2_128,
        fast: &FastBinaryCurve128,
        basis: &NormalBasis128,
        solver: &S3Solver128,
        index: &Index128,
        base: &Base128,
        target: FastPoint128,
        target_x: u128,
        state: &State128,
        scan: &mut StateScan128,
        probes: &mut u64,
        clock: &mut PhaseClock,
        split: &mut ExtractSplit,
    ) -> Option<Relation128> {
        let n = gf.n;
        let compact = index.compact.as_ref().expect("the compact root table");
        let filter = if P == PIPE_COMPACT {
            None
        } else {
            Some(index.filter.as_ref().expect("the root filter"))
        };
        scan.inputs.clear();
        for shift in 0..n {
            for &normal_root in &state.normal_roots {
                let absolute = basis.to_poly.apply(basis.rotate(normal_root, shift));
                scan.inputs.push((absolute, target_x));
            }
        }
        scan.batch.solve(gf, basis, solver, &scan.inputs);
        split.root_calls += scan.inputs.len() as u64;
        scan.keys.clear();
        for (candidate, result) in scan.batch.results.iter().enumerate() {
            let Some(partners) = *result else {
                continue;
            };
            for partner in partners {
                let (canonical, partner_shift) =
                    target_canonical::<C>(basis, basis.to_normal.apply(partner));
                match filter {
                    Some(filter) => {
                        filter.prefetch(canonical);
                        if P == PIPE_FILTER_PLANT {
                            compact.prefetch(canonical);
                        }
                    }
                    None => compact.prefetch(canonical),
                }
                scan.keys.push(ProbeKey128 {
                    canonical,
                    partner,
                    partner_shift,
                    candidate: candidate as u32,
                });
            }
        }
        scan.survivors.clear();
        let mut planted_found = 0u64;
        for (position, key) in scan.keys.iter().enumerate() {
            match filter {
                Some(filter) => {
                    if filter.contains(key.canonical) {
                        compact.prefetch(key.canonical);
                        scan.survivors.push(position as u32);
                    } else if P == PIPE_FILTER_PLANT {
                        planted_found += black_box(compact.get(black_box(key.canonical))).is_some() as u64;
                    }
                }
                None => scan.survivors.push(position as u32),
            }
        }
        split.planted_found += planted_found;
        let first = *probes;
        let roots_per_shift = state.normal_roots.len();
        for &position in &scan.survivors {
            let key = &scan.keys[position as usize];
            *probes = first + position as u64 + 1;
            split.filter_passes += 1;
            let Some(value) = compact.get(key.canonical) else {
                continue;
            };
            let candidate = key.candidate as usize;
            let shift = candidate / roots_per_shift;
            let left_x = index.shifted[state.left as usize][shift];
            let right_x =
                index.shifted[state.right as usize][(shift + state.relative as usize) % n as usize];
            let absolute = scan.inputs[candidate].0;
            let partner = key.partner;
            let partner_shift = key.partner_shift;
            let (left2, right2, relative2, stored_shift) = unpack(value);
            let left_shift2 = ((stored_shift + n - partner_shift) % n) as usize;
            let right_shift2 = (left_shift2 + relative2) % n as usize;
            let codes = [
                left_x,
                right_x,
                index.shifted[left2][left_shift2],
                index.shifted[right2][right_shift2],
            ];
            split.pdp += clock.lap();
            let lifted = lift128(fast, base, &codes, target);
            split.relation_check += clock.lap();
            split.relation_checks += 1;
            if let Some(point_indices) = lifted {
                return Some(Relation128 {
                    point_indices,
                    x_codes: codes,
                    intermediates: [absolute, partner],
                    probes: *probes,
                });
            }
        }
        *probes = first + scan.keys.len() as u64;
        None
    }

    #[cfg(test)]
    mod table_filter_tests {
        use super::*;

        fn small_instance(
            columns: usize,
        ) -> (FastBinaryCurve128, Gf2_128, NormalBasis128, S3Solver128, Base128, Vec<u128>) {
            let curve = KoblitzCurve::new(1, 83).unwrap();
            let fast = FastBinaryCurve128::new(&curve.curve.irreducible, 1).unwrap();
            let gf = Gf2_128::new(&curve.curve.irreducible);
            let b = gf.from_element(&curve.curve.b);
            let r = curve.subgroup_order.to_u64().unwrap();
            let (points, labels, reps, _) = construct_base128(&fast, &curve, b, columns, r);
            let mut by_x: HashMap<u128, Vec<usize>> = HashMap::new();
            for (i, point) in points.iter().enumerate() {
                by_x.entry(point.unwrap().0).or_default().push(i);
            }
            let reps: Vec<u128> = reps.iter().map(|p| p.unwrap()[0]).collect();
            let base = Base128 { points, labels, by_x, columns };
            let basis = NormalBasis128::new(&gf);
            let solver = S3Solver128::new(&gf, b);
            (fast, gf, basis, solver, base, reps)
        }

        fn mix(value: u64) -> u64 {
            mix_root_bloom(value.wrapping_add(0x9E37_79B9_7F4A_7C15))
        }

        #[test]
        fn compact_slot_round_trips_every_field_and_rejects_overflow() {
            for value in [0u64, pack(599, 599, 82, 82), pack(1, 2, 3, 4), pack(2047, 2047, 2047, 2047)] {
                let word = COMPACT_OCCUPIED | CompactRootTable128::compress(value) | COMPACT_KEY_MASK;
                assert_eq!(CompactRootTable128::expand(word), value);
                assert_eq!(word & COMPACT_KEY_MASK, COMPACT_KEY_MASK);
            }
            assert!(std::panic::catch_unwind(|| CompactRootTable128::compress(pack(2048, 0, 0, 0))).is_err());
            let mut table = CompactRootTable128::with_capacity(8);
            assert!(std::panic::catch_unwind(move || table.insert_if_absent(1u128 << 83, 0)).is_err());
        }

        #[test]
        fn layouts_store_the_same_map_and_the_filter_has_no_false_negatives() {
            let (_, gf, basis, solver, _, reps) = small_instance(9);
            let reference = build_index128_mode(&gf, &basis, &solver, &reps, TABLE_BASE, 28);
            assert!(reference.compact.is_none() && reference.filter.is_none());
            for (mode, bits) in [(TABLE_COMPACT, 28), (TABLE_FILTER, 28), (TABLE_FILTER, 14), (TABLE_FILTER_PLANT, 16)] {
                let index = build_index128_mode(&gf, &basis, &solver, &reps, mode, bits);
                assert_eq!(index.states.len(), reference.states.len());
                assert_eq!(index.root_entries(), reference.table.len);
                assert_eq!(index.table.len, 0);
                let compact = index.compact.as_ref().unwrap();
                assert_eq!(compact.slots.len(), reference.table.slots.len());
                assert_eq!(index.root_table_bytes() * 2, reference.root_table_bytes());
                for &(key, value) in &reference.table.slots {
                    if key != u128::MAX {
                        assert_eq!(compact.get(key), Some(value));
                        if let Some(filter) = &index.filter {
                            assert!(filter.contains(key), "filter false negative");
                        }
                    }
                }
                let mut rejected = 0u64;
                for trial in 0..200_000u64 {
                    let key = ((mix(trial) as u128) << 64 | mix(!trial) as u128) & basis.mask;
                    let expected = reference.table.get(key);
                    assert_eq!(compact.get(key), expected);
                    if let Some(filter) = &index.filter {
                        if !filter.contains(key) {
                            rejected += 1;
                            assert_eq!(expected, None);
                        }
                    }
                }
                assert_eq!(compact.get(1u128 << 100), None);
                if mode != TABLE_COMPACT {
                    assert!(rejected > 0);
                }
            }
        }

        #[test]
        fn every_layout_finds_the_pipelines_relation_with_the_same_probes() {
            let (fast, gf, basis, solver, base, reps) = small_instance(9);
            let reference = build_index128_mode(&gf, &basis, &solver, &reps, TABLE_BASE, 28);
            let compact = build_index128_mode(&gf, &basis, &solver, &reps, TABLE_COMPACT, 28);
            let filtered = build_index128_mode(&gf, &basis, &solver, &reps, TABLE_FILTER, 28);
            let tiny = build_index128_mode(&gf, &basis, &solver, &reps, TABLE_FILTER, 13);
            let planted = build_index128_mode(&gf, &basis, &solver, &reps, TABLE_FILTER_PLANT, 15);
            let mut seed = 0x0123_4567_89AB_CDEFu64;
            let mut false_positive_probes = 0u64;
            let mut solved = 0usize;
            for trial in 0..24u64 {
                let mut pick = || {
                    seed = mix(seed ^ trial);
                    (seed % base.points.len() as u64) as usize
                };
                let mut target = base.points[pick()];
                for _ in 0..3 {
                    target = fast.add(target, base.points[pick()]);
                }
                let Some((tx, ty)) = target else { continue };
                let start = mix((tx ^ ty.rotate_left(29)) as u64) as usize;
                macro_rules! run {
                    ($c:expr, $o:expr, $p:expr, $index:expr) => {{
                        let mut clock = PhaseClock::start();
                        let mut split = ExtractSplit::default();
                        let relation = extract128::<{ $c }, { $o }, { $p }>(
                            &gf, &fast, &basis, &solver, $index, &base, target, start, &mut clock,
                            &mut split,
                        );
                        (relation.map(|r| (r.point_indices, r.x_codes, r.intermediates, r.probes)),
                         split.filter_passes, split.planted_found, split.relation_checks)
                    }};
                }
                macro_rules! compare {
                    ($c:expr, $o:expr) => {{
                        let (want, _, _, checks) = run!($c, $o, PIPE_PREFETCH, &reference);
                        let (off, _, _, _) = run!($c, $o, PIPE_OFF, &reference);
                        assert_eq!(want, off);
                        let want = want.expect("a planted four-point target decomposes");
                        let probes = want.3;
                        for (got, passes, found, got_checks) in [
                            run!($c, $o, PIPE_COMPACT, &compact),
                            run!($c, $o, PIPE_FILTER, &filtered),
                            run!($c, $o, PIPE_FILTER, &tiny),
                            run!($c, $o, PIPE_FILTER_PLANT, &planted),
                        ] {
                            assert_eq!(got, Some(want), "relation and probes differ");
                            assert_eq!(found, 0, "a rejected key was found in the table");
                            assert_eq!(got_checks, checks);
                            assert!(passes >= checks && passes <= probes);
                        }
                        let (_, tiny_passes, _, _) = run!($c, $o, PIPE_FILTER, &tiny);
                        false_positive_probes += tiny_passes - checks;
                        solved += 1;
                    }};
                }
                compare!(CANON_LIFT, ORDER_FEISTEL);
                compare!(CANON_LIFT, ORDER_LEFT_MAJOR);
                compare!(CANON_FULL, ORDER_FEISTEL);
            }
            assert!(solved >= 60);
            assert!(false_positive_probes > 0, "the tiny filter should produce false positives");
        }
    }

"""

SELECT_OLD = """        if P == PIPE_PREFETCH {
            scan_state128_pipelined::<C>(
"""
SELECT_NEW = """        if P >= PIPE_COMPACT {
            scan_state128_filtered::<C, P>(
                gf, fast, basis, solver, index, base, target, target_x, state, scan, probes, clock,
                split,
            )
        } else if P == PIPE_PREFETCH {
            scan_state128_pipelined::<C>(
"""

RANK_OLD = """        let cached_log_table = super::log_cache::input_path();
"""
RANK_NEW = RANK_OLD + """        assert!(
            index.root_table == TABLE_BASE || cached_log_table.is_some(),
            "KIC_ROOT_TABLE other than base needs the verified cached factor-log table"
        );
"""

LOOP_OLD = """        let (probe_pipeline, probe_pipeline_name) = probe_pipeline_from_env();
"""
LOOP_NEW = LOOP_OLD + """        let root_table_name = TABLE_NAMES[index.root_table as usize];
        assert!(
            index.root_table == TABLE_BASE
                || (probe_pipeline == PIPE_PREFETCH
                    && target_canon == CANON_LIFT
                    && scan_order == ORDER_FEISTEL),
            "KIC_ROOT_TABLE other than base runs with prefetch, lift and feistel"
        );
        let table_loop = match index.root_table {
            TABLE_COMPACT => PIPE_COMPACT,
            TABLE_FILTER => PIPE_FILTER,
            TABLE_FILTER_PLANT => PIPE_FILTER_PLANT,
            _ => PIPE_OFF,
        };
"""

RELATION_OLD = """            let relation = match target_canon {
"""
RELATION_NEW = """            macro_rules! table_extract {
                ($p:expr) => {
                    extract128::<CANON_LIFT, ORDER_FEISTEL, { $p }>(
                        &gf, &fast, &basis, &solver, &index, &base, target, start,
                        &mut clock, &mut split,
                    )
                };
            }
            let relation = if table_loop != PIPE_OFF {
                match table_loop {
                    PIPE_COMPACT => table_extract!(PIPE_COMPACT),
                    PIPE_FILTER => table_extract!(PIPE_FILTER),
                    _ => table_extract!(PIPE_FILTER_PLANT),
                }
            } else { match target_canon {
"""
RELATION_END_OLD = """                _ => target_extract!(CANON_VERIFY),
            };
"""
RELATION_END_NEW = """                _ => target_extract!(CANON_VERIFY),
            } };
"""

RECORD_OLD = """                "skipped_symmetric_states":split.skipped_symmetric_states,
"""
RECORD_NEW = RECORD_OLD + """                "root_table":root_table_name,
                "filter_passes":split.filter_passes,
                "planted_rejected_found":split.planted_found,
"""

SUMMARY_OLD = """            "root_table_entries":index.table.len,
"""
SUMMARY_NEW = """            "root_table_entries":index.root_entries(),
            "root_table":root_table_name,
            "root_table_slots":index.compact.as_ref().map_or(index.table.slots.len(), |c| c.slots.len()),
            "root_table_bytes":index.root_table_bytes(),
            "root_filter_bytes":index.filter.as_ref().map_or(0, RootFilter128::bytes),
            "root_filter_log2_bits":index.filter.as_ref().map(|f| f.log2_bits),
            "root_filter_hashes":index.filter.as_ref().map(|_| ROOT_FILTER_HASHES),
            "root_filter_ones_fraction":index.filter.as_ref().map(RootFilter128::ones_fraction),
            "root_filter_build_ms":index.filter_build_ms,
"""


def table_edits(head, wide):
    head = replace(head, HEAD_OLD, HEAD_NEW)
    head = replace(head, SPLIT_OLD, SPLIT_NEW)
    wide = replace(wide, SCRATCH_OLD, SCRATCH_NEW)
    wide = replace(wide, TABLE_ANCHOR, TABLE_CODE + TABLE_ANCHOR)
    wide = replace(wide, INDEX_OLD, INDEX_NEW)
    wide = replace(wide, BUILD_SIG_OLD, BUILD_SIG_NEW)
    wide = replace(wide, BUILD_TABLE_OLD, BUILD_TABLE_NEW)
    wide = replace(wide, SCAN_ANCHOR, SCAN_CODE + SCAN_ANCHOR)
    wide = replace(wide, SELECT_OLD, SELECT_NEW)
    wide = replace(wide, RANK_OLD, RANK_NEW)
    wide = replace(wide, LOOP_OLD, LOOP_NEW)
    wide = replace(wide, RELATION_OLD, RELATION_NEW)
    wide = replace(wide, RELATION_END_OLD, RELATION_END_NEW)
    wide = replace(wide, RECORD_OLD, RECORD_NEW)
    wide = replace(wide, SUMMARY_OLD, SUMMARY_NEW)
    return head, wide


def probepipe_text():
    text = probepipe.derive(probepipe.combined_text())
    digest = hashlib.sha256(text.encode()).hexdigest()
    if digest != PROBEPIPE_SHA256:
        raise ValueError("probe-pipeline derivation differs from claude/n83-probe-pipeline's frozen producer: "
                         + digest)
    return text


def derive(text):
    head, rest = text.split(WIDE_START, 1)
    wide, tail = rest.split(WIDE_END, 1)
    head, wide = table_edits(head, wide)
    return head + WIDE_START + wide + WIDE_END + tail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = derive(probepipe_text())
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit("derived online source differs from " + str(OUTPUT))
    else:
        OUTPUT.write_text(text)
    print("online_source_sha256=" + hashlib.sha256(text.encode()).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
