import subprocess,sys,time
def run(cmd):
    best=1e9
    for _ in range(7):
        t=time.perf_counter(); subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); best=min(best,time.perf_counter()-t)
    return best*1000
S=sys.argv[1]
for a in ['named','all','cjs']:
    o=run([S+'/esb',f'app/{a}.js','--minify',f'--outfile=out/ours/{a}.min.js'])
    e=run(['node_modules/.bin/esbuild',f'app/{a}.js','--bundle','--minify','--format=iife',f'--outfile=out/esb/{a}.min.js','--log-level=error'])
    print(f'{a:6} ours {o:7.1f} ms   esbuild {e:7.1f} ms   ratio {o/e:5.2f}x')
