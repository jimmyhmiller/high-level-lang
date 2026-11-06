#!/usr/bin/env python3
# Lowered output byte for byte against another build: every case verify.py runs for older targets,
# plus every year for the feature fixture, and TypeScript at no target and two, minified and not. Temporaries are named in the order
# lowering makes them, which a check that only runs the output cannot see. Run from corpus/.
#   usage: same-lowered.py NEW-ESB BASE-ESB
import os, subprocess, sys
NEW, BASE = sys.argv[1:3]
S = "out/same-lowered"; os.makedirs(S, exist_ok=True)
CASES = [("app/lower/all.js", y, f) for y in [2022, 2021, 2020, 2019, 2018, 2017, 2016, 2015] for f in [[], ["--minify"]]]
CASES += [(f"app/{a}.js", 2015, ["--minify"]) for a in ["immer", "rx", "zod", "preact", "features", "datefns", "exes", "excjs", "exdate", "eximmer"]]
CASES += [(f"app/{a}.js", 2015, []) for a in ["immer", "rx", "zod", "preact", "features", "datefns"]]
CASES += [("app/react.js", 2017, ["--platform=node"])]
CASES += [(f"app/ts/{a}.ts", y, f) for a in ["rx", "zod4", "immer", "main"] for y in [None, 2018, 2015] for f in [[], ["--minify"]]]
bad = 0
for i, (entry, year, flags) in enumerate(CASES):
    outs = []
    for b, tag in [(NEW, "new"), (BASE, "base")]:
        out = f"{S}/{i}.{tag}.js"
        target = [f"--target=es{year}"] if year else []
        r = subprocess.run([b, entry, f"--outfile={out}"] + target + flags, capture_output=True, text=True, timeout=120)
        outs.append((r.returncode, open(out).read() if os.path.exists(out) else "", (r.stderr + r.stdout).replace(out, "OUT")))
    if outs[0] != outs[1] or outs[0][0] != 0 or not outs[0][1]:
        bad += 1
        print(f"DIFF {entry} es{year} {' '.join(flags)} (exit {outs[0][0]} vs {outs[1][0]})")
print(f"{len(CASES)} lowered outputs, {bad} differ")
sys.exit(1 if bad else 0)
