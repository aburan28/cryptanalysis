//! **Hash-function construction visualizations** — Merkle-Damgård
//! chain for the MD/SHA-2 family, sponge construction for SHA-3,
//! tree construction for BLAKE3, compression-function state evolution.

use crate::visualize::format_round_bars;

// ── Merkle-Damgård chain diagram ─────────────────────────────────────

/// Render the Merkle-Damgård chain used by MD5, SHA-1, SHA-256,
/// SHA-512, RIPEMD-160.
pub fn demo_merkle_damgard_diagram() -> String {
    let mut s = String::from("# Merkle-Damgård construction\n\n");
    s.push_str(
        "Used by MD4, MD5, SHA-1, SHA-256, SHA-512, RIPEMD-160 — the entire \
         pre-SHA-3 hash family.  Iterates a fixed-size compression function `f` \
         over blocks of the padded message.\n\n",
    );
    s.push_str("```\n");
    s.push_str("                                                                   \n");
    s.push_str("            ┌──────┐    ┌──────┐    ┌──────┐    ┌──────────┐         \n");
    s.push_str("            │ blk0 │    │ blk1 │    │ blk2 │    │ blkN-1   │         \n");
    s.push_str("            │      │    │      │    │      │    │ pad+len  │         \n");
    s.push_str("            └───┬──┘    └───┬──┘    └───┬──┘    └─────┬────┘         \n");
    s.push_str("                ▼           ▼           ▼             ▼              \n");
    s.push_str("    IV ─►──► f(·) ─► H_1 ─► f(·) ─► H_2 ─► f(·) ─► ... ─► f(·) ─► H_N \n");
    s.push_str("                                                                     \n");
    s.push_str("  digest = H_N\n");
    s.push_str("```\n");
    s.push_str(
        "\n**Length-extension vulnerability**: an attacker who knows `H = digest = H_N` \
         can resume `f` from that state and append more blocks — forging `H(prefix || \
         extra)` without knowing the prefix.  Every MD-Damgård hash used as `H(secret || \
         msg)` MAC fails to this.  HMAC fixes it by wrapping `H(K_o || H(K_i || msg))`.\n",
    );
    s
}

// ── Sponge construction for SHA-3 ────────────────────────────────────

/// Render the SHA-3 / Keccak sponge construction.
pub fn demo_sponge_diagram() -> String {
    let mut s = String::from("# Sponge construction (SHA-3, SHAKE)\n\n");
    s.push_str(
        "Used by SHA-3, SHAKE128, SHAKE256.  A permutation `f` rotates a fixed-size \
         state; message blocks XOR into the **rate** portion (`r` bits), output is \
         read from the same.  The **capacity** portion (`c` bits) is never directly \
         touched by input/output, providing the security margin.\n\n",
    );
    s.push_str("```\n");
    s.push_str("                Absorb phase                            Squeeze phase\n");
    s.push_str("                                                                      \n");
    s.push_str("       m_0    m_1    m_2  ...                                         \n");
    s.push_str("        ⊕      ⊕      ⊕                                                \n");
    s.push_str("  ┌─────r─────────────────┐  ←── digest read from r ──┐                \n");
    s.push_str("  │   rate  (r bits)      │   ┌────────┐    ┌────────┐                 \n");
    s.push_str("  ├────────────────────────┤   │   f   │  ──►│   f   │  ──►   ...      \n");
    s.push_str("  │ capacity (c bits) NEVER│   └────────┘    └────────┘                 \n");
    s.push_str("  └────────────────────────┘                                            \n");
    s.push_str("                                                                       \n");
    s.push_str("  state width b = r + c = 1600 bits for SHA-3                          \n");
    s.push_str("  SHA3-256:  r = 1088, c =  512   (security ≈ 128 bits)                 \n");
    s.push_str("  SHA3-512:  r =  576, c = 1024   (security ≈ 256 bits)                 \n");
    s.push_str("  SHAKE128:  r = 1344, c =  256                                         \n");
    s.push_str("  SHAKE256:  r = 1088, c =  512                                         \n");
    s.push_str("```\n");
    s.push_str(
        "\n**No length-extension attack** in sponge mode — the capacity is opaque to \
         attackers, so resuming `f` from the digest doesn't help.\n",
    );
    s
}

// ── BLAKE3 tree diagram ──────────────────────────────────────────────

/// Render the BLAKE3 binary-tree construction.
pub fn demo_blake3_tree_diagram() -> String {
    let mut s = String::from("# BLAKE3 binary-tree mode\n\n");
    s.push_str(
        "BLAKE3 splits the message into 1024-byte **chunks**, hashes each chunk \
         independently with a chunk-position-keyed BLAKE3 compression, then combines \
         the chunk chaining values pairwise in a binary tree.\n\n",
    );
    s.push_str("```\n");
    s.push_str("                                        ROOT\n");
    s.push_str("                                          │\n");
    s.push_str("                       ┌──────────────────┴──────────────────┐\n");
    s.push_str("                       ▼                                     ▼\n");
    s.push_str("                 parent_node                          parent_node\n");
    s.push_str("                       │                                     │\n");
    s.push_str("           ┌───────────┴────────────┐         ┌───────────┴────────────┐\n");
    s.push_str("           ▼                        ▼         ▼                        ▼\n");
    s.push_str("        chunk_0                 chunk_1     chunk_2                 chunk_3\n");
    s.push_str("        (1024B)                 (1024B)     (1024B)                 (1024B)\n");
    s.push_str("```\n");
    s.push_str(
        "\n**Parallelism**: each chunk hashes independently → multi-thread / SIMD friendly.\n\
         **Tree structure**: provides incremental verification and streaming hash trees.\n\
         **Domain separation**: chunk-position counter + flag bits in the compression \
         input prevent cross-chunk extension.\n",
    );
    s
}

// ── SHA-256 round state evolution ────────────────────────────────────

/// Render SHA-256's 8-word state at every 8th round during the
/// compression of a single block.  Shows how the working variables
/// `a, b, c, d, e, f, g, h` diffuse from the initial IV.
pub fn demo_sha256_round_trace(input: &[u8]) -> String {
    let mut s = String::from("# SHA-256 working-variable trace (every 8th round)\n\n");
    s.push_str(
        "Compress one 512-bit block.  Show the 8 working variables `(a,b,c,d,e,f,g,h)` \
         at rounds 0, 8, 16, 24, 32, 40, 48, 56, 64.  See how each is increasingly \
         randomised away from the initial IV.\n\n",
    );
    // Initial SHA-256 IV.
    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
        0x5be0cd19,
    ];
    // Round constants K_t.
    let k: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
        0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
        0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
        0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
        0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
        0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
        0xc67178f2,
    ];
    // Pad input to exactly one 512-bit block (only support short inputs for the demo).
    let mut block = [0u8; 64];
    let n = input.len().min(55);
    block[..n].copy_from_slice(&input[..n]);
    block[n] = 0x80;
    let bit_len = (n as u64) * 8;
    block[56..64].copy_from_slice(&bit_len.to_be_bytes());
    // Message schedule.
    let mut w = [0u32; 64];
    for i in 0..16 {
        w[i] = u32::from_be_bytes([
            block[4 * i],
            block[4 * i + 1],
            block[4 * i + 2],
            block[4 * i + 3],
        ]);
    }
    for i in 16..64 {
        let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
        let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
        w[i] = w[i - 16]
            .wrapping_add(s0)
            .wrapping_add(w[i - 7])
            .wrapping_add(s1);
    }
    let mut a = h[0];
    let mut b = h[1];
    let mut c = h[2];
    let mut d = h[3];
    let mut e = h[4];
    let mut f = h[5];
    let mut g = h[6];
    let mut hh = h[7];
    s.push_str("```\n");
    s.push_str("  round    a        b        c        d        e        f        g        h\n");
    s.push_str(&format!(
        "    0   {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x}\n",
        a, b, c, d, e, f, g, hh
    ));
    for round in 0..64 {
        let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
        let ch = (e & f) ^ (!e & g);
        let t1 = hh
            .wrapping_add(s1)
            .wrapping_add(ch)
            .wrapping_add(k[round])
            .wrapping_add(w[round]);
        let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
        let maj = (a & b) ^ (a & c) ^ (b & c);
        let t2 = s0.wrapping_add(maj);
        hh = g;
        g = f;
        f = e;
        e = d.wrapping_add(t1);
        d = c;
        c = b;
        b = a;
        a = t1.wrapping_add(t2);
        if (round + 1) % 8 == 0 {
            s.push_str(&format!(
                "  {:>3}   {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x}\n",
                round + 1,
                a,
                b,
                c,
                d,
                e,
                f,
                g,
                hh
            ));
        }
    }
    h[0] = h[0].wrapping_add(a);
    h[1] = h[1].wrapping_add(b);
    h[2] = h[2].wrapping_add(c);
    h[3] = h[3].wrapping_add(d);
    h[4] = h[4].wrapping_add(e);
    h[5] = h[5].wrapping_add(f);
    h[6] = h[6].wrapping_add(g);
    h[7] = h[7].wrapping_add(hh);
    s.push_str(&format!(
        "  DIG   {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x}  ← final IV + state\n",
        h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7]
    ));
    s.push_str("```\n");
    s
}

// ── Hash output Hamming-distance "diffusion" curve ───────────────────

/// Render Hamming distance between hash outputs after `i` bit flips
/// of the input, for `i = 1..16`.  Ideal hash gives ~ half the output
/// bits flipped regardless of `i`.
pub fn demo_hash_avalanche() -> String {
    use crate::hash::{md5, sha256};
    let mut s = String::from("# Hash output avalanche (single-bit input perturbations)\n\n");
    s.push_str(
        "Encode a 32-byte message; flip one input bit at increasing positions; \
         measure Hamming distance from the unperturbed digest.\n\n",
    );
    let base: Vec<u8> = (0..32u8).collect();
    let mut hd_md5 = Vec::new();
    let mut hd_sha = Vec::new();
    let h0_md5 = md5(&base);
    let h0_sha = sha256(&base);
    for bit in 0..256 {
        let byte = bit / 8;
        let mask = 1u8 << (bit % 8);
        let mut perturbed = base.clone();
        perturbed[byte] ^= mask;
        let m = md5(&perturbed);
        let s_ = sha256(&perturbed);
        let h1: u32 = m
            .iter()
            .zip(&h0_md5)
            .map(|(a, b)| (a ^ b).count_ones())
            .sum();
        let h2: u32 = s_
            .iter()
            .zip(&h0_sha)
            .map(|(a, b)| (a ^ b).count_ones())
            .sum();
        hd_md5.push(h1 as usize);
        hd_sha.push(h2 as usize);
    }
    // Bin to 16 buckets of 16 bit-flips each, average.
    let mut buckets_md5 = vec![0usize; 16];
    let mut buckets_sha = vec![0usize; 16];
    for i in 0..256 {
        buckets_md5[i / 16] += hd_md5[i];
        buckets_sha[i / 16] += hd_sha[i];
    }
    for v in buckets_md5.iter_mut() {
        *v /= 16;
    }
    for v in buckets_sha.iter_mut() {
        *v /= 16;
    }
    s.push_str("## MD5 (128-bit digest, ideal avalanche ≈ 64 bits)\n\n");
    s.push_str(&format_round_bars(
        &buckets_md5,
        "Mean Hamming distance per input-bit bucket",
        30,
    ));
    s.push_str("\n## SHA-256 (256-bit digest, ideal avalanche ≈ 128 bits)\n\n");
    s.push_str(&format_round_bars(
        &buckets_sha,
        "Mean Hamming distance per input-bit bucket",
        30,
    ));
    s
}

// ── Aggregate ────────────────────────────────────────────────────────

pub fn run_all_hash_demos() -> String {
    let mut s = String::new();
    s.push_str("# Hash-function visual-demo bundle\n\n---\n\n");
    s.push_str(&demo_merkle_damgard_diagram());
    s.push_str("\n---\n\n");
    s.push_str(&demo_sponge_diagram());
    s.push_str("\n---\n\n");
    s.push_str(&demo_blake3_tree_diagram());
    s.push_str("\n---\n\n");
    s.push_str(&demo_sha256_round_trace(b"abc"));
    s.push_str("\n---\n\n");
    s.push_str(&demo_hash_avalanche());
    s
}

// ── Tests ────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn merkle_damgard_renders() {
        let s = demo_merkle_damgard_diagram();
        assert!(s.contains("Merkle-Damgård"));
        assert!(s.contains("Length-extension"));
    }

    #[test]
    fn sponge_renders_capacity_explanation() {
        let s = demo_sponge_diagram();
        assert!(s.contains("Sponge"));
        assert!(s.contains("rate"));
        assert!(s.contains("capacity"));
        assert!(s.contains("SHA3-256"));
    }

    #[test]
    fn blake3_tree_renders() {
        let s = demo_blake3_tree_diagram();
        assert!(s.contains("BLAKE3"));
        assert!(s.contains("chunk_0"));
        assert!(s.contains("parent_node"));
    }

    #[test]
    fn sha256_trace_shows_rounds() {
        let s = demo_sha256_round_trace(b"abc");
        assert!(s.contains("round"));
        assert!(s.contains("DIG"));
        // FIPS 180-4 SHA-256("abc") = ba7816bf8f01cfea4141...
        assert!(s.contains("ba7816bf"));
    }

    #[test]
    fn hash_avalanche_renders_both() {
        let s = demo_hash_avalanche();
        assert!(s.contains("MD5"));
        assert!(s.contains("SHA-256"));
    }

    #[test]
    fn aggregate_runs_clean() {
        let s = run_all_hash_demos();
        assert!(s.contains("Merkle-Damgård"));
        assert!(s.contains("Sponge"));
        assert!(s.contains("BLAKE3"));
        assert!(s.contains("SHA-256"));
    }

    #[test]
    #[ignore]
    fn demo_all_hash_visuals() {
        println!("{}", run_all_hash_demos());
    }
}
