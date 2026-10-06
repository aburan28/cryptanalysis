"""Run once per process so the cache's first-use cost is visible."""

import argparse
import importlib.util
import json
import random
import time
import tracemalloc


parser = argparse.ArgumentParser()
parser.add_argument('--field', required=True)
parser.add_argument('--trace-memory', action='store_true')
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('profile_field', args.field)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rng = random.Random(20260924)
if args.trace_memory:
    tracemalloc.start()
start = time.perf_counter_ns()
f = module.Onb(131)
init_ns = time.perf_counter_ns() - start
a = f.fromCoords(rng.getrandbits(131))
first_ns = {}
for k in (1, 2):
    start = time.perf_counter_ns()
    f.frob(a, k)
    first_ns[k] = time.perf_counter_ns() - start
peak = tracemalloc.get_traced_memory()[1] if args.trace_memory else None
print(json.dumps({'init_ns': init_ns, 'first_frob_ns': first_ns,
                  'peak_traced_bytes': peak}))
