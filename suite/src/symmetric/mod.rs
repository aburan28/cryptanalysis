//! Symmetric-key cryptography.
//!
//! ## Block ciphers
//!
//! ### AES-family (128-bit block)
//! - **AES** (`aes::AesKey`, FIPS 197) — 128/192/256-bit keys
//! - **Camellia** (`camellia`, RFC 3713) — NTT/Mitsubishi, ISO/IEC 18033-3
//! - **Serpent** (`serpent`) and **Twofish** (`twofish`) — AES finalists
//! - **MARS** (`mars`) and **RC6** (`rc6`) — AES finalists (IBM, RSA)
//! - **SM4** (`sm4`), **Kuznyechik** (`kuznyechik`, 128-bit GOST)
//! - **ARIA** (`aria`, RFC 5794, Korean), **SEED** (`seed`, RFC 4269)
//! - **SQUARE** (`square`) — Daemen/Knudsen/Rijmen 1997, AES precursor
//! - **Lucifer** (`lucifer`) — IBM 1971, the DES ancestor (Sorkin variant)
//!
//! ### 64-bit-block legacy
//! - **DES** (`des`) and **3DES** (`des3`)
//! - **Magma** (64-bit GOST `gost_magma`, RFC 8891)
//! - **Blowfish** (`blowfish`) and **IDEA** (`idea`)
//! - **CAST-128 / CAST5** (`cast5`, RFC 2144)
//! - **MISTY1** (`misty1`, RFC 2994) and **KASUMI** (`kasumi`, 3GPP)
//! - **RC5** (`rc5`)
//! - **SAFER-K-64** (`safer`) — Massey 1993
//! - **Skipjack** (`skipjack`) — NSA Clipper, declassified 1998
//! - **FEAL-8** (`feal`) — Shimizu/Miyaguchi 1987 (broken)
//!
//! ### Lightweight / academic
//! - **Simon** (`simon`) and **Speck** (`speck`) — NSA 2013 ARX/AND-RX
//! - **PRESENT** (`present`, ISO/IEC 29192-2) — CHES 2007
//! - **SKINNY** (`skinny`) and **GIFT** (`gift`) — modern tweakable lightweight
//! - **HIGHT** (`hight`, ISO/IEC 18033-3) — Korean lightweight
//! - **TEA** (`tea`) and **XTEA** (`xtea`) — Wheeler/Needham
//!
//! ### Wide-block
//! - **Threefish** (`threefish`) — 256/512/1024-bit blocks, Skein family
//!
//! ## Stream ciphers
//!
//! - **RC4** (`rc4`) — Rivest 1987 (broken, kept for legacy)
//! - **ChaCha20**, **ChaCha8/12**, **XChaCha20** (`chacha20`)
//! - **Salsa20**, **XSalsa20**, **HSalsa20** (`salsa20`)
//! - **Trivium** (`trivium`) and **Grain v1** (`grain`) — eSTREAM finalists
//!
//! ## AEAD
//!
//! - **AES-GCM**, **AES-CCM** (RFC 3610), **AES-SIV** (RFC 5297)
//! - **ChaCha20-Poly1305** (RFC 8439)
//! - **Ascon-128** / **Ascon-128a** (`ascon`) — NIST Lightweight Crypto winner
//! - **AEGIS-128L / AEGIS-256** (`aegis`) — CAESAR finalists (Wu-Preneel 2014)
//!
//! ## Generic modes of operation
//!
//! [`modes`] hosts generic block-cipher modes that work over the
//! [`modes::BlockCipher<N>`] trait — so the same code wraps AES,
//! Camellia, Twofish, Serpent, Kuznyechik, etc.  Includes:
//!
//! - Confidentiality-only: [`modes::ecb`], [`modes::cfb`], [`modes::ofb`].
//! - AEAD: [`modes::ccm`] (RFC 3610), [`modes::siv`] (RFC 5297,
//!   misuse-resistant).
//! - Specialised: [`modes::kw`] (RFC 3394 key wrap),
//!   [`modes::xts`] (IEEE P1619 disk encryption).

pub mod aegis;
pub mod aes;
pub mod aes_cbc;
pub mod aria;
pub mod ascon;
pub mod blowfish;
pub mod camellia;
pub mod cast5;
pub mod chacha20;
pub mod cmac;
pub mod des;
pub mod des3;
pub mod feal;
pub mod gift;
pub mod gost_magma;
pub mod grain;
pub mod hight;
pub mod idea;
pub mod kasumi;
pub mod kuznyechik;
pub mod lucifer;
pub mod mars;
pub mod misty1;
pub mod modes;
pub mod pmac;
pub mod present;
pub mod rc4;
pub mod rc5;
pub mod rc6;
pub mod safer;
pub mod salsa20;
pub mod seed;
pub mod serpent;
pub mod simon;
pub mod skinny;
pub mod skipjack;
pub mod sm4;
pub mod speck;
pub mod square;
pub mod tea;
pub mod threefish;
pub mod trivium;
pub mod twofish;
pub mod visualize;
pub mod xtea;

pub use aes::{aes_ctr, aes_gcm_decrypt, aes_gcm_encrypt, decrypt_block, encrypt_block, AesKey};
pub use aes_cbc::{
    aes_cbc_decrypt, aes_cbc_encrypt, padding_oracle_attack, pkcs7_pad as cbc_pkcs7_pad,
    pkcs7_unpad as cbc_pkcs7_unpad,
};
pub use chacha20::{
    chacha12_xor, chacha20_block, chacha20_poly1305_decrypt, chacha20_poly1305_encrypt,
    chacha20_xor, chacha8_xor, hchacha20, poly1305, xchacha20_xor,
};
pub use cmac::{aes_cmac, CmacTag};
pub use des::Des;
pub use des3::TripleDes;
pub use gost_magma::Magma;
pub use kuznyechik::Kuznyechik;
pub use modes::{
    ccm_decrypt, ccm_encrypt, cfb_decrypt, cfb_encrypt, ecb_decrypt, ecb_encrypt, kw_unwrap,
    kw_wrap, ofb_apply, siv_decrypt, siv_encrypt, xts_decrypt, xts_encrypt, BlockCipher,
    BlockCipher128, CcmTagLen,
};
pub use rc4::{rc4, Rc4};
pub use rc5::Rc5;
pub use salsa20::{hsalsa20, salsa20_block, salsa20_xor, secretbox, secretbox_open, xsalsa20_xor};
pub use simon::{Simon128_128, Simon128_256, Simon64_128};
pub use sm4::Sm4;
// pub use speck::{Speck128_128, Speck128_256, Speck64_128};
