//! Same-input two-scalar norm-4033 Horner pilot for rho restart points.
use std::time::Instant;
use num_bigint::BigInt;
use serde_json::Value;
use super::{scalar_words_256, unit_orbit_windows};
use std::collections::BTreeMap;

pub(super) fn run(fixture_path: &str, count: usize) {
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read frozen fixture"))
        .expect("parse frozen fixture");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let inputs = rows.iter().take(count).map(|row| {
        let a = BigInt::parse_bytes(
            row["a_hex"].as_str().expect("a").as_bytes(),16).expect("a hex");
        let b = BigInt::parse_bytes(
            row["b_hex"].as_str().expect("b").as_bytes(),16).expect("b hex");
        (scalar_words_256(&a).expect("a words"),
         scalar_words_256(&b).expect("b words"),
         row["point_hex"].as_str().expect("expected").to_owned())
    }).collect::<Vec<_>>();
    let generator_start = Instant::now();
    let generator_bytes = unit_orbit_windows::warm_alt_split_prime_two_x_table()
        + unit_orbit_windows::warm_joint_seed_sets();
    let generator_preparation_ms = generator_start.elapsed().as_secs_f64()*1000.0;
    let q_start = Instant::now();
    let q_table = unit_orbit_windows::prepare_joint_q(
        fixture["q_hex"].as_str().expect("Q"));
    let q_preparation_ms = q_start.elapsed().as_secs_f64()*1000.0;
    let retained_bytes = generator_bytes + q_table.retained_bytes;
    let start = Instant::now();
    let answers = inputs.iter().map(|(a,b,_)|
        unit_orbit_windows::multiply_u256_tau_joint(*a,*b,&q_table))
        .collect::<Vec<_>>();
    let online_ms = start.elapsed().as_secs_f64()*1000.0;
    for (index,(actual,(_,_,expected))) in answers.iter().zip(inputs.iter()).enumerate() {
        assert_eq!(actual,expected,"rho joint case {index}");
    }
    println!("verified=1 count={count} online_ms={online_ms:.6} \
              generator_preparation_ms={generator_preparation_ms:.6} \
              q_preparation_ms={q_preparation_ms:.6} retained_bytes={retained_bytes} \
              mode=joint point={}",answers.last().expect("nonempty"));
}

pub(super) fn run_demand(fixture_path: &str, count: usize) {
    run_demand_variant(fixture_path,count,false,None,QStorage::Affine);
}

pub(super) fn run_graph(fixture_path: &str, count: usize) {
    run_demand_variant(fixture_path,count,true,None,QStorage::Affine);
}

pub(super) fn write_graph_plan(fixture_path: &str, count: usize, plan_path: &str) {
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read fixture"))
        .expect("parse fixture");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let b_hex = rows.iter().take(count).map(|row|
        row["b_hex"].as_str().expect("b hex").to_owned()).collect::<Vec<_>>();
    let b_choices = b_hex.iter().map(|hex| {
        let b = BigInt::parse_bytes(hex.as_bytes(),16).expect("b scalar");
        unit_orbit_windows::joint_choices_for_words(scalar_words_256(&b).expect("b words"))
    }).collect::<Vec<_>>();
    let plan = unit_orbit_windows::plan_joint_q_graph(&b_choices);
    let artifact = serde_json::json!({
        "schema":1,"count":count,"b_hex":b_hex,"choices":b_choices,
        "graph":unit_orbit_windows::joint_graph_plan_json(&plan),
    });
    std::fs::write(plan_path,serde_json::to_string_pretty(&artifact).unwrap()+"\n")
        .expect("write graph plan");
    println!("planned=1 count={count} graph_edges={} direct_seeds={} plan_bytes={}",
             plan.graph_edges,plan.direct_seeds,plan.retained_bytes);
}

fn load_graph_plan(plan_path: &str, rows: &[Value], count: usize)
    -> (Vec<[(usize,usize);23]>,unit_orbit_windows::JointQGraphPlan) {
    let artifact: Value = serde_json::from_str(
        &std::fs::read_to_string(plan_path).expect("read graph plan"))
        .expect("parse graph plan");
    assert_eq!(artifact["schema"].as_u64(),Some(1));
    assert_eq!(artifact["count"].as_u64(),Some(count as u64));
    let b_hex = artifact["b_hex"].as_array().expect("plan b scalars");
    assert_eq!(b_hex.len(),count);
    for (stored,row) in b_hex.iter().zip(rows.iter().take(count)) {
        assert_eq!(stored.as_str(),row["b_hex"].as_str(),"plan scalar stream");
    }
    let choices = artifact["choices"].as_array().expect("plan choices").iter()
        .map(|row| {
            let pairs = serde_json::from_value::<Vec<(usize,usize)>>(row.clone())
                .expect("plan choice pairs");
            let array: [(usize,usize);23] = pairs.try_into().expect("23 plan choices");
            array
        }).collect::<Vec<_>>();
    assert_eq!(choices.len(),count);
    for (stored,hex) in choices.iter().zip(b_hex.iter()) {
        let b = BigInt::parse_bytes(hex.as_str().expect("b scalar").as_bytes(),16)
            .expect("b hex");
        assert_eq!(*stored,unit_orbit_windows::joint_choices_for_words(
            scalar_words_256(&b).expect("b words")),"plan recoding");
    }
    let plan = unit_orbit_windows::joint_graph_plan_from_json(&artifact["graph"]);
    (choices,plan)
}

pub(super) fn run_graph_from_plan(fixture_path: &str, count: usize, plan_path: &str) {
    run_demand_variant(fixture_path,count,true,Some(plan_path),QStorage::Affine);
}

pub(super) fn run_projective_graph_from_plan(
    fixture_path: &str, count: usize, plan_path: &str) {
    run_demand_variant(fixture_path,count,true,Some(plan_path),QStorage::Projective);
}

pub(super) fn run_hybrid_graph_from_plan(
    fixture_path: &str, count: usize, plan_path: &str) {
    run_demand_variant(fixture_path,count,true,Some(plan_path),QStorage::Hybrid);
}

#[derive(Clone, Copy)]
enum QStorage { Affine, Projective, Hybrid }

enum SparseQRepresentation {
    Affine(unit_orbit_windows::SparseJointQTables),
    Projective(unit_orbit_windows::SparseJointQProjectiveTables),
    Hybrid(unit_orbit_windows::SparseJointQHybridTables),
}

impl SparseQRepresentation {
    fn retained_bytes(&self) -> usize {
        match self { Self::Affine(q) => q.retained_bytes,
                     Self::Projective(q) => q.retained_bytes,
                     Self::Hybrid(q) => q.retained_bytes }
    }
    fn constructed_points(&self) -> usize {
        match self { Self::Affine(q) => q.constructed_points,
                     Self::Projective(q) => q.constructed_points,
                     Self::Hybrid(q) => q.constructed_points }
    }
}

fn run_demand_variant(fixture_path: &str, count: usize,
                      graph: bool, plan_path: Option<&str>, storage: QStorage) {
    assert!(matches!(storage,QStorage::Affine) || plan_path.is_some(),
            "alternate Q table needs a frozen graph plan");
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read frozen fixture"))
        .expect("parse frozen fixture");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let inputs = rows.iter().take(count).map(|row| {
        let a = BigInt::parse_bytes(
            row["a_hex"].as_str().expect("a").as_bytes(),16).expect("a hex");
        let b = BigInt::parse_bytes(
            row["b_hex"].as_str().expect("b").as_bytes(),16).expect("b hex");
        (scalar_words_256(&a).expect("a words"),
         scalar_words_256(&b).expect("b words"),
         row["point_hex"].as_str().expect("expected").to_owned())
    }).collect::<Vec<_>>();
    let generator_start = Instant::now();
    let generator_bytes = unit_orbit_windows::warm_alt_split_prime_two_x_table()
        + unit_orbit_windows::warm_joint_seed_sets();
    let generator_preparation_ms = generator_start.elapsed().as_secs_f64()*1000.0;
    let plan_load_start = Instant::now();
    let precomputed = plan_path.map(|path| load_graph_plan(path,rows,count));
    let hybrid_selection = if matches!(storage,QStorage::Hybrid) {
        let (choices,plan) = precomputed.as_ref().expect("hybrid frozen plan");
        Some(unit_orbit_windows::compile_joint_q_hybrid_selection(plan,choices))
    } else { None };
    let plan_load_ms = if plan_path.is_some() {
        plan_load_start.elapsed().as_secs_f64()*1000.0
    } else { 0.0 };
    let graph_plan_ms = 0.0;
    let target_start = Instant::now();
    let online_choices = if plan_path.is_some() { None } else { Some(inputs.iter().map(|(_,b,_)|
        unit_orbit_windows::joint_choices_for_words(*b)).collect::<Vec<_>>()) };
    let b_choices = if let Some((choices,_)) = precomputed.as_ref() { choices }
        else { online_choices.as_ref().expect("online choices") };
    let (q_table,graph_edges,direct_seeds) = if let Some((_,plan)) = precomputed.as_ref() {
        let q_hex = fixture["q_hex"].as_str().expect("Q");
        let table = match storage {
            QStorage::Projective => SparseQRepresentation::Projective(
                unit_orbit_windows::instantiate_joint_q_graph_projective(q_hex,plan)),
            QStorage::Hybrid => SparseQRepresentation::Hybrid(
                unit_orbit_windows::instantiate_joint_q_graph_hybrid(
                    q_hex,plan,hybrid_selection.as_ref().expect("hybrid selector"))),
            QStorage::Affine => SparseQRepresentation::Affine(
                unit_orbit_windows::instantiate_joint_q_graph(q_hex,plan)),
        };
        (table,plan.graph_edges,plan.direct_seeds)
    } else if graph {
        let (table,edges,direct) = unit_orbit_windows::prepare_joint_q_sparse_graph(
            fixture["q_hex"].as_str().expect("Q"), b_choices);
        (SparseQRepresentation::Affine(table),edges,direct)
    } else {
        (SparseQRepresentation::Affine(unit_orbit_windows::prepare_joint_q_sparse(
            fixture["q_hex"].as_str().expect("Q"), b_choices)),0,0)
    };
    let target_preparation_ms = target_start.elapsed().as_secs_f64()*1000.0;
    let eval_start = Instant::now();
    let answers = inputs.iter().zip(b_choices.iter()).map(|((a,_,_),b)| match &q_table {
        SparseQRepresentation::Affine(q) =>
            unit_orbit_windows::multiply_u256_tau_joint_sparse(*a,*b,q),
        SparseQRepresentation::Projective(q) =>
            unit_orbit_windows::multiply_u256_tau_joint_sparse_projective(*a,*b,q),
        SparseQRepresentation::Hybrid(q) =>
            unit_orbit_windows::multiply_u256_tau_joint_sparse_hybrid(*a,*b,q),
    })
        .collect::<Vec<_>>();
    let restart_eval_ms = eval_start.elapsed().as_secs_f64()*1000.0;
    let online_ms = target_preparation_ms + restart_eval_ms;
    for (index,(actual,(_,_,expected))) in answers.iter().zip(inputs.iter()).enumerate() {
        assert_eq!(actual,expected,"rho sparse joint case {index}");
    }
    let plan_bytes = precomputed.as_ref().map(|(choices,plan)|
        plan.retained_bytes + choices.capacity()*std::mem::size_of_val(&choices[0]))
        .unwrap_or(0) + hybrid_selection.as_ref().map_or(0,|s| s.retained_bytes());
    let retained_bytes = generator_bytes + q_table.retained_bytes() + plan_bytes;
    let mode = if matches!(storage,QStorage::Projective) { "joint_graph_projective_planned" }
        else if matches!(storage,QStorage::Hybrid) { "joint_graph_hybrid_planned" }
        else if plan_path.is_some() { "joint_graph_planned" }
        else if graph { "joint_graph" } else { "joint_demand" };
    println!("verified=1 count={count} online_ms={online_ms:.6} \
              target_preparation_ms={target_preparation_ms:.6} \
              restart_eval_ms={restart_eval_ms:.6} \
              generator_preparation_ms={generator_preparation_ms:.6} \
              graph_plan_ms={graph_plan_ms:.6} plan_load_ms={plan_load_ms:.6} \
              plan_bytes={plan_bytes} \
              retained_bytes={retained_bytes} constructed_q_points={} \
              graph_edges={graph_edges} direct_seeds={direct_seeds} \
              mode={mode} hybrid_affine_points={} hybrid_projective_points={} point={}",
              q_table.constructed_points(),
              match &q_table { SparseQRepresentation::Hybrid(q) => q.affine_points,
                               _ => 0 },
              match &q_table { SparseQRepresentation::Hybrid(q) => q.projective_points,
                               _ => 0 },
              answers.last().expect("nonempty"));
}

pub(super) fn run_profile(fixture_path: &str, count: usize) {
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read frozen fixture"))
        .expect("parse frozen fixture");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let mut digit_raw = BTreeMap::<(usize,usize,usize,usize),usize>::new();
    let mut digit_orbit = BTreeMap::<(usize,usize,usize),usize>::new();
    let mut terminal_raw = BTreeMap::<(usize,usize,usize,usize),usize>::new();
    let mut terminal_orbit = BTreeMap::<(usize,usize,usize),usize>::new();
    let (mut g_only,mut q_only,mut neither) = (0usize,0usize,0usize);
    for row in rows.iter().take(count) {
        let a = BigInt::parse_bytes(
            row["a_hex"].as_str().expect("a").as_bytes(),16).expect("a hex");
        let b = BigInt::parse_bytes(
            row["b_hex"].as_str().expect("b").as_bytes(),16).expect("b hex");
        let a = unit_orbit_windows::joint_choices_for_words(
            scalar_words_256(&a).expect("a words"));
        let b = unit_orbit_windows::joint_choices_for_words(
            scalar_words_256(&b).expect("b words"));
        for index in 0..a.len() {
            let (ga,gu) = a[index];
            let (qb,qu) = b[index];
            if ga == 0 && qb == 0 { neither += 1; continue; }
            if ga == 0 { q_only += 1; continue; }
            if qb == 0 { g_only += 1; continue; }
            assert!(gu < 6 && qu < 6);
            let relative_rotation = ((qu/2+3-gu/2)%3)*2;
            let relative_sign = (qu^gu)&1;
            let orbit_key = (ga,qb,relative_rotation+relative_sign);
            let raw_key = (ga,gu,qb,qu);
            if index == a.len()-1 {
                *terminal_raw.entry(raw_key).or_default() += 1;
                *terminal_orbit.entry(orbit_key).or_default() += 1;
            } else {
                *digit_raw.entry(raw_key).or_default() += 1;
                *digit_orbit.entry(orbit_key).or_default() += 1;
            }
        }
    }
    let both_digit = digit_raw.values().sum::<usize>();
    let both_terminal = terminal_raw.values().sum::<usize>();
    let digit_reused = digit_orbit.values().filter(|&&n| n > 1).count();
    let terminal_reused = terminal_orbit.values().filter(|&&n| n > 1).count();
    let b_choices = rows.iter().take(count).map(|row| {
        let b = BigInt::parse_bytes(row["b_hex"].as_str().expect("b").as_bytes(),16)
            .expect("b hex");
        unit_orbit_windows::joint_choices_for_words(scalar_words_256(&b).expect("b words"))
    }).collect::<Vec<_>>();
    let (q_digit_seeds,q_terminal_seeds) =
        unit_orbit_windows::joint_q_seed_pairs_for_choices(&b_choices);
    println!("{}",serde_json::json!({
        "q_digit_seeds":q_digit_seeds,"q_terminal_seeds":q_terminal_seeds,
        "schema":1,"count":count,"steps_per_restart":23,
        "g_only":g_only,"q_only":q_only,"neither":neither,
        "both_digit":both_digit,"both_terminal":both_terminal,
        "digit_unique_raw":digit_raw.len(),
        "digit_unique_common_unit_orbit":digit_orbit.len(),
        "digit_reused_orbits":digit_reused,
        "digit_max_orbit_frequency":digit_orbit.values().copied().max().unwrap_or(0),
        "digit_precompute_addition_savings_upper_bound":both_digit-digit_orbit.len(),
        "terminal_unique_raw":terminal_raw.len(),
        "terminal_unique_common_unit_orbit":terminal_orbit.len(),
        "terminal_reused_orbits":terminal_reused,
        "terminal_precompute_addition_savings_upper_bound":
            both_terminal-terminal_orbit.len(),
    }));
}

pub(super) fn run_fused(fixture_path: &str, count: usize) {
    run_fused_variant(fixture_path,count,false,None);
}

pub(super) fn run_fused_graph(fixture_path: &str, count: usize) {
    run_fused_variant(fixture_path,count,true,None);
}

pub(super) fn run_fused_graph_from_plan(fixture_path: &str, count: usize, plan_path: &str) {
    run_fused_variant(fixture_path,count,true,Some(plan_path));
}

fn run_fused_variant(fixture_path: &str, count: usize, graph: bool,
                     plan_path: Option<&str>) {
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read frozen fixture"))
        .expect("parse frozen fixture");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let inputs = rows.iter().take(count).map(|row| {
        let a = BigInt::parse_bytes(
            row["a_hex"].as_str().expect("a").as_bytes(),16).expect("a hex");
        let b = BigInt::parse_bytes(
            row["b_hex"].as_str().expect("b").as_bytes(),16).expect("b hex");
        (scalar_words_256(&a).expect("a words"),
         scalar_words_256(&b).expect("b words"),
         row["point_hex"].as_str().expect("expected").to_owned())
    }).collect::<Vec<_>>();
    let a_words = inputs.iter().map(|(a,_,_)| *a).collect::<Vec<_>>();
    let generator_start = Instant::now();
    let generator_bytes = unit_orbit_windows::warm_alt_split_prime_two_x_table()
        + unit_orbit_windows::warm_joint_seed_sets();
    let generator_preparation_ms = generator_start.elapsed().as_secs_f64()*1000.0;
    let plan_load_start = Instant::now();
    let precomputed = plan_path.map(|path| load_graph_plan(path,rows,count));
    let plan_load_ms = if plan_path.is_some() {
        plan_load_start.elapsed().as_secs_f64()*1000.0
    } else { 0.0 };
    let graph_plan_ms = 0.0;
    let target_start = Instant::now();
    let online_choices = if plan_path.is_some() { None } else { Some(inputs.iter().map(|(_,b,_)|
        unit_orbit_windows::joint_choices_for_words(*b)).collect::<Vec<_>>()) };
    let b_choices = if let Some((choices,_)) = precomputed.as_ref() { choices }
        else { online_choices.as_ref().expect("online choices") };
    let (q_table,graph_edges,direct_seeds) = if let Some((_,plan)) = precomputed.as_ref() {
        (unit_orbit_windows::instantiate_joint_q_graph(
            fixture["q_hex"].as_str().expect("Q"),plan),
         plan.graph_edges,plan.direct_seeds)
    } else if graph {
        unit_orbit_windows::prepare_joint_q_sparse_graph(
            fixture["q_hex"].as_str().expect("Q"), b_choices)
    } else {
        (unit_orbit_windows::prepare_joint_q_sparse(
            fixture["q_hex"].as_str().expect("Q"), b_choices),0,0)
    };
    let target_preparation_ms = target_start.elapsed().as_secs_f64()*1000.0;
    let eval_start = Instant::now();
    let (answers,fused_pair_sums) = unit_orbit_windows::multiply_u256_tau_joint_fused_batch(
        &a_words,b_choices,&q_table);
    let restart_eval_ms = eval_start.elapsed().as_secs_f64()*1000.0;
    let online_ms = target_preparation_ms + restart_eval_ms;
    for (index,(actual,(_,_,expected))) in answers.iter().zip(inputs.iter()).enumerate() {
        assert_eq!(actual,expected,"rho fused joint case {index}");
    }
    let plan_bytes = precomputed.as_ref().map(|(choices,plan)|
        plan.retained_bytes + choices.capacity()*std::mem::size_of_val(&choices[0]))
        .unwrap_or(0);
    let retained_bytes = generator_bytes + q_table.retained_bytes + plan_bytes;
    let mode = if plan_path.is_some() { "joint_fused_graph_planned" }
        else if graph { "joint_fused_graph" } else { "joint_fused" };
    println!("verified=1 count={count} online_ms={online_ms:.6} \
              target_preparation_ms={target_preparation_ms:.6} \
              restart_eval_ms={restart_eval_ms:.6} \
              generator_preparation_ms={generator_preparation_ms:.6} \
              graph_plan_ms={graph_plan_ms:.6} plan_load_ms={plan_load_ms:.6} \
              plan_bytes={plan_bytes} \
              retained_bytes={retained_bytes} constructed_q_points={} \
              graph_edges={graph_edges} direct_seeds={direct_seeds} \
              fused_pair_sums={fused_pair_sums} mode={mode} point={}",
              q_table.constructed_points,answers.last().expect("nonempty"));
}
