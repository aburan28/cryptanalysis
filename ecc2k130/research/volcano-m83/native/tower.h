// Arithmetic in F_(2^(m r)) = F_(2^m)[Y]/(g(Y)), gcd(m, r) = 1, for the
// explicit conductor-prime isogeny computations of the m=83 volcano study.
//
// F_(2^m) = F_2[z]/(f(z)), m <= 120, f a trinomial or pentanomial; elements
// are unsigned __int128 with bit i the coefficient of z^i.  g(Y) is a sparse
// irreducible over F_2 of degree r, hence irreducible over F_(2^m).  A tower
// element is r base-field coefficients (coefficient i multiplies Y^i).
//
// Multiplication packs both operands by Kronecker substitution into slots of
// 2m-1 bits, multiplies the resulting F_2[x] polynomials
// with a PMULL Karatsuba, and reduces each slot mod f and the result mod g.
#pragma once

#include <stddef.h>
#include <stdint.h>

typedef unsigned __int128 u128;
typedef uint64_t u64;

typedef struct {
    int m;
    int ftaps[4]; // f = z^m + sum z^ftaps[i] + 1  (0 terminated list)
    int nftaps;
    u128 mask;   // 2^m - 1
    u128 trmask; // bit i = Tr_{2^m/2}(z^i)
    int r;
    int gtaps[4]; // g = Y^r + sum Y^gtaps[i] + 1
    int ngtaps;
    uint8_t *ytrace; // ytrace[i] = Tr_{2^r/2}(Y^i), i < r
    int S;           // words per Kronecker slot
    int W;           // words per packed input coefficient
    int slot;        // Kronecker slot width in bits, 2m - 1
    size_t nwords;   // packed operand words
    int threads;     // >= 2: top Karatsuba level on three threads
    u64 *tsa, *tscratch;
    u64 *pa, *pb, *pc, *scratch;
    u128 *wide; // 2r-1 unreduced coefficients
} tower;

// base field F_(2^m)
u128 fm_mul(const tower *T, u128 a, u128 b);
u128 fm_sqr(const tower *T, u128 a);
u128 fm_inv(const tower *T, u128 a);
int fm_trace(const tower *T, u128 a);

// tower F_(2^(m r)); elements are arrays of r u128
int tower_init(tower *T, int m, const int *ftaps, int nftaps, int r, const int *gtaps, int ngtaps);
void tower_free(tower *T);
u128 *tw_alloc(const tower *T);
void tw_copy(const tower *T, u128 *c, const u128 *a);
void tw_zero(const tower *T, u128 *c);
void tw_one(const tower *T, u128 *c);
int tw_is_zero(const tower *T, const u128 *a);
int tw_equal(const tower *T, const u128 *a, const u128 *b);
void tw_add(const tower *T, u128 *c, const u128 *a, const u128 *b);
void tw_mul(tower *T, u128 *c, const u128 *a, const u128 *b);  // c may alias a or b
void tw_sqr(tower *T, u128 *c, const u128 *a);                 // c may alias a
void tw_scale(const tower *T, u128 *c, const u128 *a, u128 s); // c = s a, s in F_(2^m)
void tw_inv(tower *T, u128 *c, const u128 *a);
void tw_frob_q(tower *T, u128 *c, const u128 *a); // a^(2^m)
int tw_trace2(const tower *T, const u128 *a);     // Tr to F_2
u128 tw_trace_q(const tower *T, const u128 *a);   // Tr to F_(2^m)

// carryless Karatsuba (exposed for tests): c[2n] = a[n] * b[n]
void clmul(u64 *c, const u64 *a, const u64 *b, size_t n, u64 *scratch);
size_t clmul_scratch_words(size_t n);
