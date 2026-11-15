// Checks our scanner (`out/bin/twc`) against Tailwind's own (oxide, loaded from a test app).
//
// usage:
//   node tools/tailwind-scan-check.mjs content FILE...      each file's text, extension and all,
//                                                           extracted by both (oxide's scanFiles)
//   node tools/tailwind-scan-check.mjs sources BASE PATTERN [--not BASE PATTERN]...
//                                                           one set of sources scanned by both
//   node tools/tailwind-scan-check.mjs projects [NAME...]   the apps, the TanStack examples and the
//                                                           fixtures under out/scan-fixtures
//
// A check passes when the candidate sets are identical, and for sources when the files read are
// too. The first differences are printed otherwise. Exits non-zero when any check fails.
import { createRequire } from 'node:module'
import { execFileSync } from 'node:child_process'
import path from 'node:path'
import fs from 'node:fs'
import os from 'node:os'
import { pathToFileURL } from 'node:url'

const here = path.dirname(new URL(import.meta.url).pathname)
const repo = path.resolve(here, '..')
const twc = path.join(repo, 'out/bin/twc')
const apps = '/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/.claude/worktrees/agent-a64d0cb41475d4d5e/out/real/apps'
const examples = '/Users/jimmyhmiller/Documents/Code/projects/high-level-lang/.worktrees/tanstack/out/real/router/examples/react'
const fixtures = path.join(repo, 'out/scan-fixtures')
const oracleApp = path.join(apps, 'start-tailwind-v4')

const requireIn = (dir) => createRequire(path.join(dir, 'package.json'))
const { Scanner } = requireIn(oracleApp)(requireIn(oracleApp).resolve('@tailwindcss/oxide'))
const bytewise = (a, b) => Buffer.compare(Buffer.from(a), Buffer.from(b))
const sorted = (xs) => [...new Set(xs)].sort(bytewise)

function ours(args) {
  const out = execFileSync(twc, args, { maxBuffer: 1 << 30, encoding: 'utf8' })
  return out === '' ? [] : out.slice(0, -1).split('\n')
}

// The first few items each list has and the other lacks.
function differences(a, b) {
  const inB = new Set(b), inA = new Set(a)
  return { missing: a.filter((x) => !inB.has(x)), extra: b.filter((x) => !inA.has(x)) }
}

function report(name, what, expected, actual) {
  const { missing, extra } = differences(expected, actual)
  if (missing.length === 0 && extra.length === 0) return true
  console.log(`FAIL ${name}: ${what}: ${missing.length} missing, ${extra.length} extra`)
  for (const x of missing.slice(0, 8)) console.log(`  - ${JSON.stringify(x)}`)
  for (const x of extra.slice(0, 8)) console.log(`  + ${JSON.stringify(x)}`)
  return false
}

function checkContent(file) {
  const extension = path.extname(file).slice(1)
  // scanFiles takes a JavaScript string, so oxide sees the file's text as UTF-8 makes it (bad bytes
  // replaced); ours is given those bytes too.
  const content = fs.readFileSync(file, 'utf8')
  const expected = sorted(new Scanner({ sources: [] }).scanFiles([{ content, extension }]))
  const text = path.join(fs.mkdtempSync(path.join(fs.realpathSync(os.tmpdir()), 'scan-')), 'content.' + extension)
  fs.writeFileSync(text, content)
  const actual = ours(['extract', extension, text])
  fs.rmSync(path.dirname(text), { recursive: true })
  return report(file, 'candidates', expected, actual)
}

function checkSources(name, sources) {
  const started = performance.now()
  const scanner = new Scanner({ sources })
  const expected = sorted(scanner.scan())
  const expectedFiles = sorted(scanner.scannedFiles)
  const theirs = performance.now() - started
  const args = sources.flatMap((s) => [s.negated ? '--not' : '--source', s.base, s.pattern])
  const begun = performance.now()
  const actual = ours(['scan', ...args])
  const mine = performance.now() - begun
  const actualFiles = ours(['scanned-files', ...args])
  const ok = report(name, 'candidates', expected, actual) & report(name, 'files', expectedFiles, actualFiles)
  if (ok) console.log(`ok   ${name}: ${expected.length} candidates, ${expectedFiles.length} files (oxide ${theirs.toFixed(0)} ms, ours ${mine.toFixed(0)} ms)`)
  return ok
}

// The sources @tailwindcss/vite gives the scanner for an app's stylesheet (as tools/tailwind-oracle.mjs).
async function appSources(app, sheet) {
  const require = requireIn(app)
  const { compile } = await import(pathToFileURL(require.resolve('@tailwindcss/node')).href)
  const file = path.join(app, sheet)
  const compiler = await compile(fs.readFileSync(file, 'utf8'), { base: path.dirname(file), shouldRewriteUrls: true, onDependency() {} })
  return (compiler.root === 'none' ? [] : compiler.root === null ? [{ base: app, pattern: '**/*', negated: false }]
    : [{ ...compiler.root, negated: false }]).concat(compiler.sources)
}

async function projects() {
  const list = []
  for (const name of fs.readdirSync(apps).sort()) {
    const app = path.join(apps, name)
    const sheet = ['src/styles/app.css', 'src/styles.css'].find((s) => fs.existsSync(path.join(app, s)))
    if (sheet) list.push({ name: `app ${name}`, sources: await appSources(app, sheet) })
  }
  for (const name of fs.readdirSync(examples).sort()) {
    const dir = path.join(examples, name)
    if (fs.statSync(dir).isDirectory()) list.push({ name: `example ${name}`, sources: [{ base: dir, pattern: '**/*', negated: false }] })
  }
  if (fs.existsSync(path.join(fixtures, 'fixtures.json'))) {
    for (const f of JSON.parse(fs.readFileSync(path.join(fixtures, 'fixtures.json'), 'utf8'))) {
      list.push({ name: `fixture ${f.name}`, sources: f.sources.map((s) => ({ ...s, base: path.resolve(fixtures, s.base) })) })
    }
  }
  return list
}

const [mode, ...args] = process.argv.slice(2)
let ok = true
if (mode === 'content') {
  let passed = 0
  for (const file of args) if (checkContent(file)) passed++; else ok = false
  console.log(`${passed} of ${args.length} files the same`)
} else if (mode === 'sources') {
  const sources = []
  for (let i = 0; i < args.length; i += 3) sources.push({ base: args[i + 1] === undefined ? args[i] : args[i + 1], pattern: args[i + 2], negated: args[i] === '--not' })
  ok = checkSources('sources', sources)
} else if (mode === 'projects') {
  const wanted = new Set(args)
  let passed = 0, total = 0
  for (const p of await projects()) {
    if (wanted.size && ![...wanted].some((w) => p.name.includes(w))) continue
    total++
    if (checkSources(p.name, p.sources)) passed++; else ok = false
  }
  console.log(`${passed} of ${total} projects the same`)
} else {
  console.error('usage: tailwind-scan-check.mjs content FILE... | sources --source BASE PATTERN... | projects [NAME...]')
  process.exit(2)
}
process.exit(ok ? 0 : 1)
