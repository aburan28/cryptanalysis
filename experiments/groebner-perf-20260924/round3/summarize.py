"""Derived summaries; raw warmups, failures and individual timings remain intact."""
import hashlib
import json
import math
from pathlib import Path
import random
import statistics

HERE = Path(__file__).resolve().parent
results = HERE/'results'
cert = json.loads((results/'certificate-benchmark.json').read_text())
gpu = json.loads((results/'gpu-tiled.json').read_text())
queries = json.loads((results/'query-check.json').read_text())
packing = json.loads((results/'packing-benchmark.json').read_text())
summary = {'scope': 'Verifier, internal Macaulay matrix, and planted PDP phase diagnostics',
           'complete_dlp_cost': None, 'natural_relation_yield': None,
           'verifier': [{k:v for k,v in c.items() if k != 'samples'} for c in cert['cells']],
           'gpu_checked_matrices': gpu['checked_matrices'], 'gpu_cells': [],
           'query_cells': [], 'packing_cells': []}
for c in gpu['cells']:
    measured = [s for s in c['samples'] if not s['warmup']]
    logs = [math.log(s['cpu_ms']/s['gpu_wall_ms']) for s in measured]
    rng = random.Random(2026092407)
    bootstrap = sorted(math.exp(statistics.mean(rng.choices(logs,k=len(logs)))) for _ in range(10000))
    summary['gpu_cells'].append({k:v for k,v in c.items() if k != 'samples'} | {
        'paired_geomean_speedup': math.exp(statistics.mean(logs)),
        'paired_bootstrap_95pct': [bootstrap[250],bootstrap[9749]],
        'charged_ms_including_warmups': {arm: sum(s[arm] for s in c['samples']) for arm in ('cpu_ms','gpu_wall_ms')}})
for seed in sorted({q['seed'] for q in queries['queries']}):
    rows = [q for q in queries['queries'] if q['seed'] == seed]
    measured = [q for q in rows if q['repetition'] != 0]
    summary['query_cells'].append({'seed': seed, 'fresh_query_count': len(rows),
                                  'first_query_ns': rows[0]['query_ns'],
                                  'subsequent_query_median_ns': statistics.median(q['query_ns'] for q in measured),
                                  'charged_query_ns': sum(q['query_ns'] for q in rows),
                                  'instance_setup_ns': rows[0]['instance_setup_ns'],
                                  'all_original_equation_and_curve_checks_pass': all(q['result']['verified'] for q in rows)})
for c in packing['cells']:
    summary['packing_cells'].append({'name': c['name'], 'median_ns': c['median_ns'],
                                    'ratio_of_medians': c['median_ns']['list']/c['median_ns']['array']})
summary['uncertainty'] = 'Paired bootstraps over repeated calls on a shared host; five GPU samples per cell; captured batches reuse two inputs and are not independent new target queries'
(results/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
# Check every frozen measurement receipt against its referenced artifact.
for name, key in [('certificate-benchmark.json','sha256'), ('gpu-run.json','source_sha256'),
                  ('query-check.json','sha256'), ('packing-benchmark.json','sha256')]:
    data = json.loads((results/name).read_text())
    for file,digest in data[key].items():
        assert hashlib.sha256(Path(file).read_bytes()).hexdigest() == digest, (name,file)
assert hashlib.sha256((HERE/'build/boolean-certificate-ubsan.dylib').read_bytes()).hexdigest() == json.loads((results/'validation-ubsan.json').read_text())['library_sha256']
manifest = {str(p.relative_to(HERE)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(HERE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts
            and p.name != 'artifact-manifest.json'}
(results/'artifact-manifest.json').write_text(json.dumps({'status':'PASS','sha256':manifest},indent=2)+'\n')
print(json.dumps({'query':summary['query_cells'],'packing':summary['packing_cells']},indent=2))
print('All measurement source/binary/input hashes match the current referenced artifacts.')
