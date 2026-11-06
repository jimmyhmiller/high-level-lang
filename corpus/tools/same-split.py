#!/usr/bin/env python3
# Code splitting and stylesheet assets byte for byte against another build: every file of each
# output directory, maps included. verify.py normalises hashed names away; this does not, so a
# changed hash shows. Run from corpus/.
#   usage: same-split.py NEW-ESB BASE-ESB
import filecmp, os, shutil, subprocess, sys
NEW, BASE = sys.argv[1:3]
S = "out/same-split"
SPLITS = [["app/split/a.js", "app/split/b.js"], ["app/split/real1.js", "app/split/real2.js"],
          ["app/split/ts-entry.ts"], ["app/split/a.js", "app/split/sub/nested.js"]]
MODES = [[], ["--minify"], ["--sourcemap"], ["--minify", "--sourcemap"]]
ASSETS = ["--loader:.png=file", "--loader:.woff2=file"]
cases = [(entries + ["--splitting", "--format=esm"], flags, True) for entries in SPLITS for flags in MODES]
cases += [(["app/css/entry.js"] + ASSETS, flags, False) for flags in MODES]
def tree(d):
    return sorted(os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs)
bad = 0
for i, (args, flags, split) in enumerate(cases):
    dirs = []
    for b, tag in [(NEW, "new"), (BASE, "base")]:
        d = f"{S}/{i}/{tag}"
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        where = [f"--outdir={d}"] if split else [f"--outfile={d}/app.js"]
        r = subprocess.run([b] + args + where + flags, capture_output=True, timeout=120)
        dirs.append((d, r.returncode))
    (a, ca), (b, cb) = dirs
    same = ca == 0 and cb == 0 and tree(a) == tree(b) and len(tree(a)) > 0 and \
        all(filecmp.cmp(f"{a}/{f}", f"{b}/{f}", shallow=False) for f in tree(a))
    if not same:
        bad += 1
        print(f"DIFF {' '.join(args)} {' '.join(flags)}")
print(f"{len(cases)} split and asset builds, {bad} differ")
sys.exit(1 if bad else 0)
