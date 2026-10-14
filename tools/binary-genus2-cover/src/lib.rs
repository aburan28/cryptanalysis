//! Same-field degree-three cover of `y²+xy=x³+a*x²+1` by a genus-two curve.
//!
//! The group transfer is into the Jacobian, using the existing checked
//! characteristic-two Mumford arithmetic. See the study for the geometric
//! proof. No generic norm or discrete-log solver is implemented here.

#![recursion_limit = "256"]

use curve_backend::binary_ecc::{
    BinaryCoverPoint, BinaryPoint, F2mElement, F2mPoly, HyperellipticCurve, IrreduciblePoly,
    MumfordDivisor,
};

pub mod checks;

pub type Result<T> = std::result::Result<T, String>;

#[derive(Clone, Debug)]
pub struct GenusTwoCover {
    source: HyperellipticCurve,
    a: F2mElement,
}

impl GenusTwoCover {
    /// Construct `v²+u²v=u⁵+a*u⁴+u³+u`; `b=1` is fixed.
    pub fn new(m: u32, irr: IrreduciblePoly, a: F2mElement) -> Result<Self> {
        if a.m_value() != m {
            return Err("a has the wrong field width".into());
        }
        let zero = F2mElement::zero(m);
        let one = F2mElement::one(m);
        let h = F2mPoly::from_coeffs(vec![zero.clone(), zero.clone(), one.clone()], m);
        let f = F2mPoly::from_coeffs(
            vec![zero.clone(), one.clone(), zero, one.clone(), a.clone(), one],
            m,
        );
        let source = HyperellipticCurve::try_new(m, irr, h, f, 2).map_err(|e| e.to_string())?;
        let cover = Self { source, a };
        cover.verify_cleared_map_identity()?;
        Ok(cover)
    }

    pub fn source(&self) -> &HyperellipticCurve {
        &self.source
    }

    pub fn target_contains(&self, p: &BinaryPoint) -> bool {
        let BinaryPoint::Affine { x, y } = p else {
            return true;
        };
        let c = &self.source;
        if x.m_value() != c.m || y.m_value() != c.m {
            return false;
        }
        let x2 = x.square(&c.irr);
        y.square(&c.irr).add(&x.mul(y, &c.irr))
            == x2
                .mul(x, &c.irr)
                .add(&self.a.mul(&x2, &c.irr))
                .add(&F2mElement::one(c.m))
    }

    /// Evaluate the projective extension, including all rational poles.
    pub fn map_point(&self, p: &BinaryCoverPoint) -> Result<BinaryPoint> {
        let c = &self.source;
        let BinaryCoverPoint::Affine { u, v } = p else {
            return Ok(BinaryPoint::Infinity);
        };
        if u.m_value() != c.m || v.m_value() != c.m || !c.is_on_curve(u, v) {
            return Err("point is not on the declared source curve".into());
        }
        let t = u.add(&F2mElement::one(c.m));
        if t.is_zero() {
            return Ok(BinaryPoint::Infinity);
        }
        let ti = t
            .flt_inverse(&c.irr)
            .ok_or("nonzero denominator has no inverse")?;
        let ti2 = ti.square(&c.irr);
        let u2 = u.square(&c.irr);
        let x = u2.mul(u, &c.irr).mul(&ti2, &c.irr);
        let numerator = u
            .mul(&t, &c.irr)
            .mul(v, &c.irr)
            .add(&u2)
            .add(u)
            .add(&F2mElement::one(c.m));
        let y = numerator.mul(&ti2.mul(&ti, &c.irr), &c.irr);
        let image = BinaryPoint::Affine { x, y };
        if !self.target_contains(&image) {
            return Err("map failed the target equation".into());
        }
        Ok(image)
    }

    /// The reduced pair for `pi*([P]-[O])`, relative to source infinity.
    pub fn pullback(&self, p: &BinaryPoint) -> Result<MumfordDivisor> {
        if !self.target_contains(p) {
            return Err("point is not on the declared elliptic curve".into());
        }
        let c = &self.source;
        let BinaryPoint::Affine { x, y } = p else {
            return Ok(MumfordDivisor::identity(c.m));
        };
        if x.is_zero() {
            return MumfordDivisor::try_new(c, F2mPoly::x(c.m), F2mPoly::zero(c.m))
                .map_err(|e| e.to_string());
        }
        let xi = x.flt_inverse(&c.irr).ok_or("nonzero x has no inverse")?;
        let one = F2mElement::one(c.m);
        let slope = x.add(&y.add(&one).mul(&xi.square(&c.irr), &c.irr));
        let u = F2mPoly::from_coeffs(vec![x.clone(), xi, one.clone()], c.m);
        let v = F2mPoly::from_coeffs(vec![x.add(y).add(&one), slope], c.m);
        MumfordDivisor::try_new(c, u, v).map_err(|e| e.to_string())
    }

    /// Inverse on the pullback image only. Recompute and compare the full pair.
    /// A valid arbitrary Jacobian class may be outside this image.
    pub fn inverse_on_image(&self, d: &MumfordDivisor) -> Result<BinaryPoint> {
        let c = &self.source;
        d.validate(c).map_err(|e| e.to_string())?;
        if d.is_identity() {
            return Ok(BinaryPoint::Infinity);
        }
        let one = F2mElement::one(c.m);
        let p = if d.u == F2mPoly::x(c.m) && d.v.is_zero() {
            BinaryPoint::Affine {
                x: F2mElement::zero(c.m),
                y: one,
            }
        } else if d.u.degree() == Some(2) {
            let x = d.u.coeff(0);
            if x.is_zero() {
                return Err("divisor is outside the pullback image".into());
            }
            let y = d.v.coeff(0).add(&x).add(&one);
            BinaryPoint::Affine { x, y }
        } else {
            return Err("divisor is outside the pullback image".into());
        };
        if self.pullback(&p)? != *d {
            return Err("divisor is outside the pullback image".into());
        }
        Ok(p)
    }

    /// Exact coefficient checks in k[u], for each coefficient of v.
    /// With t=u+1 and B=u*t*v+u²+u+1, the cleared E equation is
    /// B²+u³*t*B+u⁹+a*u⁶*t²+t⁶ = u²*t²*(v²+u²*v+f).
    pub fn verify_cleared_map_identity(&self) -> Result<()> {
        let c = &self.source;
        let irr = &c.irr;
        let u = F2mPoly::x(c.m);
        let one = F2mPoly::one(c.m);
        let t = u.add(&one);
        let u2 = u.mul(&u, irr);
        let u3 = u2.mul(&u, irr);
        let t2 = t.mul(&t, irr);
        let t3 = t2.mul(&t, irr);
        let b0 = u2.add(&u).add(&one);
        let b1 = u.mul(&t, irr);
        let factor = u2.mul(&t2, irr);
        let constant = b0
            .mul(&b0, irr)
            .add(&u3.mul(&t, irr).mul(&b0, irr))
            .add(&u3.mul(&u3, irr).mul(&u3, irr))
            .add(&u3.mul(&u3, irr).mul(&t2, irr).scalar_mul(&self.a, irr))
            .add(&t3.mul(&t3, irr));
        if b1.mul(&b1, irr) != factor
            || u3.mul(&t, irr).mul(&b1, irr) != factor.mul(&c.h, irr)
            || constant != factor.mul(&c.f, irr)
        {
            return Err("cleared map identity does not hold coefficientwise".into());
        }
        Ok(())
    }
}
