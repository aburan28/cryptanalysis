"""Opt-in native sparse F4, returning an independently checked derivation DAG."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

from algebraic_certificate import verify

HERE = Path(__file__).resolve().parent


def compute(nvars, equations, *, timeout=30, max_work=20_000_000,
            max_nodes=1_000_000, max_rows=10_000, batch=64, record=True,
            check=True, max_check_work=20_000_000, max_retained_terms=2_000_000,
            binary=None):
    if type(nvars) is not int or not 1 <= nvars <= 64:
        return {'status':'unsupported','complete':False,'verified':False,
                'reason':'native sparse monomial masks support 1..64 variables'}
    if not isinstance(equations,(tuple,list)) or len(equations)>4096:
        raise ValueError('equations must be a sequence of at most 4096 rows')
    if check and not record:
        raise ValueError('independent algebraic checking requires a derivation proof')
    if type(max_work) is not int or not 0 <= max_work < 1 << 64:
        raise ValueError('invalid native work limit')
    for value,limit in ((max_nodes,10_000_000),(max_rows,1_000_000),(batch,max_rows)):
        if type(value) is not int or not 1 <= value <= limit:
            raise ValueError('invalid native shape/node budget')
    binary = Path(binary or HERE/'build/native-f4').resolve()
    start = time.perf_counter()
    # Snapshot original input rows; the verifier gets these originals, never
    # rows transformed or normalized by the producer.
    originals = []
    for row in equations:
        if not isinstance(row,(tuple,list,set,frozenset)):
            raise ValueError('equation must be a finite term collection')
        copied = list(row)
        if any(type(mask) is not int or not 0 <= mask < 1 << nvars for mask in copied):
            raise ValueError('monomial outside the declared Boolean ring')
        originals.append(copied)
    text = f'{nvars} {len(originals)} {max_work} {max_nodes} {max_rows} {batch} {int(record)}\n'
    text += ''.join(f'{len(row)} {" ".join(map(str,row))}\n' for row in originals)
    preparation = time.perf_counter()-start
    launched = time.perf_counter()
    try:
        process = subprocess.run([str(binary)],input=text,text=True,capture_output=True,timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'status':'timeout','complete':False,'verified':False,
                'preparation_seconds':preparation,'total_seconds':time.perf_counter()-start}
    process_seconds = time.perf_counter()-launched
    parsed = time.perf_counter()
    try:
        result = json.loads(process.stdout)
    except (json.JSONDecodeError,UnicodeError):
        result = {'status':'producer-failure','stderr':process.stderr[-2000:]}
    parsing = time.perf_counter()-parsed
    result.update(complete=False,verified=False,returncode=process.returncode,
                  preparation_seconds=preparation,process_seconds=process_seconds,
                  parsing_seconds=parsing,verification_seconds=0,
                  algorithm='sparse-Boolean-F4-with-derivations',hard_subprocess_timeout=True)
    if result['status']=='gb' and process.returncode==0 and check:
        checked = time.perf_counter()
        certificate = verify(nvars,originals,result['basis'],result['proof'],
                             max_work=max_check_work,max_retained_terms=max_retained_terms)
        result['verification_seconds'] = time.perf_counter()-checked
        result['certificate'] = certificate
        result['verified'] = result['complete'] = certificate['verified']
        if not certificate['verified']:
            result['status'] = 'inconclusive' if certificate['status']=='inconclusive' else 'verification-failed'
    elif result['status']=='gb' and process.returncode!=0:
        result['status'] = 'producer-failure'
    result['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    result['total_seconds'] = time.perf_counter()-start
    return result
