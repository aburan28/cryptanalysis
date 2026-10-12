use ecdlp_surfaces::{
    cli::{parse_point, Args},
    json::{boolean, number, object, point, projective, text, Json},
    Result,
};

const HELP: &str = "transfer_check [--prime 101] [--a 1] [--b 46] [--r 109]\n\
  [--p-point 2,37] [--q-point 64,19] [--scalar n] [--output file.json]\n\
Certify the explicit quartic-model transfer on a prime cyclic subgroup.\n\
Use O for the identity. --scalar is optional; an unknown discrete log is not required.\n\
Subgroup membership is checked by enumeration, so only small fields are supported.";

fn run() -> Result<()> {
    let args = Args::parse(&[
        "prime", "a", "b", "r", "p-point", "q-point", "scalar", "output",
    ])?;
    if args.help {
        println!("{HELP}");
        return Ok(());
    }
    let curve = args.curve()?;
    let p = parse_point(&curve, args.get("p-point").unwrap_or("2,37"))?;
    let q = parse_point(&curve, args.get("q-point").unwrap_or("64,19"))?;
    let r = args.number("r", 109_u64)?;
    let certificate = curve.certify_transfer(p, q, r, args.optional_number("scalar")?)?;
    let report = object([
        ("source", object([
            ("field_prime", number(curve.prime())),
            ("a", number(curve.a())), ("b", number(curve.b())),
            ("curve_order", number(certificate.curve_order)),
            ("subgroup_order", number(r)), ("P", point(p)), ("Q", point(q)),
        ])),
        ("transfer", object([
            ("map", text("(x,y) -> [1:x:y:x^2]; origin -> [0:0:0:1]")),
            ("inverse", text("[W:X:Y:Z] -> (X/W,Y/W) for W != 0; otherwise origin")),
            ("law", text("U * V = encode(decode(U) + decode(V))")),
            ("image_P", projective(certificate.image_p)),
            ("image_Q", projective(certificate.image_q)),
            ("image_P_order", number(r)),
            ("P_has_prime_order_r", boolean(true)),
            ("Q_in_generated_subgroup", boolean(true)),
            ("roundtrip_P_verified", boolean(curve.decode(certificate.image_p)? == p)),
            ("roundtrip_Q_verified", boolean(curve.decode(certificate.image_q)? == q)),
            ("scalar_mod_r", certificate.scalar.map(number).unwrap_or(Json::Null)),
            ("scalar_relation_verified", certificate.scalar.map(|_| boolean(true)).unwrap_or(Json::Null)),
            ("ambient_quadric_group_law", boolean(false)),
        ])),
        ("interpretation", text("The map is injective and the transported group law preserves the ECDLP relation. Subgroup membership was enumerated; no faster target solver is supplied.")),
    ]);
    args.emit(&report)
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(2);
    }
}
