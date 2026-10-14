//! The Tier 1 paired, alternating timing run of protocol.json.
//!
//! usage: loop_bench <protocol.json> <out.jsonl> [--rounds R] [--keys M] [--workloads a,b]
//!
//! Every override marks the run `"smoke": true`; a smoke run is a script test,
//! never a timing result.  Each pass writes one JSON line with its wall ns,
//! TSC ticks, thread CPU ns, context switches, CPU id and output summary; the
//! summary is checked against the workload's reference (exhaustive, record
//! mode) and a mismatch is written, not dropped.  `lift_scan_2pass` rows
//! time two back-to-back lift_scan passes; their `keys` field is the nominal
//! pass length, so their ns/key is twice lift_scan's in expectation.

use canon_n131_loop::*;
use std::io::Write;
use std::time::Instant;

#[repr(C)]
struct Timespec {
    sec: i64,
    nsec: i64,
}
extern "C" {
    fn clock_gettime(clk: i32, ts: *mut Timespec) -> i32;
    fn getrusage(who: i32, r: *mut [i64; 18]) -> i32;
    fn sched_getcpu() -> i32;
}
fn thread_cpu_ns() -> i64 {
    let mut t = Timespec { sec: 0, nsec: 0 };
    unsafe { clock_gettime(3, &mut t) }; // CLOCK_THREAD_CPUTIME_ID
    t.sec * 1_000_000_000 + t.nsec
}
fn rusage() -> [i64; 18] {
    let mut r = [0i64; 18];
    unsafe { getrusage(1, &mut r) }; // RUSAGE_THREAD
    r
}
fn tsc() -> u64 {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        core::arch::x86_64::_rdtsc()
    }
    #[cfg(not(target_arch = "x86_64"))]
    0
}

fn arg(a: &[String], k: &str) -> Option<String> {
    a.iter().position(|x| x == k).map(|i| a[i + 1].clone())
}

fn main() {
    let a: Vec<String> = std::env::args().collect();
    let text = std::fs::read_to_string(&a[1]).expect("protocol");
    let mut out = std::io::BufWriter::new(std::fs::File::create(&a[2]).expect("out"));
    let p_rounds = json_int(&text, "rounds").expect("rounds") as usize;
    let p_keys = json_int(&text, "keys_per_pass").expect("keys_per_pass") as usize;
    let rounds = arg(&a, "--rounds").map(|s| s.parse().unwrap()).unwrap_or(p_rounds);
    let keys = arg(&a, "--keys").map(|s| s.parse().unwrap()).unwrap_or(p_keys);
    let mut wls = workloads_from_protocol(&text);
    if let Some(list) = arg(&a, "--workloads") {
        let keep: Vec<&str> = list.split(',').collect();
        wls.retain(|w| keep.contains(&w.name.as_str()));
    }
    // Arms 0..6 are the loop symbols; arm 7 is the positive control of protocol
    // v2: the lift_scan symbol run twice back to back inside one timed interval,
    // a known 2x effect the paired analysis must resolve.
    const BENCH_ARMS: [&str; 8] = ["null", "exhaustive", "gap_scan", "refine_bf", "exhaustive_bf",
                                   "lift_scan", "lift_scan_aa", "lift_scan_2pass"];
    let na = BENCH_ARMS.len();
    let smoke = rounds != p_rounds || keys != p_keys || wls.len() != 4;
    let c = Ctx { g: consts(), cyc: ToCyclic::new() };

    let t0 = Instant::now();
    let mut built = vec![];
    for wl in &wls {
        let (t, _) = wl.build(&c);
        let (r, _) = record(ARM_EXHAUSTIVE as usize, wl.work, &t, &c, wl.s0(), keys);
        built.push((wl.clone(), t, r));
    }
    writeln!(
        out,
        "{{\"type\":\"meta\",\"smoke\":{smoke},\"rounds\":{rounds},\"keys_per_pass\":{keys},\"workloads\":[{}],\
\"arms\":[{}],\"build_s\":{:.3},\"cpu_at_start\":{}}}",
        wls.iter().map(|w| format!("\"{}\"", w.name)).collect::<Vec<_>>().join(","),
        BENCH_ARMS.iter().map(|n| format!("\"{n}\"")).collect::<Vec<_>>().join(","),
        t0.elapsed().as_secs_f64(),
        unsafe { sched_getcpu() }
    )
    .unwrap();

    // warmup: one untimed pass of every arm on every workload
    for (wl, t, _) in &built {
        for arm in 0..7 {
            std::hint::black_box(loop_fn(arm, wl.work)(t, &c, wl.s0(), keys));
        }
    }

    let mut mismatches = 0usize;
    for r in 0..rounds {
        let mut order: Vec<usize> = (0..na).collect();
        order.rotate_left(r % na);
        if (r / na) % 2 == 1 {
            order.reverse();
        }
        for (wl, t, refsum) in &built {
            for (pos, &arm) in order.iter().enumerate() {
                let sym = if arm == 7 { ARM_LIFT_SCAN as usize } else { arm };
                let f = std::hint::black_box(loop_fn(sym, wl.work));
                let twice = arm == 7;
                let cpu = unsafe { sched_getcpu() };
                let ru0 = rusage();
                let c0 = thread_cpu_ns();
                let k0 = tsc();
                let w0 = Instant::now();
                let mut s = f(t, &c, std::hint::black_box(wl.s0()), keys);
                if twice {
                    let s1 = s;
                    s = f(t, &c, std::hint::black_box(wl.s0()), keys);
                    if s1 != s {
                        s.hits = u64::MAX; // forces a mismatch row
                    }
                }
                let wall = w0.elapsed().as_nanos() as u64;
                let k1 = tsc();
                let c1 = thread_cpu_ns();
                let ru1 = rusage();
                let correct = arm == 0 || s == *refsum;
                if !correct {
                    mismatches += 1;
                }
                writeln!(
                    out,
                    "{{\"type\":\"pass\",\"workload\":\"{}\",\"round\":{r},\"position\":{pos},\"arm\":\"{}\",\
\"keys\":{keys},\"wall_ns\":{wall},\"tsc\":{},\"thread_cpu_ns\":{},\"nvcsw\":{},\"nivcsw\":{},\"minflt\":{},\
\"cpu\":{cpu},\"hits\":{},\"key_hash\":\"{:016x}\",\"shift_sum\":{},\"correct\":{correct}}}",
                    wl.name, BENCH_ARMS[arm], k1.wrapping_sub(k0), c1 - c0, ru1[16] - ru0[16],
                    ru1[17] - ru0[17], ru1[8] - ru0[8], s.hits, s.key_hash, s.shift_sum
                )
                .unwrap();
            }
        }
        out.flush().unwrap();
        eprintln!("round {r}/{rounds} done, {:.1} s", t0.elapsed().as_secs_f64());
    }
    writeln!(out, "{{\"type\":\"end\",\"mismatches\":{mismatches},\"total_s\":{:.3}}}", t0.elapsed().as_secs_f64())
        .unwrap();
    if mismatches > 0 {
        std::process::exit(2);
    }
}
