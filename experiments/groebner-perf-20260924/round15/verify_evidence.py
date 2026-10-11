"""Check current source/evidence inventory and audit the retained measurements."""
import hashlib
import gzip
import json
from pathlib import Path

from audit import main

HERE = Path(__file__).resolve().parent


def verify():
    inventory = json.loads((HERE/'results/inventory.json').read_text())
    for name, expected in inventory.items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,name
    profile = HERE/'results/profile'
    receipt = json.loads(gzip.decompress((profile/'receipt.json.gz').read_bytes()))
    assert receipt['returncode']==receipt['sampler_returncode']==0 and receipt['failure'] is None
    assert receipt['script_sha256']==hashlib.sha256((profile/'profile_native_verifier.py').read_bytes()).hexdigest()
    for name, expected in receipt['ready']['source_sha256'].items():
        assert hashlib.sha256((HERE/'reference'/Path(name).name).read_bytes()).hexdigest()==expected
    child = json.loads((profile/'child-result.txt').read_text())
    assert child['status']=='VERIFIED' and child['certificate_calls']==457
    main()


if __name__=='__main__': verify()
