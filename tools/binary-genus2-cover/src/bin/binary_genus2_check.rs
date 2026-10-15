use binary_genus2_cover::checks::{check_n83, small_field_controls};
use ecdlp_surfaces::{binary::parse_binary_point, cli::Args};
use serde_json::json;

fn run() -> Result<(), String> {
    let args = Args::parse(&["a", "q-point", "scalar", "output"])?;
    if args.help {
        println!("binary_genus2_check [--a 0|1|both] [--q-point 0xX,0xY|O] [--scalar K] [--output FILE]\n\
Constructs a same-field genus-two cover and checks Jacobian transfers for the pinned GF(2^83) fixtures.\n\
Default: both a values, public Q=37P. Supplied Q requires one a; omit --scalar for an unknown log.\n\
The basis is z^83+z^45+z^2+z+1. No generic norm or unknown-log solver is provided.");
        return Ok(());
    }
    let variants: &[u8] = match args.get("a").unwrap_or("both") {
        "0" => &[0],
        "1" => &[1],
        "both" => &[0, 1],
        _ => return Err("choose --a 0, 1, or both".into()),
    };
    let q = args.get("q-point").map(parse_binary_point).transpose()?;
    if q.is_some() && variants.len() != 1 {
        return Err("a supplied Q requires a single --a".into());
    }
    let scalar = args.optional_number("scalar")?;
    let cases = variants
        .iter()
        .map(|&a| check_n83(a, q, scalar))
        .collect::<Result<Vec<_>, _>>()?;
    let report = json!({"schema":"ecdlp.binary-genus2-run/v1","cases":cases,
        "small_field_controls":small_field_controls()?,
        "interpretation":"Explicit genus-two cover and image subgroup arithmetic; no descent or faster ECDLP solver established."});
    let encoded = serde_json::to_string_pretty(&report).map_err(|e| e.to_string())? + "\n";
    if let Some(path) = args.get("output") {
        std::fs::write(path, encoded).map_err(|e| e.to_string())?;
        println!("Wrote {path}");
    } else {
        print!("{encoded}");
    }
    Ok(())
}

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e}");
        std::process::exit(2);
    }
}
