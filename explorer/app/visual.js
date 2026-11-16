"use strict";
// The tower drawn: a map of its modules, each module's code beside a picture of it in its own
// language's terms, and any declaration in the middle of what uses it and what it uses. Uses the
// catalog app.js loaded (CAT) and its helpers.

// ------------------------------------------------------------ graphs: laid out by dagre, panned and zoomed

// nodes: {id, label, sub?, lang, badge?, dim?, shape?}; edges: {from, to, label?, dashed?}.
function drawGraph(box, nodes, edges, opts = {}) {
  const g = new dagre.graphlib.Graph({ multigraph: true, compound: !!opts.clusters });
  g.setGraph({ rankdir: opts.rankdir || "LR", nodesep: opts.nodesep ?? 10, ranksep: opts.ranksep ?? 70, edgesep: 6, marginx: 24, marginy: 24 });
  g.setDefaultEdgeLabel(() => ({}));
  const byId = new Map(nodes.map(n => [n.id, n]));
  for (const n of nodes) {
    const w = Math.max(n.label.length * 7.4, (n.sub || "").length * 6.2) + 26 + (n.badge ? 28 : 0);
    g.setNode(n.id, { width: Math.min(Math.max(w, 60), 360), height: n.sub ? 36 : 24 });
  }
  for (const c of opts.clusters || []) g.setNode(c.id, { label: c.label, clusterLabelPos: "top", paddingTop: 24 });
  for (const n of nodes) if (n.parent) g.setParent(n.id, n.parent);
  edges.forEach((e, i) => { if (byId.has(e.from) && byId.has(e.to) && e.from !== e.to) g.setEdge(e.from, e.to, {}, "e" + i); });
  if (opts.layers) columnLayout(g, nodes, edges, opts); else dagre.layout(g);
  const W = g.graph().width || 100, H = g.graph().height || 100;
  let es = "", ns = "", cs = "";
  for (const c of opts.clusters || []) { const v = g.node(c.id); if (!v || !v.width) continue;
    cs += `<g class="gc"><rect x="${v.x - v.width / 2}" y="${v.y - v.height / 2}" width="${v.width}" height="${v.height}" rx="10"/><text x="${v.x - v.width / 2 + 12}" y="${v.y - v.height / 2 + 16}">${esc(c.label)}</text></g>`; }
  edges.forEach((e, i) => {
    const ed = g.edge({ v: e.from, w: e.to, name: "e" + i }); if (!ed) return;
    const p = ed.points; let d = `M${p[0].x} ${p[0].y}`;
    for (let k = 1; k < p.length - 1; k++) { const mx = (p[k].x + p[k + 1].x) / 2, my = (p[k].y + p[k + 1].y) / 2; d += ` Q${p[k].x} ${p[k].y} ${mx} ${my}`; }
    d += ` L${p[p.length - 1].x} ${p[p.length - 1].y}`;
    es += `<path class="ge${e.dashed ? " dashed" : ""}" data-f="${esc(e.from)}" data-t="${esc(e.to)}" d="${d}" marker-end="url(#arrow)"><title>${esc(e.label || "")}</title></path>`;
  });
  for (const n of nodes) {
    const v = g.node(n.id); if (!v) continue;
    const x = v.x - v.width / 2, y = v.y - v.height / 2;
    ns += `<g class="gn lc-${n.lang || "rules"}${n.dim ? " faded" : ""}${n.shape === "ext" ? " ext" : ""}${n.shape === "base" ? " base" : ""}" data-id="${esc(n.id)}"><title>${esc(n.title || n.label)}</title>
      <rect x="${x}" y="${y}" width="${v.width}" height="${v.height}" rx="${n.shape === "ext" ? 12 : 5}"/>
      <text x="${x + 10}" y="${y + (n.sub ? 14 : v.height / 2)}" class="gl">${esc(n.label)}</text>${n.sub ? `<text x="${x + 10}" y="${y + 27}" class="gs">${esc(n.sub)}</text>` : ""}
      ${n.badge ? `<text x="${x + v.width - 8}" y="${y + (n.sub ? 14 : v.height / 2)}" class="gb">${esc(n.badge)}</text>` : ""}</g>`;
  }
  box.innerHTML = `<svg class="graph" width="100%" height="100%"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="ah"/></marker></defs><g class="vp">${(g.graph().columns || []).map(c => `<text class="colh" x="${c.x}" y="22">${esc(c.label)}</text>`).join("")}${cs}${es}${ns}</g></svg>`;
  const svg = box.querySelector("svg"), vp = box.querySelector(".vp");
  let s = 1, tx = 0, ty = 0;
  const apply = () => vp.setAttribute("transform", `translate(${tx} ${ty}) scale(${s})`);
  // The whole drawing if it reads at that size; else as small as still reads, around `centerOn`.
  const fit = () => { const r = box.getBoundingClientRect(); s = Math.min(1.1, (r.width - 10) / W, (r.height - 10) / H); if (!isFinite(s) || s <= 0) s = 1;
    tx = (r.width - W * s) / 2; ty = Math.max(4, (r.height - H * s) / 2);
    if (opts.minScale && s < opts.minScale) { s = opts.minScale; const v = opts.centerOn && g.node(opts.centerOn); const cx = v ? v.x : W / 2, cy = v ? v.y : H / 2; tx = r.width / 2 - cx * s; ty = r.height / 2 - cy * s;
      if (opts.topLeft) { tx = 8; ty = 4; } }
    apply(); };
  fit();
  svg.addEventListener("wheel", e => { e.preventDefault(); const r = svg.getBoundingClientRect(); const mx = e.clientX - r.left, my = e.clientY - r.top; const k = Math.exp(-e.deltaY * 0.0015); tx = mx - (mx - tx) * k; ty = my - (my - ty) * k; s *= k; apply(); }, { passive: false });
  let drag = null;
  svg.addEventListener("mousedown", e => { if (e.target.closest(".gn")) return; drag = { x: e.clientX - tx, y: e.clientY - ty }; svg.classList.add("dragging"); });
  window.addEventListener("mousemove", e => { if (drag) { tx = e.clientX - drag.x; ty = e.clientY - drag.y; apply(); } });
  window.addEventListener("mouseup", () => { drag = null; svg.classList.remove("dragging"); });
  const hot = (id, dim = true) => {
    vp.classList.toggle("hovering", !!id && dim);
    vp.querySelectorAll(".hot").forEach(x => x.classList.remove("hot"));
    if (!id) return;
    vp.querySelectorAll(`.gn[data-id="${CSS.escape(id)}"]`).forEach(x => x.classList.add("hot"));
    vp.querySelectorAll(`.ge[data-f="${CSS.escape(id)}"], .ge[data-t="${CSS.escape(id)}"]`).forEach(x => { x.classList.add("hot"); [x.dataset.f, x.dataset.t].forEach(o => vp.querySelectorAll(`.gn[data-id="${CSS.escape(o)}"]`).forEach(n => n.classList.add("hot"))); });
  };
  vp.addEventListener("mouseover", e => { const n = e.target.closest(".gn"); if (n) hot(n.dataset.id); else hot(selected, false); if (n && opts.onHover) opts.onHover(n.dataset.id); });
  vp.addEventListener("mouseleave", () => hot(selected, false));
  vp.addEventListener("click", e => { const n = e.target.closest(".gn"); if (n && opts.onClick) opts.onClick(n.dataset.id, e); });
  let selected = null;
  const api = {
    fit,
    select(id, center) {
      selected = id; vp.querySelectorAll(".gn.sel").forEach(x => x.classList.remove("sel"));
      if (!id) { hot(null); return; }
      vp.querySelectorAll(`.gn[data-id="${CSS.escape(id)}"]`).forEach(x => x.classList.add("sel")); hot(id, false);
      const v = g.node(id);
      if (v && center) { const r = box.getBoundingClientRect(); s = Math.max(s, 0.8); tx = r.width / 2 - v.x * s; ty = r.height / 2 - v.y * s; apply(); }
    },
  };
  return api;
}

// Columns: each node in its layer's column, in the order given; an edge a curve from one to the next.
function columnLayout(g, nodes, edges, opts) {
  const colW = opts.colWidth || 220, rowH = opts.rowHeight || 44, gap = opts.colGap || 70, top = 40;
  const cols = new Map();
  for (const n of nodes) { const l = opts.layers.get(n.id) ?? 0; if (!cols.has(l)) cols.set(l, []); cols.get(l).push(n); }
  let maxRows = 0;
  for (const [l, ns] of cols) { ns.sort(opts.order || (() => 0)); ns.forEach((n, i) => { const v = g.node(n.id); v.width = colW - 20; v.x = 24 + l * (colW + gap) + v.width / 2; v.y = top + i * rowH + v.height / 2; }); maxRows = Math.max(maxRows, ns.length); }
  edges.forEach((e, i) => { const ed = g.edge({ v: e.from, w: e.to, name: "e" + i }); if (!ed) return; const a = g.node(e.from), b = g.node(e.to);
    const ax = a.x + a.width / 2, bx = b.x - b.width / 2; ed.points = [{ x: ax, y: a.y }, { x: (ax + bx) / 2, y: a.y }, { x: (ax + bx) / 2, y: b.y }, { x: bx, y: b.y }]; });
  g.graph().width = 48 + cols.size * (colW + gap); g.graph().height = top + maxRows * rowH + 24;
  g.graph().columns = [...cols.keys()].map(l => ({ x: 24 + l * (colW + gap), label: (opts.columnLabel || (x => "layer " + x))(l) }));
}

const dirOf = f => short(f).split("/")[0];
const baseOf = f => f.split("/").pop();
const declsIn = f => CAT.decls.filter(d => d.file === f && d.kind !== "node kind");
const fileLines = f => linesOf(f).filter(l => l.trim() && !l.trim().startsWith("#")).length;
const EDGE_WORD = { "called by": "calls", "asserted from attrs": "asserts", "asserted from rules": "asserts", "read by": "reads", "derived by": "derives", "used by": "uses",
  "kept or staged by pipeline": "keeps", "matched or made in rules": "matches", "matched or made in attrs": "matches", "matched or made in rewrite": "rewrites", "placed by scopes": "places", "made by grammar": "makes" };

// ------------------------------------------------------------ the map

MORE.map = function (main) {
  const files = Object.keys(CAT.files).sort();
  const dirs = [...new Set(files.map(dirOf))];
  const off = new Set(JSON.parse(sessionStorage.getItem("mapoff") || "[]"));
  main.innerHTML = `<div class="page wide"><div class="row"><h1>The tower</h1><span class="muted">every module, colored by its language; an arrow runs from what a module builds on to the module. Scroll to zoom, drag to move, click to open.</span></div>
    <div class="row" id="dirs">${dirs.map(d => `<label class="check"><input type="checkbox" value="${esc(d)}"${off.has(d) ? "" : " checked"}> ${esc(d)}</label>`).join("")}
      <span class="faint">·</span>${["syntax", "rules", "attrs", "facts", "rewrite", "scopes", "pipeline", "bundler"].map(l => `<span class="tag lc-${l}">${esc(LANG_NAME[l])}</span>`).join("")}
      <input type="search" id="mapq" placeholder="find a module" style="margin-left:auto"></div>
    <div class="canvas-row"><div class="canvas faint-edges" id="map"></div><aside class="panel side-info" id="mapinfo"><div class="body"><p class="muted">Hover a module to see what it builds on and what builds on it.</p></div></aside></div></div>`;
  const draw = () => {
    const keep = files.filter(f => !off.has(dirOf(f)));
    const set = new Set(keep);
    const seen = new Set(), edges = [];
    for (const d of CAT.deps) if (set.has(d.from) && set.has(d.to)) { const k = d.to + ">" + d.from; if (!seen.has(k)) { seen.add(k); edges.push({ from: d.to, to: d.from, dashed: !!d.over, label: d.over ? "is over" : "uses" }); } }
    // How high in the tower a module stands: one above the highest of what it builds on.
    const uses = new Map(keep.map(f => [f, []])); for (const e of edges) uses.get(e.to).push(e.from);
    const depth = new Map(), busy = new Set();
    const level = f => { if (depth.has(f)) return depth.get(f); if (busy.has(f)) return 0; busy.add(f); const l = Math.max(-1, ...uses.get(f).map(level)) + 1; busy.delete(f); depth.set(f, l); return l; };
    keep.forEach(level);
    const nodes = keep.map(f => ({ id: f, label: baseOf(f), sub: dirOf(f) + " · " + fileLines(f) + " lines", lang: langOf(f), title: f }));
    const order = ["languages", "bundle", "app", "react", "tanstack", "vite", "tools"];
    const gr = drawGraph($("#map"), nodes, edges, { layers: depth, colWidth: 200, rowHeight: 42, colGap: 60, minScale: 0.85, topLeft: true,
      order: (a, b) => order.indexOf(dirOf(a.id)) - order.indexOf(dirOf(b.id)) || a.label.localeCompare(b.label),
      columnLabel: l => l === 0 ? "builds on nothing" : l === 1 ? "on those" : "level " + l,
      onClick: id => location.hash = "code/" + enc(id + ":1"),
      onHover: id => info(id) });
    $("#mapq").oninput = e => { const q = e.target.value.toLowerCase(); const hit = q && keep.find(f => f.toLowerCase().includes(q)); if (hit) { gr.select(hit, true); info(hit); } };
  };
  const info = f => {
    const uses = CAT.deps.filter(d => d.from === f), usedBy = CAT.deps.filter(d => d.to === f);
    const ds = declsIn(f);
    $("#mapinfo").innerHTML = `<header><span class="tag lc-${langOf(f)}">${esc(LANG_NAME[langOf(f)])}</span><code>${esc(short(f))}</code></header><div class="body">
      ${ds[0] && ds[0].doc ? `<p class="muted">${esc(ds[0].doc.slice(0, 220))}</p>` : linesOf(f)[0].startsWith("#") ? `<p class="muted">${esc(linesOf(f).filter(l => l.startsWith("#")).slice(0, 3).map(l => l.slice(1).trim()).join(" ").slice(0, 260))}</p>` : ""}
      <p><b>${fileLines(f)}</b> lines · <b>${ds.length}</b> declarations</p>
      <p class="faint">builds on</p><div class="row">${uses.map(d => `<a class="chip lc-${langOf(d.to)}" href="#code/${enc(d.to + ":1")}">${esc(baseOf(d.to))}</a>`).join("") || "<span class='faint'>nothing</span>"}</div>
      <p class="faint">built on by</p><div class="row">${usedBy.map(d => `<a class="chip lc-${langOf(d.from)}" href="#code/${enc(d.from + ":1")}">${esc(baseOf(d.from))}</a>`).join("") || "<span class='faint'>nothing</span>"}</div>
      <a class="btn" href="#code/${enc(f + ":1")}">Open its code</a></div>`;
  };
  $("#dirs").onchange = e => { if (e.target.value) { e.target.checked ? off.delete(e.target.value) : off.add(e.target.value); sessionStorage.setItem("mapoff", JSON.stringify([...off])); draw(); } };
  draw();
};

// ------------------------------------------------------------ code: every name a link

const declIndex = {};
function namesOf(file) {
  if (declIndex[file]) return declIndex[file];
  const m = new Map();
  for (const d of declsIn(file)) if (!m.has(d.name)) m.set(d.name, d);
  return (declIndex[file] = m);
}
const fileOfModule = () => { if (!CAT._fom) { CAT._fom = {}; for (const [f, m] of Object.entries(CAT.modules)) if (!(m in CAT._fom)) CAT._fom[m] = f; } return CAT._fom; };
const kindDecl = name => { if (!CAT._kinds) CAT._kinds = new Map(CAT.decls.filter(d => d.kind === "node kind").map(d => [d.name, d])); return CAT._kinds.get(name); };

// The declaration a name in `file` means: an alias's (`js.render`), the file's own, a node kind.
function resolve(file, word) {
  const dot = word.indexOf(".");
  if (dot > 0) {
    const mod = (CAT.aliases[file] || {})[word.slice(0, dot)];
    if (mod) { const f = fileOfModule()[mod]; if (f) return namesOf(f).get(word.slice(dot + 1)) || null; }
    const slash = word.indexOf("/");
    if (slash > 0) { const f = fileOfModule()[word.slice(0, slash)]; if (f) return namesOf(f).get(word.slice(slash + 1)) || null; }
    return null;
  }
  const own = namesOf(file).get(word);
  if (own) return own;
  if (/^[A-Z]/.test(word)) return kindDecl(word) || null;
  return null;
}
function codeLine(line, file) {
  let out = "", i = 0;
  while (i < line.length) {
    const c = line[i];
    if (c === "#" || (c === ";" && line[i + 1] === ";")) { out += `<span class="k-com">${esc(line.slice(i))}</span>`; break; }
    if (c === '"' || c === "`") { let j = i + 1; while (j < line.length && line[j] !== c) j += line[j] === "\\" ? 2 : 1; out += `<span class="k-str">${esc(line.slice(i, j + 1))}</span>`; i = j + 1; continue; }
    const m = /^(@[\w-]+|[A-Za-z_][\w-]*[?!]?(?:[./][A-Za-z_][\w-]*[?!]?)?|\d+)/.exec(line.slice(i));
    if (m) {
      const w = m[0];
      const d = !/^\d/.test(w) && !KWS.has(w) ? resolve(file, w.replace(/^@/, "")) : null;
      const cls = w[0] === "@" ? "k-host" : /^\d/.test(w) ? "k-num" : /^[A-Z]/.test(w) ? "k-kind" : KWS.has(w) ? "k-kw" : "";
      if (d) out += `<a class="sym ${cls}" data-d="${d.id}">${esc(w)}</a>`;
      else if (w.includes(".") && !w.startsWith("@")) { const [a, b] = [w.slice(0, w.indexOf(".")), w.slice(w.indexOf(".") + 1)]; out += codeLine(a, file) + "." + codeLine(b, file); }
      else out += cls ? `<span class="${cls}">${esc(w)}</span>` : esc(w);
      i += w.length; continue;
    }
    out += esc(c); i++;
  }
  return out;
}

let tip = null;
function tooltip(el, d) {
  if (!tip) { tip = document.createElement("div"); tip.className = "tip"; document.body.append(tip); }
  if (!el) { tip.hidden = true; return; }
  const first = linesOf(d.file)[d.line - 1] || "";
  tip.innerHTML = `<div class="row"><span class="tag lc-${d.kind === "node kind" ? "syntax" : langOf(d.file)}">${esc(d.kind)}</span><code>${esc(d.name)}</code><span class="faint">${esc(short(d.file))}:${d.line}</span></div><pre class="code">${hiLine(first.trim().slice(0, 150))}</pre>${d.doc ? `<p class="muted">${esc(d.doc.slice(0, 260))}</p>` : ""}`;
  tip.hidden = false;
  const r = el.getBoundingClientRect(); tip.style.left = Math.min(r.left, innerWidth - 470) + "px"; tip.style.top = (r.bottom + 6) + "px";
}
function wireCode(pane, file, onLine) {
  pane.addEventListener("mouseover", e => {
    const a = e.target.closest("a.sym");
    pane.querySelectorAll(".sym.hot").forEach(x => x.classList.remove("hot"));
    if (!a) { tooltip(null); return; }
    pane.querySelectorAll(`a.sym[data-d="${a.dataset.d}"]`).forEach(x => x.classList.add("hot"));
    tooltip(a, CAT.decls[+a.dataset.d]);
  });
  pane.addEventListener("mouseleave", () => tooltip(null));
  pane.addEventListener("click", e => {
    const a = e.target.closest("a.sym"), f = e.target.closest(".focusbtn");
    if (f) { location.hash = "focus/" + f.dataset.d; return; }
    if (a) { tooltip(null); const d = CAT.decls[+a.dataset.d]; if (e.altKey || e.metaKey) location.hash = "focus/" + d.id; else location.hash = "code/" + enc(d.file + ":" + d.line); return; }
    const ln = e.target.closest(".cl"); if (ln && onLine) onLine(+ln.dataset.l);
  });
}

MORE.code = function (main, rest) {
  const spec = rest.join("/");
  if (!spec) {
    const last = sessionStorage.getItem("lastcode"); if (last) { location.hash = "code/" + enc(last); return; }
    location.hash = "map"; return;
  }
  const i = spec.lastIndexOf(":"); const file = i > 0 ? spec.slice(0, i) : spec; const line = i > 0 ? +spec.slice(i + 1) : 1;
  if (!CAT.files[file]) throw new Error("no file " + file + " under src/");
  sessionStorage.setItem("lastcode", file + ":" + line);
  const lang = langOf(file), lines = linesOf(file), decls = declsIn(file);
  const starts = new Map(decls.map(d => [d.line, d]));
  const lg = CAT.languages.find(l => l.key === lang);
  main.innerHTML = `<div class="page wide">
    <div class="crumbs"><a href="#map">The tower</a> / <span>${esc(dirOf(file))}</span> /</div>
    <div class="row"><h1><code>${esc(baseOf(file))}</code></h1><span class="tag lc-${lang}">${esc(LANG_NAME[lang])}</span><span class="muted">${fileLines(file)} lines · ${decls.length} declarations</span>
      ${lg ? `<span class="faint">written in a language defined by</span>${lg.grammar ? `<a class="chip lc-syntax" href="#code/${enc(lg.grammar + ":1")}">${esc(baseOf(lg.grammar))}</a>` : ""}<a class="chip lc-coil" href="#file/${enc(lg.compiler)}:1">${esc(baseOf(lg.compiler))}</a>` : ""}</div>
    <div class="codegrid"><section class="panel code-pane"><header>Code <span class="sub">hover a name for what it is · click to go to it · ⌥-click to see it in the middle of what uses it</span></header>
        <div class="codebody" id="code">${lines.map((l, k) => { const d = starts.get(k + 1); return `<div class="cl${k + 1 === line ? " at" : ""}${d ? " dl" : ""}" data-l="${k + 1}" id="L${k + 1}"><span class="n">${k + 1}</span>${d ? `<button class="focusbtn" data-d="${d.id}" title="see ${esc(d.name)} in the middle of what uses it">◎</button>` : `<span class="nofocus"></span>`}<span class="t">${codeLine(l, file) || " "}</span></div>`; }).join("")}</div></section>
      <section class="panel pic-pane"><header id="pichead">Picture</header><div class="pic" id="pic"></div></section></div></div>`;
  const pic = picture(file, lang, $("#pic"), $("#pichead"), l => { goLine(l); });
  const goLine = l => { const el = $(`#L${l}`); if (!el) return; main.querySelectorAll(".cl.at").forEach(x => x.classList.remove("at")); el.classList.add("at"); const box = $("#code"); box.scrollTop = el.offsetTop - box.offsetTop - 80; history.replaceState(null, "", "#code/" + enc(file + ":" + l)); };
  wireCode($("#code"), file, l => { let d = null; for (const x of decls) if (x.line <= l) d = x; if (d && pic && pic.select) pic.select(d, l); });
  goLine(line);
  let d0 = null; for (const x of decls) if (x.line <= line) d0 = x; if (d0 && pic && pic.select) pic.select(d0, line);
};

// ------------------------------------------------------------ a module's picture, in its language's terms

function picture(file, lang, box, head, goLine) {
  if (lang === "rules" || lang === "attrs") return callPicture(file, box, head, goLine);
  if (lang === "facts") return factsPicture(file, box, head, goLine);
  if (lang === "rewrite") return rewritePicture(file, box, head, goLine);
  if (lang === "syntax") return grammarPicture(file, box, head, goLine);
  if (lang === "pipeline") return pipelinePicture(file, box, head, goLine);
  if (lang === "scopes") return scopesPicture(file, box, head, goLine);
  head.innerHTML = "Picture"; box.innerHTML = `<p class="empty">A build spec is data: each setting is given meaning by <a href="#code/${enc("src/bundle/spec.rules:1")}">spec.rules</a>.</p>`;
}

const SHOWN_KINDS = new Set(["fn", "record", "enum", "setting", "on", "inh", "syn", "input", "rewrite"]);
function callPicture(file, box, head, goLine) {
  const ds = declsIn(file).filter(d => SHOWN_KINDS.has(d.kind));
  const mine = new Set(ds.map(d => d.id));
  const nodes = [], edges = [], ext = new Map(), seen = new Set();
  const extNode = (f, side) => { const id = side + ":" + f; if (!ext.has(id)) { ext.set(id, { id, label: baseOf(f), sub: side === "in" ? "uses this module" : "this module uses", lang: langOf(f), shape: "ext", n: 0 }); } ext.get(id).n++; return id; };
  for (const [a, b, label] of CAT.edges) {
    const da = CAT.decls[a], db = CAT.decls[b];
    if (mine.has(a) && mine.has(b)) { const k = a + ">" + b; if (!seen.has(k)) { seen.add(k); edges.push({ from: "d" + a, to: "d" + b, label: EDGE_WORD[label] || label }); } }
    else if (mine.has(a) && db && db.file !== file && db.kind !== "node kind") { const x = extNode(db.file, "out"); const k = a + ">" + x; if (!seen.has(k)) { seen.add(k); edges.push({ from: "d" + a, to: x, label: EDGE_WORD[label] || label }); } }
    else if (mine.has(b) && da && da.file !== file) { const x = extNode(da.file, "in"); const k = x + ">" + b; if (!seen.has(k)) { seen.add(k); edges.push({ from: x, to: "d" + b, label: EDGE_WORD[label] || label }); } }
  }
  const linked = new Set(edges.flatMap(e => [e.from, e.to]));
  for (const d of ds) nodes.push({ id: "d" + d.id, label: d.name.length > 38 ? d.name.slice(0, 36) + "…" : d.name, sub: d.kind === "fn" ? "" : d.kind, lang: langOf(file), dim: !linked.has("d" + d.id), title: d.name });
  for (const n of ext.values()) { n.badge = String(n.n); nodes.push(n); }
  head.innerHTML = `Who calls whom <span class="sub">${ds.length} declarations · ${[...ext.keys()].filter(k => k.startsWith("out")).length} modules it uses · ${[...ext.keys()].filter(k => k.startsWith("in")).length} that use it</span>`;
  const gr = drawGraph(box, nodes, edges, { rankdir: "LR", ranksep: 60, nodesep: 6,
    onClick: id => { if (id.startsWith("d")) { const d = CAT.decls[+id.slice(1)]; goLine(d.line); gr.select(id); } else location.hash = "code/" + enc(id.slice(id.indexOf(":") + 1) + ":1"); } });
  return { select: d => gr.select("d" + d.id, true) };
}

function factsPicture(file, box, head, goLine) {
  const rels = declsIn(file).filter(d => d.kind === "relation");
  const relIds = new Map(rels.map(d => [d.name, d]));
  const rules = CAT.facts[file] || [];
  const derived = new Set(rules.map(r => r.head));
  const nodes = rels.map(d => ({ id: d.name, label: d.name, sub: "(" + (d.cols || []).join(", ") + ")", lang: "facts", shape: derived.has(d.name) ? "" : "base", title: d.doc || d.name }));
  const edges = [], seen = new Set();
  for (const r of rules) for (const a of r.body) if (relIds.has(a.rel)) { const k = a.rel + ">" + r.head; if (!seen.has(k)) { seen.add(k); edges.push({ from: a.rel, to: r.head, dashed: a.neg, label: (a.neg ? "not " : "") + "read by line " + r.line }); } }
  // Code in other languages that states a relation's facts.
  const ext = new Map();
  for (const [a, b, label] of CAT.edges) { const db = CAT.decls[b], da = CAT.decls[a]; if (db && db.file === file && label.startsWith("asserted") && da) { const id = "x:" + da.file; if (!ext.has(id)) { ext.set(id, true); nodes.push({ id, label: baseOf(da.file), sub: "states facts", lang: langOf(da.file), shape: "ext" }); } const k = id + ">" + db.name; if (!seen.has(k)) { seen.add(k); edges.push({ from: id, to: db.name, label: "asserts" }); } } }
  head.innerHTML = `Which relations are derived from which <span class="sub">${rels.length} relations · ${rules.length} rules · dashed box: given, not derived</span>`;
  const gr = drawGraph(box, nodes, edges, { rankdir: "LR", ranksep: 70, nodesep: 6,
    onClick: id => { if (id.startsWith("x:")) location.hash = "code/" + enc(id.slice(2) + ":1"); else { const d = relIds.get(id); goLine(d.line); gr.select(id); } } });
  return { select: (d, l) => { const r = rules.find(x => l >= x.line && l <= x.end); gr.select(r ? r.head : d.kind === "relation" ? d.name : null, true); } };
}

function rewritePicture(file, box, head, goLine) {
  const rs = CAT.rewrites[file] || [];
  head.innerHTML = `What each rule matches and makes <span class="sub">${rs.length} rules · the number is how often it applied in your builds</span>`;
  let sec = null, html = "";
  for (const r of rs) {
    if (r.section !== sec) { sec = r.section; html += `<h2 class="sect">${esc(sec || "rules")}</h2>`; }
    const n = COUNTS[file + ":" + r.line];
    html += `<div class="rcard" data-l="${r.line}" id="R${r.line}"><div class="row"><b><code>${esc(r.name)}</code></b>${n ? `<a class="chip lc-rewrite" href="#rule/${enc(file + ":" + r.line)}">applied ${n.toLocaleString()}×</a>` : `<span class="faint">not applied yet</span>`}</div>
      <div class="row trees">${termTree(r.lhs)}<span class="faint">⇒</span>${termTree(r.rhs)}</div>${r.guards.length ? `<div class="row"><span class="faint">when</span>${r.guards.map(g => `<code class="k-host">${esc(g)}</code>`).join(" ")}</div>` : ""}</div>`;
  }
  box.innerHTML = `<div class="rgrid">${html}</div>`; box.classList.add("scroll");
  box.querySelectorAll(".rcard").forEach(c => c.onclick = e => { if (!e.target.closest("a")) goLine(+c.dataset.l); });
  return { select: d => { box.querySelectorAll(".rcard.sel").forEach(x => x.classList.remove("sel")); const c = $(`#R${d.line}`); if (c) { c.classList.add("sel"); c.scrollIntoView({ block: "nearest" }); } } };
}

function grammarPicture(file, box, head, goLine) {
  const prods = CAT.grammars[file];
  const ds = declsIn(file).filter(d => ["rule", "token", "fragment", "infix", "suffix", "postfix"].includes(d.kind));
  const ids = new Map(ds.map(d => [d.id, d]));
  const edges = [], seen = new Set();
  for (const [a, b] of CAT.edges) if (ids.has(a) && ids.has(b)) { const k = a + ">" + b; if (!seen.has(k)) { seen.add(k); edges.push({ from: "d" + a, to: "d" + b, label: "uses" }); } }
  box.innerHTML = `<div class="gsplit"><div class="gtop" id="gtop"></div><div class="gbottom" id="gbottom"><p class="empty">Click a production for its railroad.</p></div></div>`;
  head.innerHTML = `Which productions use which <span class="sub">${ds.length} productions · an arrow runs from a production to one it uses</span>`;
  const gr = drawGraph($("#gtop"), ds.map(d => ({ id: "d" + d.id, label: d.name, sub: d.kind === "rule" ? "" : d.kind, lang: "syntax", shape: d.kind === "rule" ? "" : "base" })), edges,
    { rankdir: "LR", ranksep: 50, nodesep: 4, onClick: id => { const d = CAT.decls[+id.slice(1)]; goLine(d.line); show(d); } });
  const show = d => { gr.select("d" + d.id, true); const p = prods && prods.find(x => x.name === d.name);
    $("#gbottom").innerHTML = p ? (p.body ? `<div class="row"><code>${esc(p.name)}</code><span class="faint">${esc(p.kind)}</span></div><div class="rr">${railroad(p.body)}</div>` : p.levels ? `<div class="row"><code>${esc(p.name)}</code> operators, loosest first</div>${p.levels.map(l => `<div class="row"><span class="faint">${l.assoc}</span>${l.ops.map(o => `<code>${esc(o.op)}</code><span class="k-kind">${esc(o.kind)}</span>`).join(" ")}</div>`).join("")}` : "") : `<p class="empty">${esc(d.name)} has no drawing.</p>`; };
  return { select: d => { if (ids.has(d.id)) show(d); } };
}

function pipelinePicture(file, box, head, goLine) {
  const P = CAT.pipeline;
  const nodes = [], edges = [];
  for (const m of P.mechanisms) { nodes.push({ id: "m:" + m.name, label: m.name, sub: "mechanism", lang: "pipeline", title: m.doc }); const f = m.body.find(l => l.startsWith("from ")); if (f) edges.push({ from: "m:" + f.slice(5), to: "m:" + m.name, label: "from" }); }
  for (const s of P.strategies) { nodes.push({ id: "s:" + s.name, label: s.name, sub: "strategy", lang: "rules", title: s.doc, shape: "ext" }); const f = s.body.find(l => l.startsWith("from ")); if (f) edges.push({ from: "s:" + f.slice(5), to: "s:" + s.name, label: "from" });
    const u = s.body.find(l => l.startsWith("uses ")); if (u) edges.push({ from: "m:" + u.slice(5), to: "s:" + s.name, label: "uses", dashed: true });
    for (const l of s.body.filter(l => l.startsWith("keep with "))) { const m = l.split(/\s+/)[2]; edges.push({ from: "m:" + m, to: "s:" + s.name, dashed: true, label: "keeps with" }); } }
  const plans = P.plans.map(p => ({ name: p.name, par: Object.fromEntries(p.body.filter(l => / parallel/.test(l)).map(l => { const [s, , n] = l.split(/\s+/); return [s, n || "∥"]; })) }));
  head.innerHTML = `How work is kept and divided <span class="sub">mechanisms and strategies · stages under each plan</span>`;
  box.innerHTML = `<div class="gsplit"><div class="gtop" id="ptop"></div><div class="gbottom scroll"><table class="t matrix"><thead><tr><th>stage</th><th>per</th>${plans.map(p => `<th>${esc(p.name)}</th>`).join("")}</tr></thead><tbody>${P.stages.map(s => `<tr data-l="${s.line}"><td><code>${esc(s.name)}</code></td><td class="faint">${esc(s.per)}</td>${plans.map(p => `<td class="${p.par[s.name] ? "par" : "ser"}">${p.par[s.name] ? esc(p.par[s.name]) : "·"}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div>`;
  const byName = new Map([...P.mechanisms.map(m => ["m:" + m.name, m]), ...P.strategies.map(s => ["s:" + s.name, s])]);
  const gr = drawGraph($("#ptop"), nodes, edges, { rankdir: "LR", ranksep: 60, onClick: id => { goLine(byName.get(id).line); gr.select(id); } });
  box.querySelectorAll("tr[data-l]").forEach(r => r.onclick = () => goLine(+r.dataset.l));
  return { select: (d, l) => { const hit = [...byName.entries()].find(([, v]) => v.line === d.line); if (hit) gr.select(hit[0], true); } };
}

function scopesPicture(file, box, head, goLine) {
  const nodes = new Map(), edges = [];
  const node = (id, label, sub, lang, shape) => { if (!nodes.has(id)) nodes.set(id, { id, label, sub, lang, shape }); return id; };
  const ds = declsIn(file);
  for (const d of ds) {
    const words = d.name.split(/\s+/);
    if (d.kind === "scope") { const kind = words[0]; node("k:" + kind, kind, "a kind of scope", "scopes"); for (const w of words.slice(1)) edges.push({ from: node("n:" + w, w, "", "syntax", "ext"), to: "k:" + kind, label: "opens a " + kind + " scope (line " + d.line + ")" }); }
    if (d.kind === "names" || d.kind === "name") { const at = words.indexOf("in"); if (at < 0) continue; const kinds = words.slice(at + 1); for (const w of words.slice(0, at)) for (const k of kinds) edges.push({ from: node("n:" + w, w, "", "syntax", "ext"), to: node("k:" + k, k, "a kind of scope", "scopes"), dashed: true, label: (d.kind === "names" ? "names land in " : "its name lands in ") + k + " (line " + d.line + ")" }); }
  }
  head.innerHTML = `Which nodes open scopes, and where names land <span class="sub">solid: opens · dashed: names land in</span>`;
  const gr = drawGraph(box, [...nodes.values()], edges, { rankdir: "LR", ranksep: 120, nodesep: 4, onClick: id => { if (id.startsWith("n:")) { const k = kindDecl(id.slice(2)); if (k) location.hash = "focus/" + k.id; } gr.select(id); } });
  return { select: () => {} };
}

// ------------------------------------------------------------ one declaration in the middle

MORE.focus = function (main, rest) {
  const d = CAT.decls[+rest[0]];
  if (!d) throw new Error("no declaration " + rest[0]);
  const into = new Map(), outof = new Map();
  for (const [a, b, label] of CAT.edges) {
    if (b === d.id) into.set(a, label); if (a === d.id) outof.set(b, label);
  }
  const LIMIT = 28;
  const nodes = new Map(), edges = [];
  const add = (x, extra = {}) => { const dd = CAT.decls[x]; if (!nodes.has(x)) nodes.set(x, Object.assign({ id: String(x), label: dd.name.length > 34 ? dd.name.slice(0, 32) + "…" : dd.name, sub: baseOf(dd.file) + (dd.kind === "fn" ? "" : " · " + dd.kind), lang: dd.kind === "node kind" ? "syntax" : langOf(dd.file), title: dd.name + "\n" + dd.file + ":" + dd.line }, extra)); };
  add(d.id, { shape: "" });
  // Node kinds a declaration matches or makes are many and alike: one node says how many.
  const kindsOut = [...outof.keys()].filter(x => CAT.decls[x].kind === "node kind");
  for (const x of kindsOut) outof.delete(x);
  const ins = [...into.entries()].slice(0, LIMIT), outs = [...outof.entries()].slice(0, LIMIT);
  if (kindsOut.length) { nodes.set("kinds", { id: "kinds", label: kindsOut.length + " node kinds", sub: kindsOut.slice(0, 6).map(x => CAT.decls[x].name).join(" ") + (kindsOut.length > 6 ? " …" : ""), lang: "syntax", shape: "ext", title: kindsOut.map(x => CAT.decls[x].name).join(", ") }); edges.push({ from: String(d.id), to: "kinds", label: "matches" }); }
  for (const [x, l] of ins) { add(x); edges.push({ from: String(x), to: String(d.id), label: EDGE_WORD[l] || l }); }
  for (const [x, l] of outs) { add(x); edges.push({ from: String(d.id), to: String(x), label: EDGE_WORD[l] || l }); }
  // A second step: who uses the callers, what the callees use, a few each.
  for (const [x] of ins.slice(0, 10)) { let k = 0; for (const [a, b, l] of CAT.edges) if (b === x && a !== d.id && k < 3) { k++; add(a, { dim: true }); edges.push({ from: String(a), to: String(x), label: EDGE_WORD[l] || l }); } }
  for (const [x] of outs.slice(0, 10)) { let k = 0; for (const [a, b, l] of CAT.edges) if (a === x && b !== d.id && k < 3) { k++; add(b, { dim: true }); edges.push({ from: String(x), to: String(b), label: EDGE_WORD[l] || l }); } }
  const lines = linesOf(d.file).slice(d.line - 1, Math.min(d.end || d.line, d.line + 60));
  const r = ruleAt(d.file + ":" + d.line);
  main.innerHTML = `<div class="page wide">
    <div class="crumbs"><a href="#map">The tower</a> / <a href="#code/${enc(d.file + ":" + d.line)}">${esc(short(d.file))}</a> /</div>
    <div class="row"><h1><code>${esc(d.name)}</code></h1><span class="tag lc-${d.kind === "node kind" ? "syntax" : langOf(d.file)}">${esc(d.kind)}</span>
      <span class="muted">used by ${into.size}${into.size > LIMIT ? ` (${LIMIT} shown)` : ""} · uses ${outof.size}${outof.size > LIMIT ? ` (${LIMIT} shown)` : ""}</span>
      <a class="btn small" href="#code/${enc(d.file + ":" + d.line)}">Open in its code</a>${(r.kind === "rewrite" || r.kind === "facts rule") ? `<a class="btn small" href="#rule/${enc(r.key)}">Where it applied</a>` : ""}</div>
    ${d.doc ? `<p class="lede">${esc(d.doc)}</p>` : ""}
    <div class="canvas focus" id="fg"></div>
    <section class="panel"><header><code>${esc(short(d.file))}:${d.line}</code></header><div class="codebody short" id="fcode">${lines.map((l, k) => `<div class="cl" data-l="${d.line + k}"><span class="n">${d.line + k}</span><span class="nofocus"></span><span class="t">${codeLine(l, d.file) || " "}</span></div>`).join("")}</div></section></div>`;
  const gr = drawGraph($("#fg"), [...nodes.values()], edges, { rankdir: "LR", ranksep: 110, nodesep: 6, minScale: 0.7, centerOn: String(d.id), onClick: (id, e) => { if (id === "kinds") return; location.hash = e.altKey || e.metaKey ? "code/" + enc(CAT.decls[+id].file + ":" + CAT.decls[+id].line) : "focus/" + id; } });
  gr.select(String(d.id));
  wireCode($("#fcode"), d.file);
};
