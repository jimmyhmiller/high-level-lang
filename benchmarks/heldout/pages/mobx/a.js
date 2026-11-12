import { observable, autorun, runInAction } from "mobx";
const o = observable({ a: 1 }); const log = []; autorun(() => log.push(o.a)); runInAction(() => { o.a = 2; }); console.log(log.join(","));
