import { win } from "./nodom.js";
import { jQueryFactory } from "jquery/factory";
const $ = jQueryFactory(win);
console.log(typeof $, $.fn.jquery, $.extend(true, {}, { a: { b: 1 } }, { a: { c: 2 } }).a.c, $.isPlainObject({}), $.map([1, 2, 3], x => x * 2).join(","), $.trim ? "trim" : "notrim", Object.keys($).length);
