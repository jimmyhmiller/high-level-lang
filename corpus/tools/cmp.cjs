// usage: cmp.cjs ours.js esbuild.js expected-stdout
const acorn=require("acorn"),e=require("esbuild"),fs=require("fs"),cp=require("child_process");
const [ours,theirs,exp]=process.argv.slice(2);
const strip=(c)=>{for(const sourceType of["script","module"]){try{return JSON.stringify(acorn.parse(c,{ecmaVersion:"latest",sourceType}),(k,v)=>k==="start"||k==="end"||k==="raw"?undefined:v)}catch{}}return null};
const n=f=>e.transformSync(fs.readFileSync(f,"utf8"),{loader:"js",legalComments:"none",minifyWhitespace:true,logLevel:"silent"}).code;
let a,b;try{a=n(ours)}catch(x){console.log("OUR OUTPUT INVALID:",x.errors?.[0]?.text,x.errors?.[0]?.location?.lineText?.slice(Math.max(0,x.errors[0].location.column-60),x.errors[0].location.column+60));process.exit(1)}
b=n(theirs);
const r=cp.spawnSync("node",[ours],{encoding:"utf8"});const out=r.stdout+r.stderr;const expected=fs.readFileSync(exp,"utf8");
const tree=a===b?"":` sameTree=${strip(a)===strip(b)}`;
console.log(`bytes ours=${fs.statSync(ours).size} esbuild=${fs.statSync(theirs).size} normalized ours=${a.length} esbuild=${b.length} identical=${a===b}${tree} stdout-matches=${out===expected}`);
if(out!==expected){console.log("OUTPUT:",out.slice(0,400))}
if(a!==b&&strip(a)!==strip(b)){let i=0;while(i<a.length&&a[i]===b[i])i++;console.log("OURS   : "+a.slice(Math.max(0,i-70),i+70).replace(/\n/g,"\\n"));console.log("ESBUILD: "+b.slice(Math.max(0,i-70),i+70).replace(/\n/g,"\\n"))}
