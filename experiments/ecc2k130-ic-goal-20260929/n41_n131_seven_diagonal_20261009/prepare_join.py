#!/usr/bin/env python3
"""Export frozen seven-block projected states for the native group join."""
import json
from pathlib import Path
import run_v2

here = Path(__file__).resolve().parent
context = run_v2.source.setup()
protocol = json.loads((here / "protocol_v2.json").read_text())
if list(context["public_q"]) != protocol["public_target_q"]:
    raise ValueError("public target drift")
rows = [f"{context['public_q'][0]} {context['public_q'][1]} 549756390943 7"]
for block in context["states"]:
    states = [state for mask in sorted(block) for state in block[mask]]
    if len(states) != 64:
        raise ValueError("wrong block size")
    rows.append("64")
    for state in states:
        x, y = state["projected"]
        rows.append(f"{x} {y} {state['column']} {state['mask']} {state['sign']}")
output = here / "join_input.txt"
if output.exists():
    raise FileExistsError(output)
output.write_text("\n".join(rows) + "\n")
print(json.dumps({"status": "EXPORTED", "sha256": run_v2.source.sha(output)}))
