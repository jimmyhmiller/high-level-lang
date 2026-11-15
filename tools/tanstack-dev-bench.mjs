// The TanStack apps in development, ours against Vite with TanStack's plugins: how long from starting
// the server to the page shown in Chrome, how long from saving a route file to the page showing the
// edit (Fast Refresh of the route's component, the page kept), and how much memory the server's
// processes hold (every process it started, summed), at their peak and once the edits are done.
//
// usage: node tools/tanstack-dev-bench.mjs [ESB] [ROUNDS] [EDITS]
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { spawn, execFileSync } from 'node:child_process';
import { cpSync, rmSync, symlinkSync, readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const esb = resolve(process.argv[2] ?? join(root, 'out/bin/esb'));
const rounds = Number(process.argv[3] ?? 3);
const edits = Number(process.argv[4] ?? 5);
const work = join(root, 'out/tanstack-dev-bench');

const apps = {
  router: { fixture: 'benchmarks/tanstack-router', file: 'src/routes/index.tsx', text: 'Welcome home', id: 'title',
            ours: (port) => [esb, ['index.html', '--hmr', `--serve=${port}`, '--outdir=devout', '--tanstack-router', '--no-cache']],
            vite: (port) => ['node_modules/.bin/vite', ['--port', String(port), '--strictPort']] },
  start: { fixture: 'benchmarks/tanstack-start', file: 'src/routes/index.tsx', text: 'Start home', id: 'title',
           ours: (port) => [esb, ['--tanstack-start', '--hmr', `--serve=${port}`, '--no-cache']],
           vite: (port) => ['node_modules/.bin/vite', ['dev', '--port', String(port), '--strictPort']] },
};

function copy(name, fixture) {
  const d = join(work, name);
  rmSync(d, { recursive: true, force: true });
  mkdirSync(d, { recursive: true });
  cpSync(join(root, fixture), d, { recursive: true, filter: (p) => !/node_modules|dist|START-SPEC/.test(p.slice(join(root, fixture).length)) });
  // Its own node_modules of the fixture's packages: what development writes there stays in the copy.
  mkdirSync(join(d, 'node_modules'));
  for (const n of readdirSync(join(root, fixture, 'node_modules'))) symlinkSync(join(root, fixture, 'node_modules', n), join(d, 'node_modules', n));
  return d;
}

// The resident megabytes of a process and every process under it.
function treeRss(pid) {
  const table = execFileSync('ps', ['-axo', 'pid=,ppid=,rss=']).toString().trim().split('\n').map((l) => l.trim().split(/\s+/).map(Number));
  const kids = new Map();
  for (const [p, pp] of table) kids.set(pp, [...(kids.get(pp) ?? []), p]);
  const rss = new Map(table.map(([p, , r]) => [p, r]));
  let total = 0;
  const todo = [pid];
  while (todo.length) { const p = todo.pop(); total += rss.get(p) ?? 0; todo.push(...(kids.get(p) ?? [])); }
  return total / 1024;
}

let port = 41000;
async function round(browser, app, tool) {
  const a = apps[app];
  const dir = copy(`${app}-${tool}`, a.fixture);
  const p = port++;
  const [cmd, argv] = a[tool](p);
  const began = performance.now();
  const server = spawn(cmd, argv, { cwd: dir, stdio: ['ignore', 'pipe', 'pipe'], detached: true });
  let log = '';
  server.stdout.on('data', (d) => { log += d; });
  server.stderr.on('data', (d) => { log += d; });
  let peak = 0;
  const sampler = setInterval(() => { try { peak = Math.max(peak, treeRss(server.pid)); } catch {} }, 50);
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  try {
    // The first page: asked for until the server answers, then shown.
    for (;;) {
      if (server.exitCode !== null) throw new Error(`${tool} exited:\n${log}`);
      if (performance.now() - began > 60000) throw new Error(`${tool} did not answer:\n${log}`);
      try { await page.goto(`http://localhost:${p}/`, { timeout: 5000 }); break; } catch { await new Promise((r) => setTimeout(r, 20)); }
    }
    await page.getByTestId(a.id).filter({ hasText: a.text }).first().waitFor({ timeout: 30000 });
    await page.waitForFunction(() => self.$_TSR === undefined || self.$_TSR.hydrated, null, { timeout: 10000 }).catch(() => {});
    const first = performance.now() - began;
    await page.waitForTimeout(500);
    const updates = [];
    const path = join(dir, a.file);
    const original = readFileSync(path, 'utf8');
    for (let i = 1; i <= edits; i++) {
      const text = `${a.text} ${i}`;
      await page.evaluate(() => { window.__kept = true; });
      const t = performance.now();
      writeFileSync(path, original.replace(a.text, text));
      await page.getByTestId(a.id).filter({ hasText: new RegExp(`^${text}$`) }).first().waitFor({ timeout: 20000 });
      updates.push(performance.now() - t);
      if (!(await page.evaluate(() => window.__kept === true))) errors.push(`edit ${i} reloaded the page`);
      await page.waitForTimeout(300);
    }
    const after = treeRss(server.pid);
    return { first, updates, peak: Math.max(peak, after), after, errors };
  } finally {
    clearInterval(sampler);
    await page.close();
    try { process.kill(-server.pid, 'SIGTERM'); } catch {}
    await new Promise((r) => setTimeout(r, 300));
  }
}

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const results = {};
for (let r = 0; r < rounds; r++) {
  for (const app of Object.keys(apps)) {
    for (const tool of ['ours', 'vite']) {
      const res = await round(browser, app, tool);
      (results[`${app} ${tool}`] ??= []).push(res);
    }
  }
}
await browser.close();
console.log(`TanStack apps in development (${rounds} rounds of a fresh server, ${edits} edits each, interleaved; load ${(await import('node:os')).loadavg()[0].toFixed(1)})`);
console.log('                 first page ms   edit shown ms (median, worst)   peak MB   after edits MB   problems');
for (const [key, rs] of Object.entries(results)) {
  const ups = rs.flatMap((x) => x.updates);
  console.log(`  ${key.padEnd(14)} ${median(rs.map((x) => x.first)).toFixed(0).padStart(10)}   ${median(ups).toFixed(0).padStart(14)} ${Math.max(...ups).toFixed(0).padStart(8)}`
    + `   ${median(rs.map((x) => x.peak)).toFixed(0).padStart(11)} ${median(rs.map((x) => x.after)).toFixed(0).padStart(12)}   ${rs.flatMap((x) => x.errors).join('; ') || 'none'}`);
}
