//! Asymmetric cryptography: RSA, plus three partially-homomorphic
//! encryption schemes — Paillier (additive over `Z_n²`),
//! ElGamal (multiplicative over `Z_p*`), and EC-ElGamal
//! (additive over an elliptic curve).

pub mod ec_elgamal;
pub mod elgamal;
pub mod paillier;
pub mod rsa;

pub use ec_elgamal::{
    ec_elgamal_add, ec_elgamal_add_plain, ec_elgamal_decrypt, ec_elgamal_decrypt_bounded,
    ec_elgamal_decrypt_point, ec_elgamal_encrypt, ec_elgamal_keygen, ec_elgamal_mul_scalar,
    EcElGamalCiphertext, EcElGamalPrivateKey, EcElGamalPublicKey,
};
pub use elgamal::{
    elgamal_decrypt, elgamal_encrypt, elgamal_keygen, elgamal_mul, elgamal_mul_plain, elgamal_pow,
    elgamal_rerandomise, ElGamalCiphertext, ElGamalGroup, ElGamalPrivateKey, ElGamalPublicKey,
};
pub use paillier::{
    paillier_add, paillier_add_plain, paillier_decrypt, paillier_encrypt, paillier_keygen,
    paillier_mul_scalar, paillier_rerandomise, PaillierPrivateKey, PaillierPublicKey,
};
pub use rsa::{
    is_prime, random_prime, rsa_decrypt, rsa_encrypt, rsa_sign, rsa_verify, RsaKeyPair,
    RsaPrivateKey, RsaPublicKey,
};
// Note: textbook RSA (`rsa_encrypt_raw`/`rsa_decrypt_raw`) and the PKCS#1 v1.5
// padding helpers are deliberately not re-exported.  They are `pub(crate)`
// internal helpers for `rsa_encrypt`/`rsa_decrypt`; exposing them invites
// misuse (textbook RSA is malleable and not semantically secure).
