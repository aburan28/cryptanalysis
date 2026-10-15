// Bernstein–Lange table file (shared by both BL binaries; `include!`d).
//
// One record per stored distinguished point, 40 bytes, little endian:
// x (u128), y (u128) in the polynomial basis, then its logarithm a (u64),
// with [a]G = (x, y). Records are sorted by (x, y), strictly increasing, so
// the file is a canonical encoding of the set: two tables are equal exactly
// when their bytes are. The BLAKE3 of the file is checked on every load; the
// SHA-256 is taken outside the process by the harness.

/// Bytes in one record.
pub const BL_RECORD_BYTES: usize = 40;

/// Write `rows` (any order) as a canonical table; returns (count, blake3 hex).
pub fn bl_write_table(path: &str, mut rows: Vec<(u128, u128, u64)>) -> (usize, String) {
    use std::io::Write;
    rows.sort_unstable_by_key(|row| (row.0, row.1));
    for pair in rows.windows(2) {
        assert!(
            (pair[0].0, pair[0].1) < (pair[1].0, pair[1].1),
            "duplicate point in a BL table"
        );
    }
    let mut hasher = blake3::Hasher::new();
    let file = std::fs::File::create(path).expect("create BL table");
    let mut out = std::io::BufWriter::with_capacity(1 << 20, file);
    let mut record = [0u8; BL_RECORD_BYTES];
    for (x, y, a) in &rows {
        record[..16].copy_from_slice(&x.to_le_bytes());
        record[16..32].copy_from_slice(&y.to_le_bytes());
        record[32..].copy_from_slice(&a.to_le_bytes());
        hasher.update(&record);
        out.write_all(&record).expect("write BL table");
    }
    out.flush().expect("flush BL table");
    out.get_ref().sync_all().expect("sync BL table");
    (rows.len(), hasher.finalize().to_hex().to_string())
}

/// Read a canonical table; panics on a malformed file or a BLAKE3 mismatch.
/// Returns (rows, blake3 hex, read-and-parse milliseconds).
pub fn bl_read_table(path: &str, expect_blake3: Option<&str>) -> (Vec<(u128, u128, u64)>, String, f64) {
    let started = std::time::Instant::now();
    let bytes = std::fs::read(path).expect("read BL table");
    assert!(
        bytes.len() % BL_RECORD_BYTES == 0,
        "BL table length is not a whole number of records"
    );
    let digest = blake3::hash(&bytes).to_hex().to_string();
    if let Some(expected) = expect_blake3 {
        assert_eq!(digest, expected, "BL table BLAKE3 differs from the expected digest");
    }
    let mut rows = Vec::with_capacity(bytes.len() / BL_RECORD_BYTES);
    for record in bytes.chunks_exact(BL_RECORD_BYTES) {
        let x = u128::from_le_bytes(record[..16].try_into().unwrap());
        let y = u128::from_le_bytes(record[16..32].try_into().unwrap());
        let a = u64::from_le_bytes(record[32..].try_into().unwrap());
        rows.push((x, y, a));
    }
    for pair in rows.windows(2) {
        assert!(
            (pair[0].0, pair[0].1) < (pair[1].0, pair[1].1),
            "BL table is not strictly sorted"
        );
    }
    (rows, digest, started.elapsed().as_secs_f64() * 1000.0)
}

/// Peak resident set of this process in bytes (Linux ru_maxrss is KiB).
pub fn bl_peak_rss_bytes() -> Option<u64> {
    // SAFETY: getrusage fills the zero-initialised plain-data structure.
    let mut usage: libc::rusage = unsafe { std::mem::zeroed() };
    if unsafe { libc::getrusage(libc::RUSAGE_SELF, &mut usage) } != 0 {
        return None;
    }
    u64::try_from(usage.ru_maxrss).ok().map(|kib| kib.saturating_mul(1024))
}

/// The precomputation's stop rule: a wall-clock budget, a step count or a
/// round count (exactly one), evaluated before every lane round. A budget
/// is read every 256 rounds, so the stop round is a multiple of 256 and a
/// round-count rerun reproduces the same table.
pub struct BlStop {
    pub budget_ms: Option<f64>,
    pub stop_steps: Option<u64>,
    pub stop_rounds: Option<u64>,
    pub started: std::time::Instant,
}

impl BlStop {
    pub fn from_env_or_args(budget_ms: Option<f64>, stop_steps: Option<u64>, stop_rounds: Option<u64>) -> Self {
        let set = [budget_ms.is_some(), stop_steps.is_some(), stop_rounds.is_some()]
            .iter()
            .filter(|v| **v)
            .count();
        assert_eq!(set, 1, "give exactly one of a budget, a step count or a round count");
        BlStop { budget_ms, stop_steps, stop_rounds, started: std::time::Instant::now() }
    }

    pub fn reached(&self, rounds: u64, steps: u64) -> bool {
        if let Some(limit) = self.stop_rounds {
            return rounds >= limit;
        }
        if let Some(limit) = self.stop_steps {
            return steps >= limit;
        }
        let budget = self.budget_ms.unwrap();
        rounds % 256 == 0 && self.started.elapsed().as_secs_f64() * 1000.0 >= budget
    }
}
