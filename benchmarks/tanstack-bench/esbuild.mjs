// The TanStack Router app built by esbuild with TanStack's own esbuild plugin, as far as it goes:
// the route tree, not route splitting, which the plugin refuses with esbuild. Run from the app. usage: node esbuild.mjs APP-DIR OUT-DIR
import { createRequire } from 'node:module';
import { join } from 'node:path';
const [app, out] = process.argv.slice(2);
const require = createRequire(join(app, 'package.json'));
const esbuild = require('esbuild');
const { tanstackRouter } = await import(require.resolve('@tanstack/router-plugin/esbuild'));
await esbuild.build({
  absWorkingDir: app, entryPoints: ['src/main.tsx'], bundle: true, splitting: true, format: 'esm', minify: true,
  outdir: out, jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' }, logLevel: 'warning',
  plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: false })],
});
