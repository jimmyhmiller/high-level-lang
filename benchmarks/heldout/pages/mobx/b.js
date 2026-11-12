import { makeAutoObservable, reaction, toJS, configure, computed } from "mobx";
configure({ enforceActions: "never" });
class S { xs = [1]; constructor() { makeAutoObservable(this); } get n() { return this.xs.length; } }
const s = new S(); const log = []; reaction(() => s.n, n => log.push(n)); s.xs.push(2); console.log(log.join(","), JSON.stringify(toJS(s)), computed(() => s.n * 2).get());
