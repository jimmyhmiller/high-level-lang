// Runs a built TanStack Router app (benchmarks/tanstack-router) in a headless browser and checks
// what each route shows, and which scripts each step loads: a route's component is loaded when the
// route is visited, not before.
//
// usage: node tools/router-app-check.mjs DIST [--split]
//   DIST holds index.html and what it loads; unknown paths are served index.html, as a single-page
//   app's server does. With --split, also check that route components arrive in their own scripts.
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, extname, join } from 'node:path';

const dist = resolve(process.argv[2]);
const split = process.argv.includes('--split');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.map': 'application/json' };

const server = createServer(async (req, res) => {
  const path = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const file = join(dist, path);
  try {
    if (!file.startsWith(dist)) throw new Error('outside');
    const body = await readFile(file);
    res.writeHead(200, { 'content-type': types[extname(file)] ?? 'application/octet-stream' });
    res.end(body);
  } catch {
    if (extname(path) && extname(path) !== '.html') { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'content-type': 'text/html' });
    res.end(await readFile(join(dist, 'index.html')));
  }
});
await new Promise((ok) => server.listen(0, ok));
const base = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const page = await browser.newPage();
const errors = [];
const scripts = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push('console: ' + m.text()); });
page.on('response', (r) => { if (r.status() >= 400 && !r.url().endsWith('/favicon.ico')) errors.push(`${r.status()} ${r.url()}`); });
page.on('request', (r) => { if (r.resourceType() === 'script') scripts.push(new URL(r.url()).pathname); });

let passed = 0;
const failures = [];
function check(ok, what) {
  if (ok) { passed++; console.log('ok  ', what); } else { failures.push(what); console.log('FAIL', what); }
}
// The text of the first element with the test id, once it is `want` (or what it is after 5 s).
async function text(id, want) {
  const el = page.getByTestId(id).first();
  const deadline = Date.now() + 5000;
  for (;;) {
    const got = (await page.getByTestId(id).count()) ? await el.textContent() : null;
    if (want === undefined ? got !== null : got === want || (want instanceof RegExp && got !== null && want.test(got))) return got;
    if (Date.now() > deadline) return got;
    await page.waitForTimeout(25);
  }
}
function since(n) { return scripts.slice(n); }

try {
  await page.goto(base + '/');
  check((await text('title', 'Welcome home')) === 'Welcome home', '/ shows the index route');
  await page.getByTestId('counter').click();
  await page.getByTestId('counter').click();
  check((await text('counter', 'clicks: 2')) === 'clicks: 2', 'the index route is interactive');
  const home = scripts.length;

  let before = scripts.length;
  await page.getByRole('link', { name: 'About' }).click();
  check((await text('title', 'About')) === 'About', 'a link to /about shows the about route');
  check(page.url() === base + '/about', 'the address is /about');
  if (split) check(since(before).length > 0, 'visiting /about loads a script it did not need before');

  before = scripts.length;
  await page.getByRole('link', { name: 'Posts' }).click();
  check((await text('title', 'Posts')) === 'Posts', '/posts shows its layout, with its loader\'s posts');
  check((await text('posts-index', 'Pick a post.')) === 'Pick a post.', '/posts/ shows the index under the layout');
  await page.getByRole('link', { name: 'Second post' }).click();
  check((await text('post-title', 'Second post')) === 'Second post', 'a post\'s link shows it, from its loader and params');

  await page.getByRole('link', { name: 'Dashboard' }).click();
  check((await text('title', 'Dashboard')) === 'Dashboard' && (await text('auth-layout')) !== null, 'a pathless layout wraps /dashboard');

  await page.getByRole('link', { name: 'Pricing' }).click();
  check((await text('title', 'Pricing: pro')) === 'Pricing: pro', 'a route group\'s route reads its validated search');

  await page.goto(base + '/pricing?plan=other');
  check((await text('title', 'Pricing: free')) === 'Pricing: free', 'loaded directly, search validation gives the default');

  await page.goto(base + '/posts/2');
  check((await text('post-title', 'Second post')) === 'Second post', 'a post loads directly at its address');

  const quiet = errors.length;
  await page.goto(base + '/posts/99');
  check(/post 99 not found/.test((await text('post-error', /post 99 not found/)) ?? ''),
    'a loader that throws shows the route\'s error component');
  errors.splice(quiet);

  await page.goto(base + '/nowhere');
  check((await text('not-found', 'Nothing here')) === 'Nothing here', 'an unknown address shows the root\'s not-found component');

  if (split) {
    const fresh = await browser.newPage();
    const first = [];
    fresh.on('request', (r) => { if (r.resourceType() === 'script') first.push(new URL(r.url()).pathname); });
    await fresh.goto(base + '/');
    await fresh.getByTestId('title').waitFor();
    const all = new Set(scripts);
    check(first.length < all.size, `/ loads ${first.length} of the ${all.size} scripts the app has`);
    await fresh.close();
  }
  check(errors.length === 0, 'no errors: ' + errors.join(' | '));
  void home;
} finally {
  await browser.close();
  server.close();
}
console.log(`router-app-check: ${passed} passed, ${failures.length} failed`);
process.exit(failures.length ? 1 : 0);
