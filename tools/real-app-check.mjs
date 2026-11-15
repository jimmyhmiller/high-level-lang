// A TanStack application built two ways (ours and Vite's) and every route without parameters visited
// in Chrome: what the server sends, what the page shows once loaded (hydrated, for Start), and the
// errors, compared. A Start build (DIR/client and DIR/server/server.js) runs as Start's server runs
// it (tools/start-serve.mjs); a Router build (DIR/index.html) is served as a single-page app's
// server serves it, every path that names no file answered with the page. The routes are the route
// tree's (`fullPaths` in its FileRoutesByFullPath interface), so nothing is chosen by hand.
//
// usage: node tools/real-app-check.mjs APP OURS-DIR VITE-DIR
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { spawn } from 'node:child_process';
import { readFileSync, existsSync } from 'node:fs';
import { readFile } from 'node:fs/promises';
import { createServer } from 'node:http';
import { resolve, join, extname } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const [app, ours, vite] = process.argv.slice(2).map((p) => resolve(p));

const tree = readFileSync(join(app, 'src/routeTree.gen.ts'), 'utf8');
const listed = tree.match(/fullPaths:\s*([^\n]*)/);
const paths = [...new Set((listed ? listed[1] : '').match(/'[^']*'/g)?.map((p) => p.slice(1, -1)) ?? ['/'])]
  .filter((p) => !p.includes('$') && !p.includes('*'));

// A single-page app's build: its files, and the page for any path that names none.
async function serveStatic(dir) {
  const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json' };
  const server = createServer(async (req, res) => {
    const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    const file = join(dir, path);
    try {
      if (!file.startsWith(dir) || path.endsWith('/')) throw new Error('page');
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' });
      res.end(body);
    } catch {
      if (extname(path) && extname(path) !== '.html') { res.writeHead(404); res.end(); return; }
      res.writeHead(200, { 'content-type': 'text/html' });
      res.end(await readFile(join(dir, 'index.html')));
    }
  });
  await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
  return { server: { kill: () => server.close() }, base: `http://127.0.0.1:${server.address().port}`, log: () => '' };
}

async function serve(dir) {
  if (existsSync(join(dir, 'index.html'))) return serveStatic(dir);
  const server = spawn('node', [join(root, 'tools/start-serve.mjs'), join(dir, 'server/server.js'), join(dir, 'client')], { cwd: app, stdio: ['ignore', 'pipe', 'pipe'] });
  let out = '';
  server.stdout.on('data', (d) => { out += d; });
  server.stderr.on('data', (d) => { out += d; });
  const port = await new Promise((ok, fail) => {
    const deadline = Date.now() + 20000;
    const poll = setInterval(() => {
      const m = out.match(/listening on (\d+)/);
      if (m) { clearInterval(poll); ok(m[1]); }
      if (Date.now() > deadline || server.exitCode !== null) { clearInterval(poll); fail(new Error('the server did not start:\n' + out)); }
    }, 25);
  });
  return { server, base: `http://127.0.0.1:${port}`, log: () => out };
}

const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
async function visit(base, path) {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e).split('\n')[0]));
  page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(m.text().split('\n')[0]); });
  page.on('response', (r) => { if (r.status() >= 400 && !r.request().isNavigationRequest() && !r.url().endsWith('/favicon.ico')) errors.push(`${r.status()} ${new URL(r.url()).pathname}`); });
  const status = (await fetch(base + path)).status;
  await page.goto(base + path, { waitUntil: 'load' });
  await page.waitForFunction(() => self.$_TSR === undefined || self.$_TSR.hydrated, null, { timeout: 8000 }).catch(() => errors.push('not hydrated'));
  await page.waitForTimeout(300);
  const text = (await page.evaluate(() => document.body.innerText)).replace(/\s+/g, ' ').trim();
  await page.close();
  return { status, text, errors };
}

let failures = 0;
const runs = [];
for (const dir of [ours, vite]) {
  const s = await serve(dir);
  const seen = {};
  for (const p of paths) seen[p] = await visit(s.base, p);
  s.server.kill();
  runs.push(seen);
}
for (const p of paths) {
  const [a, b] = [runs[0][p], runs[1][p]];
  const same = a.status === b.status && a.text === b.text;
  const clean = a.errors.length === 0 || a.errors.join() === b.errors.join();
  if (!same || !clean) failures++;
  console.log(`${same && clean ? 'ok  ' : 'FAIL'} ${p}: ${a.status} ${a.text.slice(0, 70)}${same ? '' : `\n       vite: ${b.status} ${b.text.slice(0, 70)}`}${clean ? '' : `\n       errors: ${a.errors.join(' | ')} (vite: ${b.errors.join(' | ') || 'none'})`}`);
}
await browser.close();
console.log(`real-app-check: ${paths.length - failures} of ${paths.length} routes as Vite's`);
process.exit(failures ? 1 : 0);
