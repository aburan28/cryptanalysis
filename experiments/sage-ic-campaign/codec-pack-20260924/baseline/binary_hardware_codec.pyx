# SPDX-License-Identifier: GPL-2.0-or-later
# cython: fast_getattr=False
# distutils: language = c++
# distutils: libraries = ntl gmp
"""Native polynomial-basis transfer between Sage NTL points and uint32 arrays."""
import numpy as np
from sage.schemes.elliptic_curves.ell_point import (
    EllipticCurvePoint_field, EllipticCurvePoint_finite_field,
)
from sage.rings.finite_rings.element_ntl_gf2e cimport FiniteField_ntl_gf2eElement
from sage.libs.ntl.types cimport GF2E_c
from sage.structure.element cimport Element
from sage.structure.parent cimport Parent

cdef extern from *:
    """
    #include <NTL/GF2E.h>
    static inline void bh_pack_element(unsigned char* dst, const NTL::GF2E& x, long bytes) {
        NTL::BytesFromGF2X(dst, NTL::rep(x), bytes);
    }
    static inline void bh_unpack_element(NTL::GF2E& x, const unsigned char* src, long bytes) {
        NTL::GF2X polynomial;
        NTL::GF2XFromBytes(polynomial, src, bytes);
        NTL::conv(x, polynomial);
    }
    """
    void bh_pack_element(unsigned char*, const GF2E_c&, long) except +
    void bh_unpack_element(GF2E_c&, const unsigned char*, long) except +


def supports(field):
    return isinstance(field.zero(), FiniteField_ntl_gf2eElement)


def pack_points(curve, points, unsigned int words):
    """Validate all inputs and pack NTL coordinates without Python integers."""
    if words < 1 or words > 8 or words != (int(curve.base_ring().degree())+31)//32:
        raise ValueError('invalid coordinate width')
    if not supports(curve.base_ring()):
        raise TypeError('native codec requires Sage NTL GF(2^m) elements')
    items = list(points)
    n = len(items)
    if n*words*8 > 256*1024*1024:
        raise ValueError('packed input exceeds the working-set cap')
    data = np.zeros((2*n, words), dtype=np.uint32)
    flags = np.zeros(n, dtype=np.bool_)
    cdef unsigned char[:, ::1] raw = data.view(np.uint8).reshape((2*n, 4*words))
    cdef unsigned char[::1] zero = flags.view(np.uint8)
    cdef Py_ssize_t i
    cdef FiniteField_ntl_gf2eElement x, y
    for i in range(n):
        P = items[i]
        if not isinstance(P, EllipticCurvePoint_field) or P.curve() is not curve:
            raise ValueError('each input must be a Sage point on this curve')
        if not P:
            zero[i] = 1
            continue
        coordinates = P.xy()
        x = coordinates[0]
        y = coordinates[1]
        bh_pack_element(&raw[2*i, 0], x.x, 4*words)
        bh_pack_element(&raw[2*i+1, 0], y.x, 4*words)
    return data, flags


def unpack_points(curve, data, flags, unsigned int words):
    """Construct regular Sage points from internally generated coordinates."""
    if words < 1 or words > 8 or words != (int(curve.base_ring().degree())+31)//32:
        raise ValueError('invalid coordinate width')
    if data.dtype != np.dtype('uint32') or not data.flags.c_contiguous:
        raise ValueError('invalid packed coordinates')
    if flags.dtype != np.dtype('bool') or not flags.flags.c_contiguous:
        raise ValueError('invalid infinity flags')
    if data.ndim != 2 or flags.ndim != 1 or data.shape != (2*len(flags), words):
        raise ValueError('inconsistent packed dimensions')
    cdef const unsigned char[:, ::1] raw = data.view(np.uint8).reshape((len(data), 4*words))
    cdef const unsigned char[::1] zero = flags.view(np.uint8)
    cdef FiniteField_ntl_gf2eElement model = curve.base_ring().zero()
    cdef FiniteField_ntl_gf2eElement x, y
    cdef Py_ssize_t i
    cdef Element point
    cdef Parent point_parent
    cdef bint standard_points
    model._cache.F.restore()
    one = curve.base_ring().one()
    constructor = curve._point
    standard_points = constructor is EllipticCurvePoint_finite_field
    if standard_points:
        point_parent = curve.point_homset()
        allocate = constructor.__new__
    output = []
    for i in range(len(flags)):
        if zero[i]:
            output.append(curve(0))
            continue
        x = model._new()
        y = model._new()
        bh_unpack_element(x.x, &raw[2*i, 0], 4*words)
        bh_unpack_element(y.x, &raw[2*i+1, 0], 4*words)
        if standard_points:
            point = allocate(constructor)
            point._parent = point_parent
            point._codomain = curve
            point._normalized = True
            point._coords = (x, y, one)
            output.append(point)
        else:
            output.append(constructor(curve, [x, y, one], check=False))
    return output
