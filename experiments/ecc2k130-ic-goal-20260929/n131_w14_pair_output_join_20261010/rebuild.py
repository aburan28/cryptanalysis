#!/usr/bin/env python3
"""Rebuild both native joins and replay frozen functional controls."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

here = Path(__file__).resolve().parent
legacy = here.parent / "n131_w14_coupled_fouratom_inverse_20261010"
support = here.parent / "n131_w14_ten_source_gate_20261009" / "support_w14.tsv"
compiler = subprocess.run(["clang++", "--version"], capture_output=True,
                          text=True, check=True).stdout.splitlines()[0]
rows = []
v1 = json.loads((here / "result.json").read_text())["rows"]
v2 = json.loads((here / "result_filtered.json").read_text())["rows"]
with tempfile.TemporaryDirectory(prefix="pair-output-join-", dir="/private/tmp") as tmp:
    for source, binary in [("native.cpp", "native"),
                           ("native_filtered.cpp", "native_filtered")]:
        output = Path(tmp) / binary
        command = ["clang++", "-O3", "-std=c++17", source, "-o", str(output)]
        compile_process = subprocess.run(command, cwd=here, capture_output=True, text=True)
        assert compile_process.returncode == 0, compile_process.stderr
        rebuilt = hashlib.sha256(output.read_bytes()).hexdigest()
        measured = hashlib.sha256((here / binary).read_bytes()).hexdigest()
        cases = ([(41,"positive"),(41,"trace_zero_control"),
                  (131,"positive"),(131,"trace_zero_control")]
                 if binary == "native" else
                 [(131,"positive"),(131,"trace_zero_control")])
        replays = []
        for n, case in cases:
            input_path = legacy / f"native_n{n}_{case}.txt"
            result_path = Path(tmp) / f"{binary}_n{n}_{case}.json"
            args = [str(output),str(input_path),str(result_path)]
            if binary == "native_filtered":
                args.append(str(support))
            args.extend(["20","4294967296"])
            process = subprocess.run(args, capture_output=True, text=True,
                                     timeout=25)
            assert process.returncode == 0, process.stderr
            got = json.loads(result_path.read_text())
            expected_row = next(row for row in (v1 if binary == "native" else v2)
                                if row["case"] == case and
                                (row.get("field_degree",131) == n) and
                                row["variant"] == ("pair_join" if binary == "native"
                                                   else "filtered_pair_join"))
            expected = expected_row["native"]
            for key in ("status","pair_output_entries","distinct_pair_outputs", "hits"):
                assert got[key] == expected[key], (binary,n,case,key)
            if binary == "native_filtered":
                assert got["allowed_source_pairs"] == expected["allowed_source_pairs"]
            replays.append({"field_degree": n, "case": case,
                            "hit_count": len(got["hits"]),
                            "pair_outputs": got["distinct_pair_outputs"]})
        rows.append({"source": source, "binary": binary,
                     "measured_sha256": measured, "rebuilt_sha256": rebuilt,
                     "byte_identical": rebuilt == measured,
                     "command": command[:5]+["<temporary output>"],
                     "compiler_warning": compile_process.stderr.strip(),
                     "functional_replays": replays})
record = {"status": "PASS_FUNCTIONAL_REBUILD_REPLAY", "compiler": compiler,
          "rows": rows,
          "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(here / "rebuild.json").write_text(json.dumps(record, indent=2, sort_keys=True)+"\n")
print(json.dumps({"status": record["status"], "binaries": len(rows)}, sort_keys=True))
