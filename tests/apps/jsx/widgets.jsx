import React from "./react-default.js";
export const Tag = ({ title, children }) => <section title={title}>{children}</section>;
export const lib = { Item: (p) => <li {...p} />, deep: { Inner: () => <b>inner</b> } };
export default function Card() {
  return <>
    <h1>heading</h1>
    tail
  </>;
}
// Never used: a pure call that tree shaking should remove.
export const unused = <div>{"unused"}</div>;
