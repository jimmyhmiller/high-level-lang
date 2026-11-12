import { observable, computed, autorun, action, runInAction, reaction, makeAutoObservable, toJS, configure } from "mobx";
configure({ enforceActions: "never" });
const log = [];
class Store { items = []; filter = ""; constructor() { makeAutoObservable(this); } get count() { return this.items.filter(i => i.includes(this.filter)).length; } add(x) { this.items.push(x); } }
const st = new Store();
autorun(() => log.push("count=" + st.count));
st.add("apple"); st.add("banana"); st.filter = "an";
const o = observable({ a: 1, b: { c: [1, 2] } });
const c = computed(() => o.a * 2);
reaction(() => o.b.c.length, n => log.push("len " + n));
runInAction(() => { o.a = 21; o.b.c.push(3); });
log.push(c.get(), JSON.stringify(toJS(o)));
console.log(log.join("|"));
