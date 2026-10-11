//! MD5 chosen-prefix collision pipeline — end-to-end demonstration.
//!
//! Walks through the four phases of a Flame-class chosen-prefix
//! collision attack using the machinery in
//! [`crypto::cryptanalysis::md5_chosen_prefix`]:
//!
//!   Phase 0. Verify Wang's published colliding pair (sanity check).
//!   Phase 1. Compute IHVs for two distinct chosen prefixes.
//!   Phase 2. Birthday-phase IHV alignment (rho with distinguished points).
//!   Phase 3. Near-collision block chain composer (demonstrates the
//!            framework; full chain construction requires an online
//!            path generator — see hashclash FFI module).
//!
//! Run with:
//!   cargo run --release --example md5_chosen_prefix_demo

use cryptanalysis_suite::cryptanalysis::md5_chosen_prefix::{
    apply_delta_m, compose_near_collision_chain, find_near_collision_block, ihv_after_prefix,
    parse_conditions_table, rho_chosen_prefix_birthday, trace_block, WalkSide, WANG_BLOCK1_ROUND1,
    WANG_DELTA_M0, WANG_DELTA_M1, WANG_M, WANG_M_PRIME,
};
use cryptanalysis_suite::cryptanalysis::md5_differential::{md5, MD5_IV};
use cryptanalysis_suite::cryptanalysis::md5_hashclash_ffi::{
    ChosenPrefixCollision, FfiError, HASHCLASH_LINKED,
};
use std::time::Instant;

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{:02x}", x)).collect()
}

fn banner(s: &str) {
    println!("\n╔{:═<78}╗", "");
    println!("║ {:<76} ║", s);
    println!("╚{:═<78}╝", "");
}

fn main() {
    println!("MD5 Chosen-Prefix Collision Pipeline — Wang / Stevens / Flame lineage");
    println!("====================================================================");

    // ── Phase 0: Verify Wang's published colliding pair ──────────────
    banner("PHASE 0 — Wang published-pair regression");
    let h1 = md5(&WANG_M, 64);
    let h2 = md5(&WANG_M_PRIME, 64);
    println!("  MD5(M)  = {}", hex(&h1));
    println!("  MD5(M') = {}", hex(&h2));
    assert_eq!(h1, h2, "Wang pair must collide");
    assert_ne!(WANG_M, WANG_M_PRIME, "M and M' must differ");
    let diff_bits: u32 = WANG_M
        .iter()
        .zip(WANG_M_PRIME.iter())
        .map(|(a, b)| (a ^ b).count_ones())
        .sum();
    println!("  M ≠ M' in {} bits across 1024", diff_bits);
    println!("  → Confirmed: published Wang 2004 collision verified.");

    // Demonstrate apply_delta_m round-trip.
    let mut m0 = [0u8; 64];
    m0.copy_from_slice(&WANG_M[..64]);
    let m0_p = apply_delta_m(&m0, &WANG_DELTA_M0);
    assert_eq!(&m0_p[..], &WANG_M_PRIME[..64]);
    println!("  → apply_delta_m(WANG_M_0, ΔM_0) reproduces WANG_M'_0.");
    let _ = WANG_DELTA_M1; // exported for completeness

    // ── Phase 1: IHV computation for chosen prefixes ──────────────────
    banner("PHASE 1 — IHV computation for two chosen prefixes");
    // Prefixes must exceed one MD5 block (64 bytes) for IHVs to
    // diverge from MD5_IV — otherwise the chosen-prefix problem is
    // vacuous.  Real attacks use ≥1 full block of attacker-controlled
    // content (e.g. a complete X.509 TBSCertificate prefix).
    let prefix_p = b"From: Alice <alice@example.com>\nSubject: Loan approval (counterparty: A)\nDate: Mon, 25 May 2026\nPlease honour the attached cheque.\n";
    let prefix_q = b"From: Mallory <mal@evil.org>\nSubject: Wire $10M to account 999\nDate: Mon, 25 May 2026\nUrgent - process immediately.\n";
    let (iv_p, tail_p) = ihv_after_prefix(prefix_p);
    let (iv_q, tail_q) = ihv_after_prefix(prefix_q);
    println!("  prefix_P = {:?}", std::str::from_utf8(prefix_p).unwrap());
    println!("  prefix_Q = {:?}", std::str::from_utf8(prefix_q).unwrap());
    println!(
        "  IHV_P = {:08x?}  (residual tail {} bytes)",
        iv_p,
        tail_p.len()
    );
    println!(
        "  IHV_Q = {:08x?}  (residual tail {} bytes)",
        iv_q,
        tail_q.len()
    );
    let initial_delta = [
        iv_q[0].wrapping_sub(iv_p[0]),
        iv_q[1].wrapping_sub(iv_p[1]),
        iv_q[2].wrapping_sub(iv_p[2]),
        iv_q[3].wrapping_sub(iv_p[3]),
    ];
    println!("  ΔIHV_initial = {:08x?}", initial_delta);
    println!(
        "  popcount(ΔIHV) = {}",
        initial_delta.iter().map(|d| d.count_ones()).sum::<u32>()
    );

    // ── Phase 2: Birthday-phase IHV alignment ────────────────────────
    banner("PHASE 2 — Pollard-rho birthday: project IHVs to a common 16-bit slice");
    println!("  Walk function f(s) = MD5_compress(s, block_from(s))");
    println!("  Distinguished-point bits w = 4 (mean walk len ~16)");
    println!("  Projection: low 16 bits of each IHV word (64-bit joint key)");
    println!("  Cross-side detection via WalkSide tag");
    let t0 = Instant::now();
    let r = rho_chosen_prefix_birthday(
        &iv_p, &iv_q, /* proj_bits */ 16, /* dp_bits */ 4, /* max_walks */ 2000,
        /* max_walk_len */ 1024, /* seed */ 0xDEADBEEF,
    );
    let elapsed = t0.elapsed();
    match r {
        Some((sp, p_id, p_start, sq, q_id, q_start)) => {
            println!("  ✓ Cross-side hit after {:.2?}", elapsed);
            println!("    {:?} walk #{} from start {:08x?}", sp, p_id, p_start);
            println!("    {:?} walk #{} from start {:08x?}", sq, q_id, q_start);
            assert_eq!(sp, WalkSide::P);
            assert_eq!(sq, WalkSide::Q);
        }
        None => {
            println!("  · No cross-side hit in 2000 walks ({:.2?}).", elapsed);
            println!("    (At 16-bit projection, birthday cost is ~2^32 walks —");
            println!("    bump max_walks for a real run, or accept this is");
            println!("    a demonstration of the search machinery, not a hit.)");
        }
    }

    // ── Phase 3: Near-collision block chain ──────────────────────────
    banner("PHASE 3 — Near-collision block chain composer");
    println!("  Trivial case: iv_p == iv_q (ΔIHV = 0) → empty chain.");
    let empty = compose_near_collision_chain(&MD5_IV, &MD5_IV, 3, 100, 42);
    println!("  Chain length: {} blocks", empty.len());

    println!("\n  Non-trivial case (Wang's block): single-block identical-prefix.");
    println!("  search_wang_block1 with 1000 trials...");
    let t0 = Instant::now();
    let res = find_near_collision_block(&MD5_IV, &MD5_IV, &[0; 4], 1000, 0xC0FFEE);
    let elapsed = t0.elapsed();
    match res {
        Some(step) => {
            println!(
                "  ✓ Wang-like near-collision block found in {:.2?}",
                elapsed
            );
            println!("    ΔIHV_in  = {:08x?}", step.delta_in);
            println!(
                "    ΔIHV_out = {:08x?} (popcnt {})",
                step.delta_out,
                step.delta_out.iter().map(|d| d.count_ones()).sum::<u32>()
            );
        }
        None => {
            println!("  · No near-collision in 1000 trials ({:.2?}).", elapsed);
            println!("    (Search uses only ~10 of the ~270 SNKO conditions;");
            println!("    success rate per trial is ~2^-24.  Run with larger budget");
            println!("    or load the full conditions table via parse_conditions_table.)");
        }
    }

    // ── Phase 4: Demonstrate conditions-table loader ─────────────────
    banner("PHASE 4 — Conditions-table loader (drop-in for full SNKO table)");
    let example_table = "\
# Wang block-1 round-1 conditions (excerpt — full SNKO table is ~270 lines)
# Format: Q<step> bit<n> <Z|O|E|N>
#   Z = bit must be 0
#   O = bit must be 1
#   E = bit must equal previous Q's bit
#   N = bit must differ from previous Q's bit
Q1 bit6 Z
Q1 bit12 Z
Q1 bit23 Z
Q2 bit6 E
Q2 bit12 O
Q2 bit23 O
Q4 bit23 E
Q5 bit31 Z
Q12 bit15 Z
Q15 bit31 Z
";
    match parse_conditions_table(example_table) {
        Ok(cs) => {
            println!("  Parsed {} conditions:", cs.len());
            for c in &cs {
                println!("    Q[{:2}] bit{:2} {:?}", c.step, c.bit, c.cond);
            }
            // Apply to Wang's block and report satisfaction.
            let mut b = [0u8; 64];
            b.copy_from_slice(&WANG_M[..64]);
            let trace = trace_block(&MD5_IV, &b);
            let sat = cs
                .iter()
                .filter(|c| {
                    use cryptanalysis_suite::cryptanalysis::md5_chosen_prefix::check_condition;
                    check_condition(&trace, c)
                })
                .count();
            println!(
                "  Wang's published block satisfies {}/{} of these.",
                sat,
                cs.len()
            );
        }
        Err(e) => println!("  parse error: {}", e),
    }
    // Also exercise the built-in (uses same encoded table).
    let _ = WANG_BLOCK1_ROUND1;

    // ── Phase 5: hashclash FFI status ────────────────────────────────
    banner("PHASE 5 — hashclash FFI (Marc Stevens' reference implementation)");
    println!(
        "  Compile-time link status: HASHCLASH_LINKED = {}",
        HASHCLASH_LINKED
    );
    let cpc = ChosenPrefixCollision::new(prefix_p, prefix_q);
    match cpc.find() {
        Ok((m, mp)) => {
            println!("  ✓ Real chosen-prefix collision via hashclash:");
            println!("    M  ({} bytes) MD5 = {}", m.len(), hex(&md5(&m, 64)));
            println!("    M' ({} bytes) MD5 = {}", mp.len(), hex(&md5(&mp, 64)));
        }
        Err(FfiError::NotLinked) => {
            println!("  · hashclash not linked at build time (expected default).");
            println!("    To enable real chosen-prefix collisions:");
            println!("      1. git clone https://github.com/cr-marcstevens/hashclash");
            println!("      2. Build with CPC shim (see md5_hashclash_ffi module docs)");
            println!("      3. export HASHCLASH_PREFIX=/path/to/hashclash/install");
            println!("      4. cargo build --release --example md5_chosen_prefix_demo");
        }
        Err(e) => println!("  · FFI error: {:?}", e),
    }

    banner("DONE");
    println!("  Pipeline complete.  See src/cryptanalysis/md5_chosen_prefix.rs");
    println!("  for implementation notes on what's faithful vs. what requires");
    println!("  Stevens-level path-construction (delegated to hashclash FFI).");
}
