//! Boolean-function utilities used by S-box and full-cipher analysis.
//!
//! All functions operate on a "truth table" representation:
//! `Vec<u8>` of length `2^n`, where entry `x` holds `f(x) ∈ {0, 1}`
//! (or any `u8` for non-Boolean codomains where noted).  This is the
//! representation cryptographers conventionally use because it makes
//! the Walsh–Hadamard transform a `2^n`-step in-place computation.

/// Walsh–Hadamard transform of a `±1`-valued function.
///
/// Input is interpreted via the standard `f → (-1)^f(x)` lift: a `0`
/// entry in `truth_table` becomes `+1`, a `1` entry becomes `-1`.
/// The output `W[a]` is then
/// `W(a) = Σ_x (-1)^(a·x ⊕ f(x))`,
/// the "Walsh coefficient" of `f` at frequency `a`.
///
/// This is the workhorse of linear cryptanalysis: for a Boolean
/// component function `b · S`, the maximum |Walsh coefficient| over
/// all `a` is twice the maximum LAT entry, and `2^(n-1) - max|W|/2`
/// is the function's nonlinearity.
///
/// Length must be a power of 2 ≤ 2^20 (1 Mi).  Panics otherwise.
///
/// # Complexity
/// Time `O(n · 2^n)`, in-place; allocates a single `Vec<i64>`.
pub fn walsh_hadamard(truth_table: &[u8]) -> Vec<i64> {
    let n = truth_table.len();
    assert!(
        n.is_power_of_two(),
        "truth table length must be a power of 2"
    );
    assert!(n <= 1 << 20, "truth table too large; max 2^20 entries");

    let mut out: Vec<i64> = truth_table
        .iter()
        .map(|&v| if v & 1 == 0 { 1i64 } else { -1i64 })
        .collect();

    // In-place radix-2 fast Walsh–Hadamard.  Identical structure to FFT
    // butterflies but with ± instead of complex roots of unity.
    let mut h = 1;
    while h < n {
        let mut i = 0;
        while i < n {
            for j in i..(i + h) {
                let a = out[j];
                let b = out[j + h];
                out[j] = a + b;
                out[j + h] = a - b;
            }
            i += h * 2;
        }
        h *= 2;
    }
    out
}

/// Compute the Algebraic Normal Form coefficients of a Boolean function.
///
/// ANF expresses `f(x)` as a sum (XOR) of multilinear monomials:
/// `f(x) = ⊕_{S ⊆ {0,...,n-1}} a_S · ∏_{i ∈ S} x_i`.
/// Returns a `Vec<u8>` of length `2^n` where index `mask` holds
/// `a_S` for `S = bits set in mask`.
///
/// Computed via the Möbius transform — same butterfly shape as Walsh
/// but with XOR instead of `±`.  In-place, allocates one `Vec<u8>`.
pub fn anf_coefficients(truth_table: &[u8]) -> Vec<u8> {
    let n = truth_table.len();
    assert!(
        n.is_power_of_two(),
        "truth table length must be a power of 2"
    );
    let mut out: Vec<u8> = truth_table.iter().map(|&v| v & 1).collect();

    let mut h = 1;
    while h < n {
        let mut i = 0;
        while i < n {
            for j in i..(i + h) {
                out[j + h] ^= out[j];
            }
            i += h * 2;
        }
        h *= 2;
    }
    out
}

/// Algebraic degree of a Boolean function = `max popcount(mask)` over
/// all monomials with non-zero coefficient in the ANF.
///
/// Higher degree resists higher-order differential and integral
/// attacks.  An `n`-bit balanced Boolean function reaches at most
/// degree `n`; affine functions have degree ≤ 1.
pub fn algebraic_degree(truth_table: &[u8]) -> u32 {
    let anf = anf_coefficients(truth_table);
    let mut deg = 0;
    for (mask, &c) in anf.iter().enumerate() {
        if c & 1 == 1 {
            let d = (mask as u64).count_ones();
            if d > deg {
                deg = d;
            }
        }
    }
    deg
}

#[cfg(test)]
mod tests {
    use super::*;

    /// AND function over 2 bits: `f(x0, x1) = x0 ∧ x1`.
    /// Truth table indexed as `(x1, x0)` (LSB-first): f(00)=0, f(01)=0, f(10)=0, f(11)=1.
    #[test]
    fn anf_of_and_is_x0_times_x1() {
        let tt = vec![0, 0, 0, 1];
        let anf = anf_coefficients(&tt);
        // Expected: a_{00} = 0, a_{01} = 0, a_{10} = 0, a_{11} = 1.
        assert_eq!(anf, vec![0, 0, 0, 1]);
    }

    #[test]
    fn anf_of_xor_is_x0_xor_x1() {
        let tt = vec![0, 1, 1, 0];
        let anf = anf_coefficients(&tt);
        assert_eq!(anf, vec![0, 1, 1, 0]);
    }

    #[test]
    fn algebraic_degree_of_and_is_2() {
        let tt = vec![0, 0, 0, 1];
        assert_eq!(algebraic_degree(&tt), 2);
    }

    #[test]
    fn algebraic_degree_of_xor_is_1() {
        let tt = vec![0, 1, 1, 0];
        assert_eq!(algebraic_degree(&tt), 1);
    }

    #[test]
    fn walsh_of_constant_zero_is_concentrated_at_origin() {
        // f ≡ 0 → all (-1)^0 = +1, so W(0) = n, W(a≠0) = 0.
        let tt = vec![0u8; 16];
        let w = walsh_hadamard(&tt);
        assert_eq!(w[0], 16);
        for &v in &w[1..] {
            assert_eq!(v, 0);
        }
    }

    #[test]
    fn walsh_of_xor_function_is_concentrated() {
        // f(x) = x_0 XOR x_1 XOR x_2 XOR x_3 (parity).  Walsh coefficient
        // is non-zero only at the all-ones mask.
        let n: usize = 16;
        let tt: Vec<u8> = (0..n)
            .map(|x| ((x as u32).count_ones() & 1) as u8)
            .collect();
        let w = walsh_hadamard(&tt);
        // For parity function, only the "all-ones" Walsh coefficient is non-zero.
        for (a, &v) in w.iter().enumerate() {
            if a == n - 1 {
                assert_eq!(v.unsigned_abs(), n as u64);
            } else {
                assert_eq!(v, 0, "expected W({}) = 0, got {}", a, v);
            }
        }
    }
}
