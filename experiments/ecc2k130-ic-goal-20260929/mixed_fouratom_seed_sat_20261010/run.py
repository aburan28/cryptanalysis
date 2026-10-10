#!/usr/bin/env python3
"""Bounded CryptoMiniSat search with four masks and seed unpinned."""

import hashlib
import json
import subprocess
import time
from pathlib import Path
import psutil

here=Path(__file__).resolve().parent
root=here.parent
field_path=root.parent/"koblitz-polynomial-w-pair-20260925/pair_oracle.py"
circuit_base_path=root.parent/"koblitz-polynomial-w-pair-20260925/karatsuba_circuit.py"
method_path=here/"circuit.py"
mixed=root/"n131_w14_mixed_rotation_fouratom_join_20261010/inputs.json"
w6=root/"n41_upper_xor_projection_20261010/w6_input.txt"
solver=Path("/opt/homebrew/bin/cryptominisat5")
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
protocol=json.loads((here/"protocol.json").read_text())
assert protocol["status"]=="FROZEN_BEFORE_UNPINNED_SEED_N41_SAT"
sources={"circuit.py":method_path,"freeze.py":here/"freeze.py",
         "run.py":here/"run.py","field_source":field_path,
         "circuit_base":circuit_base_path,
         "mixed_inputs":mixed,"w6_input":w6,"solver":solver}
assert protocol["source_sha256"]=={name:sha(path) for name,path in sources.items()}
rows=[]
for case in protocol["case_order"]:
    formula=here/f"n41_{case}.xcnf"
    assert sha(formula)==protocol["cases"][case]["formula_sha256"]
    command=[str(solver),*protocol["solver_flags"],str(formula)]
    started=time.monotonic_ns()
    stdout_path=here/f"n41_{case}.solver.stdout.txt"
    stderr_path=here/f"n41_{case}.solver.stderr.txt"
    peak_rss=0
    with stdout_path.open("w") as out,stderr_path.open("w") as err:
        process=subprocess.Popen(command,stdout=out,stderr=err)
        observed=psutil.Process(process.pid)
        status="EXITED"
        while process.poll() is None:
            try:peak_rss=max(peak_rss,observed.memory_info().rss)
            except psutil.NoSuchProcess:pass
            if peak_rss>protocol["rss_cap_bytes"]:
                status="OOM";process.kill();break
            if time.monotonic_ns()-started>=protocol["parent_cap_seconds_per_case"]*10**9:
                status="CENSORED_TIME";process.kill();break
            time.sleep(0.05)
        code=process.wait()
    stdout=stdout_path.read_text()
    stderr=stderr_path.read_text()
    wall=time.monotonic_ns()-started
    sat="s SATISFIABLE" in stdout
    unsat="s UNSATISFIABLE" in stdout
    if sat:status="SAT"
    elif unsat:status="UNSAT"
    elif status=="EXITED":status="EXITED_WITHOUT_STATUS"
    rows.append({"case":case,"status":status,"returncode":code,
                 "parent_wall_ns":wall,"peak_solver_rss_bytes":peak_rss,
                 "formula_sha256":sha(formula),
                 "solver_stdout_sha256":sha(here/f"n41_{case}.solver.stdout.txt"),
                 "solver_stderr_sha256":sha(here/f"n41_{case}.solver.stderr.txt"),
                 "model_literal_count":sum(len(line.split())-1 for line in stdout.splitlines()
                                           if line.startswith("v "))})
    (here/"result.json").write_text(json.dumps({"rows":rows,
        "protocol_sha256":sha(here/"protocol.json")},indent=2,sort_keys=True)+"\n")
    print(json.dumps({"case":case,"status":status,"wall_s":wall/1e9,
                      "model_literals":rows[-1]["model_literal_count"]},sort_keys=True),flush=True)
