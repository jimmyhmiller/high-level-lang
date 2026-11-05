/*! first legal */
//! line legal
/** @license MIT */
// @preserve kept
/* plain comment */
import { b } from "./b.js";
const s = "/*! not a comment */";
function f() {
  /*! inside function */
  return 1;
}
console.log(b, s, f());
