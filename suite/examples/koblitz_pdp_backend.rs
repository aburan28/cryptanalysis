//! Run one native backend against an exported binary-Koblitz PDP instance.
//!
//! The exporter writes the source system and a canonical identity into its
//! manifest.  This executable runs in a separate process, authenticates every
//! exported representation, reconstructs the algebraic source system, and
//! refuses to report a solver result unless the regenerated ANF is byte-exact.
//! SAT and meet-in-the-middle witnesses are checked against that source before
//! they are accepted.
//!
//! ```text
//! koblitz_pdp_backend native-sat /tmp/pdp/manifest.json 100000
//! koblitz_pdp_backend direct-mitm /tmp/pdp/manifest.json
//! ```

use cryptanalysis_suite::binary_ecc::curve::{point_add, point_neg};
use cryptanalysis_suite::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement, IrreduciblePoly};
use cryptanalysis_suite::cryptanalysis::binary_semaev_s4::{weil_descend_s4, S4System};
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, DecompositionSystem, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    factor_x_n_minus_1, find_irreducible_sparse, invariant_subspace_basis, points_with_x,
};
use cryptanalysis_suite::cryptanalysis::sat::{SolveResult, SolverStats};
use cryptanalysis_suite::cryptanalysis::semaev_sat::{
    encode_boolean_system_with, encode_semaev_s4_with, S4Options, XorEncoding,
};
use num_bigint::BigUint;
use num_traits::{One, Zero};
use serde_json::{json, Value};
use std::collections::{HashMap, HashSet};
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::time::Instant;

#[derive(Clone, Debug, PartialEq, Eq)]
struct Row {
    /// Zero-based Boolean variable ids in each square-free monomial.
    monomials: Vec<Vec<u32>>,
    constant: bool,
}

enum SourceSystem {
    SymmetrisedS4,
    ChainedS3(DecompositionSystem),
}

struct VerifiedInstance {
    id: String,
    n: u32,
    ell: usize,
    conflict_budget_from_manifest: u64,
    curve: BinaryCurve,
    basis: Vec<F2mElement>,
    target: BinaryPoint,
    rows: Vec<Row>,
    n_vars: u32,
    source: SourceSystem,
    artifact_receipts: Value,
    verification_ns: u128,
}

fn value_u64(value: &Value, name: &str) -> Result<u64, String> {
    value
        .as_u64()
        .ok_or_else(|| format!("{name} must be an unsigned integer"))
}

fn value_string<'a>(value: &'a Value, name: &str) -> Result<&'a str, String> {
    value
        .as_str()
        .ok_or_else(|| format!("{name} must be a string"))
}

fn parse_decimal(value: &Value, name: &str, n: u32) -> Result<BigUint, String> {
    let text = value_string(value, name)?;
    let parsed = BigUint::parse_bytes(text.as_bytes(), 10)
        .ok_or_else(|| format!("{name} is not a base-10 integer"))?;
    if parsed.bits() > u64::from(n) {
        return Err(format!("{name} does not fit in F_2^{n}"));
    }
    Ok(parsed)
}

fn point_key(point: &BinaryPoint) -> Option<(BigUint, BigUint)> {
    match point {
        BinaryPoint::Infinity => None,
        BinaryPoint::Affine { x, y } => Some((x.to_biguint(), y.to_biguint())),
    }
}

fn rows_from_s4(system: &S4System) -> Vec<Row> {
    let n_x = system.n_x_vars();
    let mut rows = Vec::new();
    for (i, coefficients) in system.correspondence.iter().enumerate() {
        for (degree, sigma) in coefficients.iter().enumerate() {
            let mut monomials: Vec<Vec<u32>> = sigma
                .monomials()
                .filter(|m| !m.is_empty())
                .cloned()
                .collect();
            monomials.push(vec![n_x + system.e_var(i, degree)]);
            rows.push(Row {
                monomials,
                constant: sigma.has_constant(),
            });
        }
    }
    for equation in &system.semaev {
        rows.push(Row {
            monomials: equation
                .monomials()
                .filter(|m| !m.is_empty())
                .map(|m| m.iter().map(|v| n_x + *v).collect())
                .collect(),
            constant: equation.has_constant(),
        });
    }
    rows
}

fn rows_from_chained(system: &DecompositionSystem) -> Vec<Row> {
    system
        .equations
        .iter()
        .map(|equation| Row {
            monomials: equation
                .terms
                .iter()
                .filter(|term| term.mask != 0)
                .map(|term| {
                    (0..system.n_vars)
                        .filter(|v| (term.mask >> v) & 1 == 1)
                        .map(|v| v as u32)
                        .collect()
                })
                .collect(),
            constant: equation.terms.iter().any(|term| term.mask == 0),
        })
        .collect()
}

fn wdsat_anf(n_vars: u32, rows: &[Row]) -> String {
    let active: Vec<&Row> = rows
        .iter()
        .filter(|row| row.constant || !row.monomials.is_empty())
        .collect();
    let mut out = format!("p cnf {n_vars} {}\n", active.len());
    for row in active {
        out.push('x');
        for monomial in &row.monomials {
            if monomial.len() > 1 {
                out.push_str(&format!(" .{}", monomial.len()));
            }
            for variable in monomial {
                out.push_str(&format!(" {}", variable + 1));
            }
        }
        if !row.constant {
            out.push_str(" T");
        }
        out.push_str(" 0\n");
    }
    out
}

fn safe_artifact_path(directory: &Path, path: &str) -> Result<PathBuf, String> {
    let relative = Path::new(path);
    let mut components = relative.components();
    let one = components.next();
    if !matches!(one, Some(Component::Normal(_))) || components.next().is_some() {
        return Err(format!("export path must be one local filename: {path}"));
    }
    Ok(directory.join(relative))
}

fn verify_exports(directory: &Path, exports: &Value) -> Result<Value, String> {
    let object = exports
        .as_object()
        .ok_or_else(|| "exports must be an object".to_string())?;
    let expected_names = ["wdsat_anf", "cryptominisat_xor_dimacs", "magma_boolean_f4"];
    if object.len() != expected_names.len()
        || expected_names
            .iter()
            .any(|name| !object.contains_key(*name))
    {
        return Err("exports must contain exactly the three source representations".to_string());
    }
    let mut receipts = serde_json::Map::new();
    for name in expected_names {
        let descriptor = &object[name];
        let path_text = value_string(&descriptor["path"], &format!("exports.{name}.path"))?;
        let path = safe_artifact_path(directory, path_text)?;
        let metadata = fs::symlink_metadata(&path)
            .map_err(|error| format!("stat {}: {error}", path.display()))?;
        if metadata.file_type().is_symlink() || !metadata.is_file() {
            return Err(format!("{name} must be a regular local file"));
        }
        let bytes = fs::read(&path).map_err(|error| format!("read {}: {error}", path.display()))?;
        let actual_bytes = bytes.len() as u64;
        let expected_bytes = value_u64(&descriptor["bytes"], &format!("exports.{name}.bytes"))?;
        let actual_blake3 = blake3::hash(&bytes).to_hex().to_string();
        let expected_blake3 =
            value_string(&descriptor["blake3"], &format!("exports.{name}.blake3"))?;
        if actual_bytes != expected_bytes || actual_blake3 != expected_blake3 {
            return Err(format!("{name} does not match its manifest digest"));
        }
        receipts.insert(
            name.to_string(),
            json!({
                "path":path_text,
                "bytes":actual_bytes,
                "blake3":actual_blake3,
                "valid":true,
            }),
        );
    }
    Ok(Value::Object(receipts))
}

fn source_identity_from_manifest(manifest: &Value, source_schema: &str) -> Result<Value, String> {
    match source_schema {
        "koblitz_pdp_source_instance.v1" => Ok(json!({
            "schema":"koblitz_pdp_source_identity.v1",
            "n":manifest["n"],
            "ell":manifest["ell"],
            "m":manifest["m"],
            "seed":manifest["seed"],
            "curve_a":manifest["curve_a"],
            "irreducible_low_terms":manifest["irreducible_low_terms"],
            "factor_base_predicate":manifest["factor_base_predicate"],
            "factor_base_basis_bitmasks":manifest["factor_base_basis_bitmasks"],
            "target":manifest["target"],
            "representation":manifest["representation"],
            "source_variables":manifest["source_variables"],
            "source_equations":manifest["source_equations"],
            "exports":manifest["exports"],
        })),
        "koblitz_pdp_source_instance.v2" => Ok(json!({
            "schema":"koblitz_pdp_source_identity.v2",
            "n":manifest["n"],
            "ell":manifest["ell"],
            "m":manifest["m"],
            "seed":manifest["seed"],
            "blind_instance_id":manifest["blind_instance_id"],
            "target_mode":manifest["target_mode"],
            "curve_a":manifest["curve_a"],
            "irreducible_low_terms":manifest["irreducible_low_terms"],
            "factor_base_predicate":manifest["factor_base_predicate"],
            "factor_base_basis_bitmasks":manifest["factor_base_basis_bitmasks"],
            "target":manifest["target"],
            "representation":manifest["representation"],
            "source_variables":manifest["source_variables"],
            "source_equations":manifest["source_equations"],
            "exports":manifest["exports"],
        })),
        other => Err(format!("unsupported source_instance schema {other}")),
    }
}

fn verify_source_identity(manifest: &Value) -> Result<String, String> {
    let source = &manifest["source_instance"];
    let source_schema = value_string(&source["schema"], "source_instance.schema")?;
    match source_schema {
        "koblitz_pdp_source_instance.v1" => {
            if manifest.get("blind_instance_id").is_some() || manifest.get("target_mode").is_some()
            {
                return Err(
                    "legacy source identity cannot carry explicit-target fields".to_string()
                );
            }
        }
        "koblitz_pdp_source_instance.v2" => {
            value_string(&manifest["blind_instance_id"], "blind_instance_id")?;
            if manifest["target_mode"] != "explicit_affine" {
                return Err("v2 source identity requires explicit_affine target mode".to_string());
            }
        }
        _ => {}
    }
    let identity = source_identity_from_manifest(manifest, source_schema)?;
    if source["identity"] != identity {
        return Err("source identity does not match the top-level manifest".to_string());
    }
    let encoded = serde_json::to_vec(&identity).map_err(|error| error.to_string())?;
    let actual = blake3::hash(&encoded).to_hex().to_string();
    let claimed = value_string(&source["id_blake3"], "source_instance.id_blake3")?;
    if claimed != actual {
        return Err("source instance identity digest mismatch".to_string());
    }
    Ok(actual)
}

fn verify_instance(manifest_path: &Path) -> Result<VerifiedInstance, String> {
    let started = Instant::now();
    let text = fs::read_to_string(manifest_path)
        .map_err(|error| format!("read {}: {error}", manifest_path.display()))?;
    let manifest: Value = serde_json::from_str(&text)
        .map_err(|error| format!("parse {}: {error}", manifest_path.display()))?;
    if manifest["kind"] != "binary_koblitz_pdp_cross_solver_instance" {
        return Err("manifest kind is not a binary-Koblitz PDP instance".to_string());
    }
    if manifest["m"] != 3 {
        return Err("isolated backends currently require m=3".to_string());
    }
    let directory = manifest_path
        .parent()
        .ok_or_else(|| "manifest has no parent directory".to_string())?;
    let artifact_receipts = verify_exports(directory, &manifest["exports"])?;
    let id = verify_source_identity(&manifest)?;

    let n = u32::try_from(value_u64(&manifest["n"], "n")?)
        .map_err(|_| "n does not fit u32".to_string())?;
    let ell = usize::try_from(value_u64(&manifest["ell"], "ell")?)
        .map_err(|_| "ell does not fit usize".to_string())?;
    let curve_a = u8::try_from(value_u64(&manifest["curve_a"], "curve_a")?)
        .map_err(|_| "curve_a does not fit u8".to_string())?;
    if curve_a > 1 {
        return Err("Koblitz curve parameter a must be 0 or 1".to_string());
    }
    let low_terms: Vec<u32> = manifest["irreducible_low_terms"]
        .as_array()
        .ok_or_else(|| "irreducible_low_terms must be an array".to_string())?
        .iter()
        .map(|value| {
            u32::try_from(value_u64(value, "irreducible low term")?)
                .map_err(|_| "irreducible low term does not fit u32".to_string())
        })
        .collect::<Result<_, _>>()?;
    if low_terms.is_empty()
        || low_terms[0] != 0
        || low_terms.windows(2).any(|pair| pair[0] >= pair[1])
        || low_terms.iter().any(|term| *term >= n)
    {
        return Err(
            "irreducible_low_terms must be sorted, unique, include 0, and be below n".to_string(),
        );
    }
    let irreducible = IrreduciblePoly {
        degree: n,
        low_terms,
    };
    let curve = BinaryCurve {
        m: n,
        irreducible: irreducible.clone(),
        a: if curve_a == 0 {
            F2mElement::zero(n)
        } else {
            F2mElement::one(n)
        },
        b: F2mElement::one(n),
        generator: BinaryPoint::Infinity,
        order: BigUint::zero(),
        cofactor: BigUint::one(),
    };

    let basis_values = manifest["factor_base_basis_bitmasks"]
        .as_array()
        .ok_or_else(|| "factor_base_basis_bitmasks must be an array".to_string())?;
    if basis_values.len() != ell {
        return Err("factor-base basis length does not match ell".to_string());
    }
    let basis: Vec<F2mElement> = basis_values
        .iter()
        .enumerate()
        .map(|(index, value)| {
            parse_decimal(value, &format!("factor basis {index}"), n)
                .map(|bits| F2mElement::from_biguint(&bits, n))
        })
        .collect::<Result<_, _>>()?;
    let mut span = HashSet::new();
    if ell >= usize::BITS as usize {
        return Err("factor-base dimension exceeds materialisation representation".to_string());
    }
    for mask in 0..(1usize << ell) {
        let mut x = F2mElement::zero(n);
        for (index, element) in basis.iter().enumerate() {
            if (mask >> index) & 1 == 1 {
                x = x.add(element);
            }
        }
        span.insert(x.to_biguint());
    }
    if span.len() != 1usize << ell {
        return Err("factor-base basis is linearly dependent".to_string());
    }

    let predicate = &manifest["factor_base_predicate"];
    if predicate["enumerates_target_subgroup"] != false
        || predicate["uses_discrete_log_labels"] != false
    {
        return Err("factor-base predicate violates the public-algebra contract".to_string());
    }
    match value_string(&predicate["kind"], "factor_base_predicate.kind")? {
        "polynomial_subspace" => {
            let expected_irreducible = find_irreducible_sparse(n)
                .ok_or_else(|| "cannot reconstruct the sparse field polynomial".to_string())?;
            if expected_irreducible.low_terms != irreducible.low_terms {
                return Err(
                    "standard field polynomial does not match public construction".to_string(),
                );
            }
            for (index, element) in basis.iter().enumerate() {
                if *element != F2mElement::from_bit_positions(&[index as u32], n) {
                    return Err(
                        "standard factor-base basis is not the public polynomial subspace"
                            .to_string(),
                    );
                }
            }
        }
        "ggmp_linearised_kernel" => {
            let factor_index = usize::try_from(value_u64(
                &predicate["factor_index"],
                "factor_base_predicate.factor_index",
            )?)
            .map_err(|_| "factor index does not fit usize".to_string())?;
            let (expected_irreducible, expected_basis) = invariant_subspace_basis(n, factor_index)
                .ok_or_else(|| "cannot reconstruct the GGMP invariant subspace".to_string())?;
            if expected_irreducible.low_terms != irreducible.low_terms || expected_basis != basis {
                return Err("GGMP basis does not match its public linearised kernel".to_string());
            }
            let factor = *factor_x_n_minus_1(n)
                .get(factor_index)
                .ok_or_else(|| "GGMP factor index is out of range".to_string())?;
            if value_u64(
                &predicate["factor_bitmask"],
                "factor_base_predicate.factor_bitmask",
            )? != factor
            {
                return Err(
                    "GGMP factor bitmask does not match the public factorization".to_string(),
                );
            }
            let expected_exponents: Vec<u64> =
                (0..64).filter(|index| (factor >> index) & 1 == 1).collect();
            let actual_exponents: Vec<u64> = predicate["linearised_exponents"]
                .as_array()
                .ok_or_else(|| "GGMP linearised exponents must be an array".to_string())?
                .iter()
                .map(|value| value_u64(value, "GGMP linearised exponent"))
                .collect::<Result<_, _>>()?;
            if actual_exponents != expected_exponents {
                return Err("GGMP exponents do not match the public factor polynomial".to_string());
            }
        }
        other => return Err(format!("unsupported factor-base predicate {other}")),
    }

    let target_object = manifest["target"]
        .as_object()
        .ok_or_else(|| "target must be an affine point".to_string())?;
    let target = BinaryPoint::Affine {
        x: F2mElement::from_biguint(&parse_decimal(&target_object["x"], "target.x", n)?, n),
        y: F2mElement::from_biguint(&parse_decimal(&target_object["y"], "target.y", n)?, n),
    };
    if !curve.is_on_curve(&target) {
        return Err("target does not lie on the manifest curve".to_string());
    }
    let target_x = match &target {
        BinaryPoint::Affine { x, .. } => x,
        BinaryPoint::Infinity => unreachable!(),
    };

    let representation = value_string(&manifest["representation"], "representation")?;
    let (n_vars, rows, source) = match representation {
        "symmetrised_s4" => {
            for (index, element) in basis.iter().enumerate() {
                if *element != F2mElement::from_bit_positions(&[index as u32], n) {
                    return Err(
                        "symmetrised_s4 manifest does not use the standard polynomial basis"
                            .to_string(),
                    );
                }
            }
            let system =
                weil_descend_s4(n, ell as u32, &irreducible, &F2mElement::one(n), target_x);
            (
                system.n_x_vars() + system.n_e_vars(),
                rows_from_s4(&system),
                SourceSystem::SymmetrisedS4,
            )
        }
        "chained_s3" => {
            let field = FieldStructure::new(n, &irreducible);
            let system =
                build_decomposition_system(&basis, target_x, &F2mElement::one(n), 3, &field)
                    .ok_or_else(|| {
                        "chained S3 system exceeds its representation cap".to_string()
                    })?;
            let n_vars = u32::try_from(system.n_vars)
                .map_err(|_| "source variable count does not fit u32".to_string())?;
            let rows = rows_from_chained(&system);
            (n_vars, rows, SourceSystem::ChainedS3(system))
        }
        other => return Err(format!("unsupported source representation {other}")),
    };
    if value_u64(&manifest["source_variables"], "source_variables")? != u64::from(n_vars)
        || value_u64(&manifest["source_equations"], "source_equations")? != rows.len() as u64
    {
        return Err("regenerated source dimensions do not match the manifest".to_string());
    }
    let expected_anf = wdsat_anf(n_vars, &rows);
    let anf_path = safe_artifact_path(
        directory,
        value_string(&manifest["exports"]["wdsat_anf"]["path"], "ANF path")?,
    )?;
    let actual_anf = fs::read_to_string(&anf_path)
        .map_err(|error| format!("read {}: {error}", anf_path.display()))?;
    if actual_anf != expected_anf {
        return Err(
            "regenerated algebraic source is not byte-identical to instance.anf".to_string(),
        );
    }
    let conflict_budget_from_manifest = manifest["native_sat"]["conflict_budget"]
        .as_u64()
        .ok_or_else(|| "native_sat.conflict_budget is missing".to_string())?;

    Ok(VerifiedInstance {
        id,
        n,
        ell,
        conflict_budget_from_manifest,
        curve,
        basis,
        target,
        rows,
        n_vars,
        source,
        artifact_receipts,
        verification_ns: started.elapsed().as_nanos(),
    })
}

fn stats_json(stats: &SolverStats) -> Value {
    json!({
        "decisions":stats.decisions,
        "conflicts":stats.conflicts,
        "restarts":stats.restarts,
        "propagations":stats.propagations,
        "xor_passes":stats.xor_passes,
        "xor_propagations":stats.xor_propagations,
        "xor_conflicts":stats.xor_conflicts,
        "xor_repivots":stats.xor_repivots,
        "xor_row_ops":stats.xor_row_ops,
        "xor_row_scans":stats.xor_row_scans,
        "xor_reason_lits":stats.xor_reason_lits,
        "clause_visits":stats.clause_visits,
        "clause_lit_visits":stats.clause_lit_visits,
        "analyze_lit_visits":stats.analyze_lit_visits,
        "learnt_clauses":stats.learnt_clauses,
        "learnt_lits_raw":stats.learnt_lits_raw,
        "learnt_lits_kept":stats.learnt_lits_kept,
        "max_level":stats.max_level,
        "phase_ns":{
            "propagate_clauses":stats.ns_propagate_clauses,
            "propagate_xors":stats.ns_propagate_xors,
            "analyze":stats.ns_analyze,
            "minimize":stats.ns_minimize,
            "reduce_db":stats.ns_reduce_db,
        }
    })
}

fn validate_rows(rows: &[Row], assignment: &[bool], n_vars: u32) -> bool {
    assignment.len() >= n_vars as usize
        && rows.iter().all(|row| {
            !row.monomials.iter().fold(row.constant, |parity, monomial| {
                parity
                    ^ monomial
                        .iter()
                        .all(|variable| assignment[*variable as usize])
            })
        })
}

fn source_point_witness_valid(
    curve: &BinaryCurve,
    basis: &[F2mElement],
    target: &BinaryPoint,
    assignment: &[bool],
) -> bool {
    if assignment.len() < 3 * basis.len() {
        return false;
    }
    let xs: Vec<_> = (0..3)
        .map(|summand| {
            basis
                .iter()
                .enumerate()
                .fold(F2mElement::zero(curve.m), |x, (index, element)| {
                    if assignment[summand * basis.len() + index] {
                        x.add(element)
                    } else {
                        x
                    }
                })
        })
        .collect();
    let lifts: Vec<_> = xs.iter().map(|x| points_with_x(curve, x)).collect();
    lifts[0].iter().any(|p0| {
        lifts[1].iter().any(|p1| {
            lifts[2]
                .iter()
                .any(|p2| point_add(curve, &point_add(curve, p0, p1), p2) == *target)
        })
    })
}

fn validate_assignment(
    instance: VerifiedInstance,
    assignment_path: &Path,
) -> Result<(Value, bool), String> {
    let assignment_bytes = fs::read(assignment_path)
        .map_err(|error| format!("read {}: {error}", assignment_path.display()))?;
    let assignment: Vec<bool> = serde_json::from_slice(&assignment_bytes)
        .map_err(|error| format!("parse {}: {error}", assignment_path.display()))?;
    if assignment.len() != instance.n_vars as usize {
        return Err(format!(
            "assignment has {} values; expected exactly {} source variables",
            assignment.len(),
            instance.n_vars
        ));
    }
    let model_valid = validate_rows(&instance.rows, &assignment, instance.n_vars);
    let witness_valid = source_point_witness_valid(
        &instance.curve,
        &instance.basis,
        &instance.target,
        &assignment,
    );
    let accepted = model_valid && witness_valid;
    Ok((
        json!({
            "schema":"koblitz_pdp_assignment_validation.v1",
            "status":if accepted {"valid_point_witness"} else if !model_valid {"invalid_source_model"} else {"nonlifting_source_model"},
            "source_instance_id":instance.id,
            "source_instance_verified":true,
            "source_artifacts":instance.artifact_receipts,
            "regenerated_source_exact":true,
            "assignment_values":assignment.len(),
            "assignment_blake3":blake3::hash(&assignment_bytes).to_hex().to_string(),
            "source_assignment":assignment,
            "source_model_valid":model_valid,
            "source_witness_valid":witness_valid,
            "timing_ns":{"source_verification":instance.verification_ns},
            "interpretation":"A SAT model is a PDP witness only when its source equations hold and rational factor-base lifts sum to the exact target",
        }),
        accepted,
    ))
}

fn native_sat(instance: VerifiedInstance, conflict_budget: u64) -> (Value, bool) {
    let encoding_started = Instant::now();
    let (mut solver, initial_clauses, solver_variables) = match instance.source {
        SourceSystem::SymmetrisedS4 => {
            let target_x = match &instance.target {
                BinaryPoint::Affine { x, .. } => x,
                BinaryPoint::Infinity => unreachable!(),
            };
            let encoding = encode_semaev_s4_with(
                instance.n,
                instance.ell as u32,
                &instance.curve.irreducible,
                &F2mElement::one(instance.n),
                target_x,
                S4Options {
                    encoding: XorEncoding::Native,
                    break_symmetry: false,
                },
            );
            let clauses = encoding.solver.n_clauses();
            let variables = encoding.solver.n_vars();
            (encoding.solver, clauses, variables)
        }
        SourceSystem::ChainedS3(system) => {
            let encoding = encode_boolean_system_with(
                system.n_vars,
                &system.equations,
                &[],
                XorEncoding::Native,
            );
            let clauses = encoding.solver.n_clauses();
            let variables = encoding.solver.n_vars();
            (encoding.solver, clauses, variables)
        }
    };
    solver.conflict_budget = conflict_budget;
    let encoding_ns = encoding_started.elapsed().as_nanos();
    let solve_started = Instant::now();
    let max_models = 64usize;
    let mut models_examined = 0usize;
    let mut nonlifting_models_blocked = 0usize;
    let mut model_valid = None;
    let mut witness_valid = None;
    let (status, accepted) = loop {
        match solver.solve() {
            SolveResult::Sat => {
                let assignment = solver.model();
                let source_valid = validate_rows(&instance.rows, &assignment, instance.n_vars);
                model_valid = Some(source_valid);
                if !source_valid {
                    break ("sat_invalid_model", false);
                }
                models_examined += 1;
                let point_valid = source_point_witness_valid(
                    &instance.curve,
                    &instance.basis,
                    &instance.target,
                    &assignment,
                );
                witness_valid = Some(point_valid);
                if point_valid {
                    break ("sat", true);
                }
                nonlifting_models_blocked += 1;
                if models_examined >= max_models {
                    break ("model_cap_inconclusive", true);
                }
                // The factor coordinates determine the rational-lift question.
                // Block this x tuple while allowing the solver to choose new
                // chain/correspondence auxiliaries for other tuples.
                let clause: Vec<i32> = (0..3 * instance.ell)
                    .map(|index| {
                        let literal = (index + 1) as i32;
                        if assignment[index] {
                            -literal
                        } else {
                            literal
                        }
                    })
                    .collect();
                solver.reset_search();
                solver.add_clause(clause);
            }
            SolveResult::Unsat => break ("unsat", true),
            SolveResult::Unknown => break ("unknown_inconclusive", true),
        }
    };
    let solve_ns = solve_started.elapsed().as_nanos();
    (
        json!({
            "schema":"koblitz_pdp_isolated_backend.v1",
            "backend":"native-sat",
            "status":status,
            "source_instance_id":instance.id,
            "source_instance_verified":true,
            "source_artifacts":instance.artifact_receipts,
            "regenerated_source_exact":true,
            "conflict_budget":conflict_budget,
            "manifest_conflict_budget":instance.conflict_budget_from_manifest,
            "source_variables":instance.n_vars,
            "solver_variables":solver_variables,
            "initial_cnf_clauses":initial_clauses,
            "native_xor_rows":solver.n_xors(),
            "max_models":max_models,
            "models_examined":models_examined,
            "nonlifting_models_blocked":nonlifting_models_blocked,
            "source_model_valid":model_valid,
            "source_witness_valid":witness_valid,
            "stats":stats_json(&solver.stats),
            "timing_ns":{
                "source_verification":instance.verification_ns,
                "encoding":encoding_ns,
                "solve":solve_ns,
            },
            "interpretation":"Unknown is inconclusive; SAT is accepted only after exact source-row and rational point-witness validation",
        }),
        accepted,
    )
}

fn materialise_factor_points(curve: &BinaryCurve, basis: &[F2mElement]) -> Vec<BinaryPoint> {
    let mut points = Vec::new();
    for mask in 0..(1usize << basis.len()) {
        let mut x = F2mElement::zero(curve.m);
        for (index, element) in basis.iter().enumerate() {
            if (mask >> index) & 1 == 1 {
                x = x.add(element);
            }
        }
        points.extend(points_with_x(curve, &x));
    }
    points
}

fn direct_mitm(instance: VerifiedInstance) -> (Value, bool) {
    if instance.ell > 10 {
        return (
            json!({
                "schema":"koblitz_pdp_isolated_backend.v1",
                "backend":"direct-mitm",
                "status":"not_run_resource_cap",
                "source_instance_id":instance.id,
                "source_instance_verified":true,
                "source_artifacts":instance.artifact_receipts,
                "regenerated_source_exact":true,
                "ell":instance.ell,
                "ell_cap":10,
                "exhaustive":false,
                "source_witness_valid":Value::Null,
                "timing_ns":{"source_verification":instance.verification_ns},
            }),
            true,
        );
    }
    let factor_started = Instant::now();
    let points = materialise_factor_points(&instance.curve, &instance.basis);
    let factor_base_ns = factor_started.elapsed().as_nanos();
    let search_started = Instant::now();
    let mut pairs: HashMap<Option<(BigUint, BigUint)>, (usize, usize)> = HashMap::new();
    let mut additions = 0u64;
    for i in 0..points.len() {
        for j in i..points.len() {
            let sum = point_add(&instance.curve, &points[i], &points[j]);
            additions += 1;
            pairs.entry(point_key(&sum)).or_insert((i, j));
        }
    }
    let mut witness = None;
    for (k, point) in points.iter().enumerate() {
        let needed = point_add(&instance.curve, &instance.target, &point_neg(point));
        additions += 1;
        if let Some(&(i, j)) = pairs.get(&point_key(&needed)) {
            witness = Some((i, j, k));
            break;
        }
    }
    let search_ns = search_started.elapsed().as_nanos();
    let witness_valid = witness.map(|(i, j, k)| {
        let sum = point_add(
            &instance.curve,
            &point_add(&instance.curve, &points[i], &points[j]),
            &points[k],
        );
        sum == instance.target
    });
    let status = match (witness, witness_valid) {
        (Some(_), Some(true)) => "sat",
        (Some(_), _) => "sat_invalid_witness",
        (None, _) => "unsat",
    };
    let accepted = witness_valid != Some(false);
    (
        json!({
            "schema":"koblitz_pdp_isolated_backend.v1",
            "backend":"direct-mitm",
            "status":status,
            "source_instance_id":instance.id,
            "source_instance_verified":true,
            "source_artifacts":instance.artifact_receipts,
            "regenerated_source_exact":true,
            "factor_points":points.len(),
            "pair_entries":pairs.len(),
            "group_additions":additions,
            "exhaustive":true,
            "witness_indices":witness.map(|(i,j,k)| vec![i,j,k]),
            "source_witness_valid":witness_valid,
            "timing_ns":{
                "source_verification":instance.verification_ns,
                "factor_base_materialisation":factor_base_ns,
                "search":search_ns,
            },
            "interpretation":"SAT is accepted only after the factor-point sum equals the exact manifest target",
        }),
        accepted,
    )
}

fn usage() -> &'static str {
    "usage: koblitz_pdp_backend <verify-source|native-sat|direct-mitm|validate-model> <manifest.json> [conflict-budget|assignment.json]"
}

fn run(args: &[String]) -> Result<(Value, bool), String> {
    if !matches!(args.len(), 3 | 4) {
        return Err(usage().to_string());
    }
    let backend = args[1].as_str();
    if matches!(backend, "verify-source" | "direct-mitm") && args.len() != 3 {
        return Err(format!("{backend} does not take a conflict budget"));
    }
    if backend == "native-sat" && args.len() != 4 {
        return Err("native-sat requires a conflict budget".to_string());
    }
    if backend == "validate-model" && args.len() != 4 {
        return Err("validate-model requires an assignment JSON file".to_string());
    }
    let manifest_path = Path::new(&args[2]);
    let instance = verify_instance(manifest_path)?;
    match backend {
        "verify-source" => Ok((
            json!({
                "schema":"koblitz_pdp_source_verification.v1",
                "status":"verified",
                "source_instance_id":instance.id,
                "source_instance_verified":true,
                "source_artifacts":instance.artifact_receipts,
                "regenerated_source_exact":true,
                "n":instance.n,
                "ell":instance.ell,
                "source_variables":instance.n_vars,
                "timing_ns":{"source_verification":instance.verification_ns},
                "interpretation":"The algebraic factor base, explicit affine target, source identity, and all exported equations were independently reconstructed without running a solver",
            }),
            true,
        )),
        "native-sat" => {
            let budget = args[3]
                .parse::<u64>()
                .map_err(|_| "conflict budget must be an unsigned integer".to_string())?;
            if budget != instance.conflict_budget_from_manifest {
                return Err(format!(
                    "conflict budget {budget} does not match frozen manifest budget {}",
                    instance.conflict_budget_from_manifest
                ));
            }
            Ok(native_sat(instance, budget))
        }
        "direct-mitm" => Ok(direct_mitm(instance)),
        "validate-model" => validate_assignment(instance, Path::new(&args[3])),
        _ => Err(format!("unknown backend {backend}; {}", usage())),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() == 2 && args[1] == "--version" {
        println!("koblitz_pdp_backend 1 (koblitz_pdp_isolated_backend.v1)");
        return;
    }
    match run(&args) {
        Ok((result, accepted)) => {
            println!(
                "{}",
                serde_json::to_string_pretty(&result).expect("backend json")
            );
            if !accepted {
                std::process::exit(2);
            }
        }
        Err(error) => {
            eprintln!("koblitz_pdp_backend: {error}");
            std::process::exit(2);
        }
    }
}
