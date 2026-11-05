# The differential exerciser over each library: validates the oracle, then compares us.
import os, subprocess, sys
S = sys.argv[1]
apps = sys.argv[2:] or "exes excjs exdate exd3 exrx eximmer".split()
def node(f):
    try:
        r = subprocess.run(["node", f], capture_output=True, text=True, timeout=120)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
for a in apps:
    subprocess.run(["node_modules/.bin/esbuild", f"app/{a}.js", "--bundle", "--format=iife", f"--outfile=out/esb/{a}.plain.js", "--log-level=silent"])
    subprocess.run(["node_modules/.bin/esbuild", f"app/{a}.js", "--bundle", "--format=iife", "--minify", f"--outfile=out/esb/{a}.min.js", "--log-level=silent"])
    e1, e2 = node(f"out/esb/{a}.plain.js"), node(f"out/esb/{a}.min.js")
    total = [l for l in e1.splitlines() if l.startswith("TOTAL")]
    oracle = "oracle-ok" if e1 == e2 else "ORACLE-UNSTABLE"
    subprocess.run([S + "/esb", f"app/{a}.js", f"--outfile=out/ours/{a}.js"], capture_output=True)
    subprocess.run([S + "/esb", f"app/{a}.js", "--minify", f"--outfile=out/ours/{a}.min.js"], capture_output=True)
    o1, o2 = node(f"out/ours/{a}.js"), node(f"out/ours/{a}.min.js")
    # Only lines both esbuild builds agree on are evidence.
    l1, l2 = e1.split("\n"), e2.split("\n")
    stable = [i for i in range(min(len(l1), len(l2))) if l1[i] == l2[i]]
    def verdict(x):
        lx = x.split("\n")
        bad = [i for i in stable if i >= len(lx) or lx[i] != l1[i]]
        if not bad: return f"same"
        i = bad[0]
        return f"DIFF({len(bad)}) {lx[i][:100] if i < len(lx) else 'missing'}"
    oracle = f"{len(stable)}/{len(l1)} stable"
    print(f"{a:8} {oracle} {total[0] if total else 'no-total':32} plain:{verdict(o1)}  min:{verdict(o2)}")
