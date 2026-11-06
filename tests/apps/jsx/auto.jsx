import { renderToStaticMarkup as render } from "react-dom/server";
import { Fragment as Frag } from "react";
const Item = ({ label, children }) => <li title={label}>{children}</li>;
const rest = { className: "c", id: "i" };
const list = ["a", "b"];
const jsx = "shadow";
function shadowing(jsxs) {
  return <div>{jsxs}<b>two</b></div>;
}
console.log(render(<div />));
console.log(render(<div {...rest} />));
console.log(render(<div {...rest} key="after" />));
console.log(render(<div key="before" {...rest} />));
console.log(render(<Item label="x">one</Item>));
console.log(render(<ul>{list.map((x) => <Item key={x} label={x}>{x}</Item>)}</ul>));
console.log(render(<>a<b>c</b></>));
console.log(render(<><i /></>));
console.log(render(<Frag>f</Frag>));
console.log(render(shadowing("arg")));
console.log(render(<p>{...list}</p>));
console.log(render(<p>{jsx}</p>));
export const unused = <div>{"gone"}</div>;
