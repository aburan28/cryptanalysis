// Included in a disposable copy of eisenstein_fixed.rs by native_overlay.py.

fn radix929_audit_cli() {
    let retained = unit_orbit_windows::radix929_warm();
    let checked = unit_orbit_windows::radix929_audit();
    println!("verified=1 top_states={checked} top_orbits=136993 \
              point_entries=1863085 retained_bytes={retained}");
}

fn radix929_atlas_cli() {
    use std::io::Write;
    unit_orbit_windows::radix929_warm();
    std::io::stdout().write_all(&unit_orbit_windows::radix929_atlas_bytes())
        .expect("write radix-929 atlas bytes");
}

fn radix929_fixture(path: &str, only_case: Option<usize>) {
    let fixture: Value = serde_json::from_slice(&fs::read(path).expect("read fixture"))
        .expect("parse fixture");
    assert_eq!(fixture["schema"].as_u64(), Some(1));
    let cases = fixture["cases"].as_array().expect("fixture cases");
    LazyLock::force(&HYBRID_FIELD);
    let retained = unit_orbit_windows::radix929_warm();
    let indices: Box<dyn Iterator<Item = usize>> = match only_case {
        Some(index) => Box::new(std::iter::once(index)),
        None => Box::new(0..cases.len()),
    };
    for index in indices {
        let case = &cases[index];
        assert_eq!(case["index"].as_u64(), Some(index as u64));
        assert_eq!(case["base_x_hex"].as_str(), Some(GENERATOR_X_HEX));
        assert_eq!(case["base_y_hex"].as_str(), Some(GENERATOR_Y_HEX));
        let scalar = scalar_from_hex(case["scalar_hex"].as_str().expect("scalar"));
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
            unit_orbit_windows::multiply_u256_radix929_gauge_tree_pareto(words);
        assert_eq!(point, expected, "radix-929 point mismatch at case {index}");
        let online_ms = start.elapsed().as_secs_f64() * 1000.0;
        assert_eq!(retained_bytes, retained);
        if only_case.is_some() {
            println!("verified=1 online_ms={online_ms:.6} index={index} \
                      additions={additions} rotations={rotations} \
                      retained_bytes={retained_bytes} point={point}");
        } else {
            println!("{}", json!({"index": index, "verified": true,
                "point": point, "additions": additions,
                "rotations": rotations, "retained_bytes": retained_bytes}));
        }
    }
}
