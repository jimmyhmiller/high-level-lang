// Accepts its own updates: edit anything here and the page shows it without losing the count.
export function view(count) {
  return `
    <h1 style="font-family: system-ui; color: rebeccapurple">Hot module replacement</h1>
    <p style="font-family: system-ui">Clicked ${count} times.</p>
    <button style="font-size: 1.2em">Click</button>
  `;
}

if (import.meta.hot) {
  import.meta.hot.accept(() => globalThis.redraw());
}
