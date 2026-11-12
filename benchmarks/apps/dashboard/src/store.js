// State as a stream of actions folded with immer, as a small redux-style store would have it.
import { BehaviorSubject, Subject, scan, startWith, map, distinctUntilChanged } from "rxjs";
import { produce } from "immer";
import { projects } from "./data.js";

function reduce(draft, action) {
  switch (action.type) {
    case "toggle": {
      const task = draft.projects.flatMap((p) => p.tasks).find((t) => t.id === action.id);
      if (task) task.done = !task.done;
      break;
    }
    case "assign": {
      for (const p of draft.projects) for (const t of p.tasks) if (t.id === action.id) t.assignee = action.who;
      break;
    }
    case "filter":
      draft.filter = action.text;
      break;
  }
}

export function createStore() {
  const actions = new Subject();
  const state = new BehaviorSubject({ projects, filter: "" });
  actions.pipe(scan((s, a) => produce(s, (d) => reduce(d, a)), state.value), startWith(state.value)).subscribe(state);
  return {
    dispatch: (a) => actions.next(a),
    get: () => state.value,
    select: (f) => state.pipe(map(f), distinctUntilChanged()),
  };
}
