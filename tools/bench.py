#!/usr/bin/env python3
# usage: bench.py BIN-DIR: our --minify against esbuild's, best of seven, in tests/.
import os,subprocess,sys,time
def run(cmd):
    best=1e9
    for _ in range(7):
        t=time.perf_counter(); subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); best=min(best,time.perf_counter()-t)
    return best*1000
S=os.path.abspath(sys.argv[1])
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests"))
for a in ['named','all','cjs']:
    o=run([S+'/esb',f'apps/{a}.js','--minify',f'--outfile=../out/ours/{a}.min.js'])
    e=run(['node_modules/.bin/esbuild',f'apps/{a}.js','--bundle','--minify','--format=iife',f'--outfile=../out/esb/{a}.min.js','--log-level=error'])
    print(f'{a:6} ours {o:7.1f} ms   esbuild {e:7.1f} ms   ratio {o/e:5.2f}x')
