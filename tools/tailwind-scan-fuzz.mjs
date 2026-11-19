// Random text for checking the extractor and pre-processors against oxide: lines made of the
// bytes the machines treat specially, and of pieces of class names, written to one file per
// extension (the extractor works line by line, so one file holds many cases).
//
// usage: node tools/tailwind-scan-fuzz.mjs OUT_DIR [SEED] [LINES]
//
// Then `node tools/tailwind-scan-check.mjs content OUT_DIR/*`. With the same seed the same text is
// made again.
import fs from 'node:fs'
import path from 'node:path'

const [out, seedArg = '1', linesArg = '4000'] = process.argv.slice(2)
let seed = Number(seedArg) >>> 0 || 1
const random = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296)
const pick = (xs) => xs[Math.floor(random() * xs.length)]

const pieces = [
  'flex', 'p-4', 'px-2.5', 'bg-red-500', 'hover:', 'md:', '[', ']', '(', ')', '{', '}', '<', '>', ':', '/', '!', '-',
  '--', '_', '.', ',', ';', '=', '"', "'", '`', '\\', '$', '${', '%', '@', '*', '**', '#', '~', '&', '|', '+', '?', ' ',
  '  ', '\t', 'var(', '--x', '[color:red]', '[&:hover]', 'group-hover/name', '/50', '/[20%]', '(--c)', '-[]', 'a', 'Z',
  '2xl', '1.5', 'é', '☃', ' ', 'class', 'className', ':class', '%w[', '%p(', 'erb_template <<~ERB', 'ERB',
  '<template lang="pug">', '</template>', 'html!', 'addClass(', 'removeClass(', '[%', '%]', '~w(', '~s[', '@@', '@("@")',
  ' class:', '\nclass:', '-#', '/ ', '= ', '- ', '~ ', '\n', '\n  ', '\n    ', 'data-[x=y]', 'supports-(--z)', '*:',
  '[--v:1px]', 'w-[calc(100%-1rem)]', "content-['x']", 'url(https://a.b/c)', 'x:', 'b:c:d', ':div.p-2', 'text-[length:var(--w)]',
]

function line() {
  const n = 1 + Math.floor(random() * 14)
  let s = ''
  for (let i = 0; i < n; i++) s += pick(pieces)
  return s
}

const extensions = ['html', 'js', 'clj', 'heex', 'cshtml', 'haml', 'json', 'md', 'pug', 'rb', 'slim', 'svelte', 'rs', 'tt', 'twig', 'vue', 'css']
fs.mkdirSync(out, { recursive: true })
const lines = Number(linesArg)
for (const extension of extensions) {
  // Pre-processors read a whole file, so theirs are many small files' worth in blocks.
  const blocks = []
  for (let b = 0; b < (extension === 'html' || extension === 'js' ? 1 : 40); b++) {
    const text = []
    for (let i = 0; i < (extension === 'html' || extension === 'js' ? lines : lines / 40); i++) text.push(line())
    blocks.push(text.join('\n') + '\n')
  }
  blocks.forEach((text, b) => {
    const file = path.join(out, `fuzz-${seedArg}-${b}.${extension}`)
    fs.writeFileSync(file, text)
    console.log(file)
  })
}
