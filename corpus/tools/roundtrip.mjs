// Differential test: esbuild(original) must equal esbuild(our printed output).
// usage: node roundtrip.mjs LISTFILE OUTDIR [--show N]
import fs from 'node:fs';
import * as esbuild from 'esbuild';
import * as acorn from 'acorn';
const [list, outdir] = process.argv.slice(2);
const show = Number((process.argv.indexOf('--show') > 0 && process.argv[process.argv.indexOf('--show') + 1]) || 12);
const paths = fs.readFileSync(list, 'utf8').split('\n').filter(Boolean);
const norm = (code) => {
  try { return { ok: esbuild.transformSync(code, { loader: 'js', logLevel: 'silent', legalComments: 'none', minifyWhitespace: true }).code }; }
  catch (e) { return { err: e.errors?.[0]?.text ?? String(e) }; }
};
// esbuild preserves some written parentheses. So when its text differs, compare
// acorn's trees, with positions and raw spellings removed.
const strip = (n) => JSON.stringify(n, (k, v) => (k === 'start' || k === 'end' || k === 'raw' ? undefined : v));
const tree = (code) => { for (const sourceType of ['script', 'module']) { try { return strip(acorn.parse(code, { ecmaVersion: 'latest', sourceType, allowHashBang: true, allowReturnOutsideFunction: true })); } catch {} } return null; };
const astEqual = (a, b) => { const x = tree(a); return x !== null && x === tree(b); };
let arrowParens = 0, same = 0, skipped = 0, diff = 0, missing = 0, unparsable = 0; const bad = [];
paths.forEach((p, i) => {
  const orig = norm(fs.readFileSync(p, 'utf8'));
  if (orig.err) { skipped++; return; }             // esbuild itself rejects the original
  const printed = `${outdir}/${i}.js`;
  if (!fs.existsSync(printed)) { missing++; bad.push([p, 'our parser failed']); return; }
  const ours = norm(fs.readFileSync(printed, 'utf8'));
  if (ours.err) { unparsable++; bad.push([p, 'our output does not parse: ' + ours.err, printed]); return; }
  if (ours.ok === orig.ok) same++;
  else if (astEqual(fs.readFileSync(p, 'utf8'), fs.readFileSync(printed, 'utf8'))) arrowParens++;
  else { diff++; bad.push([p, 'normalized output differs', printed]); }
});
console.log(JSON.stringify({ total: paths.length, identical: same, sameAcornTree: arrowParens, differs: diff, ourOutputInvalid: unparsable, ourParserFailed: missing, esbuildRejectsOriginal: skipped }));
for (const b of bad.slice(0, show)) console.log(b.join(' | '));
