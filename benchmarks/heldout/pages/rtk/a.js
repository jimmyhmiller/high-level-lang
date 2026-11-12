import { configureStore, createSlice } from "@reduxjs/toolkit";
const s = createSlice({ name: "c", initialState: { n: 0 }, reducers: { inc(st) { st.n++; } } });
const store = configureStore({ reducer: s.reducer }); store.dispatch(s.actions.inc()); console.log(JSON.stringify(store.getState()));
