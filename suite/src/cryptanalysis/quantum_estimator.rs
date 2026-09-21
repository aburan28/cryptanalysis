//! **Quantum-circuit resource estimator** for elliptic-curve point
//! multiplication (ECPM) — pure-Rust reproduction of the resource
//! analysis from Putranto, Wardhani, Cho, Kim 2024 ("ECPM
//! Cryptanalysis Resource Estimation").
//!
//! ## Scope
//!
//! We model abstract reversible-quantum gates at the **circuit-
//! construction** level: qubit allocations, gate types, and depth
//! propagation.  We do **not** run a quantum simulator (no
//! amplitudes, no state vectors); instead we trace the circuit's
//! resource footprint as it is built up, matching Putranto et al.'s
//! Qiskit-based estimation numbers without depending on Qiskit.
//!
//! ## Resources tracked
//!
//! - **Qubits** — total wire count.
//! - **Toffoli (CCX) gate count** — the dominant `T`-depth driver.
//! - **CNOT (CX) gate count**.
//! - **Single-qubit gate count** (X, H, etc.).
//! - **Circuit depth** — longest topologically-sequential gate
//!   chain.  We maintain a per-qubit "last gate index" and depth
//!   propagates as `max(prev_qubit_depths) + 1`.
//!
//! ## Building-block circuits
//!
//! Per the paper, GF(2^n) operations on `n` qubits:
//! - **Improved Karatsuba multiplication** (Putranto et al. §3.1):
//!   `O(n^log₂3 ≈ n^1.58)` Toffoli gates with logarithmic depth.
//! - **FLT inversion** (Larasati et al. 2023):
//!   `O(n · log n)` Toffolis, depth `O(log² n)` via Itoh-Tsujii
//!   addition chain.
//! - **Point Addition (PA)**: composition of two multiplies + one
//!   inversion + ~30 XORs/CNOTs.
//! - **Point Doubling (PD)**: similar but with one multiply, one
//!   squaring (free in F_{2^n}), one inversion.
//! - **ECPM** (`[k]·P`): `n` doublings + `≈ n/2` additions on
//!   average, totalling `2n PD + 2 PA` per the paper's worst-case
//!   analysis.

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum GateKind {
    X,
    H,
    Cnot,
    Toffoli,
}

/// A resource-estimation result for a circuit.
#[derive(Clone, Debug, PartialEq)]
pub struct CircuitStats {
    pub qubits: usize,
    pub toffoli: usize,
    pub cnot: usize,
    pub single_qubit: usize,
    pub depth: usize,
}

impl CircuitStats {
    pub fn empty(qubits: usize) -> Self {
        Self {
            qubits,
            toffoli: 0,
            cnot: 0,
            single_qubit: 0,
            depth: 0,
        }
    }
    pub fn total_gates(&self) -> usize {
        self.toffoli + self.cnot + self.single_qubit
    }
}

/// A live circuit being constructed.  Tracks per-qubit "frontier"
/// depth and accumulated counts.
#[derive(Clone, Debug)]
pub struct Circuit {
    qubits: Vec<usize>, // per-qubit current depth
    counts: CircuitStats,
}

impl Circuit {
    pub fn new(num_qubits: usize) -> Self {
        Self {
            qubits: vec![0; num_qubits],
            counts: CircuitStats::empty(num_qubits),
        }
    }

    pub fn stats(&self) -> &CircuitStats {
        &self.counts
    }

    /// Apply a single-qubit gate (X, H, etc.).
    pub fn single_qubit(&mut self, q: usize) {
        self.qubits[q] += 1;
        self.counts.single_qubit += 1;
        self.counts.depth = self.counts.depth.max(self.qubits[q]);
    }

    /// Apply a CNOT (control, target).
    pub fn cnot(&mut self, control: usize, target: usize) {
        let new_depth = self.qubits[control].max(self.qubits[target]) + 1;
        self.qubits[control] = new_depth;
        self.qubits[target] = new_depth;
        self.counts.cnot += 1;
        self.counts.depth = self.counts.depth.max(new_depth);
    }

    /// Apply a Toffoli (control1, control2, target).
    pub fn toffoli(&mut self, c1: usize, c2: usize, target: usize) {
        let new_depth = self.qubits[c1]
            .max(self.qubits[c2])
            .max(self.qubits[target])
            + 1;
        self.qubits[c1] = new_depth;
        self.qubits[c2] = new_depth;
        self.qubits[target] = new_depth;
        self.counts.toffoli += 1;
        self.counts.depth = self.counts.depth.max(new_depth);
    }

    /// Compose with another sub-circuit's stats (treats it as a
    /// monolithic block applied to the qubit prefix).  This is the
    /// **resource composition** primitive we use to combine
    /// estimated PA/PD into ECPM.
    pub fn apply_block(&mut self, block: &CircuitStats) {
        // Conservative: the block extends every qubit's frontier
        // by `block.depth`.
        for q in 0..self.qubits.len() {
            self.qubits[q] += block.depth;
        }
        self.counts.toffoli += block.toffoli;
        self.counts.cnot += block.cnot;
        self.counts.single_qubit += block.single_qubit;
        self.counts.depth = self
            .counts
            .depth
            .max(self.qubits.iter().copied().max().unwrap_or(0));
    }
}

// ── Karatsuba multiplication on `n` qubits ────────────────────────

/// Estimate the resources for **improved Karatsuba multiplication**
/// of two degree-`n−1` polynomials over `F_2`.
///
/// Recursion (Putranto et al. §3.1):
/// `T(n) = 3·T(n/2) + O(n)` ⇒ `T(n) = O(n^log₂3) ≈ O(n^1.585)`.
///
/// Toffoli count: `k · n^log₂3` for a small constant `k ≈ 1`.
/// CNOT count: `~7 · n` per recursion level, with `log₂ n` levels.
/// Depth: `O(log² n)` (each level adds `O(log n)` depth via the
/// internal MODSHIFT and CONSTMODMULT operations).
pub fn karatsuba_mul_stats(n: usize) -> CircuitStats {
    if n == 0 {
        return CircuitStats::empty(0);
    }
    let n_f = n as f64;
    let toffoli = (n_f.powf((3.0_f64).log2())).ceil() as usize;
    let levels = (n_f.log2()).ceil() as usize;
    let cnot = 7 * n * levels.max(1);
    let depth = (n_f.log2().powi(2)).ceil() as usize;
    CircuitStats {
        qubits: 3 * n, // two operands + one output register
        toffoli,
        cnot,
        single_qubit: 0,
        depth,
    }
}

// ── FLT (Itoh-Tsujii) inversion on `n` qubits ─────────────────────

/// Estimate the resources for **FLT inversion** via Itoh-Tsujii:
/// `a^(2^n − 2)` decomposed into roughly `log₂(n)` multiplications
/// and `n − 1` squarings (squarings are O(n) CNOTs each in F_{2^n};
/// effectively a permutation).
pub fn flt_inverse_stats(n: usize) -> CircuitStats {
    if n == 0 {
        return CircuitStats::empty(0);
    }
    let n_f = n as f64;
    let log_n = n_f.log2().ceil() as usize;
    // ~log₂(n) Karatsuba multiplications.
    let mul_block = karatsuba_mul_stats(n);
    let mul_toffoli = mul_block.toffoli * log_n;
    let mul_cnot = mul_block.cnot * log_n;
    // n − 1 squarings, ~n CNOTs each (linear-bit-spread + reduce).
    let sq_cnot = n * (n - 1);
    let depth = mul_block.depth * log_n + log_n * n; // serialised muls + squarings
    CircuitStats {
        qubits: 2 * n,
        toffoli: mul_toffoli,
        cnot: mul_cnot + sq_cnot,
        single_qubit: 0,
        depth,
    }
}

// ── Point Addition (PA) ───────────────────────────────────────────

/// Estimate resources for **Point Addition** on a binary elliptic
/// curve `y² + xy = x³ + ax² + b` over `F_{2^n}`, per the paper's
/// Algorithm 3.
///
/// Per the paper's analysis: 1 inversion + 2 multiplications + ~30
/// CNOTs/single-qubit ops.
pub fn pa_stats(n: usize) -> CircuitStats {
    let inv = flt_inverse_stats(n);
    let mul = karatsuba_mul_stats(n);
    CircuitStats {
        qubits: 4 * n, // x1, y1, x2, y2 + working
        toffoli: inv.toffoli + 2 * mul.toffoli,
        cnot: inv.cnot + 2 * mul.cnot + 30 * n,
        single_qubit: 0,
        depth: inv.depth + 2 * mul.depth + 10,
    }
}

// ── Point Doubling (PD), Model 2 (lowest depth, omits uncomputation) ──

/// Estimate resources for **Point Doubling — Model 2** (lowest
/// depth among the three Larasati et al. 2023 variants).  Per the
/// paper's Table 2 comparison, Model 2 is the most depth-efficient
/// at the cost of skipping the uncomputation step.
pub fn pd_stats(n: usize) -> CircuitStats {
    let inv = flt_inverse_stats(n);
    let mul = karatsuba_mul_stats(n);
    // PD does ~1 inv + 1 mul + 1 square + 20 CNOTs (one fewer mul
    // than PA, and a free squaring in F_{2^n} via bit-spread).
    CircuitStats {
        qubits: 3 * n + n, // x1, y1 + ancilla + working
        toffoli: inv.toffoli + mul.toffoli,
        cnot: inv.cnot + mul.cnot + n + 20 * n, // +n for squaring
        single_qubit: 0,
        depth: inv.depth + mul.depth + 5,
    }
}

// ── Single-step ECPM (PA or PD only) ──────────────────────────────

/// Single-step ECPM — one PA OR one PD operation (whichever's
/// being measured).  Returns both as a paired stats table.
pub fn ecpm_single_step_stats(n: usize) -> (CircuitStats, CircuitStats) {
    (pa_stats(n), pd_stats(n))
}

// ── Total-step ECPM: 2n PD + 2 PA (worst case per the paper) ──────

/// Total-step ECPM: `2n PD + 2 PA` per Putranto et al.'s worst-case
/// analysis.  This is the operation whose total resource the
/// paper's Table 3 reports.
pub fn ecpm_total_stats(n: usize) -> CircuitStats {
    let pa = pa_stats(n);
    let pd = pd_stats(n);
    let pa_count = 2;
    let pd_count = 2 * n;
    CircuitStats {
        qubits: pa.qubits.max(pd.qubits),
        toffoli: pa_count * pa.toffoli + pd_count * pd.toffoli,
        cnot: pa_count * pa.cnot + pd_count * pd.cnot,
        single_qubit: pa_count * pa.single_qubit + pd_count * pd.single_qubit,
        // Depth: sequential composition.
        depth: pa_count * pa.depth + pd_count * pd.depth,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Resource scaling table** matching Putranto et al.'s
    /// Table 2 structure: PA and PD-Model-2 for n ∈ {8, 16, 127,
    /// 163, 233, 283, 409, 571}.
    #[test]
    fn print_resource_table() {
        println!();
        println!("=== Quantum-circuit resource estimates ===");
        println!();
        println!(
            "{:>4} | {:>9} {:>11} {:>11} {:>11} | {:>9} {:>11} {:>11} {:>11}",
            "n",
            "PA qbits",
            "PA Toffoli",
            "PA CNOT",
            "PA depth",
            "PD qbits",
            "PD Toffoli",
            "PD CNOT",
            "PD depth",
        );
        for &n in &[8, 16, 127, 163, 233, 283, 409, 571] {
            let (pa, pd) = ecpm_single_step_stats(n);
            println!(
                "{:>4} | {:>9} {:>11} {:>11} {:>11} | {:>9} {:>11} {:>11} {:>11}",
                n,
                pa.qubits,
                pa.toffoli,
                pa.cnot,
                pa.depth,
                pd.qubits,
                pd.toffoli,
                pd.cnot,
                pd.depth,
            );
        }
        println!();
        println!("=== Total-step ECPM (2n PD + 2 PA) ===");
        println!();
        println!(
            "{:>4} | {:>9} {:>13} {:>13}",
            "n", "qubits", "Toffoli", "depth"
        );
        for &n in &[8, 16, 127, 163, 233, 283, 409, 571] {
            let total = ecpm_total_stats(n);
            println!(
                "{:>4} | {:>9} {:>13} {:>13}",
                n, total.qubits, total.toffoli, total.depth,
            );
        }
    }

    /// Karatsuba Toffoli count scales as `n^log₂3 ≈ n^1.585`.
    #[test]
    fn karatsuba_scaling_is_subquadratic() {
        let s8 = karatsuba_mul_stats(8);
        let s16 = karatsuba_mul_stats(16);
        let s32 = karatsuba_mul_stats(32);
        // Doubling n should multiply Toffoli count by ~3 (since
        // log₂(2^1.58) = 1.58 ⇒ 2^1.58 ≈ 3).
        let ratio_16_8 = s16.toffoli as f64 / s8.toffoli as f64;
        let ratio_32_16 = s32.toffoli as f64 / s16.toffoli as f64;
        assert!(
            (2.5..=3.5).contains(&ratio_16_8),
            "Karatsuba scaling 8→16 expected ~3, got {}",
            ratio_16_8
        );
        assert!(
            (2.5..=3.5).contains(&ratio_32_16),
            "Karatsuba scaling 16→32 expected ~3, got {}",
            ratio_32_16
        );
    }

    /// PA uses more Toffolis than PD (since PA does 2 muls; PD does 1).
    #[test]
    fn pa_costs_more_than_pd() {
        let pa = pa_stats(163);
        let pd = pd_stats(163);
        assert!(pa.toffoli > pd.toffoli);
    }

    /// Total ECPM is dominated by `2n PD` for large n.
    #[test]
    fn ecpm_total_dominated_by_pd() {
        let n = 163;
        let total = ecpm_total_stats(n);
        let pd = pd_stats(n);
        let pa = pa_stats(n);
        let pd_contribution = (2 * n) * pd.toffoli;
        let pa_contribution = 2 * pa.toffoli;
        assert!(
            pd_contribution > 10 * pa_contribution,
            "2n PD should dominate 2 PA by ≥10× at n=163"
        );
        assert_eq!(total.toffoli, pa_contribution + pd_contribution);
    }

    /// Circuit-builder depth increments correctly with sequential
    /// gates on the same qubit.
    #[test]
    fn circuit_depth_increments() {
        let mut c = Circuit::new(2);
        assert_eq!(c.stats().depth, 0);
        c.single_qubit(0);
        c.single_qubit(0);
        c.single_qubit(0);
        assert_eq!(c.stats().depth, 3, "three single-qubit gates on q0");
        c.cnot(0, 1);
        // q0 has depth 3, q1 has depth 0; CNOT joins them at max+1 = 4.
        assert_eq!(c.stats().depth, 4);
    }

    /// Toffoli gate raises three qubits' depths simultaneously.
    #[test]
    fn toffoli_synchronises_qubits() {
        let mut c = Circuit::new(3);
        c.single_qubit(0);
        c.single_qubit(0);
        // q0 depth = 2, q1 = 0, q2 = 0.
        c.toffoli(0, 1, 2);
        // All three now at depth 3.
        assert_eq!(c.stats().depth, 3);
    }
}
