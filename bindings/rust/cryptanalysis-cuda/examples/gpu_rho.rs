//! Solve one small discrete logarithm on the GPU and print the statistics.
//!
//! ```text
//! cargo run --example gpu_rho                 # Z_p^*, 31-bit subgroup
//! cargo run --example gpu_rho -- ec           # a 28-bit elliptic curve
//! ```
//!
//! Exits quietly with a message when the machine has no NVIDIA device, so it
//! is safe to run anywhere.

use std::process::ExitCode;

use cryptanalysis::{Elem, Group};
use cryptanalysis_cuda::{device_count, device_name, ptx_source, CudaRho, Params, PtxSource};

fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(e) => {
            eprintln!("error: {e}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<ExitCode, Box<dyn std::error::Error>> {
    println!("kernel PTX: {}", ptx_source());
    if ptx_source() == PtxSource::Unavailable {
        println!(
            "No kernel available: build with CUDA_PATH set so build.rs can produce PTX, \
             or install NVRTC for the run-time fallback."
        );
        return Ok(ExitCode::SUCCESS);
    }

    let devices = device_count();
    println!("CUDA devices: {devices}");
    if devices == 0 {
        println!("No NVIDIA device on this machine - nothing to run.");
        return Ok(ExitCode::SUCCESS);
    }
    println!("device 0: {}", device_name(0)?);

    let curve = std::env::args().nth(1).as_deref() == Some("ec");
    let (group, base, x) = if curve {
        // y^2 = x^3 + 3x + 11 over F_1000000007, the fixture tests/test_gpu.c uses.
        let (p, a, b) = (1_000_000_007u64, 3u64, 11u64);
        let order = Group::ec_count_points(p, a, b)?;
        let g = Group::ec(p, a, b, order)?;
        let base = g.find_generator(1)?;
        (g, base, 987_654_321 % order)
    } else {
        let g = Group::zp(2_000_000_579, 1_000_000_289)?;
        let base = g.find_generator(1)?;
        (g, base, 123_456_789)
    };
    let target: Elem = group.mul(&base, x)?;
    println!(
        "solving in a group of order {} (x = {x} is the answer we expect)",
        group.order()
    );

    let params = Params {
        seed: 7,
        ..Params::default()
    };
    let rho = CudaRho::new(&params)?;
    let (got, stats) = rho.solve(&group, base, target, &params)?;

    println!("x         = {got}");
    println!("group_ops = {}", stats.group_ops);
    println!("launches  = {}", stats.launches);
    println!("dps       = {}", stats.dps);
    println!("restarts  = {}", stats.restarts);
    println!("threads   = {} ({} walks)", stats.threads, stats.walks());
    println!("seconds   = {:.3}", stats.seconds);
    if stats.seconds > 0.0 {
        println!(
            "rate      = {:.2e} group ops/s",
            stats.group_ops as f64 / stats.seconds
        );
    }

    if got != x {
        eprintln!("wrong answer: expected {x}");
        return Ok(ExitCode::FAILURE);
    }
    Ok(ExitCode::SUCCESS)
}
