//! **Auto-attack runner** — apply every applicable cryptanalytic
//! technique to a named cipher and emit a Markdown report.
//!
//! Discovery logic:
//!
//! 1. **S-box analysis** runs unconditionally if the cipher exposes a
//!    single S-box (`CipherEntry::sbox()` returns `Some`).  Emits a
//!    DDT/LAT/BCT/DLCT report via `Sbox::report`.
//!
//! 2. **Boomerang distinguisher** runs unconditionally with the
//!    cipher's canonical `(α, δ)` and a default `n_pairs = 65536`.
//!
//! 3. **Rectangle attack** runs unconditionally with a default
//!    `pool_size = 2048`.
//!
//! 4. **Differential trail search** runs only if the cipher is
//!    `trail_searchable` (currently: 4×4-bit SPN ciphers, i.e.
//!    ToySpn).  Skipped for AES because the 8-bit S-box DDT row
//!    explosion makes our naive enumeration too slow.
//!
//! ## What this does NOT do
//!
//! - Pick the *optimal* trail for each cipher.  We use the canonical
//!   `(α, δ) = (0x01, 0x01)` for every cipher; a real attack would
//!   first run the trail search and feed the best `(α, β, γ, δ)`
//!   into the boomerang/rectangle.  Plumbing the trail-search output
//!   back into the distinguisher is the natural next iteration.
//!
//! - Mount key-recovery attacks.  Distinguishers only.  Key recovery
//!   (e.g., wrong-key-pair filtering, partial-decryption attacks) is
//!   implemented in `aes/square.rs` and `aes/differential.rs` for AES
//!   but not auto-wired here.

use crate::cryptanalysis::boomerang::{
    boomerang_distinguisher, differential_trail_search, rectangle_attack, SpnTrailModel, ToySpn,
};
use crate::cryptanalysis::cipher_registry::RegisteredCipher;
use std::time::Instant;

/// All-in-one auto-attack result for one cipher.
#[derive(Clone, Debug)]
pub struct AutoAttackReport {
    pub cipher_name: String,
    pub markdown: String,
    pub elapsed_ms: u128,
    /// Number of attack sections that ran (`sbox`, `boomerang`,
    /// `rectangle`, `trail_search`).
    pub sections_run: usize,
}

/// **Run all applicable attacks** against `cipher_name`.  Returns a
/// Markdown report.  Defaults can be overridden via
/// [`AutoAttackOptions`] (or use [`auto_attack`] for sane defaults).
pub fn auto_attack(cipher_name: &str) -> Result<AutoAttackReport, String> {
    auto_attack_with(cipher_name, AutoAttackOptions::default())
}

/// Knobs for the auto-attack runner.
#[derive(Clone, Debug)]
pub struct AutoAttackOptions {
    /// Number of plaintext pairs for the boomerang distinguisher.
    pub boomerang_pairs: usize,
    /// Pool size for the rectangle attack.
    pub rectangle_pool: usize,
    /// Trail-search threshold (`p ≥ threshold` to keep a trail).
    pub trail_threshold: f64,
    /// Max trails to render in the report.
    pub trail_top_k: usize,
}

impl Default for AutoAttackOptions {
    fn default() -> Self {
        Self {
            boomerang_pairs: 65_536,
            rectangle_pool: 2048,
            trail_threshold: 2f64.powi(-12),
            trail_top_k: 5,
        }
    }
}

/// Run all applicable attacks against `cipher_name` with custom
/// `opts`.  Returns `Err(msg)` if the cipher name is unknown.
pub fn auto_attack_with(
    cipher_name: &str,
    opts: AutoAttackOptions,
) -> Result<AutoAttackReport, String> {
    let cipher = RegisteredCipher::from_name(cipher_name)
        .ok_or_else(|| format!("unknown cipher: {}", cipher_name))?;
    let entry = cipher.entry();
    let mut md = String::new();
    let mut sections_run = 0;
    let t0 = Instant::now();
    md.push_str(&format!("# Auto-cryptanalysis: `{}`\n\n", cipher_name));
    md.push_str(&format!("**Cipher**: {}\n\n", entry.description));
    md.push_str(&format!(
        "**Block size**: {} bytes ({} bits)\n\n",
        entry.block_bytes,
        entry.block_bytes * 8
    ));
    md.push_str(&format!("**Rounds**: {}\n\n", entry.rounds));
    md.push_str(&format!(
        "**Canonical (α, δ)**: `{}` / `{}`\n\n",
        hex(&entry.canonical_alpha),
        hex(&entry.canonical_delta)
    ));

    // ── Section 1: S-box analysis ──────────────────────────────────
    if let Some(sbox) = cipher.sbox() {
        md.push_str("## S-box analysis\n\n");
        let r = sbox.report();
        md.push_str(&format!(
            "| metric | value |\n|---|---|\n\
             | bits in / out | {} / {} |\n\
             | bijective | {} |\n\
             | balanced | {} |\n\
             | max DDT entry (differential uniformity) | {} |\n\
             | max differential probability | {:.4} |\n\
             | max linear bias | {:.4} |\n\
             | nonlinearity | {} |\n\
             | algebraic degree | {} |\n\
             | boomerang uniformity | {} |\n\
             | max DLCT bias | {:.4} |\n\n",
            r.n_in,
            r.n_out,
            r.bijective,
            r.balanced,
            r.differential_uniformity,
            r.max_differential_probability,
            r.max_linear_bias,
            r.nonlinearity,
            r.algebraic_degree,
            match r.boomerang_uniformity {
                Some(v) => v.to_string(),
                None => "—".into(),
            },
            r.max_dlct_bias,
        ));
        sections_run += 1;
    }

    // ── Section 2: Boomerang distinguisher ─────────────────────────
    md.push_str("## Boomerang distinguisher\n\n");
    md.push_str(&format!(
        "Run on `{}` random pairs `(P, P ⊕ α)`.  Count quartets \
         `(P₁, P₂, P₃, P₄)` with `P₃ ⊕ P₄ = α` after the \
         `C → C ⊕ δ → decrypt` chain.\n\n",
        opts.boomerang_pairs
    ));
    let t_b = Instant::now();
    let b_result = boomerang_distinguisher(
        &cipher,
        &entry.canonical_alpha,
        &entry.canonical_delta,
        opts.boomerang_pairs,
        None,
    );
    let b_elapsed = t_b.elapsed().as_millis();
    md.push_str(&format!(
        "- **elapsed**: {} ms\n\
         - **right quartets**: {} / {}\n\
         - **empirical (pq)²**: {:.4e}\n\
         - **random baseline**: {:.4e}\n\
         - **distinguishes from random (10×)**: {}\n\n",
        b_elapsed,
        b_result.right_quartets,
        b_result.n_pairs,
        b_result.empirical_probability,
        b_result.random_baseline,
        if b_result.distinguishes_from_random(10.0) {
            "✓"
        } else {
            "✗"
        },
    ));
    sections_run += 1;

    // ── Section 3: Rectangle attack ────────────────────────────────
    md.push_str("## Rectangle attack\n\n");
    md.push_str(&format!(
        "Pure-chosen-plaintext variant.  Generate `{}` pairs \
         `(P, P ⊕ α)`, look for quartets via hash bucketing on \
         `C ⊕ δ`.\n\n",
        opts.rectangle_pool
    ));
    let t_r = Instant::now();
    let r_result = rectangle_attack(
        &cipher,
        &entry.canonical_alpha,
        &entry.canonical_delta,
        opts.rectangle_pool,
        None,
    );
    let r_elapsed = t_r.elapsed().as_millis();
    md.push_str(&format!(
        "- **elapsed**: {} ms\n\
         - **right rectangles**: {}\n\
         - **pool size**: {}\n\n",
        r_elapsed, r_result.right_quartets, r_result.pool_size
    ));
    sections_run += 1;

    // ── Section 4: Differential trail search ───────────────────────
    if entry.trail_searchable {
        md.push_str("## Differential trail search\n\n");
        md.push_str(&format!(
            "Branch-and-bound over a 4×4-bit SPN model, threshold \
             `2^{{{}}}`.  Reports top-{} trails seeded with `α = {}`.\n\n",
            opts.trail_threshold.log2().round() as i32,
            opts.trail_top_k,
            hex(&entry.canonical_alpha),
        ));
        let sbox = cipher.sbox().expect("trail_searchable ⇒ has Sbox");
        let ddt = sbox.ddt();
        let model = SpnTrailModel {
            ddt,
            sbox_bits: 4,
            n_sboxes: 4,
            linear_layer: |x| ToySpn::bit_permutation(x as u16) as u64,
        };
        let alpha_u64 =
            u16::from_le_bytes([entry.canonical_alpha[0], entry.canonical_alpha[1]]) as u64;
        let t_t = Instant::now();
        let mut trails =
            differential_trail_search(&model, alpha_u64, entry.rounds, opts.trail_threshold);
        let t_elapsed = t_t.elapsed().as_millis();
        trails.truncate(opts.trail_top_k);
        md.push_str(&format!(
            "- **elapsed**: {} ms\n\
             - **trails found**: {}\n\n",
            t_elapsed,
            trails.len()
        ));
        if !trails.is_empty() {
            md.push_str("| rank | input α | output ω | probability | log₂ p |\n");
            md.push_str("|----:|---------|----------|------------:|-------:|\n");
            for (rank, t) in trails.iter().enumerate() {
                md.push_str(&format!(
                    "| {} | 0x{:04x} | 0x{:04x} | {:.4e} | {:.2} |\n",
                    rank + 1,
                    t.alpha,
                    t.omega,
                    t.probability,
                    t.probability.log2(),
                ));
            }
            md.push('\n');
        }
        sections_run += 1;
    } else {
        md.push_str("## Differential trail search\n\n");
        md.push_str(
            "_Skipped._ This cipher's structure is not in the \
             `SpnTrailModel` family (currently 4×4-bit SPNs only).  \
             For AES-class ciphers, see `cryptanalysis/aes/milp.rs` \
             which encodes the trail search as a MILP.\n\n",
        );
    }

    md.push_str("---\n");
    md.push_str(&format!(
        "**Total elapsed**: {} ms across {} attack sections.\n",
        t0.elapsed().as_millis(),
        sections_run
    ));

    Ok(AutoAttackReport {
        cipher_name: cipher_name.to_string(),
        markdown: md,
        elapsed_ms: t0.elapsed().as_millis(),
        sections_run,
    })
}

/// Format a byte slice as `0x` hex.
fn hex(bytes: &[u8]) -> String {
    let mut s = String::from("0x");
    for b in bytes {
        s.push_str(&format!("{:02x}", b));
    }
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **Auto-attack runs on each registered cipher**: produces a
    /// non-empty Markdown report with at least 2 sections (sbox +
    /// boomerang).
    #[test]
    fn auto_attack_runs_on_all_registered_ciphers() {
        // Small overrides so this is fast.
        let opts = AutoAttackOptions {
            boomerang_pairs: 256,
            rectangle_pool: 64,
            trail_threshold: 2f64.powi(-8),
            trail_top_k: 3,
        };
        for name in crate::cryptanalysis::cipher_registry::list_ciphers() {
            let report = auto_attack_with(name, opts.clone())
                .unwrap_or_else(|e| panic!("auto_attack failed for {}: {}", name, e));
            assert!(
                report.sections_run >= 2,
                "cipher {} ran only {} sections",
                name,
                report.sections_run,
            );
            assert!(
                report.markdown.contains("Boomerang distinguisher"),
                "missing boomerang section for {}",
                name
            );
        }
    }

    /// **Auto-attack rejects unknown cipher**.
    #[test]
    fn auto_attack_rejects_unknown_cipher() {
        let r = auto_attack("not-a-cipher");
        assert!(r.is_err());
    }

    /// **Auto-attack on `toyspn-2r` includes a trail-search section**
    /// (trail_searchable is true).
    #[test]
    fn auto_attack_toyspn_runs_trail_search() {
        let opts = AutoAttackOptions {
            boomerang_pairs: 256,
            rectangle_pool: 64,
            trail_threshold: 2f64.powi(-10),
            trail_top_k: 5,
        };
        let report = auto_attack_with("toyspn-2r", opts).unwrap();
        assert!(
            report.markdown.contains("Differential trail search"),
            "expected trail-search section"
        );
        assert!(
            report.sections_run == 4,
            "toyspn-2r should run all 4 sections, got {}",
            report.sections_run
        );
    }

    /// **Auto-attack on AES skips the trail search** (8-bit S-box not
    /// in the SPN trail-search model).
    #[test]
    fn auto_attack_aes_skips_trail_search() {
        let opts = AutoAttackOptions {
            boomerang_pairs: 32,
            rectangle_pool: 32,
            trail_threshold: 2f64.powi(-8),
            trail_top_k: 3,
        };
        let report = auto_attack_with("aes-2r", opts).unwrap();
        assert!(report.markdown.contains("_Skipped._"));
        // 3 sections: sbox + boomerang + rectangle.
        assert_eq!(report.sections_run, 3);
    }

    /// **Report is well-formed Markdown**: starts with a level-1 header.
    #[test]
    fn auto_attack_report_is_markdown() {
        let opts = AutoAttackOptions {
            boomerang_pairs: 32,
            rectangle_pool: 32,
            trail_threshold: 2f64.powi(-8),
            trail_top_k: 3,
        };
        let report = auto_attack_with("toyspn-1r", opts).unwrap();
        assert!(report.markdown.starts_with("# Auto-cryptanalysis"));
    }
}
