"""Bijective schedules for quotient-table classes and unordered query pairs."""

import math
import random


def affine_parameters(domain, seed):
    rng = random.Random(seed)
    step = rng.randrange(1, domain)
    while math.gcd(step, domain) != 1:
        step = rng.randrange(1, domain)
    return step, rng.randrange(domain)


def affine_rank(position, domain, step, offset):
    if position < 0 or position >= domain:
        raise IndexError(position)
    return (step * position + offset) % domain


def unordered_pair(rank, size):
    """Unrank (i,j) with 0<=i<=j<size in j-major triangular order."""
    domain = size * (size + 1) // 2
    if rank < 0 or rank >= domain:
        raise IndexError(rank)
    j = (math.isqrt(8 * rank + 1) - 1) // 2
    i = rank - j * (j + 1) // 2
    return i, j


def cross_orbit_pair(rank, orbits, orbit_size):
    """Unrank (orbit i, orbit j, relative shift) with i<j.

    The pair (representative_i, shift(representative_j)) includes every
    cross-orbit unordered pair exactly once modulo simultaneous signed
    Frobenius action.
    """
    domain = orbits * (orbits - 1) // 2 * orbit_size
    if rank < 0 or rank >= domain:
        raise IndexError(rank)
    pair_rank, shift = divmod(rank, orbit_size)
    j = (1 + math.isqrt(1 + 8 * pair_rank)) // 2
    i = pair_rank - j * (j - 1) // 2
    return i, j, shift


def within_orbit_pair(rank, orbits, degree):
    """Unrank nonidentity unordered pairs within a signed-Frobenius orbit.

    For odd degree n, relative positions modulo swapping are n+1 classes.
    The inverse pair has zero sum; the remaining n classes are emitted.
    """
    domain = orbits * degree
    if rank < 0 or rank >= domain:
        raise IndexError(rank)
    orbit_index, class_index = divmod(rank, degree)
    positive_count = (degree + 1) // 2
    if class_index < positive_count:
        shift = class_index
    else:
        shift = degree + class_index - positive_count + 1
    return orbit_index, shift
