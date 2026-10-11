//! **Top-level ASCII visualization primitives** for every module in
//! the library — symmetric, hash, ECC, asymmetric, PQC, ZK.
//!
//! Re-exports the cryptanalysis-side helpers (which originated this
//! visualization layer) so any module can render heat-maps, state
//! grids, signed bars, trajectories, trees, and progress bars
//! without depending on `cryptanalysis::*`.
//!
//! Submodule-specific renderers live in their own `visualize.rs`
//! files (e.g. `symmetric::visualize`, `hash::visualize`,
//! `ecc::visualize`) and call into the primitives here.
//!
//! ## ANSI colors
//!
//! All renderers consult [`color::enabled()`] before emitting ANSI
//! escape codes.  Auto-detected from stdout TTY status; respects
//! `NO_COLOR` (off) and `CRYPTO_COLOR={always|never}` overrides.
//! Pipe a colored visual to a file → the file gets plain text.

pub mod color;

pub use crate::cryptanalysis::visualize::{
    format_active_pattern, format_birthday_curve, format_boomerang_quartet_diagram,
    format_histogram, format_joux_tree, format_matrix_heatmap, format_path_trajectory,
    format_recovery_progress, format_round_bars, format_signed_bars, format_state_grid,
    format_table_4bit_heatmap, format_table_8bit_summary, format_trail, hex,
};

// ── Additional general-purpose primitives ────────────────────────────

/// Render a dataflow diagram: a sequence of named stages connected
/// by arrows.  Used for cipher-mode dataflow visualizations.
///
/// `nodes`: each entry is `(name, width)`.  Renders one row of
/// boxes connected by `──►` arrows.
pub fn format_dataflow_horizontal(nodes: &[(&str, usize)]) -> String {
    if nodes.is_empty() {
        return String::new();
    }
    let mut s = String::from("```\n");
    // Top border
    for (name, width) in nodes {
        let w = (*width).max(name.len() + 2);
        s.push('┌');
        for _ in 0..w {
            s.push('─');
        }
        s.push('┐');
        s.push_str("    ");
    }
    s.push('\n');
    // Label row
    for (i, (name, width)) in nodes.iter().enumerate() {
        let w = (*width).max(name.len() + 2);
        let pad = (w - name.len()) / 2;
        s.push('│');
        for _ in 0..pad {
            s.push(' ');
        }
        s.push_str(name);
        for _ in 0..(w - pad - name.len()) {
            s.push(' ');
        }
        s.push('│');
        if i + 1 < nodes.len() {
            s.push_str(" ──►");
        } else {
            s.push_str("    ");
        }
    }
    s.push('\n');
    // Bottom border
    for (name, width) in nodes {
        let w = (*width).max(name.len() + 2);
        s.push('└');
        for _ in 0..w {
            s.push('─');
        }
        s.push('┘');
        s.push_str("    ");
    }
    s.push('\n');
    s.push_str("```\n");
    s
}

/// Render an XOR fan-in junction: two inputs converging to one output.
///
/// ```text
///   A ──┐
///       ⊕──► C
///   B ──┘
/// ```
pub fn format_xor_junction(a: &str, b: &str, c: &str) -> String {
    let mut s = String::from("```\n");
    s.push_str(&format!("  {} ──┐\n", a));
    s.push_str(&format!("      ⊕──► {}\n", c));
    s.push_str(&format!("  {} ──┘\n", b));
    s.push_str("```\n");
    s
}

/// Render a 2-D `width × height` bitmap as ASCII shading, treating
/// each byte as an intensity 0..255.  Used for the ECB penguin demo.
pub fn format_bitmap_shaded(pixels: &[u8], width: usize, height: usize, title: &str) -> String {
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    assert_eq!(pixels.len(), width * height);
    s.push_str("```\n");
    let levels = ['·', '░', '▒', '▓', '█'];
    for row in 0..height {
        for col in 0..width {
            let p = pixels[row * width + col];
            let lv = ((p as usize) * (levels.len() - 1)) / 255;
            s.push(levels[lv.min(levels.len() - 1)]);
            s.push(' ');
        }
        s.push('\n');
    }
    s.push_str("```\n");
    s
}

/// Render an N-ary tree as ASCII, with labels at each node.  Used
/// for BLAKE3 tree, Merkle tree visualizations.
pub fn format_tree(root_label: &str, levels: usize, branching: usize) -> String {
    let mut s = String::from("```\n");
    s.push_str(&format!("  {}\n", root_label));
    let mut indent = 0;
    let mut count = 1;
    for level in 1..=levels {
        indent += 2;
        count *= branching;
        let line_indent: String = " ".repeat(indent);
        s.push_str(&format!("{}│\n", line_indent));
        let leaf = count;
        for i in 0..leaf.min(branching * 2) {
            s.push_str(&format!("{}├── L{}-{}\n", line_indent, level, i));
        }
        if leaf > branching * 2 {
            s.push_str(&format!(
                "{}└── ... ({} more)\n",
                line_indent,
                leaf - branching * 2
            ));
        }
    }
    s.push_str("```\n");
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dataflow_horizontal_renders() {
        let s = format_dataflow_horizontal(&[("P", 5), ("XOR K", 8), ("AES", 5)]);
        assert!(s.contains("P"));
        assert!(s.contains("AES"));
        assert!(s.contains("──►"));
    }

    #[test]
    fn xor_junction_renders_three_labels() {
        let s = format_xor_junction("IV", "P_0", "C_0");
        assert!(s.contains("IV"));
        assert!(s.contains("P_0"));
        assert!(s.contains("C_0"));
        assert!(s.contains("⊕"));
    }

    #[test]
    fn bitmap_renders_correct_dimensions() {
        let pixels = vec![0u8, 64, 128, 192, 255, 0, 0, 255];
        let s = format_bitmap_shaded(&pixels, 4, 2, "Test");
        assert!(s.contains("Test"));
        // 2 rows of 4 chars each = at least 8 levels chars rendered.
        let level_chars: usize = s
            .chars()
            .filter(|c| ['·', '░', '▒', '▓', '█'].contains(c))
            .count();
        assert!(level_chars >= 8);
    }

    #[test]
    fn tree_renders_levels() {
        let s = format_tree("ROOT", 2, 2);
        assert!(s.contains("ROOT"));
        assert!(s.contains("L1"));
        assert!(s.contains("L2"));
    }
}
