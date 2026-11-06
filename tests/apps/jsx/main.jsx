import React from "./react-default.js";
import Card, { Tag, lib } from "./widgets";
const show = (x) => console.log(JSON.stringify(x));
const name = "world", n = 3, more = { a: 1, b: 2 }, list = [1, 2];
class Self { m() { return <this.Foo x="1" />; } Foo() {} }
show(<div />);
show(<div></div>);
show(<div a="1" b='2' c={3} d e="&amp;&lt;&#65;&#x41;&bogus;&;&nbsp;" />);
show(<a-b c-d="1" e:f="2" />);
show(<svg:rect xlink:href="#x" />);
show(<Tag title="t">x</Tag>);
show(<lib.Item key="k" />);
show(<lib.deep.Inner />);
show(new Self().m());
show(<div {...more} />);
show(<div x="1" {...more} y="2" {...more} />);
show(<div>hello</div>);
show(<div>  leading and trailing  </div>);
show(<div>
  multi
     line   text

  with blanks
</div>);
show(<div>   </div>);
show(<div>
</div>);
show(<div>a{name}b {n} c</div>);
show(<div>{name}{n}</div>);
show(<div>{name} {n}</div>);
show(<div>
  {name}
  {n}
</div>);
show(<div>{/* nothing */}</div>);
show(<div>{/* nothing */}x{ }</div>);
show(<div>{...list}</div>);
show(<div>=&gt;> no</div>.type === undefined ? 0 : 1);
show(<div>caf&eacute; &copy; é ☃ &#9731;</div>);
show(<div attr="line
break &amp; more" />);
show(<></>);
show(<>x</>);
show(<><a />{n}<b>c</b></>);
show(<div a=<b /> c=<></> />);
show(<div a={<b>{<c />}</b>} />);
show(<Card />);
show(n < 2 ? <a /> : <b />);
show(n < 5);
show(n > 5);
show([<a key="1" />, <b key="2" />]);
show((() => <a />)());
show(<div // comment
  a="1" /* block */ b="2"
/>);
show(<div>// not a comment /* neither */</div>);
show(<div>{`template ${name}`}</div>);
show(<div style={{ color: "red" }} onClick={() => n}>{list.map((x) => <i key={x}>{x}</i>)}</div>);
var A = { B: { C: "abc" } };
show(<A.B.C />);
function shadow(React) { return <div />; }
show(shadow({ createElement: (t) => "shadowed " + t }));
function keep() { return <_under /> || <$dollar />; }
var _under = 1, $dollar = 2;
show(keep());
show(<div>text</div>.children);
var é = "e";
show(<é />);
show(<Ünï />);
var Ünï = "u";
