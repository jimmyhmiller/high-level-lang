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
parser.add_argument('--minified-only', action='store_true')
parser.add_argument('--turbopack', default=str(ROOT/'out/bin/turbopack-cli-4ebb2b7'))
parser.add_argument('--binary', default=str(ROOT/'out/bin/esb'), help='our executable; use an explicitly built release binary to compare optimization levels')
args = parser.parse_args()
assert args.runs > 0
# `.noindex`: Spotlight skips it, so indexing the thousands of files a build writes does not load the
# machine while the next build is timed.
WORK = ROOT/'out/bundler-comparison.noindex'
WORK.mkdir(parents=True, exist_ok=True)
comparison_lock = (WORK/'.benchmark.lock').open('w')
try: fcntl.flock(comparison_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError: raise SystemExit('Another comparison is running; timing runs must be sequential.')
ADAPTER = ROOT/'benchmarks/bundlers/build.mjs'
TP = Path(args.turbopack)
BINARY = Path(args.binary).resolve()
TOOLS = [f'ours-{policy}-{unit}' for policy in ['exact','package','balanced'] for unit in ['modules','fragments']] + ['esbuild','bun','rolldown','rspack','rollup','webpack']
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
for package in ['rolldown','rollup','webpack','@rspack/core','@rollup/plugin-node-resolve','@rollup/plugin-commonjs','@rollup/plugin-terser','@rollup/plugin-replace']:
    metadata['versions'][package] = json.loads((ROOT/'benchmarks/bundlers/node_modules'/package/'package.json').read_text())['version']
metadata['versions']['bun'] = subprocess.check_output(['bun','--version'],text=True).strip()


# Real applications, built where they are, from their own sources and installed packages: the entry,
# what each bundler must be told beyond resolving packages (constants to substitute, which imports
# are files whose URL the code gets), and how Chrome checks the build: the element the app renders
# into, what a person does first, what the page must then show, and static files served beside the
# output. Turbopack's CLI takes no constants, so it builds none of them.
APPS = {
    # marmelab/react-admin's e-commerce demo (see benchmarks/react-admin-demo/README.md): React 19,
    # MUI, react-query, react-router, Apollo/GraphQL, echarts, faker data and an msw service worker.
    'react-admin': dict(
        dir=ROOT/'benchmarks/react-admin-demo', entry='src/index.tsx',
        define={'process.env.NODE_ENV': '"production"', 'process.env.REACT_APP_DATA_PROVIDER': '""',
                'import.meta.env.MODE': '"production"'},
        files=['.svg'], root='root', wait='Monthly Revenue',
        steps=[['fill', 'input[name=username]', 'demo'], ['fill', 'input[name=password]', 'demo'], ['click', 'button[type=submit]']],
        statics=['node_modules/msw/lib/mockServiceWorker.js']),
}


def put(root, name, text):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)


def prepare(case):
    if case in APPS:
        app=APPS[case]
        assert (app['dir']/'node_modules').exists(), f'First run npm ci in {app["dir"]}'
        return app['dir'],None,None
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
    elif case=='three10':
        # esbuild's JavaScript benchmark: ten copies of three.js's sources, every namespace kept.
        for n in range(1,11):
            shutil.copytree(ROOT/'tests/node_modules/three/src',root/f'three{n}',copy_function=os.link)
        count=1
        imports=''.join(f'import * as copy{n} from "./three{n}/Three.js";' for n in range(1,11))
        values=','.join(f'[Object.keys(copy{n}).length,new copy{n}.Vector3(1,2,3).applyMatrix4(new copy{n}.Matrix4().makeRotationX({n}/10)).toArray().map((x)=>x.toFixed(6)).join(" ")]' for n in range(1,11))
        put(root,'driver-0.js',imports+'import {record} from "./record.js";record(0,['+values+']);')
    elif case=='dashboard':
        # A single-page app on real packages: React rendering, d3, date-fns, lodash-es, zod, immer and
        # RxJS, five routes each loaded with import().
        shutil.copytree(ROOT/'tests/node_modules',root/'node_modules',copy_function=os.link)
        shutil.copytree(ROOT/'benchmarks/apps/dashboard/src',root/'src')
        routes=['overview','charts','calendar','tasks','reports']
        count=len(routes)
        for i,route in enumerate(routes):
            put(root,f'driver-{i}.js',f'import {{{route}}} from "./src/routes/{route}.js";import {{record}} from "./record.js";record({i},{route}());')
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


def app_command(tool, app, output, minify, config):
    defines=[f'--define:{k}={v}' for k,v in app['define'].items()]
    loaders=[f'--loader:{x}=file' for x in app['files']]
    if tool.startswith('ours-'):
        _,policy,unit=tool.split('-')
        return [str(BINARY),app['entry'],'--splitting','--format=esm','--pipeline=full','--no-cache','--strategy=once',f'--chunk-policy={policy}',f'--fragments={str(unit=="fragments").lower()}',*defines,*loaders,f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='esbuild':
        return [str(ROOT/'tests/node_modules/.bin/esbuild'),app['entry'],'--bundle','--splitting','--format=esm','--platform=browser','--target=esnext','--log-level=warning',*defines,*loaders,f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='bun':
        return ['bun','build','./'+app['entry'],'--splitting','--format=esm','--target=browser',*[x for k,v in app['define'].items() for x in ['--define',f'{k}={v}']],
                *[x for e in app['files'] for x in ['--loader',f'{e}:file']],f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='turbopack': raise ValueError('turbopack-cli takes no defines')
    config.write_text(json.dumps(dict(input={'index':str(app['dir']/app['entry'])},output=str(output),minify=minify,define=app['define'],files=app['files'],typescript=True)))
    return ['node',str(ADAPTER),tool,str(config)]


def command(tool, root, output, minify, config):
    if tool.startswith('ours-'):
        _,policy,unit=tool.split('-')
        return [str(BINARY),'main.js','--splitting','--format=esm','--pipeline=full','--no-cache','--strategy=once',f'--chunk-policy={policy}',f'--fragments={str(unit=="fragments").lower()}','--define:process.env.NODE_ENV="production"',f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='esbuild':
        return [str(ROOT/'tests/node_modules/.bin/esbuild'),'main.js','--bundle','--splitting','--format=esm','--platform=browser','--target=esnext','--log-level=warning','--define:process.env.NODE_ENV="production"',f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='bun':
        return ['bun','build','./main.js','--splitting','--format=esm','--target=browser','--define','process.env.NODE_ENV="production"',f'--outdir={output}',*(['--minify'] if minify else [])]
    if tool=='turbopack':
        return [str(TP),'build','./main.js','--dir',str(root),'--target','browser','--no-sourcemap',*(['--no-minify'] if not minify else [])]
    config.write_text(json.dumps(dict(input={'main':str(root/'main.js')},output=str(output),minify=minify)))
    return ['node',str(ADAPTER),tool,str(config)]


def measure(cmd,cwd):
    # communicate() waits for completion directly; the RSS sampler never inserts a polling delay
    # into wall time. /usr/bin/time captures even short-lived native process high-water RSS.
    load=os.getloadavg()[0]
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
    times=re.search(r'([\d.]+) real\s+([\d.]+) user\s+([\d.]+) sys',stderr)
    cpu=float(times[2])+float(times[3]) if times else 0.0
    if proc.returncode!=0 or killed[0]: raise RuntimeError(json.dumps(dict(code=proc.returncode,reason=killed[0],stdout=stdout[-2000:],stderr=stderr[-5000:])))
    return dict(seconds=elapsed,cpu_seconds=cpu,peak_mib=max(peak[0],highwater),main_process_peak_mib=highwater,load=round(load,2)),stdout,stderr


def size_of(output,files):
    bodies=[(output/name).read_bytes() for name in files]
    return dict(bytes=sum(map(len,bodies)),gzip_bytes=sum(len(gzip.compress(body,mtime=0)) for body in bodies),files=len(bodies))


# An application's build run in Chrome (benchmarks/bundlers/app-check.mjs): it must show what it
# should, throw nothing and fail no request; the JS the first page loads, and all it loads.
def app_checked(case, output):
    app=APPS[case]
    checked=subprocess.run(['node',str(ROOT/'benchmarks/bundlers/app-check.mjs'),str(output),'index.js',app['root'],app['wait'],*[str(app['dir']/x) for x in app['statics']]],
                           capture_output=True,text=True,timeout=180,env={**os.environ,'APP_STEPS':json.dumps(app['steps'])})
    assert checked.returncode==0,checked.stdout+checked.stderr
    browser=json.loads(checked.stdout)
    (WORK/f'{case}-{output.parent.name}-{output.name}-browser.json').write_text(json.dumps(browser,indent=2))
    assert browser['ok'] and not browser['failed'],json.dumps(dict(errors=browser['errors'],failed=browser['failed']))
    js=sorted(str(p.relative_to(output)) for p in output.rglob('*.js'))
    return dict(total_js=size_of(output,js),first_route=size_of(output,browser['initial']),all_loaded=size_of(output,browser['loaded']))


rows=[];samples=[]
report=WORK/(args.report_name+'.json')
def save(): report.write_text(json.dumps(dict(metadata=metadata,results=rows,samples=samples),indent=2)+'\n')
for case in args.cases.split(','):
    root,count,expected=prepare(case)
    print(json.dumps(dict(progress='fixture',case=case,roots=count)),flush=True)
    for minify in ([False] if args.plain_only else [True] if args.minified_only else [False,True]):
        modes={};failed={}
        tools=[tool for tool in TOOLS if not (case in APPS and tool=='turbopack')]
        for tool in tools:
            output=root/'dist' if tool=='turbopack' else WORK/'outputs'/case/('minified' if minify else 'plain')/tool
            config=WORK/f'{case}-{tool}-{minify}.json'
            cmd=app_command(tool,APPS[case],output,minify,config) if case in APPS else command(tool,root,output,minify,config)
            modes[tool]=(output,cmd)
        # Rotate tool order each repetition. Each invocation gets a fresh process and clean output.
        for repeat in range(args.runs):
            ordered=tools[repeat%len(tools):]+tools[:repeat%len(tools)]
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
        for tool in tools:
            output,cmd=modes[tool]
            row=dict(case=case,minify=minify,tool=tool,command=cmd)
            if tool in failed:
                row.update(status='build-failed',error=failed[tool]);rows.append(row);save();continue
            measurements=[item for item in samples if item['case']==case and item['minify']==minify and item['tool']==tool]
            row.update(runs=len(measurements),median_seconds=round(statistics.median(item['seconds'] for item in measurements),4),
                       median_cpu_seconds=round(statistics.median(item['cpu_seconds'] for item in measurements),4),
                       min_seconds=round(min(item['seconds'] for item in measurements),4),max_seconds=round(max(item['seconds'] for item in measurements),4),
                       median_peak_mib=round(statistics.median(item['peak_mib'] for item in measurements),1),max_peak_mib=round(max(item['peak_mib'] for item in measurements),1))
            if case in APPS:
                try: row.update(status='correct',**app_checked(case,output))
                except Exception as error: row.update(status='incorrect-or-validation-failed',error=str(error))
                rows.append(row);save();print(json.dumps(row),flush=True);continue
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
