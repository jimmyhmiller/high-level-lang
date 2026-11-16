"use strict";
// Code as structure: a file of the tower drawn from the tree its own grammar reads (out/bin/hltree,
// the compilers' parsers), so a rule is read by its shape. Small expressions stay text (linked, as
// in the code view); what has shape is drawn: a function's signature, a match as a table of
// patterns and results, `where` as equations, a comprehension as the clauses it runs through, a
// record made or updated as its fields, a pattern as the nodes it matches, an attribute grammar's
// equations on the children they give to, a Datalog rule's atoms joined by colored variables.

// Positions are bytes; a file with any non-ASCII text needs them turned into characters.
function slicer(text) {
  const bytes = new TextEncoder().encode(text);
  if (bytes.length === text.length) return (lo, hi) => text.slice(lo, hi);
  const at = new Int32Array(bytes.length + 1); let ci = 0, bi = 0;
  for (const ch of text) {
    const c = ch.codePointAt(0), n = c < 0x80 ? 1 : c < 0x800 ? 2 : c < 0x10000 ? 3 : 4;
    for (let k = 0; k < n; k++) at[bi + k] = ci; bi += n; ci += ch.length;
  }
  at[bytes.length] = text.length;
  return (lo, hi) => text.slice(at[lo], at[hi]);
}

const kidsOf = n => n.c || [];
const isNone = n => !n || n.k === "None";

function Projector(file) {
  const text = CAT.files[file].text, sl = slicer(text);
  const src = n => sl(n.lo, n.hi);
  const oneLine = s => s.replace(/\s*\n\s*/g, " ");
  const inline = n => `<span class="ix">${codeLine(oneLine(src(n)), file)}</span>`;
  const small = n => { const s = src(n); return s.length <= 58 && !s.includes("\n"); };
  const BIG = new Set(["Match", "MatchN", "WhereE", "Comp", "CompSpread", "MapComp", "If", "IfLet", "Block", "First", "Any", "All", "Last", "Count", "Sum", "Fold", "Scan", "WithCtx"]);
  const hasBig = n => BIG.has(n.k) || kidsOf(n).some(hasBig);

  // ---------------------------------------------------------------- expressions
  function expr(n) {
    if (!n || isNone(n)) return "";
    if (small(n) && !hasBig(n)) return inline(n);
    const k = kidsOf(n);
    switch (n.k) {
      case "WhereE": return `<div class="s-where">${expr(k[0])}<div class="s-eqs"><span class="s-kw">where</span>${kidsOf(k[1]).map(i => `<div class="s-eq"><span class="s-name">${esc(kidsOf(i)[0].t)}</span><span class="s-op">=</span><div>${expr(kidsOf(i)[1])}</div></div>`).join("")}</div></div>`;
      case "Match": return matchTable([k[0]], kidsOf(k[1]), arm => [kidsOf(arm)[0]], arm => kidsOf(arm)[1], arm => kidsOf(arm)[2]);
      case "MatchN": return matchTable([k[0], ...kidsOf(k[1])], kidsOf(k[2]), arm => armNPatterns(arm), arm => armNGuard(arm), arm => kidsOf(arm)[kidsOf(arm).length - 1]);
      case "Comp": case "CompSpread": return pipeline(n.k === "Comp" ? "list of" : "list of all of", kidsOf(k[1]), expr(k[0]));
      case "MapComp": return pipeline("map of", kidsOf(k[2]), `${expr(k[0])}<span class="s-op">:</span>${expr(k[1])}`);
      case "First": case "Any": case "All": case "Last": case "Count": case "Sum":
        return pipeline(n.k.toLowerCase(), [k[0], ...kidsOf(k[1])], expr(k[2]));
      case "Fold": case "Scan": return pipeline(`${n.k.toLowerCase()} <span class="s-name">${esc(k[0].t)}</span> = ${expr(k[1])}`, kidsOf(k[2]), expr(k[3]));
      case "If": return `<div class="s-if"><div class="s-row"><span class="s-kw">if</span>${expr(k[0])}</div><div class="s-branch"><span class="s-kw">then</span><div>${stmt(k[1])}</div></div>${isNone(k[2]) ? "" : `<div class="s-branch"><span class="s-kw">else</span><div>${stmt(k[2])}</div></div>`}</div>`;
      case "IfLet": return `<div class="s-if"><div class="s-row"><span class="s-kw">if let</span>${pattern(k[0])}<span class="s-op">=</span>${expr(k[1])}</div><div class="s-branch"><span class="s-kw">then</span><div>${stmt(k[2])}</div></div>${isNone(k[3]) ? "" : `<div class="s-branch"><span class="s-kw">else</span><div>${stmt(k[3])}</div></div>`}</div>`;
      case "Block": return block(n);
      case "Group": return expr(k[0]);
      case "Ctor": return fields(inline(k[0]), kidsOf(k[1]));
      case "WithE": return `<div class="s-rec"><div class="s-rech">${expr(k[0])}<span class="s-kw">with</span></div>${kidsOf(k[1]).map(f => `<div class="s-field"><span class="s-name">${esc(kidsOf(f)[0].t)}</span><div>${expr(kidsOf(f)[1])}</div></div>`).join("")}</div>`;
      case "Call": return kidsOf(k[1]).length ? fields(inline(k[0]), kidsOf(k[1]), true, k[0]) : inline(n);
      case "And": case "Or": case "Concat": case "Default": case "Add": {
        const parts = []; (function flat(x) { if (x.k === n.k) kidsOf(x).forEach(flat); else parts.push(x); })(n);
        const op = { And: "and", Or: "or", Concat: "++", Default: "??", Add: "+" }[n.k];
        return `<div class="s-chain">${parts.map((p, i) => `<div class="s-link">${i ? `<span class="s-op">${op}</span>` : `<span class="s-op"></span>`}<div>${expr(p)}</div></div>`).join("")}</div>`;
      }
      case "WithCtx": return `<div class="s-block"><div class="s-row"><span class="s-kw">with</span>${kidsOf(k[0]).map(b => `${inline(kidsOf(b)[0])}<span class="s-op">=</span>${expr(kidsOf(b)[1])}`).join(", ")}</div>${block(k[1])}</div>`;
      case "IsE": return `<div class="s-row">${expr(k[0])}<span class="s-kw">is</span>${pattern(k[1])}</div>`;
      case "Not": return `<div class="s-row"><span class="s-kw">not</span>${expr(k[0])}</div>`;
      case "SomeE": return `<div class="s-row"><span class="s-kw">some</span>${expr(k[0])}</div>`;
      case "ListLit": return `<div class="s-chain">${kidsOf(k[0]).map(a => `<div class="s-link"><span class="s-op">•</span><div>${expr(a)}</div></div>`).join("")}</div>`;
      default: return `<div class="s-raw">${codeLine(src(n).split("\n").map(l => l.trim()).join("\n"), file).replace(/\n/g, "<br>")}</div>`;
    }
  }
  // A record made, or a call, as its arguments: a name's on its own line.
  // A call's arguments in the order given are labelled with the parameters they are passed as, read
  // from the function's own signature (wherever it is declared), so `f(ds, i + 1, b, before, c)`
  // reads as what each value is for.
  function fields(head, args, call, callee) {
    const d = call && callee ? resolve(file, src(callee)) : null;
    const ps = d && d.params ? d.params : [];
    return `<div class="s-rec${call ? " call" : ""}"><div class="s-rech">${head}</div>${args.map((a, i) => a.k === "Named"
      ? `<div class="s-field"><span class="s-name">${esc(kidsOf(a)[0].t)}</span><div>${expr(kidsOf(a)[1])}</div></div>`
      : `<div class="s-field"><span class="s-name${ps[i] ? " s-param-of" : ""}">${esc(ps[i] || "")}</span><div>${a.k === "Spread" ? expr(kidsOf(a)[0]) + "<span class='s-op'>…</span>" : expr(a)}</div></div>`).join("")}</div>`;
  }
  function armNPatterns(arm) { const ks = kidsOf(arm); return [ks[0], ...(ks[1] && ks[1].k === "List" ? kidsOf(ks[1]) : [])]; }
  function armNGuard(arm) { const ks = kidsOf(arm); return ks.length > 3 ? ks[2] : null; }
  function matchTable(subjects, arms, pats, guard, body) {
    return `<div class="s-match"><div class="s-mhead"><span class="s-kw">match</span>${subjects.map(expr).join('<span class="s-op">,</span>')}</div>
      <table class="s-arms"><tbody>${arms.map(a => { const g = guard(a), b = body(a);
        const pat = `<td class="s-pat">${pats(a).map(pattern).join('<span class="s-op">,</span>')}${g && !isNone(g) ? `<div class="s-guard"><span class="s-kw">if</span>${expr(g)}</div>` : ""}</td>`;
        // A result with a shape of its own goes under its pattern, the width of the table.
        return hasBig(b) ? `<tr class="s-tall">${pat}<td class="s-arrow">⇓</td><td></td></tr><tr class="s-under"><td colspan="3">${stmtOrExpr(b)}</td></tr>`
          : `<tr>${pat}<td class="s-arrow">⇒</td><td>${stmtOrExpr(b)}</td></tr>`; }).join("")}</tbody></table></div>`;
  }
  function pipeline(label, clauses, result) {
    return `<div class="s-pipe"><span class="s-kw s-q">${label}</span>${clauses.map(clause).join('<span class="s-flow">→</span>')}<span class="s-flow">⇒</span><div class="s-yield">${result}</div></div>`;
  }
  function clause(c) {
    const k = kidsOf(c);
    switch (c.k) {
      case "InHead": return `<span class="s-clause"><span class="s-kw">for</span><span class="s-name">${esc(k[0].t)}</span><span class="s-kw">in</span>${expr(k[1])}</span>`;
      case "RangeHead": return `<span class="s-clause"><span class="s-kw">for</span><span class="s-name">${esc(k[0].t)}</span><span class="s-kw">in</span>${expr(k[1])}<span class="s-op">..</span>${expr(k[2])}</span>`;
      case "FromHead": return `<span class="s-clause"><span class="s-kw">for</span><span class="s-name">${esc(k[0].t)}</span><span class="s-kw">from</span>${expr(k[1])}</span>`;
      case "PatHead": return `<span class="s-clause"><span class="s-kw">for</span>${pattern(k[0])}<span class="s-kw">in</span>${expr(k[1])}</span>`;
      case "QueryHead": return `<span class="s-clause"><span class="s-kw">for</span>${expr(k[0])}</span>`;
      case "IfClause": return `<span class="s-clause test"><span class="s-kw">if</span>${expr(k[0])}</span>`;
      case "LetClause": return `<span class="s-clause"><span class="s-kw">if let</span>${pattern(k[0])}<span class="s-op">=</span>${expr(k[1])}</span>`;
      case "WhileClause": return `<span class="s-clause test"><span class="s-kw">while</span>${expr(k[0])}</span>`;
      case "DistinctClause": return `<span class="s-clause test"><span class="s-kw">distinct</span>${expr(k[0])}</span>`;
      default: return `<span class="s-clause">${expr(c)}</span>`;
    }
  }
  // ---------------------------------------------------------------- statements
  function block(b) { return `<div class="s-block">${kidsOf(kidsOf(b)[0]).map(s => `<div class="s-stmt">${stmt(s)}</div>`).join("")}</div>`; }
  function stmtOrExpr(n) { return ["Let", "Var", "For", "While", "Assign", "Append", "Extend", "Print", "Assert"].includes(n.k) ? stmt(n) : expr(n); }
  function stmt(s) {
    if (!s || isNone(s)) return "";
    const k = kidsOf(s);
    switch (s.k) {
      case "Let": case "Var": return `<div class="s-row"><span class="s-kw">${s.k === "Let" ? "let" : "var"}</span><span class="s-name">${esc(k[0].t)}</span>${isNone(k[1]) ? "" : `<span class="s-op">:</span>${inline(k[1])}`}<span class="s-op">=</span><div>${expr(k[2])}</div></div>`;
      case "For": return `<div class="s-loop"><div class="s-row">${clause(k[0])}</div>${block(k[1])}</div>`;
      case "While": return `<div class="s-loop"><div class="s-row"><span class="s-kw">while</span>${expr(k[0])}</div>${block(k[1])}</div>`;
      case "Assign": case "Append": case "Extend": return `<div class="s-row">${expr(k[0])}<span class="s-op">${{ Assign: "=", Append: "+=", Extend: "++=" }[s.k]}</span><div>${expr(k[1])}</div></div>`;
      default: return expr(s);
    }
  }
  // ---------------------------------------------------------------- patterns: the nodes they match
  function pattern(p) {
    if (!p || isNone(p)) return "";
    const k = kidsOf(p);
    switch (p.k) {
      case "PNode": case "PNodeQ": { const name = p.k === "PNode" ? k[0] : k[1]; const args = kidsOf(p.k === "PNode" ? k[1] : k[2]);
        const d = resolve(file, name.t || ""); const label = d ? `<a class="sym" data-d="${d.id}">${esc(name.t)}</a>` : esc(name.t || src(name));
        return `<span class="p-node"><span class="p-kind">${label}</span>${args.length ? `<span class="p-kids">${args.map(pattern).join("")}</span>` : ""}</span>`; }
      case "PAny": return `<span class="p-any">_</span>`;
      case "Name": return `<span class="p-var">${esc(p.t)}</span>`;
      case "Rest": return `<span class="p-var">${esc(p.t)}</span>`;
      case "PAs": return `<span class="p-as">${pattern(k[0])}<span class="s-kw">as</span><span class="p-var">${esc(k[1].t || "")}</span></span>`;
      // `a | b | c` reads as the first and a list of the rest.
      case "POr": return `<span class="p-or">${[k[0], ...(k[1] && k[1].k === "List" ? kidsOf(k[1]) : k.slice(1))].map(pattern).map(x => `<span class="p-alt">${x}</span>`).join("")}</span>`;
      default: return `<span class="p-lit">${codeLine(oneLine(src(p)), file)}</span>`;
    }
  }
  // ---------------------------------------------------------------- declarations
  const declAt = new Map(declsIn(file).map(d => [d.line, d]));
  const breaks = []; { const b = new TextEncoder().encode(text); for (let i = 0; i < b.length; i++) if (b[i] === 10) breaks.push(i); }
  const lineOf = n => { let lo = 0, hi = breaks.length; while (lo < hi) { const m = (lo + hi) >> 1; if (breaks[m] < n.lo) lo = m + 1; else hi = m; } return lo + 1; };
  function card(n, kind, name, head, body) {
    const line = lineOf(n), d = declAt.get(line) || CAT.decls.find(x => x.file === file && x.line === line);
    return `<section class="s-card" id="D${line}" data-l="${line}"><header><span class="tag lc-${langOf(file)}">${esc(kind)}</span><span class="s-dname">${esc(name)}</span>${head || ""}
      <span class="s-tools">${d ? `<a class="s-focus" href="#focus/${d.id}" title="what uses it, and what it uses">◎</a>` : ""}<a class="s-line" href="#code/${enc(file + ":" + line)}/text">${line}</a></span></header>
      ${d && d.doc ? `<p class="s-doc">${esc(d.doc)}</p>` : ""}${body ? `<div class="s-body">${body}</div>` : ""}</section>`;
  }
  const typ = t => isNone(t) ? "" : `<span class="s-type">${inline(t)}</span>`;
  const params = ps => `<span class="s-params">${kidsOf(ps).map(p => `<span class="s-param"><span class="s-name">${esc(kidsOf(p)[0].t)}</span>${typ(kidsOf(p)[1])}</span>`).join("")}</span>`;
  function decl(n) {
    const k = kidsOf(n);
    switch (n.k) {
      case "Fn": case "MemoFn": case "EverywhereFn":
        return card(n, { Fn: "fn", MemoFn: "memo fn", EverywhereFn: "everywhere fn" }[n.k], k[0].t, `${params(k[1])}${isNone(k[2]) ? "" : `<span class="s-op">→</span>${typ(k[2])}`}`, stmtOrExpr(k[3]));
      case "Record": case "BoxedRecord": case "FRecord":
        return card(n, n.k === "BoxedRecord" ? "boxed record" : "record", k[0].t, "", `<div class="s-rec">${kidsOf(k[1]).map(f => `<div class="s-field"><span class="s-name">${esc(kidsOf(f)[0].t)}</span><div>${typ(kidsOf(f)[1])}</div></div>`).join("")}</div>`);
      case "Enum": return card(n, "enum", k[0].t, "", `<div class="s-row">${kidsOf(k[1]).map(v => `<span class="p-node"><span class="p-kind">${esc(v.t)}</span></span>`).join("")}</div>`);
      case "Setting": case "Const": case "Context": case "State": case "TaskState": case "Inh": case "Given": case "Input": case "Sized": case "Collect":
        return card(n, n.k.toLowerCase(), k[0].t, `<span class="s-op">:</span>${typ(k[1])}`, k[2] && !isNone(k[2]) ? `<div class="s-row"><span class="s-op">=</span><div>${expr(k[2])}</div></div>` : "");
      case "On": return onCard(n);
      case "Rewrite": return card(n, "rewrite", "", `<span class="s-row">${pattern(k[0])}</span>`, `${isNone(k[1]) ? "" : `<div class="s-guard"><span class="s-kw">if</span>${expr(k[1])}</div>`}<div class="s-row"><span class="s-op">⇒</span><div>${expr(k[2])}</div></div>`);
      case "Foreign": return card(n, "foreign", k[0].t || src(k[0]), `<span class="s-kw">as</span><span class="s-name">${esc(k[1].t)}</span>`, `<div class="s-raw">${kidsOf(k[2]).map(i => codeLine(oneLine(src(i)), file)).join("<br>")}</div>`);
      default: return card(n, n.k.toLowerCase(), "", `<span class="ix">${codeLine(oneLine(src(n)).slice(0, 160), file)}</span>`, "");
    }
  }
  // `on Pat { child.attr = e … }`: the pattern, and each child's equations beside its name.
  function onCard(n) {
    const k = kidsOf(n), stmts = kidsOf(kidsOf(k[2])[0]);
    const byTarget = new Map(), other = [];
    for (const s of stmts) {
      if (s.k === "Assign") { const t = src(kidsOf(s)[0]); const dot = t.indexOf("."); if (dot > 0) { const who = t.slice(0, dot); if (!byTarget.has(who)) byTarget.set(who, []); byTarget.get(who).push([t.slice(dot + 1), kidsOf(s)[1]]); continue; } }
      other.push(s);
    }
    const eqs = [...byTarget.entries()].map(([who, xs]) => `<div class="s-attrs"><span class="p-var">${esc(who)}</span><div>${xs.map(([a, e]) => `<div class="s-row"><span class="s-attr">.${esc(a)}</span><span class="s-op">=</span><div>${expr(e)}</div></div>`).join("")}</div></div>`).join("");
    const rest = other.map(s => `<div class="s-stmt">${stmt(s)}</div>`).join("");
    return card(n, "on", "", `<span class="s-row">${pattern(k[0])}</span>`, `${isNone(k[1]) ? "" : `<div class="s-guard"><span class="s-kw">if</span>${expr(k[1])}</div>`}${eqs ? `<div class="s-eqh">gives its children</div>${eqs}` : ""}${rest ? `<div class="s-eqh">and</div>${rest}` : ""}${!isNone(k[3]) ? `<div class="s-eqs"><span class="s-kw">where</span>${kidsOf(kidsOf(k[3])[0]).map(i => `<div class="s-eq"><span class="s-name">${esc(kidsOf(i)[0].t)}</span><span class="s-op">=</span><div>${expr(kidsOf(i)[1])}</div></div>`).join("")}</div>` : ""}`);
  }
  // ---------------------------------------------------------------- Datalog
  const HUES = ["--l-facts", "--l-rewrite", "--l-syntax", "--l-scopes", "--l-attrs", "--l-rules", "--l-pipeline"];
  function factsItem(n) {
    const k = kidsOf(n);
    if (n.k === "Relation") return card(n, "relation", k[0].t, `<span class="s-params">${kidsOf(k[1]).map(c => `<span class="s-param"><span class="s-name">${esc(c.t)}</span></span>`).join("")}</span>`, "");
    if (n.k !== "Clause") return "";
    const vars = new Map(); const color = v => { if (!vars.has(v)) vars.set(v, HUES[vars.size % HUES.length]); return vars.get(v); };
    const atom = (a, cls) => { const ak = kidsOf(a); const rel = ak[0].t; const d = CAT.decls.find(x => x.file === file && x.kind === "relation" && x.name === rel);
      return `<span class="f-atom ${cls}"><span class="f-rel">${d ? `<a class="sym" data-d="${d.id}">${esc(rel)}</a>` : esc(rel)}</span><span class="f-args">${kidsOf(ak[1]).map(v => { const name = v.t || src(v); const base = (v.c && v.c[0] && v.c[0].t) || name;
        return `<span class="f-var" style="--c:var(${color(base)})">${esc(name)}</span>`; }).join("")}</span></span>`; };
    const head = k[0], body = kidsOf(k[1]);
    return `<section class="s-card f-rule" id="D${lineOf(n)}" data-l="${lineOf(n)}"><div class="f-head">${atom(head, "head")}<span class="f-if">⟸</span>${COUNTS[file + ":" + lineOf(n)] ? `<a class="chip lc-facts" href="#rule/${enc(file + ":" + lineOf(n))}">derived ${COUNTS[file + ":" + lineOf(n)].toLocaleString()}×</a>` : `<span class="faint">not derived yet</span>`}<span class="s-tools"><a class="s-line" href="#rule/${enc(file + ":" + lineOf(n))}" title="where it applied">${lineOf(n)}</a></span></div>
      <div class="f-body">${body.map(b => b.k === "Negated" ? atom(kidsOf(b)[0], "neg") : b.k === "Differs" ? `<span class="f-atom differs"><span class="f-var" style="--c:var(${color(kidsOf(b)[0].t)})">${esc(kidsOf(b)[0].t)}</span><span class="s-op">≠</span><span class="f-var" style="--c:var(${color(kidsOf(b)[1].t)})">${esc(kidsOf(b)[1].t)}</span></span>` : atom(b, "")).join("")}</div></section>`;
  }

  // ---------------------------------------------------------------- tables (.scopes, .pipeline)
  // Each item a keyword and the names it lists: node kinds as the nodes they are, a nested clause as
  // a row of its own.
  const label = k => k.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase();
  function value(v) {
    if (v.k === "List") return kidsOf(v).map(value).join("");
    if (v.k === "Name" || v.k === "Upper") { const d = resolve(file, v.t); return /^[A-Z]/.test(v.t) ? `<span class="p-node"><span class="p-kind">${d ? `<a class="sym" data-d="${d.id}">${esc(v.t)}</a>` : esc(v.t)}</span></span>` : `<span class="s-chipname">${d ? `<a class="sym" data-d="${d.id}">${esc(v.t)}</a>` : esc(v.t)}</span>`; }
    if (v.t) return `<span class="p-lit">${esc(v.t)}</span>`;
    if (isNone(v)) return "";
    if (!kidsOf(v).length) return `<span class="s-flag">${esc(label(v.k))}</span>`;
    // `check by f`: the clause says its own keyword; the item around it need not say it again.
    const only = kidsOf(v).length === 1 ? kidsOf(v)[0] : null;
    if (only && kidsOf(only).length && label(only.k).startsWith(label(v.k))) return value(only);
    return `<div class="s-trow"><span class="s-kw">${esc(label(v.k))}</span><span class="s-tvals">${kidsOf(v).map(value).join("")}</span></div>`;
  }
  function tableItem(n) {
    const k = kidsOf(n), d = declAt.get(lineOf(n));
    const named = k[0] && (k[0].k === "Name") && d && d.name === k[0].t;
    const rest = named ? k.slice(1) : k;
    const flags = rest.filter(v => !v.t && !isNone(v) && !kidsOf(v).length && v.k !== "List");
    const rows = rest.filter(v => !flags.includes(v));
    return card(n, d ? d.kind : label(n.k), named ? k[0].t : "", flags.map(value).join(""), `<div class="s-table">${rows.map(v => v.k === "List" && kidsOf(v).some(x => kidsOf(x).length) ? kidsOf(v).map(value).join("") : `<div class="s-trow"><span class="s-tvals">${value(v)}</span></div>`).join("")}</div>`);
  }

  function items(tree) {
    const lang = langOf(file);
    if (lang === "facts") return kidsOf(kidsOf(tree)[0]);
    if (lang === "scopes" || lang === "pipeline") return kidsOf(tree).filter(c => c.k === "List").flatMap(kidsOf);
    const list = kidsOf(tree).find(c => c.k === "List");
    return list ? kidsOf(list) : [];
  }
  const render = n => { const lang = langOf(file); return lang === "facts" ? factsItem(n) : lang === "scopes" || lang === "pipeline" ? tableItem(n) : decl(n); };
  return {
    // One card per declaration, each with the line it starts on.
    cards(tree) { return this.makers(tree).map(m => ({ html: m() })).filter(c => c.html); },
    // Each card as a function that makes it, so a page can make a few at a time.
    makers(tree) {
      if (tree.error) return [() => `<p class="empty">The grammar does not read this file: ${esc(tree.error)} (line ${tree.line}, column ${tree.col}).</p>`];
      return items(tree).filter(d => d.k !== "Use").map(n => () => render(n));
    },
    file(tree) {
      if (tree.error) return this.cards(tree)[0].html;
      const uses = items(tree).filter(d => d.k === "Use");
      const strip = uses.length ? `<section class="s-uses"><span class="s-kw">uses</span>${uses.map(u => { const m = kidsOf(u)[0], a = kidsOf(u)[1]; const f = fileOfModule()[m.t || src(m)];
        return f ? `<a class="chip lc-${langOf(f)}" href="#code/${enc(f + ":1")}">${esc(a.t)} = ${esc(baseOf(f))}</a>` : `<span class="chip">${esc(a.t)} = ${esc(m.t || src(m))}</span>`; }).join("")}</section>` : "";
      return strip + this.cards(tree).map(c => c.html).join("");
    },
  };
}

// ------------------------------------------------------------ files of the other languages, by shape

function rewriteStructure(file) { return rewriteCards(file).join(""); }
function rewriteCards(file) {
  const rs = CAT.rewrites[file] || []; let sec = null; const html = [];
  for (const r of rs) {
    if (r.section !== sec) { sec = r.section; html.push(`<h2 class="s-sect">${esc(sec || "rules")}</h2>`); }
    const n = COUNTS[file + ":" + r.line];
    html.push(`<section class="s-card" id="D${r.line}" data-l="${r.line}"><header><span class="tag lc-rewrite">rule</span><span class="s-dname">${esc(r.name)}</span>${n ? `<a class="chip lc-rewrite" href="#rule/${enc(file + ":" + r.line)}">applied ${n.toLocaleString()}×</a>` : ""}<span class="s-tools"><a class="s-line" href="#code/${enc(file + ":" + r.line)}/text">${r.line}</a></span></header>
      <div class="s-body"><div class="row trees">${termTree(r.lhs)}<span class="faint" style="font-size:18px">⇒</span>${termTree(r.rhs)}</div>${r.guards.length ? `<div class="s-guard"><span class="s-kw">when</span>${r.guards.map(g => `<code class="k-host">${esc(g)}</code>`).join(" ")}</div>` : ""}</div></section>`);
  }
  return html;
}
function grammarStructure(file) { const cs = grammarCards(file); return cs && cs.join(""); }
function grammarCards(file) {
  const prods = CAT.grammars[file];
  if (!prods) return null;
  return prods.map(p => grammarCard(file, p));
}
function grammarCard(file, p) {
  return `<section class="s-card" id="D${p.line}" data-l="${p.line}"><header><span class="tag lc-syntax">${esc([...p.mods, p.kind].join(" "))}</span><span class="s-dname">${esc(p.name)}</span><span class="s-tools"><a class="s-line" href="#code/${enc(file + ":" + p.line)}/text">${p.line}</a></span></header>
    <div class="s-body rr">${p.body ? railroad(p.body) : p.levels ? p.levels.map(l => `<div class="s-row"><span class="faint">${l.assoc}</span>${l.ops.map(o => `<code class="k-str">${esc(o.op)}</code><span class="p-node"><span class="p-kind">${esc(o.kind)}</span></span>`).join(" ")}</div>`).join("") : ""}</div></section>`;
}

// Under a recorded rule's card, the places it applied in the builds made so far: real code, each one
// a click from being kept as an example of the rule.
async function appliedUnder(card, file) {
  if (card.querySelector(".s-applied")) return;
  const key = file + ":" + card.dataset.l;
  const box = document.createElement("div"); box.className = "s-applied"; box.innerHTML = `<span class="spinner"></span>`;
  card.append(box);
  const occ = await api("rule?key=" + enc(key));
  const total = occ.reduce((a, o) => a + o.count, 0);
  if (!total) { box.innerHTML = `<p class="muted">It has not applied in any build yet. <a href="#rule/${enc(key)}">Its page</a> keeps examples.</p>`; return; }
  const shown = occ.flatMap(o => o.items.slice(0, 3).map((it, i) => occurrence(o.build, it, i))).slice(0, 6);
  box.innerHTML = `<div class="s-eqh">where it applied · ${total.toLocaleString()} in ${occ.length} build${occ.length === 1 ? "" : "s"} · <a href="#rule/${enc(key)}">all, and its examples</a></div>${shown.join("")}`;
  wirePins(box, key);
}

// ------------------------------------------------------------ the atlas: every definition, drawn

const TREE_LANGS = new Set(["rules", "attrs", "facts", "scopes", "pipeline"]);
// Every declaration of a file as a card: drawn from its tree, its rewrite trees, its railroads; a
// file no grammar here reads (a .bundler target) as its text.
async function makersOf(file) {
  const lang = langOf(file), now = cs => cs.map(c => () => c);
  if (lang === "rewrite") return now(rewriteCards(file));
  if (lang === "syntax") { const g = CAT.grammars[file]; return g ? g.map(p => () => grammarCard(file, p)) : now(textCards(file)); }
  if (TREE_LANGS.has(lang)) return Projector(file).makers(await api("tree?path=" + enc(file)));
  return now(textCards(file));
}
function textCards(file) {
  const lines = linesOf(file);
  return declsIn(file).map(d => `<section class="s-card" data-l="${d.line}"><header><span class="tag lc-${langOf(file)}">${esc(d.kind)}</span><span class="s-dname">${esc(d.name)}</span><span class="s-tools"><a class="s-line" href="#code/${enc(file + ":" + d.line)}/text">${d.line}</a></span></header>
    <div class="s-raw">${lines.slice(d.line - 1, Math.min(d.end || d.line, d.line + 14)).map(l => codeLine(l, file)).join("<br>")}</div></section>`);
}

const ATLAS_DIRS = ["languages", "bundle", "app", "react", "tanstack", "vite", "tools"];
MORE.map = function (main) {
  const files = Object.keys(CAT.files).filter(f => f.startsWith("src/") && declsIn(f).length)
    .sort((a, b) => (ATLAS_DIRS.indexOf(dirOf(a)) + 99) % 99 - (ATLAS_DIRS.indexOf(dirOf(b)) + 99) % 99 || a.localeCompare(b));
  const langs = [...new Set(files.map(langOf))];
  let off = new Set(); try { off = new Set(JSON.parse(localStorage.getItem("atlasoff") || "[]")); } catch (e) {}
  const total = files.reduce((a, f) => a + declsIn(f).length, 0);
  main.innerHTML = `<div class="atlas">
    <div class="atlas-bar"><h1>Every definition</h1><span class="muted">${total.toLocaleString()} in ${files.length} files</span>
      <input type="search" id="aq" placeholder="find a definition by name or doc">
      <span class="row" id="alangs">${langs.map(l => `<button class="tag lc-${l} toggle" data-l="${l}" aria-pressed="${!off.has(l)}">${esc(LANG_NAME[l])}</button>`).join("")}</span>
      <span class="faint" id="acount"></span></div>
    <nav class="atlas-toc">${ATLAS_DIRS.filter(d => files.some(f => dirOf(f) === d)).map(d => `<div class="toc-dir"><b>${esc(d)}</b>${files.filter(f => dirOf(f) === d).map(f => `<a href="#" data-f="${esc(f)}" class="lc-${langOf(f)}">${esc(baseOf(f))}<span>${declsIn(f).length}</span></a>`).join("")}</div>`).join("")}</nav>
    <div class="atlas-files" id="afiles">${files.map(f => `<section class="atlas-file" data-f="${esc(f)}" style="--n:${declsIn(f).length}">
      <header><span class="tag lc-${langOf(f)}">${esc(LANG_NAME[langOf(f)])}</span><a href="#code/${enc(f + ":1")}"><code>${esc(short(f))}</code></a><span class="faint">${declsIn(f).length} · ${fileLines(f)} lines</span></header>
      <div class="atlas-grid"></div></section>`).join("")}</div></div>`;
  const box = $("#afiles");
  const q = () => $("#aq").value.trim().toLowerCase();
  const matches = d => { const s = q(); return !s || d.name.toLowerCase().includes(s) || (d.doc || "").toLowerCase().includes(s); };
  const filterSection = sec => {
    const f = sec.dataset.f, hit = !off.has(langOf(f)) && declsIn(f).some(matches);
    sec.hidden = !hit;
    if (sec.dataset.done) { const names = new Map(declsIn(f).map(d => [d.line, d])); sec.querySelectorAll(".s-card").forEach(c => { const d = names.get(+c.dataset.l); c.hidden = !!q() && !(d ? matches(d) : false); }); }
  };
  const filter = () => { box.querySelectorAll(".atlas-file").forEach(filterSection); later(); const shown = [...box.querySelectorAll(".atlas-file:not([hidden])")].map(x => x.dataset.f); $("#acount").textContent = q() || off.size ? `${shown.reduce((a, f) => a + declsIn(f).filter(matches).length, 0).toLocaleString()} shown` : ""; };
  // Only what is near the screen is in the page: a section is drawn as it comes within a screen or
  // two, one per frame, and emptied again when it is far away (its cards kept, to put back at once),
  // so the page holds a few thousand elements, not hundreds of thousands. Off the screen, the
  // browser neither lays out nor paints a section (content-visibility).
  const makers = new Map(), html = new Map(), heights = new Map(), queue = [];
  const estimate = f => Math.max(80, Math.round(fileLines(f) * (langOf(f) === "syntax" ? 9 : 5.2)));
  box.querySelectorAll(".atlas-file").forEach(sec => sec.style.setProperty("--h", estimate(sec.dataset.f) + "px"));
  // A section's cards are made and put in a few at a time, each frame stopping after a few
  // milliseconds, so scrolling never waits on a big file.
  const BUDGET = 6;
  const frame = () => new Promise(r => requestAnimationFrame(r));
  const finish = sec => {
    const f = sec.dataset.f, grid = sec.querySelector(".atlas-grid");
    sec.dataset.done = 1; delete sec.dataset.filling;
    requestAnimationFrame(() => {
      // every size read first, then every mark made: one layout, not one per card
      const cards = [...grid.querySelectorAll(".s-card")];
      const cut = cards.map(c => { const b = c.querySelector(".s-body"); return [c.scrollHeight > c.clientHeight + 2, !!b && b.scrollWidth > b.clientWidth + 2]; });
      const h = sec.offsetHeight;
      cards.forEach((c, i) => { if (cut[i][0]) c.classList.add("clipped"); if (cut[i][1]) c.classList.add("clipped-x"); });
      heights.set(f, h); sec.style.setProperty("--h", h + "px");
    });
    filterSection(sec);
  };
  // How far a section is from the screen, measured now: what is drawn or emptied is decided by where
  // things are, not by notices of what changed, which arrive after heights have moved.
  const scroller = $("#main");
  const distance = (sec, v = scroller.getBoundingClientRect()) => {
    const r = sec.getBoundingClientRect();
    return r.bottom < v.top ? v.top - r.bottom : r.top > v.bottom ? r.top - v.bottom : 0;
  };
  const NEAR = 1200, FAR = 5000;
  let pumping = false;
  const pump = async () => {
    if (pumping) return; pumping = true;
    while (queue.length) {
      // nearest first: what is on the screen draws before what is a screen away
      { const v = scroller.getBoundingClientRect(), d = new Map(queue.map(x => [x, distance(x, v)])); queue.sort((x, y) => d.get(x) - d.get(y)); }
      const sec = queue.shift(); if (sec.dataset.done || sec.hidden || distance(sec) > NEAR * 2) continue;
      const f = sec.dataset.f, grid = sec.querySelector(".atlas-grid");
      if (!makers.has(f)) { try { makers.set(f, await makersOf(f)); } catch (e) { makers.set(f, [() => `<p class="empty">${esc(String(e.message || e))}</p>`]); } }
      const ms = makers.get(f), made = html.get(f) || []; html.set(f, made);
      grid.innerHTML = ""; sec.classList.remove("ph"); sec.dataset.filling = 1;
      let i = 0, t = performance.now();
      while (i < ms.length) {
        if (made[i] === undefined) made[i] = ms[i]();
        // cards already made go in many at a time; making them is what costs
        let k = i + 1; while (k < ms.length && made[k] !== undefined && k - i < 60) k++;
        grid.insertAdjacentHTML("beforeend", made.slice(i, k).join("")); i = k;
        if (performance.now() - t > BUDGET) {
          await frame(); t = performance.now();
          if (distance(sec) > FAR) break;  // scrolled away while it was being drawn
        }
      }
      if (i < ms.length) { grid.innerHTML = ""; sec.classList.add("ph"); delete sec.dataset.filling; continue; }
      finish(sec);
      await frame(); settle();
    }
    pumping = false;
  };
  const draw = sec => { if (!sec.dataset.done && !queue.includes(sec)) { queue.push(sec); pump(); } };
  const drop = sec => {
    if (sec.dataset.filling) return;
    sec.style.setProperty("--h", (heights.get(sec.dataset.f) || sec.offsetHeight) + "px");
    sec.querySelector(".atlas-grid").innerHTML = ""; delete sec.dataset.done; sec.classList.add("ph");
  };
  // Every section measured first, then drawn or emptied: one layout per frame.
  const settle = () => {
    const v = scroller.getBoundingClientRect();
    const ds = [...box.querySelectorAll(".atlas-file:not([hidden])")].map(sec => [sec, distance(sec, v)]);
    for (const [sec, d] of ds) { if (d <= NEAR) draw(sec); else if (d > FAR && sec.dataset.done) drop(sec); }
  };
  let pending = false;
  const later = () => { if (!pending) { pending = true; requestAnimationFrame(() => { pending = false; settle(); }); } };
  scroller.addEventListener("scroll", later, { passive: true });
  addEventListener("resize", later);
  box.querySelectorAll(".atlas-file").forEach(sec => sec.classList.add("ph"));
  // The page is left for another: stop listening to its scroll.
  const gone = new MutationObserver(() => { if (!box.isConnected) { scroller.removeEventListener("scroll", later); removeEventListener("resize", later); gone.disconnect(); } });
  gone.observe(main, { childList: true });
  wireCode(box, null, null);
  box.addEventListener("click", e => {
    if (e.target.closest("a, button, .s-applied")) return;
    const c = e.target.closest(".s-card"), sec = e.target.closest(".atlas-file");
    if (c && sec) location.hash = "code/" + enc(sec.dataset.f + ":" + c.dataset.l);
  });
  main.querySelector(".atlas-toc").addEventListener("click", e => { const a = e.target.closest("a[data-f]"); if (!a) return; e.preventDefault(); const sec = box.querySelector(`.atlas-file[data-f="${CSS.escape(a.dataset.f)}"]`); if (sec) { sec.scrollIntoView({ block: "start" }); later(); } });
  $("#aq").oninput = filter;
  $("#alangs").onclick = e => { const b = e.target.closest("button[data-l]"); if (!b) return; off.has(b.dataset.l) ? off.delete(b.dataset.l) : off.add(b.dataset.l); b.setAttribute("aria-pressed", !off.has(b.dataset.l)); try { localStorage.setItem("atlasoff", JSON.stringify([...off])); } catch (e) {} filter(); };
  filter();
};
