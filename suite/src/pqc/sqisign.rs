//! **SQIsign** — Short Quaternion and Isogeny Signature (educational
//! toy-parameter implementation).
//!
//! SQIsign (De Feo, Kohel, Leroux, Petit, Wesolowski 2020; NIST
//! additional-signatures candidate, round 2) is the most compact
//! post-quantum signature scheme known: ~180-byte signatures at NIST
//! level 1, an order of magnitude smaller than ML-DSA or Falcon.  Its
//! security rests on the hardness of the **supersingular isogeny path
//! problem**: given two supersingular elliptic curves over `F_{p²}`,
//! find an isogeny between them.  Unlike SIDH (broken in 2022 by
//! Castryck–Decru), SQIsign publishes no torsion-point images, so the
//! attack does not apply.
//!
//! # The protocol
//! SQIsign is the Fiat–Shamir transform of an identification protocol
//! walked on the **supersingular ℓ-isogeny graph**: vertices are
//! j-invariants of supersingular curves over `F_{p²}` (~p/12 of them),
//! and edges are degree-ℓ isogenies.  Two j-invariants are 2-isogenous
//! iff they are a root pair of the classical **modular polynomial**
//! `Φ₂(X, Y)`, so a walk can be verified with pure field arithmetic —
//! no curve or kernel computations needed.
//!
//! ```text
//!               secret φ_sk
//!        E₀ ─────────────────▶ E_A        (public key: j(E_A))
//!        │                      ┆
//!  φ_com │                      ┆ φ_rsp   (response: the signature)
//!        ▼                      ▼
//!        E₁ ─────────────────▶ E₂
//!               φ_chl (derived by hashing the message)
//! ```
//!
//! 1. **KeyGen**: secret random walk `φ_sk: E₀ → E_A`; publish `j(E_A)`.
//! 2. **Commit**: random walk `φ_com: E₀ → E₁`; send `j(E₁)`.
//! 3. **Challenge**: hash `(pk, j(E₁), msg)` into a *deterministic*
//!    walk `φ_chl: E₁ → E₂`.
//! 4. **Respond**: produce an isogeny path `φ_rsp: E_A → E₂`.
//! 5. **Verify**: recompute the challenge walk, then check the response
//!    is a genuine path `E_A → E₂` in the isogeny graph (each
//!    consecutive pair must satisfy `Φ₂(j, j') = 0`).
//!
//! # What real SQIsign does that we do not
//! Step 4 is the entire difficulty of SQIsign.  The signer knows the
//! endomorphism rings of `E₀` and `E_A` (via the **Deuring
//! correspondence**, curves ↔ quaternion orders), converts the path
//! problem into ideal arithmetic in a quaternion algebra, and runs the
//! **KLPT algorithm** to produce a *fresh* ideal — hence a fresh
//! isogeny `E_A → E₂` whose distribution is independent of the secret,
//! which is what makes the protocol zero-knowledge.  That machinery
//! (plus its constant-degree variants in SQIsign 2.x) is thousands of
//! lines of quaternion lattice arithmetic.
//!
//! This educational implementation replaces KLPT with **breadth-first
//! search** in the (precomputed) toy isogeny graph.  Consequences:
//!
//! - Only viable for toy `p` (here `p = 431`, giving 37 supersingular
//!   j-invariants).  At real sizes (`p ≈ 2²⁵⁰`) the graph has ~2²⁴⁶
//!   vertices and BFS is precisely the hard problem.
//! - **No security whatsoever**: at toy scale *anyone* can run the same
//!   BFS, so unforgeability is void; and the response path is not
//!   independent of the graph structure, so zero-knowledge is void too.
//!   What survives — and what this module is for — is the exact
//!   *protocol structure* and the verifier's job, which are the same as
//!   in the real scheme.
//!
//! The same educational compromise as `pqc::csidh` (toy prime,
//! brute-force point/root finding); see SECURITY.md.

use crate::hash::sha3::shake256;
use rand::{rngs::OsRng, Rng};
use std::collections::{BTreeMap, HashMap, VecDeque};
use std::sync::OnceLock;

// ── Parameters ────────────────────────────────────────────────────────────────

/// Base-field characteristic.  `p ≡ 3 (mod 4)` so that `i² = −1` is a
/// non-residue (making `F_{p²} = F_p(i)`) and `j = 1728` is
/// supersingular.  `p = 431` is the traditional toy SQIsign prime:
/// `p + 1 = 432 = 2⁴ · 3³` is smooth, and the graph has 37 vertices.
pub const P: u64 = 431;

/// Length of the secret-key walk `E₀ → E_A`.
pub const SK_WALK_LEN: usize = 12;
/// Length of the commitment walk `E₀ → E₁`.
pub const COM_WALK_LEN: usize = 12;
/// Length of the challenge walk `E₁ → E₂`.
pub const CHL_WALK_LEN: usize = 12;
/// Maximum accepted response-path length.  Real SQIsign fixes the
/// response degree exactly (2^e with e ≈ 15·log₂ p); we only cap it.
pub const MAX_RSP_LEN: usize = 24;

// ── F_{p²} arithmetic ─────────────────────────────────────────────────────────

/// An element `a + b·i` of `F_{p²}`, `i² = −1`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct Fp2 {
    pub a: u64,
    pub b: u64,
}

impl Fp2 {
    pub fn new(a: u64, b: u64) -> Self {
        Fp2 { a: a % P, b: b % P }
    }
    pub fn from_u64(a: u64) -> Self {
        Fp2::new(a, 0)
    }
    pub fn add(&self, o: &Fp2) -> Fp2 {
        Fp2 {
            a: (self.a + o.a) % P,
            b: (self.b + o.b) % P,
        }
    }
    pub fn sub(&self, o: &Fp2) -> Fp2 {
        Fp2 {
            a: (self.a + P - o.a) % P,
            b: (self.b + P - o.b) % P,
        }
    }
    pub fn mul(&self, o: &Fp2) -> Fp2 {
        // (a + bi)(c + di) = (ac − bd) + (ad + bc)i.
        let (a, b, c, d) = (self.a, self.b, o.a, o.b);
        Fp2 {
            a: (a * c + (P - 1) * (b * d % P)) % P,
            b: (a * d + b * c) % P,
        }
    }
    pub fn is_zero(&self) -> bool {
        self.a == 0 && self.b == 0
    }
    /// Serialise for hashing: four bytes, `a` then `b`, little-endian u16.
    fn to_bytes(self) -> [u8; 4] {
        let (a, b) = (self.a as u16, self.b as u16);
        [a as u8, (a >> 8) as u8, b as u8, (b >> 8) as u8]
    }
}

// ── The modular polynomial Φ₂ ─────────────────────────────────────────────────

/// Evaluate the classical modular polynomial
/// ```text
/// Φ₂(X,Y) = X³ + Y³ − X²Y² + 1488·(X²Y + XY²) − 162000·(X² + Y²)
///           + 40773375·XY + 8748000000·(X + Y) − 157464000000000
/// ```
/// at `(x, y)` over `F_{p²}`.  `Φ₂(j, j') = 0` iff the curves with
/// j-invariants `j, j'` are connected by a 2-isogeny.
pub fn phi2(x: &Fp2, y: &Fp2) -> Fp2 {
    // Coefficients reduced mod p (they are integers; rem_euclid handles
    // the negative ones).
    let c1488 = Fp2::from_u64(1488u64 % P);
    let cm162000 = Fp2::from_u64((-162000i64).rem_euclid(P as i64) as u64);
    let c40773375 = Fp2::from_u64(40773375u64 % P);
    let c8748000000 = Fp2::from_u64(8748000000u64 % P);
    let cm157464e9 = Fp2::from_u64((-157464000000000i64).rem_euclid(P as i64) as u64);

    let x2 = x.mul(x);
    let x3 = x2.mul(x);
    let y2 = y.mul(y);
    let y3 = y2.mul(y);
    let xy = x.mul(y);

    let mut acc = x3.add(&y3);
    acc = acc.sub(&x2.mul(&y2));
    acc = acc.add(&c1488.mul(&xy.mul(&x.add(y))));
    acc = acc.add(&cm162000.mul(&x2.add(&y2)));
    acc = acc.add(&c40773375.mul(&xy));
    acc = acc.add(&c8748000000.mul(&x.add(y)));
    acc.add(&cm157464e9)
}

// ── The supersingular 2-isogeny graph ─────────────────────────────────────────

/// The full supersingular 2-isogeny graph over `F_{p²}`, as adjacency
/// lists of j-invariants.  Neighbour lists are sorted and deduplicated
/// (double edges at the ramified vertices j = 0, 1728 are collapsed),
/// which gives every walk a canonical encoding.
pub struct IsogenyGraph {
    adj: BTreeMap<Fp2, Vec<Fp2>>,
}

impl IsogenyGraph {
    /// Neighbours of `j` (empty slice if `j` is not supersingular).
    pub fn neighbors(&self, j: &Fp2) -> &[Fp2] {
        self.adj.get(j).map(|v| v.as_slice()).unwrap_or(&[])
    }
    pub fn contains(&self, j: &Fp2) -> bool {
        self.adj.contains_key(j)
    }
    pub fn vertex_count(&self) -> usize {
        self.adj.len()
    }

    /// All distinct roots of the cubic `Φ₂(j, Y)` by brute-force scan of
    /// `F_{p²}` — 185 761 evaluations for p = 431.  Only possible for a
    /// toy prime; production implementations never enumerate the graph.
    fn phi2_roots(j: &Fp2) -> Vec<Fp2> {
        let mut roots = Vec::new();
        for a in 0..P {
            for b in 0..P {
                let y = Fp2 { a, b };
                if phi2(j, &y).is_zero() {
                    roots.push(y);
                }
            }
        }
        roots
    }

    /// Build the whole graph by BFS from the known supersingular vertex
    /// `j = 1728` (supersingular because p ≡ 3 mod 4).  The
    /// 2-isogeny graph on supersingular curves is connected (Mestre),
    /// so this reaches every supersingular j-invariant.
    fn build() -> IsogenyGraph {
        let start = j0();
        let mut adj = BTreeMap::new();
        let mut queue = VecDeque::from([start]);
        while let Some(j) = queue.pop_front() {
            if adj.contains_key(&j) {
                continue;
            }
            let roots = Self::phi2_roots(&j);
            for r in &roots {
                if !adj.contains_key(r) {
                    queue.push_back(*r);
                }
            }
            adj.insert(j, roots);
        }
        IsogenyGraph { adj }
    }

    /// Shortest path between two vertices (inclusive of endpoints).
    /// This is the toy stand-in for the KLPT algorithm — see the module
    /// docs for why that substitution destroys security.
    fn shortest_path(&self, from: &Fp2, to: &Fp2) -> Option<Vec<Fp2>> {
        if from == to {
            return Some(vec![*from]);
        }
        let mut prev: HashMap<Fp2, Fp2> = HashMap::new();
        let mut queue = VecDeque::from([*from]);
        while let Some(j) = queue.pop_front() {
            for n in self.neighbors(&j) {
                if *n != *from && !prev.contains_key(n) {
                    prev.insert(*n, j);
                    if n == to {
                        let mut path = vec![*to];
                        let mut cur = *to;
                        while cur != *from {
                            cur = prev[&cur];
                            path.push(cur);
                        }
                        path.reverse();
                        return Some(path);
                    }
                    queue.push_back(*n);
                }
            }
        }
        None
    }
}

/// The base vertex `j(E₀) = 1728`, i.e. `E₀: y² = x³ + x`.
pub fn j0() -> Fp2 {
    Fp2::from_u64(1728)
}

/// The (lazily built, cached) toy isogeny graph.
pub fn graph() -> &'static IsogenyGraph {
    static GRAPH: OnceLock<IsogenyGraph> = OnceLock::new();
    GRAPH.get_or_init(IsogenyGraph::build)
}

// ── Walks ─────────────────────────────────────────────────────────────────────

/// Candidate next vertices for a walk step: the neighbours of `cur`
/// with the predecessor removed (so the *preferred* step never
/// backtracks).  Only when every neighbour equals the predecessor —
/// i.e. `cur` is a degree-1 or ramified vertex whose sole edge leads
/// back — do we fall back to the full neighbour set, forcing a
/// backtrack because there is no other way to continue.  Returns an
/// empty vector iff `cur` has no neighbours at all (not a supersingular
/// graph vertex); callers must treat that as the end of the walk rather
/// than index into it.
fn step_choices(g: &IsogenyGraph, cur: &Fp2, prev: Option<Fp2>) -> Vec<Fp2> {
    let forward: Vec<Fp2> = g
        .neighbors(cur)
        .iter()
        .copied()
        .filter(|n| Some(*n) != prev)
        .collect();
    if forward.is_empty() {
        g.neighbors(cur).to_vec()
    } else {
        forward
    }
}

/// Random walk of up to `len` steps starting at `start`.  Each step
/// avoids backtracking where the graph allows it (see `step_choices`);
/// it can only step back at a forced dead-end.  Returns the vertex
/// path (length `len + 1` for the well-connected toy graph, shorter
/// only if a vertex with no neighbours is reached).
fn random_walk(start: Fp2, len: usize) -> Vec<Fp2> {
    let g = graph();
    let mut rng = OsRng;
    let mut path = vec![start];
    for _ in 0..len {
        let cur = *path.last().unwrap();
        let prev = if path.len() >= 2 {
            Some(path[path.len() - 2])
        } else {
            None
        };
        let choices = step_choices(g, &cur, prev);
        if choices.is_empty() {
            break;
        }
        path.push(choices[rng.gen_range(0..choices.len())]);
    }
    path
}

/// The deterministic challenge walk from `start`, with each step's
/// edge index taken from a SHAKE256 stream over `(pk, commitment,
/// msg)`.  Steps avoid backtracking where possible (see `step_choices`)
/// and back-step only at forced dead-ends.  Both signer and verifier
/// recompute this identically, so any early stop at a neighbour-less
/// vertex is agreed by both.
fn challenge_walk(pk: &Fp2, commitment: &Fp2, msg: &[u8]) -> Vec<Fp2> {
    let g = graph();
    let mut input = b"SQIsign-toy-challenge".to_vec();
    input.extend_from_slice(&pk.to_bytes());
    input.extend_from_slice(&commitment.to_bytes());
    input.extend_from_slice(msg);
    let stream = shake256(&input, CHL_WALK_LEN);

    let mut path = vec![*commitment];
    for &byte in stream.iter() {
        let cur = *path.last().unwrap();
        let prev = if path.len() >= 2 {
            Some(path[path.len() - 2])
        } else {
            None
        };
        let choices = step_choices(g, &cur, prev);
        if choices.is_empty() {
            break;
        }
        path.push(choices[byte as usize % choices.len()]);
    }
    path
}

// ── Keys and signatures ───────────────────────────────────────────────────────

/// Public key: the j-invariant of the secret curve `E_A`.
#[derive(Clone, Debug, PartialEq)]
pub struct SqiSignPublicKey {
    pub j: Fp2,
}

/// Secret key: the isogeny walk `E₀ → E_A` (as its j-invariant path).
/// Real SQIsign stores the equivalent quaternion-ideal data instead.
#[derive(Clone, Debug)]
pub struct SqiSignSecretKey {
    pub path: Vec<Fp2>,
}

/// A signature: the commitment `j(E₁)` plus the response path
/// `j(E_A) → j(E₂)` (inclusive of both endpoints).
#[derive(Clone, Debug, PartialEq)]
pub struct SqiSignature {
    pub commitment: Fp2,
    pub response: Vec<Fp2>,
}

/// KeyGen: secret walk `φ_sk: E₀ → E_A`, public key `j(E_A)`.
pub fn sqisign_keygen() -> (SqiSignPublicKey, SqiSignSecretKey) {
    let path = random_walk(j0(), SK_WALK_LEN);
    let pk = SqiSignPublicKey {
        j: *path.last().unwrap(),
    };
    (pk, SqiSignSecretKey { path })
}

/// Sign: commit with a fresh random walk `E₀ → E₁`, derive the
/// challenge walk `E₁ → E₂` from the message, and respond with a path
/// `E_A → E₂`.
///
/// The response here is a BFS shortest path — the toy substitute for
/// KLPT (see module docs).  Like real SQIsign the signature therefore
/// consists of one curve and one isogeny path; unlike real SQIsign the
/// path is not sampled independently of the secret.
///
/// # ⚠️ The secret key is deliberately unused
/// This toy signer derives the response entirely from public data
/// (`pk` and the toy isogeny graph), so **`sk` is ignored and anyone
/// holding only the public key can produce a valid signature** — the
/// scheme is completely forgeable at these parameters.  The `sk`
/// argument is kept solely so the signature matches the real SQIsign
/// API, where producing the response *requires* the secret endomorphism
/// data via the Deuring correspondence + KLPT.  Recovering that data
/// from `pk` is the isogeny path problem, which is infeasible at real
/// parameters but trivial (a BFS) here.  Do not read secret-key
/// dependence into this signer.  See `sqisign_keygen` and the module
/// docs.
pub fn sqisign_sign(pk: &SqiSignPublicKey, _sk: &SqiSignSecretKey, msg: &[u8]) -> SqiSignature {
    let com_path = random_walk(j0(), COM_WALK_LEN);
    let commitment = *com_path.last().unwrap();
    let chl_path = challenge_walk(&pk.j, &commitment, msg);
    let j2 = *chl_path.last().unwrap();
    // In the real scheme only the secret-key holder can produce this
    // path (via the Deuring correspondence + KLPT).  In the toy graph,
    // BFS finds one in milliseconds — which is exactly why toy
    // parameters offer no security.
    let response = graph()
        .shortest_path(&pk.j, &j2)
        .expect("supersingular 2-isogeny graph is connected");
    SqiSignature {
        commitment,
        response,
    }
}

/// Verify: recompute the challenge walk from `(pk, commitment, msg)`,
/// then check the response is a genuine isogeny path from `j(E_A)` to
/// `j(E₂)`: correct endpoints, bounded length, and every consecutive
/// pair of j-invariants a root of `Φ₂`.
pub fn sqisign_verify(pk: &SqiSignPublicKey, msg: &[u8], sig: &SqiSignature) -> bool {
    let g = graph();
    // The public key and commitment must be supersingular j-invariants.
    if !g.contains(&pk.j) || !g.contains(&sig.commitment) {
        return false;
    }
    let chl_path = challenge_walk(&pk.j, &sig.commitment, msg);
    let j2 = *chl_path.last().unwrap();

    // Endpoint and length checks.
    if sig.response.first() != Some(&pk.j) || sig.response.last() != Some(&j2) {
        return false;
    }
    if sig.response.len() > MAX_RSP_LEN + 1 {
        return false;
    }
    // Each edge must be a 2-isogeny: Φ₂(j, j') = 0.  This is the whole
    // point of the modular polynomial — verification never touches a
    // curve equation.
    for w in sig.response.windows(2) {
        if !phi2(&w[0], &w[1]).is_zero() {
            return false;
        }
    }
    true
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn graph_has_expected_vertex_count() {
        // #supersingular j-invariants = ⌊p/12⌋ + ε, with ε = 2 for
        // p ≡ 11 (mod 12).  p = 431 → 35 + 2 = 37.
        assert_eq!(graph().vertex_count(), 37);
    }

    #[test]
    fn graph_vertices_have_at_most_three_neighbors() {
        // Φ₂(j, Y) is a cubic, so out-degree ≤ 3 (fewer at the ramified
        // vertices where roots collide).
        let g = graph();
        for j in g.adj.keys() {
            let n = g.neighbors(j).len();
            assert!((1..=3).contains(&n), "j = {:?} has {} neighbors", j, n);
        }
    }

    #[test]
    fn graph_adjacency_is_symmetric() {
        // Φ₂ is symmetric in X and Y, so 2-isogenies come in dual pairs.
        let g = graph();
        for (j, ns) in g.adj.iter() {
            for n in ns {
                assert!(
                    g.neighbors(n).contains(j),
                    "asymmetric edge {:?} -> {:?}",
                    j,
                    n
                );
            }
        }
    }

    #[test]
    fn base_vertex_is_in_graph() {
        assert!(graph().contains(&j0()));
    }

    #[test]
    fn phi2_detects_non_adjacent_pairs() {
        // A vertex is never 2-isogenous to a random non-neighbour.
        let g = graph();
        let j = j0();
        let ns = g.neighbors(&j);
        for other in g.adj.keys() {
            if *other != j && !ns.contains(other) {
                assert!(!phi2(&j, other).is_zero());
            }
        }
    }

    #[test]
    fn sign_verify_roundtrip() {
        let (pk, sk) = sqisign_keygen();
        let msg = b"SQIsign: the smallest post-quantum signatures";
        let sig = sqisign_sign(&pk, &sk, msg);
        assert!(sqisign_verify(&pk, msg, &sig));
    }

    #[test]
    fn wrong_message_rejected() {
        let (pk, sk) = sqisign_keygen();
        let sig = sqisign_sign(&pk, &sk, b"original message");
        assert!(!sqisign_verify(&pk, b"tampered message", &sig));
    }

    #[test]
    fn wrong_public_key_rejected() {
        let (pk_a, sk_a) = sqisign_keygen();
        let msg = b"message";
        let sig = sqisign_sign(&pk_a, &sk_a, msg);
        // Any other supersingular j-invariant as "public key" must fail:
        // the response path starts at the wrong vertex.
        let other = graph().adj.keys().find(|j| **j != pk_a.j).unwrap();
        let pk_b = SqiSignPublicKey { j: *other };
        assert!(!sqisign_verify(&pk_b, msg, &sig));
    }

    #[test]
    fn non_supersingular_public_key_rejected() {
        // An ordinary (non-supersingular) j-invariant is not a graph
        // vertex and must be rejected outright.
        let g = graph();
        let mut ordinary = None;
        'outer: for a in 0..P {
            let j = Fp2::from_u64(a);
            if !g.contains(&j) {
                ordinary = Some(j);
                break 'outer;
            }
        }
        let pk = SqiSignPublicKey {
            j: ordinary.unwrap(),
        };
        let (pk_real, sk) = sqisign_keygen();
        let sig = sqisign_sign(&pk_real, &sk, b"m");
        assert!(!sqisign_verify(&pk, b"m", &sig));
    }

    #[test]
    fn corrupted_response_path_rejected() {
        let (pk, sk) = sqisign_keygen();
        let msg = b"message";
        let mut sig = sqisign_sign(&pk, &sk, msg);
        if sig.response.len() >= 3 {
            // Replace an interior vertex with something non-adjacent.
            let g = graph();
            let mid = sig.response.len() / 2;
            let bad = g
                .adj
                .keys()
                .find(|j| {
                    !g.neighbors(&sig.response[mid - 1]).contains(j)
                        && phi2(&sig.response[mid - 1], j) != Fp2::from_u64(0)
                })
                .unwrap();
            sig.response[mid] = *bad;
            assert!(!sqisign_verify(&pk, msg, &sig));
        } else {
            // Degenerate short path: truncating it breaks the endpoint.
            sig.response.pop();
            assert!(!sqisign_verify(&pk, msg, &sig));
        }
    }

    #[test]
    fn overlong_response_rejected() {
        let (pk, sk) = sqisign_keygen();
        let msg = b"message";
        let mut sig = sqisign_sign(&pk, &sk, msg);
        // Pad the path with back-and-forth steps: still a valid walk,
        // but exceeding the length cap must be rejected.
        let g = graph();
        while sig.response.len() <= MAX_RSP_LEN + 1 {
            let last = *sig.response.last().unwrap();
            let back = g.neighbors(&last)[0];
            sig.response.push(back);
            sig.response.push(last);
        }
        // Restore the endpoint parity: path still ends at j2 because we
        // appended an even number of steps each round.
        assert!(!sqisign_verify(&pk, msg, &sig));
    }

    #[test]
    fn challenge_walk_is_deterministic() {
        let (pk, _) = sqisign_keygen();
        let c = j0();
        let w1 = challenge_walk(&pk.j, &c, b"msg");
        let w2 = challenge_walk(&pk.j, &c, b"msg");
        assert_eq!(w1, w2);
        let w3 = challenge_walk(&pk.j, &c, b"other");
        assert_ne!(w1, w3);
        assert_eq!(w1.len(), CHL_WALK_LEN + 1);
    }

    #[test]
    fn response_paths_are_valid_walks() {
        // The signer's BFS output is itself a valid walk in the graph.
        let (pk, sk) = sqisign_keygen();
        let sig = sqisign_sign(&pk, &sk, b"walk check");
        for w in sig.response.windows(2) {
            assert!(phi2(&w[0], &w[1]).is_zero());
        }
        assert!(sig.response.len() <= MAX_RSP_LEN + 1);
    }
}
