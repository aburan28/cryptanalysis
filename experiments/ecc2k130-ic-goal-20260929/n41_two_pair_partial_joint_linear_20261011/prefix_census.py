"""Count exact fixed-seed pair outputs sharing partial-coordinate prefixes."""

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("project", HERE / "project_n131.py")
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)
WIDTHS = (32,36)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze():
    p = {"status":"FROZEN_N131_PAIR_PREFIX_CENSUS","widths":list(WIDTHS),
         "limits":{"workers":1,"seconds":120,"rss_bytes":4294967296},
         "sha256":{"source":sha(__file__),
                   "project":sha(HERE/"project_n131.py"),
                   "table":sha(project.TABLE)}}
    (HERE/"prefix_protocol.json").write_text(json.dumps(p,indent=2,sort_keys=True)+"\n")
    print(p["status"])


def evaluate():
    p=json.loads((HERE/"prefix_protocol.json").read_text())
    assert p["sha256"]=={"source":sha(__file__),
                          "project":sha(HERE/"project_n131.py"),
                          "table":sha(project.TABLE)}
    rows=project.table_rows()
    start=time.monotonic_ns()
    counts={}
    for width in WIDTHS:
        left={c>>width for c,_,_ in rows}
        right={project.joint.frob(c,13)>>width for c,_,_ in rows}
        counts[str(width)]={"left_unique_prefixes":len(left),
                            "right_unique_prefixes":len(right),
                            "outputs":len(rows)}
        if time.monotonic_ns()-start>120_000_000_000:
            raise TimeoutError("frozen prefix census cap")
    out={"status":"COMPLETE_N131_PAIR_PREFIX_CENSUS",
         "counts":counts,"elapsed_ns":time.monotonic_ns()-start,
         "protocol_sha256":sha(HERE/"prefix_protocol.json")}
    (HERE/"prefix_result.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(out["status"],out["counts"],out["elapsed_ns"]/1e9)


if __name__=="__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in ("freeze","evaluate"):
        raise SystemExit("usage: prefix_census.py freeze|evaluate")
    (freeze if sys.argv[1]=="freeze" else evaluate)()
