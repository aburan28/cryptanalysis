use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    koblitz_index_calculus_dlp, koblitz_index_calculus_dlp_with_progress, DecompositionStrategy,
    KoblitzCurve, KoblitzIcEvent, KoblitzIcOptions, KoblitzRelationAttemptDisposition,
};
use num_bigint::BigUint;

#[test]
fn progress_covers_the_matrix_path_and_preserves_the_result() {
    let curve = KoblitzCurve::new(0, 9).unwrap();
    let expected = BigUint::from(53u32);
    let target = curve.mul(curve.generator(), &expected);
    for strategy in [
        DecompositionStrategy::Groebner,
        DecompositionStrategy::Sat,
        DecompositionStrategy::Enumerate,
    ] {
        let options = KoblitzIcOptions {
            strategy,
            collapse_negation: false,
            stop_on_verified_rank: false,
            allow_direct_relation: false,
            ..KoblitzIcOptions::default()
        };
        let original = koblitz_index_calculus_dlp(&curve, &target, &options).unwrap();
        let mut events = Vec::new();
        let observed =
            koblitz_index_calculus_dlp_with_progress(&curve, &target, &options, &mut |event| {
                events.push(event)
            })
            .unwrap();
        assert_eq!(observed.log, Some(expected.clone()));
        assert_eq!(observed.log, original.log);
        assert_eq!(observed.trials, original.trials);
        assert_eq!(observed.relations, original.relations);
        assert!(
            !observed.direct_relation,
            "fixture must exercise the matrix"
        );
        let start = events
            .iter()
            .position(|e| matches!(e, KoblitzIcEvent::LinearAlgebraStarted { .. }))
            .unwrap();
        let solved = events
            .iter()
            .position(|e| matches!(e, KoblitzIcEvent::LinearAlgebraFinished))
            .unwrap();
        let verify = events
            .iter()
            .position(|e| matches!(e, KoblitzIcEvent::VerificationStarted))
            .unwrap();
        assert!(start < solved && solved < verify);
        assert!(matches!(
            events.first(),
            Some(KoblitzIcEvent::FactorBaseStarted)
        ));
        assert!(matches!(
            events.last(),
            Some(KoblitzIcEvent::VerificationFinished { verified: true })
        ));
        assert!(!events.contains(&KoblitzIcEvent::LinearAlgebraSkipped));
    }
}
#[test]
fn incomplete_collection_records_terminal_rank_without_solve_or_verification() {
    let curve = KoblitzCurve::new(0, 9).unwrap();
    let target = curve.mul(curve.generator(), &BigUint::from(53u32));
    let options = KoblitzIcOptions {
        max_trials: 0,
        ..KoblitzIcOptions::default()
    };
    let mut events = Vec::new();
    let report =
        koblitz_index_calculus_dlp_with_progress(&curve, &target, &options, &mut |event| {
            events.push(event)
        })
        .unwrap();
    assert!(report.log.is_none());
    assert_eq!(report.rank_checks, 1);
    assert_eq!(report.linear_solve_attempts, 1);
    assert_eq!(report.terminal_matrix_rank, 0);
    assert!(matches!(
        events.last(),
        Some(KoblitzIcEvent::LinearAlgebraIncomplete)
    ));
    assert!(events.iter().any(|event| matches!(
        event,
        KoblitzIcEvent::RelationCollectionFinished {
            collected: 0,
            trials: 0
        }
    )));
    assert!(events.iter().any(|event| matches!(
        event,
        KoblitzIcEvent::MatrixRank {
            rows: 0,
            rank: 0,
            candidate_produced: false,
            ..
        }
    )));
    assert!(!events.iter().any(|e| matches!(
        e,
        KoblitzIcEvent::LinearAlgebraFinished
            | KoblitzIcEvent::VerificationStarted
            | KoblitzIcEvent::VerificationFinished { .. }
    )));
}

#[test]
fn early_rank_checks_report_actual_solves_and_verification() {
    let curve = KoblitzCurve::new(0, 9).unwrap();
    let expected = BigUint::from(53u32);
    let target = curve.mul(curve.generator(), &expected);
    let options = KoblitzIcOptions {
        strategy: DecompositionStrategy::Enumerate,
        allow_direct_relation: false,
        ..KoblitzIcOptions::default()
    };
    let mut events = Vec::new();
    let report =
        koblitz_index_calculus_dlp_with_progress(&curve, &target, &options, &mut |event| {
            events.push(event)
        })
        .unwrap();
    assert_eq!(report.log, Some(expected));
    assert!(report.linear_solve_attempts > 0);
    let announced_solves = events
        .iter()
        .filter(|event| matches!(event, KoblitzIcEvent::LinearAlgebraStarted { .. }))
        .count();
    assert_eq!(announced_solves, report.linear_solve_attempts);
    assert!(matches!(
        events.last(),
        Some(KoblitzIcEvent::VerificationFinished { verified: true })
    ));
    assert!(!events.contains(&KoblitzIcEvent::LinearAlgebraSkipped));
}

#[test]
fn direct_relation_reports_a_skip_without_claiming_a_matrix_solve() {
    use rand::{rngs::StdRng, Rng, SeedableRng};

    let curve = KoblitzCurve::new(0, 9).unwrap();
    let options = KoblitzIcOptions {
        strategy: DecompositionStrategy::Enumerate,
        max_trials: 1,
        ..KoblitzIcOptions::default()
    };
    // Choose a public fixture that makes the very first sampled relation
    // the identity, deterministically exercising the existing shortcut.
    let r = &curve.subgroup_order;
    let mut rng = StdRng::seed_from_u64(options.seed);
    let bound = r.to_u64_digits()[0];
    let a = BigUint::from(rng.gen_range(1..bound));
    let b = BigUint::from(rng.gen_range(1..bound));
    let expected = ((r - a) * cryptanalysis_suite::utils::mod_inverse(&b, r).unwrap()) % r;
    let target = curve.mul(curve.generator(), &expected);
    let mut events = Vec::new();
    let report =
        koblitz_index_calculus_dlp_with_progress(&curve, &target, &options, &mut |event| {
            events.push(event)
        })
        .unwrap();
    assert_eq!(report.log, Some(expected));
    assert!(report.direct_relation);
    assert_eq!(report.linear_solve_attempts, 0);
    let skipped = events
        .iter()
        .position(|event| matches!(event, KoblitzIcEvent::LinearAlgebraSkipped))
        .unwrap();
    let verifying = events
        .iter()
        .position(|event| matches!(event, KoblitzIcEvent::VerificationStarted))
        .unwrap();
    assert!(skipped < verifying);
    assert!(!events.iter().any(|event| matches!(
        event,
        KoblitzIcEvent::LinearAlgebraStarted { .. } | KoblitzIcEvent::LinearAlgebraFinished
    )));
    let verified = events
        .iter()
        .position(|event| {
            matches!(
                event,
                KoblitzIcEvent::VerificationFinished { verified: true }
            )
        })
        .unwrap();
    let completed = events
        .iter()
        .position(|event| {
            matches!(
                event,
                KoblitzIcEvent::RelationAttemptFinished {
                    trial: 1,
                    disposition: KoblitzRelationAttemptDisposition::DirectSolved,
                    ..
                }
            )
        })
        .unwrap();
    assert!(verified < completed);
    assert_eq!(completed, events.len() - 1);
}
