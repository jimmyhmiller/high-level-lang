// Generated test fixtures exercise generic split CSS behavior independently of the React app.
import { chromium } from '../tests/node_modules/playwright-core/index.mjs';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile, rm, readdir } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { resolve, extname } from 'node:path';
import assert from 'node:assert/strict';
const root = resolve(import.meta.dirname, '..');
const work = resolve(root, 'out/assets-check');
const binary = process.argv[2] || resolve(root, 'out/bin/esb');
await rm(work, { recursive: true, force: true });
await mkdir(work, { recursive: true });
const files = {
  'package.json': '{"type":"module"}',
  'main.js': 'import asset from "./sample.bin";import "./base.css";const URL="user-url",document="user-document",Map="user-map";globalThis.fixture={asset,locals:[URL,document,Map],open:()=>import("./lazy.js")};',
  'lazy.js': 'import "./lazy.css";if(typeof document!=="undefined"&&getComputedStyle(document.documentElement).getPropertyValue("--lazy-ready").trim()!=="yes")throw Error("CSS must precede evaluation");globalThis.runs=(globalThis.runs||0)+1;export const value=42;',
  'base.css': '@import "./cycle.css";@import "./media.css" screen;@import "./media.css" print;:root{--base-ready:yes}',
  'cycle.css': '@import "./base.css";:root{--cycle-ready:yes}',
  'media.css': ':root{--media-ready:yes}',
  'lazy.css': ':root{--lazy-ready:yes;background-image:url("./mark.svg")}',
  'mark.svg': '<svg xmlns="http://www.w3.org/2000/svg" width="2" height="2"><rect width="2" height="2" fill="green"/></svg>',
};
for (const [name,text] of Object.entries(files)) await writeFile(resolve(work, name), text);
const bytes = Buffer.from([0,255,254,0,13,10,128,42]);
await writeFile(resolve(work, 'sample.bin'), bytes);
const server = createServer(async (request, response) => {
  const path = new URL(request.url, 'http://localhost').pathname;
  if (path === '/') {
    response.setHeader('Content-Type', 'text/html');
    return response.end('<html><head><link rel="stylesheet" href="/assets/entry/main.css"></head><body><script type="module" src="/assets/entry/main.js"></script></body></html>');
  }
  if (!path.startsWith('/assets/')) { response.writeHead(404); return response.end(); }
  const file = resolve(work, 'built', path.slice(8));
  try {
    const data = await readFile(file);
    response.setHeader('Content-Type', ({'.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'})[extname(file)] || 'application/octet-stream');
    response.end(data);
  } catch { response.writeHead(404); response.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = 'http://127.0.0.1:' + server.address().port;
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
try {
  for (const policy of ['exact', 'package', 'balanced']) for (const fragments of [false, true]) for (const minify of [false, true]) {
    await rm(resolve(work,'built'), { recursive:true, force:true });
    const result = spawnSync(binary, ['main.js', '--splitting', '--format=esm', '--outdir=built', '--entry-names=entry/[name]', '--chunk-names=chunks/[name]-[hash]', '--loader:.svg=file', '--loader:.bin=file', '--public-path=/assets/', `--chunk-policy=${policy}`, `--fragments=${fragments}`, ...(minify ? ['--minify'] : []), '--sourcemap'], {cwd:work,encoding:'utf8'});
    assert.equal(result.status, 0, result.stdout + result.stderr);
    const page = await browser.newPage();
    const requests=[],errors=[];
    page.on('request', request => requests.push(request.url()));
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(base);
    await page.waitForFunction(() => !!globalThis.fixture);
    assert(!requests.some(url=>/lazy-.*\.css/.test(url)));
    assert.deepEqual(await page.evaluate(()=>fixture.locals),['user-url','user-document','user-map']);
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--base-ready').trim()),'yes');
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--cycle-ready').trim()),'yes');
    assert.equal(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--media-ready').trim()),'yes');
    const css = await readFile(resolve(work,'built/entry/main.css'),'utf8');
    assert(css.includes('@media screen') && css.includes('@media print'),css);
    let fail=true;
    await page.route(/lazy-.*\.css/,route=>{if(fail){fail=false;return route.abort();}return route.continue();});
    const rejected=await page.evaluate(()=>fixture.open().then(()=>false,()=>true));
    assert(rejected);
    assert.equal(await page.evaluate(()=>globalThis.runs||0),0);
    const values=await page.evaluate(async()=>{const [a,b]=await Promise.all([fixture.open(),fixture.open()]);return [a.value,b.value,globalThis.runs];});
    assert.deepEqual(values,[42,42,1]);
    const successfulCSS=requests.findIndex(url=>/lazy-.*\.css/.test(url));
    const lazyJS=requests.findIndex(url=>/lazy-.*\.js/.test(url));
    assert(successfulCSS>=0 && lazyJS>successfulCSS,requests);
    const asset=await page.evaluate(()=>fixture.asset);
    assert.deepEqual(Buffer.from(await (await fetch(base+asset)).arrayBuffer()),bytes);
    const lazyCSS=await readFile(resolve(work,'built/chunks', (await readdir(resolve(work,'built/chunks'))).find(name=>/^lazy-.*\.css$/.test(name))),'utf8');
    assert.match(lazyCSS,/\/assets\/mark-[A-Z0-9]+\.svg/);
    assert.deepEqual(errors,[]);
    await page.close();
    console.log(`ok   ${policy}, fragments=${fragments}, minify=${minify}: ordered CSS, cycle, media, lazy failure/retry/dedup, nested paths and binary assets`);
  }
  console.log('ALL split asset browser checks passed');
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
