// Fresh-process API adapters. No watch contexts, persistent caches, or retained bundler objects.
import { readFile } from 'node:fs/promises';
const [kind, configFile] = process.argv.slice(2);
const config = JSON.parse(await readFile(configFile, 'utf8'));
// Every tool builds for production: `process.env.NODE_ENV` is "production", as esbuild's --minify
// and webpack's production mode set it; the others are told.
const NODE_ENV = { 'process.env.NODE_ENV': '"production"' };
if (kind === 'rollup') {
  const { rollup } = await import('rollup');
  const { nodeResolve } = await import('@rollup/plugin-node-resolve');
  const { default: commonjs } = await import('@rollup/plugin-commonjs');
  const minifiers = [];
  if (config.minify) { const { default: terser } = await import('@rollup/plugin-terser'); minifiers.push(terser()); }
  const bundle = await rollup({
    input: config.input, cache: false,
    plugins: [(await import('@rollup/plugin-replace')).default({ values: NODE_ENV, preventAssignment: true }),
      nodeResolve({ browser: true }), commonjs(), ...minifiers],
    onwarn(warning, warn) { if (warning.code !== 'CIRCULAR_DEPENDENCY') warn(warning); }
  });
  try { await bundle.write({ dir: config.output, format: 'es', sourcemap: false,
    entryFileNames: '[name].js', chunkFileNames: '[name]-[hash].js' }); }
  finally { await bundle.close(); }
} else if (kind === 'rolldown') {
  const { rolldown } = await import('rolldown');
  const bundle = await rolldown({ input: config.input, platform: 'browser', transform: { define: NODE_ENV },
    onwarn(warning, warn) { if (warning.code !== 'CIRCULAR_DEPENDENCY') warn(warning); }
  });
  try { await bundle.write({ dir: config.output, format: 'es', sourcemap: false,
    minify: config.minify, entryFileNames: '[name].js', chunkFileNames: '[name]-[hash].js' }); }
  finally { await bundle.close(); }
} else if (kind === 'webpack') {
  const { default: webpack } = await import('webpack');
  const compiler = webpack({
    mode: 'production', target: ['web', 'es2022'], entry: config.input, cache: false, devtool: false,
    output: { path: config.output, filename: '[name].js', chunkFilename: '[name]-[contenthash].js',
      module: true, chunkFormat: 'module', chunkLoading: 'import', publicPath: 'auto', clean: true },
    experiments: { outputModule: true, topLevelAwait: true },
    optimization: { minimize: config.minify, usedExports: true, concatenateModules: true,
      runtimeChunk: false, splitChunks: { chunks: 'all' } },
    stats: 'errors-warnings'
  });
  await new Promise((resolve, reject) => {
    compiler.run((error, stats) => {
      compiler.close(closeError => {
        if (error || closeError) return reject(error || closeError);
        if (stats.hasErrors()) return reject(new Error(stats.toString({ all: false, errors: true })));
        resolve();
      });
    });
  });
} else if (kind === 'rspack') {
  const { rspack } = await import('@rspack/core');
  const compiler = rspack({
    mode: 'production', target: ['web', 'es2022'], entry: config.input, cache: false, devtool: false,
    output: { path: config.output, filename: '[name].js', chunkFilename: '[name]-[contenthash].js',
      module: true, chunkFormat: 'module', chunkLoading: 'import', publicPath: 'auto', clean: true },
    experiments: { outputModule: true, topLevelAwait: true },
    optimization: { minimize: config.minify, usedExports: true, concatenateModules: true,
      runtimeChunk: false, splitChunks: { chunks: 'all' } },
    stats: 'errors-warnings'
  });
  await new Promise((resolve, reject) => {
    compiler.run((error, stats) => {
      compiler.close(closeError => {
        if (error || closeError) return reject(error || closeError);
        if (stats.hasErrors()) return reject(new Error(stats.toString({ all: false, errors: true })));
        resolve();
      });
    });
  });
} else throw new Error('Unknown adapter: ' + kind);
