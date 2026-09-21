//! **KASUMI** — 3GPP block cipher (1999), the core of the 3G mobile
//! confidentiality (`f8` / UEA1) and integrity (`f9` / UIA1) algorithms.
//!
//! 64-bit block, 128-bit key, 8-round Feistel structure.  KASUMI is a
//! modified version of [`super::misty1`] adjusted for hardware
//! efficiency: the `FL` linear layer was changed (now using 16-bit
//! rotations) and the S-boxes `S7` / `S9` are **different** from
//! MISTY1's despite serving the same role.  The name *kasumi* (霞) is
//! Japanese for "mist" — a small joke from the designers.
//!
//! ## Security status
//!
//! - **Sandwich attack** (Dunkelman, Keller, Shamir, CRYPTO 2010)
//!   recovers a full KASUMI key in ≈ 2^{32} data, 2^{32} memory,
//!   2^{32} time — a *practical* break of the cipher itself.
//! - The attack does **not** extend to the same parameters of MISTY1.
//! - In 3G deployment the cipher is wrapped in `f8` (counter-style
//!   stream construction) and `f9` (CBC-MAC), which dilute the impact,
//!   but KASUMI is considered a cautionary example of "modify a strong
//!   cipher for hardware → break it".
//! - Shipping here for spec/interop interest and as a teaching example
//!   of how minor tweaks can be catastrophic.
//!
//! ## Test vector (3GPP TS 35.203 §4.1, "kasumi_testset_1")
//!
//! ```text
//! Key       = 2bd6459f82c5b300952c49104881ff48
//! Plaintext = ea024714ad5c4d84
//! Ciphertext= df1f9b251c0bf45f
//! ```
//!
//! ## Reference
//!
//! - **3GPP TS 35.202** ("Specification of the 3GPP confidentiality and
//!   integrity algorithms; Document 2: KASUMI Specification"), Annex 2.

// ── S-boxes (3GPP TS 35.202 Annex 2) ─────────────────────────────────

#[rustfmt::skip]
const S7: [u8; 128] = [
    54, 50, 62, 56, 22, 34, 94, 96, 38, 6, 63, 93, 2, 18, 123, 33,
    55, 113, 39, 114, 21, 67, 65, 12, 47, 73, 46, 27, 25, 111, 124, 81,
    53, 9, 121, 79, 52, 60, 58, 48, 101, 127, 40, 120, 104, 70, 71, 43,
    20, 122, 72, 61, 23, 109, 13, 100, 77, 1, 16, 7, 82, 10, 105, 98,
    117, 116, 76, 11, 89, 106, 0, 125, 118, 99, 86, 69, 30, 57, 126, 87,
    112, 51, 17, 5, 95, 14, 90, 84, 91, 8, 35, 103, 32, 97, 28, 66,
    102, 31, 26, 45, 75, 4, 85, 92, 37, 74, 80, 49, 68, 29, 115, 44,
    64, 107, 108, 24, 110, 83, 36, 78, 42, 19, 15, 41, 88, 119, 59, 3,
];

#[rustfmt::skip]
const S9: [u16; 512] = [
    167, 239, 161, 379, 391, 334,   9, 338,  38, 226,  48, 358, 452, 385,  90, 397,
    183, 253, 147, 331, 415, 340,  51, 362, 306, 500, 262,  82, 216, 159, 356, 177,
    175, 241, 489,  37, 206,  17,   0, 333,  44, 254, 378,  58, 143, 220,  81, 400,
     95,   3, 315, 245,  54, 235, 218, 405, 472, 264, 172, 494, 371, 290, 399,  76,
    165, 197, 395, 121, 257, 480, 423, 212, 240,  28, 462, 176, 406, 507, 288, 223,
    501, 407, 249, 265,  89, 186, 221, 428, 164,  74, 440, 196, 458, 421, 350, 163,
    232, 158, 134, 354,  13, 250, 491, 142, 191,  69, 193, 425, 152, 227, 366, 135,
    344, 300, 276, 242, 437, 320, 113, 278,  11, 243,  87, 317,  36,  93, 496,  27,
    487, 446, 482,  41,  68, 156, 457, 131, 326, 403, 339,  20,  39, 115, 442, 124,
    475, 384, 508,  53, 112, 170, 479, 151, 126, 169,  73, 268, 279, 321, 168, 364,
    363, 292,  46, 499, 393, 327, 324,  24, 456, 267, 157, 460, 488, 426, 309, 229,
    439, 506, 208, 271, 349, 401, 434, 236,  16, 209, 359,  52,  56, 120, 199, 277,
    465, 416, 252, 287, 246,   6,  83, 305, 420, 345, 153, 502,  65,  61, 244, 282,
    173, 222, 418,  67, 386, 368, 261, 101, 476, 291, 195, 430,  49,  79, 166, 330,
    280, 383, 373, 128, 382, 408, 155, 495, 367, 388, 274, 107, 459, 417,  62, 454,
    132, 225, 203, 316, 234,  14, 301,  91, 503, 286, 424, 211, 347, 307, 140, 374,
     35, 103, 125, 427,  19, 214, 453, 146, 498, 314, 444, 230, 256, 329, 198, 285,
     50, 116,  78, 410,  10, 205, 510, 171, 231,  45, 139, 467,  29,  86, 505,  32,
     72,  26, 342, 150, 313, 490, 431, 238, 411, 325, 149, 473,  40, 119, 174, 355,
    185, 233, 389,  71, 448, 273, 372,  55, 110, 178, 322,  12, 469, 392, 369, 190,
      1, 109, 375, 137, 181,  88,  75, 308, 260, 484,  98, 272, 370, 275, 412, 111,
    336, 318,   4, 504, 492, 259, 304,  77, 337, 435,  21, 357, 303, 332, 483,  18,
     47,  85,  25, 497, 474, 289, 100, 269, 296, 478, 270, 106,  31, 104, 433,  84,
    414, 486, 394,  96,  99, 154, 511, 148, 413, 361, 409, 255, 162, 215, 302, 201,
    266, 351, 343, 144, 441, 365, 108, 298, 251,  34, 182, 509, 138, 210, 335, 133,
    311, 352, 328, 141, 396, 346, 123, 319, 450, 281, 429, 228, 443, 481,  92, 404,
    485, 422, 248, 297,  23, 213, 130, 466,  22, 217, 283,  70, 294, 360, 419, 127,
    312, 377,   7, 468, 194,   2, 117, 295, 463, 258, 224, 447, 247, 187,  80, 398,
    284, 353, 105, 390, 299, 471, 470, 184,  57, 200, 348,  63, 204, 188,  33, 451,
     97,  30, 310, 219,  94, 160, 129, 493,  64, 179, 263, 102, 189, 207, 114, 402,
    438, 477, 387, 122, 192,  42, 381,   5, 145, 118, 180, 449, 293, 323, 136, 380,
     43,  66,  60, 455, 341, 445, 202, 432,   8, 237,  15, 376, 436, 464,  59, 461,
];

// ── 16-bit rotate left ───────────────────────────────────────────────

#[inline]
fn rol16(a: u16, b: u32) -> u16 {
    a.rotate_left(b)
}

// ── FI: 16-bit nonlinear function ────────────────────────────────────

#[inline]
fn fi(input: u16, subkey: u16) -> u16 {
    let mut nine: u16 = input >> 7;
    let mut seven: u16 = input & 0x7F;

    nine = S9[nine as usize] ^ seven;
    seven = (S7[seven as usize] as u16) ^ (nine & 0x7F);

    seven ^= subkey >> 9;
    nine ^= subkey & 0x1FF;

    nine = S9[nine as usize] ^ seven;
    seven = (S7[seven as usize] as u16) ^ (nine & 0x7F);

    (seven << 9) | nine
}

// ── FO: 32-bit Feistel-like using FI ─────────────────────────────────

#[inline]
fn fo(input: u32, ks: &KasumiKeys, index: usize) -> u32 {
    let mut left: u16 = (input >> 16) as u16;
    let mut right: u16 = input as u16;

    left ^= ks.koi1[index];
    left = fi(left, ks.kii1[index]);
    left ^= right;

    right ^= ks.koi2[index];
    right = fi(right, ks.kii2[index]);
    right ^= left;

    left ^= ks.koi3[index];
    left = fi(left, ks.kii3[index]);
    left ^= right;

    ((right as u32) << 16) | (left as u32)
}

// ── FL: 32-bit keyed linear layer ────────────────────────────────────

#[inline]
fn fl(input: u32, ks: &KasumiKeys, index: usize) -> u32 {
    let mut l: u16 = (input >> 16) as u16;
    let mut r: u16 = input as u16;

    let a = l & ks.kli1[index];
    r ^= rol16(a, 1);

    let b = r | ks.kli2[index];
    l ^= rol16(b, 1);

    ((l as u32) << 16) | (r as u32)
}

// ── Key schedule ──────────────────────────────────────────────────────

#[derive(Clone, Debug)]
struct KasumiKeys {
    kli1: [u16; 8],
    kli2: [u16; 8],
    koi1: [u16; 8],
    koi2: [u16; 8],
    koi3: [u16; 8],
    kii1: [u16; 8],
    kii2: [u16; 8],
    kii3: [u16; 8],
}

fn key_schedule(key: &[u8; 16]) -> KasumiKeys {
    const C: [u16; 8] = [
        0x0123, 0x4567, 0x89AB, 0xCDEF, 0xFEDC, 0xBA98, 0x7654, 0x3210,
    ];

    let mut k = [0u16; 8];
    for i in 0..8 {
        k[i] = u16::from_be_bytes([key[2 * i], key[2 * i + 1]]);
    }
    let mut kprime = [0u16; 8];
    for i in 0..8 {
        kprime[i] = k[i] ^ C[i];
    }

    let mut ks = KasumiKeys {
        kli1: [0; 8],
        kli2: [0; 8],
        koi1: [0; 8],
        koi2: [0; 8],
        koi3: [0; 8],
        kii1: [0; 8],
        kii2: [0; 8],
        kii3: [0; 8],
    };
    for n in 0..8 {
        ks.kli1[n] = rol16(k[n], 1);
        ks.kli2[n] = kprime[(n + 2) & 7];
        ks.koi1[n] = rol16(k[(n + 1) & 7], 5);
        ks.koi2[n] = rol16(k[(n + 5) & 7], 8);
        ks.koi3[n] = rol16(k[(n + 6) & 7], 13);
        ks.kii1[n] = kprime[(n + 4) & 7];
        ks.kii2[n] = kprime[(n + 3) & 7];
        ks.kii3[n] = kprime[(n + 7) & 7];
    }
    ks
}

#[derive(Clone, Debug)]
pub struct Kasumi {
    keys: KasumiKeys,
}

impl Kasumi {
    /// Construct a KASUMI cipher from a 128-bit key.
    pub fn new(key: &[u8; 16]) -> Self {
        Self {
            keys: key_schedule(key),
        }
    }

    /// Encrypt one 64-bit block in place.
    ///
    /// The 8 rounds are arranged in 4 pairs (odd round = FL then FO,
    /// even round = FO then FL), per 3GPP TS 35.202 Figure 1.
    pub fn encrypt_block(&self, block: &mut [u8; 8]) {
        let mut left = u32::from_be_bytes([block[0], block[1], block[2], block[3]]);
        let mut right = u32::from_be_bytes([block[4], block[5], block[6], block[7]]);

        let mut n = 0;
        // Loop 4 times: pair of rounds per iteration.
        loop {
            // Odd round (1, 3, 5, 7): apply FL then FO on the left half.
            let mut t = fl(left, &self.keys, n);
            t = fo(t, &self.keys, n);
            right ^= t;
            n += 1;

            // Even round (2, 4, 6, 8): apply FO then FL on the right half.
            let mut t = fo(right, &self.keys, n);
            t = fl(t, &self.keys, n);
            left ^= t;
            n += 1;

            if n > 7 {
                break;
            }
        }

        block[0..4].copy_from_slice(&left.to_be_bytes());
        block[4..8].copy_from_slice(&right.to_be_bytes());
    }

    /// Decrypt one 64-bit block in place.
    ///
    /// KASUMI is a Feistel cipher, so decryption runs the round
    /// schedule backwards.
    pub fn decrypt_block(&self, block: &mut [u8; 8]) {
        let mut left = u32::from_be_bytes([block[0], block[1], block[2], block[3]]);
        let mut right = u32::from_be_bytes([block[4], block[5], block[6], block[7]]);

        // Reverse round indices 7..0, pairing (n, n-1).
        let mut n = 7i32;
        loop {
            // Undo the (n-1, n) pair from encryption: the *last* round
            // (n=7, even-type "FO then FL on right") was XORed into left.
            let mut t = fo(right, &self.keys, n as usize);
            t = fl(t, &self.keys, n as usize);
            left ^= t;
            n -= 1;

            let mut t = fl(left, &self.keys, n as usize);
            t = fo(t, &self.keys, n as usize);
            right ^= t;
            n -= 1;

            if n < 0 {
                break;
            }
        }

        block[0..4].copy_from_slice(&left.to_be_bytes());
        block[4..8].copy_from_slice(&right.to_be_bytes());
    }
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    /// **3GPP TS 35.203 §4.1 "kasumi_testset_1"** — the canonical
    /// reference vector for the 3G F8 / F9 confidentiality and integrity
    /// algorithms.  Cross-checked against the 3GPP TS 35.202 sample C
    /// code and the `CryptoMobile/CM.py` Python implementation.
    #[test]
    fn kasumi_3gpp_testset_1() {
        let key: [u8; 16] = [
            0x2b, 0xd6, 0x45, 0x9f, 0x82, 0xc5, 0xb3, 0x00, 0x95, 0x2c, 0x49, 0x10, 0x48, 0x81,
            0xff, 0x48,
        ];
        let mut block: [u8; 8] = [0xea, 0x02, 0x47, 0x14, 0xad, 0x5c, 0x4d, 0x84];
        let expected: [u8; 8] = [0xdf, 0x1f, 0x9b, 0x25, 0x1c, 0x0b, 0xf4, 0x5f];
        let c = Kasumi::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, expected);
    }

    /// Decryption recovers the plaintext.
    #[test]
    fn kasumi_3gpp_testset_1_decrypt() {
        let key: [u8; 16] = [
            0x2b, 0xd6, 0x45, 0x9f, 0x82, 0xc5, 0xb3, 0x00, 0x95, 0x2c, 0x49, 0x10, 0x48, 0x81,
            0xff, 0x48,
        ];
        let plain: [u8; 8] = [0xea, 0x02, 0x47, 0x14, 0xad, 0x5c, 0x4d, 0x84];
        let mut block: [u8; 8] = [0xdf, 0x1f, 0x9b, 0x25, 0x1c, 0x0b, 0xf4, 0x5f];
        let c = Kasumi::new(&key);
        c.decrypt_block(&mut block);
        assert_eq!(block, plain);
    }

    /// **3GPP TS 35.203 §4.1 "kasumi_testset_2"** — second published
    /// reference vector.
    #[test]
    fn kasumi_3gpp_testset_2() {
        let key: [u8; 16] = [
            0x8c, 0xe3, 0x3e, 0x2c, 0xc3, 0xc0, 0xb5, 0xfc, 0x1f, 0x3d, 0xe8, 0xa6, 0xdc, 0x66,
            0xb1, 0xf3,
        ];
        let mut block: [u8; 8] = [0xd3, 0xc5, 0xd5, 0x92, 0x32, 0x7f, 0xb1, 0x1c];
        let expected: [u8; 8] = [0xde, 0x55, 0x19, 0x88, 0xce, 0xb2, 0xf9, 0xb7];
        let c = Kasumi::new(&key);
        c.encrypt_block(&mut block);
        assert_eq!(block, expected);
    }

    /// Encrypt → decrypt round-trip across many inputs.
    #[test]
    fn kasumi_round_trip() {
        let key = [0xA5u8; 16];
        let c = Kasumi::new(&key);
        for v in 0u64..64 {
            let p = v.wrapping_mul(0x0123_4567_89AB_CDEF).to_be_bytes();
            let mut b = p;
            c.encrypt_block(&mut b);
            c.decrypt_block(&mut b);
            assert_eq!(b, p);
        }
    }
}
