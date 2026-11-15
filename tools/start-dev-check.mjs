// The TanStack Start application in development (`esb --tanstack-start --hmr --serve=0`), in a
// headless browser, while its files are edited: pages rendered by the server, the browser's code
// updated in place, and the server's answers coming from the server's code as it now is.
//
// usage: node tools/start-dev-check.mjs [ESB]
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { spawn } from 'node:child_process';
import { cpSync, rmSync, symlinkSync, readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const esb = resolve(process.argv[2] ?? join(root, 'out/bin/esb'));
const source = join(root, 'benchmarks/tanstack-start');
const work = join(root, 'out/start-dev-check');
const app = join(work, 'app');
rmSync(work, { recursive: true, force: true });
mkdirSync(work, { recursive: true });
cpSync(source, app, { recursive: true, filter: (p) => !/node_modules|dist|START-SPEC/.test(p.slice(source.length)) });
// Its own node_modules, of the fixture's packages, for what development writes there.
mkdirSync(join(app, 'node_modules'));
for (const name of readdirSync(join(source, 'node_modules'))) symlinkSync(join(source, 'node_modules', name), join(app, 'node_modules', name));

let passed = 0;
const failures = [];
function check(ok, what) {
  if (ok) { passed++; console.log('ok  ', what); } else { failures.push(what); console.log('FAIL', what); }
}

const server = spawn(esb, ['--tanstack-start', '--hmr', '--serve=0', '--no-cache'], { cwd: app });
let log = '';
server.stdout.on('data', (d) => { log += d; });
server.stderr.on('data', (d) => { log += d; });
const base = await new Promise((ok, fail) => {
  const deadline = Date.now() + 30000;
  const poll = setInterval(() => {
    const m = log.match(/listening on (http:\/\/localhost:\d+)/);
    if (m) { clearInterval(poll); ok(m[1]); }
    if (Date.now() > deadline || server.exitCode !== null) { clearInterval(poll); fail(new Error('the server did not start:\n' + log)); }
  }, 25);
});
const builds = () => (log.match(/\[watch\] build \d+/g) ?? []).length;

const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error' && !m.text().startsWith('Failed to load resource')) errors.push(m.text()); });
// A file the page asks for and does not get is an error too (the console's own line for it is not);
// a page's own status is the server's answer, checked where it matters.
page.on('response', (r) => { if (r.status() >= 400 && !r.request().isNavigationRequest() && !r.url().endsWith('/favicon.ico')) errors.push(`${r.status()} ${new URL(r.url()).pathname}`); });

async function text(id, want, ms = 8000) {
  const deadline = Date.now() + ms;
  for (;;) {
    const got = (await page.getByTestId(id).count()) ? await page.getByTestId(id).first().textContent() : null;
    if (got === want || (want instanceof RegExp && got !== null && want.test(got))) return got;
    if (Date.now() > deadline) return got;
    await page.waitForTimeout(30);
  }
}
const hydrated = () => page.waitForFunction(() => self.$_TSR === undefined || self.$_TSR.hydrated, null, { timeout: 8000 }).catch(() => {});
// An edit, and the build it makes: the page's marker says whether it reloaded.
async function edit(file, from, to) {
  const before = builds();
  await page.evaluate(() => { window.__kept = 'still here'; });
  const path = join(app, file);
  const was = from === null ? '' : readFileSync(path, 'utf8');
  if (from !== null && !was.includes(from)) throw new Error(file + ' has no ' + from);
  writeFileSync(path, from === null ? to : was.replace(from, to));
  const deadline = Date.now() + 15000;
  while (builds() === before && Date.now() < deadline) await new Promise((r) => setTimeout(r, 25));
  await page.waitForTimeout(400);
}
const kept = () => page.evaluate(() => window.__kept === 'still here');
const served = async (path) => (await fetch(base + path)).text();

try {
  const html = await served('/');
  check(html.includes('Start home') && /Server count: (<!-- -->)?0/.test(html) && html.includes('src="/assets/index.js"'),
        'the server renders the home page, which loads the development bundle');

  await page.goto(base + '/');
  await hydrated();
  check(await page.evaluate(() => getComputedStyle(document.body).fontFamily.includes('system-ui')), 'the root route\'s stylesheet is in the page');
  await page.getByTestId('add').click();
  check((await text('count', 'Server count: 1')) === 'Server count: 1', 'a server function called from the browser answers');

  await edit('src/routes/index.tsx', 'Start home', 'Start, edited');
  check((await text('title', 'Start, edited')) === 'Start, edited' && await kept(), 'a route file edited updates its route in place');
  check((await text('add', 'Add one (1)')) === 'Add one (1)', '... and its component keeps its state (Fast Refresh)');
  check((await served('/')).includes('Start, edited'), '... and the server renders it as edited');

  await edit('src/server/store.ts', 'count += by;', 'count += by * 10;');
  await page.getByTestId('add').click();
  check(/^Server count: (10|11)$/.test(await text('count', /^Server count: 1\d$/)), 'a server-only module edited: the server function runs it as edited');
  check(await kept(), '... and the page was not reloaded');

  await edit('src/styles.css', 'margin: 2rem;', 'margin: 2rem; color: rgb(1, 2, 3);');
  const color = async () => page.evaluate(() => getComputedStyle(document.body).color);
  for (let i = 0; i < 100 && (await color()) !== 'rgb(1, 2, 3)'; i++) await page.waitForTimeout(50);
  check((await color()) === 'rgb(1, 2, 3)' && await kept(), 'the root route\'s stylesheet edited is replaced in the page');
  check((await served('/')).match(/href="(\/assets\/styles-[^"]+)"/) && (await (await fetch(base + (await served('/')).match(/href="(\/assets\/styles-[^"]+)"/)[1])).text()).includes('rgb(1, 2, 3)'),
        '... and the server links it as edited');

  await edit('src/routes/about.tsx', '.server(() => "on the server")', '.server(() => "on the edited server")');
  await page.goto(base + '/about');
  check((await text('loaded', 'loaded on the edited server')) === 'loaded on the edited server', 'an isomorphic function edited: the server renders its new branch');
  await hydrated();
  await page.getByTestId('where').click();
  check((await text('where', 'clicked in the browser')) === 'clicked in the browser', '... and the browser runs its own');

  await edit('src/routes/contact.tsx', null,
    'import { createFileRoute } from "@tanstack/react-router";\n\nexport const Route = createFileRoute("/contact")({\n  component: () => <h1 data-testid="title">Contact us</h1>,\n});\n');
  check(readFileSync(join(app, 'src/routeTree.gen.ts'), 'utf8').includes("'/contact'"), 'a route file added: the route tree is generated again with it');
  check((await served('/contact')).includes('Contact us'), '... the server renders it');
  await page.goto(base + '/contact');
  await hydrated();
  check((await text('title', 'Contact us')) === 'Contact us', '... and the browser shows it');

  const api = await fetch(base + '/api/hello');
  check(api.status === 200 && (await api.json()).hello === 'SERVER_ROUTE_SECRET', 'a route only the server has answers');
  check(errors.length === 0, 'no errors: ' + errors.join(' | '));
} catch (e) {
  failures.push(String(e));
  console.log('FAIL', e);
} finally {
  await browser.close();
  server.kill();
}
if (failures.length) console.log(log.split('\n').filter((l) => !l.includes(' bytes -> ')).slice(-30).join('\n'));
console.log(`start-dev-check: ${passed} passed, ${failures.length} failed`);
process.exit(failures.length ? 1 : 0);
