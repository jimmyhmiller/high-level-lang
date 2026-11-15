// A TanStack Start build (benchmarks/tanstack-start) run as its server runs it, and checked in a
// headless browser: pages rendered on the server, hydrated, server functions called from the
// browser, an isomorphic function taking each side's branch, a route not found, and no server-only
// code in what the browser loads.
//
// usage: node tools/start-app-check.mjs SERVER-ENTRY CLIENT-DIR
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { spawn } from 'node:child_process';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const [entry, client] = [resolve(process.argv[2]), resolve(process.argv[3])];

let passed = 0;
const failures = [];
function check(ok, what) {
  if (ok) { passed++; console.log('ok  ', what); } else { failures.push(what); console.log('FAIL', what); }
}

const server = spawn('node', [join(root, 'tools/start-serve.mjs'), entry, client], { stdio: ['ignore', 'pipe', 'pipe'] });
let out = '';
server.stdout.on('data', (d) => { out += d; });
server.stderr.on('data', (d) => { out += d; });
const port = await new Promise((ok, fail) => {
  const deadline = Date.now() + 15000;
  const poll = setInterval(() => {
    const m = out.match(/listening on (\d+)/);
    if (m) { clearInterval(poll); ok(m[1]); }
    if (Date.now() > deadline || server.exitCode !== null) { clearInterval(poll); fail(new Error('the server did not start:\n' + out)); }
  }, 25);
});
const base = `http://127.0.0.1:${port}`;

const files = (dir) => readdirSync(dir).flatMap((f) => statSync(join(dir, f)).isDirectory() ? files(join(dir, f)) : [join(dir, f)]);
const browserCode = files(client).filter((f) => f.endsWith('.js')).map((f) => readFileSync(f, 'utf8')).join('\n');

const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const page = await browser.newPage();
const errors = [];
const calls = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(m.text()); });
// A file the page asks for and does not get is an error too (the console's own line for it is not);
// a page's own status is the server's answer, checked where it matters.
page.on('response', (r) => { if (r.status() >= 400 && !r.request().isNavigationRequest() && !r.url().endsWith('/favicon.ico')) errors.push(`${r.status()} ${new URL(r.url()).pathname}`); });
page.on('request', (r) => { if (r.url().includes('/_serverFn/')) calls.push(r.method() + ' ' + new URL(r.url()).pathname); });

async function text(id, want, ms = 6000) {
  const deadline = Date.now() + ms;
  for (;;) {
    const got = (await page.getByTestId(id).count()) ? await page.getByTestId(id).first().textContent() : null;
    if (got === want || (want instanceof RegExp && got !== null && want.test(got))) return got;
    if (Date.now() > deadline) return got;
    await page.waitForTimeout(30);
  }
}

try {
  const html = await (await fetch(base + '/')).text();
  check(html.includes('Start home') && /Server count: (<!-- -->)?0/.test(html), 'the server renders the home page, with its loader\'s server function\'s answer');
  check(/<script type="module"[^>]*src="\/[^"]+\.js"/.test(html) && /<link rel="stylesheet" href="\/[^"]+\.css"/.test(html),
        'the page it renders loads the client entry and the stylesheet the root route links');

  await page.goto(base + '/');
  await page.waitForFunction(() => self.$_TSR === undefined || self.$_TSR.hydrated, null, { timeout: 8000 }).catch(() => {});
  await page.getByTestId('add').click();
  check((await text('count', 'Server count: 1')) === 'Server count: 1', 'a server function called from the browser changes the server\'s state, and the page shows it');
  check(calls.some((c) => c.startsWith('POST /_serverFn/')), 'it is called over the server function protocol: ' + calls.join(', '));

  await page.getByRole('link', { name: 'About' }).click();
  check((await text('loaded', 'loaded in the browser')) === 'loaded in the browser', 'navigated to in the browser, an isomorphic function in a loader takes the browser\'s branch');
  await page.goto(base + '/about');
  check((await text('loaded', 'loaded on the server')) === 'loaded on the server', 'rendered on the server, it takes the server\'s');
  await page.getByTestId('where').click();
  check((await text('where', 'clicked in the browser')) === 'clicked in the browser', 'called in the browser after hydration, the browser\'s');

  await page.getByRole('link', { name: 'User 2' }).click();
  check((await text('title', 'User Grace')) === 'User Grace', 'a route\'s loader calls a server function with its params');
  await page.goto(base + '/users/9');
  check((await text('not-found', 'Nothing here')) === 'Nothing here', 'a server function throwing notFound() shows the not-found component');

  check(!browserCode.includes('SERVER_ONLY_SECRET_ROW') && !browserCode.includes('users[id]'),
        'the browser\'s code has none of the server-only module');
  const api = await fetch(base + '/api/hello');
  check(api.status === 200 && (await api.json()).hello === 'SERVER_ROUTE_SECRET', 'a route only the server has answers its request with its handler');
  check(!browserCode.includes('SERVER_ROUTE_SECRET'), '... and the browser\'s code has none of it');
  check(errors.length === 0, 'no errors: ' + errors.join(' | '));
} catch (e) {
  failures.push(String(e));
  console.log('FAIL', e, '\n', out.slice(-1500));
} finally {
  await browser.close();
  server.kill();
}
console.log(`start-app-check: ${passed} passed, ${failures.length} failed`);
process.exit(failures.length ? 1 : 0);
