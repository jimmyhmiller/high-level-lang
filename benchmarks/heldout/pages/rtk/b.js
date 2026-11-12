import { createSelector, nanoid, createAction } from "@reduxjs/toolkit";
const sel = createSelector([x => x.a, x => x.b], (a, b) => a + b); console.log(sel({ a: 1, b: 2 }), nanoid().length, createAction("x/y")(3).type);
