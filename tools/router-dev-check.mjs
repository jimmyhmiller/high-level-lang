// The TanStack Router application in development (`esb index.html --hmr --serve=0 --tanstack-router`),
// in a headless browser, while its files are edited: what each edit shows, whether the page kept
// its state or reloaded, as Vite with TanStack's plugin and @vitejs/plugin-react does it.
//
// usage: node tools/router-dev-check.mjs [ESB]
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { spawn } from 'node:child_process';
import { cpSync, rmSync, symlinkSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const esb = resolve(process.argv[2] ?? join(root, 'out/bin/esb'));
const work = join(root, 'out/router-dev-check');
const app = join(work, 'app');
rmSync(work, { recursive: true, force: true });
mkdirSync(work, { recursive: true });
cpSync(join(root, 'benchmarks/tanstack-router'), app, { recursive: true, filter: (p) => !/node_modules|dist/.test(p.slice(join(root, 'benchmarks/tanstack-router').length)) });
symlinkSync(join(root, 'benchmarks/tanstack-router/node_modules'), join(app, 'node_modules'));

let passed = 0;
const failures = [];
function check(ok, what) {
  if (ok) { passed++; console.log('ok  ', what); } else { failures.push(what); console.log('FAIL', what); }
}

const server = spawn(esb, ['index.html', '--hmr', '--serve=0', '--outdir=devout', '--tanstack-router', '--no-cache'], { cwd: app });
let log = '';
server.stdout.on('data', (d) => { log += d; });
server.stderr.on('data', (d) => { log += d; });
const base = await new Promise((ok, fail) => {
  const deadline = Date.now() + 20000;
  const poll = setInterval(() => {
    const m = log.match(/serving \S+ at (http:\/\/127\.0\.0\.1:\d+)/);
    if (m && log.includes('[watch] build 1')) { clearInterval(poll); ok(m[1]); }
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
// An edit, and the build it makes: the page's marker says whether it reloaded.
async function edit(file, from, to) {
  const before = builds();
  await page.evaluate(() => { window.__kept = 'still here'; });
  const path = join(app, file);
  const was = from === null ? '' : readFileSync(path, 'utf8');
  if (from !== null && !was.includes(from)) throw new Error(file + ' has no ' + from);
  writeFileSync(path, from === null ? to : was.replace(from, to));
  const deadline = Date.now() + 10000;
  while (builds() === before && Date.now() < deadline) await new Promise((r) => setTimeout(r, 25));
  await page.waitForTimeout(400);
}
const kept = () => page.evaluate(() => window.__kept === 'still here');

try {
  await page.goto(base + '/');
  check((await text('title', 'Welcome home')) === 'Welcome home', 'the development server serves the app');
  check(await page.evaluate(() => getComputedStyle(document.body).fontFamily.includes('system-ui')), 'its stylesheet is in the page');
  await page.getByTestId('counter').click();
  await page.getByTestId('counter').click();
  check((await text('counter', 'clicks: 2')) === 'clicks: 2', 'the counter counts');

  await edit('src/components/Counter.tsx', '{label}: {n}', '{label} = {n}');
  check((await text('counter', 'clicks = 2')) === 'clicks = 2' && await kept(),
        'a component edited is refreshed in place, its state kept (Fast Refresh)');

  await edit('src/routes/index.tsx', 'Welcome home', 'Welcome back');
  check((await text('title', 'Welcome back')) === 'Welcome back' && await kept(), 'a route file edited updates its route in place');
  check((await text('counter', 'clicks = 2')) === 'clicks = 2', '... and the component below it keeps its state');

  await edit('src/styles.css', 'margin: 0;', 'margin: 0; color: rgb(1, 2, 3);');
  check(await page.evaluate(() => getComputedStyle(document.body).color) === 'rgb(1, 2, 3)' && await kept(), 'a stylesheet edited is replaced in the page');

  await page.getByRole('link', { name: 'Posts' }).click();
  check((await text('title', 'Posts')) === 'Posts', 'navigating still works');
  await edit('src/routes/posts/route.tsx', '<h1 data-testid="title">Posts</h1>', '<h1 data-testid="title">All posts</h1>');
  check((await text('title', 'All posts')) === 'All posts' && await kept(), 'a layout route with a loader edited updates in place');

  await edit('src/routes/contact.tsx', null,
    'import { createFileRoute } from "@tanstack/react-router";\n\nexport const Route = createFileRoute("/contact")({\n  component: () => <h1 data-testid="title">Contact us</h1>,\n});\n');
  const tree = readFileSync(join(app, 'src/routeTree.gen.ts'), 'utf8');
  check(tree.includes("'/contact'"), 'a route file added: the route tree is generated again with it');
  await page.goto(base + '/contact');
  check((await text('title', 'Contact us')) === 'Contact us', '... and its route is served');

  check(errors.length === 0, 'no errors: ' + errors.join(' | '));
} catch (e) {
  failures.push(String(e));
  console.log('FAIL', e);
} finally {
  await browser.close();
  server.kill();
}
if (failures.length) console.log(log.split('\n').slice(-30).join('\n'));
console.log(`router-dev-check: ${passed} passed, ${failures.length} failed`);
process.exit(failures.length ? 1 : 0);
