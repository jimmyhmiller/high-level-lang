// The TanStack Router app built by Rspack with TanStack's own Rspack plugin (route tree and
// automatic code splitting) and Rspack's SWC loader. Run from the app (the generator reads its
// routes from the working directory). usage: node rspack.mjs APP-DIR OUT-DIR RSPACK-CORE
import { createRequire } from 'node:module';
import { join } from 'node:path';
const [app, out, core] = process.argv.slice(2);
const require = createRequire(join(app, 'package.json'));
const { rspack } = await import(core);
const { tanstackRouter } = await import(require.resolve('@tanstack/router-plugin/rspack'));
const compiler = rspack({
  mode: 'production', context: app, entry: { index: './src/main.tsx' }, cache: false, devtool: false, target: ['web', 'es2022'],
  resolve: { extensions: ['.tsx', '.ts', '.jsx', '.js'] },
  module: { rules: [
    { test: /\.tsx?$/, loader: 'builtin:swc-loader', options: { jsc: { parser: { syntax: 'typescript', tsx: true }, transform: { react: { runtime: 'automatic' } } } }, type: 'javascript/auto' },
    { test: /\.css$/, type: 'css' },
  ] },
  experiments: { css: true, outputModule: true },
  output: { path: out, filename: '[name]-[contenthash].js', chunkFilename: '[name]-[contenthash].js', module: true, chunkFormat: 'module', chunkLoading: 'import', clean: true },
  optimization: { minimize: true, splitChunks: { chunks: 'all' } },
  plugins: [tanstackRouter({ target: 'react', autoCodeSplitting: true })],
  stats: 'errors-warnings',
});
await new Promise((ok, fail) => compiler.run((e, stats) => compiler.close(() => {
  if (e) return fail(e);
  if (stats.hasErrors()) return fail(new Error(stats.toString({ all: false, errors: true })));
  ok();
})));
