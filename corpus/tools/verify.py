#!/usr/bin/env python3
# Everything the bundler claims, checked against esbuild and acorn. Run from corpus/.
#   usage: verify.py ESB-BINARY JSPARSE-BINARY
import glob, gzip, json, os, re, subprocess, sys, time
ESB, PARSE = sys.argv[1], sys.argv[2]
SCRATCH = "out/verify"; os.makedirs(SCRATCH, exist_ok=True)
E = "node_modules/.bin/esbuild"
failures = []
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard
def sh(cmd, timeout=120):
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
for a in "named all cjs features three zod rx datefns preact immer react d3 reexport".split():
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
    # A line counts only if esbuild's own builds agree on it across several runs: one pair could
    # agree on a clock's value by chance.
    runs = [sh(["node", f])[1].split("\n") for f in (plain, mini, plain, mini, plain)]
    l1 = runs[0]
    stable = [i for i in range(min(len(r) for r in runs)) if all(r[i] == l1[i] for r in runs)]
    for mode, flags in [("plain", []), ("minified", ["--minify"])]:
        out = f"{SCRATCH}/{a}.{mode}.js"
        sh([ESB, f"app/{a}.js", f"--outfile={out}"] + flags, 60)
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
        sh([ESB, "app/lib.js", f"--format={fmt}", f"--outfile={o}"] + flags)
        sh([E, "app/lib.js", "--bundle", f"--format={fmt}", f"--outfile={e}", "--log-level=silent"] + flags)
        a, b = sh(["node", "-e", use.format(o)])[1], sh(["node", "-e", use.format(e)])[1]
        check(a == b and "42" in a, f"{fmt}{' '.join(flags)}: {a.strip()}")

print("== build options against esbuild")
OPT = ["--alias:fake-math/sum=./app/opt/real/sum.js", "--loader:.txt=text", "--loader:.b64=base64", "--loader:.url=dataurl"]
for name, entry, flags in [("alias and loaders", "app/opt/main.js", OPT),
                           ("banner and footer", "app/opt/main.js", OPT + ["--banner:js=/* top */", "--footer:js=/* end */"]),
                           ("minified", "app/opt/main.js", OPT + ["--minify"]),
                           ("tree shaking off", "app/opt2/main.js", ["--tree-shaking=false"])]:
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
JSX = "app/jsx"
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
        code, text = sh([ESB, f"app/ts/{entry}.ts", f"--outfile={a}"] + flags)
        sh([E, f"app/ts/{entry}.ts", "--bundle", "--log-level=error", f"--outfile={b}"] + flags)
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
    sh([ESB, f"app/fx/{a}.js", f"--outfile={ours}"])
    sh([E, f"app/fx/{a}.js", "--bundle", "--log-level=error", f"--outfile={theirs}"])
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
for label, entries, flags in [("fixture", ["app/split/a.js", "app/split/b.js"], []),
                              ("fixture minified", ["app/split/a.js", "app/split/b.js"], ["--minify"]),
                              ("nested directories", ["app/split/a.js", "app/split/sub/nested.js"], []),
                              ("lodash-es, rxjs, d3 and import()", ["app/split/real1.js", "app/split/real2.js"], []),
                              ("the same, minified", ["app/split/real1.js", "app/split/real2.js"], ["--minify"]),
                              ("TypeScript", ["app/split/ts-entry.ts"], [])]:
    ours, theirs = split_outputs(entries, flags)
    same = True
    for en in entries:
        name = re.sub(r"\.[a-z]+$", ".js", en.replace("app/split/", ""))
        x, y = sh(["node", f"{SCRATCH}/split-o/{name}"], 30), sh(["node", f"{SCRATCH}/split-e/{name}"], 30)
        same = same and x[0] == 0 and x[1] and x[1] == y[1]
    check(same and ours == theirs, f"{label}: same output as esbuild's, in the same {len(ours)} files")

print("== lowering for older targets, against esbuild and acorn")
def lowered_check(entry, year, flags, label):
    a, b = f"{SCRATCH}/low.o.cjs", f"{SCRATCH}/low.e.cjs"
    code, text = sh([ESB, entry, f"--target=es{year}", f"--outfile={a}"] + flags, 120)
    sh([E, entry, "--bundle", f"--target=es{year}", "--log-level=error", f"--outfile={b}"] + flags, 120)
    parsed = sh(["node", "tools/check-target.mjs", a, str(year)], 60)[1].strip()
    ra, rb = sh(["node", a], 60), sh(["node", b], 60)
    check(code == 0 and parsed == "ok" and ra[0] == 0 and ra[1] and ra[1] == rb[1],
          f"{label} at es{year} {' '.join(flags)}: {parsed[:120]}, same output as esbuild's")
for year in [2021, 2019, 2017, 2015]:
    lowered_check("app/lower/all.js", year, [], "every lowered feature")
lowered_check("app/lower/all.js", 2015, ["--minify"], "every lowered feature")
for app in ["immer", "rx", "zod", "preact", "features", "datefns", "exes", "excjs", "exdate", "eximmer"]:
    lowered_check(f"app/{app}.js", 2015, ["--minify"], app)
lowered_check("app/react.js", 2017, ["--platform=node"], "react")
for app in ["rx", "zod4", "immer", "main"]:
    lowered_check(f"app/ts/{app}.ts", 2018, [], f"{app}.ts")

print("== stylesheets against esbuild")
def css_normal(path):
    text = re.sub(r"-[A-Z0-9]{8}\.", "-HASH.", open(path).read())
    return subprocess.run([E, "--minify", "--loader=css", "--log-level=error"], input=text, capture_output=True, text=True, timeout=60).stdout
FILE_LOADERS = ["--loader:.png=file", "--loader:.woff2=file"]
for entry, flags in [("app/css/main.css", []), ("app/css/main.css", ["--minify"]), ("app/css/edge.css", []), ("app/css/edge.css", ["--minify"])]:
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
    sh([ESB, "app/css/entry.js", f"--outfile={SCRATCH}/css-o/app.js"] + FILE_LOADERS + flags)
    sh([E, "app/css/entry.js", "--bundle", f"--outfile={SCRATCH}/css-e/app.js", "--log-level=error"] + FILE_LOADERS + flags)
    ran = [re.sub(r"-[A-Z0-9]{8}\.", "-HASH.", sh(["node", f"{SCRATCH}/css-{w}/app.js"], 15)[1]) for w in "oe"]
    check(ran[0] and ran[0] == ran[1] and css_normal(f"{SCRATCH}/css-o/app.css") == css_normal(f"{SCRATCH}/css-e/app.css"),
          f"stylesheets imported from JavaScript, and the file loader {' '.join(flags)}: same as esbuild's")

print("== legal comments against esbuild")
def legal_tail(path):
    t = open(path).read()
    return re.findall(r"^(/\*.*?\*/|//.*)$", t[t.rfind("})();") if path.endswith(".js") else t.rfind("}"):], re.M | re.S)
for entry, ext, flags in [("app/legal/a.js", "js", []), ("app/legal/a.js", "js", ["--minify"]), ("app/legal/a.js", "js", ["--legal-comments=external"]),
                          ("app/legal/a.js", "js", ["--legal-comments=none"]), ("app/legal/c.css", "css", []), ("app/legal/c.css", "css", ["--minify"])]:
    outs = [f"{SCRATCH}/lg-{w}.{ext}" for w in "oe"]
    for o in outs:
        if os.path.exists(o + ".LEGAL.txt"): os.unlink(o + ".LEGAL.txt")
    sh([ESB, entry, f"--outfile={outs[0]}"] + flags)
    sh([E, entry, "--bundle", f"--outfile={outs[1]}", "--log-level=error"] + flags)
    files = [open(o + ".LEGAL.txt").read() if os.path.exists(o + ".LEGAL.txt") else "" for o in outs]
    check(legal_tail(outs[0]) == legal_tail(outs[1]) and files[0] == files[1], f"{entry} {' '.join(flags)}: legal comments where esbuild puts them")

for app in ["react", "named", "three", "all", "cjs"]:
    outs = [f"{SCRATCH}/lgapp-{w}.js" for w in "oe"]
    sh([ESB, f"app/{app}.js", f"--outfile={outs[0]}"])
    sh([E, f"app/{app}.js", "--bundle", f"--outfile={outs[1]}", "--log-level=error"])
    tails = [open(o).read()[open(o).read().rindex("})();") + 5:] for o in outs]
    check(tails[0] == tails[1] and len(tails[0]) > 1, f"{app}: the same license block as esbuild's, byte for byte ({len(tails[0])} bytes)")

print("== tsconfig.json against esbuild")
for entry, flags in [("app/tsc/src/main.tsx", ["--platform=node"]), ("app/tsc/src/main.tsx", ["--platform=node", "--minify"]),
                     ("app/tsc2/main.ts", []), ("app/tsc2/main.ts", ["--minify"]), ("app/tsc2/main.ts", ["--tsconfig=app/tsc/tsconfig.json"])]:
    a, b = f"{SCRATCH}/tc.o.cjs", f"{SCRATCH}/tc.e.cjs"
    code, _ = sh([ESB, entry, f"--outfile={a}"] + flags)
    sh([E, entry, "--bundle", f"--outfile={b}", "--log-level=error"] + flags)
    ra, rb = sh(["node", a], 30), sh(["node", b], 30)
    check(code == 0 and ra[0] == 0 and ra[1] and ra[1] == rb[1], f"{entry} {' '.join(flags)}: same output as esbuild's")

print("== more options against esbuild")
for entry, flags in [("app/opts/drop.js", ["--drop:console"]), ("app/opts/drop.js", ["--drop:debugger"]),
                     ("app/opts/drop.js", ["--minify", "--drop:console", "--drop:debugger"]),
                     ("app/opts/drop.js", ["--pure:makeThing", "--pure:lib.factory"]),
                     ("app/opts/drop.js", ["--packages=external", "--platform=node"]),
                     ("app/opts/charset.js", []), ("app/opts/charset.js", ["--charset=utf8"]), ("app/opts/charset.js", ["--minify"]),
                     ("app/named.js", ["--main-fields=main,module"]), ("app/named.js", ["--conditions=node"])]:
    a, b = f"{SCRATCH}/op.o.cjs", f"{SCRATCH}/op.e.cjs"
    code, _ = sh([ESB, entry, f"--outfile={a}"] + flags)
    sh([E, entry, "--bundle", f"--outfile={b}", "--log-level=error"] + flags)
    ra, rb = sh(["node", a], 30), sh(["node", b], 30)
    check(code == 0 and ra[0] == rb[0] and ra[1] == rb[1], f"{entry} {' '.join(flags)}: same output as esbuild's")
for flags in [["--drop:console"], ["--drop:debugger"]]:
    sh([ESB, "app/opts/drop.js", f"--outfile={SCRATCH}/op.o.cjs"] + flags)
    text = open(f"{SCRATCH}/op.o.cjs").read()
    gone = "drop me" not in text if flags == ["--drop:console"] else "debugger" not in text
    check(gone, f"{flags[0]}: gone from the output")
sh([ESB, "app/opts/charset.js", f"--outfile={SCRATCH}/op.o.cjs"])
lines = [l for l in open(f"{SCRATCH}/op.o.cjs", encoding="utf-8").read().split("\n") if any(ord(c) > 127 for c in l)]
check(len(lines) == 1 and "/[" in lines[0], f"ASCII output: only the regular expressions keep their bytes ({len(lines)} line)")

print("== decorators against esbuild")
for flags in [[], ["--minify"], ["--target=es2020"]]:
    a, b = f"{SCRATCH}/dc.o.cjs", f"{SCRATCH}/dc.e.cjs"
    code, _ = sh([ESB, "app/dec/main.ts", f"--outfile={a}"] + flags)
    sh([E, "app/dec/main.ts", "--bundle", f"--outfile={b}", "--log-level=error"] + flags)
    ra, rb = sh(["node", a], 30), sh(["node", b], 30)
    check(code == 0 and ra[0] == 0 and ra[1] and ra[1] == rb[1], f"experimentalDecorators {' '.join(flags)}: same output, in the same order, as esbuild's")

print("== the spec language")
SPEC = os.path.join(os.path.dirname(ESB), "spec")
code, out = sh([SPEC], 60)
check(code == 0, "the spec builds all its targets")
got = sh(["node", "-e", "require('./out/spec/plugged.js');console.log(globalThis.bundled.summary)"], 15)[1].strip()
check(got == '1.2.3 greetings, "friend"', f"plugins, a spec-defined format, a loader: {got}")
check(open("out/spec/plugged.js").read().startswith("/* built by the spec */\n"), "a spec's banner")
got = sh(["node", "out/spec/ui.cjs"], 15)[1].strip()
check(got == '["a",{"x":"1"},["b"]]', f"a spec's JSX settings: {got}")
old = sh(["node", "tools/check-target.mjs", "out/spec/old.js", "2017"], 30)[1].strip()
ran = sh(["node", "out/spec/old.js"], 30)[1].strip()
check(old == "ok" and ran == "4 4", f"a spec's syntax target: {old}, {ran}")

print("== source maps")
for a in ["named.js", "cjs.js", "features.js", "jsx/main.jsx"]:
    out = f"{SCRATCH}/{a.replace('/', '_')}.sm.js"
    sh([ESB, f"app/{a}", "--sourcemap", f"--outfile={out}"])
    code, text = sh(["node", "tools/checkmap.mjs", out])
    m = re.search(r"(\d+) sources, (\d+) mappings, (\d+) check out", text)
    check(m and m.group(2) == m.group(3), f"{a}: {m.group(0) if m else text[:80]}")

print()
print("FAILED:" if failures else "All checks passed.")
for f in failures: print("  " + f)
sys.exit(1 if failures else 0)
