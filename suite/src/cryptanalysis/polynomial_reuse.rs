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
pub fn build_decomposition_system_reusing(
    basis: &[F2mElement],
    x_r: &F2mElement,
    b: &F2mElement,
    m: usize,
    st: &FieldStructure,
) -> Option<DecompositionSystem> {
    if !algebra_cache::enabled(Layer::Preprocessing) {
        return build_decomposition_system(basis, x_r, b, m, st);
    }
    let key = template_key(basis, b, m, st);
    let template: DecompositionTemplate =
        algebra_cache::memoize(Layer::Preprocessing, &key, || {
            DecompositionTemplate::build(basis, b, m, st)
        })?;
    Some(template.instantiate(x_r))
}

/// Offline experiment only. Caller must enforce a process timeout/RSS budget;
/// the existing Buchberger engine has no interrupt hook. The 16-variable cap
/// prevents accidentally applying this toy experiment to production fields.
pub fn parameter_basis_cached(
    template: &DecompositionTemplate,
    cache: &mut algebra_cache::AlgebraCache,
) -> Option<Vec<F2BoolPoly>> {
    let total = template.n_vars + template.n as usize;
    if total > 16 {
        return None;
    }
    let key = serde_json::to_vec(template).ok()?;
    cache.memoize(Layer::Parameterized, &key, || {
        Some(super::pq_groebner_f2::groebner_basis_f2(
            template.parameterized_generators()?,
            total,
        ))
    })
}

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

    #[test]
    fn cached_parameter_basis_preserves_all_boolean_fibers() {
        let t = DecompositionTemplate::build(&[fe(1), fe(2)], &fe(1), 2, &field()).unwrap();
        let mut cache = algebra_cache::AlgebraCache::local(1024 * 1024);
        let g = parameter_basis_cached(&t, &mut cache).unwrap();
        assert_eq!(g, parameter_basis_cached(&t, &mut cache).unwrap());
        assert_eq!(cache.stats[2].local_hits, 1);
        for r in 0..8 {
            let specialized = t.specialize_parameter_basis(&g, r);
            let original = t.instantiate(&fe(r));
            for x in 0..16 {
                assert_eq!(
                    specialized.iter().all(|p| p.eval(x) == 0),
                    original.equations.iter().all(|p| p.eval(x) == 0)
                );
            }
        }
    }
}
