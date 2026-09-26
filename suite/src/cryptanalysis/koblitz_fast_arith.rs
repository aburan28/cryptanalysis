//! # Fast binary-field arithmetic for the Koblitz index-calculus hot path.
//!
//! The curve arithmetic in [`crate::binary_ecc`] is general over `m` and
//! heap-allocates a `Vec<u64>` per field operation.  The index-calculus
//! pipeline only ever builds curves with `n <= 63`
//! ([`crate::cryptanalysis::koblitz_index_calculus::MAX_N`]), where every
//! field element fits in one `u64`.  This module wraps the single-word
//! carry-less field from [`crate::cryptanalysis::semaev_decomp::Gf2`]
//! (pclmulqdq/pmull table reduction, no allocations) with the exact affine
//! group law from [`crate::binary_ecc::curve::point_add`], plus a
//! Montgomery-batched variant that replaces one inversion per point
//! addition with one inversion per whole batch.
//!
//! ## What is optimised and what is not
//!
//! - [`FastBinaryCurve::add`] is a drop-in, bit-exact replacement for
//!   affine `point_add` on `u64` coordinates: same branches (infinity,
//!   doubling, negation), same formulas.  It is used for isolated adds
//!   (the `m = 4` walk, special cases).
//! - [`FastBinaryCurve::batch_add`] evaluates many independent affine
//!   sums with a single field inversion via Montgomery's trick.  The
//!   pair-table build (`|F|(|F|+1)/2` sums) and the `m = 3` witness step
//!   (`|F|` sums of `R - P_k` per target) are the two callers; both were
//!   previously one Itoh-Tsujii inversion per sum.
//! - Nothing about the protocol changes: decomposition answers are still
//!   re-added with the slow path before they become relations, so a bug
//!   here can only cost performance, never soundness.

use crate::binary_ecc::{BinaryPoint, IrreduciblePoly};
use crate::cryptanalysis::semaev_decomp::Gf2;

/// Affine point on a binary curve with single-word coordinates.
///
/// `None` is the point at infinity; `Some((x, y))` is affine.
pub type FastPoint = Option<(u64, u64)>;

/// Single-word binary curve matching [`crate::binary_ecc::curve`] semantics.
#[derive(Clone, Debug)]
pub struct FastBinaryCurve {
    /// Field `F_{2^n}` with carry-less multiply + table reduction.
    pub gf: Gf2,
    /// Extension degree.
    pub n: u32,
    /// Curve coefficient `a` as a field element (0 or 1 on Koblitz curves).
    pub a: u64,
}

impl FastBinaryCurve {
    /// Build from an irreducible polynomial and coefficient `a`.
    ///
    /// Returns `None` when `n > 63` (elements would not fit in one word).
    pub fn new(irr: &IrreduciblePoly, a: u64) -> Option<Self> {
        if irr.degree == 0 || irr.degree > 63 {
            return None;
        }
        let gf = Gf2::new(irr);
        let n = irr.degree;
        let a = a & gf.mask;
        Some(Self { gf, n, a })
    }

    /// Project a general field element down to one word.
    #[inline]
    pub fn word(&self, e: &crate::binary_ecc::F2mElement) -> u64 {
        self.gf.from_element(e) & self.gf.mask
    }

    /// Lift one word back to the general element type.
    pub fn element(&self, w: u64) -> crate::binary_ecc::F2mElement {
        self.gf.to_element(w & self.gf.mask)
    }

    /// Exact affine addition, bit-identical to `point_add`.
    ///
    /// Returns `None` for the point at infinity.
    pub fn add(&self, p: FastPoint, q: FastPoint) -> FastPoint {
        match (p, q) {
            (None, r) | (r, None) => r,
            (Some((x1, y1)), Some((x2, y2))) => {
                if x1 == x2 {
                    if (y1 ^ y2) == x1 {
                        return None;
                    }
                    return self.double(x1, y1);
                }
                let gf = &self.gf;
                let dx = x1 ^ x2;
                let dy = y1 ^ y2;
                let lambda = gf.mul(dy, gf.inv(dx));
                let lambda_sq = gf.sqr(lambda);
                let x3 = lambda_sq ^ lambda ^ x1 ^ x2 ^ self.a;
                let y3 = gf.mul(lambda, x1 ^ x3) ^ x3 ^ y1;
                Some((x3, y3))
            }
        }
    }

    /// Exact affine doubling, bit-identical to `point_double`.
    pub fn double(&self, x1: u64, y1: u64) -> FastPoint {
        if x1 == 0 {
            return None;
        }
        let gf = &self.gf;
        let lambda = x1 ^ gf.mul(y1, gf.inv(x1));
        let lambda_sq = gf.sqr(lambda);
        let x3 = lambda_sq ^ lambda ^ self.a;
        // y3 = x1^2 + (lambda + 1) * x3
        let y3 = gf.sqr(x1) ^ gf.mul(lambda ^ 1, x3);
        Some((x3, y3))
    }

    /// Negation: `-(x, y) = (x, x + y)`.
    #[inline]
    pub fn neg(p: FastPoint) -> FastPoint {
        p.map(|(x, y)| (x, x ^ y))
    }

    /// Both curve points with the given `x`-coordinate.
    ///
    /// Bit-exact set (and order) with
    /// [`crate::cryptanalysis::koblitz_index_calculus::points_with_x`]:
    /// for `x = 0` the single point `(0, sqrt(b))`; otherwise the
    /// Artin-Schreier lift `y = x·u` plus its negation.  No allocations.
    pub fn points_with_x(&self, b: u64, x: u64) -> Vec<FastPoint> {
        let gf = &self.gf;
        let x = x & gf.mask;
        let b = b & gf.mask;
        if x == 0 {
            // y^2 = b, so y = b^{2^{n-1}} (squaring is a bijection).
            return vec![Some((0, gf.sqr_k(b, self.n - 1)))];
        }
        let x_inv_sq = gf.sqr(gf.inv(x));
        let rhs = x ^ self.a ^ gf.mul(b, x_inv_sq);
        let u = match artin_schreier_root(gf, self.n, rhs) {
            Some(u) => u,
            None => return Vec::new(),
        };
        let p = Some((x, gf.mul(x, u)));
        let np = Self::neg(p);
        if p == np {
            vec![p]
        } else {
            vec![p, np]
        }
    }

    /// Double-and-add scalar multiplication, bit-identical to
    /// [`crate::binary_ecc::curve::scalar_mul`].
    pub fn scalar_mul(&self, p: FastPoint, k: &num_bigint::BigUint) -> FastPoint {
        if k.bits() == 0 {
            return None;
        }
        let mut result: FastPoint = None;
        for i in (0..k.bits()).rev() {
            result = match result {
                None => None,
                Some((x, y)) => self.double(x, y),
            };
            if k.bit(i) {
                result = self.add(result, p);
            }
        }
        result
    }

    /// Batch affine doubling with one inversion per call.
    ///
    /// `None` (infinity) and `x == 0` double to `None`, exactly as
    /// [`Self::double`]; every other point shares a single Montgomery
    /// inversion of its x-coordinate.  Output order mirrors the input.
    pub fn batch_double(&self, points: &[FastPoint]) -> Vec<FastPoint> {
        let n = points.len();
        let mut out: Vec<FastPoint> = vec![None; n];
        let mut xs: Vec<u64> = Vec::new();
        let mut idx: Vec<usize> = Vec::new();
        xs.reserve(n);
        idx.reserve(n);
        for (k, p) in points.iter().enumerate() {
            match p {
                Some((x, _)) if *x != 0 => {
                    idx.push(k);
                    xs.push(*x);
                }
                _ => {}
            }
        }
        if xs.is_empty() {
            return out;
        }
        let mut scratch = Vec::new();
        self.gf.batch_inv(&mut xs, &mut scratch);
        // xs[t] is now 1/x of the t-th eligible point.
        let gf = &self.gf;
        for (t, &k) in idx.iter().enumerate() {
            let (x1, y1) = points[k].expect("eligible point is affine with x != 0");
            let lambda = x1 ^ gf.mul(y1, xs[t]);
            let lambda_sq = gf.sqr(lambda);
            let x3 = lambda_sq ^ lambda ^ self.a;
            let y3 = gf.sqr(x1) ^ gf.mul(lambda ^ 1, x3);
            out[k] = Some((x3, y3));
        }
        out
    }

    /// Many independent scalar multiplications with shared inversions.
    ///
    /// Bit-exact with calling [`Self::scalar_mul`] on each pair:
    /// MSB-first double-and-add where each bit position contributes one
    /// batched doubling plus (over the pairs with that bit set) one
    /// batched addition — two inversions per bit position for the whole
    /// batch instead of ~1.5 per pair per bit.  Output order mirrors the
    /// inputs; varying scalar lengths and `None` points are handled
    /// exactly as the single version handles them.
    pub fn batch_scalar_mul(
        &self,
        points: &[FastPoint],
        scalars: &[num_bigint::BigUint],
    ) -> Vec<FastPoint> {
        assert_eq!(points.len(), scalars.len(), "points/scalars align");
        let mut acc: Vec<FastPoint> = vec![None; points.len()];
        let maxbits: u64 = scalars.iter().map(|k| k.bits()).max().unwrap_or(0);
        for j in (0..maxbits).rev() {
            acc = self.batch_double(&acc);
            let mut idx: Vec<usize> = Vec::new();
            let mut pairs = Vec::new();
            for (i, (a, p)) in acc.iter().zip(points.iter()).enumerate() {
                if scalars[i].bit(j) {
                    let (ax, ay, a_inf) = match a {
                        None => (0, 0, true),
                        Some((x, y)) => (*x, *y, false),
                    };
                    let (px, py, p_inf) = match p {
                        None => (0, 0, true),
                        Some((x, y)) => (*x, *y, false),
                    };
                    idx.push(i);
                    pairs.push((ax, ay, px, py, a_inf, p_inf));
                }
            }
            if pairs.is_empty() {
                continue;
            }
            let sums = self.batch_add(&pairs);
            for (t, &i) in idx.iter().enumerate() {
                acc[i] = sums[t];
            }
        }
        acc
    }

    /// Batch affine addition with one inversion per call.
    ///
    /// Each entry is `(x1, y1, x2, y2, inf1, inf2)`; output mirrors the
    /// input order with `None` for infinity.  Generic pairs
    /// (`dx != 0`) share a single Montgomery inversion; the rare
    /// doubling/negation cases fall back to [`Self::add`] one by one
    /// (they need at most one inversion each and are a negligible
    /// fraction: only diagonal and opposite pairs).
    pub fn batch_add(&self, pairs: &[(u64, u64, u64, u64, bool, bool)]) -> Vec<FastPoint> {
        let n = pairs.len();
        let mut out: Vec<FastPoint> = vec![None; n];
        // Collect the generic denominators first.
        let mut dxs: Vec<u64> = Vec::new();
        let mut idx: Vec<usize> = Vec::new();
        dxs.reserve(n);
        idx.reserve(n);
        for (k, &(x1, y1, x2, y2, inf1, inf2)) in pairs.iter().enumerate() {
            if inf1 {
                out[k] = if inf2 { None } else { Some((x2, y2)) };
            } else if inf2 {
                out[k] = Some((x1, y1));
            } else if x1 == x2 {
                // Special case: doubling or negation.  Rare; slow path.
                out[k] = self.add(Some((x1, y1)), Some((x2, y2)));
            } else {
                idx.push(k);
                dxs.push(x1 ^ x2);
            }
        }
        if dxs.is_empty() {
            return out;
        }
        let mut scratch = Vec::new();
        self.gf.batch_inv(&mut dxs, &mut scratch);
        // dxs[k] is now 1/(x1^x2) for the k-th generic pair.
        let gf = &self.gf;
        for (t, &k) in idx.iter().enumerate() {
            let (x1, y1, x2, y2, _, _) = pairs[k];
            let inv = dxs[t];
            debug_assert_ne!(x1 ^ x2, 0);
            let lambda = gf.mul(y1 ^ y2, inv);
            let lambda_sq = gf.sqr(lambda);
            let x3 = lambda_sq ^ lambda ^ x1 ^ x2 ^ self.a;
            let y3 = gf.mul(lambda, x1 ^ x3) ^ x3 ^ y1;
            out[k] = Some((x3, y3));
        }
        out
    }
}

/// The `x`-roots of `S_3(left, right, x_3) = 0` over `F_{2^n}`, single-word.
///
/// `S_3` is quadratic in `x_3` with `A = (left+right)^2`, `B = left·right`,
/// `C = (left·right)^2 + b`.  The generic case (`A,B != 0`) is solved by the
/// half-trace: with `q = B/A`, `d = A·(1 + b/B^2)`, the two roots are
/// `q·ht(d)` and `q·ht(d) + q`, present iff `Tr(d) = 0`.  This matches the
/// general-field scan kernel term by term — except on degenerate pairs,
/// where that kernel gives up (its combined inversion hits zero) while
/// roots exist:
/// - `left == right != 0`: `A = 0`, linear, single root `C/B`;
/// - exactly one side zero: `B = 0`, `x_3^2 = C/A`, single root;
/// - `(0, 0)`: `A = B = 0`, `C = b != 0`, no roots.
///
/// Degenerate roots are returned doubled (`[r, r]`).  Callers that only
/// test `is_none` (exceptional scans) and callers that force root bits
/// (positive support, whose `first == second` arm pins the canonical
/// intermediate) both do the right thing with a doubled root.
/// One field inversion per call, no allocations.
pub fn s3_x_roots(gf: &Gf2, b: u64, left: u64, right: u64) -> Option<[u64; 2]> {
    let b = b & gf.mask;
    let s = left ^ right;
    let a = gf.sqr(s);
    let p = gf.mul(left, right);
    let ps = gf.sqr(p);
    if a == 0 {
        if left == 0 {
            // (0, 0): 0 = b != 0.  No roots.
            return None;
        }
        // Diagonal: B·x_3 + C = 0 with B = left^2 != 0.
        let root = gf.mul(ps ^ b, gf.inv(p));
        return Some([root, root]);
    }
    if ps == 0 {
        // Exactly one side is zero: A·x_3^2 + C = 0 with A != 0, C = b.
        let root = gf.sqr_k(gf.mul(b, gf.inv(a)), gf.n - 1);
        return Some([root, root]);
    }
    let inv_combined = gf.inv(gf.mul(a, ps));
    // Split the single inversion Montgomery-style: `1/a = ps·inv_c`,
    // `1/ps = a·inv_c`.
    let q = gf.mul(p, gf.mul(ps, inv_combined));
    let c = ps ^ b;
    let d = gf.mul(gf.mul(c, a), gf.mul(a, inv_combined));
    let mut half_trace = d;
    let mut power = d;
    for _ in 0..(gf.n - 1) / 2 {
        power = gf.sqr(gf.sqr(power));
        half_trace ^= power;
    }
    if (gf.sqr(half_trace) ^ half_trace) != d {
        return None;
    }
    let first = gf.mul(q, half_trace);
    Some([first, first ^ q])
}

/// One Artin-Schreier root of `u^2 + u = c` over `F_{2^n}`, if any.
///
/// Bit-exact with [`crate::cryptanalysis::binary_semaev::solve_artin_schreier`]:
/// `None` iff `Tr(c) = 1`; for odd `n` the half-trace root; for even
/// `n <= 20` the first root in integer order (replicating the slow
/// brute-force choice); for even `n > 20` `None`, matching the slow
/// fallback.  No allocations.
pub fn artin_schreier_root(gf: &Gf2, n: u32, c: u64) -> Option<u64> {
    let c = c & gf.mask;
    // Trace Tr(c) = c + c^2 + ... + c^{2^{n-1}}.
    let mut acc = c;
    let mut tr = c;
    for _ in 1..n {
        acc = gf.sqr(acc);
        tr ^= acc;
    }
    if tr == 1 {
        return None;
    }
    debug_assert!(tr == 0, "trace must lie in F_2");
    if n % 2 == 1 {
        // Half-trace H(c) = c + c^{2^2} + ... + c^{2^{n-1}}.
        let mut t = c;
        let mut a = c;
        for _ in 0..(n - 1) / 2 {
            a = gf.sqr(gf.sqr(a));
            t ^= a;
        }
        return Some(t);
    }
    if n > 20 {
        return None;
    }
    (0..(1u64 << n)).find(|&v| (gf.sqr(v) ^ v) == c)
}

/// Pack `(x, y)` exactly as [`crate::cryptanalysis::koblitz_index_calculus::pack_point`]
/// does: `0` for infinity, else `2(x + 1) + s` with `s = (y > x^y)`.
/// Exact for `n <= 62`.
#[inline]
pub fn pack_words(x: u64, y: u64) -> u64 {
    let sign = u64::from(y > (x ^ y));
    ((x + 1) << 1) | sign
}

#[inline]
pub fn pack_fast(p: FastPoint) -> u64 {
    match p {
        None => 0,
        Some((x, y)) => pack_words(x, y),
    }
}

/// Convert a general point to words; `None` when it does not fit or the
/// curve is too wide for the fast path.
pub fn point_to_words(curve: &FastBinaryCurve, p: &BinaryPoint) -> Option<FastPoint> {
    match p {
        BinaryPoint::Infinity => Some(None),
        BinaryPoint::Affine { x, y } => {
            // For n > 63 the truncation would be lossy; callers only
            // construct FastBinaryCurve for n <= 63, where every element
            // is a single word and the mask is exact.
            if curve.n > 63 {
                return None;
            }
            Some(Some((curve.word(x), curve.word(y))))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::curve::{point_add, point_double};
    use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement};
    use crate::cryptanalysis::koblitz_index_calculus::{find_irreducible_sparse, pack_point};
    use num_traits::One;
    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};

    fn toy_curve(n: u32, a: u8) -> (BinaryCurve, FastBinaryCurve) {
        let irr = find_irreducible_sparse(n).unwrap();
        let a_fe = if a == 0 {
            F2mElement::zero(n)
        } else {
            F2mElement::one(n)
        };
        let curve = BinaryCurve {
            m: n,
            irreducible: irr.clone(),
            a: a_fe,
            b: F2mElement::one(n),
            generator: BinaryPoint::Infinity,
            order: num_bigint::BigUint::one(),
            cofactor: num_bigint::BigUint::one(),
        };
        let fast = FastBinaryCurve::new(&irr, a as u64).unwrap();
        (curve, fast)
    }

    fn to_general(fast: &FastBinaryCurve, p: FastPoint) -> BinaryPoint {
        match p {
            None => BinaryPoint::Infinity,
            Some((x, y)) => BinaryPoint::Affine {
                x: fast.element(x),
                y: fast.element(y),
            },
        }
    }

    #[test]
    fn fast_add_matches_slow_on_random_points() {
        for (n, a) in [(9u32, 0u8), (11, 1), (13, 0), (23, 1), (31, 0)] {
            let (curve, fast) = toy_curve(n, a);
            let mut rng = StdRng::seed_from_u64(0x5eed ^ (n as u64));
            let mask = if n >= 64 { u64::MAX } else { (1u64 << n) - 1 };
            for _ in 0..2000 {
                let p = if rng.gen_bool(0.05) {
                    None
                } else {
                    Some((rng.gen::<u64>() & mask, rng.gen::<u64>() & mask))
                };
                let q = if rng.gen_bool(0.05) {
                    None
                } else {
                    Some((rng.gen::<u64>() & mask, rng.gen::<u64>() & mask))
                };
                let slow = point_add(&curve, &to_general(&fast, p), &to_general(&fast, q));
                let got = fast.add(p, q);
                assert_eq!(to_general(&fast, got), slow, "n={n} p={p:?} q={q:?}");
            }
        }
    }

    #[test]
    fn fast_double_matches_slow() {
        let (curve, fast) = toy_curve(13, 0);
        let mut rng = StdRng::seed_from_u64(42);
        let mask = (1u64 << 13) - 1;
        for _ in 0..2000 {
            let x: u64 = rng.gen::<u64>() & mask;
            let y: u64 = rng.gen::<u64>() & mask;
            let p = BinaryPoint::Affine {
                x: fast.element(x),
                y: fast.element(y),
            };
            assert_eq!(
                to_general(&fast, fast.double(x, y)),
                point_double(&curve, &p)
            );
        }
    }

    #[test]
    fn batch_add_matches_single_add() {
        let (_, fast) = toy_curve(17, 1);
        let mut rng = StdRng::seed_from_u64(7);
        let mask = (1u64 << 17) - 1;
        let mut pairs = Vec::new();
        for _ in 0..5000 {
            let inf1 = rng.gen_bool(0.02);
            let inf2 = rng.gen_bool(0.02);
            pairs.push((
                rng.gen::<u64>() & mask,
                rng.gen::<u64>() & mask,
                rng.gen::<u64>() & mask,
                rng.gen::<u64>() & mask,
                inf1,
                inf2,
            ));
        }
        // Force some doublings/negations.
        for k in (0..pairs.len()).step_by(97) {
            let (x1, y1, _, _, inf1, inf2) = pairs[k];
            if !inf1 && !inf2 {
                pairs[k].2 = x1;
                pairs[k].3 = y1; // P + P
            }
        }
        for k in (0..pairs.len()).step_by(131) {
            let (x1, y1, _, _, inf1, inf2) = pairs[k];
            if !inf1 && !inf2 {
                pairs[k].2 = x1;
                pairs[k].3 = x1 ^ y1; // P + (-P)
            }
        }
        let batched = fast.batch_add(&pairs);
        for (k, &(x1, y1, x2, y2, inf1, inf2)) in pairs.iter().enumerate() {
            let p = if inf1 { None } else { Some((x1, y1)) };
            let q = if inf2 { None } else { Some((x2, y2)) };
            assert_eq!(batched[k], fast.add(p, q), "row {k}");
        }
    }

    #[test]
    fn fast_scalar_mul_matches_slow() {
        use crate::binary_ecc::curve::scalar_mul;
        use num_bigint::BigUint;
        for (n, a) in [(9u32, 0u8), (13, 0), (23, 1)] {
            let (curve, fast) = toy_curve(n, a);
            let mut rng = StdRng::seed_from_u64(0xbeef ^ (n as u64));
            let mask = (1u64 << n) - 1;
            for _ in 0..200 {
                let x: u64 = rng.gen::<u64>() & mask;
                let y: u64 = rng.gen::<u64>() & mask;
                let k = BigUint::from(rng.gen_range(1u64..(1u64 << n)));
                let gp = to_general(&fast, Some((x, y)));
                assert_eq!(
                    to_general(&fast, fast.scalar_mul(Some((x, y)), &k)),
                    scalar_mul(&curve, &gp, &k),
                    "n={n}"
                );
            }
            // Zero scalar gives infinity on both paths.
            assert_eq!(
                to_general(&fast, fast.scalar_mul(Some((1, 1)), &BigUint::from(0u32))),
                scalar_mul(
                    &curve,
                    &to_general(&fast, Some((1, 1))),
                    &BigUint::from(0u32)
                ),
            );
        }
    }

    #[test]
    fn batch_double_matches_double() {
        for (n, a) in [(9u32, 0u8), (13, 0), (23, 1), (41, 0)] {
            let (_, fast) = toy_curve(n, a);
            let mut rng = StdRng::seed_from_u64(0xd8e ^ (n as u64));
            let mask = (1u64 << n) - 1;
            for _ in 0..50 {
                let pts: Vec<FastPoint> = (0..64)
                    .map(|_| {
                        let r: u64 = rng.gen_range(0..100);
                        if r < 5 {
                            None
                        } else if r < 8 {
                            Some((0, rng.gen::<u64>() & mask))
                        } else {
                            Some((rng.gen::<u64>() & mask, rng.gen::<u64>() & mask))
                        }
                    })
                    .collect();
                let got = fast.batch_double(&pts);
                assert_eq!(got.len(), pts.len());
                for (p, g) in pts.iter().zip(got.iter()) {
                    let want = match p {
                        None => None,
                        Some((x, y)) => fast.double(*x, *y),
                    };
                    assert_eq!(*g, want, "n={n} p={p:?}");
                }
            }
        }
    }

    #[test]
    fn batch_scalar_mul_matches_scalar_mul() {
        use num_bigint::BigUint;
        for (n, a) in [(9u32, 0u8), (13, 0), (23, 1), (41, 0)] {
            let (_, fast) = toy_curve(n, a);
            let mut rng = StdRng::seed_from_u64(0x8a1 ^ (n as u64));
            let mask = (1u64 << n) - 1;
            for _ in 0..25 {
                // Mixed bases (including infinity), mixed scalar lengths
                // (including zero), odd batch sizes.
                let len = rng.gen_range(1..=37);
                let mut pts = Vec::with_capacity(len);
                let mut scalars = Vec::with_capacity(len);
                for _ in 0..len {
                    pts.push(if rng.gen_bool(0.1) {
                        None
                    } else {
                        Some((rng.gen::<u64>() & mask, rng.gen::<u64>() & mask))
                    });
                    let top = rng.gen_range(0..=n);
                    let k = if top == 0 {
                        BigUint::from(0u32)
                    } else if top >= 64 {
                        BigUint::from(rng.gen::<u64>())
                    } else {
                        BigUint::from(rng.gen::<u64>() & ((1u64 << top) - 1))
                    };
                    scalars.push(k);
                }
                let got = fast.batch_scalar_mul(&pts, &scalars);
                assert_eq!(got.len(), len);
                for ((p, k), g) in pts.iter().zip(scalars.iter()).zip(got.iter()) {
                    assert_eq!(*g, fast.scalar_mul(*p, k), "n={n} p={p:?} k={k}");
                }
            }
        }
        // Empty batch.
        let (_, fast) = toy_curve(13, 0);
        assert!(fast.batch_scalar_mul(&[], &[]).is_empty());
    }

    #[test]
    fn pack_words_matches_pack_point() {
        let (_, fast) = toy_curve(23, 1);
        let mut rng = StdRng::seed_from_u64(99);
        let mask = (1u64 << 23) - 1;
        assert_eq!(pack_fast(None), pack_point(&BinaryPoint::Infinity));
        for _ in 0..5000 {
            let x: u64 = rng.gen::<u64>() & mask;
            let y: u64 = rng.gen::<u64>() & mask;
            let gp = to_general(&fast, Some((x, y)));
            assert_eq!(pack_words(x, y), pack_point(&gp));
        }
    }

    /// Slow reference: the general-field half-trace S3 solver, mirroring
    /// the orbit-factorized S5 scan kernel term by term.
    fn slow_s3_x_roots(
        irr: &crate::binary_ecc::IrreduciblePoly,
        b: &F2mElement,
        n: u32,
        left: u64,
        right: u64,
    ) -> Option<[u64; 2]> {
        use num_bigint::BigUint;
        let e = |w: u64| F2mElement::from_biguint(&BigUint::from(w), n);
        let (l, r) = (e(left), e(right));
        let sum = l.add(&r);
        let a = sum.square(irr);
        let product = l.mul(&r, irr);
        let product_square = product.square(irr);
        let inverse_combined = a.mul(&product_square, irr).flt_inverse(irr)?;
        let inverse_a = product_square.mul(&inverse_combined, irr);
        let inverse_product_square = a.mul(&inverse_combined, irr);
        let q = product.mul(&inverse_a, irr);
        let c = product_square.add(b);
        let d = c.mul(&a, irr).mul(&inverse_product_square, irr);
        let mut half_trace = d.clone();
        let mut power = d.clone();
        for _ in 0..(n - 1) / 2 {
            power = power.square(irr).square(irr);
            half_trace = half_trace.add(&power);
        }
        if half_trace.square(irr).add(&half_trace) != d {
            return None;
        }
        let first = q.mul(&half_trace, irr);
        let second = first.add(&q);
        let raw = |v: &F2mElement| v.raw_bits().first().copied().unwrap_or(0);
        Some([raw(&first), raw(&second)])
    }

    #[test]
    fn s3_roots_match_slow_reference_on_generic_pairs() {
        use crate::cryptanalysis::semaev_decomp::Gf2;
        // Generic pairs only (both sides nonzero and unequal): the fast
        // kernel must agree with the slow one bit for bit, including
        // verdict and root order.  Degenerate pairs are covered by
        // `s3_roots_degenerate_pairs_are_exact` — the slow kernel gives
        // up on those (combined inversion of zero) while roots exist.
        for n in [9u32, 13, 23, 41, 53] {
            let irr = find_irreducible_sparse(n).unwrap();
            let gf = Gf2::new(&irr);
            let b_fe = F2mElement::one(n);
            let mut rng = StdRng::seed_from_u64(0x53eed ^ (n as u64));
            let mask = if n >= 64 { u64::MAX } else { (1u64 << n) - 1 };
            for _ in 0..2000 {
                let (left, right) = (rng.gen::<u64>() & mask, rng.gen::<u64>() & mask);
                if left == 0 || right == 0 || left == right {
                    continue;
                }
                assert_eq!(
                    s3_x_roots(&gf, 1, left, right),
                    slow_s3_x_roots(&irr, &b_fe, n, left, right),
                    "n={n} left={left} right={right}"
                );
            }
        }
    }

    #[test]
    fn s3_roots_degenerate_pairs_are_exact() {
        use crate::cryptanalysis::binary_semaev::binary_semaev_s3;
        use crate::cryptanalysis::semaev_decomp::Gf2;
        // Diagonal (x, x): linear, single root.  Zero side: x_3^2 = C/A,
        // single root.  (0, 0): genuinely rootless.  Each returned root
        // must vanish under S3; single-root cases are complete by degree
        // (at most one root exists), (0, 0) by C = b != 0.
        for n in [9u32, 13, 23, 41, 53] {
            let irr = find_irreducible_sparse(n).unwrap();
            let gf = Gf2::new(&irr);
            let b_fe = F2mElement::one(n);
            let e = |w: u64| F2mElement::from_biguint(&num_bigint::BigUint::from(w), n);
            let mask = (1u64 << n) - 1;
            let mut xs = vec![0u64, 1, 2, mask];
            let mut rng = StdRng::seed_from_u64(0xd363 ^ (n as u64));
            for _ in 0..64 {
                xs.push(rng.gen::<u64>() & mask);
            }
            for &x in &xs {
                // Diagonal.
                match s3_x_roots(&gf, 1, x, x) {
                    Some([f, s]) if x != 0 => {
                        assert_eq!(f, s, "diagonal root is doubled");
                        assert!(
                            binary_semaev_s3(&e(x), &e(x), &e(f), &b_fe, &irr).is_zero(),
                            "n={n} diagonal root vanishes"
                        );
                    }
                    None => assert_eq!(x, 0, "only (0,0) is rootless"),
                    _ => panic!("unexpected diagonal shape"),
                }
                // Zero sides.
                for &(l, r) in &[(x, 0), (0, x)] {
                    match s3_x_roots(&gf, 1, l, r) {
                        Some([f, s]) if x != 0 => {
                            assert_eq!(f, s, "zero-side root is doubled");
                            assert!(
                                binary_semaev_s3(&e(l), &e(r), &e(f), &b_fe, &irr).is_zero(),
                                "n={n} zero-side root vanishes"
                            );
                        }
                        None => assert_eq!(x, 0, "only (0,0) is rootless"),
                        _ => panic!("unexpected zero-side shape"),
                    }
                }
                // The slow kernel is known-None on every degenerate pair
                // (its combined inversion hits zero) — pin that, so a
                // future reader sees the divergence is deliberate.
                assert!(slow_s3_x_roots(&irr, &b_fe, n, x, x).is_none());
                assert!(slow_s3_x_roots(&irr, &b_fe, n, x, 0).is_none());
                assert!(slow_s3_x_roots(&irr, &b_fe, n, 0, x).is_none());
            }
        }
    }

    #[test]
    fn s3_roots_satisfy_semaev_independently() {
        use crate::cryptanalysis::binary_semaev::binary_semaev_s3;
        use crate::cryptanalysis::semaev_decomp::Gf2;
        for n in [13u32, 41, 53] {
            let irr = find_irreducible_sparse(n).unwrap();
            let gf = Gf2::new(&irr);
            let b_fe = F2mElement::one(n);
            let mut rng = StdRng::seed_from_u64(0xf053 ^ (n as u64));
            let mask = (1u64 << n) - 1;
            let mut checked_some = 0;
            let mut checked_none = 0;
            for _ in 0..2000 {
                let (left, right) = (rng.gen::<u64>() & mask, rng.gen::<u64>() & mask);
                if left == 0 || right == 0 || left == right {
                    continue; // degenerate pairs: see s3_roots_degenerate_pairs_are_exact
                }
                let e = |w: u64| F2mElement::from_biguint(&num_bigint::BigUint::from(w), n);
                match s3_x_roots(&gf, 1, left, right) {
                    Some([f, s]) => {
                        assert!(
                            binary_semaev_s3(&e(left), &e(right), &e(f), &b_fe, &irr).is_zero()
                                && binary_semaev_s3(&e(left), &e(right), &e(s), &b_fe, &irr)
                                    .is_zero(),
                            "n={n} roots must vanish under S3"
                        );
                        assert_ne!(f, s, "the two roots are distinct (q != 0)");
                        checked_some += 1;
                    }
                    None => {
                        // The slow reference agrees this pair has no roots.
                        assert!(
                            slow_s3_x_roots(&irr, &b_fe, n, left, right).is_none(),
                            "n={n} fast-None must agree with slow-None"
                        );
                        checked_none += 1;
                    }
                }
            }
            assert!(
                checked_some > 0 && checked_none > 0,
                "both verdicts occur at n={n}"
            );
        }
    }

    #[test]
    fn s3_roots_none_is_exact_on_tiny_field() {
        use crate::cryptanalysis::binary_semaev::binary_semaev_s3;
        use crate::cryptanalysis::semaev_decomp::Gf2;
        // Exhaustive at n = 7: fast-None holds iff no x3 in F_{2^7}
        // zeroes S3, and fast-Some returns exactly the full root set.
        let n = 7u32;
        let irr = find_irreducible_sparse(n).unwrap();
        let gf = Gf2::new(&irr);
        let b_fe = F2mElement::one(n);
        let e = |w: u64| F2mElement::from_biguint(&num_bigint::BigUint::from(w), n);
        let mut some_count = 0;
        let mut none_count = 0;
        for left in 0..(1u64 << n) {
            for right in 0..(1u64 << n) {
                let mut actual = Vec::new();
                for x3 in 0..(1u64 << n) {
                    if binary_semaev_s3(&e(left), &e(right), &e(x3), &b_fe, &irr).is_zero() {
                        actual.push(x3);
                    }
                }
                match s3_x_roots(&gf, 1, left, right) {
                    Some([f, s]) => {
                        some_count += 1;
                        let mut got = [f, s];
                        got.sort_unstable();
                        actual.sort_unstable();
                        actual.dedup();
                        let mut want = got.to_vec();
                        want.dedup();
                        assert_eq!(
                            want.as_slice(),
                            actual.as_slice(),
                            "root set at ({left},{right})"
                        );
                        // Doubled roots happen exactly on degenerate
                        // pairs (linear / x_3^2 cases); generic pairs
                        // return two distinct roots.
                        assert_eq!(
                            f == s,
                            left == right || left == 0 || right == 0,
                            "doubling only on degenerate pairs"
                        );
                    }
                    None => {
                        none_count += 1;
                        assert!(
                            actual.is_empty(),
                            "fast-None with roots at ({left},{right})"
                        );
                    }
                }
            }
        }
        assert!(some_count > 0 && none_count > 0, "both verdicts occur");
    }

    #[test]
    fn artin_schreier_root_matches_slow() {
        use crate::cryptanalysis::binary_semaev::solve_artin_schreier;
        use crate::cryptanalysis::semaev_decomp::Gf2;
        for n in [7u32, 9, 13, 23, 41, 53] {
            let irr = find_irreducible_sparse(n).unwrap();
            let gf = Gf2::new(&irr);
            let mut rng = StdRng::seed_from_u64(0xa57 ^ (n as u64));
            let mask = (1u64 << n) - 1;
            let mut some = 0;
            let mut none = 0;
            for _ in 0..1500 {
                let c = rng.gen::<u64>() & mask;
                let fast = artin_schreier_root(&gf, n, c);
                let slow =
                    solve_artin_schreier(&gf.to_element(c), n, &irr).map(|e| gf.from_element(&e));
                assert_eq!(fast, slow, "n={n} c={c}");
                // Any returned root genuinely solves u^2 + u = c.
                if let Some(u) = fast {
                    assert_eq!(gf.sqr(u) ^ u, c);
                    some += 1;
                } else {
                    none += 1;
                }
            }
            assert!(some > 0 && none > 0, "both verdicts occur at n={n}");
        }
    }

    #[test]
    fn fast_points_with_x_matches_slow() {
        use crate::cryptanalysis::koblitz_index_calculus::points_with_x as slow_points_with_x;
        use crate::cryptanalysis::semaev_decomp::Gf2;
        for (n, a) in [(7u32, 0u8), (9, 0), (13, 0), (23, 1), (41, 0), (53, 0)] {
            let (curve, fast) = toy_curve(n, a);
            let gf = Gf2::new(&curve.irreducible);
            let b = gf.from_element(&curve.b);
            let mask = (1u64 << n) - 1;
            let mut xs: Vec<u64> = vec![0, 1, 2, mask];
            let mut rng = StdRng::seed_from_u64(0x901 ^ (n as u64));
            for _ in 0..500 {
                xs.push(rng.gen::<u64>() & mask);
            }
            if n <= 9 {
                // Exhaustive on tiny fields.
                xs.extend(0..(1u64 << n));
            }
            let mut some_empty = false;
            let mut some_full = false;
            for x in xs {
                let got: Vec<BinaryPoint> = fast
                    .points_with_x(b, x)
                    .into_iter()
                    .map(|p| to_general(&fast, p))
                    .collect();
                let want = slow_points_with_x(
                    &curve,
                    &F2mElement::from_biguint(&num_bigint::BigUint::from(x), n),
                );
                assert_eq!(got, want, "n={n} x={x}: same points in same order");
                if got.is_empty() {
                    some_empty = true;
                } else {
                    some_full = true;
                    // Every returned point is on the curve with the right x.
                    for pt in &got {
                        assert!(curve.is_on_curve(pt));
                    }
                }
            }
            assert!(some_empty && some_full, "both verdicts occur at n={n}");
        }
    }
}
