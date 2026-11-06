export const { p, q: [r, s = 7], ...others } = { p: 1, q: [2], t: 3, u: 4 };
export var [first, , third = 9] = [5, 6];
export function get() { return [p, r, s, others, first, third]; }
