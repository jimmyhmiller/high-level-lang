#!/usr/bin/env python3
# `--watch` against fresh builds. Copies the tests (apps and node_modules) to out/watch-check, starts
# ESB APP --watch there, and makes edits one at a time: to a module the bundle uses, to the entry, a
# new file the entry then imports, a write that changes nothing, a package.json, and putting the
# entry back. After each, the rebuilt output must be byte for byte what a fresh process builds from
# the same files; a write that changes nothing must not rebuild at all. Prints each rebuild's time
# and how many memo answers it computed, beside the fresh build's time.
#   usage: watch-check.py ESB [APP...] [-- FLAG...]     (APP: datefns, rx, zod, … as in tests/apps)
import json, os, queue, re, shutil, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

args = sys.argv[1:]
flags = args[args.index("--") + 1:] if "--" in args else []
args = args[:args.index("--")] if "--" in args else args
ESB, = guard.in_tests(args[:1])
APPS = args[1:] or ["datefns", "rx", "zod"]
TESTS = os.getcwd()
WORK = os.path.abspath(os.path.join(TESTS, "..", "out", "watch-check"))
BUILD = re.compile(r"\[watch\] build (\d+): ([\d.]+) ms, (\d+) memo answers computed, (\d+) inputs watched")

def fresh(entry, out):
    start = time.time()
    p = subprocess.run([ESB, entry, "--outfile=" + out] + flags, cwd=WORK, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        sys.exit("fresh build failed: " + p.stderr[-2000:])
    return (time.time() - start) * 1000

def used_module(entry):
    """A module of a package the bundle includes, from its source map: the one halfway down."""
    out = os.path.join(WORK, "map.js")
    subprocess.run([ESB, entry, "--sourcemap", "--outfile=" + out], cwd=WORK, capture_output=True, timeout=120)
    sources = [s for s in json.load(open(out + ".map"))["sources"] if "node_modules/" in s]
    path = sources[len(sources) // 2]
    return os.path.relpath(os.path.normpath(os.path.join(WORK, path)), WORK)

def package_json(module):
    d = os.path.dirname(module)
    while not os.path.exists(os.path.join(WORK, d, "package.json")):
        d = os.path.dirname(d)
    return os.path.join(d, "package.json")

def write(rel, text):
    with open(os.path.join(WORK, rel), "w") as f:
        f.write(text)

def read(rel):
    return open(os.path.join(WORK, rel)).read()

failures = 0
for app in APPS:
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(WORK)
    shutil.copytree(os.path.join(TESTS, "apps"), os.path.join(WORK, "apps"), symlinks=True)
    shutil.copytree(os.path.join(TESTS, "node_modules"), os.path.join(WORK, "node_modules"), symlinks=True)
    entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(WORK, "apps"))) if f.split(".")[0] == app)
    module = used_module(entry)
    pkg = package_json(module)
    original = read(entry)
    pkg_text = read(pkg)
    doc = json.loads(pkg_text)
    doc["sideEffects"] = not doc.get("sideEffects", True)
    steps = [
        ("edit a module it uses", lambda: write(module, 'console.log("watch probe");\n' + read(module)), True),
        ("edit the entry", lambda: write(entry, original + 'console.log("entry edit");\n'), True),
        ("new file, then import it", lambda: (write("apps/extra.js", "export const extra = 42;\n"),
                                             time.sleep(0.3),
                                             write(entry, 'import { extra } from "./extra.js";\n' + original + "console.log(extra);\n")), True),
        ("write that changes nothing", lambda: write(module, read(module)), False),
        ("flip sideEffects in package.json", lambda: write(pkg, json.dumps(doc, indent=2)), True),
        ("put the entry back", lambda: write(entry, original), True),
    ]
    lines = queue.Queue()
    proc = subprocess.Popen([ESB, entry, "--watch", "--outfile=out.js"] + flags, cwd=WORK, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, start_new_session=True)
    threading.Thread(target=lambda: [lines.put(l) for l in proc.stdout], daemon=True).start()

    def next_build(wait):
        end = time.time() + wait
        while time.time() < end:
            try:
                line = lines.get(timeout=max(0.01, end - time.time()))
            except queue.Empty:
                break
            m = BUILD.search(line)
            if m:
                return float(m.group(2)), int(m.group(3)), int(m.group(4))
            if "panic" in line or "error" in line.lower():
                print("   watcher: " + line.rstrip())
        return None

    print(f"== {app}: {entry}, editing {module}")
    first = next_build(60)
    if not first:
        sys.exit("the watcher never finished its first build")
    cold = fresh(entry, "fresh.js")
    print(f"  {'first build':34} {first[0]:7.1f} ms  {first[1]:5} memo answers  {first[2]} inputs   fresh process {cold:.0f} ms")
    for name, act, rebuilds in steps:
        act()
        got = next_build(1.5 if not rebuilds else 30)
        if not rebuilds:
            ok = got is None
            failures += not ok
            print(f"  {name:34} {'no rebuild' if ok else 'REBUILT'}{'' if ok else '  FAIL'}")
            continue
        if not got:
            failures += 1
            print(f"  {name:34} no rebuild  FAIL")
            break
        took = fresh(entry, "fresh.js")
        same = read("out.js") == read("fresh.js")
        failures += not same
        print(f"  {name:34} {got[0]:7.1f} ms  {got[1]:5} memo answers  {got[2]} inputs   fresh process {took:.0f} ms  "
              + ("identical" if same else "DIFFERENT  FAIL"))
    os.killpg(proc.pid, 9)
    proc.wait()
print("all identical" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
