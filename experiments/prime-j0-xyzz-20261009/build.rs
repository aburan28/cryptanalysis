//! Make a standalone candidate from the frozen upstream source without editing it.

use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let repo = manifest.parent().unwrap().parent().unwrap();
    let upstream = repo.join("experiments/prime-j0-secp256k1-native/src/bin");
    let main_path = upstream.join("eisenstein_fixed.rs");
    let module_path = upstream.join("eisenstein_fixed/unit_orbit_windows.rs");
    let bignum_path = repo.join("suite/src/ct_bignum.rs");
    let out = PathBuf::from(env::var("OUT_DIR").unwrap());
    let generated_module = out.join("unit_orbit_windows.rs");
    for path in [&main_path, &module_path, &bignum_path,
                 &manifest.join("src/xyzz_append.rs"),
                 &manifest.join("src/unit_orbit_append.rs")] {
        println!("cargo:rerun-if-changed={}", path.display());
    }
    let mut module = fs::read_to_string(&module_path).unwrap();
    module.push_str("\n");
    module.push_str(&fs::read_to_string(manifest.join("src/unit_orbit_append.rs")).unwrap());
    fs::write(&generated_module, module).unwrap();

    let mut source = fs::read_to_string(&main_path).unwrap().replace("//!", "//");
    let old_bignum = "#[path = \"../../../../suite/src/ct_bignum.rs\"]";
    let old_module = "#[path = \"eisenstein_fixed/unit_orbit_windows.rs\"]";
    assert_eq!(source.matches(old_bignum).count(), 1);
    assert_eq!(source.matches(old_module).count(), 1);
    assert_eq!(source.matches("fn main() {").count(), 1);
    source = source.replace(old_bignum,
        &format!("#[path = {:?}]", bignum_path.to_str().unwrap()));
    source = source.replace(old_module,
        &format!("#[path = {:?}]", generated_module.to_str().unwrap()));
    source = source.replacen("fn main() {", "fn upstream_main() {", 1);
    source.push_str("\n");
    source.push_str(&fs::read_to_string(manifest.join("src/xyzz_append.rs")).unwrap());
    fs::write(out.join("generated_main.rs"), source).unwrap();
}
