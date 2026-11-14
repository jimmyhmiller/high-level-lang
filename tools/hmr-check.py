#!/usr/bin/env python3
# Hot module replacement, end to end. Copies tests/apps/hmr to out/hmr-check, runs ESB --hmr
# --serve=0 there, and runs the bundle in Node (oracles/hmr-client.cjs), connected to the server's
# event stream. Then edits, checking what the running app does after each:
#   a module that accepts its own updates: replaced in place, its dispose data passed on, and the
#     entry's state kept;
#   a module only it imports, whose edit only gives a function a new value: patched, nothing runs
#     again;
#   the entry, and a CommonJS module only the entry imports: nothing accepts them, so a reload;
#   a write that changes nothing: no rebuild.
# Then statement-level patches, on tests/apps/hmrpatch: state kept across a function's new value, a
# value's, a function added and one taken out; what other modules call seen at once; a class's
# methods put on the instance there is; and a module run again, with the reason the client is told,
# when a statement that ran captured what changed (in its own module or another), ran code that
# reads it, or changed itself; a class whose constructor changed reloads the page.
# After each rebuild the bundle written must be what a fresh process builds from the same files.
#   usage: hmr-check.py ESB
import os, queue, re, shutil, subprocess, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

ESB, = guard.in_tests(sys.argv[1:2])
TESTS = os.getcwd()
WORK = os.path.abspath(os.path.join(TESTS, "..", "out", "hmr-check"))
CLIENT = os.path.join(TESTS, "oracles", "hmr-client.cjs")
if os.path.exists(WORK):
    shutil.rmtree(WORK)
shutil.copytree(os.path.join(TESTS, "apps", "hmr"), os.path.join(WORK, "apps", "hmr"))
shutil.copytree(os.path.join(TESTS, "apps", "hmrpatch"), os.path.join(WORK, "apps", "hmrpatch"))
# The output's directory is there already: making it would change a listing the first build read,
# which rebuilds once, sending nothing.
os.makedirs(os.path.join(WORK, "out"))

def lines_of(proc):
    q = queue.Queue()
    threading.Thread(target=lambda: [q.put(l.rstrip("\n")) for l in proc.stdout], daemon=True).start()
    return q

def wait_for(q, pattern, seconds, seen=None):
    end = time.time() + seconds
    while time.time() < end:
        try:
            line = q.get(timeout=max(0.01, end - time.time()))
        except queue.Empty:
            break
        if seen is not None:
            seen.append(line)
        m = re.search(pattern, line)
        if m:
            return m
    return None

def edit(rel, old, new):
    path = os.path.join(WORK, rel)
    text = open(path).read()
    assert old in text, f"{rel} has no {old!r}"
    open(path, "w").write(text.replace(old, new))

def fresh_matches(entry="apps/hmr/main.js", out="out/out.js"):
    """The bundle the watcher wrote, against a fresh process's first development build."""
    p = subprocess.Popen([ESB, entry, "--hmr", "--no-cache", "--outfile=out/fresh.js"], cwd=WORK,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    ok = wait_for(lines_of(p), r"\[watch\] build 1:", 30)
    os.killpg(p.pid, 9)
    p.wait()
    # The served bundle connects to its server's port, which the fresh one has none of.
    served = [l for l in open(os.path.join(WORK, out)).read().split("\n") if not l.startswith("__hmr.connect(")]
    return ok and served == open(os.path.join(WORK, "out/fresh.js")).read().split("\n")

esb = subprocess.Popen([ESB, "apps/hmr/main.js", "--hmr", "--serve=0", "--outfile=out/out.js"], cwd=WORK,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
built = lines_of(esb)
log = []
if not wait_for(built, r"\[watch\] build 1:", 30, log):
    sys.exit("no first build:\n" + "\n".join(log))
client = subprocess.Popen(["node", CLIENT, "out/out.js"], cwd=WORK, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True)
said = lines_of(client)
failures = 0

def check(ok, label):
    global failures
    failures += not ok
    print(("  ok   " if ok else "  FAIL ") + label)

def ask(expr, heard=None):
    client.stdin.write(expr + "\n")
    client.stdin.flush()
    m = wait_for(said, r"^(=>|!!) (.*)", 5, heard)
    return m.group(2) if m else None

def step(name, act, client_says, answer, asks=None, unsaid=(), entry="apps/hmr/main.js", out="out/out.js"):
    """Make an edit, wait for the rebuild and what is sent, then what the client says and answers:
    `click()` against `answer`, or each expression of `asks` against its answer. The client must
    not say what `unsaid` matches (a module that should have kept running, running again)."""
    seen, heard = [], []
    act()
    m = wait_for(built, r"\[hmr\] (update|reload|no module changed)", 10, seen)
    timing = next((l for l in seen if "[watch] build" in l), "")
    if not m:
        check(False, f"{name}: no rebuild\n" + "\n".join(seen))
        return
    for pattern in client_says:
        if not wait_for(said, pattern, 5, heard):
            check(False, f"{name}: the client never said /{pattern}/; it said {heard}")
            return
    asks = asks if asks is not None else ([("click()", answer)] if answer else [])
    got = [(expr, ask(expr, heard), want) for expr, want in asks]
    wrong = [f"{expr} => {g} (wanted {want})" for expr, g, want in got if g != want]
    ran = [l for l in heard for p in unsaid if re.search(p, l)]
    ms = re.search(r"build \d+: ([\d.]+) ms", timing)
    fresh = fresh_matches(entry, out)
    check(not wrong and not ran and fresh,
          f"{name}: {m.group(0)} in {ms.group(1) if ms else '?'} ms"
          + "".join(f", then {expr} => {g}" for expr, g, _ in got if g is not None and not wrong)
          + "".join(", " + w for w in wrong)
          + "".join(f", but the client said {l!r}" for l in ran)
          + ("" if fresh else ", but the bundle differs from a fresh build"))

check(wait_for(said, r"main ran view v1 12 config", 5) is not None, "the bundle runs, connected to the server")
check(ask("click()") == "hello clicked 1", "it has state: click() => hello clicked 1")
step("edit the accepting module", lambda: edit("apps/hmr/view.js", '"view v1"', '"view v2"'),
     [r"view replaced, was view v1", r"\[hmr\] updated apps/hmr/view.js"], "hello clicked 2")
step("edit a function of a module it imports", lambda: edit("apps/hmr/text.js", '"hello"', '"hi"'),
     [r"\[hmr\] apps/hmr/text.js: patched greet"], "hi clicked 3", unsaid=[r"view replaced"])
step("edit the entry", lambda: edit("apps/hmr/main.js", '"main ran"', '"main ran again"'),
     [r"RELOAD apps/hmr/main.js changed"], None)
step("edit CommonJS only the entry imports", lambda: edit("apps/hmr/config.cjs", '"config"', '"config2"'),
     [r"RELOAD apps/hmr/main.js changed"], None)
seen = []
same = open(os.path.join(WORK, "apps/hmr/view.js")).read()
open(os.path.join(WORK, "apps/hmr/view.js"), "w").write(same)
check(wait_for(built, r"\[watch\] build", 1.5, seen) is None, "a write that changes nothing: no rebuild")
for p in (esb, client):
    try:
        os.killpg(p.pid, 9)
    except ProcessLookupError:
        pass
    p.wait()

print("== statement-level patches")
P = "apps/hmrpatch"
OUT = "out/patch.js"
esb = subprocess.Popen([ESB, f"{P}/main.js", "--hmr", "--serve=0", f"--outfile={OUT}"], cwd=WORK,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
built = lines_of(esb)
log = []
if not wait_for(built, r"\[watch\] build 1:", 30, log):
    sys.exit("no first build:\n" + "\n".join(log))
client = subprocess.Popen(["node", CLIENT, OUT], cwd=WORK, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True)
said = lines_of(client)
check(wait_for(said, r"main ran", 5) is not None, "the bundle runs, connected to the server")
state = [("tick()", "1"), ("tick()", "2"), ("show()", "count is 2"), ("counter.inc()", "1"), ("twice.inc()", "2"),
         ("dispatch()", "1"), ("dispatch()", "2"), ('handle("a")', "a1"), ("anon()", "anon 1"), ("vault.get()", "1")]
got = [(e, ask(e), w) for e, w in state]
check(all(g == w for _, g, w in got), "it has state: " + ", ".join(f"{e} => {g}" for e, g, _ in got))
again = [r"main ran", r"RELOAD"]
def patch(name, rel, old, new, says, asks, unsaid=again):
    step(name, lambda: edit(f"{P}/{rel}", old, new), says, None, asks=asks, unsaid=unsaid, entry=f"{P}/main.js", out=OUT)
patch("a function's new value keeps its module's state", "counter.js", "n += 1;", "n += 10;",
      [r"\[hmr\] apps/hmrpatch/counter.js: patched bump$"], [("tick()", "12"), ("show()", "count is 12")])
patch("what another module calls is the new function", "words.js", '"count is "', '"total "',
      [r"\[hmr\] apps/hmrpatch/words.js: patched greeting$"], [("show()", "total 12")])
patch("a function added, and called by the one that changed", "words.js",
      'export const greeting = (n) => "total " + n;',
      'function shout(s) {\n  return s.toUpperCase();\n}\nexport const greeting = (n) => shout("total " + n);',
      [r"\[hmr\] apps/hmrpatch/words.js: patched shout, greeting$"], [("show()", "TOTAL 12")])
patch("a function a patch added, changed again", "words.js", "s.toUpperCase()", "s.toUpperCase() + \"!\"",
      [r"\[hmr\] apps/hmrpatch/words.js: patched shout$"], [("show()", "TOTAL 12!")])
patch("a function taken out", "words.js",
      'function shout(s) {\n  return s.toUpperCase() + "!";\n}\nexport const greeting = (n) => shout("total " + n);',
      'export const greeting = (n) => "sum " + n;',
      [r"\[hmr\] apps/hmrpatch/words.js: patched greeting$"], [("show()", "sum 12")])
patch("a default export with no name", "words.js", '"anon 1"', '"anon 2"',
      [r"\[hmr\] apps/hmrpatch/words.js: patched words_default$"], [("anon()", "anon 2")])
patch("a value only functions read", "counter.js", "let n = 0;", "let n = 100;",
      [r"\[hmr\] apps/hmrpatch/counter.js: patched n$"], [("tick()", "110")])
patch("a class's method, on the instance there is", "shapes.js", "this.n += 1;", "this.n += 5;",
      [r"\[hmr\] apps/hmrpatch/shapes.js: patched Counter.prototype.inc$"], [("counter.inc()", "6"), ("twice.inc()", "12")])
patch("a subclass's method, whose `super` finds what it found", "shapes.js", "super.inc() * 2", "super.inc() * 3",
      [r"\[hmr\] apps/hmrpatch/shapes.js: patched Twice.prototype.inc$"], [("twice.inc()", "33")])
patch("a class's getter", "shapes.js", '"counter at "', '"counter is "',
      [r"\[hmr\] apps/hmrpatch/shapes.js: patched Counter.prototype.label$"], [("counter.label", "counter is 6")])
patch("a function a statement captured runs it again", "store.js", "return state + 1;", "return state + 5;",
      [r"\[hmr\] apps/hmrpatch/store.js runs again: statement 3 \(`export const store = createStore\(reducer\);`\) "
       r"captured `reducer` when it ran, and the edit changed it", r"registry ran"],
      [("dispatch()", "5"), ("tick()", "120")])
patch("a value read by what a statement ran runs it again", "store.js", "const base = 10;", "const base = 20;",
      [r"\[hmr\] apps/hmrpatch/store.js runs again: statement 6 \(`export const initial = start\(\);`\) "
       r"ran `start` when it ran, and the edit changed `base`", r"registry ran"], [("dispatch()", "5")])
patch("a function another module captured runs that module again", "actions.js", '"a1"', '"a2"',
      [r"\[hmr\] apps/hmrpatch/actions.js: patched onA$",
       r"\[hmr\] apps/hmrpatch/captured.js runs again: statement 2 \(`export const handlers = \{ a: onA \};`\) "
       r"captured `onA` of apps/hmrpatch/actions.js when it ran, and the edit changed it", r"registry ran"],
      [('handle("a")', "a2"), ("tick()", "130")])
patch("a class with private names runs again", "secret.js", "return this.#v;", "return this.#v + 1;",
      [r"\[hmr\] apps/hmrpatch/secret.js runs again: statement 1 \(`export class Vault \{`\): `Vault` has private names, "
       r"which methods put on it again could not reach", r"registry ran"], [("newVault().get()", "2"), ("vault.get()", "1")])
patch("an effect that changed runs again", "effects.js", '"effects v1"', '"effects v2"',
      [r"\[hmr\] apps/hmrpatch/effects.js runs again: statement 1 \(`console.log\(\"effects v2\"\);`\) "
       r"runs as the module loads, and the edit changed it", r"effects v2", r"registry ran"], [("tick()", "140")])
patch("a class whose constructor changed reloads the page", "shapes.js", "this.n = 0;", "this.n = 1;",
      [r"RELOAD apps/hmrpatch/main.js changed, and does not accept updates: .*apps/hmrpatch/shapes.js runs again: "
       r"statement 1 \(`export class Counter \{`\): the constructor, fields, heritage or static members of `Counter` changed"],
      [], unsaid=[r"main ran"])
for p in (esb, client):
    try:
        os.killpg(p.pid, 9)
    except ProcessLookupError:
        pass
    p.wait()

# The development format runs as the bundle does: every app, built both ways, says the same in Node.
print("== the development format runs as the bundle does")
APPS = {"named": [], "all": [], "cjs": [], "features": [], "three": [], "zod": [], "rx": [], "datefns": [], "preact": [],
        "immer": [], "react": [], "d3": [], "lib": [], "excjs": [], "nodey": ["--platform=node"], "hmrdual": []}
OUT = os.path.join(WORK, "apps-out")
os.makedirs(OUT)
def run_node(path):
    try:
        p = subprocess.run(["node", path], cwd=OUT, capture_output=True, text=True, timeout=20)
        return p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        return (e.stdout or b"").decode() + "<still running after 20 s>"
for app, flags in APPS.items():
    entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(TESTS, "apps"))) if f.split(".")[0] == app)
    subprocess.run([ESB, entry, f"--outfile={OUT}/{app}.cjs"] + flags, capture_output=True, timeout=120)
    p = subprocess.Popen([ESB, entry, "--hmr", "--no-cache", f"--outfile={OUT}/{app}.dev.cjs"] + flags, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    m = wait_for(lines_of(p), r"\[watch\] build 1: ([\d.]+) ms", 60)
    os.killpg(p.pid, 9)
    p.wait()
    bundled, dev = run_node(f"{app}.cjs"), run_node(f"{app}.dev.cjs")
    check(m is not None and bundled == dev,
          f"{app}: {len(dev.splitlines())} lines the same" if bundled == dev else
          f"{app}: bundle says {bundled[:200]!r}, development build says {dev[:200]!r}")
# `--hmr-patch=false`: no module's function hands the runtime an evaluator, and an edit that could
# be patched runs its module again, saying why.
print("== --hmr-patch=false")
shutil.rmtree(os.path.join(WORK, "apps", "hmrpatch"))
shutil.copytree(os.path.join(TESTS, "apps", "hmrpatch"), os.path.join(WORK, "apps", "hmrpatch"))
p = subprocess.Popen([ESB, f"{P}/main.js", "--hmr", "--hmr-patch=false", "--no-cache", "--outfile=out/off.js"], cwd=WORK,
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
said = lines_of(p)
heard = []
first = wait_for(said, r"\[watch\] build 1:", 30, heard)
text = open(os.path.join(WORK, "out", "off.js")).read() if first else ""
check(first is not None and ".scope((" not in text, "no module hands the runtime an evaluator")
edit(f"{P}/counter.js", "n += 1;", "n += 10;")
rerun = wait_for(said, r"counter.js runs again: patching is off", 20, heard)
check(rerun is not None, "an edit a patch could make runs the module again instead: " + (rerun.group(0) if rerun else " / ".join(heard[-5:])))
os.killpg(p.pid, 9)
p.wait()

print("all checks passed" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
