// First few differing lines between two output files, around where they first differ.
const fs=require("fs");const [a,b]=process.argv.slice(2,4).map(f=>fs.readFileSync(f,"utf8").split("\n"));
let shown=0,total=0;for(let i=0;i<Math.max(a.length,b.length);i++){if(a[i]!==b[i]){total++;if(shown++<(+process.argv[4]||4)){let j=0;const x=a[i]||"",y=b[i]||"";while(j<x.length&&x[j]===y[j])j++;console.log(`line ${i+1} ${x.split(" ")[0]}`);console.log("  A:",x.slice(Math.max(0,j-40),j+80));console.log("  B:",y.slice(Math.max(0,j-40),j+80))}}}console.log("lines differing:",total);
