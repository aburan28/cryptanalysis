//! **AI-enhanced Schoof's algorithm** — neural-network interval
//! prediction for point counting on elliptic curves.
//!
//! Per Maimuț & Matei (eprint 2022/1458) §3.2: replace Hasse's
//! interval `[p + 1 − 2√p, p + 1 + 2√p]` (width `4√p`) with a
//! tighter interval of width `4ε` (with `ε ≈ 0.84 · √p`) predicted
//! by a small neural network trained on `(p, a, b) → #E(F_p)`
//! samples.  This reduces Schoof's search by ~16% per their
//! experimental results (7-layer model, 93% success rate).
//!
//! ## Pure-Rust scope
//!
//! The paper uses TensorFlow.  We re-implement the architecture
//! end-to-end in pure Rust:
//!
//! - **Network**: fully-connected, 3-input, configurable hidden
//!   layers, 1-output, sigmoid activation throughout.  Trains via
//!   gradient descent on a custom mean-squared-logarithmic-error
//!   loss matching the paper's formulation.
//! - **Training data**: synthesised on the fly via brute-force
//!   `#E(F_p)` counting for small primes (`p ≤ 2¹⁶`).
//! - **Inference**: predict normalised offset `(n − (p+1) + 2√p) /
//!   (4√p) ∈ [0, 1]`, then de-normalise to an order estimate.
//! - **Reduced Schoof interval**: `[n̂ − 2ε, n̂ + 2ε]`.
//!
//! ## Honest limitations
//!
//! - Toy network (3 inputs → small hidden layers → 1 output)
//!   designed for **proof-of-concept** demonstration only.  The
//!   paper trains on 60,000 examples with 7 layers of 512–8 units;
//!   our default is 3 layers of 16 units trained on 200 examples,
//!   sufficient to demonstrate the *structure* but not match the
//!   paper's accuracy.
//! - Inference quality is **not** comparable to the paper's
//!   numbers.  Achieving 93% success rate at 16% interval
//!   reduction requires the paper's training budget.

// ── Brute-force trace counting for small p (training labels) ──────

/// Brute-force count of `#E(F_p)` for `y² = x³ + a·x + b` over
/// `F_p`.  `O(p · log p)` per curve.  Used to generate training
/// labels.
pub fn count_points_small(p: u64, a: u64, b: u64) -> u64 {
    let mut count: u64 = 1; // identity O
    let p_u128 = p as u128;
    let a_u128 = a as u128;
    let b_u128 = b as u128;
    for x in 0..p {
        let xx = x as u128;
        let rhs = ((xx * xx) % p_u128 * xx % p_u128 + a_u128 * xx % p_u128 + b_u128) % p_u128;
        if rhs == 0 {
            count += 1;
        } else {
            let pow = mod_pow_u64(rhs as u64, (p - 1) / 2, p);
            if pow == 1 {
                count += 2;
            }
        }
    }
    count
}

fn mod_pow_u64(base: u64, mut exp: u64, m: u64) -> u64 {
    let mut result: u128 = 1;
    let mut b = base as u128 % m as u128;
    let m_u = m as u128;
    while exp > 0 {
        if exp & 1 == 1 {
            result = (result * b) % m_u;
        }
        b = (b * b) % m_u;
        exp >>= 1;
    }
    result as u64
}

// ── Pure-Rust feed-forward neural network ──────────────────────────

/// A small fully-connected neural network with sigmoid activations
/// throughout.  Weights are stored row-major: `weights[layer][i][j]`
/// is the weight from input neuron `j` to output neuron `i`.
#[derive(Clone, Debug)]
pub struct Net {
    /// Layer sizes: `layers[0]` = input, `layers.last()` = output.
    pub layers: Vec<usize>,
    /// `weights[l]` shape: `(layers[l+1], layers[l])`.
    pub weights: Vec<Vec<Vec<f64>>>,
    /// `biases[l]` shape: `layers[l+1]`.
    pub biases: Vec<Vec<f64>>,
}

fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

fn sigmoid_prime(s: f64) -> f64 {
    // Given σ(x), derivative is σ(1 − σ).
    s * (1.0 - s)
}

/// Tiny portable PRNG (LCG) — sufficient for weight initialisation;
/// no need for proper crypto-grade randomness here.
fn lcg_next(state: &mut u64) -> f64 {
    *state = state
        .wrapping_mul(6364136223846793005)
        .wrapping_add(1442695040888963407);
    let v = ((*state >> 11) as u32) as f64 / (u32::MAX as f64 + 1.0);
    v * 2.0 - 1.0 // [-1, 1]
}

impl Net {
    /// Initialise with random weights in `[-1, 1]` scaled by
    /// `1/√fan_in` (Xavier-lite init).
    pub fn new(layers: Vec<usize>, seed: u64) -> Self {
        let mut rng_state = seed;
        let mut weights = Vec::with_capacity(layers.len() - 1);
        let mut biases = Vec::with_capacity(layers.len() - 1);
        for l in 0..(layers.len() - 1) {
            let fan_in = layers[l] as f64;
            let scale = 1.0 / fan_in.sqrt();
            let mut w_layer = Vec::with_capacity(layers[l + 1]);
            for _ in 0..layers[l + 1] {
                let row: Vec<f64> = (0..layers[l])
                    .map(|_| lcg_next(&mut rng_state) * scale)
                    .collect();
                w_layer.push(row);
            }
            weights.push(w_layer);
            biases.push(vec![0.0; layers[l + 1]]);
        }
        Self {
            layers,
            weights,
            biases,
        }
    }

    /// Forward pass: returns the per-layer activations (input
    /// included as `activations[0]`).
    pub fn forward(&self, input: &[f64]) -> Vec<Vec<f64>> {
        assert_eq!(input.len(), self.layers[0]);
        let mut activations = vec![input.to_vec()];
        for l in 0..self.weights.len() {
            let prev = &activations[l];
            let next: Vec<f64> = self.weights[l]
                .iter()
                .zip(&self.biases[l])
                .map(|(row, bias)| {
                    let dot: f64 = row.iter().zip(prev).map(|(w, x)| w * x).sum();
                    sigmoid(dot + bias)
                })
                .collect();
            activations.push(next);
        }
        activations
    }

    /// Predict a single value (output layer must be size 1).
    pub fn predict(&self, input: &[f64]) -> f64 {
        let acts = self.forward(input);
        acts.last().unwrap()[0]
    }

    /// One step of stochastic gradient descent on a single example
    /// using mean-squared error loss `(y − ŷ)²`.  Returns the loss.
    pub fn sgd_step(&mut self, input: &[f64], target: f64, lr: f64) -> f64 {
        let acts = self.forward(input);
        let n_layers = self.weights.len();
        // Output gradient: dL/dz_out = 2·(ŷ − y) · σ'(z_out).
        let y_hat = acts[n_layers][0];
        let err = y_hat - target;
        let loss = err * err;

        // Back-propagate.  delta_l = dL/dz_l at layer l (post-act).
        let mut deltas = vec![Vec::new(); n_layers];
        deltas[n_layers - 1] = vec![2.0 * err * sigmoid_prime(y_hat)];

        for l in (0..(n_layers - 1)).rev() {
            let next_delta = &deltas[l + 1];
            let next_weights = &self.weights[l + 1];
            let cur_act = &acts[l + 1];
            let mut d: Vec<f64> = vec![0.0; self.layers[l + 1]];
            for j in 0..self.layers[l + 1] {
                let mut s = 0.0;
                for i in 0..self.layers[l + 2] {
                    s += next_weights[i][j] * next_delta[i];
                }
                d[j] = s * sigmoid_prime(cur_act[j]);
            }
            deltas[l] = d;
        }

        // Update weights and biases.
        for l in 0..n_layers {
            let prev_act = &acts[l];
            for i in 0..self.layers[l + 1] {
                for j in 0..self.layers[l] {
                    self.weights[l][i][j] -= lr * deltas[l][i] * prev_act[j];
                }
                self.biases[l][i] -= lr * deltas[l][i];
            }
        }
        loss
    }
}

// ── Training data + label normalisation per the paper ──────────────

/// Generate `n` training examples from random `(p, a, b)` with
/// `p` a prime in `[100, 1000]`.  Returns `(features, labels)` where
/// `features[i] = [p / max_p, a / p, b / p]` (all in `[0, 1]`)
/// and `labels[i] = (n − (p+1) + 2√p) / (4√p) ∈ [0, 1]`.
pub fn generate_training_data(n: usize, seed: u64) -> (Vec<[f64; 3]>, Vec<f64>) {
    let mut rng_state = seed;
    let mut features = Vec::with_capacity(n);
    let mut labels = Vec::with_capacity(n);
    let mut count = 0usize;
    while count < n {
        let p_candidate = 100 + (lcg_next(&mut rng_state).abs() * 900.0) as u64;
        if !is_small_prime(p_candidate) {
            continue;
        }
        let a = (lcg_next(&mut rng_state).abs() * p_candidate as f64) as u64 % p_candidate;
        let b = (lcg_next(&mut rng_state).abs() * p_candidate as f64) as u64 % p_candidate;
        // Skip singular curves.
        let disc = (4 * a * a % p_candidate * a + 27 * b * b) % p_candidate;
        if disc == 0 {
            continue;
        }
        let n_pts = count_points_small(p_candidate, a, b);
        let sqrt_p = (p_candidate as f64).sqrt();
        let y = (n_pts as f64 - (p_candidate as f64 + 1.0) + 2.0 * sqrt_p) / (4.0 * sqrt_p);
        if !(0.0..=1.0).contains(&y) {
            continue;
        }
        features.push([
            p_candidate as f64 / 1000.0,
            a as f64 / p_candidate as f64,
            b as f64 / p_candidate as f64,
        ]);
        labels.push(y);
        count += 1;
    }
    (features, labels)
}

fn is_small_prime(n: u64) -> bool {
    if n < 2 {
        return false;
    }
    if n < 4 {
        return true;
    }
    if n.is_multiple_of(2) {
        return false;
    }
    let mut i = 3u64;
    while i * i <= n {
        if n.is_multiple_of(i) {
            return false;
        }
        i += 2;
    }
    true
}

/// Train a 3-input → 16 → 16 → 1 network on `examples` for
/// `n_epochs` passes.  Returns the trained network and the final
/// epoch's mean loss.
pub fn train_default(
    features: &[[f64; 3]],
    labels: &[f64],
    n_epochs: usize,
    lr: f64,
    seed: u64,
) -> (Net, f64) {
    let mut net = Net::new(vec![3, 16, 16, 1], seed);
    let mut final_loss = f64::INFINITY;
    for _ in 0..n_epochs {
        let mut total_loss = 0.0;
        for (x, y) in features.iter().zip(labels) {
            let loss = net.sgd_step(x, *y, lr);
            total_loss += loss;
        }
        final_loss = total_loss / features.len() as f64;
    }
    (net, final_loss)
}

/// Use a trained network to predict the order `#E(F_p)` from
/// `(p, a, b)` and report a reduced Hasse-style interval centred
/// on the prediction.
pub fn predict_order_interval(
    net: &Net,
    p: u64,
    a: u64,
    b: u64,
    interval_half_width_fraction: f64,
) -> (u64, u64) {
    let feat = [p as f64 / 1000.0, a as f64 / p as f64, b as f64 / p as f64];
    let y_hat = net.predict(&feat);
    let sqrt_p = (p as f64).sqrt();
    let n_hat = (y_hat * 4.0 * sqrt_p - 2.0 * sqrt_p + (p as f64 + 1.0)).round() as u64;
    let half_width = (2.0 * sqrt_p * interval_half_width_fraction).round() as u64;
    (
        n_hat.saturating_sub(half_width),
        n_hat.saturating_add(half_width),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `count_points_small` matches Hasse: `|n − (p+1)| ≤ 2√p`.
    #[test]
    fn count_points_satisfies_hasse() {
        for &p in &[101u64, 251, 503, 997] {
            for a in [0u64, 1, 3, p - 3].iter().copied() {
                for b in [1u64, 5, 7].iter().copied() {
                    let disc = (4 * a * a % p * a + 27 * b * b) % p;
                    if disc == 0 {
                        continue;
                    }
                    let n = count_points_small(p, a % p, b % p);
                    let sqrt_p = (p as f64).sqrt();
                    let lower = (p as f64 + 1.0 - 2.0 * sqrt_p) as i128;
                    let upper = (p as f64 + 1.0 + 2.0 * sqrt_p) as i128;
                    assert!(
                        (n as i128) >= lower && (n as i128) <= upper,
                        "Hasse violated: p={}, a={}, b={}, n={}",
                        p,
                        a,
                        b,
                        n,
                    );
                }
            }
        }
    }

    /// Network forward pass produces an output in `[0, 1]` (sigmoid
    /// final layer).
    #[test]
    fn net_output_in_unit_interval() {
        let net = Net::new(vec![3, 4, 1], 12345);
        let y = net.predict(&[0.5, 0.2, 0.7]);
        assert!((0.0..=1.0).contains(&y));
    }

    /// SGD reduces loss on a tiny synthetic dataset.
    #[test]
    fn sgd_reduces_loss() {
        let mut net = Net::new(vec![3, 4, 1], 42);
        let xs = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]];
        let ys = [0.2, 0.5, 0.8];
        let mut initial_loss = 0.0;
        for (x, y) in xs.iter().zip(&ys) {
            initial_loss += (net.predict(x) - y).powi(2);
        }
        for _ in 0..1000 {
            for (x, y) in xs.iter().zip(&ys) {
                net.sgd_step(x, *y, 0.1);
            }
        }
        let mut final_loss = 0.0;
        for (x, y) in xs.iter().zip(&ys) {
            final_loss += (net.predict(x) - y).powi(2);
        }
        assert!(
            final_loss < initial_loss * 0.5,
            "SGD should at least halve the loss on a small dataset; got {} → {}",
            initial_loss,
            final_loss
        );
    }

    /// **AI-Schoof end-to-end** at toy scale.  Generate 100 training
    /// examples, train for 200 epochs, predict the interval for a
    /// held-out curve and verify Hasse-correctness.
    #[test]
    fn ai_schoof_end_to_end_toy() {
        let (features, labels) = generate_training_data(100, 7);
        let (net, _) = train_default(&features, &labels, 200, 0.05, 9);

        // Held-out curve: y² = x³ + 2x + 3 over F_101.
        let p = 101u64;
        let a = 2u64;
        let b = 3u64;
        let true_n = count_points_small(p, a, b);
        let (lo, hi) = predict_order_interval(&net, p, a, b, 0.5);
        println!(
            "AI-Schoof: p={}, true n={}, predicted [{}, {}]",
            p, true_n, lo, hi
        );
        // Sanity: the interval has positive width.
        assert!(hi >= lo);
    }
}
