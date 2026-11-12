#!/usr/bin/env python3
"""Minification soundness on libraries it was never tuned on: tests/apps/exercise.mjs calls every
export of each library in benchmarks/heldout/ex on a matrix of inputs. Ours, plain, must print what
esbuild's plain build prints, and ours, minified, what esbuild's minified build prints, on every line
where two runs of that esbuild build agree. (A library's development and production builds may
print differently: mobx's checks its arguments only in development.) Exits 1 if a line differs.
   usage: heldout-exercise.py [LIB...]   (ESB=binary)"""
import os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT/'benchmarks/heldout'
OURS = str(Path(os.environ.get('ESB', ROOT/'out/bin/esb')).resolve())
ESBUILD = str(HERE/'node_modules/.bin/esbuild')
OUT = ROOT/'out/heldout/exercise'; OUT.mkdir(parents=True, exist_ok=True)
libs = sys.argv[1:] or sorted(p.stem[3:] for p in (HERE/'ex').glob('ex-*.js'))


def build(cmd):
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"{' '.join(cmd)}\n{r.stdout}{r.stderr[-2000:]}")


# Some libraries leave a rejected promise unhandled (valibot's async parsers, mobx's development
# checks); by default Node then exits at a moment that depends on timing, so the runs would stop
# at different lines. A warning instead lets each run to its end.
def lines(f):
    return subprocess.run(['node', '--unhandled-rejections=warn', str(f)], capture_output=True, text=True, timeout=900).stdout.split('\n')


bad = []
for lib in libs:
    src = f'ex/ex-{lib}.js'
    f = {k: OUT/f'{lib}.{k}.js' for k in ('esbuild', 'esbuild-min', 'ours', 'ours-min')}
    build([ESBUILD, src, '--bundle', '--format=iife', f"--outfile={f['esbuild']}", '--log-level=silent'])
    build([ESBUILD, src, '--bundle', '--format=iife', '--minify', f"--outfile={f['esbuild-min']}", '--log-level=silent'])
    build([OURS, src, '--format=iife', f"--outfile={f['ours']}"])
    build([OURS, src, '--format=iife', '--minify', f"--outfile={f['ours-min']}"])
    for mode, oracle in (('ours', 'esbuild'), ('ours-min', 'esbuild-min')):
        a, a2 = lines(f[oracle]), lines(f[oracle])
        stable = [i for i in range(min(len(a), len(a2))) if a[i] == a2[i]]
        total = next((l for l in a if l.startswith('TOTAL')), '')
        x = lines(f[mode])
        diff = [i for i in stable if i >= len(x) or x[i] != a[i]]
        print(f'{lib:10} {mode:8} {len(stable)} of {len(a)} lines stable, {len(diff)} differ {total}', flush=True)
        if diff:
            i = diff[0]
            bad.append(f'{lib} {mode}: line {i}: {(x[i] if i < len(x) else "<missing>")[:160]!r}, {oracle} {a[i][:160]!r}')
for b in bad: print('FAIL', b)
sys.exit(1 if bad else 0)
