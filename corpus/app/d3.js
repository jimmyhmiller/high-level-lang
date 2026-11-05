import { scaleLinear, extent, mean, line } from "d3";
const s = scaleLinear().domain([0, 10]).range([0, 100]);
console.log(s(5), extent([3, 1, 2]).join(), mean([1, 2, 3]));
console.log(line()([[0, 0], [1, 1]]));
