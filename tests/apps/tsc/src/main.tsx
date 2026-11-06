import { helper } from "@lib/helper";
import { Button } from "~ui";
import exact from "exact";
import fromBase from "lib/base-url";
import { OnlyType } from "@lib/types";
class Fields { x = 1; y: number; static s = 2; #p = 3; constructor() { console.log(Object.keys(this), this.#p); } }
new Fields();
console.log(helper(), exact, fromBase, typeof Button, (<Button label="x" />).type === Button, JSON.stringify(<b>{1}</b>.props));
