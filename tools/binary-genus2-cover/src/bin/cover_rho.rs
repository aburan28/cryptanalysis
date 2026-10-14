//! Native campaign driver. Solver commands accept public jobs only.
use binary_genus2_cover::campaign::*;
use binary_genus2_cover::cryptanalysis::ecbench::{host, isolation as iso};
use binary_genus2_cover::Result;
use serde_json::{json, Value};
use std::collections::BTreeMap;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

fn args() -> Result<(String, BTreeMap<String, String>)> {
    let mut args = std::env::args().skip(1);
    let cmd = args
        .next()
        .ok_or("usage: cover_rho generate|calibrate|run|reference|verify|replay [--key value]")?;
    let mut flags = BTreeMap::new();
    while let Some(k) = args.next() {
        if !k.starts_with("--") {
            return Err(format!("expected flag, got {k}"));
        }
        let v = args
            .next()
            .ok_or_else(|| format!("missing value for {k}"))?;
        if flags.insert(k.clone(), v).is_some() {
            return Err(format!("duplicate {k}"));
        }
    }
    Ok((cmd, flags))
}
fn take(f: &mut BTreeMap<String, String>, key: &str) -> Result<String> {
    f.remove(key).ok_or_else(|| format!("missing {key}"))
}
fn done(f: BTreeMap<String, String>) -> Result<()> {
    if f.is_empty() {
        Ok(())
    } else {
        Err(format!("unknown flags: {:?}", f.keys()))
    }
}
fn now() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}
fn append(path: &Path, value: &Value) -> Result<()> {
    let mut f = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| e.to_string())?;
    serde_json::to_writer(&mut f, value).map_err(|e| e.to_string())?;
    f.write_all(b"\n").map_err(|e| e.to_string())?;
    f.sync_data().map_err(|e| e.to_string())
}
struct Reservation {
    _lock: iso::BenchLock,
    _eviction: iso::Eviction,
}
fn reserve(cpu: &str, out: &Path) -> Result<Reservation> {
    let lock = iso::BenchLock::acquire("/tmp/crypto-bench.lock", false)?;
    let plan = iso::plan_cpus(
        &iso::CpuRequest::parse(cpu)?,
        &iso::topology(),
        iso::own_affinity().as_deref(),
    )?
    .ok_or("explicit CPU reservation required")?;
    let eviction = iso::evict(&plan.reserved);
    let preflight = iso::preflight(&plan, &iso::Thresholds::default());
    // SAFETY: this program is single-threaded, and the plan supplies a valid
    // Linux CPU. No memory binding is asserted; observed policy is recorded.
    #[cfg(target_os = "linux")]
    unsafe {
        iso::pin_in_child(plan.run_cpu, None).map_err(|e| e.to_string())?;
    }
    let binary =
        fs::read(std::env::current_exe().map_err(|e| e.to_string())?).map_err(|e| e.to_string())?;
    let manifest = json!({"schema":"cover-rho.host/v1","timestamp_unix":now(),"pid":std::process::id(),
        "host":host::capture()?,"cpu_plan":plan,"preflight":preflight,"eviction":eviction.summary,
        "actual_affinity":iso::own_affinity(),"actual_cpu":iso::current_cpu(),"memory_policy":iso::mempolicy(),
        "mems_allowed":iso::mems_allowed(),"memory_type":null,"isolation_level":"L0",
        "isolation_reason":"exploratory VM campaign; no ecbench session tier certificate or independent host replay",
        "cpu_max":fs::read_to_string("/sys/fs/cgroup/cpu.max").ok(),
        "memory_max":fs::read_to_string("/sys/fs/cgroup/memory.max").ok(),
        "binary_sha256":hex_digest(&binary)});
    atomic_json(out, &manifest)?;
    Ok(Reservation {
        _lock: lock,
        _eviction: eviction,
    })
}
fn checkpoint_path(out: &Path, a: u8, index: u32, arm: &str) -> PathBuf {
    out.join(format!("a{a}-{index}-{arm}.checkpoint.json"))
}
fn load(ctx: &Context, arm: &str, path: &Path) -> Result<Search> {
    let t = Instant::now();
    if path.exists() {
        let mut s: Checkpoint = read_json(path)?;
        s.validate(ctx, arm)?;
        s.resumes += 1;
        let mut search = Search::from_state(ctx, s)?;
        search.state.resume_seconds += t.elapsed().as_secs_f64() + ctx.setup_seconds;
        Ok(search)
    } else {
        Search::from_state(ctx, Checkpoint::new(ctx, arm)?)
    }
}
fn calibrate(job: Job, out: &Path, cpu: &str) -> Result<()> {
    fs::create_dir(out).map_err(|e| e.to_string())?;
    let _guard = reserve(cpu, &out.join("host.json"))?;
    let e = Context::new(job.clone(), false)?;
    let j = Context::new(job, true)?;
    let mut rows = Vec::new();
    // Warmup, A/A repeated controls, then five ordered A B A B rounds.
    let sequence = [
        "warmup", "aa-1", "aa-2", "ab-0-a", "ab-0-b", "ab-1-a", "ab-1-b", "ab-2-a", "ab-2-b",
        "ab-3-a", "ab-3-b", "ab-4-a", "ab-4-b",
    ];
    for label in sequence {
        let jac = label.ends_with("-b");
        let arm = if jac { "jacobian" } else { "elliptic" };
        let ctx = if jac { &j } else { &e };
        let mut search = Search::from_state(ctx, Checkpoint::new(ctx, arm)?)?;
        // Exactly matched trajectory prefix, long enough for native Cantor work.
        let start = Instant::now();
        let hw = iso::HwCounters::open();
        hw.start();
        search.advance(ctx, 32)?;
        let counts = hw.stop();
        let wall = start.elapsed().as_secs_f64();
        let row = json!({"label":label,"arm":arm,"job_sha256":ctx.job.hash()?,"steps":search.state.steps,
            "search_seconds":search.state.search_seconds,"outer_wall_seconds":wall,"counts":search.state.counts,
            "hardware_counters":counts,"lane_digest":hex_digest(&serde_json::to_vec(&search.state.lanes).map_err(|e|e.to_string())?),
            "table_entries":search.state.table.len(),"status":if search.state.candidate.is_some(){"candidate"}else{"calibration_prefix"},
            "isolation_level":"L0","speedup":null});
        append(&out.join("rounds.jsonl"), &row)?;
        rows.push(row);
    }
    let digits: Vec<_> = rows
        .iter()
        .filter(|r| r["label"] != "warmup")
        .map(|r| r["lane_digest"].clone())
        .collect();
    if digits.windows(2).any(|w| w[0] != w[1]) {
        return Err("matched trajectory diverged".into());
    }
    atomic_json(
        &out.join("summary.json"),
        &json!({"schema":"cover-rho.calibration/v1","matched_lanes":true,
        "rows":rows,"common_priced_work":null,"speedup":null,"completed_full_subgroup_solves":0}),
    )
}
fn replay(job: Job, out: &Path) -> Result<()> {
    fs::create_dir(out).map_err(|e| e.to_string())?;
    let ctx = Context::new(job, true)?;
    let mut receipts = Vec::new();
    for arm in ["elliptic", "jacobian", "image_inverse"] {
        let mut full = Search::from_state(&ctx, Checkpoint::new(&ctx, arm)?)?;
        full.advance(&ctx, 8)?;
        let mut split = Search::from_state(&ctx, Checkpoint::new(&ctx, arm)?)?;
        split.advance(&ctx, 4)?;
        let p = out.join(format!("{arm}.checkpoint.json"));
        split.write(&p)?;
        let mut resumed = Search::from_state(&ctx, read_json(&p)?)?;
        resumed.advance(&ctx, 4)?;
        let a = &full.state;
        let b = &resumed.state;
        if a.steps != b.steps
            || a.lanes != b.lanes
            || a.table != b.table
            || a.counts != b.counts
            || a.candidate != b.candidate
            || a.cursor != b.cursor
            || a.cursor_a != b.cursor_a
        {
            return Err(format!("checkpoint replay mismatch for {arm}"));
        }
        receipts.push(json!({"arm":arm,"steps":a.steps,"identical_walk_state":true,"lane_digest":hex_digest(&serde_json::to_vec(&a.lanes).map_err(|e|e.to_string())?)}));
    }
    atomic_json(
        &out.join("receipt.json"),
        &json!({"schema":"cover-rho.replay/v1","job_sha256":ctx.job.hash()?,"results":receipts}),
    )
}
fn run(public: &Path, out: &Path, cpu: &str) -> Result<()> {
    fs::create_dir_all(out).map_err(|e| e.to_string())?;
    let host_path = out.join(format!("host-{}-{}.json", now(), std::process::id()));
    let _guard = reserve(cpu, &host_path)?;
    let mut workers = Vec::new();
    for a in [1, 0] {
        for arm in ["elliptic", "image_inverse", "jacobian"] {
            let mut index = 0;
            while index < 7
                && out
                    .join(format!("a{a}-{index}-{arm}.verification.json"))
                    .exists()
            {
                index += 1;
            }
            let job: Job = read_json(&public.join(format!("a{a}-{index}.json")))?;
            let ctx = Context::new(job, arm == "jacobian")?;
            let p = checkpoint_path(out, a, index, arm);
            let mut search = load(&ctx, arm, &p)?;
            search.write(&p)?;
            workers.push((ctx, search, p, false, Instant::now()));
        }
    }
    atomic_json(
        &out.join("active.json"),
        &json!({"schema":"cover-rho.active/v1","pid":std::process::id(),"started_unix":now(),"host":host_path,
        "public_directory":public,"status":"running","initial_targets_per_curve":1,"queued_targets_per_curve":7,
        "pause_file":out.join("PAUSE"),"stop_file":out.join("STOP"),"no_total_step_limit":true}),
    )?;
    loop {
        if out.join("STOP").exists() {
            break;
        }
        if out.join("PAUSE").exists() {
            for (_, search, path, _, _) in &mut workers {
                search.write(path)?;
            }
            atomic_json(
                &out.join("paused.json"),
                &json!({"pid":std::process::id(),"timestamp_unix":now(),"status":"paused_with_checkpoints"}),
            )?;
            while out.join("PAUSE").exists() && !out.join("STOP").exists() {
                std::thread::sleep(Duration::from_secs(1));
            }
            fs::remove_file(out.join("paused.json")).map_err(|e| e.to_string())?;
            continue;
        }
        let mut unfinished = false;
        for (ctx, search, path, complete, last_checkpoint) in &mut workers {
            if out.join("STOP").exists() || out.join("PAUSE").exists() {
                break;
            }
            if *complete {
                continue;
            }
            unfinished = true;
            let old = search.state.steps;
            let before = iso::conditions(&[iso::current_cpu().unwrap_or(0)]);
            let budget = if search.state.rounds > 0 && search.state.search_seconds > 0. {
                (2. * search.state.rounds as f64 / search.state.search_seconds).clamp(1., 200_000.)
                    as u64
            } else if search.state.arm == "jacobian" {
                4
            } else {
                2048
            };
            let hw = iso::HwCounters::open();
            hw.start();
            if search.state.candidate.is_none() {
                search.advance(ctx, budget)?;
            }
            let hardware = hw.stop();
            if last_checkpoint.elapsed().as_secs() >= 60 || search.state.candidate.is_some() {
                search.write(path)?;
                *last_checkpoint = Instant::now();
            }
            let row = json!({"timestamp_unix":now(),"a":ctx.job.a,"index":ctx.job.index,"arm":search.state.arm,
                "steps":search.state.steps,"rounds":search.state.rounds,"budget_rounds":budget,"segment_steps":search.state.steps-old,"walks":search.state.walks,"table_entries":search.state.table.len(),
                "search_seconds":search.state.search_seconds,"setup_seconds":search.state.setup_seconds,"checkpoint_seconds":search.state.checkpoint_seconds,
                "counts":search.state.counts,"candidate":search.state.candidate.map(|k|k.to_string()),"hardware_counters":hardware,
                "conditions_before":before,"conditions_after":iso::conditions(&[iso::current_cpu().unwrap_or(0)]),
                "rss_status":fs::read_to_string("/proc/self/status").ok().and_then(|s|s.lines().find(|l|l.starts_with("VmRSS:")).map(str::to_owned)),
                "anonymous_pages_by_numa_node":iso::anon_pages_by_node(),"isolation_level":"L0","speedup":null});
            append(&out.join("progress.jsonl"), &row)?;
            println!("{}", row);
            if search.state.candidate.is_some() {
                // The parent solver process never receives the held-out witness.
                // Verification runs through an independent CLI invocation.
                let result = out.join(format!(
                    "a{}-{}-{}.candidate.json",
                    ctx.job.a, ctx.job.index, search.state.arm
                ));
                atomic_json(
                    &result,
                    &json!({"job_sha256":ctx.job.hash()?,"scalar":search.state.candidate.unwrap().to_string()}),
                )?;
                let verification = out.join(format!(
                    "a{}-{}-{}.verification.json",
                    ctx.job.a, ctx.job.index, search.state.arm
                ));
                let status =
                    std::process::Command::new(std::env::current_exe().map_err(|e| e.to_string())?)
                        .arg("verify")
                        .arg("--job")
                        .arg(public.join(format!("a{}-{}.json", ctx.job.a, ctx.job.index)))
                        .arg("--result")
                        .arg(&result)
                        .arg("--out")
                        .arg(&verification)
                        .status()
                        .map_err(|e| e.to_string())?;
                if !status.success() {
                    return Err(format!("external verification failed: {status}"));
                }
                append(
                    &out.join("completed.jsonl"),
                    &json!({"a":ctx.job.a,"index":ctx.job.index,"arm":search.state.arm,
                    "candidate":result,"verification":verification,"checkpoint":path,"timestamp_unix":now()}),
                )?;
                let arm = search.state.arm.clone();
                let next = ctx.job.index + 1;
                if next == 8 {
                    *complete = true;
                } else {
                    let job = read_json(&public.join(format!("a{}-{next}.json", ctx.job.a)))?;
                    *ctx = Context::new(job, arm == "jacobian")?;
                    *path = checkpoint_path(out, ctx.job.a, next, &arm);
                    *search = load(ctx, &arm, path)?;
                    search.write(path)?;
                    *last_checkpoint = Instant::now();
                }
            }
        }
        if !unfinished {
            break;
        }
    }
    for (_, search, path, _, _) in &mut workers {
        search.write(path)?;
    }
    atomic_json(
        &out.join("stopped.json"),
        &json!({"timestamp_unix":now(),"pid":std::process::id(),"status":if out.join("STOP").exists(){"user_stop"}else{"all_targets_verified"}}),
    )
}
fn main_result() -> Result<()> {
    let (cmd, mut f) = args()?;
    match cmd.as_str() {
        "reference-suite" => {
            let public = PathBuf::from(take(&mut f, "--public")?);
            let out = PathBuf::from(take(&mut f, "--out")?);
            let cpu = f.remove("--cpu").unwrap_or_else(|| "4".into());
            done(f)?;
            fs::create_dir_all(&out).map_err(|e| e.to_string())?;
            let mut schedule = vec![
                (0, "warmup", "elliptic"),
                (0, "aa-1", "elliptic"),
                (0, "aa-2", "elliptic"),
            ];
            for round in ["ab-0", "ab-1", "ab-2", "ab-3", "ab-4"] {
                schedule.push((0, round, "elliptic"));
                schedule.push((0, round, "image_inverse"));
            }
            for index in 1..8 {
                schedule.push((index, "target", "elliptic"));
                schedule.push((index, "target", "image_inverse"));
            }
            for (index, label, arm) in schedule {
                let dest = out.join(format!("reference-a1-{index}-{label}-{arm}"));
                if dest.join("verification.json").exists() {
                    continue;
                }
                if dest.exists() {
                    return Err(format!(
                        "incomplete existing reference directory {}",
                        dest.display()
                    ));
                }
                let job = public.join(format!("a1-{index}.json"));
                let exe = std::env::current_exe().map_err(|e| e.to_string())?;
                let t = Instant::now();
                let status = std::process::Command::new(&exe)
                    .arg("reference")
                    .arg("--job")
                    .arg(&job)
                    .arg("--out")
                    .arg(&dest)
                    .arg("--cpu")
                    .arg(&cpu)
                    .arg("--arm")
                    .arg(arm)
                    .status()
                    .map_err(|e| e.to_string())?;
                if !status.success() {
                    return Err(format!("reference process failed: {status}"));
                }
                let reference_process_wall = t.elapsed().as_secs_f64();
                let t = Instant::now();
                let status = std::process::Command::new(&exe)
                    .arg("verify")
                    .arg("--job")
                    .arg(&job)
                    .arg("--result")
                    .arg(dest.join("result.json"))
                    .arg("--out")
                    .arg(dest.join("verification.json"))
                    .status()
                    .map_err(|e| e.to_string())?;
                if !status.success() {
                    return Err(format!("reference verification failed: {status}"));
                }
                atomic_json(
                    &dest.join("process-times.json"),
                    &json!({"reference_process_wall_seconds":reference_process_wall,
                    "verification_process_wall_seconds":t.elapsed().as_secs_f64(),"reference_process_includes_host_and_preflight":true}),
                )?;
                println!("verified a=1 target={index} label={label} arm={arm}");
            }
            Ok(())
        }
        "generate" => {
            let p = take(&mut f, "--public")?;
            let w = take(&mut f, "--witness")?;
            done(f)?;
            generate(Path::new(&p), Path::new(&w))
        }
        "calibrate" | "reference" | "replay" => {
            let j = take(&mut f, "--job")?;
            let o = take(&mut f, "--out")?;
            let cpu = f.remove("--cpu").unwrap_or_else(|| "4".into());
            let arm = f.remove("--arm").unwrap_or_else(|| "elliptic".into());
            if arm != "elliptic" && arm != "image_inverse" {
                return Err("reference arm must be elliptic or image_inverse".into());
            }
            if cmd != "reference" && arm != "elliptic" {
                return Err("--arm only applies to reference".into());
            }
            done(f)?;
            let job = read_json(Path::new(&j))?;
            if cmd == "calibrate" {
                calibrate(job, Path::new(&o), &cpu)
            } else if cmd == "replay" {
                replay(job, Path::new(&o))
            } else {
                fs::create_dir(&o).map_err(|e| e.to_string())?;
                let _guard = reserve(&cpu, &Path::new(&o).join("host.json"))?;
                let ctx = Context::new(job, false)?;
                let transfer_start = Instant::now();
                if arm == "image_inverse" {
                    for p in [ctx.job.generator, ctx.job.target] {
                        let divisor = ctx.cover.pullback(&p.binary())?;
                        if ctx.cover.inverse_on_image(&divisor)? != p.binary() {
                            return Err("reference image inverse failed".into());
                        }
                    }
                }
                let transfer_seconds = transfer_start.elapsed().as_secs_f64();
                let mut report = strong_reference(&ctx)?;
                report["arm"] = json!(arm);
                report["transfer_seconds"] = json!(transfer_seconds);
                report["transfer_counts"] = if arm == "image_inverse" {
                    json!({"pullbacks":2,"checked_image_inverses":2})
                } else {
                    json!({})
                };
                report["isolation_level"] = json!("L0");
                atomic_json(&Path::new(&o).join("result.json"), &report)
            }
        }
        "verify" => {
            let j = take(&mut f, "--job")?;
            let r = take(&mut f, "--result")?;
            let o = take(&mut f, "--out")?;
            done(f)?;
            let ctx = Context::new(read_json(Path::new(&j))?, false)?;
            let v: Value = read_json(Path::new(&r))?;
            if v["job_sha256"].as_str() != Some(&ctx.job.hash()?) {
                return Err("result job hash mismatch".into());
            }
            let k = v["scalar"]
                .as_str()
                .ok_or("missing scalar")?
                .parse::<u128>()
                .map_err(|e| e.to_string())?;
            atomic_json(Path::new(&o), &ctx.verify(k)?)
        }
        "run" => {
            let p = take(&mut f, "--public")?;
            let o = take(&mut f, "--out")?;
            let cpu = f.remove("--cpu").unwrap_or_else(|| "4".into());
            done(f)?;
            run(Path::new(&p), Path::new(&o), &cpu)
        }
        _ => Err(format!("unknown command {cmd}")),
    }
}
fn main() {
    if let Err(e) = main_result() {
        eprintln!("cover_rho: {e}");
        std::process::exit(1);
    }
}
