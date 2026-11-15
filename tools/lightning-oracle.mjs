// lightningcss 1.33.0 as Tailwind's production build and Vite 8's CSS minify run it: the oracle
// tools/lightning-check.mjs compares `twc optimize` and `twc vite-minify` with.
//
// usage: node tools/lightning-oracle.mjs MODE FILE      MODE: tailwind | vite | both
//
// `tailwind` prints `optimize(css, { minify: true }).code` from @tailwindcss/node (two lightningcss
// passes and the `@media not (` workaround); `vite` prints what Vite 8's `minifyCSS` gives for a
// client build: lightningcss `transform` with minify and the targets `convertTargets` makes of
// Vite's default `build.cssTarget` (chrome111, edge111, firefox114, safari16.4, ios16.4), and the
// line break Vite adds. Packages come from out/lc-oracle/node_modules (copied from a test app), or
// from the directory in LIGHTNING_MODULES.
import { createRequire } from 'node:module'
import path from 'node:path'
import fs from 'node:fs'
import { pathToFileURL, fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const modules = process.env.LIGHTNING_MODULES ?? path.join(here, '..', 'out', 'lc-oracle', 'node_modules')
const require = createRequire(path.join(modules, '..', 'package.json'))
const load = (name) => import(pathToFileURL(require.resolve(name)).href)

export const viteTargets = { chrome: 111 << 16, edge: 111 << 16, firefox: 114 << 16, safari: (16 << 16) | (4 << 8), ios_saf: (16 << 16) | (4 << 8) }

export async function oracle() {
  const { optimize } = await load('@tailwindcss/node')
  const { transform } = await load('lightningcss')
  return {
    tailwind: (css) => optimize(css, { minify: true }).code,
    vite: (css) => new TextDecoder().decode(transform({ filename: 'style.css', code: Buffer.from(css), minify: true, targets: viteTargets }).code) + '\n',
  }
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [mode, file] = process.argv.slice(2)
  const css = fs.readFileSync(file, 'utf8')
  const o = await oracle()
  if (mode === 'tailwind') process.stdout.write(o.tailwind(css))
  else if (mode === 'vite') process.stdout.write(o.vite(css))
  else if (mode === 'both') process.stdout.write(o.vite(o.tailwind(css)))
  else throw new Error('usage: node tools/lightning-oracle.mjs tailwind|vite|both FILE')
}
