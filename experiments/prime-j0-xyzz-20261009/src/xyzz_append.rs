// Appended after the upstream kernel by build.rs. This candidate is opt-in.

#[derive(Clone, Copy)]
struct Xyzz {
    x: Pair,
    y: Pair,
    zz: Pair,
    zzz: Pair,
    identity: bool,
}

impl Xyzz {
    fn identity() -> Self {
        Self { x: Pair::ZERO, y: Pair::one(), zz: Pair::ZERO,
               zzz: Pair::ZERO, identity: true }
    }

    fn from_affine(point: Jacobian) -> Self {
        assert!(!point.is_identity());
        Self { x: point.x, y: point.y, zz: Pair::one(),
               zzz: Pair::one(), identity: false }
    }

    fn double(self) -> Self {
        if self.identity || self.y.is_zero() {
            return Self::identity();
        }
        let u = self.y.times_field(2);
        let v = u.mul(u);
        let w = u.mul(v);
        let s = self.x.mul(v);
        let m = self.x.mul(self.x).times_field(3);
        let x = m.mul(m).sub_field(s.times_field(2));
        let y = m.mul(s.sub_field(x)).sub_field(w.mul(self.y));
        let zz = v.mul(self.zz);
        let zzz = w.mul(self.zzz);
        Self { x, y, zz, zzz, identity: false }
    }

    fn add_mixed(self, addend: Jacobian) -> Self {
        assert!(!addend.is_identity());
        if self.identity {
            return Self::from_affine(addend);
        }
        let u = addend.x.mul(self.zz);
        let s = addend.y.mul(self.zzz);
        let h = u.sub_field(self.x);
        let r = s.sub_field(self.y);
        if h.is_zero() {
            return if r.is_zero() { self.double() } else { Self::identity() };
        }
        let hh = h.mul(h);
        let hhh = h.mul(hh);
        let v = self.x.mul(hh);
        let x = r.mul(r).sub_field(hhh).sub_field(v.times_field(2));
        let y = r.mul(v.sub_field(x)).sub_field(self.y.mul(hhh));
        let zz = self.zz.mul(hh);
        let zzz = self.zzz.mul(hhh);
        Self { x, y, zz, zzz, identity: false }
    }

    fn add_mixed_deferred(self, addend: Jacobian) -> Self {
        assert!(!addend.is_identity());
        if self.identity {
            return Self::from_affine(addend);
        }
        // DEFERRED_PROTOCOL.md proves the coefficient bounds at each stage.
        let u = self.zz.mul_raw_balanced(addend.x);
        let s = self.zzz.mul_raw_balanced(addend.y);
        let h = u.sub(self.x).balance_add_output();
        let r = s.sub(self.y).balance_add_output();
        if h.is_zero() {
            return if r.is_zero() { self.double() } else { Self::identity() };
        }
        let hh = h.mul_raw_balanced(h);
        let hhh = hh.mul_raw_wide(h);
        let v = hh.mul_raw_wide(self.x);
        let x_raw = r.mul_raw_balanced(r).sub(hhh).sub(v.times_i32(2));
        let y_raw = r
            .mul_raw_wide_wide(v.sub(x_raw))
            .sub(hhh.mul_raw_wide(self.y));
        let zz_raw = hh.mul_raw_wide(self.zz);
        let zzz_raw = hhh.mul_raw_wide(self.zzz);
        Self {
            x: x_raw.balance_add_output(),
            y: y_raw.balance_add_output(),
            zz: zz_raw.balance_add_output(),
            zzz: zzz_raw.balance_add_output(),
            identity: false,
        }
    }

    fn affine_hex(self) -> String {
        if self.identity {
            return "identity".to_owned();
        }
        let inverse_zzz = self.zzz.invert_chain();
        let inverse_z = self.zz.mul(inverse_zzz);
        let inverse_zz = inverse_z.mul(inverse_z);
        let x = self.x.mul(inverse_zz).canonical_hex();
        let y = self.y.mul(inverse_zzz).canonical_hex();
        format!("{x}:{y}")
    }
}

fn check_xyzz_fixture_case(fixture_path: &str, index: usize, timed: bool, deferred: bool) {
    let fixture: Value = serde_json::from_slice(&fs::read(fixture_path).expect("read fixture"))
        .expect("parse fixture");
    assert_eq!(fixture["schema"].as_u64(), Some(1));
    let case = &fixture["cases"].as_array().expect("cases")[index];
    let base_x = case["base_x_hex"].as_str().expect("base x");
    let base_y = case["base_y_hex"].as_str().expect("base y");
    assert_eq!(base_x, GENERATOR_X_HEX);
    assert_eq!(base_y, GENERATOR_Y_HEX);
    let scalar_hex = case["scalar_hex"].as_str().expect("scalar");
    let expected = if case["expected_identity"].as_bool() == Some(true) {
        "identity".to_owned()
    } else {
        format!("{}:{}", case["expected_x_hex"].as_str().expect("expected x"),
                case["expected_y_hex"].as_str().expect("expected y"))
    };
    let preparation_start = Instant::now();
    LazyLock::force(&SCALAR_LATTICE);
    LazyLock::force(&DECODE_CONSTANTS);
    let retained_bytes = unit_orbit_windows::warm_format(14);
    let scalar = scalar_from_hex(scalar_hex);
    let preparation_ms = preparation_start.elapsed().as_secs_f64() * 1000.0;
    let start = Instant::now();
    let point = if deferred {
        unit_orbit_windows::multiply_xyzz_deferred_format(&scalar, 14).0
    } else {
        unit_orbit_windows::multiply_xyzz_format(&scalar, 14).0
    };
    let actual = point.affine_hex();
    assert_eq!(actual, expected, "XYZZ fixture mismatch");
    let online_ms = start.elapsed().as_secs_f64() * 1000.0;
    let mode = if deferred { "unit_orbit_u14_xyzz_deferred_fixed" }
               else { "unit_orbit_u14_xyzz_fixed" };
    if timed {
        println!("online_ms={online_ms:.6} preparation_ms={preparation_ms:.6} retained_bytes={retained_bytes} verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode={mode}");
    } else {
        println!("verified=1 curve=secp256k1 base_x={base_x} base_y={base_y} scalar={scalar_hex} point={actual} mode={mode}");
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() == 3
        && (args[0] == "--benchmark-scalar-unit-orbit-u14-xyzz-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-u14-xyzz-fixed-case"
            || args[0] == "--benchmark-scalar-unit-orbit-u14-xyzz-deferred-fixed-case"
            || args[0] == "--check-scalar-unit-orbit-u14-xyzz-deferred-fixed-case")
    {
        let index = args[2].parse::<usize>().expect("case index");
        check_xyzz_fixture_case(&args[1], index, args[0].starts_with("--benchmark-"),
                                args[0].contains("-deferred-"));
        return;
    }
    let deferred = args == ["--scalar-unit-orbit-u14-xyzz-deferred-fixed"];
    let jacobian_control = args == ["--scalar-unit-orbit-u14-jacobian-affine-control"];
    if !deferred && !jacobian_control && args != ["--scalar-unit-orbit-u14-xyzz-fixed"] {
        upstream_main();
        return;
    }
    unit_orbit_windows::warm_format(14);
    for line in io::stdin().lock().lines() {
        let line = line.expect("input line");
        if line.trim().is_empty() {
            continue;
        }
        let scalar = scalar_from_hex(line.trim());
        if jacobian_control {
            let (point, a, b, additions, retained_bytes) =
                unit_orbit_windows::multiply_format(&scalar, 14);
            println!("{}", json!({
                "point": point.affine_hex(),
                "representative": [a.to_string(), b.to_string()],
                "generic_additions": additions,
                "retained_bytes": retained_bytes,
                "mode": "unit_orbit_u14_jacobian_control",
            }));
            continue;
        }
        let (point, a, b, additions, retained_bytes) = if deferred {
            unit_orbit_windows::multiply_xyzz_deferred_format(&scalar, 14)
        } else {
            unit_orbit_windows::multiply_xyzz_format(&scalar, 14)
        };
        println!("{}", json!({
            "point": point.affine_hex(),
            "representative": [a.to_string(), b.to_string()],
            "generic_additions": additions,
            "retained_bytes": retained_bytes,
            "mode": if deferred { "unit_orbit_u14_xyzz_deferred_fixed" }
                    else { "unit_orbit_u14_xyzz_fixed" },
        }));
    }
}

#[cfg(test)]
mod deferred_xyzz_tests {
    use super::*;

    #[test]
    fn exceptional_addends_after_affine_and_nonaffine_accumulation() {
        let p = Jacobian::generator();
        let two_p = p.double().into_affine();
        let initial = Xyzz::identity().add_mixed_deferred(p);
        assert_eq!(initial.affine_hex(), p.affine_hex());
        assert_eq!(initial.add_mixed_deferred(p).affine_hex(), two_p.affine_hex());
        assert!(initial.add_mixed_deferred(p.neg()).identity);

        let three_p = p.add_mixed(two_p).into_affine();
        let nonaffine = initial.add_mixed_deferred(two_p);
        assert_eq!(nonaffine.affine_hex(), three_p.affine_hex());
        assert_eq!(nonaffine.add_mixed_deferred(three_p).affine_hex(),
                   three_p.double().affine_hex());
        assert!(nonaffine.add_mixed_deferred(three_p.neg()).identity);
    }
}
