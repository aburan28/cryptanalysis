// Included in a disposable copy of eisenstein_fixed.rs by native_overlay.py.

fn split671_audit_cli() {
    let retained = unit_orbit_windows::split671_warm();
    let checked = unit_orbit_windows::split671_audit();
    println!("verified=1 residues={checked} point_entries=1044625 retained_bytes={retained}");
}

fn split671_atlas_cli() {
    use std::io::Write;
    unit_orbit_windows::split671_warm();
    std::io::stdout().write_all(&unit_orbit_windows::split671_atlas_bytes())
        .expect("write split-top radix-671 atlas bytes");
}

fn split671_fixture(path: &str, only_case: Option<usize>) {
    let fixture: Value = serde_json::from_slice(&fs::read(path).expect("read fixture"))
        .expect("parse fixture");
    assert_eq!(fixture["schema"].as_u64(), Some(1));
    let cases = fixture["cases"].as_array().expect("fixture cases");
    LazyLock::force(&HYBRID_FIELD);
    let retained = unit_orbit_windows::split671_warm();
    let indices: Box<dyn Iterator<Item = usize>> = match only_case {
        Some(index) => Box::new(std::iter::once(index)),
        None => Box::new(0..cases.len()),
    };
    for index in indices {
        let case = &cases[index];
        assert_eq!(case["index"].as_u64(), Some(index as u64));
        assert_eq!(case["base_x_hex"].as_str(), Some(GENERATOR_X_HEX));
        assert_eq!(case["base_y_hex"].as_str(), Some(GENERATOR_Y_HEX));
        let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
        let scalar = scalar_from_hex(scalar_hex);
        let words = scalar_words_256(&scalar).expect("unsigned 256-bit scalar");
        let expected = if case["expected_identity"].as_bool() == Some(true) {
            "identity".to_owned()
        } else {
            format!("{}:{}",
                case["expected_x_hex"].as_str().expect("expected x"),
                case["expected_y_hex"].as_str().expect("expected y"))
        };
        let start = Instant::now();
        let (point, _, additions, retained_bytes, _, _, rotations) =
            unit_orbit_windows::multiply_u256_split671(words);
        assert_eq!(point, expected, "split-top radix-671 point mismatch at case {index}");
        let online_ms = start.elapsed().as_secs_f64() * 1000.0;
        assert_eq!(retained_bytes, retained);
        if only_case.is_some() {
            println!("verified=1 online_ms={online_ms:.6} index={index} \
                      additions={additions} rotations={rotations} \
                      retained_bytes={retained_bytes} point={point} \
                      curve=secp256k1 base_x={GENERATOR_X_HEX} \
                      base_y={GENERATOR_Y_HEX} scalar={scalar_hex}");
        } else {
            println!("{}", json!({"index": index, "verified": true,
                "point": point, "additions": additions,
                "rotations": rotations, "retained_bytes": retained_bytes}));
        }
    }
}
