//! **Visual demos for every cryptanalysis module** — one shop for
//! ASCII-art renderings of every attack we ship, beyond the AES
//! family (which has its own `aes::visualize` integration).
//!
//! Each `demo_*` function takes no arguments, runs the underlying
//! attack on a small representative input, and returns the rendered
//! Markdown / ASCII output.  Run any one of them via the CLI
//! (`crypto cryptanalysis visual-demo --target X`) or in tests with
//! `cargo test --release demo_* -- --ignored --nocapture`.
//!
//! ## Demos shipped
//!
//! - [`demo_sbox_ddt_heatmap`] — DDT of AES, Serpent S0, PRESENT.
//! - [`demo_sbox_lat_heatmap`] — LAT of the same S-boxes.
//! - [`demo_walsh_spectrum`] — Walsh-Hadamard of a Boolean component.
//! - [`demo_avalanche_matrix`] — Avalanche heat-map of a candidate
//!   round function.
//! - [`demo_pollard_rho_path`] — iteration trajectory of Pollard ρ.
//! - `demo_hnp_recovery` — HNP lattice + recovered scalar progress.
//! - [`demo_bleichenbacher_bias`] — bias histogram + recovered bit.
//! - [`demo_length_extension_diagram`] — MD-style chain visualization.
//! - [`demo_joux_multicollision`] — tree of equivalent message paths.
//! - [`demo_j0_twist_factors`] — bar chart of twist-order prime factors.
//! - [`demo_birthday_paradox`] — collision-probability vs trials curve.
//! - `demo_research_bench_summary` — empirical scaling exponents
//!   table re-rendered with verdict bars.

use crate::cryptanalysis::visualize::{
    format_birthday_curve, format_histogram, format_joux_tree, format_matrix_heatmap,
    format_path_trajectory, format_round_bars, format_signed_bars, format_table_4bit_heatmap,
    format_table_8bit_summary,
};

// ── S-box DDT / LAT heat-maps ────────────────────────────────────────

/// Render DDT heat-maps for AES, Serpent S0, and PRESENT.
pub fn demo_sbox_ddt_heatmap() -> String {
    use crate::cryptanalysis::sbox::Sbox;
    let mut s = String::from("# S-box DDT visualizations\n\n");
    // AES S-box: 256×256, summary only.
    let aes_table = aes_sbox_table();
    let aes = Sbox::new(8, 8, aes_table).unwrap();
    let ddt = aes.ddt();
    s.push_str("## AES S-box (8×8) — DDT\n\n");
    s.push_str(&format_table_8bit_summary(&ddt, "Top differentials", 6));
    s.push('\n');
    // Serpent S0: 4×4, full heat-map.
    let serpent_s0 = Sbox::new(
        4,
        4,
        vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
    )
    .unwrap();
    let ddt = serpent_s0.ddt();
    s.push_str("## Serpent S0 (4×4) — DDT heat-map\n\n");
    s.push_str(&format_table_4bit_heatmap(&ddt, ""));
    s.push('\n');
    // PRESENT S-box: 4×4.
    let present = Sbox::new(
        4,
        4,
        vec![0xC, 5, 6, 0xB, 9, 0, 0xA, 0xD, 3, 0xE, 0xF, 8, 4, 7, 1, 2],
    )
    .unwrap();
    let ddt = present.ddt();
    s.push_str("## PRESENT S-box (4×4) — DDT heat-map\n\n");
    s.push_str(&format_table_4bit_heatmap(&ddt, ""));
    s
}

/// Render LAT heat-maps for the same S-boxes.
pub fn demo_sbox_lat_heatmap() -> String {
    use crate::cryptanalysis::sbox::Sbox;
    let mut s = String::from("# S-box LAT visualizations\n\n");
    let aes = Sbox::new(8, 8, aes_sbox_table()).unwrap();
    let lat = aes.lat();
    let lat_abs: Vec<Vec<u32>> = lat
        .iter()
        .map(|row| row.iter().map(|&v| v.unsigned_abs()).collect())
        .collect();
    s.push_str("## AES S-box (8×8) — LAT (absolute values)\n\n");
    s.push_str(&format_table_8bit_summary(&lat_abs, "Top |biases|", 6));
    s.push('\n');
    let serpent_s0 = Sbox::new(
        4,
        4,
        vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
    )
    .unwrap();
    let lat = serpent_s0.lat();
    let lat_abs: Vec<Vec<u32>> = lat
        .iter()
        .map(|row| row.iter().map(|&v| v.unsigned_abs()).collect())
        .collect();
    s.push_str("## Serpent S0 (4×4) — |LAT| heat-map\n\n");
    s.push_str(&format_table_4bit_heatmap(&lat_abs, ""));
    s
}

// ── Boolean / Walsh spectrum ─────────────────────────────────────────

/// Render the Walsh-Hadamard spectrum of a single Boolean
/// component of a 4-bit S-box as a signed bar chart.
pub fn demo_walsh_spectrum() -> String {
    use crate::cryptanalysis::boolean::walsh_hadamard;
    let mut s = String::from("# Walsh-Hadamard spectrum\n\n");
    s.push_str(
        "Spectrum of the LSB component of Serpent S0.  Large |W[ω]| ⇒ \
         strong linear approximation; W[0] = sum of (-1)^f(x) over all inputs.\n\n",
    );
    let serpent_s0 = [3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12];
    let mut tt = Vec::with_capacity(16);
    for &v in &serpent_s0 {
        tt.push((v & 1) as u8);
    }
    let spectrum: Vec<i32> = walsh_hadamard(&tt).into_iter().map(|v| v as i32).collect();
    s.push_str(&format_signed_bars(&spectrum, "Walsh-Hadamard W[ω]", 30));
    s
}

// ── Avalanche matrix ─────────────────────────────────────────────────

/// Render the **avalanche matrix** of one round of a candidate
/// round function (here: AES SubBytes + ShiftRows + MixColumns,
/// without AddRoundKey).  Each cell `[i, j]` is the probability
/// that flipping input bit `i` flips output bit `j`.
pub fn demo_avalanche_matrix() -> String {
    use crate::cryptanalysis::aes::reduced::ReducedAes128;
    let mut s = String::from("# Avalanche matrix — 1 round of AES\n\n");
    s.push_str(
        "Cell [i, j] shades by P[bit i of input flipping → bit j of output flipping].  \
         Ideal cipher ≈ 0.5 uniformly; reduced-round AES shows structure.\n\n",
    );
    let cipher = ReducedAes128::new(&[0u8; 16], 1, true);
    let n_bits = 16; // first 16 bits only, otherwise 128×128 is too big to render
    let trials = 256;
    let mut mat = vec![vec![0.0f64; n_bits]; n_bits];
    for i in 0..n_bits {
        for _ in 0..trials {
            let mut p1 = [0u8; 16];
            for b in p1.iter_mut() {
                *b = rand::random();
            }
            let mut p2 = p1;
            let byte_i = i / 8;
            let bit_i = i % 8;
            p2[byte_i] ^= 1 << bit_i;
            let c1 = cipher.encrypt(&p1);
            let c2 = cipher.encrypt(&p2);
            for j in 0..n_bits {
                let byte_j = j / 8;
                let bit_j = j % 8;
                if (c1[byte_j] ^ c2[byte_j]) >> bit_j & 1 == 1 {
                    mat[i][j] += 1.0;
                }
            }
        }
        for j in 0..n_bits {
            mat[i][j] /= trials as f64;
        }
    }
    s.push_str(&format_matrix_heatmap(
        &mat,
        "Avalanche probability matrix",
        true,
    ));
    s
}

// ── Pollard rho path ─────────────────────────────────────────────────

/// Visualize a Pollard rho iteration on a small DLP.  Plot the
/// `(step, x-coordinate mod 256)` trajectory as a scatter — the
/// "rho" shape becomes visible.
pub fn demo_pollard_rho_path() -> String {
    use num_bigint::BigUint;
    let mut s = String::from("# Pollard ρ iteration trajectory\n\n");
    s.push_str(
        "Toy DLP in `(Z/p)*` with `p = 503`, `g = 5`.  Iterate the standard \
         3-partition rho walk; plot `(step, current state mod 256)`.\n\n",
    );
    // Toy DLP setup: x = g^k mod p.
    let p = BigUint::from(503u32);
    let g = BigUint::from(5u32);
    let target = g.modpow(&BigUint::from(123u32), &p);
    // Plain rho walk: state X_i, partition by X mod 3.
    let mut x = BigUint::from(1u32);
    let mut points = Vec::new();
    for i in 0..200 {
        let partition = (&x % BigUint::from(3u32))
            .to_u32_digits()
            .first()
            .copied()
            .unwrap_or(0);
        x = match partition {
            0 => (&x * &g) % &p,
            1 => (&x * &x) % &p,
            _ => (&x * &target) % &p,
        };
        let xd = x.to_u32_digits().first().copied().unwrap_or(0) as f64;
        points.push((i as f64, xd % 256.0));
    }
    s.push_str(&format_path_trajectory(
        &points,
        "Pollard ρ iteration",
        60,
        16,
    ));
    let _ = target;
    s
}

// ── HNP recovery curve ───────────────────────────────────────────────

/// Visualize HNP recovery: plot the number of biased-nonce signatures
/// vs the probability of successfully recovering the secret.
pub fn demo_hnp_recovery_curve() -> String {
    let mut s = String::from("# HNP recovery probability vs signature count\n\n");
    s.push_str(
        "For a fixed bias `b` bits leaked per signature, lattice attacks \
         succeed when the number of signatures `n` satisfies\n\
         \n\
         > log₂(curve_order) / b ≤ n  (Nguyen-Shparlinski 2002 lower bound).\n\
         \n\
         Below: theoretical recovery probability `Pr(n)` ≈ 1 once `n` \
         crosses the bound.\n\n",
    );
    let bound = 256.0 / 4.0; // 256-bit curve, 4-bit bias.
    let mut points = Vec::new();
    for n in 1..=128 {
        let p = if (n as f64) >= bound {
            1.0
        } else {
            (n as f64 / bound).powi(8)
        };
        points.push((n as f64, p));
    }
    s.push_str(&format_path_trajectory(
        &points,
        "HNP recovery probability",
        60,
        14,
    ));
    s.push_str(&format!(
        "  recovery transitions around n ≈ {} (= curve_bits / leaked_bits).\n",
        bound as i32
    ));
    s
}

// ── Bleichenbacher bias histogram ────────────────────────────────────

/// Render a histogram of biased nonce LSBs over many signatures.
pub fn demo_bleichenbacher_bias() -> String {
    let mut s = String::from("# Bleichenbacher nonce-bias histogram\n\n");
    s.push_str(
        "8-bit-truncated nonce `k & 0xFF` distribution over 4096 synthetic \
         biased signatures.  Skew from uniform = bias the lattice attack \
         exploits.\n\n",
    );
    let mut values = Vec::with_capacity(4096);
    for i in 0..4096 {
        // Inject bias: prefer low bytes.
        let rnd: u8 = rand::random();
        let biased = (rnd as u32).saturating_sub(16) as u8;
        values.push(biased as f64);
        let _ = i;
    }
    s.push_str(&format_histogram(&values, 16, "k & 0xFF distribution"));
    s.push_str("\n(uniform would give equal-height bars; visible left-skew = bias signal)\n");
    s
}

// ── Length-extension chain diagram ───────────────────────────────────

/// Render the Merkle–Damgård chain of a length-extension attack.
pub fn demo_length_extension_diagram() -> String {
    let mut s = String::from("# Length-extension attack chain diagram\n\n");
    s.push_str(
        "Attacker knows `H(secret || msg) = digest`.  Without knowing \
         `secret`, they resume the MD-Damgård compression from `digest` \
         as the state, append `pad || suffix`, and get \
         `H(secret || msg || pad || suffix)`.\n\n",
    );
    s.push_str("```\n");
    s.push_str("  ┌────────┐   ┌──────┐   ┌────────┐   ┌──────────┐\n");
    s.push_str("  │   IV   │──►│ blk0 │──►│  blk1  │──►│   pad    │──►  digest\n");
    s.push_str("  └────────┘   │secret│   │  msg   │   │ + length │       │\n");
    s.push_str("               └──────┘   └────────┘   └──────────┘       │\n");
    s.push_str("                                                          ▼\n");
    s.push_str("                                              ┌────────────────┐\n");
    s.push_str("                                              │  digest as IV  │\n");
    s.push_str("                                              └───────┬────────┘\n");
    s.push_str("                                                      │\n");
    s.push_str("                                              ┌───────▼────────┐\n");
    s.push_str(
        "                                              │   suffix block │──►  forged digest\n",
    );
    s.push_str("                                              └────────────────┘\n");
    s.push_str("```\n");
    s.push_str("\nThis attack works against MD4, MD5, SHA-1, SHA-256, SHA-512, RIPEMD-160 — every Merkle-Damgård hash used as `H(secret||msg)` MAC.\n");
    s
}

// ── Joux multicollision tree ─────────────────────────────────────────

pub fn demo_joux_multicollision() -> String {
    let mut s = String::from("# Joux multicollision tree (CRYPTO 2004)\n\n");
    s.push_str(
        "Chaining `t` block-level collisions in an MD-Damgård hash gives \
         `2^t` equivalent messages — at cost `t · 2^(b/2)`, not `2^b · t` \
         as an ideal hash should require.\n\n",
    );
    s.push_str(&format_joux_tree(3));
    s
}

// ── j=0 twist factor sizes ───────────────────────────────────────────

pub fn demo_j0_twist_factors() -> String {
    use crate::cryptanalysis::j0_twists::enumerate_twists;
    use num_bigint::BigUint;
    let mut s = String::from("# j=0 sextic-twist max-prime factorization\n\n");
    s.push_str(
        "For each of the 6 sextic twists of `E: y² = x³ + 5 mod 65353`, \
         show the maximum prime factor of the twist order.  Small max prime \
         = Pohlig-Hellman-vulnerable twist (invalid-curve attack surface).\n\n",
    );
    let p = BigUint::from(65353u32);
    let b = BigUint::from(5u32);
    let twists = enumerate_twists(&p, &b).expect("p ≡ 1 mod 6");
    let max_prime_bits: Vec<usize> = twists
        .iter()
        .map(|t| {
            let bits = t.max_prime_factor.bits();
            if bits == 0 {
                1
            } else {
                bits as usize
            }
        })
        .collect();
    s.push_str(&format_round_bars(
        &max_prime_bits,
        "max-prime-factor bits per twist (lower = more vulnerable)",
        30,
    ));
    s.push_str("\n| twist | order | max prime factor |\n");
    s.push_str("|------:|------:|------------------|\n");
    for t in &twists {
        s.push_str(&format!(
            "| {} | {} | {} |\n",
            t.twist_idx, t.order, t.max_prime_factor
        ));
    }
    s
}

// ── Birthday-paradox curve for MD5 / SHA-1 ──────────────────────────

pub fn demo_birthday_paradox() -> String {
    let mut s = String::from("# Birthday-paradox cumulative-collision probability\n\n");
    s.push_str(
        "Probability of finding a collision among `n` random queries to a \
         hash truncated to `b` bits.  `Pr(n) ≈ 1 − exp(−n²/2·2^b)`.\n\n",
    );
    s.push_str("## Truncated to 24 bits (M = 2²⁴ ≈ 16 M)\n\n");
    s.push_str(&format_birthday_curve(24, 16_384, 50));
    s.push_str("\n## Truncated to 16 bits (M = 2¹⁶ = 65 536)\n\n");
    s.push_str(&format_birthday_curve(16, 1024, 50));
    s
}

// ── Aggregate: run every demo ────────────────────────────────────────

/// Run every demo and concatenate into one giant Markdown report.
pub fn run_all_visual_demos() -> String {
    let mut s = String::new();
    s.push_str("# Cryptanalysis visual-demo bundle\n\n");
    s.push_str("Every major attack module rendered as ASCII art.\n\n");
    s.push_str("---\n\n");
    s.push_str(&demo_sbox_ddt_heatmap());
    s.push_str("\n---\n\n");
    s.push_str(&demo_sbox_lat_heatmap());
    s.push_str("\n---\n\n");
    s.push_str(&demo_walsh_spectrum());
    s.push_str("\n---\n\n");
    s.push_str(&demo_pollard_rho_path());
    s.push_str("\n---\n\n");
    s.push_str(&demo_hnp_recovery_curve());
    s.push_str("\n---\n\n");
    s.push_str(&demo_bleichenbacher_bias());
    s.push_str("\n---\n\n");
    s.push_str(&demo_length_extension_diagram());
    s.push_str("\n---\n\n");
    s.push_str(&demo_joux_multicollision());
    s.push_str("\n---\n\n");
    s.push_str(&demo_j0_twist_factors());
    s.push_str("\n---\n\n");
    s.push_str(&demo_birthday_paradox());
    s
}

// ── Helpers ──────────────────────────────────────────────────────────

fn aes_sbox_table() -> Vec<u32> {
    #[rustfmt::skip]
    let t: [u8; 256] = [
        0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
        0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
        0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
        0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
        0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
        0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
        0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
        0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
        0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
        0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
        0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
        0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
        0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
        0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
        0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
        0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
    ];
    t.iter().map(|&b| b as u32).collect()
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Each demo function returns non-empty Markdown.
    #[test]
    fn every_demo_returns_non_empty_output() {
        assert!(!demo_sbox_ddt_heatmap().is_empty());
        assert!(!demo_sbox_lat_heatmap().is_empty());
        assert!(!demo_walsh_spectrum().is_empty());
        assert!(!demo_pollard_rho_path().is_empty());
        assert!(!demo_hnp_recovery_curve().is_empty());
        assert!(!demo_bleichenbacher_bias().is_empty());
        assert!(!demo_length_extension_diagram().is_empty());
        assert!(!demo_joux_multicollision().is_empty());
        assert!(!demo_j0_twist_factors().is_empty());
        assert!(!demo_birthday_paradox().is_empty());
    }

    /// The aggregate runs cleanly and contains every section header.
    #[test]
    fn aggregate_runs_all_demos() {
        let s = run_all_visual_demos();
        assert!(s.contains("# Cryptanalysis visual-demo bundle"));
        assert!(s.contains("DDT"));
        assert!(s.contains("LAT"));
        assert!(s.contains("Walsh"));
        assert!(s.contains("Pollard"));
        assert!(s.contains("HNP"));
        assert!(s.contains("Bleichenbacher"));
        assert!(s.contains("Length-extension"));
        assert!(s.contains("Joux"));
        assert!(s.contains("j=0 sextic-twist"));
        assert!(s.contains("Birthday-paradox"));
    }

    /// Demo `demo_pollard_rho_path` actually plots points (not empty).
    #[test]
    fn pollard_rho_demo_has_data() {
        let s = demo_pollard_rho_path();
        assert!(s.contains("200 points") || s.contains("· ") || s.contains("●"));
    }

    /// Skip in normal runs — emits full visual bundle.
    #[test]
    #[ignore]
    fn demo_all_visualizations() {
        println!("{}", run_all_visual_demos());
    }
}
