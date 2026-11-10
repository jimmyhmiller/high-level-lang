#!/usr/bin/env python3
"""Fresh-process bundler comparison, with emitted code checked in Chrome before ranking it.

Install pinned adapters: npm ci --prefix benchmarks/bundlers
Run: python3 tools/compare-bundlers.py --runs=5
No watch, persistent cache, cross-build state or source maps. OS file caches are not flushed.
"""
import argparse
import gzip
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import threading
import time
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--runs', type=int, default=5)
parser.add_argument('--cases', default='large,real,mixed')
parser.add_argument('--tools', default='')
parser.add_argument('--report-name', default='results')
parser.add_argument('--plain-only', action='store_true')
parser.add_argument('--turbopack', default=str(ROOT/'out/bin/turbopack-cli-4ebb2b7'))
parser.add_argument('--binary', default=str(ROOT/'out/bin/esb'), help='our executable; use an explicitly built release binary to compare optimization levels')
args = parser.parse_args()
assert args.runs > 0
WORK = ROOT/'out/bundler-comparison'
WORK.mkdir(parents=True, exist_ok=True)
comparison_lock = (WORK/'.benchmark.lock').open('w')
try: fcntl.flock(comparison_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError: raise SystemExit('Another comparison is running; timing runs must be sequential.')
ADAPTER = ROOT/'benchmarks/bundlers/build.mjs'
TP = Path(args.turbopack)
BINARY = Path(args.binary).resolve()
TOOLS = [f'ours-{policy}-{unit}' for policy in ['exact','package','balanced'] for unit in ['modules','fragments']] + ['esbuild','rolldown','rollup','webpack']
if TP.exists(): TOOLS += ['turbopack']
if args.tools: TOOLS = [tool for tool in TOOLS if tool in args.tools.split(',')]
assert TOOLS
metadata = dict(runs=args.runs, node=subprocess.check_output(['node','--version'],text=True).strip(),
                system=subprocess.check_output(['sw_vers'],text=True).strip(),
                machine=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
                head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                turbopack=str(TP), turbopack_revision='4ebb2b7a5b' if '4ebb2b7' in TP.name else None,
                persistent_cache=False, cross_build_reuse=False, filesystem_cache_flushed=False,
                layout='one bootstrap with independently invoked dynamic report roots')
metadata['binary_sha256']={str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in [BINARY,TP] if path.exists()}
metadata['versions'] = {'esbuild': json.loads((ROOT/'tests/node_modules/esbuild/package.json').read_text())['version']}
for package in ['rolldown','rollup','webpack','@rollup/plugin-node-resolve','@rollup/plugin-commonjs','@rollup/plugin-terser']:
    metadata['versions'][package] = json.loads((ROOT/'benchmarks/bundlers/node_modules'/package/'package.json').read_text())['version']


def put(root, name, text):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)


def prepare(case):
    root=WORK/'fixtures'/case
    shutil.rmtree(root,ignore_errors=True);root.mkdir(parents=True)
    put(root,'package.json','{"type":"module","private":true}')
    if case=='large':
        source=ROOT/'out/application-scale'
        assert (source/'shared/config.js').exists(), 'First run tools/scale-check.py --effects to generate the source fixture'
        shutil.copytree(source/'features',root/'features')
        shutil.copytree(source/'shared',root/'shared')
        entries=[f'report-{i}.js' for i in range(32)]
        for name in entries: shutil.copyfile(source/name,root/name)
        for i,name in enumerate(entries):
            put(root,f'driver-{i}.js',f'import {{run}} from "./{name}";import {{record}} from "./record.js";record({i},run({{priority:3,budget:42000}}));')
        count=32
    elif case=='real':
        shutil.copytree(ROOT/'tests/node_modules',root/'node_modules',copy_function=os.link)
        for name in ['real1.js','real2.js','real-dyn.js']:
            shutil.copyfile(ROOT/'tests/apps/split'/name,root/name)
        count=2
        for i,name in enumerate(['real1.js','real2.js']):
            put(root,f'driver-{i}.js',f'import "./{name}";import {{record}} from "./record.js";record({i},true);')
    elif case=='mixed':
        count=2
        put(root,'library.js','globalThis.__mixed_init=(globalThis.__mixed_init||0)+1;\n'+'\n'.join(
            f'const config{i}={{name:"CONFIG_{i}",values:[{i},{i+1}]}};export class C{i} {{value={i};get(){{return this.value;}}}}export function f{i}(x){{return x+config{i}.values[0]+new C{i}().get();}}' for i in range(300)))
        for parity in [0,1]:
            names=[f'f{i}' for i in range(parity,300,2)]
            put(root,f'driver-{parity}.js','import {'+','.join(names)+'} from "./library.js";import {record} from "./record.js";record('+str(parity)+','+'+'.join(f'{name}(1)' for name in names)+');')
    else: raise ValueError(case)
    put(root,'record.js','globalThis.__bench_results=globalThis.__bench_results||{};export function record(id,value){globalThis.__bench_results[id]=value;}')
    loaders=','.join(f'()=>import("./driver-{i}.js")' for i in range(count))
    put(root,'main.js',f'const loaders=[{loaders}];globalThis.__bench_load=(index)=>loaders[index]();')
    runner='const logs=[];console.log=(...args)=>logs.push(args.map(String).join(" "));for(const file of process.argv.slice(1))await import(file);process.stdout.write(JSON.stringify({values:{results:globalThis.__bench_results,scaleInit:globalThis.scaleInitializations||0,mixedInit:globalThis.__mixed_init||0},logs:logs.sort()}));'
    original=subprocess.run(['node','--input-type=module','-e',runner,*[(root/f'driver-{i}.js').as_uri() for i in range(count)]],capture_output=True,text=True,timeout=120)
    assert original.returncode==0,original.stderr
    expected=root/'expected.json';expected.write_text(original.stdout)
    return root,count,expected


def command(tool, root, output, minify, config):
    if tool.startswith('ours-'):
        _,policy,unit=tool.split('-')
        return [str(BINARY),'main.js','--splitting','--format=esm','--pipeline=full','--no-cache','--strategy=once',f'--chunk-policy={policy}',f'--fragments={str(unit=="fragments").lower()}',f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='esbuild':
        return [str(ROOT/'tests/node_modules/.bin/esbuild'),'main.js','--bundle','--splitting','--format=esm','--platform=browser','--target=esnext','--log-level=warning',f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='turbopack':
        return [str(TP),'build','./main.js','--dir',str(root),'--target','browser','--no-sourcemap',*(['--no-minify'] if not minify else [])]
    config.write_text(json.dumps(dict(input={'main':str(root/'main.js')},output=str(output),minify=minify)))
    return ['node',str(ADAPTER),tool,str(config)]


def measure(cmd,cwd):
    # communicate() waits for completion directly; the RSS sampler never inserts a polling delay
    # into wall time. /usr/bin/time captures even short-lived native process high-water RSS.
    start=time.perf_counter()
    proc=subprocess.Popen(['/usr/bin/time','-l',*cmd],cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    stopped=threading.Event();peak=[0];killed=[None]
    def sample():
        while not stopped.is_set():
            peak[0]=max(peak[0],guard.group_rss_mb(proc.pid))
            if peak[0]>6000:
                killed[0]='aggregate RSS exceeded 6000 MiB'
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                break
            stopped.wait(.02)
    thread=threading.Thread(target=sample,daemon=True);thread.start()
    try: stdout,stderr=proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate();killed[0]='180-second timeout'
    except BaseException:
        try: os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError: pass
        proc.wait();stopped.set();thread.join();raise
    elapsed=time.perf_counter()-start
    stopped.set();thread.join()
    match=re.search(r'(\d+)\s+maximum resident set size',stderr)
    highwater=int(match[1])/1024**2 if match else 0
    if proc.returncode!=0 or killed[0]: raise RuntimeError(json.dumps(dict(code=proc.returncode,reason=killed[0],stdout=stdout[-2000:],stderr=stderr[-5000:])))
    return dict(seconds=elapsed,peak_mib=max(peak[0],highwater),main_process_peak_mib=highwater),stdout,stderr


def size_of(output,files):
    bodies=[(output/name).read_bytes() for name in files]
    return dict(bytes=sum(map(len,bodies)),gzip_bytes=sum(len(gzip.compress(body,mtime=0)) for body in bodies),files=len(bodies))


rows=[];samples=[]
report=WORK/(args.report_name+'.json')
def save(): report.write_text(json.dumps(dict(metadata=metadata,results=rows,samples=samples),indent=2)+'\n')
for case in args.cases.split(','):
    root,count,expected=prepare(case)
    print(json.dumps(dict(progress='fixture',case=case,roots=count)),flush=True)
    for minify in ([False] if args.plain_only else [False,True]):
        modes={};failed={}
        for tool in TOOLS:
            output=root/'dist' if tool=='turbopack' else WORK/'outputs'/case/('minified' if minify else 'plain')/tool
            config=WORK/f'{case}-{tool}-{minify}.json'
            cmd=command(tool,root,output,minify,config)
            modes[tool]=(output,cmd)
        # Rotate tool order each repetition. Each invocation gets a fresh process and clean output.
        for repeat in range(args.runs):
            ordered=TOOLS[repeat%len(TOOLS):]+TOOLS[:repeat%len(TOOLS)]
            for tool in ordered:
                if tool in failed: continue
                output,cmd=modes[tool]
                shutil.rmtree(output,ignore_errors=True)
                try:
                    measurement,stdout,stderr=measure(cmd,root)
                    assert list(output.rglob('*.js')), 'No emitted JS'
                    item=dict(case=case,minify=minify,tool=tool,repeat=repeat,**measurement)
                    samples.append(item)
                    (WORK/f'{case}-{minify}-{tool}-last-build.log').write_text(stdout+stderr)
                except Exception as error:
                    failed[tool]=str(error)
                    print(json.dumps(dict(progress='build-failed',case=case,minify=minify,tool=tool,error=str(error))),flush=True)
            print(json.dumps(dict(progress='round',case=case,minify=minify,round=repeat+1)),flush=True)
        for tool in TOOLS:
            output,cmd=modes[tool]
            row=dict(case=case,minify=minify,tool=tool,command=cmd)
            if tool in failed:
                row.update(status='build-failed',error=failed[tool]);rows.append(row);save();continue
            measurements=[item for item in samples if item['case']==case and item['minify']==minify and item['tool']==tool]
            row.update(runs=len(measurements),median_seconds=round(statistics.median(item['seconds'] for item in measurements),4),
                       min_seconds=round(min(item['seconds'] for item in measurements),4),max_seconds=round(max(item['seconds'] for item in measurements),4),
                       median_peak_mib=round(statistics.median(item['peak_mib'] for item in measurements),1),max_peak_mib=round(max(item['peak_mib'] for item in measurements),1))
            try:
                checked=subprocess.run(['node',str(ROOT/'benchmarks/bundlers/browser-check.mjs'),str(output),'turbopack' if tool=='turbopack' else 'esm',str(count),str(expected)],capture_output=True,text=True,timeout=120)
                assert checked.returncode==0,checked.stdout+checked.stderr
                browser=json.loads(checked.stdout)
                js=sorted(str(p.relative_to(output)) for p in output.rglob('*.js'))
                row.update(status='correct',total_js=size_of(output,js),first_route=size_of(output,browser['firstFiles']),all_loaded=size_of(output,browser['allLoadedFiles']))
                (WORK/f'{case}-{minify}-{tool}-browser.json').write_text(json.dumps(browser,indent=2))
            except Exception as error: row.update(status='incorrect-or-validation-failed',error=str(error))
            rows.append(row);save();print(json.dumps(row),flush=True)
save()
print('Comparison complete: '+str(report),flush=True)
