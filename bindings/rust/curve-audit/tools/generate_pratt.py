"""Generate a recursive Lucas/Pratt prime certificate for a curve input.

Run with the repository's checked Sage launcher; the Rust auditor verifies the
result without Sage. Factoring each n-1 is generation work, not a verifier
assumption. The output may take a long time for arbitrary primes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sage.all import Integer, factor

SMALL_LIMIT = 1_000_000_000_000


def integer(value: str) -> Integer:
    return Integer(value[2:], 16) if value.lower().startswith("0x") else Integer(value)


def certificate(n: Integer) -> dict:
    if n <= SMALL_LIMIT:
        if not n.is_prime(proof=True):
            raise ValueError(f"not prime: {n}")
        return {"n": str(n), "small": True}

    factors = [(Integer(q), int(e)) for q, e in factor(n - 1)]
    if not all(q.is_prime(proof=True) for q, _ in factors):
        raise ValueError(f"unproved factor in {n}-1")
    a = 2
    while a <= 100_000:
        if pow(a, n - 1, n) == 1 and all(
            pow(a, (n - 1) // q, n) != 1 for q, _ in factors
        ):
            break
        a += 1
    else:
        raise ValueError(f"no Lucas witness within 100000 candidates for {n}")
    return {
        "n": str(n),
        "a": str(a),
        "factors": [[str(q), e] for q, e in factors],
        "sub": [certificate(q) for q, _ in factors if q > SMALL_LIMIT],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    record = json.loads(raw)
    p = integer(record["field"]["characteristic"])
    r = integer(record["subgroup"]["order"])
    result = {
        "schema": "ca.prime_certificates.v1",
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "field_characteristic": certificate(p),
        "selected_order": certificate(r),
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
