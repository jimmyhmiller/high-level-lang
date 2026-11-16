"""The explorer's catalog of the tower: every language file under src/, what it declares, what
refers to what across languages, the grammars as railroad trees, Datalog rules, rewrite rules as
trees and the pipeline; and for each language, the grammar that defines it, the compiler that
compiles it, and where in src/ each of its productions is used.

Read from the files as they are, each time it is asked (`build(root)`), so an edit shows at once.
"""
import json, os, re


class CatalogError(Exception):
    pass


def fail(msg):
    raise CatalogError(msg)


def build(root):
    ROOT = os.path.abspath(root)
    SRC = os.path.join(ROOT, "src")

    def read(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    def rel(path):
        return os.path.relpath(path, ROOT)

    LANG_EXT = {".rules": "rules", ".attrs": "attrs", ".facts": "facts", ".rewrite": "rewrite",
                ".syntax": "syntax", ".scopes": "scopes", ".pipeline": "pipeline", ".bundler": "bundler"}




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




    # ---------------------------------------------------------------- the languages themselves

    # Each language: the grammar that defines it, the compiler that turns it into Coil, and a note.
    LANGUAGES = [
        ("syntax", "Grammars", None, "compiler/hl/syntax.coil",
         "The bootstrap. A .syntax grammar defines every other language, and is itself read by the parser hand-written in compiler/hl/syntax.coil."),
        ("rules", "Rules", "src/languages/rules.syntax", "compiler/hl/rules.coil",
         "A typed language over a grammar's nodes: pattern matching, comprehensions, `where`, memos, settings."),
        ("attrs", "Attribute grammars", "src/languages/rules.syntax", "compiler/hl/rules.coil",
         "Read by the rules grammar (`attrs … over …`) and compiled by the rules compiler into one traversal."),
        ("facts", "Datalog", "src/languages/facts.syntax", "compiler/hl/facts.coil",
         "Relations and rules, compiled to nested loops with indexes; each derived row can be explained (`why-REL`)."),
        ("rewrite", "Rewrite rules", "src/languages/rewrite.syntax", "compiler/hl/rewrite.coil",
         "Patterns over a grammar's nodes and what they become, compiled to a bottom-up driver run to a fixpoint."),
        ("scopes", "Scopes", "src/languages/scopes.syntax", "compiler/hl/scopes.coil",
         "Which nodes open scopes and where names land, checked against the grammar's node names."),
        ("pipeline", "Pipeline", "src/languages/pipeline.syntax", "compiler/hl/pipeline.coil",
         "Stages, plans, mechanisms and strategies: how the work is divided and how answers are kept."),
        ("bundler", "Build specs", "src/bundle/spec.syntax", "src/bundle/spec.rules",
         "Data, not a language with a compiler: read by spec.syntax, each setting given meaning by spec.rules."),
    ]
    for g in sorted({l[2] for l in LANGUAGES if l[2]}):
        if g in files and g not in grammars:
            grammars[g] = grammar_of(g)

    def leading_terms(node):
        """The literal words an alternative can start with: what a use of it begins with."""
        t = node.get("t")
        if t == "term":
            return [node["s"]] if re.match(r"^[a-z][\w\-]*$", node["s"]) else []
        if t == "seq":
            for it in node["items"]:
                if it.get("t") in ("flag", "pred"):
                    continue
                return leading_terms(it)
            return []
        if t == "alt":
            return [w for o in node["opts"] for w in leading_terms(o)]
        if t in ("opt", "rep"):
            return leading_terms(node["x"])
        return []

    languages = []
    for key, name, grammar, compiler, note in LANGUAGES:
        lang_files = sorted(p for p, f in files.items() if f["lang"] == key)
        productions = []
        for prod in grammars.get(grammar, []) if grammar else []:
            # Only a grammar's rules are forms a writer uses; its tokens and fragments are spelling.
            if prod["kind"] not in ("rule", "suffix", "postfix", "infix") or "hidden" in prod["mods"]:
                continue
            words = sorted(set(leading_terms(prod["body"]))) if "body" in prod else []
            uses = []
            if words:
                pat = re.compile(r"^\s*(?:pub\s+|boxed\s+|memo\s+|everywhere\s+)*(" + "|".join(re.escape(w) for w in words) + r")\b")
                for path in lang_files:
                    for i, line in enumerate(files[path]["lines"]):
                        if pat.match(line):
                            uses.append({"file": path, "line": i + 1, "text": line.strip()[:160]})
            productions.append({"name": prod["name"], "line": prod["line"], "words": words,
                                "count": len(uses), "uses": uses[:60]})
        languages.append({"key": key, "name": name, "grammar": grammar, "compiler": compiler, "note": note,
                          "files": lang_files,
                          "lines": sum(1 for p in lang_files for l in files[p]["lines"] if l.strip() and not l.lstrip().startswith("#")),
                          "productions": productions})


    # ---------------------------------------------------------------- the code's structure

    # What each file names its imports (`use bundle.js as js`), and the files they are.
    file_of_module = {}
    for p, f in files.items():
        file_of_module.setdefault(f["module"], p)
    aliases = {}
    deps = []
    for p, f in files.items():
        al = {}
        for i, line in enumerate(f["lines"]):
            m = re.match(r"\s*use\s+([\w.]+)(?:\s+as\s+(\w+))?", line)
            if m:
                al[m.group(2) or m.group(1).split(".")[-1]] = m.group(1)
                target = file_of_module.get(m.group(1))
                if target and target != p:
                    deps.append({"from": p, "to": target, "line": i + 1})
            m = re.match(r"\s*(?:attrs|rules|rewrite|scopes)\s+[\w.]+\s+over\s+([\w.]+)", line)
            if m and file_of_module.get(m.group(1)) and file_of_module[m.group(1)] != p:
                deps.append({"from": p, "to": file_of_module[m.group(1)], "line": i + 1, "over": True})
            m = re.match(r"\s*host\s+([\w.]+)", line)
            if m and f["lang"] == "rewrite" and file_of_module.get(m.group(1)):
                deps.append({"from": p, "to": file_of_module[m.group(1)], "line": i + 1})
        if f["lang"] == "rewrite":
            m = re.search(r"^rewrite\s+([\w.]+)", f["text"], re.M)
            if m and file_of_module.get(m.group(1)):
                deps.append({"from": p, "to": file_of_module[m.group(1)], "line": f["text"][:m.start()].count("\n") + 1, "over": True})
        aliases[p] = al
    # Who uses whom, between declarations: a call, a fact asserted, a rule reading or deriving a
    # relation, a kept function, a node kind matched.
    edges = []
    for target, groups in refs.items():
        for label, lst in groups.items():
            for r in lst:
                if r["in"] is not None and r["in"] != target:
                    edges.append([r["in"], target, label])

    return {"files": {p: {"lang": f["lang"], "module": f["module"], "text": f["text"]} for p, f in files.items()},
            "decls": decls, "refs": {str(k): v for k, v in refs.items()},
            "facts": facts_rules, "grammars": grammars, "rewrites": rewrites, "pipeline": pipeline,
            "kinds": sorted(kinds), "languages": languages,
            "modules": {p: f["module"] for p, f in files.items()}, "aliases": aliases, "deps": deps, "edges": edges}
