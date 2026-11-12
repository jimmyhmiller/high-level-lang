// Fresh-process API adapters. No watch contexts, persistent caches, or retained bundler objects.
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
// Babel's presets and webpack's loaders are this directory's, not the application's being built.
const own = createRequire(import.meta.url).resolve;
const [kind, configFile] = process.argv.slice(2);
const config = JSON.parse(await readFile(configFile, 'utf8'));
// Every tool builds for production: `process.env.NODE_ENV` is "production", as esbuild's --minify
// and webpack's production mode set it; the others are told.
const NODE_ENV = { 'process.env.NODE_ENV': '"production"', ...config.define };
// An application (tools/compare-bundlers.py's APPS) may also be TypeScript with JSX, which each tool
// compiles as its own documentation has it (Rollup and webpack through Babel, Rspack through its
// built-in SWC, Rolldown itself); and import files, whose URL the code gets.
const files = config.files ?? [];
const fileTest = new RegExp('\\.(' + files.map((x) => x.slice(1)).join('|') + ')$');
const extensions = ['.mjs', '.js', '.json', ...(config.typescript ? ['.ts', '.tsx'] : [])];
const babelPresets = [own('@babel/preset-typescript'), [own('@babel/preset-react'), { runtime: 'automatic' }]];
async function filePlugins() {
  if (!files.length) return [];
  const { default: url } = await import('@rollup/plugin-url');
  return [url({ include: files.map((x) => '**/*' + x), limit: 0, fileName: '[name]-[hash][extname]', publicPath: './' })];
}
function webpackRules(swc) {
  return [
    ...(config.typescript ? [{ test: /\.tsx?$/, exclude: /node_modules/, use: swc
      ? { loader: 'builtin:swc-loader', options: { jsc: { parser: { syntax: 'typescript', tsx: true }, transform: { react: { runtime: 'automatic' } } } } }
      : { loader: own('babel-loader'), options: { presets: babelPresets, babelrc: false, configFile: false } } }] : []),
    ...(files.length ? [{ test: fileTest, type: 'asset/resource' }] : []),
    // Packages' ES modules import without extensions, as a bundler other than webpack allows.
    ...(config.typescript ? [{ test: /\.m?js$/, resolve: { fullySpecified: false } }] : []),
  ];
}
if (kind === 'rollup') {
  const { rollup } = await import('rollup');
  const { nodeResolve } = await import('@rollup/plugin-node-resolve');
  const { default: commonjs } = await import('@rollup/plugin-commonjs');
  const minifiers = [];
  if (config.minify) { const { default: terser } = await import('@rollup/plugin-terser'); minifiers.push(terser()); }
  const bundle = await rollup({
    input: config.input, cache: false,
    plugins: [(await import('@rollup/plugin-replace')).default({ values: NODE_ENV, preventAssignment: true }),
      ...(await filePlugins()), (await import('@rollup/plugin-json')).default(),
      nodeResolve({ browser: true, extensions }), commonjs(),
      ...(config.typescript ? [(await import('@rollup/plugin-babel')).default({ babelHelpers: 'bundled', presets: babelPresets,
        extensions: ['.ts', '.tsx'], exclude: /node_modules/, babelrc: false, configFile: false })] : []),
      ...minifiers],
    onwarn(warning, warn) { if (warning.code !== 'CIRCULAR_DEPENDENCY') warn(warning); }
  });
  try { await bundle.write({ dir: config.output, format: 'es', sourcemap: false,
    entryFileNames: '[name].js', chunkFileNames: '[name]-[hash].js' }); }
  finally { await bundle.close(); }
} else if (kind === 'rolldown') {
  const { rolldown } = await import('rolldown');
  const bundle = await rolldown({ input: config.input, platform: 'browser', transform: { define: NODE_ENV, ...(config.typescript ? { jsx: 'react-jsx' } : {}) },
    plugins: await filePlugins(),
    onwarn(warning, warn) { if (warning.code !== 'CIRCULAR_DEPENDENCY') warn(warning); }
  });
  try { await bundle.write({ dir: config.output, format: 'es', sourcemap: false,
    minify: config.minify, entryFileNames: '[name].js', chunkFileNames: '[name]-[hash].js' }); }
  finally { await bundle.close(); }
} else if (kind === 'webpack') {
  const { default: webpack } = await import('webpack');
  const compiler = webpack({
    mode: 'production', target: ['web', 'es2022'], entry: config.input, cache: false, devtool: false,
    module: { rules: webpackRules(false) }, resolve: { extensions },
    plugins: [new webpack.DefinePlugin(config.define ?? {})],
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
    module: { rules: webpackRules(true) }, resolve: { extensions },
    plugins: [new rspack.DefinePlugin(config.define ?? {})],
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
