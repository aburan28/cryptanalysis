//! **Block-cipher modes of operation** — generic over any
//! [`cipher::BlockCipher<N>`] implementor.
//!
//! ## What's here
//!
//! Non-AEAD modes (build authenticity yourself or accept that you've
//! got *no* integrity):
//!
//! - [`ecb`] — Electronic Codebook (NIST SP 800-38A §6.1; broken,
//!   shipped only for teaching).
//! - [`cfb`] — Cipher Feedback (NIST SP 800-38A §6.3).
//! - [`ofb`] — Output Feedback (NIST SP 800-38A §6.4).
//!
//! Authenticated-encryption (AEAD) modes:
//!
//! - [`ccm`] — Counter with CBC-MAC, NIST SP 800-38C / RFC 3610.
//! - [`siv`] — Synthetic IV, RFC 5297 (deterministic, misuse-resistant).
//!
//! Specialised modes:
//!
//! - [`kw`] — RFC 3394 key wrap (deterministic, no IV, for high-entropy
//!   key material only).
//! - [`xts`] — IEEE P1619 / NIST SP 800-38E disk-encryption mode with
//!   ciphertext stealing.
//!
//! ## Pre-existing modes not duplicated here
//!
//! - **AES-CBC** — see `crate::symmetric::aes_cbc`.
//! - **AES-CTR** — see `crate::symmetric::aes::aes_ctr`.
//! - **AES-GCM** — see `crate::symmetric::aes::aes_gcm_*`.
//! - **AES-CMAC** — see `crate::symmetric::cmac::aes_cmac`.
//! - **ChaCha20-Poly1305** — see `crate::symmetric::chacha20`.
//!
//! These were implemented before the generic `BlockCipher` trait
//! existed; the algorithms are equivalent but the function signatures
//! take `&AesKey` directly.

pub mod ccm;
pub mod cfb;
pub mod cipher;
pub mod ctr;
pub mod eax;
pub mod ecb;
pub mod gcm;
pub mod gcm_siv;
pub mod kw;
pub mod ocb3;
pub mod ofb;
pub mod pmac;
pub mod siv;
pub mod xts;

pub use ccm::{ccm_decrypt, ccm_encrypt, CcmTagLen};
pub use cfb::{cfb_decrypt, cfb_encrypt};
pub use cipher::{BlockCipher, BlockCipher128};
pub use ctr::{ctr_apply, ctr_rfc3686};
pub use eax::{eax_decrypt, eax_encrypt};
pub use ecb::{ecb_decrypt, ecb_encrypt, pkcs7_pad, pkcs7_unpad};
pub use gcm::{gcm_decrypt, gcm_encrypt};
pub use gcm_siv::{
    gcm_siv_decrypt, gcm_siv_decrypt_with, gcm_siv_encrypt, gcm_siv_encrypt_with, polyval,
};
pub use kw::{kw_unwrap, kw_wrap};
pub use ocb3::{ocb3_decrypt, ocb3_encrypt};
pub use ofb::ofb_apply;
pub use pmac::pmac;
pub use siv::{siv_decrypt, siv_encrypt};
pub use xts::{xts_decrypt, xts_encrypt};
