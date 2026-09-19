package cryptanalysis

import (
	"fmt"
	"runtime"
)

// Elem is a group element in the public (non-Montgomery) word form of the
// C ABI:
//
//	Z_p^*  : Elem{residue in [1, p), 0, 0, 0}
//	E(F_p) : Elem{x, y, 0, 0}, or Elem{0, 0, 1, 0} for the point at infinity
type Elem [4]uint64

// ZpElem builds the element of Z_p^* with the given residue.
func ZpElem(residue uint64) Elem { return Elem{residue} }

// ECPoint builds the affine curve point (x, y).
func ECPoint(x, y uint64) Elem { return Elem{x, y} }

// Residue returns word 0 (the residue of a Z_p^* element).
func (e Elem) Residue() uint64 { return e[0] }

// XY returns the affine coordinates of a curve point.
func (e Elem) XY() (x, y uint64) { return e[0], e[1] }

// IsInfinity reports whether e is the point at infinity of a curve.
func (e Elem) IsInfinity() bool { return e[2] == 1 }

// String formats the element as a residue or a point.
func (e Elem) String() string {
	if e.IsInfinity() {
		return "O"
	}
	if e[1] == 0 && e[3] == 0 {
		return fmt.Sprintf("%d", e[0])
	}
	return fmt.Sprintf("(%d, %d)", e[0], e[1])
}

// Kind identifies the type of group behind a [Group].
type Kind int

// Group kinds.
const (
	KindZp Kind = 1 // multiplicative group (Z/pZ)^*
	KindEC Kind = 2 // elliptic curve over F_p
)

// String returns "Zp", "EC" or a numeric fallback.
func (k Kind) String() string {
	switch k {
	case KindZp:
		return "Zp"
	case KindEC:
		return "EC"
	}
	return fmt.Sprintf("Kind(%d)", int(k))
}

// Group is a cyclic group (or a subgroup of one) over a 64-bit prime field.
// It wraps an opaque C context; call [Group.Close] when done.  A Group is
// safe for concurrent read-only use (all operations except SetOrder and
// Close).
type Group struct {
	h ctxHandle
}

// NewZp creates the subgroup of (Z/pZ)^* of the given order (order must
// divide p-1; pass p-1 for the whole group).  p must be an odd prime.
func NewZp(p, order uint64) (*Group, error) {
	h, err := ctxNewZp(p, order)
	if err != nil {
		return nil, err
	}
	return newGroup(h), nil
}

// NewEC creates the curve y^2 = x^3 + ax + b over F_p with the given group
// order (obtain it with [ECCountPoints]).  When the curve has a cofactor,
// call [Group.SetOrder] with the prime subgroup order after choosing a
// base point.
func NewEC(p, a, b, order uint64) (*Group, error) {
	h, err := ctxNewEC(p, a, b, order)
	if err != nil {
		return nil, err
	}
	return newGroup(h), nil
}

// ECCountPoints returns #E(F_p) for y^2 = x^3 + ax + b.
func ECCountPoints(p, a, b uint64) (uint64, error) { return ecOrder(p, a, b) }

func newGroup(h ctxHandle) *Group {
	g := &Group{h: h}
	runtime.SetFinalizer(g, (*Group).Close)
	return g
}

// Close frees the underlying C context.  It is safe to call more than once;
// any other use of the group after Close panics.
func (g *Group) Close() {
	if g.h != nil {
		ctxFree(g.h)
		g.h = nil
		runtime.SetFinalizer(g, nil)
	}
}

func (g *Group) handle() ctxHandle {
	if g.h == nil {
		panic(ErrClosed)
	}
	return g.h
}

// Kind returns the kind of the group.
func (g *Group) Kind() Kind { defer runtime.KeepAlive(g); return ctxKind(g.handle()) }

// P returns the field prime.
func (g *Group) P() uint64 { defer runtime.KeepAlive(g); return ctxP(g.handle()) }

// Order returns the (sub)group order the context works with.
func (g *Group) Order() uint64 { defer runtime.KeepAlive(g); return ctxOrder(g.handle()) }

// Cofactor returns the cofactor set with SetOrder (1 by default).
func (g *Group) Cofactor() uint64 { defer runtime.KeepAlive(g); return ctxCofactor(g.handle()) }

// CurveA returns the curve coefficient a (0 for Z_p^*).
func (g *Group) CurveA() uint64 { defer runtime.KeepAlive(g); return ctxCurveA(g.handle()) }

// CurveB returns the curve coefficient b (0 for Z_p^*).
func (g *Group) CurveB() uint64 { defer runtime.KeepAlive(g); return ctxCurveB(g.handle()) }

// SetOrder changes the subgroup order and cofactor used by the solvers,
// typically after determining the order of a chosen base point with
// [Group.ElemOrder].
func (g *Group) SetOrder(order, cofactor uint64) {
	defer runtime.KeepAlive(g)
	ctxSetOrder(g.handle(), order, cofactor)
}

// Validate reports whether e is a valid element of the group (a residue
// in [1, p), or a point on the curve).
func (g *Group) Validate(e Elem) bool { defer runtime.KeepAlive(g); return ctxValidate(g.handle(), e) }

// Identity returns the neutral element.
func (g *Group) Identity() Elem { defer runtime.KeepAlive(g); return ctxIdentity(g.handle()) }

// IsIdentity reports whether e is the neutral element.
func (g *Group) IsIdentity(e Elem) bool {
	defer runtime.KeepAlive(g)
	return ctxIsIdentity(g.handle(), e)
}

// Equal reports whether a and b are the same (valid) element.
func (g *Group) Equal(a, b Elem) bool { defer runtime.KeepAlive(g); return ctxEqual(g.handle(), a, b) }

// Op returns a*b (multiplication in Z_p^*, point addition on a curve).
func (g *Group) Op(a, b Elem) (Elem, error) {
	defer runtime.KeepAlive(g)
	return ctxOp(g.handle(), a, b)
}

// Inv returns the inverse of a.
func (g *Group) Inv(a Elem) (Elem, error) { defer runtime.KeepAlive(g); return ctxInv(g.handle(), a) }

// Mul returns a^k (scalar multiplication [k]a on a curve).
func (g *Group) Mul(a Elem, k uint64) (Elem, error) {
	defer runtime.KeepAlive(g)
	return ctxMul(g.handle(), a, k)
}

// ElemOrder returns the order of a.
func (g *Group) ElemOrder(a Elem) (uint64, error) {
	defer runtime.KeepAlive(g)
	return ctxElemOrder(g.handle(), a)
}

// FindGenerator returns a generator of the subgroup; seed selects the
// deterministic search start (0 means random).
func (g *Group) FindGenerator(seed uint64) (Elem, error) {
	defer runtime.KeepAlive(g)
	return ctxFindGenerator(g.handle(), seed)
}

// RandomElement returns a pseudo-random element of the subgroup (the
// cofactor is applied when it is greater than one); seed 0 means random.
func (g *Group) RandomElement(seed uint64) (Elem, error) {
	defer runtime.KeepAlive(g)
	return ctxRandomElement(g.handle(), seed)
}

// LiftX returns a curve point with the given x coordinate (either of the
// two square roots), or ErrNotFound when x is not on the curve.  Curves
// only; Z_p^* groups return ErrUnsupported.
func (g *Group) LiftX(x uint64) (Elem, error) {
	defer runtime.KeepAlive(g)
	return ctxLiftX(g.handle(), x)
}
