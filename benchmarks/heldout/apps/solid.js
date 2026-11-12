import { createSignal, createMemo, createEffect, createRoot, batch } from "solid-js";
import { createStore as cs, produce } from "solid-js/store";
const log = [];
createRoot(dispose => {
  const [a, setA] = createSignal(1); const [b, setB] = createSignal(2);
  const sum = createMemo(() => a() + b());
  createEffect(() => log.push("sum " + sum()));
  batch(() => { setA(10); setB(20); });
  const [st, setSt] = cs({ todos: [{ t: "x", done: false }] });
  setSt("todos", 0, "done", true); setSt(produce(s => s.todos.push({ t: "y", done: false })));
  log.push(JSON.stringify(st.todos), sum()); dispose();
});
console.log(log.join("|"));
