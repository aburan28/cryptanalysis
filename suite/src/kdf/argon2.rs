//! **Argon2** — memory-hard password hashing function (RFC 9106, PHC winner 2015).
//!
//! Argon2 is the modern successor to scrypt/bcrypt/PBKDF2 for password
//! storage and KDF use.  It forces an attacker to allocate a large
//! memory matrix (q × 1024 bytes) and pay area-time on custom hardware,
//! while letting the defender tune memory, time, and parallelism
//! independently.  Three variants:
//!
//! * **Argon2d** — data-dependent addressing; max GPU/ASIC resistance,
//!   but the reference indices leak through cache-timing side channels.
//!   Use only where the input is not adversarially chosen (e.g. KDF of
//!   a high-entropy secret on a trusted host).
//! * **Argon2i** — data-independent addressing; immune to memory-access
//!   side channels.  Weaker against time-memory trade-offs.  Suitable
//!   for password hashing on shared hardware.
//! * **Argon2id** — first half-pass uses i-style addressing, then
//!   switches to d-style.  The RFC §4 recommendation for general use.
//!
//! # Algorithm (RFC 9106 §3)
//! 1. H₀ = BLAKE2b-512( parameters ‖ password ‖ salt ‖ key ‖ associated )
//! 2. Allocate matrix B of `p` lanes × `q/p` columns of 1024-byte blocks.
//! 3. Seed first two columns of each lane via H' (variable-length BLAKE2b).
//! 4. For each of `t` passes, over 4 vertical slices, fill each column
//!    `B[i,j] = G(B[i,j-1], B[ref])` where `ref` is chosen per variant.
//!    Subsequent passes XOR into the existing block (RFC §3.6).
//! 5. Tag = H'( XOR of all final-column blocks, out_len ).
//!
//! The compression function **G** is two passes of the BLAKE2b round
//! function over an 8×8 matrix of 16-byte words, feed-forwarded with
//! the input XOR (RFC §3.6.1).
//!
//! # Parameter tuning (RFC 9106 §4)
//! * `m_kib` — memory in KiB.  Interactive logins: 64 MiB.  Backend
//!   key derivation: 256 MiB – 1 GiB.  Must be ≥ `8 * p_lanes`.
//! * `t_passes` — iterations.  RFC default `t = 1` for Argon2id at
//!   high memory; raise if memory must be reduced.
//! * `p_lanes` — parallelism; one thread per lane.  Typically 1–4.
//! * `out_len` — tag length in bytes; 32 is standard for keys/MACs.

use crate::hash::blake2b::blake2b;

// ── Variant ──────────────────────────────────────────────────────────────────

#[derive(Copy, Clone, Debug, PartialEq, Eq)]
pub enum Argon2Variant {
    D,
    I,
    Id,
}

impl Argon2Variant {
    #[inline]
    fn id(self) -> u32 {
        match self {
            Argon2Variant::D => 0,
            Argon2Variant::I => 1,
            Argon2Variant::Id => 2,
        }
    }
}

const VERSION: u32 = 0x13;
const BLOCK_BYTES: usize = 1024;
const SYNC_POINTS: u32 = 4; // four vertical slices per pass

// ── H' — variable-length BLAKE2b (RFC 9106 §3.2) ─────────────────────────────

/// H'(input, out_len): produce `out_len` bytes by chaining 64-byte
/// BLAKE2b calls when `out_len > 64`, taking 32 bytes per intermediate.
fn h_prime(input: &[u8], out_len: usize) -> Vec<u8> {
    let mut prefixed = Vec::with_capacity(4 + input.len());
    prefixed.extend_from_slice(&(out_len as u32).to_le_bytes());
    prefixed.extend_from_slice(input);

    if out_len <= 64 {
        return blake2b(&prefixed, out_len);
    }

    // r = ceil(out_len / 32) - 2 full 32-byte stripes, then a final 64-byte block.
    // Equivalently: produce r blocks of 64 bytes, taking the first 32 of each,
    // until only ≤ 64 bytes remain; then hash those at full width.
    let mut out = Vec::with_capacity(out_len);
    let mut v = blake2b(&prefixed, 64);
    out.extend_from_slice(&v[..32]);
    let mut remaining = out_len - 32;
    while remaining > 64 {
        v = blake2b(&v, 64);
        out.extend_from_slice(&v[..32]);
        remaining -= 32;
    }
    let last = blake2b(&v, remaining);
    out.extend_from_slice(&last);
    debug_assert_eq!(out.len(), out_len);
    out
}

// ── G compression function (RFC 9106 §3.6 / §3.7) ────────────────────────────

/// BLAKE2b's GB mixing function — operates on 64-bit words but with
/// the Argon2-specific multiplication step replacing the first add of
/// each pair (RFC 9106 §3.7).  Note: Argon2 uses the BLAKE2b rotation
/// schedule (32/24/16/63) but with `a = a + b + 2*lo(a)*lo(b)` instead
/// of plain `a = a + b`.
#[inline]
fn gb(v: &mut [u64], a: usize, b: usize, c: usize, d: usize) {
    let mul = |x: u64, y: u64| {
        2u64.wrapping_mul(x & 0xFFFF_FFFF)
            .wrapping_mul(y & 0xFFFF_FFFF)
    };
    v[a] = v[a].wrapping_add(v[b]).wrapping_add(mul(v[a], v[b]));
    v[d] = (v[d] ^ v[a]).rotate_right(32);
    v[c] = v[c].wrapping_add(v[d]).wrapping_add(mul(v[c], v[d]));
    v[b] = (v[b] ^ v[c]).rotate_right(24);
    v[a] = v[a].wrapping_add(v[b]).wrapping_add(mul(v[a], v[b]));
    v[d] = (v[d] ^ v[a]).rotate_right(16);
    v[c] = v[c].wrapping_add(v[d]).wrapping_add(mul(v[c], v[d]));
    v[b] = (v[b] ^ v[c]).rotate_right(63);
}

/// P — apply BLAKE2b's round (8 GB calls in a fixed pattern) to a
/// 16-word (128-byte) array.
#[inline]
fn p_round(v: &mut [u64; 16]) {
    gb(v, 0, 4, 8, 12);
    gb(v, 1, 5, 9, 13);
    gb(v, 2, 6, 10, 14);
    gb(v, 3, 7, 11, 15);
    gb(v, 0, 5, 10, 15);
    gb(v, 1, 6, 11, 12);
    gb(v, 2, 7, 8, 13);
    gb(v, 3, 4, 9, 14);
}

/// G(X, Y): compress two 1024-byte blocks into one.
///
/// R = X XOR Y.  Apply P row-wise on the 8×8 matrix of 16-byte words
/// (each row is 16 words of 64-bit, i.e. 128 bytes), then column-wise
/// on the same view (each column being 16 words spread across rows).
/// Output = result XOR R (feed-forward).
fn g_compress(x: &[u8; BLOCK_BYTES], y: &[u8; BLOCK_BYTES], out: &mut [u8; BLOCK_BYTES]) {
    let mut r = [0u64; 128];
    for i in 0..128 {
        let xi = u64::from_le_bytes(x[8 * i..8 * i + 8].try_into().unwrap());
        let yi = u64::from_le_bytes(y[8 * i..8 * i + 8].try_into().unwrap());
        r[i] = xi ^ yi;
    }
    let original = r;

    // Row-wise: 8 rows, each row is 16 consecutive u64 words.
    let mut buf = [0u64; 16];
    for row in 0..8 {
        for k in 0..16 {
            buf[k] = r[row * 16 + k];
        }
        p_round(&mut buf);
        for k in 0..16 {
            r[row * 16 + k] = buf[k];
        }
    }

    // Column-wise: 8 columns, each column is 16 u64 words built from
    // (2*col, 2*col+1) of each of the 8 rows.
    for col in 0..8 {
        for row in 0..8 {
            buf[2 * row] = r[row * 16 + 2 * col];
            buf[2 * row + 1] = r[row * 16 + 2 * col + 1];
        }
        p_round(&mut buf);
        for row in 0..8 {
            r[row * 16 + 2 * col] = buf[2 * row];
            r[row * 16 + 2 * col + 1] = buf[2 * row + 1];
        }
    }

    for i in 0..128 {
        let w = r[i] ^ original[i];
        out[8 * i..8 * i + 8].copy_from_slice(&w.to_le_bytes());
    }
}

/// G with XOR-into-existing-output (used on passes ≥ 1 per RFC §3.6).
fn g_compress_xor(x: &[u8; BLOCK_BYTES], y: &[u8; BLOCK_BYTES], out: &mut [u8; BLOCK_BYTES]) {
    let mut tmp = [0u8; BLOCK_BYTES];
    g_compress(x, y, &mut tmp);
    for i in 0..BLOCK_BYTES {
        out[i] ^= tmp[i];
    }
}

// ── Reference-index calculation (RFC 9106 §3.4) ──────────────────────────────

/// Compute (ref_lane, ref_index) for the current block, given the
/// pseudorandom 64-bit value (J1 in the low 32 bits, J2 in the high
/// 32 bits) and the lane/slice/column context.
fn ref_position(
    pseudo_rand: u64,
    pass: u32,
    lane: u32,
    slice: u32,
    index_in_segment: u32,
    p_lanes: u32,
    segment_len: u32,
    lane_len: u32,
    same_lane: bool, // whether reference is forced to the current lane
) -> (u32, u32) {
    let j1 = (pseudo_rand & 0xFFFF_FFFF) as u32;
    let j2 = (pseudo_rand >> 32) as u32;

    let ref_lane = if same_lane { lane } else { j2 % p_lanes };

    // Size of the reference set W (RFC §3.4): all finished segments of
    // ref_lane, plus the already-filled part of the current segment if
    // ref_lane == lane, minus 1 for the immediately preceding block.
    let mut ref_area_size: u32 = if pass == 0 {
        if slice == 0 {
            // Pass 0, slice 0: only current segment counts.
            index_in_segment - 1
        } else if ref_lane == lane {
            slice * segment_len + index_in_segment - 1
        } else {
            slice * segment_len - if index_in_segment == 0 { 1 } else { 0 }
        }
    } else if ref_lane == lane {
        lane_len - segment_len + index_in_segment - 1
    } else {
        lane_len - segment_len - if index_in_segment == 0 { 1 } else { 0 }
    };

    // Non-uniform mapping J1 → relative position (RFC §3.4.1.2).
    let mut rel = j1 as u64;
    rel = (rel * rel) >> 32;
    rel = (ref_area_size as u64 * rel) >> 32;
    let rel = ref_area_size as u64 - 1 - rel;

    // Starting position depends on pass: on pass ≥ 1, the reference
    // window starts right after the current slice.
    let start_pos: u32 = if pass != 0 && slice != SYNC_POINTS - 1 {
        (slice + 1) * segment_len
    } else {
        0
    };

    // Absolute position in ref_lane.
    let abs = ((start_pos as u64 + rel) % lane_len as u64) as u32;
    // Avoid unused warning on rare paths.
    let _ = &mut ref_area_size;
    (ref_lane, abs)
}

// ── Address block generation for Argon2i / Argon2id pass-0 first-half ────────

/// Generate one 1024-byte block of pseudorandom (J1‖J2) pairs for
/// data-independent addressing.  RFC 9106 §3.4.1.1: addresses come
/// from G(zero, G(zero, input_block)) where input_block encodes
/// (pass, lane, slice, total_blocks, total_passes, type, counter).
fn fill_address_block(
    addresses: &mut [u8; BLOCK_BYTES],
    pass: u32,
    lane: u32,
    slice: u32,
    total_blocks: u32,
    total_passes: u32,
    variant_id: u32,
    counter: u32,
) {
    let mut input = [0u8; BLOCK_BYTES];
    input[0..8].copy_from_slice(&(pass as u64).to_le_bytes());
    input[8..16].copy_from_slice(&(lane as u64).to_le_bytes());
    input[16..24].copy_from_slice(&(slice as u64).to_le_bytes());
    input[24..32].copy_from_slice(&(total_blocks as u64).to_le_bytes());
    input[32..40].copy_from_slice(&(total_passes as u64).to_le_bytes());
    input[40..48].copy_from_slice(&(variant_id as u64).to_le_bytes());
    input[48..56].copy_from_slice(&(counter as u64).to_le_bytes());

    let zero = [0u8; BLOCK_BYTES];
    let mut tmp = [0u8; BLOCK_BYTES];
    g_compress(&zero, &input, &mut tmp);
    g_compress(&zero, &tmp, addresses);
}

// ── Public API ───────────────────────────────────────────────────────────────

/// Argon2 password hashing.  See module docstring for parameter
/// guidance.  Returns the `out_len`-byte tag.
pub fn argon2(
    variant: Argon2Variant,
    password: &[u8],
    salt: &[u8],
    key: &[u8],
    associated: &[u8],
    m_kib: u32,
    t_passes: u32,
    p_lanes: u32,
    out_len: u32,
) -> Result<Vec<u8>, &'static str> {
    if !(1..=0x00FF_FFFF).contains(&p_lanes) {
        return Err("argon2: p_lanes must be in 1..=2^24-1");
    }
    if t_passes < 1 {
        return Err("argon2: t_passes must be >= 1");
    }
    if out_len < 4 {
        return Err("argon2: out_len must be >= 4");
    }
    if m_kib < 8 * p_lanes {
        return Err("argon2: m_kib must be >= 8 * p_lanes");
    }

    // Round m_kib down to nearest multiple of 4*p_lanes (RFC §3.2).
    let m_prime = (m_kib / (4 * p_lanes)) * (4 * p_lanes);
    let lane_len = m_prime / p_lanes; // columns per lane (q/p)
    let segment_len = lane_len / SYNC_POINTS;
    let total_blocks = m_prime;

    // ── H₀: BLAKE2b-512 of the parameter pre-image ──
    let mut pre =
        Vec::with_capacity(40 + password.len() + salt.len() + key.len() + associated.len());
    pre.extend_from_slice(&p_lanes.to_le_bytes());
    pre.extend_from_slice(&out_len.to_le_bytes());
    pre.extend_from_slice(&m_kib.to_le_bytes());
    pre.extend_from_slice(&t_passes.to_le_bytes());
    pre.extend_from_slice(&VERSION.to_le_bytes());
    pre.extend_from_slice(&variant.id().to_le_bytes());
    pre.extend_from_slice(&(password.len() as u32).to_le_bytes());
    pre.extend_from_slice(password);
    pre.extend_from_slice(&(salt.len() as u32).to_le_bytes());
    pre.extend_from_slice(salt);
    pre.extend_from_slice(&(key.len() as u32).to_le_bytes());
    pre.extend_from_slice(key);
    pre.extend_from_slice(&(associated.len() as u32).to_le_bytes());
    pre.extend_from_slice(associated);
    let h0 = blake2b(&pre, 64); // 64 bytes

    // ── Memory matrix: total_blocks × 1024 bytes, lane-major ──
    // B[lane * lane_len + col] is the (lane, col) block.
    let mut memory: Vec<[u8; BLOCK_BYTES]> = vec![[0u8; BLOCK_BYTES]; total_blocks as usize];

    // Seed first two columns of each lane via H'(H0 ‖ LE32(col) ‖ LE32(lane), 1024).
    let mut seed = Vec::with_capacity(64 + 8);
    for lane in 0..p_lanes {
        for col in 0..2u32 {
            seed.clear();
            seed.extend_from_slice(&h0);
            seed.extend_from_slice(&col.to_le_bytes());
            seed.extend_from_slice(&lane.to_le_bytes());
            let block = h_prime(&seed, BLOCK_BYTES);
            let idx = (lane * lane_len + col) as usize;
            memory[idx].copy_from_slice(&block);
        }
    }

    // ── Fill the remaining columns over t_passes passes × 4 slices × p lanes ──
    let variant_id = variant.id();
    for pass in 0..t_passes {
        for slice in 0..SYNC_POINTS {
            for lane in 0..p_lanes {
                fill_segment(
                    &mut memory,
                    pass,
                    slice,
                    lane,
                    variant,
                    variant_id,
                    p_lanes,
                    lane_len,
                    segment_len,
                    total_blocks,
                    t_passes,
                );
            }
        }
    }

    // ── Final XOR of last column across all lanes; then H' to out_len ──
    let mut c = [0u8; BLOCK_BYTES];
    for lane in 0..p_lanes {
        let idx = (lane * lane_len + (lane_len - 1)) as usize;
        for i in 0..BLOCK_BYTES {
            c[i] ^= memory[idx][i];
        }
    }
    Ok(h_prime(&c, out_len as usize))
}

#[allow(clippy::too_many_arguments)]
fn fill_segment(
    memory: &mut [[u8; BLOCK_BYTES]],
    pass: u32,
    slice: u32,
    lane: u32,
    variant: Argon2Variant,
    variant_id: u32,
    p_lanes: u32,
    lane_len: u32,
    segment_len: u32,
    total_blocks: u32,
    t_passes: u32,
) {
    // Argon2i-style addressing is used for: Argon2i always; or Argon2id
    // in pass 0, slices 0-1 only.
    let use_independent = match variant {
        Argon2Variant::I => true,
        Argon2Variant::Id => pass == 0 && slice < SYNC_POINTS / 2,
        Argon2Variant::D => false,
    };

    let mut address_block = [0u8; BLOCK_BYTES];
    let mut address_counter: u32 = 0;

    // Starting column in this segment.  Pass 0 / slice 0 skips columns 0,1
    // (already seeded).
    let starting_index: u32 = if pass == 0 && slice == 0 { 2 } else { 0 };

    if use_independent {
        // Pre-compute the first address block (counter starts at 1).
        address_counter = 1;
        fill_address_block(
            &mut address_block,
            pass,
            lane,
            slice,
            total_blocks,
            t_passes,
            variant_id,
            address_counter,
        );
    }

    for i in starting_index..segment_len {
        let cur_col = slice * segment_len + i;
        let prev_col = if cur_col == 0 {
            lane_len - 1
        } else {
            cur_col - 1
        };
        let cur_idx = (lane * lane_len + cur_col) as usize;
        let prev_idx = (lane * lane_len + prev_col) as usize;

        // Compute J1‖J2.
        let pseudo_rand = if use_independent {
            // 128 J1/J2 pairs per address block (each 8 bytes).
            let off_in_block = (i % 128) as usize;
            if i != starting_index && off_in_block == 0 {
                address_counter += 1;
                fill_address_block(
                    &mut address_block,
                    pass,
                    lane,
                    slice,
                    total_blocks,
                    t_passes,
                    variant_id,
                    address_counter,
                );
            }
            u64::from_le_bytes(
                address_block[off_in_block * 8..off_in_block * 8 + 8]
                    .try_into()
                    .unwrap(),
            )
        } else {
            u64::from_le_bytes(memory[prev_idx][..8].try_into().unwrap())
        };

        // "Same lane" constraint: pass 0 slice 0 always uses current lane.
        let same_lane = pass == 0 && slice == 0;
        let (ref_lane, ref_col) = ref_position(
            pseudo_rand,
            pass,
            lane,
            slice,
            i,
            p_lanes,
            segment_len,
            lane_len,
            same_lane,
        );
        let ref_idx = (ref_lane * lane_len + ref_col) as usize;

        // SAFETY-of-borrow trick: we read prev_idx and ref_idx, write cur_idx.
        // All three may alias the same lane.  Clone the two reads.
        let prev = memory[prev_idx];
        let refb = memory[ref_idx];

        if pass == 0 {
            g_compress(&prev, &refb, &mut memory[cur_idx]);
        } else {
            g_compress_xor(&prev, &refb, &mut memory[cur_idx]);
        }
    }
}

/// Convenience wrapper: Argon2id with no secret key and no associated data.
pub fn argon2id(
    password: &[u8],
    salt: &[u8],
    m_kib: u32,
    t: u32,
    p: u32,
    out_len: u32,
) -> Result<Vec<u8>, &'static str> {
    argon2(
        Argon2Variant::Id,
        password,
        salt,
        &[],
        &[],
        m_kib,
        t,
        p,
        out_len,
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn h(s: &str) -> Vec<u8> {
        hex::decode(s).unwrap()
    }

    // ── RFC 9106 §5.2–5.4 official test vectors ──────────────────────────────

    #[test]
    fn argon2d_rfc9106_5_2() {
        let pw = [1u8; 32];
        let salt = [2u8; 16];
        let key = [3u8; 8];
        let ad = [4u8; 12];
        let tag = argon2(Argon2Variant::D, &pw, &salt, &key, &ad, 32, 3, 4, 32).unwrap();
        assert_eq!(
            tag,
            h("512b391b6f1162975371d30919734294f868e3be3984f3c1a13a4db9fabe4acb"),
        );
    }

    #[test]
    fn argon2i_rfc9106_5_3() {
        let pw = [1u8; 32];
        let salt = [2u8; 16];
        let key = [3u8; 8];
        let ad = [4u8; 12];
        let tag = argon2(Argon2Variant::I, &pw, &salt, &key, &ad, 32, 3, 4, 32).unwrap();
        assert_eq!(
            tag,
            h("c814d9d1dc7f37aa13f0d77f2494bda1c8de6b016dd388d29952a4c4672b6ce8"),
        );
    }

    #[test]
    fn argon2id_rfc9106_5_4() {
        let pw = [1u8; 32];
        let salt = [2u8; 16];
        let key = [3u8; 8];
        let ad = [4u8; 12];
        let tag = argon2(Argon2Variant::Id, &pw, &salt, &key, &ad, 32, 3, 4, 32).unwrap();
        assert_eq!(
            tag,
            h("0d640df58d78766c08c037a34a8b53c9d01ef0452d75b65eb52520e96b01e659"),
        );
    }

    #[test]
    fn argon2id_no_key_no_ad() {
        // Smoke test the convenience wrapper: just verify it runs and
        // returns the requested length, deterministically.
        let a = argon2id(
            b"correct horse battery staple",
            b"some salt 1234567",
            32,
            2,
            1,
            32,
        )
        .unwrap();
        let b = argon2id(
            b"correct horse battery staple",
            b"some salt 1234567",
            32,
            2,
            1,
            32,
        )
        .unwrap();
        assert_eq!(a, b);
        assert_eq!(a.len(), 32);
    }

    #[test]
    fn argon2id_different_passwords_differ() {
        let a = argon2id(b"password1", b"saltsaltsaltsalt", 32, 1, 1, 32).unwrap();
        let b = argon2id(b"password2", b"saltsaltsaltsalt", 32, 1, 1, 32).unwrap();
        assert_ne!(a, b);
    }

    #[test]
    fn argon2id_different_salts_differ() {
        let a = argon2id(b"password", b"saltA_____________", 32, 1, 1, 32).unwrap();
        let b = argon2id(b"password", b"saltB_____________", 32, 1, 1, 32).unwrap();
        assert_ne!(a, b);
    }

    #[test]
    fn argon2_rejects_bad_parameters() {
        // p_lanes = 0
        assert!(argon2(Argon2Variant::Id, b"p", b"saltsalt", &[], &[], 32, 1, 0, 32).is_err());
        // t_passes = 0
        assert!(argon2(Argon2Variant::Id, b"p", b"saltsalt", &[], &[], 32, 0, 1, 32).is_err());
        // out_len < 4
        assert!(argon2(Argon2Variant::Id, b"p", b"saltsalt", &[], &[], 32, 1, 1, 3).is_err());
        // m_kib < 8 * p_lanes
        assert!(argon2(Argon2Variant::Id, b"p", b"saltsalt", &[], &[], 7, 1, 1, 32).is_err());
    }

    #[test]
    fn argon2id_long_output() {
        // out_len > 64 exercises the H' chained branch.
        let tag = argon2id(b"password", b"saltsaltsaltsalt", 32, 1, 1, 128).unwrap();
        assert_eq!(tag.len(), 128);
        // Truncating must equal the same call with a shorter out_len?  No:
        // H' uses out_len as a prefix to the BLAKE2b call, so different
        // out_len produces an entirely different output.  Just check that
        // determinism holds and length is correct.
        let tag2 = argon2id(b"password", b"saltsaltsaltsalt", 32, 1, 1, 128).unwrap();
        assert_eq!(tag, tag2);
    }
}
