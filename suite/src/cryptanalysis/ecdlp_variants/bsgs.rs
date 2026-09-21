//! Baby-step / giant-step ECDLP family (rows #1–#4, #7–#9, #12–#13 of
//! the Galbraith–Wang–Zhang table).
//!
//! All solve `Q = xP` for `x ∈ [0, n)` on the supplied [`EcGroup`].
//! The three axes of the table appear here as three knobs:
//!
//! - **Average-case balancing** (#2): build only `⌈√(n/2)⌉` baby
//!   steps instead of `⌈√n⌉`, trading a larger worst case (`2.12√n`)
//!   for a smaller average (`1.41√n` vs the textbook `1.5√n`).
//! - **Interleaving** (#3): grow the baby and giant lists *together*,
//!   checking each new point against the other list, so the walk
//!   stops at the first collision rather than after a full table.
//! - **Two grumpy giants** (#4, Bernstein–Lange 2012): a second giant
//!   walks *away* from the first, so a random target is reached from
//!   whichever side is closer.
//! - **Negation** (#7–#9): key the baby table by x-coordinate so `±P`
//!   share a slot — half the memory; each giant hit is resolved to a
//!   sign by one verification.
//! - **Block computation** (#12–#13): advance `B` independent walkers
//!   per super-step and share one Montgomery-trick (`batch_invert`)
//!   inversion across the block, so inversions drop to `≈ ops/B`.

use std::collections::HashMap;

use num_bigint::BigUint;
use num_traits::Zero;

use super::{isqrt_ceil, key, sub_mod, to_u64, xkey, DlpSolution, EcGroup};
use crate::ecc::point::Point;

/// Refuse explicit tables larger than this many entries (~134 M
/// points would exhaust memory long before the `√n` cost matters).
const MAX_TABLE: u64 = 1 << 27;

/// `x = 0` shortcut: `Q = ∞`.
fn trivial(q: &Point) -> Option<DlpSolution> {
    if matches!(q, Point::Infinity) {
        Some(DlpSolution {
            x: BigUint::zero(),
            group_ops: 0,
            field_inversions: 0,
            table_size: 0,
        })
    } else {
        None
    }
}

fn solution(group: &EcGroup, x: BigUint, table_size: usize) -> DlpSolution {
    DlpSolution {
        x,
        group_ops: group.group_ops(),
        field_inversions: group.field_inversions(),
        table_size,
    }
}

/// Try candidate logs in order; return the first `x` with `xP = Q`.
fn resolve(group: &EcGroup, q: &Point, cands: &[BigUint]) -> Option<BigUint> {
    let n = group.order();
    for c in cands {
        let x = c % n;
        if &group.mul_setup(&x) == q {
            return Some(x);
        }
    }
    None
}

/// Build the exact baby table `{ key(jG) → j : 0 ≤ j < m }` (counted).
fn build_baby_exact(group: &EcGroup, m: u64) -> HashMap<(Vec<u8>, Vec<u8>), u64> {
    let mut table = HashMap::with_capacity(m as usize);
    let mut p = group.identity();
    for j in 0..m {
        table.entry(key(&p)).or_insert(j);
        if j + 1 < m {
            p = group.add(&p, group.generator());
        }
    }
    table
}

/// Build the negation-folded baby table `{ xkey(jG) → j }` (counted).
fn build_baby_xfold(group: &EcGroup, m: u64) -> HashMap<Vec<u8>, u64> {
    let mut table = HashMap::with_capacity(m as usize);
    let mut p = group.identity();
    for j in 0..m {
        table.entry(xkey(&p)).or_insert(j);
        if j + 1 < m {
            p = group.add(&p, group.generator());
        }
    }
    table
}

// ── #1/#2 textbook & average-case BSGS ───────────────────────────────────────

fn bsgs_core(group: &EcGroup, q: &Point, average_case: bool) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();

    // Baby-step count: ⌈√n⌉ (textbook) balances baby vs. worst-case
    // giant; ⌈√(n/2)⌉ minimises the *average* total instead.
    let m = if average_case {
        isqrt_ceil(&((n + 1u32) / 2u32))
    } else {
        isqrt_ceil(n)
    };
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("BSGS table would exceed MAX_TABLE");
    }

    let table = build_baby_exact(group, m_u64);
    let table_size = table.len();

    // Giant step S = mG; walk Q, Q−S, Q−2S, …
    let s = group.mul_setup(&m);
    let neg_s = group.neg(&s);
    let mut cur = q.clone();
    let max_i = to_u64(&(n / &m)) + 2;
    for i in 0..=max_i {
        if let Some(&j) = table.get(&key(&cur)) {
            let x = (BigUint::from(i) * &m + BigUint::from(j)) % n;
            return Ok(solution(group, x, table_size));
        }
        cur = group.add(&cur, &neg_s);
    }
    Err("BSGS: log not found within giant-step bound")
}

/// **#1 — Textbook BSGS.**  `m = ⌈√n⌉` baby steps; average `1.5√n`,
/// worst `2.0√n` group ops.  Provided as the baseline the other rows
/// improve on.
pub fn bsgs_textbook(group: &EcGroup, q: &Point) -> Result<DlpSolution, &'static str> {
    bsgs_core(group, q, false)
}

/// **#2 — Average-case-optimised BSGS.**  `m = ⌈√(n/2)⌉` baby steps
/// minimises `m + (n/m)/2`, the *expected* cost for a uniform `x`:
/// average `√(2n) ≈ 1.41√n`, worst `2.12√n`.
pub fn bsgs_average_case(group: &EcGroup, q: &Point) -> Result<DlpSolution, &'static str> {
    bsgs_core(group, q, true)
}

// ── #3 Pollard interleaving BSGS ─────────────────────────────────────────────

/// **#3 — Pollard interleaving BSGS.**  Grow the baby list `{jG}` and
/// the giant list `{Q − iS}` (with `S = mG`, `m = ⌈√n⌉`) one step at a
/// time, checking each fresh point against the *other* list.  The walk
/// halts at the first collision instead of materialising a full table,
/// giving average `≈ 1.33√n`.
pub fn bsgs_interleaving(group: &EcGroup, q: &Point) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let m = isqrt_ceil(n);
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("interleaving BSGS table would exceed MAX_TABLE");
    }
    let s = group.mul_setup(&m);
    let neg_s = group.neg(&s);

    let mut baby: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new();
    let mut giant: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new();
    let mut bp = group.identity(); // jG, j = 0,1,…
    let mut gp = q.clone(); // Q − iS, i = 0,1,…

    let max_t = m_u64 + 2;
    for t in 0..=max_t {
        // Baby point tG: does it close a giant?
        let bk = key(&bp);
        if let Some(&i) = giant.get(&bk) {
            // tG = Q − iS ⟹ x = i·m + t
            let x = (BigUint::from(i) * &m + BigUint::from(t)) % n;
            return Ok(solution(group, x, baby.len() + giant.len()));
        }
        baby.entry(bk).or_insert(t);

        // Giant point Q − tS: does it close a baby?
        let gk = key(&gp);
        if let Some(&j) = baby.get(&gk) {
            // Q − tS = jG ⟹ x = t·m + j
            let x = (BigUint::from(t) * &m + BigUint::from(j)) % n;
            return Ok(solution(group, x, baby.len() + giant.len()));
        }
        giant.entry(gk).or_insert(t);

        if t < max_t {
            bp = group.add(&bp, group.generator());
            gp = group.add(&gp, &neg_s);
        }
    }
    Err("interleaving BSGS: log not found")
}

// ── #4 two grumpy giants + a baby ────────────────────────────────────────────

/// **#4 — Two grumpy giants and a baby** (Bernstein–Lange 2012).
/// *Three* interleaved walks grown one step at a time: a baby list
/// `{tG}`, a descending giant `{Q − tS}` and an ascending giant
/// `{Q + tS}` (`S = mG`, `m = ⌈√n⌉`).  Each fresh point is checked
/// against the others, so a uniform `x` is caught by whichever giant
/// reaches its residue first and the walk halts at that first
/// collision — expected `≈ 1.25√n`, faster than textbook because the
/// two giants walk *away* from each other and the baby list is not
/// pre-materialised.
pub fn grumpy_giants(group: &EcGroup, q: &Point) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let m = isqrt_ceil(n);
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("grumpy giants table would exceed MAX_TABLE");
    }
    let s = group.mul_setup(&m);
    let neg_s = group.neg(&s);

    let mut baby: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new(); // tG ↦ t
    let mut down: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new(); // Q−iS ↦ i
    let mut up: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new(); //   Q+iS ↦ i
    let mut bp = group.identity();
    let mut dp = q.clone();
    let mut upp = q.clone();

    let max_t = m_u64 + 2;
    for t in 0..=max_t {
        let table_size = baby.len() + down.len() + up.len();
        // Baby tG vs the two giants.
        let bk = key(&bp);
        if let Some(&i) = down.get(&bk) {
            // tG = Q − iS ⟹ x = i·m + t
            let x = (BigUint::from(i) * &m + BigUint::from(t)) % n;
            return Ok(solution(group, x, table_size));
        }
        if let Some(&i) = up.get(&bk) {
            // tG = Q + iS ⟹ x = t − i·m
            let x = sub_mod(&BigUint::from(t), &(BigUint::from(i) * &m), n);
            return Ok(solution(group, x, table_size));
        }
        baby.entry(bk).or_insert(t);
        // Descending giant Q − tS vs baby.
        let dk = key(&dp);
        if let Some(&k) = baby.get(&dk) {
            // Q − tS = kG ⟹ x = t·m + k
            let x = (BigUint::from(t) * &m + BigUint::from(k)) % n;
            return Ok(solution(group, x, table_size));
        }
        down.entry(dk).or_insert(t);
        // Ascending giant Q + tS vs baby.
        let uk = key(&upp);
        if let Some(&k) = baby.get(&uk) {
            // Q + tS = kG ⟹ x = k − t·m
            let x = sub_mod(&BigUint::from(k), &(BigUint::from(t) * &m), n);
            return Ok(solution(group, x, table_size));
        }
        up.entry(uk).or_insert(t);

        if t < max_t {
            bp = group.add(&bp, group.generator());
            dp = group.add(&dp, &neg_s);
            upp = group.add(&upp, &s);
        }
    }
    Err("grumpy giants: log not found")
}

// ── #7 BSGS with negation ────────────────────────────────────────────────────

/// **#7 — BSGS with the negation map.**  The baby table stores only
/// x-coordinates, so `kG` and `−kG` share one slot: it covers the
/// residues `±k` for `k ∈ [0, m)` (`m = ⌈√(n/2)⌉`) — `2m−1` values —
/// in half the memory.  The giant step is therefore `M = 2m−1`, and
/// each x-coordinate hit is resolved to `x = i·M ± k` by one check.
pub fn bsgs_negation(group: &EcGroup, q: &Point) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let m = isqrt_ceil(&((n + 1u32) / 2u32)).max(BigUint::from(1u32));
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("negation BSGS table would exceed MAX_TABLE");
    }
    let baby = build_baby_xfold(group, m_u64);
    let table_size = baby.len();

    // Giant step covers the full ±-window width 2m−1.
    let big_m = &m * 2u32 - 1u32;
    let s = group.mul_setup(&big_m);
    let neg_s = group.neg(&s);
    let mut cur = q.clone();
    let max_i = to_u64(&(n / &big_m)) + 2;
    for i in 0..=max_i {
        if let Some(&k) = baby.get(&xkey(&cur)) {
            // cur = Q − i·M·G = ±kG ⟹ x = i·M ± k
            let base = BigUint::from(i) * &big_m;
            let cands = [
                (&base + BigUint::from(k)) % n,
                sub_mod(&base, &BigUint::from(k), n),
            ];
            if let Some(x) = resolve(group, q, &cands) {
                return Ok(solution(group, x, table_size));
            }
        }
        cur = group.add(&cur, &neg_s);
    }
    Err("negation BSGS: log not found")
}

// ── #8 interleaving BSGS with negation ───────────────────────────────────────

/// **#8 — Interleaving BSGS with negation.**  Interleaving (#3) over
/// negation-folded (x-coordinate) tables for both the baby and giant
/// lists; collisions are resolved by trying both signs.
pub fn bsgs_interleaving_negation(group: &EcGroup, q: &Point) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let m = isqrt_ceil(n);
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("interleaving-negation table would exceed MAX_TABLE");
    }
    let s = group.mul_setup(&m);
    let neg_s = group.neg(&s);

    // x-folded tables: aG ↦ a, and (Q − bS) ↦ b.
    let mut baby: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut giant: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut bp = group.identity();
    let mut gp = q.clone();

    let max_t = m_u64 + 2;
    for t in 0..=max_t {
        let bk = xkey(&bp);
        if let Some(&b) = giant.get(&bk) {
            // ±tG = ±(Q − bS): try x = b·m ± t
            let bm = BigUint::from(b) * &m;
            let cands = [
                (&bm + BigUint::from(t)) % n,
                sub_mod(&bm, &BigUint::from(t), n),
            ];
            if let Some(x) = resolve(group, q, &cands) {
                return Ok(solution(group, x, baby.len() + giant.len()));
            }
        }
        baby.entry(bk).or_insert(t);

        let gk = xkey(&gp);
        if let Some(&a) = baby.get(&gk) {
            // ±(Q − tS) = ±aG: try x = t·m ± a
            let tm = BigUint::from(t) * &m;
            let cands = [
                (&tm + BigUint::from(a)) % n,
                sub_mod(&tm, &BigUint::from(a), n),
            ];
            if let Some(x) = resolve(group, q, &cands) {
                return Ok(solution(group, x, baby.len() + giant.len()));
            }
        }
        giant.entry(gk).or_insert(t);

        if t < max_t {
            bp = group.add(&bp, group.generator());
            gp = group.add(&gp, &neg_s);
        }
    }
    Err("interleaving-negation BSGS: log not found")
}

// ── #9 grumpy giants with negation ───────────────────────────────────────────

/// **#9 — Grumpy giants with negation.**  The interleaved three-walk
/// grumpy search (#4) over x-coordinate-folded tables, so `±P` share a
/// slot.  Each x-coordinate hit yields up to two sign candidates,
/// resolved by verification.
pub fn grumpy_giants_negation(group: &EcGroup, q: &Point) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let m = isqrt_ceil(n);
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("grumpy-negation table would exceed MAX_TABLE");
    }
    let s = group.mul_setup(&m);
    let neg_s = group.neg(&s);

    let mut baby: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut down: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut up: HashMap<Vec<u8>, u64> = HashMap::new();
    let mut bp = group.identity();
    let mut dp = q.clone();
    let mut upp = q.clone();

    let max_t = m_u64 + 2;
    for t in 0..=max_t {
        let table_size = baby.len() + down.len() + up.len();
        let tm = BigUint::from(t) * &m;
        // Baby ±tG vs the two giants.
        let bk = xkey(&bp);
        if let Some(&i) = down.get(&bk) {
            // ±tG = ±(Q − iS): x = i·m ± t
            let im = BigUint::from(i) * &m;
            let cands = [
                (&im + BigUint::from(t)) % n,
                sub_mod(&im, &BigUint::from(t), n),
            ];
            if let Some(x) = resolve(group, q, &cands) {
                return Ok(solution(group, x, table_size));
            }
        }
        if let Some(&i) = up.get(&bk) {
            // ±tG = ±(Q + iS): x = ±t − i·m
            let im = BigUint::from(i) * &m;
            let cands = [
                sub_mod(&BigUint::from(t), &im, n),
                sub_mod(&BigUint::zero(), &(&im + BigUint::from(t)), n),
            ];
            if let Some(x) = resolve(group, q, &cands) {
                return Ok(solution(group, x, table_size));
            }
        }
        baby.entry(bk).or_insert(t);
        // Descending giant ±(Q − tS) vs baby.
        let dk = xkey(&dp);
        if let Some(&k) = baby.get(&dk) {
            // x − t·m ≡ ±k ⟹ x = t·m ± k
            let cands = [
                (&tm + BigUint::from(k)) % n,
                sub_mod(&tm, &BigUint::from(k), n),
            ];
            if let Some(x) = resolve(group, q, &cands) {
                return Ok(solution(group, x, table_size));
            }
        }
        down.entry(dk).or_insert(t);
        // Ascending giant ±(Q + tS) vs baby.
        let uk = xkey(&upp);
        if let Some(&k) = baby.get(&uk) {
            // x + t·m ≡ ±k ⟹ x = ±k − t·m
            let cands = [
                sub_mod(&BigUint::from(k), &tm, n),
                sub_mod(&BigUint::zero(), &(&tm + BigUint::from(k)), n),
            ];
            if let Some(x) = resolve(group, q, &cands) {
                return Ok(solution(group, x, table_size));
            }
        }
        up.entry(uk).or_insert(t);

        if t < max_t {
            bp = group.add(&bp, group.generator());
            dp = group.add(&dp, &neg_s);
            upp = group.add(&upp, &s);
        }
    }
    Err("grumpy-negation giants: log not found")
}

// ── #12 interleaving BSGS with block computation ─────────────────────────────

/// **#12 — Interleaving BSGS with block computation.**  Identical
/// search to #3, but the single baby/giant chains are split into `B`
/// independent sub-walks advanced together: each super-step adds the
/// constant `B·G` (resp. `−B·S`) to all `B` walkers through one
/// [`batch_add`](EcGroup::batch_add).  So `B` fresh points cost one
/// inversion instead of `B` — `field_inversions ≈ group_ops / B`.
pub fn bsgs_interleaving_block(
    group: &EcGroup,
    q: &Point,
    block: usize,
) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let b = block.max(1) as u64;
    let m = isqrt_ceil(n);
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("interleaving-block table would exceed MAX_TABLE");
    }
    let s = group.mul_setup(&m);
    let neg_s = group.neg(&s);

    // Block step constants and initial walker positions (set-up).
    let step_baby = group.mul_setup(&BigUint::from(b)); // B·G
    let step_giant = group.mul_pt_setup(&neg_s, &BigUint::from(b)); // −B·S
    let mut bpos: Vec<Point> = (0..b).map(|r| group.mul_setup(&BigUint::from(r))).collect();
    let mut gpos: Vec<Point> = (0..b)
        .map(|r| group.add_setup(q, &group.mul_pt_setup(&neg_s, &BigUint::from(r))))
        .collect();

    let mut baby: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new();
    let mut giant: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new();

    let max_index = m_u64 + to_u64(&(n / &m)) + 2;
    let super_steps = max_index / b + 2;
    for c in 0..=super_steps {
        for r in 0..b as usize {
            let j = c * b + r as u64; // baby index
            let bk = key(&bpos[r]);
            if let Some(&i) = giant.get(&bk) {
                let x = (BigUint::from(i) * &m + BigUint::from(j)) % n;
                return Ok(solution(group, x, baby.len() + giant.len()));
            }
            baby.entry(bk).or_insert(j);
        }
        for r in 0..b as usize {
            let i = c * b + r as u64; // giant index
            let gk = key(&gpos[r]);
            if let Some(&j) = baby.get(&gk) {
                let x = (BigUint::from(i) * &m + BigUint::from(j)) % n;
                return Ok(solution(group, x, baby.len() + giant.len()));
            }
            giant.entry(gk).or_insert(i);
        }
        // Advance both blocks with one batched inversion each.
        bpos = group.batch_add(&pairs_with(&bpos, &step_baby));
        gpos = group.batch_add(&pairs_with(&gpos, &step_giant));
    }
    Err("interleaving-block BSGS: log not found")
}

// ── #13 grumpy giants with block computation ─────────────────────────────────

/// **#13 — Grumpy giants with block computation.**  The interleaved
/// three-walk grumpy search (#4) where the baby list and both giants
/// are advanced `B` walkers at a time, each super-step sharing one
/// inversion per block via Montgomery's trick — so the grumpy speed-up
/// and the inversion amortisation compound.
pub fn grumpy_giants_block(
    group: &EcGroup,
    q: &Point,
    block: usize,
) -> Result<DlpSolution, &'static str> {
    if let Some(s) = trivial(q) {
        return Ok(s);
    }
    group.reset();
    let n = group.order();
    let b = block.max(1) as u64;
    let m = isqrt_ceil(n);
    let m_u64 = to_u64(&m);
    if m_u64 > MAX_TABLE {
        return Err("grumpy-block table would exceed MAX_TABLE");
    }
    let s = group.mul_setup(&m);
    let neg_s = group.neg(&s);

    // Block step constants and initial walker positions (set-up).
    let step_baby = group.mul_setup(&BigUint::from(b)); // +B·G
    let step_down = group.mul_pt_setup(&neg_s, &BigUint::from(b)); // −B·S
    let step_up = group.mul_pt_setup(&s, &BigUint::from(b)); //      +B·S
    let mut bpos: Vec<Point> = (0..b).map(|r| group.mul_setup(&BigUint::from(r))).collect();
    let mut dpos: Vec<Point> = (0..b)
        .map(|r| group.add_setup(q, &group.mul_pt_setup(&neg_s, &BigUint::from(r))))
        .collect();
    let mut upos: Vec<Point> = (0..b)
        .map(|r| group.add_setup(q, &group.mul_pt_setup(&s, &BigUint::from(r))))
        .collect();

    let mut baby: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new();
    let mut down: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new();
    let mut up: HashMap<(Vec<u8>, Vec<u8>), u64> = HashMap::new();

    let max_index = m_u64 + 2;
    let super_steps = max_index / b + 2;
    for c in 0..=super_steps {
        let table_size = baby.len() + down.len() + up.len();
        for r in 0..b as usize {
            let t = c * b + r as u64; // baby index
            let bk = key(&bpos[r]);
            if let Some(&i) = down.get(&bk) {
                let x = (BigUint::from(i) * &m + BigUint::from(t)) % n;
                return Ok(solution(group, x, table_size));
            }
            if let Some(&i) = up.get(&bk) {
                let x = sub_mod(&BigUint::from(t), &(BigUint::from(i) * &m), n);
                return Ok(solution(group, x, table_size));
            }
            baby.entry(bk).or_insert(t);
        }
        for r in 0..b as usize {
            let i = c * b + r as u64; // descending giant index
            let dk = key(&dpos[r]);
            if let Some(&k) = baby.get(&dk) {
                let x = (BigUint::from(i) * &m + BigUint::from(k)) % n;
                return Ok(solution(group, x, table_size));
            }
            down.entry(dk).or_insert(i);
        }
        for r in 0..b as usize {
            let i = c * b + r as u64; // ascending giant index
            let uk = key(&upos[r]);
            if let Some(&k) = baby.get(&uk) {
                let x = sub_mod(&BigUint::from(k), &(BigUint::from(i) * &m), n);
                return Ok(solution(group, x, table_size));
            }
            up.entry(uk).or_insert(i);
        }
        bpos = group.batch_add(&pairs_with(&bpos, &step_baby));
        dpos = group.batch_add(&pairs_with(&dpos, &step_down));
        upos = group.batch_add(&pairs_with(&upos, &step_up));
    }
    Err("grumpy-block giants: log not found")
}

/// Pair every walker with a shared constant step, for [`batch_add`].
fn pairs_with(walkers: &[Point], step: &Point) -> Vec<(Point, Point)> {
    walkers.iter().map(|p| (p.clone(), step.clone())).collect()
}

#[cfg(test)]
mod tests {
    use super::super::{demo_group_mid, demo_group_small};
    use super::*;

    fn plant(group: &EcGroup, x: u64) -> Point {
        group.mul_setup(&BigUint::from(x))
    }

    /// Every solver recovers a planted log on the small demo curve.
    #[test]
    fn all_variants_recover_small() {
        let g = demo_group_small();
        let secrets = [1u64, 2, 777, 5000, 9999, 10038];
        for &x in &secrets {
            let q = plant(&g, x);
            let want = BigUint::from(x);
            assert_eq!(bsgs_textbook(&g, &q).unwrap().x, want, "textbook x={x}");
            assert_eq!(bsgs_average_case(&g, &q).unwrap().x, want, "avg x={x}");
            assert_eq!(
                bsgs_interleaving(&g, &q).unwrap().x,
                want,
                "interleave x={x}"
            );
            assert_eq!(grumpy_giants(&g, &q).unwrap().x, want, "grumpy x={x}");
            assert_eq!(bsgs_negation(&g, &q).unwrap().x, want, "neg x={x}");
            assert_eq!(
                bsgs_interleaving_negation(&g, &q).unwrap().x,
                want,
                "interleave-neg x={x}"
            );
            assert_eq!(
                grumpy_giants_negation(&g, &q).unwrap().x,
                want,
                "grumpy-neg x={x}"
            );
            assert_eq!(
                bsgs_interleaving_block(&g, &q, 16).unwrap().x,
                want,
                "interleave-block x={x}"
            );
            assert_eq!(
                grumpy_giants_block(&g, &q, 16).unwrap().x,
                want,
                "grumpy-block x={x}"
            );
        }
    }

    /// `x = 0` (Q = ∞) handled by every solver.
    #[test]
    fn zero_log() {
        let g = demo_group_small();
        let q = Point::Infinity;
        assert!(bsgs_textbook(&g, &q).unwrap().x.is_zero());
        assert!(grumpy_giants_negation(&g, &q).unwrap().x.is_zero());
        assert!(bsgs_interleaving_block(&g, &q, 8).unwrap().x.is_zero());
    }

    /// Negation halves the baby table vs. textbook.
    #[test]
    fn negation_halves_table() {
        let g = demo_group_mid();
        let q = plant(&g, 31337);
        let plain = bsgs_textbook(&g, &q).unwrap();
        let neg = bsgs_negation(&g, &q).unwrap();
        assert_eq!(neg.x, BigUint::from(31337u32));
        // ⌈√(n/2)⌉ vs ⌈√n⌉ ⇒ ~1/√2 the entries.
        assert!(
            (neg.table_size as f64) < 0.8 * (plain.table_size as f64),
            "neg table {} not < 0.8·{}",
            neg.table_size,
            plain.table_size
        );
    }

    /// Block computation cuts inversions to ≈ ops/B.
    #[test]
    fn block_computation_amortises_inversions() {
        let g = demo_group_mid();
        let q = plant(&g, 54321);
        let block = 32usize;
        let sol = bsgs_interleaving_block(&g, &q, block).unwrap();
        assert_eq!(sol.x, BigUint::from(54321u32));
        // Far fewer inversions than group ops once batched.
        assert!(
            sol.field_inversions * 4 < sol.group_ops,
            "inversions {} not ≪ ops {}",
            sol.field_inversions,
            sol.group_ops
        );
    }

    /// Plain affine solvers spend ≈ one inversion per group op.
    #[test]
    fn plain_variants_invert_per_op() {
        let g = demo_group_mid();
        let q = plant(&g, 4242);
        let sol = grumpy_giants(&g, &q).unwrap();
        assert_eq!(sol.x, BigUint::from(4242u32));
        assert!(sol.field_inversions >= sol.group_ops.saturating_sub(2));
    }

    /// Mid curve, a couple of secrets, all variants agree.
    #[test]
    fn agreement_mid() {
        let g = demo_group_mid();
        for &x in &[123u64, 98_892, 50_000] {
            let q = plant(&g, x);
            let w = BigUint::from(x);
            assert_eq!(bsgs_average_case(&g, &q).unwrap().x, w);
            assert_eq!(bsgs_interleaving(&g, &q).unwrap().x, w);
            assert_eq!(grumpy_giants_block(&g, &q, 24).unwrap().x, w);
            assert_eq!(bsgs_interleaving_negation(&g, &q).unwrap().x, w);
        }
    }
}
