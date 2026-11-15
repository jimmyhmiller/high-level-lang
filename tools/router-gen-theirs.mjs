// Runs TanStack Router's own route generator (@tanstack/router-generator, from benchmarks/tanstack-router)
// on each project root given, as its Vite plugin does: tsr.config.json in the root, the tree and the
// route files written. Prints one line per root: `ok` or `error <message>`.
//
// usage: node tools/router-gen-theirs.mjs ROOT...
import { resolve } from 'node:path';
const here = new URL('.', import.meta.url).pathname;
const { Generator, getConfig } = await import(resolve(here, '../benchmarks/tanstack-router/node_modules/@tanstack/router-generator/dist/esm/index.js'));

for (const root of process.argv.slice(2)) {
  try {
    process.chdir(root);
    const config = getConfig({ disableLogging: true }, root);
    const g = new Generator({ config, root });
    await g.run();
    console.log('ok');
  } catch (e) {
    console.log('error ' + String(e && e.message || e).split('\n')[0]);
  }
}
