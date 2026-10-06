"""Build, preflight and retain one frozen complete-query timing attempt."""
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
    runner={k:os.environ.get(k) for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','RUNNER_OS','RUNNER_ARCH')}
    runner.update(platform=platform.platform(),architecture=platform.machine(),python=sys.version,
                  git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  worktree_status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
    (out/'runner.json').write_text(json.dumps(runner,indent=2)+'\n')
    report={'status':'RUNNING','commands':[],'returncodes':[],'performance_claim':None}
    jobs=[('build',[str(HERE/'build.py')]),
          ('unit',['-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v']),
          ('controls',[str(HERE/'native_controls.py'),'--output',str(out/'controls.json.gz')]),
          ('preflight',[str(HERE/'preflight.py'),'--output',str(out/'preflight.json.gz')]),
          ('measure',[str(HERE/'measure.py'),'--preflight',str(out/'preflight.json.gz'),'--output',str(out/'panel')]),
          ('analysis',[str(HERE/'analyze.py'),'--input',str(out/'panel'),'--output',str(out/'analysis.json')])]
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
        for version in (62,):
            source=HERE.parent/f'round{version}/build'
            if source.exists():shutil.copytree(source,out/'native'/f'round{version}',symlinks=False)
        cache=HERE.parent.parent/'pdp-scaling/sumpoly_cache.pkl'
        if cache.exists():
            (out/'native/resources').mkdir(parents=True,exist_ok=True)
            shutil.copy2(cache,out/'native/resources'/cache.name)
        (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    subprocess.run([sys.executable,str(HERE/'audit.py'),'--evidence',str(out),
                    '--output',str(out/'independent-audit.json')],cwd=ROOT,check=True)
if __name__=='__main__':main()
