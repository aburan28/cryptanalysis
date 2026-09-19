// Package dlog is the control plane's own arithmetic: enough of the C
// library's group layer to verify a distinguished point and to turn a
// collision into a discrete logarithm.
//
// Why a second implementation rather than cgo or a subprocess:
//
//   - The control plane must verify every point an agent submits, and it
//     must do it on the request path.  Forking `ca` per upload is a process
//     per few hundred points; linking the C library with cgo makes the
//     control plane's build depend on a C toolchain, which is exactly the
//     dependency that makes a container image hard to rebuild in a hurry.
//   - Two independent implementations that must agree is a stronger test
//     than one implementation tested against itself.  The suite runs the C
//     `ca dist-walk` and checks that this package verifies every point it
//     produced, and that both agree on the discrete logarithm.
//
// The C library is the reference.  Where this file looks strange -- the
// Montgomery conversion inside the hash, in particular -- it is because the
// value being reproduced is what the C code hashes, and a hash that differs
// by so much as a constant would make every point look undistinguished.
package dlog

import (
	"errors"
	"fmt"
	"math/big"
	"math/bits"
	"strconv"
	"strings"
)

// Kind selects a concrete group.
type Kind string

const (
	Zp Kind = "zp"
	EC Kind = "ec"
)

// Group is a subgroup of (Z/pZ)^* or of E(F_p) over a 64-bit prime.
type Group struct {
	Kind  Kind
	P     uint64
	A, B  uint64 // curve coefficients
	Order uint64 // n

	rModP uint64 // 2^64 mod p, the Montgomery form of 1
}

// Point is an element: X for Z_p^*, (X, Y) for a curve, Inf for the
// identity of a curve group.
type Point struct {
	X, Y uint64
	Inf  bool
}

// NewGroup validates the parameters and precomputes what the hash needs.
func NewGroup(kind Kind, p, a, b, order uint64) (*Group, error) {
	if p < 5 || p%2 == 0 {
		return nil, errors.New("p must be an odd prime greater than 3")
	}
	if order < 2 {
		return nil, errors.New("the subgroup order must be known")
	}
	switch kind {
	case Zp, EC:
	default:
		return nil, fmt.Errorf("unknown group kind %q", kind)
	}
	g := &Group{Kind: kind, P: p, A: a % p, B: b % p, Order: order}
	// 2^64 mod p, computed without 128-bit arithmetic: 2^64 - 1 reduced,
	// plus one, reduced again.
	g.rModP = (^uint64(0)%p + 1) % p
	if kind == EC {
		// 4a^3 + 27b^2 != 0, the same non-singularity check the library makes.
		a3 := mulMod(mulMod(g.A, g.A, p), g.A, p)
		disc := addMod(mulMod(4, a3, p), mulMod(27, mulMod(g.B, g.B, p), p), p)
		if disc == 0 {
			return nil, errors.New("singular curve: 4a^3 + 27b^2 == 0")
		}
	}
	return g, nil
}

// ---- modular arithmetic ---------------------------------------------------

func addMod(a, b, m uint64) uint64 {
	s := a + b
	if s < a || s >= m { // wrapped, or simply too big
		s -= m
	}
	return s
}

func subMod(a, b, m uint64) uint64 {
	if a >= b {
		return a - b
	}
	return a + (m - b)
}

// mulMod is exact for every modulus up to 2^64-1: the 128-bit product's high
// word is below m whenever both operands are, which is precisely the
// condition bits.Div64 needs in order not to panic.
func mulMod(a, b, m uint64) uint64 {
	a %= m
	b %= m
	hi, lo := bits.Mul64(a, b)
	_, rem := bits.Div64(hi, lo, m)
	return rem
}

func powMod(a, e, m uint64) uint64 {
	r := uint64(1) % m
	a %= m
	for e > 0 {
		if e&1 == 1 {
			r = mulMod(r, a, m)
		}
		a = mulMod(a, a, m)
		e >>= 1
	}
	return r
}

// invMod returns a^-1 mod m, or 0 when the inverse does not exist.  big.Int
// rather than a hand-rolled extended Euclid: it is called once per collision
// and per field inversion, never in a hot loop, and this way there is no
// signed-overflow corner to get wrong.
func invMod(a, m uint64) uint64 {
	if m == 0 {
		return 0
	}
	x := new(big.Int).SetUint64(a % m)
	n := new(big.Int).SetUint64(m)
	if x.Sign() == 0 {
		return 0
	}
	inv := new(big.Int).ModInverse(x, n)
	if inv == nil {
		return 0
	}
	return inv.Uint64()
}

func gcd(a, b uint64) uint64 {
	for b != 0 {
		a, b = b, a%b
	}
	return a
}

// ---- the library's hash ---------------------------------------------------

// mix64 is ca_mix64: the finaliser the C library hashes elements with.
func mix64(x uint64) uint64 {
	x ^= x >> 33
	x *= 0xff51afd7ed558ccd
	x ^= x >> 33
	x *= 0xc4ceb9fe1a85ec53
	x ^= x >> 33
	return x
}

// montTo converts to the internal Montgomery representation, a*2^64 mod p.
//
// The element hash in the C library runs over the *stored* words, which are
// in Montgomery form, so a hash computed from the canonical coordinates
// would be a different function and every point would fail the
// distinguished-point test.  This is the one place where the control plane
// has to know a representation detail of the library.
func (g *Group) montTo(a uint64) uint64 { return mulMod(a%g.P, g.rModP, g.P) }

// Hash reproduces ca_group_hash for this group.
func (g *Group) Hash(pt Point) uint64 {
	if g.Kind == Zp {
		return mix64(g.montTo(pt.X) ^ 0x5bd1e995)
	}
	if pt.Inf {
		return 0x9e3779b97f4a7c15
	}
	return mix64(g.montTo(pt.X)*0x9E3779B97F4A7C15 ^ mix64(g.montTo(pt.Y)))
}

// ---- group operations -----------------------------------------------------

// Identity is 1 in Z_p^*, the point at infinity on a curve.
func (g *Group) Identity() Point {
	if g.Kind == Zp {
		return Point{X: 1 % g.P}
	}
	return Point{Inf: true}
}

func (g *Group) IsIdentity(pt Point) bool {
	if g.Kind == Zp {
		return pt.X == 1%g.P
	}
	return pt.Inf
}

func (g *Group) Equal(a, b Point) bool {
	if g.Kind == Zp {
		return a.X == b.X
	}
	if a.Inf || b.Inf {
		return a.Inf && b.Inf
	}
	return a.X == b.X && a.Y == b.Y
}

// Valid reports whether the point is really in the group's ambient set: a
// nonzero residue, or a point on the curve.  It is the first thing checked
// about anything an agent sends.
func (g *Group) Valid(pt Point) bool {
	if g.Kind == Zp {
		return pt.X != 0 && pt.X < g.P
	}
	if pt.Inf {
		return true
	}
	if pt.X >= g.P || pt.Y >= g.P {
		return false
	}
	// y^2 == x^3 + a x + b
	lhs := mulMod(pt.Y, pt.Y, g.P)
	rhs := addMod(mulMod(mulMod(pt.X, pt.X, g.P), pt.X, g.P),
		addMod(mulMod(g.A, pt.X, g.P), g.B, g.P), g.P)
	return lhs == rhs
}

// Add is the group operation: multiplication mod p, or the chord-and-tangent
// addition on the curve.
func (g *Group) Add(a, b Point) Point {
	if g.Kind == Zp {
		return Point{X: mulMod(a.X, b.X, g.P)}
	}
	if a.Inf {
		return b
	}
	if b.Inf {
		return a
	}
	p := g.P
	var lambda uint64
	if a.X == b.X {
		if a.Y != b.Y || a.Y == 0 {
			return Point{Inf: true} // P + (-P)
		}
		// tangent: (3x^2 + a) / 2y
		num := addMod(mulMod(3, mulMod(a.X, a.X, p), p), g.A, p)
		den := invMod(mulMod(2, a.Y, p), p)
		if den == 0 {
			return Point{Inf: true}
		}
		lambda = mulMod(num, den, p)
	} else {
		den := invMod(subMod(b.X, a.X, p), p)
		if den == 0 {
			return Point{Inf: true}
		}
		lambda = mulMod(subMod(b.Y, a.Y, p), den, p)
	}
	x := subMod(subMod(mulMod(lambda, lambda, p), a.X, p), b.X, p)
	y := subMod(mulMod(lambda, subMod(a.X, x, p), p), a.Y, p)
	return Point{X: x, Y: y}
}

// ScalarMul is k*P (additive) or P^k (multiplicative), by double-and-add.
func (g *Group) ScalarMul(pt Point, k uint64) Point {
	r := g.Identity()
	acc := pt
	for k > 0 {
		if k&1 == 1 {
			r = g.Add(r, acc)
		}
		acc = g.Add(acc, acc)
		k >>= 1
	}
	return r
}

// ---- element syntax -------------------------------------------------------

// ParsePoint accepts the library CLI's spelling: "123" for Z_p^*, "x,y" or
// "inf" for a curve.  Keeping one syntax means a campaign's base and target
// can be pasted straight into a `ca` command line.
func (g *Group) ParsePoint(s string) (Point, error) {
	s = strings.TrimSpace(s)
	if g.Kind == Zp {
		x, err := strconv.ParseUint(s, 0, 64)
		if err != nil {
			return Point{}, fmt.Errorf("bad Z_p element %q: %w", s, err)
		}
		pt := Point{X: x % g.P}
		if !g.Valid(pt) {
			return Point{}, fmt.Errorf("%q is not a unit mod p", s)
		}
		return pt, nil
	}
	if s == "inf" || s == "O" {
		return Point{Inf: true}, nil
	}
	parts := strings.SplitN(s, ",", 2)
	if len(parts) != 2 {
		return Point{}, fmt.Errorf("curve element %q is not x,y or inf", s)
	}
	x, err := strconv.ParseUint(strings.TrimSpace(parts[0]), 0, 64)
	if err != nil {
		return Point{}, fmt.Errorf("bad x in %q: %w", s, err)
	}
	y, err := strconv.ParseUint(strings.TrimSpace(parts[1]), 0, 64)
	if err != nil {
		return Point{}, fmt.Errorf("bad y in %q: %w", s, err)
	}
	pt := Point{X: x, Y: y}
	if !g.Valid(pt) {
		return Point{}, fmt.Errorf("%q is not on the curve", s)
	}
	return pt, nil
}

// String formats a point in the same syntax.
func (g *Group) String(pt Point) string {
	if g.Kind == Zp {
		return strconv.FormatUint(pt.X, 10)
	}
	if pt.Inf {
		return "inf"
	}
	return strconv.FormatUint(pt.X, 10) + "," + strconv.FormatUint(pt.Y, 10)
}
