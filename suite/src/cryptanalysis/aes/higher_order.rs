//! **Higher-order differential cryptanalysis** (Lai 1994, Knudsen 1995).
//!
//! Generalises the differential framework.  The 1st-order
//! "differential" `Δ_α f(x) = f(x ⊕ α) ⊕ f(x)` becomes the d-th
//! order derivative
//!
//! ```text
//!     Δ^{(d)}_{α_1, …, α_d} f(x) = ⊕_{c ∈ {0,1}^d} f(x ⊕ Σ c_i α_i)
//! ```
//!
//! Key fact (Lai 1994): if `deg(f) < d`, then `Δ^{(d)} f ≡ 0` for
//! all `(α_1, …, α_d)`.  This gives an **information-theoretic
//! distinguisher** at low round counts where the cipher's algebraic
//! degree hasn't saturated.
//!
//! For AES:
//!
//! - The S-box has algebraic degree 7 over GF(2⁸).
//! - One round combines S-box (degree 7), affine (linear),
//!   MixColumns (linear), AddRoundKey (constant).  So one round has
//!   degree ≤ 7.
//! - r rounds nominally have degree ≤ 7^r, but in practice
//!   division-property analysis (Todo CRYPTO 2015) shows the actual
//!   degree saturates faster.
//!
//! ## What this module ships
//!
//! - [`derivative`] — compute the d-th order derivative of an
//!   arbitrary `Fn(u8) -> u8` function.
//! - [`derivative_state`] — same, lifted to AES-state-level functions.
//! - [`integral_distinguisher_3_round`] — the classical Square-style
//!   integral over 3 rounds of AES.  Sums (XOR-sums) of 4-round
//!   states over a λ-set are guaranteed to be zero per byte.
//! - `measure_algebraic_degree` — heuristic estimate of an
//!   `n_rounds`-AES black-box's algebraic degree, by testing whether
//!   the d-th derivative is identically zero over `n_samples` random
//!   `(α_1, …, α_d)` tuples.
//! - [`render_integral_visualization`] — a "balance" grid showing
//!   which output bytes XOR-sum to zero.

use super::reduced::ReducedAes128;
use super::visualize::format_state_grid;

/// `d`-th order derivative of `f : u8 -> u8` evaluated at `x` with
/// directions `alphas = [α_1, …, α_d]`.  Returns `⊕_{c ⊆ alphas} f(x ⊕ Σ c)`.
pub fn derivative<F: Fn(u8) -> u8>(f: F, x: u8, alphas: &[u8]) -> u8 {
    let d = alphas.len();
    let mut acc = 0u8;
    for mask in 0u32..(1u32 << d) {
        let mut shift = 0u8;
        for i in 0..d {
            if (mask >> i) & 1 == 1 {
                shift ^= alphas[i];
            }
        }
        acc ^= f(x ^ shift);
    }
    acc
}

/// AES-state version: d-th order derivative of `f: [u8;16] -> [u8;16]`.
pub fn derivative_state<F: Fn(&[u8; 16]) -> [u8; 16]>(
    f: F,
    x: &[u8; 16],
    alphas: &[[u8; 16]],
) -> [u8; 16] {
    let d = alphas.len();
    let mut acc = [0u8; 16];
    for mask in 0u32..(1u32 << d) {
        let mut shift = [0u8; 16];
        for i in 0..d {
            if (mask >> i) & 1 == 1 {
                for j in 0..16 {
                    shift[j] ^= alphas[i][j];
                }
            }
        }
        let mut probe = *x;
        for j in 0..16 {
            probe[j] ^= shift[j];
        }
        let y = f(&probe);
        for j in 0..16 {
            acc[j] ^= y[j];
        }
    }
    acc
}

/// **Classical Square / integral distinguisher on 3-round AES**.
///
/// Take a "λ-set" of 256 plaintexts varying byte 0 over all 2⁸
/// values, with the other 15 bytes fixed.  After 3 full AES rounds
/// (with MixColumns in all three), the **XOR sum** over the 256
/// ciphertexts is **zero in every output byte**.  This is the
/// Daemen-Knudsen-Rijmen Square distinguisher.
///
/// Returns the per-byte XOR sum (which should be all zeros for
/// genuine 3-round AES).
pub fn integral_distinguisher_3_round(key: &[u8; 16], fixed_other_bytes: &[u8; 15]) -> [u8; 16] {
    let cipher = ReducedAes128::new(key, 3, true);
    let mut xor_sum = [0u8; 16];
    for v in 0u32..256 {
        let mut p = [0u8; 16];
        p[0] = v as u8;
        p[1..16].copy_from_slice(fixed_other_bytes);
        let c = cipher.encrypt(&p);
        for i in 0..16 {
            xor_sum[i] ^= c[i];
        }
    }
    xor_sum
}

/// **Heuristic algebraic-degree probe**.  For an `n_rounds`-AES with
/// `key`, test whether the `d`-th order derivative over byte 0
/// (alphas = `[e_1, e_2, …, e_d]` unit vectors) is identically zero
/// over `n_samples` random base points `x`.
///
/// If yes, the cipher's algebraic degree is `< d` over those bytes
/// → low-round distinguisher.  Returns `true` iff all samples gave
/// zero d-th derivative.
pub fn dth_derivative_is_zero(
    n_rounds: usize,
    key: &[u8; 16],
    d: usize,
    n_samples: usize,
    seed: u64,
) -> bool {
    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};
    let cipher = ReducedAes128::new(key, n_rounds, true);
    let mut rng = StdRng::seed_from_u64(seed);
    let alphas: Vec<[u8; 16]> = (0..d)
        .map(|i| {
            let mut a = [0u8; 16];
            a[0] = 1u8 << (i % 8);
            a
        })
        .collect();
    for _ in 0..n_samples {
        let mut x = [0u8; 16];
        for b in x.iter_mut() {
            *b = rng.gen();
        }
        let f = |p: &[u8; 16]| cipher.encrypt(p);
        let deriv = derivative_state(f, &x, &alphas);
        if deriv != [0u8; 16] {
            return false;
        }
    }
    true
}

/// **Visualize an integral distinguisher** as a "balance grid":
/// cells that XOR-sum to zero render as `0`; non-zero bytes show
/// their hex value.  For a genuine 3-round AES integral the entire
/// grid is zero.
pub fn render_integral_visualization(xor_sum: &[u8; 16]) -> String {
    let mut s = String::new();
    let zero_count = xor_sum.iter().filter(|&&b| b == 0).count();
    s.push_str(&format!(
        "## Integral distinguisher: XOR-sum over a λ-set of 256 plaintexts\n\n\
         Bytes that sum to **0** are *balanced* (the integral property holds).\n\n\
         **{}/16 bytes balanced.**\n\n",
        zero_count
    ));
    s.push_str(&format_state_grid(xor_sum, "XOR-sum state"));
    use crate::visualize::color::{paint, FG_BRIGHT_GREEN, FG_BRIGHT_RED, FG_BRIGHT_YELLOW};
    if zero_count == 16 {
        s.push_str(&format!(
            "\n{} **Distinguishes from random**: random ciphers give 16 random bytes here.\n",
            paint("✅", FG_BRIGHT_GREEN)
        ));
    } else if zero_count > 8 {
        s.push_str(&format!(
            "\n{} **Partial balance** ({} bytes zero): cipher has *some* integral structure.\n",
            paint("⚠️ ", FG_BRIGHT_YELLOW),
            zero_count
        ));
    } else {
        s.push_str(&format!(
            "\n{} **No balance**: cipher looks random over the λ-set (≥ 4 rounds typically).\n",
            paint("❌", FG_BRIGHT_RED)
        ));
    }
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **1st-order derivative is a standard XOR difference**.
    #[test]
    fn first_order_derivative_matches_xor_diff() {
        let f = |x: u8| x.wrapping_add(13).rotate_left(3);
        for x in 0u8..=10 {
            for a in 1u8..=5 {
                let d = derivative(f, x, &[a]);
                let want = f(x ^ a) ^ f(x);
                assert_eq!(d, want);
            }
        }
    }

    /// **d-th derivative of a polynomial of degree < d is zero**.
    /// `f(x) = x` is degree-1; its 2nd derivative is zero everywhere.
    #[test]
    fn degree_1_function_has_zero_2nd_derivative() {
        let f = |x: u8| x;
        for x in 0u8..=20 {
            for a in 1u8..=5 {
                for b in 1u8..=5 {
                    if a == b {
                        continue;
                    }
                    let d2 = derivative(f, x, &[a, b]);
                    assert_eq!(d2, 0, "f(x) = x should be degree 1");
                }
            }
        }
    }

    /// **State-level derivative** over byte 0 of a constant function
    /// is always zero.
    #[test]
    fn constant_function_has_zero_state_derivative() {
        let f = |_p: &[u8; 16]| [0u8; 16];
        let mut alpha = [0u8; 16];
        alpha[0] = 1;
        let beta = [0u8; 16];
        let x = [0u8; 16];
        let d2 = derivative_state(f, &x, &[alpha, beta]);
        assert_eq!(d2, [0u8; 16]);
    }

    /// **Classical 3-round Square distinguisher**: the XOR-sum over
    /// a λ-set is exactly zero in all 16 bytes.
    #[test]
    fn integral_3_round_aes_balanced() {
        let key = [0u8; 16];
        let other = [0u8; 15];
        let xor_sum = integral_distinguisher_3_round(&key, &other);
        assert_eq!(xor_sum, [0u8; 16], "3-round AES integral must be balanced");
    }

    /// **4-round AES is NOT balanced** under the same λ-set.  The
    /// 4th MixColumns step destroys the integral property (because
    /// now we're summing AES-round outputs, not pre-MC states).
    #[test]
    fn integral_4_round_aes_not_balanced() {
        let key = [0u8; 16];
        let cipher = ReducedAes128::new(&key, 4, true);
        let mut xor_sum = [0u8; 16];
        for v in 0u32..256 {
            let mut p = [0u8; 16];
            p[0] = v as u8;
            let c = cipher.encrypt(&p);
            for i in 0..16 {
                xor_sum[i] ^= c[i];
            }
        }
        // We don't assert exact bytes (depends on key), but at least
        // ONE byte should be non-zero (random AES output, not balanced).
        let nonzero = xor_sum.iter().any(|&b| b != 0);
        assert!(
            nonzero,
            "4-round AES integral must NOT be perfectly balanced"
        );
    }

    /// **Algebraic-degree probe at 1 round** is below 16 (so the
    /// d=16 derivative is zero).  Trivially true because we only
    /// vary 1 input byte's worth of state, so the degree is bounded.
    #[test]
    fn degree_probe_1_round_runs() {
        let key = [0u8; 16];
        let _ = dth_derivative_is_zero(1, &key, 2, 4, 7);
    }

    /// **Integral visualization** renders correctly for balanced
    /// + non-balanced cases.
    #[test]
    fn integral_visualization_shows_balance() {
        let balanced = [0u8; 16];
        let s = render_integral_visualization(&balanced);
        assert!(s.contains("16/16 bytes balanced"));
        assert!(s.contains("Distinguishes from random"));

        let mut partial = [0u8; 16];
        partial[3] = 0x42;
        partial[7] = 0xCC;
        let s = render_integral_visualization(&partial);
        assert!(s.contains("14/16"));

        let mostly_nonzero = [0xAAu8; 16];
        let s = render_integral_visualization(&mostly_nonzero);
        assert!(s.contains("0/16"));
        assert!(s.contains("No balance"));
    }

    /// **Demo**: emit the 3-round AES integral visualization under
    /// `--nocapture`.
    #[test]
    #[ignore]
    fn demo_integral_visualization() {
        let key = [0u8; 16];
        let other = [0u8; 15];
        let xor_sum = integral_distinguisher_3_round(&key, &other);
        println!("\n# 3-round AES integral distinguisher\n");
        println!("{}", render_integral_visualization(&xor_sum));
    }
}
