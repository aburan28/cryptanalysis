#!/usr/bin/env python3
"""Compile the Q1481 leaf-only mask schedule into pinned Q1479 WDSat."""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
Q1479 = PARENT / "q20261011_n83_distinct_roots"
BUILD = Path("/Volumes/SSD990/llm/tmp/q1481_leaf_mask_build/n83")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch(source: Path, schedule: dict[str, dict]) -> str:
    path = source / "wdsat.c"
    data = path.read_text()
    anchor = "static int_t set[__ID_SIZE__];\n"
    assert data.count(anchor) == 1
    arrays = "\n".join(
        f"static const int_t q1481_mask_{i}[] = {{" +
        ", ".join(map(str, schedule[str(i)]["flip_ids"])) + "};"
        for i in range(1, 9))
    choices = "\n".join(
        f"    case {i}: flips = q1481_mask_{i}; "
        f"length = sizeof(q1481_mask_{i}) / sizeof(q1481_mask_{i}[0]); break;"
        for i in range(1, 9))
    definition = f'''

/* Q1481: flip only first-branch leaf signs after selector policy is set. */
{arrays}
static unsigned char q1481_mark[__ID_SIZE__];
static void q1481_apply_mask(int_t count) {{
    const char *raw = getenv("Q1481_LEAF_MASK");
    char *end = NULL;
    long phase = raw ? strtol(raw, &end, 10) : -1;
    if (!raw || !*raw || !end || *end || phase < 0 || phase > 8) {{
        fprintf(stderr, "Q1481_BAD_PHASE\\n"); fflush(stderr); exit(64);
    }}
    const int_t *flips = NULL;
    size_t length = 0;
    switch (phase) {{
    case 0: break;
{choices}
    default: exit(64);
    }}
    for (size_t i = 0; i < length; ++i) {{
        int_t variable = flips[i];
        if (variable < 2 || variable > 333 || variable > count ||
            q1481_mark[variable]) {{
            fprintf(stderr, "Q1481_BAD_LEAF_ID\\n"); fflush(stderr); exit(64);
        }}
        q1481_mark[variable] = 1;
    }}
    size_t changed = 0;
    for (int_t i = 0; i < count; ++i) {{
        int_t variable = set[i] < 0 ? -set[i] : set[i];
        if (q1481_mark[variable]) {{ set[i] = -set[i]; changed++; }}
    }}
    if (changed != length) {{
        fprintf(stderr, "Q1481_BAD_MASK_COUNT\\n"); fflush(stderr); exit(64);
    }}
    fprintf(stderr, "Q1481_MASK %ld %lld\\n", phase, (long long)length);
    fflush(stderr);
}}
'''
    data = data.replace(anchor, anchor + definition)
    call = "\t\tq1473_apply_selector(nb_min_vars);\n"
    assert data.count(call) == 1
    data = data.replace(call, call + "\t\tq1481_apply_mask(nb_min_vars);\n")
    path.write_text(data)
    return sha(path)


def main() -> None:
    assert not BUILD.exists() and not (HERE / "build_receipt.json").exists()
    frozen = json.loads((HERE / "freeze.json").read_text())
    parent = json.loads((Q1479 / "build_receipt.json").read_text())
    schedule = json.loads((HERE / "mask_schedule.json").read_text())
    assert frozen["files_sha256"]["build.py"] == sha(Path(__file__))
    assert frozen["mask_schedule_sha256"] == sha(HERE / "mask_schedule.json")
    assert frozen["q1479_build_sha256"] == sha(Q1479 / "build_receipt.json")
    src = Path(frozen["parent_source_dir"])
    assert sha(src / "wdsat.c") == frozen["parent_wdsat_c_sha256"] == parent[
        "patched_wdsat_c_sha256"]
    BUILD.mkdir(parents=True)
    shutil.copytree(src, BUILD / "src")
    modified = patch(BUILD / "src", schedule)
    process = subprocess.run(["make", "-f", "makefile"], cwd=BUILD / "src",
                             capture_output=True, text=True)
    (HERE / "build.stdout.txt").write_text(process.stdout)
    (HERE / "build.stderr.txt").write_text(process.stderr)
    binary = BUILD / "wdsat_solver"
    assert process.returncode == 0 and binary.exists(), process.stderr[-2000:]
    receipt = {"proposal_id": "Q1481", "candidate_id": None,
               "freeze_sha256": sha(HERE / "freeze.json"),
               "q1479_build_sha256": sha(Q1479 / "build_receipt.json"),
               "patched_wdsat_c_sha256": modified,
               "patched_source_path": str(BUILD / "src/wdsat.c"),
               "binary_path": str(binary), "binary_sha256": sha(binary),
               "config_sha256": sha(BUILD / "src/config.h"),
               "compiler": subprocess.check_output(["gcc", "--version"],
                                                    text=True).splitlines()[0],
               "architecture": platform.machine(), "os": platform.platform(),
               "return_code": process.returncode,
               "build_stdout_sha256": sha(HERE / "build.stdout.txt"),
               "build_stderr_sha256": sha(HERE / "build.stderr.txt"),
               "source_sha256": sha(Path(__file__))}
    (HERE / "build_receipt.json").write_text(json.dumps(receipt, indent=2,
                                                        sort_keys=True) + "\n")
    print("Q1481 built", receipt["binary_sha256"][:12])


if __name__ == "__main__":
    main()
