//! **Write the plan a device needs to build a folded pair table.**
//!
//! A folded build walks one row per signed Frobenius orbit, each over
//! the orbit-sorted suffix of the base that starts at its own orbit, and
//! names every sum in a normal basis.  None of that is the device's to
//! decide: the rows are `PairSumTable::folded_rows`, the basis is
//! `FrobeniusCanon`'s, and a device that derived either for itself would
//! build a table the CPU could not read.  So the CPU writes them down.
//!
//! The format is documented in `gpu/ecc2k/fold_io.hpp`, beside the
//! reader; `gpu/ecc2k/fold2k.cu` reads it, builds the table on a GPU and
//! writes the table file `examples/load_fold_table.rs` checks.  The
//! emulation test reads it too (`test_emu_* --plan`), and requires it to
//! be `vec_fold.h`'s plan exactly for the same base.
//!
//! Usage: `cargo run --release --example dump_fold_plan -- DEGREE POINTS SEED OUT`
//! with `SEED` in decimal or `0x` hex.  The base is
//! `build_subgroup_orbit_factor_base(KoblitzCurve::new(0, DEGREE), SEED, POINTS)`,
//! which is what the table file names so that the CPU can rebuild it.
use std::io::Write;
use std::process::ExitCode;

use cryptanalysis_suite::cryptanalysis::koblitz_fast::{FastCurve, FrobeniusCanon};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_subgroup_orbit_factor_base, FoldedRows, KoblitzCurve, PairSumTable,
};

fn parse_u64(s: &str) -> Result<u64, String> {
    match s.strip_prefix("0x") {
        Some(hex) => u64::from_str_radix(&hex.replace('_', ""), 16),
        None => s.replace('_', "").parse(),
    }
    .map_err(|e| format!("{s}: {e}"))
}

fn put_u32s(bytes: &mut Vec<u8>, values: impl IntoIterator<Item = u32>) {
    for v in values {
        bytes.extend_from_slice(&v.to_le_bytes());
    }
}

fn put_u64s(bytes: &mut Vec<u8>, values: impl IntoIterator<Item = u64>) {
    for v in values {
        bytes.extend_from_slice(&v.to_le_bytes());
    }
}

fn run(args: &[String]) -> Result<(), String> {
    let [degree, points, seed, out] = args else {
        return Err("usage: dump_fold_plan DEGREE POINTS SEED OUT".into());
    };
    let degree = u32::try_from(parse_u64(degree)?).map_err(|e| e.to_string())?;
    let request = u32::try_from(parse_u64(points)?).map_err(|e| e.to_string())?;
    let seed = parse_u64(seed)?;
    let kc = KoblitzCurve::new(0, degree).ok_or("no Koblitz curve at that degree")?;
    let fb = build_subgroup_orbit_factor_base(&kc, seed, request as usize)?;
    let curve = FastCurve::new(&kc.curve).ok_or("field too wide for single-word arithmetic")?;
    let canon = FrobeniusCanon::new(&curve.field, degree).ok_or("no normal element found")?;
    let FoldedRows {
        reps,
        order,
        suffix,
    } = PairSumTable::folded_rows(&fb);
    let points: Vec<_> = fb.points.iter().map(|p| curve.lift(p)).collect();
    if points.iter().any(|p| p.infinity) {
        return Err("a subgroup base has no O, and this one does".into());
    }

    let mut bytes: Vec<u8> = Vec::new();
    bytes.extend_from_slice(b"PTPLAN1\0");
    put_u32s(&mut bytes, [degree, request]);
    put_u64s(&mut bytes, [seed]);
    put_u32s(
        &mut bytes,
        [
            points.len() as u32,
            fb.signed_orbits.len() as u32,
            reps.len() as u32,
            canon.tables().len() as u32,
        ],
    );
    put_u64s(&mut bytes, canon.tables().iter().flatten().copied());
    put_u64s(&mut bytes, order.iter().map(|&i| points[i as usize].x));
    put_u64s(&mut bytes, order.iter().map(|&i| points[i as usize].y));
    put_u32s(&mut bytes, suffix.iter().copied());
    put_u32s(&mut bytes, reps.iter().map(|&(o, _)| o));
    put_u64s(&mut bytes, reps.iter().map(|&(_, i)| points[i].x));
    put_u64s(&mut bytes, reps.iter().map(|&(_, i)| points[i].y));

    std::fs::File::create(out)
        .and_then(|mut f| f.write_all(&bytes))
        .map_err(|e| format!("{out}: {e}"))?;
    eprintln!(
        "{out}: n = {degree}, {} points in {} signed orbits, {} rows; folded table about \
         {} bytes",
        points.len(),
        fb.signed_orbits.len(),
        reps.len(),
        PairSumTable::folded_byte_size(reps.len(), points.len(), degree),
    );
    Ok(())
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(e) => {
            eprintln!("dump_fold_plan: {e}");
            ExitCode::FAILURE
        }
    }
}
