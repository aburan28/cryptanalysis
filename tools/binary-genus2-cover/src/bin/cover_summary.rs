//! Summarize recorded native campaign values; never execute a search.
use binary_genus2_cover::campaign::{atomic_json, read_json, Checkpoint, Job};
use binary_genus2_cover::Result;
use serde_json::{json, Value};
use std::fs;
use std::path::Path;

fn summarize(root: &Path) -> Result<Value> {
    let mut calibrations = Vec::new();
    for a in 0..=1 {
        let job: Job = read_json(&root.join(format!("public/a{a}-0.json")))?;
        let cal: Value = read_json(&root.join(format!("calibration-a{a}/summary.json")))?;
        let ideal = (std::f64::consts::PI * job.order as f64 / (2. * 166.)).sqrt();
        let mut arms = Vec::new();
        for arm in ["elliptic", "jacobian"] {
            let mut samples = Vec::new();
            for row in cal["rows"].as_array().ok_or("missing calibration rows")? {
                if row["arm"] == arm && row["label"].as_str().is_some_and(|s| s.starts_with("ab-"))
                {
                    let steps = row["steps"].as_u64().ok_or("missing steps")?;
                    let seconds = row["search_seconds"].as_f64().ok_or("missing seconds")?;
                    if seconds <= 0. {
                        return Err("nonpositive recorded duration".into());
                    }
                    samples.push(steps as f64 / seconds);
                }
            }
            if samples.len() != 5 {
                return Err("expected five calibration samples per arm".into());
            }
            samples.sort_by(f64::total_cmp);
            arms.push(json!({"arm":arm,"n":samples.len(),"median_steps_per_second":samples[2],"min_steps_per_second":samples[0],"max_steps_per_second":samples[4],
                "heuristic_ideal_steps_divided_by_median_rate_seconds":ideal/samples[2],
                "estimate_label":"birthday scale / short-prefix rate; not a completed solve time or a calibrated runtime prediction",
                "source":format!("calibration-a{a}/summary.json"),"isolation_level":"L0","speedup":null}));
        }
        calibrations.push(json!({"a":a,"order":job.order.to_string(),"automorphisms":166,"ideal_birthday_steps":ideal,"arms":arms}));
    }
    let mut references = Vec::new();
    let mut progress = Vec::new();
    for entry in fs::read_dir(root).map_err(|e| e.to_string())? {
        let entry = entry.map_err(|e| e.to_string())?;
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.starts_with("reference-") && entry.path().is_dir() {
            let p = entry.path().join("result.json");
            if p.exists() {
                let result: Value = read_json(&p)?;
                let verification = entry.path().join("verification.json");
                references.push(json!({"directory":name,"result":result,"verification":if verification.exists(){read_json::<Value>(&verification)?}else{Value::Null}}));
            }
        }
    }
    let campaign = root.join("campaign");
    if campaign.exists() {
        for entry in fs::read_dir(&campaign).map_err(|e| e.to_string())? {
            let e = entry.map_err(|e| e.to_string())?;
            if e.file_name()
                .to_string_lossy()
                .ends_with(".checkpoint.json")
            {
                let s: Checkpoint = read_json(&e.path())?;
                progress.push(json!({"checkpoint":e.file_name().to_string_lossy(),"arm":s.arm,"job_sha256":s.job_sha256,"steps":s.steps,"rounds":s.rounds,
                    "search_seconds":s.search_seconds,"setup_seconds":s.setup_seconds,"setup_counts":s.setup_counts,
                    "checkpoint_seconds_through_previous_write":s.checkpoint_seconds,"resume_seconds":s.resume_seconds,
                    "counts":s.counts,"table_entries":s.table.len(),"candidate":s.candidate.map(|k|k.to_string())}));
            }
        }
    }
    references.sort_by_key(|r| r["directory"].as_str().unwrap().to_owned());
    progress.sort_by_key(|r| r["checkpoint"].as_str().unwrap().to_owned());
    Ok(
        json!({"schema":"cover-rho.snapshot/v1","calibration":calibrations,"references":references,"checkpoint_snapshots":progress,
        "calibration_is_completed_solve":false,"common_priced_work":null,"speedup":null,"independent_host_replay":false,"ecbench_audit":null}),
    )
}
fn main() {
    let args: Vec<_> = std::env::args().skip(1).collect();
    let result = if args.len() == 2 {
        summarize(Path::new(&args[0])).and_then(|s| atomic_json(Path::new(&args[1]), &s))
    } else {
        Err("usage: cover_summary RUN_ROOT OUTPUT_JSON".into())
    };
    if let Err(e) = result {
        eprintln!("cover_summary: {e}");
        std::process::exit(1);
    }
}
