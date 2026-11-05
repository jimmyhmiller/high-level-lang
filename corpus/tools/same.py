#!/usr/bin/env python3
# Byte-for-byte against a frozen binary, while code moves between languages. Every app, every
# mode, and the accept/reject answer for every test262 file. Run from corpus/.
#   usage: same.py NEW-ESB NEW-JSPARSE BASE-ESB BASE-JSPARSE
import glob, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard
# No single run may take much memory or time: a runaway stops the comparison, not the machine.
MB, SECONDS = 3000, 120
def capped(cmd):
    code, out, err, peak, reason = guard.run(cmd, MB, SECONDS, quiet=True)
    if reason:
        print("STOPPED: " + " ".join(cmd) + ": " + reason); sys.exit(2)
    return code, out, err
NE, NP, BE, BP = sys.argv[1:5]
S = "out/same"; os.makedirs(S, exist_ok=True)
APPS = "named all cjs features three zod rx datefns preact immer react d3 lib excjs nodey".split()
MODES = {
  "plain": [],
  "min": ["--minify"],
  "minid": ["--minify-identifiers"],
  "minsyn": ["--minify-syntax"],
  "pretty": ["--pretty"],
  "esm": ["--format=esm"],
  "cjsf": ["--format=cjs"],
  "global": ["--global-name=X"],
  "map": ["--sourcemap"],
  "node": ["--platform=node"],
  "ext": ["--external:lodash-es"],
  "def": ["--define:DEBUG=false"],
}
bad = 0; n = 0
def run(bin, app, flags, out):
    code, o, e = capped([bin, f"app/{app}.js", f"--outfile={out}"] + flags)
    return code, (e + o).replace(out, "OUT")
for app in APPS:
    if not os.path.exists(f"app/{app}.js"): continue
    for mode, flags in MODES.items():
        os.makedirs(f"{S}/new", exist_ok=True); os.makedirs(f"{S}/base", exist_ok=True)
        a, b = f"{S}/new/{app}.{mode}.js", f"{S}/base/{app}.{mode}.js"
        for f in (a, b, a + ".map", b + ".map"):
            if os.path.exists(f): os.remove(f)
        ca, ea = run(NE, app, flags, a); cb, eb = run(BE, app, flags, b)
        n += 1
        same = ca == cb and (cb != 0 or (open(a, "rb").read() == open(b, "rb").read()))
        if cb != 0: same = same and ea.split("\n")[0][-120:] == eb.split("\n")[0][-120:]
        if same and os.path.exists(b + ".map"):
            same = open(a + ".map", "rb").read() == open(b + ".map", "rb").read()
        if not same:
            bad += 1; print(f"DIFF {app} {mode} rc {ca} vs {cb}: {ea[:200] if ca else ''}")
for name in ["pass", "fail", "early"]:
    files = sorted(glob.glob(f"vendor/test262-parser-tests/{name}/*.js"))
    lst = f"{S}/{name}.list"; open(lst, "w").write("\n".join(files) + "\n")
    for mode in ["accepted", "strict", "check"]:
        ra = capped([NP, mode, lst])[1]
        rb = capped([BP, mode, lst])[1]
        n += 1
        if ra != rb:
            bad += 1; print(f"DIFF jsparse {mode} {name}: {ra.strip().splitlines()[-1:]} vs {rb.strip().splitlines()[-1:]}")
print(f"{n} comparisons, {bad} differ")
sys.exit(1 if bad else 0)
