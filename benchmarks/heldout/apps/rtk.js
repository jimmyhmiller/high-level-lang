import { configureStore, createSlice, createAsyncThunk, createSelector, nanoid, createEntityAdapter } from "@reduxjs/toolkit";
const adapter = createEntityAdapter();
const slice = createSlice({ name: "todos", initialState: adapter.getInitialState({ n: 0 }), reducers: { add: adapter.addOne, inc(s) { s.n++; } } });
const store = configureStore({ reducer: { todos: slice.reducer } });
store.dispatch(slice.actions.add({ id: "a", t: 1 })); store.dispatch(slice.actions.add({ id: "b", t: 2 })); store.dispatch(slice.actions.inc());
const sel = createSelector([s => s.todos.entities], e => Object.values(e).reduce((x, y) => x + y.t, 0));
const thunk = createAsyncThunk("x/y", async n => n * 2);
const r = await store.dispatch(thunk(21));
console.log(JSON.stringify(store.getState()), sel(store.getState()), r.type, r.payload, typeof nanoid());
