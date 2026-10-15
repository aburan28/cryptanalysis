#!/usr/bin/env python3
"""Change only the execution core after two preserved CPU-13 A/A failures."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
plan=json.loads((HERE/'tier1-affine-manifest.json').read_text())
rules=json.loads((HERE/'tier1-affine-rules.json').read_text())
assert plan['isolation']=={'cpus':'13','execution_cpu':13}
assert rules['execution_cpu']==13 and rules['service_cpu']==2
plan['isolation']={'cpus':'40','execution_cpu':40}
rules['execution_cpu']=40
rules['placement_reason']='new physical core 40 after both full CPU-13 panels failed one adjacent A/A gate; source, fixture, arm order and acceptance unchanged'
old='/workspace/isolated-bench/panels/tier1-affine-rules.json'
new='/workspace/isolated-bench/panels/tier1-affine-cpu40-rules.json'
assert old in plan['artifacts']
plan['artifacts']=[new if item==old else item for item in plan['artifacts']]
(HERE/'tier1-affine-cpu40-rules.json').write_text(json.dumps(rules,sort_keys=True,indent=2)+'\n')
(HERE/'tier1-affine-cpu40-manifest.json').write_text(json.dumps(plan,sort_keys=True,indent=2)+'\n')
