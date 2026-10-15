use binary_genus2_cover::{
    checks::{element, small_field_controls},
    GenusTwoCover,
};
use curve_backend::binary_ecc::{
    BinaryCoverPoint, BinaryPoint, F2mPoly, IrreduciblePoly, MumfordDivisor,
};

#[test]
fn exhaustive_small_fields_preserve_the_group_law() {
    let controls = small_field_controls().unwrap();
    assert_eq!(controls.len(), 8);
    assert_eq!(controls[0]["genus2_projective_points"], 2);
    assert_eq!(controls[1]["genus2_projective_points"], 4);
    assert_eq!(controls[2]["genus2_projective_points"], 8);
    assert_eq!(controls[3]["genus2_projective_points"], 8);
}

#[test]
fn exceptional_fibers_and_outside_image_are_handled() {
    let cover = GenusTwoCover::new(
        1,
        IrreduciblePoly {
            degree: 1,
            low_terms: vec![0],
        },
        element(1, 1),
    )
    .unwrap();
    let zero = element(0, 1);
    let one = element(1, 1);
    assert_eq!(
        cover
            .map_point(&BinaryCoverPoint::Affine {
                u: zero.clone(),
                v: zero.clone()
            })
            .unwrap(),
        BinaryPoint::Affine {
            x: zero.clone(),
            y: one.clone()
        }
    );
    for v in [zero.clone(), one.clone()] {
        assert_eq!(
            cover
                .map_point(&BinaryCoverPoint::Affine { u: one.clone(), v })
                .unwrap(),
            BinaryPoint::Infinity
        );
    }
    let outside = MumfordDivisor::try_from_point(cover.source(), &one, &zero).unwrap();
    assert!(cover.inverse_on_image(&outside).is_err());
    assert!(cover
        .pullback(&BinaryPoint::Affine {
            x: zero.clone(),
            y: zero.clone()
        })
        .is_err());
    assert!(cover
        .map_point(&BinaryCoverPoint::Affine {
            u: zero,
            v: one.clone()
        })
        .is_err());
    assert!(cover
        .pullback(&BinaryPoint::Affine {
            x: element(0, 2),
            y: element(1, 2)
        })
        .is_err());
    let invalid = MumfordDivisor {
        u: F2mPoly::x(1),
        v: F2mPoly::constant(one),
    };
    assert!(cover.inverse_on_image(&invalid).is_err());
}

#[test]
fn invalid_fields_and_coefficient_widths_are_rejected() {
    assert!(GenusTwoCover::new(
        4,
        IrreduciblePoly {
            degree: 4,
            low_terms: vec![2, 0]
        },
        element(0, 4)
    )
    .is_err());
    assert!(GenusTwoCover::new(
        3,
        IrreduciblePoly {
            degree: 3,
            low_terms: vec![1, 0]
        },
        element(0, 4)
    )
    .is_err());
}
