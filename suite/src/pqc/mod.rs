//! Post-quantum cryptography.
//!
//! NIST standards: ML-KEM (FIPS 203, `ml_kem`), ML-DSA (FIPS 204,
//! `ml_dsa`), SLH-DSA (FIPS 205, `slh_dsa`) — all validated against
//! official test vectors where the module docs say so.
//!
//! Other families: lattice KEMs (toy Kyber, NTRU, NTRU Prime,
//! FrodoKEM), code-based KEMs (McEliece, Classic McEliece, BIKE, HQC),
//! hybrid (X-Wing), and isogeny-based schemes (CSIDH key exchange,
//! SQIsign signatures — both with toy parameters).
//!
//! NIST additional-signatures ("on-ramp") round-3 candidates, all as
//! educational toy-parameter implementations:
//!   - Multivariate: `uov`, `mayo`, `qr_uov`, `snova`.
//!   - Lattice: `hawk` (LIP), `fn_dsa` (Falcon / draft FIPS 206).
//!   - MPC-in-the-head (`mpcith` engine): `sdith`, `mqom`, `faest`.
//!
//! See individual modules for algorithm documentation and limitations.

pub mod bike;
pub mod classic_mceliece;
pub mod csidh;
pub mod faest;
pub mod fast;
pub mod fn_dsa;
pub mod frodo;
pub mod hawk;
pub mod hqc;
pub mod kyber;
pub mod mayo;
pub mod mceliece;
pub mod ml_dsa;
pub mod ml_kem;
pub mod mpcith;
pub mod mqom;
pub mod ntru;
pub mod ntru_prime;
pub mod qr_uov;
pub mod sdith;
pub mod slh_dsa;
pub mod snova;
pub mod sqisign;
pub mod uov;
pub mod x_wing;

pub use kyber::{
    kyber_decapsulate, kyber_encapsulate, kyber_keygen, KyberCiphertext, KyberPrivateKey,
    KyberPublicKey,
};

pub use ml_kem::{
    ml_kem_decaps, ml_kem_encaps, ml_kem_encaps_internal, ml_kem_keygen, ml_kem_keygen_internal,
    MlKemDecapsKey, MlKemEncapsKey, MlKemParams, ML_KEM_1024, ML_KEM_512, ML_KEM_768,
};

pub use ml_dsa::{
    ml_dsa_65_keygen, ml_dsa_65_sign, ml_dsa_65_verify, MlDsaPublicKey, MlDsaSecretKey,
};

pub use sqisign::{
    sqisign_keygen, sqisign_sign, sqisign_verify, SqiSignPublicKey, SqiSignSecretKey, SqiSignature,
};

// NIST additional-signatures (on-ramp) round-3 candidates.

pub use uov::{uov_keygen, uov_sign, uov_verify, UovPublicKey, UovSecretKey};

pub use mayo::{mayo_keygen, mayo_sign, mayo_verify, MayoPublicKey, MayoSecretKey, MayoSignature};

pub use qr_uov::{qr_uov_keygen, qr_uov_sign, qr_uov_verify, QrUovPublicKey, QrUovSecretKey};

pub use snova::{snova_keygen, snova_sign, snova_verify, SnovaPublicKey, SnovaSecretKey};

pub use hawk::{hawk_keygen, hawk_sign, hawk_verify, HawkPublicKey, HawkSecretKey, HawkSignature};

pub use fn_dsa::{
    fn_dsa_keygen, fn_dsa_sign, fn_dsa_verify, FnDsaPublicKey, FnDsaSecretKey, FnDsaSignature,
};

pub use sdith::{sdith_keygen, sdith_sign, sdith_verify, SdithPublicKey, SdithSecretKey};

pub use mqom::{mqom_keygen, mqom_sign, mqom_verify, MqomPublicKey, MqomSecretKey};

pub use faest::{faest_keygen, faest_sign, faest_verify, FaestPublicKey, FaestSecretKey};

pub use mceliece::{
    mceliece_decrypt, mceliece_encrypt, McElieceKeyPair, McEliecePrivateKey, McElieceePublicKey,
};

pub use ntru::{
    ntru_decapsulate, ntru_encapsulate, ntru_keygen, NtruKeyPair, NtruPrivateKey, NtruPublicKey,
};

pub use frodo::{
    frodo_decapsulate, frodo_encapsulate, frodo_keygen, FrodoCiphertext, FrodoKeyPair,
    FrodoPrivateKey, FrodoPublicKey,
};

pub use hqc::{
    hqc_decapsulate, hqc_encapsulate, hqc_keygen, HqcCiphertext, HqcKeyPair, HqcPrivateKey,
    HqcPublicKey,
};

pub use x_wing::{
    x_wing_decapsulate, x_wing_encapsulate, x_wing_keygen, XWingCiphertext, XWingKeyPair,
    XWingPrivateKey, XWingPublicKey,
};
