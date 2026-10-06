//! Native replay for the bounded crypto-to-cryptanalysis source mirror.

use clap::Parser;
use cryptanalysis_suite::hash::sha256;
use serde::Deserialize;
use std::collections::BTreeSet;
use std::fs;
use std::path::{Component, Path, PathBuf};
use std::process::ExitCode;

const SCHEMA_VERSION: &str = "hyperelliptic-cover-source-parity/v1";
const BINARY_ADAPTER_MODE: &str = "binary_module_rustdoc_adapter";
const BINARY_ADAPTER_VERSION: &str = "unlinked-private-field-helper-rustdoc/v1";
const DOMAIN_BINDING_MODE: &str = "selected_domain_binding";
const DOMAIN_BINDING_VERSION: &str = "coefficient-field-equality/v1";

#[derive(Parser, Debug)]
#[command(name = "hyperelliptic-source-parity")]
#[command(about = "Verify the recorded crypto-to-cryptanalysis source mirror")]
struct Cli {
    /// Optional crypto checkout used to recheck source hashes and parity.
    #[arg(long, value_name = "PATH")]
    crypto_root: Option<PathBuf>,
}

#[derive(Debug, Deserialize)]
struct Manifest {
    schema_version: String,
    source_repository: String,
    source_branch: String,
    source_implementation_commit: String,
    source_baseline_commit: String,
    captured_at: String,
    files: Vec<FileRecord>,
}

#[derive(Clone, Debug, Deserialize)]
struct FileRecord {
    source_path: PathBuf,
    mirror_path: PathBuf,
    source_sha256: String,
    mirror_sha256: String,
    mode: String,
    #[serde(default)]
    adapter_version: Option<String>,
    #[serde(default)]
    required_fragments: Vec<String>,
}

fn digest(data: &[u8]) -> String {
    hex::encode(sha256(data))
}

fn replace_all(data: &[u8], needle: &[u8], replacement: &[u8]) -> Vec<u8> {
    debug_assert!(!needle.is_empty());
    let mut output = Vec::with_capacity(data.len());
    let mut offset = 0;
    while let Some(relative) = data[offset..]
        .windows(needle.len())
        .position(|candidate| candidate == needle)
    {
        let start = offset + relative;
        output.extend_from_slice(&data[offset..start]);
        output.extend_from_slice(replacement);
        offset = start + needle.len();
    }
    output.extend_from_slice(&data[offset..]);
    output
}

fn binary_module_adapter(data: &[u8]) -> Vec<u8> {
    let normalized = replace_all(data, b"[`f2m::karatsuba_mul`]", b"`f2m::karatsuba_mul`");
    replace_all(&normalized, b"[`f2m::flt_inverse`]", b"`f2m::flt_inverse`")
}

fn is_lower_hex(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn is_relative_file_path(path: &Path) -> bool {
    !path.as_os_str().is_empty()
        && path
            .components()
            .all(|component| matches!(component, Component::Normal(_) | Component::CurDir))
}

fn validate_manifest(manifest: &Manifest, errors: &mut Vec<String>) {
    if manifest.schema_version != SCHEMA_VERSION {
        errors.push(format!(
            "unsupported schema_version {:?}; expected {SCHEMA_VERSION:?}",
            manifest.schema_version
        ));
    }
    if manifest.source_repository.is_empty() {
        errors.push("source_repository must not be empty".to_string());
    }
    if manifest.source_branch.is_empty() {
        errors.push("source_branch must not be empty".to_string());
    }
    for (field, value) in [
        (
            "source_implementation_commit",
            manifest.source_implementation_commit.as_str(),
        ),
        (
            "source_baseline_commit",
            manifest.source_baseline_commit.as_str(),
        ),
    ] {
        if !is_lower_hex(value, 40) {
            errors.push(format!(
                "{field} must be a 40-character lowercase hex commit"
            ));
        }
    }
    if manifest.captured_at.is_empty() {
        errors.push("captured_at must not be empty".to_string());
    }
    if manifest.files.is_empty() {
        errors.push("files must contain at least one parity record".to_string());
    }

    let mut sources = BTreeSet::new();
    let mut mirrors = BTreeSet::new();
    for record in &manifest.files {
        let mirror = record.mirror_path.display();
        if !is_relative_file_path(&record.source_path) {
            errors.push(format!(
                "{}: source_path must stay within the crypto checkout",
                record.source_path.display()
            ));
        }
        if !is_relative_file_path(&record.mirror_path) {
            errors.push(format!(
                "{mirror}: mirror_path must stay within the cryptanalysis checkout"
            ));
        }
        if !sources.insert(record.source_path.clone()) {
            errors.push(format!(
                "{}: duplicate source_path",
                record.source_path.display()
            ));
        }
        if !mirrors.insert(record.mirror_path.clone()) {
            errors.push(format!("{mirror}: duplicate mirror_path"));
        }
        if !is_lower_hex(&record.source_sha256, 64) {
            errors.push(format!("{mirror}: source_sha256 must be lowercase SHA-256"));
        }
        if !is_lower_hex(&record.mirror_sha256, 64) {
            errors.push(format!("{mirror}: mirror_sha256 must be lowercase SHA-256"));
        }

        match record.mode.as_str() {
            "exact" => {
                if record.adapter_version.is_some() || !record.required_fragments.is_empty() {
                    errors.push(format!(
                        "{mirror}: exact records cannot declare adapter metadata"
                    ));
                }
                if record.source_sha256 != record.mirror_sha256 {
                    errors.push(format!("{mirror}: exact manifest hashes disagree"));
                }
            }
            BINARY_ADAPTER_MODE => {
                if record.adapter_version.as_deref() != Some(BINARY_ADAPTER_VERSION) {
                    errors.push(format!(
                        "{mirror}: unsupported binary-module adapter version {:?}",
                        record.adapter_version
                    ));
                }
                if !record.required_fragments.is_empty() {
                    errors.push(format!(
                        "{mirror}: binary-module adapter cannot declare required_fragments"
                    ));
                }
            }
            DOMAIN_BINDING_MODE => {
                if record.adapter_version.as_deref() != Some(DOMAIN_BINDING_VERSION) {
                    errors.push(format!(
                        "{mirror}: unsupported domain-binding adapter version {:?}",
                        record.adapter_version
                    ));
                }
                if record.required_fragments.is_empty() {
                    errors.push(format!(
                        "{mirror}: selected-domain binding needs required_fragments"
                    ));
                }
                if record.required_fragments.iter().any(String::is_empty) {
                    errors.push(format!(
                        "{mirror}: selected-domain fragments must not be empty"
                    ));
                }
            }
            mode => errors.push(format!("{mirror}: unsupported parity mode {mode:?}")),
        }
    }
}

fn read_recorded_file(path: &Path, errors: &mut Vec<String>) -> Option<Vec<u8>> {
    match fs::read(path) {
        Ok(data) => Some(data),
        Err(error) => {
            errors.push(format!("read {}: {error}", path.display()));
            None
        }
    }
}

fn contains(haystack: &[u8], needle: &[u8]) -> bool {
    !needle.is_empty()
        && haystack
            .windows(needle.len())
            .any(|window| window == needle)
}

fn verify_pair(
    record: &FileRecord,
    source_data: &[u8],
    mirror_data: &[u8],
    errors: &mut Vec<String>,
) {
    let mirror = record.mirror_path.display();
    match record.mode.as_str() {
        "exact" => {
            if source_data != mirror_data {
                errors.push(format!("{mirror}: bytes differ from crypto source"));
            }
        }
        BINARY_ADAPTER_MODE => {
            if binary_module_adapter(source_data) != mirror_data {
                errors.push(format!("{mirror}: unexpected adapter difference"));
            }
        }
        DOMAIN_BINDING_MODE => {
            for fragment in &record.required_fragments {
                let encoded = fragment.as_bytes();
                if !contains(source_data, encoded) || !contains(mirror_data, encoded) {
                    errors.push(format!(
                        "{mirror}: missing shared domain-binding fragment {fragment:?}"
                    ));
                }
            }
        }
        _ => {}
    }
}

fn verify_files(
    manifest: &Manifest,
    repository: &Path,
    crypto_root: Option<&Path>,
    errors: &mut Vec<String>,
) {
    for record in &manifest.files {
        if !is_relative_file_path(&record.mirror_path) {
            continue;
        }
        let mirror_path = repository.join(&record.mirror_path);
        let Some(mirror_data) = read_recorded_file(&mirror_path, errors) else {
            continue;
        };
        let mirror_digest = digest(&mirror_data);
        if mirror_digest != record.mirror_sha256 {
            errors.push(format!(
                "{}: expected {}, got {mirror_digest}",
                record.mirror_path.display(),
                record.mirror_sha256
            ));
        }

        let Some(crypto_root) = crypto_root else {
            continue;
        };
        if !is_relative_file_path(&record.source_path) {
            continue;
        }
        let source_path = crypto_root.join(&record.source_path);
        let Some(source_data) = read_recorded_file(&source_path, errors) else {
            continue;
        };
        let source_digest = digest(&source_data);
        if source_digest != record.source_sha256 {
            errors.push(format!(
                "{}: expected {}, got {source_digest}",
                record.source_path.display(),
                record.source_sha256
            ));
            continue;
        }
        verify_pair(record, &source_data, &mirror_data, errors);
    }
}

fn run(cli: &Cli) -> Result<String, Vec<String>> {
    let repository = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("suite Cargo manifest must have a repository parent");
    let manifest_path = repository
        .join("experiments")
        .join("hyperelliptic-cover-infrastructure")
        .join("source-parity.json");
    let manifest_bytes = fs::read(&manifest_path)
        .map_err(|error| vec![format!("read {}: {error}", manifest_path.display())])?;
    let manifest: Manifest = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| vec![format!("parse {}: {error}", manifest_path.display())])?;

    let mut errors = Vec::new();
    validate_manifest(&manifest, &mut errors);
    verify_files(
        &manifest,
        repository,
        cli.crypto_root.as_deref(),
        &mut errors,
    );
    if errors.is_empty() {
        let qualifier = if cli.crypto_root.is_some() {
            " and crypto source"
        } else {
            ""
        };
        Ok(format!(
            "hyperelliptic mirror manifest{qualifier}: verified"
        ))
    } else {
        Err(errors)
    }
}

fn main() -> ExitCode {
    let cli = Cli::parse();
    match run(&cli) {
        Ok(message) => {
            println!("{message}");
            ExitCode::SUCCESS
        }
        Err(errors) => {
            for error in errors {
                eprintln!("error: {error}");
            }
            ExitCode::from(1)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record(mode: &str) -> FileRecord {
        FileRecord {
            source_path: "source.rs".into(),
            mirror_path: "mirror.rs".into(),
            source_sha256: "0".repeat(64),
            mirror_sha256: "0".repeat(64),
            mode: mode.to_string(),
            adapter_version: None,
            required_fragments: Vec::new(),
        }
    }

    #[test]
    fn binary_adapter_performs_only_the_two_declared_rewrites() {
        let source = b"//! [`f2m::karatsuba_mul`] x [`f2m::flt_inverse`] [other]";
        assert_eq!(
            binary_module_adapter(source),
            b"//! `f2m::karatsuba_mul` x `f2m::flt_inverse` [other]"
        );
    }

    #[test]
    fn exact_mode_rejects_a_byte_difference() {
        let mut errors = Vec::new();
        verify_pair(&record("exact"), b"same", b"different", &mut errors);
        assert_eq!(errors, ["mirror.rs: bytes differ from crypto source"]);
    }

    #[test]
    fn selected_binding_requires_every_fragment_on_both_sides() {
        let mut selected = record(DOMAIN_BINDING_MODE);
        selected.required_fragments = vec!["guard".into(), "test".into()];
        let mut errors = Vec::new();
        verify_pair(&selected, b"guard and test", b"guard only", &mut errors);
        assert_eq!(
            errors,
            ["mirror.rs: missing shared domain-binding fragment \"test\""]
        );
    }

    #[test]
    fn repository_paths_cannot_escape_the_checkout() {
        assert!(is_relative_file_path(Path::new("suite/src/file.rs")));
        assert!(!is_relative_file_path(Path::new("../outside")));
        assert!(!is_relative_file_path(Path::new("/absolute")));
    }

    #[test]
    fn invalid_record_paths_are_not_read() {
        let mut invalid = record("exact");
        invalid.source_path = "../outside-source".into();
        invalid.mirror_path = "../outside-mirror".into();
        let manifest = Manifest {
            schema_version: SCHEMA_VERSION.into(),
            source_repository: "https://example.invalid/source".into(),
            source_branch: "test".into(),
            source_implementation_commit: "0".repeat(40),
            source_baseline_commit: "0".repeat(40),
            captured_at: "test".into(),
            files: vec![invalid],
        };
        let mut errors = Vec::new();
        verify_files(
            &manifest,
            Path::new("missing-repository"),
            Some(Path::new("missing-crypto")),
            &mut errors,
        );
        assert!(errors.is_empty());
    }
}
