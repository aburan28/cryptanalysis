"""Freeze plain-text right-middle targets from the checked N41 fixture."""

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'n41_two_pair_relaxation_20261011/targets.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    f=json.loads(SOURCE.read_text())
    assert f['status']=='PASS_N41_TARGET_DERIVED_TWO_PAIR_FIXTURES'
    rows=[('positive',*f['known_positive']['right_middle_point'])]
    rows += [('control_'+str(i),*r['right_middle_point'])
             for i,r in enumerate(f['controls'])]
    assert len(rows)==9
    target=HERE/'targets.txt'
    target.write_text(str(len(rows))+'\n'+''.join('%s %d %d\n'%row for row in rows))
    receipt={'status':'FROZEN_N41_RIGHT_MIDDLE_TARGET_INPUT',
             'rows':rows,'source_sha256':sha(SOURCE),
             'producer_sha256':sha(HERE/'make_input.py'),
             'input_sha256':sha(target)}
    (HERE/'input_manifest.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':receipt['status'],'rows':len(rows)}))
if __name__=='__main__':main()
