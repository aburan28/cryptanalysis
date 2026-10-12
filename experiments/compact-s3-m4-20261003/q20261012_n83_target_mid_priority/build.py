#!/usr/bin/env python3
"""Add two target-side branch priorities to the frozen Q1488 WDSat source."""
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1488 = PARENT / "q20261012_n83_first_pair_restart"
MANIFEST = PARENT / "q20261011_wdsat_order/order_manifest.json"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1507_target_priority")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def priorities():
    source = read(MANIFEST)["cells"]["n83"]
    mids = source["pair_mid_first_ids"]
    leaves = source["interleaved_leaves_priority"]
    selectors = source["selector_priority"]
    assert len(mids) == 166 and len(leaves) == 332 and len(selectors) == 2
    target_mid = selectors + mids[83:] + mids[:83]
    target_leaf = selectors + [leaves[4 * i + j] for i in range(83)
                               for j in (2, 3)] + [leaves[4 * i + j]
                                                   for i in range(83) for j in (0, 1)]
    assert len(target_mid) == len(set(target_mid)) == 168
    assert len(target_leaf) == len(set(target_leaf)) == 334
    return {"q1507_target_mid_first": target_mid,
            "q1507_target_leaf_first": target_leaf}


def main():
    protocol = read(HERE / "protocol.json")
    parent = read(Q1488 / "build_receipt.json")
    assert sha(MANIFEST) == protocol["order_manifest_sha256"]
    assert sha(Q1488 / "build_receipt.json") == protocol["q1488_build_receipt_sha256"]
    source = Path(parent["patched_source_path"])
    assert sha(source) == parent["patched_wdsat_c_sha256"]
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    BUILD.mkdir(parents=True)
    shutil.copytree(source.parent, BUILD / "src")
    target = BUILD / "src/wdsat.c"
    data = target.read_text()
    decl = ""
    cases = ""
    for name, values in priorities().items():
        decl += f"static const int_t {name}[] = {{" + ", ".join(map(str, values)) + "};\n"
        cases += (f'    if (mode && strcmp(mode, "{name}") == 0) {{\n'
                  f"        priority = {name};\n"
                  f"        length = sizeof({name}) / sizeof({name}[0]);\n"
                  "    } else\n")
    anchor = "static unsigned char q1469_seen[__ID_SIZE__];"
    assert data.count(anchor) == 1
    data = data.replace(anchor, decl + anchor)
    anchor2 = '    if (mode && strcmp(mode, "q1478_leafpair_first") == 0) {'
    assert data.count(anchor2) == 1
    data = data.replace(anchor2, cases + anchor2)
    # Keep first-pair capture active through the existing branch cap.
    capture_cap = "    if (count >= 32768) q1479_capture_enabled = false;"
    assert data.count(capture_cap) == 1
    data = data.replace(capture_cap,
                        "    if (count >= 1048576) q1479_capture_enabled = false;")
    target.write_text(data)
    proc = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                          text=True, capture_output=True)
    # Preserve the compiler transcript without Make's trailing spaces.
    (HERE / "build.stdout.txt").write_text(
        "\n".join(line.rstrip() for line in proc.stdout.splitlines()) + "\n")
    (HERE / "build.stderr.txt").write_text(proc.stderr)
    binary = BUILD / "wdsat_solver"
    assert proc.returncode == 0 and binary.exists(), proc.stderr[-2000:]
    receipt = {"proposal_id": "Q1507", "candidate_id": None,
               "source_sha256": sha(Path(__file__)),
               "parent_source_sha256": sha(source),
               "parent_build_receipt_sha256": sha(Q1488 / "build_receipt.json"),
               "order_manifest_sha256": sha(MANIFEST),
               "patched_source_sha256": sha(target),
               "patched_source_path": str(target),
               "binary_sha256": sha(binary), "binary_path": str(binary),
               "config_sha256": sha(BUILD / "src/config.h"),
               "compiler": subprocess.check_output(["gcc", "--version"],
                                                    text=True).splitlines()[0],
               "architecture": platform.machine(),
               "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
               "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
               "return_code": proc.returncode,
               "priorities": priorities()}
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")
    print("PASS Q1507 WDSat target-side priorities", sha(binary)[:12])


if __name__ == "__main__":
    main()
