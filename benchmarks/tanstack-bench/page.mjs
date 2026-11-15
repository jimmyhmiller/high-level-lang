// The page a bundler's output of the TanStack Router app is loaded by, for one that writes none:
// its stylesheets, and its entry (a module), or for Turbopack's CLI the chunks its bootstrap
// declares and then the bootstrap, as benchmarks/bundlers/app-check.mjs loads them.
// usage: node page.mjs OUTDIR ENTRY|turbopack
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { parse } from '../../tests/node_modules/acorn/dist/acorn.mjs';
const [out, entry] = process.argv.slice(2);
const files = await readdir(out);
const styles = files.filter((f) => f.endsWith('.css')).map((f) => `<link rel="stylesheet" href="/${f}">`).join('');
async function turbopack() {
  const boots = files.filter((n) => /^turbopack-.*\.js$/.test(n));
  if (boots.length === 0) throw new Error('Turbopack emitted no bootstrap');
  const initial = new Set();
  for (const name of boots) {
    const find = (n) => {
      if (!n || typeof n !== 'object') return null;
      if (n.type === 'ObjectExpression') {
        const p = n.properties.find((p) => (p.key?.name || p.key?.value) === 'otherChunks' && p.value.type === 'ArrayExpression');
        if (p) return p;
      }
      for (const v of Object.values(n)) for (const c of Array.isArray(v) ? v : [v]) if (c && typeof c === 'object') { const f = find(c); if (f) return f; }
      return null;
    };
    const other = find(parse(await readFile(resolve(out, name), 'utf8'), { ecmaVersion: 'latest', sourceType: 'script' }));
    if (!other) throw new Error('Turbopack bootstrap has no otherChunks');
    for (const n of other.value.elements) initial.add(n.type === 'Literal' ? n.value : n.properties.find((p) => (p.key.name || p.key.value) === 'path').value.value);
  }
  return '<script>globalThis.TURBOPACK_CHUNK_BASE_PATH="/";</script>' + [...initial].filter((n) => n.endsWith('.js')).concat(boots).map((n) => `<script src="/${n}"></script>`).join('');
}
const scripts = entry === 'turbopack' ? await turbopack() : `<script type="module" src="/${entry}"></script>`;
await writeFile(resolve(out, 'index.html'), `<!doctype html><html><head><meta charset="utf-8"><title>TanStack Router app</title>${styles}</head><body><div id="app"></div>${scripts}</body></html>\n`);
