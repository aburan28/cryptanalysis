use std::env;
use std::fs;
use std::path::PathBuf;

fn main() {
    let source = fs::read_to_string("src/main.rs").expect("read frozen arithmetic source");
    let mut generated = String::new();
    for line in source.lines() {
        if line.starts_with("#![") {
            continue;
        }
        if let Some(rest) = line.strip_prefix("//!") {
            generated.push_str("///");
            generated.push_str(rest);
        } else {
            generated.push_str(line);
        }
        generated.push('\n');
    }
    let output = PathBuf::from(env::var("OUT_DIR").expect("Cargo OUT_DIR"));
    fs::write(output.join("legacy.rs"), generated).expect("write shared arithmetic module");
    println!("cargo:rerun-if-changed=src/main.rs");
}
