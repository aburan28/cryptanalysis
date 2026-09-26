//! The measurement core of `perfbench`: a registry of fixed-input kernels,
//! each returning a fingerprint of its output, timed one run at a time.
//!
//! A kernel is a [`Workload`] built by an untimed `setup`.  Each sample
//! calls [`Workload::prepare`] (untimed, for kernels that consume their
//! input, such as an in-place elimination) and then [`Workload::run`]
//! (timed).  `run` must do the same work every call and return a
//! fingerprint of what it computed; the harness refuses a kernel whose
//! fingerprint changes between samples, and `scripts/perf/perfindex.py`
//! refuses a comparison whose baseline and candidate fingerprints differ,
//! because a faster run that computes something else is not a speedup.
//!
//! Output is one JSON object per kernel on stdout, so the runner can
//! alternate baseline and candidate binaries kernel by kernel.

#![allow(dead_code)] // helpers are shared by kernels that may not use all of them

use std::hint::black_box;
use std::time::{Duration, Instant};

/// A timed unit of work with fixed inputs.
pub trait Workload {
    /// Untimed per-sample preparation (restore consumed inputs).
    fn prepare(&mut self) {}
    /// The timed work.  Returns a fingerprint of everything it computed.
    fn run(&mut self) -> u64;
}

/// A workload from a closure that needs no per-sample preparation.
pub struct Closure<F: FnMut() -> u64>(pub F);

impl<F: FnMut() -> u64> Workload for Closure<F> {
    fn run(&mut self) -> u64 {
        (self.0)()
    }
}

/// A workload that clones a pristine input before every sample (untimed)
/// and hands the copy to the timed body.
pub struct Fresh<T: Clone, F: FnMut(&mut T) -> u64> {
    pristine: T,
    work: Option<T>,
    body: F,
}

impl<T: Clone, F: FnMut(&mut T) -> u64> Fresh<T, F> {
    pub fn new(input: T, body: F) -> Self {
        Fresh {
            pristine: input,
            work: None,
            body,
        }
    }
}

impl<T: Clone, F: FnMut(&mut T) -> u64> Workload for Fresh<T, F> {
    fn prepare(&mut self) {
        self.work = Some(self.pristine.clone());
    }
    fn run(&mut self) -> u64 {
        let work = self.work.as_mut().expect("prepare runs before run");
        (self.body)(work)
    }
}

/// Which runs include a kernel.  `Quick` kernels form the default index;
/// `Full` adds the slower cells.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Tier {
    Quick,
    Full,
}

/// One registered kernel.
pub struct Kernel {
    /// Stable identifier, `area/name`.  Never reuse an ID for different
    /// work: the index pairs baseline and candidate by ID.
    pub id: &'static str,
    /// The area weight group (see `docs/perf/PERFORMANCE_INDEX.md`).
    pub area: &'static str,
    /// What one run computes, in one line.
    pub desc: &'static str,
    pub tier: Tier,
    /// Builds the inputs (untimed) and returns the workload.
    pub setup: fn() -> Box<dyn Workload>,
}

/// FNV-1a over 64-bit words with a final avalanche: a fingerprint that
/// is stable across Rust versions and platforms (unlike `DefaultHasher`).
#[derive(Clone, Copy, Debug)]
pub struct Fp(u64);

impl Default for Fp {
    fn default() -> Self {
        Fp::new()
    }
}

impl Fp {
    pub const fn new() -> Self {
        Fp(0xcbf2_9ce4_8422_2325)
    }
    #[inline]
    pub fn u64(mut self, x: u64) -> Self {
        for b in x.to_le_bytes() {
            self.0 ^= b as u64;
            self.0 = self.0.wrapping_mul(0x0000_0100_0000_01b3);
        }
        self
    }
    pub fn u128(self, x: u128) -> Self {
        self.u64(x as u64).u64((x >> 64) as u64)
    }
    pub fn usize(self, x: usize) -> Self {
        self.u64(x as u64)
    }
    pub fn bool(self, x: bool) -> Self {
        self.u64(x as u64)
    }
    pub fn words(mut self, xs: &[u64]) -> Self {
        self = self.usize(xs.len());
        for &x in xs {
            self = self.u64(x);
        }
        self
    }
    pub fn bytes(mut self, xs: &[u8]) -> Self {
        self = self.usize(xs.len());
        for &b in xs {
            self.0 ^= b as u64;
            self.0 = self.0.wrapping_mul(0x0000_0100_0000_01b3);
        }
        self
    }
    pub fn str(self, s: &str) -> Self {
        self.bytes(s.as_bytes())
    }
    pub fn finish(self) -> u64 {
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
        z ^ (z >> 31)
    }
}

/// Carries the workload into `ThreadPool::install`, which demands `Send`.
struct OnThisThread<'a>(&'a mut Box<dyn Workload>);

impl<'a> OnThisThread<'a> {
    // A method, so the closure captures the whole wrapper and not the
    // non-`Send` field alone (edition 2021 disjoint capture).
    fn into_inner(self) -> &'a mut Box<dyn Workload> {
        self.0
    }
}

// SAFETY: the pool is built with `use_current_thread`, so `install` called
// from this thread runs its closure inline on this thread; the workload
// never leaves the thread that owns it.
unsafe impl Send for OnThisThread<'_> {}

/// The region `perfindex.py instr` restricts callgrind to
/// (`--toggle-collect=*perfbench_measured_region*`).
#[inline(never)]
pub fn perfbench_measured_region(w: &mut dyn Workload) -> u64 {
    black_box(w.run())
}

struct Options {
    filters: Vec<String>,
    exact: bool,
    full: bool,
    samples: usize,
    min_samples: usize,
    max_seconds: f64,
    warmup_seconds: f64,
    instr: bool,
}

fn parse_options(args: &[String]) -> Options {
    let mut o = Options {
        filters: Vec::new(),
        exact: false,
        full: false,
        samples: 11,
        min_samples: 3,
        max_seconds: 3.0,
        warmup_seconds: 0.2,
        instr: false,
    };
    let mut i = 0;
    let value = |i: &mut usize| -> String {
        *i += 1;
        args.get(*i)
            .cloned()
            .unwrap_or_else(|| panic!("missing value after {}", args[*i - 1]))
    };
    while i < args.len() {
        match args[i].as_str() {
            "--filter" => o
                .filters
                .extend(value(&mut i).split(',').map(str::to_string)),
            "--exact" => o.exact = true,
            "--full" => o.full = true,
            "--samples" => o.samples = value(&mut i).parse().expect("--samples N"),
            "--min-samples" => o.min_samples = value(&mut i).parse().expect("--min-samples N"),
            "--max-seconds" => o.max_seconds = value(&mut i).parse().expect("--max-seconds S"),
            "--warmup-seconds" => {
                o.warmup_seconds = value(&mut i).parse().expect("--warmup-seconds S")
            }
            "--instr" => o.instr = true,
            other => panic!("unknown option {other}"),
        }
        i += 1;
    }
    o
}

fn selected<'a>(kernels: &'a [Kernel], o: &Options) -> Vec<&'a Kernel> {
    kernels
        .iter()
        .filter(|k| o.full || k.tier == Tier::Quick || !o.filters.is_empty())
        .filter(|k| {
            o.filters.is_empty()
                || o.filters.iter().any(|f| {
                    if o.exact {
                        k.id == f
                    } else {
                        k.id.contains(f.as_str())
                    }
                })
        })
        .collect()
}

fn json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

fn median(xs: &mut [u64]) -> u64 {
    xs.sort_unstable();
    let n = xs.len();
    if n % 2 == 1 {
        xs[n / 2]
    } else {
        (xs[n / 2 - 1] + xs[n / 2]) / 2
    }
}

fn measure(k: &Kernel, o: &Options) {
    let setup_start = Instant::now();
    let mut w = (k.setup)();
    let setup_ns = setup_start.elapsed().as_nanos() as u64;

    if o.instr {
        // One warm run outside the region, one measured run inside it, both
        // on a one-thread rayon pool whose only worker is this thread: work a
        // kernel hands to rayon then runs inline under
        // `perfbench_measured_region`, where callgrind counts it, instead of
        // on a pool worker whose stack never enters the region.
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(1)
            .use_current_thread()
            .build()
            .expect("one-thread rayon pool");
        let job = OnThisThread(&mut w);
        let (fp0, fp) = pool.install(move || {
            let w = job.into_inner();
            w.prepare();
            let fp0 = black_box(w.run());
            w.prepare();
            (fp0, perfbench_measured_region(w.as_mut()))
        });
        drop(pool);
        assert_eq!(fp0, fp, "{}: fingerprint changed between runs", k.id);
        println!(
            "{{\"id\":{},\"area\":{},\"fingerprint\":\"{:016x}\",\"setup_ns\":{}}}",
            json_str(k.id),
            json_str(k.area),
            fp,
            setup_ns
        );
        return;
    }

    // Warm-up: at least one run, until `warmup_seconds` has passed.
    let warm_start = Instant::now();
    w.prepare();
    let fp = black_box(w.run());
    while warm_start.elapsed().as_secs_f64() < o.warmup_seconds {
        w.prepare();
        let again = black_box(w.run());
        assert_eq!(fp, again, "{}: fingerprint changed between runs", k.id);
    }

    let budget = Duration::from_secs_f64(o.max_seconds);
    let start = Instant::now();
    let mut samples = Vec::with_capacity(o.samples);
    while samples.len() < o.samples && (samples.len() < o.min_samples || start.elapsed() < budget) {
        w.prepare();
        let t = Instant::now();
        let got = black_box(w.run());
        let ns = t.elapsed().as_nanos() as u64;
        assert_eq!(fp, got, "{}: fingerprint changed between runs", k.id);
        samples.push(ns);
    }
    let list = samples
        .iter()
        .map(u64::to_string)
        .collect::<Vec<_>>()
        .join(",");
    let min = *samples.iter().min().unwrap();
    let med = median(&mut samples.clone());
    println!(
        "{{\"id\":{},\"area\":{},\"fingerprint\":\"{:016x}\",\"setup_ns\":{},\"median_ns\":{},\"min_ns\":{},\"samples_ns\":[{}]}}",
        json_str(k.id),
        json_str(k.area),
        fp,
        setup_ns,
        med,
        min,
        list
    );
}

const USAGE: &str = "\
perfbench — fixed-input kernels for the performance index

USAGE:
  perfbench list [--full]
  perfbench run  [--filter A,B] [--exact] [--full] [--samples N] [--min-samples N]
                 [--max-seconds S] [--warmup-seconds S] [--instr]

Kernels run on the rayon pool as configured by RAYON_NUM_THREADS; the index
runner sets it explicitly.  Compare builds with scripts/perf/perfindex.py.";

pub fn main(kernels: Vec<Kernel>) {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let mut ids = std::collections::HashSet::new();
    for k in &kernels {
        assert!(ids.insert(k.id), "duplicate kernel id {}", k.id);
        assert!(
            k.id.starts_with(k.area) && k.id[k.area.len()..].starts_with('/'),
            "kernel id {} must start with its area {}/",
            k.id,
            k.area
        );
    }
    match args.first().map(String::as_str) {
        Some("list") => {
            let o = parse_options(&args[1..]);
            for k in selected(&kernels, &o) {
                println!(
                    "{{\"id\":{},\"area\":{},\"tier\":\"{:?}\",\"desc\":{}}}",
                    json_str(k.id),
                    json_str(k.area),
                    k.tier,
                    json_str(k.desc)
                );
            }
        }
        Some("run") => {
            let o = parse_options(&args[1..]);
            let chosen = selected(&kernels, &o);
            if chosen.is_empty() {
                eprintln!("no kernel matches");
                std::process::exit(2);
            }
            for k in chosen {
                measure(k, &o);
            }
        }
        _ => {
            eprintln!("{USAGE}");
            std::process::exit(2);
        }
    }
}
