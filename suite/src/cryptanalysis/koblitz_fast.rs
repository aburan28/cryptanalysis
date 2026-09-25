//! Single-word point arithmetic for the hot loops of the Koblitz index
//! calculus: the pair-sum table, the `|F|` subtractions of an `m = 3`
//! decomposition, the probe `[a]G + [b]Q` of every trial, and the
//! signed-Frobenius ρ walk the pipeline is measured against.
//!
//! The general [`BinaryPoint`] carries `Vec<u64>`-backed coordinates and
//! allocates on every field operation, which for the `n ≤ 62` fields the
//! pipeline actually runs in costs two orders of magnitude more than the
//! arithmetic.  Every operation here is a few carry-less multiplies on a
//! [`Gf2`] and never allocates; a slice of additions sharing one summand
//! is done with a single field inversion by Montgomery's trick.
//!
//! The formulas are exactly those of [`crate::binary_ecc::curve`]
//! (`y² + xy = x³ + ax² + b`), and the tests below check every operation
//! against that reference on random points, so the two representations
//! are interchangeable: [`FastCurve::lift`] and [`FastCurve::lower`]
//! convert.  Results handed back to the pipeline are still re-verified
//! in the general arithmetic where the code already did so.

use num_bigint::BigUint;

use crate::binary_ecc::{BinaryCurve, BinaryPoint, F2mElement};
use crate::cryptanalysis::semaev_decomp::Gf2;

/// A point with single-word coordinates, or `O`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct FastPoint {
    pub x: u64,
    pub y: u64,
    pub infinity: bool,
}

impl FastPoint {
    /// The point at infinity.
    pub const INFINITY: Self = Self {
        x: 0,
        y: 0,
        infinity: true,
    };

    /// An affine point.
    pub fn affine(x: u64, y: u64) -> Self {
        Self {
            x,
            y,
            infinity: false,
        }
    }

    /// Packed identity, identical to
    /// [`crate::cryptanalysis::koblitz_index_calculus::pack_point`] on the
    /// lowered point: `0` for `O`, otherwise `2(x + 1) + s` with the sign
    /// bit `s` separating `P` from `−P`.
    #[inline]
    pub fn pack(self) -> u64 {
        if self.infinity {
            0
        } else {
            let sign = u64::from(self.y > (self.x ^ self.y));
            ((self.x + 1) << 1) | sign
        }
    }
}

/// A point in López–Dahab projective coordinates, `(X : Y : Z)` for the
/// affine `(X/Z, Y/Z²)`, with `Z = 0` standing for `O`.  Internal to the
/// scalar multiplication; nothing outside [`FastCurve`] sees one.
#[derive(Clone, Copy, Debug)]
struct LdPoint {
    x: u64,
    y: u64,
    z: u64,
}

impl LdPoint {
    const INFINITY: Self = Self { x: 1, y: 0, z: 0 };
}

/// `y² + xy = x³ + ax² + b` over `F_{2^n}`, `n ≤ 62`, in one word per
/// coordinate.
#[derive(Clone, Debug)]
pub struct FastCurve {
    pub field: Gf2,
    pub n: u32,
    pub a: u64,
    pub b: u64,
    /// The eight-lane AVX-512 kernel for [`Self::add_many_lazy`], when
    /// the CPU has it and the field's reduction polynomial suits it.
    #[cfg(all(target_arch = "x86_64", suite_avx512))]
    simd: Option<simd512::Simd512>,
}

impl FastCurve {
    /// Largest extension degree handled: the packed identity needs
    /// `2(x + 1)` to fit in a word.
    pub const MAX_DEGREE: u32 = 62;

    /// `None` when the field is too wide.
    pub fn new(curve: &BinaryCurve) -> Option<Self> {
        if curve.m > Self::MAX_DEGREE || curve.irreducible.degree != curve.m {
            return None;
        }
        let field = Gf2::new(&curve.irreducible);
        let a = field.from_element(&curve.a);
        let b = field.from_element(&curve.b);
        Some(Self {
            #[cfg(all(target_arch = "x86_64", suite_avx512))]
            simd: simd512::Simd512::new(&field),
            field,
            n: curve.m,
            a,
            b,
        })
    }

    /// Project a general point down.
    pub fn lift(&self, p: &BinaryPoint) -> FastPoint {
        match p {
            BinaryPoint::Infinity => FastPoint::INFINITY,
            BinaryPoint::Affine { x, y } => {
                FastPoint::affine(self.field.from_element(x), self.field.from_element(y))
            }
        }
    }

    /// Lift back to the general representation.
    pub fn lower(&self, p: FastPoint) -> BinaryPoint {
        if p.infinity {
            BinaryPoint::Infinity
        } else {
            BinaryPoint::Affine {
                x: self.element(p.x),
                y: self.element(p.y),
            }
        }
    }

    fn element(&self, v: u64) -> F2mElement {
        F2mElement::from_biguint(&BigUint::from(v), self.n)
    }

    /// Whether `p` satisfies the curve equation.
    pub fn is_on_curve(&self, p: FastPoint) -> bool {
        if p.infinity {
            return true;
        }
        let f = &self.field;
        let lhs = f.sqr(p.y) ^ f.mul(p.x, p.y);
        let x2 = f.sqr(p.x);
        let rhs = f.mul(x2, p.x) ^ f.mul(self.a, x2) ^ self.b;
        lhs == rhs
    }

    /// `−P = (x, x + y)`.
    #[inline]
    pub fn neg(&self, p: FastPoint) -> FastPoint {
        if p.infinity {
            p
        } else {
            FastPoint::affine(p.x, p.x ^ p.y)
        }
    }

    /// `[2]P`.
    pub fn double(&self, p: FastPoint) -> FastPoint {
        if p.infinity || p.x == 0 {
            return FastPoint::INFINITY;
        }
        let f = &self.field;
        let lambda = p.x ^ f.mul(p.y, f.inv(p.x));
        self.double_with_lambda(p, lambda)
    }

    #[inline]
    fn double_with_lambda(&self, p: FastPoint, lambda: u64) -> FastPoint {
        let f = &self.field;
        let x3 = f.sqr(lambda) ^ lambda ^ self.a;
        let y3 = f.sqr(p.x) ^ f.mul(lambda ^ 1, x3);
        FastPoint::affine(x3, y3)
    }

    #[inline]
    fn add_with_lambda(&self, p: FastPoint, q: FastPoint, lambda: u64) -> FastPoint {
        let f = &self.field;
        let x3 = f.sqr(lambda) ^ lambda ^ p.x ^ q.x ^ self.a;
        let y3 = f.mul(lambda, p.x ^ x3) ^ x3 ^ p.y;
        FastPoint::affine(x3, y3)
    }

    /// `P + Q`.
    pub fn add(&self, p: FastPoint, q: FastPoint) -> FastPoint {
        if p.infinity {
            return q;
        }
        if q.infinity {
            return p;
        }
        if p.x == q.x {
            if p.y ^ q.y == p.x {
                return FastPoint::INFINITY;
            }
            return self.double(p);
        }
        let f = &self.field;
        let lambda = f.mul(p.y ^ q.y, f.inv(p.x ^ q.x));
        self.add_with_lambda(p, q, lambda)
    }

    /// `P + Q_j` for every `j`, appended to `out`, with **one** field
    /// inversion for the whole slice (Montgomery's trick over the
    /// denominators `x_P + x_{Q_j}`).  Degenerate pairs (an `O`
    /// operand, `Q_j = ±P`) are handled individually.
    pub fn add_many(
        &self,
        p: FastPoint,
        qs: &[FastPoint],
        out: &mut Vec<FastPoint>,
        scratch: &mut BatchScratch,
    ) {
        let f = &self.field;
        scratch.dens.clear();
        scratch.dens.extend(qs.iter().map(|q| {
            if p.infinity || q.infinity || q.x == p.x {
                0
            } else {
                p.x ^ q.x
            }
        }));
        f.batch_inv(&mut scratch.dens, &mut scratch.acc);
        let mut double_p: Option<FastPoint> = None;
        out.reserve(qs.len());
        for (q, &inv) in qs.iter().zip(&scratch.dens) {
            if inv == 0 {
                let sum = if p.infinity {
                    *q
                } else if q.infinity {
                    p
                } else if p.y ^ q.y == p.x {
                    FastPoint::INFINITY
                } else {
                    *double_p.get_or_insert_with(|| self.double(p))
                };
                out.push(sum);
                continue;
            }
            let lambda = f.mul(p.y ^ q.y, inv);
            out.push(self.add_with_lambda(p, *q, lambda));
        }
    }

    /// [`Self::add_many`] without the ordinates: each sum's `x` and `O`
    /// flag are final, its `y` is left at `0`, and its slope `λ` is
    /// appended to `lambdas` for [`Self::finish_lazy`] to complete it
    /// later.  Degenerate sums (an `O` operand, `Q_j = ±P`) come back
    /// complete, marked by `λ = LAZY_DONE`.
    ///
    /// A decomposition scan keys every `R − P_k` by its abscissa alone
    /// and looks at the full point only for the few the table's filter
    /// admits, so computing `y` for the rest is a multiplication per
    /// point spent on nothing.
    pub fn add_many_lazy(
        &self,
        p: FastPoint,
        qs: &[FastPoint],
        out: &mut Vec<FastPoint>,
        lambdas: &mut Vec<u64>,
        scratch: &mut BatchScratch,
    ) {
        #[cfg(all(target_arch = "x86_64", suite_avx512))]
        if let Some(simd) = &self.simd {
            if simd.add_many_lazy(self, p, qs, out, lambdas, scratch) {
                return;
            }
        }
        self.add_many_lazy_scalar(p, qs, out, lambdas, scratch);
    }

    /// The portable body of [`Self::add_many_lazy`]; also what the SIMD
    /// kernel falls back to on a block with a degenerate sum.
    fn add_many_lazy_scalar(
        &self,
        p: FastPoint,
        qs: &[FastPoint],
        out: &mut Vec<FastPoint>,
        lambdas: &mut Vec<u64>,
        scratch: &mut BatchScratch,
    ) {
        let f = &self.field;
        scratch.dens.clear();
        scratch.dens.extend(qs.iter().map(|q| {
            if p.infinity || q.infinity || q.x == p.x {
                0
            } else {
                p.x ^ q.x
            }
        }));
        f.batch_inv(&mut scratch.dens, &mut scratch.acc);
        out.reserve(qs.len());
        lambdas.reserve(qs.len());
        for (q, &inv) in qs.iter().zip(&scratch.dens) {
            if inv == 0 {
                out.push(self.add(p, *q));
                lambdas.push(Self::LAZY_DONE);
                continue;
            }
            let lambda = f.mul(p.y ^ q.y, inv);
            let x3 = f.sqr(lambda) ^ lambda ^ p.x ^ q.x ^ self.a;
            out.push(FastPoint::affine(x3, 0));
            lambdas.push(lambda);
        }
    }

    /// The `λ` [`Self::add_many_lazy`] records for a sum it already
    /// completed.  No real slope equals it: a field element has fewer
    /// than 63 bits.
    pub const LAZY_DONE: u64 = u64::MAX;

    /// Complete a sum from [`Self::add_many_lazy`]: `y₃ = λ(x_P + x₃) +
    /// x₃ + y_P`, exactly as [`Self::add`] computes it.
    #[inline]
    pub fn finish_lazy(&self, p: FastPoint, sum: FastPoint, lambda: u64) -> FastPoint {
        if lambda == Self::LAZY_DONE {
            return sum;
        }
        let y3 = self.field.mul(lambda, p.x ^ sum.x) ^ sum.x ^ p.y;
        FastPoint::affine(sum.x, y3)
    }

    /// `P_i + Q_i` for every `i`, appended to `out`, with **one** field
    /// inversion for the whole slice.  This is what lets many
    /// independent walks share the cost of the one inversion a point
    /// addition needs: with `w` walks stepping together the inversion
    /// costs `3 + 1/w` multiplications each instead of the `2n` a
    /// Fermat inversion takes.
    pub fn add_pairwise(
        &self,
        ps: &[FastPoint],
        qs: &[FastPoint],
        out: &mut Vec<FastPoint>,
        scratch: &mut BatchScratch,
    ) {
        assert_eq!(ps.len(), qs.len(), "pairwise addition needs equal slices");
        let f = &self.field;
        scratch.dens.clear();
        scratch.dens.extend(ps.iter().zip(qs).map(|(p, q)| {
            if p.infinity || q.infinity || p.x == q.x {
                0
            } else {
                p.x ^ q.x
            }
        }));
        f.batch_inv(&mut scratch.dens, &mut scratch.acc);
        out.reserve(ps.len());
        for ((p, q), &inv) in ps.iter().zip(qs).zip(&scratch.dens) {
            if inv == 0 {
                out.push(self.add(*p, *q));
                continue;
            }
            let lambda = f.mul(p.y ^ q.y, inv);
            out.push(self.add_with_lambda(*p, *q, lambda));
        }
    }

    /// `[k]P` by double-and-add.
    pub fn mul_u64(&self, p: FastPoint, k: u64) -> FastPoint {
        if k == 0 || p.infinity {
            return FastPoint::INFINITY;
        }
        self.ladder(p, 64 - k.leading_zeros() as u64, |i| (k >> i) & 1 == 1)
    }

    /// `[k]P` for a scalar of any size.
    pub fn mul(&self, p: FastPoint, k: &BigUint) -> FastPoint {
        let bits = k.bits();
        if bits == 0 || p.infinity {
            return FastPoint::INFINITY;
        }
        self.ladder(p, bits, |i| k.bit(i))
    }

    /// Left-to-right double-and-add over the `bits` low bits of a scalar,
    /// in López–Dahab coordinates with **one** inversion at the end.
    ///
    /// The affine double-and-add this replaces paid a Fermat inversion —
    /// `n − 1` squarings and several multiplications — on every doubling
    /// and every addition.  López–Dahab `(X : Y : Z) ↦ (X/Z, Y/Z²)` needs
    /// none: a doubling is five squarings and four multiplications, a
    /// mixed addition of the affine `P` nine multiplications and five
    /// squarings, and the single inversion converts the result back.
    /// The point is the same, so everything downstream — the probe, the
    /// pair table, the pinned counters — sees no difference.
    fn ladder(&self, p: FastPoint, bits: u64, bit: impl Fn(u64) -> bool) -> FastPoint {
        let mut r = LdPoint::INFINITY;
        for i in (0..bits).rev() {
            r = self.ld_double(r);
            if bit(i) {
                r = self.ld_add_affine(r, p);
            }
        }
        self.ld_to_affine(r)
    }

    /// López–Dahab doubling (Hankerson–Menezes–Vanstone, Alg. 3.24):
    /// `Z₃ = X₁²Z₁²`, `X₃ = X₁⁴ + bZ₁⁴`,
    /// `Y₃ = bZ₁⁴·Z₃ + X₃·(aZ₃ + Y₁² + bZ₁⁴)`.  `O` and the 2-torsion
    /// point (`X₁ = 0`) both give `Z₃ = 0`, which is `O`.
    #[inline]
    fn ld_double(&self, p: LdPoint) -> LdPoint {
        if p.z == 0 {
            return LdPoint::INFINITY;
        }
        let f = &self.field;
        let x2 = f.sqr(p.x);
        let z2 = f.sqr(p.z);
        let z3 = f.mul(x2, z2);
        let bz4 = f.mul(self.b, f.sqr(z2));
        let x3 = f.sqr(x2) ^ bz4;
        let az3 = match self.a {
            0 => 0,
            1 => z3,
            a => f.mul(a, z3),
        };
        let y3 = f.mul(bz4, z3) ^ f.mul(x3, az3 ^ f.sqr(p.y) ^ bz4);
        LdPoint {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// López–Dahab `P + Q` for an affine `Q ≠ O`
    /// (Hankerson–Menezes–Vanstone, Alg. 3.25, general `a`):
    /// `A = Y₁ + y₂Z₁²`, `B = X₁ + x₂Z₁`, `C = BZ₁`, `Z₃ = C²`,
    /// `X₃ = A² + C(A + B² + aC)`,
    /// `Y₃ = (x₂Z₃ + X₃)(AC + Z₃) + (x₂ + y₂)Z₃²`.
    /// `B = 0` means equal abscissae: `Q` again (double it) or `−Q` (`O`).
    #[inline]
    fn ld_add_affine(&self, p: LdPoint, q: FastPoint) -> LdPoint {
        let affine_q = LdPoint {
            x: q.x,
            y: q.y,
            z: 1,
        };
        if p.z == 0 {
            return affine_q;
        }
        let f = &self.field;
        let z1_2 = f.sqr(p.z);
        let a_ = p.y ^ f.mul(q.y, z1_2);
        let b_ = p.x ^ f.mul(q.x, p.z);
        if b_ == 0 {
            return if a_ == 0 {
                self.ld_double(affine_q)
            } else {
                LdPoint::INFINITY
            };
        }
        let c = f.mul(b_, p.z);
        let z3 = f.sqr(c);
        let ac = match self.a {
            0 => 0,
            1 => c,
            a => f.mul(a, c),
        };
        let x3 = f.sqr(a_) ^ f.mul(c, a_ ^ f.sqr(b_) ^ ac);
        let y3 = f.mul(f.mul(q.x, z3) ^ x3, f.mul(a_, c) ^ z3) ^ f.mul(q.x ^ q.y, f.sqr(z3));
        LdPoint {
            x: x3,
            y: y3,
            z: z3,
        }
    }

    /// Back to affine: `(X/Z, Y/Z²)`, one inversion.
    #[inline]
    fn ld_to_affine(&self, p: LdPoint) -> FastPoint {
        if p.z == 0 {
            return FastPoint::INFINITY;
        }
        let f = &self.field;
        let zi = f.inv(p.z);
        FastPoint::affine(f.mul(p.x, zi), f.mul(p.y, f.sqr(zi)))
    }

    /// The `2^k`-power Frobenius `(x, y) ↦ (x^{2^k}, y^{2^k})`.
    #[inline]
    pub fn frobenius_k(&self, p: FastPoint, k: u32) -> FastPoint {
        if p.infinity {
            return p;
        }
        FastPoint::affine(self.field.sqr_k(p.x, k), self.field.sqr_k(p.y, k))
    }
}

/// **Canonical names for Frobenius orbits of abscissae**, in a normal
/// basis where the Frobenius is a rotation.
///
/// The folded pair table needs one key per orbit of `x` under `x ↦ x²`,
/// and the obvious one — the least element of the orbit — costs `n − 1`
/// squarings, a dependency chain of spreads and reduction-table lookups.
/// In a normal basis `{β, β², β⁴, …}` the same map is a one-bit cyclic
/// rotation of the coordinate word, because `(Σ c_k β^{2^k})² =
/// Σ c_k β^{2^{k+1}}`.  So the orbit of `x` is the set of rotations of
/// its coordinate word, and the least rotation names it.
///
/// The change of basis is one `F_2`-linear map, applied as eight
/// byte-table lookups; the minimum is `n` rotations of a word.  Nothing
/// is squared and nothing is reduced.
///
/// The key it produces is *not* the least element of the orbit in the
/// polynomial basis — it is a different function of the point.  What
/// matters is only that it is constant on orbits and distinct across
/// them, which a bijective linear map followed by a rotation-invariant
/// minimum is.
#[derive(Clone, Debug)]
pub struct FrobeniusCanon {
    n: u32,
    mask: u64,
    /// `tables[i][b]`: the normal coordinates of the field element whose
    /// `i`-th byte is `b` and whose other bytes are zero.
    tables: Vec<[u64; 256]>,
}

impl FrobeniusCanon {
    /// Build the basis change, or `None` if no normal element turns up —
    /// which the normal basis theorem says will not happen, but the
    /// search is randomised and bounded rather than trusted.
    pub fn new(field: &Gf2, n: u32) -> Option<Self> {
        if n == 0 || n > 63 {
            return None;
        }
        let mask = (1u64 << n) - 1;
        // A normal element: one whose Frobenius orbit is a basis.
        let mut inverse = None;
        let mut candidate = 2u64;
        for _ in 0..4096 {
            candidate = candidate.wrapping_mul(0x9e37_79b9_7f4a_7c15) ^ (candidate >> 29);
            let gamma = candidate & mask;
            if gamma == 0 {
                continue;
            }
            // Columns of the map "normal coordinates -> field element".
            let mut column = gamma;
            let columns: Vec<u64> = (0..n)
                .map(|_| {
                    let c = column;
                    column = field.sqr(column);
                    c
                })
                .collect();
            if let Some(inv) = invert_f2(&columns, n) {
                inverse = Some(inv);
                break;
            }
        }
        let inverse = inverse?;
        // Column `j` of the inverse, so a set bit of `x` contributes one
        // XOR rather than one parity.
        let by_bit: Vec<u64> = (0..n)
            .map(|j| (0..n).fold(0u64, |acc, i| acc | (((inverse[i as usize] >> j) & 1) << i)))
            .collect();
        let bytes = n.div_ceil(8) as usize;
        let tables = (0..bytes)
            .map(|bi| {
                let mut table = [0u64; 256];
                for (b, slot) in table.iter_mut().enumerate() {
                    let mut acc = 0u64;
                    for t in 0..8 {
                        let j = bi * 8 + t;
                        if (b >> t) & 1 == 1 && j < n as usize {
                            acc ^= by_bit[j];
                        }
                    }
                    *slot = acc;
                }
                table
            })
            .collect();
        Some(Self { n, mask, tables })
    }

    /// The normal coordinates of a field element.
    #[inline]
    pub fn coords(&self, x: u64) -> u64 {
        let mut acc = 0u64;
        for (i, table) in self.tables.iter().enumerate() {
            acc ^= table[((x >> (8 * i)) & 0xff) as usize];
        }
        acc
    }

    /// The least rotation of the normal coordinates: a name for the
    /// Frobenius orbit of `x`, equal for every element of it and for no
    /// element outside it.
    #[inline]
    pub fn canon(&self, x: u64) -> u64 {
        self.least_rotation(self.coords(x)).0
    }

    /// The canonical name together with the rotation that produced it:
    /// `(c, t)` with `c = rotl^t(coords(x))`, `0 ≤ t < n`.  Two abscissae
    /// with one name are Frobenius conjugates, and the shift says which
    /// power: `coords(x') = rotl^{t − t'}(coords(x))`, so `x' = x^{2^{t − t'}}`.
    #[inline]
    pub fn canon_with_shift(&self, x: u64) -> (u64, u32) {
        self.least_rotation(self.coords(x))
    }

    /// `rotl^t` on `n`-bit words, `0 ≤ t < n`.
    #[inline(always)]
    fn rotl(&self, v: u64, t: u32) -> u64 {
        if t == 0 {
            v
        } else {
            ((v << t) | (v >> (self.n - t))) & self.mask
        }
    }

    /// The least of the `n` cyclic rotations of `c`, and the smallest
    /// `t` with `rotl^t(c)` equal to it.
    ///
    /// Trying all `n` rotations is a serial chain of `n − 1` rotate-and-
    /// compare steps per point.  It need not be: `rotl^t(c)` has as many
    /// leading zeros as the zero run of `c` that ends at bit `n − 1 − t`,
    /// and more leading zeros is a smaller word, so the least rotation
    /// starts at one of the *longest* cyclic zero runs of `c`.  Those are
    /// found with one AND-with-rotate per bit of run length —
    /// `Z_k = Z_{k−1} ∧ rotl^{k−1}(¬c)` has bit `p` set exactly when bits
    /// `p, p−1, …, p−k+1` of `c` are all zero — which for a random word is
    /// about `log₂ n` steps.  Only the rotations that begin at one of the
    /// `Z_L` positions are then compared, usually one or two.
    ///
    /// Bit-for-bit the same answer as the exhaustive scan (the tests
    /// check it on every word pattern class, including periodic ones where
    /// several rotations tie and the smallest `t` must win).
    #[inline]
    fn least_rotation(&self, c: u64) -> (u64, u32) {
        let n = self.n;
        let zeros = !c & self.mask;
        if zeros == 0 || c == 0 {
            // All ones, or all zeros: every rotation is the same word.
            return (c, 0);
        }
        // Grow the run length while some run is still that long.
        let mut run = zeros;
        let mut len = 1u32;
        loop {
            let next = run & self.rotl(zeros, len);
            if next == 0 {
                break;
            }
            run = next;
            len += 1;
        }
        // `run` marks the top bit `p` of every zero run of length `len`.
        let mut best = u64::MAX;
        let mut best_t = 0u32;
        let mut tops = run;
        while tops != 0 {
            let p = tops.trailing_zeros();
            tops &= tops - 1;
            let t = n - 1 - p;
            let v = self.rotl(c, t);
            if v < best || (v == best && t < best_t) {
                best = v;
                best_t = t;
            }
        }
        (best, best_t)
    }

    /// [`Self::canon`] of every element of `xs`, appended to `out` in
    /// order — the same values, computed in bulk.
    ///
    /// On AVX-512 this computes every rotation instead of searching for
    /// the least one — `n − 1` rotate-and-min steps on sixteen keys at
    /// once in two independent registers, with no branch that depends on
    /// the data.  The basis change stays a scalar table walk: in a vector
    /// it would be a gather.
    ///
    /// What was measured, and what was not (`n = 53`, one host):
    /// on its own, over fresh abscissae, this is *slower* than the scalar
    /// key — 16.6 ns against 13.4 ns a key (`examples/scan_block_bench.rs`).
    /// Inside a decomposition scan the scalar key costs about 28 ns (scan
    /// with and without keying), and with this one the scan falls from
    /// 61 ns to 39–41 ns a summand and the `k0n53` pipeline from 1.43 s to
    /// 1.05 s.  Why the scalar key is dearer in context was not
    /// established; interference from the surrounding kernels on the
    /// branch predictor or the micro-op cache are candidates, untested.
    /// Use it where it has been measured to win.
    pub fn canon_many(&self, xs: &[u64], out: &mut Vec<u64>) {
        let start = out.len();
        out.extend_from_slice(xs);
        self.canon_in_place(&mut out[start..]);
    }

    /// [`Self::canon_many`] overwriting its input: every `x` becomes
    /// [`Self::canon`]`(x)`.
    pub fn canon_in_place(&self, xs: &mut [u64]) {
        #[cfg(all(target_arch = "x86_64", suite_avx512))]
        if canon_simd_enabled() {
            let mut chunks = xs.chunks_exact_mut(16);
            for chunk in &mut chunks {
                let mut c = [0u64; 16];
                for (slot, &x) in c.iter_mut().zip(chunk.iter()) {
                    *slot = self.coords(x);
                }
                // SAFETY: `canon_simd_enabled` checked AVX-512F.
                let mins = unsafe { least_rotation16_avx512(&c, self.n, self.mask) };
                chunk.copy_from_slice(&mins);
            }
            for x in chunks.into_remainder() {
                *x = self.canon(*x);
            }
            return;
        }
        for x in xs {
            *x = self.canon(*x);
        }
    }

    /// The extension degree this was built for.
    pub fn degree(&self) -> u32 {
        self.n
    }

    /// The byte tables the change of basis is applied through:
    /// `tables()[i][b]` is the normal coordinates of the field element
    /// whose `i`-th byte is `b` and whose other bytes are zero, so
    /// [`Self::coords`] is their XOR over the bytes of `x`.
    ///
    /// Exposed because the basis change is *data*, and a device that
    /// has to produce the same keys needs to be handed it rather than
    /// rediscover it: the normal element comes from a randomised search,
    /// so an independent search would find a different basis and a
    /// different — equally valid, but incompatible — naming of the same
    /// orbits.  `gpu/ecc2k/pairtable.cuh`'s `pt_canon` takes these and
    /// is checked against [`Self::canon`] on them.
    pub fn tables(&self) -> &[[u64; 256]] {
        &self.tables
    }
}

/// `x ↦ x^{2^t}` for every `t < n`, each applied as byte-table lookups.
///
/// A power of the Frobenius is `F_2`-linear, so like the change of basis
/// in [`FrobeniusCanon`] it is a table per byte of the argument: `⌈n/8⌉`
/// lookups and XORs, whatever `t` is, where the squaring chain it
/// replaces costs `t` dependent squarings.  A walk that canonicalises
/// over the Frobenius conjugates needs it to carry `y` (and `x`) to the
/// conjugate the rotation chose; a walk that steps by `P + φ^j(P)` needs
/// it for `φ^j` itself.
#[derive(Clone, Debug)]
pub struct FrobeniusPowers {
    n: u32,
    bytes: usize,
    /// `tables[t·bytes + i][b]`: `(b·2^{8i})^{2^t}`.
    tables: Vec<[u64; 256]>,
}

impl FrobeniusPowers {
    /// Tables for every power `t < n` of the Frobenius of `field`.
    pub fn new(field: &Gf2, n: u32) -> Self {
        let bytes = n.div_ceil(8) as usize;
        let mut tables = Vec::with_capacity(n as usize * bytes);
        for t in 0..n {
            for i in 0..bytes {
                let basis: Vec<u64> = (0..8)
                    .map(|j| {
                        let bit = 8 * i + j;
                        if bit < n as usize {
                            field.sqr_k(1u64 << bit, t)
                        } else {
                            0
                        }
                    })
                    .collect();
                let mut table = [0u64; 256];
                for (b, slot) in table.iter_mut().enumerate() {
                    *slot = (0..8)
                        .filter(|j| (b >> j) & 1 == 1)
                        .fold(0u64, |acc, j| acc ^ basis[j]);
                }
                tables.push(table);
            }
        }
        Self { n, bytes, tables }
    }

    /// `x^{2^t}`, for `t < n`.
    #[inline]
    pub fn apply(&self, t: u32, x: u64) -> u64 {
        debug_assert!(t < self.n);
        let base = t as usize * self.bytes;
        let mut acc = 0u64;
        for i in 0..self.bytes {
            acc ^= self.tables[base + i][((x >> (8 * i)) & 0xff) as usize];
        }
        acc
    }

    /// The extension degree this was built for.
    pub fn degree(&self) -> u32 {
        self.n
    }
}

/// Whether [`FrobeniusCanon::canon_many`] takes the AVX-512 path:
/// the CPU has AVX-512F and `KIC_SCAN_SIMD=0` has not turned the scan's
/// vector kernels off.
#[cfg(all(target_arch = "x86_64", suite_avx512))]
fn canon_simd_enabled() -> bool {
    static ON: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *ON.get_or_init(|| {
        is_x86_feature_detected!("avx512f") && std::env::var("KIC_SCAN_SIMD").as_deref() != Ok("0")
    })
}

/// The least cyclic rotation of each of sixteen `n`-bit words.
///
/// Rotation by one is `((v << 1) | (v >> (n − 1))) & mask`, one
/// ternary-logic op after the two shifts, and the running minimum is an
/// unsigned `vpminuq`; after `n − 1` steps every rotation has been
/// compared.  Two registers of eight advance together so each step's
/// latency is hidden behind the other's.
///
/// # Safety
///
/// The CPU must support AVX-512F, and `1 ≤ n ≤ 63` with
/// `mask = 2^n − 1`.
#[cfg(all(target_arch = "x86_64", suite_avx512))]
#[clippy::msrv = "1.89"]
#[target_feature(enable = "avx512f")]
unsafe fn least_rotation16_avx512(c: &[u64; 16], n: u32, mask: u64) -> [u64; 16] {
    use std::arch::x86_64::*;
    let m = _mm512_set1_epi64(mask as i64);
    let back = _mm_cvtsi64_si128(i64::from(n - 1));
    let mut a = _mm512_loadu_si512(c.as_ptr().cast());
    let mut b = _mm512_loadu_si512(c.as_ptr().add(8).cast());
    let (mut best_a, mut best_b) = (a, b);
    for _ in 1..n {
        // (a << 1 | a >> (n − 1)) & mask: truth table 0xA8 is (A | B) & C.
        a = _mm512_ternarylogic_epi64::<0xA8>(
            _mm512_slli_epi64::<1>(a),
            _mm512_srl_epi64(a, back),
            m,
        );
        b = _mm512_ternarylogic_epi64::<0xA8>(
            _mm512_slli_epi64::<1>(b),
            _mm512_srl_epi64(b, back),
            m,
        );
        best_a = _mm512_min_epu64(best_a, a);
        best_b = _mm512_min_epu64(best_b, b);
    }
    let mut out = [0u64; 16];
    _mm512_storeu_si512(out.as_mut_ptr().cast(), best_a);
    _mm512_storeu_si512(out.as_mut_ptr().add(8).cast(), best_b);
    out
}

/// Invert an `n × n` matrix over `F_2` given as its columns, returning
/// the rows of the inverse; `None` when the columns are dependent.
fn invert_f2(columns: &[u64], n: u32) -> Option<Vec<u64>> {
    // Row `i` carries, in bit `k`, the `i`-th bit of column `k`.
    let mut a: Vec<u64> = (0..n)
        .map(|i| (0..n).fold(0u64, |acc, k| acc | (((columns[k as usize] >> i) & 1) << k)))
        .collect();
    let mut inv: Vec<u64> = (0..n).map(|i| 1u64 << i).collect();
    for c in 0..n as usize {
        let pivot = (c..n as usize).find(|&r| (a[r] >> c) & 1 == 1)?;
        a.swap(c, pivot);
        inv.swap(c, pivot);
        for r in 0..n as usize {
            if r != c && (a[r] >> c) & 1 == 1 {
                a[r] ^= a[c];
                inv[r] ^= inv[c];
            }
        }
    }
    Some(inv)
}

/// Reusable buffers for [`FastCurve::add_many`].
#[derive(Clone, Debug, Default)]
pub struct BatchScratch {
    dens: Vec<u64>,
    acc: Vec<u64>,
    /// Structure-of-arrays copies of a block's addends, for the SIMD path.
    #[cfg(all(target_arch = "x86_64", suite_avx512))]
    qx: Vec<u64>,
    #[cfg(all(target_arch = "x86_64", suite_avx512))]
    qy: Vec<u64>,
}

/// Eight-lane AVX-512 field arithmetic for the decomposition scan.
///
/// The scan's inner loop is `R − P_k` for a block of base points: a
/// batched inversion of the denominators `x_R + x_k`, then a slope and an
/// abscissa per point — about five field multiplications each, all
/// independent across `k`.  `vpclmulqdq` forms four 64 × 64 carry-less
/// products per instruction, so two of them multiply eight lanes.
///
/// **Reduction without a table.**  The scalar field folds the high half
/// through byte-indexed tables; a vector version would need gathers.
/// Instead, write the product as `L + z^n·H`: since `z^n ≡ t(z)`, the
/// tail of the reduction polynomial, it equals `L + H·t`, and when `t`
/// is short (`n + deg t ≤ 65`) `H·t` fits in one word and is a handful
/// of shifts and XORs over `t`'s terms.  A second such fold finishes
/// when `2·deg t ≤ n + 1`.  Every field the pipeline runs — the
/// low-tail polynomials `find_irreducible_sparse` picks — qualifies; a
/// field that does not simply never builds a [`Simd512`].
///
/// The results are the same field elements as the scalar path, lane for
/// lane (the tests compare them), so nothing downstream can tell which
/// ran — the pinned counters included.
///
/// Compiled only on a toolchain where AVX-512 is stable (1.89+; see
/// `build.rs`); older toolchains take the scalar path everywhere.
#[cfg(all(target_arch = "x86_64", suite_avx512))]
#[clippy::msrv = "1.89"]
mod simd512 {
    use super::{BatchScratch, FastCurve, FastPoint};
    use crate::cryptanalysis::semaev_decomp::Gf2;
    use std::arch::x86_64::*;

    /// A field the kernel can reduce, on a CPU that has the kernel.
    #[derive(Clone, Copy, Debug)]
    pub(super) struct Simd512 {
        n: u32,
        mask: u64,
        terms: [u32; 8],
        nterms: usize,
    }

    impl Simd512 {
        pub(super) fn new(field: &Gf2) -> Option<Self> {
            if !(is_x86_feature_detected!("avx512f") && is_x86_feature_detected!("vpclmulqdq")) {
                return None;
            }
            // `KIC_SCAN_SIMD=0` keeps the scalar path: a same-binary
            // control for anything this kernel is credited with.
            if std::env::var("KIC_SCAN_SIMD").as_deref() == Ok("0") {
                return None;
            }
            Self::for_field(field)
        }

        /// The field-shape half of [`Self::new`], without the CPU check.
        pub(super) fn for_field(field: &Gf2) -> Option<Self> {
            let n = field.n;
            if !(2..=63).contains(&n) {
                return None;
            }
            let tail = field.irr ^ (1u64 << n);
            let t_max = 63 - tail.leading_zeros();
            // H has at most n − 1 bits, so H·t has degree ≤ n − 2 + deg t,
            // which must stay inside one word; the second fold's input has
            // degree ≤ deg t − 2, and its output must land below z^n.
            if n + t_max > 65 || 2 * t_max > n + 1 || tail.count_ones() as usize > 8 {
                return None;
            }
            let mut terms = [0u32; 8];
            let mut nterms = 0;
            for t in 0..n {
                if (tail >> t) & 1 == 1 {
                    terms[nterms] = t;
                    nterms += 1;
                }
            }
            Some(Self {
                n,
                mask: (1u64 << n) - 1,
                terms,
                nterms,
            })
        }

        /// [`FastCurve::add_many_lazy`] eight lanes at a time.  Returns
        /// `false`, having written nothing, when a sum is degenerate
        /// (`R = O`, or some `x_k = x_R`) — the caller then takes the
        /// scalar path, which handles those one by one.
        pub(super) fn add_many_lazy(
            &self,
            curve: &FastCurve,
            p: FastPoint,
            qs: &[FastPoint],
            out: &mut Vec<FastPoint>,
            lambdas: &mut Vec<u64>,
            scratch: &mut BatchScratch,
        ) -> bool {
            if p.infinity || qs.is_empty() {
                return false;
            }
            let padded = qs.len().div_ceil(8) * 8;
            let BatchScratch { dens, acc, qx, qy } = scratch;
            dens.clear();
            qx.clear();
            qy.clear();
            for q in qs {
                if q.infinity || q.x == p.x {
                    return false;
                }
                qx.push(q.x);
                qy.push(q.y);
                dens.push(p.x ^ q.x);
            }
            // Pad to whole vectors with a harmless denominator of 1.
            qx.resize(padded, 0);
            qy.resize(padded, 0);
            dens.resize(padded, 1);
            acc.clear();
            acc.resize(padded, 0);
            // SAFETY: a `Simd512` is only built after detecting avx512f
            // and vpclmulqdq; every slice holds `padded` words.
            unsafe { self.kernel(curve, p, dens, acc, qx, qy) };
            // `acc` now holds the abscissae and `dens` the slopes.
            out.reserve(qs.len());
            lambdas.reserve(qs.len());
            out.extend(acc[..qs.len()].iter().map(|&x| FastPoint::affine(x, 0)));
            lambdas.extend_from_slice(&dens[..qs.len()]);
            true
        }

        /// Montgomery's trick across eight lanes, then the slope and
        /// abscissa of every sum.  On return `pre` holds `x₃` and `dens`
        /// holds `λ`, lane for lane.
        #[target_feature(enable = "avx512f,vpclmulqdq")]
        unsafe fn kernel(
            &self,
            curve: &FastCurve,
            p: FastPoint,
            dens: &mut [u64],
            pre: &mut [u64],
            qx: &[u64],
            qy: &[u64],
        ) {
            let groups = dens.len() / 8;
            let ld = |s: &[u64], g: usize| _mm512_loadu_si512(s.as_ptr().add(8 * g) as *const _);
            let mut acc = _mm512_set1_epi64(1);
            for g in 0..groups {
                _mm512_storeu_si512(pre.as_mut_ptr().add(8 * g) as *mut _, acc);
                acc = self.mul(acc, ld(dens, g));
            }
            // The eight lane products are non-zero; invert them together.
            let mut lanes = [0u64; 8];
            _mm512_storeu_si512(lanes.as_mut_ptr() as *mut _, acc);
            let mut tmp = Vec::with_capacity(8);
            curve.field.batch_inv(&mut lanes, &mut tmp);
            let mut inv_acc = _mm512_loadu_si512(lanes.as_ptr() as *const _);
            let py = _mm512_set1_epi64(p.y as i64);
            let px_a = _mm512_set1_epi64((p.x ^ curve.a) as i64);
            for g in (0..groups).rev() {
                let d = ld(dens, g);
                let inv = self.mul(inv_acc, ld(pre, g));
                inv_acc = self.mul(inv_acc, d);
                let lambda = self.mul(_mm512_xor_si512(py, ld(qy, g)), inv);
                let x3 = _mm512_xor_si512(
                    _mm512_xor_si512(self.mul(lambda, lambda), lambda),
                    _mm512_xor_si512(px_a, ld(qx, g)),
                );
                _mm512_storeu_si512(pre.as_mut_ptr().add(8 * g) as *mut _, x3);
                _mm512_storeu_si512(dens.as_mut_ptr().add(8 * g) as *mut _, lambda);
            }
        }

        /// Eight field multiplications: two `vpclmulqdq` for the 128-bit
        /// products, then two shift-and-XOR folds by the tail.
        #[inline]
        #[target_feature(enable = "avx512f,vpclmulqdq")]
        unsafe fn mul(&self, a: __m512i, b: __m512i) -> __m512i {
            let even = _mm512_clmulepi64_epi128::<0x00>(a, b);
            let odd = _mm512_clmulepi64_epi128::<0x11>(a, b);
            let lo = _mm512_unpacklo_epi64(even, odd);
            let hi = _mm512_unpackhi_epi64(even, odd);
            let n = _mm_cvtsi64_si128(i64::from(self.n));
            let n_rev = _mm_cvtsi64_si128(i64::from(64 - self.n));
            let mask = _mm512_set1_epi64(self.mask as i64);
            let h = _mm512_or_si512(_mm512_srl_epi64(lo, n), _mm512_sll_epi64(hi, n_rev));
            let f = self.times_tail(h);
            let low = _mm512_xor_si512(_mm512_and_si512(lo, mask), _mm512_and_si512(f, mask));
            let f2 = self.times_tail(_mm512_srl_epi64(f, n));
            _mm512_xor_si512(low, f2)
        }

        /// `h · t` for the tail `t`, as one word per lane: the caller
        /// guarantees the product fits.
        #[inline]
        #[target_feature(enable = "avx512f")]
        unsafe fn times_tail(&self, h: __m512i) -> __m512i {
            let mut acc = _mm512_setzero_si512();
            for &t in &self.terms[..self.nterms] {
                acc = _mm512_xor_si512(acc, _mm512_sll_epi64(h, _mm_cvtsi64_si128(i64::from(t))));
            }
            acc
        }

        /// Test hook: multiply eight pairs through the kernel's `mul`.
        #[cfg(test)]
        pub(super) fn mul8(&self, a: &[u64; 8], b: &[u64; 8]) -> [u64; 8] {
            let mut out = [0u64; 8];
            // SAFETY: tests call this only after the CPU check.
            unsafe {
                let r = self.mul(
                    _mm512_loadu_si512(a.as_ptr() as *const _),
                    _mm512_loadu_si512(b.as_ptr() as *const _),
                );
                _mm512_storeu_si512(out.as_mut_ptr() as *mut _, r);
            }
            out
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// The run-based least rotation against the exhaustive scan, on
    /// random words and on the patterns where it could go wrong: all
    /// zeros and ones, single bits, periodic words where several
    /// rotations tie, and runs that wrap around bit `n − 1`.
    #[test]
    fn least_rotation_matches_exhaustive_scan() {
        fn brute(c: u64, n: u32, mask: u64) -> (u64, u32) {
            let (mut best, mut best_t, mut v) = (c, 0u32, c);
            for t in 1..n {
                v = ((v << 1) | (v >> (n - 1))) & mask;
                if v < best {
                    best = v;
                    best_t = t;
                }
            }
            (best, best_t)
        }
        let mut s = 0x2545_F491_4F6C_DD1Du64;
        for n in 2u32..=63 {
            let mask = (1u64 << n) - 1;
            let canon = FrobeniusCanon {
                n,
                mask,
                tables: Vec::new(),
            };
            let mut words = vec![0, mask, 1, 1 << (n - 1), mask ^ 1, mask >> 1];
            for period in 1..=n.min(12) {
                if n % period == 0 {
                    for pat in 1..(1u64 << period).min(64) {
                        let mut w = 0u64;
                        for k in 0..n / period {
                            w |= pat << (k * period);
                        }
                        words.push(w & mask);
                    }
                }
            }
            for _ in 0..400 {
                s ^= s << 13;
                s ^= s >> 7;
                s ^= s << 17;
                words.push(s & mask);
                // Sparse and dense words have long runs of one kind.
                words.push(s & (s >> 3) & (s >> 7) & mask);
                words.push((s | (s >> 5) | (s >> 11)) & mask);
            }
            for c in words {
                assert_eq!(
                    canon.least_rotation(c),
                    brute(c, n, mask),
                    "n = {n}, c = {c:#x}"
                );
            }
        }
    }
    use crate::binary_ecc::curve::{point_add, point_double, scalar_mul};
    use crate::cryptanalysis::koblitz_index_calculus::{pack_point, KoblitzCurve};
    use rand::rngs::StdRng;
    use rand::{Rng, SeedableRng};

    fn random_points(kc: &KoblitzCurve, count: usize, seed: u64) -> Vec<BinaryPoint> {
        let mut rng = StdRng::seed_from_u64(seed);
        let r = kc.subgroup_order.to_u64_digits()[0];
        let mut points: Vec<BinaryPoint> = (0..count)
            .map(|_| kc.mul(kc.generator(), &BigUint::from(rng.gen_range(1..r))))
            .collect();
        // A few points outside the prime-order subgroup too.
        for _ in 0..4 {
            let k = BigUint::from(rng.gen_range(1..(1u64 << 20)));
            let x = crate::binary_ecc::F2mElement::from_biguint(&k, kc.n);
            if let Some(p) =
                crate::cryptanalysis::koblitz_index_calculus::points_with_x(&kc.curve, &x)
                    .into_iter()
                    .next()
            {
                points.push(p);
            }
        }
        points.push(BinaryPoint::Infinity);
        points
    }

    /// Degrees the [`FrobeniusCanon`] tests sweep.
    ///
    /// `koblitz_index_calculus` already checks the key on the degrees the
    /// pipeline runs at — 13, 19, 23, 31, 53, 61 — and those are all
    /// prime, so no element there ever lies in a proper subfield.  These
    /// include composites, where an orbit is *shorter* than `n` and its
    /// coordinate word is a repeating pattern that its own rotation
    /// fixes.  That is the case a least-rotation key has to get right and
    /// a sampled prime-degree test cannot reach.
    const NB_DEGREES: [u32; 8] = [8, 12, 16, 20, 23, 31, 53, 61];

    fn nb_field(n: u32) -> Gf2 {
        Gf2::new(&crate::cryptanalysis::koblitz_index_calculus::find_irreducible_sparse(n).unwrap())
    }

    #[test]
    fn the_change_of_basis_is_a_bijection_and_turns_squaring_into_a_rotation() {
        // The property everything else rests on, checked directly rather
        // than through the key: `coords` is one-to-one, and squaring in
        // the field is a one-bit rotation of the coordinate word.  If
        // either half failed, the key would still be *constant* on orbits
        // and would silently merge some of them.
        for n in NB_DEGREES {
            let f = nb_field(n);
            let canon = FrobeniusCanon::new(&f, n)
                .unwrap_or_else(|| panic!("degree {n}: no normal element"));
            assert_eq!(canon.degree(), n);
            let mask = (1u64 << n) - 1;
            let rot1 = |c: u64| ((c << 1) | (c >> (n - 1))) & mask;

            let mut rng = StdRng::seed_from_u64(0xA110_0000 + n as u64);
            let mut seen: std::collections::HashMap<u64, u64> = Default::default();
            for _ in 0..2000 {
                let x = rng.gen::<u64>() & mask;
                let c = canon.coords(x);
                assert_eq!(
                    *seen.entry(c).or_insert(x),
                    x,
                    "degree {n}: coords sent two elements to {c:#x}"
                );
                assert_eq!(
                    canon.coords(f.sqr(x)),
                    rot1(c),
                    "degree {n}: coords(x²) is not a rotation of coords(x), x = {x:#x}"
                );
            }
            assert_eq!(canon.coords(0), 0, "degree {n}: coords is not linear at 0");
        }
    }

    #[test]
    fn the_least_rotation_is_constant_on_a_frobenius_orbit() {
        for n in NB_DEGREES {
            let f = nb_field(n);
            let canon = FrobeniusCanon::new(&f, n).unwrap();
            let mask = (1u64 << n) - 1;
            let mut rng = StdRng::seed_from_u64(0xB1A5_0000 + n as u64);
            for _ in 0..300 {
                let x = rng.gen::<u64>() & mask;
                let want = canon.canon(x);
                let mut v = x;
                for k in 0..n {
                    assert_eq!(
                        canon.canon(v),
                        want,
                        "degree {n}: image {k} of {x:#x} keys apart"
                    );
                    v = f.sqr(v);
                }
                assert_eq!(v, x, "degree {n}: the orbit did not close");
            }
        }
    }

    #[test]
    fn canon_many_is_canon_elementwise() {
        // Bulk keys must be bit-for-bit the per-element ones on whatever
        // path the CPU takes: random words, the all-zero and all-one
        // words, and periodic words whose rotations tie.
        for n in NB_DEGREES {
            let f = nb_field(n);
            let canon = FrobeniusCanon::new(&f, n).unwrap();
            let mask = (1u64 << n) - 1;
            let mut rng = StdRng::seed_from_u64(0xCA40_0000 + n as u64);
            let mut xs: Vec<u64> = (0..997).map(|_| rng.gen::<u64>() & mask).collect();
            xs.extend([0, mask, 1, mask >> 1, 0x5555_5555_5555_5555 & mask]);
            for len in [0usize, 1, 15, 16, 17, 33, xs.len()] {
                let mut out = vec![7u64];
                canon.canon_many(&xs[..len], &mut out);
                let want: Vec<u64> = std::iter::once(7)
                    .chain(xs[..len].iter().map(|&x| canon.canon(x)))
                    .collect();
                assert_eq!(out, want, "degree {n}, {len} keys");
            }
        }
    }

    #[test]
    fn the_least_rotation_partitions_exactly_as_the_squaring_chain() {
        // The two keys pick different representatives; the claim is
        // that they cut the field into the *same* orbits.  These degrees
        // are small enough to enumerate whole rather than sample, and
        // composite, so the short orbits are all present.
        for n in [8u32, 12, 16, 20] {
            let f = nb_field(n);
            let canon = FrobeniusCanon::new(&f, n).unwrap();
            let mut poly_of: std::collections::HashMap<u64, u64> = Default::default();
            let mut nb_of: std::collections::HashMap<u64, u64> = Default::default();
            let mut mismatch = 0usize;
            for x in 0..(1u64 << n) {
                // The polynomial-basis key: least element of the orbit.
                let mut v = x;
                let mut best = x;
                for _ in 1..n {
                    v = f.sqr(v);
                    best = best.min(v);
                }
                let (pk, nk) = (best, canon.canon(x));
                let a = *poly_of.entry(pk).or_insert(nk);
                let b = *nb_of.entry(nk).or_insert(pk);
                if a != nk || b != pk {
                    mismatch += 1;
                }
            }
            assert_eq!(
                mismatch, 0,
                "degree {n}: the two keys disagree on {mismatch} elements"
            );
            assert_eq!(
                poly_of.len(),
                nb_of.len(),
                "degree {n}: different orbit counts"
            );
        }
    }

    #[test]
    fn every_degree_the_pipeline_reaches_has_a_normal_element() {
        // `PairSumTable` keeps a squaring-chain fallback for the `None`
        // this can in principle return, and that fallback names orbits
        // *differently* from the rotation.  A build that quietly fell
        // back and a probe that did not would agree on nothing, so the
        // search failing is not a slow path, it is a wrong one — and the
        // bound on it is a random search over 4096 candidates.  Sweeping
        // every degree the pipeline can be given is what says the bound
        // is enough in practice.
        let mut checked = 0usize;
        for n in 8u32..=FastCurve::MAX_DEGREE {
            for a in [0u8, 1] {
                let Some(kc) = KoblitzCurve::new(a, n) else {
                    continue;
                };
                let fc = FastCurve::new(&kc.curve).unwrap();
                assert!(
                    FrobeniusCanon::new(&fc.field, fc.n).is_some(),
                    "degree {n}, a = {a}: no normal element found"
                );
                checked += 1;
            }
        }
        // Both curve shapes at every degree `KoblitzCurve` will build:
        // fewer than `MAX_DEGREE - 8` of them, since not every degree
        // gives a usable subgroup.  The bound is only here to say the
        // loop is not vacuous — pinning the exact count would turn a
        // change in which degrees `KoblitzCurve::new` accepts into a
        // failure of the normal-element search, which is not what this
        // test is about.
        assert!(checked >= 10, "the sweep only reached {checked} curves");
    }

    /// The lazy batched addition, completed, equals the eager one on
    /// every sum, degenerate ones included, and its abscissae are final
    /// before completion.
    #[test]
    fn lazy_batched_additions_equal_eager_ones() {
        let kc = KoblitzCurve::new(1, 19).unwrap();
        let fc = FastCurve::new(&kc.curve).unwrap();
        let points: Vec<FastPoint> = random_points(&kc, 40, 99)
            .iter()
            .map(|p| fc.lift(p))
            .collect();
        let mut qs = points.clone();
        // Q = P, Q = −P and O, the degenerate cases.
        for &p in points.iter().take(3) {
            qs.push(p);
            qs.push(fc.neg(p));
        }
        let mut scratch = BatchScratch::default();
        for &p in &points {
            let (mut eager, mut lazy, mut lambdas) = (Vec::new(), Vec::new(), Vec::new());
            fc.add_many(p, &qs, &mut eager, &mut scratch);
            fc.add_many_lazy(p, &qs, &mut lazy, &mut lambdas, &mut scratch);
            assert_eq!(lazy.len(), eager.len());
            for ((&l, &lambda), &e) in lazy.iter().zip(&lambdas).zip(&eager) {
                assert_eq!((l.x, l.infinity), (e.x, e.infinity));
                assert_eq!(fc.finish_lazy(p, l, lambda), e);
            }
        }
    }

    /// The eight-lane kernel against the scalar field and the scalar
    /// batched addition, on every degree whose polynomial it accepts and
    /// on blocks of every length around the lane width, plus a block with
    /// a degenerate sum (which must fall back and still agree).  Skipped
    /// on a CPU without AVX-512 and VPCLMULQDQ.
    #[cfg(all(target_arch = "x86_64", suite_avx512))]
    #[test]
    fn avx512_kernel_matches_scalar_arithmetic() {
        if !(is_x86_feature_detected!("avx512f") && is_x86_feature_detected!("vpclmulqdq")) {
            eprintln!("skipped: no AVX-512 + VPCLMULQDQ on this CPU");
            return;
        }
        let mut rng = StdRng::seed_from_u64(0x512);
        let mut accepted = 0;
        for n in 2u32..=62 {
            let field = nb_field(n);
            let Some(simd) = simd512::Simd512::for_field(&field) else {
                continue;
            };
            accepted += 1;
            for _ in 0..200 {
                let a: [u64; 8] = std::array::from_fn(|_| rng.gen::<u64>() & field.mask);
                let b: [u64; 8] = std::array::from_fn(|i| {
                    if i == 7 {
                        field.mask
                    } else {
                        rng.gen::<u64>() & field.mask
                    }
                });
                let got = simd.mul8(&a, &b);
                for l in 0..8 {
                    assert_eq!(got[l], field.mul(a[l], b[l]), "n = {n}, lane {l}");
                }
            }
        }
        assert!(
            accepted >= 50,
            "the kernel accepted only {accepted} degrees"
        );

        let mut curves = 0;
        for (a, n) in [(1u8, 19u32), (0, 31), (0, 41), (0, 53)] {
            let Some(kc) = KoblitzCurve::new(a, n) else {
                continue;
            };
            let fc = FastCurve::new(&kc.curve).unwrap();
            if fc.simd.is_none() {
                continue;
            }
            curves += 1;
            let points: Vec<FastPoint> = random_points(&kc, 40, 7 * u64::from(n))
                .iter()
                .map(|p| fc.lift(p))
                .filter(|p| !p.infinity)
                .collect();
            let mut scratch = BatchScratch::default();
            for len in (1..=17).chain([31, 40]) {
                let qs = &points[..len.min(points.len())];
                for &p in points.iter().take(6) {
                    let skip_degenerate = qs.iter().all(|q| q.x != p.x);
                    let (mut want, mut want_l) = (Vec::new(), Vec::new());
                    fc.add_many_lazy_scalar(p, qs, &mut want, &mut want_l, &mut scratch);
                    let (mut got, mut got_l) = (Vec::new(), Vec::new());
                    fc.add_many_lazy(p, qs, &mut got, &mut got_l, &mut scratch);
                    assert_eq!(
                        got, want,
                        "n = {n}, len = {len}, degenerate = {}",
                        !skip_degenerate
                    );
                    assert_eq!(got_l, want_l, "n = {n}, len = {len}");
                }
            }
        }
        assert!(curves >= 2, "only {curves} curves exercised the kernel");
    }

    /// The López–Dahab ladder against affine double-and-add, on both
    /// Koblitz curves at several degrees, over scalars that reach every
    /// special case: `0`, `1`, `2`, the subgroup order and its neighbours
    /// (where the ladder passes through `±P` and `O`), and wide random
    /// scalars; `P` ranges over subgroup points, points outside the
    /// subgroup, and `O`.
    #[test]
    fn projective_ladder_matches_affine_double_and_add() {
        fn affine(fc: &FastCurve, p: FastPoint, k: &BigUint) -> FastPoint {
            let mut r = FastPoint::INFINITY;
            for i in (0..k.bits()).rev() {
                r = fc.double(r);
                if k.bit(i) {
                    r = fc.add(r, p);
                }
            }
            r
        }
        let mut rng = StdRng::seed_from_u64(0x1ad0);
        let mut curves = 0;
        for (a, n) in [
            (0u8, 9u32),
            (1, 11),
            (0, 13),
            (1, 15),
            (1, 19),
            (0, 31),
            (0, 41),
            (0, 53),
        ] {
            // Not every (a, n) has a usable prime-order subgroup.
            let Some(kc) = KoblitzCurve::new(a, n) else {
                continue;
            };
            curves += 1;
            let fc = FastCurve::new(&kc.curve).unwrap();
            let r = &kc.subgroup_order;
            let h = &kc.cofactor;
            let mut scalars: Vec<BigUint> = [0u64, 1, 2, 3, 4, 5, 7, 8]
                .iter()
                .map(|&v| BigUint::from(v))
                .collect();
            scalars.extend([
                r - 1u32,
                r.clone(),
                r + 1u32,
                r * h,
                r * h - 1u32,
                r * 2u32 - 1u32,
            ]);
            for _ in 0..12 {
                scalars.push(BigUint::from(rng.gen::<u64>()));
                scalars.push(BigUint::from(rng.gen::<u128>()));
            }
            for p in random_points(&kc, 6, 31 + u64::from(n)) {
                let fp = fc.lift(&p);
                for k in &scalars {
                    let want = affine(&fc, fp, k);
                    assert_eq!(fc.mul(fp, k), want, "n = {n}, k = {k}");
                    if let Some(&k64) = k.to_u64_digits().first().filter(|_| k.bits() <= 64) {
                        assert_eq!(fc.mul_u64(fp, k64), want, "mul_u64, n = {n}, k = {k}");
                    }
                }
            }
        }
        assert!(curves >= 5, "only {curves} curves checked");
    }

    #[test]
    fn matches_the_general_arithmetic_on_random_points() {
        for (a, n) in [(0u8, 9u32), (1, 11), (1, 15), (1, 19), (0, 31)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fc = FastCurve::new(&kc.curve).unwrap();
            let points = random_points(&kc, 24, 7 + u64::from(n));
            for p in &points {
                let fp = fc.lift(p);
                assert_eq!(&fc.lower(fp), p, "lift/lower round trip at n = {n}");
                assert!(fc.is_on_curve(fp));
                assert_eq!(fp.pack(), pack_point(p), "pack at n = {n}");
                assert_eq!(fc.lower(fc.neg(fp)), crate::binary_ecc::curve::point_neg(p));
                assert_eq!(fc.lower(fc.double(fp)), point_double(&kc.curve, p));
                assert_eq!(fc.lower(fc.frobenius_k(fp, 1)), kc.frobenius(p));
                for q in &points {
                    let fq = fc.lift(q);
                    assert_eq!(
                        fc.lower(fc.add(fp, fq)),
                        point_add(&kc.curve, p, q),
                        "add at n = {n}"
                    );
                }
                let k = BigUint::from(0x9e37_79b9u64 + u64::from(n));
                assert_eq!(fc.lower(fc.mul(fp, &k)), scalar_mul(&kc.curve, p, &k));
                assert_eq!(
                    fc.mul(fp, &k),
                    fc.mul_u64(fp, 0x9e37_79b9u64 + u64::from(n))
                );
            }
        }
    }

    #[test]
    fn batched_additions_equal_individual_ones() {
        let kc = KoblitzCurve::new(0, 19).unwrap();
        let fc = FastCurve::new(&kc.curve).unwrap();
        let points: Vec<FastPoint> = random_points(&kc, 40, 3)
            .iter()
            .map(|p| fc.lift(p))
            .collect();
        let mut scratch = BatchScratch::default();
        let mut out = Vec::new();
        for &p in &points {
            // Include P itself, −P and O among the addends.
            let mut qs = points.clone();
            qs.push(p);
            qs.push(fc.neg(p));
            qs.push(FastPoint::INFINITY);
            out.clear();
            fc.add_many(p, &qs, &mut out, &mut scratch);
            assert_eq!(out.len(), qs.len());
            for (q, sum) in qs.iter().zip(&out) {
                assert_eq!(*sum, fc.add(p, *q));
            }
        }
    }

    #[test]
    fn pairwise_additions_equal_individual_ones() {
        let kc = KoblitzCurve::new(1, 19).unwrap();
        let fc = FastCurve::new(&kc.curve).unwrap();
        let points: Vec<FastPoint> = random_points(&kc, 24, 11)
            .iter()
            .map(|p| fc.lift(p))
            .collect();
        // Degenerate pairs too: P + P, P + (−P), P + O.
        let mut ps: Vec<FastPoint> = Vec::new();
        let mut qs: Vec<FastPoint> = Vec::new();
        for (i, &p) in points.iter().enumerate() {
            ps.push(p);
            qs.push(points[(i * 7 + 3) % points.len()]);
            ps.push(p);
            qs.push(p);
            ps.push(p);
            qs.push(fc.neg(p));
            ps.push(p);
            qs.push(FastPoint::INFINITY);
        }
        let mut out = Vec::new();
        let mut scratch = BatchScratch::default();
        fc.add_pairwise(&ps, &qs, &mut out, &mut scratch);
        assert_eq!(out.len(), ps.len());
        for ((p, q), sum) in ps.iter().zip(&qs).zip(&out) {
            assert_eq!(*sum, fc.add(*p, *q));
        }
    }

    #[test]
    fn refuses_fields_wider_than_a_word() {
        let curve = BinaryCurve::sect113r1();
        assert!(FastCurve::new(&curve).is_none());
    }
}
