// Does this file parse at exactly this ECMAScript version? Lowering is only done if it does.
//   node tools/check-target.mjs FILE YEAR
import * as acorn from "acorn";
import fs from "node:fs";
const [, , file, year] = process.argv;
const text = fs.readFileSync(file, "utf8");
try {
  acorn.parse(text, { ecmaVersion: Number(year), sourceType: "script" });
  console.log("ok");
} catch (e) {
  console.log(`rejected at es${year}: ${e.message}: ${text.slice(Math.max(0, e.pos - 40), e.pos + 40)}`);
}
