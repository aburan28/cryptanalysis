//! SipHash-2-4 — keyed PRF for hashtable DoS resistance.
//!
//! Aumasson & Bernstein, "SipHash: a fast short-input PRF" (Indocrypt
//! 2012).  Used by Rust's `std::collections::HashMap`, the Linux
//! kernel, Bitcoin's compact-block relay, Perl, Python, OpenDNS,
//! Redis ... a real production primitive.
//!
//! # Why ship this
//!
//! Filling the keyed-PRF gap.  HMAC-SHA-256 is a keyed PRF too but
//! is heavyweight; SipHash is `O(1)` setup and very fast on small
//! inputs (cache-line-sized keys, two 64-bit words of state).
//! 64-bit output is the canonical variant ("SipHash-2-4-64").

/// 16-byte key for SipHash-2-4.  Two 64-bit halves k0, k1.
#[derive(Clone, Copy, Debug)]
pub struct SipKey(pub [u8; 16]);

/// SipHash-2-4 of `data` under 16-byte `key`.  Returns a 64-bit hash.
pub fn siphash(key: &SipKey, data: &[u8]) -> u64 {
    let k0 = u64::from_le_bytes(key.0[..8].try_into().unwrap());
    let k1 = u64::from_le_bytes(key.0[8..].try_into().unwrap());

    let mut v0 = k0 ^ 0x736f6d6570736575;
    let mut v1 = k1 ^ 0x646f72616e646f6d;
    let mut v2 = k0 ^ 0x6c7967656e657261;
    let mut v3 = k1 ^ 0x7465646279746573;

    let len = data.len();
    let last_byte = (len as u64 & 0xff) << 56;
    let n_full = len & !7;

    // Compress full 8-byte blocks (2 SipRounds per block).
    for chunk_start in (0..n_full).step_by(8) {
        let m = u64::from_le_bytes(data[chunk_start..chunk_start + 8].try_into().unwrap());
        v3 ^= m;
        sip_round(&mut v0, &mut v1, &mut v2, &mut v3);
        sip_round(&mut v0, &mut v1, &mut v2, &mut v3);
        v0 ^= m;
    }

    // Final chunk: pack remaining bytes + length-LSB into a u64.
    let mut last = last_byte;
    for (i, &b) in data[n_full..].iter().enumerate() {
        last |= (b as u64) << (8 * i);
    }
    v3 ^= last;
    sip_round(&mut v0, &mut v1, &mut v2, &mut v3);
    sip_round(&mut v0, &mut v1, &mut v2, &mut v3);
    v0 ^= last;

    // Finalisation: 4 SipRounds.
    v2 ^= 0xff;
    sip_round(&mut v0, &mut v1, &mut v2, &mut v3);
    sip_round(&mut v0, &mut v1, &mut v2, &mut v3);
    sip_round(&mut v0, &mut v1, &mut v2, &mut v3);
    sip_round(&mut v0, &mut v1, &mut v2, &mut v3);

    v0 ^ v1 ^ v2 ^ v3
}

#[inline]
fn sip_round(v0: &mut u64, v1: &mut u64, v2: &mut u64, v3: &mut u64) {
    *v0 = v0.wrapping_add(*v1);
    *v1 = v1.rotate_left(13);
    *v1 ^= *v0;
    *v0 = v0.rotate_left(32);
    *v2 = v2.wrapping_add(*v3);
    *v3 = v3.rotate_left(16);
    *v3 ^= *v2;
    *v0 = v0.wrapping_add(*v3);
    *v3 = v3.rotate_left(21);
    *v3 ^= *v0;
    *v2 = v2.wrapping_add(*v1);
    *v1 = v1.rotate_left(17);
    *v1 ^= *v2;
    *v2 = v2.rotate_left(32);
}

#[cfg(test)]
mod tests {
    use super::*;

    /// **Reference test vectors from the SipHash paper appendix
    /// (Aumasson-Bernstein 2012)**: key = 00..0F, then `siphash(i)`
    /// for `i = 0..63` is the corresponding entry.  We check the
    /// first three.
    #[test]
    fn siphash_test_vectors() {
        let key = SipKey([
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f,
        ]);
        // Empty input.
        assert_eq!(siphash(&key, &[]), 0x726fdb47dd0e0e31);
        // 1-byte input [0x00].
        assert_eq!(siphash(&key, &[0x00]), 0x74f839c593dc67fd);
        // 2-byte input [0x00, 0x01].
        assert_eq!(siphash(&key, &[0x00, 0x01]), 0x0d6c8009d9a94f5a);
    }

    /// Different keys → different outputs.
    #[test]
    fn key_separation() {
        let k1 = SipKey([0u8; 16]);
        let k2 = SipKey([1u8; 16]);
        let h1 = siphash(&k1, b"hello");
        let h2 = siphash(&k2, b"hello");
        assert_ne!(h1, h2);
    }

    /// Empty + null-key edge case (also a published vector).
    #[test]
    fn empty_input_with_test_key() {
        let key = SipKey([
            0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d,
            0x0e, 0x0f,
        ]);
        assert_eq!(siphash(&key, b""), 0x726fdb47dd0e0e31);
    }
}
