//! Target-independent Semaev preprocessing shared by Gröbner and SAT frontends.
//! The final link is D + sum_k r_k C_k: squaring is F2-linear. We store
//! coefficient polynomials, not target answers. No specialization denominators.
use super::{
    algebra_cache::{self, Layer},
    koblitz_groebner::*,
    pq_groebner_f2::{F2BoolMono, F2BoolPoly},
};
use crate::binary_ecc::F2mElement;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct DecompositionTemplate {
    pub n: u32,
    pub n_vars: usize,
    pub ell: usize,
    pub m: usize,
    pub prefix: Vec<F2BoolPoly>,
    pub constant: Vec<F2BoolPoly>,
    /// `coefficients[k][j]` is the coefficient of target bit k in equation j.
    pub coefficients: Vec<Vec<F2BoolPoly>>,
    /// The inputs the template was built from, so an in-process memo can
    /// confirm a hit exactly rather than trust a hash.  Not serialised:
    /// the shared cache keys on the full inputs already.
    #[serde(skip)]
    source: Option<TemplateSource>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct TemplateSource {
    basis: Vec<Vec<u64>>,
    b: Vec<u64>,
    squares: Vec<u64>,
    reduced: Vec<Vec<u64>>,
}
impl DecompositionTemplate {
    pub fn build(
        basis: &[F2mElement],
        b: &F2mElement,
        m: usize,
        st: &FieldStructure,
    ) -> Option<Self> {
        if m < 2 || st.n == 0 || st.n > 64 {
            return None;
        }
        let n = st.n;
        let ell = basis.len();
        let n_vars = m
            .checked_mul(ell)?
            .checked_add((m - 2).checked_mul(n as usize)?)?;
        if n_vars > MAX_VARS {
            return None;
        }
        let xs: Vec<_> = (0..m)
            .map(|i| SymElement::from_subspace_vars(basis, i * ell, n, n_vars))
            .collect();
        let inter: Vec<_> = (0..m - 2)
            .map(|i| SymElement::from_free_vars(m * ell + i * n as usize, n, n_vars))
            .collect();
        let mut prefix = Vec::new();
        let (x, y) = if m == 2 {
            (&xs[0], &xs[1])
        } else {
            prefix.extend(sym_semaev_s3(&xs[0], &xs[1], &inter[0], b, st));
            for i in 0..m - 3 {
                prefix.extend(sym_semaev_s3(&inter[i], &xs[i + 2], &inter[i + 1], b, st));
            }
            (&inter[m - 3], &xs[m - 1])
        };
        let a = x.add(y).square(st);
        let c = x.mul(y, st);
        let constant = c.square(st).add(&SymElement::constant(b, n, n_vars)).coords;
        let coefficients = (0..n)
            .map(|k| {
                let bit = SymElement::constant(&F2mElement::from_bit_positions(&[k], n), n, n_vars);
                a.mul(&bit.square(st), st).add(&c.mul(&bit, st)).coords
            })
            .collect();
        Some(Self {
            n,
            n_vars,
            ell,
            m,
            prefix,
            constant,
            coefficients,
            source: Some(TemplateSource {
                basis: basis.iter().map(|e| e.raw_bits().to_vec()).collect(),
                b: b.raw_bits().to_vec(),
                squares: st.squares.clone(),
                reduced: st.reduced.clone(),
            }),
        })
    }

    /// Whether this template was built from exactly these inputs.
    fn matches(&self, basis: &[F2mElement], b: &F2mElement, m: usize, st: &FieldStructure) -> bool {
        self.m == m
            && self.n == st.n
            && self.source.as_ref().is_some_and(|s| {
                s.basis.len() == basis.len()
                    && s.basis
                        .iter()
                        .zip(basis)
                        .all(|(x, e)| x.as_slice() == e.raw_bits())
                    && s.b.as_slice() == b.raw_bits()
                    && s.squares == st.squares
                    && s.reduced == st.reduced
            })
    }
    pub fn instantiate(&self, x_r: &F2mElement) -> DecompositionSystem {
        let bits = x_r.raw_bits().first().copied().unwrap_or(0);
        let mut last = self.constant.clone();
        for k in 0..self.n as usize {
            if bits & (1u64 << k) != 0 {
                for (p, c) in last.iter_mut().zip(&self.coefficients[k]) {
                    *p = p.add(c);
                }
            }
        }
        let mut equations = self.prefix.clone();
        equations.extend(last);
        DecompositionSystem {
            equations,
            n_vars: self.n_vars,
            ell: self.ell,
            m: self.m,
        }
    }
    /// Experimental: keep target bits as additional Boolean variables. These are
    /// not invertible parameters in a rational-function coefficient field.
    pub fn parameterized_generators(&self) -> Option<Vec<F2BoolPoly>> {
        let total = self.n_vars + self.n as usize;
        if total > MAX_VARS {
            return None;
        }
        let mut out = self.prefix.clone();
        let mut last = self.constant.clone();
        for p in out.iter_mut().chain(last.iter_mut()) {
            p.n_vars = total;
        }
        for (k, coeff) in self.coefficients.iter().enumerate() {
            for (p, c) in last.iter_mut().zip(coeff) {
                let mut c = c.clone();
                c.n_vars = total;
                *p = p.add(&c.mul_mono(F2BoolMono::var((self.n_vars + k) as u32)));
            }
        }
        out.extend(last);
        Some(out)
    }
    /// Specialization preserves ideal equality when the input generates the
    /// original ideal. It need not preserve the Gröbner property: re-reduce.
    pub fn specialize_parameter_basis(&self, basis: &[F2BoolPoly], target: u64) -> Vec<F2BoolPoly> {
        assert!(self.n_vars + self.n as usize <= MAX_VARS);
        let low = if self.n_vars == 64 {
            u64::MAX
        } else {
            (1u64 << self.n_vars) - 1
        };
        basis
            .iter()
            .map(|p| {
                F2BoolPoly::from_monos(
                    p.terms
                        .iter()
                        .filter_map(|t| {
                            let parameters = t.mask >> self.n_vars;
                            if parameters & !target == 0 {
                                Some(F2BoolMono::from_mask(t.mask & low))
                            } else {
                                None
                            }
                        })
                        .collect(),
                    self.n_vars,
                )
            })
            .collect()
    }
}

/// Key includes complete field structure, ordered subspace basis, b, layout and
/// encoder fingerprint. Curve a is absent because S3 is independent of a; point
/// membership/lifting and SAT domain constraints are still handled downstream.
pub fn template_key(
    basis: &[F2mElement],
    b: &F2mElement,
    m: usize,
    st: &FieldStructure,
) -> Vec<u8> {
    let basis_bits: Vec<_> = basis.iter().map(|x| x.raw_bits()).collect();
    serde_json::to_vec(&(st, basis_bits, b.raw_bits(), m, "boolean-degrevlex-v0-high")).unwrap()
}
/// Templates kept per thread when no algebra cache is configured.  A
/// decomposition run asks the same `(field, basis, b, m)` for every
/// target, so a handful covers any caller; the list is searched
/// linearly and the oldest entry dropped.
const LOCAL_TEMPLATES: usize = 8;

thread_local! {
    static TEMPLATES: std::cell::RefCell<Vec<(u64, std::rc::Rc<DecompositionTemplate>)>> =
        const { std::cell::RefCell::new(Vec::new()) };
}

/// A hash of everything a template depends on: the field's structure
/// constants, the ordered basis, `b` and `m`.  Collisions would hand one
/// template to another system, so the full inputs are also compared by
/// [`DecompositionTemplate::matches`] before a hit is used.
fn local_template_key(basis: &[F2mElement], b: &F2mElement, m: usize, st: &FieldStructure) -> u64 {
    use std::hash::{Hash, Hasher};
    let mut h = std::collections::hash_map::DefaultHasher::new();
    st.n.hash(&mut h);
    st.squares.hash(&mut h);
    st.reduced.hash(&mut h);
    for e in basis {
        e.raw_bits().hash(&mut h);
    }
    b.raw_bits().hash(&mut h);
    m.hash(&mut h);
    h.finish()
}

/// The decomposition system for target abscissa `x_r`.  Everything but
/// the last link is independent of the target and the last link is
/// linear in its bits, so the system is instantiated from a
/// [`DecompositionTemplate`] built once — `n` polynomial additions per
/// target instead of the symbolic field arithmetic of
/// [`build_decomposition_system`], which measured 29 % of a whole
/// `m = 2` decomposition at `n = 23`.  The equations are identical
/// either way (`every_target_matches_original_chain`).
///
/// With the algebra cache configured (`IC_PREPROCESS_CACHE`), templates
/// go through it; otherwise a small per-thread memo holds them.
/// `IC_TEMPLATE_MEMO=0` restores building every system from scratch, as
/// a same-binary control.
pub fn build_decomposition_system_reusing(
    basis: &[F2mElement],
    x_r: &F2mElement,
    b: &F2mElement,
    m: usize,
    st: &FieldStructure,
) -> Option<DecompositionSystem> {
    if !algebra_cache::enabled(Layer::Preprocessing) {
        static MEMO_OFF: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        if *MEMO_OFF.get_or_init(|| std::env::var("IC_TEMPLATE_MEMO").as_deref() == Ok("0")) {
            return build_decomposition_system(basis, x_r, b, m, st);
        }
        let key = local_template_key(basis, b, m, st);
        let hit = TEMPLATES.with(|t| {
            t.borrow()
                .iter()
                .find(|(k, tpl)| *k == key && tpl.matches(basis, b, m, st))
                .map(|(_, tpl)| tpl.clone())
        });
        let template = match hit {
            Some(t) => t,
            None => {
                let Some(built) = DecompositionTemplate::build(basis, b, m, st) else {
                    return build_decomposition_system(basis, x_r, b, m, st);
                };
                let built = std::rc::Rc::new(built);
                TEMPLATES.with(|t| {
                    let mut t = t.borrow_mut();
                    if t.len() == LOCAL_TEMPLATES {
                        t.remove(0);
                    }
                    t.push((key, built.clone()));
                });
                built
            }
        };
        return Some(template.instantiate(x_r));
    }
    let key = template_key(basis, b, m, st);
    let template: DecompositionTemplate =
        algebra_cache::memoize(Layer::Preprocessing, &key, || {
            DecompositionTemplate::build(basis, b, m, st)
        })?;
    Some(template.instantiate(x_r))
}

// There is deliberately no cache for a Gröbner basis of
// `parameterized_generators()`.  `parameter_basis_cached` held one, under
// `Layer::Parameterized`, until it was measured on every template its
// 16-variable cap admitted (n = 3, 4; m = 2, 3; every ell and b = 1..3; 24
// templates, 288 targets):
//
//   * computing the basis once cost 1.5x to 821x more operations than
//     solving EVERY target in the field from scratch.  A cache of the 2^n
//     answers dominates a cache of the basis, and no reuse pattern can
//     amortise a basis that costs more than everything it could replace;
//   * completing from the specialized basis was cheaper than solving from
//     scratch in 17 of 24 templates and dearer in 7; where it was cheaper
//     the systems cost 24 to 650 operations to begin with;
//   * the specialization stayed a Gröbner basis for 100% of targets at
//     ell = 1, 85% at ell = 2 and 47% at ell = 3.  Completing from it is
//     correct either way, since it generates the right ideal; genericity
//     only decides the cost.
//
// The 2026-09-14 experiment reached the same verdict on wall time
// (research/polynomial_reuse_20260914/RESULTS.md: "failed its promotion
// criterion"), on an engine that had not yet closed under the field
// equations and so did less work than a correct one.  `parameterized_generators`
// and `specialize_parameter_basis` remain: they are exact, cheap, and that
// experiment's benchmark reproduces through them.

#[cfg(test)]
mod tests {
    use super::*;
    use crate::binary_ecc::IrreduciblePoly;
    fn field() -> FieldStructure {
        FieldStructure::new(
            3,
            &IrreduciblePoly {
                degree: 3,
                low_terms: vec![1, 0],
            },
        )
    }
    fn fe(x: u64) -> F2mElement {
        F2mElement::from_bit_positions(&(0..3).filter(|k| x & (1 << k) != 0).collect::<Vec<_>>(), 3)
    }
    #[test]
    fn every_target_matches_original_chain() {
        let st = field();
        let basis = vec![fe(1), fe(2)];
        for m in 2..=4 {
            let t = DecompositionTemplate::build(&basis, &fe(1), m, &st).unwrap();
            for r in 0..8 {
                assert_eq!(
                    t.instantiate(&fe(r)).equations,
                    build_decomposition_system(&basis, &fe(r), &fe(1), m, &st)
                        .unwrap()
                        .equations
                );
            }
        }
    }
    #[test]
    fn memoised_systems_match_direct_builds_on_real_curves() {
        use crate::cryptanalysis::koblitz_index_calculus::{
            build_frobenius_factor_base, KoblitzCurve,
        };
        use num_bigint::BigUint;
        for (a, n, m) in [(0u8, 9u32, 2usize), (0, 9, 3), (1, 17, 2), (0, 13, 3)] {
            let kc = KoblitzCurve::new(a, n).unwrap();
            let fb = build_frobenius_factor_base(&kc, 0).unwrap();
            let st = FieldStructure::new(kc.n, &kc.curve.irreducible);
            for k in 1..24u32 {
                let x = match kc.mul(kc.generator(), &BigUint::from(1000 + 37 * k)) {
                    crate::binary_ecc::BinaryPoint::Affine { x, .. } => x,
                    _ => continue,
                };
                let direct =
                    build_decomposition_system(&fb.subspace_basis, &x, &kc.curve.b, m, &st);
                let reused =
                    build_decomposition_system_reusing(&fb.subspace_basis, &x, &kc.curve.b, m, &st);
                assert_eq!(
                    direct.map(|s| s.equations),
                    reused.map(|s| s.equations),
                    "K_{a}/2^{n} m={m} k={k}"
                );
            }
        }
    }
    #[test]
    fn target_symbolization_matches_every_specialization() {
        let st = field();
        let t = DecompositionTemplate::build(&[fe(1), fe(2)], &fe(1), 2, &st).unwrap();
        let p = t.parameterized_generators().unwrap();
        for r in 0..8 {
            assert_eq!(
                t.specialize_parameter_basis(&p, r),
                t.instantiate(&fe(r)).equations
            );
        }
    }
    #[test]
    fn keys_separate_basis_order_and_curve_coefficient() {
        let st = field();
        assert_ne!(
            template_key(&[fe(1), fe(2)], &fe(1), 2, &st),
            template_key(&[fe(2), fe(1)], &fe(1), 2, &st)
        );
        assert_ne!(
            template_key(&[fe(1)], &fe(1), 2, &st),
            template_key(&[fe(1)], &fe(2), 2, &st)
        );
    }

    /// Specializing a Gröbner basis of the parametric system gives a
    /// generating set of the target's ideal, generic target or not, so
    /// completing it must land on the target's own reduced basis: reduced
    /// Gröbner bases are unique.  Zero sets alone cannot show that — a
    /// generating set with the right ideal has the right zero set whether or
    /// not anything was closed — so this compares the bases.  `b = 1` is
    /// the Koblitz coefficient, where the engine used to stop short.
    #[test]
    fn specialized_parameter_basis_completes_to_the_targets_basis() {
        use super::super::pq_groebner_f2::{groebner_basis_f2, is_boolean_groebner_basis};
        for b in 1..=3 {
            let t = DecompositionTemplate::build(&[fe(1), fe(2)], &fe(b), 2, &field()).unwrap();
            let total = t.n_vars + t.n as usize;
            let g = groebner_basis_f2(t.parameterized_generators().unwrap(), total);
            assert!(
                is_boolean_groebner_basis(&g),
                "b = {b}: parametric basis not closed"
            );
            for r in 0..8 {
                let specialized = t.specialize_parameter_basis(&g, r);
                let original = t.instantiate(&fe(r)).equations;
                for x in 0..16 {
                    assert_eq!(
                        specialized.iter().all(|p| p.eval(x) == 0),
                        original.iter().all(|p| p.eval(x) == 0)
                    );
                }
                assert_eq!(
                    groebner_basis_f2(specialized, t.n_vars),
                    groebner_basis_f2(original, t.n_vars),
                    "b = {b}, r = {r}"
                );
            }
        }
    }
}
