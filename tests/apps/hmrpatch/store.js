function createStore(reduce) {
  let state = 0;
  return { dispatch: () => (state = reduce(state)) };
}
function reducer(state) {
  return state + 1;
}
export const store = createStore(reducer);

const base = 10;
function start() {
  return base;
}
export const initial = start();
