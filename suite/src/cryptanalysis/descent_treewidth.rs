//! # Descent primal-graph **treewidth** — the reformulated P2 predictor.
//!
//! Workflow iteration 3 (EXP-E, `descent_lowgamma`) **refuted** the spectral
//! form of the proof-complexity bridge: the structured *subfield* factor
//! base is the easiest case (lowest refutation degree `D*`) yet has *higher*
//! spectral expansion `γ`. So spectral `γ` does not explain solving-degree
//! ease. The driver's recommended reformulation is **treewidth** of the
//! constraint **primal (moral) graph**, for a sharp theoretical reason:
//!
//! - Gaussian / Gröbner elimination cost — and the Macaulay solving degree
//!   `D*` — is governed by **fill-in**, which is bounded by the treewidth of
//!   the primal graph (vertices = variables, clique per constraint). A
//!   *subfield* factor base induces **block structure** (the multiplication
//!   table of `F_{2^d}` couples variables in tight clusters), which gives
//!   **low treewidth** even when the spectral gap is large — exactly the
//!   regime that broke the spectral predictor.
//!
//! So the reformulated **prediction P2′** is: `D*` is positively monotone in
//! the **treewidth** `tw(G_primal)` of the `V`-substituted system, and in
//! particular the low-`D*` subfield case should be **low-treewidth**.
//!
//! ## What we compute
//!
//! - **Primal graph** of the descended system on a factor-base subspace `V`:
//!   one vertex per bit-variable, a clique on the variables of each equation
//!   ([`primal_graph`]).
//! - **Exact treewidth** via the Bodlaender–Fomin subset dynamic program
//!   over elimination orderings ([`exact_treewidth`]), `O(2^v · v²)`. Exact
//!   (not a heuristic) for `v ≤ 18` vertices — i.e. `n' ≤ 9`, which covers
//!   the whole regime the rest of the program runs in.
//!
//! ## References
//!
//! - H. Bodlaender et al., *On exact algorithms for treewidth*, ESA 2006
//!   (the subset DP used here).
//! - `research/notes/index-calculus/RESEARCH_FFD_WORKFLOW.md` iteration 3 (the spectral refutation that
//!   motivates this) and `research/notes/index-calculus/RESEARCH_FFD_PROOF_COMPLEXITY.md` §3.

use crate::cryptanalysis::ffd_harness::{quad_monomial_index, F2BoolPoly};

/// Largest vertex count for which we run the exact treewidth DP. `2^18`
/// subsets is a few hundred ms; beyond this the caller should use a
/// heuristic (not implemented here — the program never needs it).
pub const EXACT_TW_VERTEX_CAP: usize = 18;

// ── Primal (moral) graph ────────────────────────────────────────────

/// Primal graph of an `F_2`-quadratic system in `new_vars` Boolean
/// variables: one vertex per variable; for every equation, the set of
/// variables that occur in it forms a **clique** (they will couple under
/// elimination). Returned as an adjacency-bitmask vector: `adj[v]` has bit
/// `u` set iff `{u, v}` is an edge.
pub fn primal_graph(eqs: &[F2BoolPoly], new_vars: u32) -> Vec<u32> {
    assert!(new_vars <= 32, "bitmask adjacency supports ≤ 32 vertices");
    let nv = new_vars as usize;
    let mut adj = vec![0u32; nv];
    for eq in eqs {
        // Collect the variables occurring in this equation.
        let mut occ: u32 = 0;
        // Linear occurrences.
        for i in 0..new_vars {
            if eq.coeffs.get(1 + i as usize).copied().unwrap_or(false) {
                occ |= 1 << i;
            }
        }
        // Quadratic occurrences x_a·x_c.
        for a in 0..new_vars {
            for c in (a + 1)..new_vars {
                let idx = quad_monomial_index(a, c, new_vars);
                if idx < eq.coeffs.len() && eq.coeffs[idx] {
                    occ |= 1 << a;
                    occ |= 1 << c;
                }
            }
        }
        // Clique on `occ`.
        let verts: Vec<u32> = (0..new_vars).filter(|&i| (occ >> i) & 1 == 1).collect();
        for (p, &u) in verts.iter().enumerate() {
            for &w in &verts[p + 1..] {
                adj[u as usize] |= 1 << w;
                adj[w as usize] |= 1 << u;
            }
        }
    }
    adj
}

/// Number of edges in an adjacency-bitmask graph.
pub fn edge_count(adj: &[u32]) -> usize {
    adj.iter().map(|m| m.count_ones() as usize).sum::<usize>() / 2
}

/// Edge **density** of an `n`-vertex graph: `edges / C(n,2) ∈ [0,1]`.
/// `1.0` means the complete graph K_n (treewidth `n−1`, carrying no
/// structural information). This is the diagnostic that explains why
/// treewidth fails as a `D*` predictor here (see module docs / P2″):
/// the descended primal graph is **saturated**, so every family has the
/// same treewidth `2n'−1` regardless of how easy its `D*` is.
pub fn edge_density(adj: &[u32], n: usize) -> f64 {
    if n < 2 {
        return 0.0;
    }
    let max = (n * (n - 1) / 2) as f64;
    edge_count(adj) as f64 / max
}

// ── Exact treewidth (subset DP over elimination orderings) ──────────

/// Exact treewidth of an adjacency-bitmask graph on `n` vertices, via the
/// Bodlaender–Fomin dynamic program:
///
/// ```text
///   TW(S) = min_{v∈S} max( TW(S∖{v}),  q(S∖{v}, v) )
/// ```
///
/// where `q(W, v)` = number of vertices outside `W ∪ {v}` reachable from
/// `v` through vertices of `W` (the size of the clique created when `v` is
/// eliminated after `W`). `TW(∅) = 0`; the answer is `TW(full set)`.
///
/// Returns `None` if `n > EXACT_TW_VERTEX_CAP` (DP table too large).
pub fn exact_treewidth(adj: &[u32], n: usize) -> Option<usize> {
    if n == 0 {
        return Some(0);
    }
    if n > EXACT_TW_VERTEX_CAP {
        return None;
    }
    let full = (1u32 << n) - 1;
    // tw[S] = minimum width of eliminating the vertices in S (in some order),
    // measured as the max clique-minus-one created. We store the max
    // neighbor-count q (so treewidth = stored value).
    let size = 1usize << n;
    let mut tw = vec![usize::MAX; size];
    tw[0] = 0;
    // Process subsets in increasing popcount order so S∖{v} is ready.
    let mut order: Vec<u32> = (0..size as u32).collect();
    order.sort_by_key(|s| s.count_ones());
    for &s in &order {
        if s == 0 {
            continue;
        }
        let mut best = usize::MAX;
        let mut bits = s;
        while bits != 0 {
            let v = bits.trailing_zeros();
            bits &= bits - 1;
            let w = s & !(1u32 << v); // S without v
            let sub = tw[w as usize];
            if sub == usize::MAX {
                continue;
            }
            let q = q_neighbors(adj, n, w, v, full);
            let width = sub.max(q);
            if width < best {
                best = width;
            }
        }
        tw[s as usize] = best;
    }
    Some(tw[full as usize])
}

/// `q(W, v)`: the number of vertices **outside** `W ∪ {v}` that are
/// adjacent to the connected component of `v` in the subgraph induced by
/// `W ∪ {v}`. This is the size of the clique formed on `v`'s "later"
/// neighbors when `v` is eliminated after the set `W`.
fn q_neighbors(adj: &[u32], _n: usize, w: u32, v: u32, full: u32) -> usize {
    // Component of v within W ∪ {v}.
    let allowed = w | (1u32 << v);
    let mut comp = 1u32 << v;
    loop {
        let mut grow = comp;
        let mut bits = comp;
        while bits != 0 {
            let u = bits.trailing_zeros() as usize;
            bits &= bits - 1;
            grow |= adj[u] & allowed;
        }
        if grow == comp {
            break;
        }
        comp = grow;
    }
    // Outside-neighbors: vertices in (full ∖ (W∪{v})) adjacent to comp.
    let outside = full & !allowed;
    let mut nbrs: u32 = 0;
    let mut bits = comp;
    while bits != 0 {
        let u = bits.trailing_zeros() as usize;
        bits &= bits - 1;
        nbrs |= adj[u] & outside;
    }
    nbrs.count_ones() as usize
}

// ── Tests ───────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// Build adjacency from an edge list.
    fn graph(n: usize, edges: &[(usize, usize)]) -> Vec<u32> {
        let mut adj = vec![0u32; n];
        for &(a, b) in edges {
            adj[a] |= 1 << b;
            adj[b] |= 1 << a;
        }
        adj
    }

    /// Treewidth of a tree (here a path) is 1.
    #[test]
    fn treewidth_path_is_one() {
        let g = graph(5, &[(0, 1), (1, 2), (2, 3), (3, 4)]);
        assert_eq!(exact_treewidth(&g, 5), Some(1));
    }

    /// Treewidth of the complete graph K_n is n−1.
    #[test]
    fn treewidth_complete_is_n_minus_1() {
        for n in 1..=6usize {
            let mut edges = Vec::new();
            for a in 0..n {
                for b in (a + 1)..n {
                    edges.push((a, b));
                }
            }
            let g = graph(n, &edges);
            assert_eq!(exact_treewidth(&g, n), Some(n - 1), "K_{n}");
        }
    }

    /// Treewidth of a cycle C_n (n ≥ 3) is 2.
    #[test]
    fn treewidth_cycle_is_two() {
        let n = 6;
        let mut edges: Vec<(usize, usize)> = (0..n).map(|i| (i, (i + 1) % n)).collect();
        edges.dedup();
        let g = graph(n, &edges);
        assert_eq!(exact_treewidth(&g, n), Some(2));
    }

    /// An empty (edgeless) graph has treewidth 0.
    #[test]
    fn treewidth_edgeless_is_zero() {
        let g = vec![0u32; 4];
        assert_eq!(exact_treewidth(&g, 4), Some(0));
    }

    /// The two disjoint triangles graph has treewidth 2 (each component is
    /// K_3); treewidth is the max over components.
    #[test]
    fn treewidth_two_triangles() {
        let g = graph(6, &[(0, 1), (1, 2), (0, 2), (3, 4), (4, 5), (3, 5)]);
        assert_eq!(exact_treewidth(&g, 6), Some(2));
    }

    /// Vertex cap is respected.
    #[test]
    fn vertex_cap_returns_none() {
        let g = vec![0u32; EXACT_TW_VERTEX_CAP + 1];
        assert_eq!(exact_treewidth(&g, EXACT_TW_VERTEX_CAP + 1), None);
    }

    /// Primal graph: a single equation with a quadratic monomial x0·x1 and
    /// a linear x2 makes a clique on {0,1,2} (treewidth 2).
    #[test]
    fn primal_graph_cliques_per_equation() {
        let nv = 3u32;
        let mut eq = F2BoolPoly::zero(nv);
        // linear x2
        eq.coeffs[1 + 2] = true;
        // quadratic x0·x1
        let idx = quad_monomial_index(0, 1, nv);
        eq.coeffs[idx] = true;
        let g = primal_graph(&[eq], nv);
        // {0,1,2} should be a clique.
        assert_eq!(edge_count(&g), 3);
        assert_eq!(exact_treewidth(&g, 3), Some(2));
    }

    /// **The treewidth finding, locked in (P2″ negative).** The descended
    /// Semaev system's primal graph is the **complete** graph K_{2n'}: the
    /// Frobenius-squared terms couple essentially every pair of variables,
    /// so the graph is saturated (density 1.0) and treewidth is `2n'−1`
    /// regardless of the factor-base family. Hence treewidth — like
    /// spectral γ — cannot discriminate the easy (subfield) case from the
    /// hard (random) one: the structure that lowers `D*` lives in the
    /// algebraic *coefficients*, not in the variable-incidence graph.
    #[test]
    fn descended_primal_graph_is_complete() {
        use crate::binary_ecc::F2mElement;
        use crate::cryptanalysis::descent_expansion::enumerate_irreducibles;
        use crate::cryptanalysis::descent_lowgamma::{
            descend_on_subspace, BasisFamily, FactorSubspace,
        };
        let n = 8;
        let n_sub = 4;
        let irr = enumerate_irreducibles(n, 1).into_iter().next().unwrap();
        let b = F2mElement::from_bit_positions(&[0, 3], n);
        let x3 = F2mElement::from_bit_positions(&[1], n);
        for fam in [
            BasisFamily::Subfield,
            BasisFamily::Coordinate,
            BasisFamily::Random,
        ] {
            let v = FactorSubspace::build(fam, n, n_sub, &irr, 0x77).unwrap();
            let eqs = descend_on_subspace(n, &v, &irr, &b, &x3);
            let nv = 2 * n_sub;
            let g = primal_graph(&eqs, nv);
            assert!(
                (edge_density(&g, nv as usize) - 1.0).abs() < 1e-9,
                "{fam:?}: primal graph should be complete (saturated)"
            );
            assert_eq!(exact_treewidth(&g, nv as usize), Some(nv as usize - 1));
        }
    }
}
