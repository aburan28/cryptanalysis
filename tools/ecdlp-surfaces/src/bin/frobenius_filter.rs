use ecdlp_surfaces::{
    cli::Args,
    frobenius::filter,
    json::{boolean, number, object, text, Json},
    Result,
};

const HELP: &str = "frobenius_filter [--q 101] [--trace -7] [--coeffs 14,251,1414,10201]\n\
  [--output file.json]\n\
Input surface polynomial: T^4+c1*T^3+c2*T^2+c3*T+c4 (coeffs=c1,c2,c3,c4).\n\
Source polynomial: T^2-trace*T+q. Defaults describe E x E for the example curve.\n\
Passing is a necessary-condition filter; it does not construct a transfer map.";

fn run() -> Result<()> {
    let args = Args::parse(&["q", "trace", "coeffs", "output"])?;
    if args.help {
        println!("{HELP}");
        return Ok(());
    }
    let pieces = args
        .get("coeffs")
        .unwrap_or("14,251,1414,10201")
        .split(',')
        .map(|piece| {
            piece
                .trim()
                .parse::<i128>()
                .map_err(|_| "Invalid polynomial coefficient.".to_owned())
        })
        .collect::<Result<Vec<_>>>()?;
    let coefficients: [i128; 4] = pieces
        .try_into()
        .map_err(|_| "Supply exactly four coefficients c1,c2,c3,c4.")?;
    let result = filter(
        args.number("q", 101_u64)?,
        args.number("trace", -7_i128)?,
        coefficients,
    )?;
    let mut surface_coefficients = vec![number(1)];
    surface_coefficients.extend(result.coefficients.into_iter().map(number));
    let report = object([
        ("field_size", number(result.q)),
        ("source_polynomial_coefficients", Json::Array(vec![number(1), number(-result.source_trace), number(result.q)])),
        ("surface_polynomial_coefficients", Json::Array(surface_coefficients)),
        ("quotient_coefficients", Json::Array(result.quotient.into_iter().map(number).collect())),
        ("remainder_coefficients", Json::Array(result.remainder.into_iter().map(number).collect())),
        ("source_polynomial_divides", boolean(result.divides)),
        ("surface_reciprocal_conditions_pass", boolean(result.reciprocal)),
        ("quotient_elliptic_shape", boolean(result.quotient_elliptic_shape)),
        ("quotient_hasse_bound_pass", boolean(result.quotient_hasse_bound)),
        ("passes_necessary_conditions", boolean(result.passes_necessary_conditions())),
        ("subgroup_transfer_certified", boolean(false)),
        ("interpretation", text("This filters supplied Frobenius polynomials. It does not validate existence of a variety, construct a homomorphism, or certify subgroup preservation.")),
    ]);
    args.emit(&report)
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(2);
    }
}
