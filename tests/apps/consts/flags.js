// What the cases import: constants at the start of the file, one exported by name, one that is no
// constant (assigned), and what a namespace import reads.
export const isServer = false;
export const level = 2, tag = "srv";
const hidden = true;
export { hidden as shown };
export let changing = 1;
changing = 3;
console.log("flags ran");
