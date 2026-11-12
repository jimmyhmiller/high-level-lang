#!/usr/bin/env python3
"""Libraries the bundler was never tuned on (benchmarks/heldout): each exerciser in apps/ built by
ours and esbuild, plain and minified, every output run under Node. Reports minified bytes and gzip
against esbuild (and terser and swc over esbuild's plain bundle, for context), best-of-N wall time,
and whether our minified output prints what esbuild's does. Exits 1 if any build fails or differs.
   usage: heldout-sizes.py [APP...]   (ESB=binary, RUNS=builds per timing, default 5)
   setup: npm ci --prefix benchmarks/heldout && node benchmarks/heldout/node_modules/esbuild/install.js"""
import gzip, json, os, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT/'benchmarks/heldout'
OURS = str(Path(os.environ.get('ESB', ROOT/'out/bin/esb')).resolve())
RUNS = int(os.environ.get('RUNS', '5'))
ESBUILD = str(HERE/'node_modules/.bin/esbuild')
OUT = ROOT/'out/heldout/sizes'; OUT.mkdir(parents=True, exist_ok=True)
# Needs a DOM, so under Node both bundles fail the same way: compared by the error's first line.
DOM = {'lit'}
apps = sys.argv[1:] or sorted(p.stem for p in (HERE/'apps').glob('*.js') if p.stem != 'nodom')


def run(cmd, timeout=300):
    t = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE, timeout=timeout)
    return r, time.perf_counter() - t


def node(path, app):
    r, _ = run(['node', str(path)], 60)
    if r.returncode == 0:
        return r.stdout
    err = next((l for l in r.stderr.splitlines() if re.match(r'\w*Error\b', l)), r.stderr[-300:])
    return 'EXIT ' + (err if app in DOM else r.stderr[-600:])


def gz(p): return len(gzip.compress(Path(p).read_bytes(), 9))


rows, bad = [], []
for a in apps:
    src = f'apps/{a}.js'
    row, outs = {'app': a}, {}
    for tool, minify in [('esbuild', False), ('esbuild', True), ('ours', False), ('ours', True)]:
        key = tool + ('.min' if minify else '')
        o = OUT/f'{a}.{key}.mjs'
        cmd = ([ESBUILD, src, '--bundle', '--log-level=error'] if tool == 'esbuild' else [OURS, src]) + \
              ['--format=esm', f'--outfile={o}'] + (['--minify'] if minify else [])
        best = None
        for _ in range(RUNS if minify else 1):
            o.unlink(missing_ok=True)
            r, dt = run(cmd)
            best = dt if best is None else min(best, dt)
        if r.returncode or not o.exists() or not o.stat().st_size:
            row[key] = 'build failed: ' + (r.stderr or r.stdout)[-400:]
            bad.append(f'{a} {key}: build failed')
            continue
        outs[key] = node(o, a)
        row[key] = {'bytes': o.stat().st_size, 'gzip': gz(o), 'ms': round(best * 1000, 1)}
    plain = OUT/f'{a}.esbuild.mjs'
    if plain.exists():
        t = OUT/f'{a}.terser.mjs'
        r, _ = run(['node', 'node_modules/terser/bin/terser', str(plain), '--module', '-c', '-m', '-o', str(t)])
        if not r.returncode: row['terser'] = {'bytes': t.stat().st_size, 'gzip': gz(t)}
        s = OUT/f'{a}.swc.mjs'
        r, _ = run(['node', '-e', 'const swc=require("@swc/core"),fs=require("fs");'
                    f'swc.minify(fs.readFileSync({json.dumps(str(plain))},"utf8"),{{module:true,compress:true,mangle:true}})'
                    f'.then(r=>fs.writeFileSync({json.dumps(str(s))},r.code))'])
        if not r.returncode: row['swc'] = {'bytes': s.stat().st_size, 'gzip': gz(s)}
    for k in ('ours', 'ours.min'):
        if k in outs and outs[k] != outs.get('esbuild.min'):
            bad.append(f'{a} {k}: prints something other than esbuild\'s bundle')
    row['same'] = all(outs.get(k) == outs.get('esbuild.min') for k in ('ours', 'ours.min'))
    rows.append(row)
    e, o = row.get('esbuild.min'), row.get('ours.min')
    if isinstance(e, dict) and isinstance(o, dict):
        print(f"{a:10} esbuild {e['bytes']:7} ours {o['bytes']:7} {100*(o['bytes']/e['bytes']-1):+6.1f}%  "
              f"gzip {100*(o['gzip']/e['gzip']-1):+5.1f}%  terser {row.get('terser', {}).get('bytes', '-'):>7} "
              f"swc {row.get('swc', {}).get('bytes', '-'):>7}  {e['ms']:6.1f} vs {o['ms']:6.1f} ms  "
              f"{'same' if row['same'] else 'DIFFERENT'}", flush=True)
(OUT/'results.json').write_text(json.dumps(rows, indent=1))
for b in bad: print('FAIL', b)
sys.exit(1 if bad else 0)
