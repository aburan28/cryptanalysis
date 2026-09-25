//! Build script for the suite.
//!
//! Its only job is optional: with the `gpu-emulator` feature it compiles
//! the GPU kernel's source, `cuda/f4_gf2_device.cuh`, as C through
//! `cuda/f4_gf2_emulate.c` and links it, so the tests run the device
//! algorithm on the host.  It uses the system C compiler (`CC`, else `cc`)
//! and `ar` directly rather than a build dependency.  Without the feature
//! it does nothing, and the CUDA backend never needs it: libcuda and NVRTC
//! are opened at run time.

use std::env;
use std::path::PathBuf;
use std::process::Command;

fn main() {
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=cuda/f4_gf2_device.cuh");
    println!("cargo:rerun-if-changed=cuda/f4_gf2_emulate.c");
    println!("cargo:rerun-if-env-changed=CC");
    println!("cargo:rerun-if-env-changed=AR");
    if env::var_os("CARGO_FEATURE_GPU_EMULATOR").is_none() {
        return;
    }
    let out = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR"));
    let obj = out.join("f4_gf2_emulate.o");
    let cc = env::var("CC").unwrap_or_else(|_| "cc".into());
    let status = Command::new(&cc)
        .args(["-std=c11", "-O2", "-fPIC", "-Wall", "-Wextra", "-c"])
        .arg("cuda/f4_gf2_emulate.c")
        .arg("-o")
        .arg(&obj)
        .status()
        .unwrap_or_else(|e| panic!("cannot run the C compiler {cc:?}: {e}"));
    assert!(status.success(), "compiling cuda/f4_gf2_emulate.c failed");
    let lib = out.join("libf4_gf2_emulate.a");
    let _ = std::fs::remove_file(&lib);
    let ar = env::var("AR").unwrap_or_else(|_| "ar".into());
    let status = Command::new(&ar)
        .arg("crs")
        .arg(&lib)
        .arg(&obj)
        .status()
        .unwrap_or_else(|e| panic!("cannot run {ar:?}: {e}"));
    assert!(status.success(), "archiving the emulator failed");
    println!("cargo:rustc-link-search=native={}", out.display());
    println!("cargo:rustc-link-lib=static=f4_gf2_emulate");
}
