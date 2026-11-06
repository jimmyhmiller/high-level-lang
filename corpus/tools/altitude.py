#!/usr/bin/env python3
# How much of the bundler's .rules and .attrs is written at a low level: loops over indices,
# variables updated in place, global state, children read by position, byte scanning. A
# function counts as low-level if any of these appear in it. It is a measure of the
# source, by pattern, not a proof; run it before and after a change to see the change.
#   usage: altitude.py [--fns] [files...]   (default: poc/lang/bundle/*.rules *.attrs)
import collections, glob, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../poc/lang/bundle")
PATTERNS = collections.OrderedDict([
    ("while",   re.compile(r"^\s*while\b[^\n]*\{\s*$", re.M)),
    ("var",     re.compile(r"^\s*var ", re.M)),
    ("kids[i]", re.compile(r"\.kids\[")),
    ("bytes",   re.compile(r"'\\?.'")),
    ("buf",     re.compile(r"\bbuf-")),
    ("out-arg", re.compile(r"\bmut \[")),
])
DECL = re.compile(r"\n(?=(?:memo )?fn |on |rewrite |const |record |state |task state |enum |inh |given |collect |input |use |rules |attrs |#)")
STATE = re.compile(r"^(?:task )?state ([a-z][\w\-?!]*)", re.M)
# A context is bound for a scope with `with`; written to any other way it is state like the rest.
CONTEXT = re.compile(r"^context ([a-z][\w\-?!]*)", re.M)


def code_lines(chunk):
    return [l for l in chunk.split("\n") if l.strip() and not l.strip().startswith("#")]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show = "--fns" in sys.argv
    files = args or sorted(glob.glob(os.path.join(ROOT, "*.rules")) + glob.glob(os.path.join(ROOT, "*.attrs")))
    fns = collections.Counter()
    lines = collections.Counter()
    per_file = []
    total_lines = total_fns = 0
    states = 0
    for path in files:
        src = open(path).read()
        names = STATE.findall(src)
        states += len(names)
        names += CONTEXT.findall(src)
        writes = [re.compile(r"(?:^|\{)\s*" + re.escape(n) + r"(\[[^\]]*\])?\s*(=|\+=|\+\+=)[^=>]", re.M) for n in names]
        low_here = all_here = 0
        for chunk in DECL.split(src):
            if not re.match(r"(memo )?fn |on |rewrite ", chunk):
                continue
            n = len(code_lines(chunk))
            total_lines += n
            total_fns += 1
            all_here += n
            hits = [k for k, r in PATTERNS.items() if r.search(chunk)]
            if any(w.search(chunk) for w in writes):
                hits.append("global")
            for k in hits:
                fns[k] += 1
                lines[k] += n
            if hits:
                fns["any"] += 1
                lines["any"] += n
                low_here += n
                if show:
                    head = chunk.split("\n")[0][:70]
                    print(f"  {os.path.basename(path)}: {head}  [{', '.join(hits)}]")
        per_file.append((os.path.basename(path), all_here, low_here))
    print(f"{total_fns} functions, `on` blocks and rewrites, {total_lines} lines of code; {states} global state declarations")
    for k in list(PATTERNS) + ["global", "any"]:
        print(f"  {k:8} {fns[k]:4} functions  {lines[k]:5} lines  {100 * lines[k] // max(total_lines, 1):3}%")
    print("by file (lines of code, of which low-level):")
    for name, a, l in sorted(per_file, key=lambda x: -x[2]):
        print(f"  {name:18} {a:5} {l:5}  {100 * l // max(a, 1):3}%")


main()
