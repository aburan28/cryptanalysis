//! **Top-level ASCII visualization helpers** for every cryptanalysis
//! module — promotes the `aes::visualize` primitives to a generally
//! accessible location and adds new ones that the non-AES attacks need:
//!
//! - [`format_matrix_heatmap`] — generic m × n matrix heat-map for
//!   lattices, relation matrices, S-box tables.
//! - [`format_path_trajectory`] — ASCII scatter / line plot for
//!   Pollard rho iteration paths, multi-key HNP recovery curves, …
//! - `format_tree` — text-mode tree (Joux multicollision diagram).
//! - [`format_signed_bars`] — bipolar bar chart for signed values
//!   (Walsh spectra, linear biases, correlation coefficients).
//! - [`format_birthday_curve`] — ASCII line plot of `√n` collision
//!   cost vs number of trials.
//!
//! The AES-specific primitives in `aes::visualize` (state grid,
//! active-byte pattern, etc.) are re-exported here so callers don't
//! have to know they live in the AES subdirectory.

pub use crate::cryptanalysis::aes::visualize::{
    format_active_pattern, format_boomerang_quartet_diagram, format_histogram,
    format_recovery_progress, format_round_bars, format_state_grid, format_table_4bit_heatmap,
    format_table_8bit_summary, format_trail, hex,
};

// ── Generic matrix heat-map ──────────────────────────────────────────

/// Render an `m × n` matrix of `f64` values as an ASCII heat-map.
/// 5-level shading: `· ░ ▒ ▓ █` (zero/near-zero → max).
///
/// Useful for:
/// - Lattice basis matrices (entries can be `i64`-cast-to-f64).
/// - Sparse relation matrices in index calculus.
/// - Avalanche matrices.
pub fn format_matrix_heatmap(matrix: &[Vec<f64>], title: &str, label_cols: bool) -> String {
    if matrix.is_empty() {
        return String::from("(empty matrix)\n");
    }
    let m = matrix.len();
    let n = matrix[0].len();
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    // Find max absolute value for normalisation.
    let max_abs: f64 = matrix
        .iter()
        .flatten()
        .map(|v| v.abs())
        .fold(0.0, f64::max)
        .max(1e-12);
    s.push_str("```\n");
    if label_cols {
        s.push_str("       ");
        for c in 0..n {
            s.push_str(&format!(" {:>3}", c));
        }
        s.push('\n');
    }
    use crate::visualize::color::{heatmap_color, paint_char};
    for r in 0..m {
        s.push_str(&format!(" {:>4}  ", r));
        for c in 0..n {
            let v = matrix[r][c].abs();
            let lv = (v / max_abs * 4.0).round() as usize;
            let lv = lv.min(4);
            let ch = ['·', '░', '▒', '▓', '█'][lv];
            s.push_str("   ");
            s.push_str(&paint_char(ch, heatmap_color(lv)));
        }
        s.push('\n');
    }
    s.push_str("```\n");
    s.push_str(&format!(
        "Matrix: {} × {}, max |entry| ≈ {:.3}\n",
        m, n, max_abs
    ));
    s
}

// ── Path trajectory (Pollard rho, sample walks) ──────────────────────

/// Render a sequence of (x, y) points as a 2-D scatter on a small
/// terminal grid.  Used for Pollard rho iteration paths, where x is
/// the iteration index and y is some scalar.
///
/// `width` / `height` are the grid extents in cells.  Points outside
/// the data range get clipped.
pub fn format_path_trajectory(
    points: &[(f64, f64)],
    title: &str,
    width: usize,
    height: usize,
) -> String {
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    if points.is_empty() {
        s.push_str("(no points)\n");
        return s;
    }
    let min_x = points.iter().map(|p| p.0).fold(f64::INFINITY, f64::min);
    let max_x = points.iter().map(|p| p.0).fold(f64::NEG_INFINITY, f64::max);
    let min_y = points.iter().map(|p| p.1).fold(f64::INFINITY, f64::min);
    let max_y = points.iter().map(|p| p.1).fold(f64::NEG_INFINITY, f64::max);
    let dx = (max_x - min_x).max(1e-12);
    let dy = (max_y - min_y).max(1e-12);
    let mut grid: Vec<Vec<char>> = vec![vec![' '; width]; height];
    for &(x, y) in points {
        let cx = (((x - min_x) / dx) * (width as f64 - 1.0)).round() as usize;
        let cy = (((max_y - y) / dy) * (height as f64 - 1.0)).round() as usize;
        if cx < width && cy < height {
            grid[cy][cx] = if grid[cy][cx] == ' ' { '·' } else { '●' };
        }
    }
    s.push_str("```\n");
    use crate::visualize::color::{paint_char, FG_BRIGHT_CYAN, FG_BRIGHT_MAGENTA};
    for row in &grid {
        s.push_str("  ");
        for &c in row {
            if c == '●' {
                s.push_str(&paint_char(c, FG_BRIGHT_MAGENTA));
            } else if c == '·' {
                s.push_str(&paint_char(c, FG_BRIGHT_CYAN));
            } else {
                s.push(c);
            }
        }
        s.push('\n');
    }
    s.push_str("  └");
    for _ in 0..width {
        s.push('─');
    }
    s.push('\n');
    s.push_str(&format!(
        "  x ∈ [{:.3}, {:.3}], y ∈ [{:.3}, {:.3}], {} points\n",
        min_x,
        max_x,
        min_y,
        max_y,
        points.len()
    ));
    s.push_str("```\n");
    s
}

// ── Signed-bar chart (bipolar) ───────────────────────────────────────

/// Render a sequence of signed `i32` values as a bipolar bar chart
/// with the zero line in the middle.  Used for Walsh-Hadamard
/// spectra (signed) and linear-cryptanalysis biases.
///
/// Example:
///
/// ```text
/// idx  0 │                  ╞══════ +32
/// idx  1 │           ════╡             -16
/// idx  2 │                  ╞══════ +32
/// idx  3 │                  ╞ +2
/// ```
pub fn format_signed_bars(values: &[i32], title: &str, max_width: usize) -> String {
    let mut s = String::new();
    if !title.is_empty() {
        s.push_str(&format!("**{}**\n\n", title));
    }
    let max_abs = values.iter().map(|v| v.abs()).max().unwrap_or(1).max(1);
    let half = max_width / 2;
    s.push_str("```\n");
    use crate::visualize::color::{paint, signed_color};
    for (i, &v) in values.iter().enumerate() {
        let bar_width = ((v.unsigned_abs() as usize) * half) / (max_abs as usize);
        let bar_str = "═".repeat(bar_width);
        let colored_bar = paint(&bar_str, signed_color(v));
        let mut line = String::new();
        if v >= 0 {
            line.push_str(&" ".repeat(half));
            line.push('│');
            line.push_str(&colored_bar);
        } else {
            let pad = half.saturating_sub(bar_width);
            line.push_str(&" ".repeat(pad));
            line.push_str(&colored_bar);
            line.push('│');
            line.push_str(&" ".repeat(half));
        }
        s.push_str(&format!(
            "  idx {:>3}  {}  {}\n",
            i,
            line,
            paint(&format!("{:>+5}", v), signed_color(v))
        ));
    }
    s.push_str("```\n");
    s
}

// ── ASCII tree (Joux multicollision, attack-graph diagrams) ──────────

/// Render a binary tree where each node is labeled, edges go down-
/// left and down-right.  Used for Joux multicollision visualization:
/// each internal node is a chain step where two different blocks
/// produce the same compression state.
///
/// Returns a multi-line ASCII art diagram.  `depth` controls how
/// many levels to render (each level doubles the leaf count).
pub fn format_joux_tree(depth: usize) -> String {
    let mut s = String::new();
    s.push_str("```\n");
    s.push_str("Joux multicollision chain ");
    s.push_str(&format!(
        "({} steps → 2^{} = {} equivalent messages)\n\n",
        depth,
        depth,
        1usize << depth
    ));
    // Render as a horizontal chain with "choice points".
    s.push_str("  IV ");
    for i in 0..depth {
        s.push_str(&format!("──┬── state_{} ", i + 1));
    }
    s.push_str("──┐\n");
    s.push_str("     ");
    for i in 0..depth {
        s.push_str("  │  (choose B_a^{");
        s.push_str(&format!("{}", i + 1));
        s.push('}');
        let _ = i;
        s.push_str("        ");
    }
    s.push_str("     ");
    s.push('\n');
    s.push_str("     ");
    for _ in 0..depth {
        s.push_str("  │   or B_b^{·}");
        s.push_str("           ");
    }
    s.push_str("     ");
    s.push('\n');
    s.push_str(&format!(
        "Each of the {} step{} offers a free choice of block,\n\
         and all 2^{} combinations hash to the same final digest.\n",
        depth,
        if depth == 1 { "" } else { "s" },
        depth,
    ));
    s.push_str("```\n");
    s
}

// ── Birthday-attack expected-collision curve ─────────────────────────

/// Render the **birthday paradox cumulative-probability curve** for
/// a hash truncated to `b` bits over `max_trials` queries.  Shows the
/// theoretical `1 − exp(−n² / 2 · 2^b)` vs trial count.
pub fn format_birthday_curve(b: u32, max_trials: usize, width: usize) -> String {
    let mut s = String::new();
    s.push_str(&format!(
        "**Birthday-collision expected probability** (b = {} bits)\n\n",
        b
    ));
    let n_b = (1u128 << b.min(63)) as f64; // domain size
    let mut points = Vec::new();
    for step in 0..=width {
        let n = (step as f64 / width as f64) * (max_trials as f64);
        let p = 1.0 - (-n * n / (2.0 * n_b)).exp();
        points.push((n, p));
    }
    s.push_str(&format_path_trajectory(&points, "", width.max(20), 12));
    s.push_str(&format!(
        "  √(2^{}) ≈ {:.0} trials gives Pr[collision] ≈ 0.39 (the rule of thumb)\n",
        b,
        2f64.powf(b as f64 / 2.0)
    ));
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matrix_heatmap_renders_with_negatives() {
        let m = vec![vec![1.0, -2.0, 3.0], vec![-4.0, 0.0, 1.5]];
        let s = format_matrix_heatmap(&m, "Test matrix", true);
        assert!(s.contains("Test matrix"));
        assert!(s.contains("█")); // max |entry| = 4 → max shading present
        assert!(s.contains("2 × 3") || s.contains("Matrix: 2 × 3"));
    }

    #[test]
    fn path_trajectory_renders_simple_line() {
        let points = vec![(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)];
        let s = format_path_trajectory(&points, "Diagonal", 20, 8);
        assert!(s.contains("Diagonal"));
        assert!(s.contains("·") || s.contains("●"));
        assert!(s.contains("4 points"));
    }

    #[test]
    fn signed_bars_show_both_directions() {
        let s = format_signed_bars(&[5, -3, 8, 0, -8], "Walsh", 30);
        assert!(s.contains("Walsh"));
        assert!(s.contains("+5"));
        assert!(s.contains("-3"));
        assert!(s.contains("+8"));
        assert!(s.contains("-8"));
    }

    #[test]
    fn joux_tree_renders() {
        let s = format_joux_tree(3);
        assert!(s.contains("Joux multicollision"));
        assert!(s.contains("2^3"));
        assert!(s.contains("state_1"));
        assert!(s.contains("state_3"));
    }

    #[test]
    fn birthday_curve_renders_for_known_bits() {
        let s = format_birthday_curve(16, 1024, 40);
        assert!(s.contains("Birthday"));
        assert!(s.contains("b = 16"));
    }
}
