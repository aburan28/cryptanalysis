//! # Cryptanalysis — toolkit for analysing novel ciphers and hashes.
//!
//! This module gives security researchers a set of building blocks for
//! evaluating proposed symmetric primitives **before** they are deployed.
//! The intent is to make the kinds of analysis that used to require
//! ad-hoc Python scripts (DDT / LAT printouts, Walsh transforms, SAC
//! matrices, chi-squared distinguishers) into a single library that
//! plugs cleanly into a cipher's existing Rust implementation.
//!
//! ## What's included
//!
//! - [`sbox::Sbox`] — generic n-in / m-out S-box with the full modern
//!   distinguishing-table battery:
//!   [`Sbox::ddt`] (Differential Distribution Table),
//!   [`Sbox::lat`] (Linear Approximation Table),
//!   [`Sbox::bct`] (Boomerang Connectivity Table — Cid et al.,
//!   EUROCRYPT 2018),
//!   [`Sbox::dlct`] (Differential-Linear Connectivity Table —
//!   Bar-On et al., EUROCRYPT 2019),
//!   [`Sbox::truncated_ddt`] (Knudsen, FSE 1994),
//!   plus the derived metrics
//!   [`Sbox::differential_uniformity`],
//!   [`Sbox::max_differential_probability`],
//!   [`Sbox::max_linear_bias`],
//!   [`Sbox::nonlinearity`],
//!   [`Sbox::boomerang_uniformity`],
//!   [`Sbox::max_dlct_bias`],
//!   [`Sbox::is_balanced`],
//!   [`Sbox::is_bijective`],
//!   and [`Sbox::algebraic_degree`].
//!
//! - [`boolean`] — Boolean-function helpers: Walsh–Hadamard transform,
//!   algebraic normal form, algebraic degree.  These are the
//!   primitives the S-box analysis is layered on top of, exposed
//!   independently because designers of stream ciphers and
//!   non-table-based round functions often want them.
//!
//! - [`avalanche`] — diffusion measurements over arbitrary functions
//!   (`fn(&[u8]) -> Vec<u8>`).  Full avalanche matrix, Strict
//!   Avalanche Criterion (SAC) score, Bit-Independence Criterion
//!   (BIC) score.  Works on any function you can call from Rust —
//!   useful for end-to-end testing of your full cipher, not just
//!   individual components.
//!
//! - [`statistical`] — chi-squared, monobit, runs, and byte-frequency
//!   distinguishers over the output of an arbitrary cipher / hash /
//!   PRF.  These are the classic "is the output statistically
//!   distinguishable from random?" tests.
//!
//! ## How to use it
//!
//! 1. Wrap your S-box(es) in [`Sbox::new`] and call [`Sbox::report`]
//!    to get a one-page summary of differential / linear strength.
//! 2. For your full round function or full cipher, expose it as a
//!    closure `|input: &[u8]| -> Vec<u8>` and pass it to
//!    [`avalanche::full_avalanche`] or
//!    [`statistical::chi_squared_byte_test`].
//! 3. For a Boolean function (say, a tap from your nonlinear filter),
//!    convert it to a truth table (`Vec<u8>` of 0s/1s) and call
//!    [`boolean::walsh_hadamard`] or [`boolean::algebraic_degree`].
//!
//! ## What this is NOT
//!
//! - **Not a full automated trail-search engine.**  Searching for the
//!   best `r`-round differential trail in a cipher with state larger
//!   than ~16 bits is genuinely hard (MILP / SAT).  We give you the
//!   per-round building blocks (DDT, LAT) so you can plug them into
//!   your own search; we do not ship a CP/SAT/MILP backend.
//! - **Not a substitute for academic peer review.**  Passing every
//!   test in this module does NOT mean a cipher is secure.  Lots of
//!   broken ciphers had clean DDT/LAT and high SAC scores.  These
//!   tools are necessary, not sufficient.
//! - **Not constant-time.**  This module is *analytical*, not
//!   operational — it is meant to be run on a designer's workstation
//!   against a candidate cipher, not on a production server.  The
//!   code uses `Vec` allocations and `match`-based dispatch
//!   throughout.
//!
//! ## Example: analyse a 4-bit S-box
//!
//! ```
//! use cryptanalysis_suite::cryptanalysis::sbox::Sbox;
//!
//! // Serpent S0 — Anderson/Biham/Knudsen 1998.
//! let s0 = Sbox::new(4, 4, vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12]).unwrap();
//!
//! assert!(s0.is_bijective());
//! assert!(s0.is_balanced());
//! // Serpent's S-boxes have differential uniformity 4 (i.e. max DDT entry = 4).
//! assert_eq!(s0.differential_uniformity(), 4);
//! // ... and max DP = 4/16 = 0.25.
//! assert!((s0.max_differential_probability() - 0.25).abs() < 1e-9);
//! ```

pub mod aes;
pub mod ai_schoof;
pub mod algebra_cache;
pub mod aut_folded_rho;
pub mod auto_attack;
pub mod avalanche;
pub mod b_seed_profile;
pub mod binary_isogeny;
pub mod binary_semaev;
pub mod binary_semaev_s4;
pub mod bleichenbacher;
pub mod boolean;
pub mod boomerang;
pub mod bsgs_fast;
pub mod canonical_lift;
pub mod cga_hnc;
pub mod cheon_attack;
pub mod cipher_registry;
pub mod cm_canonical_lift;
pub mod coleman_integration;
pub mod coordinate_descent;
pub mod coordinate_quotients;
pub mod coordinate_search;
pub mod crossbred;
pub mod degree_reduction;
pub mod degree_reduction_anf;
pub mod descent_algebraic;
pub mod descent_expansion;
pub mod descent_lowgamma;
pub mod descent_treewidth;
pub mod diem_descent;
pub mod ec_challenges;
pub mod ec_index_calculus;
pub mod ec_index_calculus_curves;
pub mod ec_index_calculus_j0;
pub mod ec_trapdoor;
pub mod ecdlp_variants;
pub mod ecdsa_audit;
pub mod ecm;
pub mod eds_mov;
pub mod eds_net;
pub mod eds_residue;
pub mod eds_tate;
pub mod f4_batch;
pub mod f4_fp;
pub mod f4_gf2;
pub mod f4_gpu;
pub mod ffd_harness;
pub mod fght_snfs;
pub(crate) mod fx_hash;
pub mod gaudry_cubic;
pub mod ghs_descent;
pub mod ghs_full_attack;
pub mod groebner_f4;
pub mod hash_attacks;
pub mod hilbert_class_poly;
pub mod hnp_ecdsa;
pub mod hyperelliptic_ic_bench;
pub mod hyperelliptic_index_calculus;
pub mod index_calculus_budget;
pub mod invalid_curve_attack;
pub mod isogeny_class_search;
pub mod isogeny_degree_search;
pub mod j0_twists;
pub mod koblitz_bench;
pub mod koblitz_factor_base_search;
pub mod koblitz_fast;
pub mod koblitz_groebner;
pub mod koblitz_index_calculus;
pub mod koblitz_pdp_phase_a;
pub mod koblitz_relation_solver;
pub mod koblitz_sparse_la;
pub mod koblitz_symmetrised;
pub mod lattice;
pub mod legacy_curve_attacks;
pub mod mazur_tate_sigma;
pub mod md5_chosen_prefix;
pub mod md5_differential;
pub mod md5_hashclash_ffi;
pub mod ml_dsa_fault;
pub mod ml_dsa_leakage;
pub mod ml_kem_pco;
pub mod ml_rho_walks;
pub mod mlwe;
pub mod modular_polynomial;
pub mod mov_attack;
pub mod mq_fes;
pub mod mq_monica;
pub mod multi_key_hnp;
pub mod nonanom_formal_log;
pub mod orbit_homology;
pub mod p256_attacks;
pub mod p256_isogeny_cover;
pub mod p256_structural;
pub mod pc_degree_avg;
pub mod pc_degree_harness;
pub mod petit_quisquater;
pub mod pkm_criterion;
pub mod pohlig_hellman;
pub mod pollard_collab;
pub mod pollard_rho;
pub mod polynomial_reuse;
pub mod pq_descent;
pub mod pq_groebner_f2;
pub mod pq_sparse_la;
pub mod pq_wiedemann;
pub mod pq_xl;
pub mod preprocessing_rho;
pub mod prime_orbit_index_calculus;
pub mod quantum_estimator;
pub mod quasi_subfield;
pub mod research_bench;
pub mod residual_walk;
pub mod sat;
pub mod sbox;
pub mod semaev_corpus;
pub mod semaev_decomp;
pub mod semaev_higher;
pub mod semaev_leading_form;
pub mod semaev_sat;
pub mod sha1_differential;
pub mod shor;
pub mod signal_ratchet;
pub mod signature_corpus;
pub mod solinas_correlations;
pub mod sparse_macaulay;
pub mod statistical;
pub mod symmetrized_semaev;
pub mod tls12_kdf;
pub mod tls13_kdf;
pub mod visual_demos;
pub mod visualize;
pub mod wdsat_oracle;
pub mod weak_curves;
pub mod weil_charts;

pub use aut_folded_rho::{
    apply_aut, aut_folded_rho_dlp, canonical_form, AutElt, FoldedRhoOptions, FoldedRhoSolution,
    J0CurveAut,
};
pub use avalanche::{bit_independence_score, full_avalanche, sac_score, AvalancheReport};
pub use bleichenbacher::{
    bias_magnitude, bleichenbacher_direct, signature_to_sample, BleichenbacherPeak,
    BleichenbacherSample,
};
pub use boolean::{algebraic_degree, anf_coefficients, walsh_hadamard};
pub use boomerang::{
    boomerang_distinguisher, boomerang_trail_search, differential_trail_search, rectangle_attack,
    sandwich_distinguisher, BlockCipher, BoomerangResult, BoomerangTrailPair, DifferentialTrail,
    RectangleResult, SandwichResult, SpnTrailModel, ToySpn,
};
pub use canonical_lift::{
    find_anomalous_curve, hensel_lift_point, smart_attack_anomalous, ZpCurve, ZpInt, ZpPoint,
};
pub use ec_index_calculus::{
    build_factor_base, ec_index_calculus_dlp, find_one_relation, find_roots_fp,
    gaussian_eliminate_mod_n, pollard_rho_ecdlp, semaev_s3, semaev_s3_in_x3, semaev_s4_in_x4,
    sqrt_mod_p, FactorBaseEntry, Relation,
};
pub use ec_index_calculus_j0::{
    build_eisenstein_factor_base, eisenstein_smooth_ic_dlp, j0_index_calculus_dlp,
};
pub use ecdlp_variants::{
    bsgs_average_case, bsgs_interleaving, bsgs_interleaving_block, bsgs_interleaving_negation,
    bsgs_negation, bsgs_textbook, demo_group_mid, demo_group_small, gaudry_schost,
    gaudry_schost_montgomery, gaudry_schost_negation, grumpy_giants, grumpy_giants_block,
    grumpy_giants_negation, DlpSolution, EcGroup, GaudrySchostOptions,
};
pub use ecdsa_audit::{
    audit_ecdsa_transcript, quick_bias_score, AuditOptions, AuditResult, EcdsaSample,
};
pub use hnp_ecdsa::{
    hnp_recover_key, hnp_recover_key_with_reduction, BiasedSignature, HnpReduction,
};
pub use j0_twists::{
    enumerate_twists, factorise_small, format_twist_table, max_prime_factor, naive_point_count,
    primitive_root, twist_coefficients, TwistInfo,
};
pub use koblitz_bench::{
    bench_instance, ffd_summary, format_ffd_table, format_oracle_table, format_system_table,
    max_m_within_budget, n_vars_for, profile_system, subspace_ladder, sweep_ffd, sweep_systems,
    FfdSummary, InstanceBench, OracleRun, SystemProfile,
};
pub use koblitz_groebner::{
    build_decomposition_system, first_fall_degree, macaulay_profile, matrix_f4_f2,
    matrix_f4_f2_counted, solve_boolean_system, solve_boolean_system_filtered, sym_semaev_s3,
    DecompositionSystem, FieldStructure, MacaulayProfile, SolveOptions, SolveStats, SolverEngine,
    SymElement,
};
pub use koblitz_index_calculus::{
    all_factors_of_x_n_minus_1, available_subspace_dimensions,
    build_explicit_frobenius_orbit_factor_base, build_frobenius_factor_base,
    build_frobenius_factor_base_from_divisor, build_frobenius_union_factor_base,
    build_subgroup_orbit_factor_base, cyclotomic_cosets, enumerate_decompose, factor_x_n_minus_1,
    find_irreducible, find_irreducible_sparse, frobenius_eigenvalue, frobenius_eigenvalue_q,
    groebner_decompose, individual_log, individual_log_with_pair_table, invariant_factors,
    invariant_subspace_basis, is_irreducible_f2, koblitz_index_calculus_dlp,
    koblitz_index_calculus_dlp_with_factor_base,
    koblitz_index_calculus_dlp_with_factor_base_and_progress, koblitz_point_count,
    koblitz_signed_frobenius_rho_reference, koblitz_signed_frobenius_rho_with_progress,
    koblitz_speedup_model, linearised_kernel, linearised_kernel_basis, order_of_2_mod_n,
    pack_point, point_key, points_with_x, probe_scalar, q_linearised_kernel_basis,
    restrict_factor_base_to_orbits, sat_decompose, saturate_factor_base_two_torsion,
    solve_factor_base_logs, solve_factor_base_logs_from_relations, span_f2, subfield_group_order,
    subspace_basis_for_divisor, subspace_basis_for_factors, top_factor_indices,
    verify_collected_relation, CollectedRelation, CollectionReport, DecompositionStrategy,
    FactorBaseDomain, FactorBaseLogSolver, FactorBaseLogTable, FrobeniusFactorBase,
    IndividualLogReport, IndividualLogSolver, KoblitzCurve, KoblitzIcEvent, KoblitzIcOptions,
    KoblitzIcReport, KoblitzRankRecord, KoblitzRelation, KoblitzRelationAttemptDisposition,
    KoblitzRelationAttemptRecord, KoblitzSignedRhoCharges, KoblitzSignedRhoEvent,
    KoblitzSignedRhoOptions, KoblitzSignedRhoReport, KoblitzSpeedup, LinearAlgebra, LogTableReport,
    PairSumTable, RelationCollector, RelationWorkUnit, SatDecompositionOptions,
    SatDecompositionStats, MAX_SUBFIELD_DEGREE, PRECOMPUTE_BATCH_TRIALS,
};
pub use koblitz_sparse_la::{
    block_wiedemann_kernel, filter_relations, solve_sparse_system, BlockWiedemannOptions,
    BlockWiedemannReport, CsrMatrix, FilterOptions, FilterReport, FilteredSystem, SparseRow,
    SparseSolveOptions, SparseSolveOutcome, SparseSolveReport,
};
pub use lattice::{bkz_reduce, lll_reduce};
pub use legacy_curve_attacks::{
    bounded_bsgs_binary, bounded_bsgs_prime, legacy_curve_attack_report,
    run_legacy_curve_attack_demos, BoundedDlpSolution, LegacyCurveAttackDemo,
};
pub use multi_key_hnp::{build_transcript, multi_key_hnp_recover_master, ChildKeySignature};
pub use pollard_rho::{
    pollard_rho_dlp, pollard_rho_dlp_zp, pollard_rho_dlp_zp_multi, pollard_rho_dp_dlp_zp,
    pollard_rho_dp_dlp_zp_multi, DpRhoOptions, RhoOptions, RhoSolution,
};
pub use preprocessing_rho::{
    build_preprocessing_table, expected_online_cost, online_solve, preprocessing_rho_dlp,
    PreprocessingOptions, PreprocessingTable,
};
pub use sbox::{Sbox, SboxReport};
pub use sha1_differential::{
    estimate_differential, find_near_collision, round_function_truth_table, sha1, sha1_avalanche,
    sha1_compress, DifferentialEstimate, NearCollision,
};
pub use shor::{shor_factor, shor_order_find};
pub use signature_corpus::{
    CorpusAnalyzer, CorpusReport, Finding, ReportRow, Severity, SignatureRecord,
};
pub use statistical::{chi_squared_byte_test, monobit_test, runs_test, ChiSquaredReport};
