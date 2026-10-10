"""Rebuild the archived experiment with CUDA 13.3.73, without running GPU code."""
import argparse,hashlib,json,subprocess,tarfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--nvcc',default='/usr/local/cuda-13.3/bin/nvcc')
    p.add_argument('--inverse-only',action='store_true',help='Compile the bounded inverse probe instead of the walk; still execute no GPU code')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    m=json.loads((HERE/'snapshot-manifest.json').read_text())
    archive=HERE/'source-snapshot.tar.gz'
    if sha(archive)!=m['archive_sha256']:raise RuntimeError('Source archive checksum differs')
    source=out/'source';source.mkdir()
    with tarfile.open(archive) as t:
        for member in t.getmembers():
            if not member.isfile() or Path(member.name).is_absolute() or '..' in Path(member.name).parts:
                raise RuntimeError('Unsafe source archive entry')
            blob=t.extractfile(member).read();target=source/member.name
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(blob)
    for name,digest in m['source_files'].items():
        if sha(source/name)!=digest:raise RuntimeError('Source checksum differs: '+name)
    compiler=subprocess.check_output([a.nvcc,'--version'],text=True)
    if 'V13.3.73' not in compiler:raise RuntimeError('Exact reproduction requires CUDA 13.3.73')
    if a.inverse_only:
        target=source/'research/rtx5090-structural/test_small_blocks_inverse.cu'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((HERE/'test_small_blocks_inverse.cu').read_bytes())
    results=dict(compiler=compiler,profiles={},gpu_kernels_launched=False)
    for label,row in m['profiles'].items():
        command=list(row['command']);command[0]=a.nvcc
        if a.inverse_only:
            command[command.index('src/main.cu')]=str(target)
            command[command.index('-o')+1]='inverse-'+label
        r=subprocess.run(command,cwd=source,capture_output=True,text=True,timeout=600)
        raw=r.stdout+r.stderr;(out/(label+'-build.log')).write_text(raw)
        result=dict(exit=r.returncode,command=command,performance_b=None,gpu_correctness=None)
        if r.returncode==0:
            binary=source/command[command.index('-o')+1]
            result['binary_sha256']=sha(binary);lines=raw.splitlines()
            result['walk_resources']=next((lines[i:i+6] for i,s in enumerate(lines)
                if "Compiling entry function '_ZN12eccPacked1314walk" in s),[])
        else:result['error_tail']=raw[-1500:]
        results['profiles'][label]=result
        (out/'build-results.json').write_text(json.dumps(results,indent=2)+'\n')
    return 0 if all(r['exit']==0 for r in results['profiles'].values()) else 1
if __name__=='__main__':raise SystemExit(main())
