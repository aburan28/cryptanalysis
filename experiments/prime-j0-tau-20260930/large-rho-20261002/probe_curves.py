"""Identify practical j=0 prime-subgroup fixtures for one-target C rho tests."""

from sage.all import EllipticCurve, GF, ZZ


def main():
    p = 2**61 - 1
    field = GF(p)
    for b in (5, 11, 13):
        curve = EllipticCurve(field, [0, b])
        order = ZZ(curve.cardinality())
        print(f"p={p} b={b} order={order} factorization={list(order.factor())}")


if __name__ == "__main__":
    main()
