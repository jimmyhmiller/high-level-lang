#!/usr/bin/env python3
"""Parser benchmark: ours (out/bin/jsparse) against Oxc, SWC and esbuild natively, and acorn, meriyah,
Babel, TypeScript, SWC, Oxc and esbuild through their JavaScript APIs.

  - each big file, every parser in a fresh process: the best and the median of ROUNDS parses
    after three untimed ones;
  - one timed pass over each corpus: every JS file the repository's benchmarks install, and, given
    a VS Code checkout, its TypeScript sources;
  - peak memory parsing typescript.js once.

Ours is timed parsing, and parsing then checking early errors; the others as they parse (esbuild's
parser visits too: it binds scopes and folds constants). Results go to out/results.json.
  usage: run.py [--vscode DIR] [--rounds N] [--only ts]
Needs: tools/build-tools.sh run (out/bin/jsparse), `npm install` here, cargo, go."""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = HERE + '/out'
OURS = ROOT + '/out/bin/jsparse'
JS_API = ['acorn', 'meriyah', 'babel', 'typescript', 'swc', 'oxc', 'oxc-raw', 'esbuild']
JS_ONLY = {'acorn', 'meriyah'}
NODE = ['node', '--max-old-space-size=16000', HERE + '/bench.mjs']
CHECKER = 'https://raw.githubusercontent.com/microsoft/TypeScript/v5.9.3/src/compiler/checker.ts'
BIG_JS = ['benchmarks/realworld/node_modules/typescript/lib/typescript.js',
          'benchmarks/react-admin-demo/node_modules/echarts/dist/echarts.js',
          'tests/node_modules/react-dom/cjs/react-dom-client.development.js',
          'tests/node_modules/three/build/three.module.js',
          'benchmarks/heldout/node_modules/vue/dist/vue.global.js',
          'benchmarks/realworld/node_modules/d3/dist/d3.js',
          'tests/node_modules/lodash/lodash.js',
          'benchmarks/heldout/node_modules/moment/moment.js']
TREES = ['tests', 'benchmarks/bundlers', 'benchmarks/react-admin-demo', 'benchmarks/realworld', 'benchmarks/heldout']

ap = argparse.ArgumentParser()
ap.add_argument('--vscode', help='a VS Code checkout: its four biggest sources, and all of them as a corpus')
ap.add_argument('--rounds', type=int, default=9)
ap.add_argument('--only', choices=['ts'], help='only the TypeScript files and corpus, merged into the results')
args = ap.parse_args()
os.makedirs(OUT, exist_ok=True)

def write_list(name, paths):
    with open(f'{OUT}/{name}', 'w') as f: f.write('\n'.join(paths) + '\n')
    return f'{OUT}/{name}'

def lines(f): return [l for l in open(f).read().split('\n') if l]

# ---------------------------------------------------------------- the parsers, built
subprocess.run(['cargo', 'build', '--release', '--quiet'], cwd=HERE + '/rust', check=True)
esbuild_version = json.load(open(ROOT + '/tests/node_modules/esbuild/package.json'))['version']
src = OUT + '/esbuild-src'
if not os.path.exists(OUT + '/esbuild-parsebench'):
    # esbuild's parser is internal to its module: the driver is built inside a copy of it.
    info = json.loads(subprocess.run(['go', 'mod', 'download', '-json', f'github.com/evanw/esbuild@v{esbuild_version}'],
                                     cwd=OUT, capture_output=True, text=True, env=dict(os.environ, GOFLAGS='-mod=mod'), check=True).stdout)
    shutil.rmtree(src, ignore_errors=True); shutil.copytree(info['Dir'], src)
    subprocess.run(['chmod', '-R', 'u+w', src], check=True)
    os.makedirs(src + '/cmd/parsebench'); shutil.copy(HERE + '/esbuild/main.go', src + '/cmd/parsebench/main.go')
    subprocess.run(['go', 'build', '-o', OUT + '/esbuild-parsebench', './cmd/parsebench'], cwd=src, check=True)
RUST = HERE + '/rust/target/release/parsebench'

# ---------------------------------------------------------------- what they parse
os.makedirs(HERE + '/data', exist_ok=True)
checker = HERE + '/data/checker.ts'
if not os.path.exists(checker): urllib.request.urlretrieve(CHECKER, checker)
big_ts = [checker]
corpora = []
if not args.only:
    js = sorted(os.path.join(d, f) for t in TREES for d, _, fs in os.walk(f'{ROOT}/{t}/node_modules')
                for f in fs if re.search(r'\.(c|m)?js$', f) and os.path.isfile(os.path.join(d, f)))
    corpora.append(('node_modules JS', write_list('js-corpus.list', js)))
if args.vscode:
    ts = sorted(os.path.join(d, f) for d, _, fs in os.walk(args.vscode + '/src') for f in fs if f.endswith('.ts') and not f.endswith('.d.ts'))
    real = [p for p in ts if '/test/' not in p and '.test.' not in p]
    big_ts += sorted(real, key=lambda p: -os.path.getsize(p))[:4]
    corpora.append(('VS Code TS', write_list('ts-corpus.list', ts)))
files = big_ts if args.only else [f'{ROOT}/{f}' for f in BIG_JS] + big_ts

def one(path):
    fd, name = tempfile.mkstemp(suffix='.list', dir=OUT); os.write(fd, (path + '\n').encode()); os.close(fd)
    return name

def out(cmd, env=None): return subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, **(env or {}))).stdout

runners = {
    'ours': lambda l, r, w: out([OURS, 'bench', l, str(r)]),
    'native oxc': lambda l, r, w: out([RUST, 'oxc', l, str(r), str(w)]),
    'native swc': lambda l, r, w: out([RUST, 'swc', l, str(r), str(w)]),
    'native esbuild (1 thread)': lambda l, r, w: out([OUT + '/esbuild-parsebench', l, str(r), str(w)], {'GOMAXPROCS': '1'}),
    'native esbuild': lambda l, r, w: out([OUT + '/esbuild-parsebench', l, str(r), str(w)]),
}
for p in JS_API:
    runners['js ' + p] = (lambda p: lambda l, r, w: out(NODE + [p, l, str(r), str(w)]))(p)

results = json.load(open(OUT + '/results.json')) if args.only else {'files': {}, 'corpus': {}, 'memory': {}}

# ---------------------------------------------------------------- big files
for f in files:
    lst = one(f)
    row = {}
    for name, run in runners.items():
        if f.endswith('.ts') and name.split()[-1] in JS_ONLY: continue
        m = re.search(r'^BENCH \S+ (\d+) (\d+) (\d+)(?: (\d+) (\d+))?$', run(lst, args.rounds, 3), re.M)
        if not m: row[name] = None; continue
        size, best, med = int(m.group(1)), int(m.group(2)), int(m.group(3))
        row[name] = {'bytes': size, 'best_us': best, 'median_us': med}
        if name == 'ours':
            row['ours (parse + early errors)'] = {'bytes': size, 'best_us': best + int(m.group(4)), 'median_us': med + int(m.group(5))}
    os.unlink(lst)
    results['files'][f] = row
    print(os.path.basename(f), {k: (v or {}).get('best_us') for k, v in row.items()}, flush=True)

# ---------------------------------------------------------------- corpora: one timed pass
for corpus, lst in corpora:
    row = {}
    # Ours keeps every tree it makes, so a corpus is cut into chunks of a few thousand files.
    paths = lines(lst)
    us = check = byts = done = 0
    for k in range(0, len(paths), 3000):
        chunk = one('\n'.join(paths[k:k + 3000]))
        for m in re.finditer(r'^BENCH \S+ (\d+) (\d+) \d+ (\d+) \d+$', runners['ours'](chunk, 1, 0), re.M):
            done += 1; byts += int(m.group(1)); us += int(m.group(2)); check += int(m.group(3))
        os.unlink(chunk)
    row['ours'] = {'files': done, 'bytes': byts, 'us': us}
    row['ours (parse + early errors)'] = {'files': done, 'bytes': byts, 'us': us + check}
    for name, run in runners.items():
        if name == 'ours' or (corpus == 'VS Code TS' and name.split()[-1] in JS_ONLY): continue
        m = re.search(r'CORPUS \S+ files (\d+) failed (\d+) bytes (\d+) us (\d+)', run(lst, 1, 0))
        row[name] = None if not m else {'files': int(m.group(1)) - int(m.group(2)), 'bytes': int(m.group(3)), 'us': int(m.group(4))}
    results['corpus'][corpus] = row
    print(corpus, {k: v and round(v['bytes'] / v['us'], 1) for k, v in row.items()}, flush=True)

# ---------------------------------------------------------------- peak memory, typescript.js once
if not args.only:
    lst = one(f'{ROOT}/{BIG_JS[0]}')
    def rss(cmd, env=None):
        r = subprocess.run(['/usr/bin/time', '-l'] + cmd, capture_output=True, text=True, env=dict(os.environ, **(env or {})))
        m = re.search(r'(\d+)\s+maximum resident set size', r.stderr)
        return int(m.group(1)) if m else None
    results['memory'] = {'ours': rss([OURS, 'check', lst]),
                         'native oxc': rss([RUST, 'oxc', lst, '1', '0']), 'native swc': rss([RUST, 'swc', lst, '1', '0']),
                         'native esbuild': rss([OUT + '/esbuild-parsebench', lst, '1', '0'])}
    for p in JS_API: results['memory']['js ' + p] = rss(NODE + [p, lst, '1', '0'])
    os.unlink(lst)
    print('peak MB', {k: v and v >> 20 for k, v in results['memory'].items()})
json.dump(results, open(OUT + '/results.json', 'w'), indent=1)
