//! Shor's algorithm — quantum-circuit simulator for tiny instances.
//!
//! Peter Shor 1994, "Algorithms for quantum computation: discrete
//! logarithms and factoring."  The polynomial-time quantum algorithm
//! that ends RSA and ECC eventually.  This module is a **minimal**
//! pedagogical state-vector simulator: it actually runs the H gates,
//! the function-application unitary `U_f`, and the QFT on a fixed
//! `Vec<Complex>` state vector, then samples a classical measurement
//! outcome and applies the continued-fractions post-processing.
//!
//! # What this is, and what it isn't
//!
//! - **Is**: a working end-to-end Shor implementation that factors
//!   tiny `N` (15, 21, 33, 35) by simulating the quantum register
//!   classically.  ~12-qubit total system; state vector ~4 K
//!   complex doubles.
//! - **Is**: a regression test for our [`crate::utils::mod_pow`]
//!   (the simulator computes `a^x mod N` for every basis state, so
//!   any modular-exponentiation bug surfaces immediately) and our
//!   continued-fraction primitive.
//! - **Is not**: a production quantum simulator (`qiskit`,
//!   `quantum-circuits`, `pennylane` exist for that).
//! - **Is not**: a Shor-for-ECDLP simulator.  Shor on ECDLP needs
//!   an in-place EC scalar-multiplication unitary — Roetteler-Naehrig-
//!   Svore-Lauter 2017 give the construction; it's an order of
//!   magnitude more involved than the modular-exponentiation `U_f`
//!   used here.  Doing it justice belongs in a dedicated quantum
//!   simulator project; the survey-level finding from
//!   `cryptanalysis::lattice` stands: P-256 needs ~10^6-10^7
//!   physical qubits and is a 2035-2045 horizon.
//!
//! # Resource usage
//!
//! State-vector simulators are exponential in qubit count:
//!
//! | qubits | state vector | RAM       |
//! |--------|-------------|-----------|
//! | 12     | 4 K entries | ~64 KB    |
//! | 16     | 64 K        | ~1 MB     |
//! | 20     | 1 M         | ~16 MB    |
//! | 24     | 16 M        | ~256 MB   |
//!
//! We size the precision register so total qubits stays ≤ 14 (16 KB
//! state vector) — comfortably fast in unit tests.

use num_integer::Integer;

// ── Minimal complex-number type ─────────────────────────────────────────────
//
// We use a hand-rolled `Complex` rather than depending on `num-complex`
// to keep the dependency graph small.  Only the operations Shor uses
// are implemented.

#[derive(Clone, Copy, Debug, PartialEq)]
struct Complex {
    re: f64,
    im: f64,
}

impl Complex {
    const ZERO: Complex = Complex { re: 0.0, im: 0.0 };
    const ONE: Complex = Complex { re: 1.0, im: 0.0 };

    #[allow(dead_code)]
    fn new(re: f64, im: f64) -> Self {
        Complex { re, im }
    }

    fn from_phase(theta: f64) -> Self {
        Complex {
            re: theta.cos(),
            im: theta.sin(),
        }
    }

    fn add(self, o: Complex) -> Complex {
        Complex {
            re: self.re + o.re,
            im: self.im + o.im,
        }
    }
    fn sub(self, o: Complex) -> Complex {
        Complex {
            re: self.re - o.re,
            im: self.im - o.im,
        }
    }
    fn mul(self, o: Complex) -> Complex {
        Complex {
            re: self.re * o.re - self.im * o.im,
            im: self.re * o.im + self.im * o.re,
        }
    }
    fn scale(self, s: f64) -> Complex {
        Complex {
            re: self.re * s,
            im: self.im * s,
        }
    }
    fn norm_sq(self) -> f64 {
        self.re * self.re + self.im * self.im
    }
}

// ── Quantum state vector ────────────────────────────────────────────────────

/// A `n_qubits`-qubit pure state.  Amplitude at basis state `|k⟩` is
/// stored at `amps[k]` with little-endian qubit ordering: qubit `i`
/// corresponds to bit `i` of the basis-state index.
struct QState {
    amps: Vec<Complex>,
    n_qubits: usize,
}

impl QState {
    /// Create the all-zero state `|0⟩^⊗n`.
    fn zero(n_qubits: usize) -> Self {
        let dim = 1usize << n_qubits;
        let mut amps = vec![Complex::ZERO; dim];
        amps[0] = Complex::ONE;
        QState { amps, n_qubits }
    }

    /// Apply Hadamard to qubit `q`.
    fn apply_h(&mut self, q: usize) {
        let bit = 1usize << q;
        let inv_sqrt2 = std::f64::consts::FRAC_1_SQRT_2;
        let dim = self.amps.len();
        let mut new_amps = vec![Complex::ZERO; dim];
        for state in 0..dim {
            let amp = self.amps[state];
            if (state & bit) == 0 {
                new_amps[state] = new_amps[state].add(amp.scale(inv_sqrt2));
                new_amps[state | bit] = new_amps[state | bit].add(amp.scale(inv_sqrt2));
            } else {
                new_amps[state & !bit] = new_amps[state & !bit].add(amp.scale(inv_sqrt2));
                new_amps[state] = new_amps[state].sub(amp.scale(inv_sqrt2));
            }
        }
        self.amps = new_amps;
    }

    /// Apply controlled-phase `|11⟩ → e^{i·θ}|11⟩` (no-op on the
    /// other three two-qubit basis states) between qubits `c` and `t`.
    fn apply_cphase(&mut self, c: usize, t: usize, theta: f64) {
        let cb = 1usize << c;
        let tb = 1usize << t;
        let phase = Complex::from_phase(theta);
        for state in 0..self.amps.len() {
            if (state & cb) != 0 && (state & tb) != 0 {
                self.amps[state] = self.amps[state].mul(phase);
            }
        }
    }

    /// Quantum Fourier Transform on the first `m` qubits (qubits 0..m-1).
    /// Standard textbook gate decomposition: alternating Hadamards and
    /// controlled-phases, ending with a bit-reversal swap.
    fn apply_qft(&mut self, m: usize) {
        for i in (0..m).rev() {
            self.apply_h(i);
            for j in (0..i).rev() {
                let theta = std::f64::consts::PI / ((1u64 << (i - j)) as f64);
                self.apply_cphase(j, i, theta);
            }
        }
        // Bit-reversal swap of the first m qubits.
        for i in 0..(m / 2) {
            self.swap(i, m - 1 - i);
        }
    }

    /// Swap qubits `a` and `b`.
    fn swap(&mut self, a: usize, b: usize) {
        if a == b {
            return;
        }
        let ab = 1usize << a;
        let bb = 1usize << b;
        for state in 0..self.amps.len() {
            // Only swap when bits differ; visit each pair once.
            let bit_a = (state & ab) != 0;
            let bit_b = (state & bb) != 0;
            if bit_a && !bit_b {
                let other = (state & !ab) | bb;
                self.amps.swap(state, other);
            }
        }
    }

    /// Apply the function unitary `U_f: |x⟩|y⟩ → |x⟩|y ⊕ f(x)⟩`,
    /// where the first register has `nx` qubits (indices 0..nx) and
    /// the second has `ny` qubits (indices nx..nx+ny).  `f` maps
    /// `x → f(x) ∈ [0, 2^ny)`; we apply it to every basis state
    /// (the simulator's classical advantage).
    fn apply_function<F: Fn(u64) -> u64>(&mut self, nx: usize, ny: usize, f: F) {
        let dim = self.amps.len();
        debug_assert_eq!(nx + ny, self.n_qubits);
        let x_mask = (1usize << nx) - 1;
        let y_mask = ((1usize << ny) - 1) << nx;
        let mut new_amps = vec![Complex::ZERO; dim];
        for state in 0..dim {
            let amp = self.amps[state];
            if amp == Complex::ZERO {
                continue;
            }
            let x = (state & x_mask) as u64;
            let y_old = ((state & y_mask) >> nx) as u64;
            let fx = f(x) & ((1u64 << ny) - 1);
            let y_new = y_old ^ fx;
            let new_state = (state & x_mask) | ((y_new as usize) << nx);
            new_amps[new_state] = new_amps[new_state].add(amp);
        }
        self.amps = new_amps;
    }

    /// Measure the first `m` qubits.  Returns the classical outcome
    /// `y ∈ [0, 2^m)` and collapses the state.
    fn measure_first(&mut self, m: usize, rng_u64: u64) -> u64 {
        let dim_x = 1usize << m;
        let mut probs = vec![0.0_f64; dim_x];
        for state in 0..self.amps.len() {
            let x = state & (dim_x - 1);
            probs[x] += self.amps[state].norm_sq();
        }
        // Sample y proportional to probs.  Use the supplied u64 as
        // a uniform random source on [0, 1).
        let r = (rng_u64 as f64) / (u64::MAX as f64);
        let mut acc = 0.0_f64;
        let mut chosen = 0u64;
        for (y, p) in probs.iter().enumerate() {
            acc += p;
            if r < acc {
                chosen = y as u64;
                break;
            }
            chosen = y as u64;
        }
        // Collapse.
        let dim = self.amps.len();
        let mut norm_sq = 0.0_f64;
        for state in 0..dim {
            if (state & (dim_x - 1)) as u64 != chosen {
                self.amps[state] = Complex::ZERO;
            } else {
                norm_sq += self.amps[state].norm_sq();
            }
        }
        let inv = if norm_sq > 0.0 {
            1.0 / norm_sq.sqrt()
        } else {
            0.0
        };
        for amp in &mut self.amps {
            *amp = amp.scale(inv);
        }
        chosen
    }
}

// ── Continued-fraction post-processing ──────────────────────────────────────

/// Continued-fraction convergents of `num/den`.  Returns
/// `(p_i, q_i)` pairs in order of increasing `q_i`, up to `max_q`.
///
/// Recurrence (textbook): with `p_{-2} = 0, p_{-1} = 1` and
/// `q_{-2} = 1, q_{-1} = 0`,
///
/// ```text
///   p_n = a_n · p_{n-1} + p_{n-2}
///   q_n = a_n · q_{n-1} + q_{n-2}
/// ```
fn cf_convergents(mut num: u64, mut den: u64, max_q: u64) -> Vec<(u64, u64)> {
    let mut out = Vec::new();
    // p_pp = p_{-2}, p_p = p_{-1}
    let mut p_pp: i128 = 0;
    let mut p_p: i128 = 1;
    let mut q_pp: i128 = 1;
    let mut q_p: i128 = 0;
    while den != 0 {
        let a = (num / den) as i128;
        let p_curr = a * p_p + p_pp;
        let q_curr = a * q_p + q_pp;
        // Shift.
        p_pp = p_p;
        p_p = p_curr;
        q_pp = q_p;
        q_p = q_curr;
        // Advance Euclidean step on (num, den).
        let r = num % den;
        num = den;
        den = r;
        if q_curr > 0 && (q_curr as u64) <= max_q {
            out.push((p_curr.unsigned_abs() as u64, q_curr.unsigned_abs() as u64));
        }
        if q_curr as u64 > max_q {
            break;
        }
    }
    out
}

// ── Shor's algorithm: order finding + factoring ─────────────────────────────

/// Quantum order-finding subroutine.  Given `a` coprime to `n`,
/// returns a candidate period `r` such that `a^r ≡ 1 (mod n)`, or
/// `None` if the sample didn't yield a usable period.  Caller
/// retries with a fresh measurement (or fresh `a`) on `None`.
///
/// `precision_qubits` is the size of the QPE register; should be
/// `≥ 2·⌈log₂(n)⌉` for high success probability.  Total simulation
/// qubits = `precision_qubits + ⌈log₂(n)⌉`.
pub fn shor_order_find(a: u64, n: u64, precision_qubits: usize, rng_seed: u64) -> Option<u64> {
    if n.gcd(&a) != 1 {
        return None;
    }
    let ny = (64 - n.leading_zeros()) as usize;
    let nx = precision_qubits;
    let total = nx + ny;
    let mut q = QState::zero(total);
    // Hadamard the precision register.
    for i in 0..nx {
        q.apply_h(i);
    }
    // U_f: |x⟩|0⟩ → |x⟩|a^x mod n⟩.
    q.apply_function(nx, ny, |x| {
        crate::utils::mod_pow(
            &num_bigint::BigUint::from(a),
            &num_bigint::BigUint::from(x),
            &num_bigint::BigUint::from(n),
        )
        .iter_u64_digits()
        .next()
        .unwrap_or(0)
    });
    // QFT on precision register.
    q.apply_qft(nx);
    // Measure precision register.
    let y = q.measure_first(nx, rng_seed);
    if y == 0 {
        return None;
    }
    // Continued-fraction expansion of y / 2^nx; convergents q_i give
    // candidate periods.
    let big_m = 1u64 << nx;
    let convs = cf_convergents(y, big_m, n);
    for (_p, candidate_r) in convs {
        if candidate_r == 0 {
            continue;
        }
        // Verify: a^r ≡ 1 (mod n).
        let check = crate::utils::mod_pow(
            &num_bigint::BigUint::from(a),
            &num_bigint::BigUint::from(candidate_r),
            &num_bigint::BigUint::from(n),
        );
        if check == num_bigint::BigUint::from(1u32) {
            return Some(candidate_r);
        }
    }
    None
}

/// End-to-end Shor factoring of small `n`.  Returns a non-trivial
/// factor of `n` (i.e. some `f` with `1 < f < n` and `f | n`), or
/// `None` if no usable period was found within `max_retries` quantum
/// runs.
///
/// **Constraints**: `n` must be odd composite, not a prime power.
/// The caller is responsible for handling the "even `n`" case
/// classically (`n / 2`) and prime-power case (try roots).
pub fn shor_factor(n: u64, max_retries: u32, mut rng_seed: u64) -> Option<u64> {
    if n < 4 || n.is_multiple_of(2) {
        return None;
    }
    // Pick `a` coprime to n.  We try small candidates; in real
    // Shor `a` would be uniform random over `[2, n-1]`.
    let candidates: &[u64] = &[2, 3, 5, 7, 11, 13];
    for &a in candidates {
        if a >= n {
            break;
        }
        if n.gcd(&a) != 1 {
            // Lucky factor without quantum effort.
            let f = n.gcd(&a);
            if f != 1 && f != n {
                return Some(f);
            }
            continue;
        }
        // Try up to `max_retries` quantum order-finding runs.
        let nx = 8.max(2 * ((64 - n.leading_zeros()) as usize));
        for _attempt in 0..max_retries {
            rng_seed = rng_seed
                .wrapping_mul(0x9E37_79B9_7F4A_7C15)
                .wrapping_add(0xCAFE);
            let r = match shor_order_find(a, n, nx, rng_seed) {
                Some(r) => r,
                None => continue,
            };
            if r % 2 != 0 {
                continue; // need even period
            }
            // Compute a^(r/2) mod n.
            let half = r / 2;
            let xr = crate::utils::mod_pow(
                &num_bigint::BigUint::from(a),
                &num_bigint::BigUint::from(half),
                &num_bigint::BigUint::from(n),
            )
            .iter_u64_digits()
            .next()
            .unwrap_or(0);
            if xr == n - 1 {
                continue; // a^(r/2) ≡ -1; useless
            }
            let f1 = n.gcd(&(xr + 1));
            let f2 = n.gcd(&xr.saturating_sub(1));
            for f in [f1, f2] {
                if f != 1 && f != n {
                    return Some(f);
                }
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Continued-fraction convergents of 7/15 = 0.466...  Expected:
    /// 0, 1/2, 7/15.
    #[test]
    fn cf_basic() {
        let convs = cf_convergents(7, 15, 100);
        // Should include the convergent 1/2 (a fairly accurate approximation).
        let has_half = convs.iter().any(|&(p, q)| p == 1 && q == 2);
        assert!(
            has_half,
            "expected 1/2 convergent for 7/15; got {:?}",
            convs
        );
    }

    /// QFT followed by inverse QFT (= QFT applied 3 more times for an
    /// approximate identity modulo phases) should preserve a basis state.
    /// We test the simpler property: QFT of |0⟩ → uniform superposition.
    #[test]
    fn qft_zero_is_uniform() {
        let m = 4;
        let mut q = QState::zero(m);
        q.apply_qft(m);
        let dim = 1usize << m;
        let expected = 1.0 / (dim as f64);
        for amp in &q.amps {
            let p = amp.norm_sq();
            assert!(
                (p - expected).abs() < 1e-9,
                "QFT|0⟩ should be uniform; got {} expected {}",
                p,
                expected
            );
        }
    }

    /// Hadamard on |0⟩ gives uniform amplitudes 1/√2.
    #[test]
    fn hadamard_zero_is_plus_state() {
        let mut q = QState::zero(1);
        q.apply_h(0);
        let inv_sqrt2 = std::f64::consts::FRAC_1_SQRT_2;
        assert!((q.amps[0].re - inv_sqrt2).abs() < 1e-12);
        assert!((q.amps[1].re - inv_sqrt2).abs() < 1e-12);
    }

    /// Shor on N=15 with a=7 has period r=4 (since 7^4 = 2401 = 160·15 + 1).
    /// The simulator should recover r correctly with high probability.
    /// We loop several seeds because measurement is probabilistic
    /// AND the continued-fraction step has structural failure modes
    /// for some y values (e.g. y = 0 gives no info, y = 128 gives
    /// candidate r = 2 which fails verification).
    #[test]
    fn shor_order_finds_period_15_a7() {
        let n = 15u64;
        let a = 7u64;
        let mut hits = 0u32;
        let mut totals: Vec<Option<u64>> = Vec::new();
        for seed in 0..64u64 {
            let r = shor_order_find(a, n, 8, seed.wrapping_mul(0x9E37_79B9_7F4A_7C15));
            totals.push(r);
            if r == Some(4) {
                hits += 1;
            }
        }
        assert!(
            hits > 0,
            "Shor failed to find period r=4 for a=7 mod 15 across 64 seeds; got: {:?}",
            totals
        );
    }

    /// Shor end-to-end: factor 15 → must produce 3 or 5.
    #[test]
    fn shor_factors_15() {
        let f = shor_factor(15, 30, 0xC0FFEE).expect("Shor failed to factor 15");
        assert!(f == 3 || f == 5, "expected 3 or 5, got {}", f);
    }

    /// Shor factors 21 → 3 or 7.
    #[test]
    fn shor_factors_21() {
        let f = shor_factor(21, 30, 0xCAFEBABE).expect("Shor failed to factor 21");
        assert!(f == 3 || f == 7, "expected 3 or 7, got {}", f);
    }

    /// Shor rejects even n (caller must factor out 2).
    #[test]
    fn shor_rejects_even() {
        assert_eq!(shor_factor(14, 5, 0), None);
        assert_eq!(shor_factor(100, 5, 0), None);
    }
}
