//! A fast, non-cryptographic hasher for the Gröbner engines' internal maps.
//!
//! The F4 engines key hash maps by monomials — packed `u64` masks or
//! exponent vectors — built and dropped inside one run.  Nothing
//! adversarial reaches those maps, so the DoS resistance of the standard
//! library's SipHash buys nothing there, and its per-key cost is paid on
//! every term of every row packed.  This is the multiply-rotate scheme of
//! `FxHash` (rustc's hasher): one rotate, one XOR and one multiply per word.

use std::collections::{HashMap, HashSet};
use std::hash::{BuildHasherDefault, Hasher};

#[derive(Default, Clone, Copy)]
pub(crate) struct FxHasher(u64);

impl Hasher for FxHasher {
    #[inline]
    fn write(&mut self, bytes: &[u8]) {
        for chunk in bytes.chunks(8) {
            let mut w = [0u8; 8];
            w[..chunk.len()].copy_from_slice(chunk);
            self.write_u64(u64::from_le_bytes(w));
        }
    }
    #[inline]
    fn write_u32(&mut self, x: u32) {
        self.write_u64(x as u64);
    }
    #[inline]
    fn write_u64(&mut self, x: u64) {
        self.0 = (self.0.rotate_left(5) ^ x).wrapping_mul(0x51_7c_c1_b7_27_22_0a_95);
    }
    #[inline]
    fn write_usize(&mut self, x: usize) {
        self.write_u64(x as u64);
    }
    #[inline]
    fn finish(&self) -> u64 {
        self.0
    }
}

pub(crate) type FxBuild = BuildHasherDefault<FxHasher>;
pub(crate) type FxMap<K, V> = HashMap<K, V, FxBuild>;
pub(crate) type FxSet<K> = HashSet<K, FxBuild>;

/// A hasher for maps keyed by one monomial mask.
///
/// [`FxHasher`] on a single word is `x · K`, whose low bits are no better
/// mixed than `x`'s own: a mask with `t` trailing zero bits hashes to a value
/// with at least `t`.  The table picks a bucket from the low bits, so the
/// monomials of a system in which the low-index variables do not occur — the
/// tail links of a chained decomposition, every row a support-local root
/// builds for them — crowd into a few buckets and every lookup probes a long
/// run.  The splitmix64 finaliser spreads every input bit over every output
/// bit.  It is the hasher the inherited engine's cached column layouts have
/// always used; a lookup returns what it would under any other hash.
#[derive(Default, Clone, Copy)]
pub(crate) struct MaskHasher(u64);

impl Hasher for MaskHasher {
    #[inline]
    fn finish(&self) -> u64 {
        self.0
    }

    fn write(&mut self, bytes: &[u8]) {
        let mut value = 0xcbf29ce484222325u64;
        for &byte in bytes {
            value = (value ^ u64::from(byte)).wrapping_mul(0x100000001b3);
        }
        self.write_u64(value);
    }

    #[inline]
    fn write_u64(&mut self, value: u64) {
        let mut mixed = value.wrapping_add(0x9e3779b97f4a7c15);
        mixed = (mixed ^ (mixed >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
        mixed = (mixed ^ (mixed >> 27)).wrapping_mul(0x94d049bb133111eb);
        self.0 = mixed ^ (mixed >> 31);
    }
}

/// Monomial mask → value, hashed by [`MaskHasher`].
pub(crate) type MaskMap<V> = HashMap<u64, V, BuildHasherDefault<MaskHasher>>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn maps_behave_like_std_maps() {
        let mut m: FxMap<Vec<u32>, u64> = FxMap::default();
        let mut s: FxSet<u64> = FxSet::default();
        for i in 0..10_000u64 {
            m.insert(vec![i as u32, (i * 7) as u32, 3], i);
            s.insert(i << 20);
        }
        assert_eq!(m.len(), 10_000);
        assert_eq!(s.len(), 10_000);
        for i in 0..10_000u64 {
            assert_eq!(m[&vec![i as u32, (i * 7) as u32, 3]], i);
            assert!(s.contains(&(i << 20)));
        }
    }

    #[test]
    fn mask_hash_spreads_masks_without_low_bits() {
        // Masks over variables 20..34 only: under `FxHasher` every hash
        // has twenty trailing zeros; under `MaskHasher` the low byte of
        // the hashes takes most of its 256 values.
        use std::hash::BuildHasher;
        let build = BuildHasherDefault::<MaskHasher>::default();
        let low: HashSet<u64> = (0..4096u64)
            .map(|i| build.hash_one(i << 20) & 0xff)
            .collect();
        assert!(low.len() > 200, "{}", low.len());
        let mut m: MaskMap<usize> = MaskMap::default();
        for i in 0..4096u64 {
            m.insert(i << 20, i as usize);
        }
        assert!((0..4096u64).all(|i| m[&(i << 20)] == i as usize));
    }
}
