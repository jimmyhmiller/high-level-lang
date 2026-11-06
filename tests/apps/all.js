import _ from "lodash-es";
console.log(_.VERSION, Object.keys(_).length);
console.log(JSON.stringify(_.chunk([1, 2, 3, 4, 5], 2)), _.camelCase("hello big world"));
console.log(_.chain([3, 1, 2]).sortBy().map((x) => x * 2).value().join());
console.log(_.template("hi <%= who %>")({ who: "there" }));
