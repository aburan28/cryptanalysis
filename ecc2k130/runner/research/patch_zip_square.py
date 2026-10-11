"""Replace only the normal-basis squaring permutation."""


def patch(source):
    start = source.index("ECC_HD P131 sqr131(const P131 &a){")
    end = source.index("#ifndef ECC_PACKED_PERM_SIGMA", start)
    return source[:start] + '''#include "zip_square.h"
ECC_HD P131 sqr131(const P131 &a) {
    return goal22SquareNormal(a);
}
''' + source[end:]
