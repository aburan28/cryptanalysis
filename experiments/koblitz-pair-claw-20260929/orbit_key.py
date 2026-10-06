#!/usr/bin/env python3
"""Fast signed-Frobenius orbit key for type-II ONB Koblitz points."""

import hashlib

KEY_BYTES = 48  # Two n-bit coordinates fit for n <= 131.


class OrbitKey:
    def __init__(self, onb):
        self.onb = onb
        self.n = onb.m
        self.mask = (1 << self.n) - 1
        modulus = 2 * self.n + 1
        coordinate_cycle = []
        index = 1
        for _ in range(self.n):
            coordinate_cycle.append(index - 1)
            doubled = 2 * index % modulus
            index = min(doubled, modulus - doubled)
        assert index == 1 and len(set(coordinate_cycle)) == self.n
        self.coordinate_cycle = tuple(coordinate_cycle)
        cycle_position = {coordinate: position
                          for position, coordinate in enumerate(coordinate_cycle)}
        tables = []
        for offset in range(0, self.n, 8):
            table = [0] * 256
            for byte in range(1, 256):
                bit = byte & -byte
                coordinate = offset + bit.bit_length() - 1
                table[byte] = table[byte ^ bit]
                if coordinate < self.n:
                    table[byte] |= 1 << cycle_position[coordinate]
            tables.append(tuple(table))
        self.tables = tuple(tables)
        self.coordinate_bytes = (self.n + 7) // 8

    def cycle_bits(self, field_element):
        coordinates = self.onb.toCoords(field_element)
        result = 0
        for table, byte in zip(self.tables,
                               coordinates.to_bytes(self.coordinate_bytes,
                                                    "little")):
            result |= table[byte]
        return result

    def canonical(self, point):
        """Return (packed orbit key, Frobenius exponent, sign)."""
        if point is None:
            return -1, 0, 1
        x = self.cycle_bits(point[0])
        y = self.cycle_bits(point[1])
        best, best_j, best_sign = None, 0, 1
        for j in range(self.n):
            positive = (x << self.n) | y
            negative = (x << self.n) | (x ^ y)
            if best is None or positive < best:
                best, best_j, best_sign = positive, j, 1
            if negative < best:
                best, best_j, best_sign = negative, j, -1
            x = ((x << 1) | (x >> (self.n - 1))) & self.mask
            y = ((y << 1) | (y >> (self.n - 1))) & self.mask
        return best, best_j, best_sign

    def point_from_key(self, key):
        if key == -1:
            return None
        x_cycle, y_cycle = key >> self.n, key & self.mask
        x_coords = y_coords = 0
        for position, coordinate in enumerate(self.coordinate_cycle):
            x_coords |= ((x_cycle >> position) & 1) << coordinate
            y_coords |= ((y_cycle >> position) & 1) << coordinate
        return self.onb.fromCoords(x_coords), self.onb.fromCoords(y_coords)


def digest_key(key):
    encoded = b"identity" if key == -1 else key.to_bytes(KEY_BYTES, "little")
    return hashlib.blake2s(encoded, digest_size=16).digest()
