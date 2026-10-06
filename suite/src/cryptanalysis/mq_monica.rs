//! ALMASTY Monica: striped-down Crossbred for quadratic Boolean systems.
//!
//! Port of <https://gitlab.lip6.fr/almasty/mq> `monica.c` (public domain):
//! linearise `v ≈ √(2m)` variables, Gray-code-enumerate the other `u = n − v`,
//! and solve a `v × v` linear system at each step via FFS incremental updates.
//!
//! Asymptotic work is about `2^u · poly(v)` bit operations versus Möbius
//! `O(n · 2^n)`.  When `u` is meaningfully smaller than `n` this is the
//! lever that can beat plain Möbius on the same quadratic Semaev ANF.

use super::mq_fes::QuadraticForm;

/// Bitner–Ehrlich–Reingold focus / stack state (`ffs.h`).
#[derive(Clone, Debug)]
struct Ffs {
    focus: [i32; 66],
    stack: [i32; 65],
    sp: i32,
    k1: i32,
    k2: i32,
}

impl Ffs {
    fn reset(n: usize) -> Self {
        let mut focus = [0i32; 66];
        for j in 0..=64 {
            focus[j] = j as i32;
        }
        let mut stack = [0i32; 65];
        stack[0] = (n + 1) as i32;
        Self {
            focus,
            stack,
            sp: 1,
            k1: (n + 1) as i32,
            k2: -1,
        }
    }

    fn step(&mut self) {
        let j = self.focus[0];
        self.focus[0] = 0;
        self.focus[j as usize] = self.focus[(j + 1) as usize];
        self.focus[(j + 1) as usize] = j + 1;
        self.k1 = j;
        self.sp -= j;
        self.k2 = self.stack[(self.sp - 1) as usize];
        self.stack[self.sp as usize] = j;
        self.sp += 1;
    }
}

/// Quadratic form with ALMASTY indexing: `q[i][j]` for `i < j`.
#[derive(Clone, Debug)]
struct AlmastyPoly {
    c: bool,
    l: [bool; 64],
    q: [[bool; 64]; 63],
}

impl AlmastyPoly {
    fn zero() -> Self {
        Self {
            c: false,
            l: [false; 64],
            q: [[false; 64]; 63],
        }
    }

    fn from_quadratic(form: &QuadraticForm) -> Self {
        let mut p = Self::zero();
        p.c = form.constant;
        for i in 0..form.n {
            p.l[i] = form.linear[i];
        }
        for i in 0..form.n {
            for j in 0..i {
                if form.quad[i][j] {
                    // Our storage is quad[hi][lo]; ALMASTY wants q[lo][hi].
                    p.q[j][i] = true;
                }
            }
        }
        p
    }

    fn eval(&self, n: usize, x: u64) -> bool {
        let mut r = self.c;
        for i in 0..n {
            if ((x >> i) & 1) == 1 && self.l[i] {
                r = !r;
            }
        }
        for i in 0..n {
            for j in (i + 1)..n {
                if self.q[i][j] && ((x >> i) & 1) == 1 && ((x >> j) & 1) == 1 {
                    r = !r;
                }
            }
        }
        r
    }
}

#[derive(Clone, Debug)]
struct SymbolicPoly {
    q: [[bool; 64]; 63],
    b: [[bool; 64]; 64],
    l: [bool; 64],
    c: AlmastyPoly,
}

impl SymbolicPoly {
    fn from_poly(p: &AlmastyPoly, n: usize, v: usize) -> Self {
        let mut sp = Self {
            q: [[false; 64]; 63],
            b: [[false; 64]; 64],
            l: [false; 64],
            c: AlmastyPoly::zero(),
        };
        for i in v..n {
            for j in (i + 1)..n {
                sp.c.q[i - v][j - v] = p.q[i][j];
            }
        }
        for i in 0..v {
            for j in (i + 1)..v {
                sp.q[i][j] = p.q[i][j];
            }
        }
        for i in 0..v {
            for j in v..n {
                sp.b[i][j - v] ^= p.q[i][j];
            }
        }
        for i in v..n {
            sp.c.l[i - v] ^= p.l[i];
        }
        for i in 0..v {
            sp.l[i] ^= p.l[i];
        }
        sp.c.c = p.c;
        sp
    }
}

fn sum_poly(a: &mut AlmastyPoly, b: &AlmastyPoly, n: usize) {
    a.c ^= b.c;
    for i in 0..n {
        a.l[i] ^= b.l[i];
    }
    for i in 0..n {
        for j in (i + 1)..n {
            a.q[i][j] ^= b.q[i][j];
        }
    }
}

fn sum_symbolic(a: &mut SymbolicPoly, b: &SymbolicPoly, u: usize, v: usize) {
    sum_poly(&mut a.c, &b.c, u);
    for i in 0..v {
        for j in 0..u {
            a.b[i][j] ^= b.b[i][j];
        }
    }
    for i in 0..v {
        a.l[i] ^= b.l[i];
    }
    for i in 0..v {
        for j in (i + 1)..v {
            a.q[i][j] ^= b.q[i][j];
        }
    }
}

fn gauss_reduce_quadratic(sp: &mut [SymbolicPoly], m: usize, u: usize, v: usize) {
    let mut k = 0usize;
    for i in 0..v {
        for j in (i + 1)..v {
            let mut p = None;
            for l in k..m {
                if sp[l].q[i][j] {
                    p = Some(l);
                    break;
                }
            }
            let Some(p) = p else {
                continue;
            };
            sp.swap(p, k);
            for l in 0..m {
                if l != k && sp[l].q[i][j] {
                    let pivot = sp[k].clone();
                    sum_symbolic(&mut sp[l], &pivot, u, v);
                }
            }
            k += 1;
        }
    }
}

#[derive(Clone, Debug)]
struct EnumState {
    bq: [[bool; 66]; 65],
    bl: [bool; 65],
    bc: bool,
    al: [[bool; 64]; 65],
    ac: [bool; 64],
}

impl EnumState {
    fn setup(sp: &SymbolicPoly, u: usize, v: usize) -> Self {
        let mut es = Self {
            bq: [[false; 66]; 65],
            bl: [false; 65],
            bc: sp.c.c,
            al: [[false; 64]; 65],
            ac: [false; 64],
        };
        for i in 0..u {
            es.bl[i] = sp.c.l[i];
        }
        for i in 0..u {
            for j in (i + 1)..u {
                es.bq[i][j] = sp.c.q[i][j];
            }
        }
        for i in 1..u {
            es.bq[i][u + 1] = es.bq[i - 1][i];
        }
        for i in 0..v {
            es.ac[i] = sp.l[i];
        }
        for i in 0..u {
            for j in 0..v {
                es.al[i][j] = sp.b[j][i];
            }
        }
        es
    }

    fn update(&mut self, ffs: &Ffs, v: usize) {
        let k1 = ffs.k1 as usize;
        let k2 = ffs.k2 as usize;
        self.bl[k1] ^= self.bq[k1][k2];
        self.bc ^= self.bl[k1];
        for i in 0..v {
            self.ac[i] ^= self.al[k1][i];
        }
    }
}

/// Solve `A z = b` for the current enumeration slice; returns solutions in `z`.
fn solve_linear(es: &[EnumState], l: usize, v: usize, output: &mut [u64]) -> usize {
    let mut a = vec![0u64; l];
    let mut b = vec![false; l];
    let mut pivot = vec![false; l];
    for i in 0..l {
        b[i] = es[i].bc;
        for j in 0..v {
            if es[i].ac[j] {
                a[i] |= 1u64 << j;
            }
        }
    }
    let mut r = 0usize;
    for i in 0..v {
        let mask = 1u64 << i;
        let mut p = None;
        for j in 0..l {
            if !pivot[j] && (a[j] & mask) != 0 {
                p = Some(j);
                break;
            }
        }
        let Some(p) = p else {
            r += 1;
            continue;
        };
        a.swap(i, p);
        b.swap(i, p);
        pivot[i] = true;
        for j in 0..l {
            if j != i && (a[j] & mask) != 0 {
                a[j] ^= a[i];
                b[j] ^= b[i];
            }
        }
    }
    for i in 0..l {
        if !pivot[i] && b[i] {
            return 0;
        }
    }
    let mut x = 0u64;
    for i in 0..v {
        if b[i] {
            x |= 1u64 << i;
        }
    }
    let mut n_solutions = 1usize;
    output[0] = x;
    if r > 0 {
        for i in 0..v {
            if !pivot[i] {
                let mask = 1u64 << i;
                let mut basis = mask;
                for j in 0..i {
                    if (a[j] & mask) != 0 {
                        basis ^= 1u64 << j;
                    }
                }
                for j in 0..n_solutions {
                    output[n_solutions + j] = output[j] ^ basis;
                }
                n_solutions *= 2;
            }
        }
    }
    debug_assert_eq!(n_solutions, 1usize << r);
    n_solutions
}

/// Default Monica inner hybridisation: `v = ⌊√(2m) − 1/2⌋`, capped by `n`.
pub fn default_inner_vars(n: usize, m: usize) -> usize {
    if m == 0 || n == 0 {
        return 0;
    }
    let max_v = ((2.0 * m as f64).sqrt() - 0.5).floor().max(0.0) as usize;
    max_v.min(n)
}

/// Estimated work: Monica beats Möbius only past the packed-table regime.
///
/// Calibrated against a release wall-clock on `n=14,m=32` where a naïve
/// `2^u·l·v²` count predicted Monica ahead but Möbius won by ~4–5×: each
/// Monica linear-solve step is far heavier than a Möbius XOR.  With a
/// ×20 fudge, Monica wins only near `n ≥ 28`, i.e. past the `n ≤ 24`
/// Möbius memory cap — so Monica's real role here is **range extension**,
/// not beating Möbius inside the cap.
pub fn monica_beats_moebius(n: usize, m: usize) -> bool {
    let v = default_inner_vars(n, m);
    if v == 0 || v > n || v > 20 {
        return false;
    }
    let u = n - v;
    let quad_monomials = v * v.saturating_sub(1) / 2;
    if m < quad_monomials {
        return false;
    }
    let mut l = m - quad_monomials;
    if l > v + 4 {
        l = v + 4;
    }
    let moebius = (n as u128).saturating_mul(1u128 << n.min(62));
    let monica = 20u128
        .saturating_mul(1u128 << u.min(62))
        .saturating_mul((l as u128).saturating_mul((v as u128).saturating_mul(v as u128)));
    monica < moebius
}

/// Find common zeros by Monica hybrid search.
///
/// Returns `None` if the system is too large for this port (`n > 40`,
/// `m > 128`, or `v`/`l` constraints).  Solutions are verified against the
/// original forms.
pub fn monica_find_all(forms: &[QuadraticForm], max_solutions: usize) -> Option<Vec<u64>> {
    monica_search(forms, max_solutions, false)
}

/// First common zero, stopping as soon as one verified solution appears.
pub fn monica_find_one(forms: &[QuadraticForm]) -> Option<u64> {
    monica_search(forms, 1, true)?.into_iter().next()
}

fn monica_search(
    forms: &[QuadraticForm],
    max_solutions: usize,
    early_exit: bool,
) -> Option<Vec<u64>> {
    if forms.is_empty() {
        return Some(vec![0]);
    }
    let n = forms[0].n;
    let m = forms.len();
    if n > 40 || m > 128 || forms.iter().any(|f| f.n != n) {
        return None;
    }
    let v = default_inner_vars(n, m);
    if v == 0 || v > 64 {
        return None;
    }
    let u = n - v;
    let quad_monomials = v * v.saturating_sub(1) / 2;
    if m < quad_monomials {
        return None;
    }
    let mut l = m - quad_monomials;
    let max_excess = 4usize;
    if l > v + max_excess {
        l = v + max_excess;
    }
    if l < v || l > 64 {
        return None;
    }

    let polys: Vec<_> = forms.iter().map(AlmastyPoly::from_quadratic).collect();
    let mut sp: Vec<_> = polys
        .iter()
        .map(|p| SymbolicPoly::from_poly(p, n, v))
        .collect();
    gauss_reduce_quadratic(&mut sp, m, u, v);

    let mut ffs = Ffs::reset(u);
    ffs.step();
    let mut es: Vec<_> = (0..l)
        .map(|i| EnumState::setup(&sp[quad_monomials + i], u, v))
        .collect();

    let mut out = Vec::new();
    let mut zbuf = vec![0u64; 1usize << v.min(20)];

    for y in 0u64..(1u64 << u) {
        if v > 20 {
            return None;
        }
        let n_sol = solve_linear(&es, l, v, &mut zbuf);
        let yy = y ^ (y >> 1);
        for i in 0..n_sol {
            let x = (yy << v) | zbuf[i];
            if polys.iter().all(|p| !p.eval(n, x)) {
                out.push(x);
                if out.len() >= max_solutions || early_exit {
                    return Some(out);
                }
            }
        }
        for state in &mut es {
            state.update(&ffs, v);
        }
        ffs.step();
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::cryptanalysis::mq_fes::{gray_find_all, moebius_find_all, QuadraticForm};
    use crate::cryptanalysis::wdsat_oracle::AnfRow;

    fn forms_from_rows(rows: &[AnfRow], n: usize) -> Vec<QuadraticForm> {
        rows.iter()
            .map(|r| QuadraticForm::from_anf_row(r, n).unwrap())
            .collect()
    }

    #[test]
    fn monica_agrees_with_moebius_on_tiny_system() {
        let rows = [
            AnfRow {
                monomials: vec![vec![0], vec![1]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![0]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![1], vec![2]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![0, 2], vec![1]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![0, 1], vec![2]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![1, 2]],
                constant: true,
            },
        ];
        // Need enough eqs for v=⌊√(2m)-0.5⌋; with m=6, v=2, n=3, u=1.
        let forms = forms_from_rows(&rows, 3);
        let mut a = monica_find_all(&forms, 64).expect("monica");
        let mut b = moebius_find_all(&forms, 64).unwrap();
        a.sort_unstable();
        b.sort_unstable();
        assert_eq!(a, b);
    }

    #[test]
    fn monica_agrees_with_gray_on_randomish_quadratics() {
        let rows = [
            AnfRow {
                monomials: vec![vec![0, 1], vec![2], vec![4], vec![3, 5]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![1, 3], vec![0, 4], vec![2, 3], vec![5]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![0, 5], vec![1, 2], vec![3], vec![4]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![2, 4], vec![0, 3], vec![1], vec![5]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![0, 2], vec![1, 4], vec![3, 5]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![1, 5], vec![2, 3], vec![0], vec![4]],
                constant: false,
            },
            AnfRow {
                monomials: vec![vec![0, 1], vec![2, 5], vec![3, 4]],
                constant: true,
            },
            AnfRow {
                monomials: vec![vec![0, 4], vec![1, 3], vec![2], vec![5]],
                constant: false,
            },
        ];
        // m=8 → v=⌊√16-0.5⌋=3; n=6 → u=3. Monica still correct; cost model
        // no longer claims a win over Möbius at this size (calibrated).
        let forms = forms_from_rows(&rows, 6);
        let mut a = monica_find_all(&forms, 256).expect("monica");
        let mut b = gray_find_all(&forms, 256);
        a.sort_unstable();
        b.sort_unstable();
        assert_eq!(a, b);
    }
}
