"""Rebuild and archive local or CI evidence for the column-index experiment."""
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
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    runner={k:os.environ.get(k) for k in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','RUNNER_OS','RUNNER_ARCH')}
    runner.update(platform=platform.platform(),architecture=platform.machine(),python=sys.version,
                  git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  worktree_status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
    (out/'runner.json').write_text(json.dumps(runner,indent=2)+'\n')
    report={'status':'RUNNING','commands':[],'returncodes':[],'timing_eligible':False}
    jobs=[('build',[str(HERE/'build.py')]),
          ('unit',['-m','unittest','discover','-s',str(HERE),'-p','test_*.py','-v']),
          ('screen',[str(HERE/'validate.py'),'--out',str(out/'screen.json.gz')])]
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
        if (HERE/'build').exists():shutil.copytree(HERE/'build',out/'native/round58',symlinks=False)
        (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    subprocess.run([sys.executable,str(HERE/'audit.py'),'--evidence',str(out),
                    '--output',str(out/'independent-audit.json')],cwd=ROOT,check=True)
if __name__=='__main__':main()
