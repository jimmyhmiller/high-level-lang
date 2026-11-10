#!/usr/bin/env python3
"""Split JS, CSS, assets and package maps must rebuild exactly like a fresh build."""
import json
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
ROOT = Path(__file__).resolve().parent.parent
ESB = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'out/bin/esb'
WORK = ROOT/'out/multi-output-check'
if WORK.exists(): shutil.rmtree(WORK)
WORK.mkdir(parents=True)
files = {
 'package.json': json.dumps({'type':'module','imports':{'#chosen':'./one.js'}}),
 'one.js':'export const chosen=1;', 'two.js':'export const chosen=2;',
 'main.js':'import {chosen} from "#chosen";import asset from "./image.svg";import "./base.css";export {chosen,asset};export const lazy=()=>import("./lazy.js");',
 'other.js':'export const value=3;',
 'lazy.js':'import "./lazy.css";export const value=4;',
 'base.css':':root{--base:one}', 'lazy.css':':root{--lazy:one;background:url("./image.svg")}',
 'image.svg':'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"/>'
}
for path,text in files.items(): (WORK/path).write_text(text)
common = [str(ESB),'main.js','other.js','--splitting','--format=esm','--fragments=true','--chunk-policy=balanced','--loader:.svg=file','--public-path=/assets/','--sourcemap','--pipeline=full']

def fresh_matches():
    fresh=WORK/'fresh'
    fresh.mkdir(exist_ok=True)
    for child in fresh.iterdir():
        if child.is_dir(): shutil.rmtree(child)
        else: child.unlink()
    result=subprocess.run(common+['--outdir=fresh','--no-cache'],cwd=WORK,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    current=[p for p in fresh.rglob('*') if p.is_file()]
    assert current
    for path in current:
        counterpart=WORK/'built'/path.relative_to(fresh)
        assert counterpart.exists() and counterpart.read_bytes()==path.read_bytes(),str(path.relative_to(fresh))

# Persistent cache must handle the enum-valued resolution keys and all output kinds.
for label in ['cold','warm']:
    result=subprocess.run(common+['--outdir=built','--cache'],cwd=WORK,capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stdout+result.stderr
    fresh_matches()
    print('ok   multi-output persistent cache',label,flush=True)

proc=subprocess.Popen(common+['--outdir=built','--watch'],cwd=WORK,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
lines=queue.Queue()
threading.Thread(target=lambda:[lines.put(line) for line in proc.stdout],daemon=True).start()
def await_build(timeout=30):
    end=time.monotonic()+timeout
    seen=[]
    while time.monotonic()<end:
        try: line=lines.get(timeout=max(0.01,end-time.monotonic()))
        except queue.Empty: break
        seen.append(line)
        if re.search(r'\[watch\] build \d+:',line):return True
        if 'panic:' in line:raise AssertionError(''.join(seen))
    return False

def edit(path,text):
    staged=WORK.parent/'multi-output-next.tmp'
    staged.write_text(text)
    staged.replace(WORK/path)

try:
    assert await_build(),'no initial watch build'
    fresh_matches()
    for label,path,text in [
        ('JavaScript','lazy.js',files['lazy.js'].replace('value=4','value=40')),
        ('stylesheet','lazy.css',files['lazy.css'].replace('--lazy:one','--lazy:two')),
        ('asset','image.svg',files['image.svg'].replace('width="2"','width="4"')),
        ('package imports','package.json',files['package.json'].replace('./one.js','./two.js')),
        ('entry','other.js','export const value=30;')
    ]:
        edit(path,text)
        assert await_build(),label+' did not rebuild'
        # No later rebuild may be consumed as if it belonged to the next edit.
        assert not await_build(0.4),label+' triggered an unrelated follow-up rebuild'
        fresh_matches()
        print('ok   split watch',label,'matches every fresh output byte',flush=True)
    edit('lazy.js',(WORK/'lazy.js').read_text())
    assert not await_build(1),'same-content write rebuilt'
    print('ok   same-content write does not rebuild',flush=True)
finally:
    os.killpg(proc.pid,signal.SIGKILL)
    proc.wait()
print('ALL multi-output cache/watch checks passed')
