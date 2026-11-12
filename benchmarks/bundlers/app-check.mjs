// A real application's build, run in Chrome: an HTML page holding its root element loads the entry
// script; any static files it needs are served beside the output (a service worker, say). Prints
// what the page shows once it has settled, the errors it threw, the requests that failed, and the
// output's JS files the first page asked for (`initial`, before any step) and in all (`loaded`), so
// builds of the same application by different bundlers can be compared.
//   node app-check.mjs OUTDIR ENTRY_FILE_IN_OUTDIR ROOT_ID WAIT_TEXT [STATIC_FILE...]
// APP_STEPS (JSON): what a person does first, as [["fill", selector, text] | ["click", selector] |
// ENTRY_FILE `turbopack`: Turbopack's CLI emits a bootstrap, not an entry module; the page loads the
// chunks it declares (`otherChunks`) and then it, with TURBOPACK_CHUNK_BASE_PATH set, as
// browser-check.mjs does.
// ["wait", text]...], such as signing in; WAIT_TEXT is then what the page must come to show. What the
// page shows once each wait is met is kept (`snapshots`): an application whose data does not change
// from one load to the next must show the same, however it was built.
import { chromium } from '../../tests/node_modules/playwright-core/index.mjs';
import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { parse } from '../../tests/node_modules/acorn/dist/acorn.mjs';
import { resolve, extname, basename } from 'node:path';
const [outArg, entry, rootId, waitText, ...statics] = process.argv.slice(2);
const output = resolve(outArg);
const types = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json', '.woff2': 'font/woff2' };
const extra = Object.fromEntries(statics.map((p) => ['/' + basename(p), resolve(p)]));
async function turbopackScripts() {
  const bootstraps = (await readdir(output)).filter((name) => /^turbopack-.*\.js$/.test(name));
  if (bootstraps.length === 0) throw new Error('Turbopack emitted no bootstrap');
  const initial = new Set();
  for (const name of bootstraps) {
    const tree = parse(await readFile(resolve(output, name), 'utf8'), { ecmaVersion: 'latest', sourceType: 'script' });
    const find = (node) => {
      if (!node || typeof node !== 'object') return null;
      if (node.type === 'ObjectExpression') {
        const p = node.properties.find((p) => (p.key?.name || p.key?.value) === 'otherChunks' && p.value.type === 'ArrayExpression');
        if (p) return p;
      }
      for (const v of Object.values(node)) {
        for (const child of Array.isArray(v) ? v : [v]) { if (child && typeof child === 'object') { const f = find(child); if (f) return f; } }
      }
      return null;
    };
    const other = find(tree);
    if (!other) throw new Error('Turbopack bootstrap has no static otherChunks declaration');
    for (const node of other.value.elements) {
      initial.add(node.type === 'Literal' ? node.value : node.properties.find((p) => (p.key.name || p.key.value) === 'path').value.value);
    }
  }
  return '<script>globalThis.TURBOPACK_CHUNK_BASE_PATH="/";</script>' + [...initial, ...bootstraps].map((n) => `<script src="/${n}"></script>`).join('');
}
const scripts = entry === 'turbopack' ? await turbopackScripts() : `<script type="module" src="/${entry}"></script>`;
const page = `<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><body><div id="${rootId}"></div>${scripts}`;
const loaded = [];
const server = createServer(async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  if (/\.m?js$/.test(path) && !extra[path] && !loaded.includes(path.slice(1))) loaded.push(path.slice(1));
  if (path === '/' || !extname(path)) { res.setHeader('Content-Type', 'text/html'); return res.end(page); }
  const file = extra[path] ?? resolve(output, path.slice(1));
  if (!extra[path] && !file.startsWith(output + '/')) { res.writeHead(403); return res.end(); }
  try { const body = await readFile(file); res.setHeader('Content-Type', types[extname(file)] || 'application/octet-stream'); res.end(body); }
  catch { res.writeHead(404); res.end(); }
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, timezoneId: 'UTC', locale: 'en-US' });
const tab = await ctx.newPage();
const errors = [], failed = [];
tab.on('pageerror', (e) => errors.push(String(e.message)));
tab.on('response', (r) => { if (r.status() >= 400) failed.push(r.status() + ' ' + new URL(r.url()).pathname); });
let ok = true, initial = [], step = 'loading the page';
const snapshots = [];
const shown = () => tab.evaluate(() => document.body.innerText);
try {
  await tab.goto(`http://127.0.0.1:${server.address().port}/`);
  await tab.waitForLoadState('networkidle');
  initial = [...loaded];
  for (const [what, a, b] of JSON.parse(process.env.APP_STEPS || '[]')) {
    step = `${what} ${a}`;
    if (what === 'fill') await tab.fill(a, b, { timeout: 30000 });
    else if (what === 'click') await tab.click(a, { timeout: 30000 });
    else if (what === 'wait') {
      await tab.waitForFunction((t) => document.body.innerText.includes(t), a, { timeout: 30000 });
      snapshots.push(await shown());
    }
  }
  step = `wait ${waitText}`;
  await tab.waitForFunction((t) => document.body.innerText.includes(t), waitText, { timeout: 30000 });
  await tab.waitForLoadState('networkidle');
  await tab.waitForTimeout(1500);
} catch (e) { ok = false; errors.push(`at ${step}: ${e.message.split('\n')[0]}`); }
const text = await shown();
process.stdout.write(JSON.stringify({ ok: ok && errors.length === 0, errors, failed, initial, loaded, snapshots, text }));
await browser.close();
server.close();
