"""Replace per-update polynomial squaring while preserving its exact map."""


def patch(source, native=0):
    assert native in (0, 1, 2, 3, 4)
    start = source.index('ECC_HD P131 squarePolynomial131(P131 a) {')
    end = source.index('ECC_HD P131 sqr131(', start)
    return (source[:start] + f'#define GOAL22_POLY_NATIVE {native}\n'
            + '#include "poly_square.h"\n'
            + 'ECC_HD P131 squarePolynomial131(P131 a) { return goal22SquarePolynomial(a); }\n'
            + source[end:])
