#!/usr/bin/env python3
# How much of the bundler's .rules and .attrs is imperative rather than declarative. A function,
# `on` block or rewrite counts as imperative, all its lines, if its code has any statement: a block
# body of steps, `let`, `var`, an `if`, a `for` or `while` statement, `return`, an assignment, or a
# call made for its effect (`assert`, `f!(…)`). Declarative is what is left: one expression made of
# matches, rewrites, attribute equations (`child.attr = value` in an `on` block), comprehensions and
# queries, with guards on rules, arms and comprehension clauses. It is a measure of the source, by
# pattern, not a proof; run it before and after a change to see the change.
#   usage: altitude.py [--fns] [files...]   (default: src/bundle/*.rules *.attrs)
import collections, glob, os, re, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../src/bundle")
DECL = re.compile(r"\n(?=(?:everywhere |memo )?fn |on |rewrite |const |record |state |task state |context "
                  r"|enum |inh |syn |given |collect |input |use |rules |attrs |include |#)")
UNIT = re.compile(r"(?:everywhere |memo )?fn |on |rewrite ")
IMPERATIVE = collections.OrderedDict([
    ("block",  re.compile(r"^(?:everywhere |memo )?fn [^=\n]*\{\s*$", re.M)),
    ("let",    re.compile(r"^\s+let ", re.M)),
    ("var",    re.compile(r"^\s*var ", re.M)),
    ("if",     re.compile(r"\bif\b")),
    ("for",    re.compile(r"^\s*for [^\n]*\{\s*$", re.M)),
    ("while",  re.compile(r"^\s*while\b", re.M)),
    ("return", re.compile(r"\breturn\b")),
    ("assign", re.compile(r"^\s*[a-z][\w\-?!.\[\]]*\s*(?:=|\+=|\+\+=)\s", re.M)),
    ("effect", re.compile(r"^\s*(?:assert |[a-z][\w.\-]*!\()", re.M)),
])
# Guards are declarative: a comprehension's or quantifier's `if`, a rewrite's, a match arm's.
GUARDS = [
    (re.compile(r"(\bfor\b[^\]\n]*?)\bif\b"), r"\1WHERE"),
    (re.compile(r"(\b(?:first|last|any|all|count|sum)\b[^:\n]*?)\bif\b"), r"\1WHERE"),
    (re.compile(r"(^rewrite[^\n]*?)\bif\b", re.M), r"\1WHERE"),
    (re.compile(r"\bif\b(?=[^\n]*=>)"), "WHERE"),
]
# In an `on` block, `target.attr = value` is an equation.
EQUATION = re.compile(r"^\s*[\w\-]+\.[\w\-]+\s*=\s", re.M)


def code_lines(chunk):
    return [l for l in chunk.split("\n") if l.strip() and not l.strip().startswith("#")]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    show = "--fns" in sys.argv
    files = args or sorted(glob.glob(os.path.join(ROOT, "*.rules")) + glob.glob(os.path.join(ROOT, "*.attrs")))
    lines = collections.Counter()
    per_file = []
    total_lines = total_units = imperative_units = 0
    for path in files:
        all_here = imp_here = 0
        for chunk in DECL.split(open(path).read()):
            if not UNIT.match(chunk):
                continue
            code = code_lines(chunk)
            n = len(code)
            body = "\n".join(code)
            if chunk.startswith("on "):
                body = EQUATION.sub("  EQ ", body)
            for r, to in GUARDS:
                body = r.sub(to, body)
            # `e where x = …, y = …`: what follows `where` is equations.
            before_where = re.split(r"\bwhere\b", body)[0]
            hits = [k for k, r in IMPERATIVE.items() if r.search(before_where if k == "assign" else body)]
            total_lines += n
            total_units += 1
            all_here += n
            for k in hits:
                lines[k] += n
            if hits:
                imperative_units += 1
                imp_here += n
                if show:
                    print(f"  {os.path.basename(path)}: {code[0][:70]}  [{', '.join(hits)}]")
        per_file.append((os.path.basename(path), all_here, imp_here))
    imp = sum(i for _, _, i in per_file)
    print(f"{total_units} functions, `on` blocks and rewrites, {total_lines} lines of code")
    print(f"imperative: {imperative_units} of them, {imp} lines, {100 * imp // max(total_lines, 1)}%")
    print("lines in units with each (a unit can have several):")
    for k in IMPERATIVE:
        print(f"  {k:8} {lines[k]:5} lines  {100 * lines[k] // max(total_lines, 1):3}%")
    print("by file (lines of code, of which imperative):")
    for name, a, i in sorted(per_file, key=lambda x: -x[2]):
        print(f"  {name:18} {a:5} {i:5}  {100 * i // max(a, 1):3}%")


main()
