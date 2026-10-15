//! The host capsule: what the machine was, so a number keeps its host.
//!
//! Facts split two ways, as `docs/ic/measurement/README.md` §6 splits
//! them.  **Stable** facts (CPU model and features, topology, NUMA,
//! frequency policy, SMT, kernel, virtualisation, toolchain) are hashed
//! into `env_class_id`; two wall-clock arms must share it.  **Volatile**
//! facts (load, PSI, ticks) are sampled around every run by the runner
//! and never hashed.  Build provenance (the binary's hash, the commit)
//! is recorded beside the class but not in it: a baseline and a
//! candidate are different binaries on the same host class.
//!
//! The class id here is `ECBENV2h…` (`ECBENV1h…` for capsules captured
//! before version 2, which still recompute under their own definition),
//! not ICMS's `ENV1h…`: the two hash different fact sets, and a shared
//! prefix would invite a join that means nothing.

use std::collections::BTreeMap;
use std::process::Command;

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::cryptanalysis::ecbench::canonical::{sha256_hex, short_id};
use crate::cryptanalysis::ecbench::isolation::{topology, CpuSettings, Topology};

/// One performance level of a heterogeneous CPU (Apple's P and E
/// cores), from `hw.perflevelN.*`.
#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct PerfLevel {
    pub name: String,
    pub physical: Option<u32>,
    pub logical: Option<u32>,
}

/// Facts that do not change between two runs on one machine.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct StableFacts {
    pub os: String,
    pub arch: String,
    pub kernel_release: Option<String>,
    pub cpu_vendor: Option<String>,
    pub cpu_model: Option<String>,
    /// `family/model/stepping` on x86.
    pub cpu_signature: Option<String>,
    pub microcode: Option<String>,
    /// Features AGENTS.md §10 names, detected at run time.
    pub features: Vec<String>,
    /// SHA-256 of the full sorted flag list (`/proc/cpuinfo`), Linux only.
    pub flags_sha256: Option<String>,
    /// Online logical CPUs: the topology's count on Linux, whatever this
    /// process may use (`isolcpus`, a cpuset or `taskset` narrow that,
    /// and it is recorded apart as [`HostCapsule::process_affinity`]).
    pub logical_cpus: u32,
    pub physical_cores: Option<u32>,
    pub packages: Option<u32>,
    pub numa_nodes: u32,
    pub topology: Topology,
    /// Heterogeneous cores (macOS): a run cannot choose between them.
    pub perf_levels: Vec<PerfLevel>,
    pub mem_total_kib: Option<u64>,
    /// Frequency policy, SMT, isolation flags per CPU (Linux).
    pub cpu_settings: BTreeMap<u32, CpuSettings>,
    pub transparent_hugepages: Option<String>,
    /// `hypervisor` CPU flag, DMI product, or `kern.hv_vmm_present`.
    pub virtualization: BTreeMap<String, String>,
    /// `rustc -Vv` of the toolchain on PATH.  The binary's own hash is
    /// the stronger fact and sits in [`BuildFacts`].
    pub rustc_vv: Option<String>,
}

/// Where the measured code came from.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct BuildFacts {
    pub binary_path: Option<String>,
    pub binary_sha256: Option<String>,
    pub git_commit: Option<String>,
    /// Whether the selected source tree was dirty, as declared at build time
    /// or observed in the runtime-worktree fallback.
    pub git_dirty: Option<bool>,
    /// How `git_commit` was obtained: a compile-time input or a runtime
    /// worktree fallback used by unbound developer builds.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub git_commit_source: Option<String>,
    /// The worktree found beside the executable at capture time. This is
    /// diagnostic only and never overrides embedded build provenance.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub runtime_git_commit: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub runtime_git_dirty: Option<bool>,
    /// Built with debug assertions: an unoptimised build times nothing.
    pub debug_assertions: bool,
    pub target_os: String,
    pub target_arch: String,
    /// Compiler flags in the environment that change generated code.
    pub build_env: BTreeMap<String, String>,
}

/// The whole capsule.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct HostCapsule {
    pub schema: String,
    pub env_class_id: String,
    pub env_class_sha256: String,
    pub stable: StableFacts,
    pub build: BuildFacts,
    /// The CPUs the capturing process was allowed, when the OS says.  It
    /// depends on how the process was launched, so it is not in the class.
    #[serde(default)]
    pub process_affinity: Option<Vec<u32>>,
    pub captured_unix_ms: u128,
}

/// Stdout of a probe that reports through its exit status as well
/// (`systemd-detect-virt` prints `none` and exits 1 on bare metal).
#[cfg(target_os = "linux")]
fn run_any(cmd: &str, args: &[&str]) -> Option<String> {
    let out = Command::new(cmd).args(args).output().ok()?;
    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
    (!text.is_empty()).then_some(text)
}

fn run(cmd: &str, args: &[&str]) -> Option<String> {
    let out = Command::new(cmd).args(args).output().ok()?;
    out.status
        .success()
        .then(|| String::from_utf8_lossy(&out.stdout).trim().to_string())
}

#[cfg(target_os = "macos")]
fn sysctl(name: &str) -> Option<String> {
    run("sysctl", &["-n", name]).filter(|s| !s.is_empty())
}

fn uname_release() -> Option<String> {
    #[cfg(unix)]
    {
        // SAFETY: uname fills a zeroed struct.
        unsafe {
            let mut u: libc::utsname = std::mem::zeroed();
            if libc::uname(&mut u) == 0 {
                let c = std::ffi::CStr::from_ptr(u.release.as_ptr());
                return Some(c.to_string_lossy().into_owned());
            }
        }
    }
    None
}

/// Features named in AGENTS.md §10, as the running CPU reports them.
pub fn detected_features() -> Vec<String> {
    let mut f: Vec<&str> = Vec::new();
    #[cfg(target_arch = "x86_64")]
    {
        macro_rules! probe {
            ($($name:tt),*) => {$(
                if std::arch::is_x86_feature_detected!($name) { f.push($name); }
            )*};
        }
        probe!(
            "popcnt",
            "sse4.2",
            "avx",
            "avx2",
            "bmi1",
            "bmi2",
            "adx",
            "fma",
            "pclmulqdq",
            "vpclmulqdq",
            "gfni",
            "aes",
            "vaes",
            "sha",
            "avx512f",
            "avx512bw",
            "avx512dq",
            "avx512vl",
            "avx512ifma",
            "avx512vbmi"
        );
    }
    #[cfg(target_arch = "aarch64")]
    {
        macro_rules! probe {
            ($($name:tt),*) => {$(
                if std::arch::is_aarch64_feature_detected!($name) { f.push($name); }
            )*};
        }
        probe!("neon", "aes", "pmull", "sha2", "sha3", "crc", "lse", "dotprod", "sve", "sve2");
    }
    let mut v: Vec<String> = f.into_iter().map(String::from).collect();
    v.sort();
    v
}

#[cfg(target_os = "linux")]
fn cpuinfo() -> BTreeMap<String, String> {
    // First processor's block: model name, vendor, family, model,
    // stepping, microcode, flags.
    let mut out = BTreeMap::new();
    if let Ok(text) = std::fs::read_to_string("/proc/cpuinfo") {
        for line in text.lines() {
            if line.trim().is_empty() && !out.is_empty() {
                break;
            }
            if let Some((k, v)) = line.split_once(':') {
                out.entry(k.trim().to_string())
                    .or_insert_with(|| v.trim().to_string());
            }
        }
    }
    out
}

fn stable_facts() -> StableFacts {
    let topo = topology();
    // The online count, not `available_parallelism`, which follows this
    // process's affinity and would make the class depend on `taskset`.
    let logical = if topo.cpus.is_empty() {
        std::thread::available_parallelism()
            .map(|n| n.get() as u32)
            .unwrap_or(1)
    } else {
        topo.cpus.len() as u32
    };
    let mut virtualization = BTreeMap::new();
    #[allow(unused_mut)]
    let mut perf_levels = Vec::new();
    #[allow(unused_mut)]
    let mut facts = StableFacts {
        os: std::env::consts::OS.into(),
        arch: std::env::consts::ARCH.into(),
        kernel_release: uname_release(),
        cpu_vendor: None,
        cpu_model: None,
        cpu_signature: None,
        microcode: None,
        features: detected_features(),
        flags_sha256: None,
        logical_cpus: logical,
        physical_cores: None,
        packages: None,
        numa_nodes: topo.nodes.len().max(1) as u32,
        topology: topo.clone(),
        perf_levels: Vec::new(),
        mem_total_kib: None,
        cpu_settings: BTreeMap::new(),
        transparent_hugepages: None,
        virtualization: BTreeMap::new(),
        rustc_vv: run("rustc", &["-Vv"]),
    };
    #[cfg(target_os = "linux")]
    {
        let ci = cpuinfo();
        facts.cpu_vendor = ci.get("vendor_id").or(ci.get("CPU implementer")).cloned();
        facts.cpu_model = ci.get("model name").or(ci.get("CPU part")).cloned();
        if let (Some(fam), Some(m), Some(s)) =
            (ci.get("cpu family"), ci.get("model"), ci.get("stepping"))
        {
            facts.cpu_signature = Some(format!("{fam}/{m}/{s}"));
        }
        facts.microcode = ci.get("microcode").cloned();
        if let Some(flags) = ci.get("flags").or(ci.get("Features")) {
            let mut fl: Vec<&str> = flags.split_whitespace().collect();
            fl.sort_unstable();
            if fl.contains(&"hypervisor") {
                virtualization.insert("cpu_flag".into(), "hypervisor".into());
            }
            facts.flags_sha256 = Some(sha256_hex(fl.join(" ").as_bytes()));
        }
        let cores: std::collections::BTreeSet<(Option<u32>, Option<u32>)> =
            topo.cpus.iter().map(|c| (c.package, c.core_id)).collect();
        facts.physical_cores = (!topo.cpus.is_empty()).then_some(cores.len() as u32);
        let pkgs: std::collections::BTreeSet<Option<u32>> =
            topo.cpus.iter().map(|c| c.package).collect();
        facts.packages = (!topo.cpus.is_empty()).then_some(pkgs.len() as u32);
        facts.mem_total_kib = std::fs::read_to_string("/proc/meminfo").ok().and_then(|m| {
            m.lines()
                .find(|l| l.starts_with("MemTotal:"))
                .and_then(|l| l.split_whitespace().nth(1)?.parse().ok())
        });
        facts.cpu_settings = topo
            .cpus
            .iter()
            .map(|c| {
                (
                    c.cpu,
                    crate::cryptanalysis::ecbench::isolation::cpu_settings(c.cpu),
                )
            })
            .collect();
        facts.transparent_hugepages =
            std::fs::read_to_string("/sys/kernel/mm/transparent_hugepage/enabled")
                .ok()
                .map(|s| s.trim().to_string());
        for (k, path) in [
            ("dmi_product", "/sys/class/dmi/id/product_name"),
            ("dmi_vendor", "/sys/class/dmi/id/sys_vendor"),
        ] {
            if let Ok(v) = std::fs::read_to_string(path) {
                virtualization.insert(k.into(), v.trim().into());
            }
        }
        if let Some(v) = run_any("systemd-detect-virt", &["--vm"]) {
            virtualization.insert("systemd_detect_virt_vm".into(), v);
        }
    }
    #[cfg(target_os = "macos")]
    {
        facts.cpu_model = sysctl("machdep.cpu.brand_string");
        facts.cpu_vendor = sysctl("machdep.cpu.vendor");
        facts.physical_cores = sysctl("hw.physicalcpu").and_then(|s| s.parse().ok());
        facts.packages = sysctl("hw.packages").and_then(|s| s.parse().ok());
        facts.mem_total_kib = sysctl("hw.memsize")
            .and_then(|s| s.parse::<u64>().ok())
            .map(|b| b / 1024);
        let levels: u32 = sysctl("hw.nperflevels")
            .and_then(|s| s.parse().ok())
            .unwrap_or(0);
        for l in 0..levels {
            perf_levels.push(PerfLevel {
                name: sysctl(&format!("hw.perflevel{l}.name")).unwrap_or_default(),
                physical: sysctl(&format!("hw.perflevel{l}.physicalcpu"))
                    .and_then(|s| s.parse().ok()),
                logical: sysctl(&format!("hw.perflevel{l}.logicalcpu"))
                    .and_then(|s| s.parse().ok()),
            });
        }
        if let Some(v) = sysctl("kern.hv_vmm_present") {
            virtualization.insert("kern_hv_vmm_present".into(), v);
        }
    }
    facts.virtualization = virtualization;
    facts.perf_levels = perf_levels;
    facts
}

/// Whether the capsule shows a virtual machine.  `None` when nothing
/// said either way, which never passes a bare-metal gate.
pub fn is_virtual(s: &StableFacts) -> Option<bool> {
    if s.virtualization.contains_key("cpu_flag") {
        return Some(true);
    }
    if let Some(v) = s.virtualization.get("systemd_detect_virt_vm") {
        return Some(v != "none");
    }
    if let Some(v) = s.virtualization.get("kern_hv_vmm_present") {
        return Some(v == "1");
    }
    None
}

fn select_git_facts(
    embedded_commit: Option<&str>,
    embedded_dirty: Option<bool>,
    runtime_commit: Option<String>,
    runtime_dirty: Option<bool>,
) -> (Option<String>, Option<bool>, bool) {
    if let Some(commit) = embedded_commit {
        (Some(commit.to_owned()), embedded_dirty, true)
    } else {
        (runtime_commit, runtime_dirty, false)
    }
}

// Keep these probes local to this long-lived module. Frozen-source replay
// materializes historical crate roots together with the current host capsule,
// so adding a new crate-root module as a dependency would make old evidence
// stop compiling.
fn embedded_git_commit() -> Option<&'static str> {
    option_env!("CRYPTO_BUILD_GIT_COMMIT").or(option_env!("GITHUB_SHA"))
}

fn embedded_git_dirty() -> Option<bool> {
    match option_env!("CRYPTO_BUILD_GIT_DIRTY")? {
        "1" | "true" | "TRUE" => Some(true),
        "0" | "false" | "FALSE" => Some(false),
        _ => None,
    }
}

fn embedded_git_source() -> Option<&'static str> {
    if option_env!("CRYPTO_BUILD_GIT_COMMIT").is_some() {
        Some("CRYPTO_BUILD_GIT_COMMIT")
    } else if option_env!("GITHUB_SHA").is_some() {
        Some("GITHUB_SHA")
    } else {
        None
    }
}

fn build_facts() -> BuildFacts {
    let exe = std::env::current_exe().ok();
    let binary_sha256 = exe
        .as_ref()
        .and_then(|p| std::fs::read(p).ok())
        .map(|b| sha256_hex(&b));
    // The commit of the worktree the binary sits in (target/release/…),
    // not of whatever directory the session was started from.
    let repo = exe
        .as_ref()
        .and_then(|p| p.parent())
        .map(|d| d.display().to_string());
    let git = |args: &[&str]| -> Option<String> {
        let dir = repo.as_deref()?;
        let mut full = vec!["-C", dir];
        full.extend_from_slice(args);
        run("git", &full)
    };
    let runtime_git_commit = git(&["rev-parse", "HEAD"]);
    let runtime_git_dirty =
        git(&["status", "--porcelain", "--untracked-files=no"]).map(|s| !s.is_empty());
    let (git_commit, git_dirty, embedded) = select_git_facts(
        embedded_git_commit(),
        embedded_git_dirty(),
        runtime_git_commit.clone(),
        runtime_git_dirty,
    );
    let git_commit_source = if embedded {
        embedded_git_source().map(str::to_owned)
    } else {
        runtime_git_commit
            .as_ref()
            .map(|_| "runtime_worktree".to_owned())
    };
    let build_env = [
        "RUSTFLAGS",
        "CARGO_ENCODED_RUSTFLAGS",
        "CARGO_PROFILE_RELEASE_LTO",
        "CC",
        "CFLAGS",
    ]
    .iter()
    .filter_map(|k| std::env::var(k).ok().map(|v| (k.to_string(), v)))
    .collect();
    BuildFacts {
        binary_path: exe.map(|p| p.display().to_string()),
        binary_sha256,
        git_commit,
        git_dirty,
        git_commit_source,
        runtime_git_commit,
        runtime_git_dirty,
        debug_assertions: cfg!(debug_assertions),
        target_os: std::env::consts::OS.into(),
        target_arch: std::env::consts::ARCH.into(),
        build_env,
    }
}

/// The stable facts that define the class.  Topology enters as its
/// shape (CPU → core, package, node, siblings), settings as values.
/// Version 1 of the class, kept so that `ECBENV1h…` ids recorded before
/// version 2 still recompute.  It hashed each NUMA node's `MemTotal`,
/// which moves between boots of one machine (the kernel's reservations
/// land differently), so one host could get a new class per reboot.
fn class_view_v1(s: &StableFacts) -> Value {
    json!({
        "schema": "ecbench.env_class/v1",
        "os": s.os,
        "arch": s.arch,
        "kernel_release": s.kernel_release,
        "cpu_vendor": s.cpu_vendor,
        "cpu_model": s.cpu_model,
        "cpu_signature": s.cpu_signature,
        "microcode": s.microcode,
        "features": s.features,
        "flags_sha256": s.flags_sha256,
        "logical_cpus": s.logical_cpus,
        "physical_cores": s.physical_cores,
        "packages": s.packages,
        "numa_nodes": s.numa_nodes,
        "topology": serde_json::to_value(&s.topology).unwrap_or(Value::Null),
        "perf_levels": serde_json::to_value(&s.perf_levels).unwrap_or(Value::Null),
        "cpu_settings": serde_json::to_value(&s.cpu_settings).unwrap_or(Value::Null),
        "transparent_hugepages": s.transparent_hugepages,
        "virtualization": s.virtualization,
        "rustc_vv": s.rustc_vv,
    })
}

/// Memory rounded to the nearest GiB: what a machine has, without the
/// few megabytes a boot reserves differently.
fn gib(kib: Option<u64>) -> Option<u64> {
    kib.map(|k| (k + (1 << 19)) >> 20)
}

/// The class, version 2: the topology's shape (CPU to core, package,
/// node and siblings; node to CPUs and distances) and memory in whole
/// GiB, so the class survives a reboot.  Every fact is an integer or a
/// string, so the view hashes as it stands.
fn class_view_v2(s: &StableFacts) -> Value {
    let cpus: Vec<Value> = s
        .topology
        .cpus
        .iter()
        .map(|c| json!([c.cpu, c.core_id, c.package, c.node, c.siblings]))
        .collect();
    let nodes: Vec<Value> = s
        .topology
        .nodes
        .iter()
        .map(|n| json!([n.node, n.cpus, n.distances, gib(n.mem_total_kib)]))
        .collect();
    json!({
        "schema": "ecbench.env_class/v2",
        "os": s.os,
        "arch": s.arch,
        "kernel_release": s.kernel_release,
        "cpu_vendor": s.cpu_vendor,
        "cpu_model": s.cpu_model,
        "cpu_signature": s.cpu_signature,
        "microcode": s.microcode,
        "features": s.features,
        "flags_sha256": s.flags_sha256,
        "logical_cpus": s.logical_cpus,
        "physical_cores": s.physical_cores,
        "packages": s.packages,
        "numa_nodes": s.numa_nodes,
        "cpus": cpus,
        "nodes": nodes,
        "mem_total_gib": gib(s.mem_total_kib),
        "perf_levels": serde_json::to_value(&s.perf_levels).unwrap_or(Value::Null),
        "cpu_settings": serde_json::to_value(&s.cpu_settings).unwrap_or(Value::Null),
        "transparent_hugepages": s.transparent_hugepages,
        "virtualization": s.virtualization,
        "rustc_vv": s.rustc_vv,
    })
}

/// A conservative hardware class for cross-machine replay admission.
/// Unlike the measurement environment class, this excludes the compiler on
/// PATH, kernel release, CPU governor and other settings that can change on
/// the same physical host. Equal classes may still be distinct machines;
/// rejecting those receipts is safer than accepting a local replay.
fn hardware_class_view_v1(s: &StableFacts) -> Value {
    let cpus: Vec<Value> = s
        .topology
        .cpus
        .iter()
        .map(|c| json!([c.cpu, c.core_id, c.package, c.node, c.siblings]))
        .collect();
    let nodes: Vec<Value> = s
        .topology
        .nodes
        .iter()
        .map(|n| json!([n.node, n.cpus, n.distances, gib(n.mem_total_kib)]))
        .collect();
    json!({
        "schema": "ecbench.hardware_class/v1",
        "arch": s.arch,
        "cpu_vendor": s.cpu_vendor,
        "cpu_model": s.cpu_model,
        "cpu_signature": s.cpu_signature,
        "logical_cpus": s.logical_cpus,
        "physical_cores": s.physical_cores,
        "packages": s.packages,
        "numa_nodes": s.numa_nodes,
        "cpus": cpus,
        "nodes": nodes,
        "perf_levels": s.perf_levels,
        "mem_total_gib": gib(s.mem_total_kib),
    })
}

/// Class of the hardware profile, independent of toolchain and OS policy.
/// A different value is necessary, though not by itself sufficient, to
/// establish that an audit ran on another physical machine.
pub fn hardware_class_id(c: &HostCapsule) -> Result<String, String> {
    short_id("ECBHW1", &hardware_class_view_v1(&c.stable)).map(|(id, _)| id)
}

/// Capture the capsule now.
pub fn capture() -> Result<HostCapsule, String> {
    let stable = stable_facts();
    let (env_class_id, env_class_sha256) = short_id("ECBENV2", &class_view_v2(&stable))?;
    Ok(HostCapsule {
        schema: "ecbench.host/v1".into(),
        env_class_id,
        env_class_sha256,
        stable,
        build: build_facts(),
        process_affinity: crate::cryptanalysis::ecbench::isolation::own_affinity(),
        captured_unix_ms: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_millis())
            .unwrap_or(0),
    })
}

/// Recompute the class id from a capsule's stable facts; an audit
/// compares it with the stored one.
pub fn recompute_class(c: &HostCapsule) -> Result<String, String> {
    // Each id recomputes under the definition it was made with.
    if c.env_class_id.starts_with("ECBENV1h") {
        Ok(short_id("ECBENV1", &class_view_v1(&c.stable))?.0)
    } else {
        Ok(short_id("ECBENV2", &class_view_v2(&c.stable))?.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn class_ignores_boot_to_boot_memory_jitter() {
        let mut a = capture().unwrap();
        a.stable.mem_total_kib = Some(16 * 1024 * 1024 - 300_000);
        let mut b = a.clone();
        b.stable.mem_total_kib = Some(16 * 1024 * 1024 - 260_000);
        assert_eq!(
            short_id("ECBENV2", &class_view_v2(&a.stable)).unwrap(),
            short_id("ECBENV2", &class_view_v2(&b.stable)).unwrap()
        );
        b.stable.mem_total_kib = Some(32 * 1024 * 1024);
        assert_ne!(
            short_id("ECBENV2", &class_view_v2(&a.stable)).unwrap(),
            short_id("ECBENV2", &class_view_v2(&b.stable)).unwrap()
        );
    }

    #[test]
    fn capsule_class_is_stable_and_recomputable() {
        let a = capture().unwrap();
        assert!(a.env_class_id.starts_with("ECBENV2h"));
        assert_eq!(recompute_class(&a).unwrap(), a.env_class_id);
        assert!(!a.stable.os.is_empty());
    }

    #[test]
    fn hardware_class_does_not_change_with_toolchain_or_kernel() {
        let a = capture().unwrap();
        let mut b = a.clone();
        b.stable.rustc_vv = Some("another compiler on PATH".into());
        b.stable.kernel_release = Some("another kernel".into());
        assert_ne!(recompute_class(&a).unwrap(), recompute_class(&b).unwrap());
        assert_eq!(
            hardware_class_id(&a).unwrap(),
            hardware_class_id(&b).unwrap()
        );
        b.stable.logical_cpus += 1;
        assert_ne!(
            hardware_class_id(&a).unwrap(),
            hardware_class_id(&b).unwrap()
        );
    }

    #[test]
    fn embedded_commit_wins_over_runtime_worktree() {
        let selected = select_git_facts(
            Some("1111111111111111111111111111111111111111"),
            Some(false),
            Some("2222222222222222222222222222222222222222".into()),
            Some(true),
        );
        assert_eq!(
            selected.0.as_deref(),
            Some("1111111111111111111111111111111111111111")
        );
        assert_eq!(selected.1, Some(false));
        assert!(selected.2);
    }

    #[test]
    fn unbound_build_falls_back_to_runtime_worktree() {
        let selected = select_git_facts(
            None,
            None,
            Some("2222222222222222222222222222222222222222".into()),
            Some(true),
        );
        assert_eq!(
            selected.0.as_deref(),
            Some("2222222222222222222222222222222222222222")
        );
        assert_eq!(selected.1, Some(true));
        assert!(!selected.2);
    }
}
