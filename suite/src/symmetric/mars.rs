//! **MARS** — IBM's AES finalist (Burwick, Coppersmith et al., 1998–1999).
//!
//! MARS uses a heterogeneous, "Type-3 Feistel"-style structure that
//! looks more like a sandwich than a uniform iterated cipher: an outer
//! pair of fast, *unkeyed* mixing layers wrapping an inner
//! *keyed* "cryptographic core".  The rationale, per the IBM team:
//! the outer mixing layers cheaply guarantee full diffusion of any
//! single-bit input difference before the keyed core sees it (and,
//! symmetrically, hide internal structure from chosen-ciphertext
//! attacks), while the inner core does the heavy lifting with a
//! multiplication-driven keyed nonlinearity that resists differential
//! and linear cryptanalysis with a wide margin.
//!
//! ## Structure
//!
//! On a 4-word state `(A, B, C, D)` (each `u32`, little-endian):
//!
//! 1. **Whiten**: `A,B,C,D += K[0..4]`.
//! 2. **Forward mixing** (8 rounds, unkeyed): each round applies four
//!    S-box lookups driven by rotations of the "source" word, plus
//!    two extra `+=` "feedback" steps in rounds 0,1,4,5 to prevent
//!    a low-difference attack on the pure mixing layer.
//! 3. **Keyed core** (16 rounds): each round computes
//!    `(L, M, R) = E(A, K[2i+4], K[2i+5])` where the E-function
//!    combines a key-add, a 9-bit S-box lookup, a key-multiply, two
//!    fixed and two data-dependent rotations.  The three outputs
//!    `(L, M, R)` are folded into the remaining three words.  The
//!    first 8 of these rounds use a "forward" word order and the
//!    second 8 a "backward" order — chosen to make encryption and
//!    decryption have the same structure.
//! 4. **Backwards mixing** (8 rounds, unkeyed): inverse-like of the
//!    forward mixing layer (different S-box assignment and direction).
//! 5. **Unwhiten**: `A,B,C,D -= K[36..40]`.
//!
//! Total: **32 rounds**, but only 16 are keyed.  The 40-word expanded
//! key fills `K[0..40]`; the **round-2 key schedule** (used here, per
//! IBM's post-NIST-tweak submission and Gladman's 2000 reference) is
//! a four-iteration mixing of a 15-word working array.  After
//! expansion, multiplicative keys `K[5], K[7], …, K[35]` are "fixed"
//! so they neither contain long runs of equal bits nor are weak
//! multiplicands (`weakness mask` algorithm in `fix_mult_key`).
//!
//! ## Conventions
//!
//! - Plaintext / key / ciphertext bytes are loaded **little-endian**
//!   per the IBM `ecb_tbl.txt` test-vector file (RFC-style hex strings
//!   are byte arrays in memory order, four bytes per `u32`).
//! - Key sizes accepted: 128, 192, 256 bits.
//!
//! ## Security note
//!
//! MARS reached the AES finals; the final NIST report cited high
//! security margin but criticised its "heterogeneous" structure as
//! complex to analyse.  No practical attack on the full 32-round
//! cipher has been published.  As with all AES finalist runner-ups,
//! **prefer AES** for new designs.
//!
//! ## References
//!
//! - **C. Burwick, D. Coppersmith, E. D'Avignon et al.**,
//!   *MARS — a candidate cipher for AES* (revised), IBM, 1999.
//! - Brian Gladman's round-2 reference implementation (Jan 2000):
//!   the source of the S-box / b-tab constants used here.
//! - **IBM `ecb_tbl.txt`** Known-Answer-Test file (the
//!   `KEY=0…, PT=0…` row gives the canonical zero-vector).

// ── Constants ────────────────────────────────────────────────────────

/// The MARS 512-entry S-box.  `S[0..256]` is "S0" and `S[256..512]` is
/// "S1" in the IBM paper's terminology; the 9-bit-index lookup
/// `S[m & 0x1ff]` used inside `E` reads from both halves uniformly.
///
/// Values are taken verbatim from Gladman's round-2 reference; the
/// `b_tab` constants for multiplicative-key fixing are entries 265-268.
#[rustfmt::skip]
const SBOX: [u32; 512] = [
    0x09d0c479, 0x28c8ffe0, 0x84aa6c39, 0x9dad7287,
    0x7dff9be3, 0xd4268361, 0xc96da1d4, 0x7974cc93,
    0x85d0582e, 0x2a4b5705, 0x1ca16a62, 0xc3bd279d,
    0x0f1f25e5, 0x5160372f, 0xc695c1fb, 0x4d7ff1e4,
    0xae5f6bf4, 0x0d72ee46, 0xff23de8a, 0xb1cf8e83,
    0xf14902e2, 0x3e981e42, 0x8bf53eb6, 0x7f4bf8ac,
    0x83631f83, 0x25970205, 0x76afe784, 0x3a7931d4,
    0x4f846450, 0x5c64c3f6, 0x210a5f18, 0xc6986a26,
    0x28f4e826, 0x3a60a81c, 0xd340a664, 0x7ea820c4,
    0x526687c5, 0x7eddd12b, 0x32a11d1d, 0x9c9ef086,
    0x80f6e831, 0xab6f04ad, 0x56fb9b53, 0x8b2e095c,
    0xb68556ae, 0xd2250b0d, 0x294a7721, 0xe21fb253,
    0xae136749, 0xe82aae86, 0x93365104, 0x99404a66,
    0x78a784dc, 0xb69ba84b, 0x04046793, 0x23db5c1e,
    0x46cae1d6, 0x2fe28134, 0x5a223942, 0x1863cd5b,
    0xc190c6e3, 0x07dfb846, 0x6eb88816, 0x2d0dcc4a,
    0xa4ccae59, 0x3798670d, 0xcbfa9493, 0x4f481d45,
    0xeafc8ca8, 0xdb1129d6, 0xb0449e20, 0x0f5407fb,
    0x6167d9a8, 0xd1f45763, 0x4daa96c3, 0x3bec5958,
    0xababa014, 0xb6ccd201, 0x38d6279f, 0x02682215,
    0x8f376cd5, 0x092c237e, 0xbfc56593, 0x32889d2c,
    0x854b3e95, 0x05bb9b43, 0x7dcd5dcd, 0xa02e926c,
    0xfae527e5, 0x36a1c330, 0x3412e1ae, 0xf257f462,
    0x3c4f1d71, 0x30a2e809, 0x68e5f551, 0x9c61ba44,
    0x5ded0ab8, 0x75ce09c8, 0x9654f93e, 0x698c0cca,
    0x243cb3e4, 0x2b062b97, 0x0f3b8d9e, 0x00e050df,
    0xfc5d6166, 0xe35f9288, 0xc079550d, 0x0591aee8,
    0x8e531e74, 0x75fe3578, 0x2f6d829a, 0xf60b21ae,
    0x95e8eb8d, 0x6699486b, 0x901d7d9b, 0xfd6d6e31,
    0x1090acef, 0xe0670dd8, 0xdab2e692, 0xcd6d4365,
    0xe5393514, 0x3af345f0, 0x6241fc4d, 0x460da3a3,
    0x7bcf3729, 0x8bf1d1e0, 0x14aac070, 0x1587ed55,
    0x3afd7d3e, 0xd2f29e01, 0x29a9d1f6, 0xefb10c53,
    0xcf3b870f, 0xb414935c, 0x664465ed, 0x024acac7,
    0x59a744c1, 0x1d2936a7, 0xdc580aa6, 0xcf574ca8,
    0x040a7a10, 0x6cd81807, 0x8a98be4c, 0xaccea063,
    0xc33e92b5, 0xd1e0e03d, 0xb322517e, 0x2092bd13,
    0x386b2c4a, 0x52e8dd58, 0x58656dfb, 0x50820371,
    0x41811896, 0xe337ef7e, 0xd39fb119, 0xc97f0df6,
    0x68fea01b, 0xa150a6e5, 0x55258962, 0xeb6ff41b,
    0xd7c9cd7a, 0xa619cd9e, 0xbcf09576, 0x2672c073,
    0xf003fb3c, 0x4ab7a50b, 0x1484126a, 0x487ba9b1,
    0xa64fc9c6, 0xf6957d49, 0x38b06a75, 0xdd805fcd,
    0x63d094cf, 0xf51c999e, 0x1aa4d343, 0xb8495294,
    0xce9f8e99, 0xbffcd770, 0xc7c275cc, 0x378453a7,
    0x7b21be33, 0x397f41bd, 0x4e94d131, 0x92cc1f98,
    0x5915ea51, 0x99f861b7, 0xc9980a88, 0x1d74fd5f,
    0xb0a495f8, 0x614deed0, 0xb5778eea, 0x5941792d,
    0xfa90c1f8, 0x33f824b4, 0xc4965372, 0x3ff6d550,
    0x4ca5fec0, 0x8630e964, 0x5b3fbbd6, 0x7da26a48,
    0xb203231a, 0x04297514, 0x2d639306, 0x2eb13149,
    0x16a45272, 0x532459a0, 0x8e5f4872, 0xf966c7d9,
    0x07128dc0, 0x0d44db62, 0xafc8d52d, 0x06316131,
    0xd838e7ce, 0x1bc41d00, 0x3a2e8c0f, 0xea83837e,
    0xb984737d, 0x13ba4891, 0xc4f8b949, 0xa6d6acb3,
    0xa215cdce, 0x8359838b, 0x6bd1aa31, 0xf579dd52,
    0x21b93f93, 0xf5176781, 0x187dfdde, 0xe94aeb76,
    0x2b38fd54, 0x431de1da, 0xab394825, 0x9ad3048f,
    0xdfea32aa, 0x659473e3, 0x623f7863, 0xf3346c59,
    0xab3ab685, 0x3346a90b, 0x6b56443e, 0xc6de01f8,
    0x8d421fc0, 0x9b0ed10c, 0x88f1a1e9, 0x54c1f029,
    0x7dead57b, 0x8d7ba426, 0x4cf5178a, 0x551a7cca,
    0x1a9a5f08, 0xfcd651b9, 0x25605182, 0xe11fc6c3,
    0xb6fd9676, 0x337b3027, 0xb7c8eb14, 0x9e5fd030,
    0x6b57e354, 0xad913cf7, 0x7e16688d, 0x58872a69,
    0x2c2fc7df, 0xe389ccc6, 0x30738df1, 0x0824a734,
    0xe1797a8b, 0xa4a8d57b, 0x5b5d193b, 0xc8a8309b,
    0x73f9a978, 0x73398d32, 0x0f59573e, 0xe9df2b03,
    0xe8a5b6c8, 0x848d0704, 0x98df93c2, 0x720a1dc3,
    0x684f259a, 0x943ba848, 0xa6370152, 0x863b5ea3,
    0xd17b978b, 0x6d9b58ef, 0x0a700dd4, 0xa73d36bf,
    0x8e6a0829, 0x8695bc14, 0xe35b3447, 0x933ac568,
    0x8894b022, 0x2f511c27, 0xddfbcc3c, 0x006662b6,
    0x117c83fe, 0x4e12b414, 0xc2bca766, 0x3a2fec10,
    0xf4562420, 0x55792e2a, 0x46f5d857, 0xceda25ce,
    0xc3601d3b, 0x6c00ab46, 0xefac9c28, 0xb3c35047,
    0x611dfee3, 0x257c3207, 0xfdd58482, 0x3b14d84f,
    0x23becb64, 0xa075f3a3, 0x088f8ead, 0x07adf158,
    0x7796943c, 0xfacabf3d, 0xc09730cd, 0xf7679969,
    0xda44e9ed, 0x2c854c12, 0x35935fa3, 0x2f057d9f,
    0x690624f8, 0x1cb0bafd, 0x7b0dbdc6, 0x810f23bb,
    0xfa929a1a, 0x6d969a17, 0x6742979b, 0x74ac7d05,
    0x010e65c4, 0x86a3d963, 0xf907b5a0, 0xd0042bd3,
    0x158d7d03, 0x287a8255, 0xbba8366f, 0x096edc33,
    0x21916a7b, 0x77b56b86, 0x951622f9, 0xa6c5e650,
    0x8cea17d1, 0xcd8c62bc, 0xa3d63433, 0x358a68fd,
    0x0f9b9d3c, 0xd6aa295b, 0xfe33384a, 0xc000738e,
    0xcd67eb2f, 0xe2eb6dc2, 0x97338b02, 0x06c9f246,
    0x419cf1ad, 0x2b83c045, 0x3723f18a, 0xcb5b3089,
    0x160bead7, 0x5d494656, 0x35f8a74b, 0x1e4e6c9e,
    0x000399bd, 0x67466880, 0xb4174831, 0xacf423b2,
    0xca815ab3, 0x5a6395e7, 0x302a67c5, 0x8bdb446b,
    0x108f8fa4, 0x10223eda, 0x92b8b48b, 0x7f38d0ee,
    0xab2701d4, 0x0262d415, 0xaf224a30, 0xb3d88aba,
    0xf8b2c3af, 0xdaf7ef70, 0xcc97d3b7, 0xe9614b6c,
    0x2baebff4, 0x70f687cf, 0x386c9156, 0xce092ee5,
    0x01e87da6, 0x6ce91e6a, 0xbb7bcc84, 0xc7922c20,
    0x9d3b71fd, 0x060e41c6, 0xd7590f15, 0x4e03bb47,
    0x183c198e, 0x63eeb240, 0x2ddbf49a, 0x6d5cba54,
    0x923750af, 0xf9e14236, 0x7838162b, 0x59726c72,
    0x81b66760, 0xbb2926c1, 0x48a0ce0d, 0xa6c0496d,
    0xad43507b, 0x718d496a, 0x9df057af, 0x44b1bde6,
    0x054356dc, 0xde7ced35, 0xd51a138b, 0x62088cc9,
    0x35830311, 0xc96efca2, 0x686f86ec, 0x8e77cb68,
    0x63e1d6b8, 0xc80f9778, 0x79c491fd, 0x1b4c67f2,
    0x72698d7d, 0x5e368c31, 0xf7d95e2e, 0xa1d3493f,
    0xdcd9433e, 0x896f1552, 0x4bc4ca7a, 0xa6d1baf4,
    0xa5a96dcc, 0x0bef8b46, 0xa169fda7, 0x74df40b7,
    0x4e208804, 0x9a756607, 0x038e87c8, 0x20211e44,
    0x8b7ad4bf, 0xc6403f35, 0x1848e36d, 0x80bdb038,
    0x1e62891c, 0x643d2107, 0xbf04d6f8, 0x21092c8c,
    0xf644f389, 0x0778404e, 0x7b78adb8, 0xa2c52d53,
    0x42157abe, 0xa2253e2e, 0x7bf3f4ae, 0x80f594f9,
    0x953194e7, 0x77eb92ed, 0xb3816930, 0xda8d9336,
    0xbf447469, 0xf26d9483, 0xee6faed5, 0x71371235,
    0xde425f73, 0xb4e59f43, 0x7dbe2d4e, 0x2d37b185,
    0x49dc9a63, 0x98c39d98, 0x1301c9a2, 0x389b1bbf,
    0x0c18588d, 0xa421c1ba, 0x7aa3865c, 0x71e08558,
    0x3c5cfcaa, 0x7d239ca4, 0x0297d9dd, 0xd7dc2830,
    0x4b37802b, 0x7428ab54, 0xaeee0347, 0x4b3fbb85,
    0x692f2f08, 0x134e578e, 0x36d9e0bf, 0xae8b5fcf,
    0xedb93ecf, 0x2b27248e, 0x170eb1ef, 0x7dc57fd6,
    0x1e760f16, 0xb1136601, 0x864e1b9b, 0xd7ea7319,
    0x3ab871bd, 0xcfa4d76f, 0xe31bd782, 0x0dbeb469,
    0xabb96061, 0x5370f85d, 0xffb07e37, 0xda30d0fb,
    0xebc977b6, 0x0b98b40f, 0x3a4d0fe6, 0xdf4fc26b,
    0x159cf22a, 0xc298d6e2, 0x2b78ef6a, 0x61a94ac0,
    0xab561187, 0x14eea0f0, 0xdf0d4164, 0x19af70ee,
];

/// `b_tab[i] = SBOX[265 + i]`, used by the multiplicative-key fix-up
/// step of the key schedule.  Pulled into a small array purely for
/// clarity at the call site.
const B_TAB: [u32; 4] = [SBOX[265], SBOX[266], SBOX[267], SBOX[268]];

// ── Round building blocks ────────────────────────────────────────────
//
// These mirror the Gladman macros `f_mix`, `b_mix`, `f_ktr`, `r_ktr`.
// Each takes the four state words by mutable reference; the ordering
// of the `a, b, c, d` arguments rotates with the round counter, as in
// the original C code.

/// Forward mixing round.  Uses S0 lookups on bytes 0,2 of `a` and S1
/// lookups on bytes 1,3 (where "byte 0" is the LSB).  `a` is finally
/// rotated right by 24 bits — equivalent to "consuming" each byte
/// after it has driven one S-box.
#[inline(always)]
fn f_mix(a: &mut u32, b: &mut u32, c: &mut u32, d: &mut u32) {
    let r = a.rotate_right(8);
    *b ^= SBOX[(*a & 0xff) as usize];
    *b = b.wrapping_add(SBOX[((r & 0xff) as usize) + 256]);
    let r2 = a.rotate_right(16);
    *a = a.rotate_right(24);
    *c = c.wrapping_add(SBOX[(r2 & 0xff) as usize]);
    *d ^= SBOX[((*a & 0xff) as usize) + 256];
}

/// Backwards mixing round.  Mirror of `f_mix` with left rotations and
/// signs flipped on the additions.  Despite the names, `f_mix` and
/// `b_mix` are **not** literal inverses of each other — MARS is not
/// symmetric across the layers, only across encryption/decryption
/// of the full cipher.
#[inline(always)]
fn b_mix(a: &mut u32, b: &mut u32, c: &mut u32, d: &mut u32) {
    let r = a.rotate_left(8);
    *b ^= SBOX[((*a & 0xff) as usize) + 256];
    *c = c.wrapping_sub(SBOX[(r & 0xff) as usize]);
    let r2 = a.rotate_left(16);
    *a = a.rotate_left(24);
    *d = d.wrapping_sub(SBOX[((r2 & 0xff) as usize) + 256]);
    *d ^= SBOX[(*a & 0xff) as usize];
}

/// Forward keyed-transformation round (encryption direction).  The
/// E-function combines a key-add, a 9-bit S-box lookup, a key-multiply
/// (the multiplicative-key step that gives MARS most of its
/// non-linearity), and two data-dependent rotations.
///
/// The three outputs `(M, L, R)` are folded back into the remaining
/// three state words: `c += M^<<<r`, `d ^= R`, `b += L<<<r`.
#[inline(always)]
fn f_ktr(a: &mut u32, b: &mut u32, c: &mut u32, d: &mut u32, key: &[u32; 40], i: usize) {
    let m = a.wrapping_add(key[i]);
    *a = a.rotate_left(13);
    let r0 = a.wrapping_mul(key[i + 1]);
    let mut l = SBOX[(m & 0x1ff) as usize];
    let r1 = r0.rotate_left(5);
    *c = c.wrapping_add(m.rotate_left(r1 & 31));
    l ^= r1;
    let r2 = r1.rotate_left(5);
    l ^= r2;
    *d ^= r2;
    *b = b.wrapping_add(l.rotate_left(r2 & 31));
}

/// Reverse keyed transformation (decryption direction).  Algebraically
/// the inverse of `f_ktr` for the same `(i, key)`; the rotation of `a`
/// and the order of the `c -=`/`b -=` updates flip.
#[inline(always)]
fn r_ktr(a: &mut u32, b: &mut u32, c: &mut u32, d: &mut u32, key: &[u32; 40], i: usize) {
    let r0 = a.wrapping_mul(key[i + 1]);
    *a = a.rotate_right(13);
    let m = a.wrapping_add(key[i]);
    let mut l = SBOX[(m & 0x1ff) as usize];
    let r1 = r0.rotate_left(5);
    l ^= r1;
    *c = c.wrapping_sub(m.rotate_left(r1 & 31));
    let r2 = r1.rotate_left(5);
    l ^= r2;
    *d ^= r2;
    *b = b.wrapping_sub(l.rotate_left(r2 & 31));
}

// ── Key schedule ─────────────────────────────────────────────────────

/// Round-2 MARS key schedule.  Expands the user key (4/6/8 little-
/// endian `u32` words) into 40 round-key words.
///
/// The schedule has two phases:
/// 1. **Mixing**: a 15-word working array `t[0..15]` is filled with
///    the user key followed by its length-in-words `m` and zero padding.
///    Four iterations then run a "linear stir" (`tk1`/`tk2`) followed
///    by 4 × "S-box stir" (`tk3`) over all 15 slots; ten of those
///    slots (`t[0,4,8,12,1,5,9,13,2,6]`) are written into the round-
///    key array each iteration.
/// 2. **Multiplicative-key fix-up**: for each odd index `i ∈ 5..37`
///    that is used as a *multiplier* in the keyed-core rounds, the
///    low two bits are forced to `11` (so the key is odd and not
///    `≡ 1 mod 4`), and any internal run of ≥ 10 equal bits is
///    masked out via [`fix_mult_key`] to avoid weak multipliers.
fn expand_key(key: &[u8]) -> [u32; 40] {
    let key_bytes = key.len();
    assert!(matches!(key_bytes, 16 | 24 | 32));
    let m = (key_bytes / 4) as u32;

    // Build the 15-word working array.
    let mut t = [0u32; 15];
    for i in 0..(m as usize) {
        t[i] = u32::from_le_bytes(key[i * 4..i * 4 + 4].try_into().unwrap());
    }
    t[m as usize] = m;
    // remainder already zero

    let mut l_key = [0u32; 40];
    let mut kp = 0usize;

    for iter in 0..4u32 {
        // ── Linear stir (tk1/tk2) ────────────────────────────────────
        // 15 steps, alternating two "accumulators" t1, t2.  Each step
        // updates `t[j]` (and the accumulator it owns) using
        // `rotl(t_prev ^ t[(j+8) % 15], 3) ^ (iter + 4j)`.
        let mut t1 = t[13];
        let mut t2 = t[14];
        for j in 0..15u32 {
            let neighbour = t[((j + 8) % 15) as usize];
            // Even j picks t1; odd j picks t2.  The constant added is
            // `iter + 4*j` per the round-2 spec.
            if j % 2 == 0 {
                t1 = (t1 ^ neighbour).rotate_left(3) ^ (iter + 4 * j);
                t[j as usize] ^= t1;
                t1 = t[j as usize];
            } else {
                t2 = (t2 ^ neighbour).rotate_left(3) ^ (iter + 4 * j);
                t[j as usize] ^= t2;
                t2 = t[j as usize];
            }
        }
        // ── S-box stir (tk3), 4 passes over all 15 slots ─────────────
        //   t[j] = rotl(t[j] + SBOX[t_prev & 511], 9)
        // The "previous" t starts each pass as `t[14]` (matches the
        // reference, where the last `tk3 (14)` of an earlier pass
        // leaves `t1 = t[14]`; the first pass's seed is `t1 = t[14]`
        // because `tk1(14)` was the final linear-stir update).
        let mut t1 = t[14];
        for _ in 0..4u32 {
            for j in 0..15usize {
                let new = t[j]
                    .wrapping_add(SBOX[(t1 & 0x1ff) as usize])
                    .rotate_left(9);
                t[j] = new;
                t1 = new;
            }
        }
        // ── Round-key picks ──────────────────────────────────────────
        // 10 of the 15 working-array slots become K[10·iter + 0..10],
        // in the fixed order `0,4,8,12,1,5,9,13,2,6`.
        for &idx in &[0, 4, 8, 12, 1, 5, 9, 13, 2, 6] {
            l_key[kp] = t[idx];
            kp += 1;
        }
    }

    // ── Multiplicative-key fix-up ────────────────────────────────────
    for i in (5..37).step_by(2) {
        let raw = l_key[i];
        l_key[i] = fix_mult_key(raw, l_key[i - 1]);
    }

    l_key
}

/// "Fix" a 32-bit value `raw` so it is safe to use as a multiplier
/// inside the keyed core.
///
/// Two requirements:
/// - **Odd, not ≡ 1 mod 4** — force the low two bits to `11`.
/// - **No long run of equal bits** — if `raw` has any internal
///   sequence of ≥ 10 zero or ≥ 10 one bits (counting only bits 1..30,
///   plus a special-case top-end exception), mask those bits with a
///   rotated entry from [`B_TAB`].  The rotation amount is the low
///   five bits of the *previous* round key (`prev`), per the round-2
///   spec; the round-1 spec used `l_key[i+3] & 31` instead.
///
/// The "weakness mask" derivation is exactly the algorithm in
/// Gladman's reference: see comments inline.
fn fix_mult_key(raw: u32, prev: u32) -> u32 {
    let mut w = raw | 3;

    // Set bit `j` of `mm` iff bit `j` and bit `j+1` of `w` are equal
    // (i.e. they're both 0 or both 1).  Bit 31 is cleared up front.
    let mut mm = (!w ^ (w >> 1)) & 0x7fff_ffff;
    // Nine consecutive bits in `mm` mean ten consecutive equal bits
    // in `w`.  Two rounds of `mm &= shifts` collapse runs of 10+ into
    // "set bit at the bottom of the run".
    mm &= (mm >> 1) & (mm >> 2);
    mm &= (mm >> 3) & (mm >> 6);

    if mm == 0 {
        return w;
    }

    // Re-expand each "run bottom" bit back into 8 set bits one
    // position above it.
    mm <<= 1;
    mm |= mm << 1;
    mm |= mm << 2;
    mm |= mm << 4;
    mm &= 0xffff_fffc;

    w ^= B_TAB[(raw & 3) as usize].rotate_left(prev & 31) & mm;
    w
}

// ── Cipher API ───────────────────────────────────────────────────────

/// MARS context.  Holds the 40-word expanded round-key array
/// (160 bytes) and exposes block encrypt / decrypt.  Constructed once
/// per key via [`Mars::new`]; both endpoints can be called repeatedly.
#[derive(Clone, Debug)]
pub struct Mars {
    l_key: [u32; 40],
}

impl Drop for Mars {
    fn drop(&mut self) {
        // Best-effort scrub of expanded key material.  Same caveat as
        // `SerpentKey`: register/stack spills are outside our control.
        for w in self.l_key.iter_mut() {
            *w = 0;
        }
    }
}

impl Mars {
    /// Construct a MARS instance from a 128, 192, or 256-bit key.
    ///
    /// Returns an error for any other key length.  The key bytes are
    /// loaded **little-endian** four at a time into the working
    /// array — i.e. the byte order matches the IBM `ecb_tbl.txt`
    /// known-answer-test convention.
    pub fn new(key: &[u8]) -> Result<Self, &'static str> {
        if !matches!(key.len(), 16 | 24 | 32) {
            return Err("MARS key must be 16, 24, or 32 bytes (128/192/256-bit)");
        }
        Ok(Mars {
            l_key: expand_key(key),
        })
    }

    /// Encrypt one 16-byte block in place.
    pub fn encrypt_block(&self, block: &mut [u8; 16]) {
        let mut a = u32::from_le_bytes(block[0..4].try_into().unwrap()).wrapping_add(self.l_key[0]);
        let mut b = u32::from_le_bytes(block[4..8].try_into().unwrap()).wrapping_add(self.l_key[1]);
        let mut c =
            u32::from_le_bytes(block[8..12].try_into().unwrap()).wrapping_add(self.l_key[2]);
        let mut d =
            u32::from_le_bytes(block[12..16].try_into().unwrap()).wrapping_add(self.l_key[3]);

        // ── Forward mixing (8 rounds) ───────────────────────────────
        // The 2 ↑ `a += d` / `b += c` "feedback" steps appear in
        // rounds 0,1,4,5 only — they prevent a low-difference attack
        // on the otherwise pure mixing layer.
        f_mix(&mut a, &mut b, &mut c, &mut d);
        a = a.wrapping_add(d);
        f_mix(&mut b, &mut c, &mut d, &mut a);
        b = b.wrapping_add(c);
        f_mix(&mut c, &mut d, &mut a, &mut b);
        f_mix(&mut d, &mut a, &mut b, &mut c);
        f_mix(&mut a, &mut b, &mut c, &mut d);
        a = a.wrapping_add(d);
        f_mix(&mut b, &mut c, &mut d, &mut a);
        b = b.wrapping_add(c);
        f_mix(&mut c, &mut d, &mut a, &mut b);
        f_mix(&mut d, &mut a, &mut b, &mut c);

        // ── Keyed core (16 rounds) ──────────────────────────────────
        // First 8 rounds: "forward" word order (a, b, c, d) rotated.
        // Next 8 rounds: "backward" — swap c ↔ d in the call signature
        // so the E-function outputs land in mirrored positions.
        let k = &self.l_key;
        f_ktr(&mut a, &mut b, &mut c, &mut d, k, 4);
        f_ktr(&mut b, &mut c, &mut d, &mut a, k, 6);
        f_ktr(&mut c, &mut d, &mut a, &mut b, k, 8);
        f_ktr(&mut d, &mut a, &mut b, &mut c, k, 10);
        f_ktr(&mut a, &mut b, &mut c, &mut d, k, 12);
        f_ktr(&mut b, &mut c, &mut d, &mut a, k, 14);
        f_ktr(&mut c, &mut d, &mut a, &mut b, k, 16);
        f_ktr(&mut d, &mut a, &mut b, &mut c, k, 18);
        // "Backward" half — note the (a, d, c, b) ordering on each call.
        f_ktr(&mut a, &mut d, &mut c, &mut b, k, 20);
        f_ktr(&mut b, &mut a, &mut d, &mut c, k, 22);
        f_ktr(&mut c, &mut b, &mut a, &mut d, k, 24);
        f_ktr(&mut d, &mut c, &mut b, &mut a, k, 26);
        f_ktr(&mut a, &mut d, &mut c, &mut b, k, 28);
        f_ktr(&mut b, &mut a, &mut d, &mut c, k, 30);
        f_ktr(&mut c, &mut b, &mut a, &mut d, k, 32);
        f_ktr(&mut d, &mut c, &mut b, &mut a, k, 34);

        // ── Backwards mixing (8 rounds) ─────────────────────────────
        b_mix(&mut a, &mut b, &mut c, &mut d);
        b_mix(&mut b, &mut c, &mut d, &mut a);
        c = c.wrapping_sub(b);
        b_mix(&mut c, &mut d, &mut a, &mut b);
        d = d.wrapping_sub(a);
        b_mix(&mut d, &mut a, &mut b, &mut c);
        b_mix(&mut a, &mut b, &mut c, &mut d);
        b_mix(&mut b, &mut c, &mut d, &mut a);
        c = c.wrapping_sub(b);
        b_mix(&mut c, &mut d, &mut a, &mut b);
        d = d.wrapping_sub(a);
        b_mix(&mut d, &mut a, &mut b, &mut c);

        block[0..4].copy_from_slice(&a.wrapping_sub(self.l_key[36]).to_le_bytes());
        block[4..8].copy_from_slice(&b.wrapping_sub(self.l_key[37]).to_le_bytes());
        block[8..12].copy_from_slice(&c.wrapping_sub(self.l_key[38]).to_le_bytes());
        block[12..16].copy_from_slice(&d.wrapping_sub(self.l_key[39]).to_le_bytes());
    }

    /// Decrypt one 16-byte block in place.  Mirror of `encrypt_block`.
    pub fn decrypt_block(&self, block: &mut [u8; 16]) {
        // The decryption "loads in reverse": ct[0..4] → d, ct[4..8] → c,
        // ct[8..12] → b, ct[12..16] → a.  This reflects the cipher's
        // not-fully-symmetric structure: encryption uses K[0..4] then
        // K[36..40]; decryption swaps them and reverses both halves.
        let mut d =
            u32::from_le_bytes(block[0..4].try_into().unwrap()).wrapping_add(self.l_key[36]);
        let mut c =
            u32::from_le_bytes(block[4..8].try_into().unwrap()).wrapping_add(self.l_key[37]);
        let mut b =
            u32::from_le_bytes(block[8..12].try_into().unwrap()).wrapping_add(self.l_key[38]);
        let mut a =
            u32::from_le_bytes(block[12..16].try_into().unwrap()).wrapping_add(self.l_key[39]);

        // Forward mixing on the loaded values (yes, the *encrypt*
        // forward mixing — MARS uses the same primitive in both
        // directions; only the keyed core uses a true inverse).
        f_mix(&mut a, &mut b, &mut c, &mut d);
        a = a.wrapping_add(d);
        f_mix(&mut b, &mut c, &mut d, &mut a);
        b = b.wrapping_add(c);
        f_mix(&mut c, &mut d, &mut a, &mut b);
        f_mix(&mut d, &mut a, &mut b, &mut c);
        f_mix(&mut a, &mut b, &mut c, &mut d);
        a = a.wrapping_add(d);
        f_mix(&mut b, &mut c, &mut d, &mut a);
        b = b.wrapping_add(c);
        f_mix(&mut c, &mut d, &mut a, &mut b);
        f_mix(&mut d, &mut a, &mut b, &mut c);

        // Reverse keyed core: 16 calls of `r_ktr` with key indices
        // descending from 34 down to 4 in steps of 2.  The
        // "backward half" word-ordering (a, d, c, b) comes first now,
        // mirroring the encryption.
        let k = &self.l_key;
        r_ktr(&mut a, &mut b, &mut c, &mut d, k, 34);
        r_ktr(&mut b, &mut c, &mut d, &mut a, k, 32);
        r_ktr(&mut c, &mut d, &mut a, &mut b, k, 30);
        r_ktr(&mut d, &mut a, &mut b, &mut c, k, 28);
        r_ktr(&mut a, &mut b, &mut c, &mut d, k, 26);
        r_ktr(&mut b, &mut c, &mut d, &mut a, k, 24);
        r_ktr(&mut c, &mut d, &mut a, &mut b, k, 22);
        r_ktr(&mut d, &mut a, &mut b, &mut c, k, 20);
        r_ktr(&mut a, &mut d, &mut c, &mut b, k, 18);
        r_ktr(&mut b, &mut a, &mut d, &mut c, k, 16);
        r_ktr(&mut c, &mut b, &mut a, &mut d, k, 14);
        r_ktr(&mut d, &mut c, &mut b, &mut a, k, 12);
        r_ktr(&mut a, &mut d, &mut c, &mut b, k, 10);
        r_ktr(&mut b, &mut a, &mut d, &mut c, k, 8);
        r_ktr(&mut c, &mut b, &mut a, &mut d, k, 6);
        r_ktr(&mut d, &mut c, &mut b, &mut a, k, 4);

        b_mix(&mut a, &mut b, &mut c, &mut d);
        b_mix(&mut b, &mut c, &mut d, &mut a);
        c = c.wrapping_sub(b);
        b_mix(&mut c, &mut d, &mut a, &mut b);
        d = d.wrapping_sub(a);
        b_mix(&mut d, &mut a, &mut b, &mut c);
        b_mix(&mut a, &mut b, &mut c, &mut d);
        b_mix(&mut b, &mut c, &mut d, &mut a);
        c = c.wrapping_sub(b);
        b_mix(&mut c, &mut d, &mut a, &mut b);
        d = d.wrapping_sub(a);
        b_mix(&mut d, &mut a, &mut b, &mut c);

        block[0..4].copy_from_slice(&d.wrapping_sub(self.l_key[0]).to_le_bytes());
        block[4..8].copy_from_slice(&c.wrapping_sub(self.l_key[1]).to_le_bytes());
        block[8..12].copy_from_slice(&b.wrapping_sub(self.l_key[2]).to_le_bytes());
        block[12..16].copy_from_slice(&a.wrapping_sub(self.l_key[3]).to_le_bytes());
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
        (0..s.len())
            .step_by(2)
            .map(|i| u8::from_str_radix(&s[i..i + 2], 16).unwrap())
            .collect()
    }
    fn hex16(s: &str) -> [u8; 16] {
        let v = h(s);
        let mut a = [0u8; 16];
        a.copy_from_slice(&v);
        a
    }

    /// **IBM `ecb_tbl.txt` row I=1, KEYSIZE=128**:
    /// Key = 0…0, PT = 0…0, CT = DCC07B8DFB0738D6E30A22DFCF27E886.
    /// The canonical zero-vector for MARS.
    /// Source: https://shaih.github.io/pubs/mars/test-vectors/ecb_tbl.txt
    #[test]
    fn mars_kat_zero_128() {
        let cipher = Mars::new(&[0u8; 16]).unwrap();
        let mut block = [0u8; 16];
        cipher.encrypt_block(&mut block);
        assert_eq!(
            block,
            hex16("dcc07b8dfb0738d6e30a22dfcf27e886"),
            "MARS-128 zero KAT mismatch",
        );
        cipher.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 16], "MARS-128 zero-key round-trip failed");
    }

    /// **Zero-key zero-plaintext, 192-bit key**.  Generated by running
    /// the round-2 reference implementation (Gladman, Jan 2000).
    #[test]
    fn mars_kat_zero_192() {
        let cipher = Mars::new(&[0u8; 24]).unwrap();
        let mut block = [0u8; 16];
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("f6b1b53c34b2b9e87f748482197e67e6"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 16]);
    }

    /// **Zero-key zero-plaintext, 256-bit key**.
    #[test]
    fn mars_kat_zero_256() {
        let cipher = Mars::new(&[0u8; 32]).unwrap();
        let mut block = [0u8; 16];
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("e998f63d39378523a951320451085d56"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, [0u8; 16]);
    }

    /// **Non-zero structured-bytes test, 128-bit key**.
    /// Key bytes = 00,01,…,0f; PT bytes = 10,11,…,1f.
    /// Reference output from round-2 Gladman implementation.
    #[test]
    fn mars_structured_128() {
        let mut key = [0u8; 16];
        for (i, b) in key.iter_mut().enumerate() {
            *b = i as u8;
        }
        let mut pt = [0u8; 16];
        for (i, b) in pt.iter_mut().enumerate() {
            *b = 0x10 + i as u8;
        }
        let cipher = Mars::new(&key).unwrap();
        let mut block = pt;
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("3f60ae8146985265cf8a7e26c9143c0a"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// **Non-zero, 192-bit key, descending plaintext bytes**.
    /// Key bytes = 00..17; PT bytes = a0..af.
    #[test]
    fn mars_structured_192() {
        let mut key = [0u8; 24];
        for (i, b) in key.iter_mut().enumerate() {
            *b = i as u8;
        }
        let mut pt = [0u8; 16];
        for (i, b) in pt.iter_mut().enumerate() {
            *b = 0xa0 + i as u8;
        }
        let cipher = Mars::new(&key).unwrap();
        let mut block = pt;
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("e0578a2b0ff3da3bee9f08f1122575bd"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// **Non-zero, 256-bit key**.
    /// Key bytes = 80..9f; PT bytes = f0,ef,…,e1.
    #[test]
    fn mars_structured_256() {
        let mut key = [0u8; 32];
        for (i, b) in key.iter_mut().enumerate() {
            *b = 0x80 + i as u8;
        }
        let mut pt = [0u8; 16];
        for (i, b) in pt.iter_mut().enumerate() {
            *b = 0xf0 - i as u8;
        }
        let cipher = Mars::new(&key).unwrap();
        let mut block = pt;
        cipher.encrypt_block(&mut block);
        assert_eq!(block, hex16("19be0dc19b0a21a7b28743705980e682"));
        cipher.decrypt_block(&mut block);
        assert_eq!(block, pt);
    }

    /// Round-trip across many random keys/plaintexts at all three key
    /// lengths.  Catches inverse-round bugs that single-vector tests
    /// can miss (off-by-one on the i counter, swapped word ordering
    /// in `r_ktr` calls, etc.).
    #[test]
    fn mars_random_round_trip() {
        let mut seed: u64 = 0xdead_beef_cafe_babe;
        for &klen in &[16usize, 24, 32] {
            for _ in 0..16 {
                let mut key = vec![0u8; klen];
                let mut pt = [0u8; 16];
                for b in key.iter_mut() {
                    seed = seed
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (seed >> 56) as u8;
                }
                for b in pt.iter_mut() {
                    seed = seed
                        .wrapping_mul(6364136223846793005)
                        .wrapping_add(1442695040888963407);
                    *b = (seed >> 56) as u8;
                }
                let cipher = Mars::new(&key).unwrap();
                let mut block = pt;
                cipher.encrypt_block(&mut block);
                assert_ne!(block, pt, "zero output");
                cipher.decrypt_block(&mut block);
                assert_eq!(block, pt, "round-trip failed");
            }
        }
    }

    /// **`b_tab` cross-check**: must match the reference comment in
    /// Gladman's source, `s_box[265..269]`.
    #[test]
    fn mars_b_tab_constants() {
        assert_eq!(B_TAB, [0xa4a8d57b, 0x5b5d193b, 0xc8a8309b, 0x73f9a978]);
    }

    /// Invalid key lengths must be rejected.
    #[test]
    fn mars_rejects_bad_key_length() {
        assert!(Mars::new(&[]).is_err());
        assert!(Mars::new(&[0u8; 15]).is_err());
        assert!(Mars::new(&[0u8; 20]).is_err());
        assert!(Mars::new(&[0u8; 33]).is_err());
        assert!(Mars::new(&[0u8; 16]).is_ok());
        assert!(Mars::new(&[0u8; 24]).is_ok());
        assert!(Mars::new(&[0u8; 32]).is_ok());
    }

    /// Single-bit-difference avalanche.  A correctly implemented
    /// MARS encryption should flip ~64 of 128 ciphertext bits per
    /// one-bit plaintext change.  We require at least 40 to leave
    /// margin for sampling noise (this is one specific pair).
    #[test]
    fn mars_avalanche() {
        let key = [0x77u8; 16];
        let cipher = Mars::new(&key).unwrap();
        let mut b1 = [0u8; 16];
        let mut b2 = [0u8; 16];
        b2[0] = 1;
        cipher.encrypt_block(&mut b1);
        cipher.encrypt_block(&mut b2);
        let differing: u32 = b1
            .iter()
            .zip(b2.iter())
            .map(|(a, b)| (a ^ b).count_ones())
            .sum();
        assert!(differing >= 40, "weak avalanche: {} bits", differing);
    }
}
