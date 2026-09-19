// Package cryptanalysis provides Go bindings for libcryptanalysis, a toolkit
// of discrete-logarithm algorithms over 64-bit prime-field groups: the
// multiplicative group (Z/pZ)^* and elliptic curves y^2 = x^3 + ax + b over
// F_p.
//
// The package is built with cgo and compiles the C library from the
// repository's src/ directory itself, so a plain "go build" or "go test"
// works without a prior cmake build.  A C compiler (gcc or clang) and
// CGO_ENABLED=1 are required.
//
// # Groups and elements
//
// A [Group] is created with [NewZp] or [NewEC] and freed with
// [Group.Close] (a finalizer frees it eventually if you forget).  Group
// elements are plain [Elem] values, four uint64 words in the public
// representation of the C ABI: for Z_p^* word 0 holds the residue; for a
// curve words 0 and 1 hold the affine x and y and word 2 is 1 for the
// point at infinity.
//
// # Solvers
//
// [Group.BSGS], [Group.Kangaroo] and [Group.Grumpy] solve base^x = target
// for x in an interval [lo, hi] (lo == hi == 0 means the whole group).
// [Group.Rho] works on the whole group and [Group.Dlog] runs
// Pohlig-Hellman on top of a chosen solver.  All of them take an optional
// [*Options] (nil means library defaults) and return the exponent, work
// [Stats] and an error which is an [*Error] carrying the C status code;
// errors.Is(err, ErrNotFound) and errors.Is(err, ErrLimit) work.
//
// [Group.Cheon] implements Cheon's attack on the strong Diffie-Hellman
// problem and [ICSolve] / [ICContext] index calculus in (Z/pZ)^*.
//
// # Number theory helpers
//
// [IsPrime], [NextPrime], [PrimitiveRoot], [PowMod], [InvMod] and
// [Factorize] expose the library's 64-bit arithmetic helpers.
package cryptanalysis
