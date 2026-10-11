"""Verify tracked correctness evidence, pinned proof generation and admission."""
import gzip
import hashlib
import json
from pathlib import Path
import subprocess

from build import generated_sources
from audit import audit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    inventory = json.loads((HERE/'results/inventory.json').read_text())
    for name,digest in inventory.items():
        path = (HERE/name).resolve()
        assert path.is_relative_to(ROOT) and hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
    subprocess.run(['git','ls-files','--error-unmatch',*[str((HERE/name).relative_to(ROOT)) for name in inventory]],
                   cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
    receipt = json.loads((HERE/'results/build-receipt.json').read_text())
    for name,digest in receipt['source_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    assert receipt['generated_sha256']=={k:hashlib.sha256(v.encode()).hexdigest() for k,v in generated_sources().items()}
    for filename in ('device-optimized.log','device-ubsan.log'):
        text = (HERE/'results'/filename).read_text()
        assert 'PASS cases=40 partial_words=26315144 truth_words=26315144 root_words=148248 device=Apple M4 Pro' in text
    for filename in ('integration-final.log','contract-metadata-final.log','journal-metadata-final.log'):
        text = (HERE/'results'/filename).read_text()
        assert '\nOK\n' in text and '\nFAILED' not in text,filename
    admission = json.loads((HERE/'results/local-paired.json.gz.admission.json').read_text())
    assert not admission['admitted'] and admission['timed_attempts']==0
    assert admission['load'][0] > admission['logical_cpus']*admission['max_load_per_cpu']
    assert not (HERE/'results/local-paired.json.gz').exists()
    report = json.loads(gzip.decompress((HERE/'results/correctness.json.gz').read_bytes()))
    assert report['correctness_only']
    for filename in ('benchmark.py','audit.py','compare_query.py','coefficient_query.py','journal.py'):
        source = HERE/filename
        assert report['source_sha256'][str(source.relative_to(ROOT))] == hashlib.sha256(source.read_bytes()).hexdigest(),filename
    summary = audit(HERE/'results/correctness.json.gz')
    assert sum(summary['statuses'].values()) == 192
    expected = json.loads((HERE/'results/correctness-audit.json').read_text())
    assert {k:v for k,v in summary.items() if k!='report'} == {k:v for k,v in expected.items() if k!='report'}
    assert not summary['timing_admission_eligible'] and all(c['all_attempts_verified'] for c in summary['controls'])
    print(json.dumps({'artifacts':len(inventory),'device_cases':80,'complete_trace_queries':192,
                      'correctness_verified':True,'performance_eligible':False},indent=2))


if __name__=='__main__': main()
