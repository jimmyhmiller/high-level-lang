#!/usr/bin/env python3
"""Checks blame (`esb --blame=BASE,HEAD`) and what-if (`esb --what-if=DIR`) against builds.

Blame and what-if answer by solving linking's rules again on the facts two ledgers hold. These
checks do not take their word for it: they build the trees the answers are about and look.

- Identity: a build blamed against itself changes nothing.
- Accounting: each route's groups and the outputs' own bytes add up to what the route changed by.
- Counterfactuals, built: for every edit blame says gained or lost something alone (or as any one
  of several), the earlier tree with only that file taken from the later one is built, and each
  module blame names must have gained (or lost) bytes in that route.
- What-if, built: the package edit it proposes (`"sideEffects": false`) and the statement it
  proposes be free of side effects (`/* @__PURE__ */`) are made to a copy of the tree and built,
  and the modules it says would go are gone.
- Expectations: the cause each fixture was written to show (tests/apps/blame).
- Plans: blame and what-if say the same under `--pipeline=full` as on one thread.
- Watching: `--watch --ledger` prints the blame of each rebuild.

usage: blame-check.py [ESB]
"""
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
FIXTURES = os.path.join(ROOT, "tests/apps/blame")
OUT = os.path.join(ROOT, "out/blame-check")

CASES = {
    "namespace": {"entries": ["main.js"], "flags": ["--minify"], "runs": True},
    "joint": {"entries": ["main.js"], "flags": ["--minify"], "runs": True},
    "zod": {"entries": ["main.js"], "flags": ["--minify"], "runs": True},
    "split": {"entries": ["home.js", "admin.js"], "flags": ["--splitting", "--format=esm", "--minify"], "runs": False},
}

failures = []
skipped = []
passed = 0


def check(ok, what):
    global passed
    if ok:
        passed += 1
    else:
        failures.append(what)
        print("FAIL", what)


def run(args, cwd=None, ok_codes=(0,)):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if p.returncode not in ok_codes:
        raise RuntimeError("%s failed (%d):\n%s%s" % (" ".join(args), p.returncode, p.stdout[-2000:], p.stderr[-2000:]))
    return p


def tree(case, side):
    return os.path.join(FIXTURES, case, side)


def build(case, src, name):
    """Builds the tree at `src` with a ledger; answers the analysis directory and the ledger."""
    c = CASES[case]
    out = os.path.join(OUT, case, name)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    where = ["--outdir=" + out + "/dist"] if "--splitting" in c["flags"] else ["--outfile=" + out + "/dist/main.js"]
    run([ESB] + c["entries"] + c["flags"] + where + ["--analyze=" + out + "/an", "--ledger"], cwd=src)
    if c["runs"]:
        node = os.path.join(ROOT, "tests/node_modules/.bin/node")
        run(["node", out + "/dist/main.js"], cwd=src)
    with open(out + "/an/ledger.json") as f:
        return out + "/an", json.load(f)


def module_bytes(ledger, root):
    """Each module's bytes in a route of a ledger."""
    out = {}
    for r in ledger["routes"]:
        if r["root"] == root:
            for p, b in zip(r["parts"], r["bytes-of"]):
                key = ledger["parts"][p]["key"]
                m = key[: key.index("#")]
                out[m] = out.get(m, 0) + b
    return out


def blame(a, b, extra=()):
    return json.loads(run([ESB, "--blame-json=%s,%s" % (a, b)] + list(extra)).stdout)


def blame_text(a, b, extra=()):
    return run([ESB, "--blame=%s,%s" % (a, b)] + list(extra)).stdout


def what_if(a, extra=()):
    return json.loads(run([ESB, "--what-if-json=" + a] + list(extra)).stdout)


def copy_with(case, files, name):
    """The earlier tree, with `files` taken from the later one: beside the two, so that it finds
    the packages they find, by the same paths."""
    dest = os.path.join(FIXTURES, case, ".check-" + name)
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(tree(case, "base"), dest, symlinks=True)
    for f in files:
        shutil.copy(os.path.join(tree(case, "head"), f), os.path.join(dest, f))
    return dest


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    built = {}
    for case in CASES:
        built[case] = {side: build(case, tree(case, side), side) for side in ("base", "head")}

    for case, sides in built.items():
        (base_dir, base), (head_dir, head) = sides["base"], sides["head"]
        # Identity.
        for side, (d, _) in sides.items():
            same = blame(d, d)
            check(all(r["before"] == r["after"] and not r["groups"] for r in same["routes"]) and not same["edits"],
                  "%s: the %s build blamed against itself changes nothing" % (case, side))
        found = blame(base_dir, head_dir)
        back = blame(head_dir, base_dir)
        # Accounting, both ways.
        for b in (found, back):
            for r in b["routes"]:
                total = sum(g["bytes"] for g in r["groups"]) + r["own"]
                check(total == r["after"] - r["before"],
                      "%s: route %s's groups and own bytes add up to its change (%d, %d)" % (case, r["root"], total, r["after"] - r["before"]))
        # Each cause found one way is found the other, with the bytes it moved the other way. What
        # edits make only together, each of them alone undoes; what any of them makes, only all
        # of them together undo.
        dual = {"together": "any", "any": "together"}
        def causes(b, flip):
            return sorted((r["root"], dual.get(g["kind"], g["kind"]) if flip else g["kind"], tuple(sorted(g["edits"])), -g["bytes"] if flip else g["bytes"])
                          for r in b["routes"] for g in r["groups"])
        check(causes(found, False) == causes(back, True),
              "%s: blamed backwards, each cause moves the same bytes the other way" % case)
        # The same on many threads.
        check(blame_text(base_dir, head_dir) == blame_text(base_dir, head_dir, ["--pipeline=full"]),
              "%s: blame says the same under --pipeline=full" % case)
        check(run([ESB, "--what-if=" + head_dir]).stdout == run([ESB, "--what-if=" + head_dir, "--pipeline=full"]).stdout,
              "%s: what-if says the same under --pipeline=full" % case)

        # Counterfactuals, built: an edit that alone gains or loses a module's bytes does so when
        # it is the only file taken from the later tree.
        for r in found["routes"]:
            for g in r["groups"]:
                if g["kind"] not in ("alone", "any"):
                    continue
                for e in g["edits"]:
                    if e.startswith("<") or not os.path.exists(os.path.join(tree(case, "head"), e)):
                        continue
                    src = copy_with(case, [e], "only-" + e.replace("/", "_"))
                    try:
                        _, only = build(case, src, "only-" + e.replace("/", "_"))
                    except RuntimeError as err:
                        # Linking's rules say what an edit alone reaches; the bundler may refuse
                        # that tree (an import of a name not yet exported). Said, not hidden.
                        skipped.append("%s: the earlier tree with only %s from the later does not build (%s)"
                                       % (case, e, str(err).strip().splitlines()[-1][:160]))
                        continue
                    finally:
                        shutil.rmtree(src, ignore_errors=True)
                    before = module_bytes(base, r["root"])
                    after = module_bytes(only, r["root"])
                    for m in g["modules"]:
                        if m["bytes"] > 0 and not m["module"].startswith("<"):
                            check(after.get(m["module"], 0) > before.get(m["module"], 0),
                                  "%s: with only %s edited, route %s gains bytes of %s, as blame says (%d -> %d)"
                                  % (case, e, r["root"], m["module"], before.get(m["module"], 0), after.get(m["module"], 0)))
                        elif m["bytes"] < 0 and not m["module"].startswith("<"):
                            check(after.get(m["module"], 0) < before.get(m["module"], 0),
                                  "%s: with only %s edited, route %s loses bytes of %s, as blame says (%d -> %d)"
                                  % (case, e, r["root"], m["module"], before.get(m["module"], 0), after.get(m["module"], 0)))

    def groups(case):
        return [(r["root"], g) for r in blame(built[case]["base"][0], built[case]["head"][0])["routes"] for g in r["groups"]]

    def has(case, root, kind, edits, module=None, positive=True):
        return any(rt == root and g["kind"] == kind and sorted(g["edits"]) == sorted(edits)
                   and (g["bytes"] > 0) == positive
                   and (module is None or any(m["module"].endswith(module) for m in g["modules"]))
                   for rt, g in groups(case))

    # Expectations.
    check(has("namespace", "main.js", "alone", ["main.js"], "lib/locales/he.js"),
          "namespace: reading the namespace as a value is main.js's edit, and brings he.js")
    check(has("namespace", "main.js", "edited", ["greet.js"]), "namespace: greet() made longer is greet.js edited in place")
    check(has("joint", "main.js", "any", ["one.js", "two.js"], "heavy.js"), "joint: heavy.js comes with either one.js's edit or two.js's")
    check(has("joint", "main.js", "together", ["lib.js", "main.js"], "lib.js"),
          "joint: b comes only with lib.js exporting it and main.js reading it, together")
    check(has("split", "admin.js", "alone", ["admin.js"], "report.js"), "split: admin.js importing report.js statically puts it in admin's route")
    check(has("split", "report.js", "alone", ["admin.js"], "report.js", positive=False),
          "split: report.js's route goes with admin.js's edit, not with the entries")
    check(any(rt == "main.js" and g["kind"] == "alone" and g["edits"] == ["main.js"] and g["bytes"] > 300000
              and any("locales" in h["place"] for h in g["chain"]) for rt, g in groups("zod")),
          "zod: `schemas = z` brings over 300 KB, through the locales' namespace object")

    # What-if, built.
    w = what_if(built["joint"]["head"][0])
    pkg = [s for r in w["routes"] for s in r["savings"] if s["kind"] == "package" and s["about"] == "fxlib"]
    check(len(pkg) == 1 and pkg[0]["bytes"] > 0, "joint: what-if tries fxlib saying it has no side effects")
    pure = [s for r in w["routes"] for s in r["savings"] if s["kind"] == "pure" and s["text"] == "install();"]
    check(len(pure) == 1 and pure[0]["bytes"] > 0, "joint: what-if tries `install();` having no side effects")
    for label, edit in (("sideEffects", "package"), ("pure", "statement")):
        dest = os.path.join(FIXTURES, "joint", ".check-what-if-" + label)
        shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(tree("joint", "head"), dest, symlinks=True)
        if edit == "package":
            p = os.path.join(dest, "node_modules/fxlib/package.json")
            doc = json.load(open(p))
            doc["sideEffects"] = False
            json.dump(doc, open(p, "w"))
            claimed = pkg[0] if pkg else None
        else:
            p = os.path.join(dest, "node_modules/fxlib/index.js")
            text = open(p).read()
            open(p, "w").write(text.replace("\ninstall();", "\n/* @__PURE__ */ install();"))
            claimed = pure[0] if pure else None
        _, edited = build("joint", dest, "what-if-" + label)
        shutil.rmtree(dest, ignore_errors=True)
        now = module_bytes(edited, "main.js")
        for m in (claimed or {"modules": []})["modules"]:
            check(now.get(m["module"], 0) == 0,
                  "joint: with the %s edit made, %s is gone from the route, as what-if says" % (label, m["module"]))
    z = what_if(built["zod"]["head"][0])
    check(any(s["kind"] == "whole" and s["about"].endswith("zod/v4/locales/index.js") and s["bytes"] > 250000
              for r in z["routes"] for s in r["savings"]),
          "zod: what-if finds the locales' namespace object, read whole, holding over 250 KB")

    # Watching.
    dest = os.path.join(OUT, "watch")
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(tree("namespace", "base"), dest)
    log = open(os.path.join(OUT, "watch.log"), "w")
    p = subprocess.Popen([ESB, "main.js", "--minify", "--outfile=out/main.js", "--analyze=out/an", "--ledger", "--watch", "--no-cache"],
                         cwd=dest, stdout=log, stderr=subprocess.STDOUT)
    try:
        time.sleep(1.5)
        shutil.copy(os.path.join(tree("namespace", "head"), "main.js"), os.path.join(dest, "main.js"))
        time.sleep(1.5)
    finally:
        p.terminate()
        p.wait()
        log.close()
    text = open(os.path.join(OUT, "watch.log")).read()
    check("edit to main.js" in text and "locales/he.js" in text, "watch: a rebuild prints which edit brought what")

    for s in skipped:
        print("skipped:", s)
    print("blame-check: %d passed, %d failed, %d counterfactual trees the bundler refuses" % (passed, len(failures), len(skipped)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
