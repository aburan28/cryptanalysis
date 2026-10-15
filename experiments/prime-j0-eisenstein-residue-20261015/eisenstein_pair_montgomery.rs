//! Power-of-two Montgomery arithmetic in the Eisenstein residue field.
#[path = "eisenstein_pair_fixed_int.rs"]
mod fixed_int;
use fixed_int::I512 as I;
use num_bigint::{BigInt, BigUint, Sign};
use num_traits::Zero;
use serde_json::Value;
use std::{cmp::Ordering, env, fs, time::Instant};

const P_HEX: &str = "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f";
const HALF_P_HEX: &str = "7fffffffffffffffffffffffffffffffffffffffffffffffffffffff7ffffe17";
const BETA_HEX: &str = "7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee";
const GX_HEX: &str = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798";
const GY_HEX: &str = "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8";
const PI_A_HEX: &str = "-114ca50f7a8e2f3f657c1108d9d44cfd9";
const PI_B_HEX: &str = "-3086d221a7d46bcde86c90e49284eb16";
const INV_P_MOD_RADIX: u128 = 0x434ddc0123db5fa627c7f6e22ddacacf;
const INV_RADIX_MOD_P_HEX: &str = "bcb223fedc24a059d838091dd2253530ffffffffffffffffffffffff434dd931";

fn big_hex(s: &str) -> BigInt { BigInt::parse_bytes(s.as_bytes(),16).unwrap() }
fn to_big(value: I) -> BigInt {
    let mut bytes = Vec::with_capacity(64);
    for limb in value.limbs { bytes.extend_from_slice(&limb.to_le_bytes()); }
    BigInt::from_bytes_le(if value.negative { Sign::Minus } else { Sign::Plus }, &bytes)
}

#[derive(Clone, Copy)]
struct Context { p: I, half_p: I, c: I, a: I, b: I, amb: I, one: F }

fn low_mod_radix(value: I) -> u128 {
    let low = value.limbs[0] as u128 | ((value.limbs[1] as u128) << 64);
    if value.negative { low.wrapping_neg() } else { low }
}
fn centered_radix(value: u128) -> I {
    if value >> 127 == 0 { I::from_u128(value) }
    else { I::from_u128(value.wrapping_neg()).neg() }
}
fn divide_radix_exact(value: I) -> I {
    assert_eq!(value.limbs[0],0);
    assert_eq!(value.limbs[1],0);
    let mut limbs=[0u64;8];
    limbs[..6].copy_from_slice(&value.limbs[2..8]);
    I {negative:value.negative,limbs}
}

impl Context {
    fn new() -> Self {
        let p = I::from_hex(P_HEX);
        let half_p = I::from_hex(HALF_P_HEX);
        let c = I::from_u128((1u128 << 32) + 977);
        let a = I::from_hex(PI_A_HEX);
        let b = I::from_hex(PI_B_HEX);
        let amb = a.sub(b);
        assert_eq!(p, I::ONE.shl_bits(256).sub(c));
        assert_eq!(half_p.add(half_p).add(I::ONE), p);
        assert_eq!(a.mul(a).sub(a.mul(b)).add(b.mul(b)),p);
        assert_eq!((to_big(a) + to_big(b)*big_hex(BETA_HEX)) % to_big(p), BigInt::zero());
        let mut ctx=Self { p, half_p, c, a, b, amb, one:F::zero() };
        ctx.one=ctx.reduce(I::ONE.shl_bits(128),I::ZERO);
        ctx
    }
    fn nearest(&self, numerator: I) -> I {
        let shifted = numerator.add(self.half_p);
        let q0 = shifted.shr256_floor();
        let low = shifted.sub(q0.shl_bits(256));
        assert!(!low.negative && low.cmp_signed(I::ONE.shl_bits(256)) == Ordering::Less);
        let correction = q0.mul(self.c);
        assert!(correction.abs().cmp_abs(self.p.sub(self.c)) == Ordering::Less);
        let r = low.add(correction);
        if r.negative { q0.sub(I::ONE) }
        else if r.cmp_signed(self.p) != Ordering::Less { q0.add(I::ONE) }
        else { q0 }
    }
    fn reduce(&self, x: I, y: I) -> F {
        let q1 = self.nearest(self.amb.mul(x).add(self.b.mul(y)));
        let q2 = self.nearest(self.b.neg().mul(x).add(self.a.mul(y)));
        let u = x.sub(q1.mul(self.a)).add(q2.mul(self.b));
        let v = y.sub(q1.mul(self.b)).sub(q2.mul(self.amb));
        assert!(u.fits_signed_magnitude128() && v.fits_signed_magnitude128());
        F { u, v }
    }
    fn montgomery_reduce(&self, x: I, y: I) -> F {
        let n1 = low_mod_radix(self.amb).wrapping_mul(low_mod_radix(x))
            .wrapping_add(low_mod_radix(self.b).wrapping_mul(low_mod_radix(y)));
        let n2 = low_mod_radix(self.b.neg()).wrapping_mul(low_mod_radix(x))
            .wrapping_add(low_mod_radix(self.a).wrapping_mul(low_mod_radix(y)));
        let q1=centered_radix(n1.wrapping_neg().wrapping_mul(INV_P_MOD_RADIX));
        let q2=centered_radix(n2.wrapping_neg().wrapping_mul(INV_P_MOD_RADIX));
        let nx=x.add(q1.mul(self.a)).sub(q2.mul(self.b));
        let ny=y.add(q1.mul(self.b)).add(q2.mul(self.amb));
        let zx=divide_radix_exact(nx);
        let zy=divide_radix_exact(ny);
        if zx.fits_signed_magnitude128() && zy.fits_signed_magnitude128() {
            F {u:zx,v:zy}
        } else { self.reduce(zx,zy) }
    }
    fn from_field(&self, x: I) -> F {
        assert!(!x.negative && x.cmp_signed(self.p) == Ordering::Less);
        let represented=(to_big(x)<<128usize)%to_big(self.p);
        self.reduce(I::from_hex(&represented.to_str_radix(16)),I::ZERO)
    }
    fn to_field(&self, x: F) -> BigInt {
        let p = to_big(self.p);
        let mut result = (to_big(x.u) + to_big(x.v)*big_hex(BETA_HEX))
            *big_hex(INV_RADIX_MOD_P_HEX)% &p;
        if result.sign() == Sign::Minus { result += p; }
        result
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
struct F { u: I, v: I }
impl F {
    fn zero() -> Self { Self { u:I::ZERO, v:I::ZERO } }
    fn one() -> Self { Self { u:I::ONE, v:I::ZERO } }
    fn is_zero(self) -> bool { self.u.is_zero() && self.v.is_zero() }
    fn canonical(self, ctx: &Context) -> Self { ctx.reduce(self.u,self.v) }
    fn add(self, rhs: Self, _ctx: &Context) -> Self {
        Self {u:self.u.add(rhs.u),v:self.v.add(rhs.v)}
    }
    fn sub(self, rhs: Self, _ctx: &Context) -> Self {
        Self {u:self.u.sub(rhs.u),v:self.v.sub(rhs.v)}
    }
    fn mul(self, rhs: Self, ctx: &Context) -> Self {
        let a = self.u.mul(rhs.u);
        let b = self.v.mul(rhs.v);
        let c = self.u.add(self.v).mul(rhs.u.add(rhs.v));
        ctx.montgomery_reduce(a.sub(b),c.sub(a).sub(b.shl_bits(1)))
    }
    fn square(self, ctx: &Context) -> Self { self.mul(self,ctx) }
    fn mul_small(self, n: u128, _ctx: &Context) -> Self {
        let factor = I::from_u128(n);
        Self {u:self.u.mul(factor),v:self.v.mul(factor)}
    }
    fn rotate(self, ctx: &Context) -> Self {
        ctx.reduce(self.v.neg(), self.u.sub(self.v))
    }
    fn pack33(self) -> [u8;33] {
        assert!(self.u.fits_signed_magnitude128() && self.v.fits_signed_magnitude128());
        let mut out = [0u8;33];
        let set = |out: &mut [u8;33], bit:usize| { out[bit/8] |= 1u8 << (bit%8); };
        for (offset, coord) in [(0usize,self.u),(129usize,self.v)] {
            let magnitude = coord.abs_u128();
            for bit in 0..128 {
                if (magnitude >> bit) & 1 == 1 { set(&mut out,offset+bit); }
            }
            if coord.negative { set(&mut out,offset+128); }
        }
        out
    }
    fn unpack33(payload: [u8;33]) -> Self {
        assert_eq!(payload[32] & 0b11111100,0);
        let get = |bit:usize| -> bool { payload[bit/8] & (1u8 << (bit%8)) != 0 };
        let coord = |offset:usize| -> I {
            let mut mag = 0u128;
            for bit in 0..128 { if get(offset+bit) { mag |= 1u128 << bit; } }
            assert!(!(get(offset+128) && mag == 0), "negative zero encoding");
            let value = I::from_u128(mag);
            if get(offset+128) { value.neg() } else { value }
        };
        Self {u:coord(0),v:coord(129)}
    }
}

#[derive(Clone, Copy)]
struct Point { x:F,y:F,z:F }
impl Point {
    fn identity() -> Self { Self { x:F::zero(),y:F::one(),z:F::zero() } }
    fn generator(ctx:&Context) -> Self {
        Self { x:ctx.from_field(I::from_hex(GX_HEX)),
               y:ctx.from_field(I::from_hex(GY_HEX)),z:ctx.one }
    }
    fn double(self,ctx:&Context) -> Self {
        if self.z.is_zero() || self.y.is_zero() { return Self::identity(); }
        let a=self.x.square(ctx);
        let b=self.y.square(ctx);
        let c=b.square(ctx);
        let d=self.x.add(b,ctx).square(ctx).sub(a,ctx).sub(c,ctx).mul_small(2,ctx);
        let e=a.mul_small(3,ctx);
        let f=e.square(ctx);
        let x=f.sub(d.mul_small(2,ctx),ctx);
        let y=e.mul(d.sub(x,ctx),ctx).sub(c.mul_small(8,ctx),ctx);
        let z=self.y.mul(self.z,ctx).mul_small(2,ctx);
        Self{x,y,z}
    }
    fn add_mixed(self,q:Self,ctx:&Context) -> Self {
        assert_eq!(q.z,ctx.one);
        if self.z.is_zero() { return q; }
        let zz=self.z.square(ctx);
        let u=q.x.mul(zz,ctx);
        let s=q.y.mul(self.z.mul(zz,ctx),ctx);
        let h=u.sub(self.x,ctx).canonical(ctx);
        let dy=s.sub(self.y,ctx);
        if h.is_zero() { return if dy.canonical(ctx).is_zero() { self.double(ctx) } else { Self::identity() }; }
        let hh=h.square(ctx);
        let hhh=h.mul(hh,ctx);
        let v=self.x.mul(hh,ctx);
        let x=dy.square(ctx).sub(hhh,ctx).sub(v.mul_small(2,ctx),ctx);
        let y=dy.mul(v.sub(x,ctx),ctx).sub(self.y.mul(hhh,ctx),ctx);
        let z=self.z.mul(h,ctx);
        Self{x,y,z}
    }
    fn multiply_binary(q:Self,scalar:&BigUint,ctx:&Context) -> Self {
        let mut out=Self::identity();
        for byte in scalar.to_bytes_be() {
            for bit in (0..8).rev() {
                out=out.double(ctx);
                if (byte >> bit) & 1 != 0 { out=out.add_mixed(q,ctx); }
            }
        }
        out
    }
    fn matches_affine(self,x:F,y:F,ctx:&Context) -> bool {
        if self.z.is_zero() { return false; }
        let zz=self.z.square(ctx);
        self.x.canonical(ctx) == x.mul(zz,ctx).canonical(ctx)
            && self.y.canonical(ctx) == y.mul(self.z.mul(zz,ctx),ctx).canonical(ctx)
    }
}

fn main() {
    let args:Vec<String>=env::args().collect();
    assert_eq!(args.len(),3,"usage: eisenstein_pair_fixed fixture.json count");
    let count:usize=args[2].parse().unwrap();
    let ctx=Context::new();
    let data:Value=serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
    let cases=data["cases"].as_array().unwrap();
    assert!(count>0 && count<=cases.len());
    let g=Point::generator(&ctx);
    assert_eq!(F::unpack33(g.x.pack33()),g.x);
    assert_eq!(ctx.to_field(g.x.rotate(&ctx)),
               (big_hex(BETA_HEX)*big_hex(GX_HEX))%to_big(ctx.p));
    assert_eq!(g.x.rotate(&ctx).rotate(&ctx).rotate(&ctx),g.x);
    let started=Instant::now();
    let mut outputs=Vec::with_capacity(count);
    for case in cases.iter().take(count) {
        let scalar=BigUint::parse_bytes(case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
        outputs.push(Point::multiply_binary(g,&scalar,&ctx));
    }
    let online_ms=started.elapsed().as_secs_f64()*1000.0;
    for (case,out) in cases.iter().take(count).zip(outputs) {
        let (x,y)=case["point_hex"].as_str().unwrap().split_once(':').unwrap();
        let expected_x=ctx.from_field(I::from_hex(x));
        let expected_y=ctx.from_field(I::from_hex(y));
        assert_eq!(F::unpack33(expected_x.pack33()),expected_x);
        assert_eq!(F::unpack33(expected_y.pack33()),expected_y);
        assert_eq!(ctx.to_field(expected_x.rotate(&ctx)),
                   (big_hex(BETA_HEX)*big_hex(x))%to_big(ctx.p));
        assert!(out.matches_affine(expected_x,expected_y,&ctx));
    }
    println!("scheme=eisenstein_pair_montgomery reducer=radix128 count={count} online_ms={online_ms:.6} verified=1 packed_x_bytes=33");
}
