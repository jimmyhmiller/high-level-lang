// First difference between acorn trees of two files, ignoring positions.
const acorn=require("acorn"),fs=require("fs");
const p=f=>{const c=fs.readFileSync(f,"utf8");return [acorn.parse(c,{ecmaVersion:"latest",sourceType:"script"}),c]};
const [[a,ca],[b,cb]]=process.argv.slice(2).map(p);
function d(x,y,path){if(x===y)return false;if(path.endsWith(".name")&&typeof x==="string"&&typeof y==="string"&&x.replace(/\d+$/,"")===y.replace(/\d+$/,""))return false;if(typeof x!=="object"||typeof y!=="object"||!x||!y){console.log(path,JSON.stringify(x)?.slice(0,80),"vs",JSON.stringify(y)?.slice(0,80));return true}
 for(const k of new Set([...Object.keys(x),...Object.keys(y)])){if(k==="start"||k==="end"||k==="raw")continue;if(d(x[k],y[k],path+"."+k)){if(x.start!==undefined&&!globalThis.done){globalThis.done=1;console.log("A:",ca.slice(x.start,Math.min(x.end,x.start+200)));console.log("B:",cb.slice(y.start,Math.min(y.end,y.start+200)))}return true}}return false}
d(a,b,"");
