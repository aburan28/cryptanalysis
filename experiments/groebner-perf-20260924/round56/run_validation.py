"""Rebuild and retain portable CPU correctness evidence for rounds 55 and 56."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    report={'status':'RUNNING','commands':[],'returncodes':[],'timing_eligible':False}
    runner={k:os.environ.get(k) for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','RUNNER_OS','RUNNER_ARCH')}
    runner.update(platform=platform.platform(),architecture=platform.machine(),python=sys.version,
                  git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  worktree_status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
    (out/'runner.json').write_text(json.dumps(runner,indent=2)+'\n')
    jobs=[]
    for version in (55,56):
        jobs.append((f'build-{version}',[str(HERE.parent/f'round{version}/build.py')]))
    for version in (55,56):
        jobs.append((f'unit-{version}',['-m','unittest','discover','-s',str(HERE.parent/f'round{version}'),'-p','test_*.py','-v']))
        jobs.append((f'screen-{version}',[str(HERE.parent/f'round{version}/screen.py'),'--output',str(out/f'round{version}-screen.json.gz')]))
    jobs += [('queries',[str(HERE/'validate_queries.py'),'--output',str(out/'queries.json.gz')]),
             ('probe-guards',[str(HERE.parent/'round55/validate_probe_guard.py'),'--output',str(out/'probe-guards.json')]),
             ('phases',[str(HERE.parent/'round55/profile_phases.py'),'--screen',str(out/'round55-screen.json.gz'),'--output',str(out/'phases')])]
    try:
        for name,arguments in jobs:
            command=[sys.executable,'-u',*arguments];report['commands'].append(command)
            with (out/(name+'.log')).open('x') as log:
                result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            report['returncodes'].append(result.returncode)
            (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
            result.check_returncode();print('PASS',name,flush=True)
        report['status']='PASS'
    except BaseException as error:
        report.update(status='FAIL',error=repr(error));raise
    finally:
        for version in (55,56):
            source=HERE.parent/f'round{version}/build'
            if source.exists(): shutil.copytree(source,out/'native'/f'round{version}',symlinks=False)
        (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    subprocess.run([sys.executable,str(HERE/'audit_evidence.py'),'--evidence',str(out),'--output',str(out/'independent-audit.json')],cwd=ROOT,check=True)
if __name__=='__main__': main()
