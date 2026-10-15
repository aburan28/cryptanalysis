//! Strong single-target Pollard rho on Koblitz curves `E_a / F_{2^n}`: the
//! reference that `vs_rho` comparisons should be measured against.
//!
//! Each property below fixes a weakness of a reference that an earlier
//! comparison in this repository was measured against (see the 2026-09-29 and
//! 2026-09-30 errata in `docs/ic/BOUNDARY_TARGETS.md`):
//!
//! * **distinguished points**: only states whose hash has `dp_bits` low zero
//!   bits are stored, instead of a table holding every step;
//! * **signed-Frobenius quotient in a normal basis**: Frobenius is a rotation of
//!   normal coordinates, so the canonical representative of the orbit
//!   `{±φ^k(P)}` is the least rotation of the x normal coordinates (sign chosen
//!   by y), converted back once; the orbit multiplier `±λ^k` comes from a table;
//! * **library field arithmetic**: every multiply, square and inversion is
//!   [`Gf2`] (hardware carry-less multiply where the CPU has one), inversion by
//!   Itoh–Tsujii with its Frobenius powers taken as rotations;
//! * **lockstep lanes**: `lanes` independent walks advance together and their
//!   slope denominators are inverted with one field inversion
//!   ([`Gf2::batch_inv`], Montgomery's trick).
//!
//! The algorithm is rung 3 of `examples/koblitz_rho_batch_ks_strong.rs` at one
//! target. With the same seeds it walks the same trajectory step for step;
//! `koblitz_rho_fixture … strong` is checked against that example in
//! `research/notes/index-calculus/RESEARCH_FIXED_REFERENCE_RHO_20261001.md`.
//!
//! Walk construction (Kuhn–Struik style, single target): every walk starts at
//! `c·G + Q` (`b = 1`) for a fresh `c`, jumps are known multiples of `G`, and the
//! state `(P, a, b)` keeps `P = a·G + b·Q`; canonicalization multiplies `a` and
//! `b` by the orbit multiplier. Two walks meeting at a stored distinguished
//! point give `a + b·d = a' + b'·d`, solved when `b ≠ b'` and verified by
//! `[d]G = Q` before it is returned.
//!
//! **Widths.** The walk is written once over a field word `E` (`u64` for
//! `n ≤ 63`, `u128` for the wide fields up to `n = 127` that the m = 83
//! gate needs) and a scalar `S` (`u64`, or `u128` for a subgroup order past
//! `2^64`).  [`StrongRho`] and the other unsuffixed names are the one-word
//! instantiation every committed reference run used; the generic code is
//! that code with the word made a parameter, and the committed sessions'
//! replays pin that it walks identically.  The hash mixers fold a word to
//! 64 bits by [`FieldWord::fold64`], which is the identity on values below
//! `2^64`.

use crate::binary_ecc::BinaryPoint;
use crate::cryptanalysis::koblitz_index_calculus::KoblitzCurve;
use crate::cryptanalysis::semaev_decomp::Gf2;
use crate::cryptanalysis::wide_gf2m::WideGf2;
use num_bigint::BigUint;
use rand::distributions::uniform::SampleUniform;
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::collections::{BTreeSet, HashMap};
use std::fmt::Debug;
use std::hash::Hash;
use std::ops::{BitAnd, BitOr, BitXor, Shl, Shr, Sub};

/// Number of precomputed jumps (`r`-adding walk).
pub const JUMPS: usize = 32;

/// A field element word: `u64` or `u128`, bit `i` the coefficient of `z^i`.
pub trait FieldWord:
    Copy
    + Eq
    + Ord
    + Hash
    + Debug
    + Default
    + Send
    + Sync
    + BitXor<Output = Self>
    + BitAnd<Output = Self>
    + BitOr<Output = Self>
    + Sub<Output = Self>
    + Shl<u32, Output = Self>
    + Shr<u32, Output = Self>
    + From<u8>
    + From<u64>
{
    const BITS: u32;
    /// A 64-bit image for the walk's hash mixers: the word itself when it
    /// fits, so a one-word field hashes exactly as it always did.
    fn fold64(self) -> u64;
    /// Byte `i` (bits `8i .. 8i + 8`).
    fn byte(self, i: u32) -> usize;
    fn bit(self, i: u32) -> bool;
    /// Index of the lowest set bit (`BITS` for zero).
    fn trailing_zeros(self) -> u32;
}

impl FieldWord for u64 {
    const BITS: u32 = 64;
    #[inline(always)]
    fn fold64(self) -> u64 {
        self
    }
    #[inline(always)]
    fn byte(self, i: u32) -> usize {
        ((self >> (8 * i)) & 0xff) as usize
    }
    #[inline(always)]
    fn bit(self, i: u32) -> bool {
        (self >> i) & 1 == 1
    }
    #[inline(always)]
    fn trailing_zeros(self) -> u32 {
        u64::trailing_zeros(self)
    }
}

impl FieldWord for u128 {
    const BITS: u32 = 128;
    #[inline(always)]
    fn fold64(self) -> u64 {
        (self as u64) ^ ((self >> 64) as u64).rotate_left(29)
    }
    #[inline(always)]
    fn byte(self, i: u32) -> usize {
        ((self >> (8 * i)) & 0xff) as usize
    }
    #[inline(always)]
    fn bit(self, i: u32) -> bool {
        (self >> i) & 1 == 1
    }
    #[inline(always)]
    fn trailing_zeros(self) -> u32 {
        u128::trailing_zeros(self)
    }
}

/// The field operations the walk needs.
pub trait RhoField: Send + Sync {
    type E: FieldWord;
    fn degree(&self) -> u32;
    fn mul(&self, a: Self::E, b: Self::E) -> Self::E;
    fn sqr(&self, a: Self::E) -> Self::E;
    fn batch_inv(&self, xs: &mut [Self::E], scratch: &mut Vec<Self::E>);
}

impl RhoField for Gf2 {
    type E = u64;
    #[inline(always)]
    fn degree(&self) -> u32 {
        self.n
    }
    #[inline(always)]
    fn mul(&self, a: u64, b: u64) -> u64 {
        Gf2::mul(self, a, b)
    }
    #[inline(always)]
    fn sqr(&self, a: u64) -> u64 {
        Gf2::sqr(self, a)
    }
    fn batch_inv(&self, xs: &mut [u64], scratch: &mut Vec<u64>) {
        Gf2::batch_inv(self, xs, scratch)
    }
}

impl RhoField for WideGf2 {
    type E = u128;
    #[inline(always)]
    fn degree(&self) -> u32 {
        self.n
    }
    #[inline(always)]
    fn mul(&self, a: u128, b: u128) -> u128 {
        WideGf2::mul(self, a, b)
    }
    #[inline(always)]
    fn sqr(&self, a: u128) -> u128 {
        WideGf2::sqr(self, a)
    }
    fn batch_inv(&self, xs: &mut [u128], scratch: &mut Vec<u128>) {
        WideGf2::batch_inv(self, xs, scratch)
    }
}

/// A scalar modulo the subgroup order: `u64`, or `u128` for an order past
/// `2^64` (below `2^127`).
pub trait RhoScalar:
    Copy + Eq + Ord + Hash + Debug + Send + Sync + SampleUniform + std::fmt::Display
{
    /// Precomputed state for repeated multiplication modulo one `m`.
    type MulCtx: Copy + Send + Sync;
    fn zero() -> Self;
    fn one() -> Self;
    fn from_biguint(v: &BigUint) -> Option<Self>;
    fn to_f64(self) -> f64;
    fn to_u128(self) -> u128;
    /// Bits in the binary expansion (`0` for zero).
    fn bit_len(self) -> u32;
    fn bit(self, i: u32) -> bool;
    fn mul_ctx(m: Self) -> Self::MulCtx;
    fn mul_in(ctx: &Self::MulCtx, a: Self, b: Self) -> Self;
    fn mul_mod(a: Self, b: Self, m: Self) -> Self;
    fn add_mod(a: Self, b: Self, m: Self) -> Self;
    fn sub_mod(a: Self, b: Self, m: Self) -> Self;
    fn inverse_mod(v: Self, m: Self) -> Option<Self>;
}

impl RhoScalar for u64 {
    type MulCtx = MulMod;
    fn zero() -> Self {
        0
    }
    fn one() -> Self {
        1
    }
    fn from_biguint(v: &BigUint) -> Option<Self> {
        let d = v.to_u64_digits();
        match d.len() {
            0 => Some(0),
            1 => Some(d[0]),
            _ => None,
        }
    }
    fn to_f64(self) -> f64 {
        self as f64
    }
    fn to_u128(self) -> u128 {
        u128::from(self)
    }
    fn bit_len(self) -> u32 {
        64 - self.leading_zeros()
    }
    fn bit(self, i: u32) -> bool {
        (self >> i) & 1 == 1
    }
    fn mul_ctx(m: Self) -> MulMod {
        MulMod::new(m)
    }
    #[inline(always)]
    fn mul_in(ctx: &MulMod, a: Self, b: Self) -> Self {
        ctx.mul(a, b)
    }
    fn mul_mod(a: Self, b: Self, m: Self) -> Self {
        mul_mod(a, b, m)
    }
    #[inline(always)]
    fn add_mod(a: Self, b: Self, m: Self) -> Self {
        add_mod(a, b, m)
    }
    fn sub_mod(a: Self, b: Self, m: Self) -> Self {
        sub_mod(a, b, m)
    }
    fn inverse_mod(v: Self, m: Self) -> Option<Self> {
        inverse_mod(v, m)
    }
}

/// `(a + b) mod m` for `a, b < m`, any `m`, without overflow.
fn add_mod_full(a: u128, b: u128, m: u128) -> u128 {
    let (s, carried) = a.overflowing_add(b);
    if carried || s >= m {
        s.wrapping_sub(m)
    } else {
        s
    }
}

/// `a·b mod m` for `a, b < m`, in `c = 127 − bits(m)`-bit chunks of `b` so
/// that no intermediate leaves a `u128`; by double-and-add when `m` leaves
/// fewer than eight bits of room.
fn mul_mod_u128(a: u128, b: u128, m: u128) -> u128 {
    debug_assert!(a < m && b < m);
    let mb = 128 - m.leading_zeros();
    if (128 - a.leading_zeros()) + (128 - b.leading_zeros()) <= 128 {
        return a.wrapping_mul(b) % m;
    }
    if mb > 119 {
        let mut acc = 0u128;
        for i in (0..128 - b.leading_zeros()).rev() {
            acc = add_mod_full(acc, acc, m);
            if (b >> i) & 1 == 1 {
                acc = add_mod_full(acc, a, m);
            }
        }
        return acc;
    }
    let c = 127 - mb;
    let bb = 128 - b.leading_zeros();
    let chunks = bb.div_ceil(c);
    let mut acc = 0u128;
    for i in (0..chunks).rev() {
        let shift = i * c;
        let chunk = (b >> shift) & ((1u128 << c) - 1);
        acc = (acc << c) % m;
        acc = (acc + a * chunk) % m;
    }
    acc
}

impl RhoScalar for u128 {
    type MulCtx = u128;
    fn zero() -> Self {
        0
    }
    fn one() -> Self {
        1
    }
    fn from_biguint(v: &BigUint) -> Option<Self> {
        let d = v.to_u64_digits();
        match d.len() {
            0 => Some(0),
            1 => Some(d[0] as u128),
            2 => Some(d[0] as u128 | ((d[1] as u128) << 64)),
            _ => None,
        }
    }
    fn to_f64(self) -> f64 {
        self as f64
    }
    fn to_u128(self) -> u128 {
        self
    }
    fn bit_len(self) -> u32 {
        128 - self.leading_zeros()
    }
    fn bit(self, i: u32) -> bool {
        (self >> i) & 1 == 1
    }
    fn mul_ctx(m: Self) -> u128 {
        assert!(m > 1, "modulus out of range");
        m
    }
    #[inline(always)]
    fn mul_in(m: &u128, a: Self, b: Self) -> Self {
        mul_mod_u128(a, b, *m)
    }
    fn mul_mod(a: Self, b: Self, m: Self) -> Self {
        mul_mod_u128(a % m, b % m, m)
    }
    #[inline(always)]
    fn add_mod(a: Self, b: Self, m: Self) -> Self {
        add_mod_full(a % m, b % m, m)
    }
    fn sub_mod(a: Self, b: Self, m: Self) -> Self {
        if a >= b {
            a - b
        } else {
            m - (b - a)
        }
    }
    fn inverse_mod(v: Self, m: Self) -> Option<Self> {
        use num_bigint::BigInt;
        use num_integer::Integer;
        if v == 0 {
            return None;
        }
        let e = BigInt::from(v).extended_gcd(&BigInt::from(m));
        if e.gcd != BigInt::from(1) {
            return None;
        }
        let x = e.x.mod_floor(&BigInt::from(m));
        Self::from_biguint(&x.to_biguint()?)
    }
}

/// A point of `E(F_{2^n})` with coordinates packed in one word each
/// (polynomial basis, as the field uses).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RawPointG<E> {
    /// The point at infinity.
    Infinity,
    /// An affine point.
    Affine {
        /// x-coordinate.
        x: E,
        /// y-coordinate.
        y: E,
    },
}

/// The one-word point every committed reference run used.
pub type RawPoint = RawPointG<u64>;

impl RawPointG<u64> {
    /// Pack a library point (`n ≤ 64`).
    pub fn from_binary(point: &BinaryPoint) -> Self {
        match point {
            BinaryPoint::Infinity => RawPoint::Infinity,
            BinaryPoint::Affine { x, y } => RawPoint::Affine {
                x: x.raw_bits().first().copied().unwrap_or(0),
                y: y.raw_bits().first().copied().unwrap_or(0),
            },
        }
    }
}

impl RawPointG<u128> {
    /// Pack a library point (`n ≤ 128`).
    pub fn from_binary_wide(point: &BinaryPoint) -> Self {
        let word = |bits: &[u64]| {
            bits.first().copied().unwrap_or(0) as u128
                | ((bits.get(1).copied().unwrap_or(0) as u128) << 64)
        };
        match point {
            BinaryPoint::Infinity => RawPointG::Infinity,
            BinaryPoint::Affine { x, y } => RawPointG::Affine {
                x: word(x.raw_bits()),
                y: word(y.raw_bits()),
            },
        }
    }
}

impl<E: FieldWord> RawPointG<E> {
    fn key(self) -> (u8, E, E) {
        match self {
            RawPointG::Infinity => (0, E::default(), E::default()),
            RawPointG::Affine { x, y } => (1, x, y),
        }
    }
}

/// Walk state: `point = a·G + b·Q`.
#[derive(Clone, Copy, Debug)]
pub struct WalkStateG<E, S> {
    /// Current point.
    pub point: RawPointG<E>,
    /// Coefficient of `G`.
    pub a: S,
    /// Coefficient of `Q`.
    pub b: S,
}

/// The one-word walk state.
pub type WalkState = WalkStateG<u64, u64>;

/// One precomputed jump `s·G`.
#[derive(Clone, Copy, Debug)]
pub struct JumpG<E, S> {
    /// The point `s·G`.
    pub point: RawPointG<E>,
    /// Its discrete log `s`.
    pub a: S,
}

/// The one-word jump.
pub type Jump = JumpG<u64, u64>;

/// Tunables. The defaults are the configuration measured as the strong
/// reference in PR #1090 (`lanes = 32`, `dp_bits = 4`).
#[derive(Clone, Copy, Debug)]
pub struct StrongRhoParams {
    /// Walks advanced in lockstep (batch-inversion width); at least 1.
    pub lanes: usize,
    /// A state is distinguished when `dp_hash & (2^dp_bits − 1) == 0`.
    pub dp_bits: u32,
    /// Give up after `step_cap_factor × ⌈√(πr / 2A)⌉` steps (at least 10^6).
    pub step_cap_factor: u64,
    /// On a fruitless cycle, escape instead of abandoning the walk: the
    /// state becomes the canonical form of `[2]P_next` with `a, b` doubled,
    /// a function of the walk's own state, so two merged walks escape
    /// alike.  Off is the committed reference, bit for bit; the escape is
    /// what lets a long distinguished-point walk (large `dp_bits`, as a
    /// table at m = 83 needs) survive about one fruitless cycle per few
    /// thousand steps.
    pub escape_fruitless: bool,
}

impl Default for StrongRhoParams {
    fn default() -> Self {
        Self {
            lanes: 32,
            dp_bits: 4,
            step_cap_factor: 2_000,
            escape_fruitless: false,
        }
    }
}

/// Operation counts for one solve (whole solve, setup included).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct StrongRhoCharges {
    /// Group additions (walk steps and walk starts).
    pub group_additions: u64,
    /// Scalar multiplications (jumps, start stride, candidate checks).
    pub scalar_multiplications: u64,
    /// Orbit canonicalizations.
    pub canonicalizations: u64,
    /// Jump-index hashes.
    pub partition_hashes: u64,
    /// Distinguished-point table lookups.
    pub table_queries: u64,
    /// Distinguished-point table insertions.
    pub table_inserts: u64,
    /// Collisions whose candidate failed `[d]G = Q`.
    pub failed_collisions: u64,
}

/// Result of a successful solve.
#[derive(Clone, Debug)]
pub struct StrongRhoOutcomeG<S> {
    /// The verified discrete logarithm `d` with `[d]G = Q`.
    pub scalar: S,
    /// Group-operation steps taken by all walks.
    pub walk_steps: u64,
    /// Walks started.
    pub walks: u64,
    /// Walks abandoned in a fruitless cycle (length ≤ 4).
    pub fruitless: u64,
    /// Fruitless cycles escaped by doubling (`escape_fruitless` only).
    pub escapes: u64,
    /// Walks abandoned at the length cap `8·2^dp_bits`.
    pub capped: u64,
    /// Collisions with `b = b'` (no information).
    pub wasted_merges: u64,
    /// Distinguished points stored when the solve ended.
    pub table_entries: usize,
    /// `√(πr / 2A)`, the expected step count of one ideal walk.
    pub ideal_steps: f64,
    /// Size `A` of the signed-Frobenius automorphism group on the subgroup.
    pub automorphisms: usize,
    /// Operation counts.
    pub charges: StrongRhoCharges,
    /// lit2026 W11 diagnostic: the length (steps since its start) of every
    /// walk that ended on a distinguished point, in the order they arrived.
    pub dp_trail_lengths: Vec<u32>,
    /// lit2026 W11 diagnostic: the length of every walk abandoned in a
    /// fruitless cycle (`escape_fruitless` off) or at the cap.
    pub abandoned_trail_lengths: Vec<u32>,
}

/// The one-word outcome.
pub type StrongRhoOutcome = StrongRhoOutcomeG<u64>;

/// `2^n − 1` as a word.
fn word_mask<E: FieldWord>(n: u32) -> E {
    if n == E::BITS {
        let top = E::from(1u8) << (E::BITS - 1);
        top | (top - E::from(1u8))
    } else {
        (E::from(1u8) << n) - E::from(1u8)
    }
}

/// F2-linear map on `n` bits applied by byte tables.
struct Linear<E> {
    tables: Vec<[E; 256]>,
}

impl<E: FieldWord> Linear<E> {
    fn from_images(images: &[E]) -> Self {
        let chunks = images.len().div_ceil(8);
        let mut tables = vec![[E::default(); 256]; chunks];
        for (chunk, table) in tables.iter_mut().enumerate() {
            for byte in 1usize..256 {
                let low = byte & (byte - 1);
                let bit = chunk * 8 + byte.trailing_zeros() as usize;
                let image = images.get(bit).copied().unwrap_or_default();
                table[byte] = table[low] ^ image;
            }
        }
        Self { tables }
    }

    #[inline(always)]
    fn apply(&self, v: E) -> E {
        let mut acc = E::default();
        for (chunk, table) in self.tables.iter().enumerate() {
            acc = acc ^ table[v.byte(chunk as u32)];
        }
        acc
    }
}

/// Invert the `n × n` matrix over F2 whose columns are `columns`; `None` when
/// singular. Returns the columns of the inverse (which is unique, so the
/// tables do not depend on how the elimination is written).
fn invert_columns<E: FieldWord>(columns: &[E], n: usize) -> Option<Vec<E>> {
    let one = E::from(1u8);
    // (coefficients, the identity's row beside them)
    let mut rows: Vec<(E, E)> = (0..n)
        .map(|r| {
            let mut row = E::default();
            for (i, &column) in columns.iter().enumerate() {
                if column.bit(r as u32) {
                    row = row | (one << i as u32);
                }
            }
            (row, one << r as u32)
        })
        .collect();
    for pivot in 0..n {
        let found = (pivot..n).find(|&r| rows[r].0.bit(pivot as u32))?;
        rows.swap(pivot, found);
        let (pc, pa) = rows[pivot];
        for (r, row) in rows.iter_mut().enumerate() {
            if r != pivot && row.0.bit(pivot as u32) {
                *row = (row.0 ^ pc, row.1 ^ pa);
            }
        }
    }
    let mut images = vec![E::default(); n];
    for (i, row) in rows.iter().enumerate() {
        for (r, image) in images.iter_mut().enumerate() {
            if row.1.bit(r as u32) {
                *image = *image | (one << i as u32);
            }
        }
    }
    Some(images)
}

/// Normal basis built from the conjugates of the first normal element: in it,
/// squaring (Frobenius) is a one-bit rotation.
struct NormalBasis<E> {
    n: u32,
    mask: E,
    to_normal: Linear<E>,
    to_poly: Linear<E>,
}

impl<E: FieldWord> NormalBasis<E> {
    fn new<F: RhoField<E = E>>(gf: &F) -> Self {
        let n = gf.degree() as usize;
        let mask = word_mask::<E>(gf.degree());
        for candidate in 2u64.. {
            let mut conjugates = Vec::with_capacity(n);
            let mut value = E::from(candidate) & mask;
            for _ in 0..n {
                conjugates.push(value);
                value = gf.sqr(value);
            }
            let Some(inverse_columns) = invert_columns(&conjugates, n) else {
                continue;
            };
            return Self {
                n: gf.degree(),
                mask,
                to_normal: Linear::from_images(&inverse_columns),
                to_poly: Linear::from_images(&conjugates),
            };
        }
        unreachable!("every finite field has a normal basis")
    }

    #[inline(always)]
    fn rotate(&self, v: E, k: u32) -> E {
        if k == 0 {
            return v;
        }
        ((v << k) | (v >> (self.n - k))) & self.mask
    }

    /// What a scan of all `n` rotations of the normal coordinates `c` finds:
    /// the least rotation, the smallest `k` with `rotate(c, k)` equal to it,
    /// and whether another `k` reaches it too (a periodic or constant word).
    ///
    /// The scan need not try every `k`.  `rotate(c, k)` opens with as many
    /// zeros as the zero run of `c` whose top is bit `n − 1 − k`, and more
    /// leading zeros is a smaller word, so every least rotation starts at a
    /// top of one of the *longest* cyclic zero runs.  Those tops are found
    /// one AND-with-rotate per bit of run length — `Z_j = Z_{j−1} ∧
    /// rotate(¬c, j − 1)` has bit `p` set when bits `p, p − 1, …, p − j + 1`
    /// of `c` are zero — about `log₂ n` steps on a random word, and only the
    /// rotations starting there are compared, usually one or two.  Every
    /// `k` that reaches the least is among them, so the tie is exact.
    fn least_rotation(&self, c: E) -> (E, u32, bool) {
        let zero = E::default();
        let zeros = c ^ self.mask;
        if c == zero || zeros == zero {
            // Every rotation is the same word.
            return (c, 0, self.n > 1);
        }
        let mut run = zeros;
        let mut len = 1u32;
        loop {
            let next = run & self.rotate(zeros, len);
            if next == zero {
                break;
            }
            run = next;
            len += 1;
        }
        // Tops in ascending bit order are `k = n − 1 − p` descending, so an
        // equal value found later has the smaller `k`.
        let mut tops = run;
        let mut best = (self.mask, 0u32, false);
        let mut first = true;
        while tops != zero {
            let p = tops.trailing_zeros();
            tops = tops & (tops - E::from(1u8));
            let k = self.n - 1 - p;
            let v = self.rotate(c, k);
            if first || v < best.0 {
                best = (v, k, false);
                first = false;
            } else if v == best.0 {
                best = (v, k, true);
            }
        }
        best
    }
}

/// `a·b mod m`: a floating-point quotient estimate when `m < 2^50` (off by at
/// most one, so one conditional correction finishes it), else `u128`.
#[derive(Clone, Copy)]
pub struct MulMod {
    m: u64,
    inv: f64,
    fast: bool,
}

impl MulMod {
    fn new(m: u64) -> Self {
        assert!(m > 1, "modulus must exceed 1");
        Self {
            m,
            inv: 1.0 / m as f64,
            fast: m < (1u64 << 50),
        }
    }

    #[inline(always)]
    fn mul(&self, a: u64, b: u64) -> u64 {
        debug_assert!(a < self.m && b < self.m);
        if !self.fast {
            return ((a as u128 * b as u128) % self.m as u128) as u64;
        }
        let q = ((a as f64) * (b as f64) * self.inv) as u64;
        let r = a.wrapping_mul(b).wrapping_sub(q.wrapping_mul(self.m)) as i64;
        let m = self.m as i64;
        (if r < 0 {
            r + m
        } else if r >= m {
            r - m
        } else {
            r
        }) as u64
    }
}

fn mul_mod(left: u64, right: u64, modulus: u64) -> u64 {
    ((left as u128 * right as u128) % modulus as u128) as u64
}

fn add_mod(left: u64, right: u64, modulus: u64) -> u64 {
    ((left as u128 + right as u128) % modulus as u128) as u64
}

fn sub_mod(left: u64, right: u64, modulus: u64) -> u64 {
    if left >= right {
        left - right
    } else {
        modulus - (right - left)
    }
}

fn inverse_mod(value: u64, modulus: u64) -> Option<u64> {
    if value == 0 {
        return None;
    }
    let (mut old_r, mut r) = (modulus as i128, value as i128);
    let (mut old_t, mut t) = (0i128, 1i128);
    while r != 0 {
        let quotient = old_r / r;
        (old_r, r) = (r, old_r - quotient * r);
        (old_t, t) = (t, old_t - quotient * t);
    }
    (old_r == 1).then_some(old_t.rem_euclid(modulus as i128) as u64)
}

/// Jump index of a point (a fixed 64-bit mixer; part of the walk definition).
fn partition<E: FieldWord>(point: RawPointG<E>) -> usize {
    let (_, x, y) = point.key();
    let (x, y) = (x.fold64(), y.fold64());
    let mut value = x ^ y.rotate_left(21) ^ 0x9e37_79b9_7f4a_7c15;
    value ^= value >> 30;
    value = value.wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value ^= value >> 27;
    value = value.wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^= value >> 31;
    value as usize % JUMPS
}

/// Distinguished-point hash (independent of [`partition`]).
fn dp_hash<E: FieldWord>(point: RawPointG<E>) -> u64 {
    let (_, x, y) = point.key();
    let (x, y) = (x.fold64(), y.fold64());
    let mut v = x.rotate_left(7) ^ y ^ 0x2545_f491_4f6c_dd1d;
    v ^= v >> 33;
    v = v.wrapping_mul(0xff51_afd7_ed55_8ccd);
    v ^= v >> 33;
    v = v.wrapping_mul(0xc4ce_b9fe_1a85_ec53);
    v ^ (v >> 33)
}

#[derive(Clone, Copy)]
struct Lane<E, S> {
    state: WalkStateG<E, S>,
    previous: [RawPointG<E>; 4],
    length: u64,
    live: bool,
}

/// Per-curve precomputation: field, normal basis, orbit-multiplier table.
pub struct StrongRhoG<F: RhoField, S: RhoScalar> {
    n: u32,
    curve_a: F::E,
    gf: F,
    nb: NormalBasis<F::E>,
    modulus: S,
    lambda: S,
    automorphisms: usize,
    generator: RawPointG<F::E>,
    lam_pow: Vec<S>,
    mm: S::MulCtx,
}

/// The one-word strong reference every committed run used.
pub type StrongRho = StrongRhoG<Gf2, u64>;

/// The wide strong reference: `n ≤ 127`, a subgroup order below `2^127`.
pub type WideStrongRho = StrongRhoG<WideGf2, u128>;

impl StrongRho {
    /// Precompute for `curve`. Panics when `n > 63` or the subgroup order does
    /// not fit in a `u64` (the packed representation needs both).
    pub fn new(curve: &KoblitzCurve) -> Self {
        assert!(curve.n <= 63, "packed field elements need n <= 63");
        let digits = curve.subgroup_order.to_u64_digits();
        assert_eq!(digits.len(), 1, "subgroup order must fit in a u64");
        let modulus = digits[0];
        let lambda = curve.lambda.to_u64_digits().first().copied().unwrap_or(0);
        Self::from_parts(
            Gf2::new(&curve.curve.irreducible),
            curve.a as u64,
            modulus,
            lambda,
            RawPoint::from_binary(curve.generator()),
        )
    }
}

impl<F: RhoField, S: RhoScalar> StrongRhoG<F, S> {
    /// Precompute from the field, the curve coefficient `a` of
    /// `y² + xy = x³ + a x² + 1`, the prime subgroup order, the Frobenius
    /// eigenvalue on it, and a generator.  Panics when `λ` does not have
    /// order dividing `n`.
    pub fn from_parts(
        gf: F,
        curve_a: F::E,
        modulus: S,
        lambda: S,
        generator: RawPointG<F::E>,
    ) -> Self {
        let n = gf.degree();
        let nb = NormalBasis::new(&gf);
        let mut lam_pow = Vec::with_capacity(n as usize);
        let mut cur = S::one();
        let mut orbit = BTreeSet::new();
        for _ in 0..n {
            lam_pow.push(cur);
            orbit.insert(cur);
            orbit.insert(S::sub_mod(S::zero(), cur, modulus));
            cur = S::mul_mod(cur, lambda, modulus);
        }
        assert!(cur == S::one(), "lambda must have order dividing n");
        Self {
            n,
            curve_a,
            gf,
            nb,
            modulus,
            lambda,
            automorphisms: orbit.len(),
            generator,
            lam_pow,
            mm: S::mul_ctx(modulus),
        }
    }

    /// Group arithmetic only, for a curve whose Frobenius eigenvalue is not
    /// known yet (the wide constructor finds it with this): `λ = 1`, so
    /// [`Self::canonicalize`] folds negation only.  Never walk with it.
    pub fn from_parts_unchecked(
        gf: F,
        curve_a: F::E,
        modulus: S,
        generator: RawPointG<F::E>,
    ) -> Self {
        let n = gf.degree();
        let nb = NormalBasis::new(&gf);
        Self {
            n,
            curve_a,
            gf,
            nb,
            modulus,
            lambda: S::one(),
            automorphisms: 2,
            generator,
            lam_pow: vec![S::one(); n as usize],
            mm: S::mul_ctx(modulus),
        }
    }

    /// The Frobenius orbit of an abscissa: the least normal-basis rotation of
    /// `x`'s coordinates (a name equal on `{x^{2^k}}` and nowhere else) and
    /// the `k` with `x^{2^k}` the least, the convention
    /// [`Self::canonicalize`] uses.
    pub fn x_orbit(&self, x: F::E) -> (F::E, u32) {
        let nb = &self.nb;
        let (best, best_k, _) = nb.least_rotation(nb.to_normal.apply(x));
        (best, best_k)
    }

    /// `φ^t(P) = (x^{2^t}, y^{2^t})`, by normal-basis rotation.
    pub fn frobenius(&self, t: u32, point: RawPointG<F::E>) -> RawPointG<F::E> {
        match point {
            RawPointG::Affine { x, y } if !t.is_multiple_of(self.n) => {
                let nb = &self.nb;
                let t = t % self.n;
                RawPointG::Affine {
                    x: nb.to_poly.apply(nb.rotate(nb.to_normal.apply(x), t)),
                    y: nb.to_poly.apply(nb.rotate(nb.to_normal.apply(y), t)),
                }
            }
            other => other,
        }
    }

    /// The extension degree `n`.
    pub fn degree(&self) -> u32 {
        self.n
    }

    /// Prime subgroup order `r`.
    pub fn modulus(&self) -> S {
        self.modulus
    }

    /// Eigenvalue `λ` of Frobenius on the subgroup.
    pub fn lambda(&self) -> S {
        self.lambda
    }

    /// Size of the signed-Frobenius automorphism group on the subgroup.
    pub fn automorphisms(&self) -> usize {
        self.automorphisms
    }

    /// The generator `G`.
    pub fn generator(&self) -> RawPointG<F::E> {
        self.generator
    }

    /// Expected steps of one ideal walk, `√(πr / 2A)`.
    pub fn ideal_steps(&self) -> f64 {
        (std::f64::consts::PI * self.modulus.to_f64() / (2.0 * self.automorphisms as f64)).sqrt()
    }

    #[inline(always)]
    fn mul(&self, left: F::E, right: F::E) -> F::E {
        self.gf.mul(left, right)
    }

    #[inline(always)]
    fn sqr(&self, value: F::E) -> F::E {
        self.gf.sqr(value)
    }

    /// Itoh–Tsujii inversion with the `x^(2^k)` steps as normal-basis rotations.
    fn inv(&self, value: F::E) -> F::E {
        assert!(value != F::E::default());
        let e = self.n - 1;
        let mut c = value;
        let mut k = 1u32;
        let bits = 32 - e.leading_zeros();
        for i in (0..bits - 1).rev() {
            let raised = self
                .nb
                .to_poly
                .apply(self.nb.rotate(self.nb.to_normal.apply(c), k));
            c = self.mul(c, raised);
            k *= 2;
            if (e >> i) & 1 == 1 {
                c = self.mul(self.sqr(c), value);
                k += 1;
            }
        }
        self.sqr(c)
    }

    fn double(&self, point: RawPointG<F::E>) -> RawPointG<F::E> {
        let RawPointG::Affine { x, y } = point else {
            return RawPointG::Infinity;
        };
        if x == F::E::default() {
            return RawPointG::Infinity;
        }
        let one = F::E::from(1u8);
        let lambda = x ^ self.mul(y, self.inv(x));
        let x3 = self.sqr(lambda) ^ lambda ^ self.curve_a;
        let y3 = self.sqr(x) ^ self.mul(lambda ^ one, x3);
        RawPointG::Affine { x: x3, y: y3 }
    }

    /// Group law.
    pub fn add(&self, left: RawPointG<F::E>, right: RawPointG<F::E>) -> RawPointG<F::E> {
        match (left, right) {
            (RawPointG::Infinity, point) | (point, RawPointG::Infinity) => point,
            (RawPointG::Affine { x: x1, y: y1 }, RawPointG::Affine { x: x2, y: y2 }) => {
                if x1 == x2 {
                    return if y1 ^ y2 == x1 {
                        RawPointG::Infinity
                    } else {
                        self.double(left)
                    };
                }
                let lambda = self.mul(y1 ^ y2, self.inv(x1 ^ x2));
                self.add_with_slope(x1, y1, x2, lambda)
            }
        }
    }

    #[inline(always)]
    fn add_with_slope(&self, x1: F::E, y1: F::E, x2: F::E, lambda: F::E) -> RawPointG<F::E> {
        let x3 = self.sqr(lambda) ^ lambda ^ x1 ^ x2 ^ self.curve_a;
        let y3 = self.mul(lambda, x1 ^ x3) ^ x3 ^ y1;
        RawPointG::Affine { x: x3, y: y3 }
    }

    /// `k·P` by double-and-add.
    pub fn scalar_mul(&self, point: RawPointG<F::E>, scalar: S) -> RawPointG<F::E> {
        let mut result = RawPointG::Infinity;
        for bit in (0..scalar.bit_len()).rev() {
            result = self.double(result);
            if scalar.bit(bit) {
                result = self.add(result, point);
            }
        }
        result
    }

    /// Exhaustive definition of the canonical representative: the least
    /// `(x, y)` in normal coordinates over the `2n` orbit members. Returns
    /// `(rotation k, negated)`. Used for ties and as the test reference.
    fn choice_exhaustive(&self, xc: F::E, yc: F::E) -> (u32, bool) {
        let nb = &self.nb;
        let all = word_mask::<F::E>(F::E::BITS);
        let mut best = (all, all);
        let mut choice = (0u32, false);
        for k in 0..nb.n {
            let xk = nb.rotate(xc, k);
            let yk = nb.rotate(yc, k);
            if (xk, yk) < best {
                best = (xk, yk);
                choice = (k, false);
            }
            if (xk, yk ^ xk) < best {
                best = (xk, yk ^ xk);
                choice = (k, true);
            }
        }
        choice
    }

    /// Canonical representative of the signed-Frobenius orbit of the state's
    /// point, with `a, b` multiplied by the orbit multiplier `±λ^k`.
    pub fn canonicalize(&self, state: WalkStateG<F::E, S>) -> WalkStateG<F::E, S> {
        let RawPointG::Affine { x, y } = state.point else {
            return state;
        };
        let nb = &self.nb;
        let xc = nb.to_normal.apply(x);
        let yc = nb.to_normal.apply(y);
        let (best, best_k, tie) = nb.least_rotation(xc);
        let (k, negated) = if tie {
            self.choice_exhaustive(xc, yc)
        } else {
            let yk = nb.rotate(yc, best_k);
            (best_k, (yk ^ best) < yk)
        };
        let xk = nb.rotate(xc, k);
        let yk = nb.rotate(yc, k);
        let yk = if negated { yk ^ xk } else { yk };
        let lam = self.lam_pow[k as usize];
        let multiplier = if negated {
            S::sub_mod(S::zero(), lam, self.modulus)
        } else {
            lam
        };
        WalkStateG {
            point: RawPointG::Affine {
                x: nb.to_poly.apply(xk),
                y: nb.to_poly.apply(yk),
            },
            a: S::mul_in(&self.mm, state.a, multiplier),
            b: S::mul_in(&self.mm, state.b, multiplier),
        }
    }

    /// The jump table drawn from `jump_seed` (`s` uniform in `[1, r)`, `s·G ≠ O`).
    pub fn jumps(&self, jump_seed: u64, charges: &mut StrongRhoCharges) -> Vec<JumpG<F::E, S>> {
        let mut rng = StdRng::seed_from_u64(jump_seed);
        (0..JUMPS)
            .map(|_| loop {
                let s = rng.gen_range(S::one()..self.modulus);
                charges.scalar_multiplications += 1;
                let point = self.scalar_mul(self.generator, s);
                if point != RawPointG::Infinity {
                    break JumpG { point, a: s };
                }
            })
            .collect()
    }

    /// Solve `[d]G = Q` for one target `q` in the prime subgroup.
    ///
    /// `jumps` is the jump table (see [`StrongRho::jumps`]); walk starts draw
    /// `stride ∈ [1, r)` and `cursor ∈ [0, r)` from `start_rng` and then step
    /// `c·G + Q` by `stride·G`. Returns `None` when the step cap is reached.
    pub fn solve(
        &self,
        q: RawPointG<F::E>,
        jumps: &[JumpG<F::E, S>],
        start_rng: &mut StdRng,
        params: &StrongRhoParams,
        mut charges: StrongRhoCharges,
    ) -> Option<StrongRhoOutcomeG<S>> {
        assert_eq!(jumps.len(), JUMPS, "jump table must have JUMPS entries");
        assert!(params.dp_bits < 32, "dp_bits must be below 32");
        let modulus = self.modulus;
        let stride_a = start_rng.gen_range(S::one()..modulus);
        let stride = self.scalar_mul(self.generator, stride_a);
        let mut cursor_a = start_rng.gen_range(S::zero()..modulus);
        let mut cursor = self.add(self.scalar_mul(self.generator, cursor_a), q);
        charges.scalar_multiplications += 2;
        charges.group_additions += 1;

        let dp_mask = (1u64 << params.dp_bits) - 1;
        let walk_cap = 8u64 << params.dp_bits;
        let ideal = self.ideal_steps();
        let step_cap = (ideal.ceil() as u64)
            .saturating_mul(params.step_cap_factor)
            .max(1_000_000);
        let lanes_n = params.lanes.max(1);
        let mut table: HashMap<(u8, F::E, F::E), (S, S)> = HashMap::new();
        let mut lanes = vec![
            Lane {
                state: WalkStateG {
                    point: RawPointG::Infinity,
                    a: S::zero(),
                    b: S::zero(),
                },
                previous: [RawPointG::Infinity; 4],
                length: 0,
                live: false,
            };
            lanes_n
        ];
        let zero = F::E::default();
        let mut denominators = vec![zero; lanes_n];
        let mut jump_index = vec![0usize; lanes_n];
        let mut active: Vec<usize> = Vec::with_capacity(lanes_n);
        let mut scratch: Vec<F::E> = Vec::new();
        let (mut steps, mut walks, mut fruitless, mut capped, mut wasted) = (0u64, 0u64, 0, 0, 0);
        let mut escapes = 0u64;
        let mut dp_trail_lengths: Vec<u32> = Vec::new();
        let mut abandoned_trail_lengths: Vec<u32> = Vec::new();

        while steps < step_cap {
            // Start a walk in every idle lane.
            for lane in lanes.iter_mut().filter(|lane| !lane.live) {
                loop {
                    walks += 1;
                    let start = cursor;
                    let start_a = cursor_a;
                    cursor = self.add(cursor, stride);
                    cursor_a = S::add_mod(cursor_a, stride_a, modulus);
                    charges.group_additions += 1;
                    if start == RawPointG::Infinity {
                        continue;
                    }
                    charges.canonicalizations += 1;
                    lane.state = self.canonicalize(WalkStateG {
                        point: start,
                        a: start_a,
                        b: S::one(),
                    });
                    lane.previous = [RawPointG::Infinity; 4];
                    lane.length = 0;
                    lane.live = true;
                    break;
                }
            }
            // Lanes standing on a distinguished point.
            for lane in lanes.iter_mut() {
                if !(lane.live && dp_hash(lane.state.point) & dp_mask == 0) {
                    continue;
                }
                lane.live = false;
                dp_trail_lengths.push(lane.length.min(u32::MAX as u64) as u32);
                let key = lane.state.point.key();
                charges.table_queries += 1;
                let Some(&(hit_a, hit_b)) = table.get(&key) else {
                    table.insert(key, (lane.state.a, lane.state.b));
                    charges.table_inserts += 1;
                    continue;
                };
                let denominator = S::sub_mod(lane.state.b, hit_b, modulus);
                let Some(inverse) = S::inverse_mod(denominator, modulus) else {
                    wasted += 1;
                    continue;
                };
                let candidate =
                    S::mul_mod(S::sub_mod(hit_a, lane.state.a, modulus), inverse, modulus);
                charges.scalar_multiplications += 1;
                if self.scalar_mul(self.generator, candidate) == q {
                    return Some(StrongRhoOutcomeG {
                        scalar: candidate,
                        walk_steps: steps,
                        walks,
                        fruitless,
                        escapes,
                        capped,
                        wasted_merges: wasted,
                        table_entries: table.len(),
                        ideal_steps: ideal,
                        automorphisms: self.automorphisms,
                        charges,
                        dp_trail_lengths,
                        abandoned_trail_lengths,
                    });
                }
                charges.failed_collisions += 1;
            }
            // One step for every live lane, denominators inverted together.
            active.clear();
            for (li, lane) in lanes.iter().enumerate() {
                if !lane.live {
                    continue;
                }
                let ji = partition(lane.state.point);
                charges.partition_hashes += 1;
                let j = active.len();
                jump_index[j] = ji;
                denominators[j] = match (lane.state.point, jumps[ji].point) {
                    (RawPointG::Affine { x: x1, .. }, RawPointG::Affine { x: x2, .. }) => x1 ^ x2,
                    _ => zero,
                };
                active.push(li);
            }
            self.gf
                .batch_inv(&mut denominators[..active.len()], &mut scratch);
            for (j, &li) in active.iter().enumerate() {
                let lane = &mut lanes[li];
                let jump = &jumps[jump_index[j]];
                let sum = match (lane.state.point, jump.point) {
                    (RawPointG::Affine { x: x1, y: y1 }, RawPointG::Affine { x: x2, y: y2 })
                        if denominators[j] != zero =>
                    {
                        let slope = self.mul(y1 ^ y2, denominators[j]);
                        self.add_with_slope(x1, y1, x2, slope)
                    }
                    _ => self.add(lane.state.point, jump.point),
                };
                charges.group_additions += 1;
                charges.canonicalizations += 1;
                let next = self.canonicalize(WalkStateG {
                    point: sum,
                    a: S::add_mod(lane.state.a, jump.a, modulus),
                    b: lane.state.b,
                });
                steps += 1;
                lane.length += 1;
                if next.point == lane.state.point || lane.previous.contains(&next.point) {
                    if !params.escape_fruitless {
                        fruitless += 1;
                        abandoned_trail_lengths.push(lane.length.min(u32::MAX as u64) as u32);
                        lane.live = false;
                        continue;
                    }
                    // [2]P_next, charged as one group operation; the history
                    // restarts so the escaped point is not taken for a cycle.
                    escapes += 1;
                    charges.group_additions += 1;
                    charges.canonicalizations += 1;
                    lane.state = self.canonicalize(WalkStateG {
                        point: self.add(next.point, next.point),
                        a: S::add_mod(next.a, next.a, modulus),
                        b: S::add_mod(next.b, next.b, modulus),
                    });
                    lane.previous = [RawPointG::Infinity; 4];
                    continue;
                }
                if lane.length > walk_cap {
                    capped += 1;
                    abandoned_trail_lengths.push(lane.length.min(u32::MAX as u64) as u32);
                    lane.live = false;
                    continue;
                }
                lane.previous = [
                    lane.state.point,
                    lane.previous[0],
                    lane.previous[1],
                    lane.previous[2],
                ];
                lane.state = next;
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;

    /// The run-based search returns what the exhaustive scan of all `n`
    /// rotations returns — the least word, the smallest `k` reaching it and
    /// whether another `k` does — at both widths, on random words and on
    /// the cases it could get wrong: constant words, single bits and
    /// periodic words, where several rotations tie.
    #[test]
    fn least_rotation_matches_the_exhaustive_scan() {
        fn check<E: FieldWord>(n: u32, words: &[E]) {
            let mask = word_mask::<E>(n);
            let nb = NormalBasis {
                n,
                mask,
                to_normal: Linear { tables: Vec::new() },
                to_poly: Linear { tables: Vec::new() },
            };
            for &c in words {
                let c = c & mask;
                let (mut best, mut best_k, mut tie) = (c, 0u32, false);
                for k in 1..n {
                    let v = nb.rotate(c, k);
                    if v < best {
                        (best, best_k, tie) = (v, k, false);
                    } else if v == best {
                        tie = true;
                    }
                }
                assert_eq!(
                    nb.least_rotation(c),
                    (best, best_k, tie),
                    "n = {n}, c = {c:?}"
                );
            }
        }
        let mut s = 0x2545_F491_4F6C_DD1Du64;
        let mut next = move || {
            s ^= s << 13;
            s ^= s >> 7;
            s ^= s << 17;
            s
        };
        let pattern = |n: u32, period: u32, pat: u128| {
            (0..n / period).fold(0u128, |w, k| w | (pat << (k * period)))
        };
        for n in 2u32..=127 {
            let mut words: Vec<u128> = vec![0, u128::MAX, 1, 1 << (n - 1), 3, !1];
            for period in 1..=n.min(10) {
                if n % period == 0 {
                    words.extend((1..(1u128 << period).min(48)).map(|p| pattern(n, period, p)));
                }
            }
            for _ in 0..300 {
                let w = (u128::from(next()) << 64) | u128::from(next());
                // Sparse and dense words carry long runs of one kind.
                words.extend([w, w & (w >> 3) & (w >> 7), w | (w >> 5) | (w >> 11)]);
            }
            if n <= 63 {
                check::<u64>(n, &words.iter().map(|&w| w as u64).collect::<Vec<_>>());
            }
            check::<u128>(n, &words);
        }
    }

    /// Koblitz rungs that construct, small enough to solve in a unit test.
    fn curves() -> Vec<KoblitzCurve> {
        let mut out = Vec::new();
        for n in [7u32, 11, 13, 17, 19, 23, 29, 31, 37, 41] {
            for a in [0u8, 1] {
                if let Some(curve) = KoblitzCurve::new(a, n) {
                    out.push(curve);
                }
            }
        }
        assert!(out.len() >= 8, "only {} rungs constructed", out.len());
        out
    }

    fn lib_point(curve: &KoblitzCurve, k: u64) -> RawPoint {
        RawPoint::from_binary(&curve.mul(curve.generator(), &BigUint::from(k)))
    }

    #[test]
    fn group_law_matches_the_library_curve() {
        for curve in curves() {
            let rho = StrongRho::new(&curve);
            let g = rho.generator();
            for k in [0u64, 1, 2, 3, 37, 91, 1000, rho.modulus() - 1] {
                assert_eq!(
                    rho.scalar_mul(g, k),
                    lib_point(&curve, k),
                    "n={} k={k}",
                    curve.n
                );
            }
            let p = lib_point(&curve, 37);
            let r = lib_point(&curve, 91);
            assert_eq!(rho.add(p, r), lib_point(&curve, 128));
            assert_eq!(rho.add(p, p), lib_point(&curve, 74));
        }
    }

    #[test]
    fn inverse_is_an_inverse() {
        for curve in curves() {
            let rho = StrongRho::new(&curve);
            let mask = (1u64 << curve.n) - 1;
            let mut rng = StdRng::seed_from_u64(curve.n as u64);
            for _ in 0..200 {
                let v = rng.gen::<u64>() & mask;
                if v != 0 {
                    assert_eq!(rho.mul(v, rho.inv(v)), 1, "n={}", curve.n);
                }
            }
        }
    }

    #[test]
    fn mul_mod_paths_agree() {
        let mut rng = StdRng::seed_from_u64(7);
        for m in [3u64, 1 << 20, (1 << 49) + 1, (1 << 50) - 3, (1 << 57) + 13] {
            let mm = MulMod::new(m);
            for _ in 0..20_000 {
                let (a, b) = (rng.gen_range(0..m), rng.gen_range(0..m));
                assert_eq!(mm.mul(a, b), mul_mod(a, b, m), "m={m}");
            }
            assert_eq!(mm.mul(m - 1, m - 1), mul_mod(m - 1, m - 1, m));
        }
    }

    /// The representative is a function of the orbit, and the multiplier is
    /// right: canon(σP) is the same point for every signed Frobenius image σP,
    /// and if P = a·G + b·Q then canon(P) = a'·G + b'·Q with (a', b') returned.
    #[test]
    fn canonical_form_is_orbit_invariant_and_multiplier_is_correct() {
        for curve in curves() {
            let rho = StrongRho::new(&curve);
            let r = rho.modulus();
            let d = r / 3 + 1;
            let q = rho.scalar_mul(rho.generator(), d);
            let mut rng = StdRng::seed_from_u64(1000 + curve.n as u64);
            for _ in 0..40 {
                let (a, b) = (rng.gen_range(0..r), rng.gen_range(1..r));
                let p = rho.add(rho.scalar_mul(rho.generator(), a), rho.scalar_mul(q, b));
                if p == RawPoint::Infinity {
                    continue;
                }
                let canon = rho.canonicalize(WalkState { point: p, a, b });
                let expected = rho.add(
                    rho.scalar_mul(rho.generator(), canon.a),
                    rho.scalar_mul(q, canon.b),
                );
                assert_eq!(canon.point, expected, "multiplier wrong at n={}", curve.n);
                // every orbit member maps to the same representative
                let mut image = p;
                for _ in 0..curve.n {
                    let RawPoint::Affine { x, y } = image else {
                        unreachable!()
                    };
                    for member in [image, RawPoint::Affine { x, y: y ^ x }] {
                        let c = rho.canonicalize(WalkState {
                            point: member,
                            a: 0,
                            b: 1,
                        });
                        assert_eq!(c.point, canon.point, "not orbit-invariant at n={}", curve.n);
                    }
                    image = RawPoint::Affine {
                        x: rho.sqr(x),
                        y: rho.sqr(y),
                    };
                }
            }
        }
    }

    #[test]
    fn solves_planted_targets_at_every_lane_width() {
        for curve in curves().into_iter().filter(|c| (13..=31).contains(&c.n)) {
            let rho = StrongRho::new(&curve);
            for (lanes, dp_bits) in [(1usize, 2u32), (8, 3), (32, 4)] {
                let params = StrongRhoParams {
                    lanes,
                    dp_bits,
                    ..StrongRhoParams::default()
                };
                for seed in 0..4u64 {
                    let mut charges = StrongRhoCharges::default();
                    let jumps = rho.jumps(seed ^ 0x5eed, &mut charges);
                    let mut rng = StdRng::seed_from_u64(seed);
                    let d = rng.gen_range(1..rho.modulus());
                    let q = rho.scalar_mul(rho.generator(), d);
                    let out = rho
                        .solve(q, &jumps, &mut rng, &params, charges)
                        .unwrap_or_else(|| panic!("no solve n={} lanes={lanes}", curve.n));
                    assert_eq!(out.scalar, d, "n={} lanes={lanes} seed={seed}", curve.n);
                    assert!(out.walk_steps > 0 && out.table_entries > 0);
                }
            }
        }
    }

    /// The wide field is a drop-in: with 128-bit words and 64-bit scalars the
    /// walk is the one-word walk, step for step, on every rung (the same
    /// modulus, normal basis, jumps, starts and hashes).
    #[test]
    fn the_wide_field_walks_exactly_as_the_one_word_field() {
        use crate::cryptanalysis::wide_gf2m::WideGf2;
        for curve in curves().into_iter().filter(|c| (17..=41).contains(&c.n)) {
            let narrow = StrongRho::new(&curve);
            let RawPoint::Affine { x, y } = narrow.generator() else {
                unreachable!()
            };
            let wide: StrongRhoG<WideGf2, u64> = StrongRhoG::from_parts(
                WideGf2::new(&curve.curve.irreducible),
                curve.a as u128,
                narrow.modulus(),
                narrow.lambda(),
                RawPointG::Affine {
                    x: x as u128,
                    y: y as u128,
                },
            );
            assert_eq!(wide.automorphisms(), narrow.automorphisms());
            for seed in 0..3u64 {
                let mut rng = StdRng::seed_from_u64(seed + 4242);
                let d = rng.gen_range(1..narrow.modulus());
                let qn = narrow.scalar_mul(narrow.generator(), d);
                let qw = wide.scalar_mul(wide.generator(), d);
                let RawPoint::Affine { x: qx, y: qy } = qn else {
                    unreachable!()
                };
                assert_eq!(
                    qw,
                    RawPointG::Affine {
                        x: qx as u128,
                        y: qy as u128
                    }
                );
                let mut cn = StrongRhoCharges::default();
                let mut cw = StrongRhoCharges::default();
                let jn = narrow.jumps(seed ^ 0xabc, &mut cn);
                let jw = wide.jumps(seed ^ 0xabc, &mut cw);
                let params = StrongRhoParams::default();
                let on = narrow
                    .solve(qn, &jn, &mut StdRng::seed_from_u64(seed), &params, cn)
                    .expect("narrow solve");
                let ow = wide
                    .solve(qw, &jw, &mut StdRng::seed_from_u64(seed), &params, cw)
                    .expect("wide solve");
                assert_eq!(on.scalar, d);
                assert_eq!(
                    (
                        ow.scalar,
                        ow.walk_steps,
                        ow.walks,
                        ow.fruitless,
                        ow.capped,
                        ow.wasted_merges,
                        ow.table_entries,
                        ow.charges
                    ),
                    (
                        on.scalar,
                        on.walk_steps,
                        on.walks,
                        on.fruitless,
                        on.capped,
                        on.wasted_merges,
                        on.table_entries,
                        on.charges
                    ),
                    "n={} seed={seed}",
                    curve.n
                );
            }
        }
    }

    /// The all-wide instantiation (128-bit words and scalars) solves too.
    #[test]
    fn the_wide_instantiation_solves_planted_targets() {
        use crate::cryptanalysis::wide_gf2m::WideGf2;
        for curve in curves().into_iter().filter(|c| (19..=31).contains(&c.n)) {
            let narrow = StrongRho::new(&curve);
            let RawPoint::Affine { x, y } = narrow.generator() else {
                unreachable!()
            };
            let wide: WideStrongRho = StrongRhoG::from_parts(
                WideGf2::new(&curve.curve.irreducible),
                curve.a as u128,
                narrow.modulus() as u128,
                narrow.lambda() as u128,
                RawPointG::Affine {
                    x: x as u128,
                    y: y as u128,
                },
            );
            for seed in 0..3u64 {
                let mut rng = StdRng::seed_from_u64(seed + 7);
                let d: u128 = rng.gen_range(1..wide.modulus());
                let q = wide.scalar_mul(wide.generator(), d);
                let mut c = StrongRhoCharges::default();
                let j = wide.jumps(seed, &mut c);
                let out = wide
                    .solve(q, &j, &mut rng, &StrongRhoParams::default(), c)
                    .expect("wide solve");
                assert_eq!(out.scalar, d, "n={} seed={seed}", curve.n);
            }
        }
    }

    #[test]
    fn u128_scalar_ring_matches_bigint() {
        use num_bigint::BigUint;
        let mut rng = StdRng::seed_from_u64(9);
        for m in [
            97u128,
            (1u128 << 81) + 29,
            2417851639230796216685689,
            (1u128 << 126) - 137,
            (1u128 << 127) - 1,
        ] {
            for _ in 0..500 {
                let (a, b): (u128, u128) = (rng.gen_range(0..m), rng.gen_range(0..m));
                let want = (BigUint::from(a) * BigUint::from(b)) % BigUint::from(m);
                assert_eq!(
                    BigUint::from(<u128 as RhoScalar>::mul_mod(a, b, m)),
                    want,
                    "m={m}"
                );
                let want = (BigUint::from(a) + BigUint::from(b)) % BigUint::from(m);
                assert_eq!(BigUint::from(<u128 as RhoScalar>::add_mod(a, b, m)), want);
                if a != 0 && m == 2417851639230796216685689 {
                    let inv = <u128 as RhoScalar>::inverse_mod(a, m).unwrap();
                    assert_eq!(<u128 as RhoScalar>::mul_mod(a, inv, m), 1);
                }
            }
        }
    }

    /// With the escape, long distinguished-point walks survive fruitless
    /// cycles: at dp_bits = 10 (walks of ~1000 steps, where an abandoning
    /// walk dies about a quarter of the time) every solve recovers its
    /// target, escapes happen, nothing is abandoned as fruitless, and the
    /// step count stays near the ideal.
    #[test]
    fn escaping_walks_solve_with_long_distinguished_walks() {
        for curve in curves().into_iter().filter(|c| c.n >= 37) {
            let rho = StrongRho::new(&curve);
            let params = StrongRhoParams {
                dp_bits: 10,
                escape_fruitless: true,
                ..StrongRhoParams::default()
            };
            let mut ratios = Vec::new();
            let mut escapes = 0;
            for seed in 0..6u64 {
                let mut charges = StrongRhoCharges::default();
                let jumps = rho.jumps(seed + 300, &mut charges);
                let mut rng = StdRng::seed_from_u64(seed + 500);
                let d = rng.gen_range(1..rho.modulus());
                let q = rho.scalar_mul(rho.generator(), d);
                let out = rho
                    .solve(q, &jumps, &mut rng, &params, charges)
                    .expect("solve");
                assert_eq!(out.scalar, d, "n={} seed={seed}", curve.n);
                assert_eq!(
                    out.fruitless, 0,
                    "an escaping walk is never abandoned as fruitless"
                );
                escapes += out.escapes;
                ratios.push(out.walk_steps as f64 / out.ideal_steps);
            }
            assert!(
                escapes > 0,
                "n={}: no fruitless cycle met in six solves",
                curve.n
            );
            ratios.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let median = ratios[ratios.len() / 2];
            assert!(
                (0.3..4.0).contains(&median),
                "n={} median {median}",
                curve.n
            );
        }
    }

    /// A strong rho should need about √(πr/2A) steps; at n = 37/41 the median
    /// over a few seeds stays within a generous factor of that.
    #[test]
    fn step_counts_are_near_the_ideal() {
        for curve in curves().into_iter().filter(|c| c.n >= 37) {
            let rho = StrongRho::new(&curve);
            let mut ratios = Vec::new();
            for seed in 0..9u64 {
                let mut charges = StrongRhoCharges::default();
                let jumps = rho.jumps(seed + 77, &mut charges);
                let mut rng = StdRng::seed_from_u64(seed + 99);
                let d = rng.gen_range(1..rho.modulus());
                let q = rho.scalar_mul(rho.generator(), d);
                let out = rho
                    .solve(q, &jumps, &mut rng, &StrongRhoParams::default(), charges)
                    .expect("solve");
                assert_eq!(out.scalar, d);
                ratios.push(out.walk_steps as f64 / out.ideal_steps);
            }
            ratios.sort_by(|a, b| a.partial_cmp(b).unwrap());
            let median = ratios[ratios.len() / 2];
            assert!(
                (0.3..4.0).contains(&median),
                "n={} median steps/ideal {median}",
                curve.n
            );
        }
    }
}
