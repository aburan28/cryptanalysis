//! Supersingular-isogeny arithmetic at SQIsign's NIST level-1 parameter size.
//!
//! # What this is, and what it is not
//!
//! This module is **not** SQIsign.  It is the arithmetic core that SQIsign
//! *verification* runs on: the quadratic extension field `F_p^2`, x-only
//! Montgomery curve arithmetic, and 2-isogeny chains, all at the real
//! parameter size rather than at the toy size used by
//! [`crate::pqc::sqisign`] (`p = 431`, 37 curves, a precomputed graph).
//!
//! The split is deliberate.  SQIsign's *signing* algorithm needs quaternion
//! order arithmetic, the Deuring correspondence and KLPT — tens of thousands
//! of lines, none of which is here.  SQIsign's *verifier*, by contrast, is
//! almost entirely this file: it re-derives a chain of 2-isogenies from the
//! signature and compares the codomain's j-invariant against the public key.
//! Its cost is dominated by `F_p^2` multiplication and by walking 2-isogeny
//! chains on Montgomery curves, which is exactly what is implemented and
//! measured below.
//!
//! What a real SQIsign would still need on top of this:
//!
//! * the quaternion algebra `B_{p,∞}`, maximal orders, ideals, lattice
//!   reduction over `Z^4`, and `KLPT` for equivalent-ideal search (signing);
//! * the Deuring correspondence: ideal-to-isogeny translation (signing);
//! * for the current, dimension-2 flavour of SQIsign, the theta-model
//!   `(2,2)`-isogeny machinery on products of elliptic curves (both);
//! * deterministic point compression/decompression, torsion-basis
//!   generation, the Fiat–Shamir hash, and the KAT plumbing (both).
//!
//! As a fraction of the scheme: this is most of the field/curve layer that
//! the verifier spends its cycles in, and roughly nothing of the signer.  Do
//! not read this file as "SQIsign is implemented".
//!
//! # The prime
//!
//! `p = 3 * 2^324 - 1` (326 bits, six 64-bit limbs).
//!
//! This is the genuine NIST level-1 (128-bit security) prime of the SQIsign
//! submission, not a representative stand-in.  It was read out of the
//! official reference implementation, <https://github.com/SQISign/the-sqisign>
//! at commit `7358e878`, file `src/precomp/ref/p324_3/sqisign_parameters.txt`:
//!
//! ```text
//! lvl = 1
//! p = 0x2fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff
//! security = 128
//! ```
//!
//! with the same value restated as `p324_3: p = 3 * 2^324 - 1 (326 bits, 6
//! limbs)` in `src/gf/sat64/p324_3/include/fp_generic_params.h`.  Two
//! independent cross-checks were run against that header before the
//! constants below were written down: the limb decomposition of `p` matches
//! its `FPG_P_INIT`, and the Montgomery constants [`R_MOD_P`] and
//! [`R2_MOD_P`] recomputed here from scratch match its `FPG_ONE_INIT` and
//! `FPG_R2_INIT` limb for limb.  (For the record, the sibling levels are
//! `p = 27 * 2^500 - 1` for level 3 and `p = 17 * 2^664 - 1` for level 5.)
//!
//! A note for readers expecting 254 bits: the *2023 round-1* SQIsign
//! submission used a ~254-bit level-1 prime.  The current submission — the
//! dimension-2 "SQIsign 2.0" reconstruction — moved to 326 bits, because the
//! level-1 curve arithmetic now happens in dimension 2 over a smaller
//! effective security margin per field operation.  326 bits is six limbs
//! rather than four, so every field multiplication here costs about
//! `(6/4)^2 = 2.25x` what a 254-bit one would.
//!
//! `p + 1 = 3 * 2^324` is what makes the prime useful: the full `2^324`
//! torsion of a supersingular curve over `F_p^2` is `F_p^2`-rational, so a
//! 2-isogeny walk of length 324 can be taken without ever leaving the field.
//! `p ≡ 3 (mod 4)`, so `x^2 + 1` is irreducible and `F_p^2 = F_p[i]/(i^2+1)`.
//!
//! # Why the reduction is the shape it is
//!
//! Written as `p = 48 * 2^320 - 1`, the prime has two properties that make
//! Montgomery reduction unusually cheap:
//!
//! * `p ≡ -1 (mod 2^64)`, so the Montgomery constant `p' = -p^{-1} mod 2^64`
//!   is exactly `1`.  The per-limb quotient digit is `m = t[0]`, with no
//!   multiplication at all.
//! * `m * p = m * 48 * 2^320 - m`.  The `-m` cancels `t[0]` exactly (that is
//!   what choosing `m = t[0]` means), with no borrow, so dividing by `2^64`
//!   is a pure limb shift; and the `+ m*48*2^320` part is a single
//!   `64x8 -> 70`-bit multiply landing at limb 5.
//!
//! So a CIOS round costs six `64x64 -> 128` multiplies for `a[i]*b` plus one
//! tiny multiply, instead of the usual `2n`.  A full `mul` is 36 + 6
//! multiplies.  This is the "specialised reduction exploiting the prime's
//! shape" that a generic CIOS would leave on the table, and it is why a
//! 326-bit multiplication here measures 48-61 cycles rather than the ~110 a
//! generic six-limb CIOS would need.  (The spread is real and is *between
//! builds*, not within them: two back-to-back runs of one binary agree to
//! 0.5%, but adding or removing unrelated code moves the number by a quarter.
//! Code layout and inlining decisions dominate at this size.  The current
//! tree measures 61.)
//!
//! One thing that did *not* pay off, recorded because the negative result is
//! the useful part: a dedicated squaring with the off-diagonal trick (21 limb
//! multiplies instead of 36) was written, differentially tested, and measured
//! at 51 cycles against the general multiply's 48 — no faster.  Nor reliably
//! slower: after it was removed, the two benchmark rows, now running
//! *identical* code, still differed by 5% (58 against 61), which is how big
//! the layout effect alone is here.  The plausible reason it fails to win is
//! that with the reduction already this cheap, the 12-limb doubling shift and
//! the separated reduction's carry-propagation loop cost about what the 15
//! saved multiplies do.  Forty lines of carry plumbing that buys nothing measurable
//! is not worth keeping, so [`Fp::sqr`] is just `mul(a, a)`.  This is a
//! not-measured-any-better result, not a proof that the trick cannot be made
//! to win with a more integrated reduction.
//!
//! # Security
//!
//! **Not constant time, not for production.**  The scalar ladder does use a
//! mask-based conditional swap, but nothing else here was written for it:
//! `csub_p` is data-dependent in its branch-free form only by accident, the
//! inversion chain is fine but `is_square`/`sqrt` are not, and no attempt was
//! made to defeat compiler reintroduction of branches.  See `SECURITY.md`.

#![allow(clippy::needless_range_loop)]

// ─── F_p: the base field ────────────────────────────────────────────────────

/// Number of 64-bit limbs in a field element.  `ceil(326 / 64) = 6`.
pub const NLIMBS: usize = 6;

/// Bit length of `p`.
pub const P_BITS: usize = 326;

/// `a` in `p + 1 = 3 * 2^a`: the length of the available 2-isogeny walk.
pub const TWO_TORSION_POWER: usize = 324;

const MASK64: u128 = 0xFFFF_FFFF_FFFF_FFFF;

/// `p = 3 * 2^324 - 1 = 48 * 2^320 - 1`, little-endian limbs.
pub const P: [u64; NLIMBS] = [
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0x0000_0000_0000_002f,
];

/// The top limb of `p` written as `48 * 2^320`: `m * p` adds `48 * m` here.
const P_HI_MUL: u128 = 48;

/// `R = 2^384 mod p`.  This is the Montgomery representation of `1`.
/// Matches `FPG_ONE_INIT` in the SQIsign reference.
pub const R_MOD_P: [u64; NLIMBS] = [
    0x0555_5555_5555_5555,
    0x0000_0000_0000_0000,
    0x0000_0000_0000_0000,
    0x0000_0000_0000_0000,
    0x0000_0000_0000_0000,
    0x0000_0000_0000_0010,
];

/// `R^2 = 2^768 mod p`, used to enter Montgomery form.
/// Matches `FPG_R2_INIT` in the SQIsign reference.
pub const R2_MOD_P: [u64; NLIMBS] = [
    0xc71c_71c7_1c71_c71c,
    0x5571_c71c_71c7_1c71,
    0x5555_5555_5555_5555,
    0x5555_5555_5555_5555,
    0x5555_5555_5555_5555,
    0x0000_0000_0000_0015,
];

/// `(p - 1) / 2 = 3 * 2^323 - 1`, the Euler-criterion exponent.
const EXP_P_MINUS_1_OVER_2: [u64; NLIMBS] = [
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0xffff_ffff_ffff_ffff,
    0x0000_0000_0000_0017,
];

/// `(p + 1) / 4 = 3 * 2^322`, the square-root exponent for `p ≡ 3 (mod 4)`.
const EXP_P_PLUS_1_OVER_4: [u64; NLIMBS] = [0, 0, 0, 0, 0, 0x0000_0000_0000_000c];

/// `p + 1 = 3 * 2^324`, the order of every point of `E(F_p)` for the
/// supersingular curves this module walks on, and the full group exponent of
/// `E(F_p^2)` when `#E(F_p^2) = (p+1)^2`.
pub const P_PLUS_1: [u64; NLIMBS] = [0, 0, 0, 0, 0, 0x0000_0000_0000_0030];

/// Bit length of `p + 1`.
pub const P_PLUS_1_BITS: usize = 326;

/// Subtract `p` from `r` if `r >= p`.  Branch-free: compute `r - p` and pick
/// with a mask derived from the borrow, so no secret-dependent branch is
/// emitted at this level (the rest of the module makes no such promise).
#[inline(always)]
fn csub_p(r: [u64; NLIMBS]) -> [u64; NLIMBS] {
    let mut d = [0u64; NLIMBS];
    let mut borrow = 0u64;
    for i in 0..NLIMBS {
        let (t, b1) = r[i].overflowing_sub(P[i]);
        let (t, b2) = t.overflowing_sub(borrow);
        d[i] = t;
        borrow = (b1 as u64) | (b2 as u64);
    }
    // borrow == 1  =>  r < p, keep r.   borrow == 0  =>  r >= p, keep d.
    let keep_r = 0u64.wrapping_sub(borrow);
    let mut out = [0u64; NLIMBS];
    for i in 0..NLIMBS {
        out[i] = (r[i] & keep_r) | (d[i] & !keep_r);
    }
    out
}

/// Montgomery multiplication: given `a = xR mod p` and `b = yR mod p`,
/// returns `xyR mod p`, fully reduced into `[0, p)`.
///
/// CIOS (coarsely integrated operand scanning) specialised to
/// `p = 48 * 2^320 - 1`; see the module docs for why the reduction half of
/// each round costs one small multiply instead of six.
#[inline(always)]
fn mont_mul(a: &[u64; NLIMBS], b: &[u64; NLIMBS]) -> [u64; NLIMBS] {
    // One extra limb: `t + a[i]*b` can be 385 bits wide before reduction.
    let mut t = [0u64; NLIMBS + 1];

    for i in 0..NLIMBS {
        // t += a[i] * b
        let ai = a[i] as u128;
        let mut carry: u128 = 0;
        for j in 0..NLIMBS {
            let s = (t[j] as u128) + ai * (b[j] as u128) + carry;
            t[j] = s as u64;
            carry = s >> 64;
        }
        // t[NLIMBS] is 0 on entry (the running value is < 2p < 2^327), so this
        // cannot overflow.
        debug_assert_eq!(t[NLIMBS], 0);
        t[NLIMBS] = carry as u64;
        debug_assert!(carry >> 64 == 0);

        // t := (t + m*p) / 2^64, with m = t[0] (because p' = 1).
        let w = (t[0] as u128) * P_HI_MUL; // 48*m, < 2^70

        // The `-m` half of `m*p` zeroes t[0] exactly; the division by 2^64 is
        // therefore a limb shift with nothing to borrow.
        t[0] = t[1];
        t[1] = t[2];
        t[2] = t[3];
        t[3] = t[4];
        t[4] = t[5];
        t[5] = t[6];
        t[6] = 0;

        // The `+48*m*2^320` half lands at limb 5 before the shift, so at limb
        // 4 after it.
        let s = (t[4] as u128) + (w & MASK64);
        t[4] = s as u64;
        let s = (t[5] as u128) + (w >> 64) + (s >> 64);
        t[5] = s as u64;
        t[6] = (s >> 64) as u64;
    }
    debug_assert_eq!(t[NLIMBS], 0);

    // The Montgomery result is < p + p^2/R < p + 2^268, so one conditional
    // subtraction is enough.
    csub_p([t[0], t[1], t[2], t[3], t[4], t[5]])
}

/// An element of `F_p`, held in Montgomery form (`value * 2^384 mod p`) and
/// always fully reduced into `[0, p)`, so `PartialEq` is field equality.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fp(pub(crate) [u64; NLIMBS]);

impl Fp {
    /// Additive identity.
    pub const ZERO: Fp = Fp([0; NLIMBS]);
    /// Multiplicative identity (which is `R mod p` in Montgomery form).
    pub const ONE: Fp = Fp(R_MOD_P);

    /// `a + b mod p`.
    #[inline(always)]
    pub fn add(&self, o: &Fp) -> Fp {
        let mut r = [0u64; NLIMBS];
        let mut carry = 0u64;
        for i in 0..NLIMBS {
            let s = (self.0[i] as u128) + (o.0[i] as u128) + (carry as u128);
            r[i] = s as u64;
            carry = (s >> 64) as u64;
        }
        // Both inputs are < p < 2^326, so the sum is < 2^327 and no carry
        // leaves the top limb; one conditional subtraction reduces it.
        debug_assert_eq!(carry, 0);
        Fp(csub_p(r))
    }

    /// `a - b mod p`.
    #[inline(always)]
    pub fn sub(&self, o: &Fp) -> Fp {
        let mut r = [0u64; NLIMBS];
        let mut borrow = 0u64;
        for i in 0..NLIMBS {
            let (t, b1) = self.0[i].overflowing_sub(o.0[i]);
            let (t, b2) = t.overflowing_sub(borrow);
            r[i] = t;
            borrow = (b1 as u64) | (b2 as u64);
        }
        // On borrow, add p back.
        let mask = 0u64.wrapping_sub(borrow);
        let mut carry = 0u64;
        for i in 0..NLIMBS {
            let s = (r[i] as u128) + ((P[i] & mask) as u128) + (carry as u128);
            r[i] = s as u64;
            carry = (s >> 64) as u64;
        }
        Fp(r)
    }

    /// `-a mod p`.
    #[inline(always)]
    pub fn neg(&self) -> Fp {
        Fp::ZERO.sub(self)
    }

    /// `2a mod p`.
    #[inline(always)]
    pub fn double(&self) -> Fp {
        self.add(self)
    }

    /// `a * b mod p`, Montgomery form in and out.
    #[inline(always)]
    pub fn mul(&self, o: &Fp) -> Fp {
        Fp(mont_mul(&self.0, &o.0))
    }

    /// `a^2 mod p`.
    ///
    /// This is just [`Fp::mul`] with both operands the same.  A dedicated
    /// off-diagonal squaring (21 limb multiplies instead of 36) was written
    /// and measured at 51 cycles against 48 for the general multiply: no
    /// faster, and the difference is no bigger than this benchmark's
    /// build-to-build layout noise.  See the module docs; it was dropped
    /// rather than kept as an unearned complication.
    #[inline(always)]
    pub fn sqr(&self) -> Fp {
        Fp(mont_mul(&self.0, &self.0))
    }

    /// Is this the zero element?
    #[inline(always)]
    pub fn is_zero(&self) -> bool {
        self.0 == [0u64; NLIMBS]
    }

    /// `a^e`, square-and-multiply over the little-endian limbs of `e`.
    /// Used for the Euler criterion and square roots; inversion has its own
    /// shorter chain.
    pub fn pow(&self, e: &[u64]) -> Fp {
        let mut acc = Fp::ONE;
        let mut started = false;
        for limb_i in (0..e.len()).rev() {
            for bit in (0..64).rev() {
                if started {
                    acc = acc.sqr();
                }
                if (e[limb_i] >> bit) & 1 == 1 {
                    acc = if started { acc.mul(self) } else { *self };
                    started = true;
                }
            }
        }
        if started {
            acc
        } else {
            Fp::ONE
        }
    }

    /// `x^(2^k) * x` where `x = a^(2^k - 1)`; i.e. `a^(2^(2k) - 1)`.
    /// The doubling step of the standard "all ones" addition chain.
    #[inline]
    fn chain_double(&self, k: usize) -> Fp {
        let mut t = *self;
        for _ in 0..k {
            t = t.sqr();
        }
        t.mul(self)
    }

    /// `a^-1 mod p`, by Fermat.
    ///
    /// `p - 2 = 3 * 2^324 - 3 = 3 * (2^324 - 1)`, so `a^(p-2) = y^3` with
    /// `y = a^(2^324 - 1)`.  `y` comes from the all-ones addition chain on
    /// `324 = 0b101000100`: 323 squarings and 10 multiplies, then one more
    /// squaring and multiply for the cube.  324 S + 11 M in total, against
    /// 325 S + ~163 M for a naive binary `a^(p-2)`.
    ///
    /// Returns zero for zero, which is not an inverse; callers that care must
    /// check.  (Every call site here works on invertible denominators.)
    pub fn inv(&self) -> Fp {
        let x1 = *self; // a^(2^1 - 1)
        let x2 = x1.chain_double(1); // 2^2 - 1
        let x4 = x2.chain_double(2); // 2^4 - 1
        let x5 = x4.sqr().mul(self); // 2^5 - 1
        let x10 = x5.chain_double(5); // 2^10 - 1
        let x20 = x10.chain_double(10); // 2^20 - 1
        let x40 = x20.chain_double(20); // 2^40 - 1
        let x80 = x40.chain_double(40); // 2^80 - 1
        let x81 = x80.sqr().mul(self); // 2^81 - 1
        let x162 = x81.chain_double(81); // 2^162 - 1
        let y = x162.chain_double(162); // 2^324 - 1
        y.sqr().mul(&y) // y^3 = a^(p-2)
    }

    /// Euler criterion: is `a` a square in `F_p`?  Zero counts as a square.
    pub fn is_square(&self) -> bool {
        self.is_zero() || self.pow(&EXP_P_MINUS_1_OVER_2) == Fp::ONE
    }

    /// A square root of `a` in `F_p`, or `None` if `a` is not a square.
    /// `p ≡ 3 (mod 4)`, so the root is just `a^((p+1)/4)`.
    pub fn sqrt(&self) -> Option<Fp> {
        let r = self.pow(&EXP_P_PLUS_1_OVER_4);
        if r.sqr() == *self {
            Some(r)
        } else {
            None
        }
    }

    /// Lift a small integer into the field.
    pub fn from_u64(v: u64) -> Fp {
        Fp(mont_mul(&[v, 0, 0, 0, 0, 0], &R2_MOD_P))
    }

    /// Enter Montgomery form from little-endian limbs, which must be `< p`.
    pub fn from_canonical(l: [u64; NLIMBS]) -> Fp {
        debug_assert!(lt_p(&l));
        Fp(mont_mul(&l, &R2_MOD_P))
    }

    /// Leave Montgomery form: the ordinary integer representative in `[0, p)`.
    pub fn to_canonical(&self) -> [u64; NLIMBS] {
        mont_mul(&self.0, &[1, 0, 0, 0, 0, 0])
    }
}

/// Is `l < p`?
fn lt_p(l: &[u64; NLIMBS]) -> bool {
    for i in (0..NLIMBS).rev() {
        if l[i] != P[i] {
            return l[i] < P[i];
        }
    }
    false
}

// ─── F_p^2 = F_p[i] / (i^2 + 1) ─────────────────────────────────────────────

/// An element `re + im*i` of `F_p^2`, with `i^2 = -1`.
///
/// `x^2 + 1` is irreducible over `F_p` exactly because `p ≡ 3 (mod 4)`, which
/// this prime satisfies (`p = 3*2^324 - 1 ≡ 3 mod 4`).  Every implementation
/// of SQIsign, SIKE and CSIDH uses this basis, so the formulas below are the
/// standard ones.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fp2 {
    /// Coefficient of `1`.
    pub re: Fp,
    /// Coefficient of `i`.
    pub im: Fp,
}

impl Fp2 {
    /// Additive identity.
    pub const ZERO: Fp2 = Fp2 {
        re: Fp::ZERO,
        im: Fp::ZERO,
    };
    /// Multiplicative identity.
    pub const ONE: Fp2 = Fp2 {
        re: Fp::ONE,
        im: Fp::ZERO,
    };

    /// `re + im*i`.
    #[inline(always)]
    pub fn new(re: Fp, im: Fp) -> Fp2 {
        Fp2 { re, im }
    }

    /// The image of `v` under `F_p -> F_p^2`.
    #[inline(always)]
    pub fn from_u64(v: u64) -> Fp2 {
        Fp2 {
            re: Fp::from_u64(v),
            im: Fp::ZERO,
        }
    }

    /// Componentwise addition.
    #[inline(always)]
    pub fn add(&self, o: &Fp2) -> Fp2 {
        Fp2 {
            re: self.re.add(&o.re),
            im: self.im.add(&o.im),
        }
    }

    /// Componentwise subtraction.
    #[inline(always)]
    pub fn sub(&self, o: &Fp2) -> Fp2 {
        Fp2 {
            re: self.re.sub(&o.re),
            im: self.im.sub(&o.im),
        }
    }

    /// Componentwise negation.
    #[inline(always)]
    pub fn neg(&self) -> Fp2 {
        Fp2 {
            re: self.re.neg(),
            im: self.im.neg(),
        }
    }

    /// `2a`.
    #[inline(always)]
    pub fn double(&self) -> Fp2 {
        Fp2 {
            re: self.re.double(),
            im: self.im.double(),
        }
    }

    /// Multiplication by Karatsuba: **three** `F_p` multiplications, not four.
    ///
    /// ```text
    /// (a0 + a1 i)(b0 + b1 i) = (a0 b0 - a1 b1)
    ///                        + ((a0+a1)(b0+b1) - a0 b0 - a1 b1) i
    /// ```
    ///
    /// The schoolbook form costs 4M + 2A; this costs 3M + 5A.  At six limbs a
    /// multiply is far more than an add, so the trade is worth taking — that
    /// is the whole reason `F_p^2` arithmetic is quoted as "about 3x `F_p`"
    /// rather than 4x.
    #[inline(always)]
    pub fn mul(&self, o: &Fp2) -> Fp2 {
        let v0 = self.re.mul(&o.re);
        let v1 = self.im.mul(&o.im);
        let s = self.re.add(&self.im).mul(&o.re.add(&o.im));
        Fp2 {
            re: v0.sub(&v1),
            im: s.sub(&v0).sub(&v1),
        }
    }

    /// Squaring: **two** `F_p` multiplications.
    ///
    /// ```text
    /// (a0 + a1 i)^2 = (a0 - a1)(a0 + a1) + 2 a0 a1 i
    /// ```
    ///
    /// The real part uses the difference of squares rather than two squarings,
    /// which is the standard "complex squaring" trick.
    #[inline(always)]
    pub fn sqr(&self) -> Fp2 {
        let t0 = self.re.add(&self.im);
        let t1 = self.re.sub(&self.im);
        let re = t0.mul(&t1);
        let im = self.re.mul(&self.im).double();
        Fp2 { re, im }
    }

    /// `a * b` where `b` lies in the base field.
    #[inline(always)]
    pub fn mul_fp(&self, o: &Fp) -> Fp2 {
        Fp2 {
            re: self.re.mul(o),
            im: self.im.mul(o),
        }
    }

    /// The norm `N(a) = a * conj(a) = a0^2 + a1^2`, an element of `F_p`.
    #[inline(always)]
    pub fn norm(&self) -> Fp {
        self.re.sqr().add(&self.im.sqr())
    }

    /// Inversion via the norm: `1/a = conj(a) / N(a)`.
    ///
    /// One `F_p` inversion, two `F_p` squarings and two `F_p` multiplications.
    /// Going through the norm is what keeps the single expensive inversion in
    /// the base field instead of the extension.
    pub fn inv(&self) -> Fp2 {
        let n = self.norm().inv();
        Fp2 {
            re: self.re.mul(&n),
            im: self.im.mul(&n).neg(),
        }
    }

    /// Is this the zero element?
    #[inline(always)]
    pub fn is_zero(&self) -> bool {
        self.re.is_zero() && self.im.is_zero()
    }

    /// Is `a` a square in `F_p^2`?
    ///
    /// `a = g^k` is a square iff `k` is even iff `a^((p^2-1)/2) = 1` iff
    /// `N(a)^((p-1)/2) = 1`, since `N(a) = a^(p+1)`.  So one Euler criterion
    /// in the *base* field answers it, which is half the exponent length.
    pub fn is_square(&self) -> bool {
        self.norm().is_square()
    }

    /// A square root in `F_p^2`, or `None`.
    ///
    /// The complex method for `p ≡ 3 (mod 4)`: write `a = a0 + a1 i`.  If
    /// `s = sqrt(N(a))` in `F_p` exists, then `(a0 ± s)/2` is the square of
    /// the real part of a root; take whichever of the two is a square in
    /// `F_p`, and recover the imaginary part from `a1 = 2 x0 x1`.
    pub fn sqrt(&self) -> Option<Fp2> {
        if self.is_zero() {
            return Some(Fp2::ZERO);
        }
        if self.im.is_zero() {
            // a is in F_p: either sqrt(a0) is in F_p, or sqrt(-a0) is and the
            // root is i*sqrt(-a0).
            return match self.re.sqrt() {
                Some(r) => Some(Fp2 {
                    re: r,
                    im: Fp::ZERO,
                }),
                None => self.re.neg().sqrt().map(|r| Fp2 {
                    re: Fp::ZERO,
                    im: r,
                }),
            };
        }
        let s = self.norm().sqrt()?;
        let two_inv = Fp::from_u64(2).inv();
        let mut t = self.re.add(&s).mul(&two_inv);
        if !t.is_square() {
            t = self.re.sub(&s).mul(&two_inv);
        }
        let x0 = t.sqrt()?;
        if x0.is_zero() {
            return None;
        }
        let x1 = self.im.mul(&x0.double().inv());
        let r = Fp2 { re: x0, im: x1 };
        if r.sqr() == *self {
            Some(r)
        } else {
            None
        }
    }
}

// ─── Montgomery curves, x-only projective coordinates ───────────────────────

/// A point on a Montgomery curve given only by its `x`-coordinate, in
/// projective form `(X : Z)` with `x = X/Z`.  `Z = 0` is the point at
/// infinity.
///
/// x-only is not a space optimisation: it is what makes the arithmetic fast.
/// Dropping `y` collapses `P` and `-P` to one object, which is exactly the
/// quotient on which the Montgomery differential formulas act, and it is the
/// representation the isogeny formulas (Vélu on Montgomery models) are
/// written in.
/// Note: deliberately no `PartialEq`.  `(X : Z)` is projective, so two
/// different limb patterns can be the same point; use [`PointX::same_x`].
#[derive(Clone, Copy, Debug)]
pub struct PointX {
    /// Projective `X`.
    pub x: Fp2,
    /// Projective `Z`.
    pub z: Fp2,
}

impl PointX {
    /// The point at infinity, `(1 : 0)`.
    pub const INFINITY: PointX = PointX {
        x: Fp2::ONE,
        z: Fp2::ZERO,
    };

    /// `(x : 1)`.
    pub fn from_affine(x: Fp2) -> PointX {
        PointX { x, z: Fp2::ONE }
    }

    /// Is this the point at infinity?  In x-only coordinates that is exactly
    /// `Z = 0`, which is how "the scalar killed the point" is detected.
    pub fn is_infinity(&self) -> bool {
        self.z.is_zero()
    }

    /// The affine `x`, or `None` at infinity.  Costs an inversion.
    pub fn affine_x(&self) -> Option<Fp2> {
        if self.is_infinity() {
            None
        } else {
            Some(self.x.mul(&self.z.inv()))
        }
    }

    /// Do two projective points represent the same `x`?  `X1 Z2 = X2 Z1`.
    pub fn same_x(&self, o: &PointX) -> bool {
        self.x.mul(&o.z) == o.x.mul(&self.z)
    }

    /// Conditional swap, mask-based.  Used by the ladder.
    #[inline(always)]
    fn cswap(a: &mut PointX, b: &mut PointX, swap: u64) {
        let mask = 0u64.wrapping_sub(swap & 1);
        for (pa, pb) in [
            (&mut a.x.re.0, &mut b.x.re.0),
            (&mut a.x.im.0, &mut b.x.im.0),
            (&mut a.z.re.0, &mut b.z.re.0),
            (&mut a.z.im.0, &mut b.z.im.0),
        ] {
            for i in 0..NLIMBS {
                let t = mask & (pa[i] ^ pb[i]);
                pa[i] ^= t;
                pb[i] ^= t;
            }
        }
    }
}

/// A Montgomery curve `E_{A,C}: C y^2 = C x^3 + A x^2 + C x`, stored as
/// `A24plus = A + 2C` and `C24 = 4C`.
///
/// Why this representation and not `(A : C)`: the doubling formula needs
/// `(A + 2C)` and `4C` and nothing else, and the 2- and 4-isogeny codomain
/// formulas *produce* exactly those two quantities.  Keeping them is what
/// removes the two additions per doubling and, more importantly, lets an
/// isogeny step hand its output straight to the next doubling with no
/// conversion.  This is the SIKE/SQIsign convention.
/// Note: deliberately no `PartialEq`.  `(A24plus : C24)` is projective and
/// two isogeny walkers reaching the same curve routinely land on different
/// representatives of it; use [`Curve::same_curve`] (equal model) or compare
/// [`Curve::j_invariant`] (equal up to isomorphism).
#[derive(Clone, Copy, Debug)]
pub struct Curve {
    /// `A + 2C`.
    pub a24plus: Fp2,
    /// `4C`.
    pub c24: Fp2,
}

impl Curve {
    /// The curve `y^2 = x^3 + A x^2 + x`, i.e. `C = 1`.
    pub fn from_a(a: Fp2) -> Curve {
        Curve {
            a24plus: a.add(&Fp2::from_u64(2)),
            c24: Fp2::from_u64(4),
        }
    }

    /// The projective coefficient pair `(A : C)`.
    ///
    /// From `A24plus = A + 2C`, `C24 = 4C`: `A = 4*A24plus - 2*C24` and
    /// `C = C24`, up to the common factor 4.
    pub fn a_proj(&self) -> (Fp2, Fp2) {
        let a = self.a24plus.double().double().sub(&self.c24.double());
        (a, self.c24)
    }

    /// The affine coefficient `A` (with `C` scaled to 1).  Costs an inversion.
    pub fn a_affine(&self) -> Fp2 {
        let (a, c) = self.a_proj();
        a.mul(&c.inv())
    }

    /// Are these the same curve — the same `A/C`, not merely the same
    /// projective representative of it?
    pub fn same_curve(&self, o: &Curve) -> bool {
        let (a1, c1) = self.a_proj();
        let (a2, c2) = o.a_proj();
        a1.mul(&c2) == a2.mul(&c1)
    }

    /// Rescale so that `C24 = 1`, i.e. store `a24 = (A + 2C)/(4C)`.
    /// One inversion buys one fewer multiplication in every later doubling,
    /// which pays for itself after a handful of steps — the reference
    /// implementation normalises whenever a chain of more than ~50 doublings
    /// is coming.
    pub fn normalised_a24(&self) -> Fp2 {
        self.a24plus.mul(&self.c24.inv())
    }

    /// The j-invariant, `j = 256 (A^2 - 3C^2)^3 / (C^4 (A^2 - 4C^2))`.
    ///
    /// This is the isomorphism invariant, so it is what an isogeny walk is
    /// ultimately compared on — and what makes the tests below able to check
    /// a 4-isogeny against two 2-isogenies without caring that the two
    /// formulas land on different (isomorphic) models.
    pub fn j_invariant(&self) -> Fp2 {
        let (a, c) = self.a_proj();
        let a2 = a.sqr();
        let c2 = c.sqr();
        let c4 = c2.sqr();
        let t = a2.sub(&c2.add(&c2).add(&c2)); // A^2 - 3C^2
        let num = t.sqr().mul(&t); // (A^2 - 3C^2)^3
        let den = c4.mul(&a2.sub(&c2.double().double())); // C^4 (A^2 - 4C^2)
                                                          // 256 * num / den
        let mut n = num;
        for _ in 0..8 {
            n = n.double();
        }
        n.mul(&den.inv())
    }

    /// Is `P` a point of `E` (rather than of its quadratic twist)?
    ///
    /// x-only coordinates do not by themselves distinguish the two: every
    /// `x in F_p^2` is the `x` of a point of `E` or of its twist.  The test
    /// is whether `x^3 + A x^2 + x` is a square in `F_p^2`.
    pub fn is_on_curve(&self, p: &PointX) -> bool {
        match p.affine_x() {
            None => true, // the point at infinity is on every model
            Some(x) => {
                let a = self.a_affine();
                let f = x.mul(&x.mul(&x.add(&a)).add(&Fp2::ONE)); // x(x(x+A)+1)
                f.is_square()
            }
        }
    }
}

/// `x(2P)` from `x(P)`, with the curve in `(A24plus : C24)` form.
///
/// ```text
/// t0 = (X+Z)^2 ; t1 = (X-Z)^2 ; t2 = t0 - t1 = 4XZ
/// X2 = C24 * t0 * t1
/// Z2 = t2 * (C24 * t1 + A24plus * t2)
/// ```
///
/// This is the standard Montgomery doubling, rearranged so that the only
/// curve constants appearing are `A24plus` and `C24` — which is why the curve
/// is stored that way.  Cost: 4M + 2S in `F_p^2`.
#[inline]
pub fn xdbl(p: &PointX, curve: &Curve) -> PointX {
    let t0 = p.x.add(&p.z).sqr();
    let t1 = p.x.sub(&p.z).sqr();
    let t2 = t0.sub(&t1);
    let t1 = t1.mul(&curve.c24);
    let x = t0.mul(&t1);
    let t0 = t2.mul(&curve.a24plus).add(&t1);
    let z = t0.mul(&t2);
    PointX { x, z }
}

/// `x(2P)` with a pre-normalised `a24 = (A + 2C)/(4C)`.  One multiplication
/// cheaper than [`xdbl`]: 3M + 2S.
#[inline]
pub fn xdbl_a24(p: &PointX, a24: &Fp2) -> PointX {
    let t0 = p.x.add(&p.z).sqr();
    let t1 = p.x.sub(&p.z).sqr();
    let t2 = t0.sub(&t1);
    let x = t0.mul(&t1);
    let t0 = t2.mul(a24).add(&t1);
    let z = t0.mul(&t2);
    PointX { x, z }
}

/// `x(2^e P)` by repeated doubling with a normalised `a24`.
#[inline]
pub fn xdbl_e(p: &PointX, e: usize, a24: &Fp2) -> PointX {
    let mut q = *p;
    for _ in 0..e {
        q = xdbl_a24(&q, a24);
    }
    q
}

/// Differential addition: `x(P+Q)` from `x(P)`, `x(Q)` and `x(P-Q)`.
///
/// ```text
/// X+ = Z_{P-Q} * ((X_P - Z_P)(X_Q + Z_Q) + (X_P + Z_P)(X_Q - Z_Q))^2
/// Z+ = X_{P-Q} * ((X_P - Z_P)(X_Q + Z_Q) - (X_P + Z_P)(X_Q - Z_Q))^2
/// ```
///
/// No curve constant appears at all — that is the point of *differential*
/// addition, and the reason the ladder can be written with one curve constant
/// touched only in the doubling half.  Cost: 4M + 2S.
#[inline]
pub fn xadd(p: &PointX, q: &PointX, pmq: &PointX) -> PointX {
    let t0 = p.x.add(&p.z);
    let t1 = p.x.sub(&p.z);
    let t2 = q.x.add(&q.z);
    let t3 = q.x.sub(&q.z);
    let t0 = t0.mul(&t3);
    let t1 = t1.mul(&t2);
    let t2 = t0.add(&t1);
    let t3 = t0.sub(&t1);
    PointX {
        x: pmq.z.mul(&t2.sqr()),
        z: pmq.x.mul(&t3.sqr()),
    }
}

/// Simultaneous `x(2P)` and `x(P+Q)`, sharing the `(X±Z)` sub-expressions.
///
/// Returns `(2P, P+Q)`.  `a24` must be normalised (`C24 = 1`).  Cost:
/// 6M + 4S, against 7M + 4S for a separate [`xdbl_a24`] and [`xadd`] — the
/// sharing is why the ladder uses this rather than two calls.
#[inline]
pub fn xdblad(p: &PointX, q: &PointX, pmq: &PointX, a24: &Fp2) -> (PointX, PointX) {
    let t0 = p.x.add(&p.z);
    let t1 = p.x.sub(&p.z);
    let mut rx = t0.sqr();
    let t2 = q.x.sub(&q.z);
    let mut sx = q.x.add(&q.z);
    let t0 = t0.mul(&t2);
    let mut rz = t1.sqr();
    let t1 = t1.mul(&sx);
    let t2 = rx.sub(&rz);
    rx = rx.mul(&rz);
    sx = a24.mul(&t2);
    let mut sz = t0.sub(&t1);
    rz = rz.add(&sx);
    sx = t0.add(&t1);
    rz = rz.mul(&t2);
    sz = sz.sqr();
    sx = sx.sqr();
    sz = sz.mul(&pmq.x);
    sx = sx.mul(&pmq.z);
    (PointX { x: rx, z: rz }, PointX { x: sx, z: sz })
}

/// The Montgomery ladder: `x([k]P)`.
///
/// Maintains the invariant `(R0, R1) = ([m]P, [m+1]P)`, whose *difference* is
/// always `P` — which is what lets every step be a [`xdblad`] with no
/// `y`-coordinate anywhere.  `nbits` is how many bits of `k` to read,
/// most-significant first; it must be at least the bit length of `k`.
///
/// `a24` is normalised, so the caller pays one inversion for the whole ladder
/// rather than one multiplication per step.
pub fn ladder(k: &[u64], nbits: usize, p: &PointX, a24: &Fp2) -> PointX {
    let mut r0 = PointX::INFINITY;
    let mut r1 = *p;
    let mut prevbit = 0u64;
    for i in (0..nbits).rev() {
        let bit = (k[i / 64] >> (i % 64)) & 1;
        PointX::cswap(&mut r0, &mut r1, bit ^ prevbit);
        prevbit = bit;
        let (a, b) = xdblad(&r0, &r1, p, a24);
        r0 = a;
        r1 = b;
    }
    PointX::cswap(&mut r0, &mut r1, prevbit);
    r0
}

/// [`ladder`] with the curve given in `(A24plus : C24)` form; normalises
/// `a24` first.
pub fn ladder_curve(k: &[u64], nbits: usize, p: &PointX, curve: &Curve) -> PointX {
    ladder(k, nbits, p, &curve.normalised_a24())
}

/// `x(2^e P)` with the curve in unnormalised `(A24plus : C24)` form.
///
/// Inside an isogeny chain the curve changes at every step, and an `F_p^2`
/// inversion costs about as much as 25 doublings, so normalising per step
/// would cost more than it saves.  The chain therefore pays the extra
/// multiplication per doubling and normalises nothing; only the ladder, which
/// runs 326 steps on one fixed curve, normalises.
#[inline]
pub fn xdbl_e_curve(p: &PointX, e: usize, curve: &Curve) -> PointX {
    let mut q = *p;
    for _ in 0..e {
        q = xdbl(&q, curve);
    }
    q
}

// ─── 2- and 4-isogenies ─────────────────────────────────────────────────────

/// The reusable part of a 2-isogeny: `(X2 + Z2, X2 - Z2)` for the kernel
/// generator.  Computed once per step, then applied to every pushed point.
#[derive(Clone, Copy, Debug)]
pub struct Kps2 {
    plus: Fp2,
    minus: Fp2,
}

/// The reusable part of a 4-isogeny: `(4 Z4^2, X4 - Z4, X4 + Z4)`.
#[derive(Clone, Copy, Debug)]
pub struct Kps4 {
    k0: Fp2,
    k1: Fp2,
    k2: Fp2,
}

/// Codomain of the 2-isogeny with kernel `{O, K}`, `K = (X2 : Z2)` of order 2.
///
/// Renes (*Computing isogenies between Montgomery curves*, PQCrypto 2018)
/// shows that for `E_A: y^2 = x^3 + A x^2 + x` and a 2-torsion point
/// `(x0, 0)` with `x0 != 0`, the codomain is `E_{A'}` with
/// `A' = 2(1 - 2 x0^2)`, and the x-map is
/// `x |-> x (x x0 - 1)/(x - x0)`.
///
/// In `(A24plus : C24)` form that is `(Z2^2 - X2^2 : Z2^2)`: expanding,
/// `A/C = (4 A24plus - 2 C24)/C24 = 2 - 4 x0^2`, which is Renes' `A'`.
/// Cost: 2S.
///
/// Returns `None` for `X2 = 0`, the kernel `{O, (0,0)}`.  That isogeny is the
/// one Montgomery-form case that needs a square root to name its codomain, so
/// every x-only implementation (this one, SIKE's, the SQIsign reference's)
/// excludes it and arranges its chains not to hit it.
pub fn isog2_codomain(k: &PointX) -> Option<(Curve, Kps2)> {
    if k.x.is_zero() {
        return None;
    }
    let x2 = k.x.sqr();
    let z2 = k.z.sqr();
    let curve = Curve {
        a24plus: z2.sub(&x2),
        c24: z2,
    };
    Some((
        curve,
        Kps2 {
            plus: k.x.add(&k.z),
            minus: k.x.sub(&k.z),
        },
    ))
}

/// Push a point through the 2-isogeny described by `kps`.
///
/// ```text
/// t2 = (X2+Z2)(XQ-ZQ) ;  t3 = (X2-Z2)(XQ+ZQ)
/// X' = XQ (t2 + t3) ;    Z' = ZQ (t2 - t3)
/// ```
///
/// which is `x (x x0 - 1)/(x - x0)` cleared of denominators.  Cost: 4M.
/// The kernel generator itself maps to `(* : 0)`, the point at infinity,
/// because `t2 = t3` there.
#[inline]
pub fn isog2_eval(q: &PointX, kps: &Kps2) -> PointX {
    let t0 = q.x.add(&q.z);
    let t1 = q.x.sub(&q.z);
    let t2 = kps.plus.mul(&t1);
    let t3 = kps.minus.mul(&t0);
    PointX {
        x: q.x.mul(&t2.add(&t3)),
        z: q.z.mul(&t2.sub(&t3)),
    }
}

/// Codomain of the 4-isogeny with kernel `<K>`, `K = (X4 : Z4)` of order 4.
///
/// ```text
/// A24plus = Z4^4 - X4^4 ;   C24 = Z4^4
/// ```
///
/// These are the formulas of the SQIsign reference implementation
/// (`iso_xisog_4` in `src/ec/ref/lvlx/isog.c`), which are the
/// Costello–Longa–Naehrig 4-isogeny composed with the isomorphism
/// `x |-> -x`.  The sign convention only changes *which* model of the
/// codomain you land on; it is matched by [`isog4_eval`], and the tests below
/// pin the pair down by checking the j-invariant against two composed
/// 2-isogenies, which is convention-free.
///
/// Cost: 3S + 1M.
///
/// **Precondition**: `[2]K != (0,0)`.  Use [`isog4_kernel_ok`] to check.
/// Taking a degree-4 step instead of two degree-2 steps is what halves the
/// number of codomain computations in a `2^e` chain, and is the reason every
/// production SIDH-family implementation walks in 4s.
pub fn isog4_codomain(k: &PointX) -> (Curve, Kps4) {
    let t1 = k.x.sqr();
    let t2 = k.z.sqr();
    let t3 = t2.add(&t1);
    let t4 = t2.sub(&t1);
    let curve = Curve {
        a24plus: t3.mul(&t4),
        c24: t2.sqr(),
    };
    let kps = Kps4 {
        k0: t2.double().double(),
        k1: k.x.sub(&k.z),
        k2: k.x.add(&k.z),
    };
    (curve, kps)
}

/// Is `K` a legal kernel generator for [`isog4_codomain`]?  Checks that
/// `[2]K` is not the 2-torsion point `(0,0)` and that `K` really has order 4.
pub fn isog4_kernel_ok(k: &PointX, curve: &Curve) -> bool {
    let d = xdbl(k, curve);
    if d.is_infinity() || d.x.is_zero() {
        return false;
    }
    xdbl(&d, curve).is_infinity()
}

/// Push a point through the 4-isogeny described by `kps`.  Cost: 6M + 2S.
///
/// The `2S` come from the two squarings of `X' ± Z'` after the first pair of
/// multiplications; writing it this way rather than as two composed 2-isogeny
/// evaluations (which would be 8M) is where the degree-4 step pays off on the
/// evaluation side as well as the codomain side.
#[inline]
pub fn isog4_eval(q: &PointX, kps: &Kps4) -> PointX {
    let t0 = q.x.add(&q.z);
    let t1 = q.x.sub(&q.z);
    let mut rx = t0.mul(&kps.k1);
    let mut rz = t1.mul(&kps.k2);
    let t0 = t0.mul(&t1).mul(&kps.k0);
    let t1 = rx.add(&rz);
    rz = rx.sub(&rz);
    let t1 = t1.sqr();
    rz = rz.sqr();
    rx = t0.add(&t1);
    let t0 = t0.sub(&rz);
    PointX {
        x: rx.mul(&t1),
        z: rz.mul(&t0),
    }
}

// ─── chains ─────────────────────────────────────────────────────────────────

/// An optimal strategy for a chain of `n` steps, as a flat list of `n-1`
/// jump sizes read left to right by [`chain_4_strategy`].
///
/// The problem (de Feo–Jao–Plût, *Towards quantum-resistant cryptosystems from
/// supersingular elliptic curve isogenies*, §4.2): a chain of `n` isogeny
/// steps is a triangle of `n(n+1)/2` lattice points; you may move right by one
/// with a point multiplication (cost `cost_dbl`) or down-left with an isogeny
/// evaluation (cost `cost_eval`), and you must visit the whole hypotenuse.
/// A strategy splits the triangle at some `b`, paying `b` multiplications to
/// reach a sub-triangle of height `n-b` and `n-b` evaluations to reach one of
/// height `b`.  The recurrence
///
/// ```text
/// C(n) = min_{0<b<n} ( C(n-b) + C(b) + b*cost_dbl + (n-b)*cost_eval )
/// ```
///
/// is an `O(n^2)` dynamic program, run here at chain-construction time.
///
/// Why bother: the naive chain (walk to the end, step, walk to the end again)
/// costs `Theta(n^2)` multiplications; an optimal strategy costs
/// `Theta(n log n)`.  At `n = 162` — the level-1 chain, `2^324 = 4^162` — that
/// is the difference between ~13000 and ~1300 doublings.
///
/// `cost_dbl` is the cost of *one step's worth* of doubling, i.e. two
/// `xDBL`s for a 4-isogeny chain; `cost_eval` the cost of one
/// [`isog4_eval`].  Only their ratio matters.
pub fn optimal_strategy(n: usize, cost_dbl: u64, cost_eval: u64) -> Vec<usize> {
    if n <= 1 {
        return Vec::new();
    }
    let mut cost = vec![0u64; n + 1];
    let mut split = vec![0usize; n + 1];
    for i in 2..=n {
        let mut best = u64::MAX;
        let mut best_b = 1;
        for b in 1..i {
            let c = cost[i - b]
                .saturating_add(cost[b])
                .saturating_add((b as u64) * cost_dbl)
                .saturating_add(((i - b) as u64) * cost_eval);
            if c < best {
                best = c;
                best_b = b;
            }
        }
        cost[i] = best;
        split[i] = best_b;
    }
    let mut out = Vec::with_capacity(n - 1);
    // Pre-order flattening: the jump taken at the root, then the left
    // sub-triangle, then the right one — the order the walker consumes them.
    fn flatten(n: usize, split: &[usize], out: &mut Vec<usize>) {
        if n <= 1 {
            return;
        }
        let b = split[n];
        out.push(b);
        flatten(n - b, split, out);
        flatten(b, split, out);
    }
    flatten(n, &split, &mut out);
    debug_assert_eq!(out.len(), n - 1);
    out
}

/// The default strategy costs for this field, in units of `F_p`
/// multiplications: one chain step's doubling is two [`xdbl`]s
/// (`2 * (4M + 2S)` in `F_p^2` = `2 * (4*3 + 2*2) = 32`), and one
/// [`isog4_eval`] is `6M + 2S = 22`.
pub const COST_DBL: u64 = 32;
/// See [`COST_DBL`].
pub const COST_EVAL: u64 = 22;

/// A chain of `n` 4-isogenies with kernel `<K>`, `K` of order `4^n`, walked
/// with the given strategy.  Points in `push` are carried along.
///
/// Returns the codomain curve, or `None` if a step hits the excluded
/// `[2]K = (0,0)` kernel (checked at the first step, as the reference
/// implementation does; a cyclic kernel cannot then produce one later,
/// because that would be the chain backtracking).
pub fn chain_4_strategy(
    curve: &Curve,
    kernel: &PointX,
    n: usize,
    push: &mut [PointX],
    strategy: &[usize],
) -> Option<Curve> {
    if n == 0 {
        return Some(*curve);
    }
    assert_eq!(strategy.len(), n - 1, "strategy length must be n-1");
    let mut cur = *curve;
    let mut r = *kernel;
    // Stack of deferred kernel points, with how far along the chain each sits.
    let mut pts: Vec<(PointX, usize)> = Vec::with_capacity(2 * (usize::BITS as usize));
    let mut index = 0usize;
    let mut si = 0usize;
    let mut first = true;

    for row in 1..n {
        while index < n - row {
            pts.push((r, index));
            let m = strategy[si];
            si += 1;
            r = xdbl_e_curve(&r, 2 * m, &cur);
            index += m;
        }
        if first {
            if !isog4_kernel_ok(&r, &cur) {
                return None;
            }
            first = false;
        }
        let (nc, kps) = isog4_codomain(&r);
        cur = nc;
        for (p, _) in pts.iter_mut() {
            *p = isog4_eval(p, &kps);
        }
        for p in push.iter_mut() {
            *p = isog4_eval(p, &kps);
        }
        let (nr, ni) = pts.pop().expect("strategy underflow");
        r = nr;
        index = ni;
    }
    if first && !isog4_kernel_ok(&r, &cur) {
        return None;
    }
    let (nc, kps) = isog4_codomain(&r);
    for p in push.iter_mut() {
        *p = isog4_eval(p, &kps);
    }
    Some(nc)
}

/// The same chain walked naively: re-derive the order-4 kernel point from the
/// top of the chain at every step.
///
/// Kept for two reasons: it is the obviously-correct version the strategy
/// walker is tested against, and it is the `Theta(n^2)` baseline the
/// benchmark compares the strategy walker to.
pub fn chain_4_naive(
    curve: &Curve,
    kernel: &PointX,
    n: usize,
    push: &mut [PointX],
) -> Option<Curve> {
    let mut cur = *curve;
    let mut t = *kernel;
    for i in 0..n {
        let k = xdbl_e_curve(&t, 2 * (n - 1 - i), &cur);
        if i == 0 && !isog4_kernel_ok(&k, &cur) {
            return None;
        }
        let (nc, kps) = isog4_codomain(&k);
        cur = nc;
        t = isog4_eval(&t, &kps);
        for p in push.iter_mut() {
            *p = isog4_eval(p, &kps);
        }
    }
    Some(cur)
}

/// A chain of 2-isogenies of total degree `2^e` with cyclic kernel
/// `<kernel>`, walked with an optimal strategy.
///
/// **Precondition**: `kernel` has order *exactly* `2^e`.  The walker derives
/// every step's order-4 point by doubling down from the top of the chain, so
/// a kernel of larger order silently produces steps whose kernel generator
/// has the wrong order and a meaningless result.
///
/// Odd `e` is handled by taking the single degree-2 step first, so that what
/// remains is an even-length chain of degree-4 steps.
///
/// `push` is evaluated along the whole chain.  Returns `None` on the excluded
/// kernel cases.
pub fn two_isogeny_chain(
    curve: &Curve,
    kernel: &PointX,
    e: usize,
    push: &mut [PointX],
) -> Option<Curve> {
    let n = e / 2;
    let strategy = optimal_strategy(n, COST_DBL, COST_EVAL);
    two_isogeny_chain_with_strategy(curve, kernel, e, push, &strategy)
}

/// [`two_isogeny_chain`] with a caller-supplied strategy for the `e/2`
/// degree-4 steps, so a repeated chain does not redo the `O(n^2)` dynamic
/// program.
pub fn two_isogeny_chain_with_strategy(
    curve: &Curve,
    kernel: &PointX,
    e: usize,
    push: &mut [PointX],
    strategy: &[usize],
) -> Option<Curve> {
    let mut cur = *curve;
    let mut ker = *kernel;
    let mut e = e;
    if e % 2 == 1 {
        // Peel off one degree-2 step from the *bottom* of the kernel, leaving
        // an even-degree chain behind.
        let k2 = xdbl_e_curve(&ker, e - 1, &cur);
        let (nc, kps) = isog2_codomain(&k2)?;
        ker = isog2_eval(&ker, &kps);
        for p in push.iter_mut() {
            *p = isog2_eval(p, &kps);
        }
        cur = nc;
        e -= 1;
    }
    chain_4_strategy(&cur, &ker, e / 2, push, strategy)
}

// ─── tests ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use num_bigint::BigUint;
    use num_traits::One;

    // ── seeded randomness ───────────────────────────────────────────────────

    /// SplitMix64.  A seeded generator so a failure is reproducible; there is
    /// nothing cryptographic about these tests' randomness.
    struct Rng(u64);

    impl Rng {
        fn new(seed: u64) -> Rng {
            Rng(seed)
        }
        fn next_u64(&mut self) -> u64 {
            self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
            let mut z = self.0;
            z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
            z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
            z ^ (z >> 31)
        }
        /// Uniform-ish element of `F_p`, by rejection on the top limb.
        fn fp(&mut self) -> Fp {
            loop {
                let mut l = [0u64; NLIMBS];
                for i in 0..NLIMBS {
                    l[i] = self.next_u64();
                }
                l[NLIMBS - 1] &= 0x3F; // p's top limb is 0x2f; accept ~73%
                if lt_p(&l) {
                    return Fp::from_canonical(l);
                }
            }
        }
        fn fp2(&mut self) -> Fp2 {
            Fp2 {
                re: self.fp(),
                im: self.fp(),
            }
        }
    }

    // ── the slow, obviously-correct reference ───────────────────────────────
    //
    // Everything below is schoolbook `num-bigint` modular arithmetic: no
    // Montgomery form, no limb tricks, no shared code with the
    // implementation.  If the fast path and this path agree on thousands of
    // random inputs, the fast path's limb plumbing is right.

    fn p_big() -> BigUint {
        limbs_to_big(&P)
    }

    fn limbs_to_big(l: &[u64; NLIMBS]) -> BigUint {
        let mut bytes = Vec::with_capacity(8 * NLIMBS);
        for x in l {
            bytes.extend_from_slice(&x.to_le_bytes());
        }
        BigUint::from_bytes_le(&bytes)
    }

    fn big_to_limbs(x: &BigUint) -> [u64; NLIMBS] {
        let mut b = x.to_bytes_le();
        assert!(b.len() <= 8 * NLIMBS);
        b.resize(8 * NLIMBS, 0);
        let mut l = [0u64; NLIMBS];
        for i in 0..NLIMBS {
            l[i] = u64::from_le_bytes(b[8 * i..8 * i + 8].try_into().unwrap());
        }
        l
    }

    fn to_big(a: &Fp) -> BigUint {
        limbs_to_big(&a.to_canonical())
    }

    fn from_big(x: &BigUint) -> Fp {
        Fp::from_canonical(big_to_limbs(&(x % p_big())))
    }

    /// `F_p^2` as a plain pair of `BigUint`s, multiplied schoolbook (four
    /// products, not Karatsuba) so the reference shares nothing with the
    /// implementation's three-multiplication path.
    #[derive(Clone, PartialEq, Eq, Debug)]
    struct Big2(BigUint, BigUint);

    impl Big2 {
        fn of(a: &Fp2) -> Big2 {
            Big2(to_big(&a.re), to_big(&a.im))
        }
        fn add(&self, o: &Big2) -> Big2 {
            let p = p_big();
            Big2((&self.0 + &o.0) % &p, (&self.1 + &o.1) % &p)
        }
        fn sub(&self, o: &Big2) -> Big2 {
            let p = p_big();
            Big2((&self.0 + &p - &o.0) % &p, (&self.1 + &p - &o.1) % &p)
        }
        fn mul(&self, o: &Big2) -> Big2 {
            // (a0 + a1 i)(b0 + b1 i) = (a0 b0 - a1 b1) + (a0 b1 + a1 b0) i
            let p = p_big();
            let a0b0 = (&self.0 * &o.0) % &p;
            let a1b1 = (&self.1 * &o.1) % &p;
            let a0b1 = (&self.0 * &o.1) % &p;
            let a1b0 = (&self.1 * &o.0) % &p;
            Big2((&a0b0 + &p - &a1b1) % &p, (&a0b1 + &a1b0) % &p)
        }
    }

    // ── constants ───────────────────────────────────────────────────────────

    #[test]
    fn prime_constants_are_what_the_docs_claim() {
        let p = p_big();
        // p = 3 * 2^324 - 1, the SQIsign NIST level-1 prime.
        let expect = (BigUint::from(3u32) << 324u32) - BigUint::one();
        assert_eq!(p, expect);
        assert_eq!(p.bits(), P_BITS as u64);
        // p = 48 * 2^320 - 1, the form the reduction exploits.
        assert_eq!(p, (BigUint::from(48u32) << 320u32) - BigUint::one());
        // p ≡ 3 (mod 4), so x^2 + 1 is irreducible.
        assert_eq!(&p % 4u32, BigUint::from(3u32));
        // p' = -p^-1 mod 2^64 == 1, which is what lets `mont_mul` skip a
        // multiplication per round.  p ≡ -1 (mod 2^64), so p^-1 ≡ -1 and
        // p' = 1; checking the congruence is the whole argument.
        let r64 = BigUint::one() << 64u32;
        assert_eq!(&p % &r64, &r64 - BigUint::one(), "p is not -1 mod 2^64");
        assert_eq!(
            (&p * (&r64 - BigUint::one())) % &r64,
            BigUint::one(),
            "p * -1 != 1"
        );
        // R and R^2.
        let r = BigUint::one() << (64 * NLIMBS as u32);
        assert_eq!(limbs_to_big(&R_MOD_P), &r % &p);
        assert_eq!(limbs_to_big(&R2_MOD_P), (&r * &r) % &p);
        assert_eq!(limbs_to_big(&P_PLUS_1), &p + BigUint::one());
        assert_eq!(
            limbs_to_big(&P_PLUS_1),
            BigUint::from(3u32) << TWO_TORSION_POWER as u32
        );
    }

    // ── F_p against num-bigint ──────────────────────────────────────────────

    #[test]
    fn fp_differential_against_bigint() {
        let p = p_big();
        let mut rng = Rng::new(0xF00D_1234_5678_9ABC);
        for _ in 0..4000 {
            let a = rng.fp();
            let b = rng.fp();
            let (ab, bb) = (to_big(&a), to_big(&b));

            assert_eq!(to_big(&a.add(&b)), (&ab + &bb) % &p, "add");
            assert_eq!(to_big(&a.sub(&b)), (&ab + &p - &bb) % &p, "sub");
            assert_eq!(to_big(&a.neg()), (&p - &ab) % &p, "neg");
            assert_eq!(to_big(&a.double()), (&ab + &ab) % &p, "double");
            assert_eq!(to_big(&a.mul(&b)), (&ab * &bb) % &p, "mul");
            assert_eq!(to_big(&a.sqr()), (&ab * &ab) % &p, "sqr");
            // round-trip through Montgomery form
            assert_eq!(from_big(&ab), a, "to/from canonical");
        }
    }

    #[test]
    fn fp_inverse_and_pow_against_bigint() {
        let p = p_big();
        let two = BigUint::from(2u32);
        let mut rng = Rng::new(0x0BAD_C0DE_1111_2222);
        // `modpow` on 326-bit numbers is slow; a few hundred is plenty to
        // catch a wrong addition chain, and the axiom test below runs the
        // inverse thousands of times.
        for _ in 0..400 {
            let a = rng.fp();
            if a.is_zero() {
                continue;
            }
            let ab = to_big(&a);
            assert_eq!(to_big(&a.inv()), ab.modpow(&(&p - &two), &p), "inv");
            let e = [rng.next_u64(), rng.next_u64()];
            let eb = limbs_to_big(&[e[0], e[1], 0, 0, 0, 0]);
            assert_eq!(to_big(&a.pow(&e)), ab.modpow(&eb, &p), "pow");
        }
    }

    #[test]
    fn fp_field_axioms() {
        let mut rng = Rng::new(0x5EED_0000_0000_0001);
        for _ in 0..3000 {
            let a = rng.fp();
            let b = rng.fp();
            let c = rng.fp();
            assert_eq!(a.add(&b).add(&c), a.add(&b.add(&c)), "add assoc");
            assert_eq!(a.mul(&b).mul(&c), a.mul(&b.mul(&c)), "mul assoc");
            assert_eq!(a.mul(&b.add(&c)), a.mul(&b).add(&a.mul(&c)), "distrib");
            assert_eq!(a.add(&b), b.add(&a), "add comm");
            assert_eq!(a.mul(&b), b.mul(&a), "mul comm");
            assert!(a.sub(&a).is_zero(), "a - a == 0");
            assert_eq!(a.add(&a.neg()), Fp::ZERO, "a + (-a) == 0");
            assert_eq!(a.mul(&Fp::ONE), a, "a * 1 == a");
            assert_eq!(a.add(&Fp::ZERO), a, "a + 0 == a");
            if !a.is_zero() {
                assert_eq!(a.mul(&a.inv()), Fp::ONE, "a * a^-1 == 1");
            }
        }
    }

    #[test]
    fn fp_legendre_and_sqrt() {
        let mut rng = Rng::new(0xA11C_E000_0000_0002);
        let mut nonsquares = 0;
        for _ in 0..300 {
            let a = rng.fp();
            let s = a.sqr();
            assert!(s.is_square(), "a^2 is a square");
            let r = s.sqrt().expect("sqrt of a square exists");
            assert!(r == a || r == a.neg(), "sqrt(a^2) == ±a");
            if !a.is_square() {
                nonsquares += 1;
                assert!(a.sqrt().is_none(), "non-squares have no root");
            }
        }
        // Half of F_p* is non-square; seeing none would mean the criterion is
        // broken in the direction the assertions above cannot see.
        assert!(
            nonsquares > 100,
            "suspiciously few non-squares: {nonsquares}"
        );
    }

    // ── F_p^2 against num-bigint ────────────────────────────────────────────

    #[test]
    fn fp2_differential_against_bigint() {
        let mut rng = Rng::new(0xDEAD_BEEF_CAFE_0001);
        for _ in 0..4000 {
            let a = rng.fp2();
            let b = rng.fp2();
            let (ab, bb) = (Big2::of(&a), Big2::of(&b));
            assert_eq!(Big2::of(&a.add(&b)), ab.add(&bb), "fp2 add");
            assert_eq!(Big2::of(&a.sub(&b)), ab.sub(&bb), "fp2 sub");
            // Karatsuba (3M) against schoolbook (4M).
            assert_eq!(Big2::of(&a.mul(&b)), ab.mul(&bb), "fp2 mul (karatsuba)");
            assert_eq!(Big2::of(&a.sqr()), ab.mul(&ab), "fp2 sqr");
            assert_eq!(a.sqr(), a.mul(&a), "fp2 sqr vs mul");
            assert_eq!(
                to_big(&a.norm()),
                (&ab.0 * &ab.0 + &ab.1 * &ab.1) % p_big(),
                "fp2 norm"
            );
        }
    }

    #[test]
    fn fp2_field_axioms() {
        let mut rng = Rng::new(0x5EED_0000_0000_0003);
        for _ in 0..3000 {
            let a = rng.fp2();
            let b = rng.fp2();
            let c = rng.fp2();
            assert_eq!(a.add(&b).add(&c), a.add(&b.add(&c)), "add assoc");
            assert_eq!(a.mul(&b).mul(&c), a.mul(&b.mul(&c)), "mul assoc");
            assert_eq!(a.mul(&b.add(&c)), a.mul(&b).add(&a.mul(&c)), "distrib");
            assert!(a.sub(&a).is_zero(), "a - a == 0");
            assert_eq!(a.mul(&Fp2::ONE), a, "a * 1 == a");
            if !a.is_zero() {
                assert_eq!(a.mul(&a.inv()), Fp2::ONE, "a * a^-1 == 1");
            }
            // i^2 == -1, the defining relation of the basis.
            let i = Fp2 {
                re: Fp::ZERO,
                im: Fp::ONE,
            };
            assert_eq!(i.sqr(), Fp2::ONE.neg(), "i^2 == -1");
        }
    }

    #[test]
    fn fp2_sqrt_and_squareness() {
        let mut rng = Rng::new(0xA11C_E000_0000_0004);
        let mut nonsquares = 0;
        for _ in 0..200 {
            let a = rng.fp2();
            let s = a.sqr();
            assert!(s.is_square(), "a^2 is a square in F_p^2");
            let r = s.sqrt().expect("sqrt of a square exists");
            assert_eq!(r.sqr(), s, "sqrt is a root");
            assert!(r == a || r == a.neg(), "sqrt(a^2) == ±a");
            if !a.is_square() {
                nonsquares += 1;
                assert!(a.sqrt().is_none(), "non-squares have no root");
            }
        }
        assert!(
            nonsquares > 60,
            "suspiciously few non-squares: {nonsquares}"
        );
    }

    // ── curve arithmetic ────────────────────────────────────────────────────

    /// The test curve: `E_6: y^2 = x^3 + 6x^2 + x` over `F_p^2`.
    ///
    /// `E_0: y^2 = x^3 + x` is supersingular for every `p ≡ 3 (mod 4)`, and
    /// `E_6` is 2-isogenous to it, so `E_6` is supersingular too.  `A = 6` is
    /// preferred over `A = 0` only because `(0,0)` is then not the point the
    /// chains want to avoid.  Being supersingular and defined over `F_p` with
    /// trace 0, `#E_6(F_p^2) = (p+1)^2 = (3 * 2^324)^2`, which is what the
    /// order assertions below rely on — and which
    /// `supersingular_group_order` checks rather than assumes.
    fn test_curve() -> Curve {
        Curve::from_a(Fp2::from_u64(6))
    }

    /// A random point of `E` (not of its quadratic twist).
    fn random_point(rng: &mut Rng, curve: &Curve) -> PointX {
        loop {
            let p = PointX::from_affine(rng.fp2());
            if curve.is_on_curve(&p) && !p.is_infinity() {
                return p;
            }
        }
    }

    /// `[k]P` for small `k`, by the differential chain
    /// `[n+1]P = xADD([n]P, P, [n-1]P)` — no ladder, no scalar recoding, so
    /// it shares nothing with the thing under test but `xadd`/`xdbl`.
    fn small_multiple(k: u64, p: &PointX, curve: &Curve) -> PointX {
        if k == 0 {
            return PointX::INFINITY;
        }
        if k == 1 {
            return *p;
        }
        let mut prev = *p; // [1]P
        let mut cur = xdbl(p, curve); // [2]P
        for _ in 2..k {
            let next = xadd(&cur, p, &prev);
            prev = cur;
            cur = next;
        }
        cur
    }

    #[test]
    fn ladder_matches_repeated_addition() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0x1234_5678_9ABC_DEF0);
        for _ in 0..8 {
            let p = random_point(&mut rng, &curve);
            for k in 1u64..60 {
                let by_ladder = ladder(&[k], 64, &p, &a24);
                let by_addition = small_multiple(k, &p, &curve);
                assert!(
                    by_ladder.same_x(&by_addition),
                    "ladder disagrees with repeated addition at k={k}"
                );
            }
        }
    }

    #[test]
    fn ladder_is_multiplicative() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0x0FED_CBA9_8765_4321);
        for _ in 0..12 {
            let p = random_point(&mut rng, &curve);
            let a = rng.next_u64() >> 1;
            let b = rng.next_u64() >> 1;
            // [a]([b]P) == [ab]P
            let ab = (a as u128) * (b as u128);
            let ab_limbs = [ab as u64, (ab >> 64) as u64];
            let lhs = ladder(&[a], 64, &ladder(&[b], 64, &p, &a24), &a24);
            let rhs = ladder(&ab_limbs, 128, &p, &a24);
            assert!(lhs.same_x(&rhs), "[a]([b]P) != [ab]P");
            // [1]P == P, [0]P == O
            assert!(ladder(&[1], 64, &p, &a24).same_x(&p));
            assert!(ladder(&[0], 64, &p, &a24).is_infinity());
        }
    }

    #[test]
    fn points_stay_on_the_curve_under_doubling() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0xC0FF_EE00_0000_0001);
        for _ in 0..8 {
            let mut p = random_point(&mut rng, &curve);
            for i in 0..20 {
                p = xdbl_a24(&p, &a24);
                assert!(!p.is_infinity(), "point died after {i} doublings");
                assert!(curve.is_on_curve(&p), "left the curve after {i} doublings");
            }
            // xdbl and xdbl_a24 must agree.
            let q = random_point(&mut rng, &curve);
            assert!(xdbl(&q, &curve).same_x(&xdbl_a24(&q, &a24)));
        }
    }

    #[test]
    fn supersingular_group_order() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0xBEEF_0000_0000_0005);
        let mut full_order = 0;
        for _ in 0..6 {
            let p = random_point(&mut rng, &curve);
            // #E(F_p^2) = (p+1)^2 and the group is (Z/(p+1))^2, so p+1 kills
            // everything.  This is the assertion that the curve really is
            // supersingular and that the full 2^324 torsion is rational.
            let q = ladder(&P_PLUS_1, P_PLUS_1_BITS, &p, &a24);
            assert!(q.is_infinity(), "[p+1]P is not the identity");
            // A random point has full order p+1 with probability 3/4 (its
            // 2-part is uniform in Z/2^324), so this is counted, not asserted
            // pointwise: seeing none at all would mean p+1 is not the exponent
            // but some proper divisor of it.
            let half = [0u64, 0, 0, 0, 0, 0x18]; // (p+1)/2 = 3*2^323
            if !ladder(&half, P_PLUS_1_BITS, &p, &a24).is_infinity() {
                full_order += 1;
            }
        }
        assert!(full_order > 0, "no point of full order p+1 in 6 tries");
    }

    /// A point of exact order `2^324` whose bottom 2-torsion point is not
    /// `(0,0)`.
    ///
    /// Kill the factor 3, then reject two cases: order a proper divisor of
    /// `2^324`, and `[2^323]Q = (0,0)`.  The second is the kernel every x-only
    /// Montgomery isogeny formula excludes (see [`isog2_codomain`]); a random
    /// point hits it about a third of the time, since all three 2-torsion
    /// points are reachable, so it has to be rejected rather than assumed
    /// away.
    fn full_order_two_point(rng: &mut Rng, curve: &Curve, a24: &Fp2) -> PointX {
        loop {
            let p = random_point(rng, curve);
            let q = ladder(&[3], 8, &p, a24);
            if q.is_infinity() {
                continue;
            }
            let bottom = xdbl_e(&q, TWO_TORSION_POWER - 1, a24);
            if bottom.is_infinity() {
                continue; // order is a proper divisor of 2^324
            }
            if bottom.x.is_zero() {
                continue; // the excluded kernel (0,0)
            }
            assert!(xdbl_e(&q, TWO_TORSION_POWER, a24).is_infinity());
            return q;
        }
    }

    /// A point of exact order 3: `[2^324]P` for a random `P`.  `E(F_p^2)`'s
    /// 3-part is `(Z/3)^2`, so one draw in nine lands on the identity and the
    /// draw has to be repeated.
    fn order_three_point(rng: &mut Rng, curve: &Curve, a24: &Fp2) -> PointX {
        let two_324 = [0u64, 0, 0, 0, 0, 1u64 << (TWO_TORSION_POWER - 320)];
        loop {
            let p = random_point(rng, curve);
            let r = ladder(&two_324, 326, &p, a24);
            if r.is_infinity() {
                continue;
            }
            assert!(ladder(&[3], 8, &r, a24).is_infinity(), "order should be 3");
            return r;
        }
    }

    // ── isogenies ───────────────────────────────────────────────────────────

    /// The classical modular polynomial of level 2.  `Phi_2(j(E), j(E')) = 0`
    /// exactly when `E` and `E'` are 2-isogenous, so this is an entirely
    /// independent check on the 2-isogeny codomain formula — it knows nothing
    /// about Montgomery models or `(A24plus : C24)`.
    ///
    /// The coefficients were checked against four classical 2-isogenous
    /// pairs before being written here: `Phi_2(1728, 287496) = 0`,
    /// `Phi_2(0, 54000) = 0`, and the two CM fixed points
    /// `Phi_2(1728, 1728) = Phi_2(8000, 8000) = 0`.
    fn phi2(x: &Fp2, y: &Fp2) -> Fp2 {
        let c = Fp2::from_u64;
        let x2 = x.sqr();
        let y2 = y.sqr();
        let mut acc = x2.mul(x).add(&y2.mul(y)); // X^3 + Y^3
        acc = acc.sub(&x2.mul(&y2)); // - X^2 Y^2
        acc = acc.add(&c(1488).mul(&x2.mul(y).add(&x.mul(&y2)))); // +1488(X^2Y+XY^2)
        acc = acc.sub(&c(162_000).mul(&x2.add(&y2))); // -162000(X^2+Y^2)
        acc = acc.add(&c(40_773_375).mul(&x.mul(y))); // +40773375 XY
        acc = acc.add(&c(8_748_000_000).mul(&x.add(y))); // +8748000000(X+Y)
        acc.sub(&c(157_464_000_000_000)) // -157464000000000
    }

    #[test]
    fn modular_polynomial_recognises_known_pairs() {
        // A guard on the test's own constants, in the field the other tests
        // use, so a typo cannot silently make `phi2` vacuous.
        assert!(phi2(&Fp2::from_u64(1728), &Fp2::from_u64(287_496)).is_zero());
        assert!(phi2(&Fp2::from_u64(0), &Fp2::from_u64(54_000)).is_zero());
        assert!(phi2(&Fp2::from_u64(1728), &Fp2::from_u64(1728)).is_zero());
        assert!(!phi2(&Fp2::from_u64(1728), &Fp2::from_u64(5)).is_zero());
    }

    #[test]
    fn two_isogeny_is_a_two_isogeny() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0x2222_0000_0000_0001);
        for _ in 0..6 {
            let t = full_order_two_point(&mut rng, &curve, &a24);
            // the order-2 point under t
            let k = xdbl_e(&t, TWO_TORSION_POWER - 1, &a24);
            assert!(!k.is_infinity());
            assert!(xdbl_a24(&k, &a24).is_infinity(), "k must have order 2");

            let (img, kps) = isog2_codomain(&k).expect("generic kernel");

            // (1) the codomain really is 2-isogenous: modular polynomial.
            assert!(
                phi2(&curve.j_invariant(), &img.j_invariant()).is_zero(),
                "Phi_2(j, j') != 0: the 2-isogeny codomain formula is wrong"
            );

            // (2) the kernel maps to the identity.
            assert!(isog2_eval(&k, &kps).is_infinity(), "kernel not killed");

            // (3) images land on the codomain, and (4) the image of a point
            // of order 2^324 has order 2^323 (degree-2 kernel, cyclic).
            let ti = isog2_eval(&t, &kps);
            assert!(img.is_on_curve(&ti), "image is not on the codomain");
            let a24i = img.normalised_a24();
            assert!(xdbl_e(&ti, TWO_TORSION_POWER - 1, &a24i).is_infinity());
            assert!(!xdbl_e(&ti, TWO_TORSION_POWER - 2, &a24i).is_infinity());

            // (5) a point of order 3 keeps order exactly 3: 3 is coprime to
            // the isogeny degree, so the map is injective on the 3-torsion.
            let r3 = order_three_point(&mut rng, &curve, &a24);
            let r3i = isog2_eval(&r3, &kps);
            assert!(!r3i.is_infinity(), "order-3 point killed by a 2-isogeny");
            assert!(
                ladder(&[3], 8, &r3i, &a24i).is_infinity(),
                "order 3 not preserved"
            );
        }
    }

    #[test]
    fn four_isogeny_equals_two_two_isogenies() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0x4444_0000_0000_0001);
        for _ in 0..6 {
            let t = full_order_two_point(&mut rng, &curve, &a24);
            // an order-4 point
            let k4 = xdbl_e(&t, TWO_TORSION_POWER - 2, &a24);
            assert!(isog4_kernel_ok(&k4, &curve), "kernel should be generic");

            // degree-4 in one step
            let (img4, kps4) = isog4_codomain(&k4);
            let t4 = isog4_eval(&t, &kps4);

            // the same thing as two degree-2 steps
            let k2 = xdbl_a24(&k4, &a24);
            let (mid, kpsa) = isog2_codomain(&k2).expect("generic");
            let k4b = isog2_eval(&k4, &kpsa);
            let tb = isog2_eval(&t, &kpsa);
            let (img2, kpsb) = isog2_codomain(&k4b).expect("generic");
            let t2 = isog2_eval(&tb, &kpsb);

            // j-invariants are model-independent, so they must agree even
            // though the two codomain formulas use opposite sign conventions
            // for A.
            assert_eq!(
                img4.j_invariant(),
                img2.j_invariant(),
                "4-isogeny codomain differs from two composed 2-isogenies"
            );
            // each intermediate step is a 2-isogeny
            assert!(phi2(&curve.j_invariant(), &mid.j_invariant()).is_zero());
            assert!(phi2(&mid.j_invariant(), &img2.j_invariant()).is_zero());

            // the kernel dies, images live on the codomain
            assert!(
                isog4_eval(&k4, &kps4).is_infinity(),
                "4-isogeny kernel not killed"
            );
            assert!(img4.is_on_curve(&t4), "4-isogeny image off the codomain");
            assert!(img2.is_on_curve(&t2), "2+2 image off the codomain");

            // The two models differ by x |-> -x, so the images must match up
            // to that sign.
            let (x4, x2) = (t4.affine_x().unwrap(), t2.affine_x().unwrap());
            assert!(
                x4 == x2 || x4 == x2.neg(),
                "images differ by more than the model"
            );
        }
    }

    #[test]
    fn strategy_chain_matches_naive_chain() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0x3333_0000_0000_0001);
        let t = full_order_two_point(&mut rng, &curve, &a24);
        let extra = random_point(&mut rng, &curve);

        // Short chains, where the O(n^2) naive walker is still cheap.
        for n in 1..=12usize {
            let k = xdbl_e(&t, TWO_TORSION_POWER - 2 * n, &a24);
            let strategy = optimal_strategy(n, COST_DBL, COST_EVAL);
            assert_eq!(strategy.len(), n.saturating_sub(1));

            let mut a = [k, extra];
            let ca = chain_4_strategy(&curve, &k, n, &mut a, &strategy).expect("chain");
            let mut b = [k, extra];
            let cb = chain_4_naive(&curve, &k, n, &mut b).expect("chain");

            // The two walkers derive each step's kernel point differently
            // (push-then-double vs double-then-push), so they land on the same
            // curve with different projective scalings.  Compare the curve,
            // not the representative.
            assert!(
                ca.same_curve(&cb),
                "strategy and naive codomains differ at n={n}"
            );
            assert_eq!(
                ca.j_invariant(),
                cb.j_invariant(),
                "strategy and naive j-invariants differ at n={n}"
            );
            assert!(a[0].is_infinity(), "kernel not killed at n={n}");
            assert!(b[0].is_infinity(), "kernel not killed at n={n} (naive)");
            assert!(a[1].same_x(&b[1]), "pushed point differs at n={n}");
            assert!(
                ca.is_on_curve(&a[1]),
                "pushed point off the codomain at n={n}"
            );
        }
    }

    #[test]
    fn full_length_chain_of_degree_two_to_the_324() {
        let curve = test_curve();
        let a24 = curve.normalised_a24();
        let mut rng = Rng::new(0x9999_0000_0000_0001);
        let t = full_order_two_point(&mut rng, &curve, &a24);

        // A point of order 3: [2^324]P for a generic P.  Coprime to the
        // chain's degree, so the isogeny must preserve its order exactly.
        let r3 = order_three_point(&mut rng, &curve, &a24);

        let mut push = [t, r3];
        let img =
            two_isogeny_chain(&curve, &t, TWO_TORSION_POWER, &mut push).expect("generic kernel");

        // (1) the kernel generator maps to the identity.
        assert!(
            push[0].is_infinity(),
            "kernel of the 2^324-isogeny survived"
        );

        // (2) the order-3 point keeps order exactly 3.
        let a24i = img.normalised_a24();
        assert!(!push[1].is_infinity(), "order-3 point was killed");
        assert!(
            ladder(&[3], 8, &push[1], &a24i).is_infinity(),
            "order is no longer 3"
        );
        assert!(img.is_on_curve(&push[1]), "image off the codomain");

        // (3) the codomain is still supersingular with the same group order.
        assert!(ladder(&P_PLUS_1, P_PLUS_1_BITS, &push[1], &a24i).is_infinity());
        let q = random_point(&mut rng, &img);
        assert!(ladder(&P_PLUS_1, P_PLUS_1_BITS, &q, &a24i).is_infinity());

        // (4) an odd chain length works too, exercising the leading 2-isogeny.
        // The kernel must have order exactly 2^323, so halve the 2^324 point.
        let t2 = full_order_two_point(&mut rng, &curve, &a24);
        let k323 = xdbl_a24(&t2, &a24);
        let mut push2 = [t2];
        let img_odd = two_isogeny_chain(&curve, &k323, TWO_TORSION_POWER - 1, &mut push2)
            .expect("generic kernel");
        // <t2> meets the kernel in index 2, so the image of t2 has order 2.
        assert!(
            !push2[0].is_infinity(),
            "a 2^323-isogeny should not kill a 2^324 point"
        );
        let a24o = img_odd.normalised_a24();
        assert!(
            xdbl_a24(&push2[0], &a24o).is_infinity(),
            "image should have order 2"
        );
    }
}
