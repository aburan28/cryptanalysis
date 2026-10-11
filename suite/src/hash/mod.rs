//! Hash functions and hash-based MACs.
//!
//! ## SHA family
//! - **SHA-1** (`sha1`) — FIPS 180-4 §6.1 (broken by SHAttered 2017)
//! - **SHA-256 / SHA-224** (`sha256`)
//! - **SHA-512 / SHA-384 / SHA-512/224 / SHA-512/256** (`sha512`)
//! - **SHA-3 / Keccak**, **SHAKE128 / SHAKE256** (`sha3`)
//!
//! ## BLAKE family
//! - **BLAKE2b** (`blake2b`), **BLAKE2s** (`blake2s`) — RFC 7693
//! - **BLAKE3** (`blake3`)
//!
//! ## Skein
//! - **Skein-256 / -512 / -1024** (`skein`) — UBI mode over Threefish
//!
//! ## National / regional
//! - **SM3** (`sm3`) — GB/T 32905-2016 (China)
//! - **Streebog** (`streebog`) — GOST R 34.11-2012 (Russia)
//! - **Whirlpool** (`whirlpool`) — NESSIE, ISO/IEC 10118-3
//! - **Tiger / Tiger2** (`tiger`) — Anderson-Biham 1995
//!
//! ## Compact / specialised
//! - **RIPEMD-160** (`ripemd160`) — Bitcoin address derivation
//! - **SipHash** (`siphash`) — keyed short-input hash for hash tables
//!
//! ## Classic broken (Merkle-Damgård study targets)
//! - **MD4** (`md4`), **MD5** (`md5`)
//!
//! ## MACs and customised XOFs
//! - **HMAC** (`hmac`) — RFC 2104, generic over any hash function
//! - **KMAC128 / KMAC256** (`kmac`) — NIST SP 800-185
//! - **cSHAKE128 / cSHAKE256** (`cshake`) — NIST SP 800-185

pub mod blake2b;
pub mod blake2s;
pub mod blake3;
pub mod cshake;
pub mod hmac;
pub mod kmac;
pub mod md4;
pub mod md5;
pub mod ripemd160;
pub mod sha1;
pub mod sha256;
pub mod sha3;
pub mod sha512;
pub mod siphash;
pub mod skein;
pub mod sm3;
pub mod streebog;
pub mod tiger;
pub mod visualize;
pub mod whirlpool;

pub use blake2b::{blake2b, blake2b_keyed};
pub use blake2s::{blake2s, blake2s_keyed};
pub use blake3::{blake3_derive_key, blake3_hash, blake3_keyed};
pub use cshake::{cshake128, cshake256};
pub use hmac::{
    hmac_blake2b, hmac_sha1, hmac_sha256, hmac_sha384, hmac_sha512, hmac_verify_ct, hmac_with,
};
pub use kmac::{kmac128, kmac256, kmacxof128, kmacxof256};
pub use md4::{md4, md4_compress, md4_pad};
pub use md5::{md5, md5_pad};
pub use ripemd160::{hash160, ripemd160};
pub use sha1::sha1;
pub use sha256::{sha224, sha256};
pub use sha3::{sha3_256, sha3_512, shake128, shake256};
pub use sha512::{sha384, sha512, sha512_224, sha512_256};
pub use siphash::{siphash, SipKey};
pub use skein::{skein1024, skein256, skein512};
pub use sm3::{sm3, Sm3};
pub use streebog::{streebog_256, streebog_512, Streebog};
pub use tiger::{tiger, tiger2};
pub use whirlpool::whirlpool;
