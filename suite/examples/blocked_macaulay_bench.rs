//! Does the block structure of the decomposition systems pay?
//!
//! `research/notes/ecc2k130/RESEARCH_KOBLITZ_INDEX_CALCULUS.md` lists, under *Open problems
//! from the talk*:
//!
//! > Exploiting the block/homogeneous structure of the resulting
//! > polynomial systems in the Gröbner step.  The systems are now
//! > actually built (`koblitz_groebner`), so this is measurable rather
//! > than hypothetical: the `m ≥ 3` chained systems are where it would
//! > pay.
//!
//! The structure is that the systems are **multilinear** with respect
//! to the natural block partition — one block of `ℓ` per summand, one
//! of `n` per intermediate point of the chain — degree at most one in
//! each block, even though the total degree is 2 for `m = 2` and 3 once
//! the chain appears.  Squaring is `F_2`-linear in characteristic 2 and
//! `x₁x₂` is bilinear, which is where it comes from.
//!
//! A total-degree Macaulay matrix ignores that and spends most of its
//! columns on monomials of high degree inside one block — exactly the
//! monomials the structure says cannot help.  Bounding the degree *per
//! block* instead takes the column count from `C(v, ≤D)` to
//! `Π_i C(v_i, ≤d_i)`.
//!
//! ```bash
//! cargo run --release --example blocked_macaulay_bench
//! ```
//!
//! ## What is measured, and why refutation
//!
//! **Refutation.**  A random target does not decompose, and rejection
//! is most of an attack's work; it is also the case the algebra is
//! supposed to win, in the words of the Koblitz note — *"It refutes.
//! …an answer exhaustive search cannot give in kind, only by exhausting
//! the space."*  A decomposable target has many roots and no reduction
//! pins a variable, so "did it decide" is not a question either engine
//! answers there without a search on top; the infeasibility certificate
//! is the clean, engine-neutral event.
//!
//! So: random `x_R`, both engines asked for the constant `1`, cost
//! compared in 64-bit word XORs — the same unit as `crossbred_bench`.
//! Targets where either engine fails to refute are excluded from the
//! ratio and counted in its own column rather than scored.

use cryptanalysis_suite::binary_ecc::F2mElement;
use cryptanalysis_suite::cryptanalysis::koblitz_groebner::{
    build_decomposition_system, matrix_f4_f2_blocked, matrix_f4_f2_counted, FieldStructure,
};
use cryptanalysis_suite::cryptanalysis::koblitz_index_calculus::{
    build_frobenius_factor_base, KoblitzCurve,
};
use cryptanalysis_suite::cryptanalysis::pq_groebner_f2::F2BoolPoly;
use num_bigint::BigUint;

/// Did the reduction produce the constant `1` — the infeasibility
/// certificate?
fn refutes(rows: &[F2BoolPoly]) -> bool {
    rows.iter()
        .any(|p| p.terms.len() == 1 && p.terms[0].mask == 0)
}

fn main() {
    println!();
    println!("=== Refutation cost: total-degree Macaulay against a per-block bound ===");
    println!();
    println!(
        "| n | m | ℓ | v | blocks | targets | plain refuted | plain deg / ops | \
         blocked refuted | blocked bound / ops | speedup |"
    );
    println!(
        "|--:|--:|--:|--:|:-------|--------:|--------------:|:----------------|\
         ----------------:|:--------------------|--------:|"
    );

    for (n, m) in [(9u32, 2usize), (9, 3), (13, 2), (13, 3), (15, 2)] {
        let Some(kc) = KoblitzCurve::new(0, n) else {
            continue;
        };
        let Some(fb) = build_frobenius_factor_base(&kc, 0) else {
            continue;
        };
        let st = FieldStructure::new(kc.n, &kc.curve.irreducible);

        let (mut both_plain, mut both_blocked) = (0u64, 0u64);
        let (mut plain_deg, mut blk_bound) = (0u32, 0u32);
        let (mut plain_ref, mut blocked_ref, mut both) = (0u32, 0u32, 0u32);
        let mut targets = 0u32;
        let mut blocks_desc = String::new();
        let mut p_capped = false;
        let mut b_capped = false;

        for t in 1..=8u64 {
            // A random field element.  Most do not decompose, which is
            // the point: this measures rejection.
            let xr_raw = (t.wrapping_mul(2_654_435_761) ^ 0x9E37_79B9) % (1u64 << n);
            if xr_raw == 0 {
                continue;
            }
            let x_r = F2mElement::from_biguint(&BigUint::from(xr_raw), n);
            let Some(sys) =
                build_decomposition_system(&fb.subspace_basis, &x_r, &kc.curve.b, m, &st)
            else {
                continue;
            };
            let v = sys.n_vars;
            let blocks = sys.blocks(kc.n);
            if blocks_desc.is_empty() {
                blocks_desc = format!("{blocks:?}");
            }
            targets += 1;

            // Plain: raise the total degree until the constant 1
            // appears.  The cost includes the degrees that failed,
            // because the caller cannot know the right one up front.
            let mut p_cost = 0u64;
            let mut p_ok = false;
            for d in 2..=5u32 {
                let Some((rows, ops)) = matrix_f4_f2_counted(&sys.equations, v, d) else {
                    p_capped = true;
                    break;
                };
                p_cost += ops;
                if refutes(&rows) {
                    plain_deg = plain_deg.max(d);
                    p_ok = true;
                    break;
                }
            }

            // Blocked: raise the uniform per-block bound instead.
            let mut b_cost = 0u64;
            let mut b_ok = false;
            for bound in 1..=3u32 {
                let bounds = vec![bound; blocks.len()];
                let Some((rows, ops)) = matrix_f4_f2_blocked(&sys.equations, v, &blocks, &bounds)
                else {
                    b_capped = true;
                    break;
                };
                b_cost += ops;
                if refutes(&rows) {
                    blk_bound = blk_bound.max(bound);
                    b_ok = true;
                    break;
                }
            }

            if p_ok {
                plain_ref += 1;
            }
            if b_ok {
                blocked_ref += 1;
            }
            if p_ok && b_ok {
                both += 1;
                both_plain += p_cost;
                both_blocked += b_cost;
            }
        }

        if targets == 0 {
            continue;
        }
        let speedup = if both > 0 && both_blocked > 0 {
            format!("{:.2}×", both_plain as f64 / both_blocked as f64)
        } else {
            "—".to_string()
        };
        let mark = |ok: u32, capped: bool| -> String {
            if ok == 0 && capped {
                format!("{ok}/{targets} (capped)")
            } else {
                format!("{ok}/{targets}")
            }
        };
        println!(
            "| {n} | {m} | {} | {} | {blocks_desc} | {targets} | {} | {plain_deg} / {both_plain} \
             | {} | {blk_bound} / {both_blocked} | {speedup} |",
            fb.ell,
            m * fb.ell as usize + m.saturating_sub(2) * n as usize,
            mark(plain_ref, p_capped),
            mark(blocked_ref, b_capped),
        );
    }

    println!();
    println!("Unit: 64-bit word XORs in the elimination.");
    println!();
    println!("The blocked row space is a *subspace* of the total-degree one at comparable");
    println!("reach, so it can be weaker and never wrong: `the_blocked_macaulay_returns_only");
    println!("_ideal_members` pins that every row it returns vanishes on every root.  A");
    println!("refutation from either engine is therefore a genuine certificate.");
    println!();
    println!("The two knobs are not the same knob: a per-block bound of b over k blocks");
    println!("reaches total degree k·b, so the settings are only comparable through the cost");
    println!("of whichever one refutes.  Costs are summed over the targets where BOTH engines");
    println!("refuted; `(capped)` means the Macaulay matrix exceeded the size limits before");
    println!("any setting refuted, so that row is out of reach rather than a negative result.");
}
