//! # Boolean-ring Gröbner basis over `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)`.
//!
//! Hand-rolled, no-deps Buchberger implementation
//! specialised to the **boolean polynomial ring** — the natural setting
//! for Weil-descended Petit-Quisquater systems.
//!
//! ## Design choices
//!
//! - **Monomials = `u64` bitmasks.**  In the boolean quotient `v_i² = v_i`
//!   so every variable appears with exponent 0 or 1; a monomial is just
//!   a subset of `{0, …, n-1}`.  Capped at 64 variables (plenty for the
//!   toy regime; real PQ at production scale would need a larger
//!   monomial type or a sparse exponent vector).
//!
//! - **Coefficients = none.**  Over `F_2` every non-zero element is 1,
//!   so a polynomial is exactly a set of monomials (XOR = symmetric
//!   difference).  Addition is *much* cheaper than over a general
//!   prime field.
//!
//! - **Monomial order = DegRevLex** with `v_0 > v_1 > … > v_{n-1}`.  This
//!   is the standard choice for solving systems via Gröbner basis +
//!   back-substitution.
//!
//! - **Quotient by `v_i² − v_i`** is **baked into the representation**,
//!   not added as explicit generators.  `mul_mono` uses union-of-masks,
//!   so multiplying by an idempotent monomial automatically applies
//!   `v_i² = v_i`.  This is the boolean-ring trick and is why the GB
//!   always terminates fast (the variety is contained in `{0,1}^n`).
//!
//! ## What this implements
//!
//! - [`F2BoolMono`] — monomial as `u64` bitmask.
//! - [`F2BoolPoly`] — sorted (DegRevLex desc) `Vec<F2BoolMono>`.
//! - [`spoly`] — S-polynomial of two non-zero polynomials.
//! - [`reduce`] — multivariate division-with-remainder against a basis.
//! - [`groebner_basis_f2`] — Buchberger with the coprime and chain
//!   criteria, under the normal (lowest-lcm-degree-first) selection,
//!   closed under the field equations' S-polynomials.
//! - [`is_boolean_groebner_basis`] — the unpruned criterion, to check it.
//! - [`solve_system_f2`] — brute-force solution extraction over
//!   `{0,1}^n` (fine for the toy; real PQ uses triangular back-
//!   substitution from the reduced GB).
//!
//! ## Why hand-rolled instead of `gbrl`
//!
//! The `research/gbrl/` crate has a Buchberger + RL-guided F4 over the
//! prime field `F_p` with `p = 1_000_003`.  Its `Fp` type is hard-coded
//! to that modulus — not generic over `F_2` — and parameterising it
//! would mean either a sweeping refactor of a research artefact or a
//! second copy of the polynomial machinery.  The boolean specialisation
//! here is ~10× smaller than the generic implementation (no field
//! inversions, monomials fit in a `u64`, addition is XOR of sets) so a
//! standalone module wins on both clarity and size.
//!
//! ## References
//!
//! - **B. Buchberger**, *Ein Algorithmus zum Auffinden der Basiselemente
//!   des Restklassenrings nach einem nulldimensionalen Polynomideal*,
//!   PhD thesis, Univ. Innsbruck, 1965.
//! - **R. Gebauer, H. M. Möller**, *On an installation of Buchberger's
//!   algorithm*, J. Symbolic Comput. 6 (1988).
//! - **D. Cox, J. Little, D. O'Shea**, *Ideals, Varieties, and
//!   Algorithms*, 4th ed., Springer 2015 — chapter 2 for the
//!   foundational definitions used here.
//! - **G. Bard**, *Algebraic Cryptanalysis*, Springer 2009 — chapter 13
//!   for the boolean-ring specialisation and ANF representation.

use std::cmp::Ordering;
use std::collections::HashSet;

// ── Monomial ───────────────────────────────────────────────────────

/// A monomial in `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)` represented as a
/// bitmask: bit `k` is set iff `v_k` divides the monomial.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug, serde::Serialize, serde::Deserialize)]
pub struct F2BoolMono {
    pub mask: u64,
}

impl F2BoolMono {
    /// The constant monomial `1`.
    pub fn one() -> Self {
        F2BoolMono { mask: 0 }
    }

    /// A single variable `v_k`.
    pub fn var(k: u32) -> Self {
        assert!(k < 64, "monomial cap is 64 variables");
        F2BoolMono { mask: 1u64 << k }
    }

    /// Build from a bitmask directly.
    pub fn from_mask(mask: u64) -> Self {
        F2BoolMono { mask }
    }

    /// Total degree = number of distinct variables appearing.
    pub fn degree(&self) -> u32 {
        self.mask.count_ones()
    }

    /// `self | other` — divisibility in the boolean ring.
    pub fn divides(&self, other: F2BoolMono) -> bool {
        (self.mask & !other.mask) == 0
    }

    /// `lcm(self, other)` = union of variable sets.
    pub fn lcm(&self, other: F2BoolMono) -> F2BoolMono {
        F2BoolMono {
            mask: self.mask | other.mask,
        }
    }

    /// `gcd(self, other)` = intersection of variable sets.
    pub fn gcd(&self, other: F2BoolMono) -> F2BoolMono {
        F2BoolMono {
            mask: self.mask & other.mask,
        }
    }

    /// Multiplication: `(v_a v_b)(v_b v_c) = v_a v_b v_c` (idempotent
    /// on shared variables).
    pub fn mul(&self, other: F2BoolMono) -> F2BoolMono {
        F2BoolMono {
            mask: self.mask | other.mask,
        }
    }

    /// `self / other` — exact division when `other.divides(self)`.
    /// Returns the complement-mask of `other` within `self`.
    pub fn div(&self, other: F2BoolMono) -> F2BoolMono {
        debug_assert!(other.divides(*self), "non-exact division");
        F2BoolMono {
            mask: self.mask & !other.mask,
        }
    }
}

/// DegRevLex order with `v_0 > v_1 > … > v_{n-1}`.
///
/// Standard textbook DegRevLex: `a > b` iff
/// (i)  `deg(a) > deg(b)`, or
/// (ii) `deg(a) = deg(b)` and the highest-indexed variable in the
///      symmetric difference is present in `b` (not in `a`).
///
/// This gives a graded ordering compatible with the boolean ring; in
/// the worst case the GB has up to `2^n` elements but in practice
/// (and for the PQ systems here) it terminates in O(n) elements.
#[inline]
pub fn cmp_mono(a: F2BoolMono, b: F2BoolMono) -> Ordering {
    let da = a.degree();
    let db = b.degree();
    if da != db {
        return da.cmp(&db);
    }
    let diff = a.mask ^ b.mask;
    if diff == 0 {
        return Ordering::Equal;
    }
    let high = 63 - diff.leading_zeros();
    if (a.mask >> high) & 1 == 1 {
        // a has the high-index var → a is *smaller* in DegRevLex.
        Ordering::Less
    } else {
        Ordering::Greater
    }
}

/// An integer key whose natural order is [`cmp_mono`]: degree first, and
/// within a degree the monomial lacking the highest differing variable is
/// larger, i.e. the one with the *smaller* mask.  Sorting by the key is a
/// few integer compares where the comparator recomputes two popcounts.
#[inline]
pub fn mono_key(m: F2BoolMono) -> u128 {
    (u128::from(m.degree()) << 64) | u128::from(!m.mask)
}

// ── Polynomial ─────────────────────────────────────────────────────

/// A polynomial in `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)`.
///
/// Stored as a `Vec<F2BoolMono>` sorted DESCENDING by [`cmp_mono`] with
/// no duplicates.  `terms[0]` (if present) is the leading monomial.
#[derive(Clone, PartialEq, Eq, Debug, serde::Serialize, serde::Deserialize)]
pub struct F2BoolPoly {
    pub terms: Vec<F2BoolMono>,
    pub n_vars: usize,
}

impl F2BoolPoly {
    pub fn zero(n_vars: usize) -> Self {
        F2BoolPoly {
            terms: vec![],
            n_vars,
        }
    }

    pub fn one(n_vars: usize) -> Self {
        F2BoolPoly {
            terms: vec![F2BoolMono::one()],
            n_vars,
        }
    }

    pub fn is_zero(&self) -> bool {
        self.terms.is_empty()
    }

    /// Leading monomial.
    pub fn lt(&self) -> Option<F2BoolMono> {
        self.terms.first().copied()
    }

    /// Construct from an unordered monomial list.  Sorts; cancels
    /// duplicate pairs (since `1 + 1 = 0` in `F_2`).
    pub fn from_monos(mut monos: Vec<F2BoolMono>, n_vars: usize) -> Self {
        // descending; equal keys are equal monomials, so unstable is exact
        monos.sort_unstable_by_key(|m| std::cmp::Reverse(mono_key(*m)));
        let mut out: Vec<F2BoolMono> = Vec::with_capacity(monos.len());
        for m in monos {
            if out.last() == Some(&m) {
                out.pop(); // 1 + 1 = 0
            } else {
                out.push(m);
            }
        }
        F2BoolPoly { terms: out, n_vars }
    }

    /// Specialise variable `var` to `value`: `v := 0` deletes every term
    /// holding `v`, `v := 1` folds `m` into `m ∖ v` (with cancellation).
    ///
    /// Equal to rebuilding through [`F2BoolPoly::from_monos`], without its
    /// sort.  Deleting terms keeps a sorted list sorted.  Folding lowers
    /// the degree of every term holding `v` by one and clears the same bit
    /// in each, so those terms keep their relative order, and the result
    /// is a linear merge of two sorted lists.  A `terms` not in canonical
    /// order (the field is public) takes the rebuilding path instead.
    pub fn substitute(&self, var: u32, value: bool) -> Self {
        self.substitute_dispatch(var, value, true)
    }

    /// Is `terms` in canonical order — strictly decreasing under
    /// [`cmp_mono`], hence also free of repeats?
    pub fn is_canonical(&self) -> bool {
        self.terms
            .windows(2)
            .all(|w| cmp_mono(w[0], w[1]) == Ordering::Greater)
    }

    /// [`F2BoolPoly::substitute`] for a polynomial already known to be
    /// canonical (see [`F2BoolPoly::is_canonical`]): the same result
    /// without re-checking the order.  `substitute` returns canonical
    /// polynomials, so a caller that checked its inputs once can use this
    /// for everything derived from them.
    pub(crate) fn substitute_canonical(&self, var: u32, value: bool) -> Self {
        debug_assert!(self.is_canonical(), "substitute_canonical on {self:?}");
        self.substitute_dispatch(var, value, false)
    }

    fn substitute_dispatch(&self, var: u32, value: bool, check: bool) -> Self {
        // The keys below are popcounts, and the baseline x86-64 target has
        // no `popcnt` instruction, so `count_ones` becomes a dozen-instruction
        // bit trick.  Where the CPU has it, run the same body compiled with
        // the instruction; the result is identical either way.
        #[cfg(target_arch = "x86_64")]
        {
            if std::arch::is_x86_feature_detected!("popcnt") {
                // SAFETY: the feature was just detected on this CPU.
                return unsafe { self.substitute_popcnt(var, value, check) };
            }
        }
        self.substitute_body(var, value, check)
    }

    #[cfg(target_arch = "x86_64")]
    #[target_feature(enable = "popcnt")]
    unsafe fn substitute_popcnt(&self, var: u32, value: bool, check: bool) -> Self {
        self.substitute_body(var, value, check)
    }

    #[inline(always)]
    fn substitute_body(&self, var: u32, value: bool, check: bool) -> Self {
        let bit = 1u64 << var;
        let terms = &self.terms;
        let n = terms.len();
        // Strictly decreasing `mono_key`s is canonical order; anything
        // else (the field is public) is rebuilt through `from_monos`.
        if check {
            let mut previous = u128::MAX;
            for t in terms {
                let key = mono_key(*t);
                if key >= previous {
                    let monos = terms
                        .iter()
                        .filter(|t| value || t.mask & bit == 0)
                        .map(|t| F2BoolMono::from_mask(t.mask & !bit))
                        .collect();
                    return Self::from_monos(monos, self.n_vars);
                }
                previous = key;
            }
        }
        let mut out: Vec<F2BoolMono> = Vec::with_capacity(n);
        if !value {
            out.extend(terms.iter().filter(|t| t.mask & bit == 0).copied());
            return F2BoolPoly {
                terms: out,
                n_vars: self.n_vars,
            };
        }
        // Two cursors over the same list, the kept terms and the folded
        // ones (`m ∖ v`), each already in order; merge them, cancelling
        // equal pairs.  Each cursor keys its current term once.
        let next_kept = |mut k: usize| {
            while k < n && terms[k].mask & bit != 0 {
                k += 1;
            }
            k
        };
        let next_folded = |mut k: usize| {
            while k < n && terms[k].mask & bit == 0 {
                k += 1;
            }
            k
        };
        let folded_at = |k: usize| F2BoolMono::from_mask(terms[k].mask & !bit);
        let (mut i, mut j) = (next_kept(0), next_folded(0));
        let mut ki = if i < n { mono_key(terms[i]) } else { 0 };
        let mut kj = if j < n { mono_key(folded_at(j)) } else { 0 };
        while i < n && j < n {
            match ki.cmp(&kj) {
                Ordering::Greater => {
                    out.push(terms[i]);
                    i = next_kept(i + 1);
                    if i < n {
                        ki = mono_key(terms[i]);
                    }
                }
                Ordering::Less => {
                    out.push(folded_at(j));
                    j = next_folded(j + 1);
                    if j < n {
                        kj = mono_key(folded_at(j));
                    }
                }
                Ordering::Equal => {
                    i = next_kept(i + 1);
                    j = next_folded(j + 1);
                    if i < n {
                        ki = mono_key(terms[i]);
                    }
                    if j < n {
                        kj = mono_key(folded_at(j));
                    }
                }
            }
        }
        while i < n {
            out.push(terms[i]);
            i = next_kept(i + 1);
        }
        while j < n {
            out.push(folded_at(j));
            j = next_folded(j + 1);
        }
        F2BoolPoly {
            terms: out,
            n_vars: self.n_vars,
        }
    }

    /// `p + q` = XOR of monomial sets.  Merge two sorted lists.
    pub fn add(&self, other: &Self) -> Self {
        debug_assert_eq!(self.n_vars, other.n_vars);
        let mut i = 0;
        let mut j = 0;
        let mut out: Vec<F2BoolMono> = Vec::with_capacity(self.terms.len() + other.terms.len());
        while i < self.terms.len() && j < other.terms.len() {
            match cmp_mono(self.terms[i], other.terms[j]) {
                Ordering::Greater => {
                    out.push(self.terms[i]);
                    i += 1;
                }
                Ordering::Less => {
                    out.push(other.terms[j]);
                    j += 1;
                }
                Ordering::Equal => {
                    // Cancel.
                    i += 1;
                    j += 1;
                }
            }
        }
        out.extend(self.terms[i..].iter().copied());
        out.extend(other.terms[j..].iter().copied());
        F2BoolPoly {
            terms: out,
            n_vars: self.n_vars,
        }
    }

    /// Multiply by a monomial `m`.  In the boolean ring `(a)(m) =`
    /// the term-wise union of masks; duplicate results cancel.
    pub fn mul_mono(&self, m: F2BoolMono) -> Self {
        if self.is_zero() {
            return Self::zero(self.n_vars);
        }
        let mut monos: Vec<F2BoolMono> = self.terms.iter().map(|t| t.mul(m)).collect();
        // After mul, sort order may change AND duplicates may appear
        // (because two distinct monos can collide on union with m).
        // Use `from_monos` to renormalise.
        monos.sort_unstable_by_key(|m| std::cmp::Reverse(mono_key(*m)));
        let mut out: Vec<F2BoolMono> = Vec::with_capacity(monos.len());
        for mn in monos {
            if out.last() == Some(&mn) {
                out.pop();
            } else {
                out.push(mn);
            }
        }
        F2BoolPoly {
            terms: out,
            n_vars: self.n_vars,
        }
    }

    /// Evaluate at a binary point: `v[k] = (point >> k) & 1`.
    pub fn eval(&self, point: u64) -> u32 {
        let mut sum = 0u32;
        for t in &self.terms {
            if (point & t.mask) == t.mask {
                sum ^= 1;
            }
        }
        sum
    }
}

// ── S-polynomial and reduction ─────────────────────────────────────

/// `spoly(p, q) = (lcm/lt(p)) p + (lcm/lt(q)) q`.
pub fn spoly(p: &F2BoolPoly, q: &F2BoolPoly) -> F2BoolPoly {
    let lp = p.lt().expect("spoly on zero poly");
    let lq = q.lt().expect("spoly on zero poly");
    let lcm = lp.lcm(lq);
    let p_mult = lcm.div(lp);
    let q_mult = lcm.div(lq);
    p.mul_mono(p_mult).add(&q.mul_mono(q_mult))
}

/// **Full multivariate division**: reduce *any* term (head or tail) of
/// `r` modulo `basis` until no term is divisible by any basis leading
/// monomial.  Returns the canonical remainder.
///
/// This is the full reduction needed for canonical-form / reduced-GB
/// computations.  S-polynomial reductions in Buchberger work fine with
/// either head-only or full reduction; we use full throughout for
/// uniform semantics.
pub fn reduce(r: &F2BoolPoly, basis: &[F2BoolPoly]) -> F2BoolPoly {
    let mut acc = r.clone();
    'outer: loop {
        // Scan terms in descending-monomial order and try to reduce
        // the first reducible one.
        for term_idx in 0..acc.terms.len() {
            let term = acc.terms[term_idx];
            for b in basis {
                let blt = match b.lt() {
                    Some(l) => l,
                    None => continue,
                };
                if blt.divides(term) {
                    let m = term.div(blt);
                    acc = acc.add(&b.mul_mono(m));
                    continue 'outer;
                }
            }
        }
        return acc;
    }
}

/// Decide, with no pruning criterion at all, whether `basis` is a
/// Gröbner basis of the ideal it generates in `F_2[v]/(v_i² + v_i)`.
///
/// Buchberger's criterion in the boolean ring has two parts, and the
/// second is the one this representation makes easy to forget.  Every
/// S-polynomial of two elements must reduce to zero, **and** for every
/// element `g` and every variable `v_k` in its leading monomial the
/// boolean product `v_k·g` must reduce to zero.  That product is the
/// S-polynomial of `g` with the field equation `v_k² + v_k`: the field
/// equations vanish in this representation, their S-polynomials do not.
/// `{v_0 v_1 + v_2}` passes the first part vacuously and fails the second.
///
/// Deliberately naive — every pair is reduced — so that it shares none of
/// [`groebner_basis_f2`]'s pruning and can check it independently.
pub fn is_boolean_groebner_basis(basis: &[F2BoolPoly]) -> bool {
    let basis: Vec<F2BoolPoly> = basis.iter().filter(|p| !p.is_zero()).cloned().collect();
    for (i, g) in basis.iter().enumerate() {
        let lm = g.lt().expect("non-zero");
        for k in 0..64u32 {
            if lm.mask >> k & 1 == 1 && !reduce(&g.mul_mono(F2BoolMono::var(k)), &basis).is_zero() {
                return false;
            }
        }
        for h in &basis[i + 1..] {
            if !reduce(&spoly(g, h), &basis).is_zero() {
                return false;
            }
        }
    }
    true
}

// ── Buchberger with the coprime and chain criteria ─────────────────

/// **Compute a Gröbner basis** of the ideal generated by `initial` in
/// `F_2[v_0, …, v_{n-1}] / (v_i² − v_i)` using Buchberger's algorithm
/// with Buchberger's two pair-pruning criteria: coprime leading
/// monomials, and the chain criterion.
///
/// The boolean-ring quotient (i.e. `v_i² = v_i`) is baked into the
/// representation, so the field equations `v_k² + v_k` are not stored:
/// they are zero in this normal form.  Their **S-polynomials are not**.
/// For an element `g` and a variable `v_k` in its leading monomial, the
/// S-polynomial of `g` with `v_k² + v_k` is the boolean product `v_k·g`,
/// and a basis is a boolean Gröbner basis only if every such product
/// reduces to zero.  These *field pairs* are processed after the S-pairs;
/// without them `{v0 v1 + v2}` came back unchanged, a generating set with
/// the right variety and six standard monomials against four points.
/// [`is_boolean_groebner_basis`] checks the result independently.
///
/// Returns a reduced Gröbner basis (no leading-term redundancy, each
/// non-leading term irreducible modulo the others).
pub fn groebner_basis_f2(initial: Vec<F2BoolPoly>, n_vars: usize) -> Vec<F2BoolPoly> {
    groebner_basis_f2_stats(initial, n_vars).0
}

/// What one Gröbner run cost.
///
/// The degree fields are the quantity Petit–Quisquater's Table 2 calls
/// the *maximal degree reached*, which is the interesting one because
/// it comes out **below** the first-fall-degree bound: the bound is
/// derived from a generic system and these are not generic.  The
/// operation counts are the metric `AGENTS.md` §6 asks for; `wall_ns`
/// is the practicality note beside them, never the headline.
#[derive(Clone, Copy, Debug, Default, serde::Serialize)]
pub struct GbStats {
    /// Highest lcm degree of a pair actually processed.  Buchberger
    /// reduces pairs that contribute nothing, so this runs above the
    /// degree the computation needed.
    pub max_pair_degree: u32,
    /// Highest lcm degree of a pair whose reduction produced a **new
    /// basis element**.  This is the *solving degree*: the highest
    /// degree at which the computation actually learned something, and
    /// the right analogue of the top Macaulay-matrix degree an F4 run
    /// reports.  It is the column to compare against a degree bound;
    /// `max_pair_degree` is a property of the pair strategy.
    pub solving_degree: u32,
    /// Highest degree of any monomial in any intermediate polynomial,
    /// which can exceed `max_pair_degree` during a reduction.
    pub max_poly_degree: u32,
    pub pairs_considered: u64,
    /// Pairs the coprime-leading-monomial criterion dropped unreduced.
    pub pairs_coprime_skipped: u64,
    /// Pairs the chain criterion dropped unreduced.
    pub pairs_chain_skipped: u64,
    pub spolys: u64,
    pub new_generators: u64,
    /// Reduction steps, one `acc ← acc + m·b` each.
    pub reduction_steps: u64,
    /// Monomials read or written by an addition or a monomial multiply.
    /// This is the engine's operation count.
    pub mono_ops: u64,
    /// Largest number of monomials the basis held at once; at eight
    /// bytes a monomial that is the engine's own peak footprint, which
    /// is what this reports in place of an operating-system RSS sample.
    pub peak_basis_monomials: u64,
    pub basis_len: u64,
    pub wall_ns: u64,
    /// The budget ran out with pairs still queued, so the basis
    /// returned is a truncation and every degree here is a lower
    /// bound.  A row carrying this is a statement about the engine,
    /// not about the system.
    pub timed_out: bool,
    /// Pairs still queued when the budget ran out, field pairs included.
    pub pairs_left: u64,
    /// Field-equation pairs processed: for an element `g` and a variable
    /// `v_k` in its leading monomial, the S-polynomial of `g` with
    /// `v_k² + v_k`, which here is the boolean product `v_k·g`.  They run
    /// after the S-pair queue drains, so a run that closed without them
    /// has an S-pair trajectory, and every field above this one save
    /// `mono_ops`, `reduction_steps` and `wall_ns`, identical to the
    /// engine before they were added.
    pub field_pairs: u64,
    /// Field pairs the chain criterion dropped unreduced; see the loop.
    pub field_pairs_chain_skipped: u64,
    /// New basis elements a field pair produced: the ones an engine that
    /// paired basis elements only with each other would have missed.
    /// Also counted in `new_generators`.
    pub field_generators: u64,
    /// The part of `mono_ops` spent on field pairs, so that
    /// `mono_ops - field_pair_ops` is the count the engine reported before
    /// it closed under the field equations.
    pub field_pair_ops: u64,
}

impl GbStats {
    /// The peak footprint in bytes: one `u64` mask per monomial held.
    pub fn peak_bytes(&self) -> u64 {
        self.peak_basis_monomials * 8
    }
}

fn add_counted(a: &F2BoolPoly, b: &F2BoolPoly, st: &mut GbStats) -> F2BoolPoly {
    st.mono_ops += (a.terms.len() + b.terms.len()) as u64;
    a.add(b)
}

fn mul_mono_counted(a: &F2BoolPoly, m: F2BoolMono, st: &mut GbStats) -> F2BoolPoly {
    st.mono_ops += a.terms.len() as u64;
    a.mul_mono(m)
}

fn note_degree(p: &F2BoolPoly, st: &mut GbStats) {
    if let Some(d) = p.terms.iter().map(|t| t.degree()).max() {
        st.max_poly_degree = st.max_poly_degree.max(d);
    }
}

/// [`reduce`], counting the steps and the monomials they touch.
fn reduce_counted(r: &F2BoolPoly, basis: &[F2BoolPoly], st: &mut GbStats) -> F2BoolPoly {
    let mut acc = r.clone();
    'outer: loop {
        note_degree(&acc, st);
        for term_idx in 0..acc.terms.len() {
            let term = acc.terms[term_idx];
            for b in basis {
                let Some(blt) = b.lt() else { continue };
                if blt.divides(term) {
                    let m = term.div(blt);
                    let scaled = mul_mono_counted(b, m, st);
                    acc = add_counted(&acc, &scaled, st);
                    st.reduction_steps += 1;
                    continue 'outer;
                }
            }
        }
        return acc;
    }
}

/// Queue `g`'s field pairs: one per variable of its leading monomial.
/// A variable outside it gives coprime leading monomials, and Buchberger's
/// first criterion already says that S-polynomial reduces to zero.
/// Returns the variables queued, as a mask.
fn queue_field_pairs(i: usize, g: &F2BoolPoly, field: &mut Vec<(usize, u32, u32)>) -> u64 {
    let Some(lm) = g.lt() else { return 0 };
    let degree = lm.degree() + 1;
    for k in 0..64u32 {
        if lm.mask >> k & 1 == 1 {
            field.push((i, k, degree));
        }
    }
    lm.mask
}

fn basis_monomials(basis: &[F2BoolPoly]) -> u64 {
    basis.iter().map(|p| p.terms.len() as u64).sum()
}

/// The S-pair queue of [`groebner_basis_f2_within`].
///
/// The queue is a `Vec` popped by "first entry of smallest degree" and
/// `swap_remove`, and that order decides which pairs the chain criterion
/// later sees as treated, so it is part of the engine's trajectory and
/// its counts.  This keeps the `Vec` exactly as it was and indexes it:
/// per degree, the ordered set of positions holding that degree, so the
/// pop finds the same entry as the linear `min_by_key` scan did; and the
/// set of queued pairs, so the chain criterion's "is `(a, b)` still
/// queued?" is a lookup instead of a scan of the whole queue.
struct PairQueue {
    pairs: Vec<(usize, usize, u32)>,
    by_degree: Vec<std::collections::BTreeSet<usize>>,
    queued: crate::cryptanalysis::fx_hash::FxSet<(usize, usize)>,
}

impl PairQueue {
    fn new() -> Self {
        PairQueue {
            pairs: Vec::new(),
            by_degree: Vec::new(),
            queued: Default::default(),
        }
    }

    fn len(&self) -> usize {
        self.pairs.len()
    }

    fn is_empty(&self) -> bool {
        self.pairs.is_empty()
    }

    /// Queue `(i, j)` with `i < j`.
    fn push(&mut self, i: usize, j: usize, degree: u32) {
        let d = degree as usize;
        if self.by_degree.len() <= d {
            self.by_degree.resize_with(d + 1, Default::default);
        }
        self.by_degree[d].insert(self.pairs.len());
        self.queued.insert((i, j));
        self.pairs.push((i, j, degree));
    }

    /// The first entry of smallest degree, removed by `swap_remove`.
    fn pop_min(&mut self) -> (usize, usize, u32) {
        let set = self
            .by_degree
            .iter_mut()
            .find(|set| !set.is_empty())
            .expect("pop from an empty pair queue");
        let idx = set.pop_first().unwrap();
        let last = self.pairs.len() - 1;
        if idx != last {
            // the last entry moves into the hole
            let moved = self.pairs[last].2 as usize;
            self.by_degree[moved].remove(&last);
            self.by_degree[moved].insert(idx);
        }
        let p = self.pairs.swap_remove(idx);
        self.queued.remove(&(p.0, p.1));
        p
    }

    /// Is the pair `{a, b}` still queued?
    fn contains(&self, a: usize, b: usize) -> bool {
        let (a, b) = if a < b { (a, b) } else { (b, a) };
        self.queued.contains(&(a, b))
    }
}

/// [`groebner_basis_f2`], with the cost of the run beside the basis.
pub fn groebner_basis_f2_stats(
    initial: Vec<F2BoolPoly>,
    n_vars: usize,
) -> (Vec<F2BoolPoly>, GbStats) {
    groebner_basis_f2_within(initial, n_vars, None)
}

/// [`groebner_basis_f2_stats`] with a wall-clock budget.
///
/// A boolean Gröbner basis can take longer than any experiment is
/// willing to wait — twelve variables at three summands ran for five
/// hours here without finishing.  With a budget the run stops and says
/// so, which lets a table carry an honest "did not finish" row instead
/// of silently omitting the cell.  `timed_out` marks such a result and
/// its basis is a truncation, not a Gröbner basis.
pub fn groebner_basis_f2_within(
    initial: Vec<F2BoolPoly>,
    n_vars: usize,
    budget: Option<std::time::Duration>,
) -> (Vec<F2BoolPoly>, GbStats) {
    let started = std::time::Instant::now();
    let deadline = budget.map(|b| started + b);
    let mut st = GbStats::default();
    let mut basis: Vec<F2BoolPoly> = initial.into_iter().filter(|p| !p.is_zero()).collect();
    for p in &basis {
        if let Some(d) = p.terms.iter().map(|t| t.degree()).max() {
            st.max_poly_degree = st.max_poly_degree.max(d);
        }
    }
    st.peak_basis_monomials = basis_monomials(&basis);
    // Pair queue with **normal selection strategy**: process the pair
    // whose LCM has the smallest total degree first.  This is the
    // Bayer–Stillman recommendation and prevents intermediate-polynomial
    // degree blowup that LIFO ordering causes — the classic source of
    // 10–100× speedups on dense boolean systems like Weil-descended PQ.
    let mut pairs = PairQueue::new(); // (i, j, lcm_degree)
    for i in 0..basis.len() {
        for j in (i + 1)..basis.len() {
            let lcm_deg = basis[i].lt().unwrap().lcm(basis[j].lt().unwrap()).degree();
            pairs.push(i, j, lcm_deg);
        }
    }
    // Field pairs, `(element, variable, degree)`: the degree is that of
    // `lcm(LM(g), v_k²)`, the nominal degree the semi-regular bound counts
    // the field equations at.  Drained only when the S-pair queue is empty.
    let mut field: Vec<(usize, u32, u32)> = Vec::new();
    // `pending[i]` has bit `k` set while `(i, v_k)` is still queued, so the
    // chain criterion below can ask that in constant time.
    let mut pending: Vec<u64> = Vec::new();
    for (i, p) in basis.iter().enumerate() {
        pending.push(queue_field_pairs(i, p, &mut field));
    }

    loop {
        if deadline.is_some_and(|d| std::time::Instant::now() >= d) {
            st.timed_out = true;
            st.pairs_left = (pairs.len() + field.len()) as u64;
            break;
        }
        if pairs.is_empty() {
            let Some(min_idx) = field
                .iter()
                .enumerate()
                .min_by_key(|(_, f)| f.2)
                .map(|(idx, _)| idx)
            else {
                break;
            };
            let (i, k, degree) = field.swap_remove(min_idx);
            pending[i] &= !(1u64 << k);
            // The chain criterion with the field equation as the third
            // element.  `lcm(LM(g_i), v_k²) = LM(g_i)·v_k`, and a multilinear
            // `LM(g_j)` divides that exactly when it divides `LM(g_i)`.  The
            // pair can be dropped when some such `g_j` has had both of its
            // pairs treated: `(i, j)` has, because this queue only drains
            // with the S-pair queue empty, and `(j, v_k)` has when it has
            // left the queue or never entered it, `v_k` being outside
            // `LM(g_j)` and the pair coprime.  Field pairs leave
            // lowest-degree first, so a divisor's go before its multiples'.
            // Without this the redundant elements that interreduction drops
            // at the end carry most of the field pairs: 60 to 2 100 per
            // target on the descent systems, against a final basis of 4 to 9.
            let lm_i = basis[i].lt().unwrap().mask;
            if (0..basis.len()).any(|j| {
                j != i
                    && basis[j].lt().is_some_and(|l| l.mask & !lm_i == 0)
                    && pending[j] >> k & 1 == 0
            }) {
                st.field_pairs_chain_skipped += 1;
                continue;
            }
            st.field_pairs += 1;
            let before = st.mono_ops;
            let product = mul_mono_counted(&basis[i], F2BoolMono::var(k), &mut st);
            // `v_k·g = g` when every term of `g` holds `v_k`: nothing to reduce.
            let r = if product == basis[i] {
                F2BoolPoly::zero(n_vars)
            } else {
                note_degree(&product, &mut st);
                reduce_counted(&product, &basis, &mut st)
            };
            if !r.is_zero() {
                st.new_generators += 1;
                st.field_generators += 1;
                st.solving_degree = st.solving_degree.max(degree);
                let new_idx = basis.len();
                let r_lt = r.lt().unwrap();
                for j in 0..new_idx {
                    let lcm_deg = basis[j].lt().unwrap().lcm(r_lt).degree();
                    pairs.push(j, new_idx, lcm_deg);
                }
                pending.push(queue_field_pairs(new_idx, &r, &mut field));
                basis.push(r);
                st.peak_basis_monomials = st.peak_basis_monomials.max(basis_monomials(&basis));
            }
            st.field_pair_ops += st.mono_ops - before;
            continue;
        }
        // Pop the pair with the SMALLEST lcm degree.
        let (i, j, lcm_deg) = pairs.pop_min();
        st.pairs_considered += 1;

        // Criterion 1: coprime leading monomials → S-poly reduces to 0.
        let li = basis[i].lt().unwrap();
        let lj = basis[j].lt().unwrap();
        if li.gcd(lj) == F2BoolMono::one() {
            st.pairs_coprime_skipped += 1;
            continue;
        }
        // Criterion 2, the **chain criterion**: if some other basis
        // element's leading monomial divides `lcm(li, lj)` and both of
        // its pairs with `i` and with `j` have already left the queue,
        // then `S(i, j)` is a combination of S-polynomials already
        // reduced and cannot contribute.  Skipping it is exact, not an
        // approximation — the basis returned is the same one.
        let lcm_ij = li.lcm(lj);
        let queued = |a: usize, b: usize| pairs.contains(a, b);
        if (0..basis.len()).any(|k| {
            k != i
                && k != j
                && basis[k].lt().is_some_and(|l| l.divides(lcm_ij))
                && !queued(i, k)
                && !queued(j, k)
        }) {
            st.pairs_chain_skipped += 1;
            continue;
        }
        st.max_pair_degree = st.max_pair_degree.max(lcm_deg);
        st.spolys += 1;
        let s = spoly(&basis[i], &basis[j]);
        st.mono_ops += (basis[i].terms.len() + basis[j].terms.len()) as u64 * 2;
        note_degree(&s, &mut st);
        let r = reduce_counted(&s, &basis, &mut st);
        if !r.is_zero() {
            st.new_generators += 1;
            st.solving_degree = st.solving_degree.max(lcm_deg);
            let new_idx = basis.len();
            // Add new pairs (k, new_idx) with their LCM degrees.
            let r_lt = r.lt().unwrap();
            for k in 0..new_idx {
                let lcm_deg = basis[k].lt().unwrap().lcm(r_lt).degree();
                pairs.push(k, new_idx, lcm_deg);
            }
            pending.push(queue_field_pairs(new_idx, &r, &mut field));
            basis.push(r);
            st.peak_basis_monomials = st.peak_basis_monomials.max(basis_monomials(&basis));
        }
    }

    // Inter-reduce to a reduced GB.
    let out = interreduce_counted(basis, n_vars, &mut st);
    st.basis_len = out.len() as u64;
    st.wall_ns = started.elapsed().as_nanos() as u64;
    (out, st)
}

/// Drop redundant leading terms, then reduce each remaining polynomial
/// against the others.  Returns a (reduced-shape) Gröbner basis whose
/// leading monomials are pairwise-incomparable.
fn interreduce_counted(
    mut basis: Vec<F2BoolPoly>,
    n_vars: usize,
    st: &mut GbStats,
) -> Vec<F2BoolPoly> {
    // Drop any polynomial whose LT is divisible by some *other*'s LT.
    // For *equal* LTs we drop the earlier index (so each LT-equivalence
    // class contributes exactly one survivor).
    let mut keep = vec![true; basis.len()];
    for (i, p) in basis.iter().enumerate() {
        if p.is_zero() {
            keep[i] = false;
        }
    }
    for i in 0..basis.len() {
        if !keep[i] {
            continue;
        }
        let lti = basis[i].lt().unwrap();
        for j in (i + 1)..basis.len() {
            if !keep[j] {
                continue;
            }
            let ltj = basis[j].lt().unwrap();
            if ltj.divides(lti) {
                // Includes the equal-LT case: drop i (the earlier).
                keep[i] = false;
                break;
            } else if lti.divides(ltj) {
                keep[j] = false;
            }
        }
    }
    let pruned: Vec<F2BoolPoly> = basis
        .drain(..)
        .zip(keep)
        .filter_map(|(p, k)| if k { Some(p) } else { None })
        .collect();

    // Tail-reduce: for each polynomial p, reduce p against all *other*
    // pruned polynomials.  Because pruned-set LTs are pairwise-
    // incomparable, the LT of p won't get touched (no other LT divides
    // it); the tail can still be reduced by smaller LTs.
    let mut final_basis: Vec<F2BoolPoly> = Vec::with_capacity(pruned.len());
    for i in 0..pruned.len() {
        let others: Vec<F2BoolPoly> = pruned
            .iter()
            .enumerate()
            .filter(|(j, _)| *j != i)
            .map(|(_, q)| q.clone())
            .collect();
        let r = reduce_counted(&pruned[i], &others, st);
        if !r.is_zero() {
            final_basis.push(r);
        }
    }
    final_basis.sort_by(|a, b| cmp_mono(b.lt().unwrap(), a.lt().unwrap()));
    let _ = n_vars; // present for API symmetry; representation already enforces v_i² = v_i
    final_basis
}

// ── Solution extraction ────────────────────────────────────────────

/// **Find all `{0,1}^n` solutions** of the system defined by `gb`
/// (typically a reduced Gröbner basis, but any generating set works).
/// Brute-force enumeration; suitable for `n ≤ ~24`.
///
/// Returns a `Vec` of bitmasks `v ∈ [0, 2^n)`; `(v >> k) & 1` is the
/// value of `v_k` in the solution.
pub fn solve_system_f2(gb: &[F2BoolPoly], n_vars: usize) -> Vec<u64> {
    assert!(n_vars <= 24, "brute-force solve capped at n_vars ≤ 24");
    let total = 1u64 << n_vars;
    let mut sols = Vec::new();
    for v in 0u64..total {
        if gb.iter().all(|p| p.eval(v) == 0) {
            sols.push(v);
        }
    }
    sols
}

/// Helper: also collect solutions of the system as `HashSet<u64>` for
/// fast membership tests.
pub fn solution_set(gb: &[F2BoolPoly], n_vars: usize) -> HashSet<u64> {
    solve_system_f2(gb, n_vars).into_iter().collect()
}

// ── Tests ──────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn substitute_matches_rebuilding_through_from_monos() {
        let mut x = 0xdead_beef_0bad_f00du64;
        let mut next = move || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            x
        };
        for trial in 0..2_000 {
            let n = 1 + (trial % 12);
            let terms: Vec<F2BoolMono> = (0..(next() % 40))
                .map(|_| F2BoolMono::from_mask(next() & ((1u64 << n) - 1)))
                .collect();
            let canonical = F2BoolPoly::from_monos(terms.clone(), n);
            // the field is public: an unsorted, duplicated list too
            let raw = F2BoolPoly { terms, n_vars: n };
            for p in [&canonical, &raw] {
                for var in 0..n as u32 {
                    for value in [false, true] {
                        let bit = 1u64 << var;
                        let expected = F2BoolPoly::from_monos(
                            p.terms
                                .iter()
                                .filter(|t| value || t.mask & bit == 0)
                                .map(|t| F2BoolMono::from_mask(t.mask & !bit))
                                .collect(),
                            n,
                        );
                        assert_eq!(p.substitute(var, value), expected, "{p:?} x{var}={value}");
                        if p.is_canonical() {
                            assert_eq!(p.substitute_canonical(var, value), expected);
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn pair_queue_pops_what_the_linear_scan_popped() {
        // the old queue: a Vec, `min_by_key` (first minimum) and
        // `swap_remove`, membership by scanning
        let mut x = 0x0123_4567_89ab_cdefu64;
        let mut next = move || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            x
        };
        for _ in 0..50 {
            let mut old: Vec<(usize, usize, u32)> = Vec::new();
            let mut new = PairQueue::new();
            let mut n = 0usize;
            for _ in 0..400 {
                if next() % 3 != 0 || old.is_empty() {
                    // a new element pairs with every earlier one
                    n += 1;
                    for k in 0..n - 1 {
                        let d = (next() % 7) as u32;
                        old.push((k, n - 1, d));
                        new.push(k, n - 1, d);
                    }
                } else {
                    let idx = old
                        .iter()
                        .enumerate()
                        .min_by_key(|(_, p)| p.2)
                        .map(|(i, _)| i)
                        .unwrap();
                    assert_eq!(new.pop_min(), old.swap_remove(idx));
                }
                assert_eq!(new.len(), old.len());
                let (a, b) = ((next() % 12) as usize, (next() % 12) as usize);
                let scan = old.iter().any(|p| (p.0, p.1) == (a.min(b), a.max(b)));
                assert_eq!(new.contains(a, b), scan);
            }
        }
    }

    #[test]
    fn mono_key_orders_exactly_like_cmp_mono() {
        let mut x = 0x9e37_79b9_7f4a_7c15u64;
        let mut next = || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            // sparse masks, so equal degrees and shared high bits are common
            x & (x >> 3) & (x >> 5)
        };
        let mut masks: Vec<u64> = vec![0, 1, 2, 3, u64::MAX, 1 << 63, (1 << 63) | 1];
        masks.extend((0..300).map(|_| next()));
        for &a in &masks {
            for &b in &masks {
                let (a, b) = (F2BoolMono::from_mask(a), F2BoolMono::from_mask(b));
                assert_eq!(mono_key(a).cmp(&mono_key(b)), cmp_mono(a, b), "{a:?} {b:?}");
            }
        }
    }

    /// Monomial constructors and basic operators.
    #[test]
    fn mono_basics() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        let v0v1 = v0.mul(v1);
        assert_eq!(v0v1.degree(), 2);
        assert!(v0.divides(v0v1));
        assert!(v1.divides(v0v1));
        assert_eq!(v0v1.div(v0), v1);
        assert_eq!(v0v1.gcd(v0), v0);
        assert_eq!(v0v1.lcm(F2BoolMono::var(2)).degree(), 3);
        // Idempotency: v_0 * v_0 = v_0.
        assert_eq!(v0.mul(v0), v0);
    }

    /// DegRevLex respects total degree first.
    #[test]
    fn order_respects_degree() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        let v0v1 = v0.mul(v1);
        assert_eq!(cmp_mono(v0v1, v0), Ordering::Greater);
        assert_eq!(cmp_mono(F2BoolMono::one(), v0), Ordering::Less);
    }

    /// DegRevLex ties: between `v_0` and `v_1` (same degree 1), `v_0 > v_1`.
    #[test]
    fn order_tie_break_high_index_wins_for_smaller() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        // The DegRevLex convention: lower-indexed variables sort larger.
        assert_eq!(cmp_mono(v0, v1), Ordering::Greater);
    }

    /// Polynomial addition cancels duplicates.
    #[test]
    fn poly_add_cancels() {
        let v0 = F2BoolMono::var(0);
        let v1 = F2BoolMono::var(1);
        let p = F2BoolPoly::from_monos(vec![v0, v1], 2);
        let q = F2BoolPoly::from_monos(vec![v1], 2);
        let sum = p.add(&q);
        assert_eq!(sum.terms, vec![v0]);
    }

    /// `(v_0 + 1) * v_0 = v_0² + v_0 = v_0 + v_0 = 0` in the boolean ring.
    #[test]
    fn boolean_idempotent_cancels_in_mul() {
        let v0 = F2BoolMono::var(0);
        let p = F2BoolPoly::from_monos(vec![v0, F2BoolMono::one()], 2);
        let r = p.mul_mono(v0);
        assert!(r.is_zero(), "expected 0, got {:?}", r);
    }

    /// S-polynomial of `v_0 v_1` and `v_0 + v_2`:
    ///   lcm = v_0 v_1; multipliers (1, v_1); result =
    ///   v_0 v_1 + (v_0 + v_2) · v_1 = v_0 v_1 + v_0 v_1 + v_1 v_2 = v_1 v_2.
    #[test]
    fn spoly_textbook_example() {
        let p = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(1))], 3);
        let q = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::var(2)], 3);
        let s = spoly(&p, &q);
        let expected = F2BoolPoly::from_monos(vec![F2BoolMono::var(1).mul(F2BoolMono::var(2))], 3);
        assert_eq!(s, expected);
    }

    /// Reduction: `(v_0 v_1)` against basis `[v_0 + v_2]` should give
    /// `v_1 v_2`.
    #[test]
    fn reduce_textbook_example() {
        let p = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(1))], 3);
        let b = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::var(2)], 3);
        let r = reduce(&p, &[b]);
        let expected = F2BoolPoly::from_monos(vec![F2BoolMono::var(1).mul(F2BoolMono::var(2))], 3);
        assert_eq!(r, expected);
    }

    /// **GB of a system with a unique solution.**  System:
    ///   v_0 + 1 = 0   ⇒  v_0 = 1
    ///   v_1 + v_0 = 0 ⇒  v_1 = v_0 = 1
    /// Only `(1, 1)` satisfies; GB should encode this.
    #[test]
    fn gb_unique_solution_2vars() {
        let f1 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], 2);
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(1), F2BoolMono::var(0)], 2);
        let gb = groebner_basis_f2(vec![f1, f2], 2);
        let sols = solve_system_f2(&gb, 2);
        assert_eq!(sols, vec![0b11]); // (v_0=1, v_1=1) encoded as bits 0 and 1.
    }

    /// **GB of a 0-solution system.**  System:
    ///   v_0 = 0
    ///   v_0 + 1 = 0
    /// is inconsistent — the GB should contain `1`, and there are no
    /// solutions.
    #[test]
    fn gb_zero_solution_inconsistent() {
        let f1 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0)], 1);
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0), F2BoolMono::one()], 1);
        let gb = groebner_basis_f2(vec![f1, f2], 1);
        assert!(
            gb.iter().any(|p| p.terms == vec![F2BoolMono::one()]),
            "inconsistent system should yield GB ∋ 1"
        );
        let sols = solve_system_f2(&gb, 1);
        assert!(sols.is_empty());
    }

    /// **GB respects boolean-ring quotient: `v_0² = v_0`.**
    /// Input `[v_0² + v_0]` is `[0]` in our representation; GB is empty.
    /// To force a non-trivial test we add a separate generator.
    #[test]
    fn gb_handles_idempotency() {
        // `v_0² + v_0 + 1 = 0` in F_2 / (v_0² = v_0) becomes `1 = 0`,
        // which is contradictory.  Encode it as the constant polynomial 1.
        let inconsistent = F2BoolPoly::from_monos(vec![F2BoolMono::one()], 1);
        let gb = groebner_basis_f2(vec![inconsistent], 1);
        let sols = solve_system_f2(&gb, 1);
        assert!(sols.is_empty(), "1 = 0 has no solutions");
    }

    /// **Multi-variable solution counting.**  System `v_0 v_1 = 0` in
    /// 3 variables has solutions (v_0, v_1, v_2) with v_0 v_1 = 0:
    /// excludes only (1,1,*), so 2³ - 2 = 6 solutions.
    #[test]
    fn gb_multivariate_solution_count() {
        let f = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(1))], 3);
        let gb = groebner_basis_f2(vec![f], 3);
        let sols = solve_system_f2(&gb, 3);
        assert_eq!(sols.len(), 6, "v_0 v_1 = 0 in 3 vars has 6 solutions");
        // Spot-check: (0, 0, 0), (0, 1, 0), (1, 0, 0), etc., none with
        // both v_0 = 1 and v_1 = 1.
        for v in &sols {
            assert!((*v & 0b11) != 0b11);
        }
    }

    /// **Random consistent system regression**: build a known solution
    /// `v* = (1, 0, 1, 0)`, generate polynomials by `(v_0 v_2 + 1) = 0`
    /// (true at v*), `(v_1 + v_3) = 0` (true), `(v_0 v_3) = 0` (true);
    /// confirm v* is in the GB's solution set.
    #[test]
    fn gb_random_consistent_system_contains_known_solution() {
        // v* = bit pattern 0b0101 = (v_0=1, v_1=0, v_2=1, v_3=0).
        let v_star: u64 = 0b0101;
        let f1 = F2BoolPoly::from_monos(
            vec![
                F2BoolMono::var(0).mul(F2BoolMono::var(2)),
                F2BoolMono::one(),
            ],
            4,
        );
        let f2 = F2BoolPoly::from_monos(vec![F2BoolMono::var(1), F2BoolMono::var(3)], 4);
        let f3 = F2BoolPoly::from_monos(vec![F2BoolMono::var(0).mul(F2BoolMono::var(3))], 4);
        for f in [&f1, &f2, &f3] {
            assert_eq!(f.eval(v_star), 0, "input system unsat at v*");
        }
        let gb = groebner_basis_f2(vec![f1, f2, f3], 4);
        let sols: HashSet<u64> = solve_system_f2(&gb, 4).into_iter().collect();
        assert!(
            sols.contains(&v_star),
            "GB should accept the known solution v* (got sols = {:?})",
            sols
        );
    }

    /// Multilinear monomials no leading monomial of `gb` divides.  In the
    /// boolean ring the quotient by an ideal has dimension equal to the
    /// number of its `{0,1}` points, so a set of ideal elements is a
    /// Gröbner basis exactly when this equals the number of solutions.
    /// A zero set cannot make that distinction; this count can.
    fn standard_monomial_count(gb: &[F2BoolPoly], n: usize) -> usize {
        let lms: Vec<u64> = gb.iter().filter_map(|p| p.lt()).map(|l| l.mask).collect();
        (0u64..1 << n)
            .filter(|&m| !lms.iter().any(|&l| l & !m == 0))
            .count()
    }

    /// `v0 v1 + v2` alone is not a boolean Gröbner basis:
    /// `v0 · (v0 v1 + v2) = v0 v1 + v0 v2` reduces to `v0 v2 + v2`, whose
    /// leading monomial nothing in the input divides.  An engine that only
    /// pairs basis elements with each other has no pair to process here.
    /// The variety cannot see the difference — the input and the true
    /// basis share their four solutions — and the monomial count can.
    #[test]
    fn gb_closes_under_field_equation_pairs() {
        let v = F2BoolMono::var;
        let g = F2BoolPoly::from_monos(vec![v(0).mul(v(1)), v(2)], 3);
        assert!(
            !is_boolean_groebner_basis(std::slice::from_ref(&g)),
            "the checker must reject the input"
        );
        let gb = groebner_basis_f2(vec![g], 3);
        assert!(is_boolean_groebner_basis(&gb));
        assert_eq!(solve_system_f2(&gb, 3).len(), 4);
        assert_eq!(standard_monomial_count(&gb, 3), 4);
        // The reduced basis: v0 v1 + v2, v0 v2 + v2, v1 v2 + v2.
        let lms: HashSet<u64> = gb.iter().map(|p| p.lt().unwrap().mask).collect();
        assert_eq!(lms, [0b011, 0b101, 0b110].into_iter().collect());
    }

    /// The output is a boolean Gröbner basis on random systems, checked two
    /// independent ways — the unpruned criterion, and the standard-monomial
    /// count against a brute-force solution count — and its solutions are
    /// the input's.
    #[test]
    fn gb_is_a_boolean_groebner_basis_on_random_systems() {
        use rand::{rngs::StdRng, Rng, SeedableRng};
        let mut rng = StdRng::seed_from_u64(0xB0_01EA);
        for case in 0..400 {
            let n = rng.gen_range(2..=7usize);
            let system: Vec<F2BoolPoly> = (0..rng.gen_range(1..=4))
                .map(|_| {
                    let monos = (0..rng.gen_range(1..=5))
                        .map(|_| {
                            let mut mask = 0u64;
                            for _ in 0..rng.gen_range(0..=3) {
                                mask |= 1 << rng.gen_range(0..n);
                            }
                            F2BoolMono::from_mask(mask)
                        })
                        .collect();
                    F2BoolPoly::from_monos(monos, n)
                })
                .collect();
            let truth: HashSet<u64> = (0u64..1 << n)
                .filter(|&x| system.iter().all(|p| p.eval(x) == 0))
                .collect();
            let gb = groebner_basis_f2(system, n);
            assert!(is_boolean_groebner_basis(&gb), "case {case}: not closed");
            assert_eq!(standard_monomial_count(&gb, n), truth.len(), "case {case}");
            assert_eq!(solution_set(&gb, n), truth, "case {case}");
        }
    }
}
