//! HOTP / TOTP — HMAC-based and Time-based One-Time Passwords
//! (RFC 4226 and RFC 6238).
//!
//! The de facto standard for two-factor authentication: Google Authenticator,
//! Authy, 1Password, Duo, etc. all speak this protocol.  A device and a
//! server share a symmetric `secret` and agree on a counter (HOTP) or a
//! Unix-time-derived counter (TOTP); both sides compute HMAC over that
//! counter and dynamically truncate to a short decimal code.
//!
//! # Algorithm (RFC 4226 §5.3)
//! ```text
//!   HS       = HMAC(secret, counter as 8-byte big-endian)
//!   offset   = HS[last] & 0x0F
//!   bin_code = (HS[offset] & 0x7F) << 24
//!            |  HS[offset+1]        << 16
//!            |  HS[offset+2]        << 8
//!            |  HS[offset+3]
//!   HOTP     = bin_code mod 10^digits
//! ```
//!
//! TOTP is HOTP with `counter = (unix_seconds - T0) / step`, where T0 = 0
//! and step defaults to 30 seconds (RFC 6238 §4).

use std::time::{SystemTime, UNIX_EPOCH};

use crate::hash::hmac::{hmac_sha1, hmac_sha256, hmac_sha512};

const DEFAULT_STEP: u64 = 30;

/// Dynamic-truncation step shared by all HOTP flavours.
fn truncate(hs: &[u8], digits: u32) -> u32 {
    assert!((6..=10).contains(&digits), "HOTP digits must be 6..=10");
    let offset = (hs[hs.len() - 1] & 0x0F) as usize;
    let bin_code = ((hs[offset] & 0x7F) as u32) << 24
        | (hs[offset + 1] as u32) << 16
        | (hs[offset + 2] as u32) << 8
        | (hs[offset + 3] as u32);
    // 10^10 overflows u32; compute modulus in u64 then narrow.  bin_code's
    // high bit is masked off so it fits in 31 bits — the result of `% 10^10`
    // is always ≤ bin_code < 2^31 < u32::MAX.
    let modulus = 10u64.pow(digits);
    (bin_code as u64 % modulus) as u32
}

// ── HOTP (RFC 4226) ──────────────────────────────────────────────────────────

/// HOTP using HMAC-SHA-1 — the original spec, still the most widely deployed.
pub fn hotp_sha1(secret: &[u8], counter: u64, digits: u32) -> u32 {
    let hs = hmac_sha1(secret, &counter.to_be_bytes());
    truncate(&hs, digits)
}

/// HOTP using HMAC-SHA-256.
pub fn hotp_sha256(secret: &[u8], counter: u64, digits: u32) -> u32 {
    let hs = hmac_sha256(secret, &counter.to_be_bytes());
    truncate(&hs, digits)
}

/// HOTP using HMAC-SHA-512.
pub fn hotp_sha512(secret: &[u8], counter: u64, digits: u32) -> u32 {
    let hs = hmac_sha512(secret, &counter.to_be_bytes());
    truncate(&hs, digits)
}

// ── TOTP (RFC 6238) ──────────────────────────────────────────────────────────

/// TOTP using HMAC-SHA-1.  `step` is typically 30 seconds; T0 is fixed to 0.
pub fn totp_sha1(secret: &[u8], unix_seconds: u64, step: u64, digits: u32) -> u32 {
    hotp_sha1(secret, unix_seconds / step, digits)
}

/// TOTP using HMAC-SHA-256.
pub fn totp_sha256(secret: &[u8], unix_seconds: u64, step: u64, digits: u32) -> u32 {
    hotp_sha256(secret, unix_seconds / step, digits)
}

/// TOTP using HMAC-SHA-512.
pub fn totp_sha512(secret: &[u8], unix_seconds: u64, step: u64, digits: u32) -> u32 {
    hotp_sha512(secret, unix_seconds / step, digits)
}

fn now_unix_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system clock before Unix epoch")
        .as_secs()
}

/// TOTP-SHA-1 at the current wall-clock time, 30-second step, 6 digits —
/// the Google Authenticator default.
pub fn totp_now_sha1(secret: &[u8]) -> u32 {
    totp_sha1(secret, now_unix_seconds(), DEFAULT_STEP, 6)
}

/// TOTP-SHA-256 at the current wall-clock time, 30-second step, 6 digits.
pub fn totp_now_sha256(secret: &[u8]) -> u32 {
    totp_sha256(secret, now_unix_seconds(), DEFAULT_STEP, 6)
}

/// TOTP-SHA-512 at the current wall-clock time, 30-second step, 6 digits.
pub fn totp_now_sha512(secret: &[u8]) -> u32 {
    totp_sha512(secret, now_unix_seconds(), DEFAULT_STEP, 6)
}

#[cfg(test)]
mod tests {
    use super::*;

    // RFC 4226 §5.1 reference key.
    const HOTP_SECRET: &[u8] = b"12345678901234567890";

    // RFC 6238 Appendix B reference keys (ASCII).
    const TOTP_KEY_SHA1: &[u8] = b"12345678901234567890";
    const TOTP_KEY_SHA256: &[u8] = b"12345678901234567890123456789012";
    const TOTP_KEY_SHA512: &[u8] =
        b"1234567890123456789012345678901234567890123456789012345678901234";

    // ── HOTP RFC 4226 Appendix D ─────────────────────────────────────────────

    #[test]
    fn hotp_sha1_rfc4226_vectors() {
        let expected = [
            755224, 287082, 359152, 969429, 338314, 254676, 287922, 162583, 399871, 520489,
        ];
        for (counter, code) in expected.iter().enumerate() {
            assert_eq!(hotp_sha1(HOTP_SECRET, counter as u64, 6), *code);
        }
    }

    // ── TOTP RFC 6238 Appendix B ─────────────────────────────────────────────

    #[test]
    fn totp_sha1_rfc6238_vectors() {
        let cases: &[(u64, u32)] = &[
            (59, 94287082),
            (1111111109, 7081804),
            (1111111111, 14050471),
            (1234567890, 89005924),
            (2000000000, 69279037),
            (20000000000, 65353130),
        ];
        for &(t, code) in cases {
            assert_eq!(totp_sha1(TOTP_KEY_SHA1, t, 30, 8), code);
        }
    }

    #[test]
    fn totp_sha256_rfc6238_vectors() {
        let cases: &[(u64, u32)] = &[
            (59, 46119246),
            (1111111109, 68084774),
            (1111111111, 67062674),
            (1234567890, 91819424),
            (2000000000, 90698825),
            (20000000000, 77737706),
        ];
        for &(t, code) in cases {
            assert_eq!(totp_sha256(TOTP_KEY_SHA256, t, 30, 8), code);
        }
    }

    #[test]
    fn totp_sha512_rfc6238_vectors() {
        let cases: &[(u64, u32)] = &[
            (59, 90693936),
            (1111111109, 25091201),
            (1111111111, 99943326),
            (1234567890, 93441116),
            (2000000000, 38618901),
            (20000000000, 47863826),
        ];
        for &(t, code) in cases {
            assert_eq!(totp_sha512(TOTP_KEY_SHA512, t, 30, 8), code);
        }
    }

    // ── Sanity / shape ───────────────────────────────────────────────────────

    #[test]
    fn hotp_respects_digit_count() {
        for d in 6u32..=9 {
            let code = hotp_sha1(HOTP_SECRET, 0, d);
            assert!(code < 10u32.pow(d));
        }
        // 10-digit codes can exceed 10^9; verify they fit the u32 return.
        let _ = hotp_sha1(HOTP_SECRET, 0, 10);
    }

    #[test]
    fn totp_step_changes_counter() {
        // Two timestamps within the same 30-s window produce identical codes.
        // 1_000_000_020 is on a 30-s boundary, so +0 and +29 share a window.
        let a = totp_sha1(TOTP_KEY_SHA1, 1_000_000_020, 30, 6);
        let b = totp_sha1(TOTP_KEY_SHA1, 1_000_000_049, 30, 6);
        assert_eq!(a, b);
        // Crossing into the next window changes the code.
        let c = totp_sha1(TOTP_KEY_SHA1, 1_000_000_050, 30, 6);
        assert_ne!(a, c);
    }

    #[test]
    fn totp_now_runs() {
        // Just smoke-test that the wall-clock helper produces a 6-digit code.
        let code = totp_now_sha1(b"any-secret");
        assert!(code < 1_000_000);
    }
}
