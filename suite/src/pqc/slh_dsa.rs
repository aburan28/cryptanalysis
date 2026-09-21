//! SLH-DSA — Stateless Hash-Based Digital Signatures (NIST FIPS 205).
//!
//! # Background
//! SLH-DSA (formerly SPHINCS+) was standardised in NIST FIPS 205 in
//! August 2024.  It is one of three post-quantum signature schemes the
//! NIST PQC project produced (alongside ML-DSA and FN-DSA), and the only
//! one whose security reduces *solely* to the second-preimage and
//! pseudo-randomness properties of an underlying hash function — no
//! number-theoretic or lattice assumption is required.  That makes it
//! the conservative choice: if SHA-256 stands, SLH-DSA stands.
//!
//! The trade-off is signature size.  At security category 1, the small
//! variant (this file) produces 7,856-byte signatures.
//!
//! # Construction (very brief)
//! Four nested primitives:
//!   - **WOTS+** — Winternitz one-time signature on a 16-byte hash.
//!   - **XMSS**  — Merkle tree of 2^{h'} WOTS+ public keys.
//!   - **Hypertree** — `d` layers of XMSS, each layer's leaves are the
//!     XMSS roots of the layer below; the top XMSS root is the public key.
//!   - **FORS** — Forest Of Random Subsets, a few-time signature that
//!     signs the *message digest*; the FORS public key is in turn signed
//!     by the bottom XMSS layer of the hypertree.
//!
//! All keying material flows from a single 16-byte secret seed (`SK.seed`)
//! plus a 16-byte PRF key (`SK.prf`); the public key is `(PK.seed, PK.root)`.
//!
//! This implementation targets **SLH-DSA-SHA2-128s** (FIPS 205 §11):
//!   - n = 16, h = 63, d = 7, h' = 9, a = 12, k = 14, lg(w) = 4.
//!   - All hash calls use SHA-256 (truncated to n bytes where required).
//!   - ADRS is compressed to 22 bytes per FIPS 205 §11.2.
//!
//! Sizes (FIPS 205 Table 2):
//!   - public key:  32 bytes  (2n)
//!   - secret key:  64 bytes  (4n)
//!   - signature:  7856 bytes
//!
//! For production use, see the `pqcrypto-sphincsplus` or `slh-dsa` crates.

use crate::hash::hmac::hmac_sha256;
use crate::hash::sha256::sha256;

// ── Parameters: SLH-DSA-SHA2-128s ─────────────────────────────────────────────

/// Security parameter in bytes.
const N: usize = 16;
/// Total hypertree height.
const H: usize = 63;
/// Number of hypertree layers.
const D: usize = 7;
/// Subtree (XMSS) height: H / D = 9.
const HP: usize = 9;
/// FORS tree height.
const A: usize = 12;
/// Number of FORS trees.
const K_FORS: usize = 14;
/// Winternitz parameter w = 2^4 = 16.
const W: usize = 16;
/// WOTS+ chain count: len1 = 2n (one nibble per byte), len2 = 3, len = 2n + 3 = 35.
const LEN1: usize = 2 * N;
const LEN2: usize = 3;
const LEN: usize = LEN1 + LEN2;

/// Message-digest length pulled out of H_msg, per FIPS 205 §10.2:
///   m = ⌈k·a / 8⌉ + ⌈(h − h/d)/8⌉ + ⌈(h/d)/8⌉
/// = ⌈14·12/8⌉ + ⌈54/8⌉ + ⌈9/8⌉ = 21 + 7 + 2 = 30 bytes.
const M_DIGEST: usize = 30;

/// Public key size in bytes: 2n.
pub const PK_BYTES: usize = 2 * N;
/// Secret key size in bytes: 4n.
pub const SK_BYTES: usize = 4 * N;
/// Signature size in bytes per FIPS 205 Table 2:
///   |R| + k(1 + a)·n + len·n + h·n  = 7,856 for the 128s parameter set.
pub const SIG_BYTES: usize = N + K_FORS * (1 + A) * N + H * N + D * LEN * N;

// Address types (FIPS 205 §4.3).
const ADRS_TYPE_WOTS_HASH: u32 = 0;
const ADRS_TYPE_WOTS_PK: u32 = 1;
const ADRS_TYPE_TREE: u32 = 2;
const ADRS_TYPE_FORS_TREE: u32 = 3;
const ADRS_TYPE_FORS_ROOTS: u32 = 4;
const ADRS_TYPE_WOTS_PRF: u32 = 5;
const ADRS_TYPE_FORS_PRF: u32 = 6;

// ── Address (ADRS) ────────────────────────────────────────────────────────────

/// 32-byte ADRS structure (FIPS 205 §4.3, full form).
///
/// Layout (big-endian):
///   bytes  0.. 4 = layer_address (4 bytes)
///   bytes  4..12 = tree_address  (8 bytes; we use lower 4 here)
///   bytes 12..16 = type
///   bytes 16..20 = field 1 (key_pair / padding / tree_height)
///   bytes 20..24 = field 2 (chain / tree_index)
///   bytes 24..28 = field 3 (hash address / tree_index)
///   bytes 28..32 = field 4 (unused or extension)
#[derive(Clone, Copy, Debug, Default)]
struct Adrs {
    bytes: [u8; 32],
}

impl Adrs {
    fn new() -> Self {
        Adrs { bytes: [0u8; 32] }
    }

    fn set_layer_address(&mut self, l: u32) {
        self.bytes[0..4].copy_from_slice(&l.to_be_bytes());
    }
    fn set_tree_address(&mut self, t: u64) {
        // Upper 4 bytes always zero for these parameter sets.
        self.bytes[4..8].copy_from_slice(&0u32.to_be_bytes());
        self.bytes[8..12].copy_from_slice(&((t & 0xffff_ffff) as u32).to_be_bytes());
        let upper = (t >> 32) as u32;
        self.bytes[4..8].copy_from_slice(&upper.to_be_bytes());
    }
    fn set_type_and_clear(&mut self, t: u32) {
        self.bytes[12..16].copy_from_slice(&t.to_be_bytes());
        for b in &mut self.bytes[16..32] {
            *b = 0;
        }
    }
    fn set_key_pair_address(&mut self, kp: u32) {
        self.bytes[16..20].copy_from_slice(&kp.to_be_bytes());
    }
    fn get_key_pair_address(&self) -> u32 {
        u32::from_be_bytes(self.bytes[16..20].try_into().unwrap())
    }
    fn set_chain_address(&mut self, c: u32) {
        self.bytes[20..24].copy_from_slice(&c.to_be_bytes());
    }
    fn set_tree_height(&mut self, h: u32) {
        self.bytes[20..24].copy_from_slice(&h.to_be_bytes());
    }
    fn set_hash_address(&mut self, h: u32) {
        self.bytes[24..28].copy_from_slice(&h.to_be_bytes());
    }
    fn set_tree_index(&mut self, i: u32) {
        self.bytes[24..28].copy_from_slice(&i.to_be_bytes());
    }

    /// Compressed ADRS for SHA2 instances (FIPS 205 §11.2): 22 bytes total.
    ///   layer (1) | tree (8) | type (1) | last 12 bytes of full ADRS
    fn compressed(&self) -> [u8; 22] {
        let mut out = [0u8; 22];
        out[0] = self.bytes[3]; // last byte of layer
        out[1..9].copy_from_slice(&self.bytes[4..12]); // tree
        out[9] = self.bytes[15]; // last byte of type
        out[10..22].copy_from_slice(&self.bytes[20..32]); // fields 2..4
        out
    }
}

// ── Hash building blocks (FIPS 205 §11.2.1, SHA2 / Category 1) ────────────────

/// F(PK.seed, ADRS, M_1) = Trunc_n(SHA-256(PK.seed || toByte(0, 64−n) || ADRS_c || M_1)).
fn f_hash(pk_seed: &[u8; N], adrs: &Adrs, m1: &[u8]) -> [u8; N] {
    let mut buf = Vec::with_capacity(64 + 22 + m1.len());
    buf.extend_from_slice(pk_seed);
    buf.extend_from_slice(&[0u8; 64 - N]);
    buf.extend_from_slice(&adrs.compressed());
    buf.extend_from_slice(m1);
    let d = sha256(&buf);
    let mut out = [0u8; N];
    out.copy_from_slice(&d[..N]);
    out
}

/// H(PK.seed, ADRS, M_2) — same construction as F, with M_2 the concatenation
/// of two n-byte child hashes.
#[inline]
fn h_hash(pk_seed: &[u8; N], adrs: &Adrs, left: &[u8; N], right: &[u8; N]) -> [u8; N] {
    let mut m = [0u8; 2 * N];
    m[..N].copy_from_slice(left);
    m[N..].copy_from_slice(right);
    f_hash(pk_seed, adrs, &m)
}

/// T_l(PK.seed, ADRS, M) — same SHA-256 truncation, used to hash a flat list.
fn t_hash(pk_seed: &[u8; N], adrs: &Adrs, m: &[u8]) -> [u8; N] {
    f_hash(pk_seed, adrs, m)
}

/// PRF(PK.seed, SK.seed, ADRS) = Trunc_n(SHA-256(PK.seed || toByte(0, 64−n) || ADRS_c || SK.seed)).
fn prf(pk_seed: &[u8; N], sk_seed: &[u8; N], adrs: &Adrs) -> [u8; N] {
    let mut buf = Vec::with_capacity(64 + 22 + N);
    buf.extend_from_slice(pk_seed);
    buf.extend_from_slice(&[0u8; 64 - N]);
    buf.extend_from_slice(&adrs.compressed());
    buf.extend_from_slice(sk_seed);
    let d = sha256(&buf);
    let mut out = [0u8; N];
    out.copy_from_slice(&d[..N]);
    out
}

/// PRF_msg(SK.prf, opt_rand, M) = Trunc_n(HMAC-SHA-256(SK.prf, opt_rand || M)).
fn prf_msg(sk_prf: &[u8; N], opt_rand: &[u8; N], msg: &[u8]) -> [u8; N] {
    let mut data = Vec::with_capacity(N + msg.len());
    data.extend_from_slice(opt_rand);
    data.extend_from_slice(msg);
    let mac = hmac_sha256(sk_prf, &data);
    let mut out = [0u8; N];
    out.copy_from_slice(&mac[..N]);
    out
}

/// H_msg(R, PK.seed, PK.root, M) (FIPS 205 §11.2.1):
///   seed = SHA-256(R || PK.seed || PK.root || M)
///   output m = MGF1-SHA-256(R || PK.seed || seed, m_bytes)
fn h_msg(r: &[u8; N], pk_seed: &[u8; N], pk_root: &[u8; N], msg: &[u8]) -> [u8; M_DIGEST] {
    let mut inner = Vec::with_capacity(3 * N + msg.len());
    inner.extend_from_slice(r);
    inner.extend_from_slice(pk_seed);
    inner.extend_from_slice(pk_root);
    inner.extend_from_slice(msg);
    let seed = sha256(&inner);

    // MGF1-SHA-256 seeded by (R || PK.seed || seed).
    let mut mgf_seed = Vec::with_capacity(2 * N + 32);
    mgf_seed.extend_from_slice(r);
    mgf_seed.extend_from_slice(pk_seed);
    mgf_seed.extend_from_slice(&seed);

    let mut out = [0u8; M_DIGEST];
    let mut produced = 0usize;
    let mut counter: u32 = 0;
    while produced < M_DIGEST {
        let mut buf = mgf_seed.clone();
        buf.extend_from_slice(&counter.to_be_bytes());
        let block = sha256(&buf);
        let take = (M_DIGEST - produced).min(32);
        out[produced..produced + take].copy_from_slice(&block[..take]);
        produced += take;
        counter += 1;
    }
    out
}

// ── WOTS+ (FIPS 205 §5) ──────────────────────────────────────────────────────

/// Iterated F-chain: chain^{steps}(input) starting at index `start`.
fn wots_chain(x: &[u8; N], start: u32, steps: u32, pk_seed: &[u8; N], adrs: &mut Adrs) -> [u8; N] {
    let mut tmp = *x;
    for j in 0..steps {
        adrs.set_hash_address(start + j);
        tmp = f_hash(pk_seed, adrs, &tmp);
    }
    tmp
}

/// Convert n bytes into 2n base-w (w=16) digits, MSB-first within each byte.
fn base_w_msg(msg: &[u8; N]) -> [u32; LEN1] {
    let mut out = [0u32; LEN1];
    for (i, &b) in msg.iter().enumerate() {
        out[2 * i] = (b >> 4) as u32;
        out[2 * i + 1] = (b & 0x0f) as u32;
    }
    out
}

/// Compute the WOTS+ checksum digits (3 base-16 digits packed big-endian).
fn wots_checksum(msg_digits: &[u32; LEN1]) -> [u32; LEN2] {
    let mut csum: u32 = 0;
    for &d in msg_digits.iter() {
        csum += (W as u32) - 1 - d;
    }
    // Left-shift to fill the high nibble of a 12-bit value (lg(w)·LEN2 = 12).
    // For lg(w)=4, no shift needed beyond aligning to LEN2 nibbles.
    let bytes = [(csum >> 8) as u8 & 0x0f, ((csum >> 4) as u8), (csum as u8)];
    // We want LEN2=3 nibbles from a 12-bit csum, MSB first.
    let mut out = [0u32; LEN2];
    out[0] = (csum >> 8) & 0x0f;
    out[1] = (csum >> 4) & 0x0f;
    out[2] = csum & 0x0f;
    let _ = bytes;
    out
}

/// All LEN base-w digits for a WOTS+ message: msg digits || checksum digits.
fn wots_digits(msg: &[u8; N]) -> [u32; LEN] {
    let m = base_w_msg(msg);
    let c = wots_checksum(&m);
    let mut out = [0u32; LEN];
    out[..LEN1].copy_from_slice(&m);
    out[LEN1..].copy_from_slice(&c);
    out
}

/// Generate the WOTS+ public key for a given key-pair address.
fn wots_pk_gen(sk_seed: &[u8; N], pk_seed: &[u8; N], adrs: &mut Adrs) -> [u8; N] {
    let mut chain_tops = [[0u8; N]; LEN];
    let saved_kp = adrs.get_key_pair_address();
    for i in 0..LEN {
        // PRF address for secret chain start.
        adrs.set_type_and_clear(ADRS_TYPE_WOTS_PRF);
        adrs.set_key_pair_address(saved_kp);
        adrs.set_chain_address(i as u32);
        adrs.set_hash_address(0);
        let sk_i = prf(pk_seed, sk_seed, adrs);

        // Walk the full F-chain w-1 times.
        adrs.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        adrs.set_key_pair_address(saved_kp);
        adrs.set_chain_address(i as u32);
        chain_tops[i] = wots_chain(&sk_i, 0, (W as u32) - 1, pk_seed, adrs);
    }

    // Compress chain tops with T_len under a WOTS_PK address.
    let mut adrs_pk = *adrs;
    adrs_pk.set_type_and_clear(ADRS_TYPE_WOTS_PK);
    adrs_pk.set_key_pair_address(saved_kp);
    let mut flat = Vec::with_capacity(LEN * N);
    for t in &chain_tops {
        flat.extend_from_slice(t);
    }
    t_hash(pk_seed, &adrs_pk, &flat)
}

/// Sign an n-byte message under a single WOTS+ key.
/// Returns the LEN-many n-byte chain values.
fn wots_sign(
    msg: &[u8; N],
    sk_seed: &[u8; N],
    pk_seed: &[u8; N],
    adrs: &mut Adrs,
) -> [[u8; N]; LEN] {
    let digits = wots_digits(msg);
    let mut sig = [[0u8; N]; LEN];
    let saved_kp = adrs.get_key_pair_address();
    for i in 0..LEN {
        adrs.set_type_and_clear(ADRS_TYPE_WOTS_PRF);
        adrs.set_key_pair_address(saved_kp);
        adrs.set_chain_address(i as u32);
        adrs.set_hash_address(0);
        let sk_i = prf(pk_seed, sk_seed, adrs);

        adrs.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        adrs.set_key_pair_address(saved_kp);
        adrs.set_chain_address(i as u32);
        sig[i] = wots_chain(&sk_i, 0, digits[i], pk_seed, adrs);
    }
    sig
}

/// Derive the WOTS+ public key from a signature and message — verifier side.
fn wots_pk_from_sig(
    sig: &[[u8; N]; LEN],
    msg: &[u8; N],
    pk_seed: &[u8; N],
    adrs: &mut Adrs,
) -> [u8; N] {
    let digits = wots_digits(msg);
    let mut chain_tops = [[0u8; N]; LEN];
    let saved_kp = adrs.get_key_pair_address();
    for i in 0..LEN {
        adrs.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        adrs.set_key_pair_address(saved_kp);
        adrs.set_chain_address(i as u32);
        // Continue the chain from digits[i] up to w-1.
        let remaining = (W as u32) - 1 - digits[i];
        chain_tops[i] = wots_chain(&sig[i], digits[i], remaining, pk_seed, adrs);
    }
    let mut adrs_pk = *adrs;
    adrs_pk.set_type_and_clear(ADRS_TYPE_WOTS_PK);
    adrs_pk.set_key_pair_address(saved_kp);
    let mut flat = Vec::with_capacity(LEN * N);
    for t in &chain_tops {
        flat.extend_from_slice(t);
    }
    t_hash(pk_seed, &adrs_pk, &flat)
}

// ── XMSS subtree (FIPS 205 §6) ───────────────────────────────────────────────

/// Compute the XMSS subtree root via the FIPS 205 `treehash` recursion.
fn xmss_node(
    sk_seed: &[u8; N],
    leaf_idx: u32,
    target_height: u32,
    pk_seed: &[u8; N],
    adrs: &mut Adrs,
) -> [u8; N] {
    if target_height == 0 {
        // Leaf = WOTS+ public key at leaf_idx.
        adrs.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        adrs.set_key_pair_address(leaf_idx);
        return wots_pk_gen(sk_seed, pk_seed, adrs);
    }
    let left = xmss_node(sk_seed, 2 * leaf_idx, target_height - 1, pk_seed, adrs);
    let right = xmss_node(sk_seed, 2 * leaf_idx + 1, target_height - 1, pk_seed, adrs);
    adrs.set_type_and_clear(ADRS_TYPE_TREE);
    adrs.set_tree_height(target_height);
    adrs.set_tree_index(leaf_idx);
    h_hash(pk_seed, adrs, &left, &right)
}

/// Sign one leaf in an XMSS subtree: WOTS+ signature on `msg` plus an
/// authentication path of HP nodes.
fn xmss_sign(
    msg: &[u8; N],
    sk_seed: &[u8; N],
    idx_leaf: u32,
    pk_seed: &[u8; N],
    adrs: &mut Adrs,
) -> Vec<u8> {
    let mut out = Vec::with_capacity(LEN * N + HP * N);

    // Authentication path.
    let mut auth = Vec::with_capacity(HP * N);
    for j in 0..HP {
        let k = (idx_leaf >> j) ^ 1;
        let node = xmss_node(sk_seed, k, j as u32, pk_seed, adrs);
        auth.extend_from_slice(&node);
    }

    // WOTS+ signature.
    adrs.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
    adrs.set_key_pair_address(idx_leaf);
    let wots_sig = wots_sign(msg, sk_seed, pk_seed, adrs);
    for s in &wots_sig {
        out.extend_from_slice(s);
    }
    out.extend_from_slice(&auth);
    out
}

/// Compute the XMSS public root from a signature and a leaf message.
fn xmss_pk_from_sig(
    idx_leaf: u32,
    sig: &[u8],
    msg: &[u8; N],
    pk_seed: &[u8; N],
    adrs: &mut Adrs,
) -> [u8; N] {
    // Recover WOTS+ public key.
    let mut wots_sig = [[0u8; N]; LEN];
    for (i, slot) in wots_sig.iter_mut().enumerate() {
        slot.copy_from_slice(&sig[i * N..(i + 1) * N]);
    }
    adrs.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
    adrs.set_key_pair_address(idx_leaf);
    let mut node = wots_pk_from_sig(&wots_sig, msg, pk_seed, adrs);

    // Walk the authentication path.
    let auth_off = LEN * N;
    for j in 0..HP {
        let auth_j: [u8; N] = sig[auth_off + j * N..auth_off + (j + 1) * N]
            .try_into()
            .unwrap();
        adrs.set_type_and_clear(ADRS_TYPE_TREE);
        adrs.set_tree_height((j + 1) as u32);
        let index = idx_leaf >> (j + 1);
        adrs.set_tree_index(index);
        if (idx_leaf >> j) & 1 == 0 {
            node = h_hash(pk_seed, adrs, &node, &auth_j);
        } else {
            node = h_hash(pk_seed, adrs, &auth_j, &node);
        }
    }
    node
}

// ── Hypertree (FIPS 205 §7) ──────────────────────────────────────────────────

/// Sign an n-byte message under the full hypertree.  Returns the d
/// concatenated XMSS subtree signatures.
fn ht_sign(
    msg: &[u8; N],
    sk_seed: &[u8; N],
    pk_seed: &[u8; N],
    mut tree_idx: u64,
    mut leaf_idx: u32,
) -> Vec<u8> {
    let mut out = Vec::with_capacity(D * (LEN * N + HP * N));
    let mut adrs = Adrs::new();
    adrs.set_layer_address(0);
    adrs.set_tree_address(tree_idx);

    let mut node = *msg;
    for layer in 0..D {
        let sig = xmss_sign(&node, sk_seed, leaf_idx, pk_seed, &mut adrs);
        node = xmss_pk_from_sig(leaf_idx, &sig, &node, pk_seed, &mut adrs);
        out.extend_from_slice(&sig);

        if layer == D - 1 {
            break;
        }

        leaf_idx = (tree_idx & ((1u64 << HP) - 1)) as u32;
        tree_idx >>= HP;
        adrs.set_layer_address((layer + 1) as u32);
        adrs.set_tree_address(tree_idx);
    }
    out
}

/// Verify a hypertree signature: walk up `d` XMSS layers and return whether
/// the final XMSS root matches the public root.
fn ht_verify(
    msg: &[u8; N],
    sig: &[u8],
    pk_seed: &[u8; N],
    pk_root: &[u8; N],
    mut tree_idx: u64,
    mut leaf_idx: u32,
) -> bool {
    let xmss_sig_len = (LEN + HP) * N;
    if sig.len() != D * xmss_sig_len {
        return false;
    }
    let mut adrs = Adrs::new();
    adrs.set_layer_address(0);
    adrs.set_tree_address(tree_idx);

    let mut node = *msg;
    for layer in 0..D {
        let s = &sig[layer * xmss_sig_len..(layer + 1) * xmss_sig_len];
        node = xmss_pk_from_sig(leaf_idx, s, &node, pk_seed, &mut adrs);
        if layer == D - 1 {
            break;
        }
        leaf_idx = (tree_idx & ((1u64 << HP) - 1)) as u32;
        tree_idx >>= HP;
        adrs.set_layer_address((layer + 1) as u32);
        adrs.set_tree_address(tree_idx);
    }
    node == *pk_root
}

// ── FORS (FIPS 205 §8) ───────────────────────────────────────────────────────

/// Compute one FORS secret key from (SK.seed, PK.seed, ADRS, idx).
fn fors_sk_gen(sk_seed: &[u8; N], pk_seed: &[u8; N], adrs: &mut Adrs, idx: u32) -> [u8; N] {
    let saved_kp = adrs.get_key_pair_address();
    let mut prf_adrs = *adrs;
    prf_adrs.set_type_and_clear(ADRS_TYPE_FORS_PRF);
    prf_adrs.set_key_pair_address(saved_kp);
    prf_adrs.set_tree_index(idx);
    prf(pk_seed, sk_seed, &prf_adrs)
}

/// Compute a node in one FORS tree at (tree_idx, target_height).
fn fors_node(
    sk_seed: &[u8; N],
    pk_seed: &[u8; N],
    adrs: &mut Adrs,
    tree_idx: u32,
    target_height: u32,
) -> [u8; N] {
    if target_height == 0 {
        let sk = fors_sk_gen(sk_seed, pk_seed, adrs, tree_idx);
        adrs.set_tree_height(0);
        adrs.set_tree_index(tree_idx);
        return f_hash(pk_seed, adrs, &sk);
    }
    let left = fors_node(sk_seed, pk_seed, adrs, 2 * tree_idx, target_height - 1);
    let right = fors_node(sk_seed, pk_seed, adrs, 2 * tree_idx + 1, target_height - 1);
    adrs.set_tree_height(target_height);
    adrs.set_tree_index(tree_idx);
    h_hash(pk_seed, adrs, &left, &right)
}

/// Split the M_DIGEST-byte FORS message digest into k_fors a-bit indices.
fn fors_indices(digest: &[u8]) -> [u32; K_FORS] {
    // Pull the first ⌈k·a/8⌉ = 21 bytes; MSB-first bit extraction.
    let mut out = [0u32; K_FORS];
    let mut bit_pos = 0usize;
    for slot in out.iter_mut() {
        let mut v: u32 = 0;
        for _ in 0..A {
            let byte = digest[bit_pos / 8];
            let bit = (byte >> (7 - (bit_pos % 8))) & 1;
            v = (v << 1) | bit as u32;
            bit_pos += 1;
        }
        *slot = v;
    }
    out
}

/// Sign an a·k-bit message digest with FORS.  Output is k·(1 + a)·n bytes.
fn fors_sign(digest: &[u8], sk_seed: &[u8; N], pk_seed: &[u8; N], adrs: &mut Adrs) -> Vec<u8> {
    let indices = fors_indices(digest);
    let mut out = Vec::with_capacity(K_FORS * (1 + A) * N);

    for i in 0..K_FORS {
        // Tree i covers indices [i·2^a, (i+1)·2^a).
        let leaf_global = (i as u32) * (1u32 << A) + indices[i];
        let sk_i = fors_sk_gen(sk_seed, pk_seed, adrs, leaf_global);
        out.extend_from_slice(&sk_i);

        // Authentication path for `indices[i]` within tree i.
        let mut sibling_idx = leaf_global;
        for j in 0..A {
            sibling_idx ^= 1;
            let node = fors_node(sk_seed, pk_seed, adrs, sibling_idx, j as u32);
            out.extend_from_slice(&node);
            // Move to the parent's left child slot.
            sibling_idx = (leaf_global >> (j + 1)) << 1;
        }
    }
    out
}

/// Recover the FORS public key from a FORS signature + message digest.
fn fors_pk_from_sig(sig: &[u8], digest: &[u8], pk_seed: &[u8; N], adrs: &mut Adrs) -> [u8; N] {
    let indices = fors_indices(digest);
    let mut roots = Vec::with_capacity(K_FORS * N);

    let entry_len = (1 + A) * N;
    for i in 0..K_FORS {
        let entry = &sig[i * entry_len..(i + 1) * entry_len];
        let mut node: [u8; N] = entry[..N].try_into().unwrap();
        let leaf_global = (i as u32) * (1u32 << A) + indices[i];

        adrs.set_tree_height(0);
        adrs.set_tree_index(leaf_global);
        node = f_hash(pk_seed, adrs, &node);

        let mut idx = leaf_global;
        for j in 0..A {
            let auth: [u8; N] = entry[N + j * N..N + (j + 1) * N].try_into().unwrap();
            adrs.set_tree_height((j + 1) as u32);
            let parent_idx = idx >> 1;
            adrs.set_tree_index(parent_idx);
            if idx & 1 == 0 {
                node = h_hash(pk_seed, adrs, &node, &auth);
            } else {
                node = h_hash(pk_seed, adrs, &auth, &node);
            }
            idx = parent_idx;
        }
        roots.extend_from_slice(&node);
    }

    // Compress the k roots with a FORS_ROOTS-typed T-hash.
    let mut roots_adrs = *adrs;
    roots_adrs.set_type_and_clear(ADRS_TYPE_FORS_ROOTS);
    roots_adrs.set_key_pair_address(adrs.get_key_pair_address());
    t_hash(pk_seed, &roots_adrs, &roots)
}

// ── Public types ─────────────────────────────────────────────────────────────

/// SLH-DSA public key: PK.seed ‖ PK.root, 2n = 32 bytes.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct SlhDsaPublicKey {
    pub bytes: [u8; PK_BYTES],
}

/// SLH-DSA secret key: SK.seed ‖ SK.prf ‖ PK.seed ‖ PK.root, 4n = 64 bytes.
#[derive(Clone, Debug)]
pub struct SlhDsaSecretKey {
    pub bytes: [u8; SK_BYTES],
}

impl Drop for SlhDsaSecretKey {
    fn drop(&mut self) {
        self.bytes.fill(0);
    }
}

impl SlhDsaSecretKey {
    fn sk_seed(&self) -> [u8; N] {
        let mut x = [0u8; N];
        x.copy_from_slice(&self.bytes[..N]);
        x
    }
    fn sk_prf(&self) -> [u8; N] {
        let mut x = [0u8; N];
        x.copy_from_slice(&self.bytes[N..2 * N]);
        x
    }
    fn pk_seed(&self) -> [u8; N] {
        let mut x = [0u8; N];
        x.copy_from_slice(&self.bytes[2 * N..3 * N]);
        x
    }
    fn pk_root(&self) -> [u8; N] {
        let mut x = [0u8; N];
        x.copy_from_slice(&self.bytes[3 * N..]);
        x
    }
}

impl SlhDsaPublicKey {
    fn pk_seed(&self) -> [u8; N] {
        let mut x = [0u8; N];
        x.copy_from_slice(&self.bytes[..N]);
        x
    }
    fn pk_root(&self) -> [u8; N] {
        let mut x = [0u8; N];
        x.copy_from_slice(&self.bytes[N..]);
        x
    }
}

// ── Public API ───────────────────────────────────────────────────────────────

/// Deterministic key generation from a 48-byte seed (FIPS 205 §9.1).
///
/// The 48-byte input supplies (SK.seed ‖ SK.prf ‖ PK.seed); PK.root is
/// derived from the top-layer XMSS root.
pub fn slh_dsa_sha2_128s_keygen(seed: &[u8; 48]) -> (SlhDsaPublicKey, SlhDsaSecretKey) {
    let mut sk_seed = [0u8; N];
    let mut sk_prf = [0u8; N];
    let mut pk_seed = [0u8; N];
    sk_seed.copy_from_slice(&seed[..N]);
    sk_prf.copy_from_slice(&seed[N..2 * N]);
    pk_seed.copy_from_slice(&seed[2 * N..3 * N]);

    // Compute PK.root = root of the top-layer XMSS subtree (layer D−1, tree 0).
    let mut adrs = Adrs::new();
    adrs.set_layer_address((D - 1) as u32);
    adrs.set_tree_address(0);
    let pk_root = xmss_node(&sk_seed, 0, HP as u32, &pk_seed, &mut adrs);

    let mut pk_bytes = [0u8; PK_BYTES];
    pk_bytes[..N].copy_from_slice(&pk_seed);
    pk_bytes[N..].copy_from_slice(&pk_root);

    let mut sk_bytes = [0u8; SK_BYTES];
    sk_bytes[..N].copy_from_slice(&sk_seed);
    sk_bytes[N..2 * N].copy_from_slice(&sk_prf);
    sk_bytes[2 * N..3 * N].copy_from_slice(&pk_seed);
    sk_bytes[3 * N..].copy_from_slice(&pk_root);

    (
        SlhDsaPublicKey { bytes: pk_bytes },
        SlhDsaSecretKey { bytes: sk_bytes },
    )
}

/// Split the message digest into (md, tree_idx, leaf_idx) per FIPS 205 §10.2.
fn split_digest(digest: &[u8; M_DIGEST]) -> ([u8; 21], u64, u32) {
    // md   = first ⌈k·a/8⌉ = 21 bytes
    // tree = next ⌈(h - h/d)/8⌉ = 7 bytes  (h-h/d = 54 → fits in 7 bytes; mask to 54 bits)
    // leaf = next ⌈(h/d)/8⌉ = 2 bytes      (h/d = 9 bits → mask to 9 bits)
    let mut md = [0u8; 21];
    md.copy_from_slice(&digest[..21]);

    let mut tree_bytes = [0u8; 8];
    tree_bytes[1..].copy_from_slice(&digest[21..28]);
    let tree = u64::from_be_bytes(tree_bytes);
    let tree_mask = if H - HP >= 64 {
        u64::MAX
    } else {
        (1u64 << (H - HP)) - 1
    };
    let tree = tree & tree_mask;

    let leaf_bytes = [digest[28], digest[29]];
    let leaf = u16::from_be_bytes(leaf_bytes) as u32;
    let leaf_mask = (1u32 << HP) - 1;
    let leaf = leaf & leaf_mask;

    (md, tree, leaf)
}

/// Deterministic-friendly signature (`opt_rand` becomes the public randomizer
/// `R`).  Per FIPS 205 §10.2.1 the official deterministic variant uses
/// `opt_rand = PK.seed`; the randomized variant uses fresh randomness.
pub fn slh_dsa_sha2_128s_sign(sk: &SlhDsaSecretKey, msg: &[u8], opt_rand: &[u8; 16]) -> Vec<u8> {
    let sk_seed = sk.sk_seed();
    let sk_prf = sk.sk_prf();
    let pk_seed = sk.pk_seed();
    let pk_root = sk.pk_root();

    // R = PRF_msg(SK.prf, opt_rand, M)
    let r = prf_msg(&sk_prf, opt_rand, msg);

    // digest = H_msg(R, PK.seed, PK.root, M)
    let digest = h_msg(&r, &pk_seed, &pk_root, msg);

    let (md, tree_idx, leaf_idx) = split_digest(&digest);

    // FORS signs the message digest portion `md`.
    let mut adrs = Adrs::new();
    adrs.set_layer_address(0);
    adrs.set_tree_address(tree_idx);
    adrs.set_type_and_clear(ADRS_TYPE_FORS_TREE);
    adrs.set_key_pair_address(leaf_idx);

    let mut adrs_fors = adrs;
    let fors_sig = fors_sign(&md, &sk_seed, &pk_seed, &mut adrs_fors);

    // Compute FORS public key (input to the hypertree).
    let mut adrs_pk = adrs;
    let fors_pk = fors_pk_from_sig(&fors_sig, &md, &pk_seed, &mut adrs_pk);

    // Hypertree signs the FORS public key.
    let ht_sig = ht_sign(&fors_pk, &sk_seed, &pk_seed, tree_idx, leaf_idx);

    // Assemble: R || FORS_SIG || HT_SIG
    let mut out = Vec::with_capacity(SIG_BYTES);
    out.extend_from_slice(&r);
    out.extend_from_slice(&fors_sig);
    out.extend_from_slice(&ht_sig);
    debug_assert_eq!(out.len(), SIG_BYTES);
    out
}

/// Verify an SLH-DSA-SHA2-128s signature.
pub fn slh_dsa_sha2_128s_verify(pk: &SlhDsaPublicKey, msg: &[u8], sig: &[u8]) -> bool {
    if sig.len() != SIG_BYTES {
        return false;
    }
    let pk_seed = pk.pk_seed();
    let pk_root = pk.pk_root();

    let mut r = [0u8; N];
    r.copy_from_slice(&sig[..N]);

    let fors_sig_len = K_FORS * (1 + A) * N;
    let fors_sig = &sig[N..N + fors_sig_len];
    let ht_sig = &sig[N + fors_sig_len..];

    let digest = h_msg(&r, &pk_seed, &pk_root, msg);
    let (md, tree_idx, leaf_idx) = split_digest(&digest);

    let mut adrs = Adrs::new();
    adrs.set_layer_address(0);
    adrs.set_tree_address(tree_idx);
    adrs.set_type_and_clear(ADRS_TYPE_FORS_TREE);
    adrs.set_key_pair_address(leaf_idx);

    let fors_pk = fors_pk_from_sig(fors_sig, &md, &pk_seed, &mut adrs);
    ht_verify(&fors_pk, ht_sig, &pk_seed, &pk_root, tree_idx, leaf_idx)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn deterministic_seed(byte: u8) -> [u8; 48] {
        let mut s = [0u8; 48];
        for (i, b) in s.iter_mut().enumerate() {
            *b = byte.wrapping_add(i as u8);
        }
        s
    }

    // ── Parameter sanity ─────────────────────────────────────────────────────

    #[test]
    fn parameter_sizes_match_fips_205() {
        // FIPS 205 Table 2, SLH-DSA-SHA2-128s
        assert_eq!(PK_BYTES, 32);
        assert_eq!(SK_BYTES, 64);
        assert_eq!(SIG_BYTES, 7_856);
        assert_eq!(LEN, 35);
        assert_eq!(M_DIGEST, 30);
    }

    // ── ADRS plumbing ────────────────────────────────────────────────────────

    #[test]
    fn adrs_set_type_clears_lower_fields() {
        let mut a = Adrs::new();
        a.set_key_pair_address(0xdead_beef);
        a.set_tree_index(0xcafe_f00d);
        a.set_type_and_clear(ADRS_TYPE_FORS_TREE);
        // Type field set.
        assert_eq!(&a.bytes[12..16], &ADRS_TYPE_FORS_TREE.to_be_bytes());
        // Fields 1..4 cleared.
        for b in &a.bytes[16..32] {
            assert_eq!(*b, 0);
        }
    }

    #[test]
    fn adrs_compressed_is_22_bytes() {
        let mut a = Adrs::new();
        a.set_layer_address(3);
        a.set_tree_address(0x0102_0304_0506_0708);
        a.set_type_and_clear(ADRS_TYPE_TREE);
        a.set_tree_height(5);
        a.set_tree_index(7);
        let c = a.compressed();
        assert_eq!(c.len(), 22);
        assert_eq!(c[0], 3); // last layer byte
        assert_eq!(c[9], ADRS_TYPE_TREE as u8); // last type byte
    }

    // ── WOTS+ ────────────────────────────────────────────────────────────────

    #[test]
    fn wots_digits_have_correct_checksum() {
        let msg = [0xa5u8; N];
        let d = wots_digits(&msg);
        // Each digit is < w = 16.
        for &x in d.iter() {
            assert!(x < W as u32);
        }
        // Recompute checksum and check the last LEN2 digits match.
        let mut csum: u32 = 0;
        for i in 0..LEN1 {
            csum += (W as u32) - 1 - d[i];
        }
        let exp = [(csum >> 8) & 0x0f, (csum >> 4) & 0x0f, csum & 0x0f];
        assert_eq!([d[LEN1], d[LEN1 + 1], d[LEN1 + 2]], exp);
    }

    #[test]
    fn wots_sign_verify_roundtrip() {
        let sk_seed = [0x11u8; N];
        let pk_seed = [0x22u8; N];
        let msg = [0x33u8; N];

        let mut adrs = Adrs::new();
        adrs.set_layer_address(0);
        adrs.set_tree_address(0);
        adrs.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        adrs.set_key_pair_address(42);

        let pk = wots_pk_gen(&sk_seed, &pk_seed, &mut adrs);

        let mut adrs2 = Adrs::new();
        adrs2.set_layer_address(0);
        adrs2.set_tree_address(0);
        adrs2.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        adrs2.set_key_pair_address(42);
        let sig = wots_sign(&msg, &sk_seed, &pk_seed, &mut adrs2);

        let mut adrs3 = Adrs::new();
        adrs3.set_layer_address(0);
        adrs3.set_tree_address(0);
        adrs3.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        adrs3.set_key_pair_address(42);
        let pk_check = wots_pk_from_sig(&sig, &msg, &pk_seed, &mut adrs3);

        assert_eq!(pk, pk_check, "WOTS+ pk(sign(m)) must match pk_gen()");
    }

    #[test]
    fn wots_wrong_message_yields_wrong_pk() {
        let sk_seed = [0x44u8; N];
        let pk_seed = [0x55u8; N];
        let m1 = [0x66u8; N];
        let m2 = [0x77u8; N];

        let mut a = Adrs::new();
        a.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        a.set_key_pair_address(7);
        let pk = wots_pk_gen(&sk_seed, &pk_seed, &mut a);

        let mut a = Adrs::new();
        a.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        a.set_key_pair_address(7);
        let sig = wots_sign(&m1, &sk_seed, &pk_seed, &mut a);

        let mut a = Adrs::new();
        a.set_type_and_clear(ADRS_TYPE_WOTS_HASH);
        a.set_key_pair_address(7);
        let pk_wrong = wots_pk_from_sig(&sig, &m2, &pk_seed, &mut a);

        assert_ne!(pk, pk_wrong);
    }

    // ── FORS digest splitting ────────────────────────────────────────────────

    #[test]
    fn fors_indices_use_exactly_a_bits() {
        let digest = [0xffu8; M_DIGEST];
        let idx = fors_indices(&digest);
        for &i in idx.iter() {
            assert!(i < 1u32 << A, "FORS index {i} exceeds 2^a");
        }
    }

    #[test]
    fn split_digest_masks_correctly() {
        let mut digest = [0xffu8; M_DIGEST];
        digest[21] = 0xff;
        let (_md, tree, leaf) = split_digest(&digest);
        assert!(tree < 1u64 << (H - HP));
        assert!(leaf < 1u32 << HP);
    }

    // ── End-to-end ───────────────────────────────────────────────────────────

    #[test]
    fn keygen_produces_correct_sizes() {
        let seed = deterministic_seed(0);
        let (pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        assert_eq!(pk.bytes.len(), 32);
        assert_eq!(sk.bytes.len(), 64);
        // PK.seed in both pk and sk must agree.
        assert_eq!(&pk.bytes[..N], &sk.bytes[2 * N..3 * N]);
        // PK.root in both pk and sk must agree.
        assert_eq!(&pk.bytes[N..], &sk.bytes[3 * N..]);
    }

    #[test]
    fn keygen_is_deterministic_in_seed() {
        let seed = deterministic_seed(7);
        let (pk1, sk1) = slh_dsa_sha2_128s_keygen(&seed);
        let (pk2, sk2) = slh_dsa_sha2_128s_keygen(&seed);
        assert_eq!(pk1.bytes, pk2.bytes);
        assert_eq!(sk1.bytes, sk2.bytes);
    }

    #[test]
    fn keygen_distinct_seeds_distinct_keys() {
        let (pk1, _) = slh_dsa_sha2_128s_keygen(&deterministic_seed(0));
        let (pk2, _) = slh_dsa_sha2_128s_keygen(&deterministic_seed(1));
        assert_ne!(pk1.bytes, pk2.bytes);
    }

    #[test]
    fn sign_verify_roundtrip() {
        let seed = deterministic_seed(0x10);
        let (pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        let msg = b"FIPS 205 SLH-DSA-SHA2-128s smoke test";
        let opt_rand = [0u8; 16];
        let sig = slh_dsa_sha2_128s_sign(&sk, msg, &opt_rand);
        assert_eq!(sig.len(), SIG_BYTES);
        assert!(slh_dsa_sha2_128s_verify(&pk, msg, &sig));
    }

    #[test]
    fn sign_is_deterministic_in_opt_rand() {
        let seed = deterministic_seed(0x20);
        let (_pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        let msg = b"determinism check";
        let opt_rand = [0xabu8; 16];
        let sig1 = slh_dsa_sha2_128s_sign(&sk, msg, &opt_rand);
        let sig2 = slh_dsa_sha2_128s_sign(&sk, msg, &opt_rand);
        assert_eq!(sig1, sig2);
    }

    #[test]
    fn sign_changes_with_opt_rand() {
        let seed = deterministic_seed(0x30);
        let (_pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        let msg = b"randomization check";
        let sig1 = slh_dsa_sha2_128s_sign(&sk, msg, &[0u8; 16]);
        let sig2 = slh_dsa_sha2_128s_sign(&sk, msg, &[1u8; 16]);
        assert_ne!(sig1, sig2);
    }

    #[test]
    fn verify_rejects_flipped_message_bit() {
        let seed = deterministic_seed(0x40);
        let (pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        let msg = b"original message";
        let sig = slh_dsa_sha2_128s_sign(&sk, msg, &[0u8; 16]);
        let mut tampered = msg.to_vec();
        tampered[0] ^= 0x01;
        assert!(!slh_dsa_sha2_128s_verify(&pk, &tampered, &sig));
    }

    #[test]
    fn verify_rejects_flipped_signature_byte() {
        let seed = deterministic_seed(0x50);
        let (pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        let msg = b"another message";
        let mut sig = slh_dsa_sha2_128s_sign(&sk, msg, &[0u8; 16]);
        // Flip a byte in the FORS portion.
        sig[N + 5] ^= 0x80;
        assert!(!slh_dsa_sha2_128s_verify(&pk, msg, &sig));
    }

    #[test]
    fn verify_rejects_truncated_signature() {
        let seed = deterministic_seed(0x60);
        let (pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        let msg = b"truncation test";
        let sig = slh_dsa_sha2_128s_sign(&sk, msg, &[0u8; 16]);
        let short = &sig[..sig.len() - 1];
        assert!(!slh_dsa_sha2_128s_verify(&pk, msg, short));
        let oversized = {
            let mut v = sig.clone();
            v.push(0);
            v
        };
        assert!(!slh_dsa_sha2_128s_verify(&pk, msg, &oversized));
    }

    #[test]
    fn verify_rejects_wrong_public_key() {
        let seed_a = deterministic_seed(0xa0);
        let seed_b = deterministic_seed(0xb0);
        let (_pk_a, sk_a) = slh_dsa_sha2_128s_keygen(&seed_a);
        let (pk_b, _sk_b) = slh_dsa_sha2_128s_keygen(&seed_b);
        let msg = b"cross-key forgery resistance";
        let sig = slh_dsa_sha2_128s_sign(&sk_a, msg, &[0u8; 16]);
        assert!(!slh_dsa_sha2_128s_verify(&pk_b, msg, &sig));
    }

    #[test]
    fn multiple_messages_under_same_key_verify() {
        let seed = deterministic_seed(0x70);
        let (pk, sk) = slh_dsa_sha2_128s_keygen(&seed);
        for i in 0..3u8 {
            let msg = vec![i; 1 + (i as usize) * 17];
            let sig = slh_dsa_sha2_128s_sign(&sk, &msg, &[i; 16]);
            assert!(slh_dsa_sha2_128s_verify(&pk, &msg, &sig), "iter {i}");
        }
    }
}
