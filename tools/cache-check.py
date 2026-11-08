#!/usr/bin/env python3
# The cache on disk across runs. Copies the tests (apps and node_modules) to out/cache-check, and for
# each app builds with the cache in runs one after another, changing files while nothing runs:
#   a first run with no cache, and one after it, which computes nothing;
#   an edit to a module the bundle uses, the entry, a new file the entry imports, and that file
#   gone again, each seen by the next run, which computes only what it reaches;
#   top-level names in one module that another module's nested names must step around;
#   a cache damaged on disk, and one another build of the program wrote: each set aside.
# Every run's output must be byte for byte what a fresh process builds with no cache. A run is a
# watcher stopped after its first build (which says how many memo answers it computed), or one build
# with --cache, the two sharing one cache.
#   usage: cache-check.py ESB [APP...]     (APP: datefns, rx, zod, … as in tests/apps)
import json, os, re, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

args = sys.argv[1:]
ESB, = guard.in_tests(args[:1])
APPS = args[1:] or ["datefns", "rx", "zod"]
TESTS = os.getcwd()
WORK = os.path.abspath(os.path.join(TESTS, "..", "out", "cache-check"))
STAGE = WORK + "-stage"
BUILD = re.compile(r"\[watch\] build 1: ([\d.]+) ms, (\d+) memo answers computed")
failures = 0

def write(rel, text, root):
    """A whole file, moved into place."""
    os.makedirs(STAGE, exist_ok=True)
    staged = os.path.join(STAGE, "next")
    with open(staged, "w") as f:
        f.write(text)
    os.replace(staged, os.path.join(root, rel))

def read(rel, root):
    return open(os.path.join(root, rel)).read()

def fresh(entry, root):
    p = subprocess.run([ESB, entry, "--no-cache", "--outfile=out/fresh.js"], cwd=root, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        sys.exit("fresh build failed: " + p.stderr[-2000:])
    return read("out/fresh.js", root)

def watched_run(entry, root, esb=ESB):
    """A watcher's first build: what it said, and how many memo answers it computed."""
    p = subprocess.Popen([esb, entry, "--watch", "--outfile=out/out.js"], cwd=root, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    said, computed = [], None
    deadline = time.time() + 60
    for line in p.stdout:
        said.append(line.rstrip())
        m = BUILD.search(line)
        if m:
            computed = int(m.group(2))
            break
        if time.time() > deadline:
            break
    os.killpg(p.pid, 9)
    p.wait()
    if computed is None:
        sys.exit("the watcher never finished its first build:\n" + "\n".join(said))
    return said, computed

def once_run(entry, root):
    p = subprocess.run([ESB, entry, "--cache", "--outfile=out/out.js"], cwd=root, capture_output=True, text=True, timeout=120)
    if p.returncode != 0:
        sys.exit("a build with --cache failed: " + (p.stdout + p.stderr)[-2000:])
    return p.stdout.splitlines()

def check(name, root, entry, run, most=None, says=None):
    """A run, against a fresh build: the same bytes; at most `most` answers computed; a line saying `says`."""
    global failures
    if run == "once":
        said, computed = once_run(entry, root), None
    else:
        said, computed = watched_run(entry, root, run if run != "watch" else ESB)
    same = read("out/out.js", root) == fresh(entry, root)
    ok = same and (most is None or computed <= most) and (says is None or any(says in l for l in said))
    failures += not ok
    print(f"  {name:42} " + (f"{computed:5} memo answers  " if computed is not None else " " * 20)
          + ("identical" if same else "DIFFERENT")
          + ("" if most is None or computed <= most else f"  (more than {most})")
          + ("" if says is None or any(says in l for l in said) else f"  (never said {says!r})")
          + ("" if ok else "  FAIL"))

def cache_files(root):
    d = os.path.join(root, "node_modules", ".cache", "esb")
    return [os.path.join(d, f) for f in os.listdir(d) if f.endswith(".cache")] if os.path.isdir(d) else []

def used_module(entry, root):
    out = os.path.join(root, "out", "map.js")
    subprocess.run([ESB, entry, "--no-cache", "--sourcemap", "--outfile=" + out], cwd=root, capture_output=True, timeout=120)
    sources = [s for s in json.load(open(out + ".map"))["sources"] if "node_modules/" in s]
    return os.path.relpath(os.path.normpath(os.path.join(root, "out", sources[len(sources) // 2])), root)

for app in APPS:
    if os.path.exists(WORK):
        shutil.rmtree(WORK)
    os.makedirs(os.path.join(WORK, "out"))
    shutil.copytree(os.path.join(TESTS, "apps"), os.path.join(WORK, "apps"), symlinks=True)
    shutil.copytree(os.path.join(TESTS, "node_modules"), os.path.join(WORK, "node_modules"), symlinks=True)
    entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(WORK, "apps"))) if f.split(".")[0] == app)
    module = used_module(entry, WORK)
    original = read(entry, WORK)
    print(f"== {app}: {entry}, editing {module}")
    check("first run, no cache", WORK, entry, "watch")
    check("again: nothing computed", WORK, entry, "watch", most=0)
    check("one build with --cache, from the same cache", WORK, entry, "once")
    write(module, 'console.log("cache probe");\n' + read(module, WORK), WORK)
    check("a module it uses edited", WORK, entry, "watch", most=60)
    check("again: nothing computed", WORK, entry, "watch", most=0)
    write(entry, original + 'console.log("entry edit");\n', WORK)
    check("the entry edited", WORK, entry, "watch", most=60)
    write("apps/extra.js", "export const extra = 42;\n", WORK)
    write(entry, 'import { extra } from "./extra.js";\n' + original + "console.log(extra);\n", WORK)
    check("a new file it imports", WORK, entry, "watch", most=150)
    write(entry, original, WORK)
    os.remove(os.path.join(WORK, "apps/extra.js"))
    check("the new file gone, the entry back", WORK, entry, "watch", most=150)
    files = cache_files(WORK)
    if len(files) != 1:
        failures += 1
        print(f"  one cache for one command line: found {len(files)}  FAIL")
    else:
        data = bytearray(open(files[0], "rb").read())
        data[len(data) // 2] ^= 0xFF
        open(files[0], "wb").write(bytes(data))
        check("the cache damaged on disk", WORK, entry, "watch", says="is damaged")
        check("again: nothing computed", WORK, entry, "watch", most=0)
        other = os.path.join(WORK, "out", "esb-other")
        shutil.copy2(ESB, other)
        check("a cache another build wrote", WORK, entry, other, says="another build")
        check("this build again, from what it set aside", WORK, entry, "watch", says="another build")
        check("again: nothing computed", WORK, entry, "watch", most=0)

# Names across modules, across runs: top-level names that come and go in one module, which nested
# names in another step around.
print("== names across modules")
CLASH = os.path.join(WORK, "clash")
if os.path.exists(WORK):
    shutil.rmtree(WORK)
os.makedirs(os.path.join(CLASH, "src"))
os.makedirs(os.path.join(CLASH, "out"))
write("src/main.js", 'import { f } from "./a.js";\nconsole.log(f());\n', CLASH)
write("src/a.js", "export function f() { let y = 1; let y2 = 5; return y + y2; }\n", CLASH)
check("first run", CLASH, "src/main.js", "watch")
for name, rel, text in [
        ("a top-level name a nested one had", "src/main.js", 'import { f } from "./a.js";\nvar y = 2;\nconsole.log(f(), y);\n'),
        ("another, the nested one's next", "src/main.js", 'import { f } from "./a.js";\nvar y = 2; var y2 = 3;\nconsole.log(f(), y, y2);\n'),
        ("a nested name more", "src/a.js", "export function f() { let y = 1; let y2 = 5; let y3 = 7; return y + y2 + y3; }\n"),
        ("the top-level names gone", "src/main.js", 'import { f } from "./a.js";\nconsole.log(f());\n')]:
    write(rel, text, CLASH)
    check(name, CLASH, "src/main.js", "watch")
print("all identical" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
