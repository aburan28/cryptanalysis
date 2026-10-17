// Optional 78-tripling mixed-radix joint scalar path.
pub(super) fn run_mixed78(fixture_path: &str, count: usize) {
    let fixture: Value = serde_json::from_str(
        &std::fs::read_to_string(fixture_path).expect("read frozen fixture"))
        .expect("parse frozen fixture");
    let rows = fixture["cases"].as_array().expect("cases");
    assert!(count > 0 && count <= rows.len());
    let inputs = rows.iter().take(count).map(|row| {
        let a = BigInt::parse_bytes(row["a_hex"].as_str().expect("a").as_bytes(),16)
            .expect("a hex");
        let b = BigInt::parse_bytes(row["b_hex"].as_str().expect("b").as_bytes(),16)
            .expect("b hex");
        (unit_orbit_windows::mixed78_choices_for_words(
             scalar_words_256(&a).expect("a words")),
         unit_orbit_windows::mixed78_choices_for_words(
             scalar_words_256(&b).expect("b words")),
         row["point_hex"].as_str().expect("expected").to_owned())
    }).collect::<Vec<_>>();
    let g_choices = inputs.iter().map(|(a,_,_)| *a).collect::<Vec<_>>();
    let q_choices = inputs.iter().map(|(_,b,_)| *b).collect::<Vec<_>>();
    let plan_start = Instant::now();
    let g_plan = unit_orbit_windows::compile_triple243_plan(&g_choices);
    let q_plan = unit_orbit_windows::compile_triple243_plan(&q_choices);
    let plan_load_ms = plan_start.elapsed().as_secs_f64()*1000.0;
    let setup_start = Instant::now();
    let generator_hex = format!("{}:{}",super::GENERATOR_X_HEX,super::GENERATOR_Y_HEX);
    let g_table = unit_orbit_windows::prepare_triple243_table(&generator_hex,&g_plan);
    let generator_preparation_ms = setup_start.elapsed().as_secs_f64()*1000.0;
    let target_start = Instant::now();
    let q_table = unit_orbit_windows::prepare_triple243_table(
        fixture["q_hex"].as_str().expect("Q"),&q_plan);
    let target_preparation_ms = target_start.elapsed().as_secs_f64()*1000.0;
    let eval_start = Instant::now();
    let answers = inputs.iter().map(|(a,b,_)|
        unit_orbit_windows::mixed78_joint_point(a,b,&g_table,&q_table))
        .collect::<Vec<_>>();
    let restart_eval_ms = eval_start.elapsed().as_secs_f64()*1000.0;
    for (index,(actual,(_,_,expected))) in answers.iter().zip(inputs.iter()).enumerate() {
        assert_eq!(actual,expected,"mixed78 joint case {index}");
    }
    let online_ms = target_preparation_ms+restart_eval_ms;
    println!("verified=1 count={count} online_ms={online_ms:.6} \
              target_preparation_ms={target_preparation_ms:.6} \
              restart_eval_ms={restart_eval_ms:.6} \
              generator_preparation_ms={generator_preparation_ms:.6} \
              graph_plan_ms=0.000000 plan_load_ms={plan_load_ms:.6} plan_bytes={} \
              g_table_bytes={} q_table_bytes={} \
              constructed_q_points={} graph_edges={} direct_seeds={} \
              steps=16 triplings=78 mode=joint_mixed78 point={}",
              g_plan.retained_bytes+q_plan.retained_bytes,
              g_table.retained_bytes,q_table.retained_bytes,
              q_plan.graph_edges+q_plan.direct_seeds,
              q_plan.graph_edges,q_plan.direct_seeds,
              answers.last().expect("nonempty"));
}
