// Tailwind's own compiler, run on a project's stylesheets as @tailwindcss/vite runs it: the oracle
// tools/tailwind-check.py compares our output with.
//
// usage: node tools/tailwind-oracle.mjs PROJECT STYLESHEET...
//
// For each stylesheet (a path under PROJECT) it prints one JSON line:
//   {file, root: false}                        when Tailwind leaves the file alone, or
//   {file, root: true, candidates, compiled, optimized}
// `candidates` are what oxide's scanner extracts from the sources the stylesheet's compiler names
// (`source(…)`, `@source`, or the project's root with `**/*`), sorted; `compiled` is
// `compiler.build(candidates)`, the plugin's output in development; `optimized` is that through
// `optimize(code, { minify: true })`, the plugin's output in a production build. Everything is
// loaded from the project's own node_modules, so it is the version the project installed.
import { createRequire } from 'node:module'
import path from 'node:path'
import fs from 'node:fs'
import { pathToFileURL } from 'node:url'

const [project, ...sheets] = process.argv.slice(2)
const root = path.resolve(project)
const require = createRequire(path.join(root, 'package.json'))
const load = (name) => import(pathToFileURL(require.resolve(name)).href)
const node = await load('@tailwindcss/node')
const { Scanner } = await load('@tailwindcss/oxide')
const { compile, optimize, Features } = node

for (const sheet of sheets) {
  const file = path.resolve(root, sheet)
  const content = fs.readFileSync(file, 'utf8')
  // As the plugin's Root: base is the stylesheet's directory, urls rewritten, the project's root
  // (Vite's `config.root`) scanned with `**/*` when the stylesheet names no source.
  const compiler = await compile(content, { base: path.dirname(file), shouldRewriteUrls: true, onDependency() {} })
  const features = Features.AtApply | Features.JsPluginCompat | Features.ThemeFunction | Features.Utilities | Features.Variants
  if (!(compiler.features & features)) {
    console.log(JSON.stringify({ file: sheet, root: false }))
    continue
  }
  const sources = (compiler.root === 'none' ? [] : compiler.root === null ? [{ base: root, pattern: '**/*', negated: false }]
    : [{ ...compiler.root, negated: false }]).concat(compiler.sources)
  const candidates = compiler.features & Features.Utilities ? [...new Set(new Scanner({ sources }).scan())] : []
  const compiled = compiler.build(candidates)
  const optimized = optimize(compiled, { minify: true }).code
  console.log(JSON.stringify({ file: sheet, root: true, sources, candidates: candidates.sort(), compiled, optimized }))
}
