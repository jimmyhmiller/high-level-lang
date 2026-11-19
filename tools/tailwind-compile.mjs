// Tailwind's compile of SHEET with exactly the candidates in FILE: one JSON line for build-check.py.
import { createRequire } from 'node:module'
import path from 'node:path'
import fs from 'node:fs'
import { pathToFileURL } from 'node:url'
const [project, sheet, candFile] = process.argv.slice(2)
const root = path.resolve(project)
const require = createRequire(path.join(root, 'package.json'))
const node = await import(pathToFileURL(require.resolve('@tailwindcss/node')).href)
const file = path.resolve(sheet)
const candidates = fs.readFileSync(candFile, 'utf8').split('\n').filter(Boolean)
try {
  const compiler = await node.compile(fs.readFileSync(file, 'utf8'), { base: path.dirname(file), shouldRewriteUrls: true, onDependency() {} })
  console.log(JSON.stringify({ file: path.relative(root, file), sources: [{ base: path.dirname(file), pattern: '' }], candidates, compiled: compiler.build(candidates) }))
} catch (e) {
  console.log(JSON.stringify({ file: path.relative(root, file), sources: [{ base: path.dirname(file), pattern: '' }], candidates, error: e.message.split('\n')[0] }))
}
