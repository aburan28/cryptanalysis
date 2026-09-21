//! Elliptic curve cryptography: field arithmetic, point operations,
//! key generation, ECDSA, and ECDH over secp256k1 / P-256.

pub mod barrett_ecdsa;
pub mod ct;
pub mod curve;
pub mod curve25519;
pub mod curve_zoo;
pub mod ec_kcdsa;
pub mod ecdh;
pub mod ecdsa;
pub mod ed25519;
pub mod ed448;
pub mod field;
pub mod gost_3410_2012;
pub mod keys;
pub mod p256_field;
pub mod p256_point;
pub mod point;
pub mod schnorr;
pub mod secp256k1_field;
pub mod secp256k1_point;
pub mod sm2;
pub mod visualize;
pub mod x25519;
pub mod x448;

pub use curve::CurveParams;
pub use ec_kcdsa::{
    public_key_from_private as ec_kcdsa_public_key, sign as ec_kcdsa_sign,
    verify as ec_kcdsa_verify, EcKcdsaSignature,
};
pub use ecdh::{ecdh, ecdh_raw};
pub use ecdsa::{sign, sign_hash, verify, verify_hash, EcdsaSignature};
pub use ed25519::{ed25519_pubkey, ed25519_sign, ed25519_verify};
pub use ed448::{ed448_keygen, ed448_sign, ed448_verify};
pub use field::FieldElement;
pub use gost_3410_2012::{
    sign as gost_sign, sign_hash as gost_sign_hash, sign_hash_with_k as gost_sign_hash_with_k,
    verify as gost_verify, verify_hash as gost_verify_hash, DigestBits as GostDigestBits,
    GostSignature,
};
pub use keys::{EccKeyPair, EccPrivateKey, EccPublicKey};
pub use point::Point;
pub use schnorr::{schnorr_keypair, schnorr_sign, schnorr_verify, tagged_hash, xonly_pubkey};
pub use sm2::{
    decrypt as sm2_decrypt, encrypt as sm2_encrypt, sign as sm2_sign, verify as sm2_verify,
    za as sm2_za, Sm2Signature, DEFAULT_ID as SM2_DEFAULT_ID,
};
pub use x25519::{clamp, x25519, x25519_base};
pub use x448::{x448, x448_keygen};
