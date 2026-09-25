//! Dense Gaussian elimination over `F_2`: the Method of Four Russians
//! with several Gray-code tables per pass, a word-strip pivot search, and
//! an AVX-512 row update selected at run time.
//!
//! The matrix is a slice of rows, each `n_cols.div_ceil(64)` words long
//! with bit `c % 64` of word `c / 64` holding column `c` — the layout
//! every Macaulay builder in [`crate::cryptanalysis::koblitz_groebner`]
//! produces, so this is a drop-in kernel for it.
//!
//! ## How a block is eliminated
//!
//! Columns are taken one 64-column word at a time.  For every row not yet
//! holding a pivot, the *strip* keeps that row's current word as it would
//! read after reduction by the block's pivots so far.  Finding the next
//! pivot is one pass over the strip for the lowest set column, and taking
//! it is one more pass that clears that column from the strip — no row
//! outside the block is touched while the block is being found.  The
//! pivot row itself is reduced in full by the block's earlier pivots and
//! they by it, so the block is always in reduced form on its own pivot
//! columns.
//!
//! When the block holds `k · tables` pivots (`k ≤ 8`, from the row
//! count), or the word runs out, every
//! other row is cleared of the whole block in **one pass**: its bits on
//! the pivot columns, eight at a time, index one Gray-code table each,
//! and the row is XORed with one entry of every table.  A row is
//! therefore read and written once per block rather than once per pivot,
//! which is the point of the method; several tables divide the passes by
//! their number again, at the price of `256 · suffix` words each, which
//! must stay cache resident.
//!
//! The reduced row echelon form of a matrix is unique, so
//! [`rref_counted`] can be — and in the tests is — checked bit for bit
//! against any other elimination.  The row echelon form of
//! [`echelon_counted`] is not unique: it has the same rank and row space
//! and distinct leading columns in increasing order, and nothing else is
//! promised.
//!
//! The unit charged to `word_ops` is the repository's one for this stage:
//! a 64-bit word XORed into a row.  A table entry built costs its suffix,
//! and a row cleared against `t` tables costs `t` suffixes, however the
//! hardware groups them.

use rayon::prelude::*;

/// Largest pattern width of one Gray-code table.
const MAX_TABLE_BITS: usize = 8;

/// Pattern bits per table for a matrix of `rows` rows.  A table of
/// `2^k` entries costs `2^k` row XORs to build and saves about `k/2`
/// row XORs on each of the rows it clears, so `k` tracks `log₂ rows`:
/// 256-entry tables on a 100-row matrix would cost more than the naive
/// elimination they replace.
fn table_bits(rows: usize) -> usize {
    let log = usize::BITS as usize - 1 - rows.max(2).leading_zeros() as usize;
    log.saturating_sub(1).clamp(1, MAX_TABLE_BITS)
}

/// Tables per pass when nothing else is asked for.  Four tables of 256
/// entries hold 32 pivots; at a 20 000-column suffix that is 2.5 MiB of
/// table, about one core's L2 on the hosts this was tuned on.
const DEFAULT_TABLES: usize = 4;

/// Row words per block below which a block's rows are cleared on one
/// thread.
const PARALLEL_WORDS: usize = 1 << 16;

/// Tuning knobs, fixed for a process by [`Config::from_env`] and
/// overridable in a test or a sweep.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Config {
    /// Gray-code tables per pass, 1 to 4; the block is `k · tables`
    /// pivots for `k`-bit tables.
    pub tables: usize,
    /// Row words per block from which rows are cleared in parallel.
    pub parallel_words: usize,
    /// Use the AVX-512 row update when the CPU has it.
    pub simd: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            tables: DEFAULT_TABLES,
            parallel_words: PARALLEL_WORDS,
            simd: true,
        }
    }
}

impl Config {
    /// The default, with `KIC_GF2_TABLES` (1–4), `KIC_GF2_PARALLEL_WORDS`
    /// and `KIC_GF2_SIMD=0` read once per process for ablations.
    pub fn from_env() -> Self {
        static CONFIG: std::sync::OnceLock<Config> = std::sync::OnceLock::new();
        *CONFIG.get_or_init(|| {
            let mut c = Config::default();
            if let Some(t) = std::env::var("KIC_GF2_TABLES")
                .ok()
                .and_then(|v| v.parse::<usize>().ok())
            {
                c.tables = t.clamp(1, 4);
            }
            if let Some(p) = std::env::var("KIC_GF2_PARALLEL_WORDS")
                .ok()
                .and_then(|v| v.parse::<usize>().ok())
            {
                c.parallel_words = p;
            }
            if std::env::var("KIC_GF2_SIMD").as_deref() == Ok("0") {
                c.simd = false;
            }
            c
        })
    }
}

/// Reduced row echelon form in place; returns the rank.  The pivot rows
/// end up first, in increasing pivot column, and the rest are zero.
pub fn rref(matrix: &mut [Vec<u64>], n_cols: usize) -> usize {
    let mut ops = 0;
    rref_counted(matrix, n_cols, &mut ops)
}

/// [`rref`], charging the word XORs it performs to `word_ops`.
pub fn rref_counted(matrix: &mut [Vec<u64>], n_cols: usize, word_ops: &mut u64) -> usize {
    eliminate(matrix, n_cols, true, Config::from_env(), word_ops)
}

/// Row echelon form in place — distinct leading columns in increasing
/// order, pivot rows first, no clearing above a pivot; returns the rank.
pub fn echelon_counted(matrix: &mut [Vec<u64>], n_cols: usize, word_ops: &mut u64) -> usize {
    eliminate(matrix, n_cols, false, Config::from_env(), word_ops)
}

/// The elimination with explicit settings.
pub fn eliminate(
    matrix: &mut [Vec<u64>],
    n_cols: usize,
    reduce_above: bool,
    config: Config,
    word_ops: &mut u64,
) -> usize {
    let rows = matrix.len();
    let words = n_cols.div_ceil(64);
    if rows == 0 || words == 0 {
        return 0;
    }
    debug_assert!(matrix.iter().all(|r| r.len() >= words));
    let tables = config.tables.clamp(1, 4);
    let bits = table_bits(rows);
    let block_cap = tables * bits;
    let simd = config.simd && simd_available();

    let mut strip: Vec<u64> = vec![0; rows];
    let mut pivot_cols: Vec<usize> = Vec::with_capacity(block_cap);
    let mut table: Vec<u64> = Vec::new();

    let mut pivot_row = 0usize;
    let mut word = 0usize;
    // Columns of the current word below `low` are already decided.
    let mut low = 0u32;
    while pivot_row < rows && word < words {
        let block_start = pivot_row;
        pivot_cols.clear();
        // The strip: each unpivoted row's current word, in reduced form
        // with respect to the (so far empty) block.
        for (s, row) in strip[block_start..].iter_mut().zip(&matrix[block_start..]) {
            *s = row[word];
        }
        let last_col_in_word = if word + 1 == words && !n_cols.is_multiple_of(64) {
            (n_cols % 64) as u32
        } else {
            64
        };
        let mut block_full = false;
        while pivot_row < rows && low < last_col_in_word {
            // Lowest set column at or above `low`, over the unpivoted rows.
            let mask = !0u64 << low;
            let mut best = u32::MAX;
            let mut best_row = usize::MAX;
            for (i, &s) in strip[pivot_row..].iter().enumerate() {
                let v = s & mask;
                if v != 0 {
                    let tz = v.trailing_zeros();
                    if tz < best {
                        best = tz;
                        best_row = pivot_row + i;
                        if tz == low {
                            break;
                        }
                    }
                }
            }
            if best == u32::MAX || best >= last_col_in_word {
                low = last_col_in_word;
                break;
            }
            let col = word * 64 + best as usize;
            matrix.swap(pivot_row, best_row);
            strip.swap(pivot_row, best_row);
            // Reduce the new pivot row in full by the block's earlier
            // pivots.  They are mutually reduced, so testing the row's
            // current bit on each pivot column in turn is the same as
            // testing the original bit.
            {
                let (done, rest) = matrix.split_at_mut(pivot_row);
                let row = &mut rest[0];
                for (j, &pc) in pivot_cols.iter().enumerate() {
                    if row[pc / 64] >> (pc % 64) & 1 != 0 {
                        let from = pc / 64;
                        xor_into(&mut row[from..words], &done[block_start + j][from..words]);
                        *word_ops += (words - from) as u64;
                    }
                }
            }
            // And the earlier pivots by it, on its column.
            {
                let (before, rest) = matrix.split_at_mut(pivot_row);
                let piv = &rest[0];
                let bit = best;
                for prev in &mut before[block_start..] {
                    if prev[word] >> bit & 1 != 0 {
                        xor_into(&mut prev[word..words], &piv[word..words]);
                        *word_ops += (words - word) as u64;
                    }
                }
            }
            // Clear the column from the strip of every unpivoted row.
            let ps = strip[pivot_row];
            for s in &mut strip[pivot_row + 1..] {
                if *s >> best & 1 != 0 {
                    *s ^= ps;
                }
            }
            pivot_cols.push(col);
            pivot_row += 1;
            low = best + 1;
            if pivot_cols.len() == block_cap {
                block_full = true;
                break;
            }
        }
        if !pivot_cols.is_empty() {
            clear_block(
                matrix,
                words,
                block_start,
                bits,
                &pivot_cols,
                reduce_above,
                &mut table,
                config,
                simd,
                word_ops,
            );
        }
        if !block_full || low >= last_col_in_word {
            word += 1;
            low = 0;
        }
    }
    pivot_row
}

/// Clear every row outside `block_start .. block_start + pivots` (and,
/// without `reduce_above`, above it) of the block's pivot columns.
fn clear_block(
    matrix: &mut [Vec<u64>],
    words: usize,
    block_start: usize,
    bits: usize,
    pivot_cols: &[usize],
    reduce_above: bool,
    table: &mut Vec<u64>,
    config: Config,
    simd: bool,
    word_ops: &mut u64,
) {
    let b = pivot_cols.len();
    let first_word = pivot_cols[0] / 64;
    let suffix = words - first_word;
    let n_tables = b.div_ceil(bits);
    let table_size = 1usize << bits;
    table.clear();
    table.resize(n_tables * table_size * suffix, 0);
    // Gray-code tables: entry g of table t is the XOR of the pivots whose
    // bits within the table's group are set in g.
    for t in 0..n_tables {
        let group = &pivot_cols[t * bits..((t + 1) * bits).min(b)];
        let base = t * table_size * suffix;
        for g in 1usize..(1 << group.len()) {
            let low_bit = g.trailing_zeros() as usize;
            let prev = g & (g - 1);
            let src_row = &matrix[block_start + t * bits + low_bit][first_word..words];
            let (head, tail) = table[base..].split_at_mut(g * suffix);
            let prev_entry = &head[prev * suffix..(prev + 1) * suffix];
            let dst = &mut tail[..suffix];
            for ((d, &p), &s) in dst.iter_mut().zip(prev_entry).zip(src_row) {
                *d = p ^ s;
            }
            *word_ops += suffix as u64;
        }
    }
    let table: &[u64] = table;
    // A block never crosses a word, so a row's whole pattern is its
    // pivot word gathered through the block's column mask: bit i of the
    // result is pivot i, since the pivots are in increasing column order.
    let pivot_word = first_word;
    debug_assert!(pivot_cols.iter().all(|&pc| pc / 64 == pivot_word));
    let mask = pivot_cols.iter().fold(0u64, |m, &pc| m | 1u64 << (pc % 64));
    let bmi2 = bmi2_available();
    let clear = |row: &mut Vec<u64>| -> u64 {
        let pattern = gather_bits(row[pivot_word], mask, bmi2);
        if pattern == 0 {
            return 0;
        }
        let mut idx = [0usize; 4];
        for (t, slot) in idx.iter_mut().enumerate().take(n_tables) {
            let g = (pattern >> (t * bits)) as usize & (table_size - 1);
            *slot = t * table_size * suffix + g * suffix;
        }
        let dst = &mut row[first_word..words];
        let used = xor_entries(dst, table, &idx[..n_tables], suffix, table_size, simd);
        used as u64 * suffix as u64
    };
    let (head, tail) = matrix.split_at_mut(block_start);
    let above: &mut [Vec<u64>] = if reduce_above { head } else { &mut [] };
    let below = &mut tail[b..];
    if (above.len() + below.len()) * suffix >= config.parallel_words {
        *word_ops += above
            .par_iter_mut()
            .chain(below.par_iter_mut())
            .with_min_len(64)
            .map(clear)
            .sum::<u64>();
    } else {
        *word_ops += above
            .iter_mut()
            .chain(below.iter_mut())
            .map(clear)
            .sum::<u64>();
    }
}

/// `dst ^= table[o]` for every offset `o` whose entry is not the zero
/// entry of its table; returns how many entries were applied.
#[inline]
fn xor_entries(
    dst: &mut [u64],
    table: &[u64],
    offsets: &[usize],
    suffix: usize,
    table_size: usize,
    simd: bool,
) -> usize {
    // Offsets pointing at entry 0 of a table are zero rows: skip them.
    let mut live = [0usize; 4];
    let mut n = 0;
    for &o in offsets {
        if !(o / suffix).is_multiple_of(table_size) {
            live[n] = o;
            n += 1;
        }
    }
    let live = &live[..n];
    #[cfg(all(target_arch = "x86_64", suite_avx512))]
    if simd {
        // SAFETY: `simd` is only true when `simd_available()` said the CPU
        // has AVX-512F.
        unsafe { xor_entries_avx512(dst, table, live, suffix) };
        return n;
    }
    let _ = simd;
    xor_entries_generic(dst, table, live, suffix);
    n
}

#[inline(always)]
fn xor_entries_generic(dst: &mut [u64], table: &[u64], live: &[usize], suffix: usize) {
    match *live {
        [] => {}
        [a] => xor_into(dst, &table[a..a + suffix]),
        [a, b] => {
            let (ta, tb) = (&table[a..a + suffix], &table[b..b + suffix]);
            for ((d, &x), &y) in dst.iter_mut().zip(ta).zip(tb) {
                *d ^= x ^ y;
            }
        }
        [a, b, c] => {
            let (ta, tb, tc) = (
                &table[a..a + suffix],
                &table[b..b + suffix],
                &table[c..c + suffix],
            );
            for (((d, &x), &y), &z) in dst.iter_mut().zip(ta).zip(tb).zip(tc) {
                *d ^= x ^ y ^ z;
            }
        }
        [a, b, c, e] => {
            let (ta, tb, tc, te) = (
                &table[a..a + suffix],
                &table[b..b + suffix],
                &table[c..c + suffix],
                &table[e..e + suffix],
            );
            for ((((d, &x), &y), &z), &w) in dst.iter_mut().zip(ta).zip(tb).zip(tc).zip(te) {
                *d ^= x ^ y ^ z ^ w;
            }
        }
        _ => unreachable!("at most four tables"),
    }
}

/// The same loops compiled with AVX-512 enabled, so the XORs run eight
/// words to an instruction (and three-way XORs fold into `vpternlogq`).
#[cfg(all(target_arch = "x86_64", suite_avx512))]
#[clippy::msrv = "1.89"]
#[target_feature(enable = "avx512f")]
unsafe fn xor_entries_avx512(dst: &mut [u64], table: &[u64], live: &[usize], suffix: usize) {
    xor_entries_generic(dst, table, live, suffix)
}

#[inline(always)]
fn xor_into(dst: &mut [u64], src: &[u64]) {
    for (d, &s) in dst.iter_mut().zip(src) {
        *d ^= s;
    }
}

/// The bits of `word` selected by `mask`, packed into the low bits in
/// order (`pext`).
#[inline(always)]
fn gather_bits(word: u64, mask: u64, bmi2: bool) -> u64 {
    #[cfg(target_arch = "x86_64")]
    if bmi2 {
        // SAFETY: `bmi2` is only true when `bmi2_available()` said so.
        return unsafe { pext_bmi2(word, mask) };
    }
    let _ = bmi2;
    let (mut out, mut m, mut i) = (0u64, mask, 0);
    while m != 0 {
        let low = m.trailing_zeros();
        out |= (word >> low & 1) << i;
        m &= m - 1;
        i += 1;
    }
    out
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "bmi2")]
unsafe fn pext_bmi2(word: u64, mask: u64) -> u64 {
    std::arch::x86_64::_pext_u64(word, mask)
}

fn bmi2_available() -> bool {
    #[cfg(target_arch = "x86_64")]
    {
        static HAS: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        *HAS.get_or_init(|| std::arch::is_x86_feature_detected!("bmi2"))
    }
    #[cfg(not(target_arch = "x86_64"))]
    {
        false
    }
}

/// Whether the AVX-512 row update can run on this CPU (never on a
/// toolchain older than 1.89, where AVX-512 target features are unstable
/// and the kernel is not compiled; see `build.rs`).
pub fn simd_available() -> bool {
    #[cfg(all(target_arch = "x86_64", suite_avx512))]
    {
        static HAS: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        *HAS.get_or_init(|| std::arch::is_x86_feature_detected!("avx512f"))
    }
    #[cfg(not(all(target_arch = "x86_64", suite_avx512)))]
    {
        false
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::{rngs::StdRng, Rng, SeedableRng};

    /// Textbook column-at-a-time RREF: the reference.
    fn naive_rref(m: &mut [Vec<u64>], n_cols: usize) -> usize {
        let mut r = 0;
        for c in 0..n_cols {
            let (w, bit) = (c / 64, 1u64 << (c % 64));
            let Some(p) = (r..m.len()).find(|&i| m[i][w] & bit != 0) else {
                continue;
            };
            m.swap(r, p);
            let piv = m[r].clone();
            for (i, row) in m.iter_mut().enumerate() {
                if i != r && row[w] & bit != 0 {
                    xor_into(row, &piv);
                }
            }
            r += 1;
            if r == m.len() {
                break;
            }
        }
        r
    }

    fn random_matrix(rng: &mut StdRng, rows: usize, cols: usize, density: f64) -> Vec<Vec<u64>> {
        let words = cols.div_ceil(64);
        (0..rows)
            .map(|_| {
                let mut row = vec![0u64; words];
                for c in 0..cols {
                    if rng.gen_bool(density) {
                        row[c / 64] |= 1 << (c % 64);
                    }
                }
                row
            })
            .collect()
    }

    fn configs() -> Vec<Config> {
        let mut out = Vec::new();
        for tables in 1..=4 {
            for simd in [false, true] {
                for parallel_words in [0, usize::MAX] {
                    out.push(Config {
                        tables,
                        parallel_words,
                        simd,
                    });
                }
            }
        }
        out
    }

    #[test]
    fn rref_matches_the_textbook_elimination() {
        let mut rng = StdRng::seed_from_u64(7);
        let shapes = [
            (1, 1),
            (3, 70),
            (40, 40),
            (70, 130),
            (130, 70),
            (200, 257),
            (257, 200),
            (300, 700),
        ];
        for &(rows, cols) in &shapes {
            for density in [0.02, 0.2, 0.5] {
                let m = random_matrix(&mut rng, rows, cols, density);
                let mut want = m.clone();
                let rank = naive_rref(&mut want, cols);
                for config in configs() {
                    let mut got = m.clone();
                    let mut ops = 0;
                    let r = eliminate(&mut got, cols, true, config, &mut ops);
                    assert_eq!(r, rank, "{rows}x{cols} d={density} {config:?}");
                    assert_eq!(got, want, "{rows}x{cols} d={density} {config:?}");
                }
            }
        }
    }

    #[test]
    fn rank_deficient_and_structured_matrices() {
        let mut rng = StdRng::seed_from_u64(11);
        // Low rank: products of thin random factors; duplicated rows;
        // empty column bands, which leave whole words without a pivot.
        for &(rows, cols, rank_cap) in &[(120, 300, 7), (300, 200, 45), (90, 640, 64)] {
            let basis = random_matrix(&mut rng, rank_cap, cols, 0.3);
            let mut m: Vec<Vec<u64>> = (0..rows)
                .map(|_| {
                    let mut row = vec![0u64; cols.div_ceil(64)];
                    for b in &basis {
                        if rng.gen_bool(0.5) {
                            xor_into(&mut row, b);
                        }
                    }
                    row
                })
                .collect();
            // Blank the columns 64..192 in every row.
            for row in &mut m {
                if row.len() > 2 {
                    row[1] = 0;
                    row[2] = 0;
                }
            }
            let mut want = m.clone();
            let rank = naive_rref(&mut want, cols);
            for config in configs() {
                let mut got = m.clone();
                let mut ops = 0;
                assert_eq!(eliminate(&mut got, cols, true, config, &mut ops), rank);
                assert_eq!(got, want, "{config:?}");
            }
        }
    }

    #[test]
    fn echelon_has_the_rank_and_row_space() {
        let mut rng = StdRng::seed_from_u64(13);
        for &(rows, cols) in &[(100, 150), (250, 90), (180, 520)] {
            let m = random_matrix(&mut rng, rows, cols, 0.1);
            let mut want = m.clone();
            let rank = naive_rref(&mut want, cols);
            for config in configs() {
                let mut got = m.clone();
                let mut ops = 0;
                let r = eliminate(&mut got, cols, false, config, &mut ops);
                assert_eq!(r, rank);
                // Leading columns strictly increase and the rest is zero.
                let lead = |row: &Vec<u64>| {
                    row.iter()
                        .enumerate()
                        .find(|(_, &w)| w != 0)
                        .map(|(i, w)| i * 64 + w.trailing_zeros() as usize)
                };
                let leads: Vec<usize> = got[..r].iter().map(|row| lead(row).unwrap()).collect();
                assert!(leads.windows(2).all(|w| w[0] < w[1]));
                assert!(got[r..].iter().all(|row| row.iter().all(|&w| w == 0)));
                // Same row space: its RREF is the RREF of the input.
                let mut again = got.clone();
                naive_rref(&mut again, cols);
                assert_eq!(again, want);
            }
        }
    }
}
