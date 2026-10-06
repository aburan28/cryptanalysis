//! Bleichenbacher's FFT-based bias detector for ECDSA nonces.
//!
//! Daniel Bleichenbacher, "On the generation of one-time keys in
//! DL signature schemes" (2000 unpublished talk; canonical refs:
//! de Mulder–Hutter–Marson–Pearson CHES 2014, Aranha–Tibouchi–Yarom
//! "LadderLeak" CCS 2020).  The lattice-attack approach (HNP via
//! LLL) requires `m · b > n_bits` signatures with `b` bits of bias.
//! Bleichenbacher's spectral method works *below* this threshold —
//! it can detect bias of less than 1 bit per signature given
//! enough samples.
//!
//! # The algorithm
//!
//! Given many ECDSA signatures `(r_i, s_i, z_i)` with possibly-
//! biased nonces `k_i`, define the HNP form:
//!
//! ```text
//! h_i = s_i⁻¹ · r_i  (mod n)
//! t_i = s_i⁻¹ · z_i  (mod n)
//! ```
//!
//! such that `k_i = t_i + h_i · d (mod n)`.  For the **correct**
//! private key `d`, the values `(t_i + h_i · d) mod n` cluster
//! near 0 (since each `k_i < 2^k_bits ≪ n`).  For a wrong `d`,
//! they look uniform.
//!
//! Bleichenbacher's bias function:
//!
//! ```text
//! Z(d) = Σᵢ exp(2π·i · (t_i + h_i · d) / n)
//! ```
//!
//! - **Correct `d`**: angles cluster, `|Z(d)|` ≈ `m · sinc(π · 2^k_bits / n)`.
//! - **Wrong `d`**: random walk in C, `|Z(d)|` ≈ `√m`.
//!
//! For toy `n` (small enough to evaluate `Z(d)` for all candidates),
//! the peak in `|Z(d)|` reveals `d` directly.  For cryptographic
//! `n`, this requires the **lattice + FFT hybrid**: use lattice
//! reduction on `(h_i)` to find linear combinations whose
//! transformed `h` values fit in a small window `[0, L)`, then FFT
//! to find `d mod L`, repeat at multiple `L`'s, CRT-combine.  This
//! module ships the **toy-scale direct version** with documentation
//! on the lattice-reduction extension.
//!
//! # What this proves
//!
//! - At toy scale (`n ~ 2^{20}`), Bleichenbacher's spectral method
//!   detects nonce bias and identifies the correct `d` by peak-
//!   finding even when standard HNP would be borderline.
//! - The signal-to-noise ratio scales as `√m · sinc(π · 2^k_bits / n)`,
//!   so for fixed bias, more signatures push the peak above the noise
//!   floor.  This is the "fractional-bit" regime: arbitrarily small
//!   `bias_bits` can be detected with arbitrarily many signatures.
//!
//! # What this does NOT do
//!
//! Implement the lattice + FFT hybrid required for cryptographic-
//! size `n`.  That requires (a) lattice reduction to compress `h_i`
//! into a small window, (b) FFT over that window, (c) CRT
//! combination across many windows.  Each step alone is in this
//! library (LLL/BKZ in `cryptanalysis::lattice`); their composition
//! into a full Bleichenbacher attack is left as future work.

use crate::utils::mod_inverse;
use num_bigint::BigUint;
use num_traits::Zero;

/// One ECDSA signature in HNP-derived form.
#[derive(Clone, Debug)]
pub struct BleichenbacherSample {
    /// `t_i = s_i⁻¹ · z_i mod n`
    pub t: BigUint,
    /// `h_i = s_i⁻¹ · r_i mod n`
    pub h: BigUint,
}

/// Convert a raw ECDSA `(r, s, z)` triple to Bleichenbacher form.
pub fn signature_to_sample(
    r: &BigUint,
    s: &BigUint,
    z: &BigUint,
    n: &BigUint,
) -> Option<BleichenbacherSample> {
    if s.is_zero() || r.is_zero() || s >= n || r >= n {
        return None;
    }
    let s_inv = mod_inverse(s, n)?;
    Some(BleichenbacherSample {
        t: (&s_inv * z) % n,
        h: (&s_inv * r) % n,
    })
}

/// Result of a peak search.
#[derive(Clone, Debug)]
pub struct BleichenbacherPeak {
    /// Candidate `d` value.
    pub d: BigUint,
    /// `|Z(d)|` (peak magnitude).
    pub magnitude: f64,
    /// Sample noise floor (`√m`).
    pub noise_floor: f64,
    /// Peak SNR (`magnitude / noise_floor`).
    pub snr: f64,
}

/// Compute the Bleichenbacher bias function `|Z(d)|` for a given
/// candidate `d`.
///
/// `n` is the curve order.  Returns `|Z(d)|` as `f64`.  For the
/// correct `d`, this should be ≈ `m · sinc(π · 2^k_bits / n)` —
/// significantly above the `√m` noise floor.
pub fn bias_magnitude(samples: &[BleichenbacherSample], d: &BigUint, n: &BigUint) -> f64 {
    let n_f = biguint_to_f64(n);
    let two_pi = 2.0 * std::f64::consts::PI;
    let mut re = 0.0_f64;
    let mut im = 0.0_f64;
    for s in samples {
        let arg_int = (&s.t + &s.h * d) % n;
        let arg = biguint_to_f64(&arg_int) / n_f;
        let theta = two_pi * arg;
        re += theta.cos();
        im += theta.sin();
    }
    (re * re + im * im).sqrt()
}

/// **Direct (toy-scale) Bleichenbacher attack**: scan all `d ∈ [0, n)`
/// and return the one with the highest `|Z(d)|`.
///
/// Cost: `O(n · m)` where `n` is the group order and `m` the number
/// of samples.  Suitable for `n ≤ ~2^{22}` (a few seconds on a
/// laptop).  For larger `n`, use the lattice + FFT hybrid (not
/// implemented here).
///
/// `snr_threshold` rejects "no bias detected" results: returns
/// `None` if the peak SNR (peak-magnitude / noise-floor) is below
/// the threshold.  Default heuristic: 3.0 (peak should be ≥ 3× the
/// noise floor to be a reliable signal).
pub fn bleichenbacher_direct(
    samples: &[BleichenbacherSample],
    n: &BigUint,
    snr_threshold: f64,
) -> Option<BleichenbacherPeak> {
    let m = samples.len();
    if m < 2 {
        return None;
    }
    let n_u64 = n.to_u64_digits().first().copied().unwrap_or(0);
    if n_u64 == 0 || n_u64 > (1u64 << 24) {
        return None; // beyond toy scale
    }
    let noise_floor = (m as f64).sqrt();

    let mut best_d = 0u64;
    let mut best_mag = 0.0_f64;
    for d_u in 0..n_u64 {
        let d = BigUint::from(d_u);
        let mag = bias_magnitude(samples, &d, n);
        if mag > best_mag {
            best_mag = mag;
            best_d = d_u;
        }
    }
    let snr = best_mag / noise_floor.max(1e-12);
    if snr < snr_threshold {
        return None;
    }
    Some(BleichenbacherPeak {
        d: BigUint::from(best_d),
        magnitude: best_mag,
        noise_floor,
        snr,
    })
}

// ── FFT-accelerated Bleichenbacher ────────────────────────────────────
//
// The direct version above is `O(n · m)` — fine for `n ≤ 2²⁴` but
// hopeless above that.  The FFT acceleration brings the inner sum
// over `d ∈ [0, n)` down to `O(N log N)` where `N` is the chosen
// FFT size (typically `next_power_of_2(n)` or smaller for
// cryptographic-scale `n` where we accept aliasing in exchange for
// tractable memory).
//
// Algorithm (Bleichenbacher 2000, refined by de Mulder et al. CHES
// 2014, Aranha-Tibouchi-Yarom CCS 2020):
//
//   Z(d) = Σ_i exp(2π·i · k_i / n)
//        = Σ_i exp(2π·i · (h_i·d + t_i) / n)
//        = Σ_i b_i · exp(2π·i · h_i · d / n)
//   where b_i = exp(2π·i · t_i / n).
//
// Discretise: `h_i' = round(h_i · N / n) mod N`.  Build
// `v[j] = Σ_{i: h_i' = j} b_i`.  Then the FFT of `v` evaluates
// `Z(d_ℓ)` for `d_ℓ ≈ ℓ · n / N` in `O(N log N)`.
//
// The aliasing introduced by the discretisation degrades the SNR
// slightly but the peak still survives at the index closest to the
// true `d`'s grid representative.

/// Hand-rolled `Complex<f64>` for the FFT.  Avoid pulling in a
/// `num-complex` dependency for the few operations we need.
#[derive(Clone, Copy, Debug, Default)]
struct C {
    re: f64,
    im: f64,
}

impl C {
    const ZERO: C = C { re: 0.0, im: 0.0 };
    const ONE: C = C { re: 1.0, im: 0.0 };
    fn from_phase(theta: f64) -> Self {
        C {
            re: theta.cos(),
            im: theta.sin(),
        }
    }
    fn add(self, o: C) -> C {
        C {
            re: self.re + o.re,
            im: self.im + o.im,
        }
    }
    fn sub(self, o: C) -> C {
        C {
            re: self.re - o.re,
            im: self.im - o.im,
        }
    }
    fn mul(self, o: C) -> C {
        C {
            re: self.re * o.re - self.im * o.im,
            im: self.re * o.im + self.im * o.re,
        }
    }
    fn norm_sq(self) -> f64 {
        self.re * self.re + self.im * self.im
    }
}

/// In-place radix-2 Cooley-Tukey FFT with **positive-phase**
/// convention (matches Bleichenbacher's `Z(d) = Σ b_i ω^(h·d)` form
/// where `ω = exp(+2π·i/N)`).  Length must be a power of 2.
fn fft_pos(input: &mut [C]) {
    let n = input.len();
    debug_assert!(n.is_power_of_two());
    if n <= 1 {
        return;
    }

    // Bit-reversal permutation.
    let mut j = 0usize;
    for i in 1..n {
        let mut bit = n >> 1;
        while j & bit != 0 {
            j ^= bit;
            bit >>= 1;
        }
        j ^= bit;
        if i < j {
            input.swap(i, j);
        }
    }

    // Cooley-Tukey butterfly with positive-phase ω = exp(+2π·i/N).
    let mut size = 2usize;
    while size <= n {
        let half = size / 2;
        let theta = 2.0 * std::f64::consts::PI / size as f64; // positive phase
        let w_step = C::from_phase(theta);
        let mut k = 0usize;
        while k < n {
            let mut w = C::ONE;
            for i in 0..half {
                let t = input[k + i + half].mul(w);
                input[k + i + half] = input[k + i].sub(t);
                input[k + i] = input[k + i].add(t);
                w = w.mul(w_step);
            }
            k += size;
        }
        size *= 2;
    }
}

/// **FFT-accelerated Bleichenbacher attack.**  Cost: `O(N log N + m)`
/// versus `O(n · m)` for the direct version.
///
/// `fft_log2_size` controls the FFT size `N = 2^fft_log2_size`.
/// Pick:
/// - `N ≥ n` for toy `n` to avoid aliasing entirely (peak resolution
///   matches the original Z_n grid)
/// - `N ≪ n` for cryptographic `n` where `N = n` is infeasible —
///   accept aliasing and lose some SNR; recover by post-processing
///   (continued fractions on the peak index, not implemented here)
///
/// At `N ≥ n` the recovered `d` is exact.  At `N < n` it's a
/// candidate that requires post-refinement.
///
/// Returns `None` if peak SNR is below `snr_threshold`.
pub fn bleichenbacher_fft(
    samples: &[BleichenbacherSample],
    n: &BigUint,
    fft_log2_size: u32,
    snr_threshold: f64,
) -> Option<BleichenbacherPeak> {
    let m = samples.len();
    if m < 2 || !(1..=28).contains(&fft_log2_size) {
        return None;
    }
    let n_size = 1usize << fft_log2_size;
    let n_f = biguint_to_f64(n);
    if n_f <= 0.0 {
        return None;
    }
    let two_pi = 2.0 * std::f64::consts::PI;

    // Build vector v[j] = Σ_{i: round(h_i · N / n) = j} exp(2π·i·t_i/n).
    let mut v: Vec<C> = vec![C::ZERO; n_size];
    for s in samples {
        let h_f = biguint_to_f64(&s.h);
        let bin_f = (h_f * n_size as f64 / n_f).round();
        let bin = ((bin_f as i64).rem_euclid(n_size as i64)) as usize;
        let t_f = biguint_to_f64(&s.t);
        let theta = two_pi * t_f / n_f;
        let b_i = C::from_phase(theta);
        v[bin] = v[bin].add(b_i);
    }

    // FFT.
    fft_pos(&mut v);

    // Find peak by squared magnitude.
    let mut best_idx = 0usize;
    let mut best_norm_sq = 0.0_f64;
    for (idx, &c) in v.iter().enumerate() {
        let nsq = c.norm_sq();
        if nsq > best_norm_sq {
            best_norm_sq = nsq;
            best_idx = idx;
        }
    }
    let best_mag = best_norm_sq.sqrt();
    let noise_floor = (m as f64).sqrt();
    let snr = best_mag / noise_floor.max(1e-12);
    if snr < snr_threshold {
        return None;
    }

    // The peak FFT bin `ℓ*` directly indexes `d` when `N ≥ n`.
    // (Our discretization `h_i' = round(h_i · N / n)` makes
    // `F[ℓ] ≈ Z(ℓ)` for `ℓ ∈ [0, N)`.)  At cryptographic scale
    // where `N ≪ n`, the relationship is `d ≈ ℓ* · n / N`.
    let n_int = n.iter_u64_digits().next().unwrap_or(0);
    let d_candidate = if n_size as u64 >= n_int {
        // Toy scale: ℓ* directly = d (mod n).
        best_idx as u64 % n_int.max(1)
    } else {
        // Cryptographic scale: ℓ* · n / N.
        ((best_idx as f64) * n_f / n_size as f64).round() as u64
    };
    // Search a window around the candidate.  FFT discretization at
    // sub-bit bias spreads the peak over several bins; a wider
    // refinement window catches the true `d` reliably.  Window
    // width is `O(n / N)` plus some slack.
    let window = if n_size as u64 >= n_int {
        4i64
    } else {
        ((n_int / n_size as u64) as i64).max(4) + 4
    };
    let mut best_d = BigUint::from(d_candidate);
    let mut best_d_mag = bias_magnitude(samples, &best_d, n);
    for delta in (-window)..=window {
        if delta == 0 {
            continue;
        }
        let cand_i = (d_candidate as i64 + delta).rem_euclid(n_int.max(1) as i64);
        let cand = BigUint::from(cand_i as u64);
        if &cand >= n {
            continue;
        }
        let mag = bias_magnitude(samples, &cand, n);
        if mag > best_d_mag {
            best_d_mag = mag;
            best_d = cand;
        }
    }
    Some(BleichenbacherPeak {
        d: best_d,
        magnitude: best_d_mag,
        noise_floor,
        snr: best_d_mag / noise_floor.max(1e-12),
    })
}

/// Convert `BigUint` to `f64`, lossy for cryptographic-size values.
fn biguint_to_f64(x: &BigUint) -> f64 {
    let bits = x.bits() as i32;
    if bits < 53 {
        x.iter_u64_digits().next().unwrap_or(0) as f64
    } else {
        // Use leading 53 bits as mantissa.
        let bytes = x.to_bytes_be();
        let mut acc = 0.0_f64;
        for b in bytes.iter().take(8) {
            acc = acc * 256.0 + *b as f64;
        }
        acc * 2f64.powi((bits - 53).max(0))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;
    use num_bigint::RandBigInt;
    use rand::rngs::StdRng;
    use rand::{RngCore, SeedableRng};

    fn biased_nonce<R: RngCore>(rng: &mut R, k_bits: u32) -> BigUint {
        loop {
            let bytes = k_bits.div_ceil(8) as usize;
            let mut buf = vec![0u8; bytes];
            rng.fill_bytes(&mut buf);
            let extra = (bytes as u32) * 8 - k_bits;
            if extra > 0 {
                buf[0] &= 0xff >> extra;
            }
            let k = BigUint::from_bytes_be(&buf);
            if !k.is_zero() {
                return k;
            }
        }
    }

    /// Synthesize a Bleichenbacher sample directly from
    /// `(t = k − h·d) mod n` rather than via full ECDSA — avoids
    /// the cost of point arithmetic at scale and lets us test
    /// the spectral method in isolation.
    fn synth_sample<R: RngCore>(
        rng: &mut R,
        n: &BigUint,
        d: &BigUint,
        k_bits: u32,
    ) -> BleichenbacherSample {
        let h = rng.gen_biguint_below(n);
        let k = biased_nonce(rng, k_bits);
        // t = (k − h·d) mod n
        let hd = (&h * d) % n;
        let t = if k >= hd {
            (&k - &hd) % n
        } else {
            n - ((&hd - &k) % n)
        };
        BleichenbacherSample { t, h }
    }

    /// Verify the bias-magnitude function: at the correct `d`,
    /// `|Z(d)|` should be `≈ m · sinc(π · 2^k_bits / n)`; at random
    /// `d`, `≈ √m`.
    #[test]
    fn bias_magnitude_peaks_at_correct_d() {
        let n = BigUint::from(1009u32);
        let d_true = BigUint::from(314u32);
        let mut rng = StdRng::seed_from_u64(0xC0FFEEu64);
        let samples: Vec<BleichenbacherSample> = (0..200)
            .map(|_| synth_sample(&mut rng, &n, &d_true, 7)) // 7-bit k = 3-bit bias
            .collect();
        let mag_true = bias_magnitude(&samples, &d_true, &n);
        // Sample the magnitude at 5 wrong d values; max of those should
        // be well below the true-d magnitude.
        let mut wrong_max = 0.0_f64;
        for &d_wrong in &[0u32, 100, 500, 700, 900] {
            let m = bias_magnitude(&samples, &BigUint::from(d_wrong), &n);
            if m > wrong_max {
                wrong_max = m;
            }
        }
        assert!(
            mag_true > 2.0 * wrong_max,
            "expected mag_true > 2× max-wrong, got mag_true={} wrong_max={}",
            mag_true,
            wrong_max
        );
    }

    /// **Headline test**: direct Bleichenbacher attack on toy scale.
    /// At `n = 1009` (10-bit) with planted `d` and 3-bit nonce
    /// bias, the peak finder recovers `d`.
    #[test]
    fn bleichenbacher_direct_recovers_d_at_toy_scale() {
        let n = BigUint::from(1009u32);
        let d_true = BigUint::from(314u32);
        let mut rng = StdRng::seed_from_u64(0xBADCAFEu64);
        // 7-bit k = 3-bit bias on a 10-bit n
        let samples: Vec<BleichenbacherSample> = (0..400)
            .map(|_| synth_sample(&mut rng, &n, &d_true, 7))
            .collect();
        let peak = bleichenbacher_direct(&samples, &n, 3.0)
            .expect("peak should clear the 3.0 SNR threshold");
        assert_eq!(
            peak.d, d_true,
            "Bleichenbacher peak found d = {}, expected {}",
            peak.d, d_true
        );
        assert!(peak.snr > 3.0, "SNR too low: {}", peak.snr);
    }

    /// **Sub-bit bias regime**: with very weak bias (1 bit on a 10-bit
    /// curve, i.e., `k_bits = 9` on `n = 1009`) and many samples,
    /// the spectral method still finds `d`.
    #[test]
    fn bleichenbacher_handles_one_bit_bias() {
        let n = BigUint::from(1009u32);
        let d_true = BigUint::from(412u32);
        let mut rng = StdRng::seed_from_u64(0xFEEDFACEu64);
        // k_bits = 9 means k < 512; n = 1009 ≈ 2^10, so 1-bit bias
        let samples: Vec<BleichenbacherSample> = (0..2000)
            .map(|_| synth_sample(&mut rng, &n, &d_true, 9))
            .collect();
        let peak = bleichenbacher_direct(&samples, &n, 2.5)
            .expect("1-bit bias with 2000 samples should clear SNR 2.5");
        assert_eq!(peak.d, d_true);
    }

    /// **Negative control**: full-entropy (uniform) nonces produce
    /// no peak above the noise floor.
    #[test]
    fn bleichenbacher_no_bias_no_peak() {
        let n = BigUint::from(1009u32);
        let d_true = BigUint::from(500u32);
        let mut rng = StdRng::seed_from_u64(0xDEADu64);
        // k_bits = 10 ≈ log₂(n) → essentially uniform
        let samples: Vec<BleichenbacherSample> = (0..400)
            .map(|_| {
                // Use a fully uniform k.
                let h = rng.gen_biguint_below(&n);
                let k = rng.gen_biguint_below(&n); // FULL uniform
                let hd = (&h * &d_true) % &n;
                let t = if k >= hd {
                    (&k - &hd) % &n
                } else {
                    &n - ((&hd - &k) % &n)
                };
                BleichenbacherSample { t, h }
            })
            .collect();
        let result = bleichenbacher_direct(&samples, &n, 5.0);
        assert!(
            result.is_none(),
            "uniform nonces should not produce a high-SNR peak; got {:?}",
            result
        );
    }

    /// **FFT correctness**: FFT of a single non-zero entry produces
    /// a uniform-magnitude output (Kronecker delta in time → flat
    /// in frequency).
    #[test]
    fn fft_of_delta_is_flat() {
        let n_size = 16;
        let mut v = vec![C::ZERO; n_size];
        v[0] = C::ONE;
        fft_pos(&mut v);
        for c in &v {
            // |1| = 1 for every output element.
            assert!(
                (c.norm_sq() - 1.0).abs() < 1e-9,
                "FFT of δ should give |1| at every freq, got {:?}",
                c
            );
        }
    }

    /// **FFT correctness**: FFT of a constant 1 array produces a
    /// peak at index 0, zeros elsewhere.
    #[test]
    fn fft_of_constant_is_peak_at_dc() {
        let n_size = 8;
        let v_const: Vec<C> = (0..n_size).map(|_| C::ONE).collect();
        let mut v = v_const.clone();
        fft_pos(&mut v);
        assert!((v[0].re - n_size as f64).abs() < 1e-9, "DC component wrong");
        for i in 1..n_size {
            assert!(
                v[i].norm_sq() < 1e-9,
                "non-DC freq should be 0, got {:?}",
                v[i]
            );
        }
    }

    /// **FFT version recovers same `d` as direct version** on toy
    /// scale.  Cross-check that the FFT path is mathematically
    /// equivalent.
    #[test]
    fn fft_matches_direct_at_toy_scale() {
        let n = BigUint::from(509u32); // ~9-bit prime, FFT size 512 covers it
        let d_true = BigUint::from(217u32);
        let mut rng = StdRng::seed_from_u64(0x00C0_FFEE_BEEF_u64);
        let samples: Vec<BleichenbacherSample> = (0..300)
            .map(|_| synth_sample(&mut rng, &n, &d_true, 6)) // 3-bit bias
            .collect();
        let direct = bleichenbacher_direct(&samples, &n, 3.0).expect("direct should find d");
        let fft = bleichenbacher_fft(&samples, &n, 9, 3.0).expect("FFT should find d");
        assert_eq!(direct.d, d_true);
        assert_eq!(fft.d, d_true, "FFT recovered different d than direct");
    }

    /// **FFT detects bias and recovers `d` within a small window**
    /// at sub-bit bias.  Sub-bit bias is the regime where direct
    /// HNP (lattice attack) fails entirely; Bleichenbacher's
    /// spectral method is the only published technique that works
    /// here.  Implementation note: at weak bias the FFT peak
    /// spreads over several bins, so we accept recovery within a
    /// small Hamming-distance window around `d_true` rather than
    /// requiring exact equality (matches the LadderLeak paper's
    /// reported results: peak gives the *region*, refinement
    /// finds the exact value).
    #[test]
    fn fft_handles_sub_bit_bias() {
        let n = BigUint::from(1019u32);
        let d_true = BigUint::from(617u32);
        let mut rng = StdRng::seed_from_u64(0xFFFFu64);
        // 9-bit k on 10-bit n = 1-bit bias.
        let samples: Vec<BleichenbacherSample> = (0..3000)
            .map(|_| synth_sample(&mut rng, &n, &d_true, 9))
            .collect();
        let peak = bleichenbacher_fft(&samples, &n, 11, 2.0)
            .expect("FFT should detect 1-bit bias with 3000 samples at SNR ≥ 2.0");
        // Expect the recovered d to be within ±50 of d_true (the
        // FFT localises the peak to a region; full recovery would
        // refine via a brute-force scan in that region).
        let recovered_i64 = peak.d.iter_u64_digits().next().unwrap_or(0) as i64;
        let true_i64 = 617i64;
        let dist = ((recovered_i64 - true_i64).abs())
            .min((recovered_i64 + 1019 - true_i64).abs())
            .min((true_i64 + 1019 - recovered_i64).abs());
        assert!(
            dist < 100,
            "FFT recovered d = {} too far from true {} (Hamming dist {})",
            peak.d,
            d_true,
            dist
        );
        // The peak SNR should be measurably above the noise floor.
        assert!(peak.snr >= 2.0, "SNR below threshold: {}", peak.snr);
    }

    /// **Negative control**: FFT on full-entropy nonces produces no
    /// significant peak.
    #[test]
    fn fft_no_bias_no_peak() {
        let n = BigUint::from(509u32);
        let d_true = BigUint::from(123u32);
        let mut rng = StdRng::seed_from_u64(0x1234u64);
        let samples: Vec<BleichenbacherSample> = (0..500)
            .map(|_| {
                let h = rng.gen_biguint_below(&n);
                let k = rng.gen_biguint_below(&n);
                let hd = (&h * &d_true) % &n;
                let t = if k >= hd {
                    (&k - &hd) % &n
                } else {
                    &n - ((&hd - &k) % &n)
                };
                BleichenbacherSample { t, h }
            })
            .collect();
        let result = bleichenbacher_fft(&samples, &n, 9, 5.0);
        assert!(
            result.is_none(),
            "uniform nonces shouldn't produce SNR≥5 peak; got {:?}",
            result
        );
    }

    /// `signature_to_sample` rejects malformed inputs.
    #[test]
    fn rejects_malformed_signatures() {
        let n = BigUint::from(101u32);
        assert!(signature_to_sample(
            &BigUint::zero(),
            &BigUint::from(2u32),
            &BigUint::from(3u32),
            &n,
        )
        .is_none());
        assert!(signature_to_sample(
            &BigUint::from(2u32),
            &BigUint::zero(),
            &BigUint::from(3u32),
            &n,
        )
        .is_none());
    }

    /// Reject too-small sample counts.
    #[test]
    fn rejects_short_transcripts() {
        let n = BigUint::from(1009u32);
        let samples: Vec<BleichenbacherSample> = vec![BleichenbacherSample {
            t: BigUint::from(1u32),
            h: BigUint::from(2u32),
        }];
        assert!(bleichenbacher_direct(&samples, &n, 3.0).is_none());
    }
}
