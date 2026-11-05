const e=require("esbuild"),fs=require("fs"),cp=require("child_process");
const n=f=>e.transformSync(fs.readFileSync(f,"utf8"),{loader:"js",legalComments:"none",minifyWhitespace:true}).code;
const [a,b]=process.argv.slice(2);fs.writeFileSync("/tmp/hl-a.js",n(a));fs.writeFileSync("/tmp/hl-b.js",n(b));
const r=cp.spawnSync("diff",["/tmp/hl-a.js","/tmp/hl-b.js"],{encoding:"utf8"});console.log(r.stdout.split("\n").slice(0,8).join("\n").slice(0,700));
