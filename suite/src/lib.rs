//! # cryptanalysis-suite — attack library and tools
//!
//! The attacks live in [`cryptanalysis`]; everything else in this crate is
//! there because an attack targets it or is built from it:
//!
//! | Module               | Role                                                                    |
//! |----------------------|-------------------------------------------------------------------------|
//! | `cryptanalysis`      | the suite: S-box / Boolean / avalanche / statistical primitives, symmetric and hash attacks, ECDLP solvers and index calculus, Weil descent, lattice and nonce attacks, ML-KEM / ML-DSA cryptanalysis, the collaborative Pollard rho, the auto-attack framework and research bench |
//! | `symmetric`          | AES, ChaCha20-Poly1305, Serpent, Threefish, SM4, Kuznyechik, Magma — the targets of the block-cipher attacks |
//! | `hash`               | SHA-1/2/3, MD4, MD5, SM3, Streebog, BLAKE3 — the targets of the hash attacks |
//! | `ecc`, `binary_ecc`  | prime-field and binary-field curve arithmetic the ECDLP attacks run on   |
//! | `prime_hyperelliptic`| hyperelliptic Jacobians over prime fields for the descent attacks         |
//! | `isogeny`            | CM discriminants, class groups, Vélu isogenies, ℓ-isogeny volcanoes and ECDLP sweeps across an isogeny class |
//! | `asymmetric`         | RSA, Paillier, ElGamal — targets of Bleichenbacher and the factoring demos |
//! | `pqc`                | ML-KEM, ML-DSA, SQIsign, toy Kyber and McEliece — targets of the lattice and implementation attacks |
//! | `kdf`                | HKDF and PBKDF2, exercised by the TLS key-schedule analyses               |
//! | `ecc_safety`         | curve-parameter safety auditor built on the structural attacks           |
//! | `ct_bignum`, `utils` | arithmetic, randomness and encoding helpers                              |
//! | `visualize`          | the ASCII renderers every attack report uses                             |
//!
//! Nothing in this crate is constant-time or audited.  The primitives exist
//! to be attacked, and the attacks exist to measure; see the crate README
//! for what the suite does and does not claim.

pub mod asymmetric;
pub mod binary_ecc;
pub mod cli;
pub mod cryptanalysis;
pub mod ct_bignum;
pub mod ecc;
pub mod ecc_safety;
pub mod hash;
pub mod isogeny;
pub mod kdf;
pub mod pqc;
pub mod prime_hyperelliptic;
pub mod symmetric;
pub mod utils;
pub mod visualize;
