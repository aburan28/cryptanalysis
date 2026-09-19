package cryptanalysis

// Factor is one prime-power factor of an integer.
type Factor struct {
	P uint64 // prime
	E uint32 // exponent
}

// IsPrime reports whether n is prime (deterministic Miller-Rabin for
// 64-bit inputs).
func IsPrime(n uint64) bool { return isPrime(n) }

// NextPrime returns the smallest prime strictly greater than n.
func NextPrime(n uint64) uint64 { return nextPrime(n) }

// PrimitiveRoot returns the smallest primitive root modulo the prime p.
func PrimitiveRoot(p uint64) uint64 { return primitiveRoot(p) }

// PowMod returns b^e mod m.
func PowMod(b, e, m uint64) uint64 { return powMod(b, e, m) }

// InvMod returns the inverse of a modulo m (0 when it does not exist).
func InvMod(a, m uint64) uint64 { return invMod(a, m) }

// Factorize returns the prime factorisation of n in increasing order of
// primes (empty for n <= 1).
func Factorize(n uint64) []Factor { return factorize(n) }
