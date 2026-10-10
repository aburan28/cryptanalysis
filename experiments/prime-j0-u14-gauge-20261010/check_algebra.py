#!/usr/bin/env python3
"""Check exact field identities used by the U14 representation map."""

import json

P = (1 << 256) - (1 << 32) - 977
BETA = int("7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee", 16)
PI_A = int("3086d221a7d46bcde86c90e49284eb16", 16)
PI_B_MAG = int("e4437ed6010e88286f547fa90abfe4c3", 16)


def main():
    checks = {
        "beta_nontrivial": BETA % P != 1,
        "beta_order_three": pow(BETA, 3, P) == 1,
        "beta_quadratic_relation": (BETA * BETA + BETA + 1) % P == 0,
        "pi_in_kernel": (PI_A - PI_B_MAG * BETA) % P == 0,
        "pi_norm_equals_p": PI_A * PI_A + PI_A * PI_B_MAG + PI_B_MAG * PI_B_MAG == P,
    }
    print(json.dumps({"schema": 1, "checks": checks,
                      "status": "passed" if all(checks.values()) else "failed"},
                     sort_keys=True))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
