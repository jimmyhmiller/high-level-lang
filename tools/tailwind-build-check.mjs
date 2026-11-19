// Check the CSS emitted by the actual HTML build and the development server.
import assert from 'node:assert/strict'
import { execFileSync, spawn } from 'node:child_process'
import { once } from 'node:events'
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, realpathSync, rmSync, symlinkSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { chromium } from '../tests/node_modules/playwright-core/index.mjs'

const root = path.resolve(import.meta.dirname, '..')
const esb = path.resolve(process.argv[2] ?? path.join(root, 'out/bin/esb'))
const modules = realpathSync(process.argv[3] ?? path.join(root, 'out/real/apps/start-tailwind-v4/node_modules'))
const app = mkdtempSync(path.join(root, 'out/tailwind-build-'))
const chrome = process.env.CHROME ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
const sample = '<section class="nested"><div id="sample" class="child flex p-4 md:gap-3 hover:opacity-50">hello</div></section>'
const css = `@import "tailwindcss" source(none);
@source "./templates";
.nested, #other {
  & > .child { color: rgb(10 20 30); }
  @media (min-width: 600px) { & > .child { border-top-width: 3px; } }
}
.child { color: red; user-select: none; }
`
const source = path.join(app, 'templates/classes.html')
let browser
let watcher

function build(program, args) {
  try {
    execFileSync(program, args, { cwd: app, stdio: 'pipe', timeout: 120000 })
  } catch (e) {
    throw new Error(`${program}: ${e.stderr?.toString()}${e.stdout?.toString()}`, { cause: e })
  }
}

function stylesheet(dir) {
  const assets = path.join(app, dir, 'assets')
  const files = readdirSync(assets).filter(name => name.endsWith('.css'))
  assert.equal(files.length, 1)
  return readFileSync(path.join(assets, files[0]), 'utf8')
}

async function values(page) {
  return page.locator('#sample').evaluate(element => {
    const css = getComputedStyle(element)
    return [css.display, css.paddingTop, css.gap, css.opacity, css.color, css.borderTopWidth]
  })
}

async function waitForServer(child) {
  return new Promise((resolve, reject) => {
    let output = ''
    const timeout = setTimeout(() => reject(new Error(output || 'development server did not start')), 20000)
    child.once('error', error => { clearTimeout(timeout); reject(error) })
    child.once('exit', code => { clearTimeout(timeout); reject(new Error(`dev exited ${code}\n${output}`)) })
    for (const pipe of [child.stdout, child.stderr]) pipe.on('data', bytes => {
      output += bytes
      const url = output.match(/at (http:\/\/127\.0\.0\.1:\d+)/)?.[1]
      if (url) { clearTimeout(timeout); resolve(url) }
    })
  })
}

try {
  symlinkSync(modules, path.join(app, 'node_modules'), 'dir')
  mkdirSync(path.dirname(source))
  writeFileSync(source, sample)
  writeFileSync(path.join(app, 'package.json'), '{"name":"tailwind-build-fixture","private":true,"type":"module"}')
  writeFileSync(path.join(app, 'index.html'), `<!doctype html><html><head><meta charset="utf-8"></head><body>${sample}<script type="module" src="./main.js"></script></body></html>`)
  writeFileSync(path.join(app, 'main.js'), 'import "./main.css"\n')
  writeFileSync(path.join(app, 'main.css'), css)
  writeFileSync(path.join(app, 'vite.config.js'), 'import tailwind from "@tailwindcss/vite"; export default { plugins: [tailwind()] };\n')

  build(esb, ['index.html', '--outdir=dist-esb'])
  build(path.join(modules, '.bin/vite'), ['build', '--outDir=dist-vite', '--logLevel=error'])
  const ours = stylesheet('dist-esb')
  const theirs = stylesheet('dist-vite')
  assert.doesNotMatch(ours, /@tailwind|@source|&\s*>/)
  assert.match(ours, /-webkit-user-select:\s*none/)
  assert.match(ours, /:is\(\.nested,#other\)\s*>\s*\.child/)

  browser = await chromium.launch({ executablePath: chrome })
  const page = await browser.newPage({ viewport: { width: 900, height: 600 } })
  const builds = []
  for (const text of [ours, theirs]) {
    await page.setContent(`<!doctype html><style>${text}</style>${sample}`)
    const ordinary = await values(page)
    await page.locator('#sample').hover()
    builds.push([ordinary, await values(page)])
    await page.mouse.move(899, 599)
  }
  assert.deepEqual(builds[0], builds[1])
  assert.deepEqual(builds[0][0], ['flex', '16px', '12px', '1', 'rgb(10, 20, 30)', '3px'])
  assert.equal(builds[0][1][3], '0.5')

  const image = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
  mkdirSync(path.join(app, 'components'))
  writeFileSync(path.join(app, 'components/pixel.svg'), image)
  writeFileSync(path.join(app, 'components/surface.css'), '#sample { background-image: url("./pixel.svg"); }')
  writeFileSync(path.join(app, 'main.css'), css.replace('@source', '@import "./components/surface.css";\n@source'))
  build(esb, ['index.html', '--outdir=dist-assets'])
  const asset = readdirSync(path.join(app, 'dist-assets/assets')).find(name => /^pixel-[^.]+\.svg$/.test(name))
  assert.ok(asset)
  assert.ok(stylesheet('dist-assets').includes(asset))
  assert.equal(readFileSync(path.join(app, 'dist-assets/assets', asset), 'utf8'), image)

  const pageFile = path.join(app, 'index.html')
  writeFileSync(pageFile, readFileSync(pageFile, 'utf8').replace('</head>', '<link rel="stylesheet" href="./linked.css" media="screen"></head>'))
  const linked = path.join(app, 'linked.css')
  writeFileSync(linked, '#sample { margin-top: 7px; }')
  build(esb, ['index.html', '--outdir=dist-linked'])
  const html = readFileSync(path.join(app, 'dist-linked/index.html'), 'utf8')
  const linkedAsset = html.match(/href="\/([^"]+)" media="screen"/)?.[1]
  assert.ok(linkedAsset, 'production keeps the link media attribute')
  assert.match(readFileSync(path.join(app, 'dist-linked', linkedAsset), 'utf8'), /margin-top:\s*7px/)

  watcher = spawn(esb, ['index.html', '--hmr', '--serve=0', '--outdir=dev-esb', '--no-cache'], { cwd: app })
  await page.goto(await waitForServer(watcher))
  await page.waitForFunction(() => {
    const styles = getComputedStyle(document.querySelector('#sample'))
    return styles.paddingTop === '16px' && styles.marginTop === '7px'
  })
  const devImage = await page.locator('#sample').evaluate(async element => {
    const url = getComputedStyle(element).backgroundImage.match(/^url\("(.*)"\)$/)?.[1]
    if (url) return (await fetch(url)).text()
  })
  assert.equal(devImage, image)
  assert.equal(await page.locator('link[rel="stylesheet"]').getAttribute('media'), 'screen')
  await page.locator('#sample').evaluate(element => element.className = 'child p-[13px]')
  writeFileSync(source, '<div class="p-[13px]"></div>')
  await page.waitForFunction(() => getComputedStyle(document.querySelector('#sample')).paddingTop === '13px')
  writeFileSync(linked, '#sample { margin-top: 9px; }')
  await page.waitForFunction(() => getComputedStyle(document.querySelector('#sample')).marginTop === '9px')
  console.log('Tailwind production styles match Vite, assets load, and template and linked CSS edits update the page')
} finally {
  if (watcher?.pid && watcher.exitCode === null && watcher.signalCode === null) {
    const exited = once(watcher, 'exit')
    watcher.kill()
    await exited
  }
  await browser?.close()
  rmSync(app, { recursive: true, force: true })
}
