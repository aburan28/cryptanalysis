mod arithmetic;
mod input;

use arithmetic::{
    count_points, embedding_degree, gcd, primality, small_factorization, Curve, Point, Primality,
};
use input::AuditInput;
use num_bigint::BigUint;
use num_traits::{One, ToPrimitive, Zero};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{collections::HashSet, env, fs, process};

const CRITERIA: &str = include_str!("../catalog/criteria.json");
const ATTACK_MAP: &str = include_str!("../catalog/attack_map.json");

fn sha256(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}
fn number(n: &BigUint) -> String {
    n.to_str_radix(10)
}

fn catalog() -> Result<(Vec<Value>, Value), String> {
    let criteria: Vec<Value> = serde_json::from_str(CRITERIA).map_err(|e| e.to_string())?;
    let map: Value = serde_json::from_str(ATTACK_MAP).map_err(|e| e.to_string())?;
    let attacks = map["items"].as_array().ok_or("attack_map.items missing")?;
    let mut seen = HashSet::new();
    let mut rows = Vec::new();
    for entry in criteria.iter().chain(attacks.iter()) {
        let id = entry["id"].as_str().ok_or("criterion id missing")?;
        if !seen.insert(id.to_owned()) {
            return Err(format!("duplicate criterion id: {id}"));
        }
        let source = entry["url"]
            .as_str()
            .ok_or("criterion source URL missing")?;
        if !source.starts_with("https://") {
            return Err(format!("non-HTTPS source for {id}"));
        }
        rows.push(json!({
            "id": id, "name": entry["name"],
            "family": entry.get("family").cloned().unwrap_or(Value::String("Indexed criteria".into())),
            "domain": entry.get("domain").cloned().or_else(|| entry.get("scope").cloned()).unwrap_or(Value::Null),
            "required_witness": entry.get("witness").cloned().or_else(|| entry.get("requires").cloned()).unwrap_or(Value::Null),
            "source_url": source,
            "status": "unassessed",
            "reason": "The catalog lists the method; this audit has not verified its required witness."
        }));
    }
    if criteria.len() != 23 || attacks.len() != 38 || rows.len() != 61 {
        return Err(
            "unexpected catalog revision: expected 23 indexed and 38 research criteria".into(),
        );
    }
    let meta = json!({"schema":"ca.curve_criteria.v1", "indexed_count":criteria.len(),
        "research_count":attacks.len(), "criteria_sha256":sha256(CRITERIA.as_bytes()),
        "attack_map_sha256":sha256(ATTACK_MAP.as_bytes()),
        "upstream_commit":"2f1f9c553b4b2f03643f4200d6e12ab9221900c4"});
    Ok((rows, meta))
}

fn set(checks: &mut [Value], id: &str, status: &str, reason: impl Into<String>, evidence: Value) {
    if let Some(row) = checks.iter_mut().find(|row| row["id"] == id) {
        row["status"] = json!(status);
        row["reason"] = json!(reason.into());
        row["evidence"] = evidence;
    }
}

fn factor_json(n: &BigUint) -> Value {
    let (factors, remainder, complete) = small_factorization(n, 10_000);
    json!({"factors":factors.iter().map(|(p,e)| json!({"prime":number(p),"exponent":e})).collect::<Vec<_>>(),
        "remaining_cofactor":number(&remainder),"complete":complete,"trial_division_limit":10_000})
}

fn graph_lookup(path: &str, atlas_id: Option<&str>) -> Result<Value, String> {
    let bytes = fs::read(path).map_err(|e| format!("cannot read graph: {e}"))?;
    if bytes.len() > 25_000_000 {
        return Err("graph exceeds 25 MiB".into());
    }
    let graph: Value =
        serde_json::from_slice(&bytes).map_err(|e| format!("invalid graph JSON: {e}"))?;
    let nodes = graph["nodes"].as_array().ok_or("graph.nodes missing")?;
    let edges = graph["edges"].as_array().ok_or("graph.edges missing")?;
    let Some(id) = atlas_id else {
        return Ok(
            json!({"status":"unbound", "reason":"--graph needs input.atlas_id for an exact-ID lookup; no name-only match is used.",
            "sha256":sha256(&bytes)}),
        );
    };
    let matches: Vec<_> = nodes.iter().filter(|n| n["id"] == id).collect();
    if matches.len() != 1 {
        return Ok(
            json!({"status":"not_found", "atlas_id":id,"matches":matches.len(),"sha256":sha256(&bytes)}),
        );
    }
    let links: Vec<_> = edges
        .iter()
        .filter(|e| e["source"] == id || e["target"] == id)
        .cloned()
        .collect();
    Ok(
        json!({"status":"claimed_id_match", "atlas_id":id,"node":matches[0],
        "incident_edges":links,"sha256":sha256(&bytes),
        "identity_warning":"The supplied atlas_id was not derived from the input coefficients by this binary."}),
    )
}

fn audit(
    input: AuditInput,
    raw_hash: String,
    max_k: u32,
    count_limit: u64,
    graph_path: Option<&str>,
) -> Result<Value, String> {
    let (mut checks, meta) = catalog()?;
    let prime_status = primality(&input.p);
    let field_status = match prime_status {
        Primality::ProvenPrime => "proven_prime",
        Primality::ProvenComposite => "composite",
        Primality::ProbablePrime => "probable_prime_unproved",
    };
    let supported = input.degree == 1
        && input.model == "short_weierstrass"
        && input.p > BigUint::from(3u32)
        && prime_status != Primality::ProvenComposite;
    let mut validation = json!({"field_characteristic":field_status,
        "arithmetic_supported":supported,"curve_nonsingular":null,"generator_on_curve":null,
        "r_times_generator_is_infinity":null,"curve_order_status":"unavailable"});
    let mut derived = json!({"embedding_degree_search_max":max_k,"point_count_limit":count_limit});
    let mut exact_order: Option<BigUint> = None;
    let mut invalid = prime_status == Primality::ProvenComposite;
    if input.degree == 1 {
        for id in [
            "ghs_binary",
            "ghs_odd_covering",
            "cubic_norm_one",
            "quadratic_torus",
            "extension_index_calculus",
            "cover_and_decomposition",
            "cubic_jacobian_isogeny",
            "proper_subfield_points",
            "gls_frobenius",
            "jv_intermediate_field_cover",
        ] {
            set(&mut checks,id,"outside_domain","This input has extension degree one; the listed proper-subfield route needs an extension-field instance.",Value::Null);
        }
    }
    if input.p != BigUint::from(2u32) {
        set(
            &mut checks,
            "ghs_binary",
            "outside_domain",
            "The field characteristic is not two.",
            Value::Null,
        );
    }
    if supported {
        let curve = Curve {
            p: &input.p,
            a: &input.a,
            b: &input.b,
        };
        let nonsingular = !curve.discriminant_factor().is_zero();
        validation["curve_nonsingular"] = json!(nonsingular);
        if !nonsingular {
            invalid = true;
        }
        if nonsingular {
            if let Some((x, y)) = &input.generator {
                let point = Point::Affine {
                    x: x.clone(),
                    y: y.clone(),
                };
                let on_curve = curve.contains(&point);
                validation["generator_on_curve"] = json!(on_curve);
                if !on_curve {
                    invalid = true;
                }
                if on_curve {
                    if let Some(r) = &input.r {
                        let annihilates =
                            curve.mul(&point, r).map_err(str::to_owned)? == Point::Infinity;
                        validation["r_times_generator_is_infinity"] = json!(annihilates);
                        if !annihilates {
                            invalid = true;
                        }
                    }
                }
            }
            if prime_status == Primality::ProvenPrime {
                if let Some(p) = input.p.to_u64().filter(|p| *p <= count_limit) {
                    let n = count_points(p, input.a.to_u64().unwrap(), input.b.to_u64().unwrap());
                    let n = BigUint::from(n);
                    exact_order = Some(n.clone());
                    validation["curve_order_status"] = json!("independently_counted");
                    derived["curve_order"] = json!(number(&n));
                    if input
                        .curve_order
                        .as_ref()
                        .is_some_and(|claimed| claimed != &n)
                    {
                        invalid = true;
                    }
                    let twist = BigUint::from(2u32) * &input.p + BigUint::from(2u32) - &n;
                    derived["quadratic_twist_order"] = json!(number(&twist));
                    derived["quadratic_twist_small_factors"] = factor_json(&twist);
                    let p_plus_one = &input.p + BigUint::one();
                    derived["trace"] = if n <= p_plus_one {
                        json!(number(&(&p_plus_one - &n)))
                    } else {
                        json!(format!("-{}", number(&(&n - &p_plus_one))))
                    };
                    if n == input.p {
                        set(
                            &mut checks,
                            "anomalous_prime",
                            "condition_verified",
                            "Exact point enumeration gives #E(F_p)=p.",
                            json!({"point_count":number(&n)}),
                        );
                    } else {
                        set(
                            &mut checks,
                            "anomalous_prime",
                            "condition_excluded",
                            "Exact point enumeration gives #E(F_p) different from p.",
                            json!({"point_count":number(&n)}),
                        );
                    }
                    if n == &input.p + BigUint::one() {
                        set(&mut checks,"supersingular_pairing","geometry_verified",
                            "For p>3, exact trace zero establishes the prime-field supersingular condition; pairing transfer remains separate.",json!({"trace":"0"}));
                    } else {
                        set(
                            &mut checks,
                            "supersingular_pairing",
                            "geometry_excluded",
                            "Exact nonzero trace excludes prime-field supersingularity for p>3.",
                            json!({"point_count":number(&n)}),
                        );
                    }
                    set(&mut checks,"twist_order","structural_data",
                        "Exact twist order is computed; exploitation requires an input-validation and static-scalar protocol witness.",
                        json!({"twist_order":number(&twist)}));
                }
            }
            if exact_order.is_none() {
                if let Some(claimed) = &input.curve_order {
                    validation["curve_order_status"] = json!("supplied_unverified");
                    derived["claimed_curve_order"] = json!(number(claimed));
                    if claimed == &input.p {
                        set(&mut checks,"anomalous_prime","candidate_unverified",
                            "The supplied order equals p, but this binary has not verified that large-field point count.",
                            json!({"claimed_curve_order":number(claimed)}));
                    }
                }
            }
            let mut c = None;
            for i in 0..4u32 {
                let x = BigUint::from(i);
                let f = (&x * &x * &x + &input.a * &x + &input.b) % &input.p;
                if !f.is_zero() {
                    c = Some(i);
                    break;
                }
            }
            if let Some(c) = c {
                set(&mut checks,"same_field_cover",
                    if prime_status == Primality::ProvenPrime {"geometry_verified"} else {"geometry_conditional"},
                    "The degree-two map (u,v)->(u^2+c,v) gives a smooth genus-two same-field cover; no subgroup or relation advantage follows from geometry alone.",
                    json!({"c":c,"equation":"v^2=F(u^2+c)","degree":2,"destination_field":"original_field"}));
            }
            if input.a.is_zero() || input.b.is_zero() {
                set(&mut checks,"glv_endomorphism","structural_candidate",
                    "j=0 or j=1728 special automorphisms are present; a subgroup eigenvalue and measured orbit quotient are still required.",
                    json!({"j_family":if input.a.is_zero() {"j0"} else {"j1728"}}));
            }
        }
    }
    if let Some(r) = &input.r {
        let r_prime = primality(r);
        derived["selected_order_primality"] = json!(match r_prime {
            Primality::ProvenPrime => "proven_prime",
            Primality::ProvenComposite => "composite",
            Primality::ProbablePrime => "probable_prime_unproved",
        });
        let factors = factor_json(r);
        derived["selected_order_factorization"] = factors.clone();
        let (prime_factors, _, complete) = small_factorization(r, 10_000);
        let mut exact_generator_order = false;
        if complete && supported && !invalid {
            if let Some((x, y)) = &input.generator {
                let curve = Curve {
                    p: &input.p,
                    a: &input.a,
                    b: &input.b,
                };
                let point = Point::Affine {
                    x: x.clone(),
                    y: y.clone(),
                };
                exact_generator_order =
                    curve.mul(&point, r).map_err(str::to_owned)? == Point::Infinity;
                for (factor, _) in &prime_factors {
                    if curve.mul(&point, &(r / factor)).map_err(str::to_owned)? == Point::Infinity {
                        exact_generator_order = false;
                    }
                }
                validation["generator_exact_order"] = json!(exact_generator_order);
            }
        }
        if complete && exact_generator_order && prime_factors.iter().all(|(p, _)| p.bits() <= 32) {
            set(&mut checks,"smooth_selected_order","condition_verified",
                "The generator has the exact stated order and that order factors completely into at most 32-bit primes.",factors);
        } else if complete {
            set(&mut checks,"smooth_selected_order","factorization_complete_unbound",
                "The order factorization is complete, but an exact generator-order or small-factor attack certificate is missing.",factors);
        } else if r_prime == Primality::ProvenComposite {
            set(
                &mut checks,
                "smooth_selected_order",
                "partial_factorization",
                "Only the recorded factors are established; the remaining cofactor is unresolved.",
                factors,
            );
        }
        if supported && gcd(input.p.clone(), r.clone()) == BigUint::one() {
            let k = embedding_degree(&input.p, r, max_k);
            derived["embedding_degree_within_bound"] = json!(k);
            for id in [
                "mov_weil_pairing",
                "frey_ruck_tate_pairing",
                "minimal_pairing_field",
            ] {
                if let Some(k) = k {
                    set(&mut checks,id,"structural_candidate",
                        "The modular embedding-degree condition holds; an explicit nondegenerate selected-subgroup transfer and target-field cost remain required.",
                        json!({"k":k,"r_divides_p_to_k_minus_one":true}));
                } else {
                    set(&mut checks,id,"not_found_within_bound",
                        format!("No k <= {max_k} satisfies r | p^k-1; larger degrees were not searched."),
                        json!({"max_k":max_k}));
                }
            }
        }
        if let Some(n) = &exact_order {
            validation["selected_order_divides_curve_order"] = json!(n % r == BigUint::zero());
            if n % r != BigUint::zero() {
                invalid = true;
            } else {
                let cofactor = n / r;
                derived["cofactor"] = json!(number(&cofactor));
                if cofactor > BigUint::one() {
                    set(&mut checks,"small_subgroup","structural_candidate",
                        "The exact curve order has a nontrivial cofactor; exploitability requires accepted low-order inputs and a static-scalar protocol witness.",
                        json!({"cofactor":number(&cofactor)}));
                }
            }
        } else if let Some(claimed) = &input.curve_order {
            validation["selected_order_divides_claimed_order"] =
                json!(claimed % r == BigUint::zero());
            if claimed % r != BigUint::zero() {
                invalid = true;
            }
        }
    }
    let graph = graph_path
        .map(|path| graph_lookup(path, input.atlas_id.as_deref()))
        .transpose()?;
    if let Some(g) = &graph {
        if g["status"] == "claimed_id_match" {
            set(&mut checks,"isogeny_transfer","graph_record_unbound",
                "The supplied atlas ID matches a graph node, but this binary has not bound that ID to the exact input coefficients or replayed any incident maps.",
                json!({"incident_edge_count":g["incident_edges"].as_array().map_or(0,Vec::len)}));
        }
    }
    let confirmed = checks
        .iter()
        .filter(|row| row["status"] == "condition_verified")
        .count();
    let candidates = checks
        .iter()
        .filter(|row| {
            row["status"] == "structural_candidate" || row["status"] == "candidate_unverified"
        })
        .count();
    let unassessed = checks
        .iter()
        .filter(|row| row["status"] == "unassessed")
        .count();
    let verdict = if invalid {
        "invalid_parameters"
    } else if confirmed > 0 {
        "weakness_condition_verified"
    } else {
        "incomplete_assessment"
    };
    Ok(
        json!({"schema":"ca.curve_audit.v1","catalog":meta,"input_sha256":raw_hash,
        "curve":{"name":input.name,"characteristic":number(&input.p),"degree":input.degree,
            "modulus":input.modulus,"model":input.model,"a":number(&input.a),"b":number(&input.b),
            "selected_order":input.r.as_ref().map(number),"atlas_id":input.atlas_id},
        "validation":validation,"derived":derived,"graph":graph,
        "protocol_context_supplied":input.protocol_present,"checks":checks,
        "summary":{"criteria_total":61,"verified_conditions":confirmed,"structural_candidates":candidates,"unassessed":unassessed},
        "verdict":verdict,"verdict_meaning":"This is an evidence inventory, not a certificate that a curve or implementation is safe."}),
    )
}

fn usage() -> ! {
    eprintln!("usage: ca-curve-audit catalog | audit --input FILE [--max-k 32] [--point-count-limit 100000] [--graph GRAPH.json]");
    process::exit(2)
}

fn run() -> Result<Value, String> {
    let args: Vec<String> = env::args().collect();
    if args.len() == 2 && args[1] == "catalog" {
        let (checks, meta) = catalog()?;
        return Ok(json!({"catalog":meta,"criteria":checks}));
    }
    if args.get(1).map(String::as_str) != Some("audit") {
        usage();
    }
    let mut input_path = None;
    let mut graph = None;
    let mut max_k = 32u32;
    let mut count_limit = 100_000u64;
    let mut i = 2;
    while i < args.len() {
        let value = args
            .get(i + 1)
            .ok_or_else(|| format!("missing value for {}", args[i]))?;
        match args[i].as_str() {
            "--input" => input_path = Some(value.as_str()),
            "--graph" => graph = Some(value.as_str()),
            "--max-k" => max_k = value.parse().map_err(|_| "--max-k must be an integer")?,
            "--point-count-limit" => {
                count_limit = value
                    .parse()
                    .map_err(|_| "--point-count-limit must be an integer")?
            }
            other => return Err(format!("unknown option: {other}")),
        }
        i += 2;
    }
    if !(1..=256).contains(&max_k) {
        return Err("--max-k must be 1..256".into());
    }
    if count_limit > 1_000_000 {
        return Err("--point-count-limit cannot exceed 1000000".into());
    }
    let path = input_path.ok_or("--input is required")?;
    let bytes = fs::read(path).map_err(|e| format!("cannot read input: {e}"))?;
    let hash = sha256(&bytes);
    audit(input::parse(&bytes)?, hash, max_k, count_limit, graph)
}

fn main() {
    match run() {
        Ok(report) => println!("{}", serde_json::to_string_pretty(&report).unwrap()),
        Err(error) => {
            eprintln!("error: {error}");
            process::exit(2);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(bytes: &[u8], max_k: u32) -> Value {
        audit(
            input::parse(bytes).unwrap(),
            sha256(bytes),
            max_k,
            100_000,
            None,
        )
        .unwrap()
    }

    fn status<'a>(report: &'a Value, id: &str) -> &'a str {
        report["checks"]
            .as_array()
            .unwrap()
            .iter()
            .find(|c| c["id"] == id)
            .unwrap()["status"]
            .as_str()
            .unwrap()
    }

    #[test]
    fn catalog_ids_and_sources_are_unique() {
        let (rows, meta) = catalog().unwrap();
        assert_eq!(rows.len(), 61);
        assert_eq!(meta["indexed_count"], 23);
        assert_eq!(meta["research_count"], 38);
        assert_eq!(
            meta["criteria_sha256"],
            "165fc26fa90f1789e3fe01301cda59c8fd2df1a3219fe5ba9cfc97397148ba93"
        );
        assert_eq!(
            meta["attack_map_sha256"],
            "3316d2b821a9f4be9fbd43c538a88a26877370283dbd07acdae4fcbb26dd1935"
        );
    }

    #[test]
    fn anomalous_curve_has_exact_point_and_generator_evidence() {
        let report = fixture(include_bytes!("../examples/anomalous-101.json"), 6);
        assert_eq!(report["verdict"], "weakness_condition_verified");
        assert_eq!(
            report["validation"]["curve_order_status"],
            "independently_counted"
        );
        assert_eq!(report["validation"]["generator_exact_order"], true);
        assert_eq!(status(&report, "anomalous_prime"), "condition_verified");
        assert_eq!(report["derived"]["trace"], "1");
    }

    #[test]
    fn negative_trace_and_missing_subgroup_do_not_become_safe() {
        let report = fixture(include_bytes!("../examples/negative-trace-101.json"), 6);
        assert_eq!(report["derived"]["trace"], "-13");
        assert_eq!(status(&report, "anomalous_prime"), "condition_excluded");
        assert_eq!(status(&report, "mov_weil_pairing"), "unassessed");
        assert_eq!(report["verdict"], "incomplete_assessment");
    }

    #[test]
    fn p192_checks_generator_and_bounds_pairing_without_trusting_order_claim() {
        let report = fixture(include_bytes!("../examples/nist-p192.json"), 6);
        assert_eq!(report["validation"]["generator_on_curve"], true);
        assert_eq!(report["validation"]["r_times_generator_is_infinity"], true);
        assert_eq!(
            report["validation"]["curve_order_status"],
            "supplied_unverified"
        );
        assert_eq!(
            report["validation"]["field_characteristic"],
            "probable_prime_unproved"
        );
        assert_eq!(
            status(&report, "mov_weil_pairing"),
            "not_found_within_bound"
        );
        assert_eq!(status(&report, "anomalous_prime"), "unassessed");
        assert_eq!(report["verdict"], "incomplete_assessment");
    }

    #[test]
    fn incorrect_generator_order_is_rejected() {
        let mut value: Value =
            serde_json::from_slice(include_bytes!("../examples/anomalous-101.json")).unwrap();
        value["subgroup"]["order"] = json!("5");
        let bytes = serde_json::to_vec(&value).unwrap();
        let report = fixture(&bytes, 6);
        assert_eq!(report["validation"]["r_times_generator_is_infinity"], false);
        assert_eq!(report["verdict"], "invalid_parameters");
    }

    #[test]
    fn unknown_input_key_fails_closed() {
        let mut value: Value =
            serde_json::from_slice(include_bytes!("../examples/anomalous-101.json")).unwrap();
        value["subgoup"] = json!({"order":"101"});
        assert!(input::parse(&serde_json::to_vec(&value).unwrap()).is_err());
    }

    #[test]
    fn prime_field_rejects_extension_representation_fields() {
        let mut value: Value =
            serde_json::from_slice(include_bytes!("../examples/anomalous-101.json")).unwrap();
        value["field"]["modulus"] = json!("x+1");
        assert!(input::parse(&serde_json::to_vec(&value).unwrap()).is_err());
    }

    #[test]
    fn extension_field_preserves_unsupported_criteria_as_unassessed() {
        let bytes = br#"{"schema":"ca.curve_input.v1","field":{"characteristic":"41","degree":6,"modulus":"z^6+z+1","element_encoding":"polynomial_integer"},"curve":{"model":"short_weierstrass","a":"5","b":"7"}}"#;
        let report = fixture(bytes, 6);
        assert_eq!(report["validation"]["arithmetic_supported"], false);
        assert_eq!(status(&report, "jv_intermediate_field_cover"), "unassessed");
        assert_eq!(report["verdict"], "incomplete_assessment");
    }
}
