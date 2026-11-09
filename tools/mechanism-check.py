#!/usr/bin/env python3
# The mechanisms of src/app/build.pipeline, each as a strategy keeps by it, checked against fresh
# builds. Works in tests/. For each strategy that tracks, in a copy of the tests (apps and
# node_modules) under out/mechanism-check:
#   a build with the cache, cold and then warm;
#   a watcher's build after the entry is edited, and after a module under node_modules is;
#   a watcher's build after a new file is added beside the entry and imported by it (its directory's
#   listing changes), and after a package's package.json is edited to start it at another file;
#   a run with the cache after all of those edits, made while nothing ran, and after they are undone.
# Every output must be byte for byte what a fresh build with no cache makes of the files as they
# are, but where the strategy trusts a path: an edit there is not seen, and the output is what it
# was before it. With a big app (manyzod), what a bound on answers lets go is made again.
#   usage: mechanism-check.py ESB [APP...] [--strategy=NAME...]       (APP: zod, rx, …, manyzod)
import os, re, shutil, signal, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard

args = sys.argv[1:]
ONLY = [a.split("=", 1)[1] for a in args if a.startswith("--strategy=")]
args = [a for a in args if not a.startswith("--strategy=")]
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
    return [(n, chain(n, "trust")) for n in decls if any(chain(n, "tracks")) and (not ONLY or n in ONLY)]

def write(root, rel, text):
    # Staged beside the tree, not in it: a file there for a moment would change a listing it reads.
    staged = os.path.join(os.path.dirname(root), ".staged")
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
                # An edit of two files may come as two builds: the output once they stop.
                while until_saved(2) is not None: pass
            else:
                got = until_saved(3)
                outs.append(None if got else False)
                if got: continue
            if rebuilds: outs.append(open(os.path.join(root, "out", "out.js")).read())
            else: outs[-1] = open(os.path.join(root, "out", "out.js")).read()
    finally:
        os.killpg(p.pid, signal.SIGKILL); p.wait()
    return outs, "".join(l for l in said if "[lap]" not in l)

def check(ok, what):
    global failures
    failures += not ok
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")

def trusted(paths, rel):
    import fnmatch
    return any(fnmatch.fnmatch(rel, p.replace("**/", "*").replace("/**", "/*")) for p in paths)

def add_package(root, entry):
    """A package of the check's own, which the entry imports first: its package.json names the file
    it starts at, which an edit changes. Its package.json, as a path in the tree."""
    pkg = os.path.join(root, "node_modules", "mechanism-pkg")
    os.makedirs(pkg)
    for f in ("a", "b"):
        with open(os.path.join(pkg, f + ".js"), "w") as out: out.write(f'console.log("mechanism-pkg {f}");\n')
    with open(os.path.join(pkg, "package.json"), "w") as out: out.write('{\n  "name": "mechanism-pkg",\n  "main": "a.js"\n}\n')
    text = open(os.path.join(root, entry)).read()
    with open(os.path.join(root, entry), "w") as out: out.write('import "mechanism-pkg";\n' + text)
    return "node_modules/mechanism-pkg/package.json"

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
        pj = add_package(root, entry)
        extra = os.path.join(os.path.dirname(entry), "mechanism-extra.js")
        start = {rel: open(os.path.join(root, rel)).read() for rel in (entry, module, pj)}
        print(f"== {app}, strategy {strategy}" + (f" (trusting {', '.join(trust)})" if trust else ""))
        want = fresh(root, entry)
        check(cached(root, entry, strategy) == want, "--cache, cold")
        check(cached(root, entry, strategy) == want, "--cache, warm")
        # Each edit, as the files it writes; the files as each edit leaves them, and as the watcher
        # sees them (where a strategy trusts a path, it sees no edit there).
        files, seen, states = dict(start), dict(start), []
        def edit(changes):
            def go():
                for rel, text in changes.items():
                    write(root, rel, text)
            for rel, text in changes.items():
                files[rel] = text
                if not trusted(trust, rel): seen[rel] = text
            states.append(dict(seen))
            return go
        edits = [
            (edit({entry: start[entry] + 'console.log("mechanism edit 1");\n'}), True),
            (edit({module: 'console.log("mechanism edit 2");\n' + start[module]}), not trusted(trust, module)),
            # A file the entry's directory did not list, and an import of it.
            (edit({extra: 'console.log("mechanism extra 3");\n',
                   entry: 'import "./mechanism-extra.js";\n' + start[entry] + 'console.log("mechanism edit 3");\n'}), True),
            # The file a package starts at.
            (edit({pj: start[pj].replace('"a.js"', '"b.js"')}), not trusted(trust, pj)),
        ]
        final = dict(files)
        # Back as they were, for the watcher to start from.
        for rel in (entry, module, pj): write(root, rel, start[rel])
        if os.path.exists(os.path.join(root, extra)): os.remove(os.path.join(root, extra))
        outs, log = watched(root, entry, strategy, edits)
        names = ["the entry edited", "a module edited", "a file added beside the entry and imported", "a package.json edited"]
        made = []
        for i, (state, out) in enumerate(zip(states, outs)):
            for rel, text in state.items(): write(root, rel, text)
            if extra not in state and os.path.exists(os.path.join(root, extra)): os.remove(os.path.join(root, extra))
            rebuilt = edits[i][1]
            made.append(fresh(root, entry))
            ok = out is not None and out == made[-1]
            check(ok, "watching: " + names[i] + ("" if rebuilt else ", trusted: not seen, no build")
                  + ("" if ok else " (built when it should not)" if out is None else " (output differs)"))
            if not ok: print("    the watcher said:\n" + "\n".join("    " + l for l in log.splitlines()[-40:]))
        # Each edit that is seen changes the output, so an answer kept past it would show.
        for i in range(len(made)):
            if edits[i][1]:
                check(made[i] != (made[i - 1] if i else want), f"edit {i + 1} ({names[i]}) changes the output")
        # A run with the cache after the edits, made while nothing ran, then with them undone.
        # What the run is to see: what the watcher saw (it trusts what it trusts in this cache too).
        for rel, text in states[-1].items(): write(root, rel, text)
        expect = fresh(root, entry)
        for rel, text in final.items(): write(root, rel, text)
        check(cached(root, entry, strategy) == expect, "--cache after the edits" + (", trusted ones not seen" if final != states[-1] else ""))
        for rel in (entry, module, pj): write(root, rel, start[rel])
        os.remove(os.path.join(root, extra))
        check(cached(root, entry, strategy) == fresh(root, entry), "--cache after the edits undone")

print("all mechanisms check out" if failures == 0 else f"{failures} failed")
sys.exit(1 if failures else 0)
