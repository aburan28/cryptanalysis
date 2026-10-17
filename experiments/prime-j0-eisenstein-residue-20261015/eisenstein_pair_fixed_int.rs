//! Signed, bounded 512-bit integers for exact Eisenstein ideal reduction.
//! Every arithmetic overflow is an explicit failure; field callers keep
//! reduced coordinates below 2^128 and raw products below 2^384.
use std::cmp::Ordering;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct I512 {
    pub negative: bool,
    pub limbs: [u64; 8],
}

impl I512 {
    pub const ZERO: Self = Self { negative: false, limbs: [0; 8] };
    pub const ONE: Self = Self { negative: false, limbs: [1, 0, 0, 0, 0, 0, 0, 0] };

    pub fn from_u128(value: u128) -> Self {
        let mut limbs = [0; 8];
        limbs[0] = value as u64;
        limbs[1] = (value >> 64) as u64;
        Self { negative: false, limbs }
    }

    pub fn from_hex(s: &str) -> Self {
        let (negative, digits) = if let Some(rest) = s.strip_prefix('-') {
            (true, rest)
        } else { (false, s) };
        let mut out = Self::ZERO;
        for ch in digits.bytes() {
            let nibble = (ch as char).to_digit(16).expect("hex digit") as u64;
            out = out.shl_bits(4).add(Self::from_u128(nibble as u128));
        }
        if negative { out.neg() } else { out }
    }

    pub fn is_zero(self) -> bool { self.limbs.iter().all(|&word| word == 0) }
    pub fn used(self) -> usize {
        self.limbs.iter().rposition(|&word| word != 0).map_or(0, |i| i+1)
    }
    pub fn neg(mut self) -> Self {
        if !self.is_zero() { self.negative = !self.negative; }
        self
    }
    pub fn abs(mut self) -> Self { self.negative = false; self }
    pub fn cmp_abs(self, rhs: Self) -> Ordering {
        for i in (0..8).rev() {
            match self.limbs[i].cmp(&rhs.limbs[i]) {
                Ordering::Equal => (), different => return different,
            }
        }
        Ordering::Equal
    }
    pub fn cmp_signed(self, rhs: Self) -> Ordering {
        match (self.negative, rhs.negative) {
            (false, true) => Ordering::Greater,
            (true, false) => Ordering::Less,
            (false, false) => self.cmp_abs(rhs),
            (true, true) => rhs.cmp_abs(self),
        }
    }
    fn normalized(mut self) -> Self {
        if self.is_zero() { self.negative = false; }
        self
    }
    fn add_abs(self, rhs: Self) -> Self {
        let mut out = [0; 8];
        let mut carry = 0u128;
        for i in 0..8 {
            let sum = self.limbs[i] as u128 + rhs.limbs[i] as u128 + carry;
            out[i] = sum as u64;
            carry = sum >> 64;
        }
        assert_eq!(carry, 0, "I512 addition overflow");
        Self { negative: false, limbs: out }
    }
    fn sub_abs(self, rhs: Self) -> Self {
        assert!(self.cmp_abs(rhs) != Ordering::Less);
        let mut out = [0; 8];
        let mut borrow = false;
        for i in 0..8 {
            let (first, b1) = self.limbs[i].overflowing_sub(rhs.limbs[i]);
            let (next, b2) = first.overflowing_sub(borrow as u64);
            out[i] = next;
            borrow = b1 || b2;
        }
        assert!(!borrow);
        Self { negative: false, limbs: out }
    }
    pub fn add(self, rhs: Self) -> Self {
        if self.negative == rhs.negative {
            let mut result = self.add_abs(rhs);
            result.negative = self.negative;
            result.normalized()
        } else {
            match self.cmp_abs(rhs) {
                Ordering::Greater => {
                    let mut result = self.sub_abs(rhs);
                    result.negative = self.negative;
                    result.normalized()
                }
                Ordering::Less => {
                    let mut result = rhs.sub_abs(self);
                    result.negative = rhs.negative;
                    result.normalized()
                }
                Ordering::Equal => Self::ZERO,
            }
        }
    }
    pub fn sub(self, rhs: Self) -> Self { self.add(rhs.neg()) }
    pub fn mul(self, rhs: Self) -> Self {
        let n = self.used();
        let m = rhs.used();
        if n == 0 || m == 0 { return Self::ZERO; }
        assert!(n+m <= 8, "I512 multiplication width exceeded");
        let mut out = [0u64; 8];
        for i in 0..n {
            let mut carry = 0u128;
            for j in 0..m {
                let k = i+j;
                let sum = self.limbs[i] as u128 * rhs.limbs[j] as u128
                        + out[k] as u128 + carry;
                out[k] = sum as u64;
                carry = sum >> 64;
            }
            let mut k = i+m;
            while carry != 0 {
                assert!(k < 8, "I512 multiplication overflow");
                let sum = out[k] as u128 + carry;
                out[k] = sum as u64;
                carry = sum >> 64;
                k += 1;
            }
        }
        Self { negative: self.negative != rhs.negative, limbs: out }.normalized()
    }
    pub fn shl_bits(self, bits: usize) -> Self {
        if self.is_zero() { return self; }
        let words = bits / 64;
        let shift = bits % 64;
        assert!(words < 8);
        let mut out = [0; 8];
        for i in 0..8 {
            if self.limbs[i] == 0 { continue; }
            assert!(i+words < 8, "I512 shift overflow");
            out[i+words] |= self.limbs[i] << shift;
            if shift != 0 {
                let carry = self.limbs[i] >> (64-shift);
                if carry != 0 {
                    assert!(i+words+1 < 8, "I512 shift overflow");
                    out[i+words+1] |= carry;
                }
            }
        }
        Self { negative: self.negative, limbs: out }
    }
    pub fn shr256_floor(self) -> Self {
        let mut out = [0; 8];
        out[..4].copy_from_slice(&self.limbs[4..8]);
        let truncated = Self { negative: self.negative, limbs: out }.normalized();
        if self.negative && self.limbs[..4].iter().any(|&word| word != 0) {
            truncated.sub(Self::ONE)
        } else { truncated }
    }
    pub fn fits_signed_magnitude128(self) -> bool {
        self.limbs[2..].iter().all(|&word| word == 0)
    }
    pub fn abs_u128(self) -> u128 {
        assert!(self.fits_signed_magnitude128());
        self.limbs[0] as u128 | ((self.limbs[1] as u128) << 64)
    }
}

#[cfg(test)]
mod tests {
    use super::I512;
    use num_bigint::{BigInt, Sign};

    fn to_big(value: I512) -> BigInt {
        let mut bytes = Vec::with_capacity(64);
        for limb in value.limbs { bytes.extend_from_slice(&limb.to_le_bytes()); }
        BigInt::from_bytes_le(if value.negative { Sign::Minus } else { Sign::Plus }, &bytes)
    }
    fn next(state: &mut u64) -> u64 {
        *state ^= *state << 13;
        *state ^= *state >> 7;
        *state ^= *state << 17;
        *state
    }
    fn sample(state: &mut u64) -> I512 {
        let mut limbs=[0;8];
        for limb in limbs.iter_mut().take(4) { *limb=next(state); }
        I512 { negative:next(state)&1 != 0, limbs }
    }
    #[test]
    fn signed_limb_operations_match_bigint() {
        let mut state=0x932e_834b_203f_62c7;
        for _ in 0..20_000 {
            let a=sample(&mut state);
            let b=sample(&mut state);
            let x=to_big(a);
            let y=to_big(b);
            assert_eq!(to_big(a.add(b)),&x+&y);
            assert_eq!(to_big(a.sub(b)),&x-&y);
            assert_eq!(to_big(a.mul(b)),&x*&y);
            for shift in [0usize,1,63,64,127,128,256] {
                assert_eq!(to_big(a.shl_bits(shift)),&x<<shift);
            }
            assert_eq!(to_big(a.shr256_floor()),x>>256usize);
        }
    }
}
