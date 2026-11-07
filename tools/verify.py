#!/usr/bin/env python3
# Everything the bundler claims, checked against esbuild and acorn. Run from anywhere; it works in tests/.
#   usage: verify.py ESB-BINARY JSPARSE-BINARY
import glob, gzip, json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard
ESB, PARSE = guard.in_tests(sys.argv[1:3])
SCRATCH = "../out/verify"; os.makedirs(SCRATCH, exist_ok=True)
E = "node_modules/.bin/esbuild"
failures = []
# `ESB_FLAGS` adds options to every build of ours, to run the whole suite under another plan.
EXTRA = os.environ.get("ESB_FLAGS", "").split()
def sh(cmd, timeout=120):
    if EXTRA and cmd and cmd[0] == ESB: cmd = cmd + EXTRA
    # Everything runs under a memory cap as well as a clock: a runaway fails one check.
    code, out, err, peak, reason = guard.run(cmd, 4000, timeout, quiet=True)
    if reason: return 124, "STOPPED: " + reason
    return code, out + err
def check(ok, label):
    print(("  ok   " if ok else "  FAIL ") + label)
    if not ok: failures.append(label)

print("== parser")
lists = {
    "lodash.js": ["node_modules/lodash/lodash.js"],
    "lodash-es": sorted(glob.glob("node_modules/lodash-es/*.js")),
    "test262 pass": sorted(glob.glob("test262/pass/*.js")),
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
    code, out = sh(["node", "oracles/roundtrip.mjs", listfile, outdir, "--show", "3"], 600)
    r = json.loads(out.split("\n")[0])
    check(r["differs"] == 0 and r["ourOutputInvalid"] == 0 and r["ourParserFailed"] == 0,
          f"{name}: round trip identical={r['identical']} same-tree={r['sameAcornTree']} differs={r['differs']} invalid={r['ourOutputInvalid']} (esbuild rejects {r['esbuildRejectsOriginal']})")
for name in ["fail", "early"]:
    files = sorted(glob.glob(f"test262/{name}/*.js"))
    listfile = f"{SCRATCH}/{name}.list"; open(listfile, "w").write("\n".join(files) + "\n")
    code, out = sh([PARSE, "accepted", listfile], 300)
    tail = out.strip().split(chr(10))[-1]
    m = re.match(r"parsed (\d+) failed (\d+)", tail)
    print(f"  info test262 {name}/: rejected {m.group(2)} of {int(m.group(1)) + int(m.group(2))}")

# A library inside one function is parsed in pieces of its body: put together, the same tree.
code, out = sh([PARSE, "pieces", "node_modules/lodash/lodash.js"], 60)
check(code == 0 and "inside the function body" in out and "the same tree as parsing it whole" in out,
      "lodash.js in pieces of its function's body: " + (out.strip().split("\n")[-1] if out.strip() else "no output"))

print("== bundles against esbuild")
for a in "named all cjs features three zod rx datefns preact immer react d3 reexport".split():
    theirs, ours = f"{SCRATCH}/{a}.esb.min.js", f"{SCRATCH}/{a}.min.js"
    sh([E, f"apps/{a}.js", "--bundle", "--minify", "--format=iife", f"--outfile={theirs}", "--log-level=silent"])
    expected = sh(["node", theirs], 15)[1]
    code, out = sh([ESB, f"apps/{a}.js", "--minify", f"--outfile={ours}"], 60)
    got = sh(["node", ours], 15)[1] if code == 0 else out
    o, e = os.path.getsize(ours) if code == 0 else 0, os.path.getsize(theirs)
    check(code == 0 and got == expected, f"{a}: minified output same; size {o} vs {e} ({(o-e)*100/e:+.1f}%), gzip {len(gzip.compress(open(ours,'rb').read())) if code==0 else 0} vs {len(gzip.compress(open(theirs,'rb').read()))}")

print("== normalized identity with esbuild (unminified)")
norm = "const e=require('esbuild'),fs=require('fs');const n=f=>e.transformSync(fs.readFileSync(f,'utf8'),{loader:'js',legalComments:'none',minifyWhitespace:true,logLevel:'silent'}).code;console.log(n(process.argv[1])===n(process.argv[2]))"
for a in ["named", "all"]:
    theirs, ours = f"{SCRATCH}/{a}.esb.js", f"{SCRATCH}/{a}.js"
    sh([E, f"apps/{a}.js", "--bundle", "--format=iife", f"--outfile={theirs}", "--log-level=silent"])
    sh([ESB, f"apps/{a}.js", f"--outfile={ours}"], 60)
    check(sh(["node", "-e", norm, ours, theirs])[1].strip() == "true", f"{a}: byte-identical after normalizing")

print("== whole-API differential")
for a in "exes excjs exdate exd3 eximmer".split():
    plain, mini = f"{SCRATCH}/{a}.esb.js", f"{SCRATCH}/{a}.esb.min.js"
    sh([E, f"apps/{a}.js", "--bundle", "--format=iife", f"--outfile={plain}", "--log-level=silent"])
    sh([E, f"apps/{a}.js", "--bundle", "--minify", "--format=iife", f"--outfile={mini}", "--log-level=silent"])
    # A line counts only if esbuild's own builds agree on it across several runs: one pair could
    # agree on a clock's value by chance.
    runs = [sh(["node", f])[1].split("\n") for f in (plain, mini, plain, mini, plain)]
    l1 = runs[0]
    stable = [i for i in range(min(len(r) for r in runs)) if all(r[i] == l1[i] for r in runs)]
    for mode, flags in [("plain", []), ("minified", ["--minify"])]:
        out = f"{SCRATCH}/{a}.{mode}.js"
        sh([ESB, f"apps/{a}.js", f"--outfile={out}"] + flags, 60)
        lx = sh(["node", out])[1].split("\n")
        bad = [i for i in stable if i >= len(lx) or lx[i] != l1[i]]
        total = next((x for x in l1 if x.startswith("TOTAL")), "")
        check(not bad, f"{a} {mode}: {len(stable)} stable lines all agree {total}")
        if bad:
            at = bad[0]
            print(f"       line {at}: esbuild {l1[at][:150]!r}")
            print(f"       line {at}: ours    {(lx[at] if at < len(lx) else '<missing>')[:150]!r}")

print("== formats")
for fmt, ext, use in [("esm", "mjs", "import('{}').then(m=>console.log(Object.keys(m).sort().join(),m.answer,m.hello('x'),new m.default().hi()))"),
                      ("cjs", "cjs", "const m=require('{}');console.log(Object.keys(m).sort().join(),m.answer,m.hello('x'),new m.default().hi())")]:
    for flags in [[], ["--minify"]]:
        o = os.path.abspath(f"{SCRATCH}/lib{''.join(flags)}.{ext}"); e = os.path.abspath(f"{SCRATCH}/lib.esb{''.join(flags)}.{ext}")
        sh([ESB, "apps/lib.js", f"--format={fmt}", f"--outfile={o}"] + flags)
        sh([E, "apps/lib.js", "--bundle", f"--format={fmt}", f"--outfile={e}", "--log-level=silent"] + flags)
        a, b = sh(["node", "-e", use.format(o)])[1], sh(["node", "-e", use.format(e)])[1]
        check(a == b and "42" in a, f"{fmt}{' '.join(flags)}: {a.strip()}")

print("== build options against esbuild")
OPT = ["--alias:fake-math/sum=./apps/opt/real/sum.js", "--loader:.txt=text", "--loader:.b64=base64", "--loader:.url=dataurl"]
for name, entry, flags in [("alias and loaders", "apps/opt/main.js", OPT),
                           ("banner and footer", "apps/opt/main.js", OPT + ["--banner:js=/* top */", "--footer:js=/* end */"]),
                           ("minified", "apps/opt/main.js", OPT + ["--minify"]),
                           ("tree shaking off", "apps/opt2/main.js", ["--tree-shaking=false"])]:
    tag = name.replace(" ", "_")
    ours, theirs = f"{SCRATCH}/opt-{tag}.js", f"{SCRATCH}/opt-{tag}.esb.js"
    sh([E, entry, "--bundle", f"--outfile={theirs}", "--log-level=silent"] + flags)
    code, out = sh([ESB, entry, f"--outfile={ours}"] + flags, 60)
    check(code == 0 and sh(["node", ours], 15)[1] == sh(["node", theirs], 15)[1], f"{name}: same output as esbuild's")
top = open(f"{SCRATCH}/opt-banner_and_footer.js").read()
check(top.startswith("/* top */\n") and top.endswith("/* end */\n"), "banner and footer: where esbuild puts them")
kept = open(f"{SCRATCH}/opt-tree_shaking_off.js").read()
check("UNUSED_MARKER" in kept and "OTHER_MARKER" in kept, "tree shaking off: unused statements stay")

print("== JSX against esbuild")
JSX = "apps/jsx"
NODE = ["--platform=node"]
for entry, flags in [("main.jsx", []), ("main.jsx", ["--minify"]), ("main.jsx", ["--minify-syntax"]),
                     ("main.jsx", ["--jsx-side-effects"]), ("pragma.jsx", []), ("preact.jsx", []), ("preact.jsx", ["--minify"]),
                     ("plain.js", ["--loader:.js=jsx", "--jsx-factory=h"]),
                     ("auto.jsx", ["--jsx=automatic"] + NODE), ("auto.jsx", ["--jsx=automatic", "--minify"] + NODE),
                     ("pragma2.jsx", NODE), ("dev.jsx", ["--jsx=automatic", "--jsx-dev"] + NODE)]:
    a, b = f"{SCRATCH}/jsx.o.cjs", f"{SCRATCH}/jsx.e.cjs"
    code, text = sh([ESB, f"{JSX}/{entry}", f"--outfile={a}"] + flags)
    sh([E, f"{JSX}/{entry}", "--bundle", "--log-level=error", f"--outfile={b}"] + flags)
    ra, rb = sh(["node", a], 30), sh(["node", b], 30)
    label = " ".join([entry] + flags)
    check(code == 0 and ra[0] == 0 and ra[1] and ra[1] == rb[1], f"{label}: same output as esbuild's ({len(ra[1])} bytes)")
# Kept JSX has to be JSX that still means the same: run both through esbuild's own lowering.
SHIM = '--banner:js=const React={createElement:(t,p,...c)=>({type:typeof t=="function"?"fn":t,props:p,children:c}),Fragment:"<fragment>"};'
for flags in [[], ["--minify"]]:
    a, b = f"{SCRATCH}/jsx.po.jsx", f"{SCRATCH}/jsx.pe.jsx"
    sh([ESB, f"{JSX}/main.jsx", "--jsx=preserve", f"--outfile={a}"] + flags)
    sh([E, f"{JSX}/main.jsx", "--bundle", "--jsx=preserve", "--log-level=error", f"--outfile={b}"] + flags)
    sh([E, a, "--bundle", "--log-level=error", SHIM, f"--outfile={a}.cjs"])
    sh([E, b, "--bundle", "--log-level=error", SHIM, f"--outfile={b}.cjs"])
    ra, rb = sh(["node", a + ".cjs"], 30), sh(["node", b + ".cjs"], 30)
    check(ra[0] == 0 and ra[1] and ra[1] == rb[1], f"--jsx=preserve {' '.join(flags)}: means what esbuild's means")
code, text = sh([ESB, f"{JSX}/mismatch.jsx", f"--outfile={SCRATCH}/jsx.bad.js"])
check(code != 0 and "does not match" in text, "a closing tag that does not match is an error")

print("== TypeScript against esbuild")
for entry in ["main", "eq", "rx", "zod3", "zod4", "immer"]:
    for flags in [[], ["--minify"]]:
        a, b = f"{SCRATCH}/ts.o.cjs", f"{SCRATCH}/ts.e.cjs"
        code, text = sh([ESB, f"apps/ts/{entry}.ts", f"--outfile={a}"] + flags)
        sh([E, f"apps/ts/{entry}.ts", "--bundle", "--log-level=error", f"--outfile={b}"] + flags)
        ra, rb = sh(["node", a], 30), sh(["node", b], 30)
        size = f"{os.path.getsize(a)} vs {os.path.getsize(b)} bytes" if "--minify" in flags else f"{len(ra[1])} bytes of output"
        check(code == 0 and ra[0] == 0 and ra[1] and ra[1] == rb[1], f"{' '.join([entry] + flags)}: same output as esbuild's; {size}")
all_ts = subprocess.run("find node_modules -name '*.ts' -o -name '*.tsx' -o -name '*.mts' -o -name '*.cts'", shell=True, capture_output=True, text=True).stdout.split()
source = [f for f in all_ts if not re.search(r"\.d\.[mc]?ts$", f)]
declarations = [f for f in all_ts if re.search(r"\.d\.[mc]?ts$", f)]
for name, files in [("sources", source), ("declarations", declarations)]:
    listfile = f"{SCRATCH}/ts-{name}.list"; open(listfile, "w").write("\n".join(files) + "\n")
    code, out = sh([PARSE, "check", listfile], 300)
    tail = out.strip().split("\n")[-1]
    # Esbuild rejects these too. Three say `export const x: T;`, and four are `export =       function
    # f(): T;`, a find-and-replace on `export default` in the package's own build.
    rejected = set() if name == "sources" else {f"node_modules/{f}" for f in [
        "acorn/dist/acorn.d.ts", "acorn/dist/acorn.d.mts", "preact/src/index.d.ts",
        "@jridgewell/trace-mapping/types/by-source.d.cts", "@jridgewell/trace-mapping/types/resolve.d.cts",
        "@jridgewell/trace-mapping/types/strip-filename.d.cts", "@jridgewell/trace-mapping/types/sort.d.cts"]}
    failed = set(re.findall(r"^FAIL (\S+?):\d+:\d+", out, re.M))
    check("parsed" in tail and failed == rejected, f"every TypeScript file in node_modules, {name}: {tail}, {len(rejected)} expected")

print("== side effects against esbuild")
for a in "globs via-named via-star via-local via-ns via-whole via-none".split():
    ours, theirs = f"{SCRATCH}/fx.o.cjs", f"{SCRATCH}/fx.e.cjs"
    sh([ESB, f"apps/fx/{a}.js", f"--outfile={ours}"])
    sh([E, f"apps/fx/{a}.js", "--bundle", "--log-level=error", f"--outfile={theirs}"])
    x, y = sh(["node", ours], 15)[1], sh(["node", theirs], 15)[1]
    check(x and x == y, f"{a}: runs the same module effects")

print("== code splitting against esbuild")
def split_outputs(entries, flags):
    for d in [f"{SCRATCH}/split-o", f"{SCRATCH}/split-e"]:
        os.makedirs(d, exist_ok=True)
        for f in glob.glob(d + "/**/*.*", recursive=True):
            if os.path.isfile(f): os.unlink(f)
    sh([ESB] + entries + ["--splitting", "--format=esm", f"--outdir={SCRATCH}/split-o"] + flags)
    sh([E] + entries + ["--bundle", "--splitting", "--format=esm", f"--outdir={SCRATCH}/split-e", "--log-level=error"] + flags)
    listing = lambda d: sorted(re.sub(r"-[A-Z0-9]{8}\.js$", ".js", os.path.relpath(f, d)) for f in glob.glob(d + "/**/*.js", recursive=True))
    return listing(f"{SCRATCH}/split-o"), listing(f"{SCRATCH}/split-e")
for label, entries, flags in [("fixture", ["apps/split/a.js", "apps/split/b.js"], []),
                              ("fixture minified", ["apps/split/a.js", "apps/split/b.js"], ["--minify"]),
                              ("nested directories", ["apps/split/a.js", "apps/split/sub/nested.js"], []),
                              ("lodash-es, rxjs, d3 and import()", ["apps/split/real1.js", "apps/split/real2.js"], []),
                              ("the same, minified", ["apps/split/real1.js", "apps/split/real2.js"], ["--minify"]),
                              ("TypeScript", ["apps/split/ts-entry.ts"], [])]:
    ours, theirs = split_outputs(entries, flags)
    same = True
    for en in entries:
        name = re.sub(r"\.[a-z]+$", ".js", en.replace("apps/split/", ""))
        x, y = sh(["node", f"{SCRATCH}/split-o/{name}"], 30), sh(["node", f"{SCRATCH}/split-e/{name}"], 30)
        same = same and x[0] == 0 and x[1] and x[1] == y[1]
    check(same and ours == theirs, f"{label}: same output as esbuild's, in the same {len(ours)} files")

print("== lowering for older targets, against esbuild and acorn")
def lowered_check(entry, year, flags, label):
    a, b = f"{SCRATCH}/low.o.cjs", f"{SCRATCH}/low.e.cjs"
    code, text = sh([ESB, entry, f"--target=es{year}", f"--outfile={a}"] + flags, 120)
    sh([E, entry, "--bundle", f"--target=es{year}", "--log-level=error", f"--outfile={b}"] + flags, 120)
    parsed = sh(["node", "oracles/check-target.mjs", a, str(year)], 60)[1].strip()
    ra, rb = sh(["node", a], 60), sh(["node", b], 60)
    check(code == 0 and parsed == "ok" and ra[0] == 0 and ra[1] and ra[1] == rb[1],
          f"{label} at es{year} {' '.join(flags)}: {parsed[:120]}, same output as esbuild's")
for year in [2021, 2019, 2017, 2015]:
    lowered_check("apps/lower/all.js", year, [], "every lowered feature")
lowered_check("apps/lower/all.js", 2015, ["--minify"], "every lowered feature")
for app in ["immer", "rx", "zod", "preact", "features", "datefns", "exes", "excjs", "exdate", "eximmer"]:
    lowered_check(f"apps/{app}.js", 2015, ["--minify"], app)
lowered_check("apps/react.js", 2017, ["--platform=node"], "react")
for app in ["rx", "zod4", "immer", "main"]:
    lowered_check(f"apps/ts/{app}.ts", 2018, [], f"{app}.ts")

print("== stylesheets against esbuild")
def css_normal(path):
    text = re.sub(r"-[A-Z0-9]{8}\.", "-HASH.", open(path).read())
    return subprocess.run([E, "--minify", "--loader=css", "--log-level=error"], input=text, capture_output=True, text=True, timeout=60).stdout
FILE_LOADERS = ["--loader:.png=file", "--loader:.woff2=file"]
for entry, flags in [("apps/css/main.css", []), ("apps/css/main.css", ["--minify"]), ("apps/css/edge.css", []), ("apps/css/edge.css", ["--minify"])]:
    for d in [f"{SCRATCH}/css-o", f"{SCRATCH}/css-e"]:
        os.makedirs(d, exist_ok=True)
        for f in glob.glob(d + "/*"): os.unlink(f)
    code, _ = sh([ESB, entry, f"--outfile={SCRATCH}/css-o/out.css"] + FILE_LOADERS + flags)
    sh([E, entry, "--bundle", f"--outfile={SCRATCH}/css-e/out.css", "--log-level=error"] + FILE_LOADERS + flags)
    names = lambda d: sorted(re.sub(r"-[A-Z0-9]{8}\.", "-HASH.", os.path.basename(f)) for f in glob.glob(d + "/*"))
    same = code == 0 and css_normal(f"{SCRATCH}/css-o/out.css") == css_normal(f"{SCRATCH}/css-e/out.css")
    check(same and names(f"{SCRATCH}/css-o") == names(f"{SCRATCH}/css-e"),
          f"{entry} {' '.join(flags)}: the same stylesheet as esbuild's, once both are normalised; {os.path.getsize(f'{SCRATCH}/css-o/out.css')} vs {os.path.getsize(f'{SCRATCH}/css-e/out.css')} bytes")
for flags in [[], ["--minify"]]:
    for d in [f"{SCRATCH}/css-o", f"{SCRATCH}/css-e"]:
        for f in glob.glob(d + "/*"): os.unlink(f)
    sh([ESB, "apps/css/entry.js", f"--outfile={SCRATCH}/css-o/app.js"] + FILE_LOADERS + flags)
    sh([E, "apps/css/entry.js", "--bundle", f"--outfile={SCRATCH}/css-e/app.js", "--log-level=error"] + FILE_LOADERS + flags)
    ran = [re.sub(r"-[A-Z0-9]{8}\.", "-HASH.", sh(["node", f"{SCRATCH}/css-{w}/app.js"], 15)[1]) for w in "oe"]
    check(ran[0] and ran[0] == ran[1] and css_normal(f"{SCRATCH}/css-o/app.css") == css_normal(f"{SCRATCH}/css-e/app.css"),
          f"stylesheets imported from JavaScript, and the file loader {' '.join(flags)}: same as esbuild's")

print("== legal comments against esbuild")
def legal_tail(path):
    t = open(path).read()
    return re.findall(r"^(/\*.*?\*/|//.*)$", t[t.rfind("})();") if path.endswith(".js") else t.rfind("}"):], re.M | re.S)
for entry, ext, flags in [("apps/legal/a.js", "js", []), ("apps/legal/a.js", "js", ["--minify"]), ("apps/legal/a.js", "js", ["--legal-comments=external"]),
                          ("apps/legal/a.js", "js", ["--legal-comments=none"]), ("apps/legal/c.css", "css", []), ("apps/legal/c.css", "css", ["--minify"])]:
    outs = [f"{SCRATCH}/lg-{w}.{ext}" for w in "oe"]
    for o in outs:
        if os.path.exists(o + ".LEGAL.txt"): os.unlink(o + ".LEGAL.txt")
    sh([ESB, entry, f"--outfile={outs[0]}"] + flags)
    sh([E, entry, "--bundle", f"--outfile={outs[1]}", "--log-level=error"] + flags)
    files = [open(o + ".LEGAL.txt").read() if os.path.exists(o + ".LEGAL.txt") else "" for o in outs]
    check(legal_tail(outs[0]) == legal_tail(outs[1]) and files[0] == files[1], f"{entry} {' '.join(flags)}: legal comments where esbuild puts them")

for app in ["react", "named", "three", "all", "cjs"]:
    outs = [f"{SCRATCH}/lgapp-{w}.js" for w in "oe"]
    sh([ESB, f"apps/{app}.js", f"--outfile={outs[0]}"])
    sh([E, f"apps/{app}.js", "--bundle", f"--outfile={outs[1]}", "--log-level=error"])
    tails = [open(o).read()[open(o).read().rindex("})();") + 5:] for o in outs]
    check(tails[0] == tails[1] and len(tails[0]) > 1, f"{app}: the same license block as esbuild's, byte for byte ({len(tails[0])} bytes)")

print("== tsconfig.json against esbuild")
for entry, flags in [("apps/tsc/src/main.tsx", ["--platform=node"]), ("apps/tsc/src/main.tsx", ["--platform=node", "--minify"]),
                     ("apps/tsc2/main.ts", []), ("apps/tsc2/main.ts", ["--minify"]), ("apps/tsc2/main.ts", ["--tsconfig=apps/tsc/tsconfig.json"])]:
    a, b = f"{SCRATCH}/tc.o.cjs", f"{SCRATCH}/tc.e.cjs"
    code, _ = sh([ESB, entry, f"--outfile={a}"] + flags)
    sh([E, entry, "--bundle", f"--outfile={b}", "--log-level=error"] + flags)
    ra, rb = sh(["node", a], 30), sh(["node", b], 30)
    check(code == 0 and ra[0] == 0 and ra[1] and ra[1] == rb[1], f"{entry} {' '.join(flags)}: same output as esbuild's")

print("== more options against esbuild")
for entry, flags in [("apps/opts/drop.js", ["--drop:console"]), ("apps/opts/drop.js", ["--drop:debugger"]),
                     ("apps/opts/drop.js", ["--minify", "--drop:console", "--drop:debugger"]),
                     ("apps/opts/drop.js", ["--pure:makeThing", "--pure:lib.factory"]),
                     ("apps/opts/drop.js", ["--packages=external", "--platform=node"]),
                     ("apps/opts/charset.js", []), ("apps/opts/charset.js", ["--charset=utf8"]), ("apps/opts/charset.js", ["--minify"]),
                     ("apps/named.js", ["--main-fields=main,module"]), ("apps/named.js", ["--conditions=node"])]:
    a, b = f"{SCRATCH}/op.o.cjs", f"{SCRATCH}/op.e.cjs"
    code, _ = sh([ESB, entry, f"--outfile={a}"] + flags)
    sh([E, entry, "--bundle", f"--outfile={b}", "--log-level=error"] + flags)
    ra, rb = sh(["node", a], 30), sh(["node", b], 30)
    check(code == 0 and ra[0] == rb[0] and ra[1] == rb[1], f"{entry} {' '.join(flags)}: same output as esbuild's")
for flags in [["--drop:console"], ["--drop:debugger"]]:
    sh([ESB, "apps/opts/drop.js", f"--outfile={SCRATCH}/op.o.cjs"] + flags)
    text = open(f"{SCRATCH}/op.o.cjs").read()
    gone = "drop me" not in text if flags == ["--drop:console"] else "debugger" not in text
    check(gone, f"{flags[0]}: gone from the output")
sh([ESB, "apps/opts/charset.js", f"--outfile={SCRATCH}/op.o.cjs"])
lines = [l for l in open(f"{SCRATCH}/op.o.cjs", encoding="utf-8").read().split("\n") if any(ord(c) > 127 for c in l)]
check(len(lines) == 1 and "/[" in lines[0], f"ASCII output: only the regular expressions keep their bytes ({len(lines)} line)")

print("== decorators against esbuild")
for flags in [[], ["--minify"], ["--target=es2020"]]:
    a, b = f"{SCRATCH}/dc.o.cjs", f"{SCRATCH}/dc.e.cjs"
    code, _ = sh([ESB, "apps/dec/main.ts", f"--outfile={a}"] + flags)
    sh([E, "apps/dec/main.ts", "--bundle", f"--outfile={b}", "--log-level=error"] + flags)
    ra, rb = sh(["node", a], 30), sh(["node", b], 30)
    check(code == 0 and ra[0] == 0 and ra[1] and ra[1] == rb[1], f"experimentalDecorators {' '.join(flags)}: same output, in the same order, as esbuild's")

print("== the spec language")
SPEC = os.path.join(os.path.dirname(ESB), "spec")
code, out = sh([SPEC], 60)
check(code == 0, "the spec builds all its targets")
got = sh(["node", "-e", "require('../out/spec/plugged.js');console.log(globalThis.bundled.summary)"], 15)[1].strip()
check(got == '1.2.3 greetings, "friend"', f"plugins, a spec-defined format, a loader: {got}")
check(open("../out/spec/plugged.js").read().startswith("/* built by the spec */\n"), "a spec's banner")
got = sh(["node", "../out/spec/ui.cjs"], 15)[1].strip()
check(got == '["a",{"x":"1"},["b"]]', f"a spec's JSX settings: {got}")
old = sh(["node", "oracles/check-target.mjs", "../out/spec/old.js", "2017"], 30)[1].strip()
ran = sh(["node", "../out/spec/old.js"], 30)[1].strip()
check(old == "ok" and ran == "4 4", f"a spec's syntax target: {old}, {ran}")
# A spec is data: the same program builds another one, and a step it does not offer is an error
# in the spec, at the name.
other = f"{SCRATCH}/other.bundler"
with open(other, "w") as f:
    f.write('bundler\nformat f\n  prefix "\\x41\\u{42}\\t"\nend\n'
            f'target a\n  entry "apps/lib.js"\n  outfile "{SCRATCH}/other.js"\n  format f\nend\n')
code, _ = sh([SPEC, other], 60)
check(code == 0 and open(f"{SCRATCH}/other.js").read().startswith("AB\t"), "another spec, read when the program runs, its strings unescaped")
with open(other, "w") as f:
    f.write('bundler\ntarget a\n  entry "apps/lib.js"\n  outfile "x.js"\n  transform strip-debug nope\nend\n')
code, out = sh([SPEC, other], 60)
check(code != 0 and f"{other}:5:25: no pass named nope" in out, f"a step the program does not offer: {out.strip().splitlines()[0] if out.strip() else ''}")

print("== the rules language")
code, out = sh([os.path.join(os.path.dirname(ESB), "langtest")], 30)
check(code == 0 and out.strip().endswith("all checks passed"), f"collection forms mean what they say: {out.strip().split(chr(10))[-1]}")

print("== source maps")
for a in ["named.js", "cjs.js", "features.js", "jsx/main.jsx"]:
    out = f"{SCRATCH}/{a.replace('/', '_')}.sm.js"
    sh([ESB, f"apps/{a}", "--sourcemap", f"--outfile={out}"])
    code, text = sh(["node", "oracles/checkmap.mjs", out])
    m = re.search(r"(\d+) sources, (\d+) mappings, (\d+) check out", text)
    check(m and m.group(2) == m.group(3), f"{a}: {m.group(0) if m else text[:80]}")

print("== standard output")
# With nowhere to write, one bundle goes to standard output, as esbuild's does, its map inline.
def printed(args):
    code, out, err, _, reason = guard.run([ESB] + args + EXTRA, 4000, 120, quiet=True)
    return (124 if reason else code), out, err
filed = f"{SCRATCH}/printed.js"
sh([ESB, "apps/named.js", f"--outfile={filed}"])
code, out, _ = printed(["apps/named.js"])
check(code == 0 and out == open(filed).read(), "a bundle with no output path is printed, the same as the file")
sh([ESB, "apps/named.js", "--sourcemap", f"--outfile={filed}"])
code, out, _ = printed(["apps/named.js", "--sourcemap"])
body, _, url = out.rstrip("\n").rpartition("\n")
import base64
inline = json.loads(base64.b64decode(url.split(",", 1)[1])) if url.startswith("//# sourceMappingURL=data:application/json;base64,") else {}
filemap = json.load(open(filed + ".map"))
# Its sources are named from where the build runs, as esbuild's are, not from where a file would go.
same_map = inline and all(inline[k] == filemap[k] for k in ["mappings", "sourcesContent", "names"]) and \
    all(f.endswith("/" + i) for f, i in zip(filemap["sources"], inline["sources"]))
with open(f"{SCRATCH}/inline.js", "w") as f: f.write(body + "\n")
with open(f"{SCRATCH}/inline.js.map", "w") as f: json.dump(inline, f)
m = re.search(r"(\d+) sources, (\d+) mappings, (\d+) check out", sh(["node", "oracles/checkmap.mjs", f"{SCRATCH}/inline.js"])[1])
check(code == 0 and same_map and m and m.group(2) == m.group(3) and body + "\n" == open(filed).read().rpartition("//# sourceMappingURL")[0],
      f"a printed bundle's source map is inline, the file's map named from here: {m.group(0) if m else 'no map'}")
with open(f"{SCRATCH}/sheet.css", "w") as f: f.write("body { color: red }\n")
with open(f"{SCRATCH}/sheeted.js", "w") as f: f.write('import "./sheet.css"\nconsole.log(1)\n')
for args, says in [([f"{SCRATCH}/sheeted.js"], "standard output takes one"),
                   (["apps/named.js", "--loader:.png=file"], "the file loader needs an output path"),
                   (["apps/named.js", "--legal-comments=external"], "legal comments need an output path")]:
    code, out, err = printed(args)
    check(code != 0 and out == "" and says in err, f"{' '.join(args)}: {says}")

print("== external modules")
# An entry outside any project, its packages left external: in ES module output each import stays a
# statement binding its own names, so a default import is the module's default, as when it runs
# unbundled. The checks run from tests/, whose package.json must not be taken for one at the root.
import tempfile
OUT = tempfile.mkdtemp(prefix="esb-ext-")
def put(rel, text):
    os.makedirs(os.path.dirname(f"{OUT}/{rel}"), exist_ok=True)
    with open(f"{OUT}/{rel}", "w") as f: f.write(text)
put("node_modules/dep/package.json", '{"name":"dep","type":"module","main":"index.js"}')
put("node_modules/dep/index.js", 'export default 42; export const x = 1, z = 3;')
put("node_modules/dep2/package.json", '{"name":"dep2","type":"module","main":"index.js"}')
put("node_modules/dep2/index.js", 'globalThis.order = (globalThis.order || "") + "dep2 ";')
put("node_modules/dep2/sub.js", 'export const sub = "dep2/sub";')
put("b.js", 'import {x} from "dep"\nexport const bx = x\nconst y = 1\nexport const by = y\n')
put("w.js", 'import {x} from "dep"\nexport const w = x\n')
put("a.js", 'import d, {x as y} from "dep"\nimport * as ns from "dep"\nimport "dep2"\nimport {sub} from "dep2/sub.js"\n'
            'import {bx, by} from "./b.js"\nexport {z, default as dd} from "dep"\nexport * as all from "dep"\n'
            'const wrapped = require("./w.js")\n'
            'console.log(JSON.stringify([d, y, ns.default, ns.x, sub, bx, by, wrapped.w, globalThis.order]))\n')
put("run.mjs", 'import * as m from "./out.mjs"; console.log(JSON.stringify([m.z, m.dd, m.all.default]))')
ext = ["--external:dep", "--external:dep2"]
for flags in [[], ["--minify"]]:
    code, out = sh([ESB, f"{OUT}/a.js", "--format=esm", f"--outfile={OUT}/out.mjs"] + ext + flags)
    ours = sh(["node", f"{OUT}/out.mjs"], 15)[1] + sh(["node", f"{OUT}/run.mjs"], 15)[1]
    sh([E, f"{OUT}/a.js", "--bundle", "--format=esm", f"--outfile={OUT}/out.mjs", "--log-level=error"] + ext + flags)
    theirs = sh(["node", f"{OUT}/out.mjs"], 15)[1] + sh(["node", f"{OUT}/run.mjs"], 15)[1]
    check(code == 0 and ours == theirs and ours.startswith('[42,1,42,1,"dep2/sub",1,1,1,"dep2 "]'),
          f"ES module output importing external packages {' '.join(flags)}, from outside any project: {ours.splitlines()[0] if code == 0 and ours else out.strip()[:120]}")
    if not flags:
        sh([ESB, f"{OUT}/a.js", "--format=esm", f"--outfile={OUT}/out.mjs"] + ext)
        text = open(f"{OUT}/out.mjs").read()
        # Two imports in a.js, its two re-exports, and one each in b.js and w.js.
        check("__toESM" not in text and len(re.findall(r'from\s*"dep"', text)) == 6,
              "each import of an external module stays an import statement, with no __toESM")
put("u.js", 'import {unused} from "dep"\nimport "dep2"\nconsole.log(1)\n')
sh([ESB, f"{OUT}/u.js", "--format=esm", "--minify-syntax", f"--outfile={OUT}/u.mjs"] + ext)
check(re.search(r'import\s*"dep"', open(f"{OUT}/u.mjs").read()) is not None, "--minify-syntax leaves out an import's unused names, as esbuild does")
# A package left external takes its subpaths with it; one `*` stands for anything.
for flag in ["--external:dep2", "--external:dep*"]:
    code, out = sh([ESB, f"{OUT}/a.js", "--format=esm", f"--outfile={OUT}/out.mjs", "--external:dep", flag])
    check(code == 0 and "dep2/sub.js" in open(f"{OUT}/out.mjs").read(), f"{flag} leaves dep2/sub.js external too")
code, out = sh([ESB, f"{OUT}/a.js", f"--outdir={OUT}/nested/deeper", "--external:dep", "--external:dep2"])
check(code == 0 and os.path.exists(f"{OUT}/nested/deeper/a.js"), "an output directory is made with the ones it is in")
import shutil; shutil.rmtree(OUT, ignore_errors=True)

print()
print("FAILED:" if failures else "All checks passed.")
for f in failures: print("  " + f)
sys.exit(1 if failures else 0)
