// Execute the emitted browser code, measure the requested JS closure for one route and all routes.
import { chromium } from '../../tests/node_modules/playwright-core/index.mjs';
import { createServer } from 'node:http';
import { readFile, readdir } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import assert from 'node:assert/strict';
import { parse } from '../../tests/node_modules/acorn/dist/acorn.mjs';
const [outputArg, kind, countArg, expectedFile] = process.argv.slice(2);
const output = resolve(outputArg), count = Number(countArg);
const expected = JSON.parse(await readFile(expectedFile, 'utf8'));
let scripts = '<script type="module" src="/main.js"></script>';
if (kind === 'turbopack') {
  // This CLI emits assets rather than HTML. Its bootstrap declares otherChunks that a host
  // document must load before starting the runtime; read that declaration from the JS AST.
  const bootstraps = (await readdir(output)).filter(name => /^turbopack-.*\.js$/.test(name));
  const initial = new Set();
  for (const name of bootstraps) {
    const tree = parse(await readFile(resolve(output,name),'utf8'),{ecmaVersion:'latest',sourceType:'script'});
    function findManifest(node) {
      if (!node || typeof node !== 'object') return null;
      if (node.type === 'ObjectExpression') {
        const property=node.properties.find(property=>(property.key?.name||property.key?.value)==='otherChunks' && property.value.type==='ArrayExpression');
        if (property) return property;
      }
      for (const value of Object.values(node)) {
        if (Array.isArray(value)) { for (const child of value) { const found=findManifest(child);if(found)return found; } }
        else if (value && typeof value === 'object') { const found=findManifest(value);if(found)return found; }
      }
      return null;
    }
    const other=findManifest(tree);
    assert(other, 'Turbopack bootstrap has no static otherChunks declaration');
    for (const node of other.value.elements) {
      const path = node.type==='Literal' ? node.value : node.properties.find(property=>(property.key.name||property.key.value)==='path').value.value;
      initial.add(path);
    }
  }
  scripts = '<script>globalThis.TURBOPACK_CHUNK_BASE_PATH="/";</script>' + [...initial,...bootstraps].map(name=>`<script src="/${name}"></script>`).join('');
}
assert(scripts, 'No entry bootstrap');
const requests = new Set();
const server = createServer(async (req, res) => {
  const path = new URL(req.url, 'http://localhost').pathname;
  if (path === '/') { res.setHeader('Content-Type', 'text/html'); return res.end('<!doctype html><link rel="icon" href="data:,"><body>' + scripts); }
  const filename = decodeURIComponent(path.slice(1));
  const file = resolve(output, filename);
  if (!file.startsWith(output + '/')) { res.writeHead(403); return res.end(); }
  try {
    const body = await readFile(file);
    res.setHeader('Content-Type', extname(file) === '.js' || extname(file) === '.mjs' ? 'text/javascript' : 'application/octet-stream');
    if (/\.[mc]?js$/.test(file)) requests.add(filename);
    res.end(body);
  } catch { res.writeHead(404); res.end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true });
const page = await browser.newPage();
const logs = [], errors = [], bad = [];
page.on('console', message => { if (message.type() === 'log') logs.push(message.text()); });
page.on('pageerror', error => errors.push(error.stack || String(error)));
page.on('response', response => { if (response.status() >= 400) bad.push(response.url()); });
try {
  await page.goto('http://127.0.0.1:' + server.address().port);
  await page.waitForFunction(() => typeof globalThis.__bench_load === 'function', {timeout:30000});
  await page.evaluate(() => Promise.race([globalThis.__bench_load(0), new Promise((_,reject)=>setTimeout(()=>reject(new Error('route 0 did not finish within 10 seconds')),10000))]));
  const firstFiles = [...requests].sort();
  for (let i = 1; i < count; i++) await page.evaluate(index => globalThis.__bench_load(index), i);
  const actual = await page.evaluate(() => ({ results: globalThis.__bench_results,
    scaleInit: globalThis.scaleInitializations || 0, mixedInit: globalThis.__mixed_init || 0 }));
  assert.deepEqual(actual, expected.values);
  assert.deepEqual(logs.sort(), expected.logs);
  assert.deepEqual(errors, []);
  assert.deepEqual(bad, []);
  process.stdout.write(JSON.stringify({ firstFiles, allLoadedFiles: [...requests].sort(), correct: true }));
} catch (error) {
  console.error(JSON.stringify({errors,bad,logs,requests:[...requests],state:await page.evaluate(()=>({ready:typeof globalThis.__bench_load,results:globalThis.__bench_results}))}));
  throw error;
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
