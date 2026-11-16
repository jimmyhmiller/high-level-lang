"use strict";
// The tower explorer's page. Everything it shows comes from the server (explorer/server.py): the
// catalog read from src/, builds made with `esb --record`, and the examples in explorer/examples.

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const enc = encodeURIComponent;
let CAT = null, COUNTS = {}, APPS = [], BUILDS = [];
const cache = {};

async function api(path, body) {
  const r = await fetch("/api/" + path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}
function toast(msg) { const t = document.createElement("div"); t.className = "toast"; t.textContent = msg; document.body.append(t); setTimeout(() => t.remove(), 2600); }

// ------------------------------------------------------------ the catalog: what a rule is

const LANG_NAME = { syntax: "Grammars", rules: "Rules", attrs: "Attribute grammars", facts: "Datalog", rewrite: "Rewrite rules", scopes: "Scopes", pipeline: "Pipeline", bundler: "Build specs", coil: "Coil" };
const langOf = f => (CAT.files[f] || {}).lang || (f.endsWith(".coil") ? "coil" : "rules");
const short = f => f.replace(/^src\//, "");
const linesCache = {};
const linesOf = f => linesCache[f] || (linesCache[f] = (CAT.files[f] ? CAT.files[f].text : "").split("\n"));

// A rule is named by its file and the line it starts on.
function ruleAt(key) {
  const i = key.lastIndexOf(":"), file = key.slice(0, i), line = +key.slice(i + 1);
  const rw = (CAT.rewrites[file] || []).find(r => r.line === line);
  if (rw) return { key, file, line, kind: "rewrite", name: rw.name, rw, decl: CAT.decls.find(d => d.file === file && d.line === line && d.kind === "rule") };
  const fr = (CAT.facts[file] || []).find(r => r.line === line);
  if (fr) return { key, file, line, kind: "facts rule", name: fr.head, fr };
  const ds = CAT.decls.filter(d => d.file === file && d.kind !== "node kind");
  let decl = null; for (const d of ds) if (d.line <= line) decl = d;
  if (decl) return { key: decl.file + ":" + decl.line, file, line: decl.line, kind: decl.kind, name: decl.name, decl };
  return { key, file, line, kind: "line", name: short(file) + ":" + line };
}
const ruleLink = (file, line, label) => `<a class="chip lc-${langOf(file)}" href="#rule/${enc(file + ":" + line)}" title="${esc(short(file))}:${line}">${esc(label || ruleAt(file + ":" + line).name)}</a>`;
const fileLink = (file, line, label) => `<a class="chip lc-${langOf(file)}" href="#${CAT.files[file] ? "code" : "file"}/${enc(file + ":" + (line || 1))}">${esc(label || short(file) + (line ? ":" + line : ""))}</a>`;

// ------------------------------------------------------------ highlighting

const KW = "fn match with where for in if then else let var some none and or not is first last any all count sum fold scan distinct while record enum boxed setting use as rules over everywhere return memo on inh syn input attrs rewrite problem relation facts rule when host leaves syntax start space token fragment hidden infix suffix postfix left right scopes scope names name outside of program sequential dynamic pipeline mechanism strategy stage plan size end store check cutoff evict keep uses tracks persists per whole makes defn let cond do match".split(" ");
const KWS = new Set(KW);
function hiLine(line) {
  let out = "", i = 0;
  while (i < line.length) {
    const c = line[i];
    if (c === "#" || (c === ";" && line[i + 1] === ";")) { out += `<span class="k-com">${esc(line.slice(i))}</span>`; break; }
    if (c === '"' || c === "`") { let j = i + 1; while (j < line.length && line[j] !== c) j += line[j] === "\\" ? 2 : 1; out += `<span class="k-str">${esc(line.slice(i, j + 1))}</span>`; i = j + 1; continue; }
    const m = /^(@[\w-]+|[A-Za-z_][\w-]*[?!]?|\d+)/.exec(line.slice(i));
    if (m) { const w = m[0]; const cls = w[0] === "@" ? "k-host" : /^\d/.test(w) ? "k-num" : /^[A-Z]/.test(w) ? "k-kind" : KWS.has(w) ? "k-kw" : ""; out += cls ? `<span class="${cls}">${esc(w)}</span>` : esc(w); i += w.length; continue; }
    out += esc(c); i++;
  }
  return out;
}
const hiBlock = t => t.split("\n").map(hiLine).join("\n");

// ------------------------------------------------------------ drawings: railroads, trees

const CW = 7.22, BH = 22, AR = 9, VS = 9;
const tw = s => s.length * CW;
function rr(n) {
  switch (n.t) {
    case "term": return box("term", JSON.stringify(n.s).slice(1, -1) || "ε");
    case "nt": return box("nt", n.s);
    case "class": return box("cls", n.s.length > 26 ? n.s.slice(0, 24) + "…]" : n.s);
    case "any": return box("cls", "any byte");
    case "flag": return box("flag", n.s);
    case "seq": return seq(n.items.map(rr).concat(n.action ? [act(n.action)] : []));
    case "alt": return choice(n.opts.map(rr));
    case "opt": return choice([rr(n.x), skip()]);
    case "rep": { const l = loop(rr(n.x), n.sep); return n.min === 0 ? choice([l, skip()]) : l; }
    case "pred": return pred(n.op, rr(n.x));
  }
  return box("cls", "?");
}
function box(cls, label) { const w = tw(label) + 18; return { w, up: BH / 2, down: BH / 2, draw: (x, y) => `<g class="${cls}"${cls === "nt" ? ` data-nt="${esc(label)}"` : ""}><rect x="${x}" y="${y - BH / 2}" width="${w}" height="${BH}" rx="${cls === "term" || cls === "flag" ? 11 : 3}"/><text x="${x + w / 2}" y="${y}">${esc(label)}</text></g>` }; }
function act(a) { const l = "→ " + a.kind + (a.fields.length ? "(" + a.fields.join(", ") + ")" : ""); const w = tw(l) + 16; return { w, up: BH / 2, down: BH / 2, draw: (x, y) => `<g class="act"><rect x="${x}" y="${y - BH / 2}" width="${w}" height="${BH}" rx="4"/><text x="${x + w / 2}" y="${y}">${esc(l)}</text></g>` }; }
function skip() { return { w: 0, up: 0, down: 0, draw: () => "" }; }
function seq(items) {
  if (!items.length) return { w: 20, up: 0, down: 0, draw: (x, y) => `<path d="M${x} ${y}h20"/>` };
  const g = 12, w = items.reduce((a, i) => a + i.w, 0) + g * (items.length - 1);
  return { w, up: Math.max(...items.map(i => i.up)), down: Math.max(...items.map(i => i.down)), draw(x, y) { let s = "", cx = x; items.forEach((it, k) => { s += it.draw(cx, y); cx += it.w; if (k + 1 < items.length) { s += `<path d="M${cx} ${y}h${g}"/>`; cx += g; } }); return s; } };
}
function choice(opts) {
  const inner = Math.max(...opts.map(o => o.w)), w = inner + AR * 4, offs = [0];
  for (let k = 1; k < opts.length; k++) offs.push(offs[k - 1] + opts[k - 1].down + VS + Math.max(opts[k].up, 4));
  const last = opts.length - 1;
  return { w, up: opts[0].up, down: offs[last] + opts[last].down, draw(x, y) {
    let s = "";
    opts.forEach((o, k) => { const yy = y + offs[k], ox = x + AR * 2 + (inner - o.w) / 2;
      if (k === 0) s += `<path d="M${x} ${y}H${ox}"/><path d="M${ox + o.w} ${y}H${x + w}"/>`;
      else s += `<path d="M${x} ${y}q${AR} 0 ${AR} ${AR}V${yy - AR}q0 ${AR} ${AR} ${AR}H${ox}"/><path d="M${ox + o.w} ${yy}H${x + w - AR * 2}q${AR} 0 ${AR} -${AR}V${y + AR}q0 -${AR} ${AR} -${AR}"/>`;
      s += o.draw(ox, yy); });
    return s; } };
}
function loop(item, sep) {
  const sb = sep ? box("term", sep) : null, below = item.down + VS + (sb ? BH / 2 : 0), inner = Math.max(item.w, sb ? sb.w : 0), w = inner + AR * 2;
  return { w, up: item.up, down: below + (sb ? BH / 2 : 0) + 2, draw(x, y) {
    const ix = x + AR + (inner - item.w) / 2, ly = y + below;
    let s = `<path d="M${x} ${y}H${ix}"/><path d="M${ix + item.w} ${y}H${x + w}"/>` + item.draw(ix, y);
    s += `<path d="M${x + w - AR} ${y}q${AR} 0 ${AR} ${AR}V${ly - AR}q0 ${AR} -${AR} ${AR}H${x + AR}q-${AR} 0 -${AR} -${AR}V${y + AR}q0 -${AR} ${AR} -${AR}"/>`;
    if (sb) s += sb.draw(x + w / 2 - sb.w / 2, ly);
    return s; } };
}
function pred(op, x) {
  const label = op === "!" ? "not followed by" : "followed by", pad = 8, w = Math.max(x.w, tw(label) * .85) + pad * 2;
  return { w, up: x.up + 22, down: x.down + pad, draw(px, y) { const ix = px + (w - x.w) / 2;
    return `<g class="pred"><rect x="${px}" y="${y - x.up - 20}" width="${w}" height="${x.up + x.down + 20 + pad}" rx="5"/><text x="${px + w / 2}" y="${y - x.up - 10}">${label}</text></g><path d="M${px} ${y}H${ix}"/><path d="M${ix + x.w} ${y}H${px + w}"/>` + x.draw(ix, y); } };
}
function railroad(body) {
  const d = rr(body), m = 14, W = d.w + 2 * m + 20, H = d.up + d.down + 2 * m + 16, y = m + d.up + 8, x = m + 10;
  return `<svg class="railroad" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}"><path d="M${m} ${y - 8}v16M${m + 4} ${y - 8}v16M${m + 4} ${y}H${x}"/>${d.draw(x, y)}<path d="M${x + d.w} ${y}h10M${x + d.w + 10} ${y - 8}v16M${x + d.w + 14} ${y - 8}v16"/></svg>`;
}
function termTree(t) {
  const PX = 8, H = 20, VG = 22, HG = 8;
  const cls = n => n.n.startsWith("@") || n.n.startsWith("!@") ? "h" : n.n === "_" ? "w" : /^[A-Z]/.test(n.n) ? "k" : "v";
  function size(n) { n._own = tw(n.n) * .92 + PX * 2; const c = n.c || []; c.forEach(size); const cw = c.reduce((a, k) => a + k._w, 0) + HG * Math.max(0, c.length - 1); n._w = Math.max(n._own, cw); }
  function place(n, x, y) { n._x = x + n._w / 2; n._y = y; const c = n.c || []; const cw = c.reduce((a, k) => a + k._w, 0) + HG * Math.max(0, c.length - 1); let cx = x + (n._w - cw) / 2; c.forEach(k => { place(k, cx, y + H + VG); cx += k._w + HG; }); }
  t = JSON.parse(JSON.stringify(t)); size(t); place(t, 2, 2);
  let depth = 0; (function d(n, l) { depth = Math.max(depth, l); (n.c || []).forEach(k => d(k, l + 1)); })(t, 0);
  let L = "", N = "";
  (function w(n) { (n.c || []).forEach(k => { L += `<line x1="${n._x}" y1="${n._y + H}" x2="${k._x}" y2="${k._y}"/>`; w(k); });
    N += `<g class="${cls(n)}"><rect x="${n._x - n._own / 2}" y="${n._y}" width="${n._own}" height="${H}" rx="${cls(n) === "k" ? 4 : 10}"/><text x="${n._x}" y="${n._y + H / 2}">${esc(n.n)}</text></g>`; })(t);
  const W = t._w + 4, HH = (depth + 1) * (H + VG) - VG + 4;
  return `<svg class="tree" width="${W}" height="${HH}" viewBox="0 0 ${W} ${HH}">${L}${N}</svg>`;
}

// ------------------------------------------------------------ the frame

const PLACES = [["map", "Map"], ["code", "Code"], ["builds", "Builds"], ["rules", "Rules"], ["examples", "Examples"], ["languages", "Languages"]];
// Places another script adds (visual.js): name → function(main, rest).
const MORE = {};
function frame(active) {
  const nrules = Object.values(CAT.rewrites).reduce((a, r) => a + r.length, 0) + Object.values(CAT.facts).reduce((a, r) => a + r.length, 0);
  const counts = { map: Object.keys(CAT.files).length, builds: BUILDS.length, rules: nrules, examples: EXAMPLES.length, languages: CAT.languages.length };
  $("#nav").innerHTML = PLACES.map(([id, name]) => `<a href="#${id}" aria-current="${id === active ? "page" : "false"}">${name}<small>${counts[id] ?? ""}</small></a>`).join("");
  $("#recent").innerHTML = BUILDS.slice(0, 8).map(b => `<a href="#build/${enc(b.id)}" title="${esc(b.entry + " " + b.flags.join(" "))}">${esc(b.entry.replace(/^apps\//, ""))} <small>${esc(b.flags.join(" ") || "plain")}</small></a>`).join("") || `<span class="faint" style="padding:0 8px;font-size:12px">none yet</span>`;
}
let EXAMPLES = [], STATUS = {};
async function refresh() { [BUILDS, COUNTS, EXAMPLES, STATUS] = await Promise.all([api("builds"), api("rule-counts"), api("examples"), api("status")]); }
const stale = b => b.bundler && STATUS.bundler && b.bundler !== STATUS.bundler;
const sameKind = (x, y) => x.entry === y.entry && x.flags.join(" ") === y.flags.join(" ");

async function route() {
  // Each part of the address is encoded on its own (a module's path holds slashes).
  const h = location.hash.slice(1) || "map";
  const [place, ...rest] = h.split("/").map(decodeURIComponent);
  const main = $("#main");
  try {
    if (MORE[place]) { frame(place === "focus" ? "code" : place); return MORE[place](main, rest); }
    if (place === "builds") { frame("builds"); return pageBuilds(main); }
    if (place === "build") { frame("builds"); return pageBuild(main, rest); }
    if (place === "compare") { frame("builds"); return pageCompare(main, rest[0], rest[1]); }
    if (place === "rules") { frame("rules"); return pageRules(main); }
    if (place === "rule") { frame("rules"); return pageRule(main, rest.join("/")); }
    if (place === "examples") { frame("examples"); return pageExamples(main); }
    if (place === "languages") { frame("languages"); return pageLanguages(main); }
    if (place === "language") { frame("languages"); return pageLanguage(main, rest[0]); }
    if (place === "file") { frame(""); return pageFile(main, rest.join("/")); }
    main.innerHTML = `<div class="page"><p class="empty">Nothing at #${esc(h)}.</p></div>`;
  } catch (e) {
    main.innerHTML = `<div class="page"><div class="panel"><header>Something failed</header><div class="body"><pre class="code wrap">${esc(e.message)}</pre></div></div></div>`;
  }
}

// ------------------------------------------------------------ builds

const FLAG_SETS = [
  ["--minify-syntax", "minify syntax"], ["--minify-identifiers", "minify names"], ["--splitting", "split chunks (esm)"],
  ["--platform=node", "node"], ["--tree-shaking=false", "no tree shaking"], ["--sourcemap", "source map"],
];
function pageBuilds(main) {
  main.innerHTML = `<div class="page">
    <h1>Builds</h1>
    <p class="lede">A build is a real bundle of a real app, recorded: every statement and the rules that keep it, every rewrite and where it fired. Every rule's page collects its examples from the builds made here.</p>
    <section class="panel"><header>Run a build</header><div class="body">
      <div class="row"><label>Entry <select id="entry">${APPS.map(a => `<option value="${esc(a.entry)}">${esc(a.entry)} · ${Math.round(a.bytes / 1024 * 10) / 10} KB</option>`).join("")}</select></label>
        <label>Format <select id="format"><option value="">iife</option><option>--format=esm</option><option>--format=cjs</option></select></label>
        <label>Target <select id="target"><option value="">esnext</option><option>--target=es2015</option><option>--target=es2017</option><option>--target=es2020</option></select></label></div>
      <div class="row">${FLAG_SETS.map(([f, l]) => `<label class="check"><input type="checkbox" value="${f}" class="flag"${f === "--minify-syntax" ? " checked" : ""}> ${l}</label>`).join("")}</div>
      <div class="row"><input type="text" id="more" placeholder="more flags, e.g. --define:DEBUG=false" style="flex:1;min-width:240px"><button class="btn primary" id="run">Build and record</button><span id="running"></span></div>
    </div></section>
    <section class="panel"><header>Made so far <span class="sub">out/explorer/builds</span></header>
      ${BUILDS.some(stale) ? `<div class="body"><div class="row"><span class="muted">The bundler was rebuilt (${esc(STATUS.bundler)}) since some of these were made.</span><button class="btn" id="again-all">Build each again with it, and compare</button><span id="again-status"></span></div></div>` : ""}
      ${BUILDS.length ? `<div class="tablewrap"><table class="t"><thead><tr><th>Entry</th><th>Flags</th><th class="num">Output</th><th class="num">Statements kept</th><th class="num">Rewrites</th><th class="num">Time</th><th>Made</th></tr></thead><tbody>
      ${BUILDS.map(b => `<tr class="link" data-go="#build/${enc(b.id)}"><td><code>${esc(b.entry)}</code> ${stale(b) ? `<span class="tag" title="made by the bundler of ${esc(b.bundler)}">older bundler</span>` : ""}</td><td><code class="muted">${esc(b.flags.join(" ") || "—")}</code></td>
        ${b.ok ? `<td class="num">${(b.outputBytes / 1024).toFixed(1)} KB</td><td class="num">${b.statementsKept.toLocaleString()} / ${b.statementsTotal.toLocaleString()}</td><td class="num">${b.rewrites.toLocaleString()}</td>` : `<td colspan="3"><span class="tag bad">failed</span></td>`}
        <td class="num">${b.ms} ms</td><td class="faint">${esc(b.made)}</td></tr>`).join("")}</tbody></table></div>` : `<p class="empty">No builds yet. Run one above: every rule it touches gets real examples.</p>`}
    </section></div>`;
  wireRows(main);
  if ($("#again-all")) $("#again-all").onclick = async () => {
    const latest = []; for (const b of BUILDS) if (!latest.some(x => sameKind(x, b))) latest.push(b);
    const todo = latest.filter(stale); $("#again-all").disabled = true; const done = [];
    for (const [i, b] of todo.entries()) { $("#again-status").innerHTML = `<span class="spinner"></span> ${i + 1} of ${todo.length}: ${esc(b.entry)}`; const nb = await api("builds", { entry: b.entry, flags: b.flags }); done.push([b.id, nb.id, b.entry]); }
    await refresh(); pageBuilds(main);
    $("#again-status") && ($("#again-status").innerHTML = "");
    toast("Rebuilt " + done.length);
    main.querySelector(".lede").insertAdjacentHTML("afterend", `<section class="panel"><header>What the new bundler changed</header><div class="body">${done.map(([a, b, e]) => `<a class="chip" href="#compare/${enc(a)}/${enc(b)}">${esc(e)}</a>`).join(" ")}</div></section>`);
  };
  $("#run").onclick = async () => {
    const flags = [...main.querySelectorAll(".flag:checked")].map(x => x.value).concat([$("#format").value, $("#target").value].filter(Boolean), $("#more").value.split(/\s+/).filter(Boolean));
    if (flags.includes("--splitting") && !flags.some(f => f.startsWith("--format="))) flags.push("--format=esm");
    $("#run").disabled = true; $("#running").innerHTML = `<span class="spinner"></span> bundling ${esc($("#entry").value)}…`;
    try { const b = await api("builds", { entry: $("#entry").value, flags }); await refresh(); location.hash = "build/" + b.id; }
    catch (e) { $("#running").innerHTML = `<span class="tag bad">failed</span> ${esc(e.message)}`; $("#run").disabled = false; }
  };
}
function wireRows(el) { el.querySelectorAll("[data-go]").forEach(r => r.onclick = e => { if (!e.target.closest("a")) location.hash = r.dataset.go; }); }

async function pageBuild(main, rest) {
  const b = BUILDS.find(x => x.id === rest[0]);
  if (!b) throw new Error("no build " + rest[0]);
  if (rest[1] === "m") return pageModule(main, b, rest[2], rest.slice(3).join("/"));
  if (rest[1] === "out") return pageOutput(main, b);
  if (!b.ok) { main.innerHTML = `<div class="page"><h1>${esc(b.entry)} <span class="tag bad">failed</span></h1><pre class="code wrap">${esc(b.error)}</pre></div>`; return; }
  const mods = b.modules.filter(m => m.kind !== "runtime" || m.kept > 0).sort((x, y) => y.bytes - x.bytes || y.kept - x.kept);
  const maxb = Math.max(1, ...mods.map(m => m.bytes));
  const fired = Object.entries(b.rulesFired).sort((x, y) => y[1] - x[1]);
  main.innerHTML = `<div class="page">
    <div class="crumbs"><a href="#builds">Builds</a> /</div>
    <h1><code>${esc(b.entry)}</code> <small>${esc(b.flags.join(" ") || "no flags")} · ${esc(b.made)}</small></h1>
    <div class="stats">
      <div class="stat"><b>${(b.outputBytes / 1024).toFixed(1)} KB</b><span>output</span></div>
      <div class="stat"><b>${mods.length}</b><span>modules</span></div>
      <div class="stat"><b>${b.statementsKept.toLocaleString()} / ${b.statementsTotal.toLocaleString()}</b><span>statements kept</span></div>
      <div class="stat"><b>${b.rewrites.toLocaleString()}</b><span>rewrites fired</span></div>
      <div class="stat"><b>${fired.length}</b><span>rules applied</span></div>
      <div class="stat"><b>${b.ms} ms</b><span>with recording</span></div>
    </div>
    <div class="row"><a class="btn" href="#build/${enc(b.id)}/out">Read the output</a><button class="btn" id="again">Build again</button>
      ${BUILDS.filter(x => x.id !== b.id && x.ok && x.entry === b.entry).length ? `<label>Compare with <select id="cmp"><option value="">another build of ${esc(b.entry)}…</option>${BUILDS.filter(x => x.id !== b.id && x.ok && x.entry === b.entry).map(x => `<option value="${esc(x.id)}">${esc(x.made)} · ${esc(x.flags.join(" ") || "no flags")}</option>`).join("")}</select></label>` : ""}
      ${stale(b) ? `<span class="tag" title="made by the bundler of ${esc(b.bundler)}">made by an older bundler</span>` : ""}</div>
    <div class="grid2">
      <section class="panel"><header>What it holds <span class="sub">by bytes in the output · click a module for its statements and why</span></header>
        <div class="tablewrap"><table class="t"><thead><tr><th>Module</th><th class="num">Bytes</th><th style="width:22%"></th><th class="num">Kept</th><th class="num">Rewrites</th></tr></thead><tbody>
        ${mods.map(m => `<tr class="link" data-go="#build/${enc(b.id)}/m/${enc(m.path)}"><td><code>${esc(m.path)}</code> ${m.kind !== "esm" ? `<span class="tag">${m.kind}</span>` : ""}</td><td class="num">${m.bytes.toLocaleString()}</td><td><div class="bar" style="width:${100 * m.bytes / maxb}%"></div></td><td class="num">${m.kept} / ${m.statements}</td><td class="num">${m.rewrites}</td></tr>`).join("")}
        </tbody></table></div></section>
      <section class="panel"><header>Rules that did the work <span class="sub">times each applied here</span></header>
        <div class="tablewrap"><table class="t"><thead><tr><th>Rule</th><th>Where</th><th class="num">Times</th></tr></thead><tbody>
        ${fired.map(([k, n]) => { const r = ruleAt(k); return `<tr class="link" data-go="#rule/${enc(k)}"><td>${ruleLink(r.file, r.line, r.name)}</td><td class="muted"><code>${esc(short(r.file))}:${r.line}</code></td><td class="num">${n.toLocaleString()}</td></tr>`; }).join("")}
        </tbody></table></div></section>
    </div></div>`;
  wireRows(main);
  if ($("#cmp")) $("#cmp").onchange = e => { if (e.target.value) { const o = BUILDS.find(x => x.id === e.target.value); location.hash = o.made < b.made ? `compare/${o.id}/${b.id}` : `compare/${b.id}/${o.id}`; } };
  $("#again").onclick = async () => { $("#again").disabled = true; $("#again").textContent = "Building…"; const nb = await api("builds", { entry: b.entry, flags: b.flags }); await refresh(); location.hash = "build/" + nb.id; };
}

async function pageCompare(main, a, b) {
  const c = await api(`compare?a=${enc(a)}&b=${enc(b)}`);
  const delta = (x, y) => { const d = y - x; return `<span style="color:var(${d > 0 ? "--bad" : d < 0 ? "--good" : "--faint"})">${d > 0 ? "+" : ""}${d.toLocaleString()}</span>`; };
  const stmt = (bid, s) => `<div class="occ"><div class="row"><a class="chip" href="#build/${enc(bid)}/m/${enc(s.module)}/${enc(s.key)}">${esc(s.module)}:${s.line}</a></div><pre class="code wrap" style="max-height:110px">${esc(s.text)}</pre></div>`;
  main.innerHTML = `<div class="page"><div class="crumbs"><a href="#builds">Builds</a> /</div>
    <h1>What changed <small><code>${esc(c.a.entry)}</code> · ${esc(c.a.made)} → ${esc(c.b.made)}</small></h1>
    <p class="lede">From <a href="#build/${enc(c.a.id)}">the earlier build</a> (${esc(c.a.flags.join(" ") || "no flags")}, bundler of ${esc(c.a.bundler || "?")}) to <a href="#build/${enc(c.b.id)}">the later</a> (${esc(c.b.flags.join(" ") || "no flags")}, bundler of ${esc(c.b.bundler || "?")}).</p>
    <div class="stats"><div class="stat"><b>${delta(c.a.outputBytes, c.b.outputBytes)} B</b><span>output (${c.b.outputBytes.toLocaleString()})</span></div>
      <div class="stat"><b>${delta(c.a.statementsKept, c.b.statementsKept)}</b><span>statements kept</span></div>
      <div class="stat"><b>${delta(c.a.rewrites, c.b.rewrites)}</b><span>rewrites</span></div>
      <div class="stat"><b>${delta(c.a.ms, c.b.ms)} ms</b><span>time</span></div></div>
    <div class="grid2">
      <section class="panel"><header>Kept now, not before <span class="sub">${c.gained.length}</span></header><div class="body">${c.gained.map(s => stmt(c.b.id, s)).join("") || `<p class="muted">None.</p>`}</div></section>
      <section class="panel"><header>Kept before, not now <span class="sub">${c.lost.length}</span></header><div class="body">${c.lost.map(s => stmt(c.a.id, s)).join("") || `<p class="muted">None.</p>`}</div></section>
    </div>
    <div class="grid2">
      <section class="panel"><header>Rules that applied more or less</header><div class="tablewrap"><table class="t"><thead><tr><th>Rule</th><th class="num">Before</th><th class="num">After</th><th class="num">Change</th></tr></thead><tbody>
        ${c.rules.map(d => { const r = ruleAt(d.key); return `<tr class="link" data-go="#rule/${enc(d.key)}"><td>${ruleLink(r.file, r.line, r.name)} <span class="faint">${esc(short(r.file))}:${r.line}</span></td><td class="num">${d.before}</td><td class="num">${d.after}</td><td class="num">${delta(d.before, d.after)}</td></tr>`; }).join("") || `<tr><td class="muted" colspan="4">The same counts.</td></tr>`}</tbody></table></div></section>
      <section class="panel"><header>Modules whose bytes changed</header><div class="tablewrap"><table class="t"><thead><tr><th>Module</th><th class="num">Before</th><th class="num">After</th><th class="num">Change</th></tr></thead><tbody>
        ${c.modules.map(d => `<tr class="link" data-go="#build/${enc(c.b.id)}/m/${enc(d.path)}"><td><code>${esc(d.path)}</code></td><td class="num">${d.before.toLocaleString()}</td><td class="num">${d.after.toLocaleString()}</td><td class="num">${delta(d.before, d.after)}</td></tr>`).join("") || `<tr><td class="muted" colspan="4">The same bytes.</td></tr>`}</tbody></table></div></section>
    </div></div>`;
  wireRows(main);
}

async function pageOutput(main, b) {
  const out = await api("build/output?id=" + enc(b.id));
  main.innerHTML = `<div class="page"><div class="crumbs"><a href="#builds">Builds</a> / <a href="#build/${enc(b.id)}">${esc(b.entry)}</a> /</div><h1>Output</h1>
    ${out.files.map(f => `<section class="panel"><header><code>${esc(f.path)}</code><span class="sub">${f.text.length.toLocaleString()} bytes</span></header><pre class="code wrap" style="max-height:75vh">${esc(f.text)}</pre></section>`).join("")}</div>`;
}

async function moduleOf(b, path) { const k = b.id + "|" + path; return cache[k] || (cache[k] = await api(`build/module?id=${enc(b.id)}&path=${enc(path)}`)); }

async function pageModule(main, b, path, selKey) {
  const m = await moduleOf(b, path);
  const rwIn = st => m.rewrites.filter(r => r.lo >= st.lo && r.lo < st.hi);
  let html = "", at = 0;
  const sts = [...m.statements].sort((x, y) => x.lo - y.lo);
  for (const st of sts) {
    if (st.lo > at) { const gap = m.source.slice(at, st.lo); if (gap.trim()) html += `<div class="gap">${esc(gap.trim())}</div>`; }
    const n = rwIn(st).length;
    html += `<div class="stmt ${st.kept ? "kept" : "dropped"}${st.key === selKey ? " sel" : ""}" data-key="${esc(st.key)}">${n ? `<span class="rw chip lc-rewrite" title="rewrites that fired here">${n}</span>` : ""}${esc(m.source.slice(st.lo, st.hi))}</div>`;
    at = Math.max(at, st.hi);
  }
  const kept = sts.filter(s => s.kept).length;
  main.innerHTML = `<div class="page">
    <div class="crumbs"><a href="#builds">Builds</a> / <a href="#build/${enc(b.id)}">${esc(b.entry)}</a> /</div>
    <h1><code>${esc(path)}</code> <small>${kept} of ${sts.length} statements kept · ${m.rewrites.length} rewrites</small></h1>
    <div class="split"><section class="panel"><header>Source <span class="sub">green: kept · grey: not in the output · click a statement</span></header><div class="source" id="src">${html}</div></section>
      <aside class="panel sticky" id="detail"><header>A statement</header><div class="body"><p class="empty">Click a statement for why it is in the output, or why not, and what the rewrite rules did to it.</p></div></aside></div></div>`;
  const show = key => { const st = sts.find(s => s.key === key); if (!st) return;
    main.querySelectorAll(".stmt.sel").forEach(x => x.classList.remove("sel")); const el = main.querySelector(`.stmt[data-key="${CSS.escape(key)}"]`); if (el) { el.classList.add("sel"); }
    $("#detail").innerHTML = statementDetail(b, m, st, rwIn(st)); wireStatement(b, m, st); };
  main.querySelectorAll(".stmt").forEach(el => el.onclick = () => { history.replaceState(null, "", `#build/${enc(b.id)}/m/${enc(path)}/${enc(el.dataset.key)}`); show(el.dataset.key); });
  if (selKey) { show(selKey); const el = main.querySelector(".stmt.sel"); if (el) el.scrollIntoView({ block: "center" }); }
}

// A fact's argument, said as the ledger says it: a statement or module is a link into this build.
function argHTML(b, a) {
  const kind = a.slice(0, 2), v = a.slice(2);
  if (kind === "p:") { const i = v.indexOf("#"); const mod = v.slice(0, i); return `<span class="arg"><a href="#build/${enc(b.id)}/m/${enc(mod)}/${enc(v)}" title="${esc(v)}">${esc(v.slice(i + 1))}</a></span>`; }
  if (kind === "m:") return `<span class="arg"><a href="#build/${enc(b.id)}/m/${enc(v)}">${esc(v)}</a></span>`;
  if (kind === "s:") return `<span class="arg" title="${esc(v)}">${esc(v.split("::").pop())}</span>`;
  if (kind === "n:") return `<span class="arg">"${esc(v)}"</span>`;
  return `<span class="arg">${esc(v)}</span>`;
}
function statementDetail(b, m, st, rws) {
  const text = m.source.slice(st.lo, st.hi);
  const why = st.why.length ? `<ul class="deriv">${st.why.map(w => `<li style="padding-left:${w.depth * 16}px"><span class="f"><span class="rel">${esc(w.relation)}</span>(${w.args.map(a => argHTML(b, a)).join(", ")})</span>${w.line > 0 ? ruleLink(m.rulesFile, w.line, "link.facts:" + w.line) : `<span class="faint">given</span>`}</li>`).join("")}</ul>`
    : `<p class="muted">No rule of <code>link.facts</code> derives <code>active-part</code> for it: nothing kept reads what it declares, and it has no effect of its own.</p>`;
  return `<header><span class="tag ${st.kept ? "good" : ""}">${st.kept ? "kept" : "not in the output"}</span><code style="font-weight:400">${esc(st.key)}</code></header><div class="body">
    <pre class="code wrap" style="max-height:180px">${esc(text)}</pre>
    <h2>Why ${st.kept ? "it is kept" : "it is not"}</h2>${why}
    <h2>What the rewrite rules did <small>${rws.length}</small></h2>
    ${rws.length ? rws.map(r => `<div class="occ"><div class="row">${ruleLink(r.file, r.ruleline, r.rule)}<span class="faint">${esc(short(r.file))}:${r.ruleline}</span></div><div class="ba"><pre>${esc(r.before)}</pre><span class="arrow">→</span><pre>${esc(r.after)}</pre></div></div>`).join("") : `<p class="muted">None fired on it${b.flags.some(f => f.startsWith("--minify")) ? "" : " (minifying runs most of them)"}.</p>`}
    <h2>Keep it as an example</h2>
    <div class="row"><select id="pinrule">${[...new Map(rws.map(r => [r.file + ":" + r.ruleline, r.rule])).entries()].map(([k, n]) => `<option value="${esc(k)}">${esc(n)}</option>`).join("")}${[...new Set(st.why.filter(w => w.line > 0).map(w => w.line))].map(l => `<option value="${esc(m.rulesFile + ":" + l)}">link.facts:${l} ${esc((st.why.find(w => w.line === l) || {}).relation || "")}</option>`).join("")}</select><button class="btn small" id="pin">Make an example of this statement</button></div>
  </div>`;
}
function wireStatement(b, m, st) {
  const pin = $("#pin"); if (!pin) return;
  pin.onclick = () => { const k = $("#pinrule").value; if (!k) { toast("No rule applied here to make an example for"); return; }
    draftExample(k, m.source.slice(st.lo, st.hi), b, `${m.path}, ${st.key.split("#").pop()}`); };
}

// ------------------------------------------------------------ rules

function pageRules(main) {
  const q = (sessionStorage.getItem("rulesq") || "");
  const groups = [];
  for (const [f, rs] of Object.entries(CAT.rewrites)) groups.push({ file: f, items: rs.map(r => ({ key: f + ":" + r.line, name: r.name, sub: r.section, text: r.src })) });
  for (const [f, rs] of Object.entries(CAT.facts)) if (rs.length) groups.push({ file: f, items: rs.map(r => ({ key: f + ":" + r.line, name: r.head, sub: "", text: r.text })) });
  const other = {};
  for (const d of CAT.decls) if (["fn", "on", "rule", "stage", "mechanism", "strategy", "scope", "names", "name"].includes(d.kind) && !(d.lang === "rewrite") && d.kind !== "node kind")
    (other[d.file] ||= []).push({ key: d.file + ":" + d.line, name: d.name, sub: d.kind, text: d.doc });
  for (const [f, items] of Object.entries(other)) groups.push({ file: f, items });
  const order = ["rewrite", "facts", "attrs", "rules", "scopes", "pipeline", "syntax", "bundler"];
  groups.sort((a, b) => order.indexOf(langOf(a.file)) - order.indexOf(langOf(b.file)) || a.file.localeCompare(b.file));
  const draw = () => {
    const qq = $("#rq").value.trim().toLowerCase(); sessionStorage.setItem("rulesq", qq);
    $("#rlist").innerHTML = groups.map(g => { const items = g.items.filter(i => !qq || i.name.toLowerCase().includes(qq) || (i.text || "").toLowerCase().includes(qq));
      if (!items.length) return ""; const fired = items.reduce((a, i) => a + (COUNTS[i.key] || 0), 0);
      return `<details${qq || fired ? " open" : ""}><summary><span class="tag lc-${langOf(g.file)}">${esc(LANG_NAME[langOf(g.file)])}</span> <code>${esc(short(g.file))}</code> <span class="faint">${items.length} · applied ${fired.toLocaleString()} times in your builds</span></summary>
        <table class="t"><tbody>${items.map(i => `<tr class="link" data-go="#rule/${enc(i.key)}"><td style="width:28%">${ruleLink(i.key.slice(0, i.key.lastIndexOf(":")), +i.key.slice(i.key.lastIndexOf(":") + 1), i.name)} <span class="faint">${esc(i.sub || "")}</span></td><td class="muted"><code>${esc((i.text || "").slice(0, 140))}</code></td><td class="num">${COUNTS[i.key] ? COUNTS[i.key].toLocaleString() : "<span class='faint'>—</span>"}</td></tr>`).join("")}</tbody></table></details>`; }).join("");
    wireRows($("#rlist"));
  };
  main.innerHTML = `<div class="page"><h1>Rules</h1><p class="lede">Every rule the bundler is written in. The number is how many times it applied across your builds; rewrite rules and linking's Datalog rules are recorded, the other languages are listed with what refers to them.</p>
    <input type="search" id="rq" placeholder="Find a rule by name or text" value="${esc(q)}" style="max-width:420px"><div id="rlist" style="display:flex;flex-direction:column;gap:8px"></div></div>`;
  $("#rq").oninput = draw; draw();
}

async function pageRule(main, key) {
  const r = ruleAt(key);
  const occ = await api("rule?key=" + enc(r.key));
  const exs = EXAMPLES.filter(e => e.rule.file + ":" + e.rule.line === r.key);
  const lines = linesOf(r.file);
  const end = r.decl ? r.decl.end : r.fr ? r.fr.end : r.rw ? r.line + (r.rw.src.length > 100 ? 3 : 0) : r.line;
  const src = lines.slice(r.line - 1, Math.max(r.line, end)).join("\n");
  const doc = r.decl && r.decl.doc;
  const lang = CAT.languages.find(l => l.key === langOf(r.file));
  const refs = r.decl && CAT.refs[r.decl.id];
  const total = occ.reduce((a, o) => a + o.count, 0);
  const picture = r.rw ? `<div class="row" style="overflow-x:auto">${termTree(r.rw.lhs)}<span class="faint" style="font-size:18px">⇒</span>${termTree(r.rw.rhs)}</div>${r.rw.guards.length ? `<div class="row"><span class="faint">when</span>${r.rw.guards.map(g => `<code class="k-host">${esc(g)}</code>`).join(" ")}</div>` : ""}` : "";
  main.innerHTML = `<div class="page">
    <div class="crumbs"><a href="#rules">Rules</a> / ${fileLink(r.file, r.line)}</div>
    <h1><code>${esc(r.name)}</code> <span class="tag lc-${langOf(r.file)}">${esc(r.kind)}</span> <small>applied ${total.toLocaleString()} times in ${occ.length} of ${BUILDS.filter(b => b.ok).length} builds</small></h1>
    ${doc ? `<p class="lede">${esc(doc)}</p>` : ""}
    <div class="grid2">
      <section class="panel"><header>What it is <span class="sub">${esc(short(r.file))}:${r.line}</span></header><div class="body">
        <pre class="code">${hiBlock(src)}</pre>${picture}
        ${lang ? `<p class="muted">Written in <a href="#language/${lang.key}">${esc(lang.name)}</a>${lang.grammar ? `, whose grammar is ${fileLink(lang.grammar)}` : ""} and whose compiler is ${fileLink(lang.compiler)}.</p>` : ""}
        ${refs ? `<details><summary>What refers to it <span class="faint">${Object.values(refs).reduce((a, x) => a + x.length, 0)}</span></summary>${Object.entries(refs).map(([l, xs]) => `<p class="faint" style="margin-top:6px">${esc(l)}</p>${xs.slice(0, 40).map(x => `<div class="row">${fileLink(x.file, x.line)}<code class="muted">${esc(x.text.slice(0, 110))}</code></div>`).join("")}`).join("")}</details>` : ""}
      </div></section>
      <section class="panel"><header>Examples <span class="sub">kept in explorer/examples, run by <code>server.py --check</code></span></header><div class="body" id="exs">
        ${exs.map(exampleCard).join("") || `<p class="muted">None yet. Make one from a place below where it applied, or write one.</p>`}
        <div class="row"><button class="btn small" id="newex">Write an example</button>${exs.length ? `<button class="btn small" id="runex">Run these</button>` : ""}</div>
        <div id="editor"></div>
      </div></section>
    </div>
    <section class="panel"><header>Where it applied <span class="sub">real code from the builds you made</span></header><div class="body">
      ${occ.length ? occ.map(o => `<details open><summary><code>${esc(o.build.entry)}</code> <span class="faint">${esc(o.build.flags.join(" ") || "no flags")}</span> · <b>${o.count.toLocaleString()}</b> ${o.items[0] && o.items[0].kind === "derived" ? (o.count === 1 ? "fact" : "facts") : (o.count === 1 ? "time" : "times")}${o.count > o.items.length ? ` <span class="faint">(the first ${o.items.length} shown)</span>` : ""}</summary>
        ${o.items.slice(0, 60).map((it, i) => occurrence(o.build, it, i)).join("")}</details>`).join("")
        : `<p class="muted">It has not applied in any build yet.${r.kind === "rewrite" ? ` ${short(r.file).includes("minify") || short(r.file).includes("final") ? "Minify rules run with --minify-syntax." : ""} Run a build that would use it.` : r.kind === "facts rule" ? " Linking's rules are recorded for every build; run one." : " Only rewrite rules and linking's Datalog rules are recorded so far."}</p>`}
    </div></section></div>`;
  main.querySelectorAll("[data-pin]").forEach(btn => btn.onclick = async () => {
    const [bid, mod, lo] = btn.dataset.pin.split("|"); const b = BUILDS.find(x => x.id === bid); const m = await moduleOf(b, mod);
    const st = m.statements.find(s => +lo >= s.lo && +lo < s.hi) || m.statements.find(s => s.lo === +lo);
    draftExample(r.key, st ? m.source.slice(st.lo, st.hi) : "", b, `${mod}${st ? ", " + st.key.split("#").pop() : ""}`); });
  $("#newex").onclick = () => editor(r, { title: "", source: "", flags: ["--minify-syntax", "--tree-shaking=false"], note: "" });
  if ($("#runex")) $("#runex").onclick = () => runExamples(exs.map(e => e.id));
  main.querySelectorAll("[data-run]").forEach(x => x.onclick = () => runExamples([x.dataset.run]));
  if (pendingDraft && pendingDraft.key === r.key) { editor(r, pendingDraft.ex); pendingDraft = null; $("#editor").scrollIntoView({ block: "center" }); }
}
function occurrence(build, it, i) {
  const where = it.module ? `<a class="chip" href="#build/${enc(build.id)}/m/${enc(it.module)}${it.statement ? "/" + enc(it.statement) : ""}">${esc(it.module)}${it.line ? ":" + it.line : ""}</a>` : `<span class="faint">while loading</span>`;
  const pin = it.module ? `<button class="btn small" data-pin="${esc(build.id)}|${esc(it.module)}|${it.lo}">Make an example</button>` : "";
  if (it.kind === "rewrite") return `<div class="occ"><div class="row">${where}${pin}</div><div class="ba"><pre>${esc(it.before)}</pre><span class="arrow">→</span><pre>${esc(it.after)}</pre></div></div>`;
  return `<div class="occ"><div class="row"><code>${esc(it.fact)}</code><span class="faint">${it.uses} kept statement${it.uses === 1 ? "" : "s"} rest on it</span></div>
    ${it.text ? `<div class="row">${where}${pin}</div><pre class="code wrap" style="max-height:120px">${esc(it.text)}</pre>` : it.module ? `<div class="row">${where}</div>` : ""}</div>`;
}

// ------------------------------------------------------------ examples

let pendingDraft = null;
function draftExample(key, source, build, from) {
  const flags = build.flags.filter(f => !f.startsWith("--out")).concat(build.flags.includes("--tree-shaking=false") ? [] : ["--tree-shaking=false"]);
  pendingDraft = { key, ex: { title: "", source, flags, note: `From ${from} in ${build.entry}.` } };
  const target = "#rule/" + enc(key);
  if (location.hash === target) route(); else location.hash = target;
}
function editor(r, ex) {
  $("#editor").innerHTML = `<div class="panel" style="border-style:dashed"><div class="body">
    <label>What it shows <input type="text" id="ex-title" value="${esc(ex.title)}" placeholder="e.g. a strict comparison under ! flips" style="width:100%"></label>
    <label>Source, bundled as entry.js <textarea id="ex-source">${esc(ex.source)}</textarea></label>
    <label>Flags <input type="text" id="ex-flags" value="${esc(ex.flags.join(" "))}" style="width:100%"></label>
    <div class="row"><label class="check"><input type="checkbox" id="ex-fires" checked> the rule applies</label><label>output contains <input type="text" id="ex-contains" placeholder="optional"></label></div>
    <label>Note <input type="text" id="ex-note" value="${esc(ex.note)}" style="width:100%"></label>
    <div class="row"><button class="btn primary" id="ex-save">Save and run</button><button class="btn" id="ex-cancel">Cancel</button><span id="ex-status"></span></div></div></div>`;
  $("#ex-cancel").onclick = () => $("#editor").innerHTML = "";
  $("#ex-save").onclick = async () => {
    const title = $("#ex-title").value.trim() || "example";
    const expect = { fires: $("#ex-fires").checked }; if ($("#ex-contains").value) expect.output_contains = $("#ex-contains").value;
    $("#ex-status").innerHTML = `<span class="spinner"></span> saving and running…`;
    try {
      const { id } = await api("examples", { rule: { file: r.file, line: r.line, name: r.name }, title, source: $("#ex-source").value, flags: $("#ex-flags").value.split(/\s+/).filter(Boolean), note: $("#ex-note").value, expect });
      await api("examples/run", { id }); await refresh(); route(); toast("Saved explorer/examples/" + id + ".json");
    } catch (e) { $("#ex-status").innerHTML = `<span class="tag bad">${esc(e.message)}</span>`; }
  };
}
function status(ex) {
  if (!ex.last) return `<span class="status"><i></i>not run</span>`;
  return `<span class="status ${ex.last.passed ? "pass" : "fail"}"><i></i>${ex.last.passed ? "passes" : "fails"} · fired ${ex.last.fired}× · ${esc(ex.last.ran)}</span>`;
}
function exampleCard(ex) {
  return `<div class="occ"><div class="row"><b>${esc(ex.title)}</b>${status(ex)}<button class="btn small" data-run="${esc(ex.id)}">Run</button></div>
    ${ex.note ? `<p class="faint">${esc(ex.note)}</p>` : ""}
    <details><summary class="faint">source, flags and what it did</summary><pre class="code wrap">${esc(ex.source)}</pre><p class="muted"><code>${esc(ex.flags.join(" "))}</code> · expects the rule ${ex.expect.fires ? "to apply" : "not to apply"}${ex.expect.output_contains ? `, output containing <code>${esc(ex.expect.output_contains)}</code>` : ""}</p>
      ${ex.last ? (ex.last.error ? `<pre class="code wrap">${esc(ex.last.error)}</pre>` : `${ex.last.items.slice(0, 6).map(it => it.kind === "rewrite" ? `<div class="ba"><pre>${esc(it.before)}</pre><span class="arrow">→</span><pre>${esc(it.after)}</pre></div>` : `<code class="muted">${esc(it.fact)}</code>`).join("")}<p class="faint">output</p><pre class="code wrap" style="max-height:160px">${esc(ex.last.output)}</pre>`) : ""}</details></div>`;
}
async function runExamples(ids) { toast("Running " + ids.length + " example" + (ids.length === 1 ? "" : "s") + "…"); for (const id of ids) await api("examples/run", { id }); await refresh(); route(); }

function pageExamples(main) {
  const pass = EXAMPLES.filter(e => e.last && e.last.passed).length, fail = EXAMPLES.filter(e => e.last && !e.last.passed).length;
  main.innerHTML = `<div class="page"><h1>Examples <small>${pass} pass · ${fail} fail · ${EXAMPLES.length - pass - fail} not run</small></h1>
    <p class="lede">Each example is a small program and the rule it shows. It is bundled with its flags and checked that the rule applies (and, if it says, what the output holds). They live in <code>explorer/examples</code>; <code>python3 explorer/server.py --check</code> runs them all.</p>
    <div class="row"><button class="btn primary" id="runall">Run them all</button></div>
    <section class="panel"><div class="body">${EXAMPLES.map(ex => `<div class="occ"><div class="row">${ruleLink(ex.rule.file, ex.rule.line, ex.rule.name)}<b>${esc(ex.title)}</b>${status(ex)}</div>${ex.note ? `<p class="faint">${esc(ex.note)}</p>` : ""}</div>`).join("") || `<p class="empty">None yet. Open a rule, or a statement in a build, and make one.</p>`}</div></section></div>`;
  $("#runall").onclick = () => runExamples(EXAMPLES.map(e => e.id));
}

// ------------------------------------------------------------ languages: the tower itself

function pageLanguages(main) {
  main.innerHTML = `<div class="page"><h1>Languages</h1><p class="lede">The bundler is written in these. Each is defined by a grammar written in the grammar language, and compiled to Coil by a compiler in <code>compiler/hl</code> that knows nothing about bundling. The grammar language itself is the bootstrap: its parser is written by hand.</p>
    <div class="grid2">${CAT.languages.map(l => `<a class="panel" href="#language/${l.key}" style="text-decoration:none"><header><span class="tag lc-${l.key}">${esc(l.name)}</span><span class="sub">${l.files.length} files · ${l.lines.toLocaleString()} lines</span></header><div class="body"><p class="muted">${esc(l.note)}</p><p class="faint">grammar ${l.grammar ? `<code>${esc(l.grammar)}</code>` : "written by hand"} · compiler <code>${esc(l.compiler)}</code></p></div></a>`).join("")}</div></div>`;
}
function pageLanguage(main, key) {
  const l = CAT.languages.find(x => x.key === key);
  const prods = l.grammar ? (CAT.grammars[l.grammar] || []) : [];
  const used = new Map(l.productions.map(p => [p.name, p]));
  main.innerHTML = `<div class="page"><div class="crumbs"><a href="#languages">Languages</a> /</div>
    <h1><span class="tag lc-${l.key}" style="font-size:13px">${esc(l.name)}</span> <small>${l.files.length} files, ${l.lines.toLocaleString()} lines</small></h1>
    <p class="lede">${esc(l.note)}</p>
    <div class="row">${l.grammar ? `Grammar ${fileLink(l.grammar)}` : "Its grammar is the hand-written parser"} · Compiler ${fileLink(l.compiler)}</div>
    <section class="panel"><header>Written in it</header><div class="body"><div class="row">${l.files.map(f => fileLink(f)).join(" ")}</div></div></section>
    ${prods.filter(p => p.kind === "rule" && !p.mods.includes("hidden")).map(p => { const u = used.get(p.name);
      return `<section class="panel" id="p-${esc(p.name)}"><header><code>${esc(p.name)}</code>${fileLink(l.grammar, p.line)}<span class="sub">${u && u.count ? `used ${u.count.toLocaleString()} times in src/` : ""}</span></header><div class="body">
        <div class="rr">${p.body ? railroad(p.body) : ""}</div>
        ${u && u.uses.length ? `<details><summary class="muted">Where it is used <span class="faint">(lines starting with ${u.words.map(w => `<code>${esc(w)}</code>`).join(", ")})</span></summary>${u.uses.slice(0, 40).map(x => `<div class="row">${fileLink(x.file, x.line)}<code class="muted">${hiLine(x.text)}</code></div>`).join("")}</details>` : ""}
      </div></section>`; }).join("")}
  </div>`;
  main.querySelectorAll("[data-nt]").forEach(g => g.style.cursor = "pointer");
  main.querySelectorAll("[data-nt]").forEach(g => g.onclick = () => { const t = $(`#p-${CSS.escape(g.dataset.nt)}`); if (t) t.scrollIntoView({ behavior: "smooth" }); });
}

// ------------------------------------------------------------ any file

async function pageFile(main, spec) {
  const i = spec.lastIndexOf(":"); const file = i > 0 ? spec.slice(0, i) : spec; const line = i > 0 ? +spec.slice(i + 1) : 1;
  const text = CAT.files[file] ? CAT.files[file].text : (await api("file?path=" + enc(file))).text;
  const starts = new Map(); for (const d of CAT.decls) if (d.file === file && d.kind !== "node kind") starts.set(d.line, d);
  for (const r of CAT.rewrites[file] || []) starts.set(r.line, r); for (const r of CAT.facts[file] || []) starts.set(r.line, r);
  main.innerHTML = `<div class="page"><div class="crumbs"><a href="#languages">Languages</a> / <span>${esc(file)}</span></div><h1><code>${esc(short(file))}</code> <span class="tag lc-${langOf(file)}">${esc(LANG_NAME[langOf(file)] || "")}</span></h1>
    <p class="faint">Click a line that starts a rule or declaration to open it.</p>
    <div class="lines" id="lines" style="max-height:80vh">${text.split("\n").map((l, k) => `<div class="ln${k + 1 === line ? " at" : ""}${starts.has(k + 1) ? " decl" : ""}" data-l="${k + 1}"><span class="n">${k + 1}</span><span>${hiLine(l) || " "}</span></div>`).join("")}</div></div>`;
  main.querySelectorAll(".ln.decl").forEach(el => el.onclick = () => location.hash = "rule/" + file + ":" + el.dataset.l);
  const at = $(".ln.at"); if (at) { const box = $("#lines"); box.scrollTop = at.offsetTop - box.offsetTop - 120; }
}

// ------------------------------------------------------------ start

(async () => {
  $("#main").innerHTML = `<div class="page"><p class="muted"><span class="spinner"></span> Reading the tower…</p></div>`;
  [CAT, APPS] = await Promise.all([api("catalog"), api("apps")]);
  await refresh();
  window.addEventListener("hashchange", route);
  route();
})();
