package cryptanalysis

import (
	"errors"
	"testing"
)

// Instances shared with tests/test_ffi.c.
const (
	zpP     = 2000000579
	zpOrder = 1000000289
	zpX     = 123456789

	ecP = 1000003
	ecA = 1
	ecB = 7

	icP = 1000003
)

func TestLayout(t *testing.T) {
	for i, s := range layoutSizes() {
		if s[0] != s[1] {
			t.Fatalf("struct %d: cgo sizeof %d != library sizeof %d", i, s[0], s[1])
		}
	}
	if Version() != "0.1.0" {
		t.Fatalf("Version() = %q", Version())
	}
}

func newZpFixture(t *testing.T) (*Group, Elem, Elem) {
	t.Helper()
	z, err := NewZp(zpP, zpOrder)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(z.Close)
	g, err := z.FindGenerator(1)
	if err != nil {
		t.Fatal(err)
	}
	h, err := z.Mul(g, zpX)
	if err != nil {
		t.Fatal(err)
	}
	return z, g, h
}

func TestZpGroup(t *testing.T) {
	z, g, _ := newZpFixture(t)
	if z.Kind() != KindZp || z.P() != zpP || z.Order() != zpOrder || z.Cofactor() != 2 {
		t.Fatalf("kind/p/order/cofactor = %v/%d/%d/%d", z.Kind(), z.P(), z.Order(), z.Cofactor())
	}
	if !z.Validate(g) {
		t.Fatal("generator should validate")
	}
	if z.Validate(Elem{}) {
		t.Fatal("zero must not validate")
	}
	if _, err := NewZp(1000, 0); err == nil {
		t.Fatal("NewZp(1000, 0) should fail")
	} else if !errors.Is(err, ErrInvalid) {
		t.Fatalf("NewZp(1000, 0) error = %v, want ErrInvalid", err)
	}

	// element ops
	sq, err := z.Op(g, g)
	if err != nil {
		t.Fatal(err)
	}
	g2, err := z.Mul(g, 2)
	if err != nil {
		t.Fatal(err)
	}
	if !z.Equal(sq, g2) {
		t.Fatalf("g*g = %v, g^2 = %v", sq, g2)
	}
	inv, err := z.Inv(g)
	if err != nil {
		t.Fatal(err)
	}
	one, err := z.Op(inv, g)
	if err != nil {
		t.Fatal(err)
	}
	if !z.IsIdentity(one) || !z.Equal(one, z.Identity()) {
		t.Fatalf("g^-1 * g = %v, want identity %v", one, z.Identity())
	}
	ord, err := z.ElemOrder(g)
	if err != nil {
		t.Fatal(err)
	}
	if ord != zpOrder {
		t.Fatalf("ElemOrder = %d, want %d", ord, zpOrder)
	}
	if _, err := z.Op(Elem{}, g); err == nil {
		t.Fatal("Op with invalid element should fail")
	} else if !errors.Is(err, ErrInvalid) {
		t.Fatalf("got %v, want ErrInvalid", err)
	}
	if _, err := z.LiftX(1); !errors.Is(err, ErrUnsupported) {
		t.Fatalf("LiftX on Z_p^*: %v, want ErrUnsupported", err)
	}
	r, err := z.RandomElement(5)
	if err != nil || !z.Validate(r) {
		t.Fatalf("RandomElement = %v, %v", r, err)
	}
}

func TestSolversZp(t *testing.T) {
	z, g, h := newZpFixture(t)
	o := DefaultOptions()
	o.Seed = 7

	x, st, err := z.BSGS(g, h, 0, 0, &o)
	if err != nil || x != zpX {
		t.Fatalf("BSGS = %d, %v", x, err)
	}
	if st.GroupOps == 0 {
		t.Fatal("BSGS stats: group_ops should be > 0")
	}
	if x, _, err = z.Rho(g, h, &o); err != nil || x != zpX {
		t.Fatalf("Rho = %d, %v", x, err)
	}
	if x, _, err = z.Kangaroo(g, h, 123000000, 124000000, &o); err != nil || x != zpX {
		t.Fatalf("Kangaroo = %d, %v", x, err)
	}
	if x, _, err = z.Grumpy(g, h, 123000000, 124000000, &o); err != nil || x != zpX {
		t.Fatalf("Grumpy = %d, %v", x, err)
	}
	if x, _, err = z.Dlog(g, h, &o); err != nil || x != zpX {
		t.Fatalf("Dlog(auto) = %d, %v", x, err)
	}
	o.Solver = SolverGrumpy
	if x, _, err = z.Dlog(g, h, &o); err != nil || x != zpX {
		t.Fatalf("Dlog(grumpy) = %d, %v", x, err)
	}
	// nil options mean defaults
	if x, _, err = z.Dlog(g, h, nil); err != nil || x != zpX {
		t.Fatalf("Dlog(nil) = %d, %v", x, err)
	}
	// Precomputation: defaults (dpBits=-1, auto table/coverage), threaded build.
	x, pst, err := z.Precomp(g, h, -1, 0, 0, 4, 7)
	if err != nil || x != zpX {
		t.Fatalf("Precomp = %d, %v", x, err)
	}
	if pst.GroupOps == 0 {
		t.Fatal("Precomp stats: group_ops should be > 0")
	}
}

func TestSolverErrors(t *testing.T) {
	z, g, h := newZpFixture(t)
	// The exponent is outside this interval: exhaustive BSGS reports NotFound.
	_, _, err := z.BSGS(g, h, 1, 1000, nil)
	if !errors.Is(err, ErrNotFound) {
		t.Fatalf("BSGS outside interval: %v, want ErrNotFound", err)
	}
	var e *Error
	if !errors.As(err, &e) || e.Status != StatusNotFound {
		t.Fatalf("error should be *Error with StatusNotFound, got %#v", err)
	}
	// A tiny work bound triggers ErrLimit.
	o := DefaultOptions()
	o.Seed = 7
	o.MaxOps = 10
	if _, _, err := z.Rho(g, h, &o); !errors.Is(err, ErrLimit) {
		t.Fatalf("Rho with MaxOps=10: %v, want ErrLimit", err)
	}
}

func TestCheon(t *testing.T) {
	z, g, _ := newZpFixture(t)
	d, cost := CheonBestDivisor(zpOrder)
	if d <= 1 || cost <= 0 {
		t.Fatalf("CheonBestDivisor = %d, %g", d, cost)
	}
	const alpha = 987654321
	ga, gad, err := z.CheonInstance(g, alpha, d)
	if err != nil {
		t.Fatal(err)
	}
	got, st, err := z.Cheon(g, ga, gad, d, 0)
	if err != nil || got != alpha {
		t.Fatalf("Cheon = %d, %v (stats %+v)", got, err, st)
	}
}

func TestEC(t *testing.T) {
	n, err := ECCountPoints(ecP, ecA, ecB)
	if err != nil {
		t.Fatal(err)
	}
	e, err := NewEC(ecP, ecA, ecB, n)
	if err != nil {
		t.Fatal(err)
	}
	defer e.Close()
	if _, err := NewEC(97, 0, 0, 0); err == nil {
		t.Fatal("singular curve should be rejected")
	}
	if e.Kind() != KindEC || e.CurveA() != ecA || e.CurveB() != ecB {
		t.Fatalf("kind/a/b = %v/%d/%d", e.Kind(), e.CurveA(), e.CurveB())
	}
	P, err := e.RandomElement(3)
	if err != nil {
		t.Fatal(err)
	}
	if P.IsInfinity() || !e.Validate(P) {
		t.Fatalf("random point %v invalid", P)
	}
	if e.Validate(Elem{P[0], P[1] ^ 1}) {
		t.Fatal("off-curve point must not validate")
	}
	ord, err := e.ElemOrder(P)
	if err != nil {
		t.Fatal(err)
	}
	e.SetOrder(ord, n/ord)
	if e.Order() != ord || e.Cofactor() != n/ord {
		t.Fatalf("SetOrder not applied: %d/%d", e.Order(), e.Cofactor())
	}
	Q, err := e.Mul(P, 4242)
	if err != nil {
		t.Fatal(err)
	}
	x, _, err := e.Dlog(P, Q, nil)
	if err != nil || x != 4242%ord {
		t.Fatalf("EC Dlog = %d, %v; want %d", x, err, 4242%ord)
	}
	inf := e.Identity()
	if !inf.IsInfinity() || !e.IsIdentity(inf) {
		t.Fatalf("identity = %v", inf)
	}
	L, err := e.LiftX(P[0])
	if err != nil {
		t.Fatal(err)
	}
	if L[0] != P[0] || (L[1] != P[1] && L[1] != ecP-P[1]) {
		t.Fatalf("LiftX(%d) = %v, want +-%v", P[0], L, P)
	}
	// Interval solvers on the curve as well.
	o := DefaultOptions()
	o.Seed = 11
	if x, _, err := e.Kangaroo(P, Q, 4000, 5000, &o); err != nil || x != 4242 {
		t.Fatalf("EC Kangaroo = %d, %v", x, err)
	}
}

func TestIndexCalculus(t *testing.T) {
	ip := DefaultICParams()
	ip.Seed = 3
	x, st, err := ICSolve(icP, 2, 424242, &ip)
	if err != nil {
		t.Fatal(err)
	}
	if PowMod(2, x, icP) != 424242 {
		t.Fatalf("ICSolve: 2^%d != 424242 mod %d", x, icP)
	}
	if st.FactorBaseSize == 0 || st.Relations == 0 {
		t.Fatalf("ICSolve stats look empty: %+v", st)
	}

	c, err := NewICContext(icP, 2, &ip)
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	if c.Modulus() != icP || c.FactorBaseSize() == 0 || c.PrimitiveRoot() != 2 {
		t.Fatalf("ctx modulus/fbsize/root = %d/%d/%d", c.Modulus(), c.FactorBaseSize(), c.PrimitiveRoot())
	}
	if c.Stats().FactorBaseSize != c.FactorBaseSize() {
		t.Fatalf("Stats().FactorBaseSize = %d, want %d", c.Stats().FactorBaseSize, c.FactorBaseSize())
	}
	for _, h := range []uint64{424242, 3, 999999, 65537} {
		x, _, err := c.Log(h)
		if err != nil {
			t.Fatalf("Log(%d): %v", h, err)
		}
		if PowMod(2, x, icP) != h {
			t.Fatalf("Log(%d) = %d is wrong", h, x)
		}
	}
	prime, lg, known := c.FactorBaseLog(0)
	if prime != 2 || !known || PowMod(c.PrimitiveRoot(), lg, icP) != 2 {
		t.Fatalf("FactorBaseLog(0) = %d, %d, %v", prime, lg, known)
	}
	if _, err := NewICContext(1000, 2, nil); !errors.Is(err, ErrInvalid) {
		t.Fatalf("NewICContext(1000): %v, want ErrInvalid", err)
	}
	if b, cr := ICAutoParams(20); b == 0 || cr == 0 {
		t.Fatalf("ICAutoParams(20) = %d, %d", b, cr)
	}
}

func TestNumberTheory(t *testing.T) {
	if !IsPrime(1000003) || IsPrime(1000001) {
		t.Fatal("IsPrime")
	}
	if NextPrime(1000003) != 1000033 {
		t.Fatalf("NextPrime = %d", NextPrime(1000003))
	}
	if PrimitiveRoot(1000003) != 2 {
		t.Fatalf("PrimitiveRoot = %d", PrimitiveRoot(1000003))
	}
	if inv := InvMod(3, 1000003); inv*3%1000003 != 1 {
		t.Fatalf("InvMod = %d", inv)
	}
	if PowMod(2, 10, 1000) != 24 {
		t.Fatalf("PowMod = %d", PowMod(2, 10, 1000))
	}
	f := Factorize(1000002)
	want := []Factor{{2, 1}, {3, 1}, {166667, 1}}
	if len(f) != len(want) {
		t.Fatalf("Factorize = %v", f)
	}
	for i := range want {
		if f[i] != want[i] {
			t.Fatalf("Factorize = %v, want %v", f, want)
		}
	}
	if f := Factorize(1 << 20); len(f) != 1 || f[0] != (Factor{2, 20}) {
		t.Fatalf("Factorize(2^20) = %v", f)
	}
	if len(Factorize(1)) != 0 {
		t.Fatal("Factorize(1) should be empty")
	}
}

func TestOptionsRoundTrip(t *testing.T) {
	o := DefaultOptions()
	if o.Threads != 1 || o.RhoDPBits != -1 || !o.RhoNegationMap || o.KangarooDPBits != -1 ||
		o.GrumpyAlpha != 0.7 || o.Solver != SolverAuto {
		t.Fatalf("DefaultOptions = %+v", o)
	}
	if p := DefaultICParams(); p.Method != ICLinearSieve || p.Threads != 1 {
		t.Fatalf("DefaultICParams = %+v", p)
	}
	for _, s := range []Status{StatusOK, StatusInvalid, StatusNotFound, StatusLimit} {
		if s.String() == "" || s.String() == "unknown" {
			t.Fatalf("Status(%d).String() = %q", int(s), s.String())
		}
	}
	if (&Error{Status: StatusNotFound}).Error() != "cryptanalysis: not found" {
		t.Fatalf("Error() = %q", (&Error{Status: StatusNotFound}).Error())
	}
}

func TestClose(t *testing.T) {
	z, err := NewZp(zpP, zpOrder)
	if err != nil {
		t.Fatal(err)
	}
	z.Close()
	z.Close() // idempotent
	defer func() {
		r := recover()
		if err, ok := r.(error); !ok || !errors.Is(err, ErrClosed) {
			t.Fatalf("use after Close: recovered %v, want ErrClosed", r)
		}
	}()
	z.Order()
}
