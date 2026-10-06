//! # Descent incidence-graph expansion — the P2 predictor.
//!
//! Implements the combinatorial predictor at the heart of the
//! proof-complexity bridge (`research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md` §3): the
//! **expansion `γ` of the Weil-descent incidence (Tanner) graph**, built
//! from the field's multiplication **structure-constant tensor**
//! `c_{ikj}` defined by `z^i · z^k ≡ Σ_j c_{ikj} z^j (mod m(z))`.
//!
//! ## Why this graph
//!
//! After Weil descent of binary Semaev `S₃`, the genuinely quadratic part
//! is the bilinear term `X₁·X₂ = (Σ_i a_i z^i)(Σ_k b_k z^k)`. Coordinate
//! `j` of that product is `Σ_{i,k : c_{ikj}=1} a_i b_k`, so **equation `j`
//! contains the monomial `a_i b_k` iff `c_{ikj} = 1`**. The bipartite
//! incidence graph
//!
//! ```text
//!   left  = equations           j ∈ {0, …, n−1}
//!   right = factor-base bits     i ∈ {0, …, n'−1}   (the subspace V)
//!   edge (j, i)  ⇔  ∃ k < n' : c_{ikj} = 1
//! ```
//!
//! is therefore a **curve-independent (field, basis) invariant** — exactly
//! what prediction P5 (curve-independence of `D*`, confirmed in workflow
//! iteration 1) says the predictor should be keyed on.
//!
//! ## What expansion predicts
//!
//! Proof complexity (Ben-Sasson–Wigderson; Alekhnovich–Razborov) says a
//! **high-expansion** constraint graph forces a **high** Polynomial-Calculus
//! refutation degree. Via the bridge `D* ≍ PC-degree`, the central
//! conjecture is
//!
//! ```text
//!   D* = Θ( min( m·n' ,  γ·n ) )         (proposal §3)
//! ```
//!
//! so **`D*` increases with `γ`** (NOT `1/γ`): low-expansion descents
//! (subfield / sparse-normal bases) → small `D*` → the first-fall
//! assumption holds *there*; high-expansion generic descents → large `D*`
//! → the assumption fails. Prediction **P2** is thus a *positive* monotone
//! relation between measured `D*` and computed `γ`.
//!
//! ## Two expansion measures
//!
//! - **Spectral gap** `γ_spec = 1 − σ₂` where `σ₂` is the second-largest
//!   singular value of the degree-normalized biadjacency matrix
//!   (`σ₁ = 1`). Cheap (a small symmetric eigensolve) and defined at
//!   cryptographic `n`.
//! - **Unique-neighbor (boundary) expansion** `γ_bd = min_S |∂S|/|S|`
//!   over nonempty left-subsets `S` (`∂S` = right vertices with exactly
//!   one neighbour in `S`). This is the quantity the BW degree bound
//!   actually uses; computed by subset scan (full for small `n`, capped
//!   subset size otherwise).
//!
//! ## References
//!
//! See `research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md`. Core: Ben-Sasson–Wigderson
//! 2001 (boundary expansion ⇒ width/degree), Alekhnovich–Razborov 2001.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};

// ── Structure-constant tensor ───────────────────────────────────────

/// The multiplication structure-constant tensor `c_{ikj}` of `F_{2ⁿ}` in
/// the polynomial basis `{1, z, …, z^{n−1}}` defined by `irr`:
/// `c[i][k][j] = true` iff `z^i · z^k ≡ … + z^j + … (mod m(z))`.
///
/// Reuses the tested `F2mElement` multiplication, so this is exactly the
/// field arithmetic the rest of the crate uses.
pub fn multiplication_tensor(n: u32, irr: &IrreduciblePoly) -> Vec<Vec<Vec<bool>>> {
    let nn = n as usize;
    let mut c = vec![vec![vec![false; nn]; nn]; nn];
    for i in 0..nn {
        let zi = F2mElement::from_bit_positions(&[i as u32], n);
        for k in 0..nn {
            let zk = F2mElement::from_bit_positions(&[k as u32], n);
            let prod = zi.mul(&zk, irr);
            let raw = prod.raw_bits();
            for j in 0..nn {
                let w = j / 64;
                let bit = j % 64;
                if (raw.get(w).copied().unwrap_or(0) >> bit) & 1 == 1 {
                    c[i][k][j] = true;
                }
            }
        }
    }
    c
}

// ── Incidence (Tanner) graphs ───────────────────────────────────────

/// Bipartite incidence graph as a biadjacency matrix `B[j][i]`
/// (`left × right` = equations × variables).
#[derive(Clone, Debug)]
pub struct Biadjacency {
    /// `b[j][i] = true` iff right-vertex `i` is adjacent to left-vertex `j`.
    pub b: Vec<Vec<bool>>,
    pub left: usize,
    pub right: usize,
}

impl Biadjacency {
    pub fn edges(&self) -> usize {
        self.b.iter().flatten().filter(|x| **x).count()
    }
    pub fn left_degrees(&self) -> Vec<usize> {
        self.b
            .iter()
            .map(|row| row.iter().filter(|x| **x).count())
            .collect()
    }
    pub fn right_degrees(&self) -> Vec<usize> {
        (0..self.right)
            .map(|i| (0..self.left).filter(|&j| self.b[j][i]).count())
            .collect()
    }
}

/// **Canonical, curve-independent** incidence graph from the multiplication
/// tensor: `left = n` equations (output coordinates `j`), `right = n'`
/// factor-base bit-variables (`i < n'`), edge `(j, i)` iff some `z^i · z^k`
/// (`k < n'`) contributes to coordinate `j`.
pub fn tensor_incidence(n: u32, n_sub: u32, irr: &IrreduciblePoly) -> Biadjacency {
    assert!(n_sub >= 1 && n_sub <= n);
    let c = multiplication_tensor(n, irr);
    let left = n as usize;
    let right = n_sub as usize;
    let mut b = vec![vec![false; right]; left];
    for j in 0..left {
        for i in 0..right {
            // edge iff ∃ k < n_sub with c[i][k][j].
            let mut hit = false;
            for k in 0..right {
                if c[i][k][j] {
                    hit = true;
                    break;
                }
            }
            b[j][i] = hit;
        }
    }
    Biadjacency { b, left, right }
}

/// **System-based** incidence graph from the *actual* restricted
/// Weil-descent equations of binary Semaev `S₃`. Unlike
/// [`tensor_incidence`] (which uses only the bilinear `X₁·X₂` term, whose
/// products stay below degree `n` in the refutable regime `2n' ≤ n` and so
/// are **basis-independent**), this reads the full descended system —
/// including the Frobenius-squared terms `(X₁X₂)²` and `(X₁+X₂)²x₃²`,
/// whose exponents `z^k ↦ z^{2k}` reach `2(n−1)` and therefore **do**
/// trigger reduction mod `m(z)`. That reduction is where basis dependence
/// — and hence the variation `D*` can correlate with — actually lives.
///
/// `left = n` equations, `right = 2n'` bit-variables; edge `(j, i)` iff
/// variable `i` appears in equation `j` (in any monomial, linear or
/// quadratic). The graph depends on `(field, basis, x₃)`; we expose the
/// `x₃`-dependence so a caller can confirm curve/target-independence (P5)
/// or average over targets.
pub fn system_incidence(
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
) -> Biadjacency {
    use crate::cryptanalysis::ffd_harness::{quad_monomial_index, weil_descend_s3};
    use crate::cryptanalysis::pc_degree_harness::restrict_to_subspace;
    let full = weil_descend_s3(n, irr, b, x3);
    let eqs = restrict_to_subspace(&full, n, n_sub);
    let left = n as usize;
    let right = 2 * n_sub as usize;
    let nv = right as u32;
    let mut bb = vec![vec![false; right]; left];
    for (j, eq) in eqs.iter().enumerate() {
        // Linear occurrences.
        for i in 0..right {
            if eq.coeffs.get(1 + i).copied().unwrap_or(false) {
                bb[j][i] = true;
            }
        }
        // Quadratic occurrences x_a·x_c put both a and c into equation j.
        for a in 0..nv {
            for c in (a + 1)..nv {
                let idx = quad_monomial_index(a, c, nv);
                if idx < eq.coeffs.len() && eq.coeffs[idx] {
                    bb[j][a as usize] = true;
                    bb[j][c as usize] = true;
                }
            }
        }
    }
    Biadjacency { b: bb, left, right }
}

// ── Spectral expansion ──────────────────────────────────────────────

/// Spectral expansion of a biadjacency matrix: returns
/// `(sigma_2, gamma_spec)` where `sigma_2` is the second-largest singular
/// value of the degree-normalized biadjacency `D_L^{-1/2} B D_R^{-1/2}`
/// (the largest is `1` for a connected graph) and `gamma_spec = 1 −
/// sigma_2 ∈ [0, 1]`. Higher `gamma_spec` ⇒ better expander.
pub fn spectral_expansion(g: &Biadjacency) -> (f64, f64) {
    let l = g.left;
    let r = g.right;
    if l == 0 || r == 0 {
        return (0.0, 0.0);
    }
    let ld = g.left_degrees();
    let rd = g.right_degrees();
    // Normalized biadjacency N[j][i] = B[j][i]/sqrt(ld[j]*rd[i]).
    let mut nrm = vec![vec![0.0f64; r]; l];
    for j in 0..l {
        for i in 0..r {
            if g.b[j][i] && ld[j] > 0 && rd[i] > 0 {
                nrm[j][i] = 1.0 / ((ld[j] as f64) * (rd[i] as f64)).sqrt();
            }
        }
    }
    // Gram matrix M = Nᵀ N  (r × r), symmetric PSD; singular values of N =
    // sqrt(eigenvalues of M).
    let mut m = vec![vec![0.0f64; r]; r];
    for a in 0..r {
        for c in a..r {
            let mut s = 0.0;
            for j in 0..l {
                s += nrm[j][a] * nrm[j][c];
            }
            m[a][c] = s;
            m[c][a] = s;
        }
    }
    let mut eig = jacobi_eigenvalues(&m);
    // Sort descending.
    eig.sort_by(|x, y| y.partial_cmp(x).unwrap_or(std::cmp::Ordering::Equal));
    let sigma1 = eig.first().map(|&l| l.max(0.0).sqrt()).unwrap_or(0.0);
    let sigma2 = eig.get(1).map(|&l| l.max(0.0).sqrt()).unwrap_or(0.0);
    // Normalize against sigma1 (should be ~1) for numerical robustness.
    let s2 = if sigma1 > 1e-12 {
        sigma2 / sigma1
    } else {
        sigma2
    };
    let s2 = s2.clamp(0.0, 1.0);
    (s2, 1.0 - s2)
}

/// Cyclic Jacobi eigenvalue iteration for a small real symmetric matrix.
/// Returns the eigenvalues (unsorted). Adequate for the `r ≤ few hundred`
/// sizes here; `O(r³)` per sweep, a handful of sweeps.
fn jacobi_eigenvalues(mat: &[Vec<f64>]) -> Vec<f64> {
    let n = mat.len();
    if n == 0 {
        return vec![];
    }
    let mut a: Vec<Vec<f64>> = mat.to_vec();
    let max_sweeps = 100;
    for _ in 0..max_sweeps {
        // Off-diagonal Frobenius norm.
        let mut off = 0.0;
        for p in 0..n {
            for q in (p + 1)..n {
                off += a[p][q] * a[p][q];
            }
        }
        if off <= 1e-24 {
            break;
        }
        for p in 0..n {
            for q in (p + 1)..n {
                if a[p][q].abs() < 1e-18 {
                    continue;
                }
                let app = a[p][p];
                let aqq = a[q][q];
                let apq = a[p][q];
                let theta = (aqq - app) / (2.0 * apq);
                let t = theta.signum() / (theta.abs() + (theta * theta + 1.0).sqrt());
                let cth = 1.0 / (t * t + 1.0).sqrt();
                let sth = t * cth;
                // Rotate.
                for i in 0..n {
                    let aip = a[i][p];
                    let aiq = a[i][q];
                    a[i][p] = cth * aip - sth * aiq;
                    a[i][q] = sth * aip + cth * aiq;
                }
                for i in 0..n {
                    let api = a[p][i];
                    let aqi = a[q][i];
                    a[p][i] = cth * api - sth * aqi;
                    a[q][i] = sth * api + cth * aqi;
                }
            }
        }
    }
    (0..n).map(|i| a[i][i]).collect()
}

// ── Unique-neighbor (boundary) expansion ────────────────────────────

/// Unique-neighbor (boundary) expansion `γ_bd = min_{∅≠S⊆left, |S|≤cap}
/// |∂S| / |S|`, where `∂S` is the set of right-vertices adjacent to
/// **exactly one** vertex of `S`. This is the Ben-Sasson–Wigderson
/// boundary-expansion quantity that lower-bounds the PC refutation degree.
///
/// For `left ≤ 16` every nonempty subset is scanned; for larger graphs
/// only subsets of size `≤ subset_cap` are scanned (still a valid upper
/// bound on the true minimum over small sets, which is what the degree
/// bound uses).
pub fn boundary_expansion(g: &Biadjacency, subset_cap: usize) -> f64 {
    let l = g.left;
    if l == 0 {
        return 0.0;
    }
    let mut best = f64::INFINITY;
    if l <= 16 {
        // Full scan over all nonempty subsets.
        for mask in 1u32..(1u32 << l) {
            let s: Vec<usize> = (0..l).filter(|&j| (mask >> j) & 1 == 1).collect();
            let ratio = unique_neighbor_ratio(g, &s);
            if ratio < best {
                best = ratio;
            }
        }
    } else {
        // Capped: scan subsets of size 1..=subset_cap.
        let cap = subset_cap.max(1).min(l);
        let mut combo = Vec::new();
        scan_combinations(g, l, cap, 0, &mut combo, &mut best);
    }
    if best.is_finite() {
        best
    } else {
        0.0
    }
}

fn unique_neighbor_ratio(g: &Biadjacency, s: &[usize]) -> f64 {
    if s.is_empty() {
        return f64::INFINITY;
    }
    let mut boundary = 0usize;
    for i in 0..g.right {
        let mut count = 0usize;
        for &j in s {
            if g.b[j][i] {
                count += 1;
                if count > 1 {
                    break;
                }
            }
        }
        if count == 1 {
            boundary += 1;
        }
    }
    boundary as f64 / s.len() as f64
}

fn scan_combinations(
    g: &Biadjacency,
    l: usize,
    cap: usize,
    start: usize,
    combo: &mut Vec<usize>,
    best: &mut f64,
) {
    if !combo.is_empty() {
        let ratio = unique_neighbor_ratio(g, combo);
        if ratio < *best {
            *best = ratio;
        }
    }
    if combo.len() == cap {
        return;
    }
    for j in start..l {
        combo.push(j);
        scan_combinations(g, l, cap, j + 1, combo, best);
        combo.pop();
    }
}

// ── Full report ─────────────────────────────────────────────────────

#[derive(Clone, Debug)]
pub struct ExpansionReport {
    pub n: u32,
    pub n_sub: u32,
    pub left: usize,
    pub right: usize,
    pub edges: usize,
    pub avg_left_degree: f64,
    /// Second singular value of the normalized biadjacency.
    pub sigma2: f64,
    /// Spectral expansion `1 − σ₂`.
    pub gamma_spectral: f64,
    /// Unique-neighbor boundary expansion.
    pub gamma_boundary: f64,
}

/// Compute all expansion measures for a prebuilt incidence graph.
pub fn report_from_graph(n: u32, n_sub: u32, g: &Biadjacency) -> ExpansionReport {
    let (sigma2, gamma_spectral) = spectral_expansion(g);
    let gamma_boundary = boundary_expansion(g, 4);
    let edges = g.edges();
    let avg_left_degree = if g.left > 0 {
        edges as f64 / g.left as f64
    } else {
        0.0
    };
    ExpansionReport {
        n,
        n_sub,
        left: g.left,
        right: g.right,
        edges,
        avg_left_degree,
        sigma2,
        gamma_spectral,
        gamma_boundary,
    }
}

/// Build the canonical **tensor** incidence graph for `(n, n')` and report
/// all expansion measures. Curve-independent — but note that in the
/// refutable regime `2n' ≤ n` this graph is also **basis-independent**
/// (the bilinear products never trigger reduction), so it is *not* a useful
/// P2 predictor there. Use [`system_expansion_report`] for P2.
pub fn expansion_report(n: u32, n_sub: u32, irr: &IrreduciblePoly) -> ExpansionReport {
    let g = tensor_incidence(n, n_sub, irr);
    report_from_graph(n, n_sub, &g)
}

/// Build the **system** incidence graph (full descended `S₃`, including the
/// basis-sensitive Frobenius-squared terms) and report all expansion
/// measures. This is the P2 predictor: it varies across bases at fixed
/// `(n, n')` precisely because the squared terms force reduction mod `m(z)`.
pub fn system_expansion_report(
    n: u32,
    n_sub: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x3: &F2mElement,
) -> ExpansionReport {
    let g = system_incidence(n, n_sub, irr, b, x3);
    report_from_graph(n, n_sub, &g)
}

// ── Spearman rank correlation (for the G-P2 gate) ───────────────────

/// Spearman rank correlation `ρ_s` between paired samples `(x_k, y_k)`.
/// Returns `None` if fewer than 3 pairs or zero variance. Used by gate
/// G-P2: a *positive* `ρ_s` between computed `γ` and measured `D*` is the
/// theory-predicted relation.
pub fn spearman(xs: &[f64], ys: &[f64]) -> Option<f64> {
    if xs.len() != ys.len() || xs.len() < 3 {
        return None;
    }
    let rx = ranks(xs);
    let ry = ranks(ys);
    pearson(&rx, &ry)
}

fn ranks(v: &[f64]) -> Vec<f64> {
    let n = v.len();
    let mut idx: Vec<usize> = (0..n).collect();
    idx.sort_by(|&a, &b| v[a].partial_cmp(&v[b]).unwrap_or(std::cmp::Ordering::Equal));
    let mut rank = vec![0.0f64; n];
    let mut i = 0;
    while i < n {
        let mut j = i;
        // Group ties (equal values) and assign average rank.
        while j + 1 < n && (v[idx[j + 1]] - v[idx[i]]).abs() < 1e-12 {
            j += 1;
        }
        let avg = ((i + j) as f64) / 2.0 + 1.0; // ranks are 1-based
        for k in i..=j {
            rank[idx[k]] = avg;
        }
        i = j + 1;
    }
    rank
}

fn pearson(x: &[f64], y: &[f64]) -> Option<f64> {
    let n = x.len() as f64;
    let mx = x.iter().sum::<f64>() / n;
    let my = y.iter().sum::<f64>() / n;
    let mut sxy = 0.0;
    let mut sxx = 0.0;
    let mut syy = 0.0;
    for k in 0..x.len() {
        let dx = x[k] - mx;
        let dy = y[k] - my;
        sxy += dx * dy;
        sxx += dx * dx;
        syy += dy * dy;
    }
    if sxx < 1e-15 || syy < 1e-15 {
        return None;
    }
    Some(sxy / (sxx * syy).sqrt())
}

// ── Basis enumeration (F_2-polynomial irreducibility, bit-packed) ───
//
// To test prediction P2 cleanly we must vary the expansion `γ` while
// holding `(n, n')` fixed — i.e. vary the *basis*, which means varying the
// defining irreducible polynomial `m(z)` of `F_{2ⁿ}`. These helpers
// enumerate irreducible polynomials of a given degree using Rabin's test,
// operating on degree-`≤ n` F_2-polynomials packed as `u128` bitmasks
// (bit `k` = coefficient of `z^k`). Valid for `n ≤ 31` (squaring doubles
// degree to `≤ 62` before reduction, comfortably inside `u128`).

/// Degree of a bit-packed F_2 polynomial, or `None` for the zero poly.
fn f2_deg(a: u128) -> Option<u32> {
    if a == 0 {
        None
    } else {
        Some(127 - a.leading_zeros())
    }
}

/// Reduce `a` modulo `f` (both bit-packed F_2 polynomials).
fn f2_rem(mut a: u128, f: u128) -> u128 {
    let df = f2_deg(f).expect("modulus must be nonzero");
    while let Some(da) = f2_deg(a) {
        if da < df {
            break;
        }
        a ^= f << (da - df);
    }
    a
}

/// Square a bit-packed F_2 polynomial (spread bits: `z^k ↦ z^{2k}`), then
/// reduce mod `f`.
fn f2_sqr_mod(a: u128, f: u128) -> u128 {
    let mut spread: u128 = 0;
    let mut x = a;
    let mut k = 0;
    while x != 0 {
        if x & 1 == 1 {
            spread |= 1u128 << (2 * k);
        }
        x >>= 1;
        k += 1;
    }
    f2_rem(spread, f)
}

/// gcd of two bit-packed F_2 polynomials.
fn f2_gcd(mut a: u128, mut b: u128) -> u128 {
    while b != 0 {
        let r = f2_rem(a, b);
        a = b;
        b = r;
    }
    a
}

/// Distinct prime factors of `n` (small `n`).
fn prime_factors(mut n: u32) -> Vec<u32> {
    let mut out = Vec::new();
    let mut d = 2;
    while d * d <= n {
        if n.is_multiple_of(d) {
            out.push(d);
            while n.is_multiple_of(d) {
                n /= d;
            }
        }
        d += 1;
    }
    if n > 1 {
        out.push(n);
    }
    out
}

/// Rabin irreducibility test for a bit-packed degree-`deg` F_2 polynomial
/// `f`: irreducible iff `x^{2^deg} ≡ x (mod f)` and
/// `gcd(x^{2^{deg/p}} − x, f) = 1` for every prime `p | deg`.
pub fn f2_is_irreducible(f: u128, deg: u32) -> bool {
    if deg == 0 {
        return false;
    }
    if f2_deg(f) != Some(deg) {
        return false;
    }
    if f & 1 == 0 {
        return false; // divisible by z
    }
    let x: u128 = 0b10; // the polynomial "z"
                        // For each prime p | deg: x^{2^{deg/p}} − x must be coprime to f.
    for p in prime_factors(deg) {
        let e = deg / p;
        let mut h = x;
        for _ in 0..e {
            h = f2_sqr_mod(h, f);
        }
        let g = f2_gcd(h ^ x, f);
        if f2_deg(g) != Some(0) {
            return false; // nontrivial common factor
        }
    }
    // Full condition: x^{2^deg} ≡ x (mod f).
    let mut h = x;
    for _ in 0..deg {
        h = f2_sqr_mod(h, f);
    }
    h == x
}

/// Enumerate up to `limit` irreducible polynomials of degree `n` over
/// `F_2`, returned as [`IrreduciblePoly`] (low_terms = set bits below the
/// leading `z^n`). The leading `z^n` and constant `1` are always present;
/// the interior coefficients are swept. `n ≤ 20` recommended (search is
/// `O(2^{n})` candidates in the worst case but returns early at `limit`).
pub fn enumerate_irreducibles(n: u32, limit: usize) -> Vec<IrreduciblePoly> {
    let mut out = Vec::new();
    if n == 0 || n > 31 {
        return out;
    }
    let lead = 1u128 << n;
    // Interior bits: positions 1..n-1 may be 0/1; constant (bit 0) fixed 1.
    let interior_bits = if n >= 2 { n - 1 } else { 0 };
    let combos = 1u128 << interior_bits;
    for mask in 0..combos {
        // Build candidate: z^n + (mask placed at bits 1..n-1) + 1.
        let interior = mask << 1;
        let f = lead | interior | 1;
        if f2_is_irreducible(f, n) {
            let low_terms: Vec<u32> = (0..n).filter(|&k| (f >> k) & 1 == 1).collect();
            out.push(IrreduciblePoly {
                degree: n,
                low_terms,
            });
            if out.len() >= limit {
                break;
            }
        }
    }
    out
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::ffd_harness::choose_irreducible;

    /// The multiplication tensor reproduces known `F_{2ⁿ}` identities:
    /// `z^i · z^0 = z^i`, and the reduction `z^{n} ≡ Σ low_terms`.
    #[test]
    fn tensor_reproduces_field_identities() {
        let n = 4;
        let irr = choose_irreducible(n); // z^4 + z + 1, low_terms {0,1}
        let c = multiplication_tensor(n, &irr);
        // z^i · z^0 = z^i.
        for i in 0..4usize {
            for j in 0..4usize {
                assert_eq!(c[i][0][j], i == j, "z^{i}·1 should be z^{i}");
            }
        }
        // z^2 · z^2 = z^4 ≡ z + 1  (since z^4 = z + 1).
        assert!(c[2][2][0], "z^4 should contain z^0");
        assert!(c[2][2][1], "z^4 should contain z^1");
        assert!(!c[2][2][2]);
        assert!(!c[2][2][3]);
    }

    /// Tensor incidence graph has the right shape and is symmetric in the
    /// sense that multiplication symmetry `c_{ikj}=c_{kij}` holds.
    #[test]
    fn tensor_incidence_shape() {
        let n = 6;
        let n_sub = 3;
        let irr = choose_irreducible(n);
        let g = tensor_incidence(n, n_sub, &irr);
        assert_eq!(g.left, 6);
        assert_eq!(g.right, 3);
        assert!(g.edges() > 0, "graph should have edges");
        // Multiplication tensor symmetry.
        let c = multiplication_tensor(n, &irr);
        for i in 0..n as usize {
            for k in 0..n as usize {
                for j in 0..n as usize {
                    assert_eq!(c[i][k][j], c[k][i][j], "tensor must be symmetric in i,k");
                }
            }
        }
    }

    /// Spectral gap of a complete bipartite graph K_{l,r} is 1 (σ₂ = 0):
    /// the perfect expander.
    #[test]
    fn spectral_gap_complete_bipartite() {
        let l = 4;
        let r = 3;
        let g = Biadjacency {
            b: vec![vec![true; r]; l],
            left: l,
            right: r,
        };
        let (sigma2, gamma) = spectral_expansion(&g);
        assert!(sigma2 < 1e-6, "K_lr should have σ₂≈0, got {sigma2}");
        assert!((gamma - 1.0).abs() < 1e-6);
    }

    /// A perfect matching (disjoint edges) is a poor expander: σ₂ = 1,
    /// spectral gap 0.
    #[test]
    fn spectral_gap_matching() {
        // 3 left, 3 right, identity matching.
        let mut b = vec![vec![false; 3]; 3];
        for i in 0..3 {
            b[i][i] = true;
        }
        let g = Biadjacency {
            b,
            left: 3,
            right: 3,
        };
        let (sigma2, gamma) = spectral_expansion(&g);
        assert!(
            (sigma2 - 1.0).abs() < 1e-6,
            "matching should have σ₂≈1, got {sigma2}"
        );
        assert!(gamma < 1e-6);
    }

    /// Boundary expansion of a perfect matching is 1 (each singleton `S`
    /// has exactly one unique neighbor).
    #[test]
    fn boundary_expansion_matching() {
        let mut b = vec![vec![false; 4]; 4];
        for i in 0..4 {
            b[i][i] = true;
        }
        let g = Biadjacency {
            b,
            left: 4,
            right: 4,
        };
        let bd = boundary_expansion(&g, 4);
        assert!(
            (bd - 1.0).abs() < 1e-9,
            "matching boundary expansion should be 1, got {bd}"
        );
    }

    /// Full report runs on a real field and yields finite, in-range values.
    #[test]
    fn report_runs_on_real_field() {
        for n in [5u32, 6, 7, 8] {
            let n_sub = (n / 2).max(1);
            let irr = choose_irreducible(n);
            let rep = expansion_report(n, n_sub, &irr);
            assert_eq!(rep.left, n as usize);
            assert_eq!(rep.right, n_sub as usize);
            assert!(rep.gamma_spectral >= 0.0 && rep.gamma_spectral <= 1.0);
            assert!(rep.gamma_boundary >= 0.0);
            assert!(rep.edges > 0);
        }
    }

    /// Spearman is +1 for a strictly increasing relation, −1 for decreasing.
    #[test]
    fn spearman_monotone() {
        let xs = [1.0, 2.0, 3.0, 4.0, 5.0];
        let up = [10.0, 20.0, 25.0, 40.0, 41.0];
        let down = [5.0, 4.0, 3.0, 2.0, 1.0];
        assert!((spearman(&xs, &up).unwrap() - 1.0).abs() < 1e-9);
        assert!((spearman(&xs, &down).unwrap() + 1.0).abs() < 1e-9);
    }

    /// At cryptographic size the report still completes quickly (smoke
    /// test of the "runs at cryptographic n" claim).
    #[test]
    fn report_runs_at_larger_n() {
        let n = 32;
        let n_sub = 8;
        let irr = choose_irreducible(n);
        let rep = expansion_report(n, n_sub, &irr);
        assert_eq!(rep.left, 32);
        assert!(rep.gamma_spectral >= 0.0 && rep.gamma_spectral <= 1.0);
    }

    /// Rabin irreducibility test agrees with known cases.
    #[test]
    fn irreducibility_known_cases() {
        // z^4 + z + 1 is irreducible (0b10011 = 19).
        assert!(f2_is_irreducible(0b1_0011, 4));
        // z^2 + 1 = (z+1)^2 is reducible.
        assert!(!f2_is_irreducible(0b101, 2));
        // z^2 + z + 1 is irreducible.
        assert!(f2_is_irreducible(0b111, 2));
        // z^4 + z^3 + z^2 + z + 1 is irreducible (the all-ones, period 5).
        assert!(f2_is_irreducible(0b1_1111, 4));
        // z^4 + z^2 + 1 = (z^2+z+1)^2 reducible.
        assert!(!f2_is_irreducible(0b1_0101, 4));
        // Reducible with a z factor (even constant): z^3 + z.
        assert!(!f2_is_irreducible(0b1010, 3));
    }

    /// Counts of monic irreducible polynomials match the necklace formula:
    /// deg 4 → 3, deg 5 → 6, deg 6 → 9.  Our enumerator fixes the constant
    /// term to 1 (irreducibles of degree ≥ 1 always have nonzero constant),
    /// so it should find all of them.
    #[test]
    fn irreducible_counts() {
        assert_eq!(enumerate_irreducibles(4, 100).len(), 3);
        assert_eq!(enumerate_irreducibles(5, 100).len(), 6);
        assert_eq!(enumerate_irreducibles(6, 100).len(), 9);
    }

    /// Every enumerated polynomial is genuinely irreducible and has the
    /// requested degree.
    #[test]
    fn enumerated_are_irreducible() {
        for irr in enumerate_irreducibles(8, 100) {
            assert_eq!(irr.degree, 8);
            let mut f = 1u128 << 8;
            for &k in &irr.low_terms {
                f |= 1u128 << k;
            }
            assert!(f2_is_irreducible(f, 8));
        }
    }

    /// **Structural finding (the reason `system_incidence` exists):** the
    /// *tensor* incidence graph is **basis-independent** in the refutable
    /// regime `2n' ≤ n`, because the bilinear products `z^i·z^k`
    /// (`i,k < n'`) have degree `< n` and never trigger reduction mod
    /// `m(z)`. So `tensor_incidence` is NOT a P2 predictor here; we assert
    /// the invariance explicitly so the finding is locked in.
    #[test]
    fn tensor_expansion_is_basis_independent_in_refutable_regime() {
        let n = 8;
        let n_sub = 4; // 2n' = n: refutable boundary
        let bases = enumerate_irreducibles(n, 100);
        assert!(bases.len() >= 3, "need several bases to compare");
        let gammas: Vec<f64> = bases
            .iter()
            .map(|irr| expansion_report(n, n_sub, irr).gamma_spectral)
            .collect();
        let lo = gammas.iter().cloned().fold(f64::INFINITY, f64::min);
        let hi = gammas.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        assert!(
            hi - lo < 1e-9,
            "tensor γ should be basis-INDEPENDENT in refutable regime, spread={}",
            hi - lo
        );
    }

    /// **The actual P2 ingredient:** the *system* incidence graph (full
    /// descended S₃, with the Frobenius-squared terms) DOES vary across
    /// bases at fixed `(n, n')` — there is something for `D*` to correlate
    /// with. We use a fixed `(b, x₃)` and sweep the basis.
    #[test]
    fn system_expansion_varies_across_bases() {
        let n = 8;
        let n_sub = 3;
        let bases = enumerate_irreducibles(n, 100);
        assert!(bases.len() >= 3);
        let b = F2mElement::from_bit_positions(&[0, 2], n);
        let x3 = F2mElement::from_bit_positions(&[1, 3], n);
        let gammas: Vec<f64> = bases
            .iter()
            .map(|irr| system_expansion_report(n, n_sub, irr, &b, &x3).gamma_spectral)
            .collect();
        let lo = gammas.iter().cloned().fold(f64::INFINITY, f64::min);
        let hi = gammas.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
        assert!(
            hi - lo > 1e-6,
            "system γ should vary across bases, spread={}",
            hi - lo
        );
    }

    /// The system incidence graph has the expected `n × 2n'` shape.
    #[test]
    fn system_incidence_shape() {
        let n = 7;
        let n_sub = 3;
        let irr = choose_irreducible(n);
        let b = F2mElement::from_bit_positions(&[0, 1], n);
        let x3 = F2mElement::from_bit_positions(&[2], n);
        let g = system_incidence(n, n_sub, &irr, &b, &x3);
        assert_eq!(g.left, n as usize);
        assert_eq!(g.right, 2 * n_sub as usize);
        assert!(g.edges() > 0);
    }
}
