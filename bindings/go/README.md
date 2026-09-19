# cryptanalysis (Go bindings)

Go bindings for libcryptanalysis, a toolkit of discrete-logarithm algorithms
over 64-bit prime-field groups: baby-step giant-step, Pollard rho, Pollard
kangaroo, Bernstein-Lange grumpy giants, Pohlig-Hellman, Cheon's attack on
strong Diffie-Hellman and index calculus in (Z/pZ)^*.

The package binds the flat C ABI in `include/cryptanalysis/ca_ffi.h`.

## Requirements

* Go 1.21 or newer with cgo enabled (`CGO_ENABLED=1`, the default on Linux
  and macOS when a C compiler is present).
* A C compiler supporting `-std=gnu11` and `__int128` (gcc or clang),
  pthreads and libm.

No prior cmake build is needed: the package compiles the C sources from the
repository's `src/` directory itself (the `src_*.c` wrapper files include
them one by one), so a plain `go build` / `go test` works from a checkout.

## Installation

```sh
go get github.com/aburan28/cryptanalysis/bindings/go
```

Because the package includes `../../src/*.c` and `../../include`, it must be
used from a full checkout of the repository (which is what `go get` fetches
into the module cache). To hack on it locally:

```sh
cd bindings/go
go build ./... && go vet ./... && go test ./...
```

## Example

```go
package main

import (
	"fmt"
	"log"

	cryptanalysis "github.com/aburan28/cryptanalysis/bindings/go"
)

func main() {
	// Prime-order subgroup of Z_p^* (p = 2*order + 1).
	g, err := cryptanalysis.NewZp(2000000579, 1000000289)
	if err != nil {
		log.Fatal(err)
	}
	defer g.Close()

	base, _ := g.FindGenerator(1)
	target, _ := g.Mul(base, 123456789)

	opts := cryptanalysis.DefaultOptions()
	opts.Seed = 7
	opts.Threads = 4 // Pollard rho workers
	x, stats, err := g.Dlog(base, target, &opts)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("x = %d after %d group operations in %.3fs\n",
		x, stats.GroupOps, stats.Seconds)

	// Elliptic curve y^2 = x^3 + x + 7 over F_1000003.
	n, _ := cryptanalysis.ECCountPoints(1000003, 1, 7)
	e, _ := cryptanalysis.NewEC(1000003, 1, 7, n)
	defer e.Close()
	P, _ := e.RandomElement(3)
	ord, _ := e.ElemOrder(P)
	e.SetOrder(ord, n/ord)
	Q, _ := e.Mul(P, 4242)
	k, _, _ := e.Kangaroo(P, Q, 4000, 5000, nil)
	fmt.Println("k =", k)

	// Index calculus in (Z/pZ)^*.
	y, _, err := cryptanalysis.ICSolve(1000003, 2, 424242, nil)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("log_2(424242) mod 1000003 =", y)
}
```

## API overview

| Go | C ABI |
|----|-------|
| `NewZp`, `NewEC`, `ECCountPoints`, `(*Group).Close` | `ca_ctx_new_zp`, `ca_ctx_new_ec`, `ca_ec_order`, `ca_ctx_free` |
| `Group.Kind/P/Order/Cofactor/CurveA/CurveB/SetOrder` | `ca_ctx_*` accessors |
| `Elem` (`[4]uint64`) and `Group.Op/Inv/Mul/Identity/IsIdentity/Equal/Validate/ElemOrder/FindGenerator/RandomElement/LiftX` | element functions |
| `Options`, `DefaultOptions`, `Solver`, `Stats` | `ca_ffi_options`, `ca_stats` |
| `Group.BSGS/Kangaroo/Grumpy/Rho/Dlog` | `ca_ffi_bsgs/kangaroo/grumpy/rho/dlog` |
| `Group.Cheon`, `Group.CheonInstance`, `CheonBestDivisor` | `ca_ffi_cheon*` |
| `ICParams`, `ICStats`, `ICSolve`, `ICContext` | `ca_ic_*` |
| `IsPrime`, `NextPrime`, `PrimitiveRoot`, `PowMod`, `InvMod`, `Factorize` | `ca_ffi_*` helpers |
| `Error`, `Status`, `ErrNotFound`, `ErrLimit`, ... | `ca_status`, `ca_last_error` |

Every failing call returns an `*Error` carrying the `ca_status` code and the
library's last-error message; `errors.Is(err, cryptanalysis.ErrNotFound)`
and friends work.

Element words follow the public form of the C ABI: for Z_p^* word 0 is the
residue; for a curve words 0 and 1 are the affine coordinates and word 2 is
1 for the point at infinity.

## Notes

* Groups and index-calculus contexts hold C memory. Call `Close` when done;
  a finalizer frees them eventually as a safety net.
* `Options.Threads` controls the number of pthreads Pollard rho uses inside
  the C library; the Go side stays single-threaded per call.
* Struct layouts are checked at package init against
  `ca_ffi_options_size()` and friends, so a mismatch between the headers
  and the compiled library panics early rather than corrupting memory.
