#!/usr/bin/env python3
"""Make the explorer prototype's data from the repository and a real build of the example.

Everything static (declarations, references, grammar, relations, rewrite rules, the pipeline) is
read from src/. The trace view's output, source map and analysis come from building
explorer/prototype/example with out/bin/esb. What a build cannot report yet (derivations of
`live`, which rewrite rules fired, scope and attribute values) is written down below as traces
done by hand against the real rules; each step names its rule by a line of text that must exist,
so a rule that moves or changes stops this script instead of leaving a stale reference.

    python3 explorer/prototype/gen.py      ->  out/explorer/tower-explorer.html
"""
import json, os, re, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "out", "explorer")

LANG_EXT = {".rules": "rules", ".attrs": "attrs", ".facts": "facts", ".rewrite": "rewrite",
            ".syntax": "syntax", ".scopes": "scopes", ".pipeline": "pipeline", ".bundler": "bundler"}


def fail(msg):
    sys.exit("gen.py: " + msg)


# ---------------------------------------------------------------- files

def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def rel(path):
    return os.path.relpath(path, ROOT)


files = {}  # relpath -> {lang, module, text, lines}
for d, _, names in os.walk(SRC):
    for n in sorted(names):
        ext = os.path.splitext(n)[1]
        if ext in LANG_EXT:
            p = os.path.join(d, n)
            t = read(p)
            files[rel(p)] = {"lang": LANG_EXT[ext], "text": t, "lines": t.split("\n")}


def module_name(path, f):
    """The module a file declares, or the one its path names (facts files say only `facts`)."""
    for line in f["lines"]:
        if line.startswith("#") or not line.strip():
            continue
        m = re.match(r"(rules|attrs|rewrite|scopes|pipeline)\s+([\w.\-]+)", line)
        if m:
            return m.group(2)
        break
    parts = os.path.splitext(path)[0].split(os.sep)[1:]  # drop "src"
    return ".".join(parts)


for p, f in files.items():
    f["module"] = module_name(p, f)
mod_file = {}
for p, f in files.items():
    if f["lang"] in ("rules", "attrs", "facts"):
        mod_file.setdefault(f["module"], p)


def find_line(path, needle, after=0):
    """1-based line of the first line containing `needle` at or after `after`; fails if absent."""
    f = files.get(path)
    if f is None:
        fail("no such language file: " + path)
    for i, line in enumerate(f["lines"]):
        if i + 1 >= after and needle in line:
            return i + 1
    fail("%s: no line contains %r (has the rule moved or changed?)" % (path, needle))


def doc_above(lines, i):
    """The comment block directly above 0-based line i."""
    out = []
    j = i - 1
    while j >= 0 and lines[j].lstrip().startswith("#"):
        out.append(lines[j].lstrip()[1:].strip())
        j -= 1
    text = " ".join(reversed(out))
    return re.sub(r"-{6,}", "", text).strip()


# ---------------------------------------------------------------- declarations

decls = []  # {id, file, lang, kind, name, line, doc}


def add(path, kind, name, line, **extra):
    f = files[path]
    d = {"id": len(decls), "file": path, "lang": f["lang"], "kind": kind, "name": name,
         "line": line, "doc": doc_above(f["lines"], line - 1)}
    d.update(extra)
    decls.append(d)
    return d


NAME = r"[A-Za-z_][\w\-]*[?!]?"
for path, f in files.items():
    lang = f["lang"]
    for i, line in enumerate(f["lines"]):
        ln = i + 1
        if lang in ("rules", "attrs"):
            m = re.match(r"(?:pub\s+)?(?:everywhere\s+)?(fn|memo fn)\s+(" + NAME + r")", line)
            if m:
                add(path, "fn", m.group(2), ln); continue
            m = re.match(r"(?:boxed\s+)?(record|enum)\s+(" + NAME + r")", line)
            if m:
                add(path, m.group(1), m.group(2), ln); continue
            m = re.match(r"setting\s+(" + NAME + r")", line)
            if m:
                add(path, "setting", m.group(1), ln); continue
            if lang == "attrs":
                m = re.match(r"(inh|syn|input)\s+(" + NAME + r")", line)
                if m:
                    add(path, m.group(1), m.group(2), ln); continue
                m = re.match(r"on\s+(.*?)\s*\{\s*$", line)
                if m:
                    add(path, "on", m.group(1), ln); continue
                m = re.match(r"rewrite\s+(.*?)\s*(=>|$)", line)
                if m:
                    add(path, "rewrite", m.group(1)[:60], ln); continue
        elif lang == "facts":
            m = re.match(r"relation\s+(" + NAME + r")\((.*)\)", line)
            if m:
                add(path, "relation", m.group(1), ln, cols=[c.strip() for c in m.group(2).split(",")])
        elif lang == "rewrite":
            m = re.match(r"rule\s+(" + NAME + r")\s*:", line)
            if m:
                add(path, "rule", m.group(1), ln)
        elif lang == "syntax":
            m = re.match(r"((?:hidden|memo|raw)\s+)*(rule|token|fragment)\s+(\w+)", line)
            if m:
                add(path, m.group(2), m.group(3), ln); continue
            m = re.match(r"(infix|suffix|postfix)\s+(\w+)", line)
            if m:
                add(path, m.group(1), m.group(2), ln)
        elif lang == "scopes":
            m = re.match(r"(scope|names|name|outside|program|sequential|dynamic|dynamic-name|unshadowed|unshadowed-within|ref|bind)\s+(.*?)\s*;?\s*$", line)
            if m:
                add(path, m.group(1), m.group(2), ln)
        elif lang == "pipeline":
            m = re.match(r"(mechanism|strategy|stage|plan|size)\s+([\w.\-/]+)", line)
            if m:
                add(path, m.group(1), m.group(2), ln)
        elif lang == "bundler":
            m = re.match(r"target\s+(\S+)", line)
            if m:
                add(path, "target", m.group(1), ln)

by_file = {}
for d in decls:
    by_file.setdefault(d["file"], []).append(d)
for path, ds in by_file.items():
    ds.sort(key=lambda d: d["line"])
    n = len(files[path]["lines"])
    for k, d in enumerate(ds):
        d["end"] = (ds[k + 1]["line"] - 1) if k + 1 < len(ds) else n
        # trim the next declaration's comment block and trailing blanks off this one's range
        lines = files[path]["lines"]
        e = d["end"]
        while e > d["line"] and (not lines[e - 1].strip() or lines[e - 1].lstrip().startswith("#")):
            e -= 1
        d["end"] = e


def enclosing(path, ln):
    best = None
    for d in by_file.get(path, []):
        if d["line"] <= ln:
            best = d
        else:
            break
    return best["id"] if best else None


# ---------------------------------------------------------------- references across languages

refs = {}  # decl id -> {label: [{file, line, text, in}]}


def add_ref(target, label, path, ln):
    lst = refs.setdefault(target, {}).setdefault(label, [])
    if any(r["file"] == path and r["line"] == ln for r in lst):
        return
    lst.append({"file": path, "line": ln, "text": files[path]["lines"][ln - 1].strip()[:160],
                "in": enclosing(path, ln)})


def strip_comment(line):
    out, q = [], None
    i = 0
    while i < len(line):
        c = line[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < len(line):
                out.append(line[i + 1]); i += 2; continue
            if c == q:
                q = None
        elif c in "\"`":
            q = c; out.append(c)
        elif c == "#":
            break
        else:
            out.append(c)
        i += 1
    return "".join(out)


# Node kinds: what the JavaScript grammar makes, and everywhere a pattern or a directive names one.
JS = "src/bundle/js.syntax"
kinds = {}  # kind -> {decl, fields}
for i, line in enumerate(files[JS]["lines"]):
    code = strip_comment(line)
    for m in re.finditer(r"->\s*([A-Z]\w*)(?:\(([^)]*)\))?", code):
        k = m.group(1)
        if k not in kinds:
            kinds[k] = {"line": i + 1, "fields": [x.strip() for x in (m.group(2) or "").split(",") if x.strip()]}
in_infix = False
for i, line in enumerate(files[JS]["lines"]):
    code = strip_comment(line)
    if code.startswith("infix"):
        in_infix = True
    if in_infix:
        for m in re.finditer(r"\"[^\"]*\"\s+([A-Z]\w*)", code):
            kinds.setdefault(m.group(1), {"line": i + 1, "fields": ["left", "right"]})
        if code.strip().endswith(";"):
            in_infix = False
kind_decl = {}
for k in sorted(kinds):
    d = add(JS, "node kind", k, kinds[k]["line"], fields=kinds[k]["fields"], virtual=True)
    d["doc"] = ""
    kind_decl[k] = d["id"]

kind_re = re.compile(r"(?<![\w\-.@])([A-Z]\w*)\(")
for path, f in files.items():
    if not path.startswith("src/bundle") and not path.startswith("src/app"):
        continue
    lang = f["lang"]
    for i, line in enumerate(f["lines"]):
        code = strip_comment(line)
        if lang in ("rules", "attrs", "rewrite"):
            for m in kind_re.finditer(code):
                k = m.group(1)
                if k in kind_decl:
                    add_ref(kind_decl[k], "matched or made in " + lang, path, i + 1)
        elif lang == "scopes":
            for w in re.findall(r"\b[A-Z]\w*\b", code):
                if w in kind_decl:
                    add_ref(kind_decl[w], "placed by scopes", path, i + 1)
        elif lang == "syntax" and path == JS:
            for m in re.finditer(r"->\s*([A-Z]\w*)", code):
                if m.group(1) in kind_decl and i + 1 != kinds[m.group(1)]["line"]:
                    add_ref(kind_decl[m.group(1)], "made by grammar", path, i + 1)

# Calls: a name called in its own module, or `alias.name(` through a `use … as alias`.
fns = {}  # (module, name) -> decl id
for d in decls:
    if d["lang"] in ("rules", "attrs") and d["kind"] in ("fn", "record", "setting"):
        fns.setdefault((files[d["file"]]["module"], d["name"]), d["id"])
KEYWORDS = {"if", "match", "fn", "for", "while", "some", "none", "not", "and", "or", "len", "first",
            "last", "any", "all", "count", "sum", "fold", "scan", "with", "where", "in", "print"}
call_re = re.compile(r"(?<![\w\-?!.])(?:([a-z][\w]*)\.)?(" + NAME + r")\(")
for path, f in files.items():
    if f["lang"] not in ("rules", "attrs"):
        continue
    me = f["module"]
    aliases = {}
    for line in f["lines"]:
        m = re.match(r"use\s+([\w.]+)\s+as\s+(\w+)", line)
        if m:
            aliases[m.group(2)] = m.group(1)
    for i, line in enumerate(f["lines"]):
        code = strip_comment(line)
        if re.match(r"\s*(?:pub\s+)?(?:everywhere\s+)?(?:memo\s+)?fn\s", code):
            code = code.split("=", 1)[1] if "=" in code else ""
        for m in call_re.finditer(code):
            al, name = m.group(1), m.group(2)
            if name in KEYWORDS:
                continue
            target = None
            if al and al in aliases:
                target = fns.get((aliases[al], name))
                if target is None and (name.startswith("fact-") or name.startswith("why-")):
                    fm = aliases[al]
                    rname = name.split("-", 1)[1]
                    for d in by_file.get(mod_file.get(fm, ""), []):
                        if d["kind"] == "relation" and d["name"] == rname:
                            add_ref(d["id"], "asserted from " + f["lang"] if name.startswith("fact-")
                                    else "explained from " + f["lang"], path, i + 1)
            elif not al:
                target = fns.get((me, name))
            if target is not None and decls[target]["line"] != i + 1:
                add_ref(target, "called by", path, i + 1)

# Datalog: each rule's head and body, which relations derive and read which.
facts_rules = {}  # path -> [{line, end, head, body:[{rel, neg, args}], text}]
for path, f in files.items():
    if f["lang"] != "facts":
        continue
    rel_ids = {d["name"]: d["id"] for d in by_file.get(path, []) if d["kind"] == "relation"}
    out = []
    buf, start = "", None
    for i, line in enumerate(f["lines"]):
        code = strip_comment(line).strip()
        if not code or code.startswith("relation") or code == "facts":
            continue
        if start is None:
            start = i + 1
        buf += " " + code
        if code.endswith(";"):
            stmt = buf.strip()[:-1].strip()
            if ":-" in stmt:
                head, body = stmt.split(":-", 1)
            else:
                head, body = stmt, ""
            hm = re.match(r"\s*(" + NAME + r")\((.*)\)\s*$", head)
            if not hm:
                fail("%s:%d: cannot read rule head %r" % (path, start, head))
            atoms = []
            for am in re.finditer(r"(!?)(" + NAME + r")\(([^)]*)\)", body):
                atoms.append({"rel": am.group(2), "neg": am.group(1) == "!",
                              "args": [a.strip() for a in am.group(3).split(",")]})
            for cm in re.finditer(r"(\b[A-Z]\w*\s*!=\s*[A-Z]\w*)", body):
                atoms.append({"rel": "!=", "neg": False, "args": [cm.group(1)]})
            r = {"line": start, "end": i + 1, "head": hm.group(1),
                 "args": [a.strip() for a in hm.group(2).split(",")], "body": atoms, "text": stmt}
            out.append(r)
            if r["head"] in rel_ids:
                add_ref(rel_ids[r["head"]], "derived by", path, start)
            for a in atoms:
                if a["rel"] in rel_ids:
                    add_ref(rel_ids[a["rel"]], "read by", path, start)
            buf, start = "", None
    facts_rules[path] = out

# Grammar references: which rules name a nonterminal.
syn_ids = {}
for d in decls:
    if d["lang"] == "syntax" and d["kind"] in ("rule", "token", "fragment", "infix", "suffix", "postfix"):
        syn_ids.setdefault((d["file"], d["name"]), d["id"])
for path, f in files.items():
    if f["lang"] != "syntax":
        continue
    for i, line in enumerate(f["lines"]):
        code = strip_comment(line)
        code = re.sub(r"\"(?:\\.|[^\"\\])*\"", "", code)
        code = code.split("->")[0]
        for w in set(re.findall(r"\b[A-Z]\w*\b", code)):
            t = syn_ids.get((path, w))
            if t is not None and decls[t]["line"] != i + 1:
                add_ref(t, "used by", path, i + 1)

# Pipeline names functions: a kept or staged function points back to the strategy or stage.
PIPE = "src/app/build.pipeline"
for i, line in enumerate(files[PIPE]["lines"]):
    for m in re.finditer(r"\b(bundle\.\w+|app\.\w+|hl\.\w+)/(" + NAME + r")", strip_comment(line)):
        t = fns.get((m.group(1), m.group(2)))
        if t is not None:
            add_ref(t, "kept or staged by pipeline", PIPE, i + 1)


# ---------------------------------------------------------------- the grammar, for railroads

class Tok:
    def __init__(self, s):
        self.s, self.i = s, 0
        self.toks = self.lex(s)
        self.k = 0

    @staticmethod
    def lex(s):
        out, i = [], 0
        while i < len(s):
            c = s[i]
            if c.isspace():
                i += 1
            elif c == "#":
                while i < len(s) and s[i] != "\n":
                    i += 1
            elif c == '"':
                j = i + 1
                while s[j] != '"':
                    j += 2 if s[j] == "\\" else 1
                out.append(("str", s[i + 1:j])); i = j + 1
            elif c == "[":
                j = i + 1
                while s[j] != "]":
                    j += 2 if s[j] == "\\" else 1
                out.append(("class", s[i:j + 1])); i = j + 1
            elif s.startswith("->", i):
                out.append(("->", "->")); i += 2
            elif c in "@":
                m = re.match(r"@[\w\-]+", s[i:])
                out.append(("at", m.group(0))); i += len(m.group(0))
            elif c.isalpha() or c == "_":
                m = re.match(r"[A-Za-z_][\w\-]*", s[i:])
                w = m.group(0); i += len(w)
                if w in ("if", "unless", "with") and i < len(s) and s[i] == "(":
                    j = s.index(")", i)
                    out.append(("flag", w + " " + s[i + 1:j].strip())); i = j + 1
                else:
                    out.append(("id", w))
            elif c in "()|*+?!&~,;.:=":
                out.append((c, c)); i += 1
            else:
                fail("grammar: unexpected %r in %r" % (c, s[max(0, i - 20):i + 20]))
        return out

    def peek(self, o=0):
        return self.toks[self.k + o] if self.k + o < len(self.toks) else (None, None)

    def take(self):
        t = self.peek(); self.k += 1; return t


def p_alt(t):
    opts = [p_seq(t)]
    while t.peek()[0] == "|":
        t.take(); opts.append(p_seq(t))
    return opts[0] if len(opts) == 1 else {"t": "alt", "opts": opts}


def p_seq(t):
    items, action = [], None
    while t.peek()[0] not in (None, "|", ")", ";"):
        if t.peek()[0] == "->":
            t.take()
            _, k = t.take()
            fields = []
            if t.peek()[0] == "(":
                t.take()
                while t.peek()[0] != ")":
                    tk = t.take()
                    if tk[0] == "id":
                        fields.append(tk[1])
                t.take()
            action = {"kind": k, "fields": fields}
            continue
        items.append(p_item(t))
    node = {"t": "seq", "items": items}
    if action:
        node["action"] = action
    return node


def p_item(t):
    if t.peek()[0] in ("!", "&"):
        op = t.take()[0]
        return {"t": "pred", "op": op, "x": p_item(t)}
    if t.peek()[0] == "~":
        t.take()
        x = p_item(t)
        x["keep"] = True
        return x
    x = p_primary(t)
    while True:
        k = t.peek()[0]
        if k in ("*", "+"):
            t.take(); x = {"t": "rep", "min": 0 if k == "*" else 1, "x": x}
        elif k == "?":
            t.take(); x = {"t": "opt", "x": x}
        elif k == "," and t.peek(1)[0] in ("*", "+"):
            t.take(); k2 = t.take()[0]
            x = {"t": "rep", "min": 0 if k2 == "*" else 1, "x": x, "sep": ","}
        else:
            return x


def p_primary(t):
    k, v = t.take()
    if k == "str":
        return {"t": "term", "s": v}
    if k == "class":
        return {"t": "class", "s": v}
    if k == ".":
        return {"t": "any"}
    if k == "id":
        return {"t": "nt", "s": v}
    if k == "at":
        return {"t": "flag", "s": v}
    if k == "flag":
        return {"t": "flag", "s": v}
    if k == "(":
        x = p_alt(t)
        if t.take()[0] != ")":
            fail("grammar: expected )")
        return x
    fail("grammar: unexpected token %r %r" % (k, v))


def grammar_of(path):
    text = files[path]["text"]
    out = []
    pat = re.compile(r"^((?:(?:hidden|memo|raw)\s+)*)(rule|token|fragment)\s+(\w+)([^=\n]*)\s*=", re.M)
    for m in pat.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        t = Tok(text[m.end():])
        body = p_alt(t)
        out.append({"name": m.group(3), "kind": m.group(2), "mods": m.group(1).split(),
                    "head": m.group(4).strip(), "line": line, "body": body})
    for m in re.finditer(r"^(suffix|postfix)\s+(\w+)\s+over\s+(\w+)\s+", text, re.M):
        line = text.count("\n", 0, m.start()) + 1
        t = Tok(text[m.end():])
        tail = p_seq(t)
        rep = {"t": "rep", "min": 0, "x": tail} if m.group(1) == "postfix" else {"t": "opt", "x": tail}
        out.append({"name": m.group(2), "kind": m.group(1), "mods": [], "head": "over " + m.group(3),
                    "line": line, "body": {"t": "seq", "items": [{"t": "nt", "s": m.group(3)}, rep]}})
    for m in re.finditer(r"^infix\s+(\w+)\s+over\s+(\w+)\s*\n((?:.*\n)*?.*;)", text, re.M):
        line = text.count("\n", 0, m.start()) + 1
        levels = []
        for lm in re.finditer(r"^\s*(left|right)\s+(.*)$", m.group(3), re.M):
            ops = re.findall(r"(unless\(\w+\)\s+)?\"([^\"]+)\"\s+([A-Z]\w*)", lm.group(2))
            levels.append({"assoc": lm.group(1),
                           "ops": [{"op": o[1], "kind": o[2], "flag": o[0].strip()} for o in ops]})
        out.append({"name": m.group(1), "kind": "infix", "mods": [], "head": "over " + m.group(2),
                    "line": line, "levels": levels})
    out.sort(key=lambda r: r["line"])
    return out


grammars = {}
for p in ("src/bundle/js.syntax", "src/tools/letlang.syntax", "src/bundle/package.syntax",
          "src/bundle/literal.syntax", "src/bundle/comments.syntax"):
    if p in files:
        grammars[p] = grammar_of(p)


# ---------------------------------------------------------------- rewrite rules as trees

def parse_term(s):
    s = s.strip()
    toks = re.findall(r"!?@?[\w\-?]+(?:\.\.\.)?|\(|\)|,", s)
    k = [0]

    def term():
        w = toks[k[0]]; k[0] += 1
        node = {"n": w}
        if k[0] < len(toks) and toks[k[0]] == "(":
            k[0] += 1
            node["c"] = []
            while toks[k[0]] != ")":
                node["c"].append(term())
                if toks[k[0]] == ",":
                    k[0] += 1
            k[0] += 1
        return node
    return term()


def split_top(s, sep=","):
    out, depth, cur = [], 0, ""
    for c in s:
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        if c == sep and depth == 0:
            out.append(cur); cur = ""
        else:
            cur += c
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out]


rewrites = {}
for path, f in files.items():
    if f["lang"] != "rewrite":
        continue
    text = f["text"]
    section = ""
    rules = []
    lines = f["lines"]
    i = 0
    while i < len(lines):
        line = lines[i]
        sm = re.match(r"#\s*-{8,}\s*(.+)$", line)
        if sm:
            section = sm.group(1).strip()
        m = re.match(r"rule\s+(" + NAME + r")\s*:(.*)$", line)
        if m:
            start = i + 1
            body = m.group(2)
            while not strip_comment(body).rstrip().endswith(";"):
                i += 1
                body += " " + strip_comment(lines[i]).strip()
            body = strip_comment(body).strip()[:-1].strip()
            lhs, rhs = body.split("=>", 1)
            guards = []
            if " when " in " " + lhs:
                lhs, g = re.split(r"\bwhen\b", lhs, maxsplit=1)
                guards = split_top(g)
            rules.append({"name": m.group(1), "line": start, "section": section,
                          "lhs": parse_term(lhs), "rhs": parse_term(rhs), "guards": guards,
                          "src": " ".join(body.split())})
        i += 1
    rewrites[path] = rules


# ---------------------------------------------------------------- the pipeline

def pipeline_of(path):
    lines = files[path]["lines"]
    mech, strat, stages, plans, sizes = [], [], [], [], []
    i = 0
    while i < len(lines):
        line = strip_comment(lines[i]).rstrip()
        m = re.match(r"(mechanism|strategy|plan)\s+([\w\-]+)\s*$", line)
        if m:
            kind, name, start = m.group(1), m.group(2), i + 1
            body = []
            i += 1
            while strip_comment(lines[i]).strip() != "end":
                c = strip_comment(lines[i]).rstrip()
                if c.strip():
                    if c.startswith("       ") and body:
                        body[-1] += " " + c.strip()
                    else:
                        body.append(c.strip())
                i += 1
            item = {"name": name, "line": start, "doc": doc_above(lines, start - 1), "body": body}
            {"mechanism": mech, "strategy": strat, "plan": plans}[kind].append(item)
        m = re.match(r"stage\s+([\w\-]+)\s+(per\s+[^b]*?|whole)\s+((?:bundle|hl|app)\..*)$", line)
        if m:
            start = i + 1
            body = [m.group(3)]
            while i + 1 < len(lines) and lines[i + 1].startswith("               "):
                i += 1
                body.append(strip_comment(lines[i]).strip())
            stages.append({"name": m.group(1), "per": m.group(2).strip(), "line": start,
                           "doc": doc_above(lines, start - 1), "body": " ".join(body)})
        m = re.match(r"size\s+(\S+)\s+(\d+)", line)
        if m:
            sizes.append({"name": m.group(1), "value": int(m.group(2)), "line": i + 1,
                          "doc": doc_above(lines, i)})
        i += 1
    return {"mechanisms": mech, "strategies": strat, "stages": stages, "plans": plans, "sizes": sizes}


pipeline = pipeline_of(PIPE)


# ---------------------------------------------------------------- the example, built for real

EX = os.path.join(HERE, "example")
ESB = os.path.join(ROOT, "out", "bin", "esb")
JSPARSE = os.path.join(ROOT, "out", "bin", "jsparse")
for b in (ESB, JSPARSE):
    if not os.path.exists(b):
        fail(b + " is missing: build it with tools/build-tools.sh")
tmp = tempfile.mkdtemp(prefix="explorer-")
outfile = os.path.join(tmp, "out.js")
r = subprocess.run([ESB, "main.js", "--bundle", "--minify-syntax", "--sourcemap",
                    "--outfile=" + outfile, "--analyze=" + os.path.join(tmp, "an")],
                   cwd=EX, capture_output=True, text=True)
if r.returncode != 0 or not os.path.exists(outfile):
    fail("esb failed on the example:\n" + r.stdout + r.stderr)
out_js = read(outfile)
out_map = json.loads(read(outfile + ".map"))
analysis = json.loads(read(os.path.join(tmp, "an", "analysis.json")))
for o in analysis["outputs"]:
    o["path"] = os.path.basename(o["path"])
esbuild_out = None
r2 = subprocess.run(["npx", "--no-install", "esbuild", os.path.join(EX, "main.js"), "--bundle",
                     "--minify-syntax"], cwd=os.path.join(ROOT, "tests"), capture_output=True, text=True)
if r2.returncode == 0:
    esbuild_out = re.sub(r"^\s*// .*\n", "", r2.stdout, flags=re.M)
listfile = os.path.join(tmp, "list.txt")
with open(listfile, "w") as fh:
    fh.write(os.path.join(EX, "loop.js") + "\n")
r3 = subprocess.run([JSPARSE, "check", listfile], capture_output=True, text=True)
loop_check = (r3.stdout + r3.stderr).replace(EX + "/", "")
sources = {n: read(os.path.join(EX, n)) for n in ("main.js", "greet.js", "math.js", "loop.js")}


def span(file, needle, nth=0):
    """[start, end) of the nth occurrence of needle in an example file (or the output)."""
    text = out_js if file == "out.js" else sources[file]
    at = -1
    for _ in range(nth + 1):
        at = text.find(needle, at + 1)
        if at < 0:
            fail("example %s has no %r (occurrence %d)" % (file, needle, nth))
    return [at, at + len(needle)]


def R(path, needle, after=0):
    """A rule step: its file, line and text, found by a needle that must be there."""
    ln = find_line(path, needle, after)
    return {"file": path, "line": ln, "text": files[path]["lines"][ln - 1].strip(),
            "decl": enclosing(path, ln)}


LF = "src/bundle/link.facts"
AA = "src/bundle/analysis.attrs"
MR = "src/bundle/minify.rewrite"
EA = "src/bundle/emit.attrs"
CR = "src/bundle/constants.rules"
JV = "src/bundle/jsvalue.rules"

# Each output statement and why it is there, traced by hand through the real rules.
included_main = {"fact": "included(main.js)", "rule": R(LF, "included(M) :- entry(M) ;"),
                 "from": [{"fact": "entry(main.js)", "given": "the build's entry point"}]}
log_live = {"fact": "live(console.log(…))", "rule": R(LF, "live(P) :- included(M), part-of(P, M), effect(P) ;"),
            "from": [included_main,
                     {"fact": "part-of(console.log(…), main.js)", "given": "a statement of main.js",
                      "rule": R(AA, "link.fact-part-of(")},
                     {"fact": "effect(console.log(…))", "given": "a call of console.log may do anything",
                      "rule": R(AA, "link.fact-effect(part) for p in [part] if directive or not sm.pure")}]}


def uses_chain(local, name, mod, sym):
    return {"fact": "uses(console.log(…), %s@%s)" % (name, mod),
            "rule": R(LF, "uses(P, T) :- via(P, D, N), resolved(D, N, T), !ambiguous(D, N) ;"),
            "from": [{"fact": "via(console.log(…), %s, \"%s\")" % (mod, name),
                      "rule": R(LF, "via(P, D, N) :- import-of(S, D, N), mentions(P, S) ;"),
                      "from": [{"fact": "import-of(%s@main.js, %s, \"%s\")" % (name, mod, name),
                                "given": "import { %s } from \"./%s\"" % (name, mod),
                                "rule": R(AA, "link.fact-import-of(")},
                               {"fact": "mentions(console.log(…), %s@main.js)" % name,
                                "given": "the call reads %s" % name, "rule": R(AA, "link.fact-mentions(")}]},
                     {"fact": "resolved(%s, \"%s\", %s)" % (mod, name, sym),
                      "rule": R(LF, "resolved(M, N, S) :- local-export(M, N, S) ;"),
                      "from": [{"fact": "local-export(%s, \"%s\", %s)" % (mod, name, sym),
                                "given": "export %s" % name, "rule": R(AA, "link.fact-local-export(")}]},
                     {"fact": "!ambiguous(%s, \"%s\")" % (mod, name), "given": "no two `export *` give it"}]}


def decl_live(name, mod, what):
    return {"fact": "live(%s)" % what,
            "rule": R(LF, "live(P) :- live(Q), uses(Q, S), declares(P, S) ;"),
            "from": [log_live, uses_chain(name, name, mod, name + "@" + mod),
                     {"fact": "declares(%s, %s@%s)" % (what, name, mod), "given": "the statement declares " + name,
                      "rule": R(AA, "link.fact-declares(")}]}


trace = {
    "command": "esb main.js --bundle --minify-syntax --sourcemap",
    "output": out_js.split("\n//# sourceMappingURL")[0],
    "esbuild": esbuild_out,
    "map": {"sources": [os.path.basename(s) for s in out_map["sources"]], "mappings": out_map["mappings"]},
    "analysis": analysis,
    "sources": {k: sources[k] for k in ("main.js", "greet.js", "math.js")},
    "pieces": [
        {"id": "greet", "label": "function greet", "out": span("out.js", 'function greet(name){return name!==""?"hello, "+name:"hello"}'),
         "src": {"file": "greet.js", "span": span("greet.js", 'export function greet(name) {\n  return !(name === "") ? "hello, " + name : "hello";\n}')},
         "question": "Why is greet kept?",
         "summary": "main.js calls greet, and that call is kept because it has an effect. Linking follows the import to greet.js and keeps the declaration it names.",
         "why": decl_live("greet", "greet.js", "function greet"),
         "rewrites": [
             {"before": '!(name === "")', "after": '!(name === "")', "rule": R(MR, "rule unparen"), "note": "Paren(x) => x: the printer adds back any parentheses precedence needs"},
             {"before": '!(name === "")', "after": 'name !== ""', "rule": R(MR, "rule not-seq"), "note": "Not(StrictEq(a, b)) => StrictNe(a, b)"},
             {"before": "export function greet", "after": "function greet", "rule": R(EA, "ExportLexical(d) | ExportFunction(d) | ExportClass(d) => some(rewritten(d))"), "note": "a bundle has no exports of its own modules"}]},
        {"id": "clamp", "label": "var clamp", "out": span("out.js", "var clamp=(x,lo,hi)=>x<lo?lo:x>hi?hi:x"),
         "src": {"file": "math.js", "span": span("math.js", "export const clamp = (x, lo, hi) => x < lo ? lo : x > hi ? hi : x;")},
         "question": "Why is clamp kept?",
         "summary": "This works the same way as greet: the kept console.log call uses clamp through its import.",
         "why": decl_live("clamp", "math.js", "const clamp"),
         "rewrites": []},
        {"id": "log", "label": "console.log(…)", "out": span("out.js", 'console.log(greet("world"),clamp(12,0,10))'),
         "src": {"file": "main.js", "span": span("main.js", 'console.log(greet("world"), clamp(12, 0, 10));')},
         "question": "Why is the call kept?",
         "summary": "It is a statement of the entry module, and calling console.log has an effect.",
         "why": log_live, "rewrites": []},
        {"id": "iife", "label": "(()=>{ … })()", "out": [0, 6],
         "src": None, "question": "Where does the wrapper come from?",
         "summary": "The output format, not any module. An IIFE keeps the bundle's names out of the page's global scope.",
         "why": None, "rewrites": []},
    ],
    "dropped": [
        {"id": "unused", "label": "const unused", "src": {"file": "math.js", "span": span("math.js", "export const unused = 1 + 2;")},
         "question": "Where did unused go?", "compare": True,
         "summary": "Before tree shaking, the constants at the start of math.js are folded as esbuild folds them while parsing. clamp holds an arrow, which nothing can read too soon, so that start goes on to unused. There every operator folds, and 1 + 2 becomes 3. A literal has no effect, so no rule keeps the statement. While this prototype was being built, the statement was still in the output, because the start stopped at clamp and nothing folded 1 + 2 in time. Following esbuild's rules fixed it.",
         "why_title": "Folded before tree shaking",
         "why": {"fact": "const unused = 3", "rule": R(CR, "some(s), some(v) if constant and jv.const-value?(v) =>"),
                 "from": [{"fact": "the start of math.js reaches unused", "rule": R(JV, "Regex(_) | FuncExpr(...) | GenExpr(...)"),
                           "given": "clamp holds an arrow, which cannot be read too soon"},
                          {"fact": "1 + 2 folds to 3", "rule": R(JV, "Add(l, r) => first a in value-of(l, f)"),
                           "given": "at the start of a list, every operator folds"},
                          {"fact": "3 is a constant esbuild writes in", "rule": R(JV, "fn const-value?(v: Value) -> Bool"),
                           "given": "an integer"}]},
         "candidates": [
             {"rule": R(LF, "live(P) :- included(M), part-of(P, M), effect(P) ;"), "missing": "effect(const unused): 3 has no effect"},
             {"rule": R(LF, "live(P) :- live(Q), uses(Q, S), declares(P, S) ;"), "missing": "uses(Q, unused@math.js) for a live Q: nothing imports unused"}]},
        {"id": "shout", "label": "function shout", "src": {"file": "greet.js", "span": span("greet.js", "export function shout(name) { return greet(name).toUpperCase(); }")},
         "question": "Where did shout go?",
         "summary": "No rule derives live(function shout). It has no effect (declaring a function runs nothing), and no live statement uses it. Each rule that could keep it is missing a premise:",
         "candidates": [
             {"rule": R(LF, "live(P) :- included(M), part-of(P, M), effect(P) ;"), "missing": "effect(function shout)"},
             {"rule": R(LF, "live(P) :- live(Q), uses(Q, S), declares(P, S) ;"), "missing": "uses(Q, shout@greet.js) for a live Q"},
             {"rule": R(LF, "live(P) :- live(Q), mentions(Q, S), declares(P, S) ;"), "missing": "mentions(Q, shout@greet.js) for a live Q"},
             {"rule": R(LF, "live(P) :- keep-exports(M), resolved(M, N, S), declares(P, S) ;"), "missing": "keep-exports(greet.js): only an entry's exports are kept, and only for some formats"}]},
        {"id": "imports", "label": "import statements", "src": {"file": "main.js", "span": span("main.js", 'import { greet } from "./greet.js";\nimport { clamp } from "./math.js";')},
         "question": "Where did the imports go?",
         "summary": "Linking turned each import into a direct reference to the declaration it names, so main.js's greet is greet.js's greet. With nothing left to bind, the import statements print nothing.",
         "candidates": []}],
}

# Scopes: which directive placed each binding, and where each read lands.
SJ = "src/bundle/js.scopes"
SL = "src/tools/letlang.scopes"
greet_src = sources["greet.js"]
letlang_src = "let x = 1 in\n  let x = x + 1 in\n    x"
block_src = "{ let y = 1; let y = y + 1; y }"


def occ(text, needle, nth):
    at = -1
    for _ in range(nth + 1):
        at = text.find(needle, at + 1)
        if at < 0:
            fail("scope sample has no %r (occurrence %d)" % (needle, nth))
    return [at, at + len(needle)]


scopes = {"samples": [
    {"id": "js", "title": "greet.js, by bundle.js's scopes", "lang": "JavaScript", "text": greet_src, "file": SJ,
     "regions": [{"span": [0, len(greet_src)], "kind": "program (function)", "rule": R(SJ, "program function ;")},
                 {"span": occ(greet_src, "(name) {\n  return", 0)[:1] + [occ(greet_src, "}", 0)[1]], "kind": "function greet", "rule": R(SJ, "scope function")},
                 {"span": occ(greet_src, "(name) { return greet", 0)[:1] + [len(greet_src) - 1], "kind": "function shout", "rule": R(SJ, "scope function")}],
     "binds": [{"id": "greet", "span": occ(greet_src, "greet", 0), "scope": 0, "rule": R(SJ, "name FuncDecl GenDecl AsyncFuncDecl AsyncGenDecl in function ;"), "outside": R(SJ, "outside name of FuncDecl")},
               {"id": "name1", "span": occ(greet_src, "name", 0), "scope": 1, "rule": R(SJ, "names VarDecl VarInit VarLeft VarLeftInit ExportVar Params in function ;")},
               {"id": "shout", "span": occ(greet_src, "shout", 0), "scope": 0, "rule": R(SJ, "name FuncDecl GenDecl AsyncFuncDecl AsyncGenDecl in function ;")},
               {"id": "name2", "span": occ(greet_src, "name", 3), "scope": 2, "rule": R(SJ, "names VarDecl VarInit VarLeft VarLeftInit ExportVar Params in function ;")}],
     "refs": [{"span": occ(greet_src, "name", 1), "to": "name1"}, {"span": occ(greet_src, "name", 2), "to": "name1"},
              {"span": occ(greet_src, "greet", 1), "to": "greet"}, {"span": occ(greet_src, "name", 4), "to": "name2"}]},
    {"id": "ml", "title": "ML's let … in, by tools.letlang's scopes", "lang": "letlang", "text": letlang_src, "file": SL,
     "regions": [{"span": [0, len(letlang_src)], "kind": "program (block)", "rule": R(SL, "program block ;")},
                 {"span": [0, len(letlang_src)], "kind": "let x = 1", "rule": R(SL, "scope let Let LetStmt ;")},
                 {"span": occ(letlang_src, "let x = x", 0)[:1] + [len(letlang_src)], "kind": "let x = x + 1", "rule": R(SL, "scope let Let LetStmt ;")}],
     "binds": [{"id": "x1", "span": occ(letlang_src, "x", 0), "scope": 1, "rule": R(SL, "name Let LetStmt in own ;")},
               {"id": "x2", "span": occ(letlang_src, "x", 1), "scope": 2, "rule": R(SL, "name Let LetStmt in own ;")}],
     "refs": [{"span": occ(letlang_src, "x", 2), "to": "x1", "why": R(SL, "outside init of Let LetStmt ;")},
              {"span": occ(letlang_src, "x", 3), "to": "x2"}]},
    {"id": "rust", "title": "Rust-style shadowing in a block, by the same file", "lang": "letlang", "text": block_src, "file": SL,
     "regions": [{"span": [0, len(block_src)], "kind": "block", "rule": R(SL, "scope block Block ;")},
                 {"span": [occ(block_src, "let y = 1", 0)[0], len(block_src) - 1], "kind": "let y = 1; and what follows", "rule": R(SL, "sequential LetStmt ;")},
                 {"span": [occ(block_src, "let y = y", 0)[0], len(block_src) - 1], "kind": "let y = y + 1; and what follows", "rule": R(SL, "sequential LetStmt ;")}],
     "binds": [{"id": "y1", "span": occ(block_src, "y", 0), "scope": 1, "rule": R(SL, "name Let LetStmt in own ;")},
               {"id": "y2", "span": occ(block_src, "y", 1), "scope": 2, "rule": R(SL, "name Let LetStmt in own ;")}],
     "refs": [{"span": occ(block_src, "y", 2), "to": "y1", "why": R(SL, "outside init of Let LetStmt ;")},
              {"span": occ(block_src, "y", 3), "to": "y2"}]}]}

# Attributes: in-loop flowing down loop.js's tree, as early.attrs gives it.
EAR = "src/bundle/early.attrs"
fn_on = R(EAR, "body.in-loop = false", find_line(EAR, "params.allow-super-call = f.super-call"))
attrs = {
    "file": EAR, "source": sources["loop.js"], "check": loop_check.strip(),
    "decl": R(EAR, "inh in-loop: Bool = false"),
    "rule": R(EAR, 'problem += rule(not in-loop, "continue is only valid in a loop", n)'),
    "tree": {"kind": "Program", "val": False, "eq": R(EAR, "inh in-loop: Bool = false"), "kids": [
        {"kind": "While", "val": False, "text": "while (ready) …", "kids": [
            {"kind": "Block", "field": "body", "val": True, "eq": R(EAR, "body.in-loop = true", find_line(EAR, "on While(_, body) {")), "kids": [
                {"kind": "If", "val": True, "text": "if (skip) continue;", "kids": [
                    {"kind": "Continue", "val": True, "ok": True, "span": occ(sources["loop.js"], "continue", 0)}]},
                {"kind": "ExprStmt", "val": True, "text": "step();", "kids": []}]}]},
        {"kind": "FuncDecl", "val": False, "text": "function later() …", "kids": [
            {"kind": "Block", "field": "body", "val": False, "eq": fn_on, "kids": [
                {"kind": "Continue", "val": False, "ok": False, "span": occ(sources["loop.js"], "continue", 1)}]}]}]},
}
# the `on` block that holds the function equation
j = fn_on["line"]
while not files[EAR]["lines"][j - 1].startswith("on "):
    j -= 1
attrs["on_fn"] = {"file": EAR, "line": j, "text": files[EAR]["lines"][j - 1].strip()}

# ---------------------------------------------------------------- the page

summary = {}
for p, f in files.items():
    summary.setdefault(f["lang"], {"files": 0, "lines": 0})
    summary[f["lang"]]["files"] += 1
    summary[f["lang"]]["lines"] += sum(1 for l in f["lines"] if l.strip() and not l.lstrip().startswith("#"))

data = {
    "files": {p: {"lang": f["lang"], "module": f["module"], "text": f["text"]} for p, f in files.items()},
    "decls": decls, "refs": {str(k): v for k, v in refs.items()},
    "facts": facts_rules, "grammars": grammars, "rewrites": rewrites, "pipeline": pipeline,
    "trace": trace, "scopes": scopes, "attrs": attrs, "summary": summary,
    "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
}
blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
page = read(os.path.join(HERE, "app.html")).replace("/*DATA*/null", blob)
os.makedirs(OUT, exist_ok=True)
dest = os.path.join(OUT, "tower-explorer.html")
with open(dest, "w", encoding="utf-8") as fh:
    fh.write(page)
# The artifact's host adds the document skeleton; a local copy needs its own to read as UTF-8.
with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as fh:
    fh.write('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"></head><body style="margin:0">' + page + "</body></html>")
print("%s  (%d KB; %d declarations, %d with references)" % (rel(dest), len(page) // 1024, len(decls), len(refs)))
