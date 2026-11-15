#!/usr/bin/env python3
"""Start's two-context watcher must release old transformed trees across unique edits.

usage: start-memory-check.py [ESB] [--edits=60] [--warm=20]
"""
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
ESB = Path(next((x for x in sys.argv[1:] if not x.startswith('--')), ROOT / 'out/bin/esb')).resolve()
EDITS = next((int(x.split('=')[1]) for x in sys.argv[1:] if x.startswith('--edits=')), 60)
WARM = next((int(x.split('=')[1]) for x in sys.argv[1:] if x.startswith('--warm=')), 20)
assert 5 <= WARM < EDITS - 4
SOURCE = ROOT / 'benchmarks/tanstack-start'
WORK = ROOT / 'out/start-memory-check'
shutil.rmtree(WORK, ignore_errors=True)
shutil.copytree(SOURCE, WORK, symlinks=True, ignore=shutil.ignore_patterns('node_modules', 'dist*', 'START-SPEC.md'))
(WORK / 'node_modules').symlink_to(SOURCE / 'node_modules', target_is_directory=True)
route = WORK / 'src/routes/index.tsx'
original = route.read_text()
assert 'Start home' in original
p = subprocess.Popen([str(ESB), '--tanstack-start', '--hmr', '--serve=0', '--no-cache', '--watch-interval=5'],
                     cwd=WORK, env=dict(os.environ, HL_REGION_TRACE='1'), stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT, text=True, start_new_session=True)
lines = queue.Queue()
def read():
    for line in p.stdout:
        lines.put(line)
    lines.put(None)
threading.Thread(target=read, daemon=True).start()
log = []
held = {}
try:
    for edit in range(EDITS + 1):
        deadline = time.monotonic() + 60
        while True:
            line = lines.get(timeout=max(0.01, deadline - time.monotonic()))
            assert line is not None, 'watcher exited:\n' + ''.join(log[-30:])
            log.append(line)
            m = re.search(r'\[regions\] let go \d+ regions, \d+ KB; (\d+) alive, (\d+) KB', line)
            if m:
                held[edit] = (int(m[1]), int(m[2]))
                break
        if edit in (0, WARM, EDITS):
            print(f'build {edit + 1}: {held[edit][0]} regions, {held[edit][1]} KB', flush=True)
        if edit != EDITS:
            route.write_text(original.replace('Start home', f'Start edit {edit + 1}'))
    warm = held[WARM]
    final = held[EDITS]
    # Match memory-check's 2% bound on live region bytes; unique edits must plateau.
    assert final[1] <= warm[1] * 1.02, f'regions grew: {warm} -> {final}'
    print(f'Start memory check passed: {EDITS} unique edits, live regions {warm} -> {final}', flush=True)
finally:
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        p.wait()
    (WORK / 'watch.log').write_text(''.join(log))
