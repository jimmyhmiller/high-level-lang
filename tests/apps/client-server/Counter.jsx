"use client";

import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import { label, title } from "./shared.js";

export default function Counter({ initialCount }) {
  const [count, setCount] = useState(initialCount);
  return <section>
    <p>{title}</p>
    <button onClick={() => setCount(count + 1)}>{label(count)}</button>
    <p>The initial count came from the server. Clicking runs in the browser.</p>
  </section>;
}

export function mount(element, Component, props) {
  createRoot(element).render(<Component {...props} />);
}
