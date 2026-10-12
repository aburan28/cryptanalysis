//! # Symmetrised binary Semaev `S₄`, and its Weil descent.
//!
//! Companion to [`crate::cryptanalysis::binary_semaev`] (which handles
//! `S₃`).  Where `S₃` decomposes a point into **two** factor-base
//! points, `S₄` decomposes into **three** — and `m = 3` is where index
//! calculus starts to be worth doing at all: `m = 2` buys no asymptotic
//! improvement over Pollard ρ.
//!
//! ## Why symmetrise
//!
//! `S₄(X₁, X₂, X₃, x_R)` is symmetric in `X₁, X₂, X₃`, so it can be
//! rewritten over the elementary symmetric functions
//!
//! ```text
//!     e₁ = X₁ + X₂ + X₃
//!     e₂ = X₁X₂ + X₁X₃ + X₂X₃
//!     e₃ = X₁X₂X₃
//! ```
//!
//! which collapses the monomial count by roughly `m!` — the
//! Faugère–Gaudry–Huot–Renault speed-up.  Crucially it also drops the
//! *degree*: over the `eᵢ` the descended system is quadratic, where
//! over the `Xᵢ` it would be cubic.
//!
//! The price is that the `eᵢ` are not free: they must be tied back to
//! the `Xᵢ` by a **correspondence system**, which is where the cubic
//! degree goes.  So the model has two halves, and this module builds
//! both:
//!
//! | half | variables | degree | count |
//! |---|---|---|---|
//! | correspondence `eᵢ = σᵢ(X₁,X₂,X₃)` | `x` and `e` | ≤ 3 | `6l − 3` |
//! | descended `S₄` | `e` only | ≤ 2 | `n` |
//!
//! ## Frobenius is a relocation
//!
//! [`AnfF2m::square`] does no multiplication.  In characteristic 2,
//! `(Σ c_d z^d)² = Σ c_d² z^{2d}` — no cross terms — and each `c_d` is
//! an ANF over *Boolean* variables, where `a² = a` forces `c_d² = c_d`.
//! Both facts are needed; together they make squaring pure relocation
//! of coefficients from `d` to `2d`.  Of the twelve terms of `f₃`
//! below, including `e₁⁴`, `e₂⁴`, `e₃⁴` and `e₃³`, only four need a
//! genuine multiplication.
//!
//! ## Curve support
//!
//! The symmetrised form implemented here is specialised to `b = 1`,
//! i.e. the Koblitz curve `E: y² + xy = x³ + x² + 1`, which is the
//! curve the reference corpus in
//! `research/ec-index-calculus-review/` was generated on.  `S₄` does
//! not depend on `a₂`, but it *does* depend on `b`, and the `b`-powers
//! are folded into the constants below — a general-`b` form has to be
//! re-derived from `Res_X(S₃(X₁,X₂,X), S₃(X₃,x_R,X))` and then
//! re-symmetrised.  [`weil_descend_s4`] rejects `b ≠ 1` rather than
//! silently returning the wrong system.
//!
//! ## References
//!
//! - **J.-C. Faugère, P. Gaudry, L. Huot, G. Renault**, *Using
//!   symmetries in the index calculus for elliptic curves discrete
//!   logarithm*, J. Cryptology 2014.
//! - **P. Gaudry**, *Index calculus for abelian varieties of small
//!   dimension and the elliptic curve discrete logarithm problem*,
//!   J. Symbolic Computation 2009.
//! - **I. Semaev**, *Summation polynomials and the discrete logarithm
//!   problem on elliptic curves*, 2004.

use crate::binary_ecc::{F2mElement, IrreduciblePoly};
use std::collections::BTreeSet;

// ── Sparse ANF over F₂ ──────────────────────────────────────────────

/// A polynomial over `F₂` in Boolean variables, held as its set of
/// monomials (algebraic normal form).  A monomial is a strictly
/// increasing variable-index vector; the empty vector is the constant
/// `1`.  The polynomial is the XOR-sum of its monomials.
///
/// Variables are Boolean, so `x² = x` and every monomial is squarefree.
///
/// Note that addition is *symmetric difference*: a monomial added twice
/// cancels.  That is the whole difference between this and the upstream
/// C implementation's `multiply`, which accumulates with a bitwise OR
/// and is therefore only correct on multiplicity-free products.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct AnfPoly {
    monomials: BTreeSet<Vec<u32>>,
}

impl AnfPoly {
    pub fn zero() -> Self {
        Self {
            monomials: BTreeSet::new(),
        }
    }

    /// The constant `1`.
    pub fn one() -> Self {
        let mut m = BTreeSet::new();
        m.insert(Vec::new());
        Self { monomials: m }
    }

    /// The single variable `x_v`.
    pub fn var(v: u32) -> Self {
        let mut m = BTreeSet::new();
        m.insert(vec![v]);
        Self { monomials: m }
    }

    pub fn is_zero(&self) -> bool {
        self.monomials.is_empty()
    }

    /// Number of monomials (including the constant term, if present).
    pub fn len(&self) -> usize {
        self.monomials.len()
    }

    pub fn is_empty(&self) -> bool {
        self.monomials.is_empty()
    }

    /// Highest total degree of any monomial; `0` for a constant or zero.
    pub fn degree(&self) -> usize {
        self.monomials.iter().map(|m| m.len()).max().unwrap_or(0)
    }

    /// Iterate the monomials, each a sorted variable-index slice.
    pub fn monomials(&self) -> impl Iterator<Item = &Vec<u32>> {
        self.monomials.iter()
    }

    /// Does the constant term `1` appear?
    pub fn has_constant(&self) -> bool {
        self.monomials.contains(&Vec::new())
    }

    /// XOR one monomial in (adding it twice cancels).  Removing first
    /// means only a monomial that stays is cloned.
    fn toggle(&mut self, mono: &Vec<u32>) {
        if !self.monomials.remove(mono) {
            self.monomials.insert(mono.clone());
        }
    }

    /// `self ^= other`.
    ///
    /// Two ways to form the symmetric difference, and which is cheaper
    /// depends on the sizes (`toggling_is_cheaper`).  Toggling each
    /// monomial of `other` into `self` costs one tree search apiece and
    /// leaves the rest of `self` where it is, so it is how a few
    /// monomials are added to a large sum — an accumulator gathering one
    /// product at a time, as `degree_reduction_anf` does.  One ordered
    /// merge of the two sets (`merge_xor`) visits every monomial of
    /// both and rebuilds the tree, but does no searching and no
    /// rebalancing, and wins once `other` is a sizeable fraction of
    /// `self`.  Either way a monomial of `other` that cancels is never
    /// cloned.
    pub fn xor_assign(&mut self, other: &Self) {
        if self.monomials.is_empty() {
            self.monomials = other.monomials.clone();
        } else if other.len() == 1 {
            // A single monomial, the commonest call, is toggled without
            // setting up a walk of `other`'s tree.
            if let Some(m) = other.monomials.first() {
                self.toggle(m);
            }
        } else if toggling_is_cheaper(self.len(), other.len()) {
            for m in &other.monomials {
                self.toggle(m);
            }
        } else {
            let mine = std::mem::take(&mut self.monomials);
            self.monomials = merge_xor(mine, &other.monomials);
        }
    }

    /// `self * other`, reducing `x² → x` in each product monomial.
    ///
    /// Three paths, by the number of products.  One monomial times one is
    /// the commonest call — `degree_reduction_anf` relabels a monomial by
    /// multiplying in one variable at a time — and is a single product
    /// that cannot cancel, formed without setting up a walk of either
    /// tree.  Up to `SMALL_SUM` products are toggled straight into the
    /// tree, which needs no buffer, in plain loops rather than an iterator
    /// chain whose out-of-line `next` calls would be a good part of so
    /// small a product.  More are collected and summed at once
    /// (`gathered_product`) rather than one tree operation per product.
    pub fn mul(&self, other: &Self) -> Self {
        let count = self.len() * other.len();
        if count > SMALL_SUM {
            return Self {
                monomials: gathered_product(&self.monomials, &other.monomials, count),
            };
        }
        let mut monomials = BTreeSet::new();
        if count == 1 {
            if let (Some(a), Some(b)) = (self.monomials.first(), other.monomials.first()) {
                monomials.insert(merge_squarefree(a, b));
            }
            return Self { monomials };
        }
        for a in &self.monomials {
            for b in &other.monomials {
                let m = merge_squarefree(a, b);
                // An empty tree has nothing to cancel, so the first
                // product goes straight in without a search.
                if monomials.is_empty() || !monomials.remove(&m) {
                    monomials.insert(m);
                }
            }
        }
        Self { monomials }
    }

    /// Evaluate at a Boolean assignment indexed by variable id.
    pub fn eval(&self, assignment: &[bool]) -> bool {
        let mut acc = false;
        for m in &self.monomials {
            if m.iter().all(|v| assignment[*v as usize]) {
                acc = !acc;
            }
        }
        acc
    }
}

/// Is toggling `theirs` monomials into a set of `mine` cheaper than one
/// ordered merge of the two ([`AnfPoly::xor_assign`])?
///
/// A toggle is a search, `⌊log₂ mine⌋ + 1` levels of comparisons that
/// each follow a pointer into a monomial; a merge is one sequential pass
/// over both sets and a bulk rebuild of the tree, whose cost per monomial
/// is several search levels', plus a fixed cost for the rebuild.
/// Measured on this module's monomials (x86-64, release, sets of 2 to
/// 4096), the merge overtakes the toggles once `theirs` is about half of
/// `mine` in sets of a few hundred and about a fifth in sets of a few
/// thousand, and never below about 32 monomials in all.  `theirs · depth
/// < 4 · mine` stays on the toggling side of that crossover.  That is the
/// side to err on: a misjudged toggle costs what toggling always cost,
/// where a misjudged merge rebuilds a large tree to add a few monomials.
///
/// `depth ≤ mine`, so fewer than four monomials always toggle.  Testing
/// that first changes no answer and spares the smallest sums the rest.
fn toggling_is_cheaper(mine: usize, theirs: usize) -> bool {
    let depth = (usize::BITS - mine.leading_zeros()) as usize;
    theirs < 4 || mine + theirs <= 32 || theirs.saturating_mul(depth) < mine.saturating_mul(4)
}

/// At most this many terms, a sum of monomials is toggled into a tree
/// ([`toggle_sum`]) rather than gathered, sorted and bulk-loaded
/// ([`xor_sum`]).  They fit in one leaf of the tree, so each toggle is a
/// short scan, while a gathered sum pays for its buffers however few
/// terms there are; the two cost about the same at eight terms.
const SMALL_SUM: usize = 8;

/// The XOR-sum of a few monomials, each toggled into the tree in turn —
/// removed if present, otherwise inserted as an owned monomial made by
/// `own`, and into an empty tree without a search.  For [`SMALL_SUM`]
/// terms or fewer.
fn toggle_sum<T>(
    monos: impl IntoIterator<Item = T>,
    mut own: impl FnMut(T) -> Vec<u32>,
) -> BTreeSet<Vec<u32>>
where
    T: std::borrow::Borrow<Vec<u32>>,
{
    let mut sum = BTreeSet::new();
    for m in monos {
        let mono: &Vec<u32> = m.borrow();
        if sum.is_empty() || !sum.remove(mono) {
            sum.insert(own(m));
        }
    }
    sum
}

/// The `count` products of every monomial of `a` with every monomial of
/// `b`, collected and summed at once by [`xor_sum`]: [`AnfPoly::mul`]'s
/// path for more than [`SMALL_SUM`] of them.
///
/// Kept out of line: inlined, its buffers and sort more than double the
/// machine code of `mul` around the small paths that serve most calls,
/// for a path taken once per product of more than [`SMALL_SUM`] terms.
#[inline(never)]
fn gathered_product(
    a: &BTreeSet<Vec<u32>>,
    b: &BTreeSet<Vec<u32>>,
    count: usize,
) -> BTreeSet<Vec<u32>> {
    let mut prods = Vec::with_capacity(count);
    for x in a {
        for y in b {
            prods.push(merge_squarefree(x, y));
        }
    }
    xor_sum(prods, |m| m)
}

/// The symmetric difference of two monomial sets, as one ordered merge.
///
/// `a` is consumed and its monomials move into the result; a monomial of
/// `b` is cloned only if it survives, so one that cancels is never
/// copied.  The merged sequence is sorted and duplicate-free, which is
/// the input on which `BTreeSet`'s `FromIterator` builds the tree in bulk
/// (its sort has nothing to reorder) instead of inserting and
/// rebalancing element by element.
fn merge_xor(a: BTreeSet<Vec<u32>>, b: &BTreeSet<Vec<u32>>) -> BTreeSet<Vec<u32>> {
    use std::cmp::Ordering;

    let mut out = Vec::with_capacity(a.len() + b.len());
    let mut a = a.into_iter().peekable();
    let mut b = b.iter().peekable();
    loop {
        let ord = match (a.peek(), b.peek()) {
            (Some(x), Some(y)) => x.cmp(y),
            (_, None) => {
                out.extend(a);
                break;
            }
            (None, _) => {
                out.extend(b.cloned());
                break;
            }
        };
        match ord {
            Ordering::Less => out.extend(a.next()),
            Ordering::Greater => out.extend(b.next().cloned()),
            Ordering::Equal => {
                // x ⊕ x = 0: both copies drop here, neither is cloned.
                a.next();
                b.next();
            }
        }
    }
    out.into_iter().collect()
}

/// Keep, once, each element of a sorted vector that occurs an odd number
/// of times (as judged by `same`), preserving order.  Over `F₂` a
/// monomial added `k` times contributes `k mod 2` times, and after the
/// sort its copies are adjacent, so this one pass is the XOR-sum of the
/// whole multiset.
fn retain_odd<T>(v: &mut Vec<T>, same: impl Fn(&T, &T) -> bool) {
    let len = v.len();
    let (mut write, mut read) = (0, 0);
    while read < len {
        let mut end = read + 1;
        while end < len && same(&v[end], &v[read]) {
            end += 1;
        }
        if (end - read) % 2 == 1 {
            v.swap(write, read);
            write += 1;
        }
        read = end;
    }
    v.truncate(write);
}

/// An order-preserving `u64` key for a monomial of degree ≤ 4 whose
/// variables all lie below `u16::MAX`: each variable plus one in a
/// 16-bit field, from the top, zero-padded.  Integer order on the keys
/// is then the lexicographic order of the index vectors (a proper prefix
/// is smaller, as the zero padding makes it), and distinct monomials get
/// distinct keys.  `None` for a monomial that does not fit.
fn packed_key(m: &[u32]) -> Option<u64> {
    if m.len() > 4 {
        return None;
    }
    let mut key = 0u64;
    for (k, &v) in m.iter().enumerate() {
        if v >= u32::from(u16::MAX) {
            return None;
        }
        key |= u64::from(v + 1) << (48 - 16 * k);
    }
    Some(key)
}

/// The XOR-sum of a multiset of monomials, each held as a `T` (owned, or
/// borrowed from the sets being summed): sort, cancel pairs, turn the
/// survivors into owned monomials with `own`, bulk-load them.
///
/// This is how a sum of many terms is formed without one tree operation
/// per term, and a borrowed monomial that cancels is never cloned.  When
/// every monomial has a [`packed_key`] — the Weil descent's are all at
/// most quadratic or cubic over a few dozen variables — the sort compares
/// integers instead of walking two index vectors behind two pointers per
/// comparison; equal keys are equal monomials, so which of them survives
/// cannot matter.  Otherwise it sorts the monomials themselves.  A sum of
/// [`SMALL_SUM`] terms or fewer is toggled instead ([`toggle_sum`]).
fn xor_sum<T>(monos: Vec<T>, own: impl FnMut(T) -> Vec<u32>) -> BTreeSet<Vec<u32>>
where
    T: Ord + std::borrow::Borrow<Vec<u32>>,
{
    if monos.len() <= SMALL_SUM {
        return toggle_sum(monos, own);
    }
    if monos.iter().all(|m| packed_key(m.borrow()).is_some()) {
        let mut keyed: Vec<(u64, T)> = monos
            .into_iter()
            .map(|m| (packed_key(m.borrow()).unwrap_or_default(), m))
            .collect();
        keyed.sort_unstable_by_key(|p| p.0);
        retain_odd(&mut keyed, |a, b| a.0 == b.0);
        return keyed.into_iter().map(|(_, m)| m).map(own).collect();
    }
    let mut monos = monos;
    monos.sort();
    retain_odd(&mut monos, |a, b| a == b);
    monos.into_iter().map(own).collect()
}

/// Union of two sorted variable lists, deduplicated because `x² = x`.
///
/// Forced inline, as the compiler inlined it by itself when it had one
/// caller: with several it stays out of line, and the call then adds
/// about 25 instructions to a product of one monomial by one, some 8% of
/// it (callgrind).
#[inline(always)]
fn merge_squarefree(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut out = Vec::with_capacity(a.len() + b.len());
    let (mut i, mut j) = (0, 0);
    while i < a.len() && j < b.len() {
        match a[i].cmp(&b[j]) {
            std::cmp::Ordering::Less => {
                out.push(a[i]);
                i += 1;
            }
            std::cmp::Ordering::Greater => {
                out.push(b[j]);
                j += 1;
            }
            std::cmp::Ordering::Equal => {
                out.push(a[i]); // x · x = x
                i += 1;
                j += 1;
            }
        }
    }
    out.extend_from_slice(&a[i..]);
    out.extend_from_slice(&b[j..]);
    out
}

// ── Symbolic F_{2^n} with ANF coefficients ──────────────────────────

/// An element of `F₂[vars][z]`: a polynomial in `z` whose coefficients
/// are ANF polynomials in Boolean variables.  Not reduced modulo the
/// field's irreducible until [`AnfF2m::reduce`] is called, which is
/// what lets degrees grow once and collapse once (lazy reduction).
#[derive(Clone, Debug, Default)]
pub struct AnfF2m {
    pub coeffs: Vec<AnfPoly>,
}

impl AnfF2m {
    pub fn zero(len: usize) -> Self {
        Self {
            coeffs: vec![AnfPoly::zero(); len],
        }
    }

    /// Lift a known field element to a constant symbolic element.
    pub fn from_const(c: &F2mElement, n: u32) -> Self {
        let raw = c.raw_bits();
        let mut coeffs = vec![AnfPoly::zero(); n as usize];
        for (i, slot) in coeffs.iter_mut().enumerate() {
            let set = (raw.get(i / 64).copied().unwrap_or(0) >> (i % 64)) & 1 == 1;
            if set {
                *slot = AnfPoly::one();
            }
        }
        Self { coeffs }
    }

    /// `Σ_{d < len} x_{offset + d} · z^d` — a free symbolic element
    /// whose coefficients are single fresh variables.
    pub fn from_vars(offset: u32, len: usize) -> Self {
        Self {
            coeffs: (0..len).map(|d| AnfPoly::var(offset + d as u32)).collect(),
        }
    }

    pub fn len(&self) -> usize {
        self.coeffs.len()
    }

    pub fn is_empty(&self) -> bool {
        self.coeffs.is_empty()
    }

    /// Coefficient-wise `self ⊕ other`.  Each coefficient is one ordered
    /// merge of the two monomial sets, cloning only the monomials that
    /// survive it.
    pub fn xor(&self, other: &Self) -> Self {
        let len = self.len().max(other.len());
        let coeffs = (0..len)
            .map(|i| match (self.coeffs.get(i), other.coeffs.get(i)) {
                (Some(a), Some(b)) => AnfPoly {
                    monomials: a
                        .monomials
                        .symmetric_difference(&b.monomials)
                        .cloned()
                        .collect(),
                },
                (Some(c), None) | (None, Some(c)) => c.clone(),
                (None, None) => unreachable!("i < max(len)"),
            })
            .collect();
        Self { coeffs }
    }

    /// Polynomial multiplication (convolution).  No reduction.
    ///
    /// Coefficient `k` of the product is `Σ_{i+j=k} a_i·b_j`; all the
    /// monomial products for one `k` are collected, into a buffer sized
    /// for them, and summed at once by `xor_sum`, so no intermediate
    /// `a_i·b_j` is ever built as a set.
    pub fn mul(&self, other: &Self) -> Self {
        if self.is_empty() || other.is_empty() {
            return Self::zero(0);
        }
        let coeffs = (0..self.len() + other.len() - 1)
            .map(|k| {
                let terms = k.saturating_sub(other.len() - 1)..=k.min(self.len() - 1);
                let count = terms
                    .clone()
                    .map(|i| self.coeffs[i].len() * other.coeffs[k - i].len())
                    .sum();
                let mut prods = Vec::with_capacity(count);
                for i in terms {
                    for a in &self.coeffs[i].monomials {
                        for b in &other.coeffs[k - i].monomials {
                            prods.push(merge_squarefree(a, b));
                        }
                    }
                }
                AnfPoly {
                    monomials: xor_sum(prods, |m| m),
                }
            })
            .collect();
        Self { coeffs }
    }

    /// **Squaring as relocation.**  `(Σ c_d z^d)² = Σ c_d z^{2d}`: in
    /// characteristic 2 there are no cross terms, and each `c_d` is an
    /// ANF over Boolean variables so `c_d² = c_d`.  No multiplication
    /// is performed — coefficients move from `d` to `2d` unchanged.
    pub fn square(&self) -> Self {
        if self.is_empty() {
            return Self::zero(0);
        }
        let mut out = Self::zero(2 * self.len() - 1);
        for (d, c) in self.coeffs.iter().enumerate() {
            out.coeffs[2 * d] = c.clone();
        }
        out
    }

    /// `self^k` for `k ≥ 1`, using [`AnfF2m::square`] for the powers of
    /// two and at most one real multiplication for an odd exponent.
    pub fn pow(&self, k: u32) -> Self {
        assert!(k >= 1, "pow requires a positive exponent");
        match k {
            1 => self.clone(),
            2 => self.square(),
            3 => self.square().mul(self),
            4 => self.square().square(),
            _ => {
                // General case: square-and-multiply, still paying only
                // relocations for the squarings.
                let mut result: Option<Self> = None;
                let mut base = self.clone();
                let mut e = k;
                while e > 0 {
                    if e & 1 == 1 {
                        result = Some(match result {
                            None => base.clone(),
                            Some(r) => r.mul(&base),
                        });
                    }
                    e >>= 1;
                    if e > 0 {
                        base = base.square();
                    }
                }
                result.unwrap()
            }
        }
    }

    /// Multiply by a *known* field constant.  Walks the constant's set
    /// bits and XORs a shifted copy per bit — the symbolic analogue of
    /// shift-and-add.
    ///
    /// The shifted copies are summed per output coefficient: coefficient
    /// `k` is the XOR of `self`'s coefficients `k − j` over the set bits
    /// `j`, whose monomials are gathered by reference and summed once, so
    /// only the monomials that survive are cloned.
    pub fn mul_const(&self, c: &F2mElement, n: u32) -> Self {
        if self.is_empty() {
            return Self::zero(0);
        }
        let raw = c.raw_bits();
        let shifts: Vec<usize> = (0..n as usize)
            .filter(|&j| (raw.get(j / 64).copied().unwrap_or(0) >> (j % 64)) & 1 == 1)
            .collect();
        let coeffs = (0..self.len() + n as usize - 1)
            .map(|k| {
                let mut parts = Vec::new();
                for &j in &shifts {
                    if let Some(a) = k.checked_sub(j).and_then(|i| self.coeffs.get(i)) {
                        parts.extend(&a.monomials);
                    }
                }
                AnfPoly {
                    monomials: xor_sum(parts, Vec::clone),
                }
            })
            .collect();
        Self { coeffs }
    }

    /// Reduce modulo the field's irreducible, truncating to `n`
    /// coefficients.  `z^n ≡ Σ_{t ∈ low_terms} z^t`.
    ///
    /// Formed as the combination `1 · self` of
    /// `AnfF2m::reduced_combination`: each low coefficient is summed
    /// once from every coefficient that folds onto it, where folding the
    /// top coefficients down one at a time would rebuild each target
    /// once per coefficient above it.
    pub fn reduce(&mut self, n: u32, irr: &IrreduciblePoly) {
        if self.coeffs.len() <= n as usize {
            self.coeffs.resize(n as usize, AnfPoly::zero());
            return;
        }
        self.coeffs = Self::reduced_combination(&[(self, &F2mElement::one(n))], n, irr);
    }

    /// `Σ_T c_T · X_T`, reduced modulo the field's irreducible to `n`
    /// coefficients, for symbolic elements `X_T` and *known* constants
    /// `c_T`: the element that summing the [`AnfF2m::mul_const`] products
    /// and calling [`AnfF2m::reduce`] once gives, computed without
    /// building any unreduced intermediate.
    ///
    /// Every step of that is `F₂`-linear in the coefficients: `c_T · z^i`
    /// is the XOR of `z^{i+j}` over the set bits `j` of `c_T`, and each
    /// `z^d` reduces to a fixed set of low powers ([`reduction_images`]).
    /// So coefficient `t` of the result is the XOR of every `X_T[i]`
    /// that lands on `z^t` an odd number of times, and those are
    /// gathered by reference and summed once per `t` by [`xor_sum`]: the
    /// only monomials cloned are the ones in the answer.
    fn reduced_combination(
        terms: &[(&AnfF2m, &F2mElement)],
        n: u32,
        irr: &IrreduciblePoly,
    ) -> Vec<AnfPoly> {
        let n = n as usize;
        let longest = terms.iter().map(|(x, _)| x.len()).max().unwrap_or(0);
        let images = reduction_images(longest + n, n, irr);
        let mut parts: Vec<Vec<&Vec<u32>>> = vec![Vec::new(); n];
        let mut lands = vec![0u64; n.div_ceil(64)];
        for &(x, c) in terms {
            let raw = c.raw_bits();
            let shifts: Vec<usize> = (0..n)
                .filter(|&j| (raw.get(j / 64).copied().unwrap_or(0) >> (j % 64)) & 1 == 1)
                .collect();
            for (i, coeff) in x.coeffs.iter().enumerate() {
                if coeff.is_zero() {
                    continue;
                }
                // Where `c · z^i` lands after reduction, with multiplicity
                // mod 2: two shifts that reduce onto the same `z^t` cancel.
                lands.fill(0);
                for &j in &shifts {
                    for (w, img) in lands.iter_mut().zip(&images[i + j]) {
                        *w ^= img;
                    }
                }
                for (word, &bits) in lands.iter().enumerate() {
                    let mut bits = bits;
                    while bits != 0 {
                        let t = word * 64 + bits.trailing_zeros() as usize;
                        parts[t].extend(&coeff.monomials);
                        bits &= bits - 1;
                    }
                }
            }
        }
        parts
            .into_iter()
            .map(|p| AnfPoly {
                monomials: xor_sum(p, Vec::clone),
            })
            .collect()
    }

    /// Evaluate coefficient-wise at a Boolean assignment, giving the
    /// bits of the resulting `F_{2^n}` element (low coefficient first).
    pub fn eval_bits(&self, assignment: &[bool]) -> Vec<bool> {
        self.coeffs.iter().map(|c| c.eval(assignment)).collect()
    }
}

/// `images[d]` is `z^d` reduced modulo `z^n + Σ_{t ∈ low_terms} z^t`, as
/// a bit set over the powers `0..n`, for every `d < len`: the linear map
/// that reduction applies to coefficient positions.  Built upwards, since
/// `z^d = Σ_t z^{d−n+t}` and every `d − n + t` is below `d`.
fn reduction_images(len: usize, n: usize, irr: &IrreduciblePoly) -> Vec<Vec<u64>> {
    let words = n.div_ceil(64);
    let mut images: Vec<Vec<u64>> = Vec::with_capacity(len);
    for d in 0..len {
        let mut image = vec![0u64; words];
        if d < n {
            image[d / 64] = 1 << (d % 64);
        } else {
            for &t in &irr.low_terms {
                assert!((t as usize) < n, "low terms lie below z^n");
                for (w, src) in image.iter_mut().zip(&images[d - n + t as usize]) {
                    *w ^= src;
                }
            }
        }
        images.push(image);
    }
    images
}

// ── Variable layout ─────────────────────────────────────────────────

/// Number of `z`-coefficients of `e_i` when each `X_j` has `l` of them:
/// `e_i` has degree `i(l − 1)`, hence `i·l − (i − 1)` coefficients.
pub fn e_len(i: usize, l: u32) -> usize {
    debug_assert!((1..=3).contains(&i));
    i * l as usize - (i - 1)
}

/// The Weil-descended, symmetrised `S₄` system for one target point.
///
/// Two variable spaces, each 0-indexed and independent; the SAT encoder
/// maps them into one numbering.
///
/// * **x-space** — `3l` variables, `x_{i,j}` at index `i·l + j` for
///   `i ∈ 0..3`, `j ∈ 0..l`, the bits of `X₁, X₂, X₃` in the factor-base
///   subspace `⟨1, z, …, z^{l−1}⟩`.
/// * **e-space** — `6l − 3` variables, `e_{i,d}` laid out consecutively
///   by `i` (see [`S4System::e_var`]).
#[derive(Clone, Debug)]
pub struct S4System {
    pub n: u32,
    pub l: u32,
    /// `correspondence[i][d]` is the coefficient of `z^d` in the
    /// `(i+1)`-th elementary symmetric function of `X₁, X₂, X₃`, as an
    /// ANF over **x-space**.  Pairing it with `e_{i,d}` gives the
    /// constraint `e_{i,d} ⊕ σ = 0`.
    pub correspondence: Vec<Vec<AnfPoly>>,
    /// The `n` Weil-descended `S₄` equations, as ANFs over **e-space**.
    /// Each is quadratic.
    pub semaev: Vec<AnfPoly>,
}

impl S4System {
    /// x-space index of the `j`-th bit of `X_{i+1}`.
    pub fn x_var(&self, i: usize, j: u32) -> u32 {
        debug_assert!(i < 3 && j < self.l);
        i as u32 * self.l + j
    }

    /// e-space index of `e_{i+1,d}`.
    pub fn e_var(&self, i: usize, d: usize) -> u32 {
        debug_assert!(i < 3 && d < e_len(i + 1, self.l));
        let mut base = 0usize;
        for k in 0..i {
            base += e_len(k + 1, self.l);
        }
        (base + d) as u32
    }

    /// Total number of x-space variables (`3l`).
    pub fn n_x_vars(&self) -> u32 {
        3 * self.l
    }

    /// Total number of e-space variables (`6l − 3`).
    pub fn n_e_vars(&self) -> u32 {
        (1..=3).map(|i| e_len(i, self.l) as u32).sum()
    }
}

// ── Building the system ─────────────────────────────────────────────

/// **Weil-descend the symmetrised Semaev `S₄`** for target x-coordinate
/// `x_r`, with the three unknown x-coordinates confined to the
/// `l`-dimensional factor-base subspace `⟨1, z, …, z^{l−1}⟩`.
///
/// Returns both halves of the model; see [`S4System`].
///
/// # Panics
///
/// If `b ≠ 1`.  The symmetrised form is specialised to the Koblitz
/// curve `y² + xy = x³ + x² + 1`; see the module docs.
pub fn weil_descend_s4(
    n: u32,
    l: u32,
    irr: &IrreduciblePoly,
    b: &F2mElement,
    x_r: &F2mElement,
) -> S4System {
    assert!(l >= 1 && l <= n, "subspace dimension l must lie in 1..=n");
    assert!(
        *b == F2mElement::one(n),
        "the symmetrised S₄ implemented here is specialised to b = 1 \
         (the Koblitz curve y² + xy = x³ + x² + 1); general b must be \
         re-derived — see the module documentation"
    );

    // ── half 1: the correspondence e_i = σ_i(X₁, X₂, X₃) ────────────
    // X_i lives in the subspace, so it has exactly l free bits.
    let xs: Vec<AnfF2m> = (0..3)
        .map(|i| AnfF2m::from_vars(i as u32 * l, l as usize))
        .collect();

    // These stay *unreduced*: e_i has degree i(l−1), and with l ≈ n/3
    // that is below n anyway.  Keeping them as plain z-polynomials is
    // what makes the e-variable count 6l−3 rather than 3n.
    let sigma1 = xs[0].xor(&xs[1]).xor(&xs[2]);
    let x0x1 = xs[0].mul(&xs[1]);
    let x0x2 = xs[0].mul(&xs[2]);
    let x1x2 = xs[1].mul(&xs[2]);
    let sigma2 = x0x1.xor(&x0x2).xor(&x1x2);
    let sigma3 = x0x1.mul(&xs[2]);

    let mut correspondence = Vec::with_capacity(3);
    for (i, sigma) in [sigma1, sigma2, sigma3].iter().enumerate() {
        let want = e_len(i + 1, l);
        let mut row = sigma.coeffs.clone();
        row.resize(want, AnfPoly::zero());
        debug_assert_eq!(row.len(), want);
        correspondence.push(row);
    }

    // ── half 2: S₄ over the e-variables ─────────────────────────────
    // Each e_i becomes a free symbolic element whose coefficients are
    // the fresh e-variables.
    let mut offset = 0u32;
    let mut e_syms = Vec::with_capacity(3);
    for i in 1..=3 {
        let len = e_len(i, l);
        e_syms.push(AnfF2m::from_vars(offset, len));
        offset += len as u32;
    }
    let (e1, e2, e3) = (&e_syms[0], &e_syms[1], &e_syms[2]);

    // Powers of the *known* constant x_R are reduced in the field
    // first, keeping every intermediate degree below n + max(deg e).
    let xr1 = x_r.clone();
    let xr2 = xr1.square(irr);
    let xr3 = xr2.mul(&xr1, irr);
    let xr4 = xr2.square(irr);

    // The symmetrised fourth summation polynomial for b = 1:
    //
    //   f₃ = x_R⁴ + e₁⁴ + e₃⁴ + e₂⁴x_R⁴ + e₃³x_R + e₃e₂²x_R³
    //        + e₃e₁²x_R + e₃x_R³ + e₁²e₃²x_R² + e₃²x_R⁴ + e₃² + e₂²x_R²
    //
    // Note how few real multiplications this needs: every `pow` with an
    // even exponent is a relocation, and every x_R power is a known
    // constant.  So f₃ is one F₂-linear combination Σ c_T · X_T of
    // symbolic X_T with constant c_T, which is formed and reduced in a
    // single pass (AnfF2m::reduced_combination) — the same element as
    // summing the twelve `X_T.mul_const(c_T)` products and reducing once.
    let e1_2 = e1.square();
    let e2_2 = e2.square();
    let e3_2 = e3.square();
    let e1_4 = e1_2.square();
    let e2_4 = e2_2.square();
    let e3_4 = e3_2.square();
    let e3_3 = e3_2.mul(e3);
    let e3_e2_2 = e3.mul(&e2_2);
    let e3_e1_2 = e3.mul(&e1_2);
    let e1_2_e3_2 = e1_2.mul(&e3_2);
    let xr4_sym = AnfF2m::from_const(&xr4, n);
    let one = F2mElement::one(n);

    let terms: [(&AnfF2m, &F2mElement); 12] = [
        (&xr4_sym, &one),   // x_R⁴
        (&e1_4, &one),      // e₁⁴
        (&e3_4, &one),      // e₃⁴
        (&e2_4, &xr4),      // e₂⁴ x_R⁴
        (&e3_3, &xr1),      // e₃³ x_R
        (&e3_e2_2, &xr3),   // e₃ e₂² x_R³
        (&e3_e1_2, &xr1),   // e₃ e₁² x_R
        (e3, &xr3),         // e₃ x_R³
        (&e1_2_e3_2, &xr2), // e₁² e₃² x_R²
        (&e3_2, &xr4),      // e₃² x_R⁴
        (&e3_2, &one),      // e₃²
        (&e2_2, &xr2),      // e₂² x_R²
    ];

    // One reduction, at the end.
    let semaev = AnfF2m::reduced_combination(&terms, n, irr);
    debug_assert!(
        semaev.iter().all(|c| c.degree() <= 2),
        "the symmetrised system must be quadratic in the e-variables"
    );

    S4System {
        n,
        l,
        correspondence,
        semaev,
    }
}

/// Evaluate the symmetrised `f₃` directly over `F_{2ⁿ}`, for cross-
/// checking the descended system.  This is the same twelve-term
/// expression, with everything a concrete field element.
pub fn symmetrised_s4_eval(
    e1: &F2mElement,
    e2: &F2mElement,
    e3: &F2mElement,
    x_r: &F2mElement,
    irr: &IrreduciblePoly,
) -> F2mElement {
    let sq = |z: &F2mElement| z.square(irr);
    let (e1_2, e2_2, e3_2) = (sq(e1), sq(e2), sq(e3));
    let (e1_4, e2_4, e3_4) = (sq(&e1_2), sq(&e2_2), sq(&e3_2));
    let e3_3 = e3_2.mul(e3, irr);
    let xr2 = sq(x_r);
    let xr3 = xr2.mul(x_r, irr);
    let xr4 = sq(&xr2);

    let mut acc = xr4.clone();
    acc = acc.add(&e1_4);
    acc = acc.add(&e3_4);
    acc = acc.add(&e2_4.mul(&xr4, irr));
    acc = acc.add(&e3_3.mul(x_r, irr));
    acc = acc.add(&e3.mul(&e2_2, irr).mul(&xr3, irr));
    acc = acc.add(&e3.mul(&e1_2, irr).mul(x_r, irr));
    acc = acc.add(&e3.mul(&xr3, irr));
    acc = acc.add(&e1_2.mul(&e3_2, irr).mul(&xr2, irr));
    acc = acc.add(&e3_2.mul(&xr4, irr));
    acc = acc.add(&e3_2);
    acc = acc.add(&e2_2.mul(&xr2, irr));
    acc
}

/// Elementary symmetric functions of three field elements.
pub fn elementary_symmetric_3(
    x1: &F2mElement,
    x2: &F2mElement,
    x3: &F2mElement,
    irr: &IrreduciblePoly,
) -> (F2mElement, F2mElement, F2mElement) {
    let e1 = x1.add(x2).add(x3);
    let e2 = x1.mul(x2, irr).add(&x1.mul(x3, irr)).add(&x2.mul(x3, irr));
    let e3 = x1.mul(x2, irr).mul(x3, irr);
    (e1, e2, e3)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `n = 19`, `l = 6` Koblitz parameters, taken verbatim from
    /// `INFOn19l6-1-S.dimacs` in the reference corpus (see
    /// `research/notes/ecc2k130/RESEARCH_TRIMOSKA_BENCHMARKS.md`).  The irreducible is
    /// `z¹⁹ + z⁵ + z² + z + 1`.
    fn corpus_n19l6() -> (u32, u32, IrreduciblePoly, F2mElement, [F2mElement; 3]) {
        let n = 19;
        let irr = IrreduciblePoly {
            degree: 19,
            low_terms: vec![0, 1, 2, 5],
        };
        let x_r = F2mElement::from_bit_positions(&[1, 2, 5, 6, 7, 8, 10, 11, 12, 16], n);
        let x1 = F2mElement::from_bit_positions(&[4], n);
        let x2 = F2mElement::from_bit_positions(&[2, 4, 5], n);
        let x3 = F2mElement::from_bit_positions(&[1, 4], n);
        (n, 6, irr, x_r, [x1, x2, x3])
    }

    /// **Cross-check against an independent generator.**  The planted
    /// decomposition recorded in the reference corpus must make the
    /// symmetrised `f₃` vanish.  If our twelve-term transcription were
    /// wrong, this would not hold.
    #[test]
    fn symmetrised_s4_vanishes_on_corpus_planted_solution() {
        let (n, _l, irr, x_r, xs) = corpus_n19l6();
        let (e1, e2, e3) = elementary_symmetric_3(&xs[0], &xs[1], &xs[2], &irr);
        let val = symmetrised_s4_eval(&e1, &e2, &e3, &x_r, &irr);
        assert!(
            val.is_zero(),
            "planted corpus solution must satisfy the symmetrised S₄"
        );
        let _ = n;
    }

    /// A random point of the subspace is overwhelmingly unlikely to
    /// decompose, so `f₃` should *not* vanish — a guard against a
    /// transcription that is accidentally identically zero.
    #[test]
    fn symmetrised_s4_is_not_identically_zero() {
        let (n, _l, irr, x_r, _) = corpus_n19l6();
        let y1 = F2mElement::from_bit_positions(&[0], n);
        let y2 = F2mElement::from_bit_positions(&[1], n);
        let y3 = F2mElement::from_bit_positions(&[3], n);
        let (e1, e2, e3) = elementary_symmetric_3(&y1, &y2, &y3, &irr);
        assert!(!symmetrised_s4_eval(&e1, &e2, &e3, &x_r, &irr).is_zero());
    }

    /// Squaring must be exactly relocation: same coefficients, moved
    /// from `d` to `2d`.
    #[test]
    fn square_is_relocation() {
        let a = AnfF2m::from_vars(0, 4);
        let sq = a.square();
        assert_eq!(sq.len(), 7);
        for d in 0..4 {
            assert_eq!(sq.coeffs[2 * d], a.coeffs[d], "coefficient {d} → {}", 2 * d);
            if 2 * d + 1 < sq.len() {
                assert!(sq.coeffs[2 * d + 1].is_zero(), "odd slots must be empty");
            }
        }
    }

    /// Squaring by relocation must agree with an honest multiplication.
    #[test]
    fn square_agrees_with_multiplication() {
        let a = AnfF2m::from_vars(0, 5);
        let by_mul = a.mul(&a);
        let by_shift = a.square();
        assert_eq!(by_mul.len(), by_shift.len());
        for d in 0..by_mul.len() {
            assert_eq!(by_mul.coeffs[d], by_shift.coeffs[d], "coefficient {d}");
        }
    }

    /// ANF addition is symmetric difference: adding a polynomial to
    /// itself must annihilate it.
    #[test]
    fn anf_addition_cancels() {
        let mut p = AnfPoly::var(1).mul(&AnfPoly::var(2));
        p.xor_assign(&AnfPoly::var(3));
        let q = p.clone();
        p.xor_assign(&q);
        assert!(p.is_zero(), "x ⊕ x must be 0");
    }

    /// `x · x = x`, so a squared monomial stays squarefree.
    #[test]
    fn anf_monomials_are_squarefree() {
        let x = AnfPoly::var(7);
        assert_eq!(x.mul(&x), x);
    }

    /// **End-to-end**: the descended system, evaluated at the planted
    /// solution's bits, must be all-zero — both halves.  This ties the
    /// symbolic descent to concrete field arithmetic.
    #[test]
    fn descended_system_vanishes_on_planted_solution() {
        let (n, l, irr, x_r, xs) = corpus_n19l6();
        let b = F2mElement::one(n);
        let sys = weil_descend_s4(n, l, &irr, &b, &x_r);

        // x-space assignment: the l low bits of each planted X_i.
        let mut x_assign = vec![false; sys.n_x_vars() as usize];
        for (i, x) in xs.iter().enumerate() {
            let raw = x.raw_bits();
            for j in 0..l {
                let bit = (raw[(j / 64) as usize] >> (j % 64)) & 1 == 1;
                x_assign[sys.x_var(i, j) as usize] = bit;
            }
        }

        // e-space assignment: read the e-variables off the
        // correspondence, which is exactly what it is for.
        let mut e_assign = vec![false; sys.n_e_vars() as usize];
        for i in 0..3 {
            for d in 0..e_len(i + 1, l) {
                e_assign[sys.e_var(i, d) as usize] = sys.correspondence[i][d].eval(&x_assign);
            }
        }

        // Half 1 sanity: those e-values must match the field-level
        // elementary symmetric functions of the planted X_i.
        let (e1, e2, e3) = elementary_symmetric_3(&xs[0], &xs[1], &xs[2], &irr);
        for (i, e) in [&e1, &e2, &e3].iter().enumerate() {
            // e_i is held unreduced but has degree < n here, so its
            // coefficients are directly the field element's bits.
            let raw = e.raw_bits();
            for d in 0..e_len(i + 1, l) {
                let want = (raw[d / 64] >> (d % 64)) & 1 == 1;
                let got = e_assign[sys.e_var(i, d) as usize];
                assert_eq!(got, want, "e_{}, coefficient {d}", i + 1);
            }
        }

        // Half 2: every descended equation must vanish.
        for (k, eq) in sys.semaev.iter().enumerate() {
            assert!(
                !eq.eval(&e_assign),
                "descended S₄ equation {k} did not vanish at the planted solution"
            );
        }
    }

    /// The descended system must be quadratic in the e-variables — that
    /// is the entire point of symmetrising.
    #[test]
    fn descended_system_is_quadratic() {
        let (n, l, irr, x_r, _) = corpus_n19l6();
        let b = F2mElement::one(n);
        let sys = weil_descend_s4(n, l, &irr, &b, &x_r);
        assert_eq!(sys.semaev.len(), n as usize);
        assert!(sys.semaev.iter().all(|e| e.degree() <= 2));
        // The correspondence carries the cubic part: e₃ = X₁X₂X₃.
        assert_eq!(
            sys.correspondence[0].iter().map(|p| p.degree()).max(),
            Some(1)
        );
        assert_eq!(
            sys.correspondence[1].iter().map(|p| p.degree()).max(),
            Some(2)
        );
        assert_eq!(
            sys.correspondence[2].iter().map(|p| p.degree()).max(),
            Some(3)
        );
    }

    /// A curve other than `b = 1` must be refused, not silently
    /// mis-descended.
    #[test]
    #[should_panic(expected = "specialised to b = 1")]
    fn general_b_is_rejected() {
        let (n, l, irr, x_r, _) = corpus_n19l6();
        let b = F2mElement::from_bit_positions(&[1], n);
        let _ = weil_descend_s4(n, l, &irr, &b, &x_r);
    }

    // ── The merged and gathered sums against the old toggles ────────

    /// The toggle-based arithmetic this module used before its sums
    /// became ordered merges and gathered parity sums, kept verbatim as
    /// the oracle those are pinned against.  Equal results are equal
    /// monomial sets, so `monomials()` also iterates them identically.
    mod toggle_reference {
        use super::super::{e_len, merge_squarefree, AnfF2m, AnfPoly};
        use crate::binary_ecc::{F2mElement, IrreduciblePoly};

        fn toggle(p: &mut AnfPoly, mono: Vec<u32>) {
            if !p.monomials.remove(&mono) {
                p.monomials.insert(mono);
            }
        }

        pub fn xor_assign(p: &mut AnfPoly, other: &AnfPoly) {
            for m in &other.monomials {
                toggle(p, m.clone());
            }
        }

        pub fn mul(a: &AnfPoly, b: &AnfPoly) -> AnfPoly {
            let mut out = AnfPoly::zero();
            for x in &a.monomials {
                for y in &b.monomials {
                    toggle(&mut out, merge_squarefree(x, y));
                }
            }
            out
        }

        pub fn xor(a: &AnfF2m, b: &AnfF2m) -> AnfF2m {
            let len = a.len().max(b.len());
            let mut out = AnfF2m::zero(len);
            for i in 0..len {
                if let Some(c) = a.coeffs.get(i) {
                    xor_assign(&mut out.coeffs[i], c);
                }
                if let Some(c) = b.coeffs.get(i) {
                    xor_assign(&mut out.coeffs[i], c);
                }
            }
            out
        }

        pub fn f2m_mul(a: &AnfF2m, b: &AnfF2m) -> AnfF2m {
            if a.is_empty() || b.is_empty() {
                return AnfF2m::zero(0);
            }
            let mut out = AnfF2m::zero(a.len() + b.len() - 1);
            for (i, x) in a.coeffs.iter().enumerate() {
                if x.is_zero() {
                    continue;
                }
                for (j, y) in b.coeffs.iter().enumerate() {
                    if y.is_zero() {
                        continue;
                    }
                    let prod = mul(x, y);
                    xor_assign(&mut out.coeffs[i + j], &prod);
                }
            }
            out
        }

        pub fn mul_const(a: &AnfF2m, c: &F2mElement, n: u32) -> AnfF2m {
            if a.is_empty() {
                return AnfF2m::zero(0);
            }
            let raw = c.raw_bits();
            let mut out = AnfF2m::zero(a.len() + n as usize - 1);
            for j in 0..n as usize {
                let set = (raw.get(j / 64).copied().unwrap_or(0) >> (j % 64)) & 1 == 1;
                if !set {
                    continue;
                }
                for (i, x) in a.coeffs.iter().enumerate() {
                    if !x.is_zero() {
                        let x = x.clone();
                        xor_assign(&mut out.coeffs[i + j], &x);
                    }
                }
            }
            out
        }

        pub fn reduce(a: &mut AnfF2m, n: u32, irr: &IrreduciblePoly) {
            let n = n as usize;
            if a.coeffs.len() <= n {
                a.coeffs.resize(n, AnfPoly::zero());
                return;
            }
            for d in (n..a.coeffs.len()).rev() {
                if a.coeffs[d].is_zero() {
                    continue;
                }
                let top = std::mem::replace(&mut a.coeffs[d], AnfPoly::zero());
                for &t in &irr.low_terms {
                    let target = d - n + t as usize;
                    let top = top.clone();
                    xor_assign(&mut a.coeffs[target], &top);
                }
            }
            a.coeffs.truncate(n);
        }

        /// The old `weil_descend_s4` body, both halves, with every sum,
        /// product and reduction taken from this module: returns
        /// `(correspondence, semaev)`.
        pub fn weil_descend_s4(
            n: u32,
            l: u32,
            irr: &IrreduciblePoly,
            x_r: &F2mElement,
        ) -> (Vec<Vec<AnfPoly>>, Vec<AnfPoly>) {
            let xs: Vec<AnfF2m> = (0..3)
                .map(|i| AnfF2m::from_vars(i as u32 * l, l as usize))
                .collect();
            let sigma1 = xor(&xor(&xs[0], &xs[1]), &xs[2]);
            let x0x1 = f2m_mul(&xs[0], &xs[1]);
            let x0x2 = f2m_mul(&xs[0], &xs[2]);
            let x1x2 = f2m_mul(&xs[1], &xs[2]);
            let sigma2 = xor(&xor(&x0x1, &x0x2), &x1x2);
            let sigma3 = f2m_mul(&x0x1, &xs[2]);
            let mut correspondence = Vec::with_capacity(3);
            for (i, sigma) in [sigma1, sigma2, sigma3].iter().enumerate() {
                let mut row = sigma.coeffs.clone();
                row.resize(e_len(i + 1, l), AnfPoly::zero());
                correspondence.push(row);
            }

            let mut offset = 0u32;
            let mut e_syms = Vec::with_capacity(3);
            for i in 1..=3 {
                let len = e_len(i, l);
                e_syms.push(AnfF2m::from_vars(offset, len));
                offset += len as u32;
            }
            let (e1, e2, e3) = (&e_syms[0], &e_syms[1], &e_syms[2]);
            let xr1 = x_r.clone();
            let xr2 = xr1.square(irr);
            let xr3 = xr2.mul(&xr1, irr);
            let xr4 = xr2.square(irr);
            let e1_2 = e1.square();
            let e2_2 = e2.square();
            let e3_2 = e3.square();
            let e1_4 = e1_2.square();
            let e2_4 = e2_2.square();
            let e3_4 = e3_2.square();
            let e3_3 = f2m_mul(&e3_2, e3);
            let terms: Vec<AnfF2m> = vec![
                AnfF2m::from_const(&xr4, n),
                e1_4,
                e3_4,
                mul_const(&e2_4, &xr4, n),
                mul_const(&e3_3, &xr1, n),
                mul_const(&f2m_mul(e3, &e2_2), &xr3, n),
                mul_const(&f2m_mul(e3, &e1_2), &xr1, n),
                mul_const(e3, &xr3, n),
                mul_const(&f2m_mul(&e1_2, &e3_2), &xr2, n),
                mul_const(&e3_2, &xr4, n),
                e3_2.clone(),
                mul_const(&e2_2, &xr2, n),
            ];
            let mut f3 = AnfF2m::zero(0);
            for t in &terms {
                f3 = xor(&f3, t);
            }
            reduce(&mut f3, n, irr);
            (correspondence, f3.coeffs)
        }
    }

    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};

    /// A random ANF: up to `count` monomials of degree ≤ `max_deg` over
    /// the variable ids in `palette`.  A small palette makes repeated
    /// monomials, and so cancellation, common; a palette with ids at and
    /// above `u16::MAX` and degrees above four reaches every monomial
    /// shape the sums have to order.
    fn random_anf(rng: &mut StdRng, palette: &[u32], max_deg: usize, count: usize) -> AnfPoly {
        let mut p = AnfPoly::zero();
        for _ in 0..rng.gen_range(0..=count) {
            let deg = rng.gen_range(0..=max_deg);
            let mut m: Vec<u32> = (0..deg)
                .map(|_| palette[rng.gen_range(0..palette.len())])
                .collect();
            m.sort_unstable();
            m.dedup();
            p.monomials.insert(m);
        }
        p
    }

    fn random_f2m(rng: &mut StdRng, len: usize, palette: &[u32], count: usize) -> AnfF2m {
        AnfF2m {
            coeffs: (0..len)
                .map(|_| random_anf(rng, palette, 3, count))
                .collect(),
        }
    }

    fn palettes() -> [Vec<u32>; 3] {
        [
            (0..6).collect(),
            (0..40).collect(),
            vec![0, 7, 65_533, 65_534, 65_535, 65_536, 70_000, u32::MAX - 1],
        ]
    }

    /// The ordered-merge `xor_assign` and the gathered `mul` give the
    /// toggles' monomial sets on random operands, including empty,
    /// identical and heavily overlapping ones.
    #[test]
    fn anf_sums_agree_with_toggles() {
        let mut rng = StdRng::seed_from_u64(0x0041_4e46_5f78_6f72);
        let palettes = palettes();
        for round in 0..600 {
            let palette = &palettes[round % palettes.len()];
            let a = random_anf(&mut rng, palette, 6, 40);
            let b = random_anf(&mut rng, palette, 6, 40);
            let zero = AnfPoly::zero();
            for (x, y) in [(&a, &b), (&a, &a), (&a, &zero), (&zero, &b)] {
                let mut got = x.clone();
                got.xor_assign(y);
                let mut want = x.clone();
                toggle_reference::xor_assign(&mut want, y);
                assert_eq!(got, want, "xor_assign, round {round}");
                assert_eq!(x.mul(y), toggle_reference::mul(x, y), "mul, round {round}");
            }
        }
    }

    /// `AnfF2m::{xor, mul, mul_const, reduce}` give the toggles'
    /// coefficients on random elements, with field widths on both sides
    /// of a 64-bit word and reductions deep enough to fold twice.
    #[test]
    fn symbolic_field_ops_agree_with_toggles() {
        let mut rng = StdRng::seed_from_u64(0x5334_5f66_326d);
        let palettes = palettes();
        for round in 0..80 {
            let palette = &palettes[round % palettes.len()];
            let n = [5u32, 17, 63, 64, 67, 130][round % 6];
            let mut low_terms = vec![0];
            for _ in 0..rng.gen_range(0..4) {
                low_terms.push(rng.gen_range(1..n));
            }
            low_terms.sort_unstable();
            low_terms.dedup();
            let irr = IrreduciblePoly {
                degree: n,
                low_terms,
            };
            let bits: Vec<u32> = (0..n).filter(|_| rng.gen_bool(0.5)).collect();
            let c = F2mElement::from_bit_positions(&bits, n);

            let (len_a, len_b) = (rng.gen_range(0..12), rng.gen_range(0..12));
            let a = random_f2m(&mut rng, len_a, palette, 6);
            let b = random_f2m(&mut rng, len_b, palette, 6);
            assert_eq!(a.xor(&b).coeffs, toggle_reference::xor(&a, &b).coeffs);
            assert_eq!(a.mul(&b).coeffs, toggle_reference::f2m_mul(&a, &b).coeffs);
            assert_eq!(
                a.mul_const(&c, n).coeffs,
                toggle_reference::mul_const(&a, &c, n).coeffs
            );

            let len = rng.gen_range(0..3 * n as usize);
            let long = random_f2m(&mut rng, len, palette, 6);
            let mut got = long.clone();
            got.reduce(n, &irr);
            let mut want = long;
            toggle_reference::reduce(&mut want, n, &irr);
            assert_eq!(got.coeffs, want.coeffs, "reduce, n = {n}, round {round}");
        }
    }

    /// **The descended system is unchanged**: both halves of
    /// [`weil_descend_s4`] equal the toggle-based construction's, on the
    /// perfbench cell (`n = 17, l = 4`), the corpus cell, a cell whose
    /// `e₃⁴` runs past `z^{2n}` (so reduction folds more than once), and
    /// a field wider than one 64-bit word.
    #[test]
    fn weil_descent_agrees_with_toggle_reference() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        let mut rng = StdRng::seed_from_u64(0x7765_696c);
        let cases = [
            (17, 4, find_irreducible_sparse(17).expect("irreducible")),
            (19, 6, corpus_n19l6().2),
            (11, 6, find_irreducible_sparse(11).expect("irreducible")),
            (
                67,
                3,
                IrreduciblePoly {
                    degree: 67,
                    low_terms: vec![0, 1, 2, 5],
                },
            ),
        ];
        for (n, l, irr) in cases {
            let b = F2mElement::one(n);
            for _ in 0..3 {
                let bits: Vec<u32> = (0..n).filter(|_| rng.gen_bool(0.5)).collect();
                let x_r = F2mElement::from_bit_positions(&bits, n);
                let sys = weil_descend_s4(n, l, &irr, &b, &x_r);
                let (correspondence, semaev) = toggle_reference::weil_descend_s4(n, l, &irr, &x_r);
                assert_eq!(sys.correspondence, correspondence, "n = {n}, l = {l}");
                assert_eq!(sys.semaev, semaev, "n = {n}, l = {l}");
            }
        }
    }

    /// A reduction polynomial `z^n + Σ low_terms` with `z⁰` and a random
    /// subset of the other powers below `z^n`, sparse or dense.  The
    /// symbolic reduction is a linear map for any such modulus, so it
    /// need not be irreducible to pin one implementation to another.
    fn random_modulus(rng: &mut StdRng, n: u32, density: f64) -> IrreduciblePoly {
        let mut low_terms = vec![0];
        low_terms.extend((1..n).filter(|_| rng.gen_bool(density)));
        IrreduciblePoly {
            degree: n,
            low_terms,
        }
    }

    /// The word edges the first comparison skips: fields of one, two and
    /// three coefficients, and widths on each side of 64 and 128 bits,
    /// each against a sparse, a half-full and a dense modulus (so an
    /// image `z^d mod f` can fill most of a word), with elements up to
    /// three times the field width (so reduction folds repeatedly).
    #[test]
    fn symbolic_field_ops_agree_with_toggles_at_word_edges() {
        let mut rng = StdRng::seed_from_u64(0x7764_6765);
        let palettes = palettes();
        for (round, &n) in [1u32, 2, 3, 64, 65, 127, 128, 129]
            .iter()
            .cycle()
            .take(24)
            .enumerate()
        {
            let palette = &palettes[round % palettes.len()];
            let irr = random_modulus(&mut rng, n, [0.05, 0.5, 0.95][round % 3]);
            let bits: Vec<u32> = (0..n).filter(|_| rng.gen_bool(0.5)).collect();
            let c = F2mElement::from_bit_positions(&bits, n);

            let len_a = rng.gen_range(0..6);
            let a = random_f2m(&mut rng, len_a, palette, 4);
            assert_eq!(
                a.mul_const(&c, n).coeffs,
                toggle_reference::mul_const(&a, &c, n).coeffs,
                "mul_const, n = {n}, round {round}"
            );

            let len = rng.gen_range(0..=3 * n as usize);
            let long = random_f2m(&mut rng, len, palette, 3);
            let mut got = long.clone();
            got.reduce(n, &irr);
            let mut want = long;
            toggle_reference::reduce(&mut want, n, &irr);
            assert_eq!(got.coeffs, want.coeffs, "reduce, n = {n}, round {round}");
        }
    }

    /// Both halves of [`weil_descend_s4`] against the toggles on the
    /// smallest fields, on `l = n` (where `e₃⁴` has `12n − 11`
    /// coefficients and folds about a dozen times), across the 64- and
    /// 128-bit word boundaries, and under dense moduli.
    #[test]
    fn weil_descent_agrees_with_toggle_reference_at_edges() {
        let mut rng = StdRng::seed_from_u64(0x6564_6765);
        let cases: [(u32, u32, f64); 10] = [
            (1, 1, 0.5),
            (2, 2, 0.5),
            (3, 3, 0.5),
            (5, 5, 0.9),
            (8, 8, 0.5),
            (63, 3, 0.5),
            (64, 3, 0.1),
            (65, 3, 0.9),
            (65, 8, 0.05),
            (129, 3, 0.5),
        ];
        for (n, l, density) in cases {
            let irr = random_modulus(&mut rng, n, density);
            let b = F2mElement::one(n);
            for _ in 0..2 {
                let bits: Vec<u32> = (0..n).filter(|_| rng.gen_bool(0.5)).collect();
                let x_r = F2mElement::from_bit_positions(&bits, n);
                let sys = weil_descend_s4(n, l, &irr, &b, &x_r);
                let (correspondence, semaev) = toggle_reference::weil_descend_s4(n, l, &irr, &x_r);
                assert_eq!(sys.correspondence, correspondence, "n = {n}, l = {l}");
                assert_eq!(sys.semaev, semaev, "n = {n}, l = {l}");
            }
        }
    }

    /// `xor_assign` on lopsided operands — a handful of monomials into a
    /// set of thousands and the reverse, disjoint, contained, and
    /// overlapping — and `mul` on the smallest operands, where a product
    /// of one monomial with a sum can still cancel (`x₁ · (x₂ + x₁x₂)`).
    /// These are the shapes a size-dependent choice between merging and
    /// toggling has to get right on both sides of its threshold.
    #[test]
    fn anf_sums_agree_with_toggles_on_lopsided_operands() {
        let mut rng = StdRng::seed_from_u64(0x6c6f_7073);
        let wide: Vec<u32> = (0..80).collect();
        for round in 0..60 {
            let big = random_anf(&mut rng, &wide, 3, 3000);
            let small = random_anf(&mut rng, &wide, 3, [1, 2, 3, 5][round % 4]);
            // Some of `big`'s own monomials, so that some of them cancel.
            let mut inside = AnfPoly::zero();
            for m in big.monomials().step_by(97 + round) {
                inside.monomials.insert(m.clone());
            }
            let mut mixed = inside.clone();
            mixed.xor_assign(&small);
            for (x, y) in [
                (&big, &small),
                (&small, &big),
                (&big, &inside),
                (&inside, &big),
                (&big, &mixed),
            ] {
                let mut got = x.clone();
                got.xor_assign(y);
                let mut want = x.clone();
                toggle_reference::xor_assign(&mut want, y);
                assert_eq!(got, want, "xor_assign, round {round}");
            }
        }

        let x1 = AnfPoly::var(1);
        let mut cancel = AnfPoly::var(2);
        cancel.xor_assign(&x1.mul(&AnfPoly::var(2)));
        assert!(x1.mul(&cancel).is_zero(), "x₁·(x₂ + x₁x₂) = 0");
        let palette: Vec<u32> = (0..5).collect();
        for round in 0..400 {
            let a = random_anf(&mut rng, &palette, 3, [0, 1, 2, 4][round % 4]);
            let b = random_anf(&mut rng, &palette, 3, [1, 1, 3, 8][(round / 4) % 4]);
            for (x, y) in [(&a, &b), (&b, &a), (&AnfPoly::one(), &b), (&a, &a)] {
                assert_eq!(x.mul(y), toggle_reference::mul(x, y), "mul, round {round}");
            }
        }
    }

    /// The single-monomial paths: one monomial added to a large sum, both
    /// where it is new and where it cancels, and the product of one
    /// monomial by one, including the constant `1`, shared variables and a
    /// monomial by itself.
    #[test]
    fn single_monomial_paths_agree_with_toggles() {
        let mut rng = StdRng::seed_from_u64(0x6f6e_6573);
        let wide: Vec<u32> = (0..40).collect();
        let big = random_anf(&mut rng, &wide, 3, 600);
        let fresh = random_anf(&mut rng, &wide, 3, 80);
        let single = |m: &Vec<u32>| AnfPoly {
            monomials: BTreeSet::from([m.clone()]),
        };
        // Every seventh monomial of `big` cancels; most of `fresh` are new.
        let singles: Vec<AnfPoly> = big
            .monomials()
            .step_by(7)
            .chain(fresh.monomials())
            .map(single)
            .collect();
        for one in &singles {
            let mut got = big.clone();
            got.xor_assign(one);
            let mut want = big.clone();
            toggle_reference::xor_assign(&mut want, one);
            assert_eq!(got, want, "xor_assign of {one:?}");
        }

        let unit = AnfPoly::one();
        let palette: Vec<u32> = (0..4).collect();
        let small: Vec<AnfPoly> = (0..40)
            .map(|_| random_anf(&mut rng, &palette, 3, 1))
            .filter(|p| p.len() == 1)
            .chain([unit.clone()])
            .collect();
        for a in &small {
            for b in &small {
                assert_eq!(a.mul(b), toggle_reference::mul(a, b), "{a:?} · {b:?}");
            }
        }
    }

    // ── Adversarial review: the private sums and every size threshold ──

    /// The XOR-sum of a multiset of monomials by counting: each monomial
    /// kept once if it occurs an odd number of times.  Independent of
    /// both the toggles and the sort-and-cancel under test.
    fn parity_sum<'a>(monos: impl IntoIterator<Item = &'a Vec<u32>>) -> BTreeSet<Vec<u32>> {
        let mut count = std::collections::BTreeMap::<&Vec<u32>, usize>::new();
        for m in monos {
            *count.entry(m).or_default() += 1;
        }
        count
            .into_iter()
            .filter(|(_, c)| c % 2 == 1)
            .map(|(m, _)| m.clone())
            .collect()
    }

    /// A random monomial of degree ≤ `max_deg` over `palette`, strictly
    /// increasing (what the module stores).
    fn random_mono(rng: &mut StdRng, palette: &[u32], max_deg: usize) -> Vec<u32> {
        let deg = rng.gen_range(0..=max_deg);
        let mut m: Vec<u32> = (0..deg)
            .map(|_| palette[rng.gen_range(0..palette.len())])
            .collect();
        m.sort_unstable();
        m.dedup();
        m
    }

    /// `packed_key` orders exactly as the index vectors do and is
    /// injective, at the 16-bit field edges and at the degree cap.
    #[test]
    fn review_packed_key_is_order_preserving() {
        let mut rng = StdRng::seed_from_u64(0x7061_636b);
        let palette = [0u32, 1, 2, 255, 256, 65_532, 65_533, 65_534, 65_535, 65_536];
        let monos: Vec<Vec<u32>> = (0..3000)
            .map(|_| random_mono(&mut rng, &palette, 6))
            .collect();
        for a in &monos {
            let ka = packed_key(a);
            let fits = a.len() <= 4 && a.iter().all(|&v| v < 65_535);
            assert_eq!(ka.is_some(), fits, "{a:?}");
            for b in monos.iter().take(200) {
                if let (Some(x), Some(y)) = (ka, packed_key(b)) {
                    assert_eq!(x.cmp(&y), a.cmp(b), "{a:?} vs {b:?}");
                }
            }
        }
    }

    /// `retain_odd` keeps each run of odd length once, in order.
    #[test]
    fn review_retain_odd_is_parity() {
        let mut rng = StdRng::seed_from_u64(0x006f_6464);
        for _ in 0..2000 {
            let len = rng.gen_range(0..40);
            let mut v: Vec<u8> = (0..len).map(|_| rng.gen_range(0..6)).collect();
            v.sort_unstable();
            let mut want = Vec::new();
            for x in 0..6u8 {
                if v.iter().filter(|&&y| y == x).count() % 2 == 1 {
                    want.push(x);
                }
            }
            retain_odd(&mut v, |a, b| a == b);
            assert_eq!(v, want);
        }
    }

    /// `xor_sum`, owned and borrowed, on multisets of every length across
    /// the `SMALL_SUM` switch, with multiplicities one to five, on
    /// all-packable, all-unpackable and mixed monomials.
    #[test]
    fn review_xor_sum_is_parity_sum() {
        let mut rng = StdRng::seed_from_u64(0x7873_756d);
        let packable: Vec<u32> = (0..12).collect();
        let unpackable: Vec<u32> = vec![3, 65_534, 65_535, 70_000, u32::MAX];
        for round in 0..3000 {
            let distinct = rng.gen_range(1..12);
            let pool: Vec<Vec<u32>> = (0..distinct)
                .map(|k| match round % 3 {
                    0 => random_mono(&mut rng, &packable, 4),
                    1 => {
                        // Degree five or a variable past the key's range.
                        let mut m = random_mono(&mut rng, &unpackable, 3);
                        if m.last().is_none_or(|&v| v < 65_535) {
                            m = (0..5).map(|i| i * 3 + k as u32).collect();
                        }
                        m
                    }
                    _ => {
                        let from = if rng.gen_bool(0.2) {
                            &unpackable
                        } else {
                            &packable
                        };
                        random_mono(&mut rng, from, 6)
                    }
                })
                .collect();
            let len = rng.gen_range(0..=2 * SMALL_SUM + 3);
            let mut multiset: Vec<Vec<u32>> = Vec::with_capacity(len);
            while multiset.len() < len {
                let m = &pool[rng.gen_range(0..pool.len())];
                for _ in 0..rng.gen_range(1..=5) {
                    multiset.push(m.clone());
                }
            }
            // Unsorted, as the gathered products arrive.
            for i in (1..multiset.len()).rev() {
                multiset.swap(i, rng.gen_range(0..=i));
            }
            let want = parity_sum(&multiset);
            let borrowed: Vec<&Vec<u32>> = multiset.iter().collect();
            assert_eq!(
                xor_sum(borrowed, Vec::clone),
                want,
                "borrowed, round {round}"
            );
            assert_eq!(
                xor_sum(multiset.clone(), |m| m),
                want,
                "owned, round {round}"
            );
        }
    }

    /// `xor_assign` over a grid of sizes that crosses every branch of
    /// `toggling_is_cheaper` (and the empty and single-monomial paths),
    /// with the overlap swept from disjoint through equal.
    #[test]
    fn review_xor_assign_across_size_grid() {
        let mut rng = StdRng::seed_from_u64(0x6772_6964);
        let wide: Vec<u32> = (0..60).collect();
        let sizes = [
            0usize, 1, 2, 3, 4, 5, 15, 16, 17, 28, 31, 33, 64, 100, 257, 1000, 2500,
        ];
        for &mine in &sizes {
            for &theirs in &sizes {
                for overlap in [0.0, 0.3, 1.0] {
                    let mut a = BTreeSet::new();
                    while a.len() < mine {
                        a.insert(random_mono(&mut rng, &wide, 4));
                    }
                    let mut b = BTreeSet::new();
                    let from_a: Vec<&Vec<u32>> = a.iter().collect();
                    // Drawn from `a` only while `a` has monomials `b`
                    // does not yet hold, so `b` always reaches `theirs`.
                    while b.len() < theirs {
                        if b.len() < from_a.len() && rng.gen_bool(overlap) {
                            b.insert(from_a[rng.gen_range(0..from_a.len())].clone());
                        } else {
                            b.insert(random_mono(&mut rng, &wide, 4));
                        }
                    }
                    let (a, b) = (AnfPoly { monomials: a }, AnfPoly { monomials: b });
                    let mut got = a.clone();
                    got.xor_assign(&b);
                    let mut want = a.clone();
                    toggle_reference::xor_assign(&mut want, &b);
                    assert_eq!(got, want, "mine {mine}, theirs {theirs}, overlap {overlap}");
                    assert_eq!(
                        got.monomials,
                        parity_sum(a.monomials().chain(b.monomials())),
                        "parity, mine {mine}, theirs {theirs}"
                    );
                }
            }
        }
    }

    /// `mul` at every product count from 0 to 30 — through the one-by-one,
    /// toggled and gathered paths — with cancelling products (a shared
    /// variable collapses `x·xy` and `xy·y` onto `xy`), unpackable
    /// monomials that force the gathered sum's fallback sort, and the
    /// constant.
    #[test]
    fn review_mul_across_small_sum_threshold() {
        let mut rng = StdRng::seed_from_u64(0x6d75_6c74);
        let palettes: [Vec<u32>; 3] = [
            (0..4).collect(),
            vec![1, 2, 65_534, 65_535, 1 << 20],
            (0..9).collect(),
        ];
        for round in 0..4000 {
            let palette = &palettes[round % 3];
            let deg = if round % 3 == 2 { 6 } else { 3 };
            let (la, lb) = (rng.gen_range(0..=6), rng.gen_range(0..=6));
            let mut a = AnfPoly::zero();
            for _ in 0..la {
                a.monomials.insert(random_mono(&mut rng, palette, deg));
            }
            let mut b = AnfPoly::zero();
            for _ in 0..lb {
                b.monomials.insert(random_mono(&mut rng, palette, deg));
            }
            let want = toggle_reference::mul(&a, &b);
            assert_eq!(a.mul(&b), want, "{a:?} · {b:?}");
            let mut products = Vec::new();
            for x in a.monomials() {
                for y in b.monomials() {
                    products.push(merge_squarefree(x, y));
                }
            }
            assert_eq!(
                want.monomials,
                parity_sum(&products),
                "parity {a:?} · {b:?}"
            );
        }
    }

    /// `AnfF2m::{xor, mul, mul_const, reduce}` against the toggles on
    /// coefficients of dozens to hundreds of monomials, with zero
    /// coefficients scattered in, so every per-coefficient sum is well
    /// past `SMALL_SUM` and many products cancel.
    #[test]
    fn review_symbolic_field_ops_on_dense_coefficients() {
        let mut rng = StdRng::seed_from_u64(0x6465_6e73);
        let narrow: Vec<u32> = (0..7).collect();
        let odd: Vec<u32> = vec![0, 1, 2, 3, 65_535, 65_536];
        for round in 0..40 {
            let palette = if round % 4 == 3 { &odd } else { &narrow };
            let n = [3u32, 7, 17, 64, 65][round % 5];
            let irr = random_modulus(&mut rng, n, [0.1, 0.5, 0.9][round % 3]);
            let mk = |rng: &mut StdRng, len: usize| AnfF2m {
                coeffs: (0..len)
                    .map(|_| {
                        if rng.gen_bool(0.25) {
                            AnfPoly::zero()
                        } else {
                            random_anf(rng, palette, 4, 60)
                        }
                    })
                    .collect(),
            };
            let (la, lb) = (rng.gen_range(0..9), rng.gen_range(0..9));
            let a = mk(&mut rng, la);
            let b = mk(&mut rng, lb);
            assert_eq!(a.xor(&b).coeffs, toggle_reference::xor(&a, &b).coeffs);
            let prod = a.mul(&b);
            assert_eq!(prod.coeffs, toggle_reference::f2m_mul(&a, &b).coeffs);
            let bits: Vec<u32> = (0..n).filter(|_| rng.gen_bool(0.5)).collect();
            let c = F2mElement::from_bit_positions(&bits, n);
            assert_eq!(
                prod.mul_const(&c, n).coeffs,
                toggle_reference::mul_const(&prod, &c, n).coeffs,
                "mul_const, n = {n}, round {round}"
            );
            let mut got = prod.clone();
            got.reduce(n, &irr);
            let mut want = prod;
            toggle_reference::reduce(&mut want, n, &irr);
            assert_eq!(got.coeffs, want.coeffs, "reduce, n = {n}, round {round}");
        }
    }

    /// The descent against the toggle reference on a sweep of `(n, l)`
    /// with every `l` from 1 to `n` at small `n`, the perfbench and corpus
    /// widths, and the zero and one targets.
    #[test]
    fn review_weil_descent_sweep() {
        use crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse;
        let mut rng = StdRng::seed_from_u64(0x7377_6570);
        let mut cells: Vec<(u32, u32)> = Vec::new();
        for n in 1..=7 {
            for l in 1..=n {
                cells.push((n, l));
            }
        }
        cells.extend([(13, 5), (17, 4), (17, 6), (19, 6), (23, 8), (31, 5)]);
        for (n, l) in cells {
            let irr = find_irreducible_sparse(n).expect("irreducible");
            let b = F2mElement::one(n);
            let random: Vec<u32> = (0..n).filter(|_| rng.gen_bool(0.5)).collect();
            for x_r in [
                F2mElement::zero(n),
                F2mElement::one(n),
                F2mElement::from_bit_positions(&random, n),
            ] {
                let sys = weil_descend_s4(n, l, &irr, &b, &x_r);
                let (correspondence, semaev) = toggle_reference::weil_descend_s4(n, l, &irr, &x_r);
                assert_eq!(sys.correspondence, correspondence, "n = {n}, l = {l}");
                assert_eq!(sys.semaev, semaev, "n = {n}, l = {l}");
            }
        }
    }
}
