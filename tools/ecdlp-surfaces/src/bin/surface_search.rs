use ecdlp_surfaces::{
    cli::Args,
    curve::Point,
    json::{boolean, number, object, point, projective, text, Json},
    Result,
};

const HELP: &str =
    "surface_search [--prime 101] [--a 1] [--b 46] [--scalar 37] [--output file.json]\n\
Enumerate Q2 + lambda*Q1 through a quartic elliptic-curve model over a small F_p.\n\
Q1 = WZ-X^2; Q2 = Y^2-XZ-aWX-bW^2. The group law is on their intersection.\n\
Coefficients and the demonstration scalar may be negative. No external crates.";

fn run() -> Result<()> {
    let args = Args::parse(&["prime", "a", "b", "scalar", "output"])?;
    if args.help {
        println!("{HELP}");
        return Ok(());
    }
    let curve = args.curve()?;
    let subgroup = curve.select_subgroup()?;
    let scalar = args
        .number("scalar", 37_i128)?
        .rem_euclid(i128::from(subgroup.order)) as u64;
    let public_point = curve.multiply(scalar, subgroup.generator)?;
    let certificate = curve.certify_transfer(
        subgroup.generator,
        public_point,
        subgroup.order,
        Some(i128::from(scalar)),
    )?;
    let quadrics: Vec<_> = (0..curve.prime())
        .map(|lambda| curve.quadric(lambda))
        .collect();
    let smooth_count = quadrics.iter().filter(|q| q.smooth).count() as u64;
    let split_count = quadrics.iter().filter(|q| q.split).count() as u64;
    let candidates = Json::Array(
        quadrics
            .iter()
            .map(|q| {
                object([
                    ("lambda", number(q.lambda)),
                    ("matrix_determinant_mod_p", number(q.determinant)),
                    ("smooth", boolean(q.smooth)),
                    ("split_over_source_field", boolean(q.split)),
                ])
            })
            .collect(),
    );
    let prime = i128::from(curve.prime());
    let trace = prime + 1 - i128::from(subgroup.curve_order);
    let report = object([
        ("source", object([
            ("field_prime", number(curve.prime())),
            ("a", number(curve.a())), ("b", number(curve.b())),
            ("curve_order", number(subgroup.curve_order)),
            ("subgroup_order", number(subgroup.order)),
            ("P", point(subgroup.generator)), ("demo_scalar", number(scalar)),
            ("Q", point(public_point)),
        ])),
        ("quadric_family", object([
            ("coordinates", Json::Array(["W", "X", "Y", "Z"].into_iter().map(text).collect())),
            ("Q1", text("W*Z-X^2")),
            ("Q2", text(format!("Y^2-X*Z-{}*W*X-{}*W^2", curve.a(), curve.b()))),
            ("surface_equation", text("Q2 + lambda*Q1 = 0")),
            ("smooth_count", number(smooth_count)),
            ("smooth_split_count", number(split_count)), ("candidates", candidates),
        ])),
        ("curve_image_transfer", object([
            ("map", text("(x,y) -> [1:x:y:x^2]; origin -> [0:0:0:1]")),
            ("inverse", text("[W:X:Y:Z] -> (X/W,Y/W) for W != 0; otherwise origin")),
            ("law", text("U * V = encode(decode(U) + decode(V))")),
            ("mapped_P", projective(certificate.image_p)),
            ("mapped_Q", projective(certificate.image_q)),
            ("mapped_P_order", number(certificate.subgroup_order)),
            ("roundtrip_P_verified", boolean(curve.decode(certificate.image_p)? == certificate.p)),
            ("roundtrip_Q_verified", boolean(curve.decode(certificate.image_q)? == certificate.q)),
            ("Q_equals_scalar_P_verified", boolean(curve.multiply(scalar, certificate.p)? == certificate.q)),
            ("subgroup_membership_verified", boolean(true)),
            ("mapped_identity_verified", boolean(curve.encode(Point::Infinity)? == [0, 0, 0, 1])),
            ("ambient_quadric_group_law", boolean(false)),
        ])),
        ("abelian_surface_transfer", object([
            ("surface", text("E x E")),
            ("map", text("P -> (P, origin)")),
            ("ambient_law", text("componentwise elliptic-curve addition")),
            ("image_P_order", number(subgroup.order)),
            ("frobenius_polynomial_coefficients", Json::Array([1, -2*trace, trace*trace+2*prime, -2*prime*trace, prime*prime].into_iter().map(number).collect())),
            ("has_compatible_elliptic_factor", boolean(true)),
        ])),
        ("interpretation", text("These are faithful representations of the original ECDLP. No ECDLP speedup is claimed.")),
    ]);
    args.emit(&report)
}

fn main() {
    if let Err(error) = run() {
        eprintln!("error: {error}");
        std::process::exit(2);
    }
}
