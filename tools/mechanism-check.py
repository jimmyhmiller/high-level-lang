#!/usr/bin/env python3
# The mechanisms of src/app/build.pipeline, each as a strategy keeps by it, checked against fresh
# builds. Works in tests/. For each strategy that tracks, in a copy of the tests (apps and
# node_modules) under out/mechanism-check:
#   a build with the cache, cold and then warm;
#   a watcher's build after the entry is edited, and after a module under node_modules is;
#   a run with the cache after each of those edits, made while nothing ran.
# Every output must be byte for byte what a fresh build with no cache makes of the files as they
# are, but where the strategy trusts a path: an edit there is not seen, and the output is what it
# was before it. With a big app (manyzod), what a bound on answers lets go is made again.
#   usage: mechanism-check.py ESB [APP...]       (APP: zod, rx, …, manyzod)
import os, re, shutil, signal, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

args = sys.argv[1:]
ESB, = guard.in_tests(args[:1])
APPS = args[1:] or ["zod"]
TESTS = os.getcwd()
WORK = os.path.abspath(os.path.join(TESTS, "..", "out", "mechanism-check"))
failures = 0

def strategies():
    """Each strategy that tracks, and the paths it trusts, with those of what it is `from`."""
    text = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "app", "build.pipeline")).read()
    decls = {}
    for m in re.finditer(r"^strategy\s+(\S+)(.*?)^end", text, re.S | re.M):
        body = m.group(2)
        frm = re.search(r"^\s+from\s+(\S+)", body, re.M)
        decls[m.group(1)] = {"from": frm.group(1) if frm else None,
                             "tracks": re.search(r"^\s+tracks\s*$", body, re.M) is not None,
                             "trust": re.findall(r'^\s+trust\s+"([^"]*)"', body, re.M)}
    def chain(name, key):
        out, at = [], name
        while at:
            v = decls[at][key]
            out += v if isinstance(v, list) else [v]
            at = decls[at]["from"]
        return out
    return [(n, chain(n, "trust")) for n in decls if any(chain(n, "tracks"))]

def write(root, rel, text):
    staged = os.path.join(root, ".staged")
    with open(staged, "w") as f: f.write(text)
    os.replace(staged, os.path.join(root, rel))

def fresh(root, entry):
    p = subprocess.run([ESB, entry, "--no-cache", "--outfile=out/fresh.js"], cwd=root, capture_output=True, text=True, timeout=300)
    if p.returncode != 0: sys.exit("fresh build failed: " + p.stderr[-1500:])
    return open(os.path.join(root, "out", "fresh.js")).read()

def cached(root, entry, strategy):
    p = subprocess.run([ESB, entry, "--cache", f"--strategy={strategy}", "--outfile=out/out.js"], cwd=root,
                       capture_output=True, text=True, timeout=300)
    if p.returncode != 0: sys.exit(f"--cache --strategy={strategy} failed: " + (p.stdout + p.stderr)[-1500:])
    return open(os.path.join(root, "out", "out.js")).read()

def watched(root, entry, strategy, edits):
    """A watcher; after its first build each edit in turn, with whether it should build again, and
    the output after each: after its rebuild, or a few seconds on when it should not rebuild (and
    did not)."""
    import queue, threading
    p = subprocess.Popen([ESB, entry, "--watch", "--timing", f"--strategy={strategy}", "--outfile=out/out.js"], cwd=root,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
    lines, said = queue.Queue(), []
    threading.Thread(target=lambda: [lines.put(l) for l in p.stdout], daemon=True).start()
    def until_saved(seconds):
        """Lines until the next save, or None when none comes in time; whether a build came."""
        built, end = False, time.time() + seconds
        while time.time() < end:
            try: line = lines.get(timeout=max(0.01, end - time.time()))
            except queue.Empty: return None
            said.append(line)
            if re.search(r"\[watch\] build \d+:", line): built = True
            if "[cache] saved in" in line or "[cache] nothing new to save" in line: return built
        return None
    outs = []
    try:
        if until_saved(300) is None: sys.exit("the watcher never made its first build:\n" + "".join(said)[-2000:])
        for edit, rebuilds in edits:
            edit()
            if rebuilds:
                if not until_saved(300): sys.exit("the watcher never built again:\n" + "".join(said)[-2000:])
            else:
                got = until_saved(3)
                outs.append(None if got else False)
                if got: continue
            if rebuilds: outs.append(open(os.path.join(root, "out", "out.js")).read())
            else: outs[-1] = open(os.path.join(root, "out", "out.js")).read()
    finally:
        os.killpg(p.pid, signal.SIGKILL); p.wait()
    return outs

def check(ok, what):
    global failures
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")

def trusted(paths, rel):
    import fnmatch
    return any(fnmatch.fnmatch(rel, p.replace("**/", "*").replace("/**", "/*")) for p in paths)

def prepare(app):
    root = os.path.join(WORK, app)
    if os.path.exists(root): shutil.rmtree(root)
    os.makedirs(os.path.join(root, "out"))
    if app == "manyzod":
        os.makedirs(os.path.join(root, "node_modules"))
        for i in range(1, 13):
            shutil.copytree(os.path.join(TESTS, "node_modules", "zod"), os.path.join(root, "node_modules", f"zod{i}"), symlinks=True)
        os.makedirs(os.path.join(root, "apps"))
        with open(os.path.join(root, "apps", "manyzod.js"), "w") as f:
            for i in range(1, 13):
                f.write(f'import {{ z as z{i} }} from "zod{i}"; console.log(z{i}.string().parse("a{i}"));\n')
        return root, "apps/manyzod.js", "node_modules/zod7/v4/core/util.js"
    shutil.copytree(os.path.join(TESTS, "apps"), os.path.join(root, "apps"), symlinks=True)
    shutil.copytree(os.path.join(TESTS, "node_modules"), os.path.join(root, "node_modules"), symlinks=True)
    entry = next(os.path.join("apps", f) for f in sorted(os.listdir(os.path.join(root, "apps"))) if f.split(".")[0] == app)
    mods = {"zod": "node_modules/zod/v4/locales/mk.js", "rx": "node_modules/rxjs/dist/esm5/internal/util/isAsyncIterable.js",
            "datefns": "node_modules/date-fns/locale/en-US/_lib/formatLong.js"}
    return root, entry, mods.get(app, "node_modules/zod/v4/locales/mk.js")

for app in APPS:
    for strategy, trust in strategies():
        root, entry, module = prepare(app)
        entry0, module0 = open(os.path.join(root, entry)).read(), open(os.path.join(root, module)).read()
        print(f"== {app}, strategy {strategy}" + (f" (trusting {', '.join(trust)})" if trust else ""))
        want = fresh(root, entry)
        check(cached(root, entry, strategy) == want, "--cache, cold")
        check(cached(root, entry, strategy) == want, "--cache, warm")
        n = [0]
        def edit_entry():
            n[0] += 1
            write(root, entry, entry0 + f'console.log("mechanism edit {n[0]}");\n')
        def edit_module():
            n[0] += 1
            write(root, module, f'console.log("mechanism edit {n[0]}");\n' + module0)
        outs = watched(root, entry, strategy, [(edit_entry, True), (edit_module, not trusted(trust, module))])
        # What the files say after the entry's edit, and after the module's.
        write(root, module, module0)
        after_entry = fresh(root, entry)
        write(root, module, f'console.log("mechanism edit {n[0]}");\n' + module0)
        after_module = fresh(root, entry)
        check(outs[0] == after_entry, "watching: the entry edited")
        if trusted(trust, module):
            check(outs[1] is not False and outs[1] == after_entry, "watching: a trusted module edited, not seen, no build")
        else:
            check(outs[1] == after_module, "watching: a module edited")
        write(root, entry, entry0)
        write(root, module, module0)
        check(cached(root, entry, strategy) == fresh(root, entry), "--cache after both edits undone")

print("all mechanisms check out" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
