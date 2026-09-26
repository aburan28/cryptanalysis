//! **Load a folded table the GPU path built, and ask it everything.**
//!
//! `gpu/ecc2k/test_pairtable_emu.cpp` runs `pairtable_fold_kernel` on the
//! host, assembles its output with `pt_fold_count` / `pt_fold_fill`, and —
//! given a path — writes the table it built.  That comparison is of
//! *stored state*: the same bucket offsets, presence words and words per
//! bucket as the CPU's table.  This is the other half: the table taken
//! over by `PairSumTable::from_folded_parts` and put through the lookups
//! the descent actually spends, against the table the CPU builds itself.
//!
//! For every stored pair `P_i + P_j`, `i ≤ j`, both tables must say it is
//! present and recover the same summand pairs; the loaded one's list must
//! include `(i, j)`.  Recovery walks the orbit a word's tag names, so this
//! is what exercises every tag the GPU path wrote.  Then a run of
//! multiples of the generator, most of them absent, and three-summand
//! decompositions.  Finally a control: the same words with one bucket's
//! shifted into its neighbour still load — the shift is well-formed — and
//! the stored pairs those words answered for must go missing here, or
//! this check could not see misplaced words.
//!
//! Before any probe, the stored state itself: bucket offsets and presence
//! words equal to the CPU's, and the same multiset of words in every
//! bucket.  That costs a pass over the words, so it holds at any size;
//! asking every stored pair is `|F|²/2` probes, which a wide base cannot
//! afford, so `--sample N` asks the pairs of `N` evenly spaced rows
//! instead (and the control is then judged on stored state alone).
//!
//! Usage: `cargo run --release --example load_fold_table -- [--sample N] TABLE...`
//! (`make -C gpu/ecc2k roundtrip` writes the tables and runs this;
//! `make device-roundtrip` does the same with tables a GPU built).
use std::io::Read;
use std::process::ExitCode;

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{BatchScratch, FastCurve, FastPoint};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_subgroup_orbit_factor_base, FoldedParts, FoldedStorage, FrobeniusFactorBase,
    KoblitzCurve, PairSumTable,
};

struct TableFile {
    degree: u32,
    base_request: usize,
    seed: u64,
    parts: FoldedParts,
}

/// Little-endian reads off a byte slice, failing rather than panicking
/// on a short file.
struct Cursor<'a> {
    bytes: &'a [u8],
    at: usize,
}

impl Cursor<'_> {
    fn take(&mut self, n: usize) -> Result<&[u8], String> {
        let end = self.at.checked_add(n).ok_or("length overflow")?;
        let slice = self.bytes.get(self.at..end).ok_or("file ends early")?;
        self.at = end;
        Ok(slice)
    }
    fn u32(&mut self) -> Result<u32, String> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }
    fn u64(&mut self) -> Result<u64, String> {
        Ok(u64::from_le_bytes(self.take(8)?.try_into().unwrap()))
    }
    fn u32s(&mut self, n: usize) -> Result<Vec<u32>, String> {
        (0..n).map(|_| self.u32()).collect()
    }
    fn u64s(&mut self, n: usize) -> Result<Vec<u64>, String> {
        (0..n).map(|_| self.u64()).collect()
    }
}

/// The format `write_table` in `test_pairtable_emu.cpp` documents.
fn read_table(path: &str) -> Result<TableFile, String> {
    let mut bytes = Vec::new();
    std::fs::File::open(path)
        .and_then(|mut f| f.read_to_end(&mut bytes))
        .map_err(|e| format!("{path}: {e}"))?;
    let mut c = Cursor {
        bytes: &bytes,
        at: 0,
    };
    if c.take(8)? != b"PTFOLD1\0" {
        return Err(format!("{path}: not a folded-table file"));
    }
    let degree = c.u32()?;
    let base_request = c.u32()? as usize;
    let seed = c.u64()?;
    let bucket_shift = c.u32()?;
    let buckets = c.u32()? as usize;
    let words = c.u32()? as usize;
    let present_words = c.u32()? as usize;
    let present_mask = c.u64()?;
    let canon_bytes = c.u32()? as usize;
    c.u32()?;
    let flat = c.u64s(canon_bytes * 256)?;
    let canon_tables = flat
        .chunks(256)
        .map(|t| t.try_into().unwrap())
        .collect::<Vec<[u64; 256]>>();
    let bucket_start = c.u32s(buckets + 1)?;
    let words = c.u32s(words)?;
    let present = c.u64s(present_words)?;
    if c.at != bytes.len() {
        return Err(format!("{path}: {} trailing bytes", bytes.len() - c.at));
    }
    Ok(TableFile {
        degree,
        base_request,
        seed,
        parts: FoldedParts {
            bucket_start,
            bucket_shift,
            words,
            present,
            present_mask,
            canon_tables,
        },
    })
}

/// Questions on which the two tables disagree, and stored pairs the
/// candidate fails to find or to recover.  All three must be zero.
#[derive(Default, Debug)]
struct Tally {
    disagreements: usize,
    stored_pairs: usize,
    missed_pairs: usize,
    absent_targets: usize,
}

/// Where two tables' stored state differs, if anywhere: the geometry,
/// the bucket offsets, the presence words, or the multiset of words in
/// some bucket.  Order within a bucket is whatever a build's parallel
/// cursors made it, on either side, so each bucket is compared sorted.
fn stored_difference(a: &FoldedStorage<'_>, b: &FoldedStorage<'_>) -> Option<String> {
    if a.bucket_shift != b.bucket_shift || a.present_mask != b.present_mask {
        return Some("bucket or filter geometry".into());
    }
    if a.bucket_start != b.bucket_start {
        return Some("bucket offsets".into());
    }
    if a.present != b.present {
        return Some("presence words".into());
    }
    let differ = (0..a.bucket_start.len() - 1)
        .filter(|&k| {
            let run = |s: &FoldedStorage<'_>| {
                let mut w =
                    s.words[s.bucket_start[k] as usize..s.bucket_start[k + 1] as usize].to_vec();
                w.sort_unstable();
                w
            };
            run(a) != run(b)
        })
        .count();
    (differ > 0).then(|| format!("the words of {differ} buckets"))
}

fn compare(
    kc: &KoblitzCurve,
    fb: &FrobeniusFactorBase,
    cpu: &PairSumTable,
    candidate: &PairSumTable,
    sample: Option<usize>,
) -> Tally {
    let curve = FastCurve::new(&kc.curve).expect("single-word curve");
    let points: Vec<FastPoint> = fb.points.iter().map(|p| curve.lift(p)).collect();
    let mut tally = Tally::default();
    let (mut sums, mut scratch) = (Vec::new(), BatchScratch::default());
    let (mut a, mut b) = (Vec::new(), Vec::new());
    let step = sample.map_or(1, |n| (points.len() / n.max(1)).max(1));
    for i in (0..points.len()).step_by(step) {
        sums.clear();
        curve.add_many(points[i], &points[i..], &mut sums, &mut scratch);
        for (offset, &sum) in sums.iter().enumerate() {
            let j = (i + offset) as u32;
            tally.stored_pairs += 1;
            let (in_cpu, in_candidate) = (cpu.contains_pair(sum), candidate.contains_pair(sum));
            tally.disagreements += usize::from(in_cpu != in_candidate);
            cpu.pairs_for(sum, &mut a);
            candidate.pairs_for(sum, &mut b);
            a.sort_unstable();
            b.sort_unstable();
            tally.disagreements += usize::from(a != b);
            // `O` is stored under key zero and recovery does not name
            // its summands (every `±` pair has it); presence is the claim.
            let found = in_candidate && (sum.infinity || b.contains(&(i as u32, j)));
            tally.missed_pairs += usize::from(!found);
        }
    }
    let g = curve.lift(kc.generator());
    for t in 1u64..20_000 {
        let target = curve.mul_u64(g, t.wrapping_mul(0x9e37_79b9) | 1);
        if target.infinity {
            continue;
        }
        let in_cpu = cpu.contains_pair(target);
        tally.disagreements += usize::from(in_cpu != candidate.contains_pair(target));
        tally.absent_targets += usize::from(!in_cpu);
        if t % 100 == 0 {
            tally.disagreements +=
                usize::from(cpu.decompose_fast(target, 3) != candidate.decompose_fast(target, 3));
        }
    }
    tally
}

fn check(path: &str, sample: Option<usize>) -> Result<(), String> {
    let file = read_table(path)?;
    let kc = KoblitzCurve::new(0, file.degree).ok_or("no Koblitz curve at that degree")?;
    let fb = build_subgroup_orbit_factor_base(&kc, file.seed, file.base_request)?;
    let cpu = PairSumTable::build_folded_within(&kc, &fb, u128::MAX)
        .ok_or("the CPU would not build this table")?;
    let moved = {
        // The control: one bucket's words shifted into the next bucket,
        // which leaves the offsets well-formed and the words where no
        // lookup looks for them.  A whole bucket rather than one word,
        // because a word can have an exact copy beside it — the fold
        // stores some sum orbits twice (430 of the 6256 words at n = 23
        // are copies), and a word whose copy stays behind loses nothing.
        // And from the middle of the table: bucket zero holds the key of
        // `O`, which every row stores.
        let mut parts = file.parts.clone();
        let buckets = parts.bucket_start.len() - 1;
        let b = (buckets / 2..buckets - 1)
            .find(|&b| parts.bucket_start[b] < parts.bucket_start[b + 1])
            .ok_or("no non-empty bucket")?;
        parts.bucket_start[b + 1] = parts.bucket_start[b];
        parts
    };
    let loaded = PairSumTable::from_folded_parts(&kc, &fb, file.parts)?;
    let (ours, theirs) = (
        loaded.folded_storage().expect("folded"),
        cpu.folded_storage().expect("folded"),
    );
    if let Some(what) = stored_difference(&ours, &theirs) {
        return Err(format!(
            "{path}: stored state differs from the CPU's in {what}"
        ));
    }
    let tally = compare(&kc, &fb, &cpu, &loaded, sample);
    println!(
        "{path}: n = {}, {} points, {} stored words, stored state identical to the CPU's; \
         {} stored pairs asked{}, {} probes absent from the CPU's table",
        file.degree,
        fb.points.len(),
        loaded.len(),
        tally.stored_pairs,
        sample.map_or(String::new(), |n| format!(" (rows sampled: {n})")),
        tally.absent_targets,
    );
    if tally.disagreements != 0 || tally.missed_pairs != 0 {
        return Err(format!(
            "{path}: the loaded table differs from the CPU's: {} disagreements, {} stored \
             pairs missed",
            tally.disagreements, tally.missed_pairs
        ));
    }
    if tally.absent_targets == 0 {
        return Err(format!(
            "{path}: every probe was present, so absence went unasked"
        ));
    }
    println!("  loaded: agrees with the CPU's table on every question, and finds every pair");
    let control = PairSumTable::from_folded_parts(&kc, &fb, moved)?;
    let control_stored = stored_difference(&control.folded_storage().expect("folded"), &theirs);
    if control_stored.is_none() {
        return Err(format!(
            "{path}: a bucket's words in the wrong bucket left the stored state the \
             CPU's, so that comparison cannot see them"
        ));
    }
    if sample.is_some() {
        // The sampled rows need not reach the moved bucket's pairs, so
        // the stored state is what decides here.
        println!(
            "  control: one bucket's words in the wrong bucket load, and the stored \
             state shows it ({})",
            control_stored.unwrap()
        );
        return Ok(());
    }
    let tally = compare(&kc, &fb, &cpu, &control, None);
    if tally.disagreements == 0 || tally.missed_pairs == 0 {
        return Err(format!(
            "{path}: a bucket's words in the wrong bucket lost no stored pair, so \
             this check cannot see them ({} disagreements)",
            tally.disagreements
        ));
    }
    println!(
        "  control: one bucket's words in the wrong bucket load, and are caught ({} \
         disagreements, {} pairs missed)",
        tally.disagreements, tally.missed_pairs
    );
    Ok(())
}

fn main() -> ExitCode {
    let mut args: Vec<String> = std::env::args().skip(1).collect();
    let mut sample = None;
    if args.first().map(String::as_str) == Some("--sample") && args.len() >= 2 {
        match args[1].parse::<usize>() {
            Ok(n) if n > 0 => sample = Some(n),
            _ => {
                eprintln!("--sample takes a positive row count");
                return ExitCode::FAILURE;
            }
        }
        args.drain(..2);
    }
    let paths = args;
    if paths.is_empty() {
        eprintln!("usage: load_fold_table [--sample N] TABLE...");
        return ExitCode::FAILURE;
    }
    let mut ok = true;
    for path in &paths {
        if let Err(e) = check(path, sample) {
            eprintln!("FAIL {e}");
            ok = false;
        }
    }
    if ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}
