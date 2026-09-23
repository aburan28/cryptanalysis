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
}
