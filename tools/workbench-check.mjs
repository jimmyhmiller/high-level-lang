// Actual browser and HTTP acceptance checks for the source fixture and optimized split outputs.
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { spawn } from 'node:child_process';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import assert from 'node:assert/strict';

const root = resolve(import.meta.dirname, '..');
const temporary = await mkdtemp(resolve(tmpdir(), 'workbench-'));
const chrome = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
let browser, server;
async function start() {
  let text = '';
  server = spawn('node', ['--enable-source-maps', 'out/workbench/server.mjs'], {
    cwd: root, env: { ...process.env, PORT: '0', WORKBENCH_DATA: resolve(temporary, 'projects.json') },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  server.stdout.on('data', chunk => { text += chunk; });
  server.stderr.on('data', chunk => { text += chunk; });
  for (let i = 0; i < 200; i++) {
    const match = text.match(/http:\/\/127\.0\.0\.1:(\d+)/);
    if (match) return match[0];
    if (server.exitCode !== null) throw new Error(text);
    await new Promise(r => setTimeout(r, 25));
  }
  throw new Error('server did not start: ' + text);
}
async function stop() {
  if (!server || server.exitCode !== null) return;
  const closed = new Promise(resolve => server.once('exit', resolve));
  server.kill('SIGTERM');
  await closed;
}
try {
  let base = await start();
  let response = await fetch(base + '/api/projects');
  assert.equal(response.status, 200);
  assert.equal((await response.json()).length, 4);
  response = await fetch(base + '/api/projects', { method: 'POST', body: '{bad' });
  assert.equal(response.status, 400);
  response = await fetch(base + '/api/projects', { method: 'POST', body: JSON.stringify({ name: '' }) });
  assert.equal(response.status, 422);
  response = await fetch(base + '/static/does-not-exist.svg');
  assert.equal(response.status, 404);
  console.log('ok   bundled API validates requests and serves missing-file errors');
  browser = await chromium.launch({ executablePath: chrome, headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [], badResponses = [], requests = [];
  page.on('pageerror', error => { errors.push(String(error)); console.error('browser:', error.stack); });
  page.on('response', response => { if (response.status() >= 400) badResponses.push(response.url()); });
  page.on('request', request => requests.push(request.url()));
  await page.goto(base);
  await page.getByTestId('overview').waitFor({timeout:10000});
  await page.waitForFunction(() => document.querySelectorAll('.recent-project').length === 4);
  assert.equal(await page.getByTestId('overview').evaluate(el => getComputedStyle(el).getPropertyValue('--route-ready').trim()), 'overview');
  assert.equal(await page.locator('.brand img').evaluate(el => el.complete && el.naturalWidth > 0), true);
  assert.match(await page.locator('.note').evaluate(el => getComputedStyle(el).backgroundImage), /grid-[A-Z0-9]+\.svg/);
  assert(!requests.some(url => /reports-[^/]+\.css/.test(url)), 'reports CSS should stay lazy');
  await page.screenshot({ path: resolve(root, 'out/workbench/overview.png'), fullPage: true });
  console.log('ok   React mounts, dashboard data renders, initial CSS and both SVG assets load');
  await page.getByRole('link', { name: 'Projects', exact: true }).click();
  await page.getByTestId('projects').waitFor();
  assert.equal(await page.getByTestId('projects').evaluate(el => getComputedStyle(el).getPropertyValue('--route-ready').trim()), 'projects');
  await page.getByRole('button', { name: 'New project', exact: true }).click();
  await page.getByLabel('Name', { exact: true }).fill('Acceptance launch');
  await page.getByLabel('Owner', { exact: true }).fill('Jordan');
  await page.getByLabel('Budget', { exact: true }).fill('7500');
  await page.getByRole('button', { name: 'Save project', exact: true }).click();
  await page.getByRole('cell', { name: 'Acceptance launch', exact: true }).waitFor();
  await page.getByRole('button', { name: 'Complete Acceptance launch', exact: true }).click();
  await page.waitForFunction(() => [...document.querySelectorAll('tr')].some(row => row.textContent.includes('Acceptance launch') && row.textContent.includes('done')));
  await page.getByRole('combobox', { name: 'Filter status' }).selectOption('done');
  assert.equal(await page.locator('tbody tr').count(), 2);
  await page.getByRole('textbox', { name: 'Search projects' }).fill('Acceptance');
  assert.equal(await page.locator('tbody tr').count(), 1);
  console.log('ok   lazy projects route loads styled; create, update, filter and search work');
  await page.getByRole('link', { name: 'Reports', exact: true }).click();
  await page.getByTestId('reports').waitFor();
  assert.equal(await page.getByTestId('reports').evaluate(el => getComputedStyle(el).getPropertyValue('--route-ready').trim()), 'reports');
  assert.equal(await page.locator('.budget-chart rect').count(), 5);
  assert.equal(await page.getByTestId('report-total').textContent(), 'Total investment: $127,500');
  await page.getByRole('button', { name: 'Switch theme' }).click();
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  await page.reload();
  await page.getByTestId('reports').waitFor();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  console.log('ok   lazy D3 report totals and chart render; theme survives reload');
  await stop();
  base = await start();
  response = await fetch(base + '/api/projects');
  const saved = await response.json();
  assert.equal(saved.length, 5);
  assert.equal(saved.find(p => p.name === 'Acceptance launch').status, 'done');
  const data = JSON.parse(await readFile(resolve(temporary, 'projects.json'), 'utf8'));
  assert.equal(data.length, 5);
  assert.deepEqual(errors, []);
  assert.deepEqual(badResponses, []);
  console.log('ok   mutation survives server restart; browser reports no script errors or failed requests');
  console.log('ALL Workbench browser and API checks passed');
} finally {
  if (browser) await browser.close();
  await stop();
  await rm(temporary, { recursive: true, force: true });
}
