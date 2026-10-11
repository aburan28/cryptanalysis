//! **Elliptic-curve visualizations** — scatter plot of points on a
//! toy `F_p` curve, point doubling/addition geometric diagrams,
//! scalar-multiplication double-and-add trace, and an ECDSA
//! sign/verify flow diagram.

// ── Toy curve scatter ────────────────────────────────────────────────

/// Enumerate all affine points on `y² = x³ + ax + b mod p` and
/// render them as an ASCII scatter on a `p × p` grid (downscaled to
/// `width × height`).  For demos we use small primes (`p ≤ 127`).
pub fn demo_toy_curve_scatter(p: u64, a: u64, b: u64) -> String {
    let mut s = format!("# Points on E: y² = x³ + {}x + {} mod {}\n\n", a, b, p);
    let mut pts: Vec<(u64, u64)> = Vec::new();
    for x in 0..p {
        let rhs = (x * x % p * x % p + a * x % p + b) % p;
        for y in 0..p {
            if y * y % p == rhs {
                pts.push((x, y));
            }
        }
    }
    s.push_str(&format!(
        "\n**Group order**: {} affine points + 1 point at infinity = {}\n\n",
        pts.len(),
        pts.len() + 1,
    ));
    // Render as ASCII grid (p × p, downscaled to fit ~60-wide).
    let max_dim = 60usize;
    let scale = (p as usize).max(1).div_ceil(max_dim);
    let w = (p as usize).div_ceil(scale);
    let h = w;
    let mut grid: Vec<Vec<char>> = vec![vec![' '; w]; h];
    for &(x, y) in &pts {
        let gx = (x as usize) / scale;
        let gy = h - 1 - ((y as usize) / scale);
        if gx < w && gy < h {
            grid[gy][gx] = '●';
        }
    }
    s.push_str("```\n");
    // y-axis label
    s.push_str("  y\n");
    s.push_str("  ▲\n");
    use crate::visualize::color::{paint_char, FG_BRIGHT_MAGENTA};
    for row in &grid {
        s.push_str("  │");
        for &c in row {
            if c == '●' {
                s.push_str(&paint_char(c, FG_BRIGHT_MAGENTA));
            } else {
                s.push(c);
            }
            s.push(' ');
        }
        s.push('\n');
    }
    s.push_str("  └");
    for _ in 0..(2 * w + 1) {
        s.push('─');
    }
    s.push_str("► x\n");
    s.push_str("```\n");
    // Highlight symmetry.
    s.push_str(
        "\nObserve: for every point `(x, y)` there is its negative `(x, p - y)` — the curve is symmetric about the horizontal `y = p/2` line (modular reflection).\n",
    );
    s
}

// ── Point doubling / addition diagram ────────────────────────────────

/// Render the geometric intuition behind point doubling and addition.
pub fn demo_point_operations() -> String {
    let mut s = String::from("# Elliptic-curve group law (geometric)\n\n");
    s.push_str("## Point addition: `P + Q = R`\n\n");
    s.push_str("```\n");
    s.push_str("                                    \n");
    s.push_str("           ●─ P                     \n");
    s.push_str("            \\                       \n");
    s.push_str("             \\                      \n");
    s.push_str("    ────────●───────── line through P and Q\n");
    s.push_str("              \\  Q                  \n");
    s.push_str("               \\                    \n");
    s.push_str("                ●─ third intersection -R\n");
    s.push_str("                                    \n");
    s.push_str("           ●─ R = reflect -R across y=0\n");
    s.push_str("                                    \n");
    s.push_str("```\n");
    s.push_str(
        "\n_Slope λ = (y_Q - y_P) / (x_Q - x_P);  x_R = λ² - x_P - x_Q;  y_R = λ(x_P - x_R) - y_P._\n\n",
    );
    s.push_str("## Point doubling: `2P = R`\n\n");
    s.push_str("```\n");
    s.push_str("                                    \n");
    s.push_str("           ●─ P                     \n");
    s.push_str("           /╲                       \n");
    s.push_str("          / ──── tangent line at P  \n");
    s.push_str("         /                          \n");
    s.push_str("    ────●────── intersection -2P    \n");
    s.push_str("                                    \n");
    s.push_str("    ────●────── 2P = reflect -2P    \n");
    s.push_str("```\n");
    s.push_str(
        "\n_Slope λ = (3x_P² + a) / (2y_P);  x_R = λ² - 2x_P;  y_R = λ(x_P - x_R) - y_P._\n",
    );
    s
}

// ── Scalar multiplication trace (double-and-add) ─────────────────────

/// Render the bits of a scalar `k` with a ladder of "D" (double) and
/// "DA" (double-and-add) operations.
pub fn demo_scalar_mul_ladder(k: u32) -> String {
    let mut s = format!(
        "# Scalar multiplication ladder: compute k·P with k = {} (binary {:b})\n\n",
        k, k
    );
    s.push_str(
        "Left-to-right double-and-add: process the MSB first.  For each bit, **double** \
         the accumulator; if the bit is 1, additionally **add** P.  Total ops: 1 \
         double + 1-or-0 add per bit ≈ 1.5 log₂(k) group operations.\n\n",
    );
    s.push_str("```\n");
    s.push_str("  bit  op   accumulator    description\n");
    s.push_str("  ────────────────────────────────────────\n");
    let n_bits = 32 - k.leading_zeros();
    let mut value: u64 = 0;
    let mut doubles = 0;
    let mut adds = 0;
    s.push_str("   init Q = O                  (point at infinity)\n");
    for i in (0..n_bits).rev() {
        let bit = (k >> i) & 1;
        // Double.
        value *= 2;
        doubles += 1;
        s.push_str(&format!(
            "    {:>2}  D    Q = {}·P            double\n",
            i, value
        ));
        if bit == 1 {
            // Add.
            value += 1;
            adds += 1;
            s.push_str(&format!(
                "    {:>2}  A    Q = {}·P            add P\n",
                i, value
            ));
        }
    }
    s.push_str("  ────────────────────────────────────────\n");
    s.push_str(&format!(
        "  final Q = {}·P                       total = {} doubles + {} adds = {} ops\n",
        value,
        doubles,
        adds,
        doubles + adds,
    ));
    s.push_str("```\n");
    s.push_str(
        "\n**Side-channel concern**: the count of adds equals the popcount of `k`, leaking \
         the Hamming weight of the private key via timing or power.  Constant-time scalar \
         mul (Montgomery ladder, complete-formula coordinates) does **D + A** every step \
         regardless of the bit.\n",
    );
    s
}

// ── ECDSA sign/verify flow ───────────────────────────────────────────

pub fn demo_ecdsa_flow() -> String {
    let mut s = String::from("# ECDSA sign / verify dataflow\n\n");
    s.push_str("## Sign(d, m):\n\n```\n");
    s.push_str("  1.  z = LSB(H(m), log2(n))\n");
    s.push_str("  2.  k ←$ [1, n-1]                  (or RFC 6979 deterministic)\n");
    s.push_str("  3.  (x_R, y_R) = k·G                ← scalar mul on curve\n");
    s.push_str("  4.  r = x_R mod n                   ← if r = 0 retry\n");
    s.push_str("  5.  s = k⁻¹(z + r·d) mod n          ← if s = 0 retry\n");
    s.push_str("                                                 \n");
    s.push_str("  output (r, s)\n");
    s.push_str("```\n\n");
    s.push_str("## Verify(Q, m, r, s):\n\n```\n");
    s.push_str("  1.  z = LSB(H(m), log2(n))\n");
    s.push_str("  2.  w  = s⁻¹ mod n\n");
    s.push_str("  3.  u₁ = z·w mod n\n");
    s.push_str("  4.  u₂ = r·w mod n\n");
    s.push_str("  5.  (x', y') = u₁·G + u₂·Q          ← two scalar muls + add\n");
    s.push_str("  6.  accept iff x' mod n = r\n");
    s.push_str("```\n\n");
    s.push_str(
        "**Key safety pitfall**: if you reuse `k` across two signatures of different \
         messages, the private key falls out directly — `d = (s₁·z₂ - s₂·z₁) / (r·(s₁ - s₂))`.  \
         Sony PS3 / Bitcoin Android wallet 2013 / multiple production breaches all came \
         from this exact bug.\n",
    );
    s
}

// ── Aggregate ────────────────────────────────────────────────────────

pub fn run_all_ecc_demos() -> String {
    let mut s = String::new();
    s.push_str("# Elliptic-curve visual-demo bundle\n\n---\n\n");
    s.push_str(&demo_toy_curve_scatter(31, 1, 1));
    s.push_str("\n---\n\n");
    s.push_str(&demo_point_operations());
    s.push_str("\n---\n\n");
    s.push_str(&demo_scalar_mul_ladder(13));
    s.push_str("\n---\n\n");
    s.push_str(&demo_ecdsa_flow());
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;

    #[test]
    fn curve_scatter_renders_points() {
        let s = demo_toy_curve_scatter(31, 1, 1);
        assert!(s.contains("y² = x³ + 1x + 1 mod 31"));
        assert!(s.contains("●"));
        assert!(s.contains("Group order"));
    }

    #[test]
    fn point_ops_diagram_renders_both() {
        let s = demo_point_operations();
        assert!(s.contains("Point addition"));
        assert!(s.contains("Point doubling"));
        assert!(s.contains("tangent"));
    }

    #[test]
    fn scalar_mul_ladder_renders_for_13() {
        let s = demo_scalar_mul_ladder(13);
        assert!(s.contains("k = 13"));
        // 13 in binary = 1101.  Should have 4 doubles + 3 adds.
        assert!(s.contains("4 doubles + 3 adds"));
    }

    #[test]
    fn ecdsa_flow_diagram_renders() {
        let s = demo_ecdsa_flow();
        assert!(s.contains("Sign"));
        assert!(s.contains("Verify"));
        assert!(s.contains("RFC 6979"));
        assert!(s.contains("Sony PS3"));
    }

    #[test]
    fn aggregate_runs_clean() {
        let s = run_all_ecc_demos();
        assert!(s.contains("Points on E"));
        assert!(s.contains("group law"));
        assert!(s.contains("Scalar multiplication ladder"));
        assert!(s.contains("ECDSA"));
    }

    #[test]
    #[ignore]
    fn demo_all_ecc_visuals() {
        println!("{}", run_all_ecc_demos());
    }

    // Stub to silence unused-import warnings.
    #[test]
    fn unused_biguint() {
        let _ = BigUint::from(1u32);
    }
}
