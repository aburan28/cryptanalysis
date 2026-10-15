//! Reproducible checks, with fixture arithmetic independent of the Jacobian backend.
use crate::{GenusTwoCover, Result};
use curve_backend::binary_ecc::{
    BinaryCoverPoint, BinaryPoint, F2mElement, IrreduciblePoly, MumfordDivisor,
};
use ecdlp_surfaces::binary::{
    is_prime_u64, n83_fixture, BinaryCurve, BinaryField, BinaryPoint as FixturePoint,
    FIXTURE_SOURCE, PRIME_RECEIPT_SOURCE,
};
use num_bigint::BigUint;
use serde_json::{json, Value};
use surface_evidence::hash::sha256::sha256;

pub fn element(value: u128, m: u32) -> F2mElement {
    assert!(m <= 128 && (m == 128 || value < (1_u128 << m)));
    F2mElement::from_biguint(&BigUint::from(value), m)
}

pub fn native_point(p: FixturePoint, m: u32) -> BinaryPoint {
    match p {
        FixturePoint::Infinity => BinaryPoint::Infinity,
        FixturePoint::Affine(x, y) => BinaryPoint::Affine {
            x: element(x, m),
            y: element(y, m),
        },
    }
}

pub fn divisor_json(d: &MumfordDivisor) -> Value {
    let coefficients = |p: &curve_backend::binary_ecc::F2mPoly| {
        p.coeffs
            .iter()
            .map(|c| format!("0x{:x}", c.to_biguint()))
            .collect::<Vec<_>>()
    };
    json!({"U": coefficients(&d.u), "V": coefficients(&d.v)})
}

fn point_json(p: FixturePoint) -> Value {
    match p {
        FixturePoint::Infinity => json!("O"),
        FixturePoint::Affine(x, y) => json!([format!("0x{x:x}"), format!("0x{y:x}")]),
    }
}

fn require(value: bool, message: &str) -> Result<()> {
    if value {
        Ok(())
    } else {
        Err(message.into())
    }
}

fn gcd(mut a: u128, mut b: u128) -> u128 {
    while b != 0 {
        (a, b) = (b, a % b);
    }
    a
}

pub fn check_n83(a: u8, supplied_q: Option<FixturePoint>, scalar: Option<u128>) -> Result<Value> {
    let fixture = n83_fixture(a)?;
    let e = fixture.curve;
    let p = fixture.generator;
    let r = fixture.subgroup_order;
    if a == 1 {
        let r64 = u64::try_from(r).map_err(|e| e.to_string())?;
        require(
            is_prime_u64(r64),
            "a=1 subgroup order failed deterministic u64 primality",
        )?;
    }
    let witness = if supplied_q.is_some() {
        scalar
    } else {
        Some(scalar.unwrap_or(37) % r)
    };
    let q = match supplied_q {
        Some(q) => q,
        None => e.multiply(witness.unwrap(), p)?,
    };
    require(e.is_on_curve(q), "Q is not on the pinned source model")?;
    require(p != FixturePoint::Infinity, "generator is the identity")?;
    require(
        gcd(r, fixture.cofactor) == 1 && gcd(3, r) == 1,
        "subgroup coprimality failed",
    )?;
    require(e.multiply(r, p)? == FixturePoint::Infinity, "rP is nonzero")?;
    require(e.multiply(r, q)? == FixturePoint::Infinity, "rQ is nonzero")?;
    if let Some(k) = witness {
        require(
            e.multiply(k % r, p)? == q,
            "supplied scalar does not match Q",
        )?;
    }
    let cover = GenusTwoCover::new(
        83,
        IrreduciblePoly {
            degree: 83,
            low_terms: vec![45, 2, 1, 0],
        },
        element(u128::from(a), 83),
    )?;
    let np = native_point(p, 83);
    let nq = native_point(q, 83);
    let dp = cover.pullback(&np)?;
    let dq = cover.pullback(&nq)?;
    let c = cover.source();
    require(!dp.is_identity(), "generator pullback is the identity")?;
    require(
        cover.inverse_on_image(&dp)? == np,
        "P inverse round trip failed",
    )?;
    require(
        cover.inverse_on_image(&dq)? == nq,
        "Q inverse round trip failed",
    )?;
    require(
        dp.try_scalar_mul(&BigUint::from(r), c)
            .map_err(|e| e.to_string())?
            .is_identity(),
        "rD_P is nonzero",
    )?;
    require(
        dq.try_scalar_mul(&BigUint::from(r), c)
            .map_err(|e| e.to_string())?
            .is_identity(),
        "rD_Q is nonzero",
    )?;
    if let Some(k) = witness {
        require(
            dp.try_scalar_mul(&BigUint::from(k % r), c)
                .map_err(|e| e.to_string())?
                == dq,
            "scalar relation was not preserved",
        )?;
    }
    let scalars = [0_u128, 1, 2, 3, 7, 37, 97, r - 1];
    for k in scalars {
        let kp = e.multiply(k, p)?;
        let pulled = cover.pullback(&native_point(kp, 83))?;
        require(
            dp.try_scalar_mul(&BigUint::from(k), c)
                .map_err(|e| e.to_string())?
                == pulled,
            "sampled scalar multiplication was not preserved",
        )?;
        let sum = e.add(kp, q)?;
        require(
            pulled.try_add(&dq, c).map_err(|e| e.to_string())?
                == cover.pullback(&native_point(sum, 83))?,
            "sampled addition was not preserved",
        )?;
    }
    let ec1 = if a == 0 {
        "EC1N83Ckb0h252dacc102a4"
    } else {
        "EC1N83Ckb1h1f579d351b52"
    };
    let uid = if a == 0 {
        "urn:curve:sha256:252dacc102a4f15413d4a269e2156852ad18dd6f8b25cf207146868c4592e2cc"
    } else {
        "urn:curve:sha256:1f579d351b52b0f3aba9259aa9b77738a958c3dbb995a6965bb50822ad199bb3"
    };
    let target_model = json!({"schema":"binary-genus2-model/v1","field_modulus":"0x800000000200000000007",
        "field_degree":83,"a":a,"h":["0x0","0x0","0x1"],
        "f":["0x0","0x1","0x0","0x1",format!("0x{a:x}"),"0x1"],
        "genus":2,"infinity":"unique rational point"});
    let target_model_bytes = serde_json::to_vec(&target_model).map_err(|e| e.to_string())?;
    let target_digest = sha256(&target_model_bytes)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect::<String>();
    Ok(json!({
        "a":a, "field_degree":83, "field_modulus":"0x800000000200000000007",
        "source_ec1":ec1, "source_curve_uid":uid,
        "source_icv1":if a==0 {"icv1-f2m83-tm6151469093347-debefd74"} else {"icv1-f2m83-t6151469093347-cdcc5432"},
        "target_model":target_model,"target_model_uid":format!("urn:hyperelliptic-model:sha256:{target_digest}"),
        "target_model_uid_convention":"SHA-256 of compact sorted-key target_model JSON; identifies the curve model, not a subgroup or elliptic EC1 record",
        "fixture_source":FIXTURE_SOURCE, "prime_receipt_source":PRIME_RECEIPT_SOURCE,
        "subgroup_order":r.to_string(), "cofactor":fixture.cofactor.to_string(),
        "source_order":e.trace_and_order().1.to_string(),
        "prime_proof":if a==0 {"cited historical Sage receipt; not re-proved by this command"} else {"fresh deterministic u64 Miller-Rabin with the established seven-base set"},
        "fresh_deterministic_u64_prime_check":if a==1 {Some(true)} else {None},
        "P":point_json(p), "Q":point_json(q), "D_P":divisor_json(&dp), "D_Q":divisor_json(&dq),
        "source_genus":2, "cover_degree":3, "base_field_changed":false,
        "target_curve":"v^2+u^2*v=u^5+a*u^4+u^3+u",
        "divisor_convention":"ascending U,V coefficients; classes relative to the unique source infinity",
        "map_identity_coefficientwise":true, "source_model_checked":true,
        "rP_zero":true,"rQ_zero":true,"rD_P_zero":true,"rD_Q_zero":true,
        "P_and_D_P_nonidentity":true,"gcd_r_cofactor":1,"gcd_r_cover_degree":1,
        "Q_in_source_subgroup":true,"membership_basis":"cited prime r, #E=r*h, gcd(r,h)=1, and rQ=O",
        "image_P_order":r.to_string(), "inverse_P_roundtrip":true,"inverse_Q_roundtrip":true,
        "scalar_mod_r":witness.map(|k| (k % r).to_string()),
        "known_scalar_relation_verified":witness.map(|_| true),
        "sampled_scalar_relations":scalars.len(),"sampled_addition_pairs":scalars.len(),
        "group_law_basis":"Picard pullback along the proved cover; finite checks validate this implementation",
        "norm_on_arbitrary_classes_implemented":false,"image_inverse_implemented":true,
        "unknown_log_recovered":false,"solver_advantage_measured":false
    }))
}

/// Exhaustive controls are explicitly restricted to fields of at most 16 elements.
pub fn small_field_controls() -> Result<Vec<Value>> {
    let mut rows = Vec::new();
    for m in 1..=4 {
        let low_terms = if m == 1 { vec![0] } else { vec![1, 0] };
        let low_mask = if m == 1 { 1 } else { 3 };
        let field = BinaryField::new(m, low_mask)?;
        for a in 0..=1 {
            let e = BinaryCurve::new(field, a)?;
            let cover = GenusTwoCover::new(
                m,
                IrreduciblePoly {
                    degree: m,
                    low_terms: low_terms.clone(),
                },
                element(u128::from(a), m),
            )?;
            let mut points = vec![FixturePoint::Infinity];
            let mut source_points = 1_usize;
            for x in 0..field.size() {
                for y in 0..field.size() {
                    let p = FixturePoint::Affine(x, y);
                    if e.is_on_curve(p) {
                        points.push(p);
                    }
                    let u = element(x, m);
                    let v = element(y, m);
                    if cover.source().is_on_curve(&u, &v) {
                        source_points += 1;
                        require(
                            cover.target_contains(
                                &cover.map_point(&BinaryCoverPoint::Affine { u, v })?,
                            ),
                            "small-field point map failed",
                        )?;
                    }
                }
            }
            require(
                cover.map_point(&BinaryCoverPoint::Infinity)? == BinaryPoint::Infinity,
                "infinity map failed",
            )?;
            let divisors = points
                .iter()
                .map(|&p| cover.pullback(&native_point(p, m)))
                .collect::<Result<Vec<_>>>()?;
            for (i, &p) in points.iter().enumerate() {
                require(
                    cover.inverse_on_image(&divisors[i])? == native_point(p, m),
                    "small-field inverse failed",
                )?;
                for (j, &q) in points.iter().enumerate() {
                    let expected = cover.pullback(&native_point(e.add(p, q)?, m))?;
                    require(
                        divisors[i]
                            .try_add(&divisors[j], cover.source())
                            .map_err(|e| e.to_string())?
                            == expected,
                        "exhaustive small-field addition failed",
                    )?;
                }
            }
            rows.push(json!({"m":m,"a":a,"field_size":field.size().to_string(),
                "elliptic_projective_points":points.len(),"genus2_projective_points":source_points,
                "addition_pairs_checked":points.len()*points.len(),"all_checks_passed":true}));
        }
    }
    Ok(rows)
}
