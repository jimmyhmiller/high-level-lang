#!/usr/bin/env python3
# Everything the bundler claims, checked against esbuild and acorn. Run from corpus/.
#   usage: verify.py ESB-BINARY JSPARSE-BINARY
import glob, gzip, json, os, re, subprocess, sys, time
ESB, PARSE = sys.argv[1], sys.argv[2]
SCRATCH = "out/verify"; os.makedirs(SCRATCH, exist_ok=True)
E = "node_modules/.bin/esbuild"
failures = []
def sh(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
def check(ok, label):
    print(("  ok   " if ok else "  FAIL ") + label)
    if not ok: failures.append(label)

print("== parser")
lists = {
    "lodash.js": ["node_modules/lodash/lodash.js"],
    "lodash-es": sorted(glob.glob("node_modules/lodash-es/*.js")),
    "test262 pass": sorted(glob.glob("vendor/test262-parser-tests/pass/*.js")),
    "libraries": [l for l in subprocess.run("find node_modules/three/build node_modules/three/src node_modules/preact/dist node_modules/preact/src node_modules/zod node_modules/rxjs/dist/esm node_modules/rxjs/dist/esm5 node_modules/date-fns node_modules/immer/dist node_modules/react node_modules/react-dom/cjs node_modules/axios/lib node_modules/d3-array node_modules/d3-scale node_modules/d3-shape -type f ( -name *.js -o -name *.mjs -o -name *.cjs )".split(), capture_output=True, text=True).stdout.split("\n") if l and ".min." not in l],
}
for name, files in lists.items():
    listfile = f"{SCRATCH}/{name.replace(' ', '_')}.list"
    open(listfile, "w").write("\n".join(files) + "\n")
    outdir = f"{SCRATCH}/rt-{name.replace(' ', '_')}"
    subprocess.run(["rm", "-rf", outdir]); os.makedirs(outdir)
    # test262 is a script unless named otherwise; library code decides by its own syntax.
    mode = "strict" if name == "test262 pass" else "check"
    t = time.time(); code, out = sh([PARSE, mode, listfile], 300); ms = (time.time() - t) * 1000
    tail = out.strip().split("\n")[-1]
    check("failed 0" in tail, f"{name}: {tail} ({ms:.0f} ms)")
    sh([PARSE, "printall", listfile, outdir], 300)
    code, out = sh(["node", "tools/roundtrip.mjs", listfile, outdir, "--show", "3"], 600)
    r = json.loads(out.split("\n")[0])
    check(r["differs"] == 0 and r["ourOutputInvalid"] == 0 and r["ourParserFailed"] == 0,
          f"{name}: round trip identical={r['identical']} same-tree={r['sameAcornTree']} differs={r['differs']} invalid={r['ourOutputInvalid']} (esbuild rejects {r['esbuildRejectsOriginal']})")
for name in ["fail", "early"]:
    files = sorted(glob.glob(f"vendor/test262-parser-tests/{name}/*.js"))
    listfile = f"{SCRATCH}/{name}.list"; open(listfile, "w").write("\n".join(files) + "\n")
    code, out = sh([PARSE, "accepted", listfile], 300)
    tail = out.strip().split(chr(10))[-1]
    m = re.match(r"parsed (\d+) failed (\d+)", tail)
    print(f"  info test262 {name}/: rejected {m.group(2)} of {int(m.group(1)) + int(m.group(2))}")

print("== bundles against esbuild")
for a in "named all cjs features three zod rx datefns preact immer react d3".split():
    theirs, ours = f"{SCRATCH}/{a}.esb.min.js", f"{SCRATCH}/{a}.min.js"
    sh([E, f"app/{a}.js", "--bundle", "--minify", "--format=iife", f"--outfile={theirs}", "--log-level=silent"])
    expected = sh(["node", theirs], 15)[1]
    code, out = sh([ESB, f"app/{a}.js", "--minify", f"--outfile={ours}"], 60)
    got = sh(["node", ours], 15)[1] if code == 0 else out
    o, e = os.path.getsize(ours) if code == 0 else 0, os.path.getsize(theirs)
    check(code == 0 and got == expected, f"{a}: minified output same; size {o} vs {e} ({(o-e)*100/e:+.1f}%), gzip {len(gzip.compress(open(ours,'rb').read())) if code==0 else 0} vs {len(gzip.compress(open(theirs,'rb').read()))}")

print("== normalized identity with esbuild (unminified)")
norm = "const e=require('esbuild'),fs=require('fs');const n=f=>e.transformSync(fs.readFileSync(f,'utf8'),{loader:'js',legalComments:'none',minifyWhitespace:true,logLevel:'silent'}).code;console.log(n(process.argv[1])===n(process.argv[2]))"
for a in ["named", "all"]:
    theirs, ours = f"{SCRATCH}/{a}.esb.js", f"{SCRATCH}/{a}.js"
    sh([E, f"app/{a}.js", "--bundle", "--format=iife", f"--outfile={theirs}", "--log-level=silent"])
    sh([ESB, f"app/{a}.js", f"--outfile={ours}"], 60)
    check(sh(["node", "-e", norm, ours, theirs])[1].strip() == "true", f"{a}: byte-identical after normalizing")

print("== whole-API differential")
for a in "exes excjs exdate exd3 eximmer".split():
    plain, mini = f"{SCRATCH}/{a}.esb.js", f"{SCRATCH}/{a}.esb.min.js"
    sh([E, f"app/{a}.js", "--bundle", "--format=iife", f"--outfile={plain}", "--log-level=silent"])
    sh([E, f"app/{a}.js", "--bundle", "--minify", "--format=iife", f"--outfile={mini}", "--log-level=silent"])
    l1, l2 = sh(["node", plain])[1].split("\n"), sh(["node", mini])[1].split("\n")
    stable = [i for i in range(min(len(l1), len(l2))) if l1[i] == l2[i]]
    for mode, flags in [("plain", []), ("minified", ["--minify"])]:
        out = f"{SCRATCH}/{a}.{mode}.js"
        sh([ESB, f"app/{a}.js", f"--outfile={out}"] + flags, 60)
        lx = sh(["node", out])[1].split("\n")
        bad = [i for i in stable if i >= len(lx) or lx[i] != l1[i]]
        total = next((x for x in l1 if x.startswith("TOTAL")), "")
        check(not bad, f"{a} {mode}: {len(stable)} stable lines all agree {total}")

print("== formats")
for fmt, ext, use in [("esm", "mjs", "import('{}').then(m=>console.log(Object.keys(m).sort().join(),m.answer,m.hello('x'),new m.default().hi()))"),
                      ("cjs", "cjs", "const m=require('{}');console.log(Object.keys(m).sort().join(),m.answer,m.hello('x'),new m.default().hi())")]:
    for flags in [[], ["--minify"]]:
        o = os.path.abspath(f"{SCRATCH}/lib{''.join(flags)}.{ext}"); e = os.path.abspath(f"{SCRATCH}/lib.esb{''.join(flags)}.{ext}")
        sh([ESB, "app/lib.js", f"--format={fmt}", f"--outfile={o}"] + flags)
        sh([E, "app/lib.js", "--bundle", f"--format={fmt}", f"--outfile={e}", "--log-level=silent"] + flags)
        a, b = sh(["node", "-e", use.format(o)])[1], sh(["node", "-e", use.format(e)])[1]
        check(a == b and "42" in a, f"{fmt}{' '.join(flags)}: {a.strip()}")

print("== source maps")
for a in ["named", "cjs", "features"]:
    out = f"{SCRATCH}/{a}.sm.js"
    sh([ESB, f"app/{a}.js", "--sourcemap", f"--outfile={out}"])
    code, text = sh(["node", "tools/checkmap.mjs", out])
    m = re.search(r"(\d+) sources, (\d+) mappings, (\d+) check out", text)
    check(m and m.group(2) == m.group(3), f"{a}: {m.group(0) if m else text[:80]}")

print()
print("FAILED:" if failures else "All checks passed.")
for f in failures: print("  " + f)
sys.exit(1 if failures else 0)
