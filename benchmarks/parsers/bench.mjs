// Parse each file of a list with one parser, in this process, after warming up: the best and the
// median of N timed runs, in microseconds. The parser's AST is made in full as a JavaScript value
// (Oxc's `program` getter is read, which builds it). Each file's goal is settled first: a module,
// else a script.
//   node bench.mjs PARSER LIST ROUNDS [WARMUP]
// With ROUNDS = 1 and WARMUP = 0, a whole corpus in one pass: the total and the files that failed.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const HERE = new URL('../../', import.meta.url).pathname;
const S = new URL('.', import.meta.url).pathname;
const req = (dir) => createRequire(HERE + dir + '/package.json');
const [name, listFile, roundsText, warmText] = process.argv.slice(2);
const rounds = +roundsText, warm = warmText === undefined ? 3 : +warmText;

const ts = (f) => /\.(c|m)?tsx?$/.test(f);
const jsx = (f) => /\.[jt]sx$/.test(f);
let parse;
switch (name) {
  case 'acorn': {
    const acorn = req('tests')('acorn');
    parse = (src, f, module) => acorn.parse(src, { ecmaVersion: 'latest', sourceType: module ? 'module' : 'script', allowHashBang: true, allowReturnOutsideFunction: !module });
    break;
  }
  case 'meriyah': {
    const meriyah = createRequire(S + 'package.json')('meriyah');
    parse = (src, f, module) => meriyah.parse(src, { module, next: true, jsx: jsx(f), globalReturn: !module });
    break;
  }
  case 'babel': {
    const babel = req('benchmarks/heldout')('@babel/parser');
    parse = (src, f, module) => babel.parse(src, { sourceType: module ? 'module' : 'script', allowReturnOutsideFunction: !module, errorRecovery: false,
      plugins: [...(ts(f) ? [['typescript', {}], 'decorators-legacy'] : []), ...(jsx(f) ? ['jsx'] : [])] });
    break;
  }
  case 'typescript': {
    const tsc = req('benchmarks/realworld')('typescript');
    // TypeScript's parser reports syntax errors beside the tree rather than throwing.
    parse = (src, f) => {
      const sf = tsc.createSourceFile(f, src, tsc.ScriptTarget.Latest, false, ts(f) ? (jsx(f) ? tsc.ScriptKind.TSX : tsc.ScriptKind.TS) : (jsx(f) ? tsc.ScriptKind.JSX : tsc.ScriptKind.JS));
      if (sf.parseDiagnostics.length) throw new Error(sf.parseDiagnostics[0].messageText);
      return sf;
    };
    break;
  }
  case 'swc': {
    const swc = req('benchmarks/heldout')('@swc/core');
    parse = (src, f, module) => swc.parseSync(src, { syntax: ts(f) ? 'typescript' : 'ecmascript', tsx: ts(f) && jsx(f), jsx: !ts(f) && jsx(f), target: 'esnext', isModule: module, decorators: true });
    break;
  }
  case 'oxc':
  case 'oxc-raw': {
    const oxc = createRequire(S + 'package.json')('oxc-parser');
    const raw = name === 'oxc-raw';
    parse = (src, f, module) => {
      const r = oxc.parseSync(f, src, { sourceType: module ? 'module' : 'script', ...(raw ? { experimentalRawTransfer: true } : {}) });
      if (r.errors.length) throw new Error(r.errors[0].message);
      return r.program;
    };
    break;
  }
  case 'esbuild': {
    // No parse-only API: a transform parses and prints.
    const esbuild = req('tests')('esbuild');
    // TypeScript projects such as VS Code use parameter decorators, as their tsconfig says.
    parse = (src, f, module) => esbuild.transformSync(src, { loader: ts(f) ? (jsx(f) ? 'tsx' : 'ts') : (jsx(f) ? 'jsx' : 'js'), format: module ? 'esm' : undefined, logLevel: 'silent',
      ...(ts(f) ? { tsconfigRaw: { compilerOptions: { experimentalDecorators: true } } } : {}) });
    break;
  }
  default: throw new Error('no parser ' + name);
}

const files = readFileSync(listFile, 'utf8').split('\n').filter(Boolean);
const goal = (src, f) => {
  for (const module of [true, false]) { try { parse(src, f, module); return module; } catch {} }
  return null;
};
if (rounds === 1 && warm === 0) {
  // One pass over a corpus: settle each file's goal untimed, then time a parse of every file.
  const srcs = files.map((f) => readFileSync(f, 'utf8'));
  const goals = srcs.map((s, i) => goal(s, files[i]));
  let bytes = 0, failed = 0;
  const t0 = process.hrtime.bigint();
  for (let i = 0; i < files.length; i++) {
    if (goals[i] === null) { failed++; continue; }
    parse(srcs[i], files[i], goals[i]); bytes += Buffer.byteLength(srcs[i]);
  }
  const us = Number(process.hrtime.bigint() - t0) / 1000;
  console.log(`CORPUS ${name} files ${files.length} failed ${failed} bytes ${bytes} us ${Math.round(us)}`);
} else {
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    const module = goal(src, f);
    if (module === null) { console.log(`SKIP ${f}`); continue; }
    for (let i = 0; i < warm; i++) parse(src, f, module);
    const times = [];
    for (let i = 0; i < rounds; i++) {
      const t0 = process.hrtime.bigint();
      parse(src, f, module);
      times.push(Number(process.hrtime.bigint() - t0) / 1000);
    }
    times.sort((a, b) => a - b);
    console.log(`BENCH ${f} ${Buffer.byteLength(src)} ${Math.round(times[0])} ${Math.round(times[rounds >> 1])}`);
  }
}
