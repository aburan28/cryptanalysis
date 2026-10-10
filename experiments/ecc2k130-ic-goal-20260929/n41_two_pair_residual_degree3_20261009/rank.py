#!/usr/bin/env python3
"""Certificate rows for cubic Boolean rank of exact public residuals."""

import hashlib
import itertools
import json
import resource
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
DOMAIN = GOAL / "n41_w8_two_pair_backward_20261009"
TABLE = DOMAIN / "table.bin"
RECORD_BYTES = 15
N = 41
DIM = sum(__import__("math").comb(N, degree) for degree in range(4))
MAX_ROWS = 16384
STRIDE = 977
OFFSET = 13
CAP_NS = 300_000_000_000
RSS_CAP = 4 * 1024**3
sys.path.insert(0, str(GOAL.parent / "koblitz-polynomial-w-pair-20260925"))
from pair_oracle import Field


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_paths():
    return [HERE / "rank.py", HERE / "audit.py", HERE / "native_audit.cpp",
            HERE / "sage_runtime_info.json", TABLE, DOMAIN / "result.json",
            DOMAIN / "audit.json",
            GOAL.parent / "koblitz-polynomial-w-pair-20260925/pair_oracle.py"]


def rss_bytes():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value if sys.platform == "darwin" else value * 1024


PAIRS = {pair: 1+N+k for k, pair in
         enumerate(itertools.combinations(range(N), 2))}
TRIPLES = {triple: 1+N+len(PAIRS)+k for k, triple in
           enumerate(itertools.combinations(range(N), 3))}


def feature(value):
    active = [i for i in range(N) if value & (1 << i)]
    row = 1
    for i in active:
        row |= 1 << (1+i)
    for pair in itertools.combinations(active, 2):
        row |= 1 << PAIRS[pair]
    for triple in itertools.combinations(active, 3):
        row |= 1 << TRIPLES[triple]
    return row


def rank_witness(values, count, started):
    pivots = {}
    witness = []
    processed = 0
    for k in range(MAX_ROWS):
        index = (k*STRIDE+OFFSET) % count
        row = feature(values[index])
        while row:
            leading = row.bit_length()-1
            if leading not in pivots:
                pivots[leading] = row
                witness.append(index)
                break
            row ^= pivots[leading]
        processed += 1
        if len(pivots) == DIM:
            break
        if processed % 512 == 0 and (
                time.monotonic_ns()-started > CAP_NS or rss_bytes() > RSS_CAP):
            raise TimeoutError("rank witness exceeded frozen time or RSS cap")
    return witness, processed


def main():
    outputs = [HERE / name for name in
               ("result.json", "phi.bin", "x_witness.bin", "phi_witness.bin")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("preserve first frozen rank run")
    protocol = json.loads((HERE / "protocol.json").read_text())
    if (protocol["source_sha256"] != {
            str(path): sha(path) for path in source_paths()} or
            protocol["max_rows"] != MAX_ROWS or protocol["cap_ns"] != CAP_NS):
        raise ValueError("rank source or cap changed after freeze")
    prior = json.loads((DOMAIN / "result.json").read_text())
    audit = json.loads((DOMAIN / "audit.json").read_text())
    if (prior["status"] != "EXACT_TWO_PAIR_DOMAIN" or
            audit["status"] != "PASS_INDEPENDENT_SAGE_TABLE_AUDIT" or
            prior["table_sha256"] != sha(TABLE)):
        raise ValueError("prior exact table lacks audited source identity")
    data = TABLE.read_bytes()
    if len(data) != prior["stored_labeled_residuals"]*RECORD_BYTES:
        raise ValueError("table record count changed")
    count = len(data)//RECORD_BYTES
    if __import__("math").gcd(STRIDE, count) != 1:
        raise ValueError("row schedule is not a permutation")
    started = time.monotonic_ns()
    xs = [int.from_bytes(data[i:i+6], "little")
          for i in range(0, len(data), RECORD_BYTES)]
    field = Field(N, [0, 3])
    phis = [field.inv(x ^ 1) for x in xs]
    phi_bytes = b"".join(value.to_bytes(6, "little") for value in phis)
    (HERE / "phi.bin").write_bytes(phi_bytes)
    phi_ns = time.monotonic_ns()-started
    x_start = time.monotonic_ns()
    x_witness, x_processed = rank_witness(xs, count, started)
    x_ns = time.monotonic_ns()-x_start
    p_start = time.monotonic_ns()
    phi_witness, phi_processed = rank_witness(phis, count, started)
    p_ns = time.monotonic_ns()-p_start
    for name, indices in (("x_witness.bin", x_witness),
                          ("phi_witness.bin", phi_witness)):
        (HERE / name).write_bytes(b"".join(struct.pack("<I", i) for i in indices))
    total_ns = time.monotonic_ns()-started
    result = {"status": "FULL_CUBIC_RANK" if len(x_witness) == DIM and
              len(phi_witness) == DIM else "RANK_INCOMPLETE_WITHIN_ROW_CAP",
              "proposal_id": "Q20261009182400", "candidate_id": None,
              "curve_id": prior["curve_id"],
              "public_target_q": prior["public_target_q"],
              "table_sha256": sha(TABLE), "protocol_sha256": sha(HERE / "protocol.json"),
              "phi_sha256": sha(HERE / "phi.bin"),
              "x_witness_sha256": sha(HERE / "x_witness.bin"),
              "phi_witness_sha256": sha(HERE / "phi_witness.bin"),
              "field_bits": N, "monomial_degree_max": 3,
              "monomial_dimension": DIM, "table_records": count,
              "row_schedule": {"stride": STRIDE, "offset": OFFSET,
                               "max_rows": MAX_ROWS},
              "x_rank": len(x_witness), "x_rows_processed": x_processed,
              "phi_rank": len(phi_witness), "phi_rows_processed": phi_processed,
              "phi_construction_ns": phi_ns, "x_rank_ns": x_ns,
              "phi_rank_ns": p_ns,
              "witness_serialization_ns": total_ns-phi_ns-x_ns-p_ns,
              "total_stage_ns": total_ns, "peak_rss_bytes": rss_bytes(),
              "source_sha256": protocol["source_sha256"]}
    (HERE / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print(json.dumps({key: result[key] for key in
                      ("status", "x_rank", "x_rows_processed", "phi_rank",
                       "phi_rows_processed", "total_stage_ns", "peak_rss_bytes")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
