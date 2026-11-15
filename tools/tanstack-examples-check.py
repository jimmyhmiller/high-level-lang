#!/usr/bin/env python3
"""TanStack's own example applications (benchmarks/tanstack-examples), each built by us and by Vite and
run in Chrome: every route without parameters must show what Vite's build shows, with no error Vite's
has not (tools/real-app-check.mjs).

usage: tanstack-examples-check.py [ESB]
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
SRC = os.path.join(ROOT, "benchmarks/tanstack-examples")
WORK = os.path.join(ROOT, "out/tanstack-examples")

failures, passed = [], 0


def check(ok, what):
    global passed
    if ok:
        passed += 1
        print("ok  ", what)
    else:
        failures.append(what)
        print("FAIL", what)


for name in sorted(n for n in os.listdir(SRC) if os.path.isdir(os.path.join(SRC, n))):
    src = os.path.join(SRC, name)
    if not os.path.isdir(os.path.join(src, "node_modules")):
        check(False, f"{name}: not installed (npm ci --prefix benchmarks/tanstack-examples/{name} --ignore-scripts)")
        continue
    app = os.path.join(WORK, name)
    shutil.rmtree(app, ignore_errors=True)
    shutil.copytree(src, app, symlinks=True, ignore=shutil.ignore_patterns("node_modules", "dist*"))
    os.symlink(os.path.join(src, "node_modules"), os.path.join(app, "node_modules"))
    start = os.path.exists(os.path.join(app, "src/router.tsx")) and "react-start" in open(os.path.join(app, "package.json")).read()
    ours = subprocess.run([ESB, "--tanstack-start"] if start else [ESB, "index.html", "--outdir=dist", "--tanstack-router", "--minify"],
                          cwd=app, capture_output=True, text=True, timeout=600)
    if ours.returncode != 0:
        check(False, f"{name}: builds: " + (ours.stdout + ours.stderr)[-800:])
        continue
    vite = subprocess.run([os.path.join(app, "node_modules/.bin/vite"), "build", "--outDir", "dist-vite", "--logLevel", "error"],
                          cwd=app, capture_output=True, text=True, timeout=600)
    if vite.returncode != 0:
        check(False, f"{name}: Vite builds it: " + vite.stderr[-800:])
        continue
    run = subprocess.run(["node", os.path.join(ROOT, "tools/real-app-check.mjs"), app, os.path.join(app, "dist"), os.path.join(app, "dist-vite")],
                         capture_output=True, text=True, timeout=600)
    last = (run.stdout.strip().splitlines() or ["?"])[-1]
    check(run.returncode == 0, f"{name}: {last}" + ("" if run.returncode == 0 else "\n" + run.stdout[-1500:]))
print("tanstack-examples-check: %d passed, %d failed" % (passed, len(failures)))
sys.exit(1 if failures else 0)
