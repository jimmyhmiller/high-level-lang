#!/usr/bin/env python3
"""Fragments on libraries they were never tuned on: two pages per library
(benchmarks/heldout/pages/LIB/{a,b}.js) split by esbuild, by ours with whole modules and by ours
with --fragments, all minified. Each page is run under Node with a load hook (pages/trace.mjs)
that records every file Node really loads; a page's bytes are those files'. Every page must
print what the unbundled page prints. Exits 1 if one does not.
   usage: heldout-fragments.py [LIB...]   (ESB=binary)"""
import gzip, json, os, shutil, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT/'benchmarks/heldout/pages'
OURS = str(Path(os.environ.get('ESB', ROOT/'out/bin/esb')).resolve())
ESBUILD = str(ROOT/'benchmarks/heldout/node_modules/.bin/esbuild')
OUT = ROOT/'out/heldout/fragments'
COMMON = ['--splitting', '--format=esm', '--platform=node', '--minify']
MODES = [('esbuild', [ESBUILD, '--bundle', '--log-level=error', *COMMON]),
         ('ours', [OURS, *COMMON]),
         ('ours+fragments', [OURS, *COMMON, '--fragments'])]
libs = sys.argv[1:] or sorted(p.name for p in HERE.iterdir() if p.is_dir())


def page(path):
    fd, log = tempfile.mkstemp(); os.close(fd)
    r = subprocess.run(['node', '--import', str(HERE/'trace.mjs'), str(path)], capture_output=True, text=True,
                       env={**os.environ, 'TRACE_OUT': log}, timeout=60)
    files = [f for f in json.loads(Path(log).read_text() or '[]') if not f.endswith('trace.mjs')]
    os.unlink(log)
    return (r.stdout if r.returncode == 0 else 'EXIT ' + r.stderr[-300:]), files


rows, bad = [], []
for lib in libs:
    pages = sorted(p.name for p in (HERE/lib).glob('*.js'))
    want = {p: page(HERE/lib/p)[0] for p in pages}
    cells = []
    for mode, cmd in MODES:
        outdir = OUT/lib/mode
        shutil.rmtree(outdir, ignore_errors=True)
        t = time.perf_counter()
        r = subprocess.run(cmd + [f'{lib}/{p}' for p in pages] + [f'--outdir={outdir}'], cwd=HERE, capture_output=True, text=True)
        ms = round((time.perf_counter() - t) * 1000)
        if r.returncode:
            bad.append(f'{lib} {mode}: build failed {(r.stderr or r.stdout)[-300:]}'); continue
        for p in pages:
            got, files = page(outdir/p)
            raw = sum(os.path.getsize(f) for f in files)
            gz = sum(len(gzip.compress(Path(f).read_bytes(), 9)) for f in files)
            rows.append(dict(lib=lib, mode=mode, page=p, bytes=raw, gzip=gz, files=len(files), ms=ms, ok=got == want[p]))
            cells.append(f'{mode} {Path(p).stem} {raw/1000:.1f}K' + ('' if got == want[p] else ' WRONG'))
            if got != want[p]:
                bad.append(f'{lib} {mode} {p}: {got[:200]!r}, unbundled {want[p][:200]!r}')
    print(f'{lib:10} ' + ' | '.join(cells), flush=True)
OUT.mkdir(parents=True, exist_ok=True)
(OUT/'results.json').write_text(json.dumps(rows, indent=1))
for b in bad: print('FAIL', b)
sys.exit(1 if bad else 0)
