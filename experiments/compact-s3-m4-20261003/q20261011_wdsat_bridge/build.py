#!/usr/bin/env python3
"""Build pinned WDSat with bounded static dimensions for Q1419 XCNF."""
from __future__ import annotations
import gzip
import hashlib
import json
import platform
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
UPSTREAM = Path("/private/tmp/wdsat-q1458")
TEMP = Path("/private/tmp/q1458_wdsat_build_v4")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def maxima(raw: bytes) -> dict:
    lines=raw.splitlines()
    header=lines[0].split()
    assert header[:2]==[b"p",b"cnf"]
    cnf=xor=cnf_occ=xor_occ=max_cnf=max_xor=0
    for line in lines[1:]:
        if not line or line.startswith(b"c"):continue
        terms=line.split()
        assert terms[-1]==b"0"
        if terms[0].startswith(b"x"):
            xor+=1;size=len(terms)-1;xor_occ+=size;max_xor=max(max_xor,size)
        else:
            cnf+=1;size=len(terms)-1;cnf_occ+=size;max_cnf=max(max_cnf,size)
    assert cnf+xor==int(header[3])
    return {"variables":int(header[2]),"cnf_clauses":cnf,"xor_rows":xor,
            "cnf_occurrences":cnf_occ,"xor_occurrences":xor_occ,
            "maximum_cnf_clause_length":max_cnf,
            "maximum_xor_row_length":max_xor}


def patch_quadratic_undo_storage(source: Path) -> dict:
    """Keep upstream undo semantics while allocating only populated rows."""
    header=source / "xorgauss.h"
    body=source / "xorgauss.c"
    h=header.read_text()
    c=body.read_text()
    def replace_once(text: str, old: str, new: str) -> str:
        assert text.count(old)==1,old
        return text.replace(old,new)
    h=replace_once(h,
        "extern int_t xorgauss_mask_list[__ID_SIZE__][__ID_SIZE__ + 1];",
        "extern int_t *xorgauss_mask_list[__ID_SIZE__];")
    c=replace_once(c,
        "int_t xorgauss_mask_list[__ID_SIZE__][__ID_SIZE__ + 1];\nint_t xorgauss_mask_list_top;",
        """int_t *xorgauss_mask_list[__ID_SIZE__];
int_t xorgauss_mask_list_top;
static size_t xorgauss_mask_list_capacity[__ID_SIZE__];
static void xorgauss_mask_list_ensure(int_t row, size_t need) {
    assert(row >= 0 && row < __ID_SIZE__);
    if (xorgauss_mask_list_capacity[row] >= need) return;
    size_t capacity = xorgauss_mask_list_capacity[row] ?
        xorgauss_mask_list_capacity[row] : 4;
    while (capacity < need) capacity *= 2;
    int_t *next = realloc(xorgauss_mask_list[row], capacity * sizeof(int_t));
    assert(next != NULL);
    xorgauss_mask_list[row] = next;
    xorgauss_mask_list_capacity[row] = capacity;
}""")
    c=replace_once(c,
        "xorgauss_mask_list[xorgauss_mask_list_top][1] = _uv; ///undo",
        "xorgauss_mask_list_ensure(xorgauss_mask_list_top, 3);\n\t\txorgauss_mask_list[xorgauss_mask_list_top][1] = _uv; ///undo")
    c=replace_once(c,
        "xorgauss_mask_list[xorgauss_mask_list_top][0] = 1; ///undo",
        "xorgauss_mask_list_ensure(xorgauss_mask_list_top, 2);\n\t\txorgauss_mask_list[xorgauss_mask_list_top][0] = 1; ///undo")
    c=replace_once(c,
        "xorgauss_mask_list[xorgauss_mask_list_top][xorgauss_mask_list[xorgauss_mask_list_top][0]++] = i; ///undo",
        "xorgauss_mask_list_ensure(xorgauss_mask_list_top, (size_t)xorgauss_mask_list[xorgauss_mask_list_top][0] + 1);\n\t\txorgauss_mask_list[xorgauss_mask_list_top][xorgauss_mask_list[xorgauss_mask_list_top][0]++] = i; ///undo")
    c=replace_once(c,
        "xorgauss_equivalent[xorgauss_reset[xorgauss_reset_top]] = false;\n\t}",
        "xorgauss_equivalent[xorgauss_reset[xorgauss_reset_top]] = false;\n\t\tfree(xorgauss_mask_list[xorgauss_mask_list_top]);\n\t\txorgauss_mask_list[xorgauss_mask_list_top] = NULL;\n\t\txorgauss_mask_list_capacity[xorgauss_mask_list_top] = 0;\n\t}")
    header.write_text(h)
    body.write_text(c)
    return {"xorgauss_h_sha256":sha(header),"xorgauss_c_sha256":sha(body),
            "patch_kind":"dynamic_per_row_undo_list_no_algorithm_change"}


def instrument_search(source: Path) -> dict:
    body=source / "wdsat.c"
    content=body.read_text()
    old="\tcpy_from_dimacs();\n"
    assert content.count(old)==1
    content=content.replace(old,old+'\tfprintf(stderr, "Q1458_AFTER_XOR_INIT\\n"); fflush(stderr);\n')
    old="\tif(xg == 0)\n\t{\n\t\tif (br_sym == 0)"
    assert content.count(old)==1
    content=content.replace(old,'\tfprintf(stderr, "Q1458_SEARCH_START\\n"); fflush(stderr);\n'+old)
    body.write_text(content)
    return {"wdsat_c_sha256":sha(body),"patch_kind":"stderr_phase_markers_only"}


def main() -> None:
    assert not TEMP.exists() and not (HERE / "build_receipt.json").exists()
    freeze=json.loads((HERE / "freeze.json").read_text())
    protocol=json.loads((HERE / "protocol.json").read_text())
    assert freeze["build_source_sha256"]==sha(Path(__file__))
    assert freeze["protocol_sha256"]==sha(HERE / "protocol.json")
    commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=UPSTREAM,text=True).strip()
    assert commit==freeze["upstream_commit"]==protocol["upstream_solver"]["commit"]
    assert not subprocess.check_output(["git","status","--porcelain"],cwd=UPSTREAM).strip()
    TEMP.mkdir()
    output={"proposal_id":"Q1458","candidate_id":None,"run_id":None,
            "freeze_sha256":sha(HERE / "freeze.json"),
            "upstream_commit":commit,
            "architecture":platform.machine(),"os":platform.platform(),
            "compiler":subprocess.check_output(["gcc","--version"],text=True).splitlines()[0],
            "per_degree":{},
            "initial_build_failure_sha256":sha(HERE / "build_attempt1.json")}
    for degree in ("n53","n83"):
        group=[name for name in protocol["cells"] if name.startswith(degree)]
        stats=[]
        for name in group:
            archive=PARENT / "q1419_partial_pin/runs" / name / "system.xcnf.gz"
            assert sha(archive)==freeze["cells"][name]["formula_archive_sha256"]
            raw=gzip.decompress(archive.read_bytes())
            assert hashlib.sha256(raw).hexdigest()==freeze["cells"][name]["formula_raw_sha256"]
            stats.append(maxima(raw))
        caps={"MAX_ID":max(item["variables"] for item in stats),
              "MAX_BUFFER_SIZE":max(item["cnf_occurrences"]+item["xor_occurrences"] for item in stats)+10000,
              "MAX_EQ":max(item["cnf_clauses"] for item in stats)+2,
              "MAX_EQ_SIZE":max(item["maximum_cnf_clause_length"] for item in stats)+2,
              "MAX_XEQ":max(item["xor_rows"] for item in stats)+2,
              "MAX_XEQ_SIZE":max(item["maximum_xor_row_length"] for item in stats)+2}
        dest=TEMP / degree
        shutil.copytree(UPSTREAM / "src",dest / "src")
        config=dest / "src/config.h"
        config.write_text("/* Q1458 generated CNF-XOR limits; XG-enhanced ANF disabled. */\n"+
            "\n".join(f"#define __{key}__ {value}" for key,value in caps.items())+"\n")
        patch=patch_quadratic_undo_storage(dest / "src")
        markers=instrument_search(dest / "src")
        make=subprocess.run(["make","-f","makefile"],cwd=dest / "src",
                            capture_output=True,text=True)
        (HERE / f"build_{degree}.stdout.txt").write_text(make.stdout)
        (HERE / f"build_{degree}.stderr.txt").write_text(make.stderr)
        assert make.returncode==0,make.stderr[-2000:]
        binary=dest / "wdsat_solver"
        assert binary.exists()
        output["per_degree"][degree]={"config":caps,"config_sha256":sha(config),
            "storage_patch":patch,
            "search_markers":markers,
            "binary_path":str(binary),"binary_sha256":sha(binary),
            "input_maxima":stats,"build_return_code":make.returncode,
            "build_stdout_sha256":sha(HERE / f"build_{degree}.stdout.txt"),
            "build_stderr_sha256":sha(HERE / f"build_{degree}.stderr.txt")}
    (HERE / "build_receipt.json").write_text(json.dumps(output,indent=2,sort_keys=True)+"\n")
    print("BUILT Q1458",[(n,v["binary_sha256"][:12]) for n,v in output["per_degree"].items()])


if __name__=="__main__":main()
