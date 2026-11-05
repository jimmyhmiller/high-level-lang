const e=require("esbuild"),fs=require("fs");
const n=f=>e.transformSync(fs.readFileSync(f,"utf8"),{loader:"js",legalComments:"none",minifyWhitespace:true,logLevel:"silent"}).code;
const [a,b]=process.argv.slice(2);const x=n(a),y=n(b);let i=0;while(i<x.length&&x[i]===y[i])i++;
console.log("ORIG: "+x.slice(Math.max(0,i-50),i+60).replace(/\n/g,"\\n"));console.log("OURS: "+y.slice(Math.max(0,i-50),i+60).replace(/\n/g,"\\n"));
