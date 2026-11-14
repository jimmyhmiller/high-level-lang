#!/usr/bin/env python3
"""Checks lints over what a build ships (`--lint=FILE`, bundle.lint).

- The fixture tests/apps/lint, with examples/ship.lint: exactly the findings it was written to have,
  each explained by what made it (linking's chain from the route for what ships, the place a
  pattern matched, both copies of a duplicated package). An error stops the build before it writes.
- Lints change nothing a build writes.
- A rule that cannot mean anything is an error at its place: an unknown relation, an arity, an
  unbound variable, negation through recursion, a pattern js.syntax cannot read, adding to what the
  build gives, a message naming what nothing binds.
- Watching: an error is said and the watcher goes on; the rules file is watched.
- A build spec's `lint "FILE"`.
- examples/ship.lint over real libraries runs, and finds no error.

usage: lint-check.py [ESB] [SPEC]
"""
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ESB = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(ROOT, "out/bin/esb")
SPEC = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(ROOT, "out/bin/spec")
FIXTURE = os.path.join(ROOT, "tests/apps/lint")
RULES = os.path.join(ROOT, "examples/ship.lint")
OUT = os.path.join(ROOT, "out/lint-check")

failures = []
passed = 0


def check(ok, what):
    global passed
    if ok:
        passed += 1
        print("ok  ", what)
    else:
        failures.append(what)
        print("FAIL", what)


def esb(args, cwd=FIXTURE):
    return subprocess.run([ESB] + args, cwd=cwd, capture_output=True, text=True)


def split(out, *more):
    return ["src/main.js", "--splitting", "--format=esm", "--outdir=" + out] + list(more)


FINDING = re.compile(r"^(?:(\S+): )?(error|warning) \[([a-z-]+)\] (.*)$")


def findings(text):
    return sorted((m.group(3), m.group(2), m.group(1) or "", m.group(4)) for line in text.splitlines() for m in [FINDING.match(line)] if m)


EXPECTED = sorted([
    ("debugger-shipped", "error", "src/admin/panel.js:4", "a debugger statement ships in src/admin/panel.js"),
    ("duplicate-package", "error", "", "tiny-dup ships 2 copies"),
    ("layering", "error", "src/ui/view.js:4", "src/ui/view.js:4 in src/ui needs src/db/query.js:1 in src/db"),
    ("secret-shipped", "error", "src/config.js:1", "process.env.STRIPE_SECRET is in code src/main.js sends to the browser"),
    ("console-shipped", "warning", "src/ui/view.js:4", "console.log ships in src/main.js"),
    ("dead-export", "warning", "src/db/query.js", "src/db/query.js exports pool, and nothing that ships reads it"),
    ("dead-export", "warning", "src/ui/format.js", "src/ui/format.js exports shout, and nothing that ships reads it"),
    ("dead-export", "warning", "src/ui/view.js", "src/ui/view.js exports unusedHelper, and nothing that ships reads it"),
    ("io-at-load", "warning", "src/db/query.js:5", "src/db/query.js:5 may do I/O as its module loads"),
    ("unused-dependency", "warning", "", "unused-dep is a dependency, and nothing of it ships"),
])


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)

    # The fixture, with the library of rules.
    p = esb(split(OUT + "/linted", "--lint=" + RULES))
    text = p.stdout + p.stderr
    open(OUT + "/fixture.txt", "w").write(text)
    found = findings(text)
    check(found == EXPECTED, "the fixture's findings are exactly those it was written to have"
          + ("" if found == EXPECTED else "\n  got: %r" % found))
    check(p.returncode != 0 and "the build stops" in text and not os.path.exists(OUT + "/linted/main.js"),
          "an error found stops the build before it writes anything")
    for line, what in [
        ('      src/main.js:6  render(config, label("main"));', "a secret's explanation is linking's chain from the route"),
        ("      -> config in src/config.js:1  export const config = {", "... to the statement that reads it"),
        ("      `process.env.$N` at src/config.js:2, STRIPE_SECRET", "... and the place its pattern matched"),
        ("    no public(STRIPE_SECRET)", "... and what it is not"),
        ("      copy(tiny-dup, node_modules/other-lib/node_modules/tiny-dup)", "a count is explained by what it counted"),
        ("          -> pad in node_modules/other-lib/node_modules/tiny-dup/index.js:1  export function pad(s) { return s.padStart(12, \".\"); }",
         "... each with the chain that ships it"),
        ("      needs(src/ui/view.js:4, src/db/query.js:1, query)", "a layering error says what is needed, and by what name"),
    ]:
        check(line in text.splitlines(), what)

    # Warnings only: the build writes, and what it writes is what it writes without lints.
    warnings = OUT + "/warnings.lint"
    open(warnings, "w").write(re.sub(r"^(lint [a-z-]+) error ", r"\1 warning ", open(RULES).read(), flags=re.M))
    plain = esb(split(OUT + "/plain"))
    linted = esb(split(OUT + "/warned", "--lint=" + warnings))
    same = plain.returncode == 0 and linted.returncode == 0 and all(
        open(os.path.join(OUT, "plain", f), "rb").read() == open(os.path.join(OUT, "warned", f), "rb").read()
        for f in os.listdir(OUT + "/plain"))
    check(same and sorted(os.listdir(OUT + "/plain")) == sorted(os.listdir(OUT + "/warned")),
          "lints change nothing a build writes")
    single = esb(["src/main.js", "--outfile=" + OUT + "/single/main.js", "--lint=" + warnings])
    check(single.returncode == 0 and ("secret-shipped", "warning", "src/config.js:1",
                                      "process.env.STRIPE_SECRET is in code src/main.js sends to the browser") in findings(single.stdout),
          "without code splitting, the same rules find the same")

    # Rules that cannot mean anything.
    bad = OUT + "/bad.lint"
    for rules, message in [
        ('lint x warning "a" :- shipz(R, P) ;\n', "bad.lint:1:23: no relation shipz"),
        ('lint x warning "a" :- ships(R) ;\n', "bad.lint:1:23: ships has 2 columns, not 1"),
        ('lint x warning "{Q}" :- ships(R, P) ;\n', "bad.lint:1:1: the message names {Q}"),
        ('p(X) :- route(R), X > 3 ;\n', "bad.lint:1:19: X is bound by no atom of the rule"),
        ('a(X) :- route(X), !b(X) ;\nb(X) :- route(X), !a(X) ;\nlint x warning "a" :- a(X) ;\n', "depends on its own negation"),
        ('lint x warning "a" :- code(P, `process.env.(`) ;\n', "bad.lint:1 `process.env.(`:1:13: expected PropName"),
        ('route(X) :- module(X) ;\n', "bad.lint:1:1: route is the build's: no rule adds to it"),
        ('lint x warning "a" :- ships(R, P), R > 3 ;\n', "compares src/main.js and 3, which are not both numbers"),
    ]:
        open(bad, "w").write(rules)
        p = esb(["src/main.js", "--outfile=" + OUT + "/bad/main.js", "--lint=" + bad])
        check(p.returncode != 0 and message in p.stdout + p.stderr, "an error at its place: " + message)

    # Watching: an error is said and the watcher goes on; editing the rules is an edit.
    dest = OUT + "/watch"
    shutil.copytree(FIXTURE, dest)
    open(dest + "/rules.lint", "w").write('lint stops error at P "a debugger ships" :- ships(_, P), code(P, `debugger`) ;\n')
    log = open(OUT + "/watch.log", "w")
    w = subprocess.Popen([ESB] + split("out", "--lint=rules.lint", "--watch", "--no-cache"), cwd=dest, stdout=log, stderr=subprocess.STDOUT)
    try:
        time.sleep(1.5)
        open(dest + "/rules.lint", "w").write('lint fetches warning at P "{P} fetches" :- ships(_, P), code(P, `fetch($$A)`) ;\n')
        time.sleep(1.5)
    finally:
        w.terminate()
        w.wait()
        log.close()
    text = open(OUT + "/watch.log").read()
    check("[stops] a debugger ships" in text and "[watch] build 2" in text and "[fetches] src/db/query.js:5 fetches" in text,
          "watching: an error is said, the watcher goes on, and the rules file is watched")

    # A build spec's lint.
    spec = OUT + "/lint.bundler"
    open(spec, "w").write('bundler\ntarget site\n  entries "src/main.js"\n  outdir "%s"\n  splitting\n  format esm\n  lint "%s"\nend\n'
                          % (OUT + "/spec", warnings))
    p = subprocess.run([SPEC, spec], cwd=FIXTURE, capture_output=True, text=True)
    check(p.returncode == 0 and "[duplicate-package] tiny-dup ships 2 copies" in p.stdout, "a build spec names rules with `lint`")

    # Real libraries.
    for app in ["zod", "three", "d3", "rx"]:
        p = esb(["apps/%s.js" % app, "--minify", "--outfile=" + OUT + "/apps/%s.js" % app, "--lint=" + RULES], cwd=os.path.join(ROOT, "tests"))
        check(p.returncode == 0 and re.search(r"^0 errors, \d+ warnings?$", p.stdout, re.M) is not None,
              "%s: the library of rules runs, and finds no error" % app)

    print("lint-check: %d passed, %d failed" % (passed, len(failures)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
