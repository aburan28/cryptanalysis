//! Exact native baseline for the Eisenstein-residue field and scalar path.
//! Build in the frozen prime-j0 Cargo project, which supplies num-bigint.
use num_bigint::{BigInt, BigUint, Sign};
use num_traits::{One, Signed, Zero};
use serde_json::Value;
use std::{env, fs, time::Instant};

const P_HEX: &str = "fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f";
const BETA_HEX: &str = "7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee";
const GX_HEX: &str = "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798";
const GY_HEX: &str = "483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8";
const PI_A: &str = "-367917413016453100223835821029139468249";
const PI_B: &str = "-64502973549206556628585045361533709078";

fn decimal(s: &str) -> BigInt { BigInt::parse_bytes(s.as_bytes(), 10).unwrap() }
fn hex(s: &str) -> BigInt { BigInt::parse_bytes(s.as_bytes(), 16).unwrap() }

#[derive(Clone)]
struct Context { p: BigInt, beta: BigInt, a: BigInt, b: BigInt, solinas: bool }

impl Context {
    fn new(solinas: bool) -> Self {
        let p = hex(P_HEX);
        let beta = hex(BETA_HEX);
        let a = decimal(PI_A);
        let b = decimal(PI_B);
        assert_eq!(&a*&a - &a*&b + &b*&b, p);
        assert_eq!((&a + &beta*&b) % &p, BigInt::zero());
        Self { p, beta, a, b, solinas }
    }

    fn nearest(&self, numerator: BigInt) -> BigInt {
        // floor((numerator + floor(p/2))/p), including negative numerators.
        let shifted = numerator + (&self.p >> 1);
        if self.solinas {
            // p = 2^256-c. q0=floor(shifted/2^256) and
            // shifted-q0*p = low_256(shifted)+q0*c. For this field kernel
            // |q0*c|<p, so one correction gives the exact floor quotient.
            let q0: BigInt = &shifted >> 256usize;
            let low = shifted - (&q0 << 256usize);
            let c = BigInt::from((1u64 << 32) + 977);
            let correction = &q0 * &c;
            assert!(correction.abs() < &self.p - &c);
            let r: BigInt = low + correction;
            if r.sign() == Sign::Minus { q0 - 1 }
            else if r >= self.p { q0 + 1 }
            else { q0 }
        } else {
            let q = &shifted / &self.p;
            let r: BigInt = shifted % &self.p;
            if r.sign() == Sign::Minus { q - 1 } else { q }
        }
    }

    fn reduce(&self, x: BigInt, y: BigInt) -> F {
        let q1 = self.nearest((&self.a - &self.b)*&x + &self.b*&y);
        let q2 = self.nearest(-&self.b*&x + &self.a*&y);
        let u = x - &q1*&self.a + &q2*&self.b;
        let v = y - &q1*&self.b - &q2*(&self.a - &self.b);
        debug_assert!(u.abs() < (BigInt::one() << 128));
        debug_assert!(v.abs() < (BigInt::one() << 128));
        F { u, v }
    }

    fn from_field(&self, value: BigInt) -> F {
        assert!(value >= BigInt::zero() && value < self.p);
        self.reduce(value, BigInt::zero())
    }

    fn to_field(&self, value: &F) -> BigInt {
        let mut x = (&value.u + &self.beta*&value.v) % &self.p;
        if x.sign() == Sign::Minus { x += &self.p; }
        x
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct F { u: BigInt, v: BigInt }

impl F {
    fn zero() -> Self { Self { u: BigInt::zero(), v: BigInt::zero() } }
    fn one(ctx: &Context) -> Self { ctx.from_field(BigInt::one()) }
    fn is_zero(&self) -> bool { self.u.is_zero() && self.v.is_zero() }
    fn add(&self, rhs: &Self, ctx: &Context) -> Self {
        ctx.reduce(&self.u + &rhs.u, &self.v + &rhs.v)
    }
    fn sub(&self, rhs: &Self, ctx: &Context) -> Self {
        ctx.reduce(&self.u - &rhs.u, &self.v - &rhs.v)
    }
    fn mul(&self, rhs: &Self, ctx: &Context) -> Self {
        let a = &self.u * &rhs.u;
        let b = &self.v * &rhs.v;
        let c = (&self.u + &self.v) * (&rhs.u + &rhs.v);
        ctx.reduce(&a - &b, c - a - (&b << 1))
    }
    fn square(&self, ctx: &Context) -> Self { self.mul(self, ctx) }
    fn mul_small(&self, n: i32, ctx: &Context) -> Self {
        ctx.reduce(&self.u * n, &self.v * n)
    }
    fn rotate(&self, ctx: &Context) -> Self {
        ctx.reduce(-&self.v, &self.u - &self.v)
    }

    fn pack33(&self) -> [u8; 33] {
        let bound = BigInt::one() << 128;
        assert!(self.u.abs() < bound && self.v.abs() < bound);
        let magnitude = |n: &BigInt| -> BigUint { n.abs().to_biguint().unwrap() };
        let mut words = magnitude(&self.u);
        if self.u.sign() == Sign::Minus { words += BigUint::one() << 128; }
        let mut upper = magnitude(&self.v);
        if self.v.sign() == Sign::Minus { upper += BigUint::one() << 128; }
        words += upper << 129;
        let bytes = words.to_bytes_le();
        let mut out = [0u8; 33];
        out[..bytes.len()].copy_from_slice(&bytes);
        out
    }

    fn unpack33(bytes: &[u8; 33]) -> Self {
        let packed = BigUint::from_bytes_le(bytes);
        assert!((&packed >> 258usize).is_zero());
        let mask = (BigUint::one() << 129) - BigUint::one();
        let coordinate = |word: BigUint| -> BigInt {
            let negative = (&word >> 128) == BigUint::one();
            let mag = word & ((BigUint::one() << 128) - BigUint::one());
            let result = BigInt::from(mag);
            if negative { -result } else { result }
        };
        Self { u: coordinate(&packed & &mask), v: coordinate(packed >> 129) }
    }
}

#[derive(Clone)]
struct Point { x: F, y: F, z: F }

impl Point {
    fn identity() -> Self { Self { x: F::zero(), y: F::one_raw(), z: F::zero() } }
    fn generator(ctx: &Context) -> Self {
        Self { x: ctx.from_field(hex(GX_HEX)), y: ctx.from_field(hex(GY_HEX)), z: F::one(ctx) }
    }
    fn double(&self, ctx: &Context) -> Self {
        if self.z.is_zero() || self.y.is_zero() { return Self::identity(); }
        let a = self.x.square(ctx);
        let b = self.y.square(ctx);
        let c = b.square(ctx);
        let d = self.x.add(&b,ctx).square(ctx).sub(&a,ctx).sub(&c,ctx).mul_small(2,ctx);
        let e = a.mul_small(3,ctx);
        let f = e.square(ctx);
        let x = f.sub(&d.mul_small(2,ctx),ctx);
        let y = e.mul(&d.sub(&x,ctx),ctx).sub(&c.mul_small(8,ctx),ctx);
        let z = self.y.mul(&self.z,ctx).mul_small(2,ctx);
        Self { x, y, z }
    }
    fn add_mixed(&self, q: &Self, ctx: &Context) -> Self {
        assert_eq!(q.z, F::one(ctx));
        if self.z.is_zero() { return q.clone(); }
        let zz = self.z.square(ctx);
        let u = q.x.mul(&zz,ctx);
        let s = q.y.mul(&self.z.mul(&zz,ctx),ctx);
        let h = u.sub(&self.x,ctx);
        let dy = s.sub(&self.y,ctx);
        if h.is_zero() {
            return if dy.is_zero() { self.double(ctx) } else { Self::identity() };
        }
        let hh = h.square(ctx);
        let hhh = h.mul(&hh,ctx);
        let v = self.x.mul(&hh,ctx);
        let x = dy.square(ctx).sub(&hhh,ctx).sub(&v.mul_small(2,ctx),ctx);
        let y = dy.mul(&v.sub(&x,ctx),ctx).sub(&self.y.mul(&hhh,ctx),ctx);
        let z = self.z.mul(&h,ctx);
        Self { x, y, z }
    }
    fn multiply_binary(q: &Self, scalar: &BigUint, ctx: &Context) -> Self {
        let mut out = Self::identity();
        for byte in scalar.to_bytes_be() {
            for bit in (0..8).rev() {
                out = out.double(ctx);
                if (byte >> bit) & 1 != 0 { out = out.add_mixed(q,ctx); }
            }
        }
        out
    }
    fn matches_affine(&self, x: &F, y: &F, ctx: &Context) -> bool {
        if self.z.is_zero() { return false; }
        let zz = self.z.square(ctx);
        self.x == x.mul(&zz,ctx) && self.y == y.mul(&self.z.mul(&zz,ctx),ctx)
    }
}

impl F {
    fn one_raw() -> Self { Self { u: BigInt::one(), v: BigInt::zero() } }
}

fn main() {
    let args: Vec<String> = env::args().collect();
    assert!(args.len() == 4, "usage: eisenstein_pair_native fixture.json count solinas|division");
    let count: usize = args[2].parse().unwrap();
    assert!(args[3] == "solinas" || args[3] == "division");
    let ctx = Context::new(args[3] == "solinas");
    let data: Value = serde_json::from_slice(&fs::read(&args[1]).unwrap()).unwrap();
    let cases = data["cases"].as_array().unwrap();
    assert!(count > 0 && count <= cases.len());
    let g = Point::generator(&ctx);
    let gx = g.x.clone();
    assert_eq!(F::unpack33(&gx.pack33()), gx);
    assert_eq!(ctx.to_field(&gx.rotate(&ctx)), (&ctx.beta * hex(GX_HEX)) % &ctx.p);
    assert_eq!(gx.rotate(&ctx).rotate(&ctx).rotate(&ctx), gx);
    let started = Instant::now();
    let mut outputs = Vec::with_capacity(count);
    for case in cases.iter().take(count) {
        let scalar = BigUint::parse_bytes(case["scalar_hex"].as_str().unwrap().as_bytes(),16).unwrap();
        outputs.push(Point::multiply_binary(&g, &scalar, &ctx));
    }
    let online_ms = started.elapsed().as_secs_f64() * 1000.0;
    for (case, output) in cases.iter().take(count).zip(outputs.iter()) {
        let (x,y) = case["point_hex"].as_str().unwrap().split_once(':').unwrap();
        let expected_x = ctx.from_field(hex(x));
        let expected_y = ctx.from_field(hex(y));
        assert_eq!(F::unpack33(&expected_x.pack33()), expected_x);
        assert_eq!(F::unpack33(&expected_y.pack33()), expected_y);
        assert_eq!(ctx.to_field(&expected_x.rotate(&ctx)),
                   (&ctx.beta * hex(x)) % &ctx.p);
        assert!(output.matches_affine(&expected_x, &expected_y, &ctx));
    }
    println!("scheme=eisenstein_pair_bigint reducer={} count={count} online_ms={online_ms:.6} verified=1 packed_x_bytes=33",args[3]);
}
