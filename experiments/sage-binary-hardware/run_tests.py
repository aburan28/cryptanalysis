"""Run selected backend correctness tests and retain an honest receipt."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import time
import unittest

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--backends',default='cpu')
parser.add_argument('--out',required=True,type=Path)
args=parser.parse_args()
args.out.mkdir(parents=True,exist_ok=False)
os.environ['SAGE_BINARY_BACKENDS']=args.backends
codec=list(HERE.glob('binary_hardware_codec*.so'))
if codec and os.environ.get('SAGE_BINARY_USE_INSTALLED')!='1': os.environ['SAGE_BINARY_CODEC']=str(codec[0])
from load_hardware import SOURCE, candidate, artifacts
suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_hardware.py')
stream=io.StringIO();start=time.perf_counter()
result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
(args.out/'tests.txt').write_text(stream.getvalue())
record=dict(backends=args.backends.split(','),platform=platform.platform(),
            tests_run=result.testsRun,errors=len(result.errors),failures=len(result.failures),
            skipped=len(result.skipped),successful=result.wasSuccessful(),
            elapsed_seconds=time.perf_counter()-start,
            source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            loaded_artifacts=artifacts(),
            tests_sha256=hashlib.sha256((HERE/'test_hardware.py').read_bytes()).hexdigest())
if result.wasSuccessful():
    from sage.all import GF,EllipticCurve
    E=EllipticCurve(GF(2**19,'z'),[1,1,0,0,1])
    devices={}
    for backend in record['backends']:
        with candidate.FrobeniusPlan(E,1,backend) as plan:
            assert plan.apply([E(0,1)])==[E(0,1)]
            devices[backend]={'name':plan.device_name,'codec':plan.codec,
                              'gpu_seconds':plan.last_gpu_seconds}
    record['devices']=devices
(args.out/'validation.json').write_text(json.dumps(record,indent=2)+'\n')
print(stream.getvalue());print(json.dumps(record,indent=2))
sys.exit(not result.wasSuccessful())
