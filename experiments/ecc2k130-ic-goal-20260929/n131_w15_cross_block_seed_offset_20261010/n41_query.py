#!/usr/bin/env python3
"""One frozen N41 public-point query with cross-block seed offsets 0..7."""
import hashlib
import json
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
INPUT = BASE / "n41_coupled_sixpair_full_ic_20261010/heldout_input.txt"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / "n41_query_protocol.json"
    freeze = json.loads(path.read_text())
    sources = {"runner": Path(__file__), "binary": HERE / "n41_offset_join",
               "source": HERE / "n41_offset_join.cpp", "input": INPUT,
               "build_receipt": HERE / "n41_build_receipt.json"}
    assert freeze["status"] == "FROZEN_BEFORE_N41_PUBLIC_QUERY"
    assert freeze["source_sha256"] == {name: sha(source) for name, source in sources.items()}
    assert list(map(int, INPUT.read_text().splitlines()[0].split())) == [
        *freeze["public_target"], int(freeze["subgroup_order"]), 6]
    paths = {name: HERE / name for name in ("n41_native.json", "n41_hit.json",
                                            "n41_stdout.txt", "n41_stderr.txt",
                                            "n41_query_receipt.json")}
    assert not any(item.exists() for item in paths.values())
    command = [str(HERE / "n41_offset_join"), str(INPUT),
               str(paths["n41_hit.json"]), str(paths["n41_native.json"]),
               str(freeze["max_accepted_probes"]),
               str(freeze["native_online_cap_seconds"]),
               str(freeze["rng_seed"])]
    started = time.monotonic_ns()
    status, code = None, None
    with paths["n41_stdout.txt"].open("x") as stdout, paths["n41_stderr.txt"].open("x") as stderr:
        try:
            child = subprocess.run(command, stdout=stdout, stderr=stderr,
                                   timeout=freeze["parent_cap_seconds"],
                                   check=False)
            code = child.returncode
        except subprocess.TimeoutExpired:
            status = "CENSORED_PARENT_CAP"
    parent_ns = time.monotonic_ns()-started
    native = None
    if paths["n41_native.json"].exists():
        native = json.loads(paths["n41_native.json"].read_text())
    if status is None:
        status = native["status"] if code == 0 and native else "PRODUCER_FAILURE"
    if native and native["peak_rss_bytes"] > freeze["rss_cap_bytes"]:
        status = "CENSORED_MEMORY"
    if native and native["online_ns"] > freeze["native_online_cap_seconds"]*10**9:
        status = "CENSORED_ONLINE_TIME"
    hit = None
    if paths["n41_hit.json"].exists():
        hit = json.loads(paths["n41_hit.json"].read_text())
    if status == "FOUND_PENDING_SAGE_REPLAY":
        assert hit and hit["status"] == "NATIVE_RELATION_PENDING_SAGE"
        seeds = hit["seed_sums"]
        assert seeds[2] == seeds[3] and seeds[4] == seeds[5]
        assert seeds[2]^seeds[4] in freeze["allowed_offsets"]
        assert hit["raw_sum"] == freeze["public_target"]
    receipt = {"status": status, "candidate_id": None,
               "source_sha256": freeze["source_sha256"],
               "protocol_sha256": sha(path), "command": command,
               "process_exit_code": code, "parent_wall_ns": parent_ns,
               "native": native, "hit": hit,
               "artifact_sha256": {name: sha(item) for name, item in paths.items()
                                   if name != "n41_query_receipt.json" and item.exists()}}
    with paths["n41_query_receipt.json"].open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"status": status, "parent_wall_s": parent_ns/1e9,
                      "accepted_probes": native["accepted_probes"] if native else None,
                      "offset": hit["seed_sums"][2]^hit["seed_sums"][4]
                                if hit and status == "FOUND_PENDING_SAGE_REPLAY" else None}))


if __name__ == "__main__":
    main()
