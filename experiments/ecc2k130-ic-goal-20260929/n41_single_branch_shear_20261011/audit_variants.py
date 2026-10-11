"""Audit source-bound public queries and distinguish a parser failure."""

import gzip
import hashlib
import json
from pathlib import Path

from run import HERE, ROOT, save, sources


DIRECTORIES = {
    "horner": ROOT / "n41_single_branch_horner_20261011",
    "shear": HERE,
    "halftrace": ROOT / "n41_single_branch_halftrace_20261011",
    "zelim_v1": ROOT / "n41_single_branch_zelim_20261011",
    "zelim_v2": ROOT / "n41_single_branch_zelim_v2_20261011",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def main():
    external = sources()
    baseline_protocol = load(DIRECTORIES["horner"] / "protocol.json")
    rows = {}
    for name, directory in DIRECTORIES.items():
        protocol = load(directory / "protocol.json")
        actual = {key: sha(directory / key if key in ("run.py", "circuit.py") else path)
                  for key, path in external.items()}
        assert protocol["source_sha256"] == actual, name
        for key in ("target_q", "solver_flags", "workers", "solver_cap_seconds",
                    "construction_cap_seconds", "rss_cap_bytes", "factor_base_B",
                    "folded_columns_K", "source_mask_counts"):
            assert protocol[key] == baseline_protocol[key], (name, key)
        control = load(directory / "control_result.json")
        query = load(directory / "query_result.json")
        arithmetic = load(directory / "audit_result.json")
        assert control["status"] == "PASS_FULL_N41_PUBLIC_WITNESS_ASSIGNMENT"
        assert arithmetic["status"] == "PASS_16_DIRECT_FIELD_EVALUATIONS"
        assert query["solver_started"] and not query["solver_rss_exceeded"]
        assert abs(sum(query["phase_seconds"][part] for part in
                       ("construction", "write_and_hash", "solver")) -
                   query["phase_seconds"]["total"]) < 0.05
        logs = {}
        for stream in ("stdout", "stderr"):
            path = directory / f"solver.{stream}.gz"
            raw = gzip.open(path, "rb").read()
            assert sha(path) == query[f"{stream}_gzip_sha256"]
            assert hashlib.sha256(raw).hexdigest() == query[f"{stream}_sha256"]
            logs[stream] = raw
        if name == "zelim_v1":
            failure = load(directory / "failure.json")
            assert failure["status"] == "PRODUCER_FAILURE"
            assert query["solver_returncode"] == 255 and not query["solver_timed_out"]
            assert b"PARSE ERROR!" in logs["stderr"]
            assert b"c rst  geom" not in logs["stdout"]
            status = "PRODUCER_FAILURE"
        else:
            assert query["status"] == "BOUNDED_UNKNOWN"
            assert query["solver_timed_out"] and query["solver_returncode"] == -9
            assert b"c rst  geom" in logs["stdout"]
            assert not logs["stderr"]
            assert not any(line.startswith(b"s ") for line in logs["stdout"].splitlines())
            status = query["status"]
        rows[name] = {"status": status, "and_gates": query["formula"]["and_gates"],
                      "variables": query["formula"]["variables"],
                      "clauses": query["formula"]["clauses"],
                      "native_xor_rows": query["formula"]["native_xor_rows"],
                      "quartic_field_multiplications":
                          query["formula"]["quartic_field_multiplications"],
                      "formula_sha256": query["formula"]["sha256"],
                      "solver_seconds": query["phase_seconds"]["solver"],
                      "solver_restart_lines": sum(line.startswith(b"c rst  geom")
                                                  for line in logs["stdout"].splitlines())}
    assert [rows[key]["quartic_field_multiplications"] for key in
            ("horner", "shear", "halftrace", "zelim_v2")] == [165, 141, 141, 141]
    assert [rows[key]["and_gates"] for key in
            ("horner", "shear", "halftrace", "zelim_v2")] == [120929, 97994, 97994, 97565]
    assert load(HERE / "transform_search.json")["rows"][0]["field_multiplications"] == 46
    assert load(DIRECTORIES["halftrace"] / "halftrace_audit.json")["tested_values"] == 143
    record = {"status": "PASS_SOURCE_LOG_PHASE_AND_FAILURE_CLASSIFICATION_AUDIT",
              "target": baseline_protocol["target_q"], "rows": rows,
              "source_sha256": {"audit_variants.py": sha(__file__),
                                "transform_search.json": sha(HERE / "transform_search.json")}}
    save(HERE / "variant_audit.json", record)
    print(json.dumps({"status": record["status"], "rows": rows}, sort_keys=True))


if __name__ == "__main__":
    main()
