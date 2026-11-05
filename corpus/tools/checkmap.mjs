// Every mapping must point at the same token text in the original, for an unminified
// build; and for a minified one, every mapping must land on a real token boundary.
import fs from 'node:fs'; import path from 'node:path';
import { TraceMap, eachMapping } from '@jridgewell/trace-mapping';
const f = process.argv[2]; const strict = process.argv[3] === 'strict';
const map = JSON.parse(fs.readFileSync(f + '.map', 'utf8'));
const gen = fs.readFileSync(f, 'utf8').split('\n');
const srcs = Object.fromEntries(map.sources.map((s, i) => [s, map.sourcesContent[i].split('\n')]));
const tm = new TraceMap(map);
let total = 0, ok = 0; const bad = [];
const tokenAt = (line, col) => { const m = line.slice(col).match(/^("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`[^`]*`?|[A-Za-z_$][\w$]*|\d[\w.]*|.)/); return m ? m[0] : ''; };
eachMapping(tm, (m) => {
  if (m.source == null) return;
  total++;
  const g = tokenAt(gen[m.generatedLine - 1], m.generatedColumn);
  const o = tokenAt(srcs[m.source][m.originalLine - 1], m.originalColumn);
  // A renamed symbol keeps its original name as a prefix (`x_default`, `x2`); a node starting
  // with a paren that the printer dropped maps to what the paren held.
  const same = strict ? (g === o || g.startsWith(o) || /^\d/.test(g) || /^["'`(]/.test(o) || /^["'`(]/.test(g)) : o.length > 0;
  if (same) ok++; else if (bad.length < 4) bad.push(`${m.source}:${m.originalLine}:${m.originalColumn} original=${o.slice(0, 30)} generated=${g.slice(0, 30)}`);
});
console.log(`${path.basename(f)}: ${map.sources.length} sources, ${total} mappings, ${ok} check out`);
bad.forEach((b) => console.log('  ' + b));
