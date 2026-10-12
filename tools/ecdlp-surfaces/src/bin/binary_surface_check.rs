use ecdlp_surfaces::{
    binary::{check_n83, parse_binary_point},
    cli::Args,
    json::{object, text, Json},
    Result,
};

const HELP: &str = "binary_surface_check [--degree 83] [--a 0|1|both] [--scalar 37]\n\
  [--q-point 0xX,0xY|O] [--output file.json]\n\
Checks the pinned Koblitz curves y^2+x*y=x^3+a*x^2+1 over GF(2^83),\n\
using z^83+z^45+z^2+z+1 and the recorded generators and subgroup orders.\n\
Default: both variants, public demonstration Q=37P. A supplied Q requires\n\
one --a; --scalar is then optional. Exact large integers are JSON strings.\n\
Counts quadrics algebraically; no field-wide or subgroup enumeration.\n\
The a=0 primality proof is reused from the cited repository Sage receipt.";

fn run() -> Result<()> {
    let args = Args::parse(&["degree", "a", "scalar", "q-point", "output"])?;
    if args.help {
        println!("{HELP}");
        return Ok(());
    }
    if args.number("degree", 83_u32)? != 83 {
        return Err("This CLI contains only the pinned degree-83 fixtures.".into());
    }
    let variants: &[u8] = match args.get("a").unwrap_or("both") {
        "0" => &[0],
        "1" => &[1],
        "both" => &[0, 1],
        _ => return Err("Choose --a 0, --a 1, or --a both.".into()),
    };
    let target = args.get("q-point").map(parse_binary_point).transpose()?;
    if target.is_some() && variants.len() != 1 {
        return Err("A supplied Q requires a single --a variant.".into());
    }
    let scalar = args.optional_number("scalar")?;
    let cases = variants
        .iter()
        .map(|&a| check_n83(a, scalar, target))
        .collect::<Result<Vec<_>>>()?;
    args.emit(&object([
        ("schema", text("ecdlp.binary-surface-run/v1")),
        ("cases", Json::Array(cases)),
    ]))
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(2);
    }
}
