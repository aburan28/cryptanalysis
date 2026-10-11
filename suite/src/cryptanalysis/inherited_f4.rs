//! # Inherited matrix-F4: the reduced Macaulay basis specialised down the splitting tree.
//!
//! The Koblitz decomposition oracle
//! ([`super::koblitz_groebner::solve_boolean_system`]) is a DPLL loop
//! around a Macaulay reduction: at every node it takes the current system,
//! builds the degree-`D` Macaulay matrix from scratch, reduces it, reads
//! off the refutation or the forced variables, and recurses on
//! `v := 0` and `v := 1`.  Every child rebuilds and re-reduces a matrix
//! that is a *specialisation* of the one its parent has just reduced.
//!
//! F5's organising idea is to never redo a reduction the algorithm can
//! predict.  Here the prediction is exact.  Substitution `φ_c : v ↦ c` is a
//! ring homomorphism of the Boolean ring, and the Macaulay rows of the
//! specialised system are the images of the parent's rows:
//!
//! ```text
//!     V(S|_{v=c})  =  φ_c( V(S) )  =  span{ φ_c(ρ) : ρ a reduced row of the parent }
//! ```
//!
//! (up to multipliers that cannot reach the linear tail, and up to a
//! generator whose degree *drops* under `φ_c` gaining multipliers — see
//! [`ReducedBasis::specialise`] for both).  So the child's row space is
//! spanned by the `rank` reduced rows of its parent, specialised — and most
//! of them are already in echelon form:
//!
//! - under `v := 0` every monomial containing `v` is deleted; a row whose
//!   leading monomial does not contain `v` keeps it;
//! - under `v := 1` every monomial `m ∋ v` folds into `m ∖ v`, which is
//!   *smaller* in any degree-compatible order, so again a leading monomial
//!   without `v` survives and cannot be cancelled.
//!
//! Only the rows whose **pivot contains `v`** lose their place and are
//! re-reduced against the rest — about `D/n` of them.  No Macaulay matrix
//! is built below the root, and no reduction is repeated.  Because the
//! row space is the same one the from-scratch step would compute, the
//! linear tail — hence every refutation, forced variable, split and
//! verdict — is identical; only the work per node changes.
//!
//! ## Accounting
//!
//! The stage's unit is 64-bit word XORs in the elimination.  Everything
//! this module does to a packed row is charged in that unit: the root
//! reduction through the shared kernel, every XOR of the re-reduction, and
//! the specialisation itself at one word operation per word read and per
//! word written — a charge the from-scratch path never pays, since its
//! matrix build is not counted.  Rows are stored from their first nonzero
//! word, so a rewrite reads the words from the row's leading word to the
//! end of its layout and writes those from its image's first word to the
//! end of the new one; an XOR has always started at the pivot's leading
//! word.  Wall time is reported beside it.
//!
//! ## What decides the cost: which variable the solver splits on
//!
//! Re-reducing a displaced row costs one XOR per pivot it crosses, so the
//! method's cost is the number of displaced rows times the density of the
//! basis.  Both depend on the **split variable**.  A reduced row's pivot
//! is its largest monomial under DegRevLex, so pivots are biased toward
//! the large variables; splitting on the lowest-indexed free variable (the
//! historical `LowestFree` rule) picks exactly those, and deep in the tree
//! half the basis is displaced per level.  Splitting on the smallest free
//! variable ([`super::koblitz_groebner::SplitRule::HighestFree`]) displaces
//! the fewest rows: the engine's work halves on every quadratic rung and
//! its loss on the chained cubic `m = 3` systems — whose 40%-rank-deficient
//! matrices make the reduced rows dense — turns into a `1.9×` win on the
//! deep `K_0/2^15` cell (`RESEARCH_INHERITED_F4.md` §3.5).  Restoring
//! reduced form after each level, cost-triggered fallbacks and
//! drift-triggered rebuilds were all tried and rejected; each cost more
//! than it saved.
//!
//! ## What this does not change
//!
//! Nothing about the algebra: same degree, same row space, same splitting
//! rule, same node budget.  Nothing about the decomposition oracle's cost
//! at `n = 131`, which is bounded by how many candidate tuples must be
//! ruled out and not by how one node's matrix is reduced.

use crate::cryptanalysis::fx_hash::{FxMap as HashMap, MaskMap};
use crate::cryptanalysis::koblitz_groebner::{
    all_variable_mask, build_inherited_macaulay, build_inherited_macaulay_support_local,
    echelon_f2_counted, macaulay_columns, macaulay_rows_monos_with_mask, monomials_up_to_mask,
    pack_rows, rref_f2_counted,
};
use crate::cryptanalysis::pq_groebner_f2::{cmp_mono, F2BoolMono, F2BoolPoly};
use std::cell::RefCell;
use std::rc::Rc;

/// Degree of a Boolean polynomial (`0` for a constant or zero).
fn poly_degree(p: &F2BoolPoly) -> u32 {
    p.terms
        .iter()
        .map(|t| t.mask.count_ones())
        .max()
        .unwrap_or(0)
}

/// Leading (lowest-index) set column of a packed row.
fn leading_column(row: &[u64]) -> Option<usize> {
    row.iter()
        .enumerate()
        .find(|(_, &w)| w != 0)
        .map(|(i, &w)| i * 64 + w.trailing_zeros() as usize)
}

/// Work counters for one basis operation, all in 64-bit word operations.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct InheritCost {
    /// XORs in the root reduction, in re-reducing displaced rows, and in
    /// restoring reduced form ([`ReducedBasis::reduce_fully`]).
    pub reduce_word_ops: u64,
    /// The part of `reduce_word_ops` spent restoring reduced form.
    pub rref_word_ops: u64,
    /// Word reads and writes performed by specialisation (deleting or
    /// folding the columns of the assigned variable).
    pub specialise_word_ops: u64,
    /// Rows whose pivot contained the assigned variable and were re-reduced.
    pub displaced_rows: u64,
    /// Completion rows added because a generator's degree dropped.
    pub completion_rows: u64,
    /// Products of degree falls inserted by [`ReducedBasis::close`].
    pub closure_products: u64,
}

impl InheritCost {
    /// Everything charged, in word operations.
    pub fn word_ops(&self) -> u64 {
        self.reduce_word_ops + self.specialise_word_ops
    }
    fn add(&mut self, other: InheritCost) {
        self.reduce_word_ops += other.reduce_word_ops;
        self.rref_word_ops += other.rref_word_ops;
        self.specialise_word_ops += other.specialise_word_ops;
        self.displaced_rows += other.displaced_rows;
        self.completion_rows += other.completion_rows;
        self.closure_products += other.closure_products;
    }
}

/// A column a layout step deletes (`v := 0` on a monomial containing `v`).
const DELETED: u32 = u32::MAX;

/// One change of column layout: how the columns of one epoch map to the
/// columns of the next.  [`DELETED`] marks a deleted column (`v := 0`);
/// two columns may map to the same target (`v := 1` folds `m ∋ v` onto
/// `m ∖ v`), and a materialisation XORs them together.
#[derive(Debug)]
struct LayoutStep {
    map: Rc<Vec<u32>>,
    /// Composed maps from earlier epochs to the epoch this step maps *to*,
    /// built on demand.  Shared with every basis below this step, so a
    /// child composes one step on top of what its parent already built.
    to_here: RefCell<HashMap<u32, Rc<Vec<u32>>>>,
}

/// A child's generator system, computed once per node and shared by every
/// basis at it.
#[derive(Debug)]
pub struct ChildSystem {
    system: Rc<Vec<F2BoolPoly>>,
    degrees: Rc<Vec<u32>>,
    /// `(index in the child system, degree before, degree after)` for each
    /// generator whose degree dropped.
    dropped: Vec<(usize, u32, u32)>,
}

/// The column layout after `v := 1` (`bit` is `v`'s): the kept columns
/// and the folded ones `m ∖ v` merged in descending order, a folded column
/// equal to a kept one landing on it; `map` receives old → new.  Deleting
/// the columns holding `v` keeps the rest in order, and folding keeps the
/// folded ones in order among themselves, so this is one linear merge.
///
/// Its comparisons are `cmp_mono`'s popcounts, and the baseline x86-64
/// target has no `popcnt` instruction, so where the CPU has one the same
/// merge runs compiled with it; the layout is identical either way.
fn fold_layout(columns: &[u64], bit: u64, new_columns: &mut Vec<u64>, map: &mut [u32]) {
    #[cfg(target_arch = "x86_64")]
    {
        if std::arch::is_x86_feature_detected!("popcnt") {
            // SAFETY: the feature was just detected on this CPU.
            return unsafe { fold_layout_popcnt(columns, bit, new_columns, map) };
        }
    }
    fold_layout_body(columns, bit, new_columns, map)
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "popcnt")]
unsafe fn fold_layout_popcnt(
    columns: &[u64],
    bit: u64,
    new_columns: &mut Vec<u64>,
    map: &mut [u32],
) {
    fold_layout_body(columns, bit, new_columns, map)
}

#[inline(always)]
fn fold_layout_body(columns: &[u64], bit: u64, new_columns: &mut Vec<u64>, map: &mut [u32]) {
    let n_old = columns.len();
    let (mut i, mut j) = (0usize, 0usize);
    let next_keep = |i: &mut usize| -> Option<usize> {
        while *i < n_old && columns[*i] & bit != 0 {
            *i += 1;
        }
        (*i < n_old).then_some(*i)
    };
    let next_fold = |j: &mut usize| -> Option<usize> {
        while *j < n_old && columns[*j] & bit == 0 {
            *j += 1;
        }
        (*j < n_old).then_some(*j)
    };
    loop {
        let k = next_keep(&mut i);
        let f = next_fold(&mut j);
        let target = new_columns.len() as u32;
        match (k, f) {
            (None, None) => break,
            (Some(k), None) => {
                new_columns.push(columns[k]);
                map[k] = target;
                i += 1;
            }
            (None, Some(f)) => {
                new_columns.push(columns[f] & !bit);
                map[f] = target;
                j += 1;
            }
            (Some(k), Some(f)) => {
                let (mk, mf) = (columns[k], columns[f] & !bit);
                match cmp_mono(F2BoolMono::from_mask(mk), F2BoolMono::from_mask(mf)) {
                    std::cmp::Ordering::Greater => {
                        new_columns.push(mk);
                        map[k] = target;
                        i += 1;
                    }
                    std::cmp::Ordering::Less => {
                        new_columns.push(mf);
                        map[f] = target;
                        j += 1;
                    }
                    std::cmp::Ordering::Equal => {
                        new_columns.push(mk);
                        map[k] = target;
                        map[f] = target;
                        i += 1;
                        j += 1;
                    }
                }
            }
        }
    }
}

impl ChildSystem {
    /// [`ChildSystem::new`] taking the substituted system by value, so the
    /// generators move instead of being cloned; the solver reads the
    /// child's system back through [`ChildSystem::system`].
    ///
    /// The generators must be in canonical order, as
    /// [`F2BoolPoly::substitute`] returns them: descending, so degree
    /// first, and a generator's degree is its first term's.
    pub(crate) fn from_owned(parent_degrees: &[u32], substituted: Vec<F2BoolPoly>) -> Self {
        debug_assert_eq!(parent_degrees.len(), substituted.len());
        let mut system = Vec::with_capacity(substituted.len());
        let mut degrees = Vec::with_capacity(substituted.len());
        let mut dropped = Vec::new();
        for (q, &old_degree) in substituted.into_iter().zip(parent_degrees) {
            if q.is_zero() {
                continue;
            }
            let new_degree = q.terms[0].degree();
            debug_assert_eq!(new_degree, poly_degree(&q), "canonical input");
            if new_degree != 0 && new_degree < old_degree {
                dropped.push((system.len(), old_degree, new_degree));
            }
            system.push(q);
            degrees.push(new_degree);
        }
        Self {
            system: Rc::new(system),
            degrees: Rc::new(degrees),
            dropped,
        }
    }

    /// The child's generators: the substituted system without its zeros.
    pub fn system(&self) -> &Rc<Vec<F2BoolPoly>> {
        &self.system
    }

    /// Whether some generator's degree dropped, so specialising a basis
    /// into this child would insert completion rows.
    pub fn has_dropped(&self) -> bool {
        !self.dropped.is_empty()
    }

    /// The child of a system whose generators have degrees
    /// `parent_degrees`, given `substituted[i]` — the image of the parent's
    /// `i`-th generator, zero or not.
    pub fn new(parent_degrees: &[u32], substituted: &[F2BoolPoly]) -> Self {
        debug_assert_eq!(parent_degrees.len(), substituted.len());
        let mut system = Vec::with_capacity(substituted.len());
        let mut degrees = Vec::with_capacity(substituted.len());
        let mut dropped = Vec::new();
        for (q, &old_degree) in substituted.iter().zip(parent_degrees) {
            if q.is_zero() {
                continue;
            }
            let new_degree = poly_degree(q);
            if new_degree != 0 && new_degree < old_degree {
                dropped.push((system.len(), old_degree, new_degree));
            }
            system.push(q.clone());
            degrees.push(new_degree);
        }
        Self {
            system: Rc::new(system),
            degrees: Rc::new(degrees),
            dropped,
        }
    }
}

/// A basis row: its content, valid in the layout of epoch `version`.
///
/// Rows are shared by reference between a basis and the children
/// specialised from it; a row is rewritten into a newer layout — and
/// charged for it — only when something needs its content there.
///
/// **Trimmed.**  A row is stored from the word it starts in to the end of
/// its layout.  An echelon row is zero before its leading column, and the
/// rows the tree rewrites most lead far to the right — a displaced row's
/// image falls towards the tail, and so do the pivots it hits — so the
/// words before `lead` are neither stored, read nor written, as the
/// elimination's XORs have never touched a pivot's words before its
/// leading column either.
#[derive(Clone, Debug)]
struct LazyRow {
    version: u32,
    /// The layout word `data[0]` holds.
    start: u32,
    /// The first word that can be nonzero (`≥ start`); a rewrite reads
    /// from here.
    lead: u32,
    /// Words `start ..` to the end of the layout of `version`.
    data: Rc<[u64]>,
}

impl LazyRow {
    /// Word `w` of the row in its own layout.
    fn word(&self, w: usize) -> u64 {
        if w < self.lead as usize {
            0
        } else {
            self.data[w - self.start as usize]
        }
    }

    /// The words from `w` (at least `lead`) to the end of the layout.
    fn words_from(&self, w: usize) -> &[u64] {
        debug_assert!(w >= self.lead as usize);
        &self.data[w - self.start as usize..]
    }

    /// The words a rewrite reads.
    fn live(&self) -> &[u64] {
        self.words_from(self.lead as usize)
    }
}

/// A row being reduced into a basis: words `start ..` to the end of the
/// current layout.
struct Draft {
    start: usize,
    data: Vec<u64>,
}

impl Draft {
    /// A full-width row.
    fn full(data: Vec<u64>) -> Self {
        Self { start: 0, data }
    }

    /// Leading set column at or after word `from` (a layout word).
    fn leading_column_from(&self, from: usize) -> Option<usize> {
        self.data[from - self.start..]
            .iter()
            .position(|&w| w != 0)
            .map(|i| {
                let w = from + i;
                w * 64 + self.data[w - self.start].trailing_zeros() as usize
            })
    }
}

thread_local! {
    /// Full-width staging for [`ReducedBasis::rewrite`], zero between uses.
    static STAGING: RefCell<Vec<u64>> = const { RefCell::new(Vec::new()) };
}

/// The reduced degree-`degree` Macaulay row space of a system, kept as an
/// echelon basis with distinct leading monomials, together with the
/// system it belongs to.
///
/// **Lazy materialisation.**  Only a fraction of the rows a level keeps
/// are ever touched at that level — displaced, hit as a pivot while a
/// displaced row reduces, or read for the tail; on `K_1/2^23` three
/// quarters are not.  So a kept row is not rewritten into the child's
/// layout: the child shares the parent's row by reference and records
/// the layout step, and a row is materialised only when needed, through
/// the composition of every step since it was last written, in one pass
/// charged once.  Its pivot column is tracked through the steps meanwhile,
/// which is all `specialise` needs to decide whether it stays a pivot.
#[derive(Clone, Debug)]
pub struct ReducedBasis {
    /// Macaulay degree.
    pub degree: u32,
    /// Number of Boolean variables of the ambient ring.
    pub n_vars: usize,
    /// The system whose Macaulay row space this is.
    pub system: Rc<Vec<F2BoolPoly>>,
    /// Degree of each generator when the basis was last completed.
    generator_degrees: Rc<Vec<u32>>,
    /// Variables specialised away on the path from the root.
    assigned: u64,
    /// Column monomials of the current layout, in descending order.
    columns: Vec<u64>,
    /// Monomial → column, built only when a row has to be packed from
    /// monomials (completion), which most levels never do.
    column_index: Option<MaskMap<usize>>,
    words: usize,
    /// Layout steps since the root: `history[e]` maps epoch `e` to `e + 1`.
    /// The current epoch is `history.len()`.
    history: Vec<Rc<LayoutStep>>,
    /// Echelon rows; every row is nonzero and their leading columns are
    /// pairwise distinct.
    rows: Vec<LazyRow>,
    /// `pivot_col[r]` is row `r`'s leading column in the current layout.
    pivot_col: Vec<u32>,
    /// `pivot_of[c]` is the row leading at column `c`.
    pivot_of: Vec<Option<u32>>,
    /// Rounds of degree-fall closure run per node; `0` keeps the plain
    /// Macaulay row space (see [`ReducedBasis::from_system_closed`]).
    closure_rounds: u32,
    /// Degree falls not yet multiplied by the variables, as row indices.
    pending: Vec<u32>,
    /// The row space contains the constant `1`.  The basis is then kept as
    /// that one row: every specialisation of `1` is `1`, and the solver
    /// reads nothing past it (see [`ReducedBasis::specialise_shared`]).
    refuted: bool,
    /// Multiply each generator only by the variables in its own support,
    /// at the root and in completion rows, instead of by every variable
    /// occurring in the system ([`ReducedBasis::from_system_with`]).
    /// Inherited by every basis specialised from this one.
    support_local: bool,
}

impl ReducedBasis {
    /// Build and reduce the Macaulay matrix of `system` at `degree` from
    /// scratch — the root of a splitting tree, or any node whose parent had
    /// no basis.  Multipliers range over the variables occurring in the
    /// system, the from-scratch step's own active-multiplier policy: a
    /// multiplier containing a variable that occurs nowhere adds rows that
    /// cannot reach the linear tail (see [`ReducedBasis::specialise`]).
    /// `None` if the matrix exceeds the F4 size caps.
    pub fn from_system(
        system: &[F2BoolPoly],
        n_vars: usize,
        degree: u32,
    ) -> Option<(Self, InheritCost)> {
        Self::from_system_with(system, n_vars, degree, false)
    }

    /// [`ReducedBasis::from_system`] with a choice of multipliers.  With
    /// `support_local`, generator `f` is multiplied only by monomials in the
    /// variables of its own support, so the row space is spanned by
    /// `{t·f : t ⊆ supp(f), deg t·f ≤ degree}` — a subspace of the
    /// occurring-variable one, so every consequence it yields is still in
    /// the ideal and the splitting solver still decides every target
    /// exactly; it may read a weaker tail at a node.  The policy is kept by
    /// every specialisation, whose completion rows follow it too.  On a
    /// chain in the interleaved order it drops the products of the last
    /// link by the first summands' variables, which the tail never used
    /// (`RESEARCH_SUPPORT_LOCAL_MULTIPLIERS.md`).
    pub fn from_system_with(
        system: &[F2BoolPoly],
        n_vars: usize,
        degree: u32,
        support_local: bool,
    ) -> Option<(Self, InheritCost)> {
        let system: Rc<Vec<F2BoolPoly>> =
            Rc::new(system.iter().filter(|p| !p.is_zero()).cloned().collect());
        let generator_degrees: Rc<Vec<u32>> = Rc::new(system.iter().map(poly_degree).collect());
        let quadratic_generators = generator_degrees.iter().all(|&degree| degree <= 2);
        let occurring = system
            .iter()
            .flat_map(|p| p.terms.iter())
            .fold(0u64, |acc, t| acc | t.mask)
            & all_variable_mask(n_vars);
        let (columns, mut matrix) = if support_local {
            build_inherited_macaulay_support_local(
                system.as_slice(),
                n_vars,
                degree,
                occurring,
                quadratic_generators,
            )?
        } else {
            build_inherited_macaulay(
                system.as_slice(),
                n_vars,
                degree,
                occurring,
                quadratic_generators,
            )?
        };
        let mut cost = InheritCost::default();
        let empty = |columns: Vec<u64>| Self {
            degree,
            n_vars,
            system: system.clone(),
            generator_degrees: generator_degrees.clone(),
            assigned: 0,
            column_index: None,
            words: columns.len().div_ceil(64).max(1),
            pivot_of: vec![None; columns.len()],
            columns,
            history: Vec::new(),
            rows: Vec::new(),
            pivot_col: Vec::new(),
            closure_rounds: 0,
            pending: Vec::new(),
            refuted: false,
            support_local,
        };
        if matrix.is_empty() {
            return Some((empty(Vec::new()), cost));
        }
        // A basis needs distinct leading columns and nothing more, so the
        // root is reduced to echelon form without back-substitution.  A
        // fully reduced root makes every later displaced row reduce in as
        // many XORs as it has pivot bits, and below 24 variables that paid
        // for its back-substitution while every child re-reduced all of its
        // displaced rows.  Now that a refuted child stops at its refutation
        // and a rewrite skips a row's leading zeros, the children no longer
        // earn it back on any rung (`RESEARCH_INHERITED_F4.md` §3.1).  A
        // middle ground, clearing only the pivot columns of degree below
        // `D`, was tried and costs what it saves.
        // `KIC_F4_INHERIT_ROOT=rref` restores the fully reduced root as a
        // control.
        static ROOT_POLICY: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        let full = *ROOT_POLICY
            .get_or_init(|| std::env::var("KIC_F4_INHERIT_ROOT").as_deref() == Ok("rref"));
        let rank = if full {
            rref_f2_counted(&mut matrix, columns.len(), &mut cost.reduce_word_ops)
        } else {
            echelon_f2_counted(&mut matrix, columns.len(), &mut cost.reduce_word_ops)
        };
        matrix.truncate(rank);
        let mut out = empty(columns);
        for row in matrix {
            let c = leading_column(&row).expect("rank rows are nonzero");
            debug_assert!(out.pivot_of[c].is_none());
            out.pivot_of[c] = Some(out.rows.len() as u32);
            out.pivot_col.push(c as u32);
            out.rows.push(LazyRow {
                version: 0,
                start: 0,
                lead: (c / 64) as u32,
                data: row.into(),
            });
        }
        if let Some(r) = out.one_row() {
            out.collapse_to_one(r);
        }
        Some((out, cost))
    }

    /// The row leading at the constant monomial, if the row space has one.
    /// `1` is the smallest monomial of any degree-compatible order, so it
    /// can only be the last column.
    fn one_row(&self) -> Option<usize> {
        if self.columns.last() != Some(&0) {
            return None;
        }
        self.pivot_of.last().copied().flatten().map(|r| r as usize)
    }

    /// Reduce the basis to its row `r`, which is the constant `1`.
    fn collapse_to_one(&mut self, r: usize) {
        debug_assert_eq!(self.columns[self.pivot_col[r] as usize], 0);
        let row = self.rows.swap_remove(r);
        let c = self.pivot_col[r];
        self.rows = vec![row];
        self.pivot_col = vec![c];
        self.pivot_of = vec![None; self.columns.len()];
        self.pivot_of[c as usize] = Some(0);
        self.column_index = None;
        self.pending.clear();
        self.refuted = true;
    }

    /// Monomial → current column, built on first use after a layout change.
    fn column_index(&mut self) -> &MaskMap<usize> {
        if self.column_index.is_none() {
            self.column_index = Some(
                self.columns
                    .iter()
                    .enumerate()
                    .map(|(i, &m)| (m, i))
                    .collect(),
            );
        }
        self.column_index.as_ref().expect("just built")
    }

    /// [`ReducedBasis::from_system`], closed under multiplying degree falls
    /// by monomials for `rounds` rounds at this node and at every node
    /// specialised from it (see [`ReducedBasis::close`]).  The falls seeded
    /// at the root are the rows whose leading monomial has degree in
    /// `[2, degree)` and is not a leading monomial of the degree-`degree−1`
    /// Macaulay row space: a row of that space times a monomial of degree
    /// one is already a row of the degree-`degree` matrix.
    pub fn from_system_closed(
        system: &[F2BoolPoly],
        n_vars: usize,
        degree: u32,
        rounds: u32,
    ) -> Option<(Self, InheritCost)> {
        Self::from_system_closed_with(system, n_vars, degree, rounds, false)
    }

    /// [`ReducedBasis::from_system_closed`] with the multiplier choice of
    /// [`ReducedBasis::from_system_with`].
    pub fn from_system_closed_with(
        system: &[F2BoolPoly],
        n_vars: usize,
        degree: u32,
        rounds: u32,
        support_local: bool,
    ) -> Option<(Self, InheritCost)> {
        let (mut basis, mut cost) = Self::from_system_with(system, n_vars, degree, support_local)?;
        if rounds == 0 || degree < 3 || basis.rows.is_empty() || basis.refuted {
            return Some((basis, cost));
        }
        basis.closure_rounds = rounds;
        let occurring = basis
            .system
            .iter()
            .flat_map(|p| p.terms.iter())
            .fold(0u64, |acc, t| acc | t.mask)
            & all_variable_mask(n_vars);
        let lower = macaulay_rows_monos_with_mask(
            basis.system.as_slice(),
            n_vars,
            degree - 1,
            occurring,
            None,
        )?;
        let mut lower_leading: std::collections::HashSet<u64> = std::collections::HashSet::new();
        if !lower.is_empty() {
            let columns = macaulay_columns(&lower)?;
            let mut matrix = pack_rows(&lower, &columns);
            let rank = echelon_f2_counted(&mut matrix, columns.len(), &mut cost.reduce_word_ops);
            for row in matrix.iter().take(rank) {
                if let Some(c) = leading_column(row) {
                    lower_leading.insert(columns[c]);
                }
            }
        }
        for r in 0..basis.rows.len() {
            let lead = basis.columns[basis.pivot_col[r] as usize];
            if basis.is_fall(r) && !lower_leading.contains(&lead) {
                basis.pending.push(r as u32);
            }
        }
        basis.close(&mut cost);
        Some((basis, cost))
    }

    /// Whether this basis multiplies generators only within their supports
    /// ([`ReducedBasis::from_system_with`]).
    pub fn support_local(&self) -> bool {
        self.support_local
    }

    /// Variables specialised away since the root, as a mask.
    pub fn assigned(&self) -> u64 {
        self.assigned
    }

    /// Rank of the row space.
    pub fn rank(&self) -> usize {
        self.rows.len()
    }

    /// Number of columns.
    pub fn columns(&self) -> usize {
        self.columns.len()
    }

    /// Depth of this basis below its root: the number of variables
    /// specialised away.
    pub fn depth(&self) -> u32 {
        self.assigned.count_ones()
    }

    /// The current epoch: the number of layout steps since the root.
    fn epoch(&self) -> u32 {
        self.history.len() as u32
    }

    /// Index of the first column of degree `≤ 1` (the linear tail).
    fn low_start(&self) -> usize {
        self.columns
            .iter()
            .position(|m| m.count_ones() <= 1)
            .unwrap_or(self.columns.len())
    }

    /// The composed map from the columns of epoch `from` to those of epoch
    /// `to`.  Memoised on the step that maps into `to`, which every basis
    /// below that step shares, so a node composes at most one step on top
    /// of what its ancestors already built.  Index bookkeeping, not
    /// charged, as the from-scratch path's column indexing never was.
    fn composite_to(&self, to: u32, from: u32) -> Rc<Vec<u32>> {
        debug_assert!(from < to);
        let step = &self.history[(to - 1) as usize];
        if from + 1 == to {
            return step.map.clone();
        }
        if let Some(c) = step.to_here.borrow().get(&from) {
            return c.clone();
        }
        let prev = self.composite_to(to - 1, from);
        // `DELETED` is `u32::MAX`, out of range of every map, so `get`
        // sends it (and only it) to `DELETED` without a separate test
        let map = &step.map[..];
        // an `Rc<Vec>` takes the collected buffer as it is; an `Rc<[_]>`
        // would copy it into a fresh allocation
        let composed: Rc<Vec<u32>> = Rc::new(
            prev.iter()
                .map(|&c| map.get(c as usize).copied().unwrap_or(DELETED))
                .collect(),
        );
        step.to_here.borrow_mut().insert(from, composed.clone());
        composed
    }

    /// The composed map from the columns of epoch `from` to the current
    /// layout.
    fn composite(&self, from: u32) -> Rc<Vec<u32>> {
        self.composite_to(self.epoch(), from)
    }

    /// Rewrite `row` from the layout of epoch `version` into the current
    /// one, trimmed to the first word its image touches; `None` if every
    /// bit was deleted or the folds cancelled it.  Charged one word
    /// operation per word read (from the row's `lead`) and per word
    /// written (from the image's first word to the end of the layout).
    fn rewrite(&self, row: &LazyRow, cost: &mut InheritCost) -> Option<Draft> {
        self.rewrite_with(row, cost, |image, start| Draft {
            start,
            data: image.to_vec(),
        })
    }

    /// [`ReducedBasis::rewrite`] into a shared row, for an image that is
    /// only read afterwards: one allocation, no zero fill.
    fn rewrite_frozen(&self, row: &LazyRow, cost: &mut InheritCost) -> Option<(usize, Rc<[u64]>)> {
        self.rewrite_with(row, cost, |image, start| (start, Rc::from(image)))
    }

    /// The rewrite itself; `finish` receives the image's words from its
    /// first nonzero word `start` to the end of the layout.
    fn rewrite_with<T>(
        &self,
        row: &LazyRow,
        cost: &mut InheritCost,
        finish: impl FnOnce(&[u64], usize) -> T,
    ) -> Option<T> {
        debug_assert!(row.version < self.epoch());
        let map = self.composite(row.version);
        let words = self.words;
        let live = row.live();
        let lead = row.lead as usize;
        cost.specialise_word_ops += live.len() as u64;
        STAGING.with(|staging| {
            let mut staging = staging.borrow_mut();
            if staging.len() < words {
                staging.resize(words, 0);
            }
            let staging = &mut staging[..words];
            let mut lo = usize::MAX;
            let mut scatter = |c: u32| {
                if c != DELETED {
                    let w = c as usize / 64;
                    staging[w] ^= 1u64 << (c % 64);
                    lo = lo.min(w);
                }
            };
            for (i, &word) in live.iter().enumerate() {
                let base = (lead + i) * 64;
                let mut bits = word;
                // A whole word of the map at once, so the lookups below
                // need no bounds check; only a layout's last word is short.
                if let Some(chunk) = map.get(base..base + 64) {
                    let chunk: &[u32; 64] = chunk.try_into().expect("64 entries");
                    while bits != 0 {
                        let b = bits.trailing_zeros() as usize & 63;
                        bits &= bits - 1;
                        scatter(chunk[b]);
                    }
                } else {
                    while bits != 0 {
                        let b = bits.trailing_zeros() as usize;
                        bits &= bits - 1;
                        scatter(map[base + b]);
                    }
                }
            }
            if lo == usize::MAX {
                return None;
            }
            cost.specialise_word_ops += (words - lo) as u64;
            // staging is zero below `lo`, so its tail is the image
            let image = &mut staging[lo..];
            let nonzero = image.iter().any(|&w| w != 0);
            let out = nonzero.then(|| finish(image, lo));
            image.fill(0);
            out
        })
    }

    /// Bring row `r` into the current layout if it is not there yet.  A
    /// kept row's leading monomial survives every step, so its image is
    /// nonzero.
    fn ensure_current(&mut self, r: usize, cost: &mut InheritCost) {
        if self.rows[r].version != self.epoch() {
            let (start, data) = self
                .rewrite_frozen(&self.rows[r], cost)
                .expect("a kept pivot survives");
            let lead = start + data.iter().position(|&w| w != 0).expect("nonzero");
            self.rows[r] = LazyRow {
                version: self.epoch(),
                start: start as u32,
                lead: lead as u32,
                data,
            };
        }
    }

    /// Bring every row into the current layout.
    pub fn materialise_all(&mut self, cost: &mut InheritCost) {
        for r in 0..self.rows.len() {
            self.ensure_current(r, cost);
        }
    }

    /// Row `r` in the current layout, materialising it if needed.
    fn current_row(&mut self, r: usize, cost: &mut InheritCost) -> LazyRow {
        self.ensure_current(r, cost);
        self.rows[r].clone()
    }

    /// Restore reduced row echelon form: clear every pivot column from
    /// every row but its own.
    ///
    /// One pass in **decreasing** pivot-column order suffices.  A row's
    /// bits all sit at or after its leading column, so when pivot column
    /// `c` is processed every pivot column beyond `c` has already been
    /// cleared from its row, and XORing it into another row introduces no
    /// pivot-column bit.  Only XORs are charged, as in the from-scratch
    /// kernels; the pivot-column tests are not.
    ///
    /// Why it is worth paying: after a specialisation the basis is in
    /// echelon form but not reduced — a fold `m ∋ v ↦ m ∖ v` can land on
    /// another row's pivot column, and a freshly inserted pivot has never
    /// been cleared from the rows above it.  A displaced row reduced
    /// against such a basis picks up those bits and cascades; against a
    /// reduced basis it clears one pivot column per XOR and stops.
    pub fn reduce_fully(&mut self, cost: &mut InheritCost) {
        if self.refuted {
            return;
        }
        self.materialise_all(cost);
        let words = self.words;
        let epoch = self.epoch();
        for c in (0..self.pivot_of.len()).rev() {
            let Some(r) = self.pivot_of[c] else {
                continue;
            };
            let r = r as usize;
            let (w, bit) = (c / 64, 1u64 << (c % 64));
            let pivot = self.rows[r].clone();
            for (i, row) in self.rows.iter_mut().enumerate() {
                if i != r && row.word(w) & bit != 0 {
                    let mut data = row.data.to_vec();
                    let at = w - row.start as usize;
                    for (dst, &src) in data[at..].iter_mut().zip(pivot.words_from(w)) {
                        *dst ^= src;
                    }
                    *row = LazyRow {
                        version: epoch,
                        start: row.start,
                        lead: row.lead,
                        data: data.into(),
                    };
                    cost.reduce_word_ops += (words - w) as u64;
                    cost.rref_word_ops += (words - w) as u64;
                }
            }
        }
    }

    /// Should a basis at `depth` be restored to reduced form after its
    /// specialisation?  `KIC_F4_INHERIT_RREF` names the policy: `0` never
    /// (the default), `k ≥ 1` every `k` levels.
    ///
    /// A retained negative control.  Restoring reduced form does cut the
    /// cascade — on `K_1/2^23` a displaced row then hits `9.8` pivots
    /// instead of `40.5` — but the pass itself costs `72 M` word XORs
    /// against the `49 M` it saves, because a reduced basis is *denser*
    /// than an echelon one and every specialisation refills some twenty
    /// pivot columns per row (`RESEARCH_INHERITED_F4.md` §3.5).
    fn rref_every() -> u32 {
        static EVERY: std::sync::OnceLock<u32> = std::sync::OnceLock::new();
        *EVERY.get_or_init(|| {
            std::env::var("KIC_F4_INHERIT_RREF")
                .ok()
                .and_then(|v| v.parse::<u32>().ok())
                .unwrap_or(0)
        })
    }

    /// Insert a row given in the current layout, reducing its leading term
    /// against the existing pivots until it becomes a new pivot or vanishes.
    /// Every pivot it hits is materialised first.
    fn insert(&mut self, mut row: Draft, cost: &mut InheritCost) -> Option<usize> {
        let mut from = row.start;
        loop {
            let c = row.leading_column_from(from)?;
            let w = c / 64;
            match self.pivot_of[c] {
                Some(r) => {
                    // materialise, then borrow: no row handle to clone
                    self.ensure_current(r as usize, cost);
                    let pivot = &self.rows[r as usize];
                    let at = w - row.start;
                    for (dst, &src) in row.data[at..].iter_mut().zip(pivot.words_from(w)) {
                        *dst ^= src;
                    }
                    cost.reduce_word_ops += (self.words - w) as u64;
                    from = w;
                }
                None => {
                    self.pivot_of[c] = Some(self.rows.len() as u32);
                    self.pivot_col.push(c as u32);
                    self.rows.push(LazyRow {
                        version: self.epoch(),
                        start: row.start as u32,
                        lead: w as u32,
                        data: row.data.into(),
                    });
                    return Some(self.rows.len() - 1);
                }
            }
        }
    }

    /// Did the row just inserted land on the constant `1`?  If so, collapse
    /// the basis to it.
    fn refutes(&mut self, inserted: Option<usize>) -> bool {
        match inserted {
            Some(r) if self.columns[self.pivot_col[r] as usize] == 0 => {
                self.collapse_to_one(r);
                true
            }
            _ => false,
        }
    }

    /// Adopt a new column layout: record the step, remap every pivot
    /// column and rebuild the pivot index.  Rows are left where they are.
    fn adopt_layout(&mut self, columns: Vec<u64>, map: Vec<u32>) {
        let step = LayoutStep {
            map: Rc::new(map),
            to_here: RefCell::new(HashMap::default()),
        };
        self.column_index = None;
        self.words = columns.len().div_ceil(64).max(1);
        self.pivot_of = vec![None; columns.len()];
        for (r, pc) in self.pivot_col.iter_mut().enumerate() {
            let c = step.map[*pc as usize];
            debug_assert!(c != DELETED, "a kept pivot column survives the step");
            debug_assert!(self.pivot_of[c as usize].is_none(), "row {r} collides");
            self.pivot_of[c as usize] = Some(r as u32);
            *pc = c;
        }
        self.columns = columns;
        self.history.push(Rc::new(step));
    }

    /// The basis of `system|_{var = value}`: the kept rows shared by
    /// reference, the displaced ones materialised and re-reduced, plus
    /// completion rows for any generator whose degree dropped.
    ///
    /// **Completion.**  The Macaulay matrix multiplies `f_i` by every
    /// monomial of degree `≤ D − deg f_i`.  If `deg f_i|_{v=c} < deg f_i`,
    /// the specialised system has multipliers of higher degree that no
    /// parent row maps to; those products are built and inserted, with
    /// multipliers over the variables occurring in the specialised system.
    ///
    /// **Which row space, exactly.**  Write `V_M(S)` for the Macaulay row
    /// space of `S` with multipliers over the variable set `M`.  The
    /// inherited rows span `V_{unassigned}` for the generators whose degree
    /// did not drop and the completion adds `V_{occurring}` for the rest,
    /// so the basis lies between `V_{occurring}(S')` and `V_{all}(S')`, the
    /// latter being what the from-scratch step reduces.  Every space in
    /// that sandwich has the **same linear tail**: a row `x·g` with `x`
    /// occurring in no generator lies in the tail only if `g ∈ {0, 1}`,
    /// and `g = 1` is already a refutation.  The solver reads nothing but
    /// the tail, so it behaves identically.
    pub fn specialise(&self, var: u32, value: bool) -> (Self, InheritCost) {
        let substituted: Vec<F2BoolPoly> = self
            .system
            .iter()
            .map(|p| substitute(p, var, value))
            .collect();
        let child = ChildSystem::new(&self.generator_degrees, &substituted);
        self.specialise_shared(var, value, &child)
    }

    /// The generator degrees this basis was completed for, aligned with
    /// [`ReducedBasis::system`].
    pub fn generator_degrees(&self) -> &[u32] {
        &self.generator_degrees
    }

    /// [`ReducedBasis::specialise`] with the child's system already
    /// computed — by the solver, which substitutes it anyway, once for
    /// every basis at the node.  `child` must be the image of this basis's
    /// own system under `var := value`.
    ///
    /// **Refutation.**  Once a re-reduced or completion row lands on the
    /// constant `1`, the child's tail is a refutation whatever the rows not
    /// yet inserted would add, so they are not inserted: the child is
    /// collapsed to `1` and returned.  Its row space is then no longer the
    /// sandwich above, but the solver's view of it is — every space in the
    /// sandwich contains `1`, the solver refutes on `1` before reading
    /// anything else, and a specialisation of `1` is `1`, so a refuted
    /// basis stays refuted, at no cost, through whatever the solver still
    /// assigns before it reads this degree.
    pub fn specialise_shared(
        &self,
        var: u32,
        value: bool,
        child: &ChildSystem,
    ) -> (Self, InheritCost) {
        let mut cost = InheritCost::default();
        let bit = 1u64 << var;
        if self.refuted {
            let mut out = self.clone();
            out.system = child.system.clone();
            out.generator_degrees = child.degrees.clone();
            out.assigned |= bit;
            return (out, cost);
        }
        let dropped: Vec<(usize, u32, u32)> = child
            .dropped
            .iter()
            .copied()
            .filter(|&(_, old_degree, _)| old_degree <= self.degree)
            .collect();

        // New column layout: the images of the old columns.  Deleting the
        // columns that contain `v` keeps the rest in order; folding
        // `m ∋ v ↦ m ∖ v` keeps the folded ones in order among themselves
        // (every degree drops by one, and the symmetric difference of two
        // of them is unchanged), so the new layout is a merge of two sorted
        // lists and the old → new map falls out of the merge.
        let n_old = self.columns.len();
        let mut map: Vec<u32> = vec![DELETED; n_old];
        let mut new_columns: Vec<u64> = Vec::with_capacity(n_old);
        if value {
            fold_layout(&self.columns, bit, &mut new_columns, &mut map);
        } else {
            for (k, &m) in self.columns.iter().enumerate() {
                if m & bit == 0 {
                    map[k] = new_columns.len() as u32;
                    new_columns.push(m);
                }
            }
        }
        debug_assert!(new_columns.windows(2).all(|w| {
            cmp_mono(F2BoolMono::from_mask(w[0]), F2BoolMono::from_mask(w[1]))
                == std::cmp::Ordering::Greater
        }));

        // The child starts as a copy of the parent's bookkeeping — rows by
        // reference — minus the displaced rows, then adopts the new layout.
        let mut out = Self {
            degree: self.degree,
            n_vars: self.n_vars,
            system: child.system.clone(),
            generator_degrees: child.degrees.clone(),
            assigned: self.assigned | bit,
            // Set by `adopt_layout` below; the split reads the parent's.
            columns: Vec::new(),
            column_index: None,
            words: self.words,
            history: self.history.clone(),
            rows: Vec::with_capacity(self.rows.len()),
            pivot_col: Vec::with_capacity(self.rows.len()),
            pivot_of: Vec::new(),
            closure_rounds: self.closure_rounds,
            pending: Vec::new(),
            refuted: false,
            support_local: self.support_local,
        };
        // Kept rows are renumbered; a pending fall that is kept stays pending.
        let mut is_pending = Vec::new();
        if !self.pending.is_empty() {
            is_pending = vec![false; self.rows.len()];
            for &r in &self.pending {
                is_pending[r as usize] = true;
            }
        }
        let mut displaced: Vec<(u32, LazyRow)> = Vec::new();
        for (r, (row, &pc)) in self.rows.iter().zip(&self.pivot_col).enumerate() {
            if self.columns[pc as usize] & bit == 0 {
                // Leading monomial survives and stays distinct; the row's
                // content is not needed here.
                if is_pending.get(r) == Some(&true) {
                    out.pending.push(out.rows.len() as u32);
                }
                out.rows.push(row.clone());
                out.pivot_col.push(pc);
            } else {
                displaced.push((pc, row.clone()));
            }
        }
        out.adopt_layout(new_columns, map);
        cost.displaced_rows = displaced.len() as u64;
        // Lowest pivot first.  The order changes neither the child's row
        // space nor, measurably, the cost of building it; it changes how
        // soon a refutation is found.  A row pivoting near the tail has
        // its image there too, next to the constant `1`, and inserted
        // first those rows reach `1` before the ones that re-reduce through
        // the whole basis are touched (`RESEARCH_INHERITED_F4.md` §3.7).
        displaced.sort_unstable_by_key(|&(pc, _)| std::cmp::Reverse(pc));
        for (_, row) in displaced {
            if let Some(image) = out.rewrite(&row, &mut cost) {
                let inserted = out.insert(image, &mut cost);
                if out.refutes(inserted) {
                    return (out, cost);
                }
                out.note_fall(inserted);
            }
        }

        // Completion rows for generators whose degree dropped, with
        // multipliers over the variables occurring in the specialised
        // system (the from-scratch step's own active-multiplier policy):
        // a multiplier containing a variable that occurs nowhere adds only
        // rows `x·g` that cannot reach the linear tail.  A support-local
        // basis multiplies each dropped generator only within its own
        // support, as its root did.
        if !dropped.is_empty() {
            let multiplier_mask = out
                .system
                .iter()
                .flat_map(|p| p.terms.iter())
                .fold(0u64, |acc, t| acc | t.mask)
                & all_variable_mask(out.n_vars);
            let mut completion: Vec<Vec<u64>> = Vec::new();
            for &(index, old_degree, new_degree) in &dropped {
                let p = &out.system[index];
                let old_gap = self.degree - old_degree;
                let new_gap = self.degree - new_degree;
                let mask = if self.support_local {
                    multiplier_mask & p.terms.iter().fold(0u64, |acc, t| acc | t.mask)
                } else {
                    multiplier_mask
                };
                for t in monomials_up_to_mask(mask, new_gap) {
                    if t.count_ones() <= old_gap {
                        continue;
                    }
                    let mut monos: Vec<u64> = p.terms.iter().map(|m| m.mask | t).collect();
                    monos.sort_unstable();
                    let mut row_monos = Vec::with_capacity(monos.len());
                    let mut i = 0;
                    while i < monos.len() {
                        let mut j = i;
                        while j < monos.len() && monos[j] == monos[i] {
                            j += 1;
                        }
                        if (j - i) % 2 == 1 {
                            row_monos.push(monos[i]);
                        }
                        i = j;
                    }
                    if !row_monos.is_empty() {
                        completion.push(row_monos);
                    }
                }
            }
            if !completion.is_empty() {
                out.extend_columns(&completion);
                cost.completion_rows = completion.len() as u64;
                for monos in completion {
                    let words = out.words;
                    let index = out.column_index();
                    let mut row = vec![0u64; words];
                    for m in monos {
                        let c = index[&m];
                        row[c / 64] |= 1u64 << (c % 64);
                    }
                    let inserted = out.insert(Draft::full(row), &mut cost);
                    if out.refutes(inserted) {
                        return (out, cost);
                    }
                    out.note_fall(inserted);
                }
            }
        }
        if Self::close_children() {
            out.close(&mut cost);
        } else {
            out.pending.clear();
        }
        let every = Self::rref_every();
        if every > 0 && out.depth().is_multiple_of(every) {
            out.reduce_fully(&mut cost);
        }
        (out, cost)
    }

    /// Does a closed basis keep closing below its root?
    /// `KIC_F4_CLOSURE_CHILDREN=0` confines the closure to the bases built
    /// from scratch; any other value, or none, closes every specialisation
    /// too.  Irrelevant unless `KIC_F4_CLOSURE_ROUNDS` is positive.
    fn close_children() -> bool {
        static CHILDREN: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        *CHILDREN.get_or_init(|| std::env::var("KIC_F4_CLOSURE_CHILDREN").as_deref() != Ok("0"))
    }

    /// Is row `r` a degree fall this basis closes — leading degree at
    /// least 2 and below the Macaulay degree?
    fn is_fall(&self, r: usize) -> bool {
        if self.closure_rounds == 0 {
            return false;
        }
        let d = self.columns[self.pivot_col[r] as usize].count_ones();
        d >= 2 && d < self.degree
    }

    /// Queue a freshly inserted row for closure if it is a degree fall.
    fn note_fall(&mut self, inserted: Option<usize>) {
        if let Some(r) = inserted {
            if self.is_fall(r) {
                self.pending.push(r as u32);
            }
        }
    }

    /// Multiply the pending degree falls by every monomial `t` that keeps
    /// the degree within the basis's (`1 ≤ deg t ≤ D − deg q`, over the
    /// variables occurring in the system) and insert the products; falls
    /// the products produce are queued in turn.  At most `closure_rounds`
    /// rounds run per node; what is left stays pending for the children.
    ///
    /// This is MutantXL's step at fixed degree: a degree fall `q` of the
    /// degree-`D` Macaulay row space has multiples `t·q` of degree `≤ D`
    /// that the Macaulay matrix does not contain, and on the Semaev systems
    /// here they are what lets a degree-3 basis refute or pin a branch
    /// that the plain degree-3 matrix has to split.  Every product lies in
    /// the ideal, so the tail stays sound.  Each product is charged one
    /// word read per word of `q` and one written per word of the product.
    pub fn close(&mut self, cost: &mut InheritCost) {
        if self.closure_rounds == 0 || self.refuted {
            self.pending.clear();
            return;
        }
        let multipliers = self
            .system
            .iter()
            .flat_map(|p| p.terms.iter())
            .fold(0u64, |acc, t| acc | t.mask)
            & all_variable_mask(self.n_vars);
        for _ in 0..self.closure_rounds {
            let work = std::mem::take(&mut self.pending);
            if work.is_empty() {
                break;
            }
            let mut products: Vec<Vec<u64>> = Vec::new();
            let mut read_words = 0u64;
            for r in work {
                let r = r as usize;
                if !self.is_fall(r) {
                    continue;
                }
                let gap = self.degree - self.columns[self.pivot_col[r] as usize].count_ones();
                let q = self.current_row(r, cost);
                let mut q_monos: Vec<u64> = Vec::new();
                for (i, &word) in q.live().iter().enumerate() {
                    let base = (q.lead as usize + i) * 64;
                    let mut bits = word;
                    while bits != 0 {
                        let b = bits.trailing_zeros() as usize;
                        bits &= bits - 1;
                        q_monos.push(self.columns[base + b]);
                    }
                }
                for t in monomials_up_to_mask(multipliers, gap) {
                    if t == 0 {
                        continue;
                    }
                    let mut all: Vec<u64> = q_monos.iter().map(|&m| m | t).collect();
                    all.sort_unstable();
                    let mut product = Vec::with_capacity(all.len());
                    let mut i = 0;
                    while i < all.len() {
                        let mut j = i;
                        while j < all.len() && all[j] == all[i] {
                            j += 1;
                        }
                        if (j - i) % 2 == 1 {
                            product.push(all[i]);
                        }
                        i = j;
                    }
                    if !product.is_empty() {
                        products.push(product);
                        read_words += q.live().len() as u64;
                    }
                }
            }
            if products.is_empty() {
                break;
            }
            self.extend_columns(&products);
            let words = self.words;
            cost.specialise_word_ops += read_words + (products.len() * words) as u64;
            cost.closure_products += products.len() as u64;
            let packed: Vec<Vec<u64>> = {
                let index = self.column_index();
                products
                    .iter()
                    .map(|monos| {
                        let mut row = vec![0u64; words];
                        for m in monos {
                            let c = index[m];
                            row[c / 64] |= 1u64 << (c % 64);
                        }
                        row
                    })
                    .collect()
            };
            self.absorb(packed, cost);
            if self.refuted {
                break;
            }
        }
    }

    /// Absorb a batch of rows given in the current layout: one elimination
    /// of the whole basis with the batch below it, through the shape-selected
    /// kernel ([`rref_f2_counted`]), leaving the basis in reduced row echelon
    /// form.  Inserting the rows one at a time into an echelon basis would
    /// cascade through its pivots; a batch of closure products is large
    /// enough that the Four Russians kernel reduces it for a fraction of
    /// that.  Rows whose pivot column is new and whose leading degree is a
    /// fall's are queued for closure.
    fn absorb(&mut self, batch: Vec<Vec<u64>>, cost: &mut InheritCost) {
        if batch.is_empty() {
            return;
        }
        self.materialise_all(cost);
        let was_pivot: Vec<bool> = self.pivot_of.iter().map(Option::is_some).collect();
        let words = self.words;
        let mut matrix: Vec<Vec<u64>> = self
            .rows
            .iter()
            .map(|row| {
                let mut full = vec![0u64; words];
                full[row.start as usize..].copy_from_slice(&row.data);
                full
            })
            .collect();
        matrix.extend(batch);
        let rank = rref_f2_counted(&mut matrix, self.columns.len(), &mut cost.reduce_word_ops);
        matrix.truncate(rank);
        let epoch = self.epoch();
        self.rows.clear();
        self.pivot_col.clear();
        self.pivot_of = vec![None; self.columns.len()];
        self.pending.clear();
        for (r, row) in matrix.into_iter().enumerate() {
            let c = leading_column(&row).expect("rank rows are nonzero");
            self.pivot_of[c] = Some(r as u32);
            self.pivot_col.push(c as u32);
            self.rows.push(LazyRow {
                version: epoch,
                start: 0,
                lead: (c / 64) as u32,
                data: row.into(),
            });
            if !was_pivot[c] && self.is_fall(r) {
                self.pending.push(r as u32);
            }
        }
        if let Some(r) = self.one_row() {
            self.collapse_to_one(r);
        }
    }

    /// Add any monomials of `rows_monos` missing from the layout, keeping
    /// the descending column order.  A layout step like any other: rows
    /// are not touched.
    fn extend_columns(&mut self, rows_monos: &[Vec<u64>]) {
        let index = self.column_index();
        let mut missing: Vec<u64> = rows_monos
            .iter()
            .flatten()
            .copied()
            .filter(|m| !index.contains_key(m))
            .collect();
        if missing.is_empty() {
            return;
        }
        missing.sort_unstable();
        missing.dedup();
        let mut columns = self.columns.clone();
        columns.extend(missing);
        columns.sort_by(|a, b| {
            cmp_mono(F2BoolMono::from_mask(*a), F2BoolMono::from_mask(*b)).reverse()
        });
        let index: MaskMap<usize> = columns.iter().enumerate().map(|(i, &m)| (m, i)).collect();
        let map: Vec<u32> = self.columns.iter().map(|m| index[m] as u32).collect();
        self.adopt_layout(columns, map);
    }

    /// The linear tail — the intersection of the row space with the
    /// span of the degree-`≤ 1` monomials — in reduced row echelon form,
    /// as polynomials.  Exactly what the from-scratch step's readback
    /// consumes.  Only the rows leading in the tail are materialised.
    pub fn linear_tail(&mut self, cost: &mut InheritCost) -> Vec<F2BoolPoly> {
        if self.refuted {
            return vec![F2BoolPoly::one(self.n_vars)];
        }
        let low_start = self.low_start();
        let low_width = self.columns.len() - low_start;
        if low_width == 0 {
            return Vec::new();
        }
        let low_words = low_width.div_ceil(64).max(1);
        let tail_rows: Vec<usize> = (0..self.rows.len())
            .filter(|&r| self.pivot_col[r] as usize >= low_start)
            .collect();
        let mut low: Vec<Vec<u64>> = Vec::with_capacity(tail_rows.len());
        for r in tail_rows {
            let row = self.current_row(r, cost);
            let c = self.pivot_col[r] as usize;
            let mut packed = vec![0u64; low_words];
            for column in c..self.columns.len() {
                if row.word(column / 64) & (1u64 << (column % 64)) != 0 {
                    let k = column - low_start;
                    packed[k / 64] |= 1u64 << (k % 64);
                }
            }
            low.push(packed);
        }
        if low.is_empty() {
            return Vec::new();
        }
        let rank = rref_f2_counted(&mut low, low_width, &mut cost.reduce_word_ops);
        let n_vars = self.n_vars;
        low.iter()
            .take(rank)
            .map(|row| {
                let monos: Vec<F2BoolMono> = (0..low_width)
                    .filter(|k| row[k / 64] & (1u64 << (k % 64)) != 0)
                    .map(|k| F2BoolMono::from_mask(self.columns[low_start + k]))
                    .collect();
                F2BoolPoly::from_monos(monos, n_vars)
            })
            .collect()
    }

    /// The rows the splitting solver acts on: the constant `1`, and every
    /// `v` or `v + 1` of the linear tail.
    pub fn decisive_rows(&mut self, cost: &mut InheritCost) -> Vec<F2BoolPoly> {
        self.linear_tail(cost)
            .into_iter()
            .filter(|p| {
                (p.terms.len() == 1 && p.terms[0].mask == 0)
                    || (p.terms.len() <= 2
                        && p.terms.iter().filter(|t| t.mask.count_ones() == 1).count() == 1
                        && p.terms.iter().all(|t| t.mask.count_ones() <= 1))
            })
            .collect()
    }

    /// Specialise by several assignments in sequence.
    pub fn specialise_all(&self, assignments: &[(u32, bool)]) -> (Self, InheritCost) {
        let mut cost = InheritCost::default();
        let mut basis = self.clone();
        for &(v, val) in assignments {
            let (next, c) = basis.specialise(v, val);
            cost.add(c);
            basis = next;
        }
        (basis, cost)
    }
}

/// Specialise `p` by setting variable `var` to `value`.
pub fn substitute(p: &F2BoolPoly, var: u32, value: bool) -> F2BoolPoly {
    p.substitute(var, value)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::koblitz_groebner::matrix_f4_f2;

    fn random_poly(n_vars: usize, deg: u32, terms: usize, seed: &mut u64) -> F2BoolPoly {
        let mut next = || {
            *seed ^= *seed << 13;
            *seed ^= *seed >> 7;
            *seed ^= *seed << 17;
            *seed
        };
        let mut monos = Vec::new();
        for _ in 0..terms {
            let d = (next() % (deg as u64 + 1)) as u32;
            let mut mask = 0u64;
            for _ in 0..d {
                mask |= 1u64 << (next() % n_vars as u64);
            }
            monos.push(F2BoolMono::from_mask(mask));
        }
        F2BoolPoly::from_monos(monos, n_vars)
    }

    fn canonical(mut rows: Vec<F2BoolPoly>) -> Vec<F2BoolPoly> {
        rows.retain(|p| !p.is_zero());
        rows.sort_by(|a, b| format!("{a:?}").cmp(&format!("{b:?}")));
        rows
    }

    /// RREF of a list of polynomials, as a canonical set.
    fn rref_polys(polys: &[F2BoolPoly], n_vars: usize) -> Vec<F2BoolPoly> {
        let rows_monos: Vec<Vec<u64>> = polys
            .iter()
            .filter(|p| !p.is_zero())
            .map(|p| p.terms.iter().map(|t| t.mask).collect())
            .collect();
        if rows_monos.is_empty() {
            return Vec::new();
        }
        let cols = macaulay_columns(&rows_monos).unwrap();
        let mut matrix = pack_rows(&rows_monos, &cols);
        let mut ops = 0;
        let rank = rref_f2_counted(&mut matrix, cols.len(), &mut ops);
        canonical(
            matrix
                .iter()
                .take(rank)
                .map(|row| {
                    F2BoolPoly::from_monos(
                        (0..cols.len())
                            .filter(|c| row[c / 64] & (1u64 << (c % 64)) != 0)
                            .map(|c| F2BoolMono::from_mask(cols[c]))
                            .collect(),
                        n_vars,
                    )
                })
                .collect(),
        )
    }

    /// From-scratch Macaulay row space with multipliers over `mask`.
    fn masked_space(
        system: &[F2BoolPoly],
        n_vars: usize,
        degree: u32,
        mask: u64,
    ) -> Vec<F2BoolPoly> {
        use crate::cryptanalysis::koblitz_groebner::macaulay_rows_monos_with_mask;
        let rows = macaulay_rows_monos_with_mask(system, n_vars, degree, mask, None).unwrap();
        let polys: Vec<F2BoolPoly> = rows
            .iter()
            .map(|monos| {
                F2BoolPoly::from_monos(
                    monos.iter().map(|&m| F2BoolMono::from_mask(m)).collect(),
                    n_vars,
                )
            })
            .collect();
        rref_polys(&polys, n_vars)
    }

    fn tail_of(polys: &[F2BoolPoly]) -> Vec<F2BoolPoly> {
        polys
            .iter()
            .filter(|p| p.terms.iter().all(|t| t.mask.count_ones() <= 1))
            .cloned()
            .collect()
    }

    /// The solver's view of a tail: a refutation if `1` is present,
    /// otherwise the tail itself.  The legacy step multiplies by assigned
    /// variables too, and once `1` is in the row space those junk rows put
    /// `x·1 = x` into its tail; the solver never reads past the `1`.
    fn solver_view(tail: &[F2BoolPoly], n_vars: usize) -> Vec<F2BoolPoly> {
        let tail = rref_polys(tail, n_vars);
        if tail
            .iter()
            .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0)
        {
            vec![F2BoolPoly::one(n_vars)]
        } else {
            tail
        }
    }

    /// The solver refutes a system containing the constant `1` before any
    /// reduction, so the exact row-space invariant is only claimed for
    /// systems it would actually reduce.
    fn has_constant(system: &[F2BoolPoly]) -> bool {
        system
            .iter()
            .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0)
    }

    fn occurring(system: &[F2BoolPoly]) -> u64 {
        system
            .iter()
            .flat_map(|p| p.terms.iter())
            .fold(0, |a, t| a | t.mask)
    }

    /// Does every polynomial of `inner` reduce to zero against the RREF
    /// `outer`?  (`inner ⊆ span(outer)`.)
    fn contained(inner: &[F2BoolPoly], outer: &[F2BoolPoly], n_vars: usize) -> bool {
        let joint = rref_polys(&[outer, inner].concat(), n_vars);
        joint.len() == rref_polys(outer, n_vars).len()
    }

    /// The sandwich `V_occurring(S) ⊆ basis ⊆ V_unassigned(S)` the module
    /// documents, for a node reached by assigning `assigned`.
    /// A refuted basis is collapsed to `1`, so for it the claim is only the
    /// solver's view: the smallest space of the sandwich refutes as well.
    fn assert_sandwich(
        basis: &ReducedBasis,
        system: &[F2BoolPoly],
        n_vars: usize,
        assigned: u64,
        what: &str,
    ) {
        let rows = rref_polys(&basis_polys(basis), n_vars);
        let lower = masked_space(system, n_vars, basis.degree, occurring(system) & !assigned);
        if basis.refuted {
            assert_eq!(
                rows,
                vec![F2BoolPoly::one(n_vars)],
                "{what}: a refuted basis is exactly 1"
            );
            assert!(
                has_constant(&lower),
                "{what}: refuted, but V_occurring does not contain 1"
            );
            return;
        }
        let upper = masked_space(
            system,
            n_vars,
            basis.degree,
            all_variable_mask(n_vars) & !assigned,
        );
        assert!(
            contained(&lower, &rows, n_vars),
            "{what}: V_occurring not contained in the basis"
        );
        assert!(
            contained(&rows, &upper, n_vars),
            "{what}: basis not contained in V_unassigned"
        );
    }

    /// Every row, materialised into the current layout, as polynomials.
    fn basis_polys(b: &ReducedBasis) -> Vec<F2BoolPoly> {
        let mut b = b.clone();
        let mut cost = InheritCost::default();
        b.materialise_all(&mut cost);
        b.rows
            .iter()
            .map(|row| {
                F2BoolPoly::from_monos(
                    (0..b.columns.len())
                        .filter(|c| row.word(c / 64) & (1u64 << (c % 64)) != 0)
                        .map(|c| F2BoolMono::from_mask(b.columns[c]))
                        .collect(),
                    b.n_vars,
                )
            })
            .collect()
    }

    #[test]
    fn specialised_basis_spans_the_from_scratch_row_space() {
        let mut seed = 0x1234_5678_9abc_def1u64;
        for trial in 0..60 {
            let n_vars = 5 + trial % 4;
            let m = 3 + trial % 4;
            let system: Vec<F2BoolPoly> = (0..m)
                .map(|k| random_poly(n_vars, if k % 4 == 3 { 1 } else { 2 }, 5 + k, &mut seed))
                .filter(|p| poly_degree(p) >= 1)
                .collect();
            if system.is_empty() {
                continue;
            }
            for degree in 2..=3u32 {
                let (mut root, _) = ReducedBasis::from_system(&system, n_vars, degree).unwrap();
                // Root: the sandwich with nothing assigned, and the legacy tail.
                assert_sandwich(
                    &root,
                    &system,
                    n_vars,
                    0,
                    &format!("trial {trial} degree {degree} root"),
                );
                let f4 = matrix_f4_f2(&system, n_vars, degree).unwrap();
                let mut root_cost = InheritCost::default();
                assert_eq!(
                    solver_view(&tail_of(&f4), n_vars),
                    solver_view(&root.linear_tail(&mut root_cost), n_vars),
                    "trial {trial} degree {degree}: root tail differs"
                );
                // Every one-variable specialisation, both values, then a second one.
                let occurring = system
                    .iter()
                    .flat_map(|p| p.terms.iter())
                    .fold(0, |a, t| a | t.mask);
                let _all = all_variable_mask(n_vars);
                for v in 0..n_vars as u32 {
                    if occurring & (1 << v) == 0 {
                        continue;
                    }
                    for value in [false, true] {
                        let (mut child, _) = root.specialise(v, value);
                        let child_system: Vec<F2BoolPoly> = system
                            .iter()
                            .map(|p| substitute(p, v, value))
                            .filter(|p| !p.is_zero())
                            .collect();
                        assert_eq!(*child.system, child_system);
                        if !has_constant(&child_system) {
                            assert_sandwich(
                                &child,
                                &child_system,
                                n_vars,
                                1 << v,
                                &format!("trial {trial} degree {degree} v{v}={value}"),
                            );
                        }
                        // Tail agreement with the legacy all-variable step's readback.
                        let legacy =
                            matrix_f4_f2(&child_system, n_vars, degree).unwrap_or_default();
                        let mut cost = InheritCost::default();
                        let tail = child.linear_tail(&mut cost);
                        assert_eq!(
                            solver_view(&tail_of(&legacy), n_vars),
                            solver_view(&tail, n_vars),
                            "trial {trial} degree {degree} v{v}={value}: tail differs"
                        );
                        // One more level.
                        let w = (v + 1) % n_vars as u32;
                        let (mut grandchild, _) = child.specialise(w, !value);
                        let gc_system: Vec<F2BoolPoly> = child_system
                            .iter()
                            .map(|p| substitute(p, w, !value))
                            .filter(|p| !p.is_zero())
                            .collect();
                        if !has_constant(&gc_system) {
                            assert_sandwich(
                                &grandchild,
                                &gc_system,
                                n_vars,
                                (1 << v) | (1 << w),
                                &format!(
                                    "trial {trial} degree {degree} v{v}={value} w{w}: grandchild"
                                ),
                            );
                        }
                        let legacy = matrix_f4_f2(&gc_system, n_vars, degree).unwrap_or_default();
                        let tail = grandchild.linear_tail(&mut cost);
                        assert_eq!(
                            solver_view(&tail_of(&legacy), n_vars),
                            solver_view(&tail, n_vars),
                            "trial {trial} degree {degree} v{v}={value} w{w}: grandchild tail differs"
                        );
                    }
                }
            }
        }
    }

    #[test]
    fn degree_drop_completion_rows_are_added() {
        // f = x0·x1 + x2: setting x0 = 0 makes it linear, so degree-2
        // multipliers appear in the from-scratch matrix at degree 3.
        let n_vars = 4;
        let f = F2BoolPoly::from_monos(
            vec![F2BoolMono::from_mask(0b0011), F2BoolMono::from_mask(0b0100)],
            n_vars,
        );
        let g = F2BoolPoly::from_monos(
            vec![
                F2BoolMono::from_mask(0b1100),
                F2BoolMono::from_mask(0b0010),
                F2BoolMono::one(),
            ],
            n_vars,
        );
        let (root, _) = ReducedBasis::from_system(&[f, g], n_vars, 3).unwrap();
        let (child, cost) = root.specialise(0, false);
        assert!(
            cost.completion_rows > 0,
            "f dropped to degree 1; completion expected"
        );
        let system = child.system.clone();
        assert_sandwich(&child, &system, n_vars, 1, "degree drop");
        // With every unassigned variable occurring, the sandwich is an equality.
        assert_eq!(occurring(&system), all_variable_mask(n_vars) & !1);
        assert_eq!(
            masked_space(&system, n_vars, 3, all_variable_mask(n_vars) & !1),
            rref_polys(&basis_polys(&child), n_vars)
        );
    }

    /// Every point of `F_2^n_vars` on which the whole system vanishes.
    fn variety(system: &[F2BoolPoly], n_vars: usize) -> Vec<u64> {
        (0..1u64 << n_vars)
            .filter(|&x| system.iter().all(|p| p.eval(x) == 0))
            .collect()
    }

    /// A closed basis may leave the Macaulay space — that is its point —
    /// but must stay inside the ideal and keep everything the plain basis
    /// has, so its tail refutes or pins at least what the plain one does.
    fn assert_closed_sound(
        basis: &ReducedBasis,
        system: &[F2BoolPoly],
        n_vars: usize,
        assigned: u64,
        what: &str,
    ) {
        let rows = basis_polys(basis);
        let roots = variety(system, n_vars);
        for p in &rows {
            assert!(
                roots.iter().all(|&x| p.eval(x) == 0),
                "{what}: a closed row does not vanish on the variety"
            );
        }
        if !has_constant(system) && !basis.refuted {
            let lower = masked_space(system, n_vars, basis.degree, occurring(system) & !assigned);
            assert!(
                contained(&lower, &rref_polys(&rows, n_vars), n_vars),
                "{what}: the closed basis lost part of the Macaulay space"
            );
        }
    }

    #[test]
    fn closed_bases_stay_in_the_ideal_and_contain_the_macaulay_space() {
        let mut seed = 0x0fed_cba9_8765_4321u64;
        let mut products = 0u64;
        for trial in 0..40 {
            let n_vars = 5 + trial % 4;
            let m = 3 + trial % 3;
            let system: Vec<F2BoolPoly> = (0..m)
                .map(|k| random_poly(n_vars, 2, 4 + k, &mut seed))
                .filter(|p| poly_degree(p) >= 1)
                .collect();
            if system.is_empty() {
                continue;
            }
            let rounds = 1 + trial as u32 % 2;
            let (root, cost) =
                ReducedBasis::from_system_closed(&system, n_vars, 3, rounds).unwrap();
            products += cost.closure_products;
            assert_closed_sound(&root, &system, n_vars, 0, &format!("trial {trial} root"));
            for v in 0..n_vars as u32 {
                if occurring(&system) & (1 << v) == 0 {
                    continue;
                }
                for value in [false, true] {
                    let (child, cost) = root.specialise(v, value);
                    products += cost.closure_products;
                    let child_system: Vec<F2BoolPoly> = system
                        .iter()
                        .map(|p| substitute(p, v, value))
                        .filter(|p| !p.is_zero())
                        .collect();
                    assert_closed_sound(
                        &child,
                        &child_system,
                        n_vars,
                        1 << v,
                        &format!("trial {trial} v{v}={value}"),
                    );
                }
            }
        }
        assert!(
            products > 0,
            "no degree fall was closed; the test exercised nothing"
        );
    }

    #[test]
    fn a_refuted_child_is_one_and_stays_refuted_for_free() {
        let mut seed = 0x0bad_5eed_0dd5_0001u64;
        let mut refuted_children = 0;
        for trial in 0..120 {
            let n_vars = 5 + trial % 3;
            let system: Vec<F2BoolPoly> = (0..3 + trial % 3)
                .map(|k| random_poly(n_vars, 2, 4 + k, &mut seed))
                .filter(|p| poly_degree(p) >= 1)
                .collect();
            let Some((root, _)) = ReducedBasis::from_system(&system, n_vars, 3) else {
                continue;
            };
            if root.refuted {
                continue;
            }
            let occurring = occurring(&system);
            for v in (0..n_vars as u32).filter(|v| occurring & (1 << v) != 0) {
                for value in [false, true] {
                    let (child, _) = root.specialise(v, value);
                    if !child.refuted {
                        continue;
                    }
                    refuted_children += 1;
                    let child_system: Vec<F2BoolPoly> = system
                        .iter()
                        .map(|p| substitute(p, v, value))
                        .filter(|p| !p.is_zero())
                        .collect();
                    let legacy = matrix_f4_f2(&child_system, n_vars, 3).unwrap_or_default();
                    assert!(
                        has_constant(&legacy),
                        "trial {trial} v{v}={value}: refuted, but not from scratch"
                    );
                    assert_eq!(basis_polys(&child), vec![F2BoolPoly::one(n_vars)]);
                    let Some(w) = (0..n_vars as u32).find(|&w| w != v && occurring & (1 << w) != 0)
                    else {
                        continue;
                    };
                    let (mut grandchild, cost) = child.specialise(w, !value);
                    assert!(
                        grandchild.refuted,
                        "trial {trial}: refutation lost below v{v}={value}"
                    );
                    assert_eq!(
                        cost.word_ops(),
                        0,
                        "trial {trial}: a refuted basis cost something to specialise"
                    );
                    let mut read = InheritCost::default();
                    assert_eq!(
                        grandchild.decisive_rows(&mut read),
                        vec![F2BoolPoly::one(n_vars)]
                    );
                    assert_eq!(read.word_ops(), 0);
                }
            }
        }
        assert!(
            refuted_children > 0,
            "no specialisation refuted; the test exercised nothing"
        );
    }

    #[test]
    fn zero_closure_rounds_is_the_plain_basis() {
        let mut seed = 0x5555_aaaa_1234_4321u64;
        for trial in 0..20 {
            let n_vars = 5 + trial % 4;
            let system: Vec<F2BoolPoly> = (0..4)
                .map(|k| random_poly(n_vars, 2, 5 + k, &mut seed))
                .collect();
            let (plain, plain_cost) = ReducedBasis::from_system(&system, n_vars, 3).unwrap();
            let (closed, closed_cost) =
                ReducedBasis::from_system_closed(&system, n_vars, 3, 0).unwrap();
            assert_eq!(basis_polys(&plain), basis_polys(&closed), "trial {trial}");
            assert_eq!(plain_cost, closed_cost, "trial {trial}");
        }
    }
}
