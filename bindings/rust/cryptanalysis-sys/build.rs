//! Build script: compiles the C library straight from the repository sources
//! with the `cc` crate, so no CMake step is needed to use the Rust bindings.
//!
//! The source list mirrors `CA_SOURCES` in the top-level `CMakeLists.txt`; if
//! a file is added there it must be added here too.

use std::env;
use std::path::PathBuf;

/// Files from `CA_SOURCES` in the top-level CMakeLists.txt.
const SOURCES: &[&str] = &[
    "modarith.c",
    "util.c",
    "group_common.c",
    "group_zp.c",
    "group_ec.c",
    "bsgs.c",
    "rho.c",
    "kangaroo.c",
    "grumpy.c",
    "pohlig.c",
    "cheon.c",
    "linalg.c",
    "indexcalc.c",
    "ffi.c",
];

fn main() {
    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    // bindings/rust/cryptanalysis-sys -> repository root
    let repo_root = manifest_dir
        .join("..")
        .join("..")
        .join("..")
        .canonicalize()
        .expect("repository root");
    let src_dir = repo_root.join("src");
    let include_dir = repo_root.join("include");

    for d in [&src_dir, &include_dir] {
        assert!(
            d.is_dir(),
            "expected the C sources at {}; the crate must live at <repo>/bindings/rust/cryptanalysis-sys",
            d.display()
        );
        println!("cargo:rerun-if-changed={}", d.display());
    }
    println!("cargo:rerun-if-changed=build.rs");

    let mut build = cc::Build::new();
    build
        .include(&include_dir)
        .include(&src_dir)
        .opt_level(3)
        .flag("-std=gnu11")
        .define("_GNU_SOURCE", None)
        .define("CA_BUILDING", None)
        // The library uses -Wno-unused-function in its own build; keep the
        // Rust build quiet about static helpers that are unused per file.
        .flag_if_supported("-Wno-unused-function")
        .warnings(false);
    for s in SOURCES {
        build.file(src_dir.join(s));
    }
    build.compile("cryptanalysis");

    println!("cargo:rustc-link-lib=pthread");
    println!("cargo:rustc-link-lib=m");
    // Exported for dependents that want to locate the headers (via DEP_CRYPTANALYSIS_INCLUDE).
    println!("cargo:include={}", include_dir.display());
}
