// Inputs for checking the extractor: every string literal in the tests of oxide's extractor and
// pre-processors (Tailwind's own edge cases), each written to a file of its own with the extension
// its pre-processor reads (`html` for the extractor's, which no pre-processor changes).
//
// usage: node tools/tailwind-scan-corpus.mjs OXIDE_SRC OUT_DIR
//
// OXIDE_SRC is Tailwind's `crates/oxide/src`. Prints the files written, one per line.
import fs from 'node:fs'
import path from 'node:path'

const [src, out] = process.argv.slice(2)
fs.mkdirSync(out, { recursive: true })

const extensionOf = {
  clojure: 'cljs', elixir: 'heex', haml: 'haml', json: 'json', markdown: 'mdx', pug: 'pug', razor: 'cshtml',
  ruby: 'rb', rust: 'rs', slim: 'slim', svelte: 'svelte', template_toolkit: 'tt', twig: 'twig', vue: 'vue',
}

// The string literals of a Rust source after its `mod tests`: raw strings (`r#"…"#`, `r"…"`) and
// plain ones with their escapes undone.
function literals(text) {
  const at = text.indexOf('mod tests')
  const body = at < 0 ? '' : text.slice(at)
  const found = []
  const re = /r(#*)"([\s\S]*?)"\1|"((?:\\[\s\S]|[^"\\])*)"/g
  for (let m; (m = re.exec(body)); ) {
    if (m[2] !== undefined) found.push(m[2])
    else found.push(m[3].replace(/\\(u\{([0-9a-fA-F]+)\}|x([0-9a-fA-F]{2})|n|t|r|0|\\|"|'|\n\s*)/g, (all, e, u, x) =>
      u ? String.fromCodePoint(parseInt(u, 16)) : x ? String.fromCharCode(parseInt(x, 16)) :
      e === 'n' ? '\n' : e === 't' ? '\t' : e === 'r' ? '\r' : e === '0' ? '\0' : e[0] === '\n' ? '' : e))
  }
  return found
}

const files = [
  ...fs.readdirSync(path.join(src, 'extractor')).filter((f) => f.endsWith('.rs')).map((f) => ['extractor/' + f, 'html']),
  ...fs.readdirSync(path.join(src, 'extractor/pre_processors')).filter((f) => f.endsWith('.rs'))
    .map((f) => ['extractor/pre_processors/' + f, extensionOf[f.slice(0, -3)]]).filter(([, e]) => e),
  ['scanner/mod.rs', 'html'],
]
let n = 0
for (const [file, extension] of files) {
  for (const literal of literals(fs.readFileSync(path.join(src, file), 'utf8'))) {
    if (literal.length < 2) continue
    const name = path.join(out, `${String(n++).padStart(5, '0')}-${path.basename(file, '.rs')}.${extension}`)
    fs.writeFileSync(name, literal)
    console.log(name)
  }
}
