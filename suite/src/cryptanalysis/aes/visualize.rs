//! **ASCII visualization helpers** for AES cryptanalysis output.
//!
//! Every attack produces *something* visualizable: differential
//! distribution tables, active-byte patterns, round-by-round
//! diffusion, correlation matrices, fault propagation, quartet
//! structures.  This module collects the rendering primitives so each
//! attack can drop a `println!(format_*(...))` into its test code and
//! get publishable Markdown / ASCII art under `cargo test --nocapture`.
//!
//! ## Conventions
//!
//! - Output is **plain ASCII / Unicode** — no ANSI colour codes (so
//!   it pastes into Markdown and renders the same in any terminal).
//! - Heat-map shading uses the unicode block characters
//!   `· ░ ▒ ▓ █` (5 levels) for a discrete-but-visible scale.
//! - Active-byte grids render `·` for zero, two-hex-digit values
//!   otherwise.
//! - All renderers return `String`; the caller decides whether to
//!   `println!`, write to a file, or include in a generated Markdown
//!   report.

/// Render a 4×4 AES state as a Markdown-friendly grid.  Column-major
/// AES convention is preserved: byte index `4·c + r` displays at
/// column `c`, row `r`.
///
/// Example output (16 bytes 0..15):
///
/// ```text
///     ┌────┬────┬────┬────┐
/// r0  │ 00 │ 04 │ 08 │ 0c │
///     ├────┼────┼────┼────┤
/// r1  │ 01 │ 05 │ 09 │ 0d │
///     ├────┼────┼────┼────┤
/// r2  │ 02 │ 06 │ 0a │ 0e │
///     ├────┼────┼────┼────┤
/// r3  │ 03 │ 07 │ 0b │ 0f │
///     └────┴────┴────┴────┘
/// ```
pub fn format_state_grid(bytes: &[u8; 16], title: &str) -> String {
    use crate::visualize::color::{paint, DIM, FG_BRIGHT_YELLOW};
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    s.push_str("```\n");
    s.push_str("    ┌────┬────┬────┬────┐\n");
    for r in 0..4 {
        s.push_str(&format!("r{}  │", r));
        for c in 0..4 {
            let b = bytes[4 * c + r];
            let hex_str = format!("{:02x}", b);
            // Non-zero bytes get yellow; zeros stay dim.
            let painted = if b == 0 {
                paint(&hex_str, DIM)
            } else {
                paint(&hex_str, FG_BRIGHT_YELLOW)
            };
            s.push_str(&format!(" {} │", painted));
        }
        s.push('\n');
        if r < 3 {
            s.push_str("    ├────┼────┼────┼────┤\n");
        } else {
            s.push_str("    └────┴────┴────┴────┘\n");
        }
    }
    s.push_str("```\n");
    s
}

/// Render a 4×4 AES state as an **active-byte pattern**: each cell
/// shows `▓` for non-zero, `·` for zero.  Useful for visualizing
/// differential trails where the actual byte values are noise and
/// only the active-position pattern matters.
pub fn format_active_pattern(bytes: &[u8; 16], title: &str) -> String {
    use crate::visualize::color::{paint_char, DIM, FG_BRIGHT_RED};
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    s.push_str("```\n");
    for r in 0..4 {
        s.push_str("  ");
        for c in 0..4 {
            let b = bytes[4 * c + r];
            let ch = if b == 0 { '·' } else { '▓' };
            let color = if b == 0 { DIM } else { FG_BRIGHT_RED };
            s.push(' ');
            s.push_str(&paint_char(ch, color));
        }
        s.push('\n');
    }
    s.push_str("```\n");
    s
}

/// Render side-by-side state diffs for a multi-round trail:
/// `[α_0, α_1, …, α_R]` becomes `R + 1` 4×4 grids separated by `→`.
pub fn format_trail(states: &[[u8; 16]], round_labels: &[&str]) -> String {
    assert_eq!(
        states.len(),
        round_labels.len(),
        "states and labels must align"
    );
    let mut s = String::from("```\n");
    // Print header row of labels.
    s.push_str("        ");
    for label in round_labels {
        s.push_str(&format!("{:<11}", label));
    }
    s.push('\n');
    for r in 0..4 {
        s.push_str(&format!("  row {} ", r));
        for state in states {
            s.push_str("  ");
            for c in 0..4 {
                use crate::visualize::color::{paint_char, DIM, FG_BRIGHT_RED};
                let b = state[4 * c + r];
                let ch = if b == 0 { '·' } else { '▓' };
                let col = if b == 0 { DIM } else { FG_BRIGHT_RED };
                s.push(' ');
                s.push_str(&paint_char(ch, col));
            }
            s.push(' ');
        }
        s.push('\n');
    }
    s.push_str("```\n");
    s
}

/// Render a 16×16 differential / linear / boomerang table as an
/// ASCII heat-map.  Used for 4-bit S-boxes (16×16).  For 8-bit
/// AES (256×256) prefer `format_table_8bit_summary`.
///
/// 5-level shading: `· ░ ▒ ▓ █` (zero → max).
pub fn format_table_4bit_heatmap(table: &[Vec<u32>], title: &str) -> String {
    assert_eq!(table.len(), 16);
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    let max = table.iter().flatten().copied().max().unwrap_or(1).max(1) as f64;
    s.push_str("```\n");
    s.push_str("       ");
    for c in 0..16 {
        s.push_str(&format!(" {:x}", c));
    }
    s.push('\n');
    for (r, row) in table.iter().enumerate() {
        s.push_str(&format!("  {:x}    ", r));
        for &v in row {
            let lv = ((v as f64) / max * 4.0).round() as usize;
            let lv = lv.min(4);
            let ch = ['·', '░', '▒', '▓', '█'][lv];
            s.push(' ');
            s.push_str(&crate::visualize::color::paint_char(
                ch,
                crate::visualize::color::heatmap_color(lv),
            ));
        }
        s.push('\n');
    }
    s.push_str("```\n");
    s
}

/// Compact summary for an 8-bit S-box table (256×256): max entry,
/// number of zero entries, top-5 differentials by frequency.  Full
/// 256×256 heat-map would be unreadable; this is what fits on a
/// page.
pub fn format_table_8bit_summary(table: &[Vec<u32>], title: &str, top_k: usize) -> String {
    assert_eq!(table.len(), 256);
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    let mut entries: Vec<(u8, u8, u32)> = Vec::new();
    let mut zeros = 0usize;
    let mut max = 0u32;
    for (i, row) in table.iter().enumerate() {
        for (j, &v) in row.iter().enumerate() {
            entries.push((i as u8, j as u8, v));
            if v == 0 {
                zeros += 1;
            }
            if v > max {
                max = v;
            }
        }
    }
    let mut nonzero_excluding_trivial: Vec<&(u8, u8, u32)> = entries
        .iter()
        .filter(|(i, j, _)| !(*i == 0 && *j == 0))
        .filter(|(_, _, v)| *v > 0)
        .collect();
    nonzero_excluding_trivial.sort_by_key(|(_, _, v)| std::cmp::Reverse(*v));
    s.push_str(&format!(
        "- table size: 256 × 256 ({} entries)\n\
         - max entry: {}\n\
         - zero entries: {} ({:.2}%)\n\n",
        entries.len(),
        max,
        zeros,
        (zeros as f64) / (entries.len() as f64) * 100.0,
    ));
    s.push_str("**Top entries (excluding trivial (0,0) corner)**:\n\n");
    s.push_str("| Δin (hex) | Δout (hex) | count | probability |\n");
    s.push_str("|----------:|-----------:|------:|------------:|\n");
    for (din, dout, v) in nonzero_excluding_trivial.iter().take(top_k) {
        let p = (*v as f64) / 256.0;
        s.push_str(&format!(
            "| 0x{:02x} | 0x{:02x} | {} | {:.4} |\n",
            din, dout, v, p
        ));
    }
    s.push('\n');
    s
}

/// Render a per-round bar chart of "active byte count" or any other
/// per-round integer metric.  Bar lengths normalize to the max value.
///
/// Example:
///
/// ```text
/// round  0 │█                          1
/// round  1 │████                       4
/// round  2 │██████                     6
/// round  3 │████████                   8
/// round  4 │█████████                  9
/// ```
pub fn format_round_bars(values: &[usize], title: &str, max_width: usize) -> String {
    use crate::visualize::color::{paint, FG_BRIGHT_CYAN};
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    let max = values.iter().copied().max().unwrap_or(1).max(1);
    s.push_str("```\n");
    for (i, &v) in values.iter().enumerate() {
        let bar_width = (v * max_width) / max;
        let bar = paint(&"█".repeat(bar_width), FG_BRIGHT_CYAN);
        let pad: String = " ".repeat(max_width.saturating_sub(bar_width));
        s.push_str(&format!("round {:>2} │{}{} {}\n", i, bar, pad, v));
    }
    s.push_str("```\n");
    s
}

/// Render a histogram of values bucketed into `n_bins` evenly spaced
/// bins between `min` and `max`.  Useful for visualizing the
/// distribution of, e.g., Hamming distances under a chosen ΔK.
pub fn format_histogram(values: &[f64], n_bins: usize, title: &str) -> String {
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    if values.is_empty() {
        s.push_str("(no data)\n");
        return s;
    }
    let min = values.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let range = (max - min).max(1e-12);
    let mut bins = vec![0usize; n_bins];
    for &v in values {
        let b = (((v - min) / range) * (n_bins as f64 - 1.0)).round() as usize;
        bins[b.min(n_bins - 1)] += 1;
    }
    let bin_max = bins.iter().copied().max().unwrap_or(1).max(1);
    s.push_str("```\n");
    for (i, &count) in bins.iter().enumerate() {
        let lo = min + (i as f64) * range / (n_bins as f64);
        let hi = min + ((i + 1) as f64) * range / (n_bins as f64);
        let bar_width = (count * 30) / bin_max;
        let bar: String = "█".repeat(bar_width);
        s.push_str(&format!(
            "  [{:>7.2}, {:>7.2})  │{:<30} {}\n",
            lo, hi, bar, count
        ));
    }
    s.push_str("```\n");
    s
}

/// Render the structure of a boomerang quartet:
///
/// ```text
///           P₁ ────E───→ C₁ ──⊕δ──→ C₃ ───D───→ P₃
///           ⊕α                                   │
///           │                                  ? = α
///           ↓                                   │
///           P₂ ────E───→ C₂ ──⊕δ──→ C₄ ───D───→ P₄
/// ```
///
/// Returns a Markdown code-block.
pub fn format_boomerang_quartet_diagram(
    alpha_hex: &str,
    delta_hex: &str,
    right_quartets: u64,
    total: usize,
) -> String {
    let mut s = String::new();
    s.push_str("```\n");
    s.push_str("  Quartet structure:\n");
    s.push('\n');
    s.push_str("       P₁ ───E───► C₁ ──⊕δ──► C₃ ───D───► P₃\n");
    s.push_str("       │                                   │\n");
    s.push_str("       ⊕α                              right?\n");
    s.push_str("       │                                   │\n");
    s.push_str("       ▼                                   ▼\n");
    s.push_str("       P₂ ───E───► C₂ ──⊕δ──► C₄ ───D───► P₄\n");
    s.push('\n');
    s.push_str(&format!("  α  = {}\n", alpha_hex));
    s.push_str(&format!("  δ  = {}\n", delta_hex));
    s.push_str(&format!(
        "  right quartets: {} / {} ({:.4}%)\n",
        right_quartets,
        total,
        100.0 * right_quartets as f64 / total as f64
    ));
    s.push_str("```\n");
    s
}

/// Render a small key-recovery progress bar.  `recovered` is the
/// number of key bits / bytes recovered, `total` is the target.
pub fn format_recovery_progress(recovered: usize, total: usize, label: &str) -> String {
    use crate::visualize::color::{paint, DIM, FG_BRIGHT_GREEN};
    let width = 40;
    let filled = (recovered * width) / total.max(1);
    let bar = paint(&"█".repeat(filled), FG_BRIGHT_GREEN);
    let empty = paint(&"░".repeat(width - filled), DIM);
    format!(
        "  {} │{}{}│ {}/{} ({:.1}%)\n",
        label,
        bar,
        empty,
        recovered,
        total,
        100.0 * recovered as f64 / total.max(1) as f64,
    )
}

/// Compact `bytes -> hex` formatter.
pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{:02x}", b)).collect()
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_grid_renders_16_bytes() {
        let bytes: [u8; 16] = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15];
        let s = format_state_grid(&bytes, "Test state");
        assert!(s.contains("00"));
        assert!(s.contains("0f"));
        assert!(s.contains("Test state"));
    }

    #[test]
    fn active_pattern_distinguishes_zero_from_nonzero() {
        let mut bytes = [0u8; 16];
        bytes[0] = 0xFF;
        bytes[5] = 0x01;
        let s = format_active_pattern(&bytes, "");
        // Should contain `▓` for active bytes and `·` for zero bytes.
        assert!(s.contains("▓"));
        assert!(s.contains("·"));
    }

    #[test]
    fn round_bars_zero_max_does_not_panic() {
        let s = format_round_bars(&[0, 0, 0, 0], "All zeros", 20);
        assert!(s.contains("round  0"));
        assert!(s.contains("round  3"));
    }

    #[test]
    fn round_bars_normalize_to_max() {
        let s = format_round_bars(&[1, 4, 6, 8, 9], "Diffusion", 20);
        // Bar widths should be monotonically non-decreasing along the
        // input sequence.  Count `█` characters only on lines that
        // start with `round `.
        let bars: Vec<usize> = s
            .lines()
            .filter(|l| l.trim_start().starts_with("round"))
            .map(|l| l.matches('█').count())
            .collect();
        assert_eq!(bars.len(), 5);
        assert!(
            bars.windows(2).all(|w| w[0] <= w[1]),
            "bars must be non-decreasing, got {:?}",
            bars
        );
        // Last bar has 9/9 of 20 = 20 chars.
        assert_eq!(*bars.last().unwrap(), 20);
    }

    #[test]
    fn heatmap_4bit_renders_full_table() {
        let mut t = vec![vec![0u32; 16]; 16];
        t[0][0] = 16;
        t[1][1] = 8;
        t[2][2] = 4;
        let s = format_table_4bit_heatmap(&t, "DDT");
        assert!(s.contains("█")); // max entry
        assert!(s.contains("DDT"));
        // 16 columns × 16 rows.
        let lines: Vec<&str> = s.lines().collect();
        assert!(lines.len() >= 16);
    }

    #[test]
    fn summary_8bit_lists_top_entries() {
        let mut t = vec![vec![0u32; 256]; 256];
        t[0][0] = 256; // trivial corner — should be excluded
        t[1][2] = 4;
        t[3][4] = 2;
        let s = format_table_8bit_summary(&t, "AES DDT", 5);
        assert!(s.contains("256 × 256"));
        assert!(s.contains("max entry: 256"));
        assert!(s.contains("0x01"));
        assert!(s.contains("0x02"));
    }

    #[test]
    fn boomerang_diagram_has_all_arrows() {
        let s = format_boomerang_quartet_diagram("0x01", "0x02", 4099, 16384);
        assert!(s.contains("P₁"));
        assert!(s.contains("P₂"));
        assert!(s.contains("P₃"));
        assert!(s.contains("P₄"));
        assert!(s.contains("⊕α"));
        assert!(s.contains("⊕δ"));
        assert!(s.contains("4099"));
    }

    #[test]
    fn recovery_progress_renders_percent() {
        let s = format_recovery_progress(8, 16, "K bytes");
        assert!(s.contains("8/16"));
        assert!(s.contains("50.0%"));
        assert!(s.contains("█"));
        assert!(s.contains("░"));
    }

    #[test]
    fn histogram_handles_uniform_data() {
        let vs = vec![5.0; 100];
        let s = format_histogram(&vs, 10, "Uniform");
        assert!(s.contains("Uniform"));
        assert!(s.contains("100"));
    }

    #[test]
    fn trail_renders_multi_round() {
        let states = vec![
            [0x01u8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            [0xFFu8; 16],
        ];
        let labels = vec!["round 0", "round 1"];
        let s = format_trail(&states, &labels);
        assert!(s.contains("round 0"));
        assert!(s.contains("round 1"));
    }
}
