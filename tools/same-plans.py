#!/usr/bin/env python3
# Every plan that divides the work prints what `--pipeline=single` prints, byte for byte, maps
# included: across the apps and the modes that change what parts are cut and how they print. Works
# in tests/.
#   usage: same-plans.py ESB [PLAN...]      (default plans: full two)
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard
ESB, = guard.in_tests(sys.argv[1:2])
PLANS = sys.argv[2:] or ["full", "two"]
S = "../out/same-plans"
APPS = "named all cjs rx datefns d3 zod three react preact immer features lib excjs exes exdate eximmer cjsret".split()
MODES = [[], ["--minify"], ["--pretty"], ["--sourcemap"], ["--minify", "--sourcemap"], ["--minify-syntax"],
         ["--minify-identifiers"], ["--charset=utf8", "--minify"], ["--pretty", "--sourcemap"],
         ["--target=es2017", "--minify"], ["--format=cjs", "--minify"]]

def build(app, flags, plan, d):
    os.makedirs(d, exist_ok=True)
    out = f"{d}/o.js"
    for f in (out, out + ".map"):
        if os.path.exists(f): os.remove(f)
    r = subprocess.run([ESB, f"apps/{app}.js", f"--outfile={out}", f"--pipeline={plan}"] + flags, capture_output=True, timeout=120)
    read = lambda f: open(f, "rb").read() if os.path.exists(f) else None
    return r.returncode, read(out), read(out + ".map")

n = bad = 0
for app in APPS:
    if not os.path.exists(f"apps/{app}.js"): continue
    for flags in MODES:
        want = build(app, flags, "single", f"{S}/single")
        if want[0] != 0 or not want[1]:
            bad += 1; print(f"FAIL {app} {' '.join(flags)}: the single plan did not build"); continue
        for plan in PLANS:
            n += 1
            if build(app, flags, plan, f"{S}/{plan}") != want:
                bad += 1; print(f"DIFF {app} {' '.join(flags)} --pipeline={plan}")
print(f"{n} builds under {', '.join(PLANS)}, {bad} differ from single")
sys.exit(1 if bad else 0)
