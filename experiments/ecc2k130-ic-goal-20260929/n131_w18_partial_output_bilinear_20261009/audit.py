#!/usr/bin/env sage -python
"""Independent Sage pair replay and complete XCNF terminal audit."""

import hashlib
import json
from pathlib import Path

from sage.all import EllipticCurve, GF, PolynomialRing

HERE = Path(__file__).resolve().parent
GOAL = HERE.parent
PROBE = GOAL / "n131_w18_full_width_pair_oracle/probe.json"
N = 131


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def independent_pair_check():
    positive = next(q for q in json.loads(PROBE.read_text())["queries"]
                    if q.get("z") is not None)
    ring = PolynomialRing(GF(2), "t")
    t = ring.gen()
    field = GF(2**N, name="t", modulus=t**N + t**13 + t**2 + t + 1)

    def elem(value):
        return field(ring([(value >> bit) & 1 for bit in range(N)]))

    def integer(value):
        return sum(int(bit) << bit_index
                   for bit_index, bit in enumerate(value.polynomial().list()))

    curve = EllipticCurve(field, [1, 0, 0, 0, 1])
    raw = [curve(elem(x), elem(y)) for x, y in positive["raw_points"]]
    pair_sum = raw[0] + raw[1]
    if pair_sum.is_zero() or [integer(pair_sum[0]), integer(pair_sum[1])] != positive["raw_sum"]:
        raise ValueError("independent Sage group addition differs")
    z = elem(positive["z"])
    if z != 1 / (pair_sum[0] + 1):
        raise ValueError("saved pair-output coordinate differs")
    witness = positive["matching_witnesses"][0]
    mask1, mask2 = witness["w_masks"]
    w1 = sum((elem(1 << (bit + 1)) for bit in range(18) if (mask1 >> bit) & 1), field(0))
    w2 = sum((elem(1 << (bit + 1)) for bit in range(18) if (mask2 >> bit) & 1), field(0))
    s = w1 + w2
    h = field(0)
    for j in range((N + 1) // 2):
        h += s ** (2 ** (2*j))
    if h**2 + h != s:
        raise ValueError("Sage half-trace identity differs")
    if z**2 != h**2 + field(witness["epsilon"]) + (z**2 + z) * w1 * w2:
        raise ValueError("independent Sage bilinear equation differs")
    return {"positive_z": positive["z"], "w_masks": witness["w_masks"],
            "epsilon": witness["epsilon"], "raw_sum": positive["raw_sum"]}


def parse_model(output):
    assigned = {}
    for line in output.splitlines():
        if not line.startswith("v "):
            continue
        for token in line[2:].split():
            literal = int(token)
            if literal:
                var = abs(literal)
                value = literal > 0
                if var in assigned and assigned[var] != value:
                    raise ValueError("solver model assigns a variable both ways")
                assigned[var] = value
    return assigned


def audit_xcnf(path, assigned):
    lines = path.read_text().splitlines()
    head = lines[0].split()
    if len(head) != 4 or head[:2] != ["p", "cnf"]:
        raise ValueError("invalid XCNF header")
    vars_expected, rows_expected = int(head[2]), int(head[3])
    if len(lines) - 1 != rows_expected:
        raise ValueError("XCNF row count differs")
    if len(assigned) < vars_expected or any(i not in assigned for i in range(1, vars_expected + 1)):
        raise ValueError("SAT model is incomplete")
    cnf_count = xor_count = 0
    for line in lines[1:]:
        xor = line.startswith("x ")
        terms = line[2:].split() if xor else line.split()
        if not terms or terms[-1] != "0":
            raise ValueError("malformed XCNF row")
        literals = [int(term) for term in terms[:-1]]
        values = [assigned[abs(lit)] == (lit > 0) for lit in literals]
        if xor:
            xor_count += 1
            if sum(values) % 2 != 1:
                raise ValueError("SAT model fails native XOR row")
        else:
            cnf_count += 1
            if not any(values):
                raise ValueError("SAT model fails CNF clause")
    return {"variables": vars_expected, "cnf_clauses": cnf_count,
            "native_xor_rows": xor_count}


def main():
    output = HERE / "audit.json"
    if output.exists():
        raise FileExistsError("preserve first audit")
    protocol = json.loads((HERE / "protocol.json").read_text())
    result = json.loads((HERE / "result.json").read_text())
    if protocol["source_sha256"] != {path: sha(path) for path in protocol["source_sha256"]}:
        raise ValueError("frozen source or input changed")
    if (result["source_sha256"] != protocol["source_sha256"] or
            result["protocol_sha256"] != sha(HERE / "protocol.json") or
            result["status"] != "COMPLETE_THREE_CASE_DIAGNOSTIC"):
        raise ValueError("run receipt changed")
    pair = independent_pair_check()
    if result["cases"][0]["z"] != pair["positive_z"] or result["cases"][1]["z"] != pair["positive_z"]:
        raise ValueError("positive cases use a different pair output")
    if len(result["cases"]) != 3 or result["target_count"] != 0:
        raise ValueError("case count or workload law changed")
    checked = []
    for case in result["cases"]:
        directory = HERE / case["name"]
        if json.loads((directory / "result.json").read_text()) != case:
            raise ValueError("case receipt changed")
        for file, key in (("query.xcnf", "formula_sha256"),
                          ("solver.stdout.txt", "stdout_sha256"),
                          ("solver.stderr.txt", "stderr_sha256")):
            if sha(directory / file) != case[key]:
                raise ValueError(f"case artifact changed: {file}")
        if sum(case[key] for key in ("build_ns", "solver_ns", "terminal_check_ns",
                                     "interval_overhead_ns")) != case["charged_stage_ns"]:
            raise ValueError("exclusive phase sum differs")
        if case["sampled_solver_peak_rss_bytes"] > protocol["rss_cap_bytes"]:
            raise ValueError("solver RSS exceeded cap")
        stdout = (directory / "solver.stdout.txt").read_text(errors="replace")
        statuses = [line for line in stdout.splitlines() if line.startswith("s ")]
        if case["solver_status_line"] != (statuses[-1] if statuses else None):
            raise ValueError("saved status line differs")
        model = parse_model(stdout)
        xcnf_check = None
        if case["status"] == "SAT":
            xcnf_check = audit_xcnf(directory / "query.xcnf", model)
            if (xcnf_check["cnf_clauses"] != case["counts"]["cnf_clauses"] or
                    xcnf_check["native_xor_rows"] != case["counts"]["native_xor_rows"]):
                raise ValueError("formula counts differ")
        elif model:
            raise ValueError("non-SAT case contains a model")
        checked.append({"name": case["name"], "status": case["status"],
                        "xcnf_check": xcnf_check})
    audit = {"status": "PASS_INDEPENDENT_SAGE_AND_XCNF_AUDIT",
             "proposal_id": result["proposal_id"], "candidate_id": None,
             "protocol_sha256": sha(HERE / "protocol.json"),
             "sage_pair_replay": pair, "cases": checked}
    output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": audit["status"], "cases": checked}, sort_keys=True))


if __name__ == "__main__":
    main()
