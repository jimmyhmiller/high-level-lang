import { h, render, Component } from "preact";
class App extends Component { render({ who }) { return h("div", { class: "x" }, "hi ", who); } }
const vnode = h(App, { who: "there" });
console.log(typeof vnode.type, vnode.props.who, typeof render);
