//! Improved baby-step / giant-step and Gaudry–Schost ECDLP variants.
//!
//! This module fills in the *full* algorithm table from Galbraith,
//! Wang & Zhang, "Computing Elliptic Curve Discrete Logarithms with
//! Improved Baby-step Giant-step Algorithm" (Advances in Mathematics
//! of Communications 11(3), 2017).  The crate already shipped the
//! "Pollard rho" row of that table (distinguished points, negation
//! map, Montgomery trick — see [`crate::cryptanalysis::pollard_rho`],
//! [`crate::cryptanalysis::p256_attacks`], and the `examples/`
//! vOW-style attacks).  What was missing was the *baby-step
//! giant-step family* and the *Gaudry–Schost family*.  This module
//! adds both.
//!
//! | # | Algorithm | fn |
//! |---|-----------|----|
//! | 1 | Textbook BSGS (baseline) | [`bsgs::bsgs_textbook`] |
//! | 2 | BSGS, average-case optimised | [`bsgs::bsgs_average_case`] |
//! | 3 | Pollard interleaving BSGS | [`bsgs::bsgs_interleaving`] |
//! | 4 | Two grumpy giants + a baby | [`bsgs::grumpy_giants`] |
//! | 6 | Gaudry–Schost | [`gaudry_schost::gaudry_schost`] |
//! | 7 | BSGS with negation | [`bsgs::bsgs_negation`] |
//! | 8 | Interleaving BSGS with negation | [`bsgs::bsgs_interleaving_negation`] |
//! | 9 | Grumpy giants with negation | [`bsgs::grumpy_giants_negation`] |
//! | 11 | Gaudry–Schost with negation | [`gaudry_schost::gaudry_schost_negation`] |
//! | 12 | Interleaving BSGS, block computation | [`bsgs::bsgs_interleaving_block`] |
//! | 13 | Grumpy giants, block computation | [`bsgs::grumpy_giants_block`] |
//! | 15 | Gaudry–Schost with Montgomery trick | [`gaudry_schost::gaudry_schost_montgomery`] |
//!
//! # Cost model
//!
//! Every solver returns a [`DlpSolution`] carrying three measured
//! costs so the table's constants can be reproduced empirically:
//!
//! - `group_ops` — point additions and doublings in the *main loop*
//!   (set-up scalar multiplications, e.g. forming the giant step
//!   `mP`, are not counted, matching the paper's metric).
//! - `field_inversions` — `F_p` inversions actually performed.  An
//!   affine addition or doubling costs one inversion, so for the
//!   plain variants `field_inversions ≈ group_ops`.  The *block
//!   computation* (#12, #13) and *Montgomery trick* (#15) variants
//!   batch `B` additions behind a single inversion via Montgomery's
//!   trick, driving this down to `≈ group_ops / B` — the whole point
//!   of that column of the table.  (`FieldElement::inv` is a Fermat
//!   `a^{p-2}` exponentiation, so an inversion is *much* more
//!   expensive than a multiplication; batching is a real win.)
//! - `table_size` — peak number of stored points (memory).  The
//!   negation variants (#7–#9) fold `±P` to a single x-keyed entry,
//!   halving this.
//!
//! # Scope
//!
//! # A faster path
//!
//! Every solver here uses the crate's general arithmetic — [`BigUint`]
//! coordinates and a `HashMap` keyed by coordinate bytes — because the
//! point is to state the algorithms readably and count their operations
//! exactly.  That costs an allocation per field operation and another per
//! table probe.  When the *time* matters rather than the exposition,
//! [`crate::cryptanalysis::bsgs_fast`] is the same algorithm over
//! single-word Montgomery arithmetic and a flat x-keyed table, with the
//! chains spread across cores: measured at 6.3× to 10.9× this module on
//! the same instances, and it carries the interval and many-target modes
//! this one does not.  It is capped at curves whose prime and order fit a
//! word; above that, or for operation counts, stay here.
//!
//! These are all `O(√n)` (BSGS family: deterministic; Gaudry–Schost:
//! randomised, low-memory) — exponential in the bit length, so they
//! are demonstrated on small curves (a few-thousand- to ~100k-order
//! subgroup).  They share the crate's real [`Point`] arithmetic, so a
//! correctness regression in [`Point::add`] would make every test in
//! this module fail.

use std::cell::Cell;

use num_bigint::BigUint;
use num_traits::{One, Zero};

use crate::ecc::curve::CurveParams;
use crate::ecc::field::FieldElement;
use crate::ecc::point::Point;

pub mod bsgs;
pub mod gaudry_schost;

pub use bsgs::{
    bsgs_average_case, bsgs_interleaving, bsgs_interleaving_block, bsgs_interleaving_negation,
    bsgs_negation, bsgs_textbook, grumpy_giants, grumpy_giants_block, grumpy_giants_negation,
};
pub use gaudry_schost::{
    gaudry_schost, gaudry_schost_montgomery, gaudry_schost_negation, GaudrySchostOptions,
};

/// Outcome of a discrete-log solve, with measured costs.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DlpSolution {
    /// Recovered `x` with `Q = xP` (and `0 ≤ x < n`).
    pub x: BigUint,
    /// Point additions + doublings performed in the main loop.
    pub group_ops: u64,
    /// `F_p` inversions performed (batched variants drive this far
    /// below `group_ops`).
    pub field_inversions: u64,
    /// Peak number of stored points (memory footprint).
    pub table_size: usize,
}

/// A cyclic subgroup `⟨g⟩` of order `n` on a short-Weierstrass curve,
/// wrapping the crate's real [`Point`]/[`FieldElement`] arithmetic and
/// tallying main-loop cost.
///
/// Counters are interior-mutable ([`Cell`]); call [`EcGroup::reset`]
/// at the start of a solve and read [`EcGroup::group_ops`] /
/// [`EcGroup::field_inversions`] at the end.
pub struct EcGroup {
    a: FieldElement,
    p: BigUint,
    n: BigUint,
    g: Point,
    group_ops: Cell<u64>,
    inversions: Cell<u64>,
}

impl EcGroup {
    /// Build a group from explicit parameters.  `g` must have order
    /// `n` (for our tests `n` is prime, so any non-identity point
    /// does).
    pub fn new(a: FieldElement, p: BigUint, n: BigUint, g: Point) -> Self {
        Self {
            a,
            p,
            n,
            g,
            group_ops: Cell::new(0),
            inversions: Cell::new(0),
        }
    }

    /// Build from a [`CurveParams`], using its full group order `n`
    /// and standard generator.  Appropriate when the cofactor is 1
    /// and `n` is prime (the demo curves below, and the cofactor-1
    /// zoo curves).
    pub fn from_curve(curve: &CurveParams) -> Self {
        let g = curve.generator();
        Self::new(curve.a_fe(), curve.p.clone(), curve.n.clone(), g)
    }

    /// Subgroup order.
    pub fn order(&self) -> &BigUint {
        &self.n
    }
    /// Generator.
    pub fn generator(&self) -> &Point {
        &self.g
    }
    /// Curve coefficient `a`.
    pub fn a(&self) -> &FieldElement {
        &self.a
    }
    /// Reset the main-loop cost counters.
    pub fn reset(&self) {
        self.group_ops.set(0);
        self.inversions.set(0);
    }
    /// Group operations counted since the last [`reset`](Self::reset).
    pub fn group_ops(&self) -> u64 {
        self.group_ops.get()
    }
    /// Field inversions counted since the last [`reset`](Self::reset).
    pub fn field_inversions(&self) -> u64 {
        self.inversions.get()
    }

    /// The identity (point at infinity).
    pub fn identity(&self) -> Point {
        Point::Infinity
    }

    /// Negation `-P` — free (negate `y`), not counted.
    pub fn neg(&self, p: &Point) -> Point {
        p.neg()
    }

    /// Counted addition: one group op, one inversion (unless an
    /// operand is the identity, which needs no field arithmetic).
    pub fn add(&self, x: &Point, y: &Point) -> Point {
        self.group_ops.set(self.group_ops.get() + 1);
        let trivial = matches!(x, Point::Infinity) || matches!(y, Point::Infinity);
        if !trivial {
            self.inversions.set(self.inversions.get() + 1);
        }
        x.add(y, &self.a)
    }

    /// Counted doubling.
    pub fn dbl(&self, x: &Point) -> Point {
        self.group_ops.set(self.group_ops.get() + 1);
        if !matches!(x, Point::Infinity) {
            self.inversions.set(self.inversions.get() + 1);
        }
        x.double(&self.a)
    }

    /// **Set-up** addition — *not* counted.  For building initial
    /// walker positions and constant offsets before the main loop.
    pub fn add_setup(&self, x: &Point, y: &Point) -> Point {
        x.add(y, &self.a)
    }

    /// **Set-up** scalar multiple of the generator `kG` — not counted.
    pub fn mul_setup(&self, k: &BigUint) -> Point {
        self.g.scalar_mul(k, &self.a)
    }

    /// **Set-up** scalar multiple of an arbitrary base — not counted.
    pub fn mul_pt_setup(&self, base: &Point, k: &BigUint) -> Point {
        base.scalar_mul(k, &self.a)
    }

    /// **Block (Montgomery-trick) addition.**  Adds each `Q_i` to its
    /// `P_i` for a slice of pairs, computing *all* the affine slopes
    /// from a single batched field inversion (Montgomery's trick).
    ///
    /// Cost: `pairs.len()` group ops but only **one** inversion for
    /// the whole block (plus one extra inversion per degenerate pair
    /// — identity / doubling / opposite — which can't share the
    /// batch).  This is the primitive behind algorithms #12, #13 and
    /// #15.
    pub fn batch_add(&self, pairs: &[(Point, Point)]) -> Vec<Point> {
        self.group_ops
            .set(self.group_ops.get() + pairs.len() as u64);

        let mut out: Vec<Option<Point>> = vec![None; pairs.len()];
        let mut denoms: Vec<FieldElement> = Vec::with_capacity(pairs.len());
        let mut generic_idx: Vec<usize> = Vec::with_capacity(pairs.len());

        for (i, (pp, qq)) in pairs.iter().enumerate() {
            match (pp, qq) {
                (Point::Infinity, _) => out[i] = Some(qq.clone()),
                (_, Point::Infinity) => out[i] = Some(pp.clone()),
                (Point::Affine { x: x1, .. }, Point::Affine { x: x2, .. }) => {
                    if x1 == x2 {
                        // Doubling or P + (-P): can't join the batch;
                        // fall back to a counted single addition.
                        self.inversions.set(self.inversions.get() + 1);
                        out[i] = Some(pp.add(qq, &self.a));
                    } else {
                        denoms.push(x2.sub(x1));
                        generic_idx.push(i);
                    }
                }
            }
        }

        if !denoms.is_empty() {
            // One inversion serves the entire block.
            self.inversions.set(self.inversions.get() + 1);
            let invs = batch_invert(&denoms, &self.p);
            for (k, &i) in generic_idx.iter().enumerate() {
                if let (Point::Affine { x: x1, y: y1 }, Point::Affine { x: x2, y: y2 }) =
                    (&pairs[i].0, &pairs[i].1)
                {
                    // λ = (y2 - y1) / (x2 - x1)
                    let lambda = y2.sub(y1).mul(&invs[k]);
                    let x3 = lambda.mul(&lambda).sub(x1).sub(x2);
                    let y3 = lambda.mul(&x1.sub(&x3)).sub(y1);
                    out[i] = Some(Point::Affine { x: x3, y: y3 });
                }
            }
        }

        out.into_iter()
            .map(|o| o.expect("every slot filled"))
            .collect()
    }
}

/// Montgomery's simultaneous-inversion trick: invert every element of
/// `elems` (all assumed non-zero) with a **single** field inversion
/// plus `3(k-1)` multiplications, instead of `k` inversions.
pub(crate) fn batch_invert(elems: &[FieldElement], p: &BigUint) -> Vec<FieldElement> {
    let k = elems.len();
    if k == 0 {
        return Vec::new();
    }
    // prefix[i] = elems[0] * … * elems[i-1]
    let mut prefix: Vec<FieldElement> = Vec::with_capacity(k);
    let mut acc = FieldElement::new(BigUint::one(), p.clone());
    for e in elems {
        prefix.push(acc.clone());
        acc = acc.mul(e);
    }
    // One inversion of the full product.
    let mut inv_acc = acc.inv().expect("batch_invert: zero element");
    let mut out = vec![FieldElement::new(BigUint::zero(), p.clone()); k];
    for i in (0..k).rev() {
        out[i] = inv_acc.mul(&prefix[i]);
        inv_acc = inv_acc.mul(&elems[i]);
    }
    out
}

/// Exact-identity hash key: `(x_bytes, y_bytes)`; identity → empty.
pub(crate) fn key(p: &Point) -> (Vec<u8>, Vec<u8>) {
    match p {
        Point::Infinity => (Vec::new(), Vec::new()),
        Point::Affine { x, y } => (x.value.to_bytes_be(), y.value.to_bytes_be()),
    }
}

/// Negation-folded hash key: x-coordinate only, so `P` and `-P`
/// collide; identity → empty.
pub(crate) fn xkey(p: &Point) -> Vec<u8> {
    match p {
        Point::Infinity => Vec::new(),
        Point::Affine { x, .. } => x.value.to_bytes_be(),
    }
}

/// `(a - b) mod n` for `BigUint`.
pub(crate) fn sub_mod(a: &BigUint, b: &BigUint, n: &BigUint) -> BigUint {
    let a = a % n;
    let b = b % n;
    if a >= b {
        a - b
    } else {
        n - (b - a)
    }
}

/// `⌈√n⌉`.
pub(crate) fn isqrt_ceil(n: &BigUint) -> BigUint {
    let s = n.sqrt();
    if &(&s * &s) < n {
        s + BigUint::one()
    } else {
        s
    }
}

/// Narrow a `BigUint` to `u64` for loop bounds (these algorithms are
/// only ever run on small subgroups; callers cap `n`).
pub(crate) fn to_u64(n: &BigUint) -> u64 {
    n.iter_u64_digits().next().unwrap_or(0)
}

// ── Demo curves (small, prime-order; shared by tests and examples) ───────────

/// Tiny demo group: `y² = x³ + 3x + 6` over `F_10007`, generator
/// `(0, 1973)` of prime order `10039`.  `√n ≈ 100` — full BSGS / GS
/// completes in well under a millisecond.
pub fn demo_group_small() -> EcGroup {
    let p = BigUint::from(10_007u32);
    let curve = CurveParams {
        name: "demo-10007",
        p: p.clone(),
        a: BigUint::from(3u32),
        b: BigUint::from(6u32),
        gx: BigUint::zero(),
        gy: BigUint::from(1973u32),
        n: BigUint::from(10_039u32),
        h: 1,
    };
    EcGroup::from_curve(&curve)
}

/// Mid-size demo group: `y² = x³ + 6x + 4` over `F_99013`, generator
/// `(0, 2)` of prime order `98893`.  `√n ≈ 314`.
pub fn demo_group_mid() -> EcGroup {
    let p = BigUint::from(99_013u32);
    let curve = CurveParams {
        name: "demo-99013",
        p: p.clone(),
        a: BigUint::from(6u32),
        b: BigUint::from(4u32),
        gx: BigUint::zero(),
        gy: BigUint::from(2u32),
        n: BigUint::from(98_893u32),
        h: 1,
    };
    EcGroup::from_curve(&curve)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn demo_curves_have_claimed_order() {
        for grp in [demo_group_small(), demo_group_mid()] {
            // n · G = ∞ and the generator is a real affine point.
            assert!(matches!(grp.generator(), Point::Affine { .. }));
            let ng = grp.mul_setup(grp.order());
            assert_eq!(ng, Point::Infinity, "generator order ≠ n");
            // …and no smaller multiple is ∞ at a random spot-check
            // (order is prime, so 1<k<n never lands on ∞).
            let half = grp.order() >> 1;
            assert!(matches!(grp.mul_setup(&half), Point::Affine { .. }));
        }
    }

    #[test]
    fn batch_invert_matches_individual() {
        let grp = demo_group_small();
        let p = &grp.p;
        let elems: Vec<FieldElement> = [3u32, 7, 9999, 1, 5000]
            .iter()
            .map(|v| FieldElement::new(BigUint::from(*v), p.clone()))
            .collect();
        let batched = batch_invert(&elems, p);
        for (e, b) in elems.iter().zip(batched.iter()) {
            assert_eq!(e.inv().unwrap(), *b);
            assert_eq!(e.mul(b).value, BigUint::one());
        }
    }

    #[test]
    fn batch_add_matches_sequential() {
        let grp = demo_group_small();
        // Build five independent (P_i, Q_i) generic pairs.
        let base: Vec<Point> = (1u32..=5)
            .map(|k| grp.mul_setup(&BigUint::from(k)))
            .collect();
        let off: Vec<Point> = (7u32..=11)
            .map(|k| grp.mul_setup(&BigUint::from(k)))
            .collect();
        let pairs: Vec<(Point, Point)> = base.iter().cloned().zip(off.iter().cloned()).collect();
        let batched = grp.batch_add(&pairs);
        for (i, (pp, qq)) in pairs.iter().enumerate() {
            assert_eq!(batched[i], grp.add_setup(pp, qq), "pair {i}");
        }
    }
}
