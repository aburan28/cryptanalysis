//! Fixed-parameter wide-field workflow through the existing Python ONB engine.
use clap::Args;
use serde_json::Value;
use std::{
    path::PathBuf,
    process::{Command, Stdio},
};

#[derive(Args, Clone)]
pub struct FixedArgs {
    /// Fixed K_0 parameters and target coordinates, including the field basis.
    #[arg(long)]
    pub params: PathBuf,
    /// Durable campaign directory. Rerun with the same parameters to resume.
    #[arg(long)]
    pub dir: PathBuf,
    /// Stage; all also attempts target-specific relations when base logs are incomplete.
    #[arg(long, default_value = "all", value_parser = ["select", "pairs", "collect", "logs", "solve", "all", "status"])]
    pub stage: String,
    /// Exact pair table, bounded SAT, or an opt-in learned policy with pair fallback.
    #[arg(long, default_value = "pairs", value_parser = ["pairs", "sat", "learned"])]
    pub solver: String,
    /// JSON selector trained with indexcalc_selector.py; required for learned.
    #[arg(long)]
    pub selector_model: Option<PathBuf>,
    /// Additional probes per collection stream or target in this invocation.
    #[arg(long, default_value_t = 32)]
    pub attempts: u32,
    /// Maximum new pair candidates built in this invocation.
    #[arg(long, default_value_t = 10000)]
    pub pair_budget: u64,
    /// Native SAT solve budget; a separate watchdog bounds each complete SAT query.
    #[arg(long, default_value_t = 0.25)]
    pub query_seconds: f64,
    /// Python interpreter; python-sat and pycryptosat are needed only for SAT.
    #[arg(long, default_value = "python3")]
    pub python: PathBuf,
}

pub fn run(args: FixedArgs) -> Result<Value, String> {
    let script =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("python/indexcalc/indexcalc_fixed.py");
    if !script.is_file() {
        return Err(format!(
            "fixed workflow engine is missing: {}",
            script.display()
        ));
    }
    let mut command = Command::new(&args.python);
    command.arg(script);
    if let Some(model) = &args.selector_model {
        command.arg("--selector-model").arg(model);
    }
    let result = command
        .arg("--params")
        .arg(&args.params)
        .arg("--dir")
        .arg(&args.dir)
        .arg("--stage")
        .arg(&args.stage)
        .arg("--solver")
        .arg(&args.solver)
        .arg("--attempts")
        .arg(args.attempts.to_string())
        .arg("--pair-budget")
        .arg(args.pair_budget.to_string())
        .arg("--query-seconds")
        .arg(args.query_seconds.to_string())
        .stdin(Stdio::null())
        .stderr(Stdio::inherit())
        .output()
        .map_err(|e| {
            format!(
                "could not run fixed workflow with {}: {e}",
                args.python.display()
            )
        })?;
    let report: Value = serde_json::from_slice(&result.stdout).map_err(|e| {
        format!(
            "fixed workflow exited {} without a valid JSON report: {e}",
            result.status
        )
    })?;
    if report["operation"] != "fixed" {
        return Err("fixed workflow returned an unexpected report".into());
    }
    if !result.status.success() && matches!(report["status"].as_str(), Some("complete" | "stopped"))
    {
        return Err(format!(
            "fixed workflow reported success but exited {}",
            result.status
        ));
    }
    Ok(report)
}
