// Synthetic projects for checking our scanner against oxide (tools/tailwind-scan-check.mjs): each
// a directory tree and the sources Tailwind would give the scanner for it. They exercise what the
// apps do not: gitignore and .ignore rules, git's exclude file, nested repositories, @source
// patterns and `@source not`, restricted patterns, binary and ignored files, links, every
// pre-processor's file type, and odd candidate shapes.
//
// Fixtures inside the repository get a `.git` of their own, so the repository's `out/` rule does
// not make them external; those that need no repository at all are made in the system's
// temporary directory.
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

function write(root, files) {
  for (const [name, content] of Object.entries(files)) {
    const file = path.join(root, name)
    fs.mkdirSync(path.dirname(file), { recursive: true })
    if (typeof content === 'object' && !Buffer.isBuffer(content)) fs.symlinkSync(content.link, file)
    else fs.writeFileSync(file, content)
  }
}

const tag = (name) => `<div class="c-${name.replace(/[^a-z0-9]/gi, '-')} hover:c-${name.replace(/[^a-z0-9]/gi, '_')}">\n`

// A tree where each file holds a class name made from its own path, so a file read shows.
function tree(names) {
  return Object.fromEntries(names.map((n) => [n, tag(n)]))
}

const fixtures = {
  gitignore: {
    git: true,
    files: {
      '.git/info/exclude': '# exclude file\nexcluded.html\n',
      '.gitignore': [
        'dist/', '*.log', '!keep.log', '/only-root.html', 'nested/**/deep.html', '# a comment', '\\#hash.html',
        'trailing.html   ', 'escaped\\ ', '**/build', 'a/**/b', 'ignored/', '!ignored/x.html', '*.txt', 'docs/*',
        '!docs/keep/', 'star*/', '[ab]c.html', 'q?.html', 'unclosed[.html', 'deep/**', 'x/y/', '\\!bang.html', '',
      ].join('\n') + '\n',
      '.ignore': '!notes2.txt\nby-ignore.html\n',
      'sub/.gitignore': '!special.txt\n/local.html\n',
      'sub/.ignore': '',
      ...tree([
        'index.html', 'dist/a.html', 'keep.log', 'x.log', 'only-root.html', 'sub/only-root.html', 'nested/x/y/deep.html',
        'nested/deep.html', 'nested/shallow.html', '#hash.html', 'trailing.html', 'escaped ', 'build/a.html',
        'sub/build/a.html', 'a/b', 'a/x/b', 'a/x/c', 'ignored/x.html', 'notes.txt', 'notes2.txt', 'sub/special.txt',
        'sub/other.txt', 'sub/local.html', 'sub/sub/local.html', 'excluded.html', 'sub/excluded.html', 'by-ignore.html',
        'docs/a.html', 'docs/keep/b.html', 'starry/a.html', 'start.html', 'ac.html', 'bc.html', 'cc.html', 'q1.html',
        'q12.html', 'unclosed[.html', 'deep/a/b.html', 'deep.html', 'x/y/z.html', 'y/z.html', '!bang.html', 'café.html',
      ]),
    },
    sources: [{ base: '.', pattern: '**/*' }],
  },
  'nested-repo': {
    git: true,
    files: {
      '.gitignore': '*.md\nsub/generated.html\n',
      'sub/.git/HEAD': 'ref: refs/heads/main\n',
      'sub/.gitignore': 'local.html\n',
      ...tree(['README.md', 'index.html', 'sub/readme.md', 'sub/generated.html', 'sub/local.html', 'sub/page.html']),
    },
    sources: [{ base: '.', pattern: '**/*' }],
  },
  worktree: {
    files: {
      '.git': 'gitdir: GITDIR/worktrees/wt\n',
      'GITDIR/worktrees/wt/commondir': '../..\n',
      'GITDIR/info/exclude': 'from-common.html\n',
      ...tree(['index.html', 'from-common.html']),
    },
    fix: (root) => fs.writeFileSync(path.join(root, '.git'), `gitdir: ${path.join(root, 'GITDIR/worktrees/wt')}\n`),
    sources: [{ base: '.', pattern: '**/*' }],
  },
  'detection-rules': {
    git: true,
    files: {
      '.env': 'class="env-file"\n',
      '.env.local': 'class="env-local"\n',
      'package-lock.json': '{"x": "lock-json"}\n',
      'pnpm-lock.yaml': 'lock-yaml\n',
      'bun.lockb': 'lockb\n',
      'yarn.lock': 'yarn-lock\n',
      'styles.scss': '.a { @apply scss-class; }\n',
      'styles.css': '.a { color: var(--used-var); --defined-var: 1; }\n.b { width: calc(var(--other) * 2) }\n',
      'logo.png': 'png-bytes class="png"\n',
      'assets.png/inside.html': tag('assets.png/inside.html'),
      'node_modules/pkg/index.js': tag('node_modules'),
      '.next/x.js': tag('next'),
      'venv/x.py': tag('venv'),
      'X.LOG': tag('upper-log'),
      'README': tag('readme-no-extension'),
      '.DS_Store': 'ds-store\n',
      'file.DS_Store': 'file-ds-store\n',
      '.hidden/x.html': tag('hidden-dir'),
      '.hidden.html': tag('hidden-file'),
      'archive.tar.gz': 'tar-gz\n',
      'model.bin': 'bin-file\n',
      'font.woff2': 'woff2\n',
    },
    sources: [{ base: '.', pattern: '**/*' }],
  },
  'source-patterns': {
    git: true,
    files: {
      '.gitignore': 'generated/\n',
      'styles/app.css': '@import "tailwindcss";\n',
      ...tree([
        'src/a.html', 'src/b.js', 'src/skip/c.html', 'src/deep/d.html', 'other/page.vue', 'other/page.html', 'lib/e.ts',
        'lib/sub/f.ts', 'x/one.js', 'x/two.ts', 'y/three.js', 'z/four.js', 'generated/g.html', 'generated/h.js',
        'node_modules/mylib/dist/i.js', 'node_modules/other/j.js', 'node_modules/mylib/logo.png', 'n01.html', 'n02.html',
        'n03.html', 'n10.html', 'ca.txt', 'cb.txt', 'cd.txt',
      ]),
    },
    sources: [
      { base: '.', pattern: '**/*' },
      { base: 'styles', pattern: '../src/**/*.html' },
      { base: 'styles', pattern: '../other/page.vue' },
      { base: 'styles', pattern: '../lib' },
      { base: 'styles', pattern: '../src/skip/**', negated: true },
      { base: 'styles', pattern: '../{x,y}/*.{js,ts}' },
      { base: 'styles', pattern: '../generated/h.js' },
      { base: 'styles', pattern: '../node_modules/mylib' },
      { base: 'styles', pattern: '../n{=01..03}.html' },
      { base: 'styles', pattern: '../c{a..b}.txt' },
    ],
  },
  restricted: {
    git: true,
    files: tree([
      'pages/bar/a.html', 'pages/baz/b.html', 'pages/qux/c.html', 'pages/index.html', 'pages/about.html', 'pages/bar/x.js',
      'other/o.html', 'pages/nested/root/n.html', 'pages/nested/root/deeper/m.html',
    ]),
    sources: [
      { base: '.', pattern: 'pages/ba*/*.html' },
      { base: '.', pattern: 'pages/index.html' },
      { base: 'pages/nested', pattern: 'root/*.html' },
    ],
  },
  'not-only': {
    git: true,
    files: tree(['a.html', 'b/c.html', 'b/d.js', 'e/f.html']),
    sources: [
      { base: '.', pattern: '**/*' },
      { base: '.', pattern: 'b/*.html', negated: true },
      { base: '.', pattern: 'e', negated: true },
    ],
  },
  links: {
    git: true,
    files: {
      'real/a.html': tag('real-a'),
      'real/sub/b.html': tag('real-sub-b'),
      'outside-target/c.html': tag('outside-c'),
      'link-to-file.html': { link: 'real/a.html' },
      'link-to-dir': { link: 'real' },
      'real/loop': { link: '..' },
      'broken.html': { link: 'nowhere.html' },
    },
    sources: [{ base: '.', pattern: '**/*' }],
  },
  preprocessors: {
    git: true,
    files: {
      'a.clj': '(ns app)\n[:div.flex.gap-1.5 {:class "clj-string-class"} ;; clj-comment\n :p-4 \'bg-white \'(:m-2 "x") #{:text-sm}]\n',
      'a.cljs': '[:div {:className (str "a" :clj-classname)} :px-2.5]\n',
      'a.heex': '<div class={~w(heex-sigil p-1)} id="x" class="heex-attr">\n~s[heex-s (nested) h-1]\n',
      'a.ex': 'def x, do: ~c{ex-sigil \\} w-2}\n',
      'a.cshtml': '<div class="@@razor-at @("@")razor-paren">\n',
      'a.haml': '%div.haml-class{class: "haml-attr"}\n  -# silent comment haml-silent\n    still silent\n  / html comment haml-html\n  = link_to "x", class: "haml-ruby"\n  - if x\n    %p.haml-in-block text\n  %span(class="haml-paren") #{interp}\n  %ul{class: %w[haml-w1 haml-w2]}\n',
      'a.json': '{"class": ["json-a", "json-b"], "nested": {"k": "json-c"}, "s": "[json-in-string]"}\n',
      'a.jsonl': '{"a":"jsonl-a"}\n{"b":["jsonl-b"]}\n',
      'a.md': 'Some text {props.md-dot.class} and `md-code` [link](md-link)\n<div class="md-html">\n',
      'a.mdx': '<Box className={styles.mdx-a + "mdx-b"} />\n{x.y}\n',
      'a.pug': 'div.pug-a.pug-b(class="pug-attr" data-x="a (b") pug-text\n  span.underline.font-bold(title="x") km\n  | (\n  li:  a.pug-li(href="#")\n  p.px-2.5.2xl:pug-variant\n  script.\n    // don\'t pug-script\n',
      'a.rb': '# rb-comment\nclass X\n  erb_template <<~ERB\n    <div class="rb-heredoc">\n  ERB\n  x = %w[rb-w1 rb-w2]\n  y = %p(rb-p)\n  z = "rb-string #{rb_interp}"\n  m = 50%w.rb-mod\nend\n',
      'a.erb': '<%# locals: (erb-local:) %>\n<div class="<%= x ? \'erb-a\' : \'erb-b\' %>">\n',
      'a.slim': '.slim-a.slim-b[data-x="1"]\n  p.slim-c(attr=value) slim-text\n  div class=%w[slim-w1 slim-w2]\n  .text-xl.text-red-600[\n    data-foo="bar"\n  ]\n',
      'a.slang': 'div.slang-a\n',
      'a.svelte': '<div class:svelte-active={x} class="svelte-attr">\n\tclass:svelte-tab\nclass:svelte-line\n',
      'a.rs': 'view! { <div class:rs-leptos=true class="rs-attr"/> }\n',
      'b.rs': 'html! { div.maud-a.maud-b[cond] { "maud-string" } p.px-2.5 { } span.text-[red].maud-c {} }\n',
      'a.tt': '[% IF x %]<div class="tt-a">[% END %]\n',
      'a.twig': '<div {{ attributes.addClass(\'twig-add\') }} {{ x.removeClass(["twig-remove"]) }}>\n',
      'a.vue': '<template lang="pug">\ndiv.vue-pug-a(class="vue-pug-b")\n</template>\n<script>export default { data: () => ({ c: "vue-script" }) }</script>\n',
      'b.vue': '<template>\n  <div class="vue-plain" :class="{ \'vue-obj\': x }"></div>\n</template>\n',
      'a.html': '<div class="html-a">\r\n<p class="crlf-b">\r\n',
    },
    sources: [{ base: '.', pattern: '**/*' }],
  },
  shapes: {
    git: true,
    files: {
      'shapes.html': [
        '<div class="bg-[#0088cc] bg-red-500/50 bg-red-500/[50%] bg-(--my-color) bg-(color:--x) w-[calc(100%-2rem)]">',
        '<div class="[color:red] [--my-var:10px] ![color:red] [color:red]! hover:[color:red] [&:hover]:flex [&>*]:p-2">',
        '<div class="data-[state=open]:flex supports-(--x):grid group-hover/name:block @md:flex @[400px]:p-2 *:p-1 **:m-1">',
        '<div class="content-[\'hello_world\'] content-["x"] bg-[url(\'/a.png\')] grid-cols-[repeat(2,minmax(0,1fr))]">',
        '<div class="-mx-2.5 px-2.5 from-15% w-1/2 text-2xs !flex flex! !bg-red-500! -[] group-[]:flex [] [x] a b c">',
        '<div class="émoji-☃ bg-[☃] [content:\'☃\'] ☃:flex 𝒳-class">',
        '{ underline: true, "font-bold": x }  class:flex={x} [class.foo]="x" [:div.p-2]',
        '<f:case value="0">from-blue-900 to-cyan-200</f:case>',
        '{% if true %}flex{% else %}block{% endif %}',
        "$el.classList.add(\\'-translate-x-full\\'); $el.classList.add(\\'transition-transform\\')",
        'var(--used) --custom-prop: 1; --a\\#b --1x ---',
        'bg-[${x}] [${y}] bg-[a_b] bg-[a\\ b] bg-[[nested]] bg-[(a)]] w-[1px]/[2px] text-[length:var(--x)]',
        '\u0000flex\u0000 p-4\u0000',
      ].join('\n') + '\n',
      'latin1.html': Buffer.from([0x3c, 0x64, 0x69, 0x76, 0x20, 0x63, 0x6c, 0x61, 0x73, 0x73, 0x3d, 0x22, 0x63, 0x61, 0x66, 0xe9, 0x20, 0x66, 0x6c, 0x65, 0x78, 0x22, 0x3e, 0x0a]),
    },
    sources: [{ base: '.', pattern: '**/*' }],
  },
}

// Fixtures with no repository above them: a parent's .gitignore names the project (so its auto
// source is external) and another's rule applies to its files, read up to the file system root.
const outside = {
  'no-repo': {
    files: {
      '.gitignore': 'project\n',
      'project/.gitignore': '*.skip.html\n',
      ...tree(['project/a.html', 'project/b.skip.html', 'project/node_modules/x.js']),
    },
    base: 'project',
    sources: [{ base: '.', pattern: '**/*' }],
  },
  'no-repo-auto': {
    files: {
      '.gitignore': '*.parent.html\n',
      ...tree(['project/a.html', 'project/b.parent.html']),
    },
    base: 'project',
    sources: [{ base: '.', pattern: '**/*' }],
  },
}

// Random projects: files at paths made of awkward names, gitignore files of random globs at a few
// levels, and random @source patterns (and `@source not`) beside the root's `**/*`.
function fuzzFixture(seedValue) {
  let seed = seedValue >>> 0 || 1
  const random = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296)
  const pick = (xs) => xs[Math.floor(random() * xs.length)]
  const names = ['a', 'b', 'ab', 'a.html', 'b.js', 'c.ts', 'x.y.vue', '.hidden', 'build', 'dist', 'node_modules', 'src',
    'lib', '[x]', 'b c', 'é.md', 'q1.txt', 'log.log', 'img.png', 'data.json', 'a-b_c', '{a}', '#x', '!y', 'deep']
  const dirs = ['src', 'lib', 'src/a', 'src/b', 'lib/deep', 'build', 'dist', 'src/a/build', 'x', 'x/y', 'node_modules/p', 'ab', '[x]']
  const files = {}
  const taken = new Set(dirs.flatMap((d) => d.split('/').map((_, i, parts) => parts.slice(0, i + 1).join('/'))))
  for (let i = 0; i < 40; i++) {
    const dir = random() < 0.2 ? '' : pick(dirs) + '/'
    const name = pick(names)
    if (!taken.has(dir + name)) files[dir + name] = tag(dir + name)
  }
  const glob = () => {
    const parts = []
    const n = 1 + Math.floor(random() * 3)
    for (let i = 0; i < n; i++) parts.push(pick(['*', '**', 'a', 'b', 'src', 'build', '*.html', '*.{js,ts}', '?', '[ab]', '[!a]*', 'x', 'y',
      'a*', '*b', 'deep', '{a,b}', '\\[x]', 'é*', '[a-c]*', '.*']))
    return (random() < 0.3 ? '/' : '') + parts.join('/') + (random() < 0.2 ? '/' : '')
  }
  const ignore = () => Array.from({ length: 1 + Math.floor(random() * 5) }, () => (random() < 0.25 ? '!' : '') + glob()).join('\n') + '\n'
  files['.gitignore'] = ignore()
  for (const d of ['src', 'lib', 'x']) if (random() < 0.5) files[d + '/.gitignore'] = ignore()
  if (random() < 0.3) files['.ignore'] = ignore()
  const sources = [{ base: '.', pattern: '**/*' }]
  for (let i = 0; i < Math.floor(random() * 3); i++) {
    sources.push({ base: '.', pattern: glob().replace(/^\//, ''), negated: random() < 0.4 })
  }
  return { git: true, files, sources }
}

const fuzzCount = Number(process.env.TAILWIND_SCAN_FUZZ ?? 60)

// Makes every fixture afresh and answers each one's name and sources (bases absolute).
export function makeFixtures(inRepo) {
  for (let k = 1; k <= fuzzCount; k++) fixtures[`fuzz-${k}`] = fuzzFixture(k * 7919)
  const made = []
  fs.rmSync(inRepo, { recursive: true, force: true })
  for (const [name, f] of Object.entries(fixtures)) {
    const root = path.join(inRepo, name)
    fs.mkdirSync(root, { recursive: true })
    if (f.git) fs.mkdirSync(path.join(root, '.git/info'), { recursive: true })
    write(root, f.files)
    if (f.fix) f.fix(root)
    made.push({ name, sources: f.sources.map((s) => ({ base: path.resolve(root, s.base), pattern: s.pattern, negated: !!s.negated })) })
  }
  const away = path.join(fs.realpathSync(os.tmpdir()), 'tailwind-scan-fixtures')
  fs.rmSync(away, { recursive: true, force: true })
  for (const [name, f] of Object.entries(outside)) {
    const root = path.join(away, name)
    fs.mkdirSync(root, { recursive: true })
    write(root, f.files)
    made.push({ name, sources: f.sources.map((s) => ({ base: path.resolve(root, f.base, s.base), pattern: s.pattern, negated: !!s.negated })) })
  }
  return made
}
