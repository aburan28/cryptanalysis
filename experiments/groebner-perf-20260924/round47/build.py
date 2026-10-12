"""Build a standalone checker prototype; the accepted producer is unchanged."""
import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
out=HERE/'build';out.mkdir(exist_ok=True)
compiler=os.environ.get('CXX','clang++')
shared=['-dynamiclib'] if sys.platform=='darwin' else ['-shared','-fPIC']
suffix='.dylib' if sys.platform=='darwin' else '.so'
variants={'': ['-O3'], '-ubsan': ['-O1','-g','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'], '-transform-audit':['-O2','-DCHECKER_TRANSFORM_AUDIT=1','-fsanitize=undefined','-fsanitize-undefined-trap-on-error','-fno-sanitize-recover=all'], '-budget':['-O2','-DBRANCH_CHECK_ENUMERATION_BUDGET=8'], '-partial-budget':['-O2','-DPARTIAL_CHECK_WORK_BUDGET=8'], '-symmetry-budget':['-O2','-DSYMMETRY_CHECK_WORK_BUDGET=8'], '-symmetry-workspace':['-O2','-DSYMMETRY_CHECK_AUX_BYTES=0'], '-symmetry-late-budget':['-O2','-DSYMMETRY_CHECK_WORK_BUDGET=60']}
commands=[];binaries={}
for tag,flags in variants.items():
 path=out/('checker'+tag+suffix)
 command=[compiler,'-std=c++17','-Wall','-Wextra','-Werror','-pthread',*shared,*flags,str(HERE/'checker.cpp'),'-o',str(path)]
 subprocess.run(command,check=True);commands.append(command);binaries[path.name]=hashlib.sha256(path.read_bytes()).hexdigest();print('built',path.name,flush=True)
original=HERE.parent
sources=list(HERE.glob('*.py'))+list(HERE.glob('*.cpp'))+list(HERE.glob('*.h'))
sources += [original/f'round{v}/abi.h' for v in (31,32,33,34,35,36,37,38,44,45)]
for version in (17,20,23,27,31,32,33,34,35,36,37,38,42,43,44,45):
 sources += list((original/f'round{version}').glob('*.py'))
(out/'receipt.json').write_text(json.dumps({'commands':commands,'binaries':binaries,'compiler':subprocess.check_output([compiler,'--version'],text=True),'architecture':platform.machine(),'platform':platform.platform(),'sources':{str(p.relative_to(HERE.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}},indent=2)+'\n')
