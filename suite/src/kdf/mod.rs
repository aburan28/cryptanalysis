//! Key derivation and password-hashing functions.
//!
//! - **HKDF** (`hkdf`) — RFC 5869, extract-then-expand on HMAC-SHA-256.
//! - **HMAC-DRBG** (`hmac_drbg`) — NIST SP 800-90A deterministic RNG.
//! - **PBKDF2** (`pbkdf2`) — RFC 8018, iterated HMAC.
//! - **scrypt** (`scrypt`) — RFC 7914, memory-hard via ROMix on Salsa20/8.
//! - **bcrypt** (`bcrypt`) — Provos-Mazières 1999, expensive Blowfish-style key schedule.
//! - **Argon2** (`argon2`) — RFC 9106, PHC winner; Argon2d / Argon2i / Argon2id.
//! - **HOTP / TOTP** (`hotp`) — RFC 4226 / RFC 6238, the 2FA standard.

pub mod argon2;
pub mod bcrypt;
pub mod hkdf;
pub mod hmac_drbg;
pub mod hotp;
pub mod pbkdf2;
pub mod scrypt;

pub use argon2::{argon2, argon2id, Argon2Variant};
pub use bcrypt::{bcrypt, bcrypt_hash, bcrypt_verify};
pub use hkdf::{
    hkdf, hkdf_blake2b, hkdf_expand, hkdf_expand_with, hkdf_extract, hkdf_extract_with, hkdf_sha1,
    hkdf_sha384, hkdf_sha512, hkdf_with, hmac_sha256,
};
pub use hmac_drbg::{drbg_expand, HmacDrbg};
pub use hotp::{
    hotp_sha1, hotp_sha256, hotp_sha512, totp_now_sha1, totp_now_sha256, totp_now_sha512,
    totp_sha1, totp_sha256, totp_sha512,
};
pub use pbkdf2::pbkdf2_hmac_sha256;
pub use scrypt::scrypt;
