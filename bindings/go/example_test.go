package cryptanalysis_test

import (
	"fmt"
	"log"

	cryptanalysis "github.com/aburan28/cryptanalysis/bindings/go"
)

// Solve a discrete logarithm in a prime-order subgroup of Z_p^* with
// Pohlig-Hellman + the automatically chosen solver, then check the answer.
func Example() {
	const p, order = 2000000579, 1000000289 // p = 2*order + 1
	g, err := cryptanalysis.NewZp(p, order)
	if err != nil {
		log.Fatal(err)
	}
	defer g.Close()

	base, _ := g.FindGenerator(1)
	target, _ := g.Mul(base, 123456789)

	opts := cryptanalysis.DefaultOptions()
	opts.Seed = 7
	x, _, err := g.Dlog(base, target, &opts)
	if err != nil {
		log.Fatal(err)
	}
	check, _ := g.Mul(base, x)
	fmt.Println(x, g.Equal(check, target))
	// Output: 123456789 true
}

// Interval search on an elliptic curve with Pollard's kangaroo method.
func ExampleGroup_Kangaroo() {
	const p, a, b = 1000003, 1, 7
	n, _ := cryptanalysis.ECCountPoints(p, a, b)
	e, err := cryptanalysis.NewEC(p, a, b, n)
	if err != nil {
		log.Fatal(err)
	}
	defer e.Close()

	P, _ := e.RandomElement(3)
	Q, _ := e.Mul(P, 4242)
	x, _, err := e.Kangaroo(P, Q, 4000, 5000, nil)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(x)
	// Output: 4242
}

// Index calculus in (Z/pZ)^* with a reusable precomputation.
func ExampleICContext() {
	params := cryptanalysis.DefaultICParams()
	params.Seed = 3
	ctx, err := cryptanalysis.NewICContext(1000003, 2, &params)
	if err != nil {
		log.Fatal(err)
	}
	defer ctx.Close()

	x, _, err := ctx.Log(424242)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(cryptanalysis.PowMod(2, x, 1000003))
	// Output: 424242
}
