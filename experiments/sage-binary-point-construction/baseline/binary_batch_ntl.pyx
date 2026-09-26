# SPDX-License-Identifier: GPL-2.0-or-later
# cython: fast_getattr=False
# distutils: language = c++
# distutils: libraries = ntl gmp
r"""
Native arithmetic for the ordinary binary-curve batch APIs.

The public input contract and non-NTL fallback live in :mod:`binary_batch`.
This private implementation retains ordinary Sage output points, and uses
variable-time NTL arithmetic on public mathematical inputs.
"""

from libcpp.vector cimport vector
from cysignals.signals cimport sig_check
from sage.libs.ntl.types cimport GF2E_c
from sage.rings.finite_rings.element_ntl_gf2e cimport FiniteField_ntl_gf2eElement

cdef extern from "NTL/GF2E.h" namespace "NTL":
    void add(GF2E_c&, const GF2E_c&, const GF2E_c&) except +
    void mul(GF2E_c&, const GF2E_c&, const GF2E_c&) except +
    void sqr(GF2E_c&, const GF2E_c&) except +
    void inv(GF2E_c&, const GF2E_c&) except +
    bint IsZero(const GF2E_c&)
    void clear(GF2E_c&)

cdef extern from *:
    """
    #include <NTL/GF2E.h>
    struct binary_batch_entry {
        NTL::GF2E x, y, denominator, numerator, xsum, prefix;
        Py_ssize_t index;
    };
    """
    cppclass binary_batch_entry:
        GF2E_c x, y, denominator, numerator, xsum, prefix
        Py_ssize_t index


def supports(field):
    """Whether the field uses the NTL binary-extension representation."""
    return isinstance(field.zero(), FiniteField_ntl_gf2eElement)


def _add_prepared(curve, pairs, FiniteField_ntl_gf2eElement a2):
    """Add validated point/coordinate triples; called by ``binary_batch``."""
    # Consume the generator before restoring NTL's modulus. Arbitrary input
    # iterators may perform arithmetic over a different NTL field.
    pairs = list(pairs)
    field = curve.base_ring()
    if a2.parent() is not field:
        raise ValueError('coefficient belongs to a different field')
    cdef FiniteField_ntl_gf2eElement model = field.zero()
    cdef FiniteField_ntl_gf2eElement x1, y1, x2, y2, x3, y3
    cdef vector[binary_batch_entry] active
    cdef binary_batch_entry entry
    cdef GF2E_c inverse, reciprocal, slope, result_x, result_y, temporary
    cdef Py_ssize_t i, n
    output = [None] * len(pairs)
    zero_point = None
    one = field.one()
    constructor = curve._point
    model._cache.F.restore()

    for i in range(len(pairs)):
        sig_check()
        (P, px, py), (Q, qx, qy) = pairs[i]
        if px is None:
            output[i] = Q
            continue
        if qx is None:
            output[i] = P
            continue
        x1, y1, x2, y2 = px, py, qx, qy
        if (x1.parent() is not field or y1.parent() is not field
                or x2.parent() is not field or y2.parent() is not field):
            raise ValueError('coordinates belong to a different field')
        if x1.x == x2.x:
            if y1.x != y2.x or IsZero(x1.x):
                if zero_point is None:
                    zero_point = curve(0)
                output[i] = zero_point
                continue
            sqr(entry.numerator, x1.x)
            add(entry.numerator, entry.numerator, y1.x)
            entry.denominator = x1.x
            clear(entry.xsum)
        else:
            add(entry.numerator, y1.x, y2.x)
            add(entry.denominator, x1.x, x2.x)
            entry.xsum = entry.denominator
        entry.index = i
        entry.x = x1.x
        entry.y = y1.x
        active.push_back(entry)

    n = active.size()
    if not n:
        return output
    # No zero denominator reaches this block. Montgomery inversion costs
    # one field inverse and exactly 3*(n-1) field multiplications.
    active[0].prefix = active[0].denominator
    for i in range(1, n):
        sig_check()
        mul(active[i].prefix, active[i-1].prefix, active[i].denominator)
    inv(inverse, active[n-1].prefix)
    for i in range(n-1, -1, -1):
        sig_check()
        if i:
            mul(reciprocal, inverse, active[i-1].prefix)
            mul(inverse, inverse, active[i].denominator)
        else:
            reciprocal = inverse
        mul(slope, active[i].numerator, reciprocal)
        sqr(result_x, slope)
        add(result_x, result_x, slope)
        add(result_x, result_x, active[i].xsum)
        add(result_x, result_x, a2.x)
        add(temporary, active[i].x, result_x)
        mul(result_y, slope, temporary)
        add(result_y, result_y, result_x)
        add(result_y, result_y, active[i].y)
        active[i].x = result_x
        active[i].y = result_y

    # Finish native arithmetic before invoking Python point constructors.
    for i in range(n):
        sig_check()
        x3 = model._new()
        y3 = model._new()
        x3.x = active[i].x
        y3.x = active[i].y
        output[active[i].index] = constructor(curve, [x3, y3, one], check=False)
    return output
