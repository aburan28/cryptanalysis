//! # Level E3 — the `ℓ`-isogeny ball around ECC2K-130 itself.
//!
//! At `n = 131` the solving degree is unobservable: the Boolean system
//! has `262` unknowns and its Macaulay matrices are astronomically
//! larger than anything a study library ranks.  So this level does not
//! measure `D*`.  It walks the isogeny graph **exhaustively to a fixed
//! radius** and screens every curve it reaches against the *structural*
//! properties that are known to move `D*` — the properties
//! `research/notes/index-calculus/RESEARCH_DEGREE_REDUCTION.md` §2 calls lever **L1**:
//!
//! | screen | what it would buy | what the walk finds |
//! |---|---|---|
//! | `j ∈ F_{2^d}`, `d ⊊ 131` | the subfield/Koblitz factor base, `D*` 3.53 → 2.04 | only at the start point, and only because `131` is prime |
//! | GHS magic number `2 ≤ m ≤ 6` | Weil descent to a tractable genus | unreachable for *any* `b`: see [`achievable_magic_numbers`] |
//! | sparse `b` | smaller constant vector, nothing structural | the walk finds dense `b`, and sparsity is not a lever anyway |
//!
//! ## Why the magic-number screen is decided before the walk starts
//!
//! The GHS magic number of `E_{a,b}` over `F_{2^N}/F_2` is
//! `dim_{F_2} ⟨√b, √b², √b⁴, …⟩` — the dimension of the smallest
//! **Frobenius-invariant** `F_2`-subspace containing `√b`.  Those
//! subspaces are the `F_2[x]/(x^N − 1)`-submodules of `F_{2^N}`, so
//! their dimensions are exactly the **degrees of the divisors of
//! `x^N − 1` over `F_2`**, i.e. the subset sums of the cyclotomic coset
//! sizes.
//!
//! For `N = 131`: `131` is prime and `ord_{131}(2) = 130`, so `x^131 − 1`
//! factors as `(x + 1) · f` with `f` irreducible of degree `130`.  The
//! attainable dimensions are therefore
//!
//! ```text
//!     {0, 1, 130, 131}
//! ```
//!
//! and the useful GHS window `2 ≤ m ≤ 6` is **empty** — not for
//! ECC2K-130, not for any curve over `F_{2^131}`, isogenous or not.
//! [`achievable_magic_numbers`] computes this for any `N`, and
//! [`ghs_window_is_empty`] states the `131` case as a predicate.
//!
//! That is a statement about all `2^131` curves over the field, derived
//! rather than sampled, so it covers the part of the isogeny class no
//! walk of any radius can enumerate.
//!
//! ## The same divisor set closes the quasi-subfield route
//!
//! [`crate::cryptanalysis::quasi_subfield`] (see
//! `research/notes/index-calculus/RESEARCH_QUASI_SUBFIELD.md`) reaches the ECDLP from the other
//! direction: it builds a factor base from the roots of a
//! quasi-subfield polynomial, which exist exactly where a
//! Frobenius-stable `F_2`-subspace does — i.e. exactly at the divisor
//! degrees of `t^n − 1`.  That is the **same** set
//! [`achievable_magic_numbers`] computes, so one calculation settles
//! both questions at `n = 131`:
//!
//! ```text
//!     attainable dimensions over F_{2^131}  =  {0, 1, 130, 131}
//!       → GHS window 2..=6            empty
//!       → n0 = 1    the subfield F_2, a factor base of 2 elements
//!       → n0 = 130  the trace hyperplane, a factor base of half the field
//! ```
//!
//! Neither surviving dimension is a usable factor base, so the two
//! known routes to a lower first fall degree on a binary curve are
//! closed over this field by one line of divisor arithmetic — and
//! closed for every curve, not just for ECC2K-130's isogeny class.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use crate::cryptanalysis::binary_isogeny::{j_invariant, l_isogenous_neighbours};
use crate::cryptanalysis::ec_trapdoor::{magic_number_full, FieldTower};
use crate::cryptanalysis::ghs_descent::ECurve;
use num_bigint::BigInt;
use num_traits::One;
use std::collections::{HashSet, VecDeque};

/// `z^131 + z^13 + z^2 + z + 1` — the reduction polynomial the
/// ECC2K-130 challenge specifies for `F_{2^131}`.
///
/// Distinct from [`IrreduciblePoly::deg_131`], which is the SECG
/// sect131 pentanomial `z^131 + z^8 + z^3 + z^2 + 1`.  The fields are
/// isomorphic; the basis is not, and `b`-sparsity — one of the screens
/// below — is basis-dependent, so the challenge's own basis is the one
/// to screen in.
pub fn ecc2k130_reduction_poly() -> IrreduciblePoly {
    IrreduciblePoly {
        degree: 131,
        low_terms: vec![0, 1, 2, 13],
    }
}

/// **ECC2K-130** as a curve this module can walk from:
/// `y² + xy = x³ + 1` over `F_{2^131}`, i.e. `a = 0`, `b = 1`, `j = 1`.
pub fn ecc2k130_curve() -> ECurve {
    let irr = ecc2k130_reduction_poly();
    ECurve::new(131, irr, F2mElement::zero(131), F2mElement::one(131))
}

/// The `F_{2^131}/F_2` tower the GHS magic number is taken over.  With
/// `131` prime this is the only tower there is — which is the whole
/// reason the window below is empty.
pub fn ecc2k130_tower() -> FieldTower {
    FieldTower::new(131, 131, 1, ecc2k130_reduction_poly())
}

// ── Frobenius-module dimensions: the magic numbers a field admits ───

/// Degrees of the irreducible factors of `x^n − 1` over `F_2`, **with
/// multiplicity**.
///
/// For odd `n` these are the sizes of the 2-cyclotomic cosets mod `n`,
/// each occurring once (`x^n − 1` is squarefree).  For `n = 2^v · n'`
/// with `n'` odd, `x^n − 1 = (x^{n'} − 1)^{2^v}` in characteristic 2, so
/// every factor of the odd part repeats `2^v` times — and the repeats
/// matter, because a divisor may take each factor up to `2^v` times.
pub fn cyclotomic_coset_sizes(n: u32) -> Vec<u32> {
    assert!(n >= 1, "n must be positive");
    let mut odd = n;
    let mut multiplicity = 1u32;
    while odd.is_multiple_of(2) {
        odd /= 2;
        multiplicity *= 2;
    }
    let mut seen = vec![false; odd as usize];
    let mut sizes = Vec::new();
    for s in 0..odd {
        if seen[s as usize] {
            continue;
        }
        let mut size = 0u32;
        let mut c = s;
        loop {
            seen[c as usize] = true;
            size += 1;
            c = (c * 2) % odd;
            if c == s {
                break;
            }
        }
        for _ in 0..multiplicity {
            sizes.push(size);
        }
    }
    sizes.sort_unstable();
    sizes
}

/// **Every GHS magic number attainable over `F_{2^n}`**, for any choice
/// of curve parameter `b` whatsoever.
///
/// The magic number is the dimension of the smallest Frobenius-invariant
/// `F_2`-subspace containing `√b`.  Those subspaces are the divisors of
/// `x^n − 1`, so the attainable dimensions are the subset sums of
/// [`cyclotomic_coset_sizes`].
///
/// For `n = 131` this returns `[0, 1, 130, 131]`.
pub fn achievable_magic_numbers(n: u32) -> Vec<u32> {
    let sizes = cyclotomic_coset_sizes(n);
    let mut reach = vec![false; n as usize + 1];
    reach[0] = true;
    for s in sizes {
        for d in (0..=n as usize).rev() {
            if reach[d] && d + s as usize <= n as usize {
                reach[d + s as usize] = true;
            }
        }
    }
    (0..=n).filter(|d| reach[*d as usize]).collect()
}

/// Is the useful GHS window `lo ..= hi` empty over `F_{2^n}` — i.e. can
/// **no** curve over the field descend to a tractable genus?
///
/// `ghs_window_is_empty(131, 2, 6)` is `true`, and that single fact
/// disposes of Weil descent for the entire isogeny class.
pub fn ghs_window_is_empty(n: u32, lo: u32, hi: u32) -> bool {
    !achievable_magic_numbers(n)
        .iter()
        .any(|m| *m >= lo && *m <= hi)
}

// ── Which ℓ admit a rational isogeny at all ────────────────────────

/// Discriminant of the Frobenius: `Δ = t² − 4q`, negative for an
/// ordinary curve.
pub fn frobenius_disc(t: i128, q: &BigInt) -> BigInt {
    BigInt::from(t) * BigInt::from(t) - BigInt::from(4) * q
}

/// `Δ` for ECC2K-130: `t = s_131` from the Koblitz recurrence,
/// `q = 2^131`.
pub fn ecc2k130_disc() -> BigInt {
    let t = super::census::koblitz_trace_recurrence(-1, 131);
    frobenius_disc(t, &(BigInt::one() << 131u32))
}

/// What the `ℓ`-isogeny graph looks like locally at one curve.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct LocalIsogenyStructure {
    /// The isogeny degree.
    pub l: u32,
    /// `(D_K / ℓ)`: `+1` split, `−1` inert, `0` ramified.
    pub kronecker: i32,
    /// Does `ℓ` divide the conductor of `Z[π]` in `O_K` — i.e. does the
    /// `ℓ`-volcano have positive height?
    pub divides_conductor: bool,
    /// Number of `F_q`-rational `ℓ`-isogenies out of the curve.
    pub rational_isogenies: u64,
}

impl LocalIsogenyStructure {
    /// Can the walk take a step of this degree at all?
    pub fn is_walkable(&self) -> bool {
        self.rational_isogenies > 0
    }
}

/// **Exhaustively decide, for every prime `ℓ ≤ l_max`, how many rational
/// `ℓ`-isogenies the curve has** — without any modular polynomial.
///
/// A rational `ℓ`-isogeny exists iff Frobenius has an eigenvalue on
/// `E[ℓ]`, i.e. iff `X² − tX + q` has a root mod `ℓ`.  Writing
/// `Δ = f²·D_K`, the count depends on where the curve sits in the
/// `ℓ`-volcano:
///
/// - **`ℓ ∤ f`** — the volcano has height 0 and the count is
///   `1 + (D_K/ℓ)`: `2` split, `0` inert, `1` ramified.
/// - **`ℓ | f`** — the volcano has positive height.  A **Koblitz curve
///   sits on its surface**: it is defined over `F_2`, so the `F_2`-power
///   Frobenius `τ` is one of its endomorphisms and
///   `End(E) ⊇ Z[τ] = O_K`, the maximal order of `Q(√−7)`.  A surface
///   vertex has `1 + (D_K/ℓ)` horizontal and `ℓ − (D_K/ℓ)` descending
///   neighbours, so the count is `ℓ + 1`.
///
/// This is a Legendre symbol plus a divisibility test per prime, so the
/// screen reaches `l_max = 10^5` in milliseconds, where a `Φ_ℓ` table
/// would need `Θ(ℓ³ log ℓ)` bits and stop near `ℓ = 100`.
///
/// `ℓ = 2` is special in characteristic 2 and is excluded: see
/// [`two_isogeny_is_frobenius`].
///
/// Returns `None` if `Δ` is not of the Koblitz form `f²·(−7)`.
pub fn rational_isogeny_degrees(disc: &BigInt, l_max: u32) -> Vec<LocalIsogenyStructure> {
    let conductor_primes: Vec<u64> = conductor_primes_of(disc).unwrap_or_default();
    small_odd_primes(l_max)
        .into_iter()
        .map(|l| {
            let k =
                super::class_number::kronecker_symbol(super::class_number::KOBLITZ_D_K, l as u64);
            let divides_conductor = conductor_primes.contains(&(l as u64));
            let rational_isogenies = if divides_conductor {
                l as u64 + 1
            } else {
                (1 + k) as u64
            };
            LocalIsogenyStructure {
                l,
                kronecker: k,
                divides_conductor,
                rational_isogenies,
            }
        })
        .collect()
}

/// The primes dividing the conductor of `Z[π]` in `O_K`, for a Koblitz
/// discriminant `Δ = f²·(−7)`.  `None` if `Δ` has another shape.
///
/// Re-exported from [`super::class_number`] so the screen and the class
/// count cannot disagree about what `f` is.
pub use super::class_number::koblitz_conductor_primes as conductor_primes_of;

/// Odd primes up to `l_max`, by sieve.
pub fn small_odd_primes(l_max: u32) -> Vec<u32> {
    if l_max < 3 {
        return Vec::new();
    }
    let mut sieve = vec![true; l_max as usize + 1];
    sieve[0] = false;
    if l_max >= 1 {
        sieve[1] = false;
    }
    let mut p = 2usize;
    while p * p <= l_max as usize {
        if sieve[p] {
            let mut k = p * p;
            while k <= l_max as usize {
                sieve[k] = false;
                k += p;
            }
        }
        p += 1;
    }
    (3..=l_max).filter(|l| sieve[*l as usize]).collect()
}

/// **In characteristic 2 the 2-isogeny graph carries no information.**
///
/// The Kronecker congruence `Φ_ℓ(X, Y) ≡ (X − Y^ℓ)(X^ℓ − Y) (mod ℓ)`
/// at `ℓ = 2` reads `Φ_2(X, Y) ≡ (X + Y²)(X² + Y) (mod 2)`, so the only
/// 2-isogenous `j`-invariants are `j²` (Frobenius) and `√j`
/// (Verschiebung) — both inseparable, both in the curve's own Galois
/// orbit.  An ordinary binary curve has `E[2] ≅ Z/2`, so there is no
/// separable 2-isogeny to find.
///
/// For ECC2K-130, `j = 1 ∈ F_2` is fixed by Frobenius, so the 2-isogeny
/// "walk" from it is a self-loop: `walk_isogeny_ball(.., &[2], r, ..)`
/// returns a single node at every radius.  This function states that as
/// a predicate on a `j`-invariant, so a caller can assert it rather than
/// discover it.
pub fn two_isogeny_is_frobenius(j: &F2mElement, irr: &IrreduciblePoly) -> (F2mElement, F2mElement) {
    let m = irr.degree;
    let up = j.square(irr);
    let down = j.square_k_times(m - 1, irr);
    (up, down)
}

// ── The ball walk ──────────────────────────────────────────────────

/// Structural screen applied to one curve reached by the walk.
///
/// None of these fields is a solving degree.  They are the *inputs*
/// `D*` is known to respond to, which is all that can be evaluated at
/// `n = 131`.
#[derive(Clone, Debug)]
pub struct BallScreen {
    /// `j(E')`, as the raw bit pattern.
    pub j_bits: Vec<u64>,
    /// Hamming weight of `b = 1/j` in the challenge's polynomial basis.
    /// A structural non-lever, recorded because a walk that found a
    /// sparse `b` would at least be *surprising*.
    pub b_weight: u32,
    /// The smallest proper subfield containing `j`, if any — the only
    /// screen that would matter.
    pub subfield_degree: Option<u32>,
    /// GHS magic number over `F_{2^131}/F_2`.
    pub magic: u32,
}

/// One node of the ball.
#[derive(Clone, Debug)]
pub struct BallNode {
    /// Distance from the start, in isogeny steps.
    pub depth: u32,
    /// Isogeny degree of the step that reached it.
    pub reached_by: u32,
    /// The screen.
    pub screen: BallScreen,
}

/// What the exhaustive ball walk found.
#[derive(Clone, Debug)]
pub struct BallReport {
    /// Extension degree walked in.
    pub n: u32,
    /// Isogeny degrees used.
    pub degrees: Vec<u32>,
    /// Radius actually reached (may be below the request if the node cap
    /// bit first).
    pub radius: u32,
    /// Distinct `j`-invariants visited, start included.
    pub nodes: Vec<BallNode>,
    /// True if the node cap stopped the walk before the radius.
    pub truncated: bool,
}

impl BallReport {
    /// Nodes whose `j` lies in a proper subfield — the only ones that
    /// would carry lever L1.
    pub fn subfield_hits(&self) -> Vec<&BallNode> {
        self.nodes
            .iter()
            .filter(|nd| nd.screen.subfield_degree.is_some())
            .collect()
    }

    /// Nodes whose GHS magic number lands in the tractable window.
    pub fn ghs_hits(&self, lo: u32, hi: u32) -> Vec<&BallNode> {
        self.nodes
            .iter()
            .filter(|nd| nd.screen.magic >= lo && nd.screen.magic <= hi)
            .collect()
    }

    /// Minimum Hamming weight of `b` seen away from the start — how
    /// close the walk got to a "special-looking" curve.
    pub fn min_b_weight_off_start(&self) -> Option<u32> {
        self.nodes
            .iter()
            .filter(|nd| nd.depth > 0)
            .map(|nd| nd.screen.b_weight)
            .min()
    }
}

/// Screen one curve.
pub fn screen(curve: &ECurve, tower: &FieldTower) -> BallScreen {
    let j = j_invariant(curve);
    let magic = magic_number_full(tower, &curve.a, &curve.b);
    let subfield_degree = (1..curve.m)
        .filter(|d| curve.m.is_multiple_of(*d))
        .find(|d| tower.is_in_subfield(&j, *d));
    let b_weight = curve
        .b
        .raw_bits()
        .iter()
        .map(|w| w.count_ones())
        .sum::<u32>();
    BallScreen {
        j_bits: j.raw_bits().to_vec(),
        b_weight,
        subfield_degree,
        magic,
    }
}

/// **Exhaustive breadth-first walk** of the `ℓ`-isogeny graph out to
/// `radius` steps from `start`, screening every curve reached.
///
/// Exhaustive in the sense that matters here: every `j`-invariant within
/// `radius` steps under the given isogeny degrees is visited exactly
/// once.  It is *not* exhaustive over the isogeny class — see
/// [`super::cost::SearchBoundary`] for why no walk can be, and
/// [`achievable_magic_numbers`] plus
/// [`super::census::subfield_j_count`] for the derivations that cover
/// what the walk cannot reach.
pub fn walk_isogeny_ball(
    start: &ECurve,
    tower: &FieldTower,
    degrees: &[u32],
    radius: u32,
    max_nodes: usize,
) -> BallReport {
    let mut visited: HashSet<Vec<u64>> = HashSet::new();
    let mut nodes = Vec::new();
    let mut queue: VecDeque<(ECurve, u32)> = VecDeque::new();

    let start_j = j_invariant(start);
    visited.insert(start_j.raw_bits().to_vec());
    nodes.push(BallNode {
        depth: 0,
        reached_by: 0,
        screen: screen(start, tower),
    });
    queue.push_back((start.clone(), 0));

    let mut deepest = 0u32;
    let mut truncated = false;

    while let Some((cur, depth)) = queue.pop_front() {
        if depth >= radius {
            continue;
        }
        for &l in degrees {
            for nb in l_isogenous_neighbours(&cur, l) {
                let key = j_invariant(&nb).raw_bits().to_vec();
                if !visited.insert(key) {
                    continue;
                }
                if nodes.len() >= max_nodes {
                    truncated = true;
                    return BallReport {
                        n: start.m,
                        degrees: degrees.to_vec(),
                        radius: deepest,
                        nodes,
                        truncated,
                    };
                }
                deepest = deepest.max(depth + 1);
                nodes.push(BallNode {
                    depth: depth + 1,
                    reached_by: l,
                    screen: screen(&nb, tower),
                });
                queue.push_back((nb, depth + 1));
            }
        }
    }

    BallReport {
        n: start.m,
        degrees: degrees.to_vec(),
        radius: deepest,
        nodes,
        truncated,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The challenge's reduction polynomial must actually be
    /// irreducible.  With `131` prime it is enough that `f` has no root
    /// in `F_2` and that `x^{2^131} ≡ x (mod f)`.
    #[test]
    fn ecc2k130_reduction_poly_is_irreducible() {
        let irr = ecc2k130_reduction_poly();
        // f(0) = 1 (constant term present), f(1) = 1 + 4 terms = 1.
        assert!(irr.low_terms.contains(&0), "f(0) must be 1");
        assert_eq!((irr.low_terms.len() as u32 + 1) % 2, 1, "f(1) must be 1");
        let z = F2mElement::z(131);
        assert_eq!(z.square_k_times(131, &irr), z, "x^{{2^131}} ≡ x (mod f)");
    }

    /// `x^131 − 1 = (x+1)·f` with `deg f = 130`, so the GHS magic number
    /// over `F_{2^131}` can only ever be `0, 1, 130` or `131`.
    #[test]
    fn ecc2k130_ghs_window_is_empty() {
        assert_eq!(cyclotomic_coset_sizes(131), vec![1, 130]);
        assert_eq!(achievable_magic_numbers(131), vec![0, 1, 130, 131]);
        assert!(ghs_window_is_empty(131, 2, 6));
        // The contrast: a composite degree has plenty of room, which is
        // why GHS breaks c2pnb176w1 and cannot touch ECC2K-130.
        assert!(!ghs_window_is_empty(176, 2, 6));
    }

    /// The same divisor set closes the quasi-subfield route.  A
    /// quasi-subfield factor base needs a Frobenius-stable subspace, so
    /// its dimension must be one of these; over `F_{2^131}` that leaves
    /// only `F_2` (two elements) and the trace hyperplane (half the
    /// field), neither of which is a usable factor base.
    #[test]
    fn no_usable_quasi_subfield_dimension_over_f2_131() {
        let dims = achievable_magic_numbers(131);
        let usable: Vec<u32> = dims
            .iter()
            .copied()
            .filter(|d| *d > 1 && *d < 131 && *d * 2 < 131)
            .collect();
        assert!(
            usable.is_empty(),
            "a factor base needs 1 < n0 < n/2; attainable dimensions were {dims:?}"
        );
        // Cross-check the criterion the sibling thread states: the
        // attainable dimensions are the divisor degrees of t^n − 1, and
        // `quasi_subfield` agrees on a size it can evaluate.
        let cosets =
            crate::cryptanalysis::quasi_subfield::cyclotomic_cosets(131).expect("131 is odd");
        let mut sizes: Vec<u32> = cosets.iter().map(|c| c.len() as u32).collect();
        sizes.sort_unstable();
        assert_eq!(sizes, cyclotomic_coset_sizes(131));
    }

    /// ECC2K-130 itself screens as the subfield curve (`j = 1 ∈ F_2`)
    /// with the useless magic number `1`.
    #[test]
    fn start_point_is_the_subfield_curve() {
        let curve = ecc2k130_curve();
        let tower = ecc2k130_tower();
        let s = screen(&curve, &tower);
        assert_eq!(s.subfield_degree, Some(1), "j = 1 lies in F_2");
        assert_eq!(s.b_weight, 1, "b = 1");
        assert_eq!(s.magic, 1, "√b = 1 spans a 1-dimensional module");
    }

    /// The 2-isogeny graph in characteristic 2 is the Frobenius orbit:
    /// the neighbours of `j` are `j²` and `√j`, nothing else.  For
    /// `j = 1` that is a self-loop, so the ball never leaves the start.
    #[test]
    fn two_isogeny_graph_is_degenerate() {
        let curve = ecc2k130_curve();
        let tower = ecc2k130_tower();
        let irr = ecc2k130_reduction_poly();
        let j = j_invariant(&curve);
        let (up, down) = two_isogeny_is_frobenius(&j, &irr);
        assert_eq!(up, j, "j = 1 is fixed by Frobenius");
        assert_eq!(down, j, "and by Verschiebung");

        let report = walk_isogeny_ball(&curve, &tower, &[2], 4, 64);
        assert_eq!(
            report.nodes.len(),
            1,
            "the 2-isogeny ball around j = 1 is the single point {{1}}"
        );
        assert!(!report.truncated);
    }

    /// ECC2K-130 has **no rational 3-isogeny**: `(Δ / 3) = −1`, so the
    /// walk cannot take a step at `ℓ = 3` either — and the two
    /// independent routes to that fact, the Legendre symbol and the
    /// modular polynomial, must agree.
    #[test]
    fn no_rational_three_isogeny() {
        let disc = ecc2k130_disc();
        let structure = rational_isogeny_degrees(&disc, 3);
        assert_eq!(structure.len(), 1);
        assert_eq!(structure[0].l, 3);
        assert_eq!(structure[0].kronecker, -1, "3 is inert in the CM order");
        assert!(!structure[0].is_walkable());

        let curve = ecc2k130_curve();
        let tower = ecc2k130_tower();
        let report = walk_isogeny_ball(&curve, &tower, &[3], 2, 64);
        assert_eq!(report.nodes.len(), 1, "Φ_3(X, 1) has no F_{{2^131}} root");
    }

    /// The smallest degree at which ECC2K-130 can move at all is
    /// `ℓ = 7`, and it moves there because `7 | Δ` (a ramified prime,
    /// one rational isogeny), not because `Δ` splits.
    #[test]
    fn smallest_walkable_degree_is_seven() {
        let disc = ecc2k130_disc();
        let structure = rational_isogeny_degrees(&disc, 50);
        let first = structure
            .iter()
            .find(|s| s.is_walkable())
            .expect("some prime must be walkable");
        assert_eq!(first.l, 7);
        assert_eq!(first.kronecker, 0, "7 divides the discriminant");
        assert_eq!(first.rational_isogenies, 1);
        for s in structure.iter().take_while(|s| s.l < 7) {
            assert_eq!(s.kronecker, -1, "ℓ = {} must be inert", s.l);
        }
    }

    /// At a prime dividing the conductor the volcano has positive
    /// height, and ECC2K-130 sits on its **surface** — it is defined
    /// over `F_2`, so `τ ∈ End(E)` and `End(E) = Z[τ] = O_K`.  A surface
    /// vertex has `ℓ + 1` rational `ℓ`-isogenies, not `1 + (D_K/ℓ)`.
    #[test]
    fn conductor_primes_see_the_whole_volcano() {
        let disc = ecc2k130_disc();
        let primes = conductor_primes_of(&disc).expect("Δ = f²·(−7)");
        assert!(primes.contains(&263), "263 | f");
        let structure = rational_isogeny_degrees(&disc, 300);
        let at_263 = structure.iter().find(|s| s.l == 263).unwrap();
        assert!(at_263.divides_conductor);
        assert_eq!(at_263.rational_isogenies, 264, "ℓ + 1 at a surface vertex");
        // A prime that does not divide f gets the height-0 count.
        let at_11 = structure.iter().find(|s| s.l == 11).unwrap();
        assert!(!at_11.divides_conductor);
        assert_eq!(at_11.kronecker, 1);
        assert_eq!(at_11.rational_isogenies, 2);
    }

    /// The screen must nonetheless find plenty of walkable degrees — the
    /// point is not that the class is unreachable, it is that reaching
    /// it buys nothing.  Roughly half of all primes split.
    #[test]
    fn most_primes_are_walkable_and_the_split_rate_is_half() {
        let disc = ecc2k130_disc();
        let structure = rational_isogeny_degrees(&disc, 2000);
        let walkable = structure.iter().filter(|s| s.is_walkable()).count();
        let total = structure.len();
        let rate = walkable as f64 / total as f64;
        assert!(
            (0.35..0.65).contains(&rate),
            "split rate {rate} over {total} primes"
        );
        let smallest = structure.iter().find(|s| s.is_walkable()).map(|s| s.l);
        assert!(smallest.is_some(), "some small prime must be walkable");
    }

    /// Only the start point carries subfield structure, and the GHS
    /// window stays empty, at every node the ball reaches.
    #[test]
    fn ball_finds_no_second_subfield_curve() {
        let curve = ecc2k130_curve();
        let tower = ecc2k130_tower();
        let report = walk_isogeny_ball(&curve, &tower, &[2, 3], 3, 64);
        let mut seen = HashSet::new();
        for nd in &report.nodes {
            assert!(seen.insert(nd.screen.j_bits.clone()), "no j twice");
        }
        let hits = report.subfield_hits();
        assert_eq!(hits.len(), 1, "only the start point has subfield j");
        assert_eq!(hits[0].depth, 0);
        assert!(report.ghs_hits(2, 6).is_empty(), "window is empty a priori");
    }
}
