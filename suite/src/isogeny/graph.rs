//! # ℓ-isogeny graph traversal and statistics.
//!
//! For a set of small primes `S = {ℓ_1, …, ℓ_k}` and a starting
//! curve `E_0/F_p`, the **`S`-isogeny graph** has vertices the
//! j-invariants of curves reachable from `E_0` by composing
//! `ℓ`-isogenies for `ℓ ∈ S`, and edges labelled by which `ℓ` was
//! used.  Connected components of this graph are precisely the
//! isogeny classes of `E_0` (the set of `F_p`-curves with the
//! same `#E(F_p) = p + 1 − t`).
//!
//! Computationally:
//!
//! - **Crater-level graph** (curves with maximal `End(E) = O_K`)
//!   is a Cayley graph of `Cl(O_K)` under the generating set
//!   `{[ℓ] : ℓ ∈ S}`.  Its diameter is `O(log h(O_K))` when `S`
//!   spans, much smaller than `h(O_K)` itself.
//! - **Full graph** (all conductors) is the disjoint union of one
//!   such Cayley graph per maximal-conductor curve plus the
//!   descending trees underneath.
//!
//! This module builds the graph by BFS using Vélu walks (a simple
//! but correct algorithm), records the graph structure, and
//! exposes path-finding and statistics.

use super::velu::{velu_isogeny_2, velu_isogeny_odd, VeluIsogeny};
use super::volcano::j_invariant;
use super::SmallCurve;
use num_bigint::BigUint;
use std::collections::{BTreeMap, BTreeSet, HashMap, VecDeque};

/// Find every 2-isogeny `φ: E → E'` defined over `F_p` by sampling
/// random points and reducing via the cofactor `m = #E / 2`.  At
/// most three 2-isogenies exist (one per F_p-rational root of
/// `x³ + a·x + b = 0`).  If `2 ∤ #E` we know there is no
/// F_p-rational 2-torsion and we short-circuit.  Cost:
/// `O(log² p)` per sample, `O(1)` samples per isogeny.
fn two_isogenies_via_cubic_roots(curve: &SmallCurve) -> Vec<VeluIsogeny> {
    use crate::ecc::point::Point;
    use std::collections::HashSet;
    let cm = crate::isogeny::cm::cm_discriminant(curve);
    if cm.order <= 0 || !(cm.order as u64).is_multiple_of(2) {
        return Vec::new();
    }
    let cofactor = (cm.order as u64) / 2;
    let cp = curve.to_curve_params();
    let a_fe = cp.a_fe();
    let mut seen: HashSet<u64> = HashSet::new();
    let mut result = Vec::new();
    let mut rng: u64 = curve
        .p
        .wrapping_mul(0xB492B66FBE98F273)
        .wrapping_add(curve.a)
        .wrapping_mul(0x9FB21C651E98DF25)
        .wrapping_add(curve.b);
    // Three is the upper bound — degenerate cases are fewer.
    let max_attempts = 32u64;
    for _ in 0..max_attempts {
        rng = rng
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        let p_point = match crate::isogeny::cm::sample_random_point(curve, &mut rng) {
            Some(p) => p,
            None => continue,
        };
        let q = p_point.scalar_mul(&BigUint::from(cofactor), &a_fe);
        let x_t = match &q {
            Point::Affine { x, y } => {
                // 2-torsion: y must be zero.  If non-zero, the point
                // has order > 2 (the random scalar landed in a larger
                // subgroup of the doubled cofactor) — skip and try
                // again.
                let yv = y.value.iter_u64_digits().next().unwrap_or(0);
                if yv != 0 {
                    continue;
                }
                x.value.iter_u64_digits().next().unwrap_or(0)
            }
            Point::Infinity => continue,
        };
        if !seen.insert(x_t) {
            continue;
        }
        if let Some(iso) = velu_isogeny_2(curve, x_t) {
            result.push(iso);
            if result.len() >= 3 {
                break;
            }
        }
    }
    result
}

/// One node in the isogeny graph: a curve, its j-invariant, and
/// its index in the [`IsogenyGraph`] node list.
#[derive(Clone, Debug, serde::Serialize)]
pub struct IsogenyNode {
    pub index: usize,
    pub j: u64,
    pub curve: (u64, u64, u64),
}

/// One edge: source-index, target-index, isogeny degree `ℓ`.  Each
/// undirected `ℓ`-isogeny is recorded as two directed entries in
/// the adjacency list (`source → target` and `target → source`),
/// but stored *once* here.
#[derive(Clone, Debug, serde::Serialize)]
pub struct IsogenyEdge {
    pub from: usize,
    pub to: usize,
    pub degree: u64,
}

/// The complete `S`-isogeny graph as built by [`build_graph`].
#[derive(Clone, Debug, serde::Serialize)]
pub struct IsogenyGraph {
    pub nodes: Vec<IsogenyNode>,
    pub edges: Vec<IsogenyEdge>,
    /// `adj[i] = list of (neighbour_index, degree)`.
    pub adj: Vec<Vec<(usize, u64)>>,
    pub primes: Vec<u64>,
}

impl IsogenyGraph {
    /// Number of vertices.
    pub fn order(&self) -> usize {
        self.nodes.len()
    }

    /// Number of edges (undirected).
    pub fn size(&self) -> usize {
        self.edges.len()
    }

    /// Look up a node by its j-invariant.
    pub fn index_of(&self, j: u64) -> Option<usize> {
        self.nodes.iter().find(|n| n.j == j).map(|n| n.index)
    }

    /// Degree distribution: for each prime `ℓ ∈ S`, count how
    /// many nodes have `ℓ`-degree equal to each value seen.
    pub fn degree_distribution_per_ell(&self) -> BTreeMap<u64, BTreeMap<usize, usize>> {
        let mut counts: BTreeMap<u64, BTreeMap<usize, usize>> = BTreeMap::new();
        for ell in &self.primes {
            let per_ell: BTreeMap<usize, usize> = BTreeMap::new();
            counts.insert(*ell, per_ell);
        }
        for (i, neighbours) in self.adj.iter().enumerate() {
            let _ = i;
            // Group neighbours by edge degree.
            let mut by_ell: BTreeMap<u64, usize> = BTreeMap::new();
            for &(_, deg) in neighbours {
                *by_ell.entry(deg).or_default() += 1;
            }
            for (ell, count) in by_ell {
                *counts.entry(ell).or_default().entry(count).or_default() += 1;
            }
        }
        counts
    }

    /// Graph diameter (length of the longest shortest-path) — via
    /// repeated BFS.  `O(|V| · (|V| + |E|))`.
    pub fn diameter(&self) -> usize {
        let mut best = 0;
        for src in 0..self.nodes.len() {
            let dists = self.bfs_distances(src);
            for d in dists.into_iter().flatten() {
                if d > best {
                    best = d;
                }
            }
        }
        best
    }

    /// Connected components.  Returns one `Vec<usize>` per
    /// component, listing the contained vertex indices.
    pub fn connected_components(&self) -> Vec<Vec<usize>> {
        let n = self.nodes.len();
        let mut visited = vec![false; n];
        let mut comps = Vec::new();
        for v in 0..n {
            if visited[v] {
                continue;
            }
            let mut comp = Vec::new();
            let mut q = VecDeque::new();
            q.push_back(v);
            visited[v] = true;
            while let Some(x) = q.pop_front() {
                comp.push(x);
                for &(y, _) in &self.adj[x] {
                    if !visited[y] {
                        visited[y] = true;
                        q.push_back(y);
                    }
                }
            }
            comps.push(comp);
        }
        comps
    }

    /// BFS from `src`; returns `dists[i] = Some(distance)` if `i`
    /// is reachable, else `None`.
    pub fn bfs_distances(&self, src: usize) -> Vec<Option<usize>> {
        let n = self.nodes.len();
        let mut dists = vec![None; n];
        dists[src] = Some(0);
        let mut q = VecDeque::new();
        q.push_back(src);
        while let Some(x) = q.pop_front() {
            let dx = dists[x].unwrap();
            for &(y, _) in &self.adj[x] {
                if dists[y].is_none() {
                    dists[y] = Some(dx + 1);
                    q.push_back(y);
                }
            }
        }
        dists
    }

    /// Find a path (sequence of vertex indices) from `src` to
    /// `dst`, or `None` if disconnected.
    pub fn shortest_path(&self, src: usize, dst: usize) -> Option<Vec<usize>> {
        let n = self.nodes.len();
        let mut parent: HashMap<usize, usize> = HashMap::new();
        let mut visited = vec![false; n];
        visited[src] = true;
        let mut q = VecDeque::new();
        q.push_back(src);
        while let Some(x) = q.pop_front() {
            if x == dst {
                let mut path = vec![dst];
                let mut cur = dst;
                while cur != src {
                    cur = parent[&cur];
                    path.push(cur);
                }
                path.reverse();
                return Some(path);
            }
            for &(y, _) in &self.adj[x] {
                if !visited[y] {
                    visited[y] = true;
                    parent.insert(y, x);
                    q.push_back(y);
                }
            }
        }
        None
    }

    /// Detect cycles: returns true if at least one cycle exists.
    /// A cycle is any back-edge encountered during DFS.  Note that
    /// every "horizontal" crater edge produces a 2-cycle with its
    /// reverse; we report the result modulo this trivial structure
    /// by requiring cycle length ≥ 3.
    pub fn has_long_cycle(&self) -> bool {
        let n = self.nodes.len();
        let mut color = vec![0u8; n]; // 0=white, 1=gray, 2=black
        let mut parent = vec![usize::MAX; n];
        for s in 0..n {
            if color[s] != 0 {
                continue;
            }
            let mut stack = vec![(s, 0usize)];
            while let Some((u, idx)) = stack.last().copied() {
                if idx == 0 {
                    color[u] = 1;
                }
                if idx >= self.adj[u].len() {
                    color[u] = 2;
                    stack.pop();
                    continue;
                }
                let (v, _) = self.adj[u][idx];
                let last = stack.len() - 1;
                stack[last].1 += 1;
                if color[v] == 0 {
                    parent[v] = u;
                    stack.push((v, 0));
                } else if color[v] == 1 && parent[u] != v {
                    return true;
                }
            }
        }
        false
    }
}

/// Build the `S`-isogeny graph reachable from `start`, capped at
/// `max_nodes` vertices.  Walks both directions in BFS; each
/// `ℓ`-isogeny is added once (we de-duplicate `(j₁, j₂)` pairs
/// per `ℓ`).
pub fn build_graph(start: &SmallCurve, primes: &[u64], max_nodes: usize) -> IsogenyGraph {
    let mut nodes: Vec<IsogenyNode> = Vec::new();
    let mut idx_of_j: HashMap<u64, usize> = HashMap::new();
    let mut adj: Vec<Vec<(usize, u64)>> = Vec::new();
    let mut edges: Vec<IsogenyEdge> = Vec::new();
    let mut edge_set: BTreeSet<(usize, usize, u64)> = BTreeSet::new();

    let start_j = j_invariant(start);
    nodes.push(IsogenyNode {
        index: 0,
        j: start_j,
        curve: (start.p, start.a, start.b),
    });
    idx_of_j.insert(start_j, 0);
    adj.push(Vec::new());

    // BFS keyed on curves (we keep the actual coefficients because
    // we'll need them to invoke Vélu on neighbours).
    let mut q: VecDeque<(SmallCurve, usize)> = VecDeque::new();
    q.push_back((*start, 0));

    while let Some((c, idx)) = q.pop_front() {
        if nodes.len() >= max_nodes {
            break;
        }
        for &ell in primes {
            let neighbours: Vec<VeluIsogeny> = if ell == 2 {
                two_isogenies_via_cubic_roots(&c)
            } else {
                velu_isogeny_odd(&c, ell)
            };

            for iso in neighbours {
                let j2 = j_invariant(&iso.codomain);
                let neighbour_idx = match idx_of_j.get(&j2) {
                    Some(&i) => i,
                    None => {
                        if nodes.len() >= max_nodes {
                            continue;
                        }
                        let i = nodes.len();
                        nodes.push(IsogenyNode {
                            index: i,
                            j: j2,
                            curve: (iso.codomain.p, iso.codomain.a, iso.codomain.b),
                        });
                        idx_of_j.insert(j2, i);
                        adj.push(Vec::new());
                        q.push_back((iso.codomain, i));
                        i
                    }
                };
                let key = if idx < neighbour_idx {
                    (idx, neighbour_idx, ell)
                } else {
                    (neighbour_idx, idx, ell)
                };
                if edge_set.insert(key) {
                    adj[idx].push((neighbour_idx, ell));
                    adj[neighbour_idx].push((idx, ell));
                    edges.push(IsogenyEdge {
                        from: idx,
                        to: neighbour_idx,
                        degree: ell,
                    });
                }
            }
        }
    }

    IsogenyGraph {
        nodes,
        edges,
        adj,
        primes: primes.to_vec(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::isogeny::toy_curve_b;

    #[test]
    fn graph_smoke() {
        let g = build_graph(&toy_curve_b(), &[2, 3], 32);
        assert!(g.order() >= 1);
        assert_eq!(g.adj.len(), g.nodes.len());
    }

    #[test]
    fn graph_has_starting_node_index_0() {
        let curve = toy_curve_b();
        let g = build_graph(&curve, &[2], 16);
        assert_eq!(g.nodes[0].j, j_invariant(&curve));
    }
}
