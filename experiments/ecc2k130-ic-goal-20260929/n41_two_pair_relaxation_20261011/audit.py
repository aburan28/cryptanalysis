"""Audit the N41 two-pair SAT controls, query receipts, and matrix logs."""

import gzip
import hashlib
import json
import tempfile
from pathlib import Path

import run

HERE=Path(__file__).resolve().parent

def main():
    p=run.protocol();f=run.fixture()
    control=json.loads((HERE/'control_result.json').read_text())
    assert control['status']=='PASS_FULL_N41_TWO_PAIR_RELAXED_ASSIGNMENT'
    assert control['protocol_sha256']==run.sha(HERE/'protocol.json')
    rows=[]
    for name,z in [('query_00',f['controls'][0]['target_z']),
                   ('query_01',f['controls'][1]['target_z']),
                   ('positive',f['known_positive']['target_z']),
                   ('matrix_positive',f['known_positive']['target_z'])]:
        receipt=json.loads((HERE/(name+'.json' if name!='positive' else
                                  'positive_result.json')).read_text())
        c,m,_=run.build(z)
        with tempfile.NamedTemporaryFile(prefix='n41_two_audit_',suffix='.xcnf',
                                         dir='/private/tmp') as stream:
            formula=Path(stream.name)
            c.write(formula)
            assert formula.stat().st_size==receipt['formula']['bytes']
            assert run.sha(formula)==receipt['formula']['sha256']
        stdout=gzip.decompress((HERE/(name+'.stdout.gz')).read_bytes())
        stderr=gzip.decompress((HERE/(name+'.stderr.gz')).read_bytes())
        assert hashlib.sha256(stdout).hexdigest()==receipt['stdout_sha256']
        assert hashlib.sha256(stderr).hexdigest()==receipt['stderr_sha256']
        assert receipt['status']=='BOUNDED_UNKNOWN'
        assert b's SATISFIABLE' not in stdout and b's UNSATISFIABLE' not in stdout
        assert receipt['peak_combined_rss_bytes']<run.RSS_CAP
        phases=receipt['phase_seconds']
        post=phases['total']-sum(phases[k] for k in ('construction','write_and_hash','solver'))
        assert post>=-0.01
        row={'name':name,'status':receipt['status'],
             'formula_sha256':receipt['formula']['sha256'],
             'solver_seconds':phases['solver'],
             'post_solver_log_capture_seconds':post,
             'peak_combined_rss_bytes':receipt['peak_combined_rss_bytes']}
        if name=='matrix_positive':
            matrix_protocol=json.loads((HERE/'matrix_protocol.json').read_text())
            assert matrix_protocol['status']=='FROZEN_N41_TWO_PAIR_WIDER_XOR_MATRIX_PROBE'
            assert '--maxmatrixcols=3500' in matrix_protocol['solver_flags']
            assert b'989 x 2768' in stdout and b'Using 1 matrices' in stdout
            row['wide_matrix_989x2768_used']=True
        rows.append(row)
    assert rows[0]['formula_sha256']!=rows[1]['formula_sha256']
    assert rows[2]['formula_sha256']==rows[3]['formula_sha256']
    result={'status':'AUDITED_N41_TWO_PAIR_RELAXED_BOUNDED_QUERIES',
            'source_lock_verified':True,'formulas_rebuilt_exactly':True,
            'logs_verified':True,'rows':rows,
            'sha256':{'protocol.json':run.sha(HERE/'protocol.json'),
                      'matrix_protocol.json':run.sha(HERE/'matrix_protocol.json'),
                      'audit.py':run.sha(HERE/'audit.py')}}
    run.save(HERE/'audit.json',result)
    print(json.dumps({'status':result['status'],
                      'rows':[(row['name'],row['status']) for row in rows]}))

if __name__=='__main__':main()
