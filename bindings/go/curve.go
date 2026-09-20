package cryptanalysis

import "runtime"

// CurveEndo is the efficiently computable endomorphism a curve carries.
type CurveEndo int32

const (
	// EndoNone: only the order-2 negation map (a generic curve).
	EndoNone CurveEndo = 0
	// EndoJ0: j-invariant 0 (y^2 = x^3 + b), an order-6 automorphism group.
	EndoJ0 CurveEndo = 1
	// EndoJ1728: j-invariant 1728 (y^2 = x^3 + a x), an order-4 group.
	EndoJ1728 CurveEndo = 2
)

// String returns "none", "j0" or "j1728".
func (e CurveEndo) String() string {
	switch e {
	case EndoJ0:
		return "j0"
	case EndoJ1728:
		return "j1728"
	default:
		return "none"
	}
}

// CurveInfo describes a curve's endomorphism structure and the rho speed-up
// it gives.  Beta is 0 in the CurveInfo returned by CurveSolve; use
// CurveDetect for the field constant.
type CurveInfo struct {
	Endo       CurveEndo
	AutOrder   uint32  // automorphism group the rho walk folds by (2, 4 or 6)
	Beta       uint64  // cube root of unity (j0) or sqrt(-1) (j1728) mod p, or 0
	Lambda     uint64  // eigenvalue with psi(P) = Lambda*P (mod order), or 0
	RhoSpeedup float64 // sqrt(AutOrder): rho op-count factor vs a plain sqrt(n)
}

// CurveDetect reports the endomorphism structure of y^2 = x^3 + a x + b over
// F_p for the order-`order` subgroup (order 0 => geometric structure only).
func CurveDetect(p, a, b, order uint64) (CurveInfo, error) {
	return ffiCurveDetect(p, a, b, order)
}

// CurveByName looks up a named registry curve, returning p, a, b and the
// subgroup order.
func CurveByName(name string) (p, a, b, order uint64, err error) {
	return ffiCurveByName(name)
}

// CurveNames returns the names of the curves in the registry.
func CurveNames() []string {
	var out []string
	for i := 0; ; i++ {
		n := ffiCurveName(i)
		if n == "" {
			break
		}
		out = append(out, n)
	}
	return out
}

// CurveSolve solves base^x = target folding the Pollard rho walk by the
// curve's GLV endomorphism when it has one, else the negation-map rho.  The
// returned CurveInfo reports which path ran (Beta is 0; use CurveDetect).
// Elliptic-curve groups only.
func (g *Group) CurveSolve(base, target Elem, seed uint64) (uint64, CurveInfo, Stats, error) {
	defer runtime.KeepAlive(g)
	return ffiCurveSolve(g.handle(), base, target, seed)
}
