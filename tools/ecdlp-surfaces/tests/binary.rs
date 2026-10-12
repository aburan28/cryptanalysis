use ecdlp_surfaces::binary::{
    check_n83, is_prime_u64, n83_fixture, parse_binary_point, power_of_two_decimal, BinaryCurve,
    BinaryField, BinaryPoint,
};

fn points(curve: BinaryCurve) -> Vec<BinaryPoint> {
    let mut points = vec![BinaryPoint::Infinity];
    for x in 0..curve.field().size() {
        for y in 0..curve.field().size() {
            let point = BinaryPoint::Affine(x, y);
            if curve.is_on_curve(point) {
                points.push(point);
            }
        }
    }
    points
}

// Independent carryless schoolbook multiplication followed by polynomial long
// division in three u64 words, rather than the producer's shift-and-reduce loop.
fn reference_multiply(field: BinaryField, lhs: u128, rhs: u128) -> u128 {
    let mut product = [0_u64; 3];
    for i in 0..field.degree() {
        for j in 0..field.degree() {
            if (lhs >> i) & (rhs >> j) & 1 != 0 {
                let bit = (i + j) as usize;
                product[bit / 64] ^= 1_u64 << (bit % 64);
            }
        }
    }
    for bit in (field.degree()..2 * field.degree() - 1).rev() {
        let bit = bit as usize;
        if product[bit / 64] >> (bit % 64) & 1 != 0 {
            product[bit / 64] ^= 1_u64 << (bit % 64);
            for term in 0..field.degree() {
                if field.low_terms() >> term & 1 != 0 {
                    let power = bit - field.degree() as usize + term as usize;
                    product[power / 64] ^= 1_u64 << (power % 64);
                }
            }
        }
    }
    assert_eq!(product[2], 0);
    u128::from(product[0]) | (u128::from(product[1]) << 64)
}

#[test]
fn binary_field_rejects_reducible_and_malformed_moduli() {
    assert!(BinaryField::new(0, 1).is_err());
    assert!(BinaryField::new(84, 7).is_err());
    assert!(BinaryField::new(3, 2).is_err());
    assert!(BinaryField::new(3, 8).is_err());
    assert!(BinaryField::new(83, 1).is_err());
    assert!(BinaryField::new(83, (1_u128 << 45) | 7).is_ok());
    assert!(BinaryField::new(83, (1_u128 << 7) | (1 << 4) | (1 << 2) | 1).is_ok());
}

#[test]
fn wide_field_arithmetic_matches_independent_polynomial_reduction() {
    let field = BinaryField::new(83, (1_u128 << 45) | 7).unwrap();
    let mut state = 0xA317_9862_07D1_256E_F901_u128;
    for _ in 0..32 {
        state ^= state << 13;
        state ^= state >> 7;
        let lhs = state & (field.size() - 1);
        state ^= state << 17;
        let rhs = state & (field.size() - 1);
        assert_eq!(
            field.multiply(lhs, rhs),
            reference_multiply(field, lhs, rhs)
        );
        if lhs != 0 {
            assert_eq!(field.multiply(lhs, field.inverse(lhs).unwrap()), 1);
        }
        assert_eq!(field.power(lhs, field.size()), lhs);
    }
    assert_eq!(field.trace(1), 1);
    assert_eq!(field.inverse(0), None);
}

#[test]
fn frobenius_order_and_pencil_counts_match_exhaustive_small_fields() {
    for (degree, low_terms) in [(1, 1), (2, 3), (3, 3), (4, 3), (5, 5)] {
        let field = BinaryField::new(degree, low_terms).unwrap();
        for a in [0, 1] {
            let curve = BinaryCurve::new(field, a).unwrap();
            let enumerated = points(curve);
            assert_eq!(curve.trace_and_order().1, enumerated.len() as u128);
            let members: Vec<_> = (0..field.size())
                .map(|l| curve.quadric(l).unwrap())
                .collect();
            let smooth = members.iter().filter(|m| m.smooth).count() as u128;
            let split = members.iter().filter(|m| m.split == Some(true)).count() as u128;
            let (expected_smooth, expected_split, expected_nonsplit) = curve.pencil_counts();
            assert_eq!((smooth, split), (expected_smooth, expected_split));
            assert_eq!(expected_nonsplit, smooth - split);
            assert_eq!(enumerated.len() as u128, 2 + 2 * split);
        }
    }
}

#[test]
fn split_classifier_matches_direct_projective_quadric_point_counts() {
    for (degree, low_terms) in [(1, 1), (2, 3)] {
        let field = BinaryField::new(degree, low_terms).unwrap();
        let q = field.size();
        for a in [0, 1] {
            let curve = BinaryCurve::new(field, a).unwrap();
            for lambda in 0..q {
                let member = curve.quadric(lambda).unwrap();
                if !member.smooth {
                    continue;
                }
                let mut nonzero_vectors = 0_u128;
                for w in 0..q {
                    for x in 0..q {
                        for y in 0..q {
                            for z in 0..q {
                                let vector = [w, x, y, z];
                                let [q1, q2] = curve.quadric_values(vector).unwrap();
                                if vector != [0; 4] && q2 ^ field.multiply(lambda, q1) == 0 {
                                    nonzero_vectors += 1;
                                }
                            }
                        }
                    }
                }
                let projective_count = nonzero_vectors / (q - 1);
                let expected = if member.split == Some(true) {
                    (q + 1) * (q + 1)
                } else {
                    q * q + 1
                };
                assert_eq!(projective_count, expected);
            }
        }
    }
}

#[test]
fn binary_group_axioms_and_quartic_model_include_exceptional_points() {
    let field = BinaryField::new(3, 3).unwrap();
    for a in [0, 1] {
        let curve = BinaryCurve::new(field, a).unwrap();
        let all = points(curve);
        for &p in &all {
            assert_eq!(curve.add(p, BinaryPoint::Infinity).unwrap(), p);
            assert_eq!(
                curve.add(p, curve.negate(p)).unwrap(),
                BinaryPoint::Infinity
            );
            assert_eq!(curve.decode(curve.encode(p).unwrap()).unwrap(), p);
            for scale in 1..field.size() {
                let scaled = curve.encode(p).unwrap().map(|v| field.multiply(v, scale));
                assert_eq!(curve.decode(scaled).unwrap(), p);
            }
            for &q in &all {
                let sum = curve.add(p, q).unwrap();
                assert!(curve.is_on_curve(sum));
                assert_eq!(sum, curve.add(q, p).unwrap());
                for &r in &all {
                    assert_eq!(
                        curve.add(sum, r).unwrap(),
                        curve.add(p, curve.add(q, r).unwrap()).unwrap()
                    );
                }
            }
        }
        assert_eq!(
            curve.multiply(2, BinaryPoint::Affine(0, 1)).unwrap(),
            BinaryPoint::Infinity
        );
        assert!(curve.decode([0; 4]).is_err());
        assert!(curve.decode([1, 0, 0, 1]).is_err());
        assert!(curve.decode([field.size(), 0, 0, 1]).is_err());
    }
}

#[test]
fn n83_metadata_matches_the_frozen_orders_and_generators() {
    let expected_orders = [
        9_671_406_556_923_184_866_742_756,
        9_671_406_556_910_881_928_556_062,
    ];
    for a in [0, 1] {
        let fixture = n83_fixture(a).unwrap();
        assert_eq!(
            fixture.curve.trace_and_order().1,
            expected_orders[a as usize]
        );
        assert_eq!(
            fixture.subgroup_order * fixture.cofactor,
            expected_orders[a as usize]
        );
        assert_eq!(
            fixture
                .curve
                .multiply(fixture.subgroup_order, fixture.generator)
                .unwrap(),
            BinaryPoint::Infinity
        );
        let mut conjugate = fixture.generator;
        for phase in 1..=83 {
            conjugate = fixture.curve.frobenius(conjugate);
            assert_eq!(conjugate == fixture.generator, phase == 83);
        }
    }
}

#[test]
fn n83_supplied_targets_need_no_log_and_reject_torsion_and_wrong_witnesses() {
    for a in [0, 1] {
        let fixture = n83_fixture(a).unwrap();
        let q = fixture.curve.multiply(37, fixture.generator).unwrap();
        assert!(check_n83(a, None, Some(q)).is_ok());
        assert!(check_n83(a, Some(37), Some(q)).is_ok());
        assert!(check_n83(a, Some(38), Some(q)).is_err());
        assert!(check_n83(a, None, Some(BinaryPoint::Affine(0, 1))).is_err());
        assert!(check_n83(a, None, Some(BinaryPoint::Affine(0, 0))).is_err());
        assert!(check_n83(a, None, Some(BinaryPoint::Infinity)).is_ok());
    }
}

#[test]
fn primality_check_handles_pseudoprimes_and_wide_u64_inputs() {
    for n in [0, 1, 4, 561, 3_215_031_751, 341_550_071_728_321, u64::MAX] {
        assert!(!is_prime_u64(n));
    }
    for n in [2, 3, 109, 8_569_786_107_849_059, 18_446_744_073_709_551_557] {
        assert!(is_prime_u64(n));
    }
}

#[test]
fn exact_decimal_and_point_encodings_preserve_high_words() {
    for exponent in 0..128 {
        assert_eq!(
            power_of_two_decimal(exponent),
            (1_u128 << exponent).to_string()
        );
    }
    assert_eq!(
        power_of_two_decimal(128),
        "340282366920938463463374607431768211456"
    );
    assert_eq!(
        parse_binary_point("0x477f77103dfad59850800,0x2fa5e737d542c4e4fd5c3").unwrap(),
        n83_fixture(0).unwrap().generator
    );
    assert!(parse_binary_point("not-a-point").is_err());
    assert!(parse_binary_point("0xZZ,1").is_err());
}
