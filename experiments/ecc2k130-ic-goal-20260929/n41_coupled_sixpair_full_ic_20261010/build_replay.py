#!/usr/bin/env python3
"""Rebuild from vendored source snapshots and replay both frozen targets."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_replay(source, original_include, local_include, output, temp):
    text = source.read_text()
    assert text.count(original_include) == 1
    rewritten = temp / f"{output.name}.cpp"
    rewritten.write_text(text.replace(original_include, local_include))
    command = ["c++", "-std=c++17", "-O3", "-DNDEBUG", "-I", str(HERE),
               str(rewritten), "-o", str(output)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(f"compile failed: {completed.stderr}")
    return {"rewritten_source_sha256": sha(rewritten),
            "binary_sha256": sha(output),
            "compiler_warning": completed.stderr.strip()}


def main():
    ic_protocol = json.loads((HERE / "online_protocol.json").read_text())
    rho_protocol = json.loads((HERE / "rho_protocol.json").read_text())
    fresh_protocol = json.loads((HERE / "fresh/protocol.json").read_text())
    assert sha(HERE / "helper_snapshot.cpp") == ic_protocol["source_sha256"]["helper"]
    assert sha(HERE / "rho_source_snapshot.cpp") == fresh_protocol["source_sha256"]["rho_source"]
    assert sha(HERE / "rho_helper_snapshot.cpp") == rho_protocol["source_sha256"]["helper"]
    with tempfile.TemporaryDirectory(prefix="n41_sixpair_replay_", dir="/private/tmp") as folder:
        temp = Path(folder)
        specs = (
            (HERE / "join.cpp", '#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"',
             '#include "helper_snapshot.cpp"', HERE / "join", temp / "join"),
            (HERE / "online_worker.cpp", '#include "../n131_w18_four_pairs/native_join/frozen_source/helper.cpp"',
             '#include "helper_snapshot.cpp"', HERE / "online_worker", temp / "online_worker"),
            (HERE / "rho_source_snapshot.cpp", '#include "../koblitz-s5-invariant-20260924/three_pair_s7_native.cpp"',
             '#include "rho_helper_snapshot.cpp"', HERE / "rho_r3", temp / "rho_r3"),
        )
        builds = {}
        for source, original_include, local_include, original_binary, output in specs:
            row = compile_replay(source, original_include, local_include, output, temp)
            row["executed_binary_sha256"] = sha(original_binary)
            row["byte_identical_to_executed_binary"] = (
                row["binary_sha256"] == row["executed_binary_sha256"])
            builds[output.name] = row
        heldout = subprocess.run([str(temp / "join"), str(HERE / "heldout_input.txt"),
                                  str(temp / "heldout_hit.json"),
                                  str(temp / "heldout_native.json"), "20000000", "20",
                                  "202610100743"], capture_output=True, text=True,
                                 timeout=30, check=False)
        assert heldout.returncode == 0
        assert json.loads((temp / "heldout_hit.json").read_text()) == json.loads(
            (HERE / "heldout_hit.json").read_text())
        target = fresh_protocol["target"]
        command = [str(temp / "online_worker"), str(HERE / "online_atoms.txt"),
                   str(HERE / "online_logs.txt"), str(temp / "fresh_hit.json"),
                   str(temp / "fresh_native.json"), "20000000", "20", "202610101357"]
        with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True, bufsize=1) as process:
            ready = process.stdout.readline()
            assert ready.startswith("READY ")
            stdout, stderr = process.communicate(f"{target[0]} {target[1]}\n", timeout=30)
            assert process.returncode == 0, (stdout, stderr)
        fresh_hit = json.loads((temp / "fresh_hit.json").read_text())
        fresh_native = json.loads((temp / "fresh_native.json").read_text())
        assert fresh_hit == json.loads((HERE / "fresh/ic_hit.json").read_text())
        assert fresh_native["status"] == "VERIFIED_SCALAR"
        assert fresh_native["accepted_probes"] == 59042
        rho = subprocess.run([str(temp / "rho_r3"), str(HERE / "fresh/rho_input.txt"),
                              str(temp / "rho_native.json")], capture_output=True,
                             text=True, timeout=130, check=False)
        assert rho.returncode == 0, rho.stderr
        rho_native = json.loads((temp / "rho_native.json").read_text())
        rho_expected = json.loads((HERE / "fresh/rho_native.json").read_text())
        assert rho_native["recovered_scalar"] == rho_expected["recovered_scalar"]
        assert rho_native["walk_steps"] == rho_expected["walk_steps"]
        receipt = {
            "status": "PASS_VENDORED_SOURCE_REBUILD_AND_FROZEN_TARGET_REPLAY",
            "builds": builds,
            "heldout_witness_byte_equivalent": True,
            "fresh_witness_byte_equivalent": True,
            "fresh_ic_accepted_probes": fresh_native["accepted_probes"],
            "fresh_rho_walk_steps": rho_native["walk_steps"],
            "fresh_scalar": rho_native["recovered_scalar"],
            "source_sha256": {name: sha(path) for name, path in {
                "script": __file__, "helper_snapshot": HERE / "helper_snapshot.cpp",
                "rho_source_snapshot": HERE / "rho_source_snapshot.cpp",
                "rho_helper_snapshot": HERE / "rho_helper_snapshot.cpp",
                "join_source": HERE / "join.cpp",
                "online_source": HERE / "online_worker.cpp",
            }.items()},
        }
    with (HERE / "build_replay.json").open("x") as out:
        json.dump(receipt, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps({"status": receipt["status"],
                      "binary_matches": {key: value["byte_identical_to_executed_binary"]
                                         for key, value in builds.items()}}))


if __name__ == "__main__":
    main()
