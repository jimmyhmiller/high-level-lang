// Is the output syntactically valid? Report what esbuild says about it.
import * as esbuild from 'esbuild'; import fs from 'node:fs';
const f=process.argv[2]; const c=fs.readFileSync(f,'utf8');
try{esbuild.transformSync(c,{loader:'js',logLevel:'silent'});console.log('parses')}catch(e){const x=e.errors[0];console.log(x.text);console.log(x.location.lineText.slice(Math.max(0,x.location.column-120),x.location.column+80))}
