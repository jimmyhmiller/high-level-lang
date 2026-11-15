// Candidates beyond what the apps use, for checking our Tailwind compiler against Tailwind's: every
// class Tailwind's design system lists (`getClassList`), every variant it lists (`getVariants`)
// with each of its values, over a few utilities, compounds of compound variants, and a set of
// hand-written shapes (arbitrary values, properties and variants, modifiers, negatives, fractions,
// important, bare values). Writes one JSON line: {candidates, compiled} with Tailwind's output for
// a stylesheet of `@import "tailwindcss";` (and whatever more is given) built with them.
//
// usage: node tools/tailwind-coverage.mjs PROJECT SHEET.css [extra candidates file]
import { createRequire } from 'node:module'
import path from 'node:path'
import fs from 'node:fs'
import { pathToFileURL } from 'node:url'

const [project, sheet, extraFile] = process.argv.slice(2)
const root = path.resolve(project)
const require = createRequire(path.join(root, 'package.json'))
const node = await import(pathToFileURL(require.resolve('@tailwindcss/node')).href)
const file = path.resolve(sheet)
const css = fs.readFileSync(file, 'utf8')
const ds = await node.__unstable__loadDesignSystem(css, { base: path.dirname(file) })
const classes = ds.getClassList().map(([name]) => name)
const bases = ['flex', 'p-4', 'bg-red-500/50', 'text-lg/7', '[color:red]', 'underline!']
const variants = []
for (const v of ds.getVariants()) {
  if (v.isArbitrary) {
    for (const value of v.values) variants.push(`${v.name}-${value}`)
    if (v.values.length === 0) variants.push(v.name)
    if (v.hasDash) variants.push(`${v.name}-[foo]`)
  } else {
    variants.push(v.name)
  }
}
const compounds = ['not', 'group', 'peer', 'has', 'in']
const variantCandidates = []
for (const v of variants) for (const b of bases) variantCandidates.push(`${v}:${b}`)
for (const c of compounds) for (const v of ['hover', 'focus', 'first', 'data-[state=open]', 'aria-checked', 'supports-[display:grid]', 'md', 'max-lg', '[&.is-x]', '@lg', 'group-hover', 'not-first'])
  for (const b of bases.slice(0, 2)) variantCandidates.push(`${c}-${v}:${b}`, `${c}-${v}/name:${b}`)
const handWritten = [
  'w-1/2', 'w-[calc(100%-2rem)]', '-mt-4', '-translate-x-1/2', 'top-[10px]', 'inset-x-[3px]', 'm-[-4px]', 'size-[3rem]',
  'bg-[#abc]', 'bg-[url(/a.png)]', 'bg-(--my-color)', 'bg-(color:--my-color)', 'bg-[length:10px_20px]', 'bg-[position:center]',
  'text-[14px]', 'text-[14px]/[20px]', 'text-sm/6', 'text-red-500/[33%]', 'text-red-500/25', 'text-[red]/50', 'text-(--x)',
  'border-[3px]', 'border-x-[#fff]', 'border-[length:2px]', 'shadow-[0_0_2px_red]', 'shadow-red-500/50', 'shadow-lg/20', 'shadow-[0_1px_var(--x)]/50',
  'ring-[3px]', 'ring-red-500', 'ring-offset-2', 'ring-offset-red-500', 'inset-shadow-sm', 'inset-shadow-[0_1px_red]', 'text-shadow-lg/50',
  'drop-shadow-lg', 'drop-shadow-red-500', 'drop-shadow-[0_0_2px_red]', 'drop-shadow-lg/25', 'blur-[2px]', 'grayscale-50', 'hue-rotate-15', '-hue-rotate-15',
  'grid-cols-[1fr_2fr]', 'grid-cols-12', 'col-span-3', 'row-start-[7]', 'gap-[1.5rem]', 'space-x-4', '-space-y-2', 'space-x-0', 'divide-x-2', 'divide-y',
  'aspect-[4/3]', 'aspect-16/9', 'z-[100]', '-z-10', 'order-[13]', 'opacity-[.67]', 'opacity-37', 'leading-[1.2]', 'tracking-[-.02em]', '-tracking-wide',
  'font-[600]', 'font-[Inter]', 'font-[family-name:Inter]', 'duration-[1.5s]', 'delay-75', 'ease-[cubic-bezier(0.1,0.2,0.3,0.4)]',
  'transition-[height]', 'animate-[spin_2s_linear]', 'content-[\'hello\']', 'content-["x"]', 'scale-[1.7]', '-scale-x-50', 'rotate-[30deg]', 'rotate-[1_0_0_45deg]',
  'skew-x-[3deg]', 'translate-z-4', 'perspective-[100px]', 'origin-[10%_20%]', 'cursor-[grab]', 'columns-3', 'columns-[10rem]',
  'bg-linear-to-r', 'bg-linear-45', '-bg-linear-45', 'bg-linear-[25deg]', 'bg-linear-to-r/oklch', 'bg-conic-180', 'bg-conic/[in_hsl]', 'bg-radial-[at_50%_75%]',
  'from-red-500', 'from-10%', 'via-[#123]', 'to-blue-500/50', 'from-[5%]', 'mask-t-from-50%', 'mask-linear-from-20', 'mask-radial-to-[#000]', 'mask-conic-45',
  'fill-red-500/50', 'stroke-[3]', 'stroke-2', 'outline-[3px]', 'outline-red-500', 'outline-offset-[3px]', '-outline-offset-2', 'decoration-[3px]', 'decoration-2',
  'underline-offset-[3px]', 'indent-[2em]', '-indent-4', 'line-clamp-[7]', 'max-w-[50%]', 'max-w-screen-lg', 'min-h-[100dvh]', 'basis-1/3',
  'flex-[2_2_0%]', 'flex-1/2', 'shrink-[2]', 'grow-3', 'flex-shrink-0', 'flex-grow', 'start-4', '-end-1/2', 'start-[3px]',
  'scroll-mt-[3px]', 'scroll-p-4', 'snap-x', 'snap-mandatory', 'accent-[#abc]', 'caret-red-500', 'placeholder-red-500/50', 'list-[square]', 'list-image-none',
  'object-[50%_50%]', 'will-change-[top]', 'contain-[paint]', 'backdrop-blur-[2px]', 'backdrop-opacity-25', 'backdrop-brightness-[1.5]',
  'font-stretch-75%', 'font-stretch-[66%]', 'tab-[8]', 'zoom-150', '@container/sidebar', '@container-normal', 'container', 'sr-only',
  '[mask-type:luminance]', '[--my-var:10px]', '[color:red]/50', 'hover:[color:red]', '!flex', 'flex!', 'md:hover:flex', 'dark:md:p-4',
  '[&>*]:p-4', '[&_p]:mt-2', '[@media(min-width:900px)]:flex', '[@supports(display:grid)]:grid', 'data-[size=lg]:p-8', 'data-open:flex',
  'aria-[sort=ascending]:flex', 'nth-3:flex', 'nth-[2n+1]:flex', 'nth-last-of-type-2:flex', 'supports-[display:grid]:grid',
  'supports-grid:grid', 'min-[400px]:flex', 'max-[600px]:p-4', 'min-md:flex', '@min-md:flex', '@max-sm:p-4', '@[300px]:flex', '@sm/main:flex',
  'group-hover/item:flex', 'peer-checked/x:flex', 'has-[img]:p-4', 'in-focus:flex', 'not-hover:flex', 'not-[.x]:flex', 'not-supports-grid:flex',
  'not-md:flex', 'not-dark:flex', '*:p-4', '**:p-4', 'before:content-["*"]', 'after:block', 'file:p-2', 'placeholder:text-red-500', 'marker:text-red-500',
  'selection:bg-red-500', 'first-letter:text-2xl', 'open:flex', 'inert:hidden', 'starting:opacity-0', 'print:hidden', 'portrait:hidden', 'rtl:flex',
  'contrast-more:flex', 'motion-safe:transition', 'forced-colors:flex', 'pointer-coarse:p-4', 'noscript:hidden', 'details-content:flex',
  'p-0.5', 'p-1.25', 'p-1.3', 'w-1.5', 'mt-[1px]', 'p-px', '-m-px', 'w-full', 'h-svh', 'size-12', 'inset-1/2', 'top-1/3', '-left-1/4',
  'bg-white/[0.07]', 'bg-black/[.29]', 'text-white/[0.57]', 'bg-red-500/[var(--o)]', 'bg-current/50', 'bg-transparent', 'bg-inherit',
  'text-[length:var(--x)]', 'text-[color:var(--x)]', 'w-(--x)', 'w-(length:--x)', 'p-(--gutter)',
]
let extra = []
if (extraFile) extra = fs.readFileSync(extraFile, 'utf8').split('\n').filter(Boolean)
const candidates = [...new Set([...classes, ...variantCandidates, ...handWritten, ...extra])]
const compiler = await node.compile(css, { base: path.dirname(file), shouldRewriteUrls: true, onDependency() {} })
const compiled = compiler.build(candidates)
console.log(JSON.stringify({ file: path.relative(root, file), sources: [{ base: path.dirname(file), pattern: '', negated: false }], candidates, compiled }))
