#!/usr/bin/env python3
"""Add frozen target-midpoint prefix modes to the Q1507 N83 WDSat source."""
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1507 = PARENT / "q20261012_n83_target_mid_priority"
ORDER = PARENT / "q20261011_wdsat_order/order_manifest.json"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1510_target_prefix")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def priorities():
    source = json.loads(ORDER.read_text())["cells"]["n83"]
    selectors = source["selector_priority"]
    mids = source["pair_mid_first_ids"]
    leaves = source["interleaved_leaves_priority"]
    assert len(selectors) == 2 and len(mids) == 166 and len(leaves) == 332
    first = [leaves[4*i+j] for i in range(83) for j in (2,3)]
    second = [leaves[4*i+j] for i in range(83) for j in (0,1)]
    assert first == [v for i in range(83) for v in (168+i, 251+i)]
    assert second == [v for i in range(83) for v in (2+i, 85+i)]
    result = {}
    for k in (0, 4, 16, 64, 83):
        values = selectors + mids[83:83+k] + first + second
        assert len(values) == len(set(values)) == 334+k
        result[f"q1510_tmid{k}"] = values
    assert result["q1510_tmid0"] == json.loads(
        (Q1507 / "build_receipt.json").read_text())["priorities"]["q1507_target_leaf_first"]
    return result


def main():
    protocol = json.loads((HERE / "protocol.json").read_text())
    parent = json.loads((Q1507 / "build_receipt.json").read_text())
    source = Path(parent["patched_source_path"])
    assert sha(source) == parent["patched_source_sha256"]
    assert sha(ORDER) == protocol["source_sha256"]["order_manifest"]
    assert sha(Q1507 / "build_receipt.json") == protocol["source_sha256"]["q1507_build"]
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    BUILD.mkdir()
    shutil.copytree(source.parent, BUILD / "src")
    target = BUILD / "src/wdsat.c"
    data = target.read_text()
    decl, cases = "", ""
    for name, values in priorities().items():
        decl += f"static const int_t {name}[] = {{" + ", ".join(map(str, values)) + "};\n"
        cases += (f'    if (mode && strcmp(mode, "{name}") == 0) {{\n'
                  f"        priority = {name};\n"
                  f"        length = sizeof({name}) / sizeof({name}[0]);\n"
                  "    } else\n")
    anchor = "static unsigned char q1469_seen[__ID_SIZE__];"
    anchor2 = '    if (mode && strcmp(mode, "q1478_leafpair_first") == 0) {'
    assert data.count(anchor) == data.count(anchor2) == 1
    data = data.replace(anchor, decl + anchor)
    data = data.replace(anchor2, cases + anchor2)
    target.write_text(data)
    proc = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                          text=True, capture_output=True)
    (HERE / "build.stdout.txt").write_text(
        "\n".join(line.rstrip() for line in proc.stdout.splitlines()) + "\n")
    (HERE / "build.stderr.txt").write_text(proc.stderr)
    binary = BUILD / "wdsat_solver"
    assert proc.returncode == 0 and binary.exists(), proc.stderr[-2000:]
    receipt = {"proposal_id": "Q1510", "candidate_id": None,
               "source_sha256": sha(Path(__file__)),
               "parent_build_receipt_sha256": sha(Q1507 / "build_receipt.json"),
               "parent_source_sha256": sha(source),
               "patched_source_sha256": sha(target),
               "patched_source_path": str(target),
               "order_manifest_sha256": sha(ORDER),
               "binary_sha256": sha(binary), "binary_path": str(binary),
               "config_sha256": sha(BUILD / "src/config.h"),
               "compiler": subprocess.check_output(["gcc", "--version"],
                                                    text=True).splitlines()[0],
               "architecture": platform.machine(),
               "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
               "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
               "return_code": proc.returncode, "priorities": priorities()}
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                         sort_keys=True) + "\n")
    print("PASS Q1510 target-prefix modes", sha(binary)[:12])


if __name__ == "__main__":
    main()
