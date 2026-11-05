/** @jsx h */
/** @jsxFrag Fragment */
import { h, Fragment, render } from "preact";
const vnode = <div class="a"><>x</><span style={{ color: "red" }}>y</span></div>;
console.log(vnode.type, vnode.props.class, vnode.props.children.length, vnode.props.children[1].props.style.color);
