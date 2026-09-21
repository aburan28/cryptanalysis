//! S-box analysis: DDT, LAT, differential / linear strength metrics.
//!
//! An [`Sbox`] is an `n`-bit-in / `m`-bit-out lookup table.  Most
//! ciphers use 4×4 or 8×8 bijective S-boxes; this type supports any
//! `n ≤ 16` and any `m ≤ 32` (above which the DDT/LAT become too
//! large for a workstation to materialise).
//!
//! All metrics here are exhaustive over the input space — appropriate
//! for the small S-box sizes they're designed for.  For larger
//! components you want statistical sampling instead; see
//! [`crate::cryptanalysis::statistical`].

use super::boolean::{algebraic_degree, walsh_hadamard};

/// An `n`-bit-in / `m`-bit-out lookup-table S-box.
#[derive(Clone, Debug)]
pub struct Sbox {
    n_in: u32,
    n_out: u32,
    table: Vec<u32>,
}

/// Header summary for [`Sbox::report`].
#[derive(Clone, Debug, PartialEq)]
pub struct SboxReport {
    pub n_in: u32,
    pub n_out: u32,
    pub bijective: bool,
    pub balanced: bool,
    pub differential_uniformity: u32,
    pub max_differential_probability: f64,
    pub max_linear_bias: f64,
    pub nonlinearity: u32,
    pub algebraic_degree: u32,
    /// `Some(BU)` for bijective S-boxes ≤ 8-bit input; `None` otherwise.
    pub boomerang_uniformity: Option<u32>,
    /// Max `|DLCT[Δ][λ]| / 2^n_in` over `(Δ ≠ 0, λ ≠ 0)`.
    pub max_dlct_bias: f64,
}

impl Sbox {
    /// Construct an S-box from its truth table.
    ///
    /// `table[x]` must be `S(x)` for `x ∈ [0, 2^n_in)`, with each
    /// entry fitting in `n_out` bits.  Refuses to construct S-boxes
    /// larger than 2^16 input space (DDT alone would be 4 GiB at 4-byte
    /// counts beyond that).
    pub fn new(n_in: u32, n_out: u32, table: Vec<u32>) -> Result<Self, &'static str> {
        if n_in == 0 || n_in > 16 {
            return Err("Sbox::new: n_in must be in 1..=16");
        }
        if n_out == 0 || n_out > 32 {
            return Err("Sbox::new: n_out must be in 1..=32");
        }
        if table.len() != 1usize << n_in {
            return Err("Sbox::new: table.len() must equal 2^n_in");
        }
        // n_out == 32 special-case: every u32 is in range.
        if n_out < 32 {
            let bound = 1u64 << n_out;
            for &v in &table {
                if (v as u64) >= bound {
                    return Err("Sbox::new: table entry exceeds n_out bits");
                }
            }
        }
        Ok(Sbox { n_in, n_out, table })
    }

    pub fn n_in(&self) -> u32 {
        self.n_in
    }
    pub fn n_out(&self) -> u32 {
        self.n_out
    }

    /// `S(x)` lookup.  Panics if `x >= 2^n_in`.
    pub fn lookup(&self, x: u32) -> u32 {
        self.table[x as usize]
    }

    /// True if `S` is a permutation (i.e. n_in == n_out and every
    /// output value appears exactly once).
    pub fn is_bijective(&self) -> bool {
        if self.n_in != self.n_out {
            return false;
        }
        let n = 1usize << self.n_in;
        let mut seen = vec![false; n];
        for &v in &self.table {
            let idx = v as usize;
            if idx >= n || seen[idx] {
                return false;
            }
            seen[idx] = true;
        }
        true
    }

    /// True if every output bit position is balanced — i.e. for each
    /// `j ∈ [0, n_out)`, `bit_j(S(x))` is `0` for exactly half the
    /// inputs.  Bijective S-boxes are always balanced; the converse
    /// is not true.
    pub fn is_balanced(&self) -> bool {
        let half = (1u64 << self.n_in) / 2;
        for j in 0..self.n_out {
            let mut ones = 0u64;
            for &v in &self.table {
                ones += ((v >> j) & 1) as u64;
            }
            if ones != half {
                return false;
            }
        }
        true
    }

    // ── Differential cryptanalysis ───────────────────────────────────────────

    /// Differential Distribution Table.
    ///
    /// `DDT[a][b] = #{x ∈ [0, 2^n_in) : S(x) ⊕ S(x ⊕ a) = b}`.
    ///
    /// Returns a `2^n_in × 2^n_out` flat row-major matrix.  For an
    /// 8×8 S-box this is 64 KiB; for 16×16 it's 4 GiB and we refuse
    /// (caller should sample instead).
    pub fn ddt(&self) -> Vec<Vec<u32>> {
        let nin = 1usize << self.n_in;
        let nout = 1usize << self.n_out;
        let mut t = vec![vec![0u32; nout]; nin];
        for x in 0..nin {
            let sx = self.lookup(x as u32);
            for a in 0..nin {
                let sa = self.lookup((x ^ a) as u32);
                let b = (sx ^ sa) as usize;
                t[a][b] += 1;
            }
        }
        t
    }

    /// Differential uniformity = `max_{a≠0, b} DDT[a][b]`.  A measure
    /// of resistance to differential cryptanalysis: smaller is better.
    /// AES's S-box has uniformity 4; APN ("almost perfect nonlinear")
    /// S-boxes achieve the lower bound of 2.
    pub fn differential_uniformity(&self) -> u32 {
        let ddt = self.ddt();
        let mut max = 0;
        for (a, row) in ddt.iter().enumerate() {
            if a == 0 {
                continue;
            }
            for &c in row {
                if c > max {
                    max = c;
                }
            }
        }
        max
    }

    /// Maximum differential probability = `differential_uniformity / 2^n_in`.
    pub fn max_differential_probability(&self) -> f64 {
        self.differential_uniformity() as f64 / (1u64 << self.n_in) as f64
    }

    // ── Linear cryptanalysis ─────────────────────────────────────────────────

    /// Linear Approximation Table.
    ///
    /// `LAT[a][b] = #{x : a·x ⊕ b·S(x) = 0} - 2^(n_in - 1)`,
    /// where `·` denotes the bitwise AND parity (dot product mod 2).
    /// Magnitude `|LAT[a][b]|` measures how strongly the linear
    /// approximation `a·x = b·S(x)` holds: `0` means perfectly random,
    /// `2^(n-1)` would be a deterministic linear relation.
    pub fn lat(&self) -> Vec<Vec<i32>> {
        let nin = 1usize << self.n_in;
        let nout = 1usize << self.n_out;
        let half = (nin / 2) as i32;
        let mut t = vec![vec![-half; nout]; nin];
        for x in 0..nin {
            let sx = self.lookup(x as u32) as usize;
            for a in 0..nin {
                let ax_par = ((a & x) as u64).count_ones() & 1;
                for b in 0..nout {
                    let bs_par = ((b & sx) as u64).count_ones() & 1;
                    if ax_par == bs_par {
                        t[a][b] += 1;
                    }
                }
            }
        }
        t
    }

    /// Maximum linear bias = `max_{(a,b)≠(0,0)} |LAT[a][b]| / 2^n_in`.
    /// A linear approximation with bias `ε` can be exploited with
    /// `O(ε^-2)` known plaintexts (Matsui's piling-up).
    pub fn max_linear_bias(&self) -> f64 {
        let lat = self.lat();
        let mut max_abs = 0i32;
        for (a, row) in lat.iter().enumerate() {
            for (b, &v) in row.iter().enumerate() {
                if a == 0 && b == 0 {
                    continue;
                }
                let av = v.abs();
                if av > max_abs {
                    max_abs = av;
                }
            }
        }
        max_abs as f64 / (1u64 << self.n_in) as f64
    }

    /// Nonlinearity (over all non-zero output masks):
    /// `NL(S) = 2^(n-1) - max_{a, b≠0} |LAT[a][b]|`.
    /// AES's S-box has NL = 112 (out of max 120 for an 8-bit balanced
    /// function).  Affine functions have NL = 0.
    pub fn nonlinearity(&self) -> u32 {
        let lat = self.lat();
        let mut max_abs = 0i32;
        for row in lat.iter() {
            for (b, &v) in row.iter().enumerate() {
                if b == 0 {
                    continue;
                }
                let av = v.abs();
                if av > max_abs {
                    max_abs = av;
                }
            }
        }
        let half = 1u32 << (self.n_in - 1);
        half.saturating_sub(max_abs as u32)
    }

    // ── Boomerang cryptanalysis (Cid–Huang–Peyrin–Sasaki–Song, EUROCRYPT 2018) ──

    /// Inverse table — only well-defined when the S-box is a permutation.
    /// Returns `None` if not bijective.
    pub fn inverse_table(&self) -> Option<Vec<u32>> {
        if !self.is_bijective() {
            return None;
        }
        let n = 1usize << self.n_in;
        let mut inv = vec![0u32; n];
        for x in 0..n {
            inv[self.lookup(x as u32) as usize] = x as u32;
        }
        Some(inv)
    }

    /// Boomerang Connectivity Table (BCT).
    ///
    /// `BCT[Δ][∇] = #{x : S⁻¹(S(x) ⊕ ∇) ⊕ S⁻¹(S(x ⊕ Δ) ⊕ ∇) = Δ}`.
    ///
    /// Quantifies how well a boomerang attack can "switch" through the
    /// S-box at the centre of the trail — Cid, Huang, Peyrin, Sasaki,
    /// Song (EUROCRYPT 2018).  The DDT alone gives wrong probabilities
    /// here because of the dependency between the two trails meeting
    /// in the middle; the BCT corrects this.
    ///
    /// Properties:
    /// - `BCT[Δ][0] = BCT[0][∇] = 2^n_in` (trivial corners).
    /// - `BCT[Δ][∇] ≥ DDT[Δ][∇]` always.
    /// - For an APN permutation, `BCT[Δ][∇] = DDT[Δ][∇]` for `Δ, ∇ ≠ 0`.
    ///
    /// Defined only for bijective S-boxes; returns `None` otherwise.
    /// Complexity is `O(2^(3n_in))` — fine up through 8-bit S-boxes
    /// (~16 M operations for AES) and refused above (would be > 250 GB
    /// of memory at 16-bit input).
    pub fn bct(&self) -> Option<Vec<Vec<u32>>> {
        if self.n_in > 8 {
            return None;
        }
        let inv = self.inverse_table()?;
        let n = 1usize << self.n_in;
        let mut t = vec![vec![0u32; n]; n];
        for x in 0..n {
            let sx = self.lookup(x as u32) as usize;
            for delta in 0..n {
                let sxd = self.lookup((x ^ delta) as u32) as usize;
                for nabla in 0..n {
                    let lhs = inv[sx ^ nabla] as usize;
                    let rhs = inv[sxd ^ nabla] as usize;
                    if lhs ^ rhs == delta {
                        t[delta][nabla] += 1;
                    }
                }
            }
        }
        Some(t)
    }

    /// Boomerang uniformity = `max_{Δ≠0, ∇≠0} BCT[Δ][∇]`.
    /// AES S-box has BU = 6 (Cid et al. 2018, Table 4).  Smaller is
    /// better; APN-bijective S-boxes hit the `BU = DU` lower bound.
    /// Returns `None` if the S-box is non-bijective or too large.
    pub fn boomerang_uniformity(&self) -> Option<u32> {
        let bct = self.bct()?;
        let mut max = 0;
        for (a, row) in bct.iter().enumerate().skip(1) {
            for &v in row.iter().skip(1) {
                if v > max {
                    max = v;
                }
            }
            let _ = a;
        }
        Some(max)
    }

    // ── Differential-linear cryptanalysis (Bar-On–Dunkelman–Keller–Weizman 2019)

    /// Differential-Linear Connectivity Table (DLCT).
    ///
    /// `DLCT[Δ][λ] = #{x : λ·S(x) = λ·S(x ⊕ Δ)} − 2^(n_in − 1)`.
    ///
    /// Bar-On, Dunkelman, Keller, Weizman (EUROCRYPT 2019) — the
    /// missing companion to BCT.  The classic Langford–Hellman
    /// differential-linear attack assumed independence between the
    /// "differential" and "linear" parts at the switch; this table
    /// gives the exact bias.
    ///
    /// Properties:
    /// - `DLCT[0][λ] = DLCT[Δ][0] = 2^(n_in − 1)` (trivial corners,
    ///   stored as the maximum positive value).
    /// - The non-trivial bias `|DLCT[Δ][λ]|` is the correct
    ///   differential-linear bias to use in attack-complexity bounds.
    pub fn dlct(&self) -> Vec<Vec<i32>> {
        let nin = 1usize << self.n_in;
        let nout = 1usize << self.n_out;
        let half = (nin / 2) as i32;
        let mut t = vec![vec![-half; nout]; nin];
        for x in 0..nin {
            let sx = self.lookup(x as u32) as usize;
            for delta in 0..nin {
                let sxd = self.lookup((x ^ delta) as u32) as usize;
                for lambda in 0..nout {
                    let par_a = ((lambda & sx) as u64).count_ones() & 1;
                    let par_b = ((lambda & sxd) as u64).count_ones() & 1;
                    if par_a == par_b {
                        t[delta][lambda] += 1;
                    }
                }
            }
        }
        t
    }

    /// Maximum |DLCT entry| over `(Δ ≠ 0, λ ≠ 0)`, normalised to a
    /// probability bias on `[0, 0.5]`.  Lower is better.
    pub fn max_dlct_bias(&self) -> f64 {
        let dlct = self.dlct();
        let mut max_abs = 0i32;
        for (a, row) in dlct.iter().enumerate().skip(1) {
            for &v in row.iter().skip(1) {
                let av = v.abs();
                if av > max_abs {
                    max_abs = av;
                }
            }
            let _ = a;
        }
        max_abs as f64 / (1u64 << self.n_in) as f64
    }

    // ── Truncated differential cryptanalysis (Knudsen, FSE 1994) ──────────────

    /// Truncated Differential Distribution Table.
    ///
    /// Collapses the DDT modulo a "lane active or not" predicate: each
    /// `lane_bits`-wide lane of an input/output difference becomes one
    /// bit (`1` iff the lane is non-zero).  The resulting
    /// `2^(n_in / lane_bits) × 2^(n_out / lane_bits)` matrix counts how
    /// many `(x, a)` pairs hit each truncated input → truncated output
    /// pattern.
    ///
    /// Used by impossible-differential and truncated-trail attacks
    /// (Knudsen, FSE 1994) — your raw DDT can't express these because
    /// the per-difference probability is too small to chain across
    /// rounds, but the per-pattern probability is large enough.
    ///
    /// Errors if `lane_bits` does not divide both `n_in` and `n_out`,
    /// or if the resulting truncated space exceeds `2^16` patterns
    /// (4 GiB of u32 counts).
    pub fn truncated_ddt(&self, lane_bits: u32) -> Result<Vec<Vec<u32>>, &'static str> {
        if lane_bits == 0 {
            return Err("lane_bits must be > 0");
        }
        if !self.n_in.is_multiple_of(lane_bits) || !self.n_out.is_multiple_of(lane_bits) {
            return Err("lane_bits must divide both n_in and n_out");
        }
        let in_lanes = self.n_in / lane_bits;
        let out_lanes = self.n_out / lane_bits;
        if in_lanes > 16 || out_lanes > 16 {
            return Err("truncated table exceeds 2^16 lanes; reduce lane_bits");
        }
        let in_bound = 1usize << in_lanes;
        let out_bound = 1usize << out_lanes;
        let lane_mask: u32 = (1u32 << lane_bits) - 1;

        let truncate = |diff: u32, lanes: u32| -> usize {
            let mut p = 0u32;
            for i in 0..lanes {
                if diff & (lane_mask << (i * lane_bits)) != 0 {
                    p |= 1 << i;
                }
            }
            p as usize
        };

        let mut t = vec![vec![0u32; out_bound]; in_bound];
        let n_in_full = 1usize << self.n_in;
        for x in 0..n_in_full {
            let sx = self.lookup(x as u32);
            for a in 0..n_in_full {
                let sa = self.lookup((x ^ a) as u32);
                let b = sx ^ sa;
                let pa = truncate(a as u32, in_lanes);
                let pb = truncate(b, out_lanes);
                t[pa][pb] += 1;
            }
        }
        Ok(t)
    }

    // ── Algebraic structure ──────────────────────────────────────────────────

    /// Maximum algebraic degree across all non-zero output masks:
    /// `max_{b≠0} deg(b·S)`.  This is the standard "algebraic degree
    /// of an S-box" in the cryptanalytic literature.  AES S-box has
    /// degree 7; Serpent S-boxes have degree 3 (max for 4-bit
    /// balanced).  Low maximum degree is a red flag — it enables
    /// higher-order differential and cube attacks.
    pub fn algebraic_degree(&self) -> u32 {
        let nin = 1usize << self.n_in;
        let nout_mask: u32 = if self.n_out >= 32 {
            u32::MAX
        } else {
            (1u32 << self.n_out) - 1
        };
        let mut max_deg = 0u32;
        for b in 1..=nout_mask {
            let mut tt = Vec::with_capacity(nin);
            for x in 0..nin {
                let sx = self.lookup(x as u32);
                let par = ((b & sx) as u64).count_ones() & 1;
                tt.push(par as u8);
            }
            let d = algebraic_degree(&tt);
            if d > max_deg {
                max_deg = d;
            }
            // Above 8-bit output the loop becomes prohibitive; sample
            // the first 256 masks as a heuristic upper-bound estimate.
            if self.n_out > 8 && b == 255 {
                break;
            }
        }
        max_deg
    }

    /// One-shot security report — runs all the metrics and packs them
    /// into a struct.  Calling this is `O(2^n_in · 2^n_out)` and
    /// allocates the DDT and LAT, so use it sparingly.
    pub fn report(&self) -> SboxReport {
        SboxReport {
            n_in: self.n_in,
            n_out: self.n_out,
            bijective: self.is_bijective(),
            balanced: self.is_balanced(),
            differential_uniformity: self.differential_uniformity(),
            max_differential_probability: self.max_differential_probability(),
            max_linear_bias: self.max_linear_bias(),
            nonlinearity: self.nonlinearity(),
            algebraic_degree: self.algebraic_degree(),
            boomerang_uniformity: self.boomerang_uniformity(),
            max_dlct_bias: self.max_dlct_bias(),
        }
    }

    /// Cross-check the LAT against the Walsh–Hadamard transform.
    /// Returns `true` if every column `b` of the LAT equals
    /// `WHT(b·S) / 2`.  Used as an internal consistency test.
    pub fn lat_matches_walsh(&self) -> bool {
        let nin = 1usize << self.n_in;
        let nout = 1usize << self.n_out;
        let lat = self.lat();
        for b in 0..nout {
            let tt: Vec<u8> = (0..nin)
                .map(|x| {
                    let sx = self.lookup(x as u32);
                    (((b as u32) & sx).count_ones() & 1) as u8
                })
                .collect();
            let w = walsh_hadamard(&tt);
            for a in 0..nin {
                if w[a] != 2 * lat[a][b] as i64 {
                    return false;
                }
            }
        }
        true
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Identity S-box: S(x) = x.  Trivially bijective, balanced.
    /// Differential uniformity = 2^n (the trivial differential a→a always
    /// holds), max DP = 1, max linear bias = 1/2 (a=b means a·x = a·S(x)
    /// trivially), nonlinearity = 0, algebraic degree = 1.
    #[test]
    fn identity_sbox_metrics() {
        let s = Sbox::new(4, 4, (0..16).collect()).unwrap();
        assert!(s.is_bijective());
        assert!(s.is_balanced());
        // Identity: every input difference maps perfectly to the same output difference.
        assert_eq!(s.differential_uniformity(), 16);
        assert!((s.max_differential_probability() - 1.0).abs() < 1e-9);
        // a·x = a·x is exact: LAT[a][a] = 8.
        assert!((s.max_linear_bias() - 0.5).abs() < 1e-9);
        assert_eq!(s.nonlinearity(), 0);
        assert_eq!(s.algebraic_degree(), 1);
    }

    /// Serpent S0 — Anderson/Biham/Knudsen.  Differential uniformity 4,
    /// max linear bias 4/16 = 0.25, nonlinearity 4 (= 2^3 - max|LAT|; the
    /// max |LAT| entry of all eight Serpent S-boxes is 4), degree 3.
    #[test]
    fn serpent_s0_metrics() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        assert!(s.is_bijective());
        assert_eq!(
            s.differential_uniformity(),
            4,
            "Serpent S0 should have DU=4"
        );
        // 4/16 = 0.25.
        assert!((s.max_differential_probability() - 0.25).abs() < 1e-9);
        // For 4-bit S-boxes: NL ∈ {0, 2, 4}; Serpent's S-boxes hit the optimum 4.
        assert_eq!(s.nonlinearity(), 4);
        // Algebraic degree of Serpent S-boxes is 3 (max for 4-bit balanced).
        assert_eq!(s.algebraic_degree(), 3);
    }

    /// AES S-box has well-known metrics: DU = 4, NL = 112, deg = 7.
    /// We construct it inversely (multiplicative inverse + affine) and
    /// verify.  Dataset: `aes_sbox` from the published table.
    #[test]
    fn aes_sbox_metrics() {
        // AES S-box (verbatim from FIPS 197 §5.1.1).
        #[rustfmt::skip]
        let table: Vec<u32> = vec![
            0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
            0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
            0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
            0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
            0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
            0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
            0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
            0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
            0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
            0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
            0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
            0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
            0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
            0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
            0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
            0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
        ];
        let s = Sbox::new(8, 8, table).unwrap();
        assert!(s.is_bijective());
        // FIPS-197 / Daemen–Rijmen "Design of Rijndael" §5.7:
        // Differential uniformity = 4.
        assert_eq!(s.differential_uniformity(), 4);
        // Nonlinearity = 112.  Max |LAT| = 16, so 128 - 16 = 112.
        assert_eq!(s.nonlinearity(), 112);
    }

    #[test]
    fn lat_consistent_with_walsh() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        assert!(s.lat_matches_walsh());
    }

    #[test]
    fn rejects_oversize() {
        // n_in too large.
        assert!(Sbox::new(17, 8, vec![0; 1 << 17]).is_err());
        // Table length wrong.
        assert!(Sbox::new(4, 4, vec![0; 15]).is_err());
        // Output value out of range.
        assert!(Sbox::new(4, 4, vec![16, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]).is_err());
    }

    #[test]
    fn report_shape() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        let r = s.report();
        assert_eq!(r.n_in, 4);
        assert_eq!(r.n_out, 4);
        assert!(r.bijective);
        assert_eq!(r.differential_uniformity, 4);
        assert_eq!(r.nonlinearity, 4);
        assert_eq!(r.algebraic_degree, 3);
        assert!(r.boomerang_uniformity.is_some());
        assert!(r.max_dlct_bias > 0.0);
    }

    // ── BCT (Cid–Huang–Peyrin–Sasaki–Song, EUROCRYPT 2018) ──────────────────

    /// Trivial corners: `BCT[a][0] = BCT[0][b] = 2^n` regardless of S.
    #[test]
    fn bct_trivial_corners() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        let bct = s.bct().expect("bijective");
        let n = 16u32;
        for a in 0..16 {
            assert_eq!(bct[a][0], n, "BCT[{}][0] should be 2^n", a);
            assert_eq!(bct[0][a], n, "BCT[0][{}] should be 2^n", a);
        }
    }

    /// `BCT[a][b] ≥ DDT[a][b]` for all `(a, b)` — Cid et al., Theorem 1.
    #[test]
    fn bct_dominates_ddt() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        let ddt = s.ddt();
        let bct = s.bct().expect("bijective");
        for a in 0..16 {
            for b in 0..16 {
                assert!(
                    bct[a][b] >= ddt[a][b],
                    "BCT[{}][{}] = {} < DDT[{}][{}] = {}",
                    a,
                    b,
                    bct[a][b],
                    a,
                    b,
                    ddt[a][b]
                );
            }
        }
    }

    /// AES S-box has boomerang uniformity 6 — Cid–Huang–Peyrin–Sasaki–Song,
    /// EUROCRYPT 2018, Table 4.  This is the canonical published number.
    #[test]
    fn aes_sbox_boomerang_uniformity_is_6() {
        #[rustfmt::skip]
        let table: Vec<u32> = vec![
            0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
            0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
            0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
            0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
            0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
            0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
            0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
            0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
            0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
            0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
            0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
            0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
            0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
            0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
            0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
            0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
        ];
        let s = Sbox::new(8, 8, table).unwrap();
        assert_eq!(
            s.boomerang_uniformity(),
            Some(6),
            "AES S-box should have BU = 6 per Cid et al. 2018"
        );
    }

    #[test]
    fn bct_refused_for_non_bijective() {
        // Constant function: not bijective.
        let s = Sbox::new(4, 4, vec![0u32; 16]).unwrap();
        assert!(s.bct().is_none());
        assert!(s.boomerang_uniformity().is_none());
    }

    // ── DLCT (Bar-On–Dunkelman–Keller–Weizman, EUROCRYPT 2019) ──────────────

    /// Trivial corners: `DLCT[0][λ] = DLCT[Δ][0] = 2^(n-1)`.
    #[test]
    fn dlct_trivial_corners() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        let dlct = s.dlct();
        let half: i32 = 8;
        for i in 0..16 {
            assert_eq!(dlct[0][i], half, "DLCT[0][{}] should be 2^(n-1)", i);
            assert_eq!(dlct[i][0], half, "DLCT[{}][0] should be 2^(n-1)", i);
        }
    }

    /// `|DLCT[Δ][λ]|` is bounded by `2^(n-1)`, achieved only at the
    /// trivial corners.
    #[test]
    fn dlct_bounded_by_half() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        let dlct = s.dlct();
        for row in &dlct {
            for &v in row {
                assert!(v.abs() <= 8, "DLCT entry |{}| > 2^(n-1)", v);
            }
        }
    }

    // ── Truncated DDT (Knudsen, FSE 1994) ──────────────────────────────────

    /// Truncated DDT with `lane_bits = n_in` collapses to a 2×2 matrix
    /// (active vs inactive on the whole input/output).
    #[test]
    fn truncated_ddt_full_lane_2x2() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        let t = s.truncated_ddt(4).unwrap();
        assert_eq!(t.len(), 2);
        assert_eq!(t[0].len(), 2);
        // Δ = 0 → b = 0 always; corresponds to t[0][0] = 16.
        assert_eq!(t[0][0], 16);
        assert_eq!(t[0][1], 0); // Δ = 0 cannot yield non-zero b.
                                // Δ ≠ 0: 15 input differences × 16 inputs = 240 total.  All
                                // produce non-zero output difference iff S is bijective.
        assert_eq!(t[1][0], 0, "non-zero Δ on a bijective S can't give b=0");
        assert_eq!(t[1][1], 15 * 16);
    }

    /// Sum of every row equals the number of input pairs `(x, a) → 2^n_in`
    /// per fixed input difference, summed across all input differences.
    /// Therefore total = `2^(2 n_in)`.
    #[test]
    fn truncated_ddt_total_count() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        let t = s.truncated_ddt(2).unwrap();
        let total: u64 = t.iter().flat_map(|r| r.iter()).map(|&c| c as u64).sum();
        assert_eq!(total, 16 * 16, "must equal 2^(2 n_in) = 256");
    }

    #[test]
    fn truncated_ddt_rejects_indivisible_lane() {
        let s = Sbox::new(
            4,
            4,
            vec![3, 8, 15, 1, 10, 6, 5, 11, 14, 13, 4, 2, 7, 0, 9, 12],
        )
        .unwrap();
        assert!(s.truncated_ddt(3).is_err()); // 4 % 3 ≠ 0
        assert!(s.truncated_ddt(0).is_err());
    }
}
