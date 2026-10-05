//! Bounded native bielliptic-quartic correctness diagnostic.
//! Public path modules also permit dependency-free `rustc` replay.

#[path = "../cryptanalysis/bielliptic_quartic.rs"]
pub mod bielliptic_quartic;
#[path = "../hash/sha256.rs"]
pub mod metadata_sha256;

use bielliptic_quartic::{
    collect_relations, prepare, recover, Collection, Cover, EcPoint, Limits, Precomputation,
    QuarticPoint, RecoveryReport, MAX_PAIR_TRIALS, MAX_TARGET_SHIFTS,
};
use std::collections::BTreeMap;

fn hash(bytes: &[u8]) -> String {
    metadata_sha256::sha256(bytes)
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn ec(point: EcPoint) -> String {
    match point {
        EcPoint::Infinity => "\"infinity\"".into(),
        EcPoint::Affine { x, y } => format!("[{x},{y}]"),
    }
}

fn quartic(point: QuarticPoint) -> String {
    match point {
        QuarticPoint::Infinity => "\"infinity\"".into(),
        QuarticPoint::Affine { x, v } => format!("[{x},{v}]"),
    }
}

fn point(text: &str) -> Result<EcPoint, String> {
    if text == "infinity" {
        return Ok(EcPoint::Infinity);
    }
    let (x, y) = text
        .split_once(',')
        .ok_or("point must be x,y or infinity")?;
    Ok(EcPoint::Affine {
        x: x.parse().map_err(|_| "invalid point x")?,
        y: y.parse().map_err(|_| "invalid point y")?,
    })
}

fn certificates(collection: &Collection) -> String {
    let records: Vec<_> = collection
        .certificates
        .iter()
        .map(|certificate| {
            let terms: Vec<_> = certificate
                .terms
                .iter()
                .map(|&(point, multiplicity)| {
                    format!(
                        "{{\"multiplicity\":{multiplicity},\"point\":{}}}",
                        quartic(point)
                    )
                })
                .collect();
            let line = certificate.line;
            format!(
                "{{\"line\":[{},{},{}],\"terms\":[{}]}}",
                line.a,
                line.b,
                line.c,
                terms.join(",")
            )
        })
        .collect();
    format!("[{}]", records.join(","))
}

fn emit(
    cover: &Cover,
    generator: Option<EcPoint>,
    collection: &Collection,
    precomputed: Option<&Precomputation>,
    recovered: Option<&RecoveryReport>,
    limits: Limits,
) {
    let (a, b) = cover.coefficients();
    let p = cover.modulus();
    let order = cover.group_order();
    let trace = p as i64 + 1 - order as i64;
    let gen = generator.map(ec).unwrap_or_else(|| "null".into());
    let cofactor = if precomputed.is_some() { "1" } else { "null" };
    let subgroup = precomputed
        .map(|pre| pre.subgroup_order().to_string())
        .unwrap_or_else(|| "null".into());
    // Canonical compact sorted-key JSON. Generator and subgroup are identity inputs.
    let field = format!("{{\"characteristic\":{p},\"degree\":1,\"element_encoding\":\"canonical-integer\",\"modulus\":{p},\"representation\":\"prime-field\"}}");
    let curve = format!("{{\"a\":{a},\"b\":{b},\"cofactor\":{cofactor},\"generator\":{gen},\"model\":\"y^2=x^3+a*x+b\",\"order\":{order},\"subgroup_order\":{subgroup},\"target_group\":\"E(F_p)\",\"trace\":{trace}}}");
    let curve_record = format!("{{\"curve\":{curve},\"field\":{field}}}");
    let digest = hash(curve_record.as_bytes());
    let bits = 64 - p.leading_zeros();
    let alias = format!("EC1P{bits}Cquartich{}", &digest[..12]);
    let certs = certificates(collection);
    let stats = &collection.stats;
    let prep = if let Some(pre) = precomputed {
        let base = format!(
            "[{}]",
            pre.factor_base()
                .iter()
                .copied()
                .map(ec)
                .collect::<Vec<_>>()
                .join(",")
        );
        let logs = pre
            .factor_logs()
            .map(|logs| {
                format!(
                    "[{}]",
                    logs.iter()
                        .map(u64::to_string)
                        .collect::<Vec<_>>()
                        .join(",")
                )
            })
            .unwrap_or_else(|| "null".into());
        format!("{{\"anchor_multiple\":{},\"complete\":{},\"dependent_line_rows\":{},\"factor_base\":{base},\"factor_base_sha256\":\"{}\",\"factor_logs\":{logs},\"independent_line_rows\":{},\"matrix_columns\":{},\"matrix_rank\":{},\"replayed_factor_logs\":{},\"usable_norm_images\":{},\"zero_projected_rows\":{}}}",
            pre.anchor_multiple, pre.is_complete(), pre.dependent_line_rows, hash(base.as_bytes()),
            pre.independent_line_rows, pre.matrix_columns, pre.matrix_rank, pre.replayed_factor_logs,
            pre.usable_norm_images, pre.zero_projected_rows)
    } else {
        "null".into()
    };
    let recovery = if let Some(report) = recovered {
        let scalar = report
            .scalar
            .map(|x| x.to_string())
            .unwrap_or_else(|| "null".into());
        let shift = report
            .shift
            .map(|x| x.to_string())
            .unwrap_or_else(|| "null".into());
        let sign = report
            .fiber_sign
            .map(|x| x.to_string())
            .unwrap_or_else(|| "null".into());
        let fiber = report
            .fiber
            .map(|(left, right)| format!("[{},{}]", quartic(left), quartic(right)))
            .unwrap_or_else(|| "null".into());
        format!("{{\"fiber\":{fiber},\"fiber_sign\":{sign},\"scalar\":{scalar},\"shift\":{shift},\"shifts_tested\":{},\"status\":\"{}\",\"target\":{},\"verified\":{}}}", report.shifts_tested, report.status, ec(report.target), report.verified)
    } else {
        "null".into()
    };
    let status = recovered
        .map(|report| report.status)
        .unwrap_or("collection_only");
    println!("{{\"schema\":\"bielliptic-quartic-diagnostic/v1\",\"scope\":\"tiny-prime-field-elliptic-norm-projection\",\"status\":\"{status}\",\"candidate_id\":null,\"curve_id\":\"{alias}\",\"curve_uid\":\"urn:ec-record:1:sha256:{digest}\",\"curve_record\":{curve_record},\"implementation\":{{\"kernel_sha256\":\"{}\",\"cli_sha256\":\"{}\"}},\"limits\":{{\"pair_trials\":{},\"target_shifts\":{}}},\"collection\":{{\"rational_points\":{},\"possible_pairs\":{},\"pair_trials\":{},\"unique_lines\":{},\"duplicate_lines\":{},\"nonsplit_residuals\":{},\"certified_relations\":{},\"budget_exhausted\":{},\"all_certificates_verified\":true,\"certificates_sha256\":\"{}\"}},\"certificates\":{certs},\"precomputation\":{prep},\"recovery\":{recovery},\"costs\":{{\"online_ms\":null,\"cold_ms\":null,\"total_operations\":null,\"rho_comparison\":null,\"speedup\":null}}}}",
        hash(include_bytes!("../cryptanalysis/bielliptic_quartic.rs")), hash(include_bytes!("quartic_ic.rs")),
        limits.pair_trials, limits.target_shifts, stats.rational_points, stats.possible_pairs,
        stats.pair_trials, stats.unique_lines, stats.duplicate_lines, stats.nonsplit_residuals,
        stats.certified_relations, stats.budget_exhausted, hash(certs.as_bytes()));
}

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "--help".into());
    if command == "--help" || command == "-h" {
        println!(
            "quartic-ic: certified tiny-field bielliptic quartic diagnostic\n\
            demo [--max-pairs N] [--max-shifts N]\n\
            collect --p P --a A --b B [--max-pairs N]\n\
            solve --p P --a A --b B --generator X,Y --target X,Y [--max-pairs N] [--max-shifts N]\n\
            Prime fields 5 <= P <= 257 only. Solve requires prime elliptic group order.\n\
            Recovery and certificate JSON are diagnostics; performance quantities remain null."
        );
        return Ok(());
    }
    if !["demo", "collect", "solve"].contains(&command.as_str()) {
        return Err("unknown command; use --help".into());
    }
    let mut options = BTreeMap::new();
    while let Some(key) = args.next() {
        if ![
            "--p",
            "--a",
            "--b",
            "--generator",
            "--target",
            "--max-pairs",
            "--max-shifts",
        ]
        .contains(&key.as_str())
        {
            return Err("unknown option; use --help".into());
        }
        let value = args.next().ok_or("option requires a value")?;
        if options.insert(key, value).is_some() {
            return Err("duplicate option".into());
        }
    }
    if command == "demo"
        && options
            .keys()
            .any(|key| !["--max-pairs", "--max-shifts"].contains(&key.as_str()))
    {
        return Err("demo has fixed inputs; only budgets may be set".into());
    }
    if command == "collect"
        && (options.contains_key("--generator") || options.contains_key("--target"))
    {
        return Err("collect does not accept generator or target".into());
    }
    let number = |key: &str, default: Option<u64>| -> Result<u64, String> {
        match options.get(key) {
            Some(value) => value.parse().map_err(|_| format!("invalid {key}")),
            None => default.ok_or_else(|| format!("missing {key}")),
        }
    };
    let limits = Limits {
        pair_trials: usize::try_from(number("--max-pairs", Some(MAX_PAIR_TRIALS as u64))?)
            .map_err(|_| "pair budget overflow")?,
        target_shifts: number("--max-shifts", Some(MAX_TARGET_SHIFTS))?,
    };
    let cover = if command == "demo" {
        Cover::new(53, 2, 1)
    } else {
        Cover::new(
            number("--p", None)?,
            number("--a", None)?,
            number("--b", None)?,
        )
    }
    .map_err(|error| error.to_string())?;
    if command == "collect" {
        let collection = collect_relations(&cover, limits).map_err(|error| error.to_string())?;
        emit(&cover, None, &collection, None, None, limits);
    } else {
        let generator = if command == "demo" {
            EcPoint::Affine { x: 0, y: 1 }
        } else {
            point(options.get("--generator").ok_or("missing --generator")?)?
        };
        // Fixed known-answer fixture construction is separate from the solver API.
        let target = if command == "demo" {
            cover
                .mul(generator, 17)
                .map_err(|error| error.to_string())?
        } else {
            point(options.get("--target").ok_or("missing --target")?)?
        };
        let precomputed = prepare(cover, generator, limits).map_err(|error| error.to_string())?;
        let report = recover(&precomputed, target, limits).map_err(|error| error.to_string())?;
        emit(
            precomputed.cover(),
            Some(generator),
            &precomputed.collection,
            Some(&precomputed),
            Some(&report),
            limits,
        );
        if !report.verified {
            return Err(report.status.into());
        }
    }
    Ok(())
}

fn main() {
    if let Err(error) = run() {
        eprintln!("quartic-ic: {error}");
        std::process::exit(2);
    }
}
