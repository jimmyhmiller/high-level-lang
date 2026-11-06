#!/usr/bin/env python3
# Code splitting and stylesheet assets byte for byte against another build: every file of each
# output directory, maps included. verify.py normalises hashed names away; this does not, so a
# changed hash shows. Works in tests/.
#   usage: same-split.py NEW-ESB BASE-ESB
import filecmp, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard
NEW, BASE = guard.in_tests(sys.argv[1:3])
S = "../out/same-split"
SPLITS = [["apps/split/a.js", "apps/split/b.js"], ["apps/split/real1.js", "apps/split/real2.js"],
          ["apps/split/ts-entry.ts"], ["apps/split/a.js", "apps/split/sub/nested.js"]]
MODES = [[], ["--minify"], ["--sourcemap"], ["--minify", "--sourcemap"]]
ASSETS = ["--loader:.png=file", "--loader:.woff2=file"]
cases = [(entries + ["--splitting", "--format=esm"], flags, True) for entries in SPLITS for flags in MODES]
cases += [(["apps/css/entry.js"] + ASSETS, flags, False) for flags in MODES]
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
